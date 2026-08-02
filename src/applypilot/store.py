"""Local storage. Everything personal is encrypted with a key held outside it.

SQLite holds opaque blobs; the key lives in a separate file. Ids and timestamps
stay in the clear so the panel can list applications without decrypting them
all, and nothing identifying is ever a plain column.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .models import ApplicationRecord, LearnedAnswer, Profile, RunState
from .security import Cipher, fingerprint, load_or_create_key
from .text import normalise

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    blob BLOB NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learned (
    normalised TEXT PRIMARY KEY,
    blob BLOB NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    blob BLOB NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.ensure_dirs()
        self._key = load_or_create_key(settings.key_path)
        self._cipher = Cipher(self._key)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(settings.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._cursor() as cur:
            cur.executescript(SCHEMA)

    # -- plumbing ---------------------------------------------------------

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._connection.cursor()
            try:
                yield cur
                self._connection.commit()
            finally:
                cur.close()

    @property
    def key_fingerprint(self) -> str:
        return fingerprint(self._key)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- generic encrypted values -----------------------------------------

    def get_value(self, key: str, default: Any = None) -> Any:
        with self._cursor() as cur:
            row = cur.execute("SELECT blob FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return self._cipher.decrypt_json(row["blob"])

    def set_value(self, key: str, value: Any) -> None:
        blob = self._cipher.encrypt_json(value)
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO kv (key, blob, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET blob = excluded.blob, "
                "updated_at = excluded.updated_at",
                (key, blob, _now_iso()),
            )

    def delete_value(self, key: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM kv WHERE key = ?", (key,))

    # -- profile ----------------------------------------------------------

    def get_profile(self) -> Profile:
        raw = self.get_value("profile")
        if not raw:
            return Profile()
        return Profile.model_validate(raw)

    def save_profile(self, profile: Profile) -> Profile:
        profile.updated_at = datetime.now(UTC)
        self.set_value("profile", json.loads(profile.model_dump_json()))
        return profile

    # -- learned answers --------------------------------------------------

    def get_learned(self) -> dict[str, LearnedAnswer]:
        with self._cursor() as cur:
            rows = cur.execute("SELECT normalised, blob FROM learned").fetchall()
        out: dict[str, LearnedAnswer] = {}
        for row in rows:
            out[row["normalised"]] = LearnedAnswer.model_validate(
                self._cipher.decrypt_json(row["blob"])
            )
        return out

    def learned_values(self) -> dict[str, str]:
        """The shape the mapper consumes: normalised question -> value."""
        return {key: answer.value for key, answer in self.get_learned().items()}

    def save_learned(self, answer: LearnedAnswer) -> LearnedAnswer:
        key = answer.normalised or normalise(answer.question)
        answer.normalised = key
        existing = self.get_learned().get(key)
        if existing:
            answer.times_seen = existing.times_seen + 1
        answer.updated_at = datetime.now(UTC)
        blob = self._cipher.encrypt_json(json.loads(answer.model_dump_json()))
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO learned (normalised, blob, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(normalised) DO UPDATE SET blob = excluded.blob, "
                "updated_at = excluded.updated_at",
                (key, blob, _now_iso()),
            )
        return answer

    def forget_learned(self, question: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM learned WHERE normalised = ?", (normalise(question),))

    def forget_all_learned(self) -> int:
        with self._cursor() as cur:
            count = cur.execute("SELECT COUNT(*) AS n FROM learned").fetchone()["n"]
            cur.execute("DELETE FROM learned")
        return int(count)

    # -- applications -----------------------------------------------------

    def list_applications(self) -> list[ApplicationRecord]:
        with self._cursor() as cur:
            rows = cur.execute(
                "SELECT blob FROM applications ORDER BY created_at DESC"
            ).fetchall()
        return [
            ApplicationRecord.model_validate(self._cipher.decrypt_json(row["blob"]))
            for row in rows
        ]

    def upsert_application(self, record: ApplicationRecord) -> ApplicationRecord:
        record.id = record.id or uuid.uuid4().hex
        record.updated_at = datetime.now(UTC)
        blob = self._cipher.encrypt_json(json.loads(record.model_dump_json()))
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO applications (id, blob, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "blob = excluded.blob, updated_at = excluded.updated_at",
                (record.id, blob, record.created_at.isoformat(), _now_iso()),
            )
        return record

    def find_application_by_url(self, url: str) -> ApplicationRecord | None:
        for record in self.list_applications():
            if record.url == url:
                return record
        return None

    def delete_application(self, application_id: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM applications WHERE id = ?", (application_id,))

    # -- documents --------------------------------------------------------

    def add_document(self, kind: str, filename: str, data: bytes) -> dict[str, str]:
        document_id = uuid.uuid4().hex
        suffix = Path(filename).suffix
        path = self.settings.documents_dir / f"{document_id}{suffix}"
        path.write_bytes(self._cipher.encrypt_text(data.decode("latin-1")))
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO documents (id, kind, filename, path, created_at) VALUES (?,?,?,?,?)",
                (document_id, kind, filename, str(path), _now_iso()),
            )
        return {"id": document_id, "kind": kind, "filename": filename}

    def list_documents(self) -> list[dict[str, str]]:
        with self._cursor() as cur:
            rows = cur.execute(
                "SELECT id, kind, filename, created_at FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def read_document(self, document_id: str) -> tuple[str, bytes] | None:
        with self._cursor() as cur:
            row = cur.execute(
                "SELECT filename, path FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            return None
        encrypted = Path(row["path"]).read_bytes()
        return row["filename"], self._cipher.decrypt_text(encrypted).encode("latin-1")

    def delete_document(self, document_id: str) -> None:
        with self._cursor() as cur:
            row = cur.execute(
                "SELECT path FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row:
                Path(row["path"]).unlink(missing_ok=True)
            cur.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    # -- run state --------------------------------------------------------

    def get_run(self) -> RunState:
        raw = self.get_value("run_state")
        if not raw:
            return RunState()
        return RunState.model_validate(raw)

    def save_run(self, state: RunState) -> RunState:
        state.updated_at = datetime.now(UTC)
        self.set_value("run_state", json.loads(state.model_dump_json()))
        return state

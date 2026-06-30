from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import CandidateProfile, ResumeDocument, ReusableAnswer
from .security import LocalCipher


class ProfileStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.cipher = LocalCipher(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reusable_answers (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def load(self) -> CandidateProfile:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM candidate_profile WHERE id = 1"
            ).fetchone()
        if row is None:
            return CandidateProfile()
        return CandidateProfile.model_validate(json.loads(self.cipher.decrypt(row[0])))

    def save(self, profile: CandidateProfile) -> CandidateProfile:
        self.initialize()
        payload = self.cipher.encrypt(profile.model_dump_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO candidate_profile (id, payload, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (payload,),
            )
        return profile

    def list_answers(self) -> list[ReusableAnswer]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM reusable_answers ORDER BY updated_at DESC"
            ).fetchall()
        return [
            ReusableAnswer.model_validate_json(self.cipher.decrypt(row[0]))
            for row in rows
        ]

    def save_answer(self, answer: ReusableAnswer) -> ReusableAnswer:
        self.initialize()
        payload = self.cipher.encrypt(answer.model_dump_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reusable_answers (id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (answer.id, payload),
            )
        return answer

    def delete_answer(self, answer_id: str) -> bool:
        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM reusable_answers WHERE id = ?", (answer_id,)
            )
        return cursor.rowcount > 0

    def save_resume(self, resume: ResumeDocument) -> ResumeDocument:
        self.initialize()
        payload = self.cipher.encrypt(resume.model_dump_json())
        with self._connect() as connection:
            connection.execute("UPDATE resumes SET active = 0")
            connection.execute(
                """
                INSERT INTO resumes (id, filename, sha256, payload, active, uploaded_at)
                VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(sha256) DO UPDATE SET
                    id = excluded.id,
                    filename = excluded.filename,
                    payload = excluded.payload,
                    active = 1,
                    uploaded_at = CURRENT_TIMESTAMP
                """,
                (resume.id, "encrypted", resume.sha256, payload),
            )
        return resume

    def get_active_resume(self) -> ResumeDocument | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM resumes WHERE active = 1 ORDER BY uploaded_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return ResumeDocument.model_validate_json(self.cipher.decrypt(row[0]))

    def list_resumes(self) -> list[ResumeDocument]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM resumes ORDER BY uploaded_at DESC"
            ).fetchall()
        return [ResumeDocument.model_validate_json(self.cipher.decrypt(row[0])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

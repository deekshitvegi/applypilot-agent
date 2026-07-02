from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import (
    ApplicationRecord,
    CandidateProfile,
    ResumeDocument,
    ReusableAnswer,
    TailoredArtifact,
    ProviderConfigRequest,
)
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
                CREATE TABLE IF NOT EXISTS tailored_artifacts (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_files (
                    sha256 TEXT PRIMARY KEY,
                    payload BLOB NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get_provider_config(self) -> ProviderConfigRequest | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM provider_config WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return ProviderConfigRequest.model_validate_json(self.cipher.decrypt(row[0]))

    def save_provider_config(self, config: ProviderConfigRequest) -> None:
        self.initialize()
        payload = self.cipher.encrypt(config.model_dump_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_config (id, payload, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (payload,),
            )

    def delete_provider_config(self) -> bool:
        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM provider_config WHERE id = 1")
        return cursor.rowcount > 0

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

    def save_resume_file(self, sha256: str, content: bytes) -> None:
        self.initialize()
        payload = self.cipher.encrypt_bytes(content)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO resume_files (sha256, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(sha256) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (sha256, payload),
            )

    def get_resume_file(self, sha256: str) -> bytes | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM resume_files WHERE sha256 = ?", (sha256,)
            ).fetchone()
        return self.cipher.decrypt_bytes(row[0]) if row else None

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

    def save_application(self, application: ApplicationRecord) -> ApplicationRecord:
        self.initialize()
        payload = self.cipher.encrypt(application.model_dump_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO applications (id, status, payload, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (application.id, application.status, payload),
            )
        return application

    def get_application(self, application_id: str) -> ApplicationRecord | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
        if row is None:
            return None
        return ApplicationRecord.model_validate_json(self.cipher.decrypt(row[0]))

    def list_applications(self) -> list[ApplicationRecord]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM applications ORDER BY updated_at DESC"
            ).fetchall()
        return [
            ApplicationRecord.model_validate_json(self.cipher.decrypt(row[0]))
            for row in rows
        ]

    def save_tailored_artifact(self, artifact: TailoredArtifact) -> TailoredArtifact:
        self.initialize()
        payload = self.cipher.encrypt(artifact.model_dump_json())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tailored_artifacts (id, application_id, payload, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    application_id = excluded.application_id,
                    payload = excluded.payload
                """,
                (artifact.id, artifact.application_id, payload),
            )
        return artifact

    def get_tailored_artifact(self, artifact_id: str) -> TailoredArtifact | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM tailored_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            return None
        return TailoredArtifact.model_validate_json(self.cipher.decrypt(row[0]))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

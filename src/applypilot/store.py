from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import CandidateProfile


class ProfileStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

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

    def load(self) -> CandidateProfile:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM candidate_profile WHERE id = 1"
            ).fetchone()
        if row is None:
            return CandidateProfile()
        return CandidateProfile.model_validate(json.loads(row[0]))

    def save(self, profile: CandidateProfile) -> CandidateProfile:
        self.initialize()
        payload = profile.model_dump_json()
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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)


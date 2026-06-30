from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = os.getenv("APPLYPILOT_HOST", "127.0.0.1")
    port: int = int(os.getenv("APPLYPILOT_PORT", "8765"))
    database_path: Path = Path(
        os.getenv("APPLYPILOT_DATABASE_PATH", "data/applypilot.sqlite3")
    )


settings = Settings()


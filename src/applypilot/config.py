from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = os.getenv("APPLYPILOT_HOST", "127.0.0.1")
    port: int = int(os.getenv("APPLYPILOT_PORT", "8765"))
    database_path: Path = Path(
        os.getenv("APPLYPILOT_DATABASE_PATH", "data/applypilot.sqlite3")
    )
    demo_mode: bool = env_flag("APPLYPILOT_DEMO_MODE")


settings = Settings()

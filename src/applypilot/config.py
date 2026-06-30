from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


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
    ai_provider: str = os.getenv("APPLYPILOT_AI_PROVIDER", "gemini")
    ai_model: str = os.getenv("APPLYPILOT_AI_MODEL", "gemini-2.5-flash")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")


settings = Settings()

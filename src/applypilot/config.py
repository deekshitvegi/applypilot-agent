"""Where things live and how the service is configured.

Everything personal lands in a per-user data directory outside the repository,
so a public checkout can never contain a profile, a database or a key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"


def default_data_dir() -> Path:
    """The per-user directory holding the database, key file and documents."""
    override = os.environ.get("APPLYPILOT_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ApplyPilot"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "applypilot"
    return Path.home() / ".local" / "share" / "applypilot"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    model_provider: str = "gemini"
    model_name: str = "gemini-3.5-flash-lite"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "applypilot.sqlite3"

    @property
    def key_path(self) -> Path:
        """The encryption key lives beside the database but never inside it."""
        return self.data_dir / "applypilot.key"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    port = int(os.environ.get("APPLYPILOT_PORT", DEFAULT_PORT))
    return Settings(
        data_dir=default_data_dir(),
        host=os.environ.get("APPLYPILOT_HOST", DEFAULT_HOST),
        port=port,
        model_provider=os.environ.get("APPLYPILOT_MODEL_PROVIDER", "gemini"),
        model_name=os.environ.get("APPLYPILOT_MODEL_NAME", "gemini-3.5-flash-lite"),
    )

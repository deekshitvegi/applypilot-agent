from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class LocalCipher:
    """Encrypt personal data at rest with a key kept outside the database."""

    def __init__(self, database_path: Path, key: str = "") -> None:
        self.key_path = database_path.with_suffix(database_path.suffix + ".key")
        self.configured_key = key or os.getenv("APPLYPILOT_DATA_KEY", "")
        self._fernet: Fernet | None = None

    def encrypt(self, value: str) -> str:
        return self._get_fernet().encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._get_fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            # Backward compatibility for databases created before encryption existed.
            if value.lstrip().startswith(("{", "[")):
                return value
            raise ValueError("Candidate data could not be decrypted with the local key") from None

    def _get_fernet(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet

        if self.configured_key:
            key = self.configured_key.encode("ascii")
        elif self.key_path.exists():
            key = self.key_path.read_bytes().strip()
        else:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass

        self._fernet = Fernet(key)
        return self._fernet

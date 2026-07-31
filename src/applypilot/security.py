"""Encryption at rest for everything personal.

The key is a file next to the database, never a column inside it and never a
value in the repository. Losing the key means losing the profile, which is the
intended trade: a stolen database on its own is inert.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(RuntimeError):
    """Raised when stored bytes cannot be read with the current key."""


def _restrict_permissions(path: Path) -> None:
    """Make the key file owner-readable only, as far as the platform allows."""
    with contextlib.suppress(OSError):  # platform dependent
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def load_or_create_key(key_path: Path) -> bytes:
    """Return the Fernet key at *key_path*, generating one on first run."""
    if key_path.exists():
        raw = key_path.read_bytes().strip()
        if raw:
            return raw
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    _restrict_permissions(key_path)
    return key


class Cipher:
    """Symmetric encryption for the values the store keeps."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @classmethod
    def from_key_file(cls, key_path: Path) -> Cipher:
        return cls(load_or_create_key(key_path))

    def encrypt_text(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt_text(self, token: bytes) -> str:
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken as exc:  # pragma: no cover - depends on a swapped key
            raise DecryptionError(
                "Stored data could not be decrypted with the current key file."
            ) from exc

    def encrypt_json(self, value: Any) -> bytes:
        return self.encrypt_text(json.dumps(value, separators=(",", ":"), sort_keys=True))

    def decrypt_json(self, token: bytes) -> Any:
        return json.loads(self.decrypt_text(token))


def fingerprint(key: bytes) -> str:
    """A short, non-reversible identifier for a key, safe to show in the panel."""
    import hashlib

    digest = hashlib.sha256(key).digest()[:6]
    return base64.b32encode(digest).decode("ascii").rstrip("=").lower()

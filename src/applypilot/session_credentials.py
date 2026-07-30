"""Session-scoped sign-in details for employer sites.

Held in memory for the life of the running companion only: never written to
the database, never logged, and gone when the service restarts. The user
supplies them at the start of a session and they are released to the extension
only for an exact host match on a page already confirmed to be that site's
sign-in form.

Deliberately supports signing **in** to an existing account. Creating accounts
is not automated: that involves accepting an employer's terms on the user's
behalf, which stays a human decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SessionCredential:
    host: str
    username: str
    password: str


def normalize_host(value: str) -> str:
    """Registrable host for a URL or bare hostname, lowercased, no port."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "//" not in text:
        text = f"https://{text}"
    host = (urlparse(text).hostname or "").strip(".")
    return re.sub(r"^www\.", "", host)


class SessionCredentialVault:
    """In-memory credential holder with exact-host release."""

    def __init__(self) -> None:
        self._entries: dict[str, SessionCredential] = {}

    def save(self, host: str, username: str, password: str) -> str:
        normalized = normalize_host(host)
        if not normalized:
            raise ValueError("A site host is required, for example 'myworkdayjobs.com'.")
        if not username or not password:
            raise ValueError("Both a username and a password are required.")
        self._entries[normalized] = SessionCredential(normalized, username, password)
        return normalized

    def hosts(self) -> list[dict[str, str]]:
        """Saved hosts and usernames. Never returns a password."""
        return [
            {"host": entry.host, "username": entry.username}
            for entry in sorted(self._entries.values(), key=lambda item: item.host)
        ]

    def resolve(self, page_url: str) -> SessionCredential | None:
        """Return the credential for this page, or None.

        Matching is exact on the registrable host, or a subdomain of it. A
        near-miss returns nothing: typing a password into the wrong site's form
        is the failure mode that matters most here.
        """
        host = normalize_host(page_url)
        if not host:
            return None
        best: SessionCredential | None = None
        for stored_host, entry in self._entries.items():
            matches_host = host == stored_host or host.endswith(f".{stored_host}")
            if matches_host and (best is None or len(stored_host) > len(best.host)):
                best = entry
        return best

    def forget(self, host: str) -> bool:
        return self._entries.pop(normalize_host(host), None) is not None

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

"""Session-scoped sign-in, without the service ever holding a secret.

The default path is the browser's own password manager, and it stays the
default. When session-scoped details are used instead, they live in the side
panel's memory for as long as the panel is open and go no further: not to this
service, not to the database, not to a log file. Nothing here is a secret store.

What this module does is decide whether a sign-in may be released at all. It
answers one question -- "is the page in front of us the sign-in form of exactly
the host these details were registered for?" -- and it answers it strictly:

* the host must match **exactly**, label for label, so a lookalike such as
  ``example.com.evil.test`` gets nothing;
* the page must already have been classified as a sign-in form, so a
  registration page (which would be creating an account) gets nothing;
* the release is for signing **in** and nothing else;
* an authorisation is single-use and expires.

Creating an account is never done here. That accepts an employer's terms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .adapters import host_of
from .models import PageKind

#: How long an authorisation stays good for, in seconds.
AUTHORISATION_TTL = 15 * 60


@dataclass
class Authorisation:
    """Permission to release sign-in details for exactly one host.

    Holds no secret: only which host the applicant said it was for.
    """

    host: str
    granted_at: float = field(default_factory=time.time)
    used: bool = False

    @property
    def expired(self) -> bool:
        return time.time() - self.granted_at > AUTHORISATION_TTL


@dataclass
class Decision:
    allowed: bool
    reason: str


class SessionSignIn:
    """In-memory only. Restarting the service forgets everything here."""

    def __init__(self) -> None:
        self._authorisations: dict[str, Authorisation] = {}

    def authorise(self, url_or_host: str) -> Authorisation:
        host = _host(url_or_host)
        authorisation = Authorisation(host=host)
        self._authorisations[host] = authorisation
        return authorisation

    def revoke(self, url_or_host: str = "") -> None:
        if url_or_host:
            self._authorisations.pop(_host(url_or_host), None)
        else:
            self._authorisations.clear()

    def authorised_hosts(self) -> list[str]:
        return [h for h, a in self._authorisations.items() if not a.expired]

    def may_release(self, url: str, page_kind: PageKind) -> Decision:
        """Whether sign-in details may be put on the page in front of us."""
        host = _host(url)
        if not host:
            return Decision(False, "there is no host to check against")

        if page_kind is PageKind.REGISTRATION:
            return Decision(
                False,
                "this is an account creation page. Creating an account accepts the "
                "employer's terms, so that is yours to do. I will fill everything "
                "except the password.",
            )
        if page_kind is not PageKind.SIGN_IN:
            return Decision(False, "this page has not been confirmed as a sign-in form")

        authorisation = self._authorisations.get(host)
        if authorisation is None:
            # Exact match only. Never a suffix, never "close enough".
            return Decision(
                False,
                f"no sign-in details were set for {host} in this session",
            )
        if authorisation.expired:
            self._authorisations.pop(host, None)
            return Decision(False, f"the sign-in details for {host} have expired")
        if authorisation.used:
            return Decision(False, f"the sign-in details for {host} were already used once")

        authorisation.used = True
        return Decision(True, f"{host} matches exactly and this page is its sign-in form")


def _host(url_or_host: str) -> str:
    value = (url_or_host or "").strip().lower()
    if "://" in value:
        return host_of(value)
    return value.removeprefix("www.").split("/")[0]


def same_host(left: str, right: str) -> bool:
    """Exact host equality. ``example.com.evil.test`` is not ``example.com``."""
    return bool(_host(left)) and _host(left) == _host(right)

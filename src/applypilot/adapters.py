from __future__ import annotations

from urllib.parse import urlparse

ATS_HOST_SUFFIXES = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "icims.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "jobvite.com",
    "workable.com",
    "bamboohr.com",
    "breezy.hr",
    "teamtailor.com",
    "recruitee.com",
    "successfactors.com",
    "taleo.net",
    "oraclecloud.com",
    "paylocity.com",
    "dayforcehcm.com",
)

# Job boards that list roles. They are sources to read, never trusted
# application destinations in their own right.
_BOARD_ADAPTERS = {
    "linkedin.com": "linkedin",
    "indeed.com": "indeed",
    "dice.com": "dice",
    "glassdoor.com": "glassdoor",
    "ziprecruiter.com": "ziprecruiter",
    "monster.com": "monster",
    "simplyhired.com": "simplyhired",
}

_ATS_ADAPTERS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "myworkdayjobs.com": "workday",
    "ashbyhq.com": "ashby",
    "smartrecruiters.com": "smartrecruiters",
    "icims.com": "icims",
    "jobvite.com": "jobvite",
    "workable.com": "workable",
}


def _matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def detect_adapter(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for suffix, name in {**_BOARD_ADAPTERS, **_ATS_ADAPTERS}.items():
        if _matches(host, suffix):
            return name
    return "generic"


def is_job_board(url: str) -> bool:
    """True for listing sites, whose own pages are never an application form."""
    host = (urlparse(url).hostname or "").lower()
    return any(_matches(host, suffix) for suffix in _BOARD_ADAPTERS)


def is_recognized_ats_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(_matches(host, suffix) for suffix in ATS_HOST_SUFFIXES)

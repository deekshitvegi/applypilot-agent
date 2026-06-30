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
)


def detect_adapter(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return "linkedin"
    if host == "greenhouse.io" or host.endswith(".greenhouse.io"):
        return "greenhouse"
    if host == "lever.co" or host.endswith(".lever.co"):
        return "lever"
    if host == "myworkdayjobs.com" or host.endswith(".myworkdayjobs.com"):
        return "workday"
    return "generic"


def is_recognized_ats_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in ATS_HOST_SUFFIXES)

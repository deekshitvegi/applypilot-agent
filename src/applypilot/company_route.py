"""Find an employer's own application page for a job seen on a job board.

A listing that only offers Easy Apply still usually exists on the employer's
own ATS. This module derives candidate board URLs from the company name,
**verifies** each one actually belongs to that company, and looks for the
matching posting. Nothing here is employer-specific: candidates come from the
company name and the recognised ATS host list, and an unverified guess is
never returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse

from .adapters import is_recognized_ats_url

# Legal suffixes and listing decorations that are not part of a board slug.
_COMPANY_NOISE = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|co|gmbh|bv|plc|sa|ag|pty|holdings|group|labs|technologies|technology|software|systems)\b",
    re.IGNORECASE,
)
_YC_BATCH = re.compile(r"\((?:yc\s*)?[swf]\d{2}\)", re.IGNORECASE)

# Board URL templates. Each must resolve to a recognised ATS host so the
# result passes the existing routing verification.
_BOARD_TEMPLATES = (
    "https://jobs.ashbyhq.com/{slug}",
    "https://job-boards.greenhouse.io/{slug}",
    "https://boards.greenhouse.io/{slug}",
    "https://jobs.lever.co/{slug}",
    "https://apply.workable.com/{slug}",
    "https://{slug}.recruitee.com",
    "https://jobs.smartrecruiters.com/{slug}",
)


@dataclass(frozen=True)
class CompanyRoute:
    """A verified employer application URL."""

    url: str
    board_url: str
    company: str
    matched_title: str
    confidence: float


def normalize_company(value: str) -> str:
    text = _YC_BATCH.sub(" ", str(value or ""))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    text = _COMPANY_NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def company_slugs(company: str) -> list[str]:
    """Candidate board slugs, most likely first."""
    normalized = normalize_company(company)
    if not normalized:
        return []
    words = normalized.split()
    joined = "".join(words)
    hyphenated = "-".join(words)
    slugs = [joined, hyphenated]
    if len(words) > 1:
        slugs.append(words[0])
    return [slug for slug in dict.fromkeys(slugs) if len(slug) >= 2]


def candidate_board_urls(company: str) -> list[str]:
    urls: list[str] = []
    for slug in company_slugs(company):
        urls.extend(template.format(slug=slug) for template in _BOARD_TEMPLATES)
    return list(dict.fromkeys(urls))


def _title_similarity(left: str, right: str) -> float:
    a = re.sub(r"[^a-z0-9 ]+", " ", left.lower()).strip()
    b = re.sub(r"[^a-z0-9 ]+", " ", right.lower()).strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def board_belongs_to_company(html: str, company: str) -> bool:
    """Guard against slug collisions between unrelated employers."""
    normalized = normalize_company(company)
    if not normalized:
        return False
    haystack = re.sub(r"[^a-z0-9]+", " ", html.lower())
    # Require the distinctive part of the name, not a single common word.
    target = normalized.replace(" ", "")
    return target in haystack.replace(" ", "") or normalized in haystack


def find_posting_url(html: str, board_url: str, title: str) -> tuple[str, str, float]:
    """Best matching posting link on a board page."""
    best = ("", "", 0.0)
    for match in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL
    ):
        href, inner = match.group(1), match.group(2)
        text = re.sub(r"<[^>]+>", " ", inner)
        text = re.sub(r"\s+", " ", text).strip()
        if not text or len(text) > 160:
            continue
        score = _title_similarity(title, text)
        if score > best[2]:
            best = (urljoin(board_url, href), text, score)
    return best


def resolve_company_application_url(
    company: str,
    title: str,
    fetch,
    minimum_title_score: float = 0.6,
) -> CompanyRoute | None:
    """Resolve an employer application URL, or ``None`` when unverified.

    ``fetch(url)`` returns ``(status_code, text)`` or raises. Callers supply it
    so this stays testable and so network policy lives in one place.
    """
    if not str(company or "").strip():
        return None
    for board_url in candidate_board_urls(company):
        try:
            status, html = fetch(board_url)
        except Exception:  # noqa: BLE001, S112 - an unreachable candidate is simply a miss
            continue
        if status != 200 or not html:
            continue
        if not board_belongs_to_company(html, company):
            continue
        posting_url, matched_title, score = find_posting_url(html, board_url, title)
        if posting_url and score >= minimum_title_score and is_recognized_ats_url(posting_url):
            return CompanyRoute(
                url=posting_url,
                board_url=board_url,
                company=company,
                matched_title=matched_title,
                confidence=round(score, 3),
            )
        # The board is confirmed to be the employer's even when the exact
        # posting is not matched; that is still better than an aggregator.
        if is_recognized_ats_url(board_url):
            return CompanyRoute(
                url=board_url,
                board_url=board_url,
                company=company,
                matched_title="",
                confidence=0.5,
            )
    return None


def safe_public_url(url: str) -> bool:
    """Reject non-HTTPS and loopback/private targets before fetching."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost"} or host.endswith(".local"):
        return False
    return not re.match(r"^(127\.|10\.|192\.168\.|169\.254\.|0\.)", host)

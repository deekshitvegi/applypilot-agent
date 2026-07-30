"""Company-application-page discovery for board listings.

The user's requirement: even when a LinkedIn job offers Easy Apply, apply on
the employer's own site instead. These tests cover deriving candidate boards
from a company name, refusing unverified guesses, and matching the posting.
"""

from __future__ import annotations

from applypilot.company_route import (
    board_belongs_to_company,
    candidate_board_urls,
    company_slugs,
    normalize_company,
    resolve_company_application_url,
    safe_public_url,
)

BOARD_HTML = """
<html><head><title>Acme Robotics Jobs</title></head><body>
  <h1>Acme Robotics</h1>
  <a href="/acmerobotics/1234-abcd">AI Research Engineer</a>
  <a href="/acmerobotics/5678-efgh">Staff Frontend Engineer</a>
</body></html>
"""


def test_company_slugs_drop_legal_suffixes_and_batch_tags() -> None:
    assert normalize_company("Cumulus Labs (YC W26)") == "cumulus"
    assert normalize_company("Acme Robotics, Inc.") == "acme robotics"
    assert company_slugs("Acme Robotics, Inc.")[:2] == ["acmerobotics", "acme-robotics"]


def test_candidate_urls_only_target_recognised_ats_hosts() -> None:
    urls = candidate_board_urls("Acme Robotics")
    assert any("jobs.ashbyhq.com/acmerobotics" in url for url in urls)
    assert any("greenhouse.io/acmerobotics" in url for url in urls)
    assert all(url.startswith("https://") for url in urls)


def test_resolves_the_matching_posting_on_a_verified_board() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if url == "https://jobs.ashbyhq.com/acmerobotics":
            return 200, BOARD_HTML
        return 404, ""

    route = resolve_company_application_url("Acme Robotics", "AI Research Engineer", fetch)

    assert route is not None
    assert route.url == "https://jobs.ashbyhq.com/acmerobotics/1234-abcd"
    assert route.matched_title == "AI Research Engineer"
    assert route.confidence >= 0.9


def test_rejects_a_board_belonging_to_a_different_company() -> None:
    # A slug collision must not send an application to the wrong employer.
    def fetch(_url: str) -> tuple[int, str]:
        return 200, "<html><body><h1>Totally Different Corp</h1></body></html>"

    assert resolve_company_application_url("Acme Robotics", "AI Research Engineer", fetch) is None


def test_returns_nothing_when_no_board_responds() -> None:
    def fetch(_url: str) -> tuple[int, str]:
        raise OSError("unreachable")

    assert resolve_company_application_url("Acme Robotics", "AI Engineer", fetch) is None


def test_falls_back_to_the_verified_board_when_the_title_does_not_match() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if url == "https://jobs.ashbyhq.com/acmerobotics":
            return 200, BOARD_HTML
        return 404, ""

    route = resolve_company_application_url("Acme Robotics", "Chief Dog Walker", fetch)

    assert route is not None
    assert route.url == "https://jobs.ashbyhq.com/acmerobotics"
    assert route.matched_title == ""


def test_board_ownership_check_requires_the_company_name() -> None:
    assert board_belongs_to_company(BOARD_HTML, "Acme Robotics") is True
    assert board_belongs_to_company(BOARD_HTML, "Globex Industries") is False


def test_refuses_loopback_and_plaintext_targets() -> None:
    assert safe_public_url("https://jobs.ashbyhq.com/acme") is True
    assert safe_public_url("http://jobs.ashbyhq.com/acme") is False
    assert safe_public_url("https://127.0.0.1/acme") is False
    assert safe_public_url("https://localhost/acme") is False
    assert safe_public_url("https://192.168.1.5/acme") is False

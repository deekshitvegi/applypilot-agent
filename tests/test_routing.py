"""Regressions 22 and 24, plus the adapter gaps the site survey turned up."""

from __future__ import annotations

import pytest

from applypilot.adapters import classify_host, detect_adapter, registrable_domain
from applypilot.models import HostRole, PageKind
from applypilot.routing import RouteCandidate, choose_route, decide

# ---------------------------------------------------------------------------
# 22. Host identity is decided from the URL, never by a model.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "adapter"),
    [
        ("https://boards.greenhouse.io/acme/jobs/4012345", "greenhouse"),
        ("https://job-boards.greenhouse.io/acme/jobs/4012345", "greenhouse"),
        ("https://jobs.lever.co/acme/6f2b", "lever"),
        ("https://jobs.ashbyhq.com/acme/8ac1", "ashby"),
        ("https://acme.wd1.myworkdayjobs.com/en-US/careers/job/Austin/ML-Engineer_R-1", "workday"),
        ("https://jobs.smartrecruiters.com/Acme/744000", "smartrecruiters"),
        ("https://apply.workable.com/acme/j/4C1B2/", "workable"),
        ("https://acme.recruitee.com/o/ml-engineer", "recruitee"),
        ("https://career5.successfactors.eu/career?company=acme", "successfactors"),
        ("https://careers.acme.com/us/en/job/1234/ML-Engineer", None),
        ("https://acme.icims.com/jobs/9912/ml-engineer/job", "icims"),
        ("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/x.html", "adp"),
    ],
)
def test_known_hiring_systems_are_recognised(url, adapter):
    found = detect_adapter(url)
    assert (found.name if found else None) == adapter


def test_workable_is_no_longer_generic():
    """The survey found this falling back to the generic adapter."""
    assert detect_adapter("https://apply.workable.com/acme/").name == "workable"


def test_phenom_is_recognised_from_the_page_when_the_host_is_the_employers_own():
    url = "https://careers.acme.com/us/en/job/1234/ML-Engineer"
    assert detect_adapter(url) is None
    assert detect_adapter(url, ["marker:phenom"]).name == "phenom"
    assert detect_adapter(url, ["cdn.phenompeople.com"]).name == "phenom"


@pytest.mark.parametrize(
    ("url", "role"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", HostRole.EMPLOYER),
        ("https://www.linkedin.com/jobs/view/4012345", HostRole.BOARD),
        ("https://www.indeed.com/viewjob?jk=abc", HostRole.BOARD),
        ("https://www.dice.com/job-detail/abc", HostRole.BOARD),
        ("https://jackandjill.ai/jobs/abc", HostRole.AGGREGATOR),
        ("https://some-unknown-host.test/apply", HostRole.THIRD_PARTY),
    ],
)
def test_host_roles_come_from_the_url(url, role):
    assert classify_host(url).role is role


def test_the_employers_own_domain_counts_as_the_employer():
    identity = classify_host("https://careers.acme.com/us/en/job/1", expected_company="Acme Inc.")
    assert identity.role is HostRole.EMPLOYER


def test_a_lookalike_host_is_not_the_employer():
    identity = classify_host("https://boards.greenhouse.io.evil.test/acme/jobs/1")
    assert identity.role is HostRole.THIRD_PARTY
    assert identity.adapter == "generic"


def test_a_listing_on_a_board_never_stops_the_run():
    """A model asked whether a listing 'belongs to the expected employer' said
    no, correctly, and the runner halted on the page it was meant to start from."""
    decision = decide(
        "https://www.linkedin.com/jobs/view/4012345",
        PageKind.LISTING,
        expected_company="Acme",
        expected_title="Machine Learning Engineer",
    )
    assert decision.action != "stop"


def test_an_unknown_host_is_the_only_thing_worth_stopping_on():
    decision = decide("https://who-is-this.test/apply/1", PageKind.UNKNOWN)
    assert decision.action == "stop"


def test_an_application_form_is_applied_to_wherever_it_is():
    decision = decide("https://who-is-this.test/apply/1", PageKind.APPLICATION)
    assert decision.action == "apply_here"


def test_registrable_domain_handles_compound_suffixes():
    assert registrable_domain("careers.acme.co.uk") == "acme.co.uk"
    assert registrable_domain("boards.greenhouse.io") == "greenhouse.io"


# ---------------------------------------------------------------------------
# 24. A board match on the company alone is not a route.
# ---------------------------------------------------------------------------


def test_a_company_only_board_match_never_beats_the_listings_own_apply_link():
    # apply.workable.com/bausch is BAUSCH+LOMB HELLAS, the Greek subsidiary.
    subsidiary = RouteCandidate(
        url="https://apply.workable.com/bausch/",
        source="board_company_only",
        company="BAUSCH+LOMB HELLAS",
    )
    own_link = RouteCandidate(
        url="https://careers.bauschlomb.com/job/1234",
        source="listing_apply",
        company="Bausch + Lomb",
        title="Machine Learning Engineer",
    )
    best, ranked = choose_route(
        [subsidiary, own_link], expected_company="Bausch + Lomb",
        expected_title="Machine Learning Engineer",
    )
    assert best is not None
    assert best.url == own_link.url
    assert ranked[-1].url == subsidiary.url


def test_a_company_only_board_match_is_not_followed_on_its_own():
    subsidiary = RouteCandidate(
        url="https://apply.workable.com/bausch/",
        source="board_company_only",
        company="BAUSCH+LOMB HELLAS",
    )
    best, ranked = choose_route([subsidiary], expected_company="Bausch + Lomb")
    assert best is None
    assert ranked and "not the role" in ranked[0].reason


def test_a_board_match_claiming_a_title_it_does_not_have_is_demoted():
    pretender = RouteCandidate(
        url="https://apply.workable.com/bausch/",
        source="board_company_and_title",
        company="Bausch + Lomb",
        title="Warehouse Associate",
    )
    best, _ = choose_route(
        [pretender], expected_company="Bausch + Lomb", expected_title="Machine Learning Engineer"
    )
    assert best is None


def test_a_board_match_on_company_and_role_is_followed():
    candidate = RouteCandidate(
        url="https://boards.greenhouse.io/acme/jobs/1",
        source="board_company_and_title",
        company="Acme",
        title="Machine Learning Engineer",
    )
    best, _ = choose_route(
        [candidate], expected_company="Acme", expected_title="Machine Learning Engineer"
    )
    assert best is not None


def test_a_constructed_url_never_wins_on_its_own():
    """A hand-assembled apply endpoint redirected to a careers home page; the
    posting's own button reached a 46-field form."""
    guess = RouteCandidate(
        url="https://careers.acme.com/talentcommunity/apply/9912/",
        source="constructed",
        company="Acme",
        title="Machine Learning Engineer",
    )
    best, _ = choose_route([guess], expected_company="Acme", expected_title="Machine Learning Engineer")
    assert best is None


def test_the_posting_link_wins_even_against_a_full_board_match():
    own_link = RouteCandidate(
        url="https://careers.acme.com/job/1", source="listing_apply",
        company="Acme", title="Machine Learning Engineer",
    )
    board = RouteCandidate(
        url="https://boards.greenhouse.io/acme/jobs/1", source="board_company_and_title",
        company="Acme", title="Machine Learning Engineer",
    )
    best, _ = choose_route(
        [board, own_link], expected_company="Acme", expected_title="Machine Learning Engineer"
    )
    assert best.url == own_link.url


# ---------------------------------------------------------------------------
# Sign-in and registration hand back rather than pressing on.
# ---------------------------------------------------------------------------


def test_a_sign_in_page_hands_back():
    decision = decide("https://workforcenow.adp.com/x", PageKind.SIGN_IN)
    assert decision.action == "ask"
    assert "sign in" in decision.message.lower()


def test_a_registration_page_says_what_it_will_and_will_not_do():
    decision = decide("https://career5.successfactors.eu/register", PageKind.REGISTRATION)
    assert decision.action == "ask"
    assert "except" in decision.message

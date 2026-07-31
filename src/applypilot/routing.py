"""Getting to the employer's own application.

From a listing on a job board, the destination is the employer's own posting.
The way there is the employer's own Apply control, because a URL guessed from a
pattern lands on a careers home page often enough to matter: one apply endpoint
put together by hand redirected away, while pressing the button on the posting
reached a 46-field form.

A search of a board for the same company is a fallback, and a fallback that only
matched the company -- not the role -- is not a fallback at all. Matching a
company slug alone once routed an application to a Greek subsidiary that shares
the first word of its parent's name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .adapters import HostIdentity, classify_host, company_slug
from .models import HostRole, PageKind
from .text import content_tokens, normalise

#: Where a route came from, and how much that origin is worth.
SOURCE_SCORES = {
    #: The Apply control on the posting being looked at. Always preferred.
    "listing_apply": 1000,
    #: A posting found by searching a board for this company and this role.
    "board_company_and_title": 700,
    #: A posting found by company alone. Never enough on its own.
    "board_company_only": 300,
    #: An apply URL assembled from a pattern. Last resort.
    "constructed": 150,
}

#: Below this a route is offered as a suggestion and never followed on its own.
FOLLOW_THRESHOLD = 700


@dataclass
class RouteCandidate:
    url: str
    source: str
    company: str = ""
    title: str = ""
    label: str = ""
    company_match: float = 0.0
    title_match: float = 0.0
    identity: HostIdentity | None = None
    score: int = 0
    reason: str = ""


def _overlap(left: str, right: str) -> float:
    a, b = set(content_tokens(left)), set(content_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def score_candidate(
    candidate: RouteCandidate, expected_company: str, expected_title: str
) -> RouteCandidate:
    candidate.identity = classify_host(candidate.url, expected_company)
    candidate.company_match = _overlap(candidate.company or "", expected_company)
    candidate.title_match = _overlap(candidate.title or "", expected_title)

    source = candidate.source
    if source == "board_company_and_title" and candidate.title_match < 0.34:
        # It only looked like a title match. Demote it rather than trust it.
        source = "board_company_only"

    score = SOURCE_SCORES.get(source, 0)

    if candidate.identity.role is HostRole.EMPLOYER:
        score += 60
    elif candidate.identity.role in {HostRole.BOARD, HostRole.AGGREGATOR}:
        score -= 120

    slug = company_slug(expected_company)
    if slug and slug in company_slug(candidate.company or candidate.identity.domain):
        score += 20

    candidate.score = max(0, score)
    candidate.reason = _explain(candidate, source)
    return candidate


def _explain(candidate: RouteCandidate, source: str) -> str:
    if source == "listing_apply":
        return "the posting's own apply control"
    if source == "board_company_and_title":
        return "a board listing matching both the company and the role"
    if source == "board_company_only":
        return (
            "a board listing matching the company but not the role, which is not "
            "enough to tell a parent company from a subsidiary"
        )
    return "a URL assembled from a pattern, which often lands on a careers home page"


def choose_route(
    candidates: list[RouteCandidate], expected_company: str = "", expected_title: str = ""
) -> tuple[RouteCandidate | None, list[RouteCandidate]]:
    """The route to follow, plus everything considered, best first."""
    scored = [score_candidate(c, expected_company, expected_title) for c in candidates]
    scored.sort(key=lambda c: (-c.score, c.url))
    if not scored:
        return None, []
    best = scored[0]
    if best.score < FOLLOW_THRESHOLD:
        return None, scored
    return best, scored


@dataclass
class RoutingDecision:
    action: str  # "apply_here" | "follow" | "search" | "ask" | "stop"
    url: str = ""
    message: str = ""
    identity: HostIdentity | None = None
    candidates: list[RouteCandidate] = field(default_factory=list)


def decide(
    url: str,
    kind: PageKind,
    expected_company: str = "",
    expected_title: str = "",
    candidates: list[RouteCandidate] | None = None,
    hints: list[str] | None = None,
    prefer_easy_apply: bool = False,
) -> RoutingDecision:
    """What to do next, decided without asking a model anything.

    A model may describe this page. It does not get to decide whether the run
    stops on it.
    """
    identity = classify_host(url, expected_company, hints)

    if kind is PageKind.APPLICATION:
        return RoutingDecision(
            action="apply_here",
            url=url,
            identity=identity,
            message=f"this is an application form on {identity.host} -- {identity.reason}",
        )

    if kind is PageKind.SIGN_IN:
        return RoutingDecision(
            action="ask",
            url=url,
            identity=identity,
            message=(
                f"{identity.host} wants you signed in before it will show the application. "
                "Sign in in the browser and I will carry on."
            ),
        )

    if kind is PageKind.REGISTRATION:
        return RoutingDecision(
            action="ask",
            url=url,
            identity=identity,
            message=(
                f"{identity.host} wants an account created. I will fill everything except "
                "the password -- creating the account accepts their terms, so that part is yours."
            ),
        )

    if identity.role is HostRole.THIRD_PARTY and kind not in {PageKind.LISTING, PageKind.BOARD}:
        return RoutingDecision(
            action="stop",
            url=url,
            identity=identity,
            message=f"I do not recognise {identity.host}: {identity.reason}",
        )

    if identity.role is HostRole.BOARD and prefer_easy_apply and kind is PageKind.LISTING:
        return RoutingDecision(
            action="apply_here",
            url=url,
            identity=identity,
            message="you asked me to prefer the board's own quick apply",
        )

    best, considered = choose_route(candidates or [], expected_company, expected_title)
    if best is not None:
        return RoutingDecision(
            action="follow",
            url=best.url,
            identity=identity,
            candidates=considered,
            message=f"going to the employer's own posting via {best.reason}",
        )

    if considered:
        top = considered[0]
        return RoutingDecision(
            action="ask",
            url=url,
            identity=identity,
            candidates=considered,
            message=(
                f"the closest I found is {top.url}, but it is {top.reason}. "
                "Do you want me to use it?"
            ),
        )

    return RoutingDecision(
        action="search",
        url=url,
        identity=identity,
        message=f"no apply control on this {kind.value} page; looking for the employer's posting",
    )


def normalise_company(name: str) -> str:
    return normalise(name)

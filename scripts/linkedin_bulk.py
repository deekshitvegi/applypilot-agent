"""Enough real application forms from LinkedIn to be worth measuring.

One search gives about forty postings and a handful of companies, and most of
those turn out to be on the three job boards this already handles well. The
forms worth testing against are the other ones -- every large employer runs its
own hiring system, and each draws its questions differently.

So this sweeps: many searches rather than one, every company that comes back,
and the boards biased away from the three that are already easy. What comes out
is a targets file of application forms, weighted towards the systems that are
not Greenhouse, Lever or Ashby.

    python scripts/linkedin_bulk.py --want 250
    python scripts/linkedin_bulk.py --want 250 --include-major
    python scripts/apply.py --targets corpus/linkedin_bulk.json --limit 250

Nothing signs in. LinkedIn is read through the pages it serves to anyone, and
every form found is one the employer publishes for anyone to read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_board  # noqa: E402
import linkedin_targets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "corpus" / "linkedin_bulk.json"
SEEN = ROOT / "corpus" / "linkedin_companies.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}

SEARCH = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location={location}&start={start}"
)

#: The company's own LinkedIn slug, off the link on each result card.
#:
#: Better than the name printed beside it. "Hewlett Packard Enterprise" has to
#: be guessed at -- hewlettpackardenterprise, hpe, hp -- while the slug is
#: hewlett-packard-enterprise, which is the shape boards are filed under
#: already, and it is not translated or abbreviated per card.
_CARD_COMPANY = re.compile(r'linkedin\.com/company/([a-z0-9][a-z0-9-]{1,60})')

#: One search returns ten cards and stops answering somewhere past three
#: hundred. Breadth has to come from asking different questions, not from
#: paging further, so the sweep varies both the words and the place.
KEYWORDS = (
    "AI Engineer", "Machine Learning Engineer", "Software Engineer",
    "Data Scientist", "Backend Engineer", "Full Stack Engineer",
    "Platform Engineer", "MLOps Engineer", "Research Engineer",
    "Data Engineer", "Python Developer", "Solutions Engineer",
)
LOCATIONS = (
    "United States", "Texas, United States", "California, United States",
    "New York, United States", "Remote", "Illinois, United States",
    "Washington, United States", "Massachusetts, United States",
)

#: The three this already fills well. Kept out by default: a corpus made of
#: them measures the same code path over and over.
MAJOR = {"greenhouse", "lever", "ashby"}


def fetch(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def company_names(keywords: str, location: str, pages: int, pause: float) -> list[str]:
    """Every company named on the cards of one search."""
    names: list[str] = []
    for page in range(pages):
        url = SEARCH.format(
            keywords=urllib.parse.quote(keywords),
            location=urllib.parse.quote(location),
            start=page * 10,
        )
        try:
            body = fetch(url)
        except (urllib.error.URLError, OSError, TimeoutError):
            break
        found = [slug.replace("-", " ") for slug in _CARD_COMPANY.findall(body)]
        if not found:
            break
        names.extend(found)
        time.sleep(pause)
    return names


def sweep(want_companies: int, pages: int, pause: float) -> list[str]:
    """Company names from many searches, deduplicated, in the order met."""
    seen: dict[str, None] = {}
    for location in LOCATIONS:
        for keywords in KEYWORDS:
            for name in company_names(keywords, location, pages, pause):
                cleaned = " ".join(name.split())
                if cleaned and cleaned.lower() not in {k.lower() for k in seen}:
                    seen[cleaned] = None
            print(
                f"  {len(seen):4} companies after {keywords!r} in {location!r}",
                flush=True,
            )
            if len(seen) >= want_companies:
                return list(seen)
    return list(seen)


def forms_for(company: str, per_company: int) -> list[dict]:
    """Application forms for one company, whichever system it is on."""
    resolved = find_board.find(company)
    system = resolved["system"]
    if not system:
        return []
    if system == "workday":
        return linkedin_targets.workday_openings(resolved["url"], company, per_company)
    return linkedin_targets.openings(system, company, per_company)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--want", type=int, default=250, help="how many forms")
    parser.add_argument("--per-company", type=int, default=4)
    parser.add_argument("--pages", type=int, default=4, help="search pages per query")
    parser.add_argument("--pause", type=float, default=0.6)
    parser.add_argument(
        "--include-major",
        action="store_true",
        help="keep Greenhouse, Lever and Ashby too",
    )
    parser.add_argument(
        "--companies",
        default="",
        help="a saved company list, instead of sweeping LinkedIn again",
    )
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    # Enough companies that the ones with a reachable board add up to the
    # number of forms wanted. Roughly a third answer, and each gives a few.
    want_companies = max(60, (args.want // max(1, args.per_company)) * 4)
    print(f"sweeping LinkedIn for ~{want_companies} companies\n")
    companies = sweep(want_companies, args.pages, args.pause)
    SEEN.write_text(json.dumps(companies, indent=1), encoding="utf-8")
    print(f"\n{len(companies)} companies -> {SEEN}\n")

    targets: list[dict] = []
    by_system: dict[str, int] = {}
    for index, company in enumerate(companies, 1):
        if len(targets) >= args.want:
            break
        found = forms_for(company, args.per_company)
        if not found:
            continue
        system = found[0]["ats"]
        if system in MAJOR and not args.include_major:
            print(f"  [{index}] {company[:28]:30} {system} -- skipped, already easy")
            continue
        targets.extend(found)
        by_system[system] = by_system.get(system, 0) + len(found)
        print(f"  [{index}] {company[:28]:30} {system:16} {len(found)} form(s)"
              f"   [{len(targets)}/{args.want}]", flush=True)

    Path(args.out).write_text(json.dumps(targets, indent=1), encoding="utf-8")
    print(f"\n{len(targets)} application forms -> {args.out}")
    for system, count in sorted(by_system.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4}  {system}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

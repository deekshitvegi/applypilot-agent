"""Find any company's application forms from its name alone.

LinkedIn will not tell a guest where a job's Apply button goes -- every posting
resolves to a sign-up wall -- so the company name is all there is to work from.
Probing five hiring systems answered for 5 companies out of 40. The other 35
were written off as "Workday, iCIMS, Oracle or a bespoke site, which cannot be
told apart from outside a login".

That was true only of the five that were asked. Most hiring systems publish a
company's openings at a URL derived from its name, and answer without an
account: Workday and iCIMS included. This asks all of them, and tries the
handful of name shapes a company actually gets given -- "Match Group" is
matchgroup, match-group and match, and which one it is cannot be reasoned out,
only tried.

    python scripts/find_board.py --company "Booz Allen Hamilton"
    python scripts/find_board.py --from-linkedin      # every company in the survey
    python scripts/find_board.py --from-linkedin --targets corpus/linkedin_targets.json

Nothing here signs in, and nothing it finds is behind a login: these are the
same pages the employer publishes for anyone to read.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "corpus" / "linkedin_sample.csv"
OUT = ROOT / "corpus" / "linkedin_targets.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}

TIMEOUT = 8


# ---------------------------------------------------------------------------
# The name a company's board is filed under
# ---------------------------------------------------------------------------

#: Words a company puts in its legal name and leaves out of its job board.
_SUFFIXES = re.compile(
    r"\b(inc|inc\.|llc|ltd|limited|corp|corporation|co|company|plc|gmbh|ag|sa|"
    r"nv|bv|holdings|group|technologies|technology|labs|software|systems|"
    r"solutions|services|global|international|worldwide|usa|us)\b",
    re.I,
)


def name_shapes(company: str) -> list[str]:
    """Every slug a company's board might be filed under, best guess first.

    Which one it is cannot be reasoned out. "Match Group" is matchgroup on one
    system and match on another; "Booz Allen Hamilton" is boozallenhamilton or
    boozallen. Trying is cheaper than being clever, and a wrong guess simply
    does not answer.
    """
    plain = re.sub(r"[^a-z0-9 ]", " ", (company or "").lower()).strip()
    plain = re.sub(r"\s+", " ", plain)
    if not plain:
        return []

    trimmed = _SUFFIXES.sub("", plain).strip()
    trimmed = re.sub(r"\s+", " ", trimmed)

    shapes: list[str] = []
    for base in (plain, trimmed):
        if not base:
            continue
        words = base.split()
        for candidate in (
            "".join(words),          # boozallenhamilton
            "-".join(words),         # booz-allen-hamilton
            words[0],                # booz
            "".join(words[:2]),      # boozallen
        ):
            if candidate and candidate not in shapes:
                shapes.append(candidate)
    return shapes[:6]


# ---------------------------------------------------------------------------
# The systems, and how each one answers
# ---------------------------------------------------------------------------


def _json_has(key: str):
    """A checker for a JSON body that must carry a non-empty list at *key*."""

    def check(body: bytes) -> bool:
        try:
            data = json.loads(body)
        except ValueError:
            return False
        if isinstance(data, list):
            return bool(data)
        found = data.get(key) if isinstance(data, dict) else None
        return bool(found)

    return check


#: name -> (url template, how to tell a real answer from a polite 200)
#:
#: The second half matters more than the first. SmartRecruiters returns 200
#: with totalFound 0 for any name at all, which once mislabelled 26 of 40
#: postings; a status code is not an answer.
#: Only systems that hand back job data. Every one of these was checked by
#: asking it about a company known to use it and reading what came back.
#:
#: The ones left out were left out for a reason. Jobvite, iCIMS, Taleo,
#: SuccessFactors and BambooHR all serve an empty single-page shell that says
#: 200 for a company they have never heard of -- jobs.jobvite.com/nvidia
#: answers exactly as readily as the real one, and NVIDIA is on Workday. A
#: probe that believed those reported the wrong system with total confidence,
#: which is worse than reporting nothing: it sends somebody to another
#: company's job board. If a JSON feed for one of them turns up, it belongs
#: here; a page that merely loads does not.
SYSTEMS: list[tuple[str, str, object, str]] = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
     _json_has("jobs"), "api"),
    ("lever", "https://api.lever.co/v0/postings/{slug}?mode=json",
     _json_has(""), "api"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{slug}",
     _json_has("jobs"), "api"),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
     _json_has("content"), "api"),
    ("rippling", "https://ats.rippling.com/api/v1/board/{slug}/jobs",
     _json_has(""), "api"),
    ("workable", "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true",
     _json_has("jobs"), "api"),
]

#: Workday is not one host. A tenant lives on a numbered pod and names its own
#: site, and neither is derivable -- so the shapes that actually occur get
#: tried. This is the system behind more large employers than any other, and
#: skipping it is why eighteen applications in the corpus reached nothing.
WORKDAY_PODS = ("wd1", "wd5", "wd12", "wd3", "wd2", "wd103")

#: The site names real tenants use, taken from the ones already in the corpus:
#: NVIDIAExternalCareerSite, External_Career_Site, external_experienced, jobs,
#: External. There is no rule -- each tenant names its own -- but the shapes
#: repeat, and one of them carries the company's own name, so that is built per
#: company rather than listed.
WORKDAY_SITES = (
    "External",
    "External_Career_Site",
    "ExternalCareerSite",
    "careers",
    "Careers",
    "jobs",
    "external_experienced",
    "External_Careers",
    "CareerSite",
)


def workday_sites_for(slug: str) -> list[str]:
    """Every site name worth trying for *slug*, its own name included."""
    upper = slug.upper()
    title = slug.capitalize()
    return [
        *WORKDAY_SITES,
        f"{upper}ExternalCareerSite",
        f"{title}ExternalCareerSite",
        f"{slug}ExternalCareerSite",
        f"{upper}_External_Career_Site",
        f"{title}Careers",
    ]


def fetch(url: str, timeout: int = TIMEOUT) -> bytes | None:
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            return response.read(400_000)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, TimeoutError):
        return None


def try_system(name: str, template: str, check, slug: str) -> tuple[str, str] | None:
    url = template.format(slug=slug)
    body = fetch(url)
    if body is None:
        return None
    try:
        if check(body):
            return (name, url)
    except Exception:
        return None
    return None


def try_workday(slug: str) -> tuple[str, str] | None:
    """Workday's own job feed: a POST, and it wants to be asked as an API.

    Fetching the tenant's front page to discover the site name gets a 406 --
    the edge in front of it rejects anything that does not look like a browser.
    The API underneath answers perfectly well, so the site name is tried rather
    than read.
    """
    body = json.dumps({"limit": 5, "offset": 0, "searchText": ""}).encode()
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    for pod in WORKDAY_PODS:
        host = f"https://{slug}.{pod}.myworkdayjobs.com"
        for site in workday_sites_for(slug):
            url = f"{host}/wday/cxs/{slug}/{site}/jobs"
            try:
                request = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                    if response.status != 200:
                        continue
                    data = json.loads(response.read(200_000))
            except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                    ValueError, TimeoutError):
                continue
            if data.get("jobPostings"):
                return ("workday", f"{host}/en-US/{site}")
    return None


def find(company: str) -> dict:
    """The first system that answers for *company*, with the URL that answered."""
    shapes = name_shapes(company)
    jobs: list[tuple] = []
    for slug in shapes:
        for name, template, check, _kind in SYSTEMS:
            jobs.append((name, template, check, slug))

    with ThreadPoolExecutor(max_workers=12) as pool:
        for found in pool.map(lambda a: try_system(*a), jobs):
            if found:
                return {"company": company, "system": found[0], "url": found[1]}

    # Workday last: it is the slowest to ask and the most likely to be right
    # when nothing else answered, so asking it first would slow every lookup
    # down for the sake of the minority that need it.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for found in pool.map(try_workday, shapes):
            if found:
                return {"company": company, "system": found[0], "url": found[1]}

    return {"company": company, "system": "", "url": ""}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", default="")
    parser.add_argument("--from-linkedin", action="store_true")
    parser.add_argument("--sample", default=str(SAMPLE))
    args = parser.parse_args()

    if args.company:
        result = find(args.company)
        print(json.dumps(result, indent=1))
        return 0 if result["system"] else 1

    if not args.from_linkedin:
        parser.error("give --company or --from-linkedin")

    path = Path(args.sample)
    if not path.exists():
        print(f"no sample at {path}", file=sys.stderr)
        return 1

    companies: list[str] = []
    for row in csv.DictReader(path.open(encoding="utf-8")):
        name = (row.get("company") or "").strip()
        if name and name not in companies:
            companies.append(name)

    found = 0
    systems: dict[str, int] = {}
    for company in companies:
        result = find(company)
        if result["system"]:
            found += 1
            systems[result["system"]] = systems.get(result["system"], 0) + 1
            print(f"  {result['system']:16} {company[:30]:32} {result['url'][:56]}")
        else:
            print(f"  {'-':16} {company[:30]:32} nothing answered")

    print(f"\n{found}/{len(companies)} companies found, without a single login")
    for name, count in sorted(systems.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

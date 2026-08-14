"""Turn a LinkedIn search into application forms that can actually be opened.

LinkedIn will not tell a guest where a job's Apply button goes. Every posting
surveyed resolved to the same place -- linkedin.com/signup/cold-join -- so the
destination is genuinely unavailable without an account, and reading it out of
a signed-in session at volume is scraping somebody's account into a ban.

It does not have to. The survey already showed the way: a company name is
public on the guest page, and the hiring systems publish their own openings at
a slug derived from that name. So the name is the key, and the employer's own
system hands over the apply URL directly -- no login, no rate limit, no
guessing at a redirect.

    python scripts/linkedin_survey.py --keywords "AI Engineer" --sample 60
    python scripts/linkedin_targets.py
    python scripts/apply.py --targets corpus/linkedin_targets.json

What comes out is a targets file in the same shape corpus.py writes, so
everything downstream already knows how to read it.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_board  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "corpus" / "linkedin_sample.csv"
OUT = ROOT / "corpus" / "linkedin_targets.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}

#: How each system is asked for a company's openings, and how an apply URL is
#: built from one. Only the systems that publish a board without an account.
BOARDS = {
    "greenhouse": {
        "jobs": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "pick": lambda data: data.get("jobs") or [],
        "url": lambda job, slug: f"https://boards.greenhouse.io/{slug}/jobs/{job['id']}#app",
        "title": lambda job: job.get("title", ""),
    },
    "lever": {
        "jobs": "https://api.lever.co/v0/postings/{slug}?mode=json",
        "pick": lambda data: data if isinstance(data, list) else [],
        "url": lambda job, slug: f"{job.get('hostedUrl', '').rstrip('/')}/apply",
        "title": lambda job: job.get("text", ""),
    },
    "ashby": {
        "jobs": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "pick": lambda data: data.get("jobs") or [],
        "url": lambda job, slug: f"{job.get('jobUrl', '').rstrip('/')}/application",
        "title": lambda job: job.get("title", ""),
    },
    "smartrecruiters": {
        "jobs": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
        "pick": lambda data: data.get("content") or [],
        # Two things were wrong with the obvious URL. These paths are
        # case-sensitive and the company's real name is capitalised -- the API
        # answers to a lowercase slug but the site does not, so the lowercase
        # one 404s. And the posting is a description, not a form: the form is
        # the one-click publication, keyed by the posting's uuid rather than
        # its id. The identifier comes back in the posting itself, so neither
        # has to be guessed at.
        "url": lambda job, slug: (
            "https://jobs.smartrecruiters.com/oneclick-ui/company/"
            f"{(job.get('company') or {}).get('identifier') or slug}"
            f"/publication/{job.get('uuid')}"
        ),
        "title": lambda job: job.get("name", ""),
    },
}


def slugify(company: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (company or "").lower())


def workday_openings(board_url: str, company: str, per_company: int) -> list[dict]:
    """Jobs from a Workday tenant, given the site find_board resolved.

    Workday is the system behind more large employers than any other and it was
    the whole of the "cannot be told apart from outside a login" bucket. It can:
    the feed is a POST and it answers without an account. What could not be
    guessed was the site name, and that is what find_board resolves.
    """
    # https://tenant.wd5.myworkdayjobs.com/en-US/SiteName
    parts = urllib.parse.urlsplit(board_url)
    host = f"{parts.scheme}://{parts.netloc}"
    tenant = parts.netloc.split(".")[0]
    site = parts.path.rstrip("/").split("/")[-1]
    body = json.dumps({"limit": per_company, "offset": 0, "searchText": ""}).encode()
    try:
        request = urllib.request.Request(
            f"{host}/wday/cxs/{tenant}/{site}/jobs",
            data=body,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []

    out = []
    for job in (data.get("jobPostings") or [])[:per_company]:
        path = job.get("externalPath") or ""
        if not path:
            continue
        out.append(
            {
                "ats": "workday",
                "company": company,
                "title": str(job.get("title", ""))[:90],
                "url": f"{host}/en-US/{site}{path}",
                "from": "linkedin",
            }
        )
    return out


def fetch(url: str, timeout: int = 12):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            return None
        return json.load(response)


def openings(system: str, company: str, per_company: int) -> list[dict]:
    """Real apply URLs for *company* on *system*, or []."""
    board = BOARDS.get(system)
    if board is None:
        return []
    slug = slugify(company)
    if not slug:
        return []
    try:
        data = fetch(board["jobs"].format(slug=slug))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    if not data:
        return []

    out = []
    for job in board["pick"](data)[:per_company]:
        try:
            url = board["url"](job, slug)
        except (KeyError, AttributeError, TypeError):
            continue
        if not url or not url.startswith("http"):
            continue
        out.append(
            {
                "ats": system,
                "company": company,
                "title": str(board["title"](job))[:90],
                "url": url,
                "from": "linkedin",
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(SAMPLE))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--per-company", type=int, default=3)
    args = parser.parse_args()

    path = Path(args.sample)
    if not path.exists():
        print(f"no sample at {path}; run linkedin_survey.py first", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    targets: list[dict] = []
    reachable = unreachable = 0
    seen_company: set[str] = set()

    for row in rows:
        company = (row.get("company") or "").strip()
        if not company or slugify(company) in seen_company:
            continue
        seen_company.add(slugify(company))

        # Ask every system that publishes a board, under every name shape the
        # company might be filed under. The survey's own guess covered five
        # systems and one spelling; this covers Workday too, which is most of
        # what "cannot be told apart from outside a login" actually was.
        resolved = find_board.find(company)
        system = resolved["system"]
        if not system:
            unreachable += 1
            print(f"  {'-':16} {company[:26]:28} no board answered")
            continue

        if system == "workday":
            found = workday_openings(resolved["url"], company, args.per_company)
        else:
            found = openings(system, company, args.per_company)
        if found:
            targets.extend(found)
            reachable += 1
            print(f"  {system:16} {company[:26]:28} {len(found)} opening(s)")
        else:
            unreachable += 1
            print(f"  {system:16} {company[:26]:28} board answered nothing")

    Path(args.out).write_text(json.dumps(targets, indent=1), encoding="utf-8")
    print(f"\nfrom {len(rows)} LinkedIn postings:")
    print(f"  {reachable} companies had a board that answered")
    print(f"  {unreachable} did not -- Workday, iCIMS, Oracle or a bespoke site,")
    print("    which cannot be told apart from outside a login")
    print(f"\n{len(targets)} application forms -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

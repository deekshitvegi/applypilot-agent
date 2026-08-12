"""Where LinkedIn jobs actually lead, measured rather than feared.

A search says "1,000+ jobs" and every posting looks like its own form. This
samples real postings from LinkedIn's public guest pages -- the ones shown to
anyone, no account involved -- follows each "apply" destination, and counts
which hiring system sits behind it.

The point is the distribution. Thousands of postings funnel into a handful of
systems, and covering a system covers every company on it.

  python scripts/linkedin_survey.py --keywords "AI Engineer" --sample 40

Writes corpus/linkedin_sample.csv, one row per posting.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "corpus" / "linkedin_sample.csv"

#: LinkedIn's own public endpoints -- the guest view, same as an incognito tab.
SEARCH = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location={location}&f_TPR=r2592000&start={start}"
)
POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

#: Hostname fragments that name the system behind a careers page.
SYSTEMS = [
    ("greenhouse", "greenhouse.io"),
    ("lever", "lever.co"),
    ("ashby", "ashbyhq.com"),
    ("workday", "myworkday"),
    ("icims", "icims.com"),
    ("oracle", "oraclecloud.com"),
    ("adp", "adp.com"),
    ("rippling", "rippling.com"),
    ("smartrecruiters", "smartrecruiters.com"),
    ("successfactors", "successfactors"),
    ("taleo", "taleo.net"),
    ("workable", "workable.com"),
    ("jobvite", "jobvite.com"),
    ("bamboohr", "bamboohr.com"),
    ("recruitee", "recruitee.com"),
    ("teamtailor", "teamtailor.com"),
    ("dover", "dover.com"),
    ("greenhouse", "grnh.se"),
]

_JOB_ID = re.compile(r"jobPosting:(\d+)")
_APPLY_URL = re.compile(r'<code id="applyUrl">\s*<!--"(.*?)"-->', re.DOTALL)
_TITLE = re.compile(r'<h2[^>]*top-card-layout__title[^>]*>\s*([^<]+)', re.DOTALL)
_COMPANY = re.compile(r'topcard__org-name-link[^>]*>\s*([^<]+)', re.DOTALL)


#: Which board answers to this company's name. Asked once per company.
_PROBED: dict[str, str] = {}

_FEEDS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
    ("lever", "https://api.lever.co/v0/postings/{slug}?mode=json"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{slug}"),
    ("rippling", "https://ats.rippling.com/api/v1/board/{slug}/jobs"),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{slug}/postings"),
]


def probe_company(company: str) -> str:
    """Guess the system from the company's name, by asking each system.

    The boards publish their openings at a slug derived from the company name,
    so a name that answers on one of them settles it. A name that answers
    nowhere is reported as exactly that rather than guessed at: it is usually
    Workday, iCIMS, Oracle or a bespoke careers site, none of which can be
    told apart from outside a login.
    """
    slug = re.sub(r"[^a-z0-9]", "", (company or "").lower())
    if not slug:
        return "external (company unknown)"
    if slug in _PROBED:
        return _PROBED[slug]
    found = "external (behind a login or bespoke)"
    for name, template in _FEEDS:
        try:
            request = urllib.request.Request(template.format(slug=slug), headers=HEADERS)
            with urllib.request.urlopen(request, timeout=8) as response:
                if response.status != 200:
                    continue
                body = response.read(4000).decode("utf-8", errors="replace")
                # Answering at all is not the same as knowing the company.
                # SmartRecruiters says 200 to any name and puts "totalFound: 0"
                # in the body, which mislabelled twenty-six of forty postings
                # in one run of this survey.
                if '"totalFound":0' in body.replace(" ", ""):
                    continue
                if len(body) > 20:
                    found = name
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        finally:
            time.sleep(0.3)
    _PROBED[slug] = found
    return found


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def classify(url: str) -> str:
    host = urllib.parse.urlsplit(url).netloc.lower()
    for name, fragment in SYSTEMS:
        if fragment in host or fragment in url.lower():
            return name
    if "linkedin.com" in host:
        return "linkedin wrapper"
    return f"company site ({host})"


def survey(keywords: str, location: str, sample: int, pause: float) -> int:
    job_ids: list[str] = []
    start = 0
    while len(job_ids) < sample and start <= 75:
        url = SEARCH.format(
            keywords=urllib.parse.quote(keywords),
            location=urllib.parse.quote(location),
            start=start,
        )
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"search page {start}: {err}")
            break
        found = _JOB_ID.findall(page)
        job_ids.extend(j for j in found if j not in job_ids)
        if not found:
            break
        start += 25
        time.sleep(pause)
    job_ids = job_ids[:sample]
    print(f"sampled {len(job_ids)} postings for {keywords!r}\n")

    rows: list[dict] = []
    for index, job_id in enumerate(job_ids, 1):
        time.sleep(pause)
        try:
            page = fetch(POSTING.format(job_id=job_id))
        except (urllib.error.URLError, TimeoutError) as err:
            rows.append({"job_id": job_id, "system": f"unreachable ({err})"})
            continue
        title = html.unescape((_TITLE.search(page) or [None, ""])[1]).strip()
        company = html.unescape((_COMPANY.search(page) or [None, ""])[1]).strip()
        matched = _APPLY_URL.search(page)
        if matched:
            destination = html.unescape(matched.group(1)).replace("\\/", "/")
            system = classify(destination)
        elif "offsite" in page:
            # The guest page no longer carries the destination URL -- the
            # Apply button opens a sign-in wall first -- but it still says
            # whether the job leads off LinkedIn at all. Which system is
            # behind it is then found by asking the systems themselves.
            destination = ""
            system = probe_company(company)
        else:
            system, destination = "easy apply (linkedin-hosted form)", ""
        rows.append(
            {
                "job_id": job_id,
                "title": title[:80],
                "company": company[:50],
                "system": system,
                "destination": destination[:200],
            }
        )
        print(f"  {index:3}. {system:<38} {company[:24]:<26} {title[:38]}")

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["job_id", "title", "company", "system", "destination"]
        )
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter

    counts = Counter(r.get("system", "?") for r in rows)
    print(f"\nwhere the {len(rows)} postings lead:")
    for system, count in counts.most_common():
        print(f"  {count:4}  {system}")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


def main() -> int:
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keywords", default="AI Engineer")
    parser.add_argument("--location", default="United States")
    parser.add_argument("--sample", type=int, default=40)
    parser.add_argument("--pause", type=float, default=1.2)
    args = parser.parse_args()
    return survey(args.keywords, args.location, args.sample, args.pause)


if __name__ == "__main__":
    raise SystemExit(main())

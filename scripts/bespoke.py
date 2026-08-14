"""Application forms on employers' own sites, found by rendering their pages.

The forms that matter are not the ones on the three big job boards. Most
companies send applicants to their own careers page, and what sits behind it is
a system nobody has tested against: Avature with its repeating employment
blocks, iCIMS, Phenom, Eightfold, or something written for that company alone.

None of it can be found by asking an API, because there is no API, and most of
it cannot be found by reading the HTML either -- a careers page today is an
empty shell that draws its own job list once a browser runs its script. So this
renders them.

    python scripts/bespoke.py --companies "ManTech,MCI,Jobgether"
    python scripts/bespoke.py --from corpus/linkedin_companies.json --limit 60

What comes out is a targets file of real application URLs, which apply.py then
fills and reports on. Nothing here signs in and nothing is submitted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "corpus" / "bespoke_targets.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

#: Where a company keeps its openings. Tried in order; the first that renders
#: something job-shaped wins.
CAREERS_PATHS = (
    "/careers", "/careers/", "/jobs", "/jobs/", "/company/careers",
    "/about/careers", "/careers/jobs", "/en/careers", "/join-us",
)

#: What a link to one job looks like, across every system met so far. Kept
#: broad on purpose: the point is to find forms nobody has tested, so a shape
#: that has not been seen before still has to get through.
JOB_LINK = re.compile(
    r"(jobdetail|/job/|/jobs/|/offer/|/position|/opening|/vacanc|/careers/[a-z0-9-]{6,}"
    r"|requisition|/apply/|jobid=|job_id=|gh_jid=|posting)",
    re.I,
)

#: Links that look like jobs and are not: the board's own furniture.
NOT_A_JOB = re.compile(
    r"(/search|/results|/all-jobs|/job-alert|/saved|/login|/signin|/register"
    r"|/privacy|/cookie|/terms|linkedin\.com|facebook\.com|twitter\.com|x\.com"
    r"|/rss|\.pdf$|/category|/location|/department|/team)",
    re.I,
)

#: The systems worth naming when one turns up, so a run says what it met.
VENDORS = (
    ("avature", "avature.net"), ("icims", "icims.com"), ("workday", "myworkdayjobs.com"),
    ("taleo", "taleo.net"), ("successfactors", "sapsf.com"), ("jobvite", "jobvite.com"),
    ("greenhouse", "greenhouse.io"), ("lever", "lever.co"), ("ashby", "ashbyhq.com"),
    ("smartrecruiters", "smartrecruiters.com"), ("phenom", "phenompeople.com"),
    ("eightfold", "eightfold.ai"), ("workable", "workable.com"), ("rippling", "rippling.com"),
    ("recruitee", "recruitee.com"), ("breezy", "breezy.hr"), ("jazzhr", "applytojob.com"),
    ("paylocity", "paylocity.com"), ("bamboohr", "bamboohr.com"), ("teamtailor", "teamtailor.com"),
)


def vendor_of(url: str) -> str:
    lowered = (url or "").lower()
    for name, needle in VENDORS:
        if needle in lowered:
            return name
    return "bespoke"


def domains_for(company: str) -> list[str]:
    plain = re.sub(r"[^a-z0-9 ]", " ", (company or "").lower()).strip()
    words = plain.split()
    if not words:
        return []
    joined = "".join(words)
    out = [f"{joined}.com", f"{'-'.join(words)}.com", f"{words[0]}.com"]
    if len(words) > 1:
        out.append(f"{''.join(words[:2])}.com")
    seen: list[str] = []
    for domain in out:
        if domain not in seen:
            seen.append(domain)
    return seen[:4]


def job_links(page) -> list[str]:
    """Every link on the rendered page that looks like one job."""
    hrefs = page.evaluate(
        "() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
    )
    out: list[str] = []
    for href in hrefs:
        if not href.startswith("http"):
            continue
        if NOT_A_JOB.search(href):
            continue
        if not JOB_LINK.search(href):
            continue
        if href not in out:
            out.append(href)
    return out


def careers_page(page, company: str, timeout: int) -> tuple[str, list[str]]:
    """The company's own openings page and the jobs on it, or ("", [])."""
    for domain in domains_for(company):
        for path in CAREERS_PATHS:
            for host in (f"https://www.{domain}", f"https://{domain}"):
                try:
                    page.goto(host + path, timeout=timeout, wait_until="domcontentloaded")
                    page.wait_for_timeout(3500)
                except Exception:
                    continue
                found = job_links(page)
                if len(found) >= 2:
                    return page.url, found
    return "", []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--companies", default="", help="comma separated")
    parser.add_argument("--from", dest="from_file", default="")
    parser.add_argument("--limit", type=int, default=40, help="how many companies")
    parser.add_argument("--per-company", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=25000)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    if args.companies:
        companies = [c.strip() for c in args.companies.split(",") if c.strip()]
    elif args.from_file:
        companies = json.loads(Path(args.from_file).read_text(encoding="utf-8"))[: args.limit]
    else:
        parser.error("give --companies or --from")

    from playwright.sync_api import sync_playwright

    targets: list[dict] = []
    vendors: dict[str, int] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(user_agent=USER_AGENT)
        for index, company in enumerate(companies, 1):
            page = context.new_page()
            try:
                where, found = careers_page(page, company, args.timeout)
            except Exception:
                where, found = "", []
            finally:
                page.close()

            if not found:
                print(f"  [{index}/{len(companies)}] {company[:26]:28} no careers page rendered")
                continue

            for url in found[: args.per_company]:
                system = vendor_of(url)
                vendors[system] = vendors.get(system, 0) + 1
                targets.append(
                    {"ats": system, "company": company, "title": "", "url": url,
                     "from": "careers page"}
                )
            print(
                f"  [{index}/{len(companies)}] {company[:26]:28} "
                f"{vendor_of(found[0]):15} {len(found[: args.per_company])} form(s) "
                f"via {where[:40]}",
                flush=True,
            )

    Path(args.out).write_text(json.dumps(targets, indent=1), encoding="utf-8")
    print(f"\n{len(targets)} application URLs -> {args.out}")
    for system, count in sorted(vendors.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4}  {system}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

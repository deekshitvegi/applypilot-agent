"""Many real application forms at once, so a rule is judged on all of them.

Finding a fault by meeting it on a live page costs an afternoon and finds one
fault -- whichever happened to be hit first. This reads a lot of real forms
into files, then replays every one of them against the matcher on every change.
The faults come back ranked by how many forms they affect instead of by which
was met first.

Three steps, each usable on its own:

  harvest   ask the ATSes what jobs are open, and write down where to apply
  capture   open each of those forms and save what the page is shaped like
  report    replay every saved form through the matcher and rank what fails

Nothing here ever acts on a page. It opens, reads, and closes: the same thing
a person does by looking. Captures hold the shape of a form -- labels, control
kinds, options -- and no answers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CORPUS = ROOT / "corpus"
FORMS = CORPUS / "forms"
TARGETS = CORPUS / "targets.json"
SEEDS = Path(__file__).parent / "corpus_seeds.json"

INJECTED_DIR = ROOT / "extension" / "injected"
INJECTED_ORDER = ("dom.js", "surface.js", "verify.js", "scan.js", "act.js")
#: Loaded before them, and by the panel too: one list of what counts as a
#: control's own "Choose one" row, rather than a copy in each place.
SHARED_FIRST = (ROOT / "extension" / "placeholders.js",)

USER_AGENT = "ApplyPilot-corpus/1.0 (+https://github.com/deekshitvegi/applypilot-agent)"


# --------------------------------------------------------------------- harvest


@dataclass
class Feed:
    """One ATS's public list of open jobs.

    These are the endpoints a company's own careers page calls to draw itself,
    so reading them is reading what the company publishes. No browser is
    involved and no account is needed.
    """

    name: str
    url: str
    jobs: str  # where the list lives in the response: "" means the top level
    apply_url: tuple[str, ...]  # the first of these keys that is present wins
    title: str


FEEDS = {
    "greenhouse": Feed(
        "greenhouse",
        "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "jobs",
        ("absolute_url",),
        "title",
    ),
    "lever": Feed(
        "lever",
        "https://api.lever.co/v0/postings/{slug}?mode=json",
        "",
        ("applyUrl", "hostedUrl"),
        "text",
    ),
    "ashby": Feed(
        "ashby",
        "https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "jobs",
        ("applyUrl", "jobUrl"),
        "title",
    ),
    "smartrecruiters": Feed(
        "smartrecruiters",
        "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
        "content",
        ("applyUrl", "ref"),
        "name",
    ),
}


def get_json(url: str, timeout: int = 30, body: dict | None = None):
    headers = {"User-Agent": USER_AGENT}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


#: Workday asks for its list rather than serving it, and answers with a path
#: per posting instead of a URL. It is the largest of these systems and the one
#: least like the others, so it gets its own few lines rather than being bent
#: into the shape of a feed.
WORKDAY_QUERY = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


def harvest_workday(entry: dict, per_company: int) -> list[dict]:
    tenant, site = entry["slug"], entry["site"]
    host = f"https://{tenant}.{entry.get('pod', 'wd5')}.myworkdayjobs.com"
    payload = get_json(f"{host}/wday/cxs/{tenant}/{site}/jobs", body=WORKDAY_QUERY)
    out = []
    for job in (payload.get("jobPostings") or [])[:per_company]:
        path = job.get("externalPath") or ""
        if not path:
            continue
        out.append(
            {
                "ats": "workday",
                "company": tenant,
                "title": str(job.get("title", ""))[:120],
                "url": f"{host}/en-US/{site}{path}",
            }
        )
    print(f"  ok workday/{tenant}: {payload.get('total', '?')} open, took {len(out)}")
    return out


#: Rippling answers with a bare list and gives the posting's URL, not the
#: form's. The apply step is a query on the same address.
def harvest_rippling(entry: dict, per_company: int) -> list[dict]:
    slug = entry["slug"]
    jobs = get_json(f"https://ats.rippling.com/api/v1/board/{slug}/jobs")
    out = []
    for job in (jobs or [])[:per_company]:
        uuid = job.get("uuid")
        if not uuid:
            continue
        out.append(
            {
                "ats": "rippling",
                "company": slug,
                "title": str(job.get("name", ""))[:120],
                "url": (
                    f"https://ats.rippling.com/{slug}/jobs/{uuid}/apply"
                    f"?jobBoardSlug={slug}&jobId={uuid}&step=application"
                ),
            }
        )
    print(f"  ok rippling/{slug}: {len(jobs or [])} open, took {len(out)}")
    return out


def harvest(per_company: int, pause: float) -> list[dict]:
    """Ask each seeded company's ATS what is open, and where to apply."""
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))
    found: list[dict] = []

    for entry in seeds["companies"]:
        if entry["ats"] == "rippling":
            try:
                found.extend(harvest_rippling(entry, per_company))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as err:
                print(f"  -  rippling/{entry['slug']}: {err}")
            time.sleep(pause)
            continue
        if entry["ats"] == "workday":
            try:
                found.extend(harvest_workday(entry, per_company))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as err:
                print(f"  -  workday/{entry['slug']}: {err}")
            time.sleep(pause)
            continue
        feed = FEEDS.get(entry["ats"])
        if not feed:
            print(f"  ?  unknown ats {entry['ats']!r} for {entry['slug']}")
            continue
        url = feed.url.format(slug=entry["slug"])
        try:
            payload = get_json(url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as err:
            print(f"  -  {feed.name}/{entry['slug']}: {err}")
            continue

        jobs = payload.get(feed.jobs, []) if feed.jobs else payload
        if not isinstance(jobs, list):
            print(f"  -  {feed.name}/{entry['slug']}: unexpected shape")
            continue

        taken = 0
        for job in jobs:
            if taken >= per_company:
                break
            where = next((job[k] for k in feed.apply_url if job.get(k)), "")
            if not where:
                continue
            found.append(
                {
                    "ats": feed.name,
                    "company": entry["slug"],
                    "title": str(job.get(feed.title, ""))[:120],
                    "url": where,
                }
            )
            taken += 1
        print(f"  ok {feed.name}/{entry['slug']}: {len(jobs)} open, took {taken}")
        time.sleep(pause)

    CORPUS.mkdir(exist_ok=True)
    TARGETS.write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"\n{len(found)} apply URLs -> {TARGETS.relative_to(ROOT)}")
    return found


# --------------------------------------------------------------------- capture


def slugify(target: dict) -> str:
    raw = f"{target['ats']}-{target['company']}-{target['title']}"
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:90]


def capture(limit: int, timeout: int) -> None:
    """Open each form, run the real scan, and write down its shape.

    The injected files are the ones the extension ships, so what is measured
    here is the shipping code and not a copy of it.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    targets = json.loads(TARGETS.read_text(encoding="utf-8"))[:limit]
    FORMS.mkdir(parents=True, exist_ok=True)
    scripts = [path.read_text(encoding="utf-8") for path in SHARED_FIRST]
    scripts += [(INJECTED_DIR / name).read_text(encoding="utf-8") for name in INJECTED_ORDER]

    done = failed = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(bypass_csp=True, user_agent=USER_AGENT)
        for index, target in enumerate(targets, 1):
            page = context.new_page()
            head = f"[{index}/{len(targets)}] {target['ats']}/{target['company']}"
            try:
                page.goto(target["url"], timeout=timeout, wait_until="domcontentloaded")
                # Forms drawn by script need a moment to exist at all.
                page.wait_for_timeout(2500)
                for source in scripts:
                    page.add_script_tag(content=source)
                observation = page.evaluate("() => ApplyPilot.scan.run()")
                observation["_target"] = target
                out = FORMS / f"{slugify(target)}.json"
                out.write_text(json.dumps(observation, indent=1), encoding="utf-8")
                fields = len(observation.get("fields") or [])
                print(f"  {head}: kind={observation.get('kind')} fields={fields}")
                done += 1
            except (PlaywrightTimeout, PlaywrightError) as err:
                print(f"  {head}: could not read -- {str(err).splitlines()[0][:90]}")
                failed += 1
            finally:
                page.close()
        browser.close()

    print(f"\ncaptured {done}, unreadable {failed} -> {FORMS.relative_to(ROOT)}")


# ---------------------------------------------------------------------- report

#: Someone who does not exist, so a corpus can live in a public repository and
#: so a run never depends on whose machine it is on.
TEST_PROFILE = {
    "full_name": "Alex Rivera",
    "first_name": "Alex",
    "last_name": "Rivera",
    "preferred_name": "Alex",
    "pronouns": "they/them",
    "email": "alex.rivera@example.com",
    "phone": "+1 415 555 0142",
    "phone_country_code": "+1",
    "street_address": "1 Example Street",
    "address_line_2": "Apt 4",
    "city": "Denton",
    "state": "Texas",
    "postal_code": "76201",
    "country": "United States",
    "linkedin": "https://www.linkedin.com/in/example",
    "github": "https://github.com/example",
    "website": "https://example.com",
    "work_authorization": "Yes",
    "requires_sponsorship": "No",
    "citizenship": "US Citizen",
    "over_18": "Yes",
    "background_check_consent": "Yes",
    "drug_test_consent": "Yes",
    "security_clearance": "None",
    "willing_to_relocate": "Yes",
    "notice_period": "Immediately",
    "salary_expectation": "120000",
    "work_arrangement": "Remote",
    "referral_source": "Job Board",
    "previously_employed": "No",
    "gender": "Prefer not to say",
    "race_ethnicity": "Prefer not to say",
    "hispanic_latino": "No",
    "veteran_status": "I am not a protected veteran",
    "disability_status": "No",
    "resume": "alex_rivera_resume.pdf",
    "cover_letter": "alex_rivera_cover.pdf",
}

TEST_EDUCATION = [
    {
        "school": "University of North Texas",
        "degree": "Master's Degree",
        "field_of_study": "Computer Science",
        "start_date": "2022-08",
        "end_date": "2024-05",
        "gpa": "3.8",
        "location": "Denton, Texas",
    }
]

TEST_EXPERIENCE = [
    {
        "company": "Example Labs",
        "title": "Machine Learning Engineer",
        "location": "Remote",
        "start_date": "2024-06",
        "end_date": "",
        "current": True,
        "description": "Built and shipped retrieval systems.",
    }
]


def _why(field, profile) -> str:
    """Which of the four things went wrong, for one unanswered field.

    "Required and not answered yet" is the same sentence whether nothing in the
    profile describes the question, or something does and it is empty, or the
    question is genuinely one only a person can write. They need completely
    different work, so they get counted apart.
    """
    from applypilot.facts import DEMOGRAPHIC_KEYS
    from applypilot.mapper import best_fact, match_facts, usable_options
    from applypilot.models import ControlKind

    match = best_fact(field)
    if match is None:
        if match_facts(field):
            return "several facts could answer it, none clearly"
        if field.control in {ControlKind.TEXTAREA}:
            return "open-ended writing -- no fact can answer it"
        return "no fact describes this question at all"
    if match.spec.key in DEMOGRAPHIC_KEYS:
        return "demographic -- asked on purpose"
    if not profile.fact(match.spec.key):
        return f"fact '{match.spec.key}' matched but the profile is empty there"
    if field.control in {ControlKind.SELECT, ControlKind.COMBOBOX, ControlKind.MULTISELECT}:
        if len(usable_options(field)) < 2:
            return "a list that holds nothing until it is opened or typed into"
        return "saved answer is not among the options offered"
    return "matched and answerable -- should not be here"


def report(verbose: bool) -> int:
    from collections import Counter

    from applypilot.mapper import resolve_page
    from applypilot.models import PageObservation, Profile

    profile = Profile(
        facts=dict(TEST_PROFILE),
        education=list(TEST_EDUCATION),
        experience=list(TEST_EXPERIENCE),
        skills=["Python", "PyTorch", "TypeScript", "React", "SQL"],
    )
    files = sorted(FORMS.glob("*.json"))
    if not files:
        print("no captures yet -- run `harvest` then `capture` first")
        return 1

    reasons: Counter[str] = Counter()
    controls: Counter[str] = Counter()
    unresolved_labels: Counter[str] = Counter()
    causes: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    totals = Counter()
    per_form: list[tuple[float, str, int, int]] = []

    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        target = raw.pop("_target", {})
        try:
            observation = PageObservation.model_validate(raw)
        except Exception as err:  # a capture we cannot even parse is a finding
            reasons[f"capture unreadable: {type(err).__name__}"] += 1
            continue

        kinds[observation.kind.value if hasattr(observation.kind, "value") else str(observation.kind)] += 1
        filled = asked = 0
        for resolution in resolve_page(observation.fields, profile):
            totals["fields"] += 1
            if resolution.answer is not None:
                filled += 1
                totals["filled"] += 1
            elif resolution.question is not None:
                asked += 1
                totals["asked"] += 1
                reasons[resolution.question.reason[:80]] += 1
                controls[str(resolution.field.control)] += 1
                label = (resolution.field.display_label or resolution.field.label or "")[:60]
                unresolved_labels[label] += 1
                causes[_why(resolution.field, profile)] += 1
            else:
                totals["skipped"] += 1

        answerable = filled + asked
        share = filled / answerable if answerable else 1.0
        per_form.append((share, f"{target.get('ats','?')}/{target.get('company','?')}", filled, asked))

    print(f"\n{len(files)} forms · {totals['fields']} fields")
    print(f"  filled from the profile : {totals['filled']}")
    print(f"  needing a person        : {totals['asked']}")
    print(f"  deliberately left       : {totals['skipped']}")
    print("\npage kinds: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common()))

    print("\n-- what actually went wrong, by how many fields it costs --")
    for cause, count in causes.most_common():
        print(f"  {count:4}  {cause}")

    print("\n-- how the panel words it --")
    for reason, count in reasons.most_common(15):
        print(f"  {count:4}  {reason}")

    print("\n-- which kinds of control they are --")
    for control, count in controls.most_common(10):
        print(f"  {count:4}  {control}")

    if verbose:
        print("\n-- the labels themselves --")
        for label, count in unresolved_labels.most_common(30):
            print(f"  {count:4}  {label}")

    print("\n-- forms that went worst --")
    for share, name, filled, asked in sorted(per_form)[:10]:
        print(f"  {share:5.0%}  {name}  ({filled} filled, {asked} asked)")
    return 0


# ------------------------------------------------------------------------ show


def show(pattern: str, limit: int) -> int:
    """Every field whose label matches, exactly as the page gave it.

    Ranked lists say which questions go unanswered; this says what they are
    made of. Guessing at markup is how fixtures end up agreeing with whatever
    was assumed -- the fix is always to read what the page actually sent.
    """
    wanted = re.compile(pattern, re.IGNORECASE)
    interesting = (
        "label", "display_label", "attr_label", "control", "required",
        "section", "value", "placeholder", "autocomplete", "group",
        "group_index", "disabled", "readonly", "frame",
    )
    shown = 0
    for path in sorted(FORMS.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        target = raw.get("_target", {})
        for field in raw.get("fields", []):
            label = field.get("display_label") or field.get("label") or ""
            if not wanted.search(label):
                continue
            if shown >= limit:
                print(f"\n... stopping at {limit}")
                return 0
            shown += 1
            print(f"\n=== {target.get('ats','?')}/{target.get('company','?')} · {path.name[:60]}")
            for key in interesting:
                value = field.get(key)
                if value in (None, "", [], False, 0):
                    continue
                print(f"   {key:14}= {value!r}"[:200])
            options = field.get("options") or []
            if options:
                labels = [o.get("label") for o in options]
                print(f"   {'options':14}= {len(labels)}: {labels[:8]!r}"[:200])
    if not shown:
        print(f"no field label matches {pattern!r}")
    return 0


# ------------------------------------------------------------------------ main


def main() -> int:
    # Real forms are full of characters this console cannot draw -- the red
    # asterisk a form marks required with, curly quotes, en dashes. Losing the
    # whole report to one of them is not a trade worth making.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)

    h = sub.add_parser("harvest", help="ask the ATSes where to apply")
    h.add_argument("--per-company", type=int, default=3)
    h.add_argument("--pause", type=float, default=0.4, help="seconds between companies")

    c = sub.add_parser("capture", help="open each form and save its shape")
    c.add_argument("--limit", type=int, default=40)
    c.add_argument("--timeout", type=int, default=30000)

    r = sub.add_parser("report", help="replay every saved form through the matcher")
    r.add_argument("-v", "--verbose", action="store_true")

    s = sub.add_parser("show", help="print matching fields exactly as the page gave them")
    s.add_argument("pattern", help="regular expression matched against the label")
    s.add_argument("--limit", type=int, default=6)

    args = parser.parse_args()
    if args.step == "show":
        return show(args.pattern, args.limit)
    if args.step == "harvest":
        harvest(args.per_company, args.pause)
        return 0
    if args.step == "capture":
        capture(args.limit, args.timeout)
        return 0
    return report(args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())

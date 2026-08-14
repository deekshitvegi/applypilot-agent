"""Fill real application forms on real employer sites, and write down what happened.

Everything else in scripts/ reads. corpus.py opens a page and saves its shape;
live_check.py asks what the agent makes of a page; scoreboard.py replays those
saved shapes through the matcher. None of them has ever put a value into a box
on a real employer's site, which means the number they all report -- "62% of
fields filled" -- is a claim about a replay, not about a form.

This one fills. It drives the same injected files the extension ships and the
same /plan the panel calls, so what it measures is the shipping path.

    python scripts/apply.py --limit 10
    python scripts/apply.py --url https://jobs.lever.co/.../apply
    python scripts/apply.py --limit 40 --out corpus/applications.csv

It never presses Submit, Apply, Continue or Next, and it never signs in,
registers, or touches a CAPTCHA. Those are the applicant's, and a run that
made them would be making commitments on somebody's behalf at a scale nobody
reviewed. What it produces is a filled form and an honest account of it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INJECTED_DIR = ROOT / "extension" / "injected"
SHARED_FIRST = [ROOT / "extension" / "placeholders.js"]
INJECTED_ORDER = ["dom.js", "surface.js", "verify.js", "scan.js", "act.js"]
TARGETS = ROOT / "corpus" / "targets.json"
OUT = ROOT / "corpus" / "applications.csv"
QUESTIONS_OUT = ROOT / "corpus" / "applications_questions.csv"

SERVICE = "http://127.0.0.1:8765"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

#: Words on a control that commits the application. Nothing here presses one.
#: Checked against what the scan already found rather than hunted for, so this
#: is a report of what was left alone, not an attempt to be clever about it.
COMMITTING = ("submit", "apply", "continue", "next", "finish", "send")


def service(path: str, payload: dict | None = None, timeout: int = 120) -> Any:
    """Call the local service the same way the panel does."""
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        SERVICE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def load_scripts() -> list[str]:
    scripts = [path.read_text(encoding="utf-8") for path in SHARED_FIRST]
    scripts += [(INJECTED_DIR / name).read_text(encoding="utf-8") for name in INJECTED_ORDER]
    return scripts


def targets_from(args) -> list[dict]:
    if args.url:
        return [{"ats": "given", "company": "given", "title": "", "url": args.url}]
    if not TARGETS.exists():
        print(f"no targets at {TARGETS}; run corpus.py harvest first", file=sys.stderr)
        return []
    everything = json.loads(TARGETS.read_text(encoding="utf-8"))
    if args.ats:
        everything = [t for t in everything if t.get("ats") in set(args.ats.split(","))]
    return everything[: args.limit]


def fill_one(page, target: dict, scripts: list[str], timeout: int) -> dict:
    """Open one application, fill what can be filled, and report honestly."""
    row: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ats": target.get("ats", ""),
        "company": target.get("company", ""),
        "title": target.get("title", ""),
        "url": target.get("url", ""),
        "kind": "",
        "fields": 0,
        "planned": 0,
        "verified": 0,
        "attempted": 0,
        "failed": 0,
        "needs_you": 0,
        "captcha": "",
        "submit_left_alone": 0,
        "outcome": "",
        "note": "",
    }
    questions: list[dict] = []

    page.goto(target["url"], timeout=timeout, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    for source in scripts:
        page.add_script_tag(content=source)

    observation = page.evaluate("() => ApplyPilot.scan.run()")
    row["kind"] = observation.get("kind", "")
    row["fields"] = len(observation.get("fields") or [])
    row["captcha"] = observation.get("captcha", "")
    row["submit_left_alone"] = len(
        [
            control
            for control in (observation.get("submit_controls") or [])
            + (observation.get("next_controls") or [])
            if any(word in str(control).lower() for word in COMMITTING)
        ]
    )

    if observation.get("captcha") == "challenge":
        row["outcome"] = "left alone: CAPTCHA is waiting for a person"
        return {"row": row, "questions": questions}
    if row["fields"] == 0:
        row["outcome"] = "nothing to fill: no controls found"
        return {"row": row, "questions": questions}

    plan = service("/plan", observation)
    actions = plan.get("actions") or []
    asked = plan.get("questions") or []
    row["planned"] = len(actions)
    row["needs_you"] = len(asked)

    for question in asked:
        questions.append(
            {
                "company": target.get("company", ""),
                "url": target.get("url", ""),
                "question": question.get("label", ""),
                "control": question.get("control", ""),
                "how_it_works": question.get("operation", ""),
                "required": "yes" if question.get("required") else "no",
                "options": " | ".join(
                    str(o.get("label", "")) for o in (question.get("options") or [])[:12]
                ),
                "why": question.get("reason", ""),
            }
        )

    if actions:
        # The same call the panel makes, into the page, in the planned order.
        results = page.evaluate(
            "(actions) => ApplyPilot.act.performMany(actions)", actions
        )
        for result in results or []:
            outcome = (result or {}).get("outcome", "")
            if outcome == "verified":
                row["verified"] += 1
            elif outcome == "failed":
                row["failed"] += 1
            else:
                row["attempted"] += 1

    # Controls that offer nothing until they are worked.
    #
    # A search-as-you-type box holds no options at all until something is typed
    # into it, so the first plan can only hand it back as a question. The panel
    # opens it, types the saved answer, reads what the control itself then
    # offers, and picks from that -- and without this the harness reported a
    # required city field as "left for you" on every application one large ATS
    # serves, which is honest and still an empty box.
    pending = [q for q in asked if q.get("options_pending") or q.get("saved_value")]
    if pending:
        for question in pending:
            try:
                page.evaluate(
                    "([fp, filter]) => ApplyPilot.act.openOptions(fp, filter)",
                    [question.get("fingerprint"), question.get("saved_value") or ""],
                )
                page.wait_for_timeout(700)
            except Exception:
                # A control that will not open is one that stays a question.
                continue

        second = service("/plan", page.evaluate("() => ApplyPilot.scan.run()"))
        extra = second.get("actions") or []
        # Only what the first pass did not already do.
        done = {a.get("fingerprint") for a in actions}
        extra = [a for a in extra if a.get("fingerprint") not in done]
        if extra:
            results = page.evaluate(
                "(actions) => ApplyPilot.act.performMany(actions)", extra
            )
            row["planned"] += len(extra)
            for result in results or []:
                outcome = (result or {}).get("outcome", "")
                if outcome == "verified":
                    row["verified"] += 1
                elif outcome == "failed":
                    row["failed"] += 1
                else:
                    row["attempted"] += 1
        row["needs_you"] = len(second.get("questions") or [])

    # Nothing above can press a commit control, and this says so out loud
    # rather than leaving it to be inferred from the absence of a line.
    row["outcome"] = (
        f"filled {row['verified']}/{row['planned']}, "
        f"{row['needs_you']} left for you, submit not pressed"
    )
    return {"row": row, "questions": questions}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--url", default="", help="one application, instead of the corpus")
    parser.add_argument("--ats", default="", help="only these, comma separated")
    parser.add_argument("--timeout", type=int, default=45000)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument(
        "--headed", action="store_true", help="watch it happen in a real window"
    )
    args = parser.parse_args()

    try:
        health = service("/health")
    except (urllib.error.URLError, OSError) as exc:
        print(f"the local service is not running: {exc}", file=sys.stderr)
        return 1
    answers = health.get("profile_answered")
    print(f"service {health.get('version')} · profile has {answers} answers\n")

    targets = targets_from(args)
    if not targets:
        return 1

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    rows: list[dict] = []
    questions: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        context = browser.new_context(bypass_csp=True, user_agent=USER_AGENT)
        for index, target in enumerate(targets, 1):
            head = f"[{index}/{len(targets)}] {target.get('ats')}/{target.get('company')}"
            page = context.new_page()
            try:
                got = fill_one(page, target, load_scripts(), args.timeout)
                rows.append(got["row"])
                questions.extend(got["questions"])
                print(f"  {head}: {got['row']['outcome']}")
            except (PlaywrightTimeout, PlaywrightError) as err:
                rows.append(
                    {
                        "at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "ats": target.get("ats", ""),
                        "company": target.get("company", ""),
                        "title": target.get("title", ""),
                        "url": target.get("url", ""),
                        "outcome": "could not open",
                        "note": str(err).splitlines()[0][:120],
                    }
                )
                print(f"  {head}: could not open -- {str(err).splitlines()[0][:70]}")
            finally:
                page.close()
        browser.close()

    columns = [
        "at", "ats", "company", "title", "url", "kind", "fields", "planned",
        "verified", "attempted", "failed", "needs_you", "captcha",
        "submit_left_alone", "outcome", "note",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    if questions:
        with QUESTIONS_OUT.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(questions[0].keys()))
            writer.writeheader()
            writer.writerows(questions)

    opened = [r for r in rows if r.get("outcome") != "could not open"]
    fields = sum(r.get("fields", 0) or 0 for r in opened)
    verified = sum(r.get("verified", 0) or 0 for r in opened)
    planned = sum(r.get("planned", 0) or 0 for r in opened)
    left = sum(r.get("needs_you", 0) or 0 for r in opened)
    print(f"\n{len(opened)}/{len(rows)} applications opened")
    print(f"  {fields} fields seen")
    print(f"  {planned} planned, {verified} verified onto the page")
    print(f"  {left} left for a person")
    print("  0 submitted -- this never presses a commit control")
    print(f"\n{out}")
    if questions:
        print(f"{QUESTIONS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

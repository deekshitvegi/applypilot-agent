"""Regression check against live application forms.

Runs the extension's real injected functions and the local companion against
real employer pages and asserts the outcomes that have regressed before:
sign-in pages must be recognised, application forms must not be, and known
fields must actually fill.

It never clicks Apply, Continue, Next, or Submit, and never submits anything.

    python scripts/live_check.py

Requires the companion running on 127.0.0.1:8765 and Playwright Chromium.
Exits non-zero if any expectation fails.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / "extension" / "service-worker.js").read_text(encoding="utf-8")
API = "http://127.0.0.1:8765"

CHROME_STUB = (
    "window.chrome={runtime:{onInstalled:{addListener(){}},onMessage:{addListener(){}},"
    "sendMessage(){return Promise.resolve({})}},sidePanel:{setPanelBehavior(){}},"
    "storage:{session:{get(){return Promise.resolve({})},set(){return Promise.resolve({})}}}};"
)
EXPORTS = (
    ";window.runFormPass=runFormPass;window.extractJobFromPage=extractJobFromPage;"
    ";window.detectApplicationSurface=detectApplicationSurface;window.clickReadyLogin=clickReadyLogin;"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

# expected_login: is this a credential page?
# min_fields: the scanner must see at least this many controls.
# min_filled: verified fills expected from the saved profile (None = skip).
CASES = [
    {
        "name": "ADP sign-in (two-step, shadow DOM)",
        "url": (
            "https://workforcenow.adp.com/mascsr/applicant/mdf/recruitment/postLogin.html"
            "?cid=cb3aac02-ef3b-4c14-baa6-26c70f4c180a&ccId=19000101_000001&jobId=568564"
            "&lang=en_US&requisitionId=9201878277427_1&OTP_login=true"
        ),
        "expected_login": True,
        "min_fields": 0,
        "min_filled": None,
    },
    {
        "name": "Greenhouse application (Anthropic)",
        "url": "https://job-boards.greenhouse.io/anthropic/jobs/4610158008",
        "expected_login": False,
        "min_fields": 20,
        "min_filled": 3,
    },
    {
        "name": "Lever application (demo)",
        "url": "https://jobs.lever.co/leverdemo/c559265a-55ec-4f75-ac56-78290081f6e7/apply",
        "expected_login": False,
        "min_fields": 10,
        "min_filled": 2,
    },
    {
        "name": "Ashby application (Higharc)",
        "url": (
            "https://jobs.ashbyhq.com/higharc/"
            "7697227f-f2c9-48f5-9a6c-b45ba5195ec6/application"
        ),
        "expected_login": False,
        "min_fields": 5,
        "min_filled": 2,
    },
]


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request, timeout=90))


def check(page, case: dict) -> list[str]:
    failures: list[str] = []
    page.goto(case["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(7000)

    login = page.evaluate("() => clickReadyLogin(false)")
    if bool(login.get("login_page")) is not case["expected_login"]:
        failures.append(
            f"login_page={login.get('login_page')} expected {case['expected_login']}"
        )
    if login.get("clicked"):
        failures.append("clicked a login control during a read-only check")

    scan = page.evaluate("() => runFormPass('enumerate')")
    fields = scan["fields"]
    if len(fields) < case["min_fields"]:
        failures.append(f"only {len(fields)} fields, expected >= {case['min_fields']}")

    filled = 0
    if case["min_filled"] is not None and fields:
        plan = post("/api/forms/plan", {
            "page_url": page.url, "source_url": page.url, "fields": fields,
        })
        actions = [
            {
                "field_id": a["field_id"], "value": a["value"], "source": "live-check",
                "confidence": 1,
                "expected_label": next((f["label"] for f in fields if f["id"] == a["field_id"]), ""),
                "expected_type": next((f["field_type"] for f in fields if f["id"] == a["field_id"]), ""),
                "fingerprint": next((f["fingerprint"] for f in fields if f["id"] == a["field_id"]), ""),
            }
            for a in plan["actions"]
        ]
        if actions:
            result = page.evaluate("(a) => runFormPass(a)", actions)
            filled = sum(1 for r in result["results"] if r["status"] == "verified")
            if result.get("submit_clicked"):
                failures.append("SUBMIT WAS CLICKED - must never happen")
        if filled < case["min_filled"]:
            failures.append(f"verified {filled} fills, expected >= {case['min_filled']}")

    print(
        f"  fields={len(fields):<3} login={login.get('login_page')!s:<5} verified_fills={filled}"
    )
    return failures


def main() -> int:
    try:
        health = json.load(urllib.request.urlopen(f"{API}/health", timeout=10))
        print(f"companion: {health['version']}\n")
    except Exception as error:  # noqa: BLE001
        print(f"companion not reachable at {API}: {error}")
        return 2

    failed = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200})
        context.add_init_script(CHROME_STUB + "\n" + WORKER + "\n" + EXPORTS)
        page = context.new_page()
        for case in CASES:
            print(f"{case['name']}")
            try:
                failures = check(page, case)
            except Exception as error:  # noqa: BLE001
                failures = [f"harness error: {str(error)[:120]}"]
            if failures:
                failed += 1
                for failure in failures:
                    print(f"  FAIL: {failure}")
            else:
                print("  PASS")
        browser.close()

    print(f"\n{len(CASES) - failed}/{len(CASES)} sites passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

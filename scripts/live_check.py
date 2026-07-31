"""Drive the real injected functions against real employer pages.

Fixture tests are fast and they are not enough. A change that made every
application look like a login page passed every fixture in the suite, because
the fixtures were written from pages that had already been understood. This
runs the shipping code against sites as they are today.

    python scripts/live_check.py                     every target
    python scripts/live_check.py --url URL           one page, just report
    python scripts/live_check.py --url URL --expect application

Nothing is filled in and nothing is submitted. The check reads pages and asks
what the agent makes of them.

A target that cannot be reached is a warning: sites go down and URLs rot. A
target that is read wrongly is a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECTED = ROOT / "extension" / "injected"
ORDER = ("dom.js", "surface.js", "verify.js", "scan.js", "act.js")
TARGETS = Path(__file__).resolve().parent / "live_targets.json"

OK, WARN, BAD = "  ok  ", " warn ", " FAIL "


def check_versions(port: int) -> list[str]:
    """The one check that has cost the most time when skipped."""
    problems: list[str] = []
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text("utf-8"))
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=4) as response:
            health = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[{WARN}] service not answering on 127.0.0.1:{port} ({exc})")
        print("         start it with scripts/start.ps1 -- surface checks below still run")
        return problems

    if health["version"] != manifest["version"]:
        print(f"[{BAD}] service is running {health['version']}, manifest says {manifest['version']}")
        print("         restart the service, then reload the extension")
        problems.append("version mismatch")
    else:
        print(f"[{OK}] service and extension both on {health['version']}")
    return problems


def observe(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:  # noqa: BLE001 - a busy page is still worth reading
        pass
    for filename in ORDER:
        page.add_script_tag(path=str(INJECTED / filename))
    return page.evaluate("() => ApplyPilot.scan.run()")


def describe(observation: dict) -> str:
    labelled = [f for f in observation["fields"] if f["label"]]
    return (
        f"kind={observation['kind']} fields={len(observation['fields'])} "
        f"(labelled {len(labelled)}) captcha={observation['captcha']} "
        f"apply={len(observation['apply_controls'])}"
    )


def judge(target: dict, observation: dict) -> list[str]:
    from applypilot.adapters import detect_adapter

    failures: list[str] = []
    kind = observation["kind"]

    if kind in target.get("never_kind", []):
        failures.append(f"read as {kind}, which it must never be ({target['why']})")
    elif target.get("expect_kind") and kind not in target["expect_kind"]:
        failures.append(f"read as {kind}, expected one of {target['expect_kind']}")

    expected_adapter = target.get("expect_adapter")
    if expected_adapter:
        found = detect_adapter(observation["url"], observation.get("hints", []))
        name = found.name if found else "generic"
        if name != expected_adapter:
            failures.append(f"adapter came back {name}, expected {expected_adapter}")

    if "expect_fields" in target and len(observation["fields"]) != target["expect_fields"]:
        failures.append(
            f"offered {len(observation['fields'])} fields, expected {target['expect_fields']}"
        )

    for label in target.get("expect_labels", []):
        if not any(label.lower() in (f["label"] or "").lower() for f in observation["fields"]):
            failures.append(f"no field labelled like {label!r}")

    return failures


def run(targets: list[dict], headed: bool) -> int:
    from playwright.sync_api import sync_playwright

    problems = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(
            # The extension injects through chrome.scripting, which a page's
            # Content-Security-Policy does not apply to. Without this the check
            # cannot read any site that sets a strict one -- and it reported
            # them as unreachable, which looked like the sites being down.
            bypass_csp=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        for target in targets:
            name = target.get("name") or target["url"]
            try:
                observation = observe(page, target["url"])
            except Exception as exc:  # noqa: BLE001 - usually the site, not the code
                reason = str(exc).strip().splitlines()[0][:140] if str(exc).strip() else "no detail"
                print(f"[{WARN}] {name}: could not be read -- {type(exc).__name__}: {reason}")
                continue

            failures = judge(target, observation)
            mark = BAD if failures else OK
            print(f"[{mark}] {name}: {describe(observation)}")
            for note in observation.get("notes", [])[:3]:
                print(f"         note: {note}")
            for failure in failures:
                print(f"         {failure}")
                problems += 1
        browser.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="check one page instead of the target list")
    parser.add_argument("--expect", help="the kind that page should be read as")
    parser.add_argument("--never", help="a kind that page must never be read as")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--headed", action="store_true", help="watch it happen")
    args = parser.parse_args()

    print("ApplyPilot live check -- reads pages, fills nothing, submits nothing")
    print()
    problems = len(check_versions(args.port))
    print()

    if args.url:
        targets = [
            {
                "name": args.url,
                "url": args.url,
                "expect_kind": [args.expect] if args.expect else [],
                "never_kind": [args.never] if args.never else [],
                "why": "as asked on the command line",
            }
        ]
    else:
        targets = json.loads(TARGETS.read_text("utf-8"))["targets"]

    problems += run(targets, args.headed)
    print()
    if problems:
        print(f"{problems} problem(s). Do not push on this.")
        return 1
    print("Nothing read wrongly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

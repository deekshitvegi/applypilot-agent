"""Read report bundles -- one, or a folder of them -- and say what went wrong.

A report is saved from the panel when a page misbehaves. One is easy to read by
hand. A dozen is not, and a dozen is what a bad afternoon produces: the same
control failing on six sites is the finding, and it is invisible one file at a
time.

    python scripts/read_reports.py ~/Downloads
    python scripts/read_reports.py a.zip b.zip c.zip
    python scripts/read_reports.py ~/Downloads --fields

Nothing here reaches the network and nothing is uploaded. It reads files that
are already on the machine and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

#: What the panel names its bundles.
PATTERN = "applypilot-*.zip"


def bundles(paths: list[str]) -> list[Path]:
    """Every report in *paths*, whether they name files or folders."""
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found.extend(sorted(path.glob(PATTERN)))
        elif path.is_file():
            found.append(path)
        else:
            print(f"  ! nothing at {path}", file=sys.stderr)
    return found


def read(path: Path) -> dict[str, Any] | None:
    """The report inside one bundle, or None with a reason printed."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".json")]
            if not names:
                print(f"  ! {path.name}: no report inside", file=sys.stderr)
                return None
            return json.loads(archive.read(names[0]))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as exc:
        print(f"  ! {path.name}: {exc}", file=sys.stderr)
        return None


def summarise(path: Path, report: dict[str, Any], show_fields: bool) -> Counter:
    """Print one report and return what it says went unanswered."""
    page = report.get("page") or {}
    checklist = report.get("checklist") or []
    results = report.get("results") or []

    states = Counter(item.get("state", "?") for item in checklist)
    verified = sum(1 for r in results if r.get("outcome") == "verified")

    print(f"\n=== {path.name}")
    print(f"    {page.get('url', '?')[:100]}")
    print(
        f"    {page.get('adapter') or 'no adapter'} · {page.get('kind', '?')}"
        f" · captcha {page.get('captcha', '?')} · panel {report.get('panel_version', '?')}"
    )
    counts = " · ".join(f"{n} {state}" for state, n in states.most_common())
    print(f"    {len(checklist)} fields: {counts}")
    if results:
        print(f"    {verified}/{len(results)} actions verified")
    else:
        # No results at all almost always means the report was saved before
        # Fill was pressed, which reads as total failure and is not one.
        print("    no actions were carried out (saved before filling?)")

    # A question that kept coming back. This is the complaint that a snapshot
    # cannot carry: asked once and asked six times look identical in one.
    for loop in report.get("asked_more_than_once") or []:
        print(f"      LOOP  asked {loop.get('times')}x: {str(loop.get('question'))[:76]}")

    # An answer that was taken and then not kept -- which is what causes the
    # loop above, and is invisible from the page's state alone.
    for entry in report.get("journal") or []:
        if entry.get("kind") == "not_remembered":
            print(
                f"      NOT KEPT  {str(entry.get('what'))[:44]:46}"
                f" {str(entry.get('reason'))[:58]}"
            )
        elif entry.get("kind") == "answered" and entry.get("outcome") == "failed":
            print(
                f"      DID NOT LAND  {str(entry.get('what'))[:40]:42}"
                f" {str(entry.get('evidence'))[:54]}"
            )
        elif entry.get("kind") == "chat_result" and entry.get("outcome") != "verified":
            print(
                f"      CHAT DID NOTHING  \"{str(entry.get('what'))[:38]}\""
                f" -> {str(entry.get('outcome'))[:40]}"
            )

    trouble: Counter = Counter()
    for item in checklist:
        if item.get("state") not in {"needs_you", "failed"}:
            continue
        detail = str(item.get("detail") or "")
        trouble[detail[:70]] += 1
        if show_fields:
            print(f"      [{item.get('state')}] {str(item.get('label'))[:44]:46} {detail[:60]}")
    for line in report.get("activity") or []:
        print(f"      note: {str(line)[:110]}")
    return trouble


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="report .zip files, or folders holding them")
    parser.add_argument(
        "--fields", action="store_true", help="list every field that needs someone"
    )
    args = parser.parse_args()

    found = bundles(args.paths)
    if not found:
        print("no report bundles found", file=sys.stderr)
        return 1

    across: Counter = Counter()
    sites: Counter = Counter()
    read_count = 0
    for path in found:
        report = read(path)
        if report is None:
            continue
        read_count += 1
        across.update(summarise(path, report, args.fields))
        adapter = (report.get("page") or {}).get("adapter") or "unknown"
        sites[adapter] += 1

    if read_count > 1:
        print(f"\n\n=== across {read_count} reports ===")
        print("\nwhat they were built on:")
        for adapter, count in sites.most_common():
            print(f"  {count:3}  {adapter}")
        print("\nwhy fields went unanswered, most common first:")
        for reason, count in across.most_common(20):
            print(f"  {count:3}  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

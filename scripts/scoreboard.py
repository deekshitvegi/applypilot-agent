"""How much of each real application gets filled, run after run.

Claiming a form got better is worth nothing. This writes down, for every
application in the corpus, how many of its fields were filled and how many were
left for a person -- and appends a row every time it runs, so two runs either
side of a change say plainly whether the change helped, hurt, or did nothing.

It writes two files, both openable in Excel:

  corpus/scoreboard.csv   one row per application per run
  corpus/questions.csv    one row per field left unanswered, with the kind of
                          control it is and the options it offers

Nothing here touches a page. It replays what `corpus.py capture` already read,
so a run costs seconds and can be repeated after every change.

  python scripts/scoreboard.py                 record a run
  python scripts/scoreboard.py --note "fix X"  and say what changed
  python scripts/scoreboard.py --compare       show every run so far
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

CORPUS = ROOT / "corpus"
FORMS = CORPUS / "forms"
SCOREBOARD = CORPUS / "scoreboard.csv"
QUESTIONS = CORPUS / "questions.csv"

SCORE_COLUMNS = [
    "run", "when", "version", "note",
    "ats", "company", "title", "url",
    "fields", "filled", "asked", "left_blank", "percent_filled",
]

QUESTION_COLUMNS = [
    "run", "ats", "company", "url",
    "question", "control", "how_it_works", "required",
    "option_count", "options", "why_not_filled",
]


def _version() -> str:
    import applypilot

    return applypilot.__version__


def _profile():
    from applypilot.models import Profile
    from corpus import TEST_EDUCATION, TEST_EXPERIENCE, TEST_PROFILE

    return Profile(
        facts=dict(TEST_PROFILE),
        education=list(TEST_EDUCATION),
        experience=list(TEST_EXPERIENCE),
        skills=["Python", "PyTorch", "TypeScript", "React", "SQL"],
        answer_demographics=True,
    )


def _next_run() -> int:
    if not SCOREBOARD.exists():
        return 1
    with SCOREBOARD.open(encoding="utf-8", newline="") as handle:
        runs = [int(row["run"]) for row in csv.DictReader(handle) if row.get("run")]
    return (max(runs) + 1) if runs else 1


def _why(resolution) -> str:
    """One line saying why a field was not filled, in the panel's own words."""
    if resolution.question is not None:
        return resolution.question.reason
    return resolution.skipped or "unknown"


def record(note: str) -> int:
    from applypilot.mapper import resolve_page, usable_options
    from applypilot.models import PageObservation

    files = sorted(FORMS.glob("*.json"))
    if not files:
        print("no captures yet -- run: python scripts/corpus.py capture")
        return 1

    profile = _profile()
    run = _next_run()
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    version = _version()

    score_rows: list[dict] = []
    question_rows: list[dict] = []

    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        target = raw.pop("_target", {})
        try:
            observation = PageObservation.model_validate(raw)
        except Exception:
            continue
        # Only the pages that are actually applications. A job list has nothing
        # to fill, and counting it would flatter every number here.
        kind = getattr(observation.kind, "value", str(observation.kind))
        if kind not in {"application", "registration"}:
            continue

        filled = asked = blank = 0
        for resolution in resolve_page(observation.fields, profile):
            if resolution.answer is not None:
                filled += 1
                continue
            field = resolution.field
            if resolution.question is not None:
                asked += 1
            else:
                blank += 1
            options = [o.label for o in usable_options(field)]
            question_rows.append(
                {
                    "run": run,
                    "ats": target.get("ats", ""),
                    "company": target.get("company", ""),
                    "url": target.get("url", ""),
                    "question": (field.display_label or field.attr_label or "")[:200],
                    "control": getattr(field.control, "value", str(field.control)),
                    "how_it_works": getattr(field.operation, "value", str(field.operation)),
                    "required": "yes" if field.required else "no",
                    "option_count": len(options),
                    # Enough to see what kind of answer it wants, not the whole
                    # of a 199-country list.
                    "options": " | ".join(options[:8])[:300],
                    "why_not_filled": _why(resolution)[:160],
                }
            )

        total = filled + asked + blank
        score_rows.append(
            {
                "run": run, "when": when, "version": version, "note": note,
                "ats": target.get("ats", ""), "company": target.get("company", ""),
                "title": target.get("title", "")[:80], "url": target.get("url", ""),
                "fields": total, "filled": filled, "asked": asked, "left_blank": blank,
                "percent_filled": f"{(filled / total * 100):.0f}" if total else "",
            }
        )

    _append(SCOREBOARD, SCORE_COLUMNS, score_rows)
    _append(QUESTIONS, QUESTION_COLUMNS, question_rows)

    fields = sum(r["fields"] for r in score_rows)
    filled = sum(r["filled"] for r in score_rows)
    asked = sum(r["asked"] for r in score_rows)
    print(f"run {run} -- version {version}" + (f" -- {note}" if note else ""))
    print(f"  {len(score_rows)} applications, {fields} fields")
    print(f"  filled {filled} ({filled / fields * 100:.0f}%), asked {asked}, "
          f"left blank {fields - filled - asked}")
    print(f"\n  {SCOREBOARD.relative_to(ROOT)}")
    print(f"  {QUESTIONS.relative_to(ROOT)}")

    _show_kinds(question_rows)
    return 0


def _show_kinds(rows: list[dict]) -> None:
    """What the unanswered ones are, by the kind of control they use."""
    kinds = Counter((r["control"], r["how_it_works"]) for r in rows)
    print("\n  what is left, by the kind of control:")
    for (control, how), count in kinds.most_common(10):
        print(f"    {count:5}  {control:12} worked by {how}")


def _append(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if fresh:
            writer.writeheader()
        writer.writerows(rows)


def compare() -> int:
    """Every run so far, side by side."""
    if not SCOREBOARD.exists():
        print("nothing recorded yet")
        return 1
    with SCOREBOARD.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    by_run: dict[str, list[dict]] = {}
    for row in rows:
        by_run.setdefault(row["run"], []).append(row)

    print(f"{'run':>4}  {'version':<9} {'forms':>6} {'fields':>7} {'filled':>7} "
          f"{'%':>4}  {'asked':>6}  note")
    print("-" * 78)
    previous = None
    for run in sorted(by_run, key=int):
        group = by_run[run]
        fields = sum(int(r["fields"]) for r in group)
        filled = sum(int(r["filled"]) for r in group)
        asked = sum(int(r["asked"]) for r in group)
        pct = filled / fields * 100 if fields else 0
        move = ""
        if previous is not None:
            delta = filled - previous
            move = f"  ({delta:+d})" if delta else "  (no change)"
        previous = filled
        print(f"{run:>4}  {group[0]['version']:<9} {len(group):>6} {fields:>7} "
              f"{filled:>7} {pct:>3.0f}%  {asked:>6}  {group[0]['note'][:28]}{move}")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", default="", help="what changed since the last run")
    parser.add_argument("--compare", action="store_true", help="show every run so far")
    args = parser.parse_args()
    return compare() if args.compare else record(args.note)


if __name__ == "__main__":
    raise SystemExit(main())

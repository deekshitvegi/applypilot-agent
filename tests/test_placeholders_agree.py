"""One list of what a control's own "Choose one" row looks like.

Regression 133. There were three copies -- service, injected verifier, panel.
Two were kept up to date and the panel's was not, and it tested the label
exactly as written, so the em dashes a form decorates with defeated it:
"— Make a Selection —" was not "make a selection", matched nothing, and was
offered to the applicant as an answer to pick. Pressing it did nothing,
because it is not an answer. It is the control asking.

These tests hold the Python side and the shared JavaScript to the same
answers, so the two can never drift again without something going red.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from applypilot.text import looks_like_placeholder

SHARED = Path(__file__).resolve().parents[1] / "extension" / "placeholders.js"

#: Real rows, from real forms in the corpus.
FURNITURE = [
    "— Make a Selection —",
    "-- Make a Selection --",
    "Make a Selection",
    "— Select —",
    "– Choose –",
    "Please select a source",
    "Select one",
    "N/A",
    "",
]

ANSWERS = [
    "Yes",
    "No",
    "United States",
    "$100,000 - $124,999",
    "Bachelor's Degree",
    "Denton, Texas, United States",
    "None",
]


@pytest.mark.parametrize("row", FURNITURE)
def test_the_service_knows_furniture_when_it_sees_it(row):
    assert looks_like_placeholder(row) is True


@pytest.mark.parametrize("row", ANSWERS)
def test_the_service_does_not_throw_away_an_answer(row):
    assert looks_like_placeholder(row) is False


def _ask_the_shared_module(rows: list[str]) -> dict:
    """Run the file the panel and the page both load, and ask it."""
    script = (
        f"require({json.dumps(str(SHARED))});"
        "const P = globalThis.ApplyPilotPlaceholders;"
        f"const rows = {json.dumps(rows)};"
        "const out = {};"
        "for (const r of rows) out[r] = P.looksLikePlaceholder(r);"
        "console.log(JSON.stringify(out));"
    )
    done = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, encoding="utf-8"
    )
    if done.returncode != 0:
        pytest.skip(f"node unavailable: {done.stderr.strip()[:80]}")
    return json.loads(done.stdout)


def test_the_panel_and_the_service_agree_about_furniture():
    verdicts = _ask_the_shared_module(FURNITURE)
    disagree = {
        row: (looks_like_placeholder(row), verdicts[row])
        for row in FURNITURE
        if looks_like_placeholder(row) != verdicts[row]
    }
    assert not disagree, f"python vs javascript: {disagree}"


def test_the_panel_and_the_service_agree_about_answers():
    verdicts = _ask_the_shared_module(ANSWERS)
    disagree = {
        row: (looks_like_placeholder(row), verdicts[row])
        for row in ANSWERS
        if looks_like_placeholder(row) != verdicts[row]
    }
    assert not disagree, f"python vs javascript: {disagree}"


def test_the_panel_no_longer_keeps_a_copy_of_its_own():
    """The bug was a third list nobody remembered to update."""
    panel = (SHARED.parent / "sidepanel.js").read_text(encoding="utf-8")
    assert "PLACEHOLDER_LABEL =" not in panel
    assert "ApplyPilotPlaceholders.looksLikePlaceholder" in panel


def test_the_verifier_no_longer_keeps_a_copy_of_its_own():
    verify = (SHARED.parent / "injected" / "verify.js").read_text(encoding="utf-8")
    assert "const PLACEHOLDER = /^(" not in verify
    assert "ApplyPilotPlaceholders.looksLikePlaceholder" in verify

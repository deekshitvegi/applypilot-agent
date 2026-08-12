"""Counting a question that keeps coming back, in the shipping sidepanel.js.

A report was a photograph: the state of the page at the moment somebody pressed
Save. The failures worth reporting are not states.

"Sometimes even after I answer a question the model still keeps asking me the
question again and again" -- and a snapshot of that page is indistinguishable
from a snapshot of a page whose question is being asked for the first time. The
count is the only thing that separates them, so it is kept as it happens.

These drive the real functions out of the shipped file rather than a copy, so
the counting cannot drift away from what the panel actually does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

PANEL_JS = Path(__file__).resolve().parents[1] / "extension" / "sidepanel.js"


def _lift(*names: str) -> str:
    """Pull named top-level functions out of the panel, with a state to run on.

    sidepanel.js talks to a live tab the moment it loads, so it cannot simply
    be script-tagged into a blank page. The functions under test are pure
    bookkeeping over `state`, and are lifted out whole -- text unchanged, so a
    rewrite that breaks them breaks this.
    """
    source = PANEL_JS.read_text(encoding="utf-8")
    parts = []
    for name in names:
        match = re.search(
            rf"^function {name}\(.*?^\}}", source, re.MULTILINE | re.DOTALL
        )
        assert match, f"{name} is no longer a top-level function in sidepanel.js"
        parts.append(match.group(0))
    return "\n".join(parts)


@pytest.fixture
def panel(playwright_browser):
    context = playwright_browser.new_context()
    page = context.new_page()
    page.add_script_tag(
        content="""
        const state = { journal: [], asked: new Map() };
        const JOURNAL_LIMIT = 400;
        function log() {}
        """
        + _lift("note", "askKey", "countAsk")
    )
    yield page
    context.close()


def ask(page, label, times=1):
    for _ in range(times):
        seen = page.evaluate(
            "(label) => countAsk({ label: label, reason: 'r', required: true })", label
        )
    return seen


def test_the_first_ask_counts_as_one(panel):
    assert ask(panel, "Are you based in a US timezone?") == 1


def test_the_same_question_coming_round_again_is_counted(panel):
    assert ask(panel, "How Did You Hear About Us?") == 1
    assert ask(panel, "How Did You Hear About Us?") == 2
    assert ask(panel, "How Did You Hear About Us?") == 3


def test_it_is_counted_by_its_words_not_its_fingerprint(panel):
    """An application that rebuilds itself hands out new fingerprints.

    Counting by fingerprint would call the same question, asked again after a
    rebuild, a brand new question -- which is precisely the case that needs
    catching.
    """
    first = panel.evaluate(
        "() => countAsk({ label: 'Device Type', fingerprint: 'f1' })"
    )
    second = panel.evaluate(
        "() => countAsk({ label: 'Device Type', fingerprint: 'CHANGED' })"
    )
    assert (first, second) == (1, 2)


def test_wording_is_compared_without_case_or_stray_space(panel):
    panel.evaluate("() => countAsk({ label: 'County' })")
    assert panel.evaluate("() => countAsk({ label: '  county  ' })") == 2


def test_different_questions_are_counted_apart(panel):
    assert ask(panel, "First Name") == 1
    assert ask(panel, "Last Name") == 1


def test_every_ask_is_written_into_the_journal(panel):
    ask(panel, "Device Type", times=2)
    journal = panel.evaluate("() => state.journal")
    assert [entry["kind"] for entry in journal] == ["asked", "asked"]
    assert [entry["times"] for entry in journal] == [1, 2]
    assert all(entry["at"] for entry in journal)


def test_an_answer_that_was_taken_but_not_kept_is_recorded(panel):
    panel.evaluate(
        "() => note('not_remembered', 'Gender', { reason: 'voluntary questions"
        " are not remembered unless you say so' })"
    )
    entry = panel.evaluate("() => state.journal[0]")
    assert entry["kind"] == "not_remembered"
    assert entry["what"] == "Gender"
    assert "voluntary" in entry["reason"]


def test_an_instruction_that_changed_nothing_is_recorded(panel):
    panel.evaluate(
        "() => note('chat_result', 'change my work dates to July 2024',"
        " { outcome: 'failed', evidence: 'the control is no longer on the page' })"
    )
    entry = panel.evaluate("() => state.journal[0]")
    assert entry["kind"] == "chat_result"
    assert entry["outcome"] == "failed"


def test_the_journal_does_not_grow_without_end(panel):
    """A form left open all afternoon must not fill memory."""
    panel.evaluate("() => { for (let i = 0; i < 500; i++) note('asked', 'q' + i); }")
    assert panel.evaluate("() => state.journal.length") == 400
    # The oldest are the ones dropped, so the end of a long session survives.
    assert panel.evaluate("() => state.journal[state.journal.length - 1].what") == "q499"

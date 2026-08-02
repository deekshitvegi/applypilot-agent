"""What the panel's main button offers, driven through the shipping cta.js.

The button is the only control most runs ever use. When its order of
precedence was wrong the whole tool did nothing on certain pages while
reporting that it had, so the order is pinned here rather than left to be
read off the source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

CTA_JS = Path(__file__).resolve().parents[1] / "extension" / "cta.js"


@pytest.fixture
def decide(playwright_browser):
    """Call ApplyPilotCta.decide with the real file loaded."""
    context = playwright_browser.new_context()
    page = context.new_page()
    page.add_script_tag(path=str(CTA_JS))

    def _decide(view):
        return page.evaluate("(view) => ApplyPilotCta.decide(view)", view)

    yield _decide
    context.close()


def page_with(fields=1, **extra):
    observation = {"fields": [{"fingerprint": f"f{i}"} for i in range(fields)]}
    observation.update(extra)
    return observation


def plan_with(actions=0):
    return {"actions": [{"fingerprint": f"a{i}"} for i in range(actions)]}


# ---------------------------------------------------------------------------
# 111. A question nobody can answer does not stop the fields that can be filled.
# ---------------------------------------------------------------------------


def test_fields_ready_to_fill_win_over_an_outstanding_question(decide):
    """The bug this file exists for.

    An iCIMS account-creation form had twenty-two fields with answers waiting
    and two required questions -- the resume, and "Login", which asks for an
    account this tool will not create. Asking came first, so the button became
    a scroll-to-the-question, the twenty-two were never carried out, and the
    panel read "Completed (0)". Outstanding could never reach zero, so the
    button never came back.
    """
    choice = decide(
        {
            "observation": page_with(fields=33),
            "plan": plan_with(actions=22),
            "outstanding": 2,
            "submissionPolicy": "manual",
        }
    )
    assert choice["action"] == "fill"
    assert choice["label"] == "Fill this page"
    # And it says the questions are still coming, rather than claiming
    # everything else is already done.
    assert "2 question(s) for you" in choice["note"]


def test_the_questions_are_offered_once_there_is_nothing_left_to_fill(decide):
    choice = decide(
        {
            "observation": page_with(fields=33),
            "plan": plan_with(actions=0),
            "outstanding": 2,
            "submissionPolicy": "manual",
        }
    )
    assert choice["action"] == "focus"
    assert choice["label"] == "Answer 2 questions"


def test_one_outstanding_question_is_not_pluralised(decide):
    choice = decide(
        {"observation": page_with(), "plan": plan_with(0), "outstanding": 1}
    )
    assert choice["label"] == "Answer 1 question"


def test_a_page_that_has_not_been_scanned_offers_a_scan(decide):
    choice = decide({"observation": None, "plan": None, "outstanding": 0})
    assert choice["action"] == "scan"


def test_a_scanned_page_with_no_fields_offers_a_scan(decide):
    choice = decide({"observation": {"fields": []}, "plan": plan_with(3), "outstanding": 0})
    assert choice["action"] == "scan"


# ---------------------------------------------------------------------------
# Filling still does not run past the end of the page on its own.
# ---------------------------------------------------------------------------


def test_continue_is_offered_when_the_page_is_filled_and_has_a_next(decide):
    choice = decide(
        {
            "observation": page_with(next_controls=[{"text": "Save & Continue"}]),
            "plan": plan_with(0),
            "outstanding": 0,
        }
    )
    assert choice["action"] == "next"
    assert 'Presses "Save & Continue"' in choice["note"]


def test_final_submit_is_refused_unless_it_was_set_deliberately(decide):
    choice = decide(
        {
            "observation": page_with(submit_controls=[{"text": "Submit Profile"}]),
            "plan": plan_with(0),
            "outstanding": 0,
            "submissionPolicy": "manual",
        }
    )
    assert choice["action"] == "none"
    assert choice["disabled"] is True
    assert 'Press "Submit Profile" yourself' == choice["label"]


def test_final_submit_is_offered_only_on_the_saved_policy(decide):
    choice = decide(
        {
            "observation": page_with(submit_controls=[{"text": "Submit Profile"}]),
            "plan": plan_with(0),
            "outstanding": 0,
            "submissionPolicy": "auto",
        }
    )
    assert choice["action"] == "submit"
    assert choice["disabled"] is False


def test_a_question_still_outranks_pressing_continue(decide):
    """Filling beats asking; asking still beats moving the page on."""
    choice = decide(
        {
            "observation": page_with(next_controls=[{"text": "Next"}]),
            "plan": plan_with(0),
            "outstanding": 1,
        }
    )
    assert choice["action"] == "focus"

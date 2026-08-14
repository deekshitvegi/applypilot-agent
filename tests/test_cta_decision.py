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
# A job description with an Apply button on it.
#
# 58 of 125 real job URLs landed on one of these, including every one served
# by one large ATS. The button read "Scan this page", which scanned, found the
# same nothing, and said it again. The form was a click away every time and
# the click was never offered.
# ---------------------------------------------------------------------------


def test_a_listing_offers_to_open_the_application(decide):
    choice = decide(
        {
            "observation": {
                "fields": [],
                "kind": "listing",
                "apply_controls": [{"text": "Apply", "fingerprint": "b1"}],
            },
            "plan": plan_with(0),
            "outstanding": 0,
        }
    )
    assert choice["action"] == "apply"
    assert 'Presses "Apply"' in choice["note"]


def test_opening_a_form_is_described_as_committing_to_nothing(decide):
    """Because it does not, and the tool refuses plenty that does."""
    choice = decide(
        {
            "observation": {
                "fields": [],
                "kind": "board",
                "apply_controls": [{"text": "Apply Manually"}],
            },
            "plan": plan_with(0),
            "outstanding": 0,
        }
    )
    assert "Nothing is sent" in choice["note"]


def test_a_form_with_fields_is_never_navigated_away_from(decide):
    """Plenty of applications carry an Apply control that is their own submit.

    Filling outranks opening, so a page with work to do keeps it.
    """
    choice = decide(
        {
            "observation": {
                "fields": [{"fingerprint": "f1"}],
                "kind": "application",
                "apply_controls": [{"text": "Apply"}],
            },
            "plan": plan_with(4),
            "outstanding": 0,
        }
    )
    assert choice["action"] == "fill"


def test_an_application_is_not_re_opened_even_with_nothing_to_fill(decide):
    choice = decide(
        {
            "observation": {
                "fields": [{"fingerprint": "f1"}],
                "kind": "application",
                "apply_controls": [{"text": "Apply"}],
                "submit_controls": [{"text": "Submit application"}],
            },
            "plan": plan_with(0),
            "outstanding": 0,
        }
    )
    assert choice["action"] != "apply"


def test_a_question_outranks_opening_a_new_form(decide):
    """Walking off a page with an unanswered question loses the answer."""
    choice = decide(
        {
            "observation": {
                "fields": [{"fingerprint": "f1"}],
                "kind": "listing",
                "apply_controls": [{"text": "Apply"}],
            },
            "plan": plan_with(0),
            "outstanding": 2,
        }
    )
    assert choice["action"] == "focus"


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
    assert choice["label"] == 'Press "Submit Profile" yourself'


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


def test_a_page_that_wants_an_account_is_still_filled(decide):
    """Regression 127, and the reason this decision has only one home.

    Pressing Start asked for "application" exactly, so a page classified as
    account creation was scanned, planned, and then walked straight past --
    silently, with twenty-two answers ready and on screen. Most of the
    account-creation forms there are behave this way, and filling everything
    except the credentials is precisely what the panel says it will do with
    them.
    """
    choice = decide(
        {
            "observation": page_with(fields=35, kind="registration"),
            "plan": plan_with(actions=22),
            "outstanding": 0,
            "submissionPolicy": "confirm",
        }
    )
    assert choice["action"] == "fill"


@pytest.mark.parametrize("kind", ["application", "registration", "listing", "unknown"])
def test_what_the_page_is_called_never_decides_it(decide, kind):
    """Only whether there is anything to do."""
    with_work = decide(
        {"observation": page_with(fields=9, kind=kind), "plan": plan_with(4), "outstanding": 0}
    )
    without = decide(
        {"observation": page_with(fields=9, kind=kind), "plan": plan_with(0), "outstanding": 0}
    )
    assert with_work["action"] == "fill", kind
    assert without["action"] != "fill", kind


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

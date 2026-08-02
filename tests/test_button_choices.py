"""Regression 92: a question whose answers are buttons.

One widely used applicant tracking system draws every Yes/No question as two
bare <button> elements -- no role, no name, no value, not even an aria-checked,
only class names. Nothing about them said "control", so a whole section of
questions was invisible: not unanswered, never seen, and never asked about.
"""

from __future__ import annotations

import pytest

from applypilot.models import PageObservation

pytestmark = pytest.mark.browser


def observe(page) -> PageObservation:
    return PageObservation.model_validate(page.evaluate("() => ApplyPilot.scan.run()"))


def question(page, needle: str):
    return next(f for f in observe(page).fields if needle.lower() in (f.label or "").lower())


def test_a_row_of_buttons_is_seen_as_a_question(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "work visa")
    assert field.control == "radio"
    assert [o.label for o in field.options] == ["Yes", "No"]
    assert field.value == "", "nothing is chosen yet"


def test_more_than_two_options_work_too(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "prefer to work")
    assert [o.label for o in field.options] == ["Remote", "Hybrid", "On site"]


def test_the_navigation_row_is_not_a_question(open_fixture):
    """Back beside Next is the same shape and is not something to answer."""
    page = open_fixture("button_choices.html")
    labels = [f.label for f in observe(page).fields]
    assert not any("Back" in (label or "") for label in labels), labels
    assert all("Next" not in (label or "") for label in labels), labels


def test_choosing_presses_the_button_and_reads_the_page_back(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "work visa")

    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": field.fingerprint, "option_label": "No"},
    )
    assert result["outcome"] == "verified", result
    assert result["observed"] == "No"
    # Read from the page's own marking, not from the fact that a click happened.
    assert result["signal"] == "page_class_state"
    assert page.evaluate(
        "() => document.querySelector('.yesno .picked').textContent.trim()"
    ) == "No"


def test_an_answer_already_there_is_left_alone(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "work visa")
    action = {"kind": "choose", "fingerprint": field.fingerprint, "option_label": "No"}
    page.evaluate("async (a) => await ApplyPilot.act.perform(a)", action)

    page.evaluate("() => { window.presses = 0; "
                  "for (const b of document.querySelectorAll('.yesno button')) "
                  "b.addEventListener('click', () => window.presses++); }")
    again = page.evaluate("async (a) => await ApplyPilot.act.perform(a)", action)
    assert again["outcome"] == "verified"
    assert page.evaluate("() => window.presses") == 0, "pressing again would toggle it off"


def test_an_option_the_question_does_not_offer_is_refused(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "work visa")
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": field.fingerprint, "option_label": "Maybe"},
    )
    assert result["outcome"] == "failed", result
    assert "not one of the options" in result["evidence"]


def test_the_question_it_asks_is_the_one_above_the_buttons(open_fixture):
    page = open_fixture("button_choices.html")
    field = question(page, "3 years")
    assert field.label == "Do you have at least 3 years of professional experience?"


def test_a_marker_drawn_by_css_still_makes_it_required(open_fixture):
    """The asterisk is not in the text: the class is the only thing that says so.

    Every screening question on one real form is marked this way, so all of
    them read as optional, were left blank, and were never asked about.
    """
    page = open_fixture("button_choices.html")
    field = question(page, "3 years")
    assert "*" not in (field.label or ""), "the marker is drawn, not written"
    assert field.required is True


def test_a_question_with_no_marker_is_still_optional(open_fixture):
    page = open_fixture("button_choices.html")
    assert question(page, "prefer to work").required is False

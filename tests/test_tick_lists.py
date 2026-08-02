"""Regression 97: a list of tick boxes under one heading is one question.

"Which of these have you used?" followed by eight boxes was read as eight
questions. Each is then a checkbox called "OpenAI" that answers to no saved
fact and carries no requirement of its own -- the asterisk belongs to the
question above them -- so the whole list was left blank and never asked about.
"""

from __future__ import annotations

import pytest

from applypilot.models import PageObservation

pytestmark = pytest.mark.browser


def observe(page) -> PageObservation:
    return PageObservation.model_validate(page.evaluate("() => ApplyPilot.scan.run()"))


def field(page, control: str):
    return next(f for f in observe(page).fields if f.control == control)


def providers(page):
    """The LLM providers list. There is more than one list on this page."""
    return next(f for f in observe(page).fields if "LLM providers" in (f.label or ""))


def test_the_list_is_one_question_with_its_own_options(open_fixture):
    page = open_fixture("tick_lists.html")
    got = providers(page)
    assert got.label == "Have you used any of the following LLM providers professionally?"
    assert [o.label for o in got.options] == ["OpenAI", "Anthropic", "Gemini", "None"]


def test_its_boxes_are_not_also_offered_one_at_a_time(open_fixture):
    page = open_fixture("tick_lists.html")
    labels = [f.label for f in observe(page).fields]
    assert "OpenAI" not in labels, labels
    assert "Anthropic" not in labels, labels


def test_a_box_on_its_own_stays_its_own_question(open_fixture):
    """A page whose every input is a tick box has an ancestor holding them all.

    That ancestor is not a question, and a lone agreement further down must not
    be swallowed into it.
    """
    page = open_fixture("tick_lists.html")
    solo = field(page, "checkbox")
    assert solo.label == "I have read and agree to the terms"


def test_the_question_beside_it_keeps_its_own_name(open_fixture):
    """A greedy list once came back wearing the neighbouring question's name."""
    page = open_fixture("tick_lists.html")
    assert field(page, "radio").label == "Do you need a work visa?"


def test_ticking_one_is_verified_from_the_boxes(open_fixture):
    page = open_fixture("tick_lists.html")
    got = providers(page)
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": got.fingerprint, "option_label": "Anthropic"},
    )
    assert result["outcome"] == "verified", result
    assert result["observed"] == "Anthropic"
    assert result["signal"] == "native_checked"
    assert page.evaluate("() => document.querySelector('[name=p2]').checked") is True


def test_ticking_it_again_does_not_clear_it(open_fixture):
    page = open_fixture("tick_lists.html")
    got = providers(page)
    action = {"kind": "choose", "fingerprint": got.fingerprint, "option_label": "Anthropic"}
    page.evaluate("async (a) => await ApplyPilot.act.perform(a)", action)
    again = page.evaluate("async (a) => await ApplyPilot.act.perform(a)", action)
    assert again["outcome"] == "verified"
    assert page.evaluate("() => document.querySelector('[name=p2]').checked") is True


def test_an_option_it_does_not_offer_is_refused(open_fixture):
    page = open_fixture("tick_lists.html")
    got = providers(page)
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": got.fingerprint, "option_label": "Cohere"},
    )
    assert result["outcome"] == "failed", result
    assert "not one of the options" in result["evidence"]


def test_something_already_ticked_is_left_where_it_is(open_fixture):
    page = open_fixture("tick_lists.html")
    page.evaluate("() => document.querySelector('[name=p1]').click()")
    got = providers(page)
    page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": got.fingerprint, "option_label": "Gemini"},
    )
    assert page.evaluate("() => document.querySelector('[name=p1]').checked") is True
    assert page.evaluate("() => document.querySelector('[name=p3]').checked") is True


def test_a_list_marked_required_is_required(open_fixture):
    """The marker belongs to the question above the whole list.

    From any single box that is two levels up -- one further than the marker
    search reaches -- so a required list read as optional and was skipped
    without ever being asked about. It is asked of the list now.
    """
    page = open_fixture("tick_lists.html")
    got = next(
        f for f in observe(page).fields if "LLM providers" in (f.label or "")
    )
    assert got.required is True


def test_a_list_that_is_not_marked_stays_optional(open_fixture):
    page = open_fixture("tick_lists.html")
    got = next(
        f for f in observe(page).fields if "happy to be contacted" in (f.label or "")
    )
    assert got.required is False

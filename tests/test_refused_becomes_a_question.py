"""What the page turned down is put to the person, not tried again.

Regression 132. A required field can fail, be planned again from the same
saved answer, fail again, and never once be asked about -- a dead end you can
see on screen and have no way to clear. A control that refused an answer
refuses it every time; the person sitting there can answer it in a moment.
"""

from __future__ import annotations

import pytest

from applypilot import runloop
from applypilot.models import (
    ControlKind,
    FieldObservation,
    Operation,
    Option,
    PageObservation,
    Profile,
)

VETERAN = (
    "Are you a Veteran of the United States Military with a discharge of "
    "honorable, under honorable conditions, or general discharge?"
)


def page() -> PageObservation:
    return PageObservation(
        url="https://example.test/apply",
        title="Apply",
        signature="s",
        fields=[
            FieldObservation(
                fingerprint="vet",
                label=VETERAN,
                display_label=VETERAN,
                control=ControlKind.SELECT,
                operation=Operation.LIST_PRESENT,
                section="Screening Questions",
                required=True,
                visible=True,
                options=[Option(label=o, value=o) for o in ["— Make a Selection —", "Yes", "No"]],
            ),
            FieldObservation(
                fingerprint="name",
                label="First Name",
                display_label="First Name",
                control=ControlKind.TEXT,
                operation=Operation.FREE_TEXT,
                required=True,
                visible=True,
            ),
        ],
    )


PROFILE = Profile(
    # Veteran status is voluntary, and only answered at all when that has been
    # chosen deliberately. This test is about what happens after the page
    # refuses an answer, so it starts from one being given.
    answer_demographics=True,
    facts={
        "first_name": "Alex",
        "veteran_status": "No, I am not a veteran under one of the classifications listed above",
    },
)


def test_normally_it_is_filled_without_asking():
    plan = runloop.plan_page(page(), PROFILE)
    assert [a.fingerprint for a in plan.actions] == ["vet", "name"]
    assert plan.questions == []


def test_a_control_that_refused_is_asked_about_instead():
    plan = runloop.plan_page(page(), PROFILE, None, {"vet"})
    assert [a.fingerprint for a in plan.actions] == ["name"]
    assert [q.fingerprint for q in plan.questions] == ["vet"]


def test_the_question_says_what_was_tried():
    """"This needs you" over a control is not a question anybody can act on."""
    plan = runloop.plan_page(page(), PROFILE, None, {"vet"})
    question = plan.questions[0]
    assert "would not take" in question.reason
    assert '"No"' in question.reason


def test_the_question_carries_the_choices_to_pick_from():
    plan = runloop.plan_page(page(), PROFILE, None, {"vet"})
    question = plan.questions[0]
    assert [o.label for o in question.options] == ["Yes", "No"]
    assert question.control is ControlKind.SELECT


def test_everything_else_is_still_filled():
    plan = runloop.plan_page(page(), PROFILE, None, {"vet"})
    assert plan.actions[0].value == "Alex"


@pytest.mark.parametrize("refused", [None, set()])
def test_nothing_refused_changes_nothing(refused):
    plan = runloop.plan_page(page(), PROFILE, None, refused)
    assert len(plan.actions) == 2
    assert plan.questions == []

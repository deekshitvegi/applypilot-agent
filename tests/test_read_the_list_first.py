"""Read the list before choosing from it.

Regression 139. Having a saved answer is not the same as knowing the control
will take it. A veteran question on a live Oracle application is a box that
filters a list; handed the saved answer in full it answered "No results were
found" and the field stayed empty -- the answer visible in the box, above a
list saying there was no such thing.

Nothing here is a new path. It is the one a question already takes: open the
control, read what it offers, rank the saved answer against those, and choose
when one fits. Where it fits, nobody is asked anything.
"""

from __future__ import annotations

from applypilot import runloop
from applypilot.models import (
    ControlKind,
    FieldObservation,
    Operation,
    Option,
    PageObservation,
    Profile,
)

PROFILE = Profile(
    answer_demographics=True,
    facts={
        "first_name": "Alex",
        "country": "United States",
        "veteran_status": "No, I am not a veteran under one of the classifications listed above",
    },
)


def page(*fields: FieldObservation) -> PageObservation:
    return PageObservation(url="https://example.test/a", title="a", signature="s", fields=list(fields))


def unread_picker() -> FieldObservation:
    """A search box over a list it has not shown yet."""
    return FieldObservation(
        fingerprint="vet",
        label="Veteran Status",
        display_label="Veteran Status",
        control=ControlKind.COMBOBOX,
        operation=Operation.TYPE_TO_SEARCH,
        required=True,
        visible=True,
        placeholder="Search",
    )


def readable_list() -> FieldObservation:
    return FieldObservation(
        fingerprint="country",
        label="Country",
        display_label="Country",
        control=ControlKind.SELECT,
        operation=Operation.LIST_PRESENT,
        required=True,
        visible=True,
        options=[Option(label=o, value=o) for o in ["Select", "United States", "India"]],
    )


def test_a_list_we_have_not_read_is_opened_before_anything_is_chosen():
    plan = runloop.plan_page(page(unread_picker()), PROFILE)
    assert plan.actions == [], "acted on a list it had not read"
    assert [q.fingerprint for q in plan.questions] == ["vet"]
    assert "vet" in plan.needs_options


def test_it_carries_the_saved_answer_so_nobody_has_to_be_asked():
    """The point. Opening it is not the same as giving up on it."""
    plan = runloop.plan_page(page(unread_picker()), PROFILE)
    question = plan.questions[0]
    assert question.options_pending is True
    assert question.saved_value == PROFILE.facts["veteran_status"]


def test_a_list_already_readable_is_chosen_from_straight_away():
    """No extra round trip where the choices are already on the page."""
    plan = runloop.plan_page(page(readable_list()), PROFILE)
    assert [a.fingerprint for a in plan.actions] == ["country"]
    assert plan.actions[0].option_label == "United States"
    assert plan.questions == []


def test_a_text_box_is_never_sent_round_the_houses():
    box = FieldObservation(
        fingerprint="fn", label="First Name", display_label="First Name",
        control=ControlKind.TEXT, operation=Operation.FREE_TEXT,
        required=True, visible=True,
    )
    plan = runloop.plan_page(page(box), PROFILE)
    assert [a.value for a in plan.actions] == ["Alex"]
    assert plan.questions == []


def test_the_rest_of_the_page_is_still_filled_while_one_list_is_read():
    plan = runloop.plan_page(page(unread_picker(), readable_list()), PROFILE)
    assert [a.fingerprint for a in plan.actions] == ["country"]
    assert [q.fingerprint for q in plan.questions] == ["vet"]

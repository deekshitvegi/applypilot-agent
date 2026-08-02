"""Regression 89: a box asking you to agree to something.

Nothing in the fact catalogue answers one of these, and nothing should -- what
is being agreed to is different every time. So it fell through to "optional and
nothing saved answers it" and was left blank, which is how a step got refused
with an arbitration agreement unticked and nothing on screen saying why.

It is asked now, and never ticked from a saved answer however much its label
resembles a Yes/No the profile happens to hold.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import is_agreement, resolve_field
from applypilot.models import ControlKind, FieldObservation, Profile

ARBITRATION = "I have read and agree to the terms of the Mutual Arbitration Agreement."


def box(label: str, *, required: bool = True) -> FieldObservation:
    return FieldObservation(
        fingerprint="fagree", label=label, display_label=label,
        control=ControlKind.CHECKBOX, visible=True, required=required,
    )


@pytest.mark.parametrize(
    "label",
    [
        ARBITRATION,
        "I agree to the terms and conditions",
        "I accept the Terms & Conditions",
        "I consent to the processing of my personal data",
        "I certify that the information given is true and complete",
        "I acknowledge the Code of Conduct",
        "I have read the Privacy Policy",
    ],
)
def test_these_are_agreements(label):
    assert is_agreement(box(label)) is True


@pytest.mark.parametrize(
    "label",
    [
        "This is my most recent education",
        "Have you ever been employed by us before?",
        "Send me job alerts by email",
        "I am willing to relocate",
        "This is my current job",
    ],
)
def test_these_are_not(label):
    """A checkbox is not an agreement merely for being a checkbox."""
    assert is_agreement(box(label)) is False


def test_only_a_checkbox_can_be_one():
    field = box(ARBITRATION)
    field = field.model_copy(update={"control": ControlKind.TEXT})
    assert is_agreement(field) is False


def test_an_agreement_is_asked_and_never_left_blank():
    """Left blank is what got a step refused with nothing explaining it."""
    resolution = resolve_field(box(ARBITRATION), Profile())
    assert resolution.answer is None, "never ticked on anyone's behalf"
    assert resolution.question is not None
    assert "yours to read and accept" in resolution.question.reason
    assert resolution.skipped == ""


def test_it_is_asked_even_when_the_form_does_not_call_it_required():
    resolution = resolve_field(box(ARBITRATION, required=False), Profile())
    assert resolution.question is not None
    assert resolution.skipped == ""


def test_a_saved_yes_does_not_leak_into_it():
    """The profile holds plenty of Yes answers. None of them agree to anything."""
    profile = Profile(facts={"work_authorization": "Yes", "relocate": "Yes"})
    resolution = resolve_field(box(ARBITRATION), profile)
    assert resolution.answer is None
    assert resolution.question is not None


def test_switched_on_it_is_ticked_and_says_what_was_agreed_to():
    resolution = resolve_field(box(ARBITRATION), Profile(accept_agreements=True))
    assert resolution.answer is not None
    assert resolution.answer.value == "Yes"
    # The record of what was accepted, not just that something was.
    assert "Mutual Arbitration Agreement" in resolution.answer.reason


def test_the_setting_does_not_reach_anything_that_is_not_an_agreement():
    profile = Profile(accept_agreements=True)
    resolution = resolve_field(box("This is my most recent education"), profile)
    assert resolution.answer is None or resolution.answer.value != "Yes", resolution

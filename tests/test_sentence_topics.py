"""A fact's name buried in a long question does not make the question about it.

Found by replaying 35 real forms rather than by meeting it on a page. Across
that corpus the sentence-topic path wins about sixty matches; every one it won
for a fact holding contact or identity data was wrong, and one of those sat on
a free-text box, where a wrong match types rather than being caught by the
options not fitting.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import best_fact
from applypilot.models import ControlKind, FieldObservation, Option


def asked(label: str, control=ControlKind.TEXT, options=()) -> FieldObservation:
    return FieldObservation(
        fingerprint="q",
        label=label,
        display_label=label,
        control=control,
        visible=True,
        required=True,
        options=[Option(label=o, value=o) for o in options],
    )


# ---------------------------------------------------------------------------
# 116. A fact's own word inside a longer question stole the question.
# ---------------------------------------------------------------------------

WRONG = [
    # "mobile" is how half the world says phone.
    ("Do you have a minimum of 2 years of mobile engineering experience, "
     "not including internships?", "phone"),
    ("Have you contributed to a mobile app(s) that reached a large number "
     "of users?", "phone"),
    ("Are you familiar with or open to using AI tools (such as Github "
     "Copilot, ChatGPT, Cursor) in your workflow?", "github"),
    ("Are you currently based out of the New York City or San Francisco "
     "area, and able to work out of our office?", "city"),
]


@pytest.mark.parametrize("label,never", WRONG)
def test_a_buried_word_does_not_hand_over_the_question(label, never):
    match = best_fact(asked(label))
    assert match is None or match.spec.key != never, (
        f"{never!r} claimed {label!r}"
    )


def test_the_free_text_case_is_the_dangerous_one():
    """Nothing catches this one later.

    A choice that does not fit the options is refused when the answer is
    shaped. A text box takes whatever it is given, so a phone number would
    simply have been typed into an employer's form.
    """
    match = best_fact(
        asked("Have you contributed to a mobile app that reached many users?")
    )
    assert match is None or match.spec.key != "phone"


# ---------------------------------------------------------------------------
# What the same path is for, and must keep doing.
# ---------------------------------------------------------------------------

RIGHT = [
    ("Will you now or in the future require visa sponsorship?", "requires_sponsorship"),
    ("Do you now, or will you in the future, require immigration sponsorship "
     "to work at Reddit?", "requires_sponsorship"),
    ("How did you hear about this job?", "referral_source"),
    ("Have you ever worked for Figma before, as an employee or a "
     "contractor/consultant?", "previously_employed"),
    ("Are you a veteran/have you served in the military?", "veteran_status"),
    ("Do you live with a disability (as outlined by the ADA)?", "disability_status"),
    ("Are you a US citizen or lawful permanent resident?", "citizenship"),
    ("What country are you based in?", "country"),
]


@pytest.mark.parametrize("label,expected", RIGHT)
def test_a_question_about_a_circumstance_still_finds_its_fact(label, expected):
    match = best_fact(asked(label))
    assert match is not None, f"nothing matched {label!r}"
    assert match.spec.key == expected


# ---------------------------------------------------------------------------
# 117. "Location" is how most boards ask which city you are in.
# ---------------------------------------------------------------------------

LOCATIONS = ["Location (City)", "Current location", "Current City", "Your Location"]


@pytest.mark.parametrize("label", LOCATIONS)
def test_a_qualified_location_label_is_the_city(label):
    match = best_fact(asked(label, ControlKind.COMBOBOX))
    assert match is not None, f"nothing matched {label!r}"
    assert match.spec.key == "city"


def test_a_bare_location_is_left_to_the_block_it_sits_in():
    """Inside a job it is where that job was, not where you live.

    Claiming the bare word took an employment record's own field away from it,
    so only qualified wordings are claimed.
    """
    inside_a_job = FieldObservation(
        fingerprint="j",
        label="Location",
        display_label="Location",
        control=ControlKind.TEXT,
        section="Work Experience",
        group="exp-1",
        visible=True,
    )
    match = best_fact(inside_a_job)
    assert match is None or match.spec.key != "city"

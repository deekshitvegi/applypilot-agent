"""Regression 78: one saved answer was serving two different questions.

A form that asks "Are you Hispanic or Latino?" and "Race category" separately
was answering both from a single saved value. Picking a race wrote "Asian" where
a Yes/No belonged; answering the Yes/No wrote "No" over the race. Each answer
made the other question wrong again, so both were asked over and over however
many times they were answered.
"""

from __future__ import annotations

from applypilot.mapper import best_fact
from applypilot.models import ControlKind, FieldObservation, Option


def field(label: str, *options: str) -> FieldObservation:
    return FieldObservation(
        fingerprint="f" + label[:6],
        label=label,
        display_label=label,
        control=ControlKind.SELECT,
        required=True,
        visible=True,
        options=[Option(label=o) for o in options],
    )


HISPANIC = (
    "Are you Hispanic or Latino? (A person of Cuban, Mexican, Puerto Rican, "
    "South or Central American, or other Spanish culture or origin regardless of race.)"
)


def test_the_hispanic_question_is_not_the_race_question():
    hispanic = best_fact(field(HISPANIC, "Yes", "No", "I prefer not to answer"))
    race = best_fact(field("*Race category", "Asian", "White", "Two or More Races"))

    assert hispanic is not None and race is not None
    assert hispanic.spec.key == "hispanic_latino", hispanic.spec.key
    assert race.spec.key == "race_ethnicity", race.spec.key
    assert hispanic.spec.key != race.spec.key


def test_ethnic_category_stays_with_race():
    """It reads as the race question, and it is the heading above both."""
    match = best_fact(field("*Ethnic category", "Asian", "White"))
    assert match is not None and match.spec.key == "race_ethnicity"


def test_a_combined_question_is_still_the_race_one():
    """Plenty of forms ask it as one question with Hispanic among the answers."""
    match = best_fact(
        field("Race / Ethnicity", "Hispanic or Latino", "Asian", "White")
    )
    assert match is not None and match.spec.key == "race_ethnicity"


def test_answering_one_leaves_the_other_alone():
    from applypilot.mapper import resolve_field
    from applypilot.models import Profile

    profile = Profile(
        answer_demographics=True,
        facts={"race_ethnicity": "Asian", "hispanic_latino": "No"},
    )
    hispanic = resolve_field(
        field(HISPANIC, "Yes", "No", "I prefer not to answer"), profile
    )
    race = resolve_field(
        field("*Race category", "Asian", "White", "Two or More Races"), profile
    )

    assert hispanic.answer is not None and hispanic.answer.value == "No"
    assert race.answer is not None and race.answer.value == "Asian"

"""An optional box the saved answer does not fit is left blank, not asked about.

"How did you hear about us?" is optional, and its list held nothing resembling
what was saved. It became a question that had to be cleared before anything
else could happen -- over a box the employer was content to leave empty.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import resolve_field
from applypilot.models import ControlKind, FieldObservation, Option, Profile

SOURCES = [
    "— Make a Selection —",
    "Company Website",
    "Employee Referral",
    "Job Board",
    "Social Media",
]


def hear_about_us(required: bool) -> FieldObservation:
    return FieldObservation(
        fingerprint="hdyh",
        label="How did you hear about us?",
        display_label="How did you hear about us?",
        section="Screening Questions",
        control=ControlKind.SELECT,
        visible=True,
        required=required,
        options=[Option(label=x, value=x) for x in SOURCES],
    )


#: Whatever put it there, "Yes" is not one of the sources on offer.
PROFILE = Profile(facts={"referral_source": "Yes"})


# ---------------------------------------------------------------------------
# 114. An optional field nothing saved fits is left blank rather than asked.
# ---------------------------------------------------------------------------


def test_an_optional_field_the_saved_answer_does_not_fit_is_left_blank():
    r = resolve_field(hear_about_us(required=False), PROFILE)
    assert r.question is None, "an optional box must not hold up the page"
    assert r.answer is None
    assert "nothing saved fits" in r.skipped


def test_the_same_field_is_still_asked_about_when_the_form_insists():
    """Required is the whole difference. The form said it wanted this one."""
    r = resolve_field(hear_about_us(required=True), PROFILE)
    assert r.question is not None
    assert "'Yes'" in r.question.reason


def test_a_saved_answer_that_does_fit_is_still_filled():
    r = resolve_field(
        hear_about_us(required=False), Profile(facts={"referral_source": "Job Board"})
    )
    assert r.answer is not None
    assert r.answer.value == "Job Board"


@pytest.mark.parametrize("required", [True, False])
def test_a_learned_answer_that_does_not_fit_follows_the_same_rule(required):
    learned = {"how did you hear about us": "Yes"}
    r = resolve_field(hear_about_us(required=required), Profile(), learned)
    if required:
        assert r.question is not None
    else:
        assert r.question is None
        assert "nothing saved fits" in r.skipped

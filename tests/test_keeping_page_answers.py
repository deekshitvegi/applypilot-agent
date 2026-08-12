"""Answers a page was already holding, and the rot that got in through them.

Two halves of one problem, both found in a real profile.

Filling a form is not the only way an answer gets onto a page. People type one
in themselves -- because a dropdown was fiddly, because the question was about
this employer, because it was quicker than explaining. That answer was
respected and then thrown away, so the next form asked for it again.

And the answers that *were* saved were not all sound. A yes-or-no question had
matched a fact that holds an open value, and "Yes" went in. Afterwards "How did
you hear about us?" was answered "Yes" against eleven options, on every form,
because a saved answer is trusted ahead of asking. Four facts in one profile:
referral_source and citizenship both "Yes", a degree of "Yes", a preferred name
of "No".
"""

from __future__ import annotations

from applypilot.facts import BY_KEY, accepts
from applypilot.mapper import resolve_field
from applypilot.models import ControlKind, FieldObservation, Profile


def field(**kwargs) -> FieldObservation:
    base = {
        "fingerprint": "f",
        "label": "County",
        "control": ControlKind.TEXT,
        "required": True,
        "visible": True,
    }
    base.update(kwargs)
    return FieldObservation(**base)


# ---------------------------------------------------------------------------
# What a fact will accept
# ---------------------------------------------------------------------------


def test_a_bare_yes_never_lands_in_a_fact_that_means_something_open():
    """The four that were actually found in a profile."""
    for key, value in (
        ("referral_source", "Yes"),
        ("citizenship", "Yes"),
        ("education.degree", "Yes"),
        ("preferred_name", "No"),
    ):
        assert not accepts(BY_KEY[key], value), key


def test_the_same_facts_take_a_real_answer():
    for key, value in (
        ("referral_source", "Job Board"),
        ("citizenship", "United States"),
        ("education.degree", "Master of Science"),
        ("preferred_name", "Deek"),
    ):
        assert accepts(BY_KEY[key], value), key


def test_a_fact_that_is_a_yes_or_no_question_still_takes_one():
    for key in ("work_authorization", "requires_sponsorship", "over_18"):
        assert accepts(BY_KEY[key], "Yes")
        assert accepts(BY_KEY[key], "No")


def test_a_demographic_question_phrased_as_one_takes_a_no():
    """"Are you Hispanic or Latino?" is answered by "No" and nothing else.

    It declares no choices, so the rule cannot lean on those -- it leans on the
    prompt being that question, which is the thing that actually distinguishes
    it from "Citizenship status".
    """
    assert accepts(BY_KEY["hispanic_latino"], "No")


# ---------------------------------------------------------------------------
# Offering back what is already there
# ---------------------------------------------------------------------------


def test_an_answer_typed_by_hand_is_offered_rather_than_forgotten():
    resolution = resolve_field(field(value="Denton County"), Profile())
    assert resolution.skipped == "already answered on the page"
    assert resolution.learnable == "Denton County"


def test_it_is_not_offered_when_the_profile_already_says_the_same():
    profile = Profile(facts={"city": "Denton"})
    resolution = resolve_field(field(label="City", value="Denton"), profile)
    assert resolution.learnable == ""


def test_it_is_not_offered_when_it_was_already_remembered():
    """Offering the same answer on every visit turns a prompt into furniture."""
    resolution = resolve_field(
        field(label="County", value="Denton County"),
        Profile(),
        {"county": "Denton County"},
    )
    assert resolution.learnable == ""


def test_an_empty_field_offers_nothing():
    assert resolve_field(field(value=""), Profile()).learnable == ""


def test_a_placeholder_sitting_in_a_control_is_not_an_answer():
    assert resolve_field(field(value="Please select"), Profile()).learnable == ""


def test_a_password_is_never_learned():
    resolution = resolve_field(
        field(label="Password", control=ControlKind.PASSWORD, value="hunter2"),
        Profile(),
        None,
        True,
    )
    assert resolution.learnable == ""


def test_an_account_name_beside_a_password_is_never_learned():
    resolution = resolve_field(
        field(label="Username", value="deek"), Profile(), None, True
    )
    assert resolution.learnable == ""


def test_a_value_a_page_wrote_for_itself_is_not_offered():
    """A total, a generated reference, a date already written in."""
    assert resolve_field(field(value="REQ-40182", readonly=True), Profile()).learnable == ""
    assert resolve_field(field(value="REQ-40182", disabled=True), Profile()).learnable == ""


def test_a_yes_on_a_page_is_not_offered_to_a_fact_that_cannot_hold_one():
    """The guard runs before the offer, not only at the point of saving.

    Otherwise the panel shows a Keep button that produces an error when it is
    pressed, which teaches people to ignore the button.
    """
    resolution = resolve_field(
        field(label="How did you hear about us?", value="Yes"), Profile()
    )
    assert resolution.learnable == ""


def test_an_optional_field_someone_filled_in_is_offered_too():
    """Not only required ones -- optional is where hand-typed answers live."""
    resolution = resolve_field(field(label="County", value="Denton County", required=False), Profile())
    assert resolution.learnable == "Denton County"

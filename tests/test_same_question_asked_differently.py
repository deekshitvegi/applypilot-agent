"""Regression 80: the same fact, asked at a different resolution.

A saved "25" answers a form offering "18-24 / 25-35 / 36-50". It is the same
fact; only the granularity of the question changed. The arithmetic is done here
rather than guessed at, so the answer is either right or the question is handed
back -- two bands both containing the number is a tie, and a tie is not a coin
flip.

Regression 81: a request in front of a field name is manners, not the name.
"Please identify your Veteran status" is the veteran status field, and a whole
self-identification section went unasked because it did not look like one.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import best_fact
from applypilot.matching import band_contains, best_option
from applypilot.models import ControlKind, FieldObservation, Option


def opts(*labels: str) -> list[Option]:
    return [Option(label=label) for label in labels]


def ask(label: str) -> FieldObservation:
    return FieldObservation(
        fingerprint="f", label=label, display_label=label,
        control=ControlKind.SELECT, visible=True,
    )


# ---------------------------------------------------------------------------
# The same fact, asked at a different resolution.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saved", "offered", "expected"),
    [
        ("25", ["18-24", "25-35", "36-50", "51-100"], "25-35"),
        ("25", ["Under 18", "18 to 24", "25 to 34", "35 or older"], "25 to 34"),
        ("17", ["Under 18", "18-24", "25-34"], "Under 18"),
        ("62", ["0-50", "50+"], "50+"),
        ("3.34", ["Below 3.0", "3.0-3.5", "3.5-4.0"], "3.0-3.5"),
        ("8", ["Less than 5 years", "5 to 10 years", "More than 10 years"], "5 to 10 years"),
        ("12", ["at least 10", "up to 9"], "at least 10"),
    ],
)
def test_a_number_finds_the_band_it_belongs_to(saved, offered, expected):
    match = best_option(saved, opts(*offered))
    assert match is not None, f"{saved} found nothing in {offered}"
    assert match.option.label == expected


def test_two_bands_that_both_fit_is_a_question_not_a_guess():
    assert best_option("25", opts("20-30", "24-26")) is None


def test_a_number_outside_every_band_is_a_question():
    assert best_option("200", opts("18-24", "25-35")) is None


def test_a_band_is_only_a_band_when_that_is_all_it_says():
    """"Building 25-35" is a place. Only a label that is entirely a range."""
    assert band_contains("25-35", 25) is True
    assert band_contains("Building 25-35", 25) is False
    assert band_contains("25 to 35", 30) is True
    assert band_contains("Grade 3.0-3.5", 3.2) is False


def test_text_that_merely_contains_a_number_is_not_a_band():
    assert band_contains("Class of 2025", 2025) is False
    assert band_contains("Level 3", 3) is False


def test_nothing_numeric_about_the_saved_answer_changes_nothing():
    match = best_option("Texas", opts("Alabama", "Texas", "18-24"))
    assert match is not None and match.option.label == "Texas"


# ---------------------------------------------------------------------------
# A request in front of a field name.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "key"),
    [
        ("Please identify your Veteran status", "veteran_status"),
        ("Please indicate your Veteran status", "veteran_status"),
        ("Please select your Gender", "gender"),
        ("Tell us your LinkedIn profile", "linkedin"),
        ("Please provide your email address", "email"),
        # Still works without one.
        ("Veteran status", "veteran_status"),
        ("Email address", "email"),
    ],
)
def test_a_request_in_front_of_a_field_name_is_not_part_of_it(label, key):
    match = best_fact(ask(label))
    assert match is not None, f"{label!r} matched nothing"
    assert match.spec.key == key


def test_a_label_that_is_only_a_request_still_answers_to_nothing():
    """"Please Check the box below" names no fact, and must not invent one."""
    assert best_fact(ask("Please Check the box below")) is None


def test_the_label_as_written_is_always_tried_first():
    """Stripping is a fallback, so a field really called "Select" is unharmed."""
    match = best_fact(ask("Preferred name"))
    assert match is not None and match.spec.key == "preferred_name"


# ---------------------------------------------------------------------------
# 83. Read off the live page: labels that are not names.
# ---------------------------------------------------------------------------

#: The label a real application puts on its veteran radios. Not a field name --
#: three hundred characters of VEVRAA statute -- while the control's own name
#: says "veteran" plainly. The whole section went unasked because of it.
VEVRAA = (
    "* If you believe you belong to any of the categories of protected veterans "
    "listed above, please indicate by checking the appropriate box below. As a "
    "Government contractor subject to VEVRAA, we request this information in order "
    "to measure the effectiveness of the outreach and positive recruitment efforts "
    "we undertake pursuant to VEVRAA."
)


def named(label: str, attr: str) -> FieldObservation:
    return FieldObservation(
        fingerprint="f", label=label, display_label=label, attr_label=attr,
        control=ControlKind.RADIO, visible=True,
        options=[Option(label="Yes"), Option(label="No")],
    )


def test_a_paragraph_is_not_the_name_of_a_field():
    match = best_fact(named(VEVRAA, "veteran"))
    assert match is not None, "the veteran question went unasked because of this"
    assert match.spec.key == "veteran_status"


def test_a_long_question_that_names_its_subject_is_still_read_as_one():
    """The bar sits above a sentence: this must not go near the attribute."""
    label = (
        "Are you legally authorized to work in the United States without "
        "sponsorship now or in the future?"
    )
    match = best_fact(named(label, "custom_field_7"))
    assert match is not None and match.spec.key == "work_authorization"


def test_prose_whose_name_means_nothing_still_matches_nothing():
    label = (
        "A very long paragraph of legal text about many unrelated things that goes "
        "on and on for a great many words indeed without ever naming any field at "
        "all whatsoever in any way at any point"
    )
    assert best_fact(named(label, "custom_field_7")) is None


def test_a_hugging_face_profile_has_somewhere_to_go():
    """Its own fact, distinct from GitHub and from a personal site."""
    for label, key in [
        ("Hugging Face profile", "huggingface"),
        ("HuggingFace URL", "huggingface"),
        ("GitHub profile", "github"),
        ("Portfolio", "website"),
    ]:
        match = best_fact(ask(label))
        assert match is not None, label
        assert match.spec.key == key, (label, match.spec.key)

"""Two gaps the corpus found that no single page would have made obvious.

119: the asterisk family is wider than the one on a keyboard.
120: "Company" is ambiguous, "Current company" is not.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import best_fact
from applypilot.models import ControlKind, FieldObservation, Profile
from applypilot.text import normalise


def named(label: str, **extra) -> FieldObservation:
    return FieldObservation(
        fingerprint="f", label=label, display_label=label,
        control=ControlKind.TEXT, visible=True, **extra,
    )


# ---------------------------------------------------------------------------
# 119. Two of the largest boards mark required with a character we kept.
# ---------------------------------------------------------------------------

MARKS = ["✱", "*", "†", "‡", "•", "✲", "✳", "⁎", "∗", "＊", "★"]


@pytest.mark.parametrize("mark", MARKS)
def test_a_required_mark_is_not_part_of_the_name(mark):
    assert normalise(f"Current location {mark}") == "current location"


def test_the_heavy_asterisk_was_the_one_that_got_through():
    """U+2731, which Lever and Ashby both use.

    It reads as a star and behaves as a letter, so 39 labels across the corpus
    carried one into matching: "Current location ✱" never met "current
    location".
    """
    assert normalise("Current location ✱") == "current location"
    match = best_fact(named("Current location ✱"))
    assert match is not None and match.spec.key == "city"


def test_a_word_is_not_mistaken_for_a_mark():
    assert normalise("Star Sign") == "star sign"


# ---------------------------------------------------------------------------
# 120. Only one job can be the current one.
# ---------------------------------------------------------------------------

COMPANY = [
    "Current company", "Current Employer", "Most Recent Employer",
    "Current/Most Recent Company Name",
]
TITLE = [
    "Current Job Title", "Current Title", "Most Recent Job Title",
    "Current/Most Recent Job Title",
]


@pytest.mark.parametrize("label", COMPANY)
def test_the_current_employer_is_read_without_a_block_around_it(label):
    match = best_fact(named(label))
    assert match is not None, f"nothing matched {label!r}"
    assert match.spec.key == "experience.company"


@pytest.mark.parametrize("label", TITLE)
def test_the_current_job_title_is_read_without_a_block_around_it(label):
    match = best_fact(named(label))
    assert match is not None, f"nothing matched {label!r}"
    assert match.spec.key == "experience.title"


@pytest.mark.parametrize("label", ["Company", "Title", "Position"])
def test_the_bare_word_still_needs_its_block(label):
    """A page can ask for either of these for reasons of its own.

    Which is why they were left out to begin with; saying "current" is what
    removes the doubt.
    """
    match = best_fact(named(label))
    assert match is None or not match.spec.key.startswith("experience."), (
        f"{label!r} was claimed by {match.spec.key if match else None}"
    )


def test_a_profile_with_a_current_job_answers_it():
    profile = Profile(
        facts={},
        experience=[
            {
                "company": "Example Labs",
                "title": "Machine Learning Engineer",
                "current": True,
            }
        ],
    )
    from applypilot.mapper import resolve_field

    assert resolve_field(named("Current Employer"), profile).answer.value == "Example Labs"

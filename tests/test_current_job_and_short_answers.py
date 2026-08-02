"""Two things a real run got wrong once everything else worked.

128: "Current/Last Employer" came back with the job before the current one.
129: a veteran answer spelled out in full was refused by a Yes/No control.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import resolve_field
from applypilot.matching import best_option
from applypilot.models import ControlKind, FieldObservation, Option, Profile

TWO_JOBS = Profile(
    experience=[
        # Written down first, and finished. The order things are stored in is
        # not an answer to which one is current.
        {
            "company": "Innomatics Research Labs",
            "title": "Data Science Trainee",
            "start_date": "2023-01",
            "end_date": "2023-12",
            "current": False,
        },
        {
            "company": "HCLTech",
            "title": "AI Engineer",
            "start_date": "2024-02",
            "end_date": "",
            "current": True,
        },
    ]
)


def box(label: str, **extra) -> FieldObservation:
    return FieldObservation(
        fingerprint="x", label=label, display_label=label,
        control=ControlKind.TEXT, visible=True, **extra,
    )


# ---------------------------------------------------------------------------
# 128. One employer wanted means the current one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Current/Last Employer", "HCLTech"),
        ("Current Employer", "HCLTech"),
        ("Most Recent Employer", "HCLTech"),
    ],
)
def test_a_lone_employer_box_gets_the_job_you_are_in_now(label, expected):
    answer = resolve_field(box(label), TWO_JOBS).answer
    assert answer is not None, f"nothing answered {label!r}"
    assert answer.value == expected


def test_the_title_follows_the_same_job():
    answer = resolve_field(box("Current Job Title"), TWO_JOBS).answer
    assert answer is not None and answer.value == "AI Engineer"


@pytest.mark.parametrize("index,expected", [(0, "HCLTech"), (1, "Innomatics Research Labs")])
def test_a_block_is_filled_newest_first(index, expected):
    """Changed deliberately in 1.67.0.

    This asserted the order the records happen to be stored in, which is the
    order they were typed in. A form with room for a single education entry was
    then given the school attended before the most recent one. Every form that
    offers several of these lists them newest first, and a form that offers one
    is asking for the newest.
    """
    field = box("Company", group="exp", group_index=index, section="Work Experience")
    answer = resolve_field(field, TWO_JOBS).answer
    assert answer is not None and answer.value == expected


def test_a_form_with_one_slot_gets_the_most_recent_school():
    """The report this came from: it filled the education before last."""
    profile = Profile(
        education=[
            {"school": "Aalborg Universitet", "degree": "Bachelor's Degree",
             "start_date": "2019-08", "end_date": "2022-05"},
            {"school": "University of North Texas", "degree": "Master's Degree",
             "start_date": "2023-08", "end_date": "2025-05"},
        ]
    )
    only_slot = box("School", group="edu", group_index=0, section="Education")
    answer = resolve_field(only_slot, profile).answer
    assert answer is not None and answer.value == "University of North Texas"


def test_the_latest_wins_when_nothing_is_marked_current():
    profile = Profile(
        experience=[
            {"company": "Older", "start_date": "2020-01", "end_date": "2021-01"},
            {"company": "Newer", "start_date": "2022-01", "end_date": "2023-06"},
        ]
    )
    answer = resolve_field(box("Current Employer"), profile).answer
    assert answer is not None and answer.value == "Newer"


# ---------------------------------------------------------------------------
# 129. The same question, asked shorter.
# ---------------------------------------------------------------------------

YES_NO = [Option(label=x, value=x) for x in ["— Make a Selection —", "Yes", "No", "TBD"]]


@pytest.mark.parametrize(
    "saved,expected",
    [
        ("No, I am not a veteran under one of the classifications listed above", "No"),
        ("Yes, I am a protected veteran", "Yes"),
        ("No", "No"),
        ("Yes", "Yes"),
    ],
)
def test_an_answer_that_opens_by_saying_which_it_is_can_answer_yes_or_no(saved, expected):
    match = best_option(saved, YES_NO)
    assert match is not None, f"{saved!r} matched nothing"
    assert match.option.label == expected


@pytest.mark.parametrize(
    "saved",
    [
        # And a word that merely starts with those letters is not the word.
        "Notarised documents were provided",
        "Yesterday",
    ],
)
def test_a_sentence_that_does_not_open_with_one_is_left_alone(saved):
    assert best_option(saved, YES_NO) is None


def test_the_full_wording_still_wins_where_it_is_offered():
    """A control that really does offer the statute gets the statute."""
    full = "No, I am not a veteran under one of the classifications listed above"
    options = [Option(label=x, value=x) for x in ["Yes, I am a protected veteran", full]]
    match = best_option(full, options)
    assert match is not None and match.option.label == full


def test_a_sentence_that_says_no_without_the_word_is_read_as_no():
    """Changed deliberately in 1.65.0.

    When this file was written the only rule was "opens with yes or no", and
    this sentence opens with neither, so it was asserted to match nothing.
    Equal-opportunity questions are answered in whole sentences and no two
    forms use the same ones -- one offers "No, I am not a veteran under one of
    the classifications listed above", the next offers "I am not a protected
    veteran". They are the same answer, and it is now read as one.
    """
    match = best_option("I am not a protected veteran", YES_NO)
    assert match is not None
    assert match.option.label == "No"

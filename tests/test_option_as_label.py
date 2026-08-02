"""A choice's own word is not the question the group is asking.

Regression 118. Found by capturing 35 real forms and noticing that two of them
had every Yes/No question labelled "Yes" -- a label nobody can answer and the
panel cannot even show. The markup in the fixture is copied from the live page,
not invented.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser

QUESTIONS = [
    "Are you legally authorized to work in the country for which you are applying?",
    "Will you now or in the future require sponsorship for employment visa status?",
]


def radios(observation):
    return [f for f in observation["fields"] if f["control"] == "radio"]


def test_each_group_is_labelled_with_its_question(scan):
    _, observation = scan("option_as_label.html")
    found = radios(observation)
    assert len(found) == 2, [f["label"] for f in observation["fields"]]
    for field, expected in zip(found, QUESTIONS):
        label = (field.get("display_label") or field["label"]).strip()
        assert expected in label, f"got {label!r}"


def test_no_group_is_labelled_with_one_of_its_own_options(scan):
    """The failure exactly as it appeared.

    "Yes" contains no control, is perfectly visible and is short, so a search
    for the question inside the block found the answer first.
    """
    _, observation = scan("option_as_label.html")
    for field in radios(observation):
        label = (field.get("display_label") or field["label"]).strip()
        options = [o["label"].strip() for o in field.get("options") or []]
        assert label not in options, f"{label!r} is one of its own options"


def test_the_choices_are_still_read(scan):
    _, observation = scan("option_as_label.html")
    for field in radios(observation):
        assert [o["label"] for o in field["options"]] == ["Yes", "No"]


def test_the_questions_are_still_seen_as_required(scan):
    _, observation = scan("option_as_label.html")
    assert all(f["required"] for f in radios(observation))


def test_an_ordinary_labelled_box_is_untouched(scan):
    _, observation = scan("option_as_label.html")
    emails = [f for f in observation["fields"] if f["control"] == "email"]
    assert emails, [f["control"] for f in observation["fields"]]
    assert "Email" in (emails[0].get("display_label") or emails[0]["label"])

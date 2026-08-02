"""The same answer, given in the form's own words.

Regression 138. Equal-opportunity questions are asked in whole sentences and
answered in whole sentences, and no two forms use the same ones. One offers
"No, I am not a veteran under one of the classifications listed above"; the
next offers "I am not a protected veteran". They are the same answer, and
refusing to see that left required questions unanswerable on every form that
words them differently from the one the answer was saved on.

Every option pair here was taken from a live posting.
"""

from __future__ import annotations

import pytest

from applypilot.matching import _polarity, best_option
from applypilot.models import Option


def offer(*labels: str) -> list[Option]:
    return [Option(label=text, value=text) for text in labels]


VETERAN = offer(
    "I am not a protected veteran",
    "I identify as one or more of the classifications of a protected veteran",
)

DISABILITY = offer(
    "Yes, I have a disability (or previously had a disability)",
    "No, I don't have a disability",
    "I don't wish to answer",
)

SAVED_NOT_A_VETERAN = "No, I am not a veteran under one of the classifications listed above"
SAVED_NO_DISABILITY = "No, I do not have a disability and have not had one in the past"


def test_a_veteran_answer_finds_the_form_s_own_wording():
    match = best_option(SAVED_NOT_A_VETERAN, VETERAN)
    assert match is not None, "matched nothing"
    assert match.option.label == "I am not a protected veteran"


def test_a_disability_answer_finds_the_form_s_own_wording():
    match = best_option(SAVED_NO_DISABILITY, DISABILITY)
    assert match is not None, "matched nothing"
    assert match.option.label == "No, I don't have a disability"


def test_saying_yes_finds_the_affirmative_option():
    match = best_option("Yes, I am a protected veteran", VETERAN)
    assert match is not None
    assert match.option.label.startswith("I identify")


# ---------------------------------------------------------------------------
# What must never happen.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I don't wish to answer",
        "I do not wish to answer",
        "Prefer not to say",
        "Decline to self identify",
        "Choose not to disclose",
    ],
)
def test_declining_to_say_is_never_read_as_an_answer(text):
    """It contains "don't", and counting that as No answers for somebody.

    These questions are voluntary. Turning "I would rather not say" into "No"
    would put an answer on a form that the applicant deliberately withheld.
    """
    assert _polarity(text) == "decline"


def test_a_saved_no_never_selects_the_decline_row():
    match = best_option(SAVED_NO_DISABILITY, DISABILITY)
    assert match is not None
    assert "wish to answer" not in match.option.label


def test_two_options_meaning_the_same_thing_are_refused():
    """A tie is a question for the applicant, not a coin flip."""
    both_negative = offer("I am not a protected veteran", "No, I am not one")
    assert best_option(SAVED_NOT_A_VETERAN, both_negative) is None


@pytest.mark.parametrize("text", ["Asian", "United States", "Texas", "Bachelor's Degree"])
def test_an_ordinary_answer_has_no_polarity_at_all(text):
    assert _polarity(text) == ""


def test_a_plain_wording_match_still_wins():
    """Scored below a real match, so the exact sentence is still preferred."""
    exact = offer(SAVED_NOT_A_VETERAN, "I am not a protected veteran")
    match = best_option(SAVED_NOT_A_VETERAN, exact)
    assert match is not None and match.option.label == SAVED_NOT_A_VETERAN

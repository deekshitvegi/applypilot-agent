"""Regression 102: a form restating what it was given read as a failure.

A form is entitled to write an answer down its own way. One puts a dialling
code on a phone number it was handed without one; another lists its states as
"TX - Texas" and shows that once Texas is picked. In both cases the value went
in and was accepted, and in both the read-back said it had not -- four red
crosses on a page that was correctly filled.

What must not change is the meaning of verified. The page still has to hold the
answer that was asked for; only its way of writing it down is allowed to differ.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def same(page, asked: str, page_holds: str) -> bool:
    return page.evaluate("([a, b]) => ApplyPilot.verify.same(b, a)", [asked, page_holds])


@pytest.fixture
def verify(open_fixture):
    return open_fixture("tick_lists.html")


@pytest.mark.parametrize(
    ("asked", "page_holds", "why"),
    [
        ("9408436087", "+1 940 843 6087", "a dialling code the form added"),
        ("Texas", "TX - Texas", "a state code in front of the name"),
        ("United States", "US - United States", "a country code in front"),
        ("Yes", "Yes - I am a veteran", "an option spelled out"),
        ("Master's degree", "Masters degree", "punctuation"),
        ("76208", "76208", "unchanged"),
    ],
)
def test_the_page_writing_it_its_own_way_is_the_same_answer(verify, asked, page_holds, why):
    assert same(verify, asked, page_holds) is True, why


@pytest.mark.parametrize(
    ("asked", "page_holds", "why"),
    [
        ("Texas", "TN - Tennessee", "a different state"),
        ("Texas", "Texas A&M University", "not a whole part"),
        ("3", "3 - 5 years", "one end of a range is not the answer"),
        ("2024", "2024 - 2025", "nor is one end of a span of years"),
        ("9408436087", "9408436088", "one digit out"),
        ("9408436087", "8436087", "the form dropped digits"),
        ("940843", "1940843", "too short to be a whole number"),
        ("Yes", "No", "the opposite"),
        ("", "Texas", "nothing was asked for"),
        ("Texas", "", "the page holds nothing"),
    ],
)
def test_a_different_answer_is_still_different(verify, asked, page_holds, why):
    assert same(verify, asked, page_holds) is False, why

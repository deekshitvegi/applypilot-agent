"""A saved answer that names a place, and a form that writes places its own way.

Regression 144. "What is your nationality?" on a live application offers 199
countries, one of them "United States of America (USA)". The saved citizenship
is "US Citizen". Two separate things stood between them: the status word after
the place, and the code the form puts after the name.
"""

from __future__ import annotations

import pytest

from applypilot.matching import _place_within, best_option
from applypilot.models import Option

COUNTRIES = [
    Option(label=name, value=name)
    for name in [
        "Afghanistan",
        "Albania",
        "India (IND)",
        "United Kingdom of Great Britain and Northern Ireland (GBR)",
        "United States of America (USA)",
        "United States Minor Outlying Islands",
    ]
]


# ---------------------------------------------------------------------------
# A status word after a place is not part of the place.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "saved",
    ["US Citizen", "USA Citizen", "US citizenship", "US Permanent Resident"],
)
def test_a_citizenship_answer_finds_the_country_it_names(saved):
    match = best_option(saved, COUNTRIES, "citizenship")
    assert match is not None, f"{saved!r} matched nothing"
    assert match.option.label == "United States of America (USA)"


def test_the_status_word_is_only_stripped_for_a_fact_about_a_place():
    """Taking "resident" out of anything else changes what it says."""
    assert _place_within("US Citizen", "citizenship") == "US"
    assert _place_within("US Citizen", "experience.title") == ""
    assert _place_within("Resident Engineer", "experience.title") == ""


def test_a_plain_country_still_matches():
    match = best_option("United States", COUNTRIES, "country")
    assert match is not None
    assert match.option.label == "United States of America (USA)"


def test_a_neighbouring_country_is_not_taken_instead():
    """"United States Minor Outlying Islands" is somewhere else."""
    match = best_option("United States", COUNTRIES, "country")
    assert match is not None
    assert "Minor Outlying" not in match.option.label


# ---------------------------------------------------------------------------
# The code a form writes after a name says the same thing twice.
# ---------------------------------------------------------------------------


def test_a_bracketed_code_after_a_name_is_ignored():
    match = best_option("India", COUNTRIES, "country")
    assert match is not None and match.option.label == "India (IND)"


def test_a_name_that_is_only_a_bracket_is_not_matched_to_nothing():
    options = [Option(label="(none)", value=""), Option(label="Canada", value="Canada")]
    match = best_option("Canada", options, "country")
    assert match is not None and match.option.label == "Canada"


def test_a_long_parenthetical_is_left_alone():
    """Only a short code is a code. A sentence in brackets is content."""
    options = [
        Option(label="Content (e.g. videos, ads, billboards etc)", value="a"),
        Option(label="Careers Website", value="b"),
    ]
    assert best_option("Careers Website", options, "referral_source").option.label == (
        "Careers Website"
    )

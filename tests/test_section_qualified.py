"""Regression 105: a label that cannot stand on its own.

A repeating block headed "Phones (1)" holds fields called "Type" and "Number".
Neither means anything alone -- "Number" matched no fact at all -- so a saved
phone number sat in the profile while the form asked for it in red.

The heading is the missing half. Together they are unmistakable.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import best_fact
from applypilot.models import ControlKind, FieldObservation


def field(label: str, section: str = "") -> FieldObservation:
    return FieldObservation(
        fingerprint="f", label=label, display_label=label, section=section,
        control=ControlKind.TEXT, visible=True,
    )


@pytest.mark.parametrize(
    ("section", "label", "key"),
    [
        ("Phones (1)", "Number", "phone"),
        ("Phones", "Number", "phone"),
        ("Emails (1)", "Email", "email"),
        ("Addresses (1)", "City", "city"),
        ("Addresses (1)", "Zip/Postal Code", "postal_code"),
    ],
)
def test_the_heading_finishes_the_label(section, label, key):
    match = best_fact(field(label, section))
    assert match is not None, f"{section} / {label}"
    assert match.spec.key == key


def test_the_count_in_the_heading_is_ignored():
    assert best_fact(field("Number", "Phones (1)")).spec.key == "phone"
    assert best_fact(field("Number", "Phones (2)")).spec.key == "phone"


def test_a_label_that_stands_on_its_own_is_untouched():
    """The heading is only reached when the label alone matched nothing."""
    assert best_fact(field("First name", "Personal Information")).spec.key == "first_name"
    assert best_fact(field("Country", "Addresses (1)")).spec.key == "country"


@pytest.mark.parametrize(
    ("section", "label"),
    [
        # A heading must not invent a meaning that is not there.
        ("Phones (1)", "Type"),
        ("Addresses (1)", "Type"),
        ("Education and Certifications", "Level"),
        ("Attachments (1)", "Description"),
    ],
)
def test_a_heading_does_not_invent_a_meaning(section, label):
    assert best_fact(field(label, section)) is None, f"{section} / {label}"


def test_a_sentence_is_not_finished_by_anything():
    """Only a label short enough to be missing half of itself.

    A sentence says what it is about; a heading in front of it would only add
    noise. (A sentence that matches a fact on its own still does -- that is the
    ordinary path and nothing here touches it.)
    """
    long_one = "Number of widgets assembled per shift in your most recent role"
    assert best_fact(field(long_one, "Phones (1)")) is None


def test_a_heading_that_repeats_the_label_adds_nothing():
    assert best_fact(field("Certifications", "Certifications (1)")) is None


@pytest.mark.parametrize(
    ("section", "label", "key"),
    [
        # A heading read off a page carries its furniture with it: the count of
        # entries, a required marker, the number of the block.
        ("Phones (1)* required. 2", "Number", "phone"),
        ("Addresses (1) 2", "City", "city"),
        ("Addresses (1) 2", "Zip/Postal Code", "postal_code"),
        ("Addresses (1) 2", "Address", "street_address"),
    ],
)
def test_the_heading_is_read_through_its_furniture(section, label, key):
    match = best_fact(field(label, section))
    assert match is not None, f"{section} / {label}"
    assert match.spec.key == key


def test_furniture_does_not_turn_a_heading_into_a_meaning():
    assert best_fact(field("Type", "Phones (1)* required. 2")) is None

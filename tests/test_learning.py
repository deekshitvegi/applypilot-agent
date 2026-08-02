"""Regression 9: what got written into the profile and then into later forms.

Every rejected example below was a real entry in a saved answer table, and each
one was later filled into a different employer's application.
"""

from __future__ import annotations

import pytest

from applypilot.learning import build, judge, page_label_set
from applypilot.models import ControlKind, FieldObservation, Option


def field(
    label: str,
    control: ControlKind = ControlKind.TEXT,
    options: list[str] | None = None,
) -> FieldObservation:
    return FieldObservation(
        fingerprint=f"fp:{label}",
        label=label,
        control=control,
        options=[Option(label=o, value=o) for o in (options or [])],
        options_source="native" if options else "none",
    )


def test_a_readable_answer_is_learned():
    decision = judge(field("What is your preferred start date?"), "Two weeks from an offer")
    assert decision.learn, decision.reason


def test_an_option_id_from_a_dropdown_is_not_learned():
    # "Country -> 28468" made it into the profile and then into later forms.
    control = field("Country", ControlKind.SELECT, options=["United States", "Canada"])
    decision = judge(control, "28468")
    assert not decision.learn
    assert "option id" in decision.reason


def test_a_placeholder_row_is_not_learned():
    control = field("Country", ControlKind.SELECT, options=["- Select -", "United States"])
    assert not judge(control, "- Select -").learn


@pytest.mark.parametrize(
    "label", ["Current Date", "Language", "Search", "Sort by", "Job Alerts", "Password"]
)
def test_page_furniture_is_not_a_question(label):
    control = ControlKind.PASSWORD if label == "Password" else ControlKind.TEXT
    assert not judge(field(label, control), "something").learn


def test_a_mis_scanned_label_is_not_learned_as_a_value():
    # The scan that produced "Email Address: -> Notification:" is the reason
    # a value that reads like a label is refused.
    labels = page_label_set([field("Email Address"), field("Notification")])
    decision = judge(field("Email Address"), "Notification:", page_labels=labels)
    assert not decision.learn


def test_another_fields_label_is_not_learned_as_a_value():
    labels = page_label_set([field("Email Address"), field("Notification")])
    assert not judge(field("Email Address"), "Notification", page_labels=labels).learn


def test_a_phone_number_is_learned_even_though_it_is_all_digits():
    assert judge(field("Phone Number", ControlKind.TEL), "5125550147").learn


def test_a_postal_code_is_learned_even_though_it_is_all_digits():
    assert judge(field("ZIP Code"), "78701").learn


def test_a_bare_number_in_a_plain_text_box_is_refused():
    assert not judge(field("How did you hear about us?"), "40155").learn


def test_an_opaque_identifier_is_refused():
    assert not judge(field("Which office?"), "a3f91c7d4e5b6a01").learn


def test_a_value_the_control_does_not_offer_is_refused():
    control = field("State", ControlKind.SELECT, options=["Texas", "Utah"])
    assert not judge(control, "Tejas").learn


def test_voluntary_questions_are_not_remembered_by_default():
    control = field("Gender", ControlKind.SELECT, options=["Male", "Female"])
    assert not judge(control, "Male").learn
    assert judge(control, "Male", allow_demographics=True).learn


def test_a_field_with_no_visible_label_is_not_learned():
    unlabelled = FieldObservation(fingerprint="x", label="", attr_label="q_12345")
    assert not judge(unlabelled, "Yes").learn


def test_the_learned_record_keys_on_the_normalised_question():
    answer = build(field("What is your preferred start date?"), " Two weeks ")
    assert answer.normalised == "what is your preferred start date"
    assert answer.value == "Two weeks"

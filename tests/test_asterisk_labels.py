"""Regression 36: a form where every field came back labelled "*".

Its required marker sits in its own element between the field name and the
control, so the nearest thing before each input was a lone asterisk. Nothing
matched any saved answer, and the panel reported there was nothing it could fill
on a form asking for a first name, an email and an address.
"""

from __future__ import annotations

import pytest

from applypilot.models import PageObservation, Profile
from applypilot.runloop import plan_page

pytestmark = pytest.mark.browser


@pytest.fixture
def profile() -> Profile:
    return Profile(
        facts={
            "first_name": "Alex",
            "last_name": "Rivera",
            "email": "alex@example.test",
            "phone": "5125550147",
            "country": "United States",
            "state": "Texas",
            "city": "Austin",
            "street_address": "1200 Example Parkway",
            "address_line_2": "Apt 14",
            "postal_code": "78701",
        }
    )


def labels_of(observation) -> list[str]:
    return [f["label"] for f in observation["fields"]]


def test_a_required_marker_is_not_read_as_the_field_name(scan):
    _, observation = scan("asterisk_labels_form.html")
    found = labels_of(observation)
    assert "*" not in found, f"an asterisk was taken as a label: {found}"
    for expected in ("First name", "Last name", "Email address", "Phone number", "Country"):
        assert expected in found, f"{expected} was not read; saw {found}"


def test_the_form_that_filled_nothing_now_fills_everything_it_knows(scan, profile):
    _, raw = scan("asterisk_labels_form.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)

    filled = {}
    for action in plan.actions:
        label = next(f.display_label for f in observation.fields if f.fingerprint == action.fingerprint)
        filled[label] = action.value

    assert filled["First name"] == "Alex"
    assert filled["Last name"] == "Rivera"
    assert filled["Email address"] == "alex@example.test"
    assert filled["Phone number"] == "5125550147"
    assert filled["City"] == "Austin"
    assert filled["Address 1"] == "1200 Example Parkway"
    assert filled["Address 2"] == "Apt 14"
    assert filled["Zipcode"] == "78701"
    assert filled["Country"] == "United States", "not the Minor Outlying Islands"


def test_a_dependent_dropdown_is_not_offered_as_a_question_with_no_answers(scan, profile):
    """State holds nothing but "Choose" until a country is picked."""
    _, raw = scan("asterisk_labels_form.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)

    state_question = next((q for q in plan.questions if q.label == "State"), None)
    assert state_question is not None
    assert state_question.options == [], "a placeholder row is never offered as an answer"
    assert state_question.options_pending is True


def test_state_becomes_answerable_once_country_is_chosen(open_fixture, profile):
    page = open_fixture("asterisk_labels_form.html")

    raw = page.evaluate("() => ApplyPilot.scan.run()")
    country = next(f for f in raw["fields"] if f["label"] == "Country")
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": country["fingerprint"], "option_label": "United States"},
    )
    assert result["outcome"] == "verified"

    after = PageObservation.model_validate(page.evaluate("() => ApplyPilot.scan.run()"))
    plan = plan_page(after, profile)
    filled = {
        next(f.display_label for f in after.fields if f.fingerprint == a.fingerprint): a.value
        for a in plan.actions
    }
    assert filled["State"] == "Texas", "the dependent dropdown fills on the next pass"


def test_the_cv_upload_is_asked_for_rather_than_guessed(scan, profile):
    _, raw = scan("asterisk_labels_form.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)
    assert any(q.label == "CV" for q in plan.questions)


def test_the_page_offers_a_next_control_for_auto_continue(scan):
    _, observation = scan("asterisk_labels_form.html")
    assert [c["text"] for c in observation["next_controls"]] == ["Next"]


# ---------------------------------------------------------------------------
# 38. A slashed label names the field twice, and neither reading matched.
# ---------------------------------------------------------------------------


def test_a_spaced_slash_label_resolves_from_either_side():
    from applypilot.mapper import match_facts
    from applypilot.models import ControlKind, FieldObservation

    field = FieldObservation(
        fingerprint="x",
        label="*School / education institution",
        control=ControlKind.COMBOBOX,
        section="Education",
    )
    assert [m.spec.key for m in match_facts(field)][:1] == ["education.school"]


def test_labels_are_shown_without_their_required_markers():
    from applypilot.text import pretty_label

    assert pretty_label("*GPA") == "GPA"
    assert pretty_label("*Company ") == "Company"
    assert pretty_label("Country/Region of Residence:* *") == "Country/Region of Residence"


def test_a_repeated_field_says_which_entry_it_belongs_to():
    from applypilot.mapper import _entry_context
    from applypilot.models import ControlKind, FieldObservation

    second = FieldObservation(
        fingerprint="x", label="*GPA", control=ControlKind.TEXT,
        section="Education", group="g1", group_index=1,
    )
    assert _entry_context(second) == "Education 2"


def test_a_year_field_gets_the_year_not_the_whole_date():
    from applypilot.mapper import resolve_field
    from applypilot.models import ControlKind, EducationRecord, FieldObservation, Profile

    profile = Profile(education=[EducationRecord(school="Somewhere", end_date="Jul 2025")])
    field = FieldObservation(
        fingerprint="x", label="Graduation Year", control=ControlKind.TEXT, section="Education"
    )
    resolution = resolve_field(field, profile)
    assert resolution.answer is not None
    assert resolution.answer.value == "2025"

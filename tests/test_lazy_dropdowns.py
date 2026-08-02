"""Regressions 30 and 31, found on a real application.

30. A required dropdown whose options load only when it is touched was handed
    back as a text box, asking the applicant to type a dropdown answer.
31. The form asked for the current date, and so did the panel.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import resolve_field, resolve_page
from applypilot.matching import best_option
from applypilot.models import ControlKind, FieldObservation, Option, PageObservation, Profile
from applypilot.runloop import plan_page

pytestmark = pytest.mark.browser


@pytest.fixture
def profile() -> Profile:
    return Profile(
        facts={
            "full_name": "Alex Rivera",
            "email": "alex@example.test",
            "country": "United States",
            "work_authorization": "Yes",
            "requires_sponsorship": "No",
            "salary_expectation": "150000 USD",
        }
    )


def field_by_label(observation, text):
    for field in observation["fields"]:
        if text.lower() in (field["label"] or "").lower():
            return field
    raise AssertionError(f"no field like {text!r}; saw {[f['label'] for f in observation['fields']]}")


# ---------------------------------------------------------------------------
# 30. Options get opened and read before anyone is asked.
# ---------------------------------------------------------------------------


def test_a_dropdown_that_loads_late_looks_empty_when_scanned(scan):
    """The starting condition: this is what made it look like a text field."""
    _, observation = scan("lazy_dropdowns_application.html")
    hear = field_by_label(observation, "How did you hear")
    assert hear["control"] == "select"
    assert [o["label"] for o in hear["options"]] == ["No Selection"]


def test_such_a_question_is_flagged_as_needing_its_options_opened(scan, profile):
    _, raw = scan("lazy_dropdowns_application.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)

    hear = next(q for q in plan.questions if "how did you hear" in q.label.lower())
    assert hear.options_pending is True, "a choice with no choices must not be asked as text"
    assert hear.fingerprint in plan.needs_options


def test_opening_the_control_reads_the_options_it_really_offers(open_fixture):
    page = open_fixture("lazy_dropdowns_application.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    hear = field_by_label(observation, "How did you hear")

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp)", hear["fingerprint"]
    )
    assert opened["opened"] is True
    labels = [o["label"] for o in opened["options"]]
    assert "LinkedIn" in labels and "Referral" in labels


def test_a_saved_answer_matching_an_opened_option_is_chosen_not_asked(open_fixture, profile):
    """Once the options are known, a question the profile covers stops being one."""
    page = open_fixture("lazy_dropdowns_application.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country/Region of Residence")

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp)", country["fingerprint"]
    )
    chosen = best_option("United States", [Option(**o) for o in opened["options"]], "country")
    assert chosen is not None
    assert chosen.option.label == "United States", "not the Minor Outlying Islands"

    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": country["fingerprint"], "option_label": "United States"},
    )
    assert result["outcome"] == "verified"
    assert result["signal"] == "native_select"
    assert page.evaluate("() => document.getElementById('country').value") == "United States"


def test_the_sponsorship_dropdown_is_answered_from_sponsorship_not_country(open_fixture, profile):
    page = open_fixture("lazy_dropdowns_application.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    sponsorship = field_by_label(observation, "require company sponsorship")

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp)", sponsorship["fingerprint"]
    )
    field = FieldObservation.model_validate(sponsorship)
    field.options = [Option(**o) for o in opened["options"]]
    resolution = resolve_field(field, profile)

    assert resolution.answer is not None
    assert resolution.fact_key == "requires_sponsorship"
    assert resolution.answer.value == "No"


# ---------------------------------------------------------------------------
# 31. Today's date is not a question for a person.
# ---------------------------------------------------------------------------


def test_the_current_date_is_filled_not_asked(scan, profile):
    from datetime import date

    _, raw = scan("lazy_dropdowns_application.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)

    assert not any("current date" in q.label.lower() for q in plan.questions)
    filled = {a.fingerprint: a.value for a in plan.actions}
    today = next(
        (f for f in observation.fields if f.display_label.lower() == "current date"), None
    )
    assert today is not None
    assert filled[today.fingerprint] == date.today().strftime("%m/%d/%Y"), (
        "written in the shape the control asks for"
    )


def test_a_date_of_birth_is_never_filled_with_today(scan, profile):
    _, raw = scan("lazy_dropdowns_application.html")
    observation = PageObservation.model_validate(raw)
    dob = next(f for f in observation.fields if f.display_label.lower() == "date of birth")
    assert resolve_field(dob, profile).answer is None


def test_a_native_date_input_gets_the_iso_form(profile):
    from datetime import date

    field = FieldObservation(
        fingerprint="d", label="Current Date", control=ControlKind.DATE, input_type="date"
    )
    resolution = resolve_field(field, profile)
    assert resolution.answer is not None
    assert resolution.answer.value == date.today().isoformat()


def test_full_name_is_filled_and_notification_is_left_alone(scan, profile):
    _, raw = scan("lazy_dropdowns_application.html")
    observation = PageObservation.model_validate(raw)
    resolutions = {r.field.display_label: r for r in resolve_page(observation.fields, profile)}

    assert resolutions["Full Name"].answer.value == "Alex Rivera"
    # "Notification:" is a scan artefact of this form, not a question about you.
    assert resolutions["Notification:"].answer is None


def test_conditional_follow_ups_are_left_for_the_applicant(scan, profile):
    _, raw = scan("lazy_dropdowns_application.html")
    observation = PageObservation.model_validate(raw)
    resolutions = {r.field.display_label: r for r in resolve_page(observation.fields, profile)}

    for label in ("If yes, what department and what country?", "If yes, please indicate Visa status"):
        assert resolutions[label].answer is None, label

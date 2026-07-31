"""The injected functions, driven in headless Chromium against real markup.

Every assertion here is about state the page owns. Not one of them trusts a
function's return value as evidence that something happened.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def field_by_label(observation, label):
    for field in observation["fields"]:
        if field["label"].strip().rstrip("*").strip() == label:
            return field
    labels = [f["label"] for f in observation["fields"]]
    raise AssertionError(f"no field labelled {label!r}; saw {labels}")


# ---------------------------------------------------------------------------
# 18. The reCAPTCHA badge asks nothing of anyone.
# ---------------------------------------------------------------------------


def test_the_invisible_recaptcha_badge_is_not_a_challenge(scan):
    _, observation = scan("recaptcha_badge.html")
    assert observation["captcha"] == "badge_only"
    assert observation["kind"] == "application"


def test_the_interactive_recaptcha_checkbox_is_a_challenge(scan):
    _, observation = scan("recaptcha_checkbox.html")
    assert observation["captcha"] == "challenge"


# ---------------------------------------------------------------------------
# 19, 20, 21. Sign-in, registration and application are told apart by controls.
# ---------------------------------------------------------------------------


def test_an_application_served_from_a_post_login_url_is_an_application(scan):
    _, observation = scan("postLogin_application.html")
    assert observation["kind"] == "application"
    assert len(observation["fields"]) >= 10


def test_a_two_step_sign_in_inside_a_shadow_root_is_detected(scan):
    _, observation = scan("two_step_login_shadow.html")
    assert observation["kind"] == "sign_in", observation["notes"]


def test_an_account_registration_page_is_not_a_sign_in(scan):
    _, observation = scan("account_registration.html")
    assert observation["kind"] == "registration", observation["notes"]


def test_the_state_field_named_country_region_is_read_as_state(scan):
    _, observation = scan("postLogin_application.html")
    state = field_by_label(observation, "State")
    assert state["name"] == "countryRegion"
    assert state["label"] == "State"


# ---------------------------------------------------------------------------
# 23, 24. A list of results has no questions and no way in.
# ---------------------------------------------------------------------------


def test_a_search_results_page_offers_no_fields(scan):
    _, observation = scan("board_search_page.html")
    assert observation["kind"] in {"search", "board"}, observation["notes"]
    assert observation["fields"] == []


def test_an_apply_control_on_a_search_page_is_ignored(scan):
    _, observation = scan("board_search_page.html")
    assert observation["apply_controls"] == []
    assert any("list, not a posting" in note for note in observation["notes"])


# ---------------------------------------------------------------------------
# An application does not need a <form> element.
# ---------------------------------------------------------------------------


def test_an_application_rendered_without_a_form_element_is_detected(scan):
    _, observation = scan("application_without_form.html")
    assert observation["kind"] == "application", observation["notes"]
    assert len(observation["fields"]) >= 20


def test_a_radio_groups_question_is_its_legend_not_one_of_its_buttons(scan):
    _, observation = scan("application_without_form.html")
    sponsorship = next(
        f for f in observation["fields"] if "sponsorship" in f["label"].lower()
    )
    assert sponsorship["control"] == "radio"
    assert [o["label"] for o in sponsorship["options"]] == ["Yes", "No"]


def test_education_and_employment_blocks_are_not_treated_as_repeats(scan):
    _, observation = scan("application_without_form.html")
    school = field_by_label(observation, "School")
    company = field_by_label(observation, "Company")
    assert school["group_index"] == 0
    assert company["group_index"] == 0
    assert school["section"] == "Education"
    assert company["section"] == "Work Experience"


# ---------------------------------------------------------------------------
# 10. A combobox's own text box is not evidence of anything.
# ---------------------------------------------------------------------------


def test_a_combobox_that_never_commits_is_not_reported_as_verified(open_fixture):
    page = open_fixture("combobox_silent.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")

    result = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})",
        country["fingerprint"],
    )

    assert result["outcome"] != "verified", result
    assert result["signal"] == "none"
    assert "unverified" in result["evidence"] or "not" in result["evidence"]


def test_the_text_the_executor_typed_is_present_but_never_counted(open_fixture):
    """The temptation has to exist for the test to mean anything."""
    page = open_fixture("combobox_silent.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")
    page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})",
        country["fingerprint"],
    )
    typed = page.evaluate("() => document.getElementById('country').value")
    assert typed == "United States", "the filter text should be sitting there"

    reading = page.evaluate(
        "() => ApplyPilot.verify.observe(document.getElementById('country'), 'combobox', null)"
    )
    assert reading["signal"] == "none"
    assert reading["value"] == ""


def test_a_committing_combobox_is_verified_from_the_pages_own_state(open_fixture):
    page = open_fixture("combobox_committing.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")

    result = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})",
        country["fingerprint"],
    )

    assert result["outcome"] == "verified", result
    assert result["signal"] in {"hidden_backing_input", "rendered_value", "aria_selected_option"}
    assert page.evaluate("() => document.getElementById('backing').value") == "US"


def test_choosing_the_same_value_twice_does_not_click_again(open_fixture):
    page = open_fixture("combobox_committing.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")
    action = (
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})"
    )
    page.evaluate(action, country["fingerprint"])
    again = page.evaluate(action, country["fingerprint"])
    assert again["outcome"] == "verified"
    assert "nothing was clicked" in again["evidence"]


# ---------------------------------------------------------------------------
# 11. Options come from the popup the control owns, or from nowhere.
# ---------------------------------------------------------------------------


def test_a_control_with_no_popup_of_its_own_reports_no_options(open_fixture):
    page = open_fixture("dropdown_without_popup.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    department = field_by_label(observation, "Department")

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp)", department["fingerprint"]
    )
    assert opened["options"] == []
    assert opened["opened"] is False
    assert "no list of its own" in opened["note"]


def test_scanning_never_invents_options_for_a_custom_control(scan):
    _, observation = scan("dropdown_without_popup.html")
    department = field_by_label(observation, "Department")
    assert department["options"] == []
    assert department["options_source"] == "none"


def test_options_of_an_owning_control_come_back_in_full(open_fixture):
    page = open_fixture("combobox_committing.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")
    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp)", country["fingerprint"]
    )
    assert opened["source"] == "owned_popup"
    assert [o["label"] for o in opened["options"]] == [
        "United States",
        "Canada",
        "United States Minor Outlying Islands",
    ]


# ---------------------------------------------------------------------------
# 13. A page that rebuilds itself has to be re-filled, idempotently.
# ---------------------------------------------------------------------------


def test_a_rebuild_clears_earlier_work_and_refilling_is_verified(open_fixture):
    page = open_fixture("rerender_on_select.html")

    def observe():
        return page.evaluate("() => ApplyPilot.scan.run()")

    city = field_by_label(observe(), "City")
    filled = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform({kind:'fill', fingerprint: fp, value:'Austin'})",
        city["fingerprint"],
    )
    assert filled["outcome"] == "verified"

    country = field_by_label(observe(), "Country")
    page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})",
        country["fingerprint"],
    )

    # The address block was thrown away, taking the city with it.
    assert page.evaluate("() => document.getElementById('city').value") == ""

    after = observe()
    city_again = field_by_label(after, "City")
    assert city_again["fingerprint"] == city["fingerprint"], "identity must survive a rebuild"

    refilled = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform({kind:'fill', fingerprint: fp, value:'Austin'})",
        city_again["fingerprint"],
    )
    assert refilled["outcome"] == "verified"
    assert page.evaluate("() => document.getElementById('city').value") == "Austin"


def test_filling_a_field_that_already_holds_the_value_is_a_no_op(open_fixture):
    page = open_fixture("rerender_on_select.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    city = field_by_label(observation, "City")
    action = (
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'fill', fingerprint: fp, value:'Austin'})"
    )
    page.evaluate(action, city["fingerprint"])
    again = page.evaluate(action, city["fingerprint"])
    assert again["outcome"] == "verified"
    assert "nothing was clicked" in again["evidence"]


def test_united_states_is_not_selected_as_minor_outlying_islands(open_fixture):
    page = open_fixture("rerender_on_select.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    country = field_by_label(observation, "Country")
    page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'United States'})",
        country["fingerprint"],
    )
    selected = page.evaluate(
        "() => document.getElementById('country').selectedOptions[0].textContent"
    )
    assert selected == "United States"


# ---------------------------------------------------------------------------
# Adding an entry is confirmed by the form growing.
# ---------------------------------------------------------------------------


def test_add_another_is_confirmed_by_the_form_actually_growing(open_fixture):
    page = open_fixture("repeating_history.html")
    before = page.evaluate("() => document.querySelectorAll('.entry').length")
    result = page.evaluate("async () => await ApplyPilot.act.addRepeat('Add another')")
    after = page.evaluate("() => document.querySelectorAll('.entry').length")

    assert result["outcome"] == "verified", result
    assert after == before + 1
    assert "grew from" in result["evidence"]


def test_a_second_entry_is_a_separate_set_of_fields(open_fixture):
    page = open_fixture("repeating_history.html")
    first = page.evaluate("() => ApplyPilot.scan.run()")
    first_company = field_by_label(first, "Company")

    page.evaluate("async () => await ApplyPilot.act.addRepeat('Add another')")
    second = page.evaluate("() => ApplyPilot.scan.run()")
    companies = [f for f in second["fields"] if f["label"].strip() == "Company"]

    assert len(companies) == 2
    assert {c["group_index"] for c in companies} == {0, 1}
    assert len({c["fingerprint"] for c in companies}) == 2
    assert first_company["fingerprint"] in {c["fingerprint"] for c in companies}, (
        "the entry that was already there keeps its identity"
    )


# ---------------------------------------------------------------------------
# A drawn control is verifiable only when the page records something.
# ---------------------------------------------------------------------------


def test_a_segmented_control_with_a_backing_input_verifies(open_fixture):
    page = open_fixture("segmented_controls.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    question = field_by_label(observation, "Are you 18 years of age or older?")

    result = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'Yes'})",
        question["fingerprint"],
    )
    assert result["outcome"] == "verified", result
    assert result["signal"] in {"hidden_backing_input", "aria_selected_option"}
    assert page.evaluate("() => document.getElementById('backed-value').value") == "Y"


def test_a_segmented_control_that_records_nothing_is_never_verified(open_fixture):
    page = open_fixture("segmented_controls.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    question = field_by_label(observation, "Are you willing to relocate?")

    result = page.evaluate(
        "async (fp) => await ApplyPilot.act.perform("
        "{kind:'choose', fingerprint: fp, option_label:'Yes'})",
        question["fingerprint"],
    )
    assert result["outcome"] == "attempted", result
    assert result["signal"] == "none"
    assert "unverified" in result["evidence"]


# ---------------------------------------------------------------------------
# The service and the page must normalise labels identically.
# ---------------------------------------------------------------------------


LABELS = [
    "Country/Region of Residence",
    "First Name *",
    "Address Line 2",
    "If yes, what department and what country?",
    "Are you 18 years of age or older?",
    "  Email   Address  (required) ",
    "R&D Experience",
    "Legal Name:",
    "What is your desired salary?",
    "No Selection",
]


def test_label_normalisation_matches_the_service(open_fixture):
    from applypilot.text import normalise

    page = open_fixture("recaptcha_badge.html")
    from_page = page.evaluate("(labels) => labels.map(ApplyPilot.dom.normalise)", LABELS)
    assert from_page == [normalise(label) for label in LABELS]

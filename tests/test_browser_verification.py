"""Browser-level regression tests for the verified control layer.

These tests run the extension's real injected functions (``runFormPass`` and
``applyFileToInput`` from ``extension/service-worker.js`` and
``parseScopedFieldIntents`` from ``extension/sidepanel.js``) inside a real
Chromium page against fixture forms that reproduce live ATS behavior:
custom segmented Yes/No buttons, hidden backing state, toggling controls,
React-style re-renders, multi-select checkbox groups, shadow roots, and file
uploads that reset earlier answers.

Every assertion here checks page-owned DOM state, not an action return value.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = (ROOT / "extension" / "service-worker.js").read_text(encoding="utf-8")
SIDEPANEL_SOURCE = (ROOT / "extension" / "sidepanel.js").read_text(encoding="utf-8")
FIXTURES = ROOT / "tests" / "fixtures"

# The extension source references extension APIs at the top level; a small
# stub keeps the scripts loadable inside an ordinary test page.
CHROME_STUB = (
    "window.chrome = { runtime: { onInstalled: { addListener() {} },"
    " onMessage: { addListener() {} }, sendMessage() { return Promise.resolve({}); } },"
    " sidePanel: { setPanelBehavior() {} },"
    " storage: { session: { get() { return Promise.resolve({}); },"
    " set() { return Promise.resolve({}); } } } };"
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        launched = None
        last_error = None
        for kwargs in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
            try:
                launched = playwright.chromium.launch(headless=True, **kwargs)
                break
            except Exception as error:  # noqa: BLE001 - any launch failure means "try next channel"
                last_error = error
        if launched is None:
            pytest.skip(f"No Chromium-based browser is available: {last_error}")
        yield launched
        launched.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


def load_worker_fixture(page, fixture_name: str) -> None:
    page.goto((FIXTURES / fixture_name).resolve().as_uri())
    page.add_script_tag(content=CHROME_STUB + "\n" + WORKER_SOURCE)


def scan(page) -> dict:
    return page.evaluate("() => runFormPass(null)")


def fill(page, actions: list[dict]) -> dict:
    return page.evaluate("(actions) => runFormPass(actions)", actions)


def field_by_label(result: dict, text: str, field_type: str | None = None) -> dict:
    matches = [
        field
        for field in result["fields"]
        if text.lower() in f"{field['group_label']} {field['label']}".lower()
        and (field_type is None or field["field_type"] == field_type)
    ]
    assert matches, f"No scanned field matched {text!r}: {[f['label'] for f in result['fields']]}"
    return matches[0]


def action_for(field: dict, value: str) -> dict:
    return {
        "field_id": field["id"],
        "value": value,
        "source": "test",
        "confidence": 1,
        "expected_label": field["label"],
        "expected_type": field["field_type"],
        "fingerprint": field["fingerprint"],
    }


def test_segmented_backing_state_is_verified_from_page_owned_signals(page):
    load_worker_fixture(page, "segmented_backing.html")
    scanned = scan(page)
    sponsorship = field_by_label(scanned, "sponsorship", "radio")
    assert sponsorship["value"] == ""
    assert sponsorship["state_readable"] is False

    result = fill(page, [action_for(sponsorship, "No")])
    assert result["results"][0]["status"] == "verified"
    assert result["filled_ids"] == [sponsorship["id"]]
    no_state = page.evaluate(
        "() => [...document.querySelectorAll('button')]"
        ".find((b) => b.textContent.trim() === 'No').getAttribute('data-state')"
    )
    assert no_state == "on"

    # A fresh scan (not the executor's claim) must now report the value.
    rescan = scan(page)
    assert field_by_label(rescan, "sponsorship", "radio")["value"] == "No"


def test_segmented_backing_refill_is_idempotent_and_does_not_toggle_off(page):
    load_worker_fixture(page, "segmented_backing.html")
    scanned = scan(page)
    sponsorship = field_by_label(scanned, "sponsorship", "radio")
    first = fill(page, [action_for(sponsorship, "No")])
    assert first["results"][0]["status"] == "verified"

    rescan = scan(page)
    refreshed = field_by_label(rescan, "sponsorship", "radio")
    second = fill(page, [action_for(refreshed, "No")])
    assert second["results"][0]["status"] == "verified"
    clicks = page.evaluate("() => window.__clicks")
    assert clicks == {"yes": 0, "no": 1}
    no_state = page.evaluate(
        "() => [...document.querySelectorAll('button')]"
        ".find((b) => b.textContent.trim() === 'No').getAttribute('data-state')"
    )
    assert no_state == "on"


def test_silent_segmented_buttons_are_reported_unverified_not_verified(page):
    load_worker_fixture(page, "segmented_silent.html")
    scanned = scan(page)
    policy = field_by_label(scanned, "background check", "radio")

    result = fill(page, [action_for(policy, "Yes")])
    assert result["results"][0]["status"] == "unverified"
    assert result["filled"] == 0
    assert result["filled_ids"] == []


def test_toggle_buttons_are_never_clicked_twice(page):
    load_worker_fixture(page, "segmented_toggle.html")
    scanned = scan(page)
    authorization = field_by_label(scanned, "authorized to work", "radio")

    first = fill(page, [action_for(authorization, "Yes")])
    assert first["results"][0]["status"] == "verified"

    rescan = scan(page)
    refreshed = field_by_label(rescan, "authorized to work", "radio")
    assert refreshed["value"] == "Yes"
    second = fill(page, [action_for(refreshed, "Yes")])
    assert second["results"][0]["status"] == "verified"

    clicks = page.evaluate("() => window.__clicks")
    assert clicks["yes"] == 1, "a second click would have toggled the answer off"
    pressed = page.evaluate(
        "() => [...document.querySelectorAll('button')]"
        ".find((b) => b.textContent.trim() === 'Yes').getAttribute('aria-pressed')"
    )
    assert pressed == "true"


def test_rerender_is_recovered_by_fingerprint_and_verified(page):
    load_worker_fixture(page, "rerender.html")
    scanned = scan(page)
    relocation = field_by_label(scanned, "willing to relocate", "radio")

    result = fill(page, [action_for(relocation, "Yes")])
    assert result["results"][0]["status"] == "verified"
    selected = page.evaluate(
        "() => document.querySelector('#relocation-options button.selected')?.textContent.trim()"
    )
    assert selected == "Yes"
    rescan = scan(page)
    assert field_by_label(rescan, "willing to relocate", "radio")["value"] == "Yes"


def test_multiselect_checkbox_group_is_scoped_and_verified(page):
    load_worker_fixture(page, "multiselect.html")
    scanned = scan(page)
    github = next(
        field for field in scanned["fields"]
        if field["field_type"] == "checkbox" and field["option_label"] == "GitHub CI"
    )
    result = fill(page, [action_for(github, "true")])
    assert result["results"][0]["status"] == "verified"

    checked = page.evaluate(
        "() => [...document.querySelectorAll('input[name=tools]')]"
        ".filter((box) => box.checked).map((box) => box.value)"
    )
    assert checked == ["GitHub CI"], "only the requested option may change"


def test_relocation_anywhere_selects_all_locations_except_unable(page):
    load_worker_fixture(page, "multiselect.html")
    scanned = scan(page)
    locations = [
        field for field in scanned["fields"]
        if field["field_type"] == "checkbox" and "relocating" in field["group_label"].lower()
    ]
    assert len(locations) == 3
    actions = [
        action_for(field, "false" if "unable" in field["option_label"].lower() else "true")
        for field in locations
    ]
    result = fill(page, actions)
    assert [item["status"] for item in result["results"]] == ["verified"] * 3

    checked = page.evaluate(
        "() => [...document.querySelectorAll('input[name=locations]')]"
        ".filter((box) => box.checked).map((box) => box.value)"
    )
    assert checked == ["Chicago, IL", "New York, NY"]


def test_file_upload_reset_is_detected_by_rescan_and_restored(page):
    load_worker_fixture(page, "upload_reset.html")
    scanned = scan(page)
    sponsorship = field_by_label(scanned, "sponsorship", "radio")
    first = fill(page, [action_for(sponsorship, "No")])
    assert first["results"][0]["status"] == "verified"

    file_field = next(field for field in scan(page)["fields"] if field["field_type"] == "file")
    payload = base64.b64encode(b"synthetic resume bytes").decode("ascii")
    attached = page.evaluate(
        "([fieldId, data]) => applyFileToInput(fieldId, data, 'resume.pdf', 'application/pdf')",
        [file_field["id"], payload],
    )
    assert attached["attached"] is True

    # The reactive page reset the sponsorship answer; a fresh scan must see it.
    rescan = scan(page)
    reset_field = field_by_label(rescan, "sponsorship", "radio")
    assert reset_field["value"] == ""

    restored = fill(page, [action_for(reset_field, "No")])
    assert restored["results"][0]["status"] == "verified"
    checked = page.evaluate(
        "() => document.querySelector('input[name=sponsorship][value=No]').checked"
    )
    assert checked is True


def test_options_inside_open_shadow_root_are_scanned_and_verified(page):
    load_worker_fixture(page, "shadow_options.html")
    scanned = scan(page)
    visa = field_by_label(scanned, "visa sponsorship", "radio")
    assert {option["label"] for option in visa["options"]} == {"Yes", "No"}

    result = fill(page, [action_for(visa, "No")])
    assert result["results"][0]["status"] == "verified"
    checked = page.evaluate(
        "() => document.querySelector('#host').shadowRoot"
        ".querySelector('input[value=No]').checked"
    )
    assert checked is True


# --- Chat-routing intent parser -------------------------------------------


def load_sidepanel(page) -> None:
    page.goto("about:blank")
    page.add_script_tag(content=CHROME_STUB + "\n" + SIDEPANEL_SOURCE)


def parse_intents(page, message: str, fields: list[dict], focused: str = "") -> dict:
    return page.evaluate(
        "([message, fields, focused]) => parseScopedFieldIntents(message, fields, focused)",
        [message, fields, focused],
    )


def radio_field(field_id: str, label: str, options: list[str]) -> dict:
    return {
        "id": field_id,
        "label": label,
        "group_label": label,
        "option_label": "",
        "field_type": "radio",
        "value": "",
        "fingerprint": f"fp-{field_id}",
        "options": [{"value": option, "label": option} for option in options],
    }


def checkbox_field(field_id: str, group: str, option: str) -> dict:
    return {
        "id": field_id,
        "label": f"{group} {option}",
        "group_label": group,
        "option_label": option,
        "field_type": "checkbox",
        "value": "",
        "fingerprint": f"fp-{field_id}",
        "options": [],
    }


SPONSORSHIP = "Will you now or in the future require sponsorship?"
AUTHORIZATION = "Are you legally authorized to work in the United States?"
RELOCATION = "Which locations are you open to relocating to?"
TOOLS = "Which CI tools do you have hands-on experience with?"


def test_dont_require_sponsorship_becomes_scoped_no(page):
    load_sidepanel(page)
    fields = [radio_field("ap-0", SPONSORSHIP, ["Yes", "No"])]
    parsed = parse_intents(page, "i dont require sponsorship", fields)
    assert [(item["field"]["id"], item["value"]) for item in parsed["assignments"]] == [("ap-0", "No")]
    assert parsed["canonical"] == [{"key": "requires_sponsorship", "value": False}]


def test_relocate_anywhere_selects_every_location_and_clears_unable(page):
    load_sidepanel(page)
    fields = [
        checkbox_field("ap-1", RELOCATION, "Chicago, IL"),
        checkbox_field("ap-2", RELOCATION, "New York, NY"),
        checkbox_field("ap-3", RELOCATION, "Unable to relocate"),
    ]
    parsed = parse_intents(page, "I am open to relocating anywhere in the US", fields)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "false"}
    assert parsed["canonical"] == [{"key": "willing_to_relocate", "value": True}]


def test_add_named_option_targets_only_that_checkbox(page):
    load_sidepanel(page)
    fields = [
        checkbox_field("ap-1", TOOLS, "GitHub CI"),
        checkbox_field("ap-2", TOOLS, "CircleCI"),
        checkbox_field("ap-3", TOOLS, "Jenkins"),
    ]
    parsed = parse_intents(page, "add github ci", fields)
    assert [(item["field"]["id"], item["value"]) for item in parsed["assignments"]] == [("ap-1", "true")]


def test_combined_authorization_and_sponsorship_message_parses_both(page):
    load_sidepanel(page)
    fields = [
        radio_field("ap-0", AUTHORIZATION, ["Yes", "No"]),
        radio_field("ap-1", SPONSORSHIP, ["Yes", "No"]),
    ]
    parsed = parse_intents(page, "authorization yes and sponsorship no", fields)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-0": "Yes", "ap-1": "No"}


def test_bare_reply_with_two_matching_questions_is_ambiguous(page):
    load_sidepanel(page)
    fields = [
        radio_field("ap-0", AUTHORIZATION, ["Yes", "No"]),
        radio_field("ap-1", SPONSORSHIP, ["Yes", "No"]),
    ]
    parsed = parse_intents(page, "No", fields)
    assert parsed["assignments"] == []
    assert sorted(parsed["ambiguous"]) == sorted([AUTHORIZATION, SPONSORSHIP])


def test_bare_reply_binds_to_the_focused_question_only(page):
    load_sidepanel(page)
    fields = [
        radio_field("ap-0", AUTHORIZATION, ["Yes", "No"]),
        radio_field("ap-1", SPONSORSHIP, ["Yes", "No"]),
    ]
    parsed = parse_intents(page, "No", fields, SPONSORSHIP)
    assert [(item["field"]["id"], item["value"]) for item in parsed["assignments"]] == [("ap-1", "No")]
    assert parsed["ambiguous"] == []


SELECT_ALL_QUESTION = (
    "Please select all of the tools you have hands on experience with?"
    " This must be hands on experience only."
)


def tools_fields() -> list[dict]:
    return [
        checkbox_field("ap-1", SELECT_ALL_QUESTION, "GitHub CI"),
        checkbox_field("ap-2", SELECT_ALL_QUESTION, "Docker"),
        checkbox_field("ap-3", SELECT_ALL_QUESTION, "Terraform"),
        checkbox_field("ap-4", SELECT_ALL_QUESTION, "Jenkins"),
    ]


def test_pasted_question_text_cannot_trigger_select_all(page):
    # Live regression: the question itself contains "select all", and pasting
    # it after "add github ci" used to select every option in the group.
    load_sidepanel(page)
    message = f"add github ci {SELECT_ALL_QUESTION} in this"
    parsed = parse_intents(page, message, tools_fields())
    assert [(item["field"]["id"], item["value"]) for item in parsed["assignments"]] == [("ap-1", "true")]


def test_not_all_just_these_replaces_the_whole_selection(page):
    # Live regression: "not all just github ci and docker" must become an
    # exclusive scoped correction, not a model prose reply.
    load_sidepanel(page)
    parsed = parse_intents(
        page, "not all just github ci and docker", tools_fields(), SELECT_ALL_QUESTION,
    )
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "false", "ap-4": "false"}


def test_only_correction_without_focus_binds_to_single_matching_group(page):
    load_sidepanel(page)
    fields = tools_fields() + [radio_field("ap-9", SPONSORSHIP, ["Yes", "No"])]
    parsed = parse_intents(page, "only docker and jenkins", fields)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "false", "ap-2": "true", "ap-3": "false", "ap-4": "true"}


def test_select_all_still_works_when_the_user_actually_asks_for_it(page):
    load_sidepanel(page)
    parsed = parse_intents(page, "select all of them", tools_fields(), SELECT_ALL_QUESTION)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "true", "ap-4": "true"}


def test_check_all_phrasing_selects_the_focused_group(page):
    load_sidepanel(page)
    parsed = parse_intents(page, "check all", tools_fields(), SELECT_ALL_QUESTION)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "true", "ap-4": "true"}


def test_additive_just_add_does_not_clear_other_options(page):
    # "also just add Docker" is additive: it must select Docker and leave the
    # other checkboxes in the group untouched, never clear them.
    load_sidepanel(page)
    parsed = parse_intents(page, "also just add docker", tools_fields(), SELECT_ALL_QUESTION)
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-2": "true"}


def test_conversational_sentence_with_just_and_an_option_is_not_a_correction(page):
    # An ordinary sentence containing "just" and an option name must never
    # rewrite the group selection.
    load_sidepanel(page)
    parsed = parse_intents(
        page, "it was just a small project using docker", tools_fields(),
    )
    assert parsed["assignments"] == []


def test_remove_the_rest_with_typo_replaces_the_selection(page):
    # Live regression: "I said I oly know github ci and docker remove the
    # rest" produced model prose instead of clearing the other tools.
    load_sidepanel(page)
    parsed = parse_intents(
        page, "I said I oly know github ci and docker remove the rest", tools_fields(),
    )
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "false", "ap-4": "false"}


def test_i_only_know_phrasing_is_exclusive_for_the_focused_group(page):
    load_sidepanel(page)
    parsed = parse_intents(
        page, "I only know docker and github ci", tools_fields(), SELECT_ALL_QUESTION,
    )
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {"ap-1": "true", "ap-2": "true", "ap-3": "false", "ap-4": "false"}


RELOCATION_QUESTION = (
    "If you do not currently reside in the San Jose/San Francisco Bay Area,"
    " please select what city you would be interested in a Company assisted"
    " relocation package?"
)
BACKGROUND_QUESTION = (
    "If you have any questions regarding our screening process or data privacy,"
    " please review our Background Check Policy at this link."
)
GIANT_MESSAGE = (
    "fill my phone number and also check the I have reviewed the background"
    " check policy also I'm able to relocate anywhere in the united states "
    + SELECT_ALL_QUESTION
    + " in this I only know docker and github ci also click on submit once you"
    " made these changes"
)


def giant_page_fields() -> list[dict]:
    phone = {
        "id": "ap-20",
        "label": "Phone",
        "group_label": "",
        "option_label": "",
        "field_type": "tel",
        "value": "",
        "fingerprint": "fp-ap-20",
        "options": [],
    }
    background = radio_field(
        "ap-21", BACKGROUND_QUESTION, ["I have reviewed the Background Check Policy"],
    )
    relocation = [
        checkbox_field("ap-30", RELOCATION_QUESTION, "San Jose, CA/San Francisco Bay Area"),
        checkbox_field("ap-31", RELOCATION_QUESTION, "Kansas City MO/Overland Park KS Metro Area"),
        checkbox_field(
            "ap-32", RELOCATION_QUESTION,
            "I am unable to relocate, I can only work remotely from the city where I currently reside.",
        ),
    ]
    return [phone, background, *relocation, *tools_fields()]


def test_one_message_with_many_intents_is_split_into_scoped_actions(page):
    # Live regression: one long instruction must produce phone fill, the
    # background-policy confirmation, relocation everywhere-except-unable,
    # an exclusive tools selection, and a submit-policy note — never a
    # partial fan-out or generic prose.
    load_sidepanel(page)
    parsed = parse_intents(page, GIANT_MESSAGE, giant_page_fields())
    values = {item["field"]["id"]: item["value"] for item in parsed["assignments"]}
    assert values == {
        "ap-21": "I have reviewed the Background Check Policy",
        "ap-30": "true",
        "ap-31": "true",
        "ap-32": "false",
        "ap-1": "true",   # GitHub CI
        "ap-2": "true",   # Docker
        "ap-3": "false",  # Terraform
        "ap-4": "false",  # Jenkins
    }
    assert [item["field"]["id"] for item in parsed["profileRequests"]] == ["ap-20"]
    assert parsed["profileRequests"][0]["key"] == "phone"
    assert parsed["submitRequested"] is True
    assert parsed["canonical"] == [{"key": "willing_to_relocate", "value": True}]


# --- Custom combobox: filter text is never evidence -------------------------
#
# Live regression from a real Greenhouse (react-select) form. The executor
# types into the combobox's own input to filter the option list. A previous
# release then re-read that self-written text during the verification rescan
# and reported "verified" for an option the page never accepted.


def combobox_field(page) -> dict:
    return field_by_label(scan(page), "work authorization", "select")


def test_custom_combobox_reports_real_option_as_verified(page):
    load_worker_fixture(page, "combobox_filter_input.html")
    field = combobox_field(page)
    result = fill(page, [action_for(field, "Require sponsorship now")])

    assert result["results"][0]["status"] == "verified"
    assert result["filled_ids"] == [field["id"]]
    # Page-owned state, read independently of anything the executor returned.
    assert page.evaluate("() => window.__committedValue()") == "Require sponsorship now"


def test_custom_combobox_never_verifies_its_own_filter_text(page):
    load_worker_fixture(page, "combobox_filter_input.html")
    field = combobox_field(page)
    result = fill(page, [action_for(field, "Definitely Not An Option")])

    outcome = result["results"][0]
    assert outcome["status"] == "failed"
    assert result["filled_ids"] == []
    # The page committed nothing, and no typed text was left behind to be
    # mistaken for an answer by a later scan.
    assert page.evaluate("() => window.__committedValue()") == ""
    assert page.evaluate("() => document.querySelector('#q1').value") == ""


def test_custom_combobox_with_only_typed_text_is_not_state_readable(page):
    load_worker_fixture(page, "combobox_filter_input.html")
    # Simulate stray text sitting in the filter input with nothing committed.
    page.evaluate("() => { document.querySelector('#q1').value = 'Require sponsorship now'; }")
    field = combobox_field(page)

    assert field["state_readable"] is False
    assert field["value_evidence"] == "input-text"


def test_enumerate_mode_reads_options_the_planner_would_otherwise_never_see(page):
    load_worker_fixture(page, "combobox_filter_input.html")
    plain = field_by_label(scan(page), "work authorization", "select")
    assert plain["options"] == []

    enumerated = page.evaluate("() => runFormPass('enumerate')")
    field = field_by_label(enumerated, "work authorization", "select")
    assert [option["label"] for option in field["options"]] == [
        "Authorized to work in the US",
        "Require sponsorship now",
        "Require sponsorship later",
    ]
    # Enumeration must leave the widget closed and uncommitted.
    assert page.evaluate("() => window.__committedValue()") == ""


# --- Job boards are not application forms -----------------------------------


def test_board_search_page_is_not_reported_as_an_application_surface(page):
    load_worker_fixture(page, "board_search_page.html")
    assert page.evaluate("() => detectApplicationSurface()") == {"ready": False}


def test_job_extraction_never_returns_bundled_script_text(page):
    load_worker_fixture(page, "board_search_page.html")
    job = page.evaluate("() => extractJobFromPage()")
    assert "use strict" not in job["description"]
    assert "__ANALYTICS__" not in job["description"]


# --- CAPTCHA: only pause for a challenge the user can actually solve --------
#
# Live regression: a run stopped with "Paused: CAPTCHA, MFA, or a verification
# code requires you" on an ordinary employer form. The detector matched any
# visible captcha iframe, including the invisible reCAPTCHA badge that sits on
# a large share of career sites and requires no interaction at all.


def test_invisible_recaptcha_badge_does_not_block_the_application(page):
    load_worker_fixture(page, "recaptcha_badge.html")

    entry = page.evaluate("() => clickApplicationEntry(true)")
    assert "CAPTCHA" not in (entry.get("error") or "")

    login = page.evaluate("() => clickReadyLogin(false)")
    assert "CAPTCHA" not in (login.get("error") or "")
    # No password field either, so this is simply not a login page.
    assert login["login_page"] is False


def test_recaptcha_checkbox_challenge_still_stops_for_the_user(page):
    load_worker_fixture(page, "recaptcha_checkbox.html")

    login = page.evaluate("() => clickReadyLogin(true)")

    assert login["clicked"] is False
    assert login["login_page"] is True
    assert "CAPTCHA" in login["error"]


def test_one_time_code_field_still_stops_for_the_user(page):
    load_worker_fixture(page, "recaptcha_badge.html")
    page.evaluate(
        """() => {
             const otp = document.createElement('input');
             otp.setAttribute('autocomplete', 'one-time-code');
             otp.style.width = '200px';
             document.querySelector('#application').appendChild(otp);
           }"""
    )

    login = page.evaluate("() => clickReadyLogin(true)")

    assert login["login_page"] is True
    assert "CAPTCHA" in login["error"]


# --- Forms that rebuild themselves mid-fill --------------------------------
#
# Live regression from a multi-step employer form: choosing Country rebuilt the
# address block, discarding Address Line 1-3 and City that had just been
# filled. The rescan honestly reported them empty, and the run reported
# failures for fields it could simply have filled again.


def rerender_fields(page) -> tuple[dict, dict]:
    scanned = scan(page)
    return (
        field_by_label(scanned, "country", "select"),
        field_by_label(scanned, "address line 1", "text"),
    )


def test_a_select_that_rebuilds_the_form_wipes_fields_filled_before_it(page):
    load_worker_fixture(page, "rerender_on_select.html")
    country, address = rerender_fields(page)

    # Address first, then the country that rebuilds the block around it.
    result = fill(page, [action_for(address, "1 Test Street"), action_for(country, "United States")])

    statuses = {item["field_id"]: item["status"] for item in result["results"]}
    assert statuses[country["id"]] == "verified"
    assert statuses[address["id"]] == "failed"
    assert page.evaluate("() => window.__rebuilds") == 1
    assert page.evaluate("() => document.querySelector('#addr1').value") == ""


def test_refilling_after_the_rebuild_settles_the_form(page):
    load_worker_fixture(page, "rerender_on_select.html")
    country, address = rerender_fields(page)
    fill(page, [action_for(address, "1 Test Street"), action_for(country, "United States")])

    # What fillUntilSettled does: re-plan against the rebuilt DOM and fill again.
    country, address = rerender_fields(page)
    second = fill(page, [action_for(address, "1 Test Street"), action_for(country, "United States")])

    statuses = {item["field_id"]: item["status"] for item in second["results"]}
    assert statuses[address["id"]] == "verified"
    assert statuses[country["id"]] == "verified"
    # Page-owned state, read independently of the executor's claim.
    assert page.evaluate("() => document.querySelector('#addr1').value") == "1 Test Street"


def test_reselecting_the_same_option_does_not_rebuild_the_form_again(page):
    load_worker_fixture(page, "rerender_on_select.html")
    country, _ = rerender_fields(page)
    fill(page, [action_for(country, "United States")])
    assert page.evaluate("() => window.__rebuilds") == 1

    country, _ = rerender_fields(page)
    again = fill(page, [action_for(country, "United States")])

    assert again["results"][0]["status"] == "verified"
    # Idempotence: no second rebuild, so a retry pass cannot thrash forever.
    assert page.evaluate("() => window.__rebuilds") == 1


def test_two_step_sign_in_without_a_password_field_is_still_a_login_page(page):
    # Live regression: an ADP application link redirects to "Sign in |
    # WFNPortal", which asks for a User ID and only requests the password on
    # the next screen. With no password input to find, the page was not
    # recognised as a login, so the runner treated a sign-in form as an
    # application form and filled it.
    load_worker_fixture(page, "two_step_login.html")

    login = page.evaluate("() => clickReadyLogin(false)")

    assert login["login_page"] is True
    assert login["clicked"] is False


def test_an_ordinary_application_form_is_not_mistaken_for_a_login(page):
    load_worker_fixture(page, "recaptcha_badge.html")

    login = page.evaluate("() => clickReadyLogin(false)")

    assert login["login_page"] is False


def test_an_application_form_on_a_postlogin_url_is_not_treated_as_a_login(page):
    # Live regression introduced by the two-step login fix: the ADP
    # application page lives at ".../postLogin.html" and has an email field,
    # so login detection claimed it was a sign-in page. The runner then looped
    # "Submitted a password-manager-filled login step" / "Login fields were
    # not filled" forever on a form it should simply have filled.
    load_worker_fixture(page, "postLogin_application.html")
    assert "login" in page.url.lower()

    login = page.evaluate("() => clickReadyLogin(true)")

    assert login["login_page"] is False
    assert login["clicked"] is False


def test_a_sign_in_page_is_still_detected_next_to_that_guard(page):
    # The guard must not undo two-step login detection.
    load_worker_fixture(page, "two_step_login.html")

    login = page.evaluate("() => clickReadyLogin(false)")

    assert login["login_page"] is True


def test_a_longer_employer_option_still_counts_as_the_saved_answer(page):
    # Live regression: the page had selected "United States of America" and the
    # saved answer was "United States", so the run reported "I could not
    # complete: Country" for a value the page had actually accepted.
    load_worker_fixture(page, "rerender_on_select.html")
    page.evaluate(
        """() => {
             const select = document.querySelector('#country');
             select.options[1].textContent = 'United States of America';
             select.options[1].value = 'USA';
           }"""
    )
    country = field_by_label(scan(page), "country", "select")

    result = fill(page, [action_for(country, "United States")])

    assert result["results"][0]["status"] == "verified"
    assert page.evaluate("() => document.querySelector('#country').value") == "USA"


def label_value_fields() -> list[dict]:
    return [
        {
            "id": "ap-1", "label": "State", "group_label": "State", "option_label": "",
            "name": "state", "field_type": "select", "required": True, "value": "",
            "options": [{"value": "TX", "label": "Texas"}, {"value": "CA", "label": "California"}],
            "fingerprint": "f1",
        },
        {
            "id": "ap-2", "label": "Phone Device Type", "group_label": "Phone Device Type",
            "option_label": "", "name": "pt", "field_type": "select", "required": True, "value": "",
            "options": [{"value": "M", "label": "Mobile"}, {"value": "H", "label": "Home"}],
            "fingerprint": "f2",
        },
        {
            "id": "ap-3", "label": "County", "group_label": "County", "option_label": "",
            "name": "county", "field_type": "text", "required": False, "value": "",
            "options": [], "fingerprint": "f3",
        },
    ]


def test_naming_a_field_and_its_value_fills_that_field(page):
    # Live regression: "state texas" and "set my state to Texas" produced
    # conversational prose ("your state is set to Texas") while the required
    # dropdown stayed empty and blocked the application.
    load_sidepanel(page)
    fields = label_value_fields()

    for message, expected in [
        ("state texas", ("ap-1", "Texas")),
        ("set my state to Texas", ("ap-1", "Texas")),
        ("my state is Texas", ("ap-1", "Texas")),
        ("phone device type mobile", ("ap-2", "Mobile")),
        ("county Denton County", ("ap-3", "Denton County")),
    ]:
        parsed = parse_intents(page, message, fields)
        actual = [(item["field"]["id"], item["value"]) for item in parsed["assignments"]]
        assert actual == [expected], f"{message!r} produced {actual}"


def test_label_value_answers_only_choose_options_the_page_shows(page):
    load_sidepanel(page)
    parsed = parse_intents(page, "state Atlantis", label_value_fields())

    # Atlantis is not an option, so nothing is assigned and nothing invented.
    assert parsed["assignments"] == []


def test_a_bare_option_reply_still_binds_to_its_question(page):
    load_sidepanel(page)
    parsed = parse_intents(page, "california", label_value_fields())

    assert [(i["field"]["id"], i["value"]) for i in parsed["assignments"]] == [("ap-1", "California")]


def test_a_dropdown_never_reports_unrelated_page_items_as_its_options(page):
    # Live regression from an Ashby form: a Location dropdown that exposes no
    # listbox reported 27 "options" scraped from the whole document - a salary
    # chip, Yes/No buttons, relocation checkboxes and the EEO race list - and
    # the panel then offered every one of them as a single question.
    load_worker_fixture(page, "combobox_filter_input.html")
    page.evaluate(
        """() => {
             // Page furniture that the old document-wide fallback swept up.
             const noise = document.createElement('ul');
             noise.innerHTML = '<li>$175K - $250K</li><li>Male</li><li>Female</li>'
                             + '<li data-value="x">Hispanic or Latino</li>';
             document.querySelector('main').appendChild(noise);
             // Make the widget unidentifiable as a popup owner.
             document.querySelector('#q1-menu').removeAttribute('role');
           }"""
    )

    field = field_by_label(page.evaluate("() => runFormPass('enumerate')"), "work authorization", "select")

    assert field["options"] == []

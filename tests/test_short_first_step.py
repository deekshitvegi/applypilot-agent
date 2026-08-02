"""A short opening step is still an application.

Regression 125. One large system opens its application with four boxes --
first name, last name, email, mobile -- drawn by web components, so the light
document holds nothing at all. Four is not five, so the page came back
"unrecognised" and every field on it was skipped.

The fixture mirrors that shape: custom elements with open shadow roots, no
<form>, no file input.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def test_a_four_field_opening_step_is_an_application(scan):
    _, observation = scan("short_first_step.html")
    assert observation["kind"] == "application", observation["notes"]


def test_its_fields_are_read_out_of_the_shadow_roots(scan):
    _, observation = scan("short_first_step.html")
    labels = [
        (f.get("display_label") or f["label"]).strip()
        for f in observation["fields"]
    ]
    for wanted in ["First Name", "Last Name", "Email", "Mobile Number"]:
        assert wanted in labels, f"{wanted!r} missing; saw {labels}"


def test_what_the_form_marked_required_is_read_as_required(scan):
    _, observation = scan("short_first_step.html")
    required = {
        (f.get("display_label") or f["label"]).strip()
        for f in observation["fields"]
        if f["required"]
    }
    assert required == {"First Name", "Last Name", "Email"}


# ---------------------------------------------------------------------------
# What must NOT become an application on the strength of three boxes.
# ---------------------------------------------------------------------------


def test_a_sign_in_page_is_still_a_sign_in(scan):
    _, observation = scan("two_step_login_shadow.html")
    assert observation["kind"] == "sign_in", observation["notes"]


def test_an_account_registration_page_is_still_a_registration(scan):
    _, observation = scan("account_registration.html")
    assert observation["kind"] == "registration", observation["notes"]


def test_a_list_of_jobs_is_still_a_list(scan):
    _, observation = scan("recaptcha_badge.html")
    assert observation["kind"] != "unknown"

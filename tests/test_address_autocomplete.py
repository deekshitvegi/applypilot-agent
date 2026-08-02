"""Regression 103: an address line that throws the address away.

Several applicant tracking systems build the first address line as a list of
places rather than a text box. Typing into it and looking away discards the
text, because nothing was chosen from what it offered -- so the address, and the
city and postcode it fills in for itself, all came back empty on a page that had
just been filled.

Blurring is what discards it. Where a control says in its own attributes that it
offers suggestions, its suggestions are used before looking away.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser

ADDRESS = "1710 Northstar road"


def address_field(page):
    fields = page.evaluate("() => ApplyPilot.scan.run().fields")
    return next(f for f in fields if "Address Line 1" in (f["label"] or ""))


def fill(page, value):
    return page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "fill", "fingerprint": address_field(page)["fingerprint"], "value": value},
    )


def test_the_address_survives_looking_away(open_fixture):
    page = open_fixture("address_autocomplete.html")
    fill(page, ADDRESS)
    assert page.evaluate("() => document.getElementById('line1').value") == ADDRESS


def test_the_fields_it_fills_in_for_itself_arrive_with_it(open_fixture):
    """City and postcode are the list's doing, not ours."""
    page = open_fixture("address_autocomplete.html")
    fill(page, ADDRESS)
    assert page.evaluate("() => document.getElementById('city').value") == "Denton"
    assert page.evaluate("() => document.getElementById('zip').value") == "76208"


def test_it_is_not_reported_as_a_failure(open_fixture):
    """It used to fail and leave the box empty. Now it is filled."""
    result = fill(open_fixture("address_autocomplete.html"), ADDRESS)
    assert result["outcome"] != "failed", result


def test_a_suggestion_for_somewhere_else_is_not_taken(open_fixture):
    """A list offering a different street is not an answer to this question."""
    page = open_fixture("address_autocomplete.html")
    fill(page, "1710 Northstar avenue")
    # The list offers Northstar road and Northgate drive; neither is what was
    # asked for, so neither is chosen and the box is left as the page left it.
    assert page.evaluate("() => document.getElementById('city').value") == ""
    assert page.evaluate("() => document.getElementById('zip').value") == ""


def test_an_ordinary_text_box_is_untouched_by_any_of_this(open_fixture):
    """It says nothing about suggestions, so nothing waits for any."""
    page = open_fixture("address_autocomplete.html")
    fields = page.evaluate("() => ApplyPilot.scan.run().fields")
    city = next(f for f in fields if (f["label"] or "") == "City")
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "fill", "fingerprint": city["fingerprint"], "value": "Denton"},
    )
    assert result["outcome"] == "verified", result
    assert result["signal"] == "native_value"

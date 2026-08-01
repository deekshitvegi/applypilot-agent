"""Regressions 49 and 50, read off a live application rather than guessed at.

The school field is a hidden <select> with no options carrying the value, a span
with role="combobox" that the applicant sees, and a dropdown -- search box
inside it -- appended to <body> when opened.

Looking for a control's list inside that control found nothing, so the field
could never be filled; and the search box could not be typed into because it did
not exist until the list opened somewhere else entirely.

The field names are in bracket notation, where the meaningful part is last.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def school_of(page):
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    field = next(f for f in observation["fields"] if "School" in (f["label"] or ""))
    return field, observation


def test_the_visible_widget_is_scanned_and_the_hidden_select_is_not(scan):
    _, observation = scan("detached_dropdown_picker.html")
    kinds = {f["label"]: f["control"] for f in observation["fields"]}
    assert kinds["*School / education institution"] == "combobox"
    # The hidden select carrying the value is not a second question.
    assert sum(1 for f in observation["fields"] if "School" in f["label"]) == 1


def test_a_dropdown_hung_off_the_body_is_still_this_controls_own(open_fixture):
    page = open_fixture("detached_dropdown_picker.html")
    field, _ = school_of(page)

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp, 'University of North Texas')",
        field["fingerprint"],
    )
    labels = [o["label"] for o in opened["options"]]
    assert opened["source"] == "owned_popup"
    assert "University of North Texas" in labels, labels


def test_choosing_from_it_is_verified_from_the_hidden_select(open_fixture):
    page = open_fixture("detached_dropdown_picker.html")
    field, _ = school_of(page)

    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {
            "kind": "choose",
            "fingerprint": field["fingerprint"],
            "option_label": "University of North Texas",
        },
    )
    assert result["outcome"] == "verified", result
    assert (
        page.evaluate(
            "() => document.querySelector('select[name=\\'custom[education][0][school]\\']').value"
        )
        == "University of North Texas"
    )


def test_a_closed_control_never_claims_a_list_that_is_not_its_own(open_fixture):
    """Regression 11 still holds: no list of its own means no options."""
    page = open_fixture("detached_dropdown_picker.html")
    field, _ = school_of(page)

    # Force the body dropdown open without the control saying it is expanded.
    page.evaluate(
        """() => {
          document.getElementById('drop').hidden = false;
          const ul = document.getElementById('results');
          ul.innerHTML = '<li role="option">Something Else Entirely</li>';
          document.querySelector('.picker-selection').setAttribute('aria-expanded', 'false');
          document.querySelector('.picker-selection').removeAttribute('aria-owns');
        }"""
    )
    found = page.evaluate(
        "() => Boolean(ApplyPilot.dom.ownedPopup(document.querySelector('.picker-selection')))"
    )
    assert found is False, "a control that is not open owns nothing"


def test_a_bracketed_name_is_read_from_its_last_meaningful_part(open_fixture):
    page = open_fixture("detached_dropdown_picker.html")
    assert (
        page.evaluate("() => ApplyPilot.dom.lastBracketedSegment('custom[eeo][race]')") == "race"
    )
    assert (
        page.evaluate(
            "() => ApplyPilot.dom.lastBracketedSegment('custom[education][0][school]')"
        )
        == "school"
    )


def test_an_eeo_question_with_no_label_still_reaches_its_fact(scan):
    """Its label on the page is a bare asterisk; its name says what it is."""
    from applypilot.mapper import match_facts
    from applypilot.models import FieldObservation

    _, observation = scan("detached_dropdown_picker.html")
    race = next(f for f in observation["fields"] if f["name"] == "custom[eeo][race]")
    assert race["attr_label"] == "race"

    keys = [m.spec.key for m in match_facts(FieldObservation.model_validate(race))]
    assert keys[:1] == ["race_ethnicity"], keys

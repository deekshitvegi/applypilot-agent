"""Regression 47: a picker that searches a remote list.

The school field on a real application reported
``"University of North Texas" is not among the options this control opened``
while typing the same thing by hand found it every time.

Two reasons. The whole value was set at once and one input event fired, which is
enough for a widget filtering a list it already holds and not for one running a
search per keystroke. And the list was read a fraction of a second later, before
the search had come back.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def school_field(page):
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    return next(
        f for f in observation["fields"] if "School" in (f["label"] or "")
    ), observation


def test_the_picker_offers_nothing_until_something_is_typed(open_fixture):
    """The starting condition, and why reading it straight away found nothing."""
    page = open_fixture("async_search_picker.html")
    field, _ = school_field(page)

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp, '')", field["fingerprint"]
    )
    labels = [o["label"] for o in opened["options"]]
    assert labels == ["Please enter 1 or more characters"]
    assert page.evaluate("() => ApplyPilot.act.offeredLabels(document.querySelector('.school'))") == []


def test_opening_with_the_answer_typed_finds_it(open_fixture):
    page = open_fixture("async_search_picker.html")
    field, _ = school_field(page)

    opened = page.evaluate(
        "async (fp) => await ApplyPilot.act.openOptions(fp, 'University of North Texas')",
        field["fingerprint"],
    )
    labels = [o["label"] for o in opened["options"]]
    assert "University of North Texas" in labels, labels


def test_choosing_from_it_is_verified_from_the_pages_own_state(open_fixture):
    page = open_fixture("async_search_picker.html")
    field, _ = school_field(page)

    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {
            "kind": "choose",
            "fingerprint": field["fingerprint"],
            "option_label": "University of North Texas",
        },
    )
    assert result["outcome"] == "verified", result
    assert result["signal"] in {"hidden_backing_input", "rendered_value"}
    assert (
        page.evaluate("() => document.querySelector('.school-value').value")
        == "University of North Texas"
    )


def test_a_school_that_is_not_there_says_what_was_offered(open_fixture):
    page = open_fixture("async_search_picker.html")
    field, _ = school_field(page)

    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {
            "kind": "choose",
            "fingerprint": field["fingerprint"],
            "option_label": "Hogwarts School of Witchcraft",
        },
    )
    assert result["outcome"] == "failed"
    assert "it offered" in result["evidence"], result["evidence"]


def test_add_other_education_is_recognised_and_grows_the_form(open_fixture):
    page = open_fixture("async_search_picker.html")
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    add = [c["text"] for c in observation["add_controls"]]
    assert "+ Add other education" in add, add
    assert "+ Add other work experience" in add, add

    before = page.evaluate("() => document.querySelectorAll('#education .block').length")
    result = page.evaluate(
        "async () => await ApplyPilot.act.addRepeat('+ Add other education')"
    )
    after = page.evaluate("() => document.querySelectorAll('#education .block').length")

    assert result["outcome"] == "verified", result
    assert after == before + 1


def test_a_second_entry_gets_its_own_identity(open_fixture):
    page = open_fixture("async_search_picker.html")
    page.evaluate("async () => await ApplyPilot.act.addRepeat('+ Add other education')")

    observation = page.evaluate("() => ApplyPilot.scan.run()")
    schools = [f for f in observation["fields"] if "School" in (f["label"] or "")]
    assert len(schools) == 2
    assert {s["group_index"] for s in schools} == {0, 1}
    assert len({s["fingerprint"] for s in schools}) == 2


def test_both_entries_can_be_filled_independently(open_fixture):
    page = open_fixture("async_search_picker.html")
    page.evaluate("async () => await ApplyPilot.act.addRepeat('+ Add other education')")

    observation = page.evaluate("() => ApplyPilot.scan.run()")
    schools = sorted(
        (f for f in observation["fields"] if "School" in (f["label"] or "")),
        key=lambda f: f["group_index"],
    )
    for field, wanted in zip(schools, ["University of North Texas", "IIITDM Kurnool"], strict=True):
        result = page.evaluate(
            "async (a) => await ApplyPilot.act.perform(a)",
            {"kind": "choose", "fingerprint": field["fingerprint"], "option_label": wanted},
        )
        assert result["outcome"] == "verified", (wanted, result)

    values = page.evaluate(
        "() => Array.from(document.querySelectorAll('.school-value')).map(i => i.value)"
    )
    assert values == ["University of North Texas", "IIITDM Kurnool"]

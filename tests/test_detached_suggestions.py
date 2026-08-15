"""A picker whose suggestions belong to nothing.

The rule everywhere else is that a dropdown's options come from the list that
dropdown points at, and that rule is why a salary chip and an EEO race list
were never offered together as one question. Plenty of real pickers point at
nothing at all: no aria-controls, no aria-owns, no relationship to follow.

On one of them, typing "Denton" put seven real cities on screen and the panel
reported "this control opened no list of its own, so I cannot tell you what it
offers" -- four times over, on a required field, with the answer visible.

So ownership can be established by behaviour when markup has failed: a list
that was not there before this control was typed into, sitting directly below
it. Nothing already on the page can qualify, and nothing elsewhere on it can.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def city_field(observation):
    for field in observation["fields"]:
        label = (field.get("display_label") or field.get("label") or "").lower()
        if "city" in label:
            return field
    raise AssertionError("no city field in the scan")


def test_a_list_that_appears_beside_the_control_is_that_control_s_list(scan):
    page, observation = scan("detached_suggestions.html")
    field = city_field(observation)
    opened = page.evaluate(
        "([fp, filter]) => ApplyPilot.act.openOptions(fp, filter)",
        [field["fingerprint"], "Denton"],
    )
    labels = [o["label"] for o in opened["options"]]
    assert opened["opened"] is True, opened.get("note")
    assert "Denton, TX, US" in labels, labels


def test_nothing_is_offered_when_nothing_appeared(scan):
    """A control that shows no list still reports honestly.

    The whole risk of reading a list nobody claimed is inventing one. Typing
    something no place matches must come back empty rather than reaching for
    whatever else is on the page.
    """
    page, observation = scan("detached_suggestions.html")
    field = city_field(observation)
    opened = page.evaluate(
        "([fp, filter]) => ApplyPilot.act.openOptions(fp, filter)",
        [field["fingerprint"], ""],
    )
    assert not opened["options"]

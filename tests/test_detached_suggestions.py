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


def test_a_value_the_page_wrote_into_the_box_is_read(scan):
    """The bug this fixture was made for, from the other end.

    Picking a suggestion makes the widget write its own canonical wording into
    the box -- "Denton, TX, US" where "Denton" was typed. Nothing here wrote
    that, and the widget keeps no other state a reader recognises, so refusing
    to read the box left a filled required field reported as unverified and
    asked about four times with the answer on screen.
    """
    page, observation = scan("detached_suggestions.html")
    field = city_field(observation)
    page.evaluate(
        """(fp) => {
          const el = ApplyPilot.scan.findByFingerprint(fp).element;
          el.value = "Denton, TX, US";
        }""",
        field["fingerprint"],
    )
    reading = page.evaluate(
        """(fp) => {
          const found = ApplyPilot.scan.findByFingerprint(fp);
          return ApplyPilot.verify.observe(found.element, found.kind, found.group);
        }""",
        field["fingerprint"],
    )
    assert reading["value"] == "Denton, TX, US", reading
    assert reading["signal"] != "none"


def test_our_own_typing_read_back_is_still_not_evidence(scan):
    """The rule the refusal was written for, which has to survive the fix.

    Typing "Denton" and reading "Denton" back says nothing about whether the
    page accepted it as a choice.
    """
    page, observation = scan("detached_suggestions.html")
    field = city_field(observation)
    reading = page.evaluate(
        """(fp) => {
          const found = ApplyPilot.scan.findByFingerprint(fp);
          ApplyPilot.verify.markTypedAsFilter(found.element, "Denton");
          found.element.value = "Denton";
          return ApplyPilot.verify.observe(found.element, found.kind, found.group);
        }""",
        field["fingerprint"],
    )
    assert reading["value"] == ""
    assert reading["signal"] == "none"


def test_one_control_is_listed_once(scan):
    """An upload reachable two ways came back twice, and broke the resume rule.

    Same fingerprint, same frame, listed twice. Nothing downstream minds -- both
    resolve to the same element -- except the rule that a form offering exactly
    one unlabelled upload must be asking for a resume. It saw two, gave up, and
    left the resume unattached.
    """
    _, observation = scan("control_shapes.html")
    seen = [f["fingerprint"] for f in observation["fields"]]
    assert len(seen) == len(set(seen)), "a control is listed more than once"

"""Regression 46: questions from steps that were not on screen.

A wizard keeps every step in the document and shows one at a time. Checkboxes
and radios were reported as visible wherever they were, because the check for a
styled control returned true outright instead of going on to look at whether any
ancestor was hidden. The panel offered a veteran form and a login choice from
steps that were not showing, and the text fields on the step that *was* showing
were correctly judged hidden and left out.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def labels(observation) -> list[str]:
    return [f["label"] for f in observation["fields"]]


def test_only_the_step_on_screen_is_offered(scan):
    _, observation = scan("multi_step_hidden_steps.html")
    found = labels(observation)

    assert "First name" in found
    assert "Email address" in found
    for hidden in (
        "(VEVRAA) Veteran's Self-Identification Form",
        "I have an account Login I'm applying for the first time Apply",
    ):
        assert hidden not in found, f"{hidden!r} is on a step that is not showing"


def test_a_styled_checkbox_on_the_visible_step_is_still_found(scan):
    """The drawn box is what the applicant sees, so it still counts."""
    _, observation = scan("multi_step_hidden_steps.html")
    assert "Keep me posted about roles" in labels(observation)


def test_a_styled_checkbox_on_a_hidden_step_is_not(scan):
    _, observation = scan("multi_step_hidden_steps.html")
    assert not any("Mutual Arbitration" in label for label in labels(observation))


def test_moving_to_the_next_step_changes_what_is_offered(open_fixture):
    page = open_fixture("multi_step_hidden_steps.html")
    before = page.evaluate("() => ApplyPilot.scan.run()")
    assert "First name" in [f["label"] for f in before["fields"]]

    page.evaluate(
        """() => {
          document.getElementById('step1').classList.remove('active');
          document.getElementById('step2').classList.add('active');
        }"""
    )
    after = page.evaluate("() => ApplyPilot.scan.run()")
    found = [f["label"] for f in after["fields"]]

    assert "First name" not in found
    assert any("Veteran" in label for label in found)
    assert before["signature"] != after["signature"], "the panel can tell the page moved on"

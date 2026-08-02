"""Regression 99: one box asking for several addresses at once.

"Please provide links to your GitHub, portfolio, demo, or AI projects" is one
box wanting several things, and no single fact answers it -- the label is about
GitHub and about a portfolio, so neither can claim it. It was left blank while
every address it asked for sat in the profile.

Nothing here writes anything the applicant did not enter themselves.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import composed_links, resolve_field
from applypilot.models import ControlKind, FieldObservation, Profile

SAVED = {
    "github": "https://github.com/deekshitvegi",
    "website": "deekshitvegi.com",
    "linkedin": "https://www.linkedin.com/in/deekshitvegi",
    "huggingface": "https://huggingface.co/deekshitvegi",
}


def box(label: str, control: ControlKind = ControlKind.TEXTAREA) -> FieldObservation:
    return FieldObservation(
        fingerprint="flinks", label=label, display_label=label,
        control=control, visible=True,
    )


def profile(**facts: str) -> Profile:
    return Profile(facts=dict(facts))


ASKED = "Please provide links to your GitHub, portfolio, demo, or AI projects."


def test_it_writes_out_each_address_the_question_names():
    answer = composed_links(box(ASKED), profile(**SAVED))
    assert answer == (
        "GitHub: https://github.com/deekshitvegi\nPortfolio: deekshitvegi.com"
    )


def test_it_does_not_write_out_the_ones_the_question_did_not_ask_for():
    """LinkedIn and Hugging Face are saved, and this question did not ask."""
    answer = composed_links(box(ASKED), profile(**SAVED))
    assert "LinkedIn" not in answer
    assert "Hugging Face" not in answer


def test_a_question_naming_all_of_them_gets_all_of_them():
    label = "Share your LinkedIn, GitHub, Hugging Face and portfolio URLs"
    answer = composed_links(box(label), profile(**SAVED))
    assert answer.splitlines() == [
        "GitHub: https://github.com/deekshitvegi",
        "Portfolio: deekshitvegi.com",
        "LinkedIn: https://www.linkedin.com/in/deekshitvegi",
        "Hugging Face: https://huggingface.co/deekshitvegi",
    ]


def test_only_what_is_saved_is_written():
    answer = composed_links(box(ASKED), profile(github=SAVED["github"]))
    assert answer == "GitHub: https://github.com/deekshitvegi"


def test_nothing_saved_means_nothing_written():
    assert composed_links(box(ASKED), Profile()) == ""


def test_a_single_line_box_gets_one_line():
    answer = composed_links(box(ASKED, ControlKind.TEXT), profile(**SAVED))
    assert "\n" not in answer
    assert answer == "GitHub: https://github.com/deekshitvegi · Portfolio: deekshitvegi.com"


# ---------------------------------------------------------------------------
# What it must leave alone.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        # One address, asked for plainly. Still the GitHub field.
        "GitHub URL",
        "GitHub profile url",
        "LinkedIn profile URL",
        "Personal website",
        # Asks for links but names none of them.
        "Links",
        # Not a link question at all.
        "Please describe your proudest project",
    ],
)
def test_a_question_about_one_thing_is_left_to_the_ordinary_path(label):
    assert composed_links(box(label), profile(**SAVED)) == ""


def test_the_github_field_still_gets_the_github_answer():
    """Composing must not have taken the single-address questions with it."""
    resolution = resolve_field(box("GitHub URL", ControlKind.TEXT), profile(**SAVED))
    assert resolution.answer is not None
    assert resolution.answer.value == SAVED["github"]
    assert resolution.answer.fact_key == "github"


def test_the_composed_answer_says_where_it_came_from():
    resolution = resolve_field(box(ASKED), profile(**SAVED))
    assert resolution.answer is not None
    assert "saved" in resolution.answer.reason
    assert resolution.answer.value.startswith("GitHub: ")


def test_it_never_invents_an_address():
    """Only what is in the profile, character for character."""
    answer = composed_links(box(ASKED), profile(github="https://github.com/x"))
    assert answer == "GitHub: https://github.com/x"
    assert "portfolio" not in answer.lower() or "deekshitvegi" not in answer

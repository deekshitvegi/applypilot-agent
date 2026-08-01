"""Regression 43: section headings that are not heading tags.

A form styled "Education" and "Work experience" as coloured divs. Reading only
h1-h5 found no section, so every education and employment field was blocked from
resolving -- on a page whose answers were all in the profile already.
"""

from __future__ import annotations

import pytest

from applypilot.models import (
    EducationRecord,
    ExperienceRecord,
    PageObservation,
    Profile,
)
from applypilot.runloop import plan_page

pytestmark = pytest.mark.browser


@pytest.fixture
def profile() -> Profile:
    return Profile(
        education=[
            EducationRecord(
                school="University of Example",
                degree="M.S.",
                field_of_study="Artificial Intelligence",
                start_date="Aug 2023",
                end_date="Jul 2025",
                gpa="3.8",
            )
        ],
        experience=[
            ExperienceRecord(
                company="Northwind Labs",
                title="Machine Learning Engineer",
                location="Dallas, TX",
                start_date="Jun 2025",
                current=True,
            )
        ],
    )


def test_a_styled_div_is_recognised_as_the_section_heading(scan):
    _, observation = scan("styled_section_headings.html")
    sections = {f["label"]: f["section"] for f in observation["fields"]}
    assert sections["School / education institution"] == "Education"
    assert sections["Company"] == "Work experience"


def test_a_fields_own_label_is_never_mistaken_for_the_section(scan):
    _, observation = scan("styled_section_headings.html")
    for field in observation["fields"]:
        assert field["section"] in {"Education", "Work experience"}, (
            f"{field['label']} got section {field['section']!r}"
        )


def test_the_history_fields_now_fill(scan, profile):
    _, raw = scan("styled_section_headings.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)

    filled = {
        next(f.display_label for f in observation.fields if f.fingerprint == a.fingerprint): a.value
        for a in plan.actions
    }
    assert filled["School / education institution"] == "University of Example"
    assert filled["Area of study"] == "Artificial Intelligence"
    assert filled["GPA"] == "3.8"
    assert filled["Graduation Year"] == "2025", "a year field gets the year"
    assert filled["Company"] == "Northwind Labs"
    assert filled["Job title"] == "Machine Learning Engineer"
    assert filled["Start year"] == "2025"
    assert filled["Degree"] == "Master's degree", "matched against the options offered"


def test_nothing_required_is_left_unanswered(scan, profile):
    _, raw = scan("styled_section_headings.html")
    observation = PageObservation.model_validate(raw)
    plan = plan_page(observation, profile)
    assert [q.label for q in plan.questions if q.required] == []

"""One test per mistake this agent has made on a real application.

The numbering follows the list kept in docs/REGRESSIONS.md. Nothing here checks
an employer or an applicant tracking system by name; each test states the shape
of the mistake so the fix has to be a general one.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import best_fact, match_facts, resolve_field, resolve_page
from applypilot.matching import best_option, rank_options
from applypilot.models import (
    AnswerSource,
    ControlKind,
    EducationRecord,
    ExperienceRecord,
    FieldObservation,
    Option,
    Profile,
)


def field(
    label: str = "",
    control: ControlKind = ControlKind.TEXT,
    *,
    name: str = "",
    attr_label: str = "",
    options: list[str] | None = None,
    required: bool = False,
    section: str = "",
    group: str = "",
    group_index: int = 0,
    fingerprint: str = "",
) -> FieldObservation:
    return FieldObservation(
        fingerprint=fingerprint or f"fp:{label or name}",
        label=label,
        attr_label=attr_label,
        name=name,
        control=control,
        options=[Option(label=o, value=o) for o in (options or [])],
        required=required,
        section=section,
        group=group,
        group_index=group_index,
        options_source="native" if options else "none",
    )


@pytest.fixture
def profile() -> Profile:
    return Profile(
        facts={
            "full_name": "Deekshitth Vegi",
            "first_name": "Deekshitth",
            "last_name": "Vegi",
            "email": "someone@example.com",
            "phone": "5125550147",
            "street_address": "1200 Example Parkway",
            "address_line_2": "Apt 14",
            "city": "Austin",
            "state": "Texas",
            "postal_code": "78701",
            "country": "United States",
            "work_authorization": "Yes",
            "requires_sponsorship": "No",
            "over_18": "Yes",
            "background_check_consent": "Yes",
            "willing_to_relocate": "Yes",
            "notice_period": "2 weeks",
            "salary_expectation": "150000",
            "linkedin": "https://www.linkedin.com/in/example",
        },
        education=[
            EducationRecord(
                school="University of Example",
                degree="Master's Degree",
                field_of_study="Computer Science",
                start_date="2021-08",
                end_date="2023-05",
            )
        ],
        experience=[
            ExperienceRecord(
                company="HCLTech",
                title="Machine Learning Engineer",
                location="Austin, TX",
                start_date="2023-06",
                end_date="",
                current=True,
            )
        ],
    )


# ---------------------------------------------------------------------------
# 1. A short answer must not claim a long question.
# ---------------------------------------------------------------------------


def test_country_does_not_answer_a_sponsorship_question(profile):
    sponsorship = field(
        "Does this role require visa sponsorship to work in the country in which "
        "this role is based?",
        ControlKind.SELECT,
        options=["Yes", "No"],
        required=True,
    )
    match = best_fact(sponsorship)
    assert match is not None
    assert match.spec.key == "requires_sponsorship"

    resolution = resolve_field(sponsorship, profile)
    assert resolution.answer is not None
    assert resolution.answer.value == "No"
    assert resolution.answer.fact_key == "requires_sponsorship"


def test_country_is_not_a_candidate_for_any_sponsorship_phrasing(profile):
    for label in (
        "Will you now or in the future require sponsorship to work in the country where this role sits?",
        "Do you require immigration sponsorship for employment visa status in this country?",
    ):
        keys = {m.spec.key for m in match_facts(field(label, ControlKind.SELECT, options=["Yes", "No"]))}
        assert "country" not in keys, label


# ---------------------------------------------------------------------------
# 2. A control named `countryRegion` that is visibly labelled State is a State.
# ---------------------------------------------------------------------------


def test_visible_label_beats_the_controls_own_name(profile):
    state = field("State", ControlKind.SELECT, name="countryRegion", options=["Texas", "Utah"])
    resolution = resolve_field(state, profile)
    assert resolution.fact_key == "state"
    assert resolution.answer is not None
    assert resolution.answer.value == "Texas"


def test_country_named_control_without_a_visible_label_is_low_confidence(profile):
    unlabelled = field("", ControlKind.SELECT, attr_label="country", options=["United States", "Canada"])
    resolution = resolve_field(unlabelled, profile)
    assert resolution.answer is not None
    assert resolution.answer.confidence < 0.6


# ---------------------------------------------------------------------------
# 3. History labels are short field names, never sentence questions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        "Will you now or in the future require sponsorship from the company?",
        "Are you subject to a non-compete agreement with your current or former company?",
        "Do you have a Bachelor's degree?",
        "Have you ever held a position that required a security clearance?",
    ],
)
def test_history_never_answers_a_sentence_question(profile, label):
    observation = field(label, ControlKind.TEXT)
    keys = {m.spec.key for m in match_facts(observation)}
    assert not any(k.startswith(("experience.", "education.")) for k in keys), keys

    resolution = resolve_field(observation, profile)
    assert resolution.answer is None or resolution.answer.source is not AnswerSource.HISTORY


def test_history_fills_inside_a_history_block(profile):
    company = field("Company", ControlKind.TEXT, section="Work Experience", group="exp-1")
    resolution = resolve_field(company, profile)
    assert resolution.answer is not None
    assert resolution.answer.value == "HCLTech"
    assert resolution.answer.source is AnswerSource.HISTORY


def test_history_fills_behind_an_unmistakable_label(profile):
    school = field("School", ControlKind.TEXT)
    resolution = resolve_field(school, profile)
    assert resolution.answer is not None
    assert resolution.answer.value == "University of Example"


def test_company_outside_a_history_block_is_not_filled(profile):
    stray = field("Company", ControlKind.TEXT)
    assert resolve_field(stray, profile).answer is None


# ---------------------------------------------------------------------------
# 4. A search filter is not a job title.
# ---------------------------------------------------------------------------


def test_position_location_is_not_a_job_title(profile):
    keys = {m.spec.key for m in match_facts(field("Position Location", ControlKind.TEXT))}
    assert "experience.title" not in keys
    assert "experience.location" not in keys
    assert resolve_field(field("Position Location", ControlKind.TEXT), profile).answer is None


# ---------------------------------------------------------------------------
# 5. Rank options by closeness, not by first containment.
# ---------------------------------------------------------------------------


def test_united_states_does_not_select_minor_outlying_islands():
    options = [
        Option(label="United States Minor Outlying Islands"),
        Option(label="United States"),
    ]
    chosen = best_option("United States", options)
    assert chosen is not None
    assert chosen.option.label == "United States"


def test_a_containment_only_match_that_is_far_off_is_refused():
    options = [Option(label="United States Minor Outlying Islands")]
    assert best_option("United States", options) is None


def test_value_synonyms_still_resolve():
    options = [Option(label="United States of America"), Option(label="Canada")]
    chosen = best_option("United States", options)
    assert chosen is not None
    assert chosen.option.label == "United States of America"


# ---------------------------------------------------------------------------
# 6. Labels differing only by a trailing digit are different fields.
# ---------------------------------------------------------------------------


def test_address_line_1_and_2_are_different_fields(profile):
    line1 = resolve_field(field("Address Line 1", ControlKind.TEXT), profile)
    line2 = resolve_field(field("Address Line 2", ControlKind.TEXT), profile)
    assert line1.answer is not None and line1.answer.value == "1200 Example Parkway"
    assert line2.answer is not None and line2.answer.value == "Apt 14"


def test_street_address_does_not_leak_into_line_2():
    keys = {m.spec.key for m in match_facts(field("Address Line 2", ControlKind.TEXT))}
    assert "street_address" not in keys


# ---------------------------------------------------------------------------
# 7 and 16. A follow-up is never inferred, but a saved answer to it is used.
# ---------------------------------------------------------------------------


def test_conditional_follow_up_is_not_answered_from_a_general_fact(profile):
    follow_up = field("If yes, what department and what country?", ControlKind.TEXT, required=True)
    resolution = resolve_field(follow_up, profile)
    assert resolution.answer is None
    assert resolution.question is not None


def test_conditional_follow_up_uses_an_answer_given_to_that_exact_question(profile):
    follow_up = field("If yes, what department and what country?", ControlKind.TEXT, required=True)
    learned = {"if yes, what department and what country": "Engineering, United States"}
    resolution = resolve_field(follow_up, profile, learned)
    assert resolution.question is None
    assert resolution.answer is not None
    assert resolution.answer.value == "Engineering, United States"
    assert resolution.answer.source is AnswerSource.LEARNED


# ---------------------------------------------------------------------------
# 8. A dropdown's own placeholder row is never an answer.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "placeholder",
    ["No Selection", "- Select -", "Select...", "Please select an option", "--", "Choose one", ""],
)
def test_placeholder_rows_are_never_selected(placeholder):
    options = [Option(label=placeholder), Option(label="Texas")]
    assert all(m.option.label != placeholder for m in rank_options("Texas", options))
    assert best_option(placeholder, options) is None


# ---------------------------------------------------------------------------
# 15. Short questions must be matchable.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Name", "Deekshitth Vegi"), ("Email", "someone@example.com"), ("Phone", "5125550147")],
)
def test_short_labels_resolve(profile, label, expected):
    resolution = resolve_field(field(label, ControlKind.TEXT, required=True), profile)
    assert resolution.answer is not None, f"{label} was not matched"
    assert resolution.answer.value == expected


def test_phrasings_of_the_same_question_reach_the_same_fact(profile):
    for label in ("Country", "What country are you in?", "Country/Region of Residence", "Country of Residence"):
        resolution = resolve_field(
            field(label, ControlKind.SELECT, options=["United States", "Canada"]), profile
        )
        assert resolution.fact_key == "country", label
        assert resolution.answer is not None and resolution.answer.value == "United States"


def test_the_same_fact_answers_a_dropdown_a_radio_group_and_a_text_box(profile):
    as_select = field("Country", ControlKind.SELECT, options=["United States", "Canada"])
    as_radio = field("Country", ControlKind.RADIO, options=["United States", "Canada"])
    as_text = field("Country", ControlKind.TEXT)
    for observation in (as_select, as_radio, as_text):
        resolution = resolve_field(observation, profile)
        assert resolution.answer is not None
        assert resolution.answer.value == "United States"


# ---------------------------------------------------------------------------
# 25 and 26. Ask everything required; fill optional fields you can; leave the
# rest of the optional decoration blank.
# ---------------------------------------------------------------------------


def test_optional_fields_that_the_profile_can_fill_are_filled(profile):
    optional_education = [
        field("School", ControlKind.TEXT, section="Education"),
        field("Degree", ControlKind.TEXT, section="Education"),
        field("Field of Study", ControlKind.TEXT, section="Education"),
        field("Location", ControlKind.TEXT, section="Work Experience", group="exp-1"),
    ]
    resolutions = resolve_page(optional_education, profile)
    assert all(r.answer is not None for r in resolutions), [
        (r.field.label, r.skipped) for r in resolutions
    ]
    assert [r.answer.value for r in resolutions] == [
        "University of Example",
        "Master's Degree",
        "Computer Science",
        "Austin, TX",
    ]


@pytest.mark.parametrize(
    "label", ["Middle Name", "Home Phone", "Phone Extension", "County", "Fax Number"]
)
def test_optional_decoration_is_left_blank_rather_than_asked(profile, label):
    resolution = resolve_field(field(label, ControlKind.TEXT), profile)
    assert resolution.question is None, f"{label} should not become a question"
    assert resolution.answer is None
    assert resolution.skipped


def test_anything_required_is_always_asked(profile):
    unknown_required = field(
        "Describe a time you shipped something under a hard deadline",
        ControlKind.TEXTAREA,
        required=True,
    )
    resolution = resolve_field(unknown_required, profile)
    assert resolution.question is not None
    assert resolution.question.required


def test_a_required_optional_looking_extra_is_still_asked(profile):
    resolution = resolve_field(field("Middle Name", ControlKind.TEXT, required=True), profile)
    assert resolution.question is not None


# ---------------------------------------------------------------------------
# Voluntary questions are never auto-answered unless that was saved.
# ---------------------------------------------------------------------------


def test_demographics_are_asked_by_default(profile):
    profile.facts["gender"] = "Male"
    resolution = resolve_field(
        field("Gender", ControlKind.SELECT, options=["Male", "Female", "I don't wish to answer"]),
        profile,
    )
    assert resolution.answer is None
    assert resolution.question is not None


def test_demographics_are_filled_once_that_preference_is_saved(profile):
    profile.facts["gender"] = "Male"
    profile.answer_demographics = True
    resolution = resolve_field(
        field("Gender", ControlKind.SELECT, options=["Male", "Female", "I don't wish to answer"]),
        profile,
    )
    assert resolution.answer is not None
    assert resolution.answer.value == "Male"

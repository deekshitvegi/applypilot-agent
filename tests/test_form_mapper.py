from applypilot.form_mapper import plan_form_fill
from applypilot.models import CandidateProfile, FormField, FormOption, ReusableAnswer


def test_maps_profile_answers_and_blocks_passwords() -> None:
    profile = CandidateProfile(
        legal_name="Test Candidate",
        email="candidate@example.test",
        requires_sponsorship=False,
    )
    fields = [
        FormField(id="first", label="First name", required=True),
        FormField(id="last", label="Last name", required=True),
        FormField(id="email", label="Email address", field_type="email", required=True),
        FormField(
            id="sponsor",
            label="Will you require employment sponsorship?",
            field_type="select",
            options=[FormOption(value="yes", label="Yes"), FormOption(value="no", label="No")],
            required=True,
        ),
        FormField(id="essay", label="Why are you interested?", field_type="textarea", required=True),
        FormField(id="password", label="Account password", field_type="password"),
    ]

    plan = plan_form_fill("https://careers.example.test/apply", fields, profile, [])

    values = {action.field_id: action.value for action in plan.actions}
    assert values == {
        "first": "Test",
        "last": "Candidate",
        "email": "candidate@example.test",
        "sponsor": "no",
    }
    assert [field.field_id for field in plan.unknown_fields] == ["essay"]
    assert [field.field_id for field in plan.blocked_fields] == ["password"]
    assert plan.submit_allowed is False
    assert plan.confirmation_required is True


def test_uses_similar_reusable_answer() -> None:
    field = FormField(
        id="clearance",
        label="Are you willing to obtain a security clearance?",
        required=True,
    )
    answer = ReusableAnswer(
        question="Would you be willing to obtain a security clearance?",
        answer="Yes",
    )

    plan = plan_form_fill("https://example.test", [field], CandidateProfile(), [answer])

    assert plan.actions[0].value == "Yes"
    assert plan.actions[0].source == f"answer.{answer.id}"


def test_maps_voluntary_demographics_without_an_ai_provider() -> None:
    profile = CandidateProfile(
        race_ethnicity="Prefer not to answer",
        veteran_status="No",
        disability_status="Yes",
    )
    fields = [
        FormField(
            id="race",
            label="Race / ethnicity",
            field_type="select",
            options=[
                FormOption(value="decline", label="I prefer not to answer"),
                FormOption(value="asian", label="Asian"),
            ],
        ),
        FormField(
            id="veteran",
            label="Protected veteran status",
            field_type="select",
            options=[
                FormOption(value="protected", label="Yes, I am a protected veteran"),
                FormOption(value="not-protected", label="No, I am not a protected veteran"),
            ],
        ),
        FormField(
            id="disability",
            label="Disability status",
            field_type="select",
            options=[
                FormOption(value="yes", label="Yes, I have a disability"),
                FormOption(value="no", label="No, I do not have a disability"),
            ],
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "race": "decline",
        "veteran": "not-protected",
        "disability": "yes",
    }


def test_maps_a_saved_multi_choice_answer_to_checkbox_group() -> None:
    answer = ReusableAnswer(
        question="Which office location(s) are you interested in?",
        answer="Remote, US",
    )
    fields = [
        FormField(
            id="redwood",
            label="Which office location(s) are you interested in? Redwood City, CA",
            field_type="checkbox",
        ),
        FormField(
            id="remote",
            label="Which office location(s) are you interested in? Remote, US",
            field_type="checkbox",
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, CandidateProfile(), [answer])

    assert {action.field_id: action.value for action in plan.actions} == {
        "redwood": "false",
        "remote": "true",
    }


def test_united_states_does_not_get_mistaken_for_state_field() -> None:
    profile = CandidateProfile(
        region="Illinois",
        work_authorization="Yes, I am authorized to work in the United States.",
    )
    fields = [
        FormField(
            id="authorization",
            label="Are you legally authorized to work in the United States?",
            field_type="select",
            required=True,
            options=[FormOption(value="yes", label="Yes"), FormOption(value="no", label="No")],
        ),
        FormField(
            id="state",
            label="In what US state do you currently reside in?",
            field_type="select",
            required=True,
            options=[FormOption(value="IL", label="Illinois")],
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "authorization": "yes",
        "state": "IL",
    }


def test_optional_unanswered_questions_are_included_for_guided_review() -> None:
    fields = [
        FormField(id="hispanic", label="Are you Hispanic/Latino?", field_type="select"),
        FormField(id="portfolio", label="Website", field_type="url"),
    ]

    plan = plan_form_fill("https://example.test", fields, CandidateProfile(), [])

    assert [(field.field_id, field.required) for field in plan.unknown_fields] == [
        ("hispanic", False),
        ("portfolio", False),
    ]


def test_phone_country_code_is_not_filled_with_the_whole_phone_number() -> None:
    profile = CandidateProfile(phone="+1 (940) 843-6087", country="United States")
    fields = [
        FormField(
            id="phone-code",
            label="Mobile Phone Country Code",
            field_type="select",
            options=[
                FormOption(value="US", label="US +1 United States"),
                FormOption(value="IN", label="IN +91 India"),
            ],
        )
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert plan.actions[0].value == "US"
    assert plan.actions[0].source == "profile.phone"


def test_maps_grouped_authorization_and_sponsorship_radios() -> None:
    profile = CandidateProfile(
        work_authorization="Yes, I am authorized to work in the United States.",
        requires_sponsorship=False,
    )
    fields = [
        FormField(
            id="authorized",
            label="Are you legally authorized to work in the United States?",
            group_label="Are you legally authorized to work in the United States?",
            name="authorized",
            field_type="radio",
            required=True,
            options=[FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")],
        ),
        FormField(
            id="sponsorship",
            label="Will you now or in the future require sponsorship?",
            group_label="Will you now or in the future require sponsorship?",
            name="sponsorship",
            field_type="radio",
            required=True,
            options=[FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")],
        ),
    ]

    plan = plan_form_fill("https://careers.example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "authorized": "Yes",
        "sponsorship": "No",
    }


def test_maps_referral_source_from_captured_job_url() -> None:
    field = FormField(
        id="source",
        label="How did you find out about this position?",
        field_type="radio",
        options=[
            FormOption(value="indeed", label="Indeed"),
            FormOption(value="linkedin", label="LinkedIn"),
            FormOption(value="other", label="Other"),
        ],
    )

    plan = plan_form_fill(
        "https://careers.example.test",
        [field],
        CandidateProfile(),
        [],
        source_url="https://www.linkedin.com/jobs/view/123",
    )

    assert plan.actions[0].value == "linkedin"
    assert plan.actions[0].source == "job.source_url"


def test_selects_only_resume_supported_skill_checkboxes() -> None:
    group = "What development languages are you most experienced with?"
    fields = [
        FormField(
            id="python",
            label=f"{group} Python",
            group_label=group,
            option_label="Python",
            field_type="checkbox",
            required=True,
        ),
        FormField(
            id="ruby",
            label=f"{group} Ruby",
            group_label=group,
            option_label="Ruby",
            field_type="checkbox",
            required=True,
        ),
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(),
        [],
        resume_text="Built production APIs and AI agents using Python.",
    )

    assert {action.field_id: action.value for action in plan.actions} == {
        "python": "true",
        "ruby": "false",
    }
    assert not plan.unknown_fields


def test_relocation_willingness_does_not_select_every_city() -> None:
    group = "Which city would you be interested in for a relocation package?"
    fields = [
        FormField(
            id="san-jose",
            label=f"{group} San Jose",
            group_label=group,
            option_label="San Jose, CA",
            field_type="checkbox",
            required=True,
        ),
        FormField(
            id="kansas-city",
            label=f"{group} Kansas City",
            group_label=group,
            option_label="Kansas City, MO",
            field_type="checkbox",
            required=True,
        ),
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(willing_to_relocate=True),
        [],
    )

    assert not plan.actions
    assert [(item.field_id, item.label) for item in plan.unknown_fields] == [
        ("san-jose", group)
    ]

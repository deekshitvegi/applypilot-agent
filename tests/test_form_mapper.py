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

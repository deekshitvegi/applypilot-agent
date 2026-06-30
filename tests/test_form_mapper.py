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

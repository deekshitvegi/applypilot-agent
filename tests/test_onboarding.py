from applypilot.models import CandidateProfile
from applypilot.onboarding import get_onboarding_state


def test_empty_profile_starts_with_legal_name() -> None:
    state = get_onboarding_state(CandidateProfile())

    assert state.complete is False
    assert state.next_question is not None
    assert state.next_question.key == "legal_name"


def test_complete_profile_has_no_next_question() -> None:
    profile = CandidateProfile(
        legal_name="Test Candidate",
        email="candidate@example.test",
        phone="+1 555 0100",
        city="Test City",
        country="US",
        work_authorization="Authorized to work in the US",
        requires_sponsorship=False,
        willing_to_relocate=True,
        notice_period="Two weeks",
        remote_preference="flexible",
    )

    state = get_onboarding_state(profile)

    assert state.complete is True
    assert state.missing_count == 0
    assert state.next_question is None


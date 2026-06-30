from __future__ import annotations

from .models import CandidateProfile, OnboardingQuestion, OnboardingState


QUESTIONS = (
    OnboardingQuestion(key="legal_name", prompt="What is your full legal name?"),
    OnboardingQuestion(key="email", prompt="Which email should applications use?"),
    OnboardingQuestion(key="phone", prompt="Which phone number should applications use?"),
    OnboardingQuestion(key="address_line_1", prompt="What is your street address?"),
    OnboardingQuestion(key="city", prompt="What city do you currently live in?"),
    OnboardingQuestion(key="region", prompt="What state, province, or region do you live in?"),
    OnboardingQuestion(key="postal_code", prompt="What is your postal or ZIP code?"),
    OnboardingQuestion(key="country", prompt="What country do you currently live in?"),
    OnboardingQuestion(key="current_title", prompt="What is your current professional title?"),
    OnboardingQuestion(
        key="work_authorization",
        prompt="What work authorization should be stated on applications?",
    ),
    OnboardingQuestion(
        key="requires_sponsorship",
        prompt="Will you now or in the future require employment sponsorship?",
        input_type="boolean",
    ),
    OnboardingQuestion(
        key="willing_to_relocate",
        prompt="Are you willing to relocate for a suitable role?",
        input_type="boolean",
    ),
    OnboardingQuestion(
        key="willing_to_travel",
        prompt="Are you willing to travel for work?",
        input_type="boolean",
    ),
    OnboardingQuestion(
        key="age_18_or_older",
        prompt="Are you at least 18 years old?",
        input_type="boolean",
    ),
    OnboardingQuestion(
        key="background_check_consent",
        prompt="Are you willing to complete a lawful background check if required?",
        input_type="boolean",
    ),
    OnboardingQuestion(key="notice_period", prompt="What is your notice period?"),
    OnboardingQuestion(
        key="remote_preference",
        prompt="What work arrangement do you prefer?",
        input_type="choice",
        choices=["remote", "hybrid", "onsite", "flexible"],
    ),
)


def get_onboarding_state(profile: CandidateProfile) -> OnboardingState:
    missing = []
    values = profile.model_dump()
    for question in QUESTIONS:
        value = values[question.key]
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(question)

    return OnboardingState(
        complete=not missing,
        missing_count=len(missing),
        next_question=missing[0] if missing else None,
    )

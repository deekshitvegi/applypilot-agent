from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = ""
    preferred_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    work_authorization: str = ""
    requires_sponsorship: bool | None = None
    willing_to_relocate: bool | None = None
    notice_period: str = ""
    desired_salary: str = ""
    remote_preference: Literal["", "remote", "hybrid", "onsite", "flexible"] = ""
    custom_answers: dict[str, str] = Field(default_factory=dict)


class OnboardingQuestion(BaseModel):
    key: str
    prompt: str
    input_type: Literal["text", "boolean", "choice"] = "text"
    choices: list[str] = Field(default_factory=list)


class OnboardingState(BaseModel):
    complete: bool
    missing_count: int
    next_question: OnboardingQuestion | None = None


class JobApplicationOptions(BaseModel):
    source_url: str
    company_application_url: str = ""
    company_url_verified: bool = False
    easy_apply_available: bool = False


class ApplicationRouteDecision(BaseModel):
    route: Literal["company_site", "easy_apply", "manual_review", "unavailable"]
    target_url: str = ""
    reason: str

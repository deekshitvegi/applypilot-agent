from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = ""
    preferred_name: str = ""
    email: str = ""
    phone: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    github_url: str = ""
    current_title: str = ""
    years_of_experience: str = ""
    work_authorization: str = ""
    requires_sponsorship: bool | None = None
    willing_to_relocate: bool | None = None
    willing_to_travel: bool | None = None
    age_18_or_older: bool | None = None
    background_check_consent: bool | None = None
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


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReusableAnswer(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    answer: str
    field_type: Literal["text", "boolean", "choice", "number"] = "text"
    sensitive: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class ResumeDocument(BaseModel):
    id: str = Field(default_factory=new_id)
    filename: str
    media_type: str
    sha256: str
    extracted_text: str
    uploaded_at: datetime = Field(default_factory=utc_now)
    active: bool = True


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=new_id)
    category: Literal["summary", "skill", "experience", "education", "project", "other"]
    text: str
    source_quote: str


class ResumeEvidence(BaseModel):
    summary: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)


class JobContext(BaseModel):
    source_url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str
    company_application_url: str = ""


class TailoredBullet(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class TailoredExperience(BaseModel):
    heading: str
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredResume(BaseModel):
    headline: str
    summary: str
    skills: list[str] = Field(default_factory=list)
    experiences: list[TailoredExperience] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TailorRequest(BaseModel):
    job: JobContext


class ChatRequest(BaseModel):
    message: str
    job: JobContext | None = None


class ChatResponse(BaseModel):
    answer: str
    suggested_actions: list[str] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    provider: str
    model: str
    configured: bool

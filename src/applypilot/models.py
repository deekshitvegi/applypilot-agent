from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = ""
    preferred_name: str = ""
    pronouns: str = ""
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
    gender_identity: str = ""
    race_ethnicity: str = ""
    veteran_status: str = ""
    disability_status: str = ""
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
    company_url_verified: bool = False
    easy_apply_available: bool = False
    adapter: Literal["linkedin", "greenhouse", "lever", "workday", "generic"] = "generic"


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


class JobFitAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Literal["strong", "possible", "stretch"]
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    recommendation: str


class TailorRequest(BaseModel):
    job: JobContext


class TailoredArtifactRequest(BaseModel):
    job: JobContext
    application_id: str = ""


class TailoredArtifact(BaseModel):
    id: str = Field(default_factory=new_id)
    application_id: str = ""
    tailored: TailoredResume
    created_at: datetime = Field(default_factory=utc_now)


class JobPreparation(BaseModel):
    analysis: JobFitAnalysis
    artifact: TailoredArtifact


class ChatRequest(BaseModel):
    message: str
    job: JobContext | None = None
    images: list["ChatImage"] = Field(default_factory=list, max_length=3)


class ChatImage(BaseModel):
    filename: str = Field(max_length=180)
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"]
    data_base64: str = Field(max_length=8_000_000)

    @field_validator("data_base64")
    @classmethod
    def validate_base64_size(cls, value: str) -> str:
        import base64
        import binascii

        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Image data must be valid base64") from exc
        if len(decoded) > 4 * 1024 * 1024:
            raise ValueError("Each image must be 4 MB or smaller")
        return value


class ChatResponse(BaseModel):
    answer: str
    suggested_actions: list[str] = Field(default_factory=list)


class ApplicationQuestionDraftRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    job: JobContext | None = None


class ApplicationAnswerDraft(BaseModel):
    answer: str


class ProviderStatus(BaseModel):
    provider: str
    model: str
    configured: bool
    source: Literal["encrypted_local", "environment", "none"] = "none"


class ProviderConfigRequest(BaseModel):
    provider: Literal["ollama", "gemini", "openai", "anthropic"]
    api_key: str = Field(default="", max_length=500)
    model: str = Field(min_length=2, max_length=120)

    @field_validator("api_key", "model", mode="before")
    @classmethod
    def strip_config_value(cls, value: str) -> str:
        return str(value).strip()

    @model_validator(mode="after")
    def require_remote_provider_key(self) -> ProviderConfigRequest:
        if self.provider != "ollama" and len(self.api_key) < 8:
            raise ValueError("An API key is required for this provider")
        return self


class FormOption(BaseModel):
    value: str
    label: str


class FormField(BaseModel):
    id: str
    label: str
    name: str = ""
    field_type: Literal[
        "text",
        "email",
        "tel",
        "url",
        "number",
        "textarea",
        "select",
        "checkbox",
        "radio",
        "file",
        "password",
        "other",
    ] = "text"
    required: bool = False
    value: str = ""
    options: list[FormOption] = Field(default_factory=list)


class FormFillAction(BaseModel):
    field_id: str
    value: str
    source: str
    confidence: float = Field(ge=0, le=1)


class UnknownField(BaseModel):
    field_id: str
    label: str
    required: bool
    reason: str


class FormPlanRequest(BaseModel):
    page_url: str
    fields: list[FormField]
    adapter: Literal["linkedin", "greenhouse", "lever", "workday", "generic"] = "generic"


class FormFillPlan(BaseModel):
    page_url: str
    adapter: Literal["linkedin", "greenhouse", "lever", "workday", "generic"] = "generic"
    actions: list[FormFillAction] = Field(default_factory=list)
    unknown_fields: list[UnknownField] = Field(default_factory=list)
    blocked_fields: list[UnknownField] = Field(default_factory=list)
    confirmation_required: bool = True
    submit_allowed: bool = False


ApplicationStatus = Literal[
    "discovered",
    "analyzed",
    "materials_ready",
    "filling",
    "review_required",
    "blocked",
    "submitted",
    "abandoned",
]


class ApplicationEvent(BaseModel):
    id: str = Field(default_factory=new_id)
    event_type: str
    message: str
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ApplicationRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    job: JobContext
    status: ApplicationStatus = "discovered"
    route: ApplicationRouteDecision | None = None
    blocked_reason: str = ""
    events: list[ApplicationEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ApplicationCreate(BaseModel):
    job: JobContext
    route: ApplicationRouteDecision | None = None


class ApplicationTransition(BaseModel):
    status: ApplicationStatus
    message: str
    metadata: dict[str, str] = Field(default_factory=dict)

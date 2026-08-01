"""Typed observations, actions and results.

These are the contract between the injected functions in the extension and the
reasoning in the service. Keeping them typed is what lets the state machine stay
small: a page is a list of :class:`FieldObservation`, a decision is a list of
:class:`PlannedAction`, and an outcome is one of four honest verdicts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(UTC)


class ControlKind(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    TEL = "tel"
    NUMBER = "number"
    URL = "url"
    DATE = "date"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    COMBOBOX = "combobox"
    MULTISELECT = "multiselect"
    FILE = "file"
    PASSWORD = "password"
    UNKNOWN = "unknown"


TEXTUAL_CONTROLS = {
    ControlKind.TEXT,
    ControlKind.TEXTAREA,
    ControlKind.EMAIL,
    ControlKind.TEL,
    ControlKind.NUMBER,
    ControlKind.URL,
    ControlKind.DATE,
}

CHOICE_CONTROLS = {
    ControlKind.SELECT,
    ControlKind.RADIO,
    ControlKind.COMBOBOX,
    ControlKind.MULTISELECT,
}


class PageKind(StrEnum):
    """What sort of page the agent is looking at.

    These behave completely differently and conflating them is what produced
    phantom fields on search pages and 'every application is a login page'.
    """

    APPLICATION = "application"
    LISTING = "listing"
    BOARD = "board"
    SEARCH = "search"
    SIGN_IN = "sign_in"
    REGISTRATION = "registration"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


class HostRole(StrEnum):
    """Decided from the URL alone, never by a model."""

    EMPLOYER = "employer"
    BOARD = "board"
    AGGREGATOR = "aggregator"
    THIRD_PARTY = "third_party"


class Outcome(StrEnum):
    """The four verdicts, kept distinct on purpose."""

    ATTEMPTED = "attempted"
    ACCEPTED = "accepted"
    VERIFIED = "verified"
    FAILED = "failed"


class AnswerSource(StrEnum):
    PROFILE = "profile"
    HISTORY = "history"
    LEARNED = "learned"
    USER = "user"
    MODEL = "model"
    DOCUMENT = "document"


class Option(BaseModel):
    label: str = ""
    value: str = ""
    disabled: bool = False
    selected: bool = False


class FieldObservation(BaseModel):
    """One control as the page presents it.

    ``label`` is what the applicant can read. ``attr_label`` is derived from the
    control's name, id or placeholder and is deliberately weak: a page that
    names its State field ``countryRegion`` must not be able to talk the mapper
    into filling it with a country.
    """

    model_config = ConfigDict(populate_by_name=True)

    fingerprint: str
    frame: str = ""
    label: str = ""
    attr_label: str = ""
    control: ControlKind = ControlKind.UNKNOWN
    name: str = ""
    section: str = ""
    group: str = ""
    group_index: int = 0
    options: list[Option] = Field(default_factory=list)
    required: bool = False
    visible: bool = True
    disabled: bool = False
    readonly: bool = False
    value: str = ""
    checked: bool | None = None
    max_length: int | None = None
    accepts: str = ""
    #: What the control shows when empty. Used to work out the shape a date
    #: field wants, never as a label.
    placeholder: str = ""
    input_type: str = ""
    options_source: Literal["native", "owned_popup", "none"] = "none"

    @property
    def display_label(self) -> str:
        """The label the mapper is allowed to reason about."""
        return self.label.strip()

    @property
    def has_visible_label(self) -> bool:
        return bool(self.label.strip())


class PageControl(BaseModel):
    """A button or link the page offers, identified by what it reads."""

    text: str = ""
    fingerprint: str = ""
    href: str = ""


class PageObservation(BaseModel):
    url: str = ""
    title: str = ""
    kind: PageKind = PageKind.UNKNOWN
    adapter: str = "generic"
    host_role: HostRole = HostRole.THIRD_PARTY
    fields: list[FieldObservation] = Field(default_factory=list)
    submit_controls: list[PageControl] = Field(default_factory=list)
    apply_controls: list[PageControl] = Field(default_factory=list)
    next_controls: list[PageControl] = Field(default_factory=list)
    add_controls: list[PageControl] = Field(default_factory=list)
    captcha: Literal["none", "badge_only", "challenge"] = "none"
    hints: list[str] = Field(default_factory=list)
    signature: str = ""
    observed_at: datetime = Field(default_factory=_now)
    notes: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    """A value the agent intends to put on the page, and where it came from."""

    fingerprint: str
    label: str
    value: str
    source: AnswerSource
    fact_key: str = ""
    confidence: float = 1.0
    reason: str = ""


class PlannedAction(BaseModel):
    kind: Literal["fill", "choose", "check", "upload", "click", "add_repeat"]
    fingerprint: str
    value: str = ""
    option_label: str = ""
    document_id: str = ""
    reason: str = ""


class ActionResult(BaseModel):
    """What actually happened, judged from a fresh read of page-owned state."""

    fingerprint: str
    label: str = ""
    requested: str = ""
    outcome: Outcome = Outcome.ATTEMPTED
    observed: str = ""
    signal: str = ""
    evidence: str = ""

    @property
    def is_success(self) -> bool:
        return self.outcome is Outcome.VERIFIED


class PendingQuestion(BaseModel):
    """Something only the applicant can answer."""

    fingerprint: str
    label: str
    control: ControlKind = ControlKind.UNKNOWN
    options: list[Option] = Field(default_factory=list)
    required: bool = True
    fact_key: str = ""
    reason: str = ""
    section: str = ""
    frame: str = ""
    #: What the profile holds for this question's fact, so the panel can rank
    #: the control's own options against it once they have been opened.
    saved_value: str = ""
    #: True when the control's options have not been read yet. They live behind
    #: a popup only that control owns, so they have to be opened before there is
    #: anything to show -- asking someone to type a dropdown answer is not it.
    options_pending: bool = False


class ChecklistItem(BaseModel):
    fingerprint: str
    label: str
    #: Which entry of a repeating block, when there is one. Three rows all
    #: labelled "GPA" with nothing to tell them apart is not a list anyone can
    #: act on.
    section: str = ""
    state: Literal["verified", "attempted", "needs_you", "skipped", "failed"] = "needs_you"
    value: str = ""
    detail: str = ""
    required: bool = False


class EducationRecord(BaseModel):
    id: str = ""
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""
    location: str = ""


class ExperienceRecord(BaseModel):
    id: str = ""
    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    current: bool = False
    description: str = ""


class Profile(BaseModel):
    facts: dict[str, str] = Field(default_factory=dict)
    education: list[EducationRecord] = Field(default_factory=list)
    experience: list[ExperienceRecord] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    answer_demographics: bool = False
    submission_policy: Literal["never", "confirm", "auto"] = "confirm"
    prefer_easy_apply: bool = False
    #: Work through a multi-step application without being asked to press
    #: Continue each time. Off by default; pressing final Submit is governed
    #: separately by submission_policy and is never implied by this.
    auto_advance: bool = False
    #: Attach the resume on file whenever a form asks for one. Attaching a
    #: document you uploaded yourself, to a form you are filling, is the whole
    #: point; it is a toggle because it is still an action on a page.
    auto_attach_resume: bool = True
    updated_at: datetime = Field(default_factory=_now)

    def fact(self, key: str) -> str:
        return (self.facts.get(key) or "").strip()


class LearnedAnswer(BaseModel):
    """A value the applicant typed themselves, keyed by the exact question."""

    question: str
    normalised: str
    value: str
    control: ControlKind = ControlKind.UNKNOWN
    host: str = ""
    times_seen: int = 1
    updated_at: datetime = Field(default_factory=_now)


class ApplicationRecord(BaseModel):
    id: str = ""
    company: str = ""
    role: str = ""
    url: str = ""
    route: str = ""
    status: Literal[
        "discovered", "filling", "needs_you", "ready_to_submit", "submitted", "abandoned", "failed"
    ] = "discovered"
    applied_on: date | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RunState(BaseModel):
    """The state machine's memory.

    ``no_progress_signatures`` persists here rather than in a local variable so
    a stall guard survives a stop and resume instead of resetting and looping.
    """

    run_id: str = ""
    phase: Literal[
        "idle", "routing", "scanning", "planning", "filling", "waiting_for_you",
        "advancing", "ready_to_submit", "done", "blocked"
    ] = "idle"
    url: str = ""
    company: str = ""
    role: str = ""
    step: int = 0
    attempts_on_step: int = 0
    seen_signatures: list[str] = Field(default_factory=list)
    no_progress_count: int = 0
    last_signature: str = ""
    message: str = ""
    updated_at: datetime = Field(default_factory=_now)
    results: list[ActionResult] = Field(default_factory=list)
    pending: list[PendingQuestion] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

"""The local service.

Bound to 127.0.0.1 and nowhere else. It owns the profile, the saved answers, the
history and the reasoning; the extension owns the browser. Nothing crosses that
line except typed observations one way and typed actions the other.

/health reports the running version. The panel compares it with the extension's
own and says so when they differ, because a service left running keeps serving
the code it started with, and chasing a bug that was already fixed on disk costs
an afternoon.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import (
    __version__,
    ai,
    applications,
    chat,
    documents,
    learning,
    linkedin,
    onboarding,
    resume,
    runloop,
)
from .adapters import classify_host
from .config import load_settings
from .facts import BY_KEY
from .mapper import describe_match
from .matching import rank_options, real_options
from .models import (
    ActionResult,
    ApplicationRecord,
    ChecklistItem,
    EducationRecord,
    ExperienceRecord,
    FieldObservation,
    Option,
    PageKind,
    PageObservation,
    PendingQuestion,
    PlannedAction,
    Profile,
    RunState,
)
from .routing import RouteCandidate, decide
from .session_credentials import SessionSignIn
from .store import Store
from .text import normalise

settings = load_settings()
store = Store(settings)
session_sign_in = SessionSignIn()

app = FastAPI(title="ApplyPilot", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://.*|http://(127\.0\.0\.1|localhost)(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _model() -> ai.Model:
    return ai.Model(
        api_key=store.get_value("model_api_key", "") or "",
        name=store.get_value("model_name", settings.model_name) or settings.model_name,
    )


# ---------------------------------------------------------------------------
# Health and settings
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    profile = store.get_profile()
    return {
        "ok": True,
        "version": __version__,
        "data_dir": str(settings.data_dir),
        "key_fingerprint": store.key_fingerprint,
        "model_configured": bool(store.get_value("model_api_key", "")),
        "profile_answered": len([v for v in profile.facts.values() if v]),
        "onboarding_complete": onboarding.build(profile).complete,
        "missing_for_applications": onboarding.missing_for_applications(profile),
        "documents": len(store.list_documents()),
        "applications": applications.summary(store),
    }


class SettingsPayload(BaseModel):
    model_api_key: str | None = None
    model_name: str | None = None
    submission_policy: str | None = None
    prefer_easy_apply: bool | None = None
    answer_demographics: bool | None = None
    auto_advance: bool | None = None
    auto_attach_resume: bool | None = None


@app.get("/settings")
def get_settings() -> dict[str, Any]:
    profile = store.get_profile()
    return {
        "model_configured": bool(store.get_value("model_api_key", "")),
        "model_name": store.get_value("model_name", settings.model_name),
        "submission_policy": profile.submission_policy,
        "prefer_easy_apply": profile.prefer_easy_apply,
        "answer_demographics": profile.answer_demographics,
        "auto_advance": profile.auto_advance,
        "auto_attach_resume": profile.auto_attach_resume,
        "authorised_sign_in_hosts": session_sign_in.authorised_hosts(),
    }


@app.put("/settings")
def put_settings(payload: SettingsPayload) -> dict[str, Any]:
    if payload.model_api_key is not None:
        # Encrypted at rest like everything else, and never echoed back.
        store.set_value("model_api_key", payload.model_api_key.strip())
    if payload.model_name:
        store.set_value("model_name", payload.model_name)

    profile = store.get_profile()
    if payload.submission_policy in {"never", "confirm", "auto"}:
        profile.submission_policy = payload.submission_policy  # type: ignore[assignment]
    if payload.prefer_easy_apply is not None:
        profile.prefer_easy_apply = payload.prefer_easy_apply
    if payload.answer_demographics is not None:
        profile.answer_demographics = payload.answer_demographics
    if payload.auto_advance is not None:
        profile.auto_advance = payload.auto_advance
    if payload.auto_attach_resume is not None:
        profile.auto_attach_resume = payload.auto_attach_resume
    store.save_profile(profile)
    return get_settings()


# ---------------------------------------------------------------------------
# Profile and onboarding
# ---------------------------------------------------------------------------


@app.get("/profile")
def get_profile() -> Profile:
    return store.get_profile()


@app.put("/profile")
def put_profile(profile: Profile) -> Profile:
    return store.save_profile(profile)


@app.get("/onboarding")
def get_onboarding() -> dict[str, Any]:
    built = onboarding.build(store.get_profile())
    return {
        "steps": [step.__dict__ for step in built.steps],
        "answered": built.answered,
        "total": built.total,
        "complete": built.complete,
        "required_remaining": built.required_remaining,
        "notes": built.notes,
        "next": built.next_step.__dict__ if built.next_step else None,
    }


class FactAnswer(BaseModel):
    fact_key: str
    value: str = ""
    entry: int = 0


@app.post("/profile/fact")
def save_fact(payload: FactAnswer) -> dict[str, Any]:
    """Save one answer, into the right place.

    A history key such as ``education.gpa`` belongs in an education record, not
    in the flat set of facts -- writing it flat meant answering it once did not
    stop it being asked again.
    """
    profile = store.get_profile()
    spec = BY_KEY.get(payload.fact_key)
    if spec is None:
        raise HTTPException(400, f"no such fact: {payload.fact_key}")

    if spec.record:
        records = profile.education if spec.record == "education" else profile.experience
        while len(records) <= payload.entry:
            records.append(
                EducationRecord() if spec.record == "education" else ExperienceRecord()
            )
        record = records[payload.entry]
        current = getattr(record, spec.record_field, "")
        if isinstance(current, bool):
            setattr(record, spec.record_field, payload.value.strip().lower() in {"yes", "true"})
        else:
            setattr(record, spec.record_field, payload.value.strip())
    elif payload.value.strip():
        profile.facts[payload.fact_key] = payload.value.strip()
    else:
        profile.facts.pop(payload.fact_key, None)

    store.save_profile(profile)
    return {"ok": True, "fact_key": payload.fact_key, "entry": payload.entry}


class OnboardingAnswer(BaseModel):
    key: str
    value: str = ""


@app.post("/onboarding/answer")
def post_onboarding_answer(payload: OnboardingAnswer) -> dict[str, Any]:
    profile = onboarding.answer(store.get_profile(), payload.key, payload.value)
    store.save_profile(profile)
    return get_onboarding()


@app.post("/resume")
async def upload_resume(file: UploadFile) -> dict[str, Any]:
    data = await file.read()
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "Upload a .docx resume; other formats are not read yet.")
    try:
        extracted = resume.extract(data)
    except Exception as exc:  # noqa: BLE001 - report the real reason to the panel
        raise HTTPException(400, f"That file could not be read: {exc}") from exc

    profile, added = onboarding.apply_resume(store.get_profile(), extracted)
    store.save_profile(profile)
    stored = store.add_document("resume", file.filename or "resume.docx", data)
    store.set_value("primary_resume_id", stored["id"])

    return {
        "document": stored,
        "added": added,
        "notes": extracted.notes,
        "education": [record.model_dump() for record in extracted.education],
        "experience": [record.model_dump() for record in extracted.experience],
        "skills": extracted.skills,
        "onboarding": get_onboarding(),
    }


@app.post("/import/linkedin")
async def import_linkedin(file: UploadFile) -> dict[str, Any]:
    """Import LinkedIn's own data export.

    This reads the archive LinkedIn sends when you ask for a copy of your data.
    It does not sign in to LinkedIn and it does not read any page: signing in
    with LinkedIn returns a name, an email and a picture and nothing else, and
    reading a profile page is against their terms.
    """
    data = await file.read()
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(
            400,
            "Upload the .zip LinkedIn emails you. Get it from Settings and Privacy "
            "-> Data privacy -> Get a copy of your data.",
        )
    try:
        extracted = linkedin.extract(data)
    except linkedin.NotALinkedInExport as exc:
        raise HTTPException(400, str(exc)) from exc

    profile, added = onboarding.apply_resume(store.get_profile(), extracted)
    store.save_profile(profile)
    return {
        "added": added,
        "notes": extracted.notes,
        "education": [record.model_dump() for record in extracted.education],
        "experience": [record.model_dump() for record in extracted.experience],
        "skills": extracted.skills,
        "onboarding": get_onboarding(),
    }


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@app.get("/documents")
def list_documents() -> dict[str, Any]:
    return {
        "documents": store.list_documents(),
        "primary_resume_id": store.get_value("primary_resume_id", ""),
    }


class TailorRequest(BaseModel):
    job_title: str = ""
    company: str = ""
    job_description: str = ""


@app.post("/documents/tailored-resume")
def tailored_resume(payload: TailorRequest) -> dict[str, Any]:
    profile = store.get_profile()
    if not profile.experience and not profile.education:
        raise HTTPException(
            400,
            "There is nothing in your profile to build a resume from yet. "
            "Upload your resume or add your history first.",
        )
    built = documents.build_resume(
        profile, payload.job_description, payload.job_title, payload.company
    )
    stored = store.add_document("tailored_resume", built.filename, built.data)
    return {
        "document": stored,
        "ordering": built.ordering,
        "highlighted_skills": built.highlighted_skills,
        "notes": built.notes,
    }


@app.get("/documents/{document_id}/content")
def document_content(document_id: str) -> dict[str, str]:
    """The bytes of a stored document, for the service worker to attach.

    Base64 because it travels through a message to the extension, which builds
    the File itself. The page is never handed a way to reach this service.
    """
    import base64

    found = store.read_document(document_id)
    if found is None:
        raise HTTPException(404, "no such document")
    filename, data = found
    return {
        "filename": filename,
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if filename.lower().endswith(".docx")
        else "application/octet-stream",
        "base64": base64.b64encode(data).decode("ascii"),
    }


@app.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, bool]:
    store.delete_document(document_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Planning a page
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    kind: PageKind
    adapter: str
    host_role: str
    host_reason: str
    actions: list[PlannedAction] = Field(default_factory=list)
    questions: list[PendingQuestion] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    needs_options: list[str] = Field(default_factory=list)
    narration: str = ""
    notes: list[str] = Field(default_factory=list)
    version: str = __version__


@app.post("/plan", response_model=PlanResponse)
def plan(observation: PageObservation, after_continue: bool = False) -> PlanResponse:
    profile = store.get_profile()
    identity = classify_host(observation.url, hints=observation.hints)

    state = store.get_run()
    if after_continue:
        # Only an attempt to move the page on can stall. Filling a page means
        # planning it several times over by design -- the page is re-read after
        # every choice and again on each correction pass -- and counting those
        # as failures to progress declared every page stuck on the third look,
        # which is how a run reached a new step and then refused to touch it.
        runloop.note_observation(state, observation.signature)
        store.save_run(state)

    built = runloop.plan_page(observation, profile, store.learned_values())
    notes = list(observation.notes) + built.notes

    if runloop.is_stalled(state):
        notes.append(
            "This page has not changed after several attempts, so I have stopped "
            "rather than keep trying the same thing."
        )
    if observation.captcha == "badge_only":
        notes.append("There is a reCAPTCHA badge here. It needs nothing from anyone.")

    missing = onboarding.missing_for_applications(profile)
    if missing and observation.kind is PageKind.APPLICATION:
        notes.append("Still missing from your profile: " + ", ".join(missing[:5]))

    return PlanResponse(
        kind=observation.kind,
        adapter=identity.adapter,
        host_role=identity.role.value,
        host_reason=identity.reason,
        actions=built.actions,
        questions=built.questions,
        checklist=runloop.build_checklist(observation, built, []),
        needs_options=built.needs_options,
        narration=_narrate(observation, built),
        notes=notes,
    )


def _narrate(observation: PageObservation, built: runloop.Plan) -> str:
    if observation.kind is PageKind.APPLICATION:
        parts = [f"I can see {len(observation.fields)} fields on this application."]
        if built.actions:
            parts.append(f"I am filling {len(built.actions)} of them from what you have saved.")
        if built.questions:
            parts.append(f"{len(built.questions)} need you.")
        if built.skipped:
            parts.append(f"{len(built.skipped)} are optional extras I am leaving blank.")
        return " ".join(parts)
    if observation.kind in {PageKind.SEARCH, PageKind.BOARD}:
        return "This is a list of jobs, not an application, so there is nothing here to fill in."
    if observation.kind is PageKind.SIGN_IN:
        return "This is a sign-in page. Sign in in the browser and I will carry on."
    if observation.kind is PageKind.REGISTRATION:
        return (
            "This page wants an account. I will fill everything except the password -- "
            "creating the account accepts their terms, so that part is yours."
        )
    if observation.kind is PageKind.CONFIRMATION:
        return "The page says the application was received."
    return f"This looks like a {observation.kind.value} page."


class ResultsPayload(BaseModel):
    observation: PageObservation
    results: list[ActionResult] = Field(default_factory=list)


@app.post("/results")
def post_results(payload: ResultsPayload) -> dict[str, Any]:
    """Take what actually happened and record it, honestly."""
    profile = store.get_profile()
    built = runloop.plan_page(payload.observation, profile, store.learned_values())
    merged = runloop.merge_all(payload.results)

    state = store.get_run()
    state.results = merged
    state.pending = built.questions
    state.checklist = runloop.build_checklist(payload.observation, built, merged)
    state.phase = runloop.next_phase(state, payload.observation, built, merged)  # type: ignore[assignment]
    state.message = runloop.summarise(merged, built.questions)
    store.save_run(state)

    return {
        "summary": state.message,
        "phase": state.phase,
        "checklist": [item.model_dump() for item in state.checklist],
        "unverified": [
            {"label": r.label, "requested": r.requested, "evidence": r.evidence}
            for r in merged
            if r.outcome.value in {"attempted", "accepted"}
        ],
        "failed": [
            {"label": r.label, "requested": r.requested, "evidence": r.evidence}
            for r in merged
            if r.outcome.value == "failed"
        ],
    }


class OptionsPayload(BaseModel):
    fingerprint: str
    label: str = ""
    saved_value: str = ""
    fact_key: str = ""
    options: list[Option] = Field(default_factory=list)
    source: str = "owned_popup"


@app.post("/options")
async def rank_page_options(payload: OptionsPayload) -> dict[str, Any]:
    """Rank the options a control actually opened.

    Only options that came from the control's own popup arrive here; an empty
    list means the control has none, and that is reported as such rather than
    turned into a question with invented answers.
    """
    if payload.source == "none" or not payload.options:
        return {
            "chosen": None,
            "options": [],
            "note": "this control opened no list of its own, so I cannot tell you what it offers",
        }
    if payload.source not in {"owned_popup", "native"}:
        return {
            "chosen": None,
            "options": [],
            "note": "these options did not come from a list the control owns, so they are ignored",
        }

    offered = real_options(payload.options)
    if not offered:
        return {
            "chosen": None,
            "options": [],
            "note": "this dropdown has nothing to choose from yet -- it may depend on "
                    "another field being filled in first",
        }
    ranked = rank_options(payload.saved_value, payload.options, payload.fact_key)
    chosen = ranked[0] if ranked else None
    ambiguous = len(ranked) > 1 and ranked[1].score == ranked[0].score

    if chosen is not None and not ambiguous and chosen.score >= 400:
        return {
            "chosen": chosen.option.label,
            "why": chosen.reason,
            "options": [o.model_dump() for o in offered],
        }

    note = "none of the options is close enough to your saved answer"
    if ambiguous:
        note = "two options fit equally well, so this is yours to pick"
    if not payload.saved_value:
        note = "nothing saved answers this"
    return {"chosen": None, "note": note, "options": [o.model_dump() for o in offered]}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class RoutePayload(BaseModel):
    url: str
    kind: PageKind = PageKind.UNKNOWN
    company: str = ""
    title: str = ""
    hints: list[str] = Field(default_factory=list)
    candidates: list[dict[str, str]] = Field(default_factory=list)


@app.post("/route")
def route(payload: RoutePayload) -> dict[str, Any]:
    profile = store.get_profile()
    candidates = [
        RouteCandidate(
            url=c.get("url", ""),
            source=c.get("source", "constructed"),
            company=c.get("company", ""),
            title=c.get("title", ""),
            label=c.get("label", ""),
        )
        for c in payload.candidates
        if c.get("url")
    ]
    decision = decide(
        payload.url,
        payload.kind,
        expected_company=payload.company,
        expected_title=payload.title,
        candidates=candidates,
        hints=payload.hints,
        prefer_easy_apply=profile.prefer_easy_apply,
    )
    return {
        "action": decision.action,
        "url": decision.url,
        "message": decision.message,
        "host": decision.identity.host if decision.identity else "",
        "host_role": decision.identity.role.value if decision.identity else "",
        "adapter": decision.identity.adapter if decision.identity else "generic",
        "considered": [
            {"url": c.url, "score": c.score, "reason": c.reason, "source": c.source}
            for c in decision.candidates
        ],
    }


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatPayload(BaseModel):
    text: str
    fields: list[FieldObservation] = Field(default_factory=list)
    last_fingerprint: str = ""
    pending_fingerprint: str = ""


@app.post("/chat")
def post_chat(payload: ChatPayload) -> dict[str, Any]:
    profile = store.get_profile()
    outcome = chat.interpret(
        payload.text,
        payload.fields,
        profile=profile,
        last_fingerprint=payload.last_fingerprint,
        pending_fingerprint=payload.pending_fingerprint,
    )

    # An instruction that names a fact is worth keeping, whether or not this
    # page happened to ask for it.
    if outcome.remember and outcome.fact_key and outcome.value:
        profile.facts[outcome.fact_key] = outcome.value
        store.save_profile(profile)

    return {
        "kind": outcome.kind,
        "message": outcome.message,
        "action": outcome.action.model_dump() if outcome.action else None,
        "fingerprint": outcome.fingerprint,
        "label": outcome.label,
        "value": outcome.value,
        "fact_key": outcome.fact_key,
        "options": [o.model_dump() for o in outcome.options],
    }


class SuggestPayload(BaseModel):
    label: str
    options: list[Option] = Field(default_factory=list)
    saved_value: str = ""
    fact_key: str = ""
    source: str = "owned_popup"


@app.post("/suggest")
async def suggest(payload: SuggestPayload) -> dict[str, Any]:
    """Suggest one of the page's own options for a question nothing answers.

    Matching gets first refusal. Only when that finds nothing is the model asked,
    and it is asked to pick from a list scraped off the page -- then its answer
    is checked against that same list before it is offered. A suggestion is
    shown as a suggestion; it is never filled in without being accepted.
    """
    if not payload.options:
        return {"suggested": None, "why": "this control has no options to choose between"}

    if payload.saved_value:
        ranked = rank_options(payload.saved_value, payload.options, payload.fact_key)
        if ranked and ranked[0].score >= 400:
            return {
                "suggested": ranked[0].option.label,
                "why": f"your saved answer, {ranked[0].reason}",
                "from": "profile",
            }

    model = _model()
    if not model.available:
        return {
            "suggested": None,
            "why": "nothing saved answers this, and there is no model key set",
            "kind": "model_unavailable",
        }
    try:
        chosen, why = await ai.choose_among(
            model, payload.label, payload.options, payload.saved_value
        )
    except ai.ModelUnavailable as exc:
        # Flagged so the panel keeps it out of the question card: a busy model
        # is not something the applicant needs to read while answering.
        return {"suggested": None, "why": str(exc), "kind": "model_unavailable"}
    if chosen is None:
        return {"suggested": None, "why": why}
    return {"suggested": chosen.label, "why": why, "from": "model"}


class DescribePayload(BaseModel):
    observation: PageObservation


@app.post("/describe")
async def describe(payload: DescribePayload) -> dict[str, str]:
    """Words for the panel. The model never decides anything here."""
    model = _model()
    if not model.available:
        return {"text": "", "note": "no model key is set, so this is running on matching alone"}
    try:
        return {"text": await ai.describe_page(model, payload.observation)}
    except ai.ModelUnavailable as exc:
        return {"text": "", "note": str(exc)}


# ---------------------------------------------------------------------------
# Learned answers
# ---------------------------------------------------------------------------


class LearnPayload(BaseModel):
    field: FieldObservation
    value: str
    host: str = ""
    page_labels: list[str] = Field(default_factory=list)


@app.post("/learn")
def learn(payload: LearnPayload) -> dict[str, Any]:
    profile = store.get_profile()
    decision = learning.judge(
        payload.field,
        payload.value,
        page_labels=frozenset(normalise(label) for label in payload.page_labels),
        allow_demographics=profile.answer_demographics,
    )
    if not decision.learn:
        return {"learned": False, "reason": decision.reason}
    saved = store.save_learned(learning.build(payload.field, payload.value, payload.host))
    return {"learned": True, "reason": decision.reason, "question": saved.question}


@app.get("/learned")
def get_learned() -> dict[str, Any]:
    return {
        "answers": [
            {
                "question": answer.question,
                "value": answer.value,
                "host": answer.host,
                "times_seen": answer.times_seen,
                "updated_at": answer.updated_at.isoformat(timespec="seconds"),
            }
            for answer in sorted(
                store.get_learned().values(), key=lambda a: a.updated_at, reverse=True
            )
        ]
    }


@app.delete("/learned")
def delete_learned(question: str = "") -> dict[str, Any]:
    if question:
        store.forget_learned(question)
        return {"forgotten": 1}
    return {"forgotten": store.forget_all_learned()}


@app.post("/explain")
def explain(field: FieldObservation) -> dict[str, str]:
    """Why a field resolved the way it did. For the panel and for debugging."""
    return {"label": field.display_label, "explanation": describe_match(field)}


# ---------------------------------------------------------------------------
# Run state
# ---------------------------------------------------------------------------


@app.get("/run")
def get_run() -> RunState:
    return store.get_run()


class RunCommand(BaseModel):
    command: str
    url: str = ""
    company: str = ""
    role: str = ""


@app.post("/run")
def post_run(payload: RunCommand) -> RunState:
    state = store.get_run()
    if payload.command == "start":
        state.phase = "scanning"
        state.url = payload.url or state.url
        state.company = payload.company or state.company
        state.role = payload.role or state.role
        state.message = "Starting."
        state = runloop.clear_stall(state)
    elif payload.command == "resume":
        state = runloop.resume(state)
    elif payload.command == "stop":
        state.phase = "idle"
        state.message = "Stopped."
    elif payload.command == "unblock":
        state = runloop.clear_stall(state)
    else:
        raise HTTPException(400, f"unknown command {payload.command!r}")
    return store.save_run(state)


# ---------------------------------------------------------------------------
# Sign-in authorisation (this service never holds the details themselves)
# ---------------------------------------------------------------------------


class SignInHost(BaseModel):
    host: str


@app.post("/sign-in/authorise")
def authorise_sign_in(payload: SignInHost) -> dict[str, Any]:
    authorisation = session_sign_in.authorise(payload.host)
    return {
        "host": authorisation.host,
        "expires_in": 15 * 60,
        "note": (
            "Your sign-in details stay in the panel and are never sent here or written "
            "to disk. This only records that you allowed this one host."
        ),
    }


@app.delete("/sign-in/authorise")
def revoke_sign_in(host: str = "") -> dict[str, Any]:
    session_sign_in.revoke(host)
    return {"authorised": session_sign_in.authorised_hosts()}


class SignInCheck(BaseModel):
    url: str
    kind: PageKind


@app.post("/sign-in/check")
def check_sign_in(payload: SignInCheck) -> dict[str, Any]:
    decision = session_sign_in.may_release(payload.url, payload.kind)
    return {"allowed": decision.allowed, "reason": decision.reason}


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@app.get("/applications")
def list_applications() -> dict[str, Any]:
    return {
        "applications": [record.model_dump(mode="json") for record in store.list_applications()],
        "summary": applications.summary(store),
    }


@app.post("/applications")
def upsert_application(record: ApplicationRecord) -> ApplicationRecord:
    return store.upsert_application(record)


class SubmitPayload(BaseModel):
    application_id: str
    confirmation: str = ""


@app.post("/applications/submitted")
def mark_application_submitted(payload: SubmitPayload) -> dict[str, Any]:
    record = next(
        (r for r in store.list_applications() if r.id == payload.application_id), None
    )
    if record is None:
        raise HTTPException(404, "no such application")
    updated, message = applications.mark_submitted(store, record, payload.confirmation)
    return {"application": updated.model_dump(mode="json"), "message": message}


@app.get("/applications/export", response_class=PlainTextResponse)
def export_applications() -> str:
    return applications.export_csv(store)


@app.delete("/applications/{application_id}")
def delete_application(application_id: str) -> dict[str, bool]:
    store.delete_application(application_id)
    return {"ok": True}


@app.post("/reset")
def reset(confirm: str = Body("", embed=True)) -> dict[str, Any]:
    """Clear everything local. Deliberately awkward to trigger by accident."""
    if confirm != "erase everything":
        raise HTTPException(400, 'send {"confirm": "erase everything"} to do this')
    store.delete_value("profile")
    store.delete_value("run_state")
    forgotten = store.forget_all_learned()
    for document in store.list_documents():
        store.delete_document(document["id"])
    return {"ok": True, "forgotten_answers": forgotten}

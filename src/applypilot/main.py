from __future__ import annotations

import csv
import io
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .ai import AIProviderError, AIProviderManager
from .applications import (
    InvalidApplicationTransition,
    create_application,
    transition_application,
)
from .company_route import resolve_company_application_url, safe_public_url
from .config import settings
from .documents import (
    artifact_filename,
    build_cover_letter_docx,
    build_docx,
    build_pdf,
    build_reconstructed_resume_docx,
)
from .form_mapper import (
    coerce_option,
    map_exact_reusable_answer,
    map_profile_field,
    map_source_field,
    normalize,
    plan_form_fill,
    resume_mentions_option,
)
from .models import (
    ApplicationAnswerDraft,
    ApplicationAnswerRefineRequest,
    ApplicationCreate,
    ApplicationQuestionDraftRequest,
    ApplicationRecord,
    ApplicationRouteDecision,
    ApplicationTransition,
    CandidateProfile,
    ChatRequest,
    ChatResponse,
    CompanyRouteRequest,
    CompanyRouteResult,
    CoverLetterDocument,
    FormAgentDecision,
    FormAgentRequest,
    FormField,
    FormFillPlan,
    FormPlanRequest,
    GeneratedCoverLetter,
    JobApplicationOptions,
    JobContext,
    JobFitAnalysis,
    JobPreparation,
    OnboardingState,
    PageActionDecision,
    PageActionRequest,
    PageUnderstanding,
    PageUnderstandingRequest,
    ProviderConfigRequest,
    ProviderStatus,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredArtifact,
    TailoredArtifactRequest,
    TailoredResume,
    TailorRequest,
)
from .onboarding import get_onboarding_state
from .resume import ResumeExtractionError, extract_resume
from .routing import choose_application_route
from .store import ProfileStore

store = ProfileStore(settings.database_path)
ai_provider = AIProviderManager(store, settings)
web_directory = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.demo_mode:
        store.initialize()
        prune_canonical_reusable_answers(store)
    yield


app = FastAPI(title="ApplyPilot Agent", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension|moz-extension)://.*$",
    allow_credentials=False,
    allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.mount("/assets", StaticFiles(directory=web_directory), name="assets")


def require_local_data_mode() -> None:
    if settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="The public demo does not store candidate data. Use the local agent.",
        )


def prune_canonical_reusable_answers(profile_store: ProfileStore) -> int:
    """Remove page-answer copies of canonical profile fields.

    Canonical facts are edited in the candidate profile. Keeping a second copy
    in reusable answers creates two competing truths and made one bad model
    mapping persist across later applications.
    """
    profile = profile_store.load()
    removed = 0
    for answer in profile_store.list_answers():
        label = normalize(answer.question)
        field_type = (
            "checkbox"
            if "background check" in label
            else "radio"
            if any(token in label for token in ("authorized to work", "sponsor", "relocate", "travel"))
            else "text"
        )
        field = FormField(id=answer.id, label=answer.question, field_type=field_type)
        if map_profile_field(label, field, profile) is not None:
            removed += int(profile_store.delete_answer(answer.id))
    return removed


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(web_directory / "index.html")


@app.get("/demo/ats", include_in_schema=False)
def synthetic_ats() -> FileResponse:
    return FileResponse(web_directory / "synthetic-ats.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "applypilot",
        "mode": "demo" if settings.demo_mode else "local",
        "version": __version__,
        "revision": os.getenv("RENDER_GIT_COMMIT", "local")[:7],
    }


@app.get("/api/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "mode": "demo" if settings.demo_mode else "local",
        "stores_candidate_data": not settings.demo_mode,
        "company_site_first": True,
        "live_site_automation": not settings.demo_mode,
        "resume_tailoring": ai_provider.configured and not settings.demo_mode,
        "job_fit_analysis": ai_provider.configured and not settings.demo_mode,
        "model_form_agent": ai_provider.configured and not settings.demo_mode,
        "hybrid_reasoning": ai_provider.hybrid_reasoning_enabled and not settings.demo_mode,
        "deterministic_autofill": not settings.demo_mode,
        "editable_reusable_profile": not settings.demo_mode,
        "automation_policies": ["review_each", "always_allow"],
        "supported_adapters": ["linkedin", "greenhouse", "lever", "workday", "generic"],
        "review_before_submit": True,
    }


@app.get("/api/provider", response_model=ProviderStatus)
def provider_status() -> ProviderStatus:
    return ai_provider.status()


@app.put("/api/provider", response_model=ProviderStatus)
def configure_provider(config: ProviderConfigRequest) -> ProviderStatus:
    require_local_data_mode()
    return ai_provider.configure(config)


@app.delete("/api/provider", response_model=ProviderStatus)
def disconnect_provider() -> ProviderStatus:
    require_local_data_mode()
    return ai_provider.disconnect()


@app.get("/api/provider/reasoning", response_model=ProviderStatus)
def reasoning_provider_status() -> ProviderStatus:
    return ai_provider.reasoning_status()


@app.put("/api/provider/reasoning", response_model=ProviderStatus)
def configure_reasoning_provider(config: ProviderConfigRequest) -> ProviderStatus:
    require_local_data_mode()
    try:
        return ai_provider.configure_reasoning(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.delete("/api/provider/reasoning", response_model=ProviderStatus)
def disconnect_reasoning_provider() -> ProviderStatus:
    require_local_data_mode()
    return ai_provider.disconnect_reasoning()


@app.get("/api/profile", response_model=CandidateProfile)
def get_profile() -> CandidateProfile:
    require_local_data_mode()
    return store.load()


@app.put("/api/profile", response_model=CandidateProfile)
def put_profile(profile: CandidateProfile) -> CandidateProfile:
    require_local_data_mode()
    return store.save(profile)


@app.get("/api/onboarding", response_model=OnboardingState)
def onboarding() -> OnboardingState:
    require_local_data_mode()
    return get_onboarding_state(store.load())


@app.get("/api/answers", response_model=list[ReusableAnswer])
def list_answers() -> list[ReusableAnswer]:
    require_local_data_mode()
    return store.list_answers()


@app.put("/api/answers/{answer_id}", response_model=ReusableAnswer)
def put_answer(answer_id: str, answer: ReusableAnswer) -> ReusableAnswer:
    require_local_data_mode()
    if answer.id != answer_id:
        raise HTTPException(status_code=400, detail="Answer ID does not match the URL")
    return store.save_answer(answer)


@app.delete("/api/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer(answer_id: str) -> Response:
    require_local_data_mode()
    if not store.delete_answer(answer_id):
        raise HTTPException(status_code=404, detail="Answer not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/resumes", response_model=ResumeDocument)
async def upload_resume(file: UploadFile = File(...)) -> ResumeDocument:
    require_local_data_mode()
    content = await file.read()
    try:
        resume = extract_resume(
            filename=file.filename or "resume",
            content=content,
            media_type=file.content_type or "",
        )
    except ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved = store.save_resume(resume)
    store.save_resume_file(resume.sha256, content)
    return saved


@app.get("/api/resumes", response_model=list[ResumeDocument])
def list_resumes() -> list[ResumeDocument]:
    require_local_data_mode()
    return store.list_resumes()


@app.get("/api/resumes/active", response_model=ResumeDocument)
def active_resume() -> ResumeDocument:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume has been uploaded")
    return resume


@app.get("/api/resumes/active/file")
def active_resume_file() -> Response:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume has been uploaded")
    content = store.get_resume_file(resume.sha256)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail="Re-upload this resume once to enable original-file attachment",
        )
    safe_name = resume.filename.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type=resume.media_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/api/resumes/active/file-status")
def active_resume_file_status() -> dict[str, str | bool]:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume has been uploaded")
    return {
        "available": store.get_resume_file(resume.sha256) is not None,
        "filename": resume.filename,
    }


@app.get("/api/resumes/active/reconstructed.docx")
def reconstructed_active_resume() -> Response:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume has been uploaded")
    stem = Path(resume.filename).stem or "resume"
    filename = f"{stem}-reconstructed.docx".replace('"', "")
    return Response(
        content=build_reconstructed_resume_docx(resume),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/cover-letters", response_model=CoverLetterDocument)
async def upload_cover_letter(file: UploadFile = File(...)) -> CoverLetterDocument:
    require_local_data_mode()
    content = await file.read()
    try:
        extracted = extract_resume(
            filename=file.filename or "cover-letter",
            content=content,
            media_type=file.content_type or "",
        )
    except ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    document = CoverLetterDocument(**extracted.model_dump(exclude={"id", "uploaded_at"}))
    saved = store.save_cover_letter(document)
    store.save_cover_letter_file(document.sha256, content)
    return saved


@app.get("/api/cover-letters/active", response_model=CoverLetterDocument)
def active_cover_letter() -> CoverLetterDocument:
    require_local_data_mode()
    document = store.get_active_cover_letter()
    if document is None:
        raise HTTPException(status_code=404, detail="No cover letter has been uploaded")
    return document


@app.get("/api/cover-letters/active/file")
def active_cover_letter_file() -> Response:
    require_local_data_mode()
    document = store.get_active_cover_letter()
    if document is None:
        raise HTTPException(status_code=404, detail="No cover letter has been uploaded")
    content = store.get_cover_letter_file(document.sha256)
    if content is None:
        raise HTTPException(status_code=404, detail="Re-upload this cover letter to attach it")
    safe_name = document.filename.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type=document.media_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.post("/api/cover-letters/generate", response_model=GeneratedCoverLetter)
def generate_cover_letter(request: TailorRequest) -> GeneratedCoverLetter:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="Upload a resume before generating a cover letter")
    try:
        draft = ai_provider.draft_cover_letter(store.load(), resume, request.job)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return store.save_generated_cover_letter(
        GeneratedCoverLetter(
            job_title=request.job.title,
            company=request.job.company,
            body=draft.body,
        )
    )


@app.get("/api/cover-letters/generated/{document_id}.docx")
def generated_cover_letter_file(document_id: str) -> Response:
    require_local_data_mode()
    document = store.get_generated_cover_letter(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Generated cover letter not found")
    job = JobContext(
        title=document.job_title,
        company=document.company,
        description="Generated cover-letter artifact",
    )
    company = re.sub(r"[^a-z0-9]+", "-", document.company.lower()).strip("-")
    filename = f"{company}-cover-letter" if company else "cover-letter"
    return Response(
        content=build_cover_letter_docx(document, store.load(), job),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}.docx"'},
    )


@app.post("/api/resumes/evidence", response_model=ResumeEvidence)
def extract_active_resume_evidence() -> ResumeEvidence:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume has been uploaded")
    try:
        return ai_provider.extract_evidence(resume)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/tailor", response_model=TailoredResume)
def tailor_resume(request: TailorRequest) -> TailoredResume:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="Upload a resume before tailoring")
    try:
        return ai_provider.tailor_resume(resume, request.job)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/jobs/analyze", response_model=JobFitAnalysis)
def analyze_job(request: TailorRequest) -> JobFitAnalysis:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="Upload a resume before analyzing job fit")
    try:
        return ai_provider.analyze_job(resume, request.job)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/jobs/prepare", response_model=JobPreparation)
def prepare_job(request: TailoredArtifactRequest) -> JobPreparation:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="Upload a resume before preparing a job")
    if request.application_id and store.get_application(request.application_id) is None:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        evidence = ai_provider.extract_evidence(resume)
        analysis = ai_provider.analyze_job(resume, request.job, evidence)
        tailored = ai_provider.tailor_resume(resume, request.job, evidence)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    artifact = store.save_tailored_artifact(
        TailoredArtifact(application_id=request.application_id, tailored=tailored)
    )
    return JobPreparation(analysis=analysis, artifact=artifact)


@app.post("/api/tailored", response_model=TailoredArtifact)
def create_tailored_artifact(request: TailoredArtifactRequest) -> TailoredArtifact:
    require_local_data_mode()
    resume = store.get_active_resume()
    if resume is None:
        raise HTTPException(status_code=404, detail="Upload a resume before tailoring")
    if request.application_id and store.get_application(request.application_id) is None:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        tailored = ai_provider.tailor_resume(resume, request.job)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return store.save_tailored_artifact(
        TailoredArtifact(application_id=request.application_id, tailored=tailored)
    )


def load_artifact(artifact_id: str) -> TailoredArtifact:
    artifact = store.get_tailored_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    return artifact


@app.get("/api/tailored/{artifact_id}.docx")
def download_tailored_docx(artifact_id: str) -> Response:
    require_local_data_mode()
    artifact = load_artifact(artifact_id)
    filename = artifact_filename(store.load(), "docx")
    return Response(
        content=build_docx(artifact, store.load()),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/tailored/{artifact_id}.pdf")
def download_tailored_pdf(artifact_id: str) -> Response:
    require_local_data_mode()
    artifact = load_artifact(artifact_id)
    filename = artifact_filename(store.load(), "pdf")
    return Response(
        content=build_pdf(artifact, store.load()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    require_local_data_mode()
    try:
        return ai_provider.chat(
            message=request.message,
            profile=store.load(),
            answers=store.list_answers(),
            resume=store.get_active_resume(),
            job=request.job,
            images=request.images,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/page-action", response_model=PageActionDecision)
def page_action(request: PageActionRequest) -> PageActionDecision:
    require_local_data_mode()
    try:
        decision = ai_provider.plan_page_action(request)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    allowed = {control.id for control in request.controls if not control.disabled}
    if decision.intent == "click" and decision.action_id not in allowed:
        raise HTTPException(status_code=422, detail="AI selected an unavailable page control")
    return decision


@app.post("/api/questions/draft", response_model=ApplicationAnswerDraft)
def draft_application_answer(request: ApplicationQuestionDraftRequest) -> ApplicationAnswerDraft:
    require_local_data_mode()
    try:
        return ai_provider.draft_application_answer(
            question=request.question,
            profile=store.load(),
            resume=store.get_active_resume(),
            job=request.job,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/questions/refine", response_model=ApplicationAnswerDraft)
def refine_application_answer(
    request: ApplicationAnswerRefineRequest,
) -> ApplicationAnswerDraft:
    require_local_data_mode()
    try:
        return ai_provider.refine_application_answer(
            question=request.question,
            user_answer=request.user_answer,
            profile=store.load(),
            resume=store.get_active_resume(),
            job=request.job,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/application-route", response_model=ApplicationRouteDecision)
def application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    return choose_application_route(options)


@app.post("/api/company-route", response_model=CompanyRouteResult)
def company_route(request: CompanyRouteRequest) -> CompanyRouteResult:
    """Find the employer's own application page for a job seen on a board.

    Used when a listing offers only Easy Apply: the employer almost always
    still posts the role on their own ATS, and applying there is preferred.
    Only a verified recognised-ATS URL is returned.
    """
    require_local_data_mode()

    def fetch(url: str) -> tuple[int, str]:
        if not safe_public_url(url):
            raise ValueError("Refusing to fetch a non-public URL.")
        response = httpx.get(
            url,
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "ApplyPilot/1.0 (+local job application agent)"},
        )
        return response.status_code, response.text

    resolved = resolve_company_application_url(request.company, request.title, fetch)
    if resolved is None:
        return CompanyRouteResult(found=False)
    return CompanyRouteResult(
        found=True,
        url=resolved.url,
        board_url=resolved.board_url,
        matched_title=resolved.matched_title,
        confidence=resolved.confidence,
    )


@app.post("/api/forms/plan", response_model=FormFillPlan)
def form_plan(request: FormPlanRequest) -> FormFillPlan:
    require_local_data_mode()
    resume = store.get_active_resume()
    return plan_form_fill(
        page_url=request.page_url,
        source_url=request.source_url,
        fields=request.fields,
        profile=store.load(),
        answers=store.list_answers(),
        resume_text=resume.extracted_text if resume else "",
        adapter=request.adapter,
    )


@app.post("/api/pages/understand", response_model=PageUnderstanding)
def understand_page(request: PageUnderstandingRequest) -> PageUnderstanding:
    """Classify the current page so the runner can stop instead of blundering on."""
    require_local_data_mode()
    try:
        return ai_provider.understand_page(request)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/forms/agent-plan", response_model=FormAgentDecision)
def form_agent_plan(request: FormAgentRequest) -> FormAgentDecision:
    require_local_data_mode()
    try:
        decision = ai_provider.plan_form_actions(request)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    profile = store.load()
    answers = store.list_answers()
    resume = store.get_active_resume()
    fields = {field.id: field for field in request.fields}
    safe_actions = []
    for action in decision.actions:
        field = fields.get(action.field_id)
        if field is None or field.field_type in {"password", "file", "other"}:
            continue
        label = normalize(f"{field.label} {field.name}")
        if any(
            marker in label
            for marker in (
                "password",
                "captcha",
                "verification code",
                "one time code",
                "mfa",
                "credit card",
                "bank account",
            )
        ):
            continue
        if action.confidence < 0.55:
            continue
        value = action.value.strip()
        if field.field_type == "checkbox":
            semantic = normalize(value)
            if semantic in {"true", "yes", "1", "on"}:
                value = "true"
            elif semantic in {"false", "no", "0", "off"}:
                value = "false"
            elif semantic in {
                normalize(field.option_label),
                normalize(field.label),
            }:
                value = "true"
            else:
                continue
        elif field.field_type in {"radio", "select"}:
            value = coerce_option(value, field)
            allowed = {
                normalize(option.label)
                for option in field.options
                if option.label
            } | {
                normalize(option.value)
                for option in field.options
                if option.value and normalize(option.value) != "on"
            }
            if allowed and normalize(value) not in allowed:
                continue
        message = normalize(request.user_message)
        pending = normalize(request.pending_question)
        normalized_value = normalize(value).replace("expereinced", "experienced")
        normalized_message = message.replace("expereinced", "experienced")
        label_tokens = {
            token
            for token in normalize(field.group_label or field.label).split()
            if len(token) >= 4
            and token
            not in {"what", "your", "this", "that", "with", "have", "will", "does"}
        }
        field_named = bool(label_tokens.intersection(message.split()))
        pending_matches = bool(pending) and (pending in label or label in pending)
        value_named = normalized_value in normalized_message
        if field.field_type == "checkbox" and normalized_value in {"true", "false"}:
            option = normalize(field.option_label or field.label)
            option_named = bool(option) and option in message
            consent_named = (
                "background check" in label
                and any(
                    phrase in message
                    for phrase in ("fine with", "ok with", "okay with", "reviewed", "consent")
                )
            )
            broad_multi_select = (
                normalized_value == "true"
                and field_named
                and any(
                    phrase in message
                    for phrase in (
                        "anywhere",
                        "any of these",
                        "all of them",
                        "all options",
                        "select all",
                    )
                )
            )
            value_named = option_named or consent_named or broad_multi_select
        explicit_user_supported = (
            request.origin == "chat"
            and action.grounding in {"user_message", "visible_option"}
            and value_named
            and (field_named or pending_matches)
        )

        canonical = map_profile_field(label, field, profile)
        if canonical is not None:
            expected = coerce_option(canonical[0], field)
            if normalize(value) != normalize(expected) and not explicit_user_supported:
                continue
        elif action.grounding == "profile":
            continue
        elif action.grounding == "saved_answer":
            saved = map_exact_reusable_answer(label, field, answers)
            if saved is None or normalize(value) != normalize(coerce_option(saved[0], field)):
                continue
        elif action.grounding == "source_context":
            sourced = map_source_field(label, field, request.source_url)
            if sourced is None or normalize(value) != normalize(coerce_option(sourced[0], field)):
                continue
        elif action.grounding == "resume":
            if resume is None:
                continue
            if field.field_type == "checkbox":
                if not resume_mentions_option(field.option_label, resume.extracted_text):
                    continue
            elif normalize(value) not in normalize(resume.extracted_text):
                continue
        elif action.grounding == "derived_answer":
            open_ended = field.field_type in {"text", "textarea"} and any(
                marker in label
                for marker in (
                    "why ",
                    "describe",
                    "tell us",
                    "explain",
                    "interest in",
                    "interested in",
                    "motivation",
                    "project you",
                    "experience with",
                    "additional information",
                )
            )
            protected = any(
                marker in label
                for marker in (
                    "gender",
                    "race",
                    "ethnicity",
                    "veteran",
                    "disability",
                    "date of birth",
                    "age",
                    "salary",
                    "compensation",
                    "authorized",
                    "sponsor",
                    "background check",
                )
            )
            if (
                request.origin != "automation"
                or not open_ended
                or protected
                or action.confidence < 0.75
                or len(value) < 2
            ):
                continue
        elif request.origin == "automation":
            # The automatic instruction supplies no new candidate facts. A
            # visible option alone is not evidence and must never be guessed.
            continue
        elif action.grounding in {"user_message", "visible_option"}:
            if not explicit_user_supported:
                continue
        safe_actions.append(
            action.model_copy(
                update={
                    "value": value,
                    "remember": action.remember and request.origin == "chat",
                }
            )
        )

    question = decision.question
    if decision.actions and not safe_actions and not question:
        question = "I could not safely match that request to a visible field. Which visible option should I use?"
    return decision.model_copy(
        update={
            "actions": safe_actions,
            "question": question,
            "handled": decision.handled or bool(safe_actions) or bool(question),
        }
    )


@app.post("/api/applications", response_model=ApplicationRecord)
def start_application(request: ApplicationCreate) -> ApplicationRecord:
    require_local_data_mode()
    return store.save_application(create_application(request))


@app.get("/api/applications", response_model=list[ApplicationRecord])
def list_applications() -> list[ApplicationRecord]:
    require_local_data_mode()
    return store.list_applications()


@app.get("/api/applications.csv")
def export_applications_csv() -> Response:
    require_local_data_mode()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "created_at",
            "updated_at",
            "status",
            "job_title",
            "company",
            "location",
            "source_url",
            "route",
            "last_event",
        ]
    )
    for application in store.list_applications():
        last_event = application.events[-1].message if application.events else ""
        writer.writerow(
            [
                application.created_at.isoformat(),
                application.updated_at.isoformat(),
                application.status,
                application.job.title,
                application.job.company,
                application.job.location,
                application.job.source_url,
                application.route.route if application.route else "",
                last_event,
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="applypilot-applications.csv"'},
    )


@app.get("/api/applications/{application_id}", response_model=ApplicationRecord)
def get_application(application_id: str) -> ApplicationRecord:
    require_local_data_mode()
    application = store.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@app.post(
    "/api/applications/{application_id}/transition",
    response_model=ApplicationRecord,
)
def transition_saved_application(
    application_id: str, transition: ApplicationTransition
) -> ApplicationRecord:
    require_local_data_mode()
    application = store.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        updated = transition_application(application, transition)
    except InvalidApplicationTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return store.save_application(updated)


def run() -> None:
    uvicorn.run("applypilot.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()

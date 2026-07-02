from __future__ import annotations

from contextlib import asynccontextmanager
import csv
import io
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import settings
from .documents import artifact_filename, build_docx, build_pdf
from .ai import AIProviderError, AIProviderManager
from .applications import (
    InvalidApplicationTransition,
    create_application,
    transition_application,
)
from .models import (
    ApplicationRouteDecision,
    ApplicationCreate,
    ApplicationRecord,
    ApplicationTransition,
    ApplicationAnswerDraft,
    ApplicationQuestionDraftRequest,
    CandidateProfile,
    ChatRequest,
    ChatResponse,
    FormFillPlan,
    FormPlanRequest,
    JobApplicationOptions,
    JobFitAnalysis,
    JobPreparation,
    OnboardingState,
    ProviderStatus,
    ProviderConfigRequest,
    PageActionDecision,
    PageActionRequest,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredResume,
    TailoredArtifact,
    TailoredArtifactRequest,
    TailorRequest,
)
from .onboarding import get_onboarding_state
from .form_mapper import plan_form_fill
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


@app.post("/api/application-route", response_model=ApplicationRouteDecision)
def application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    return choose_application_route(options)


@app.post("/api/forms/plan", response_model=FormFillPlan)
def form_plan(request: FormPlanRequest) -> FormFillPlan:
    require_local_data_mode()
    return plan_form_fill(
        page_url=request.page_url,
        fields=request.fields,
        profile=store.load(),
        answers=store.list_answers(),
        adapter=request.adapter,
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

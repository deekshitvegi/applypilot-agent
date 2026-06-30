from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .ai import AIProviderError, GeminiProvider
from .models import (
    ApplicationRouteDecision,
    CandidateProfile,
    ChatRequest,
    ChatResponse,
    FormFillPlan,
    FormPlanRequest,
    JobApplicationOptions,
    OnboardingState,
    ProviderStatus,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredResume,
    TailorRequest,
)
from .onboarding import get_onboarding_state
from .form_mapper import plan_form_fill
from .resume import ResumeExtractionError, extract_resume
from .routing import choose_application_route
from .store import ProfileStore

store = ProfileStore(settings.database_path)
ai_provider = GeminiProvider(settings.gemini_api_key, settings.ai_model)
web_directory = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.demo_mode:
        store.initialize()
    yield


app = FastAPI(title="ApplyPilot Agent", version="0.1.0", lifespan=lifespan)
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
    }


@app.get("/api/capabilities")
def capabilities() -> dict[str, bool | str]:
    return {
        "mode": "demo" if settings.demo_mode else "local",
        "stores_candidate_data": not settings.demo_mode,
        "company_site_first": True,
        "live_site_automation": False,
        "resume_tailoring": ai_provider.configured and not settings.demo_mode,
    }


@app.get("/api/provider", response_model=ProviderStatus)
def provider_status() -> ProviderStatus:
    return ProviderStatus(
        provider=settings.ai_provider,
        model=settings.ai_model,
        configured=ai_provider.configured,
    )


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
    try:
        resume = extract_resume(
            filename=file.filename or "resume",
            content=await file.read(),
            media_type=file.content_type or "",
        )
    except ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return store.save_resume(resume)


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


def run() -> None:
    uvicorn.run("applypilot.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()

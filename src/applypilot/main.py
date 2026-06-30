from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models import (
    ApplicationRouteDecision,
    CandidateProfile,
    JobApplicationOptions,
    OnboardingState,
)
from .onboarding import get_onboarding_state
from .routing import choose_application_route
from .store import ProfileStore

store = ProfileStore(settings.database_path)
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
    allow_methods=["GET", "PUT", "POST", "OPTIONS"],
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
        "resume_tailoring": False,
    }


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


@app.post("/api/application-route", response_model=ApplicationRouteDecision)
def application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    return choose_application_route(options)


def run() -> None:
    uvicorn.run("applypilot.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()

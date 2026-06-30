from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(_: FastAPI):
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "applypilot"}


@app.get("/api/profile", response_model=CandidateProfile)
def get_profile() -> CandidateProfile:
    return store.load()


@app.put("/api/profile", response_model=CandidateProfile)
def put_profile(profile: CandidateProfile) -> CandidateProfile:
    return store.save(profile)


@app.get("/api/onboarding", response_model=OnboardingState)
def onboarding() -> OnboardingState:
    return get_onboarding_state(store.load())


@app.post("/api/application-route", response_model=ApplicationRouteDecision)
def application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    return choose_application_route(options)


def run() -> None:
    uvicorn.run("applypilot.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()

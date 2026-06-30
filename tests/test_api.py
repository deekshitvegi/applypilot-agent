from pathlib import Path

from fastapi.testclient import TestClient

import applypilot.main as main_module
from applypilot.config import Settings
from applypilot.main import app
from applypilot.store import ProfileStore


client = TestClient(app)


def test_dashboard_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "ApplyPilot Agent — Live Demo" in response.text


def test_synthetic_ats_is_served() -> None:
    response = client.get("/demo/ats")

    assert response.status_code == 200
    assert "ApplyPilot Synthetic ATS" in response.text
    assert "application-form" in response.text


def test_capabilities_are_honest_about_incomplete_features() -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["company_site_first"] is True
    assert response.json()["live_site_automation"] is False
    assert response.json()["resume_tailoring"] is False


def test_demo_mode_refuses_candidate_profile_access(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(database_path=tmp_path / "unused.sqlite3", demo_mode=True),
    )

    with TestClient(main_module.app) as demo_client:
        response = demo_client.get("/api/profile")

    assert response.status_code == 403
    assert "does not store candidate data" in response.json()["detail"]


def test_local_resume_upload_and_provider_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(database_path=tmp_path / "local.sqlite3", demo_mode=False),
    )
    monkeypatch.setattr(main_module, "store", ProfileStore(tmp_path / "local.sqlite3"))
    resume_text = (
        "Test Candidate\nSoftware Engineer\n"
        "Built reliable Python services and automated deployment workflows.\n" * 3
    )

    upload = client.post(
        "/api/resumes",
        files={"file": ("resume.txt", resume_text, "text/plain")},
    )
    provider = client.get("/api/provider")

    assert upload.status_code == 200
    assert upload.json()["filename"] == "resume.txt"
    assert provider.status_code == 200
    assert provider.json()["provider"] == "gemini"

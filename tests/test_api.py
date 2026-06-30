from pathlib import Path

from fastapi.testclient import TestClient

import applypilot.main as main_module
from applypilot.config import Settings
from applypilot.main import app
from applypilot.models import CandidateProfile, ResumeDocument, TailoredResume
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


def test_local_capabilities_report_implemented_features() -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["company_site_first"] is True
    assert response.json()["live_site_automation"] is True
    assert response.json()["resume_tailoring"] is False
    assert response.json()["review_before_submit"] is True


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


def test_application_api_lifecycle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(database_path=tmp_path / "applications.sqlite3", demo_mode=False),
    )
    monkeypatch.setattr(
        main_module,
        "store",
        ProfileStore(tmp_path / "applications.sqlite3"),
    )
    created = client.post(
        "/api/applications",
        json={
            "job": {
                "title": "Software Engineer",
                "company": "Example Robotics",
                "description": "Build reliable Python automation.",
            }
        },
    )
    application_id = created.json()["id"]

    transitioned = client.post(
        f"/api/applications/{application_id}/transition",
        json={"status": "analyzed", "message": "Job analyzed"},
    )
    listed = client.get("/api/applications")

    assert created.status_code == 200
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "analyzed"
    assert listed.json()[0]["id"] == application_id


def test_tailored_artifact_downloads(monkeypatch, tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "tailored.sqlite3")
    local_store.save(
        CandidateProfile(
            legal_name="Test Candidate",
            email="candidate@example.test",
        )
    )
    local_store.save_resume(
        ResumeDocument(
            filename="resume.txt",
            media_type="text/plain",
            sha256="tailored-test",
            extracted_text="Verified Python automation experience. " * 5,
        )
    )
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module.ai_provider,
        "tailor_resume",
        lambda _resume, _job: TailoredResume(
            headline="Software Engineer",
            summary="Python automation engineer.",
        ),
    )

    created = client.post(
        "/api/tailored",
        json={"job": {"description": "Build Python automation."}},
    )
    artifact_id = created.json()["id"]
    docx = client.get(f"/api/tailored/{artifact_id}.docx")
    pdf = client.get(f"/api/tailored/{artifact_id}.pdf")

    assert created.status_code == 200
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

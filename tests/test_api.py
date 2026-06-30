from pathlib import Path

from fastapi.testclient import TestClient

import applypilot.main as main_module
from applypilot.config import Settings
from applypilot.main import app


client = TestClient(app)


def test_dashboard_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "ApplyPilot Agent — Live Demo" in response.text


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

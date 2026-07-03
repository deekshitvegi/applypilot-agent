from pathlib import Path

from fastapi.testclient import TestClient

import applypilot.main as main_module
from applypilot.config import Settings
from applypilot.ai import AIProviderManager
from applypilot.main import app
from applypilot.models import (
    CandidateProfile,
    FormAgentAction,
    FormAgentDecision,
    JobFitAnalysis,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredResume,
)
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


def test_form_agent_plan_validates_model_tool_actions(monkeypatch, tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "agent-plan.sqlite3")
    local_store.save(
        CandidateProfile(
            email="candidate@example.com",
            current_title="AI Engineer",
            background_check_consent=True,
        )
    )
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module.ai_provider,
        "plan_form_actions",
        lambda _request: FormAgentDecision(
            handled=True,
            actions=[
                    FormAgentAction(
                        field_id="source",
                        value="LinkedIn",
                        grounding="source_context",
                        confidence=0.98,
                    ),
                FormAgentAction(
                        field_id="consent",
                        value="yes",
                        grounding="profile",
                        confidence=0.97,
                    ),
                    FormAgentAction(
                        field_id="email",
                        value="AI Engineer",
                        grounding="profile",
                        confidence=1,
                    ),
                FormAgentAction(
                    field_id="missing",
                    value="invented",
                    grounding="user_message",
                    confidence=1,
                ),
            ],
        ),
    )

    response = client.post(
        "/api/forms/agent-plan",
        json={
            "user_message": "Use LinkedIn and confirm consent",
            "origin": "automation",
            "source_url": "https://www.linkedin.com/jobs/view/123",
            "fields": [
                {
                    "id": "source",
                    "label": "How did you find this position?",
                    "field_type": "radio",
                    "options": [
                        {"value": "on", "label": "Current Employee"},
                        {"value": "on", "label": "LinkedIn"},
                    ],
                },
                {
                    "id": "consent",
                    "label": "I reviewed the background check policy",
                    "field_type": "checkbox",
                },
                {
                    "id": "email",
                    "label": "Email",
                    "field_type": "email",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert [(item["field_id"], item["value"]) for item in response.json()["actions"]] == [
        ("source", "LinkedIn"),
        ("consent", "true"),
    ]
    assert all(item["remember"] is False for item in response.json()["actions"])


def test_form_agent_accepts_truthful_derived_open_ended_answer(monkeypatch, tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "derived-answer.sqlite3")
    local_store.save_resume(
        ResumeDocument(
            filename="resume.txt",
            media_type="text/plain",
            sha256="derived",
            extracted_text="Built Python automation and production AI systems.",
        )
    )
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module.ai_provider,
        "plan_form_actions",
        lambda _request: FormAgentDecision(
            handled=True,
            actions=[
                FormAgentAction(
                    field_id="interest",
                    value="I am interested in applying my Python automation experience to this role.",
                    grounding="derived_answer",
                    confidence=0.9,
                    remember=False,
                ),
                FormAgentAction(
                    field_id="salary",
                    value="150000",
                    grounding="derived_answer",
                    confidence=0.9,
                    remember=False,
                ),
            ],
        ),
    )

    response = client.post(
        "/api/forms/agent-plan",
        json={
            "user_message": "Complete every evidence-supported unresolved field.",
            "origin": "automation",
            "fields": [
                {
                    "id": "interest",
                    "label": "Why are you interested in this role?",
                    "field_type": "textarea",
                },
                {
                    "id": "salary",
                    "label": "What are your salary expectations?",
                    "field_type": "text",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert [item["field_id"] for item in response.json()["actions"]] == ["interest"]
    assert response.json()["actions"][0]["remember"] is False


def test_prunes_conflicting_canonical_reusable_answers(tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "canonical-cleanup.sqlite3")
    local_store.save(CandidateProfile(email="candidate@example.com", current_title="AI Engineer"))
    bad_title = ReusableAnswer(question="What is your current job title?", answer="Terraform")
    bad_email = ReusableAnswer(question="Email", answer="AI Engineer")
    custom = ReusableAnswer(question="What is your Linux experience?", answer="Experienced")
    for answer in (bad_title, bad_email, custom):
        local_store.save_answer(answer)

    assert main_module.prune_canonical_reusable_answers(local_store) == 2
    assert [(item.question, item.answer) for item in local_store.list_answers()] == [
        (custom.question, custom.answer)
    ]


def test_local_capabilities_report_implemented_features() -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["company_site_first"] is True
    assert response.json()["live_site_automation"] is True
    assert isinstance(response.json()["resume_tailoring"], bool)
    assert response.json()["deterministic_autofill"] is True
    assert response.json()["editable_reusable_profile"] is True
    assert response.json()["automation_policies"] == ["review_each", "always_allow"]
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
    local_settings = Settings(database_path=tmp_path / "local.sqlite3", demo_mode=False)
    local_store = ProfileStore(local_settings.database_path)
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module,
        "ai_provider",
        AIProviderManager(local_store, local_settings),
    )
    resume_text = (
        "Test Candidate\nSoftware Engineer\n"
        "Built reliable Python services and automated deployment workflows.\n" * 3
    )

    upload = client.post(
        "/api/resumes",
        files={"file": ("resume.txt", resume_text, "text/plain")},
    )
    provider = client.get("/api/provider")
    original = client.get("/api/resumes/active/file")
    file_status = client.get("/api/resumes/active/file-status")

    assert upload.status_code == 200
    assert upload.json()["filename"] == "resume.txt"
    assert original.status_code == 200
    assert original.content == resume_text.encode()
    assert file_status.json() == {"available": True, "filename": "resume.txt"}
    assert provider.status_code == 200
    assert provider.json()["provider"] == "gemini"


def test_resume_file_status_detects_legacy_metadata_without_raw_file(
    monkeypatch, tmp_path: Path
) -> None:
    local_settings = Settings(database_path=tmp_path / "legacy.sqlite3", demo_mode=False)
    local_store = ProfileStore(local_settings.database_path)
    local_store.save_resume(
        ResumeDocument(
            filename="legacy.pdf",
            media_type="application/pdf",
            sha256="legacy123",
            extracted_text="Legacy extracted resume text",
        )
    )
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)

    response = client.get("/api/resumes/active/file-status")
    reconstructed = client.get("/api/resumes/active/reconstructed.docx")

    assert response.status_code == 200
    assert response.json() == {"available": False, "filename": "legacy.pdf"}
    assert reconstructed.status_code == 200
    assert reconstructed.content.startswith(b"PK")


def test_local_cover_letter_upload_and_download(monkeypatch, tmp_path: Path) -> None:
    local_settings = Settings(database_path=tmp_path / "cover.sqlite3", demo_mode=False)
    local_store = ProfileStore(local_settings.database_path)
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)
    text = "Dear hiring team,\nI am interested in this role.\n" * 3

    upload = client.post(
        "/api/cover-letters",
        files={"file": ("cover-letter.txt", text, "text/plain")},
    )
    downloaded = client.get("/api/cover-letters/active/file")

    assert upload.status_code == 200
    assert upload.json()["filename"] == "cover-letter.txt"
    assert downloaded.status_code == 200
    assert downloaded.content == text.encode()


def test_provider_can_be_configured_without_returning_key(monkeypatch, tmp_path: Path) -> None:
    local_settings = Settings(
        database_path=tmp_path / "provider.sqlite3",
        demo_mode=False,
        gemini_api_key="",
    )
    local_store = ProfileStore(local_settings.database_path)
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module,
        "ai_provider",
        AIProviderManager(local_store, local_settings),
    )

    saved = client.put(
        "/api/provider",
        json={
            "provider": "openai",
            "api_key": "private-openai-test-key",
            "model": "gpt-5-mini",
        },
    )

    assert saved.status_code == 200
    assert saved.json() == {
        "provider": "openai",
        "model": "gpt-5-mini",
        "configured": True,
        "source": "encrypted_local",
        "reasoning_provider": "",
        "reasoning_model": "",
    }
    assert "private-openai-test-key" not in saved.text
    assert client.delete("/api/provider").json()["configured"] is False


def test_local_ollama_provider_requires_no_api_key(monkeypatch, tmp_path: Path) -> None:
    local_settings = Settings(
        database_path=tmp_path / "ollama.sqlite3",
        demo_mode=False,
        gemini_api_key="",
    )
    local_store = ProfileStore(local_settings.database_path)
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module,
        "ai_provider",
        AIProviderManager(local_store, local_settings),
    )

    saved = client.put(
        "/api/provider",
        json={"provider": "ollama", "api_key": "", "model": "qwen3:8b"},
    )

    assert saved.status_code == 200
    assert saved.json() == {
        "provider": "ollama",
        "model": "qwen3:8b",
        "configured": True,
        "source": "encrypted_local",
        "reasoning_provider": "",
        "reasoning_model": "",
    }


def test_ollama_reports_selective_gemini_reasoning(tmp_path: Path) -> None:
    local_settings = Settings(
        database_path=tmp_path / "hybrid.sqlite3",
        demo_mode=False,
        gemini_api_key="test-gemini-key",
    )
    local_store = ProfileStore(local_settings.database_path)
    local_store.save_provider_config(
        main_module.ProviderConfigRequest(
            provider="ollama",
            api_key="",
            model="qwen3:4b",
        )
    )
    manager = AIProviderManager(local_store, local_settings)

    status = manager.status()

    assert status.provider == "ollama"
    assert status.reasoning_provider == "gemini"
    assert status.reasoning_model == "gemini-2.5-flash"
    assert manager.hybrid_reasoning_enabled is True


def test_reasoning_provider_key_is_stored_separately(monkeypatch, tmp_path: Path) -> None:
    local_settings = Settings(
        database_path=tmp_path / "reasoning-provider.sqlite3",
        demo_mode=False,
        gemini_api_key="",
    )
    local_store = ProfileStore(local_settings.database_path)
    manager = AIProviderManager(local_store, local_settings)
    monkeypatch.setattr(main_module, "settings", local_settings)
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(main_module, "ai_provider", manager)

    class ProbeProvider:
        def probe_connection(self):
            return None

    monkeypatch.setattr("applypilot.ai.create_provider", lambda _config: ProbeProvider())

    saved = client.put(
        "/api/provider/reasoning",
        json={
            "provider": "gemini",
            "api_key": "private-gemini-test-key",
            "model": "gemini-2.5-flash",
        },
    )

    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert saved.json()["provider"] == "gemini"
    assert "private-gemini-test-key" not in saved.text
    assert client.get("/api/provider/reasoning").json()["configured"] is True
    assert client.delete("/api/provider/reasoning").json()["configured"] is False


def test_form_agent_accepts_explicit_checkbox_option_language(monkeypatch, tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "explicit-checkbox.sqlite3")
    monkeypatch.setattr(main_module, "store", local_store)
    monkeypatch.setattr(
        main_module.ai_provider,
        "plan_form_actions",
        lambda _request: FormAgentDecision(
            handled=True,
            actions=[
                FormAgentAction(
                    field_id="github-ci",
                    value="true",
                    grounding="user_message",
                    confidence=1,
                )
            ],
        ),
    )

    response = client.post(
        "/api/forms/agent-plan",
        json={
            "user_message": "For hands-on tools, add GitHub CI",
            "origin": "chat",
            "fields": [
                {
                    "id": "github-ci",
                    "label": "Please select all tools you have hands on experience with GitHub CI",
                    "group_label": "Please select all tools you have hands on experience with",
                    "option_label": "GitHub CI",
                    "field_type": "checkbox",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["actions"][0]["field_id"] == "github-ci"


def test_chat_rejects_oversized_or_invalid_images() -> None:
    invalid = client.post(
        "/api/chat",
        json={
            "message": "Read this screenshot",
            "images": [
                {
                    "filename": "screenshot.png",
                    "media_type": "image/png",
                    "data_base64": "not-base64",
                }
            ],
        },
    )

    assert invalid.status_code == 422


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

    exported = client.get("/api/applications.csv")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert "Software Engineer" in exported.text
    assert "Example Robotics" in exported.text


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


def test_job_preparation_reuses_verified_evidence(monkeypatch, tmp_path: Path) -> None:
    local_store = ProfileStore(tmp_path / "prepare.sqlite3")
    local_store.save_resume(
        ResumeDocument(
            filename="resume.txt",
            media_type="text/plain",
            sha256="prepare-test",
            extracted_text="Built Python automation services. " * 4,
        )
    )
    monkeypatch.setattr(main_module, "store", local_store)
    evidence = ResumeEvidence(summary="Verified Python experience")
    calls: list[str] = []
    monkeypatch.setattr(
        main_module.ai_provider,
        "extract_evidence",
        lambda _resume: calls.append("evidence") or evidence,
    )
    monkeypatch.setattr(
        main_module.ai_provider,
        "analyze_job",
        lambda _resume, _job, supplied: calls.append("analysis")
        or JobFitAnalysis(
            score=85,
            verdict="strong",
            summary="Strong fit",
            recommendation="Apply",
        )
        if supplied is evidence
        else None,
    )
    monkeypatch.setattr(
        main_module.ai_provider,
        "tailor_resume",
        lambda _resume, _job, supplied: calls.append("tailor")
        or TailoredResume(headline="Automation Engineer", summary="Python engineer")
        if supplied is evidence
        else None,
    )

    prepared = client.post(
        "/api/jobs/prepare",
        json={"job": {"description": "Build Python automation."}},
    )

    assert prepared.status_code == 200
    assert prepared.json()["analysis"]["score"] == 85
    assert prepared.json()["artifact"]["tailored"]["headline"] == "Automation Engineer"
    assert calls == ["evidence", "analysis", "tailor"]

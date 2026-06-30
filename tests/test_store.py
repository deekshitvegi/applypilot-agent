from pathlib import Path

import sqlite3

from applypilot.models import (
    ApplicationRecord,
    CandidateProfile,
    JobContext,
    ProviderConfigRequest,
    ResumeDocument,
    ReusableAnswer,
    TailoredArtifact,
    TailoredResume,
)
from applypilot.store import ProfileStore


def test_profile_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    profile = CandidateProfile(
        legal_name="Test Candidate",
        email="candidate@example.test",
        custom_answers={"Are you at least 18 years old?": "Yes"},
    )

    store.save(profile)

    assert store.load() == profile

    with sqlite3.connect(tmp_path / "profile.sqlite3") as connection:
        payload = connection.execute(
            "SELECT payload FROM candidate_profile WHERE id = 1"
        ).fetchone()[0]
    assert "candidate@example.test" not in payload


def test_answer_and_resume_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    answer = ReusableAnswer(question="Are you willing to travel?", answer="Yes")
    resume = ResumeDocument(
        filename="resume.txt",
        media_type="text/plain",
        sha256="abc123",
        extracted_text="Verified resume text " * 10,
    )

    store.save_answer(answer)
    store.save_resume(resume)

    assert store.list_answers() == [answer]
    assert store.get_active_resume() == resume
    assert store.list_resumes() == [resume]
    assert store.delete_answer(answer.id) is True
    assert store.list_answers() == []


def test_application_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    application = ApplicationRecord(
        job=JobContext(
            title="Software Engineer",
            company="Example Robotics",
            description="Build reliable Python automation.",
        ),
        status="analyzed",
    )

    store.save_application(application)

    assert store.get_application(application.id) == application
    assert store.list_applications() == [application]


def test_tailored_artifact_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    artifact = TailoredArtifact(
        application_id="application-1",
        tailored=TailoredResume(
            headline="Software Engineer",
            summary="Python automation engineer.",
        ),
    )

    store.save_tailored_artifact(artifact)

    assert store.get_tailored_artifact(artifact.id) == artifact


def test_provider_key_is_encrypted_and_can_be_removed(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    config = ProviderConfigRequest(
        provider="gemini",
        api_key="private-test-key",
        model="gemini-2.5-flash",
    )

    store.save_provider_config(config)

    assert store.get_provider_config() == config
    with sqlite3.connect(tmp_path / "profile.sqlite3") as connection:
        payload = connection.execute("SELECT payload FROM provider_config WHERE id = 1").fetchone()[0]
    assert "private-test-key" not in payload
    assert store.delete_provider_config() is True
    assert store.get_provider_config() is None

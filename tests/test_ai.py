from applypilot.ai import GeminiProvider
from applypilot.models import (
    EvidenceItem,
    JobContext,
    ResumeDocument,
    ResumeEvidence,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)


def test_evidence_extractor_removes_non_verbatim_claims(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    resume = ResumeDocument(
        filename="resume.txt",
        media_type="text/plain",
        sha256="abc",
        extracted_text="Built Python services that reduced deployment time by 30 percent.",
    )
    extracted = ResumeEvidence(
        items=[
            EvidenceItem(
                id="valid",
                category="experience",
                text="Reduced deployment time",
                source_quote="reduced deployment time by 30 percent",
            ),
            EvidenceItem(
                id="invented",
                category="experience",
                text="Managed ten engineers",
                source_quote="Managed ten engineers",
            ),
        ]
    )
    monkeypatch.setattr(provider, "_structured", lambda _prompt, _schema: extracted)

    result = provider.extract_evidence(resume)

    assert [item.id for item in result.items] == ["valid"]


def test_tailoring_removes_bullets_without_valid_evidence(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    resume = ResumeDocument(
        filename="resume.txt",
        media_type="text/plain",
        sha256="abc",
        extracted_text="Built Python services.",
    )
    evidence = ResumeEvidence(
        items=[
            EvidenceItem(
                id="valid",
                category="experience",
                text="Built Python services",
                source_quote="Built Python services",
            )
        ]
    )
    generated = TailoredResume(
        headline="Software Engineer",
        summary="Python engineer",
        experiences=[
            TailoredExperience(
                heading="Experience",
                bullets=[
                    TailoredBullet(text="Built Python services", evidence_ids=["valid"]),
                    TailoredBullet(text="Managed ten engineers", evidence_ids=["invented"]),
                ],
            )
        ],
    )
    monkeypatch.setattr(provider, "_structured", lambda _prompt, _schema: generated)

    result = provider.tailor_resume(
        resume,
        JobContext(description="Looking for a Python engineer."),
        evidence,
    )

    assert [bullet.text for bullet in result.experiences[0].bullets] == [
        "Built Python services"
    ]
    assert result.warnings

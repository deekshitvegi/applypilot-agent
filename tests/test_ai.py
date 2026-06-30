import json

from applypilot.ai import AnthropicProvider, GeminiProvider, OpenAIProvider
from applypilot.models import (
    ChatResponse,
    EvidenceItem,
    JobContext,
    JobFitAnalysis,
    ResumeDocument,
    ResumeEvidence,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


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


def test_job_fit_analysis_uses_verified_evidence(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    resume = ResumeDocument(
        filename="resume.txt",
        media_type="text/plain",
        sha256="fit",
        extracted_text="Built Python services.",
    )
    evidence = ResumeEvidence(
        items=[
            EvidenceItem(
                id="python",
                category="experience",
                text="Built Python services",
                source_quote="Built Python services",
            )
        ]
    )
    expected = JobFitAnalysis(
        score=82,
        verdict="strong",
        summary="Strong Python match.",
        strengths=["Python services"],
        gaps=["No Kubernetes evidence"],
        matched_keywords=["Python"],
        recommendation="Apply",
    )
    monkeypatch.setattr(provider, "_structured", lambda _prompt, _schema: expected)

    result = provider.analyze_job(
        resume,
        JobContext(description="Build Python services and Kubernetes systems."),
        evidence,
    )

    assert result == expected


def test_openai_structured_response(monkeypatch) -> None:
    expected = ChatResponse(answer="Review the salary field.")
    response = FakeResponse(
        {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": expected.model_dump_json()}
                    ]
                }
            ]
        }
    )
    monkeypatch.setattr("applypilot.ai.httpx.post", lambda *args, **kwargs: response)

    result = OpenAIProvider("test-key", "gpt-5-mini")._structured(
        "prompt", ChatResponse
    )

    assert result == expected


def test_anthropic_structured_response(monkeypatch) -> None:
    expected = ChatResponse(answer="The screenshot shows a required field.")
    response = FakeResponse(
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "return_structured_result",
                    "input": json.loads(expected.model_dump_json()),
                }
            ]
        }
    )
    monkeypatch.setattr("applypilot.ai.httpx.post", lambda *args, **kwargs: response)

    result = AnthropicProvider("test-key", "claude-test")._structured(
        "prompt", ChatResponse
    )

    assert result == expected

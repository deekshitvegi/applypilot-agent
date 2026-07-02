import json
from types import SimpleNamespace

import applypilot.ai as ai_module
from applypilot.ai import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    gemini_error_message,
)
from applypilot.models import (
    ApplicationAnswerDraft,
    CandidateProfile,
    ChatImage,
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


def test_ollama_structured_response_uses_local_schema_without_key(monkeypatch) -> None:
    expected = ChatResponse(answer="The local model is ready.")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return FakeResponse(
            {"message": {"role": "assistant", "content": expected.model_dump_json()}}
        )

    monkeypatch.setattr("applypilot.ai.httpx.post", fake_post)

    result = OllamaProvider("", "qwen3:8b")._structured("prompt", ChatResponse)

    assert result == expected
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "qwen3:8b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"]["type"] == "object"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["keep_alive"] == "45s"
    assert captured["payload"]["options"]["num_ctx"] == 8192


def test_ollama_routes_images_to_local_vision_model(monkeypatch) -> None:
    expected = ChatResponse(answer="The screenshot is readable.")
    captured = {}

    def fake_post(_url, **kwargs):
        captured["payload"] = kwargs["json"]
        return FakeResponse(
            {"message": {"role": "assistant", "content": expected.model_dump_json()}}
        )

    monkeypatch.setattr("applypilot.ai.httpx.post", fake_post)
    image = ChatImage(filename="field.png", media_type="image/png", data_base64="aA==")

    result = OllamaProvider("", "qwen3:8b")._structured(
        "Read the screenshot", ChatResponse, [image]
    )

    assert result == expected
    assert captured["payload"]["model"] == "gemma3:4b"
    assert captured["payload"]["messages"][0]["images"] == ["aA=="]


def test_application_answer_draft_uses_structured_provider(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    expected = ApplicationAnswerDraft(
        answer="I am interested in applying my verified Python automation experience."
    )
    monkeypatch.setattr(provider, "_structured", lambda _prompt, _schema: expected)

    result = provider.draft_application_answer(
        question="Why are you interested in this role?",
        profile=CandidateProfile(current_title="Software Engineer"),
        resume=None,
        job=JobContext(description="Build automation systems."),
    )

    assert result == expected


def test_gemini_quota_error_is_explained_without_client_internals() -> None:
    error = type(
        "QuotaError",
        (Exception,),
        {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded. Please retry in 39.4s.",
        },
    )()

    message = gemini_error_message(error)

    assert "free-tier rate limit" in message
    assert "40 seconds" in message
    assert "ClientError" not in message


def test_gemini_waits_for_a_short_reset_and_retries_once(monkeypatch) -> None:
    class QuotaError(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        message = "Quota exceeded. Please retry in 2.4s."

    expected = ChatResponse(answer="Hello")
    calls = []
    waits = []

    class FakeModels:
        def generate_content(self, **_kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise QuotaError
            return SimpleNamespace(text=expected.model_dump_json())

    monkeypatch.setattr(
        ai_module.genai,
        "Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )
    monkeypatch.setattr(ai_module.time, "sleep", waits.append)

    result = GeminiProvider("test-key", "test-model")._structured("Hello", ChatResponse)

    assert result.answer.endswith("Hello")
    assert "retried once successfully" in result.answer
    assert calls == [True, True]
    assert waits == [2.9]

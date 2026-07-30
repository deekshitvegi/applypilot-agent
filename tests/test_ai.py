import json
from types import SimpleNamespace

import applypilot.ai as ai_module
from applypilot.ai import (
    AIProviderError,
    AIProviderManager,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    gemini_error_message,
)
from applypilot.config import Settings
from applypilot.models import (
    ApplicationAnswerDraft,
    CandidateProfile,
    ChatImage,
    ChatResponse,
    CoverLetterDraft,
    EvidenceItem,
    FormAgentAction,
    FormAgentDecision,
    FormAgentRequest,
    FormField,
    FormOption,
    JobContext,
    JobFitAnalysis,
    ResumeDocument,
    ResumeEvidence,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)
from applypilot.store import ProfileStore


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


def test_form_agent_plans_structured_grounded_actions(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    expected = FormAgentDecision(
        handled=True,
        actions=[
            FormAgentAction(
                field_id="source",
                value="LinkedIn",
                grounding="user_message",
                confidence=0.99,
            )
        ],
        explanation="Selected the requested referral source.",
    )
    captured = {}

    def fake_structured(prompt, schema):
        captured["prompt"] = prompt
        captured["schema"] = schema
        return expected

    monkeypatch.setattr(provider, "_structured", fake_structured)
    request = FormAgentRequest(
        user_message="Change the source to LinkedIn",
        fields=[
            FormField(
                id="source",
                label="How did you find this position?",
                field_type="radio",
                options=[FormOption(value="on", label="LinkedIn")],
            )
        ],
    )

    result = provider.plan_form_actions(
        request,
        CandidateProfile(),
        [],
        None,
    )

    assert result == expected
    assert captured["schema"] is FormAgentDecision
    assert "action-planning task, not an" in captured["prompt"]
    assert "Change the source to LinkedIn" in captured["prompt"]
    assert "How did you find this position?" in captured["prompt"]
    assert captured["prompt"].index("CURRENT VISIBLE FIELDS") < captured["prompt"].index("RESUME EVIDENCE TEXT")


def test_hybrid_form_reasoning_falls_back_to_ollama(monkeypatch, tmp_path) -> None:
    manager = AIProviderManager(
        ProfileStore(tmp_path / "hybrid-fallback.sqlite3"),
        Settings(database_path=tmp_path / "hybrid-fallback.sqlite3", gemini_api_key="key"),
    )
    expected = FormAgentDecision(handled=True, question="Which Linux level should I use?")

    class Preferred:
        def plan_form_actions(self, *_args):
            raise AIProviderError("Gemini free-tier limit reached")

    class Fallback:
        def plan_form_actions(self, *_args):
            return expected

    monkeypatch.setattr(manager, "_reasoning_providers", lambda: (Preferred(), Fallback()))

    result = manager.plan_form_actions(
        FormAgentRequest(
            user_message="Fill the form",
            fields=[FormField(id="linux", label="Linux level", field_type="radio")],
        )
    )

    assert result == expected


def test_hybrid_application_answer_uses_reasoning_provider(monkeypatch, tmp_path) -> None:
    manager = AIProviderManager(
        ProfileStore(tmp_path / "hybrid-answer.sqlite3"),
        Settings(database_path=tmp_path / "hybrid-answer.sqlite3", gemini_api_key="key"),
    )
    expected = ApplicationAnswerDraft(answer="A grounded job-specific response.")

    class Preferred:
        def draft_application_answer(self, *_args):
            return expected

    class Fallback:
        def draft_application_answer(self, *_args):
            raise AssertionError("fallback should not run")

    monkeypatch.setattr(manager, "_reasoning_providers", lambda: (Preferred(), Fallback()))

    result = manager.draft_application_answer(
        "Why this role?", CandidateProfile(), None, JobContext(description="Build AI.")
    )

    assert result == expected

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


def test_answer_refinement_and_cover_letter_use_structured_provider(monkeypatch) -> None:
    provider = GeminiProvider("test-key", "test-model")
    refined = ApplicationAnswerDraft(answer="SIEM: 0 months; SOAR: 0 months.")
    cover = CoverLetterDraft(
        body="Dear Hiring Team,\n\nI offer verified Python automation experience."
    )
    outputs = iter([refined, cover])
    monkeypatch.setattr(provider, "_structured", lambda _prompt, _schema: next(outputs))
    resume = ResumeDocument(
        filename="resume.txt",
        media_type="text/plain",
        sha256="abc",
        extracted_text="Built Python automation.",
    )
    job = JobContext(title="Engineer", company="Example", description="Build automation.")

    result = provider.refine_application_answer(
        "List months for SIEM and SOAR.",
        "zero for all",
        CandidateProfile(),
        resume,
        job,
    )
    letter = provider.draft_cover_letter(CandidateProfile(), resume, job)

    assert result == refined
    assert letter == cover


def test_ollama_cover_letter_falls_back_when_json_grammar_is_rejected(monkeypatch) -> None:
    provider = OllamaProvider("", "qwen3:4b")
    monkeypatch.setattr(
        provider,
        "_structured",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ai_module.AIProviderError("Failed to parse grammar")
        ),
    )
    monkeypatch.setattr(
        ai_module.httpx,
        "post",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "message": {
                    "content": "Dear Hiring Team,\n\nI offer verified Python automation experience."
                }
            }
        ),
    )

    letter = provider.draft_cover_letter(
        CandidateProfile(),
        ResumeDocument(
            filename="resume.txt",
            media_type="text/plain",
            sha256="resume",
            extracted_text="Built Python automation.",
        ),
        JobContext(title="Engineer", company="Example", description="Build automation."),
    )

    assert "verified Python automation" in letter.body


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


def test_gemini_invalid_request_keeps_safe_google_detail() -> None:
    error = type(
        "InvalidRequest",
        (Exception,),
        {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": "Project location is not supported for the free tier",
        },
    )()

    message = gemini_error_message(error)

    assert "free tier" in message
    assert "billing-enabled" in message


def test_gemini_connection_probe_does_not_send_response_schema(monkeypatch) -> None:
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="CONNECTED")

    monkeypatch.setattr(
        ai_module.genai,
        "Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )

    GeminiProvider("test-key", "gemini-2.5-flash").probe_connection()

    assert captured["model"] == "gemini-2.5-flash"
    assert captured["contents"] == "Reply only with CONNECTED."
    assert captured["config"].response_schema is None


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


class _SchemaRejection(Exception):
    """Mimics google-genai's 400 when a nested response_schema is refused."""

    def __init__(self) -> None:
        super().__init__("Invalid JSON payload received. Unknown name \"$ref\" at response_schema")
        self.code = 400
        self.status = "INVALID_ARGUMENT"
        self.message = 'Invalid value at response_schema: unknown name "$ref"'


def test_gemini_retries_without_schema_when_google_rejects_it(monkeypatch) -> None:
    # Live regression: the field planner died with "Gemini rejected the
    # request ... invalid argument" because FormAgentDecision nests
    # FormAgentAction, which Pydantic emits as $defs/$ref. Falling back to a
    # schemaless JSON request keeps the agent working; the reply is still
    # validated against the same model before anything uses it.
    from applypilot.ai import ChatResponse, GeminiProvider

    calls: list[bool] = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            used_schema = getattr(config, "response_schema", None) is not None
            calls.append(used_schema)
            if used_schema:
                raise _SchemaRejection()
            return type("Response", (), {"text": '{"answer": "recovered"}'})()

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.models = FakeModels()

    monkeypatch.setattr("applypilot.ai.genai.Client", FakeClient)
    provider = GeminiProvider("test-key", "gemini-2.5-flash")

    result = provider._structured("prompt", ChatResponse)

    assert result.answer == "recovered"
    assert calls == [True, False]


def test_gemini_does_not_retry_schemaless_for_an_invalid_key(monkeypatch) -> None:
    import pytest

    from applypilot.ai import AIProviderError, ChatResponse, GeminiProvider

    class KeyRejection(Exception):
        def __init__(self) -> None:
            super().__init__("API key not valid")
            self.code = 401
            self.status = "UNAUTHENTICATED"
            self.message = "API key not valid"

    attempts: list[bool] = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            attempts.append(getattr(config, "response_schema", None) is not None)
            raise KeyRejection()

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.models = FakeModels()

    monkeypatch.setattr("applypilot.ai.genai.Client", FakeClient)
    provider = GeminiProvider("bad-key", "gemini-2.5-flash")

    with pytest.raises(AIProviderError, match="rejected this API key"):
        provider._structured("prompt", ChatResponse)
    assert attempts == [True]

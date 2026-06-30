from __future__ import annotations

import base64
from collections.abc import Iterable
from typing import Any

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import Settings
from .models import (
    CandidateProfile,
    ChatImage,
    ChatResponse,
    JobContext,
    ProviderConfigRequest,
    ProviderStatus,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredResume,
)
from .store import ProfileStore


DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


class AIProviderError(RuntimeError):
    pass


class BaseAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def extract_evidence(self, resume: ResumeDocument) -> ResumeEvidence:
        prompt = f"""
You are ApplyPilot's resume evidence extractor.

Extract only facts explicitly present in the resume below. Every evidence item must contain
an exact, verbatim source_quote copied from the resume. Do not infer years, metrics, skills,
dates, employers, degrees, or responsibilities. If uncertain, omit the item.

RESUME:
{resume.extracted_text[:40000]}
"""
        evidence = self._structured(prompt, ResumeEvidence)
        evidence.items = [
            item for item in evidence.items if item.source_quote in resume.extracted_text
        ]
        return evidence

    def tailor_resume(
        self,
        resume: ResumeDocument,
        job: JobContext,
        evidence: ResumeEvidence | None = None,
    ) -> TailoredResume:
        evidence = evidence or self.extract_evidence(resume)
        prompt = f"""
You are ApplyPilot's truthful resume tailoring agent.

Tailor the candidate's presentation to the job using ONLY the supplied evidence. You may
reorder, select, and clearly rephrase evidence, but never add a fact. Each tailored bullet
must cite one or more evidence_ids. Omit unsupported job keywords. Add a warning when a job
requirement has no supporting evidence. Keep the result concise and ATS-readable.

JOB:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description[:30000]}

VERIFIED EVIDENCE:
{evidence.model_dump_json(indent=2)}
"""
        tailored = self._structured(prompt, TailoredResume)
        valid_ids = {item.id for item in evidence.items}
        removed = 0
        for experience in tailored.experiences:
            valid_bullets = []
            for bullet in experience.bullets:
                if bullet.evidence_ids and set(bullet.evidence_ids).issubset(valid_ids):
                    valid_bullets.append(bullet)
                else:
                    removed += 1
            experience.bullets = valid_bullets
        if removed:
            tailored.warnings.append(
                f"Removed {removed} unsupported tailored bullet(s) during validation."
            )
        return tailored

    def chat(
        self,
        message: str,
        profile: CandidateProfile,
        answers: Iterable[ReusableAnswer],
        resume: ResumeDocument | None,
        job: JobContext | None,
        images: list[ChatImage] | None = None,
    ) -> ChatResponse:
        prompt = f"""
You are ApplyPilot, a concise job-application copilot. Answer the user's question using the
provided candidate and job context. Never invent candidate facts. Clearly label missing facts
and suggest a safe next action. Do not claim that a form was submitted or changed; chat is
advisory. Never request passwords, MFA codes, or CAPTCHA solutions. If images are attached,
inspect them as application context and mention uncertainty when text is unreadable.

CANDIDATE PROFILE:
{profile.model_dump_json(exclude={"custom_answers"}, indent=2)}

REUSABLE ANSWERS:
{[answer.model_dump(mode="json") for answer in answers]}

RESUME TEXT:
{resume.extracted_text[:20000] if resume else "No resume uploaded"}

ACTIVE JOB:
{job.model_dump_json(indent=2) if job else "No active job captured"}

USER MESSAGE:
{message}
"""
        return self._structured(prompt, ChatResponse, images or [])

    def _structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        images: list[ChatImage] | None = None,
    ) -> Any:
        raise NotImplementedError


class GeminiProvider(BaseAIProvider):
    def _structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        images: list[ChatImage] | None = None,
    ) -> Any:
        if not self.configured:
            raise AIProviderError("Gemini is not configured. Add an API key in ApplyPilot.")
        try:
            parts = [types.Part.from_text(text=prompt)]
            parts.extend(
                types.Part.from_bytes(
                    data=base64.b64decode(image.data_base64),
                    mime_type=image.media_type,
                )
                for image in images or []
            )
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            )
            if not response.text:
                raise AIProviderError("Gemini returned an empty response")
            return schema.model_validate_json(response.text)
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"Gemini request failed ({type(exc).__name__}).") from exc


class OpenAIProvider(BaseAIProvider):
    def _structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        images: list[ChatImage] | None = None,
    ) -> Any:
        if not self.configured:
            raise AIProviderError("OpenAI is not configured. Add an API key in ApplyPilot.")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        content.extend(
            {
                "type": "input_image",
                "detail": "auto",
                "image_url": f"data:{image.media_type};base64,{image.data_base64}",
            }
            for image in images or []
        )
        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema.__name__.lower(),
                    "schema": schema.model_json_schema(),
                    "strict": False,
                }
            },
            "store": False,
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            body = response.json()
            output_text = "".join(
                item.get("text", "")
                for output in body.get("output", [])
                for item in output.get("content", [])
                if item.get("type") == "output_text"
            )
            if not output_text:
                raise AIProviderError("OpenAI returned an empty response")
            return schema.model_validate_json(output_text)
        except AIProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(
                f"OpenAI rejected the request (HTTP {exc.response.status_code})."
            ) from exc
        except Exception as exc:
            raise AIProviderError(f"OpenAI request failed ({type(exc).__name__}).") from exc


class AnthropicProvider(BaseAIProvider):
    def _structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        images: list[ChatImage] | None = None,
    ) -> Any:
        if not self.configured:
            raise AIProviderError("Anthropic is not configured. Add an API key in ApplyPilot.")
        content: list[dict[str, Any]] = []
        content.extend(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": image.data_base64,
                },
            }
            for image in images or []
        )
        content.append({"type": "text", "text": prompt})
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
            "tools": [
                {
                    "name": "return_structured_result",
                    "description": "Return the requested ApplyPilot result.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": "return_structured_result"},
            "temperature": 0.2,
        }
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            body = response.json()
            tool_result = next(
                (
                    item.get("input")
                    for item in body.get("content", [])
                    if item.get("type") == "tool_use"
                    and item.get("name") == "return_structured_result"
                ),
                None,
            )
            if tool_result is None:
                raise AIProviderError("Anthropic returned an empty response")
            return schema.model_validate(tool_result)
        except AIProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(
                f"Anthropic rejected the request (HTTP {exc.response.status_code})."
            ) from exc
        except Exception as exc:
            raise AIProviderError(f"Anthropic request failed ({type(exc).__name__}).") from exc


def create_provider(config: ProviderConfigRequest) -> BaseAIProvider:
    providers = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }
    return providers[config.provider](config.api_key, config.model)


class AIProviderManager:
    def __init__(self, store: ProfileStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    def _configuration(self) -> tuple[ProviderConfigRequest, str]:
        local = self.store.get_provider_config()
        if local is not None:
            return local, "encrypted_local"
        keys = {
            "gemini": self.settings.gemini_api_key,
            "openai": self.settings.openai_api_key,
            "anthropic": self.settings.anthropic_api_key,
        }
        requested = self.settings.ai_provider if self.settings.ai_provider in keys else "gemini"
        provider = requested if keys[requested] else next(
            (name for name, value in keys.items() if value), requested
        )
        key = keys[provider]
        model = (
            self.settings.ai_model
            if provider == requested and self.settings.ai_model
            else DEFAULT_MODELS[provider]
        )
        return ProviderConfigRequest(provider=provider, api_key=key or "missing-key", model=model), (
            "environment" if key else "none"
        )

    def _provider(self) -> BaseAIProvider:
        config, source = self._configuration()
        if source == "none":
            config = config.model_copy(update={"api_key": ""})
        return create_provider(config)

    @property
    def configured(self) -> bool:
        _, source = self._configuration()
        return source != "none"

    def status(self) -> ProviderStatus:
        config, source = self._configuration()
        return ProviderStatus(
            provider=config.provider,
            model=config.model,
            configured=source != "none",
            source=source,
        )

    def configure(self, config: ProviderConfigRequest) -> ProviderStatus:
        self.store.save_provider_config(config)
        return self.status()

    def disconnect(self) -> ProviderStatus:
        self.store.delete_provider_config()
        return self.status()

    def extract_evidence(self, resume: ResumeDocument) -> ResumeEvidence:
        return self._provider().extract_evidence(resume)

    def tailor_resume(
        self, resume: ResumeDocument, job: JobContext, evidence: ResumeEvidence | None = None
    ) -> TailoredResume:
        return self._provider().tailor_resume(resume, job, evidence)

    def chat(
        self,
        message: str,
        profile: CandidateProfile,
        answers: Iterable[ReusableAnswer],
        resume: ResumeDocument | None,
        job: JobContext | None,
        images: list[ChatImage] | None = None,
    ) -> ChatResponse:
        return self._provider().chat(message, profile, answers, resume, job, images)

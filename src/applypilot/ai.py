from __future__ import annotations

from collections.abc import Iterable

from google import genai
from google.genai import types

from .models import (
    CandidateProfile,
    ChatResponse,
    JobContext,
    ResumeDocument,
    ResumeEvidence,
    ReusableAnswer,
    TailoredResume,
)


class AIProviderError(RuntimeError):
    pass


class GeminiProvider:
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
    ) -> ChatResponse:
        prompt = f"""
You are ApplyPilot, a concise job-application copilot. Answer the user's question using the
provided candidate and job context. Never invent candidate facts. Clearly label missing facts
and suggest a safe next action. Do not claim that a form was submitted or changed; chat is
advisory. Never request passwords, MFA codes, or CAPTCHA solutions.

CANDIDATE PROFILE:
{profile.model_dump_json(exclude={{"custom_answers"}}, indent=2)}

REUSABLE ANSWERS:
{[answer.model_dump(mode="json") for answer in answers]}

RESUME TEXT:
{resume.extracted_text[:20000] if resume else "No resume uploaded"}

ACTIVE JOB:
{job.model_dump_json(indent=2) if job else "No active job captured"}

USER MESSAGE:
{message}
"""
        return self._structured(prompt, ChatResponse)

    def _structured(self, prompt: str, schema):
        if not self.configured:
            raise AIProviderError(
                "Gemini is not configured. Add GEMINI_API_KEY to your local .env file."
            )
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
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
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

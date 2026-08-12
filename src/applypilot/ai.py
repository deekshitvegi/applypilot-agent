"""The model's job, and the fence around it.

A model here does two things: it puts a page into words, and it picks between
options that were scraped off that page. It never decides identity, never
decides whether to stop, never produces a value out of nothing, and never gets
to name a control.

Every answer that comes back is checked against live data before anything acts
on it. An answer that does not match something actually on the page is thrown
away with a reason, not repaired into something plausible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from .models import FieldObservation, Option, PageObservation
from .text import normalise

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT = 30.0


class ModelUnavailable(RuntimeError):
    """No key, no network, or the provider said no."""


@dataclass
class ModelReply:
    text: str
    used: bool = True
    reason: str = ""


class Model:
    """A thin client. Deliberately thin: nothing here is trusted."""

    def __init__(self, api_key: str = "", name: str = "gemini-3.5-flash-lite") -> None:
        self.api_key = (api_key or "").strip()
        self.name = name

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def ask(self, prompt: str, *, temperature: float = 0.1) -> str:
        if not self.available:
            raise ModelUnavailable("no API key has been entered in Settings yet")
        url = GEMINI_ENDPOINT.format(model=self.name)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 800},
        }
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    url, params={"key": self.api_key}, json=payload
                )
        except httpx.HTTPError as exc:
            raise ModelUnavailable(f"could not reach the model: {exc}") from exc
        if response.status_code == 429:
            # Rate limiting is not a broken key, and saying so sends people to
            # Settings to fix something that is not wrong.
            raise ModelUnavailable(
                "the model is busy right now (rate limited); matching still works"
            )
        if response.status_code in {401, 403}:
            raise ModelUnavailable("the model provider rejected the key; check it in Settings")
        if response.status_code >= 400:
            raise ModelUnavailable(f"the model provider returned {response.status_code}")
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            raise ModelUnavailable("the model returned nothing usable") from None


# ---------------------------------------------------------------------------
# Validation. Nothing below trusts what came back.
# ---------------------------------------------------------------------------


def validate_option(raw: str, options: list[Option]) -> Option | None:
    """Accept a choice only if it is one of the options the page offered.

    Not a close spelling, not a repaired version -- one of them.
    """
    wanted = normalise(raw or "")
    if not wanted:
        return None
    for option in options:
        if normalise(option.label) == wanted:
            return option
    return None


def validate_fingerprint(raw: str, fields: list[FieldObservation]) -> FieldObservation | None:
    """Accept a control reference only if that control is on the page now."""
    for observed in fields:
        if observed.fingerprint == (raw or "").strip():
            return observed
    return None


def parse_json_object(text: str) -> dict:
    """Pull a JSON object out of a reply, tolerating fenced code blocks."""
    body = (text or "").strip()
    if body.startswith("```"):
        body = body.strip("`")
        _, _, body = body.partition("\n")
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ---------------------------------------------------------------------------
# The two things a model is asked to do
# ---------------------------------------------------------------------------

_CHOICE_PROMPT = """\
A job application asks this question:

  {question}

The employer offers exactly these options, numbered:

{options}

The applicant's saved answer to this kind of question is: {saved}

Reply with a JSON object: {{"option": "<the exact text of one option above>", \
"confidence": <0 to 1>, "why": "<one short sentence>"}}
If none of the options is a fair match for the saved answer, reply with \
{{"option": null, "why": "<why not>"}}. Do not invent an option.
"""


async def choose_among(
    model: Model, question: str, options: list[Option], saved_answer: str
) -> tuple[Option | None, str]:
    """Ask which of the page's own options fits. The reply is then checked."""
    if not options:
        return None, "the control offered no options to choose between"
    listing = "\n".join(f"  {i + 1}. {o.label}" for i, o in enumerate(options))
    prompt = _CHOICE_PROMPT.format(
        question=question, options=listing, saved=saved_answer or "(nothing saved)"
    )
    reply = await model.ask(prompt)
    parsed = parse_json_object(reply)
    chosen = validate_option(str(parsed.get("option") or ""), options)
    if chosen is None:
        return None, (
            str(parsed.get("why") or "the model did not name one of the options offered here")
        )
    return chosen, str(parsed.get("why") or "")


_DESCRIBE_PROMPT = """\
Describe this page in two sentences for someone filling in a job application.
Say what the page appears to be and what it is asking for. Do not give advice, \
do not say what to click, and do not guess at anything that is not listed.

URL: {url}
Title: {title}
Detected as: {kind}
Fields on the page:
{fields}
"""


async def describe_page(model: Model, observation: PageObservation) -> str:
    """Words for the panel. Never a decision."""
    listing = "\n".join(
        f"  - {f.display_label or f.attr_label} ({f.control.value})"
        for f in observation.fields[:40]
    ) or "  (none)"
    prompt = _DESCRIBE_PROMPT.format(
        url=observation.url,
        title=observation.title,
        kind=observation.kind.value,
        fields=listing,
    )
    return await model.ask(prompt, temperature=0.3)


#: How much of a history to put in front of the model. Enough to answer "do you
#: have experience with X", short enough that the question stays the subject.
_EVIDENCE_JOBS = 6
_EVIDENCE_BULLETS = 4


def evidence_from(profile) -> str:
    """What the applicant has actually done, in plain lines.

    Only what is written down. Nothing here is generated, summarised into a
    claim, or rounded up: a model that cannot find something in these lines is
    required to say so rather than answer anyway.
    """
    lines: list[str] = []
    if profile.skills:
        lines.append("Skills listed: " + ", ".join(profile.skills[:40]))
    for record in profile.education[:4]:
        said = " in ".join(p for p in (record.degree, record.field_of_study) if p)
        where = f" at {record.school}" if record.school else ""
        when = f" ({record.start_date}-{record.end_date})" if record.end_date else ""
        if said or where:
            lines.append(f"Education: {said}{where}{when}".strip())
    for record in profile.experience[:_EVIDENCE_JOBS]:
        when = f"{record.start_date} to {record.end_date or 'now'}"
        lines.append(f"Role: {record.title or '?'} at {record.company or '?'} ({when})")
        for bullet in (record.description or "").splitlines()[:_EVIDENCE_BULLETS]:
            cleaned = bullet.strip().lstrip("-*• \t")
            if cleaned:
                lines.append(f"  - {cleaned}")
    return "\n".join(lines) or "(nothing recorded)"


_FROM_EVIDENCE_PROMPT = """\
A job application asks this question:

  {question}

The employer offers exactly these options, numbered:

{options}

Everything known about the applicant, taken from what they wrote down:

{evidence}

Answer ONLY from those lines. They are the whole of what is known.

If a line supports an answer, reply with a JSON object:
  {{"option": "<exact text of one option above>", "quote": "<the line that \
supports it, copied exactly>", "why": "<one short sentence>"}}

If nothing in those lines settles it -- including anything about how many \
years, which tools, where they live, or what they are willing to do -- reply \
{{"option": null, "why": "<what is missing>"}}.

Do not infer, do not estimate, do not answer from what is usual for someone \
with this background, and do not invent an option. A wrong answer here goes on \
a real job application in the applicant's name.
"""


async def answer_from_evidence(
    model: Model, question: str, options: list[Option], evidence: str
) -> tuple[Option | None, str]:
    """Answer a question about the applicant, from what the applicant wrote.

    This is not the model deciding anything about them. It is the model reading
    lines they wrote and saying which of the employer's own options those lines
    support -- and being made to quote the line, so a claim with nothing behind
    it is visible rather than merely plausible.
    """
    if not options:
        return None, "the control offered no options to choose between"
    listing = "\n".join(f"  {i + 1}. {o.label}" for i, o in enumerate(options))
    prompt = _FROM_EVIDENCE_PROMPT.format(
        question=question, options=listing, evidence=evidence
    )
    reply = await model.ask(prompt)
    parsed = parse_json_object(reply)
    chosen = validate_option(str(parsed.get("option") or ""), options)
    if chosen is None:
        return None, str(parsed.get("why") or "nothing you have written answers this")

    # A quote that is not in the evidence is not a quote. Without this the
    # grounding is a request rather than a rule.
    quote = str(parsed.get("quote") or "").strip()
    if not quote or normalise(quote)[:60] not in normalise(evidence):
        return None, "the model could not point at anything you wrote that says so"
    return chosen, f"from your own history: {quote[:120]}"

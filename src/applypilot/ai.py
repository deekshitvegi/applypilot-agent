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
import re
from dataclasses import dataclass
from datetime import date

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


#: The number this file puts in front of each option when it lists them. A
#: model that answers "1. Yes" is naming the first option, not inventing one --
#: it is reading back the format it was given. Undoing our own numbering is not
#: loosening the check below; leaving it in place rejected every correct answer
#: the model gave, and read as a refusal while the reasoning said the opposite.
_ENUMERATOR = re.compile(r"^\s*\(?\d{1,2}\)?\s*[.):-]\s*")


def validate_option(raw: str, options: list[Option]) -> Option | None:
    """Accept a choice only if it is one of the options the page offered.

    Not a close spelling, not a repaired version -- one of them.
    """
    wanted = normalise(_ENUMERATOR.sub("", raw or ""))
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

    # Where they are, and what they may do about it.
    #
    # This was missing, and it is the thing half these questions turn on. "Are
    # you based in a US or equivalent timezone?" is settled by an address the
    # profile already holds; without it the model had nothing and correctly
    # refused, on a question the applicant would call obvious.
    address = (profile.fact("city"), profile.fact("state"), profile.fact("country"))
    where = ", ".join(part for part in address if part)
    if where:
        lines.append(f"Lives in: {where}")
    for key, said in (
        ("work_authorization", "Legally authorised to work in the country of the role"),
        ("requires_sponsorship", "Requires visa sponsorship"),
        ("citizenship", "Citizenship"),
        ("willing_to_relocate", "Willing to relocate"),
        ("work_arrangement", "Preferred work arrangement"),
        ("notice_period", "Can start"),
        ("willing_to_travel", "Willing to travel"),
        ("highest_education", "Highest level of education"),
    ):
        value = profile.fact(key)
        if value:
            lines.append(f"{said}: {value}")

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
    if not lines:
        return "(nothing recorded)"

    # What "now" means, at the top, and only where there is something for it to
    # date. Every role reads "Jun 2025 to now", and a model has no way to date
    # "now": asked how many years of experience someone had, it answered "0-1"
    # for somebody with two years of it -- not a guess it should have made, and
    # not one it could have got right either. The date is a fact about the
    # world, like a city sitting in a country, and it is what the arithmetic
    # needs. It is not evidence about the applicant, so an empty profile is
    # still empty.
    return "\n".join([f"Today's date: {date.today():%d %B %Y}", *lines])


_FROM_EVIDENCE_PROMPT = """\
A job application asks this question:

  {question}

The employer offers exactly these options, numbered:

{options}

Everything known about the applicant, taken from what they wrote down:

{evidence}

Every fact about this applicant must come from those lines. They are the whole
of what is known about them.

You may use ordinary knowledge about the world to connect a line to the
question -- that New York City is in the United States, that Texas is in the
United States, that a master's degree is above a bachelor's. Common knowledge
may join up what they wrote with what is being asked.
Common knowledge may never supply a fact about them that they did not write.

  - "Lives in: Denton, Texas" + asked whether they live in the US -> yes, \
because Texas is in the US.
  - "Willing to work onsite anywhere in the US" + asked about an office in \
Boston -> yes, because Boston is in the US.
  - "Role: Engineer (2022 to now)" + asked for five years of experience -> \
NOT enough. Their years are a fact about them.
  - Nothing about a tool + asked whether they know it -> NOT enough, however \
usual it would be for this background.

If a line settles it, reply with a JSON object:
  {{"option": "<exact text of one option above>", "quote": "<the line that \
supports it, copied exactly>", "why": "<one short sentence>"}}

If nothing in those lines settles it, reply \
{{"option": null, "why": "<what is missing>"}}.

Employers dress these questions up. "Are you excited and able to work from our
Boston office?", "Are you passionate about working onsite?" and "Can you work
from our Boston office?" are the same question, and a stated willingness
answers all three -- do not refuse because enthusiasm itself was not written
down. But if the lines contradict what is being asked -- they will only work
remotely, and the question is about being in an office -- say so by answering
honestly, not by picking the agreeable option.

Never guess: do not estimate, do not round up, and do not invent an option.
A wrong answer here goes on a real job application in the applicant's name.
"""


#: Words that carry no subject. A quote sharing only these with a question has
#: not been shown to be about it.
_EMPTY_WORDS = frozenset(
    {
        "the", "and", "for", "you", "your", "are", "have", "has", "had", "with",
        "this", "that", "there", "any", "all", "our", "their", "his", "her",
        "will", "would", "can", "could", "should", "may", "might", "must",
        "was", "were", "been", "being", "does", "did", "doing", "not", "but",
        "from", "into", "onto", "than", "then", "when", "where", "which",
        "who", "whom", "whose", "what", "why", "how", "about", "above",
        "other", "others", "such", "some", "most", "more", "very", "please",
        "select", "choose", "answer", "question", "yes", "role", "roles",
        "work", "working", "worked", "job", "jobs", "position", "positions",
        "experience", "experiences", "years", "year", "level", "using", "use",
        "used", "able", "willing", "currently", "current", "now", "future",
        "applicant", "candidate", "company", "team", "office", "based",
    }
)


def _subjects(text: str) -> set[str]:
    """The words in *text* that name something in particular.

    Four characters and up. Three lets "per" through, which is a substring of
    "experience" and matched a question about days per week to a line about
    years of it.
    """
    return {
        word
        for word in re.findall(r"[a-z0-9+#.]{4,}", (text or "").lower())
        if word not in _EMPTY_WORDS
    }


#: Endings that make the same subject a different word. A plain prefix rule is
#: not enough: it makes "timezone" the same subject as "time", which appears in
#: half the job descriptions ever written, and a question about a timezone then
#: has to be answered by a line about something else entirely.
_ENDINGS = frozenset(
    {
        "s", "es", "d", "ed", "ing", "ion", "ions", "ship", "ships", "ment",
        "ments", "al", "ance", "ence", "ity", "ies", "er", "ers", "or", "ors",
    }
)


def _same_subject(word: str, others: set[str]) -> bool:
    """True when *word* names the same thing as one of *others*.

    "sponsor" and "sponsorship" are one subject; so are "require" and
    "requires". A question that says sponsor against a line that says
    sponsorship is the commonest shape there is, and refusing it would throw
    away most of what this check is meant to let through.
    """
    for other in others:
        if word == other:
            return True
        longer, shorter = (other, word) if len(other) > len(word) else (word, other)
        if longer.startswith(shorter) and longer[len(shorter) :] in _ENDINGS:
            return True
    return False


def _quote_bears_on(question: str, quote: str, evidence: str) -> bool:
    """False when the quoted line says nothing about what was asked.

    A quote used to be checked for existing and nothing more, which is a weaker
    rule than it reads as. Asked whether the applicant had built and deployed
    production applications in React and TypeScript, the model answered yes and
    quoted a line reading "Role: Software Developer Intern at Josh Innovations
    (Jun 2021 to Oct 2021)". Real line, real dates, no React in it -- a
    qualification claimed on a required question with nothing behind it.

    The test is deliberately narrow. The question's own subjects are found, and
    only those that appear somewhere in the evidence are used: a question about
    a timezone, whose words appear nowhere in a profile, cannot be settled this
    way and is left to the rules above. But when the evidence does talk about
    what the question names, the quoted line has to be one of the places it
    does.
    """
    asked = _subjects(question)
    if not asked:
        return True
    in_evidence = _subjects(evidence)
    known = {word for word in asked if _same_subject(word, in_evidence)}
    if not known:
        # Nothing the question names is written down anywhere. Whatever settled
        # this, it was not a subject match, and inventing one here would refuse
        # sound answers about where someone lives.
        return True
    quoted = _subjects(quote)
    return any(_same_subject(word, quoted) for word in known)


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
    said = str(parsed.get("option") or "").strip()
    chosen = validate_option(said, options)
    if chosen is None:
        why = str(parsed.get("why") or "nothing you have written answers this")
        # Say what it named, when it named something. A reply the page has no
        # option for is a different problem from a reply that declined, and
        # they were indistinguishable -- both came back as the model's own
        # sentence, which read like a refusal even when it was an answer.
        if said:
            return None, f'the model answered "{said[:40]}", which this control does not offer'
        return None, why

    # A quote that is not in the evidence is not a quote. Without this the
    # grounding is a request rather than a rule.
    quote = str(parsed.get("quote") or "").strip()
    if not quote or normalise(quote)[:60] not in normalise(evidence):
        return None, "the model could not point at anything you wrote that says so"
    if not _quote_bears_on(question, quote, evidence):
        return None, (
            "the line the model quoted does not mention what the question asks about"
        )
    return chosen, f"from your own history: {quote[:120]}"

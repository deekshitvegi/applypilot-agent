"""Asking once, so nothing has to be asked again.

An empty profile is the state that produces "why does it keep asking me the same
legal questions": every form asks about work authorisation, sponsorship, age and
consent, and with nothing saved every form asks again. So this runs first.

Onboarding never invents an answer. A resume prefills what it stated and nothing
more; everything else is a question with the applicant's own words as the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from .facts import BY_KEY, FACTS, FactSpec, Sensitivity
from .models import Profile
from .resume import ResumeExtract

#: The order the questions are asked in. Identity first because it is the
#: easiest, legal questions next because they are the ones that keep recurring.
GROUP_ORDER: tuple[str, ...] = (
    "identity",
    "contact",
    "address",
    "eligibility",
    "preferences",
    "links",
    "voluntary",
    "documents",
)

GROUP_TITLES: dict[str, str] = {
    "identity": "Who you are",
    "contact": "How to reach you",
    "address": "Where you live",
    "eligibility": "The legal questions every form asks",
    "preferences": "What you are looking for",
    "links": "Profiles and portfolio",
    "voluntary": "Voluntary questions (you can skip all of these)",
    "documents": "Your resume",
}

GROUP_NOTES: dict[str, str] = {
    "eligibility": (
        "Answer these once and no application should ask you again. They are the "
        "questions that come up on nearly every form."
    ),
    "voluntary": (
        "These are optional on every application and always have a "
        '"prefer not to answer" choice. Nothing here is filled in for you unless '
        "you turn that on."
    ),
}


@dataclass
class Step:
    key: str
    prompt: str
    kind: str
    group: str
    group_title: str
    choices: tuple[str, ...] = ()
    value: str = ""
    answered: bool = False
    optional: bool = False
    help_text: str = ""
    prefilled_from: str = ""


@dataclass
class Onboarding:
    steps: list[Step] = dataclass_field(default_factory=list)
    answered: int = 0
    total: int = 0
    notes: list[str] = dataclass_field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all(step.answered or step.optional for step in self.steps)

    @property
    def next_step(self) -> Step | None:
        """The next thing worth asking.

        Everything that matters comes first. Setup stalling on "Middle name"
        while work authorisation is still unanswered is the wrong order, and
        optional questions are only offered once the rest are done.
        """
        needed = next(
            (s for s in self.steps if not s.answered and not s.optional), None
        )
        if needed is not None:
            return needed
        return next((s for s in self.steps if not s.answered), None)

    @property
    def required_remaining(self) -> int:
        return sum(1 for s in self.steps if not s.answered and not s.optional)

    @property
    def remaining(self) -> list[Step]:
        return [step for step in self.steps if not step.answered]


def _asked_specs() -> list[FactSpec]:
    """Facts worth asking about up front, in group order."""
    by_group: dict[str, list[FactSpec]] = {}
    for spec in FACTS:
        if not spec.onboarding_group:
            continue
        by_group.setdefault(spec.onboarding_group, []).append(spec)
    ordered: list[FactSpec] = []
    for group in GROUP_ORDER:
        ordered.extend(by_group.get(group, []))
    return ordered


def build(profile: Profile, prefilled: dict[str, str] | None = None) -> Onboarding:
    """The whole questionnaire, with what is already known marked as answered."""
    prefilled = prefilled or {}
    steps: list[Step] = []
    for spec in _asked_specs():
        value = profile.fact(spec.key) or prefilled.get(spec.key, "")
        steps.append(
            Step(
                key=spec.key,
                prompt=spec.prompt or spec.key.replace("_", " ").title(),
                kind=spec.kind,
                group=spec.onboarding_group,
                group_title=GROUP_TITLES.get(spec.onboarding_group, spec.onboarding_group),
                choices=spec.choices,
                value=value,
                answered=bool(value),
                optional=spec.supplementary or spec.sensitivity is Sensitivity.DEMOGRAPHIC,
                help_text=spec.help_text,
                prefilled_from=(
                    "resume" if spec.key in prefilled and not profile.fact(spec.key) else ""
                ),
            )
        )

    result = Onboarding(
        steps=steps,
        answered=sum(1 for step in steps if step.answered),
        total=len(steps),
    )
    for group, note in GROUP_NOTES.items():
        if any(step.group == group and not step.answered for step in steps):
            result.notes.append(note)
    if not profile.education:
        result.notes.append("No education entries yet -- upload your resume or add one by hand.")
    if not profile.experience:
        result.notes.append("No work history yet -- upload your resume or add one by hand.")
    return result


def apply_resume(profile: Profile, extracted: ResumeExtract) -> tuple[Profile, list[str]]:
    """Fold what a resume stated into the profile without overwriting anything.

    A value already in the profile came from the applicant and wins. A value the
    document did not state stays missing rather than being guessed at.
    """
    added: list[str] = []
    for key, value in extracted.as_facts().items():
        if not value or profile.fact(key):
            continue
        profile.facts[key] = value
        spec = BY_KEY.get(key)
        added.append(spec.prompt if spec and spec.prompt else key)

    if extracted.education and not profile.education:
        profile.education = list(extracted.education)
        added.append(f"{len(extracted.education)} education entries")
    if extracted.experience and not profile.experience:
        profile.experience = list(extracted.experience)
        added.append(f"{len(extracted.experience)} work history entries")
    if extracted.skills and not profile.skills:
        profile.skills = list(extracted.skills)
        added.append(f"{len(extracted.skills)} skills")

    return profile, added


def answer(profile: Profile, key: str, value: str) -> Profile:
    """Record one answer. An empty value clears it rather than storing blank."""
    cleaned = (value or "").strip()
    if cleaned:
        profile.facts[key] = cleaned
    else:
        profile.facts.pop(key, None)
    return profile


def missing_for_applications(profile: Profile) -> list[str]:
    """The answers whose absence will stall a form, in plain language."""
    essential = (
        "full_name", "email", "phone", "street_address", "city", "state",
        "postal_code", "country", "work_authorization", "requires_sponsorship",
        "over_18", "background_check_consent",
    )
    missing = []
    for key in essential:
        if not profile.fact(key):
            spec = BY_KEY.get(key)
            missing.append(spec.prompt if spec and spec.prompt else key)
    return missing

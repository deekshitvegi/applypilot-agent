"""Turning what the applicant types into something that happens on the page.

An explicit instruction about a field that is visible has to end in one of three
things: a scoped action on that field, a card of choices to pick from, or one
focused question. Never a paragraph explaining what could be done.

The parsing is deterministic. A model is a last resort for wording, and even
then it only ever gets to pick among options already scraped off the page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from .facts import BY_KEY, FACTS, alias_variants
from .mapper import best_fact
from .matching import best_option, rank_options
from .models import (
    CHOICE_CONTROLS,
    ControlKind,
    FieldObservation,
    Option,
    PlannedAction,
    Profile,
)
from .text import normalise, tokens

_LAST_ANSWER = re.compile(
    r"^(?:change|set|make|update|fix)\s+(?:my\s+)?(?:the\s+)?last\s+(?:answer|one|field|reply)"
    r"(?:\s+(?:to|as|=))?\s+(?P<value>.+)$",
    re.IGNORECASE,
)
_SET_FIELD = re.compile(
    r"^(?:change|set|make|update|fix|put|use|answer)\s+(?:my\s+|the\s+)?(?P<rest>.+)$",
    re.IGNORECASE,
)
_TO_VALUE = re.compile(r"^(?P<label>.+?)\s+(?:to|as|=|:)\s+(?P<value>.+)$", re.IGNORECASE)
_YES_NO = re.compile(r"^(yes|no|y|n)$", re.IGNORECASE)
_STOP = re.compile(r"^(stop|pause|halt|wait|cancel)\b", re.IGNORECASE)
_SKIP = re.compile(r"^(skip|leave (it )?blank|ignore (it|this))\b", re.IGNORECASE)


@dataclass
class ChatOutcome:
    """What the instruction turned into."""

    kind: str  # "action" | "choices" | "clarify" | "control" | "talk"
    message: str = ""
    action: PlannedAction | None = None
    fingerprint: str = ""
    label: str = ""
    value: str = ""
    fact_key: str = ""
    options: list[Option] = dataclass_field(default_factory=list)
    remember: bool = True

    @property
    def is_scoped(self) -> bool:
        return self.kind in {"action", "choices", "clarify"}


def _live_label(observed: FieldObservation) -> str:
    return observed.display_label or observed.attr_label


def _find_field(label: str, fields: list[FieldObservation]) -> FieldObservation | None:
    """Find the control the applicant means, by its visible label."""
    wanted = normalise(label)
    if not wanted:
        return None

    for observed in fields:
        if normalise(_live_label(observed)) == wanted:
            return observed

    # Then by the fact the words name: "state" reaches a control labelled
    # "State / Province" without anyone having to type that.
    probe = FieldObservation(fingerprint="probe", label=label, control=ControlKind.TEXT)
    match = best_fact(probe)
    if match is not None:
        for observed in fields:
            found = best_fact(observed)
            if found is not None and found.spec.key == match.spec.key:
                return observed

    wanted_tokens = set(tokens(wanted))
    scored = [
        (len(wanted_tokens & set(tokens(_live_label(observed)))), observed)
        for observed in fields
        if _live_label(observed)
    ]
    scored = [(score, observed) for score, observed in scored if score == len(wanted_tokens) > 0]
    if len(scored) == 1:
        return scored[0][1]
    return None


def _fact_for_words(label: str) -> str:
    wanted = normalise(label)
    for spec in FACTS:
        if any(normalise(alias) == wanted for alias in alias_variants(spec)):
            return spec.key
    probe = FieldObservation(fingerprint="probe", label=label, control=ControlKind.TEXT)
    match = best_fact(probe)
    return match.spec.key if match else ""


def _act_on(observed: FieldObservation, value: str) -> ChatOutcome:
    """Turn a field and a value into one action, a choice card, or a question."""
    label = _live_label(observed)
    fact_key = ""
    match = best_fact(observed)
    if match is not None:
        fact_key = match.spec.key

    if observed.control in CHOICE_CONTROLS and observed.options:
        chosen = best_option(value, observed.options, fact_key)
        if chosen is not None:
            return ChatOutcome(
                kind="action",
                fingerprint=observed.fingerprint,
                label=label,
                value=chosen.option.label,
                fact_key=fact_key,
                message=f'Setting "{label}" to "{chosen.option.label}".',
                action=PlannedAction(
                    kind="choose",
                    fingerprint=observed.fingerprint,
                    option_label=chosen.option.label,
                    value=chosen.option.label,
                    reason="you asked for this directly",
                ),
            )
        ranked = rank_options(value, observed.options, fact_key)
        shortlist = [m.option for m in ranked[:6]] or observed.options[:8]
        return ChatOutcome(
            kind="choices",
            fingerprint=observed.fingerprint,
            label=label,
            value=value,
            fact_key=fact_key,
            options=shortlist,
            message=f'"{label}" does not offer "{value}". Which of these do you mean?',
        )

    if observed.control is ControlKind.CHECKBOX:
        wanted = normalise(value) in {"yes", "true", "on", "1", "checked", "tick"}
        return ChatOutcome(
            kind="action",
            fingerprint=observed.fingerprint,
            label=label,
            value="Yes" if wanted else "No",
            fact_key=fact_key,
            message=f'{"Ticking" if wanted else "Unticking"} "{label}".',
            action=PlannedAction(
                kind="check",
                fingerprint=observed.fingerprint,
                value="Yes" if wanted else "No",
                reason="you asked for this directly",
            ),
        )

    if observed.control is ControlKind.FILE:
        return ChatOutcome(
            kind="clarify",
            fingerprint=observed.fingerprint,
            label=label,
            message=f'"{label}" takes a file. Pick which of your documents to attach.',
        )

    return ChatOutcome(
        kind="action",
        fingerprint=observed.fingerprint,
        label=label,
        value=value,
        fact_key=fact_key,
        message=f'Setting "{label}" to "{value}".',
        action=PlannedAction(
            kind="fill",
            fingerprint=observed.fingerprint,
            value=value,
            reason="you asked for this directly",
        ),
    )


def interpret(
    text: str,
    fields: list[FieldObservation],
    *,
    profile: Profile | None = None,
    last_fingerprint: str = "",
    pending_fingerprint: str = "",
) -> ChatOutcome:
    """Read one instruction. An instruction about a visible field always acts."""
    said = (text or "").strip()
    if not said:
        return ChatOutcome(kind="talk", message="")

    if _STOP.match(said):
        return ChatOutcome(kind="control", message="Stopped.", value="stop", remember=False)

    by_fingerprint = {f.fingerprint: f for f in fields}

    if _SKIP.match(said) and pending_fingerprint in by_fingerprint:
        observed = by_fingerprint[pending_fingerprint]
        return ChatOutcome(
            kind="control",
            fingerprint=pending_fingerprint,
            label=_live_label(observed),
            value="skip",
            message=f'Leaving "{_live_label(observed)}" blank.',
            remember=False,
        )

    # "change my last answer to No"
    last = _LAST_ANSWER.match(said)
    if last:
        target = by_fingerprint.get(last_fingerprint)
        if target is None:
            return ChatOutcome(
                kind="clarify",
                message="I have not filled anything on this page yet. Which field do you mean?",
            )
        return _act_on(target, last.group("value").strip().strip('."'))

    # A bare yes or no answers whatever is being asked right now.
    if _YES_NO.match(said) and pending_fingerprint in by_fingerprint:
        value = "Yes" if said.lower().startswith("y") else "No"
        return _act_on(by_fingerprint[pending_fingerprint], value)

    body = said
    lead = _SET_FIELD.match(said)
    if lead:
        body = lead.group("rest").strip()

    # "state to Texas" / "middle name: Kumar"
    explicit = _TO_VALUE.match(body)
    candidates: list[tuple[str, str]] = []
    if explicit:
        candidates.append((explicit.group("label"), explicit.group("value")))

    # "state texas" -- try the longest leading phrase that names a field.
    words = body.split()
    for cut in range(min(len(words) - 1, 5), 0, -1):
        candidates.append((" ".join(words[:cut]), " ".join(words[cut:])))

    for label, value in candidates:
        value = value.strip().strip('."')
        if not value:
            continue
        observed = _find_field(label, fields)
        if observed is not None:
            return _act_on(observed, value)

    # The words name a fact but nothing on this page asks for it.
    for label, value in candidates:
        fact_key = _fact_for_words(label)
        if fact_key:
            spec = BY_KEY[fact_key]
            return ChatOutcome(
                kind="control",
                value=value.strip(),
                fact_key=fact_key,
                label=spec.prompt or fact_key,
                message=(
                    f'Nothing on this page asks for {spec.prompt or fact_key}. '
                    f'Saved "{value.strip()}" for next time.'
                ),
            )

    if len(fields) == 0:
        return ChatOutcome(
            kind="talk",
            message="There is no form on this page for me to change anything on.",
        )

    return ChatOutcome(
        kind="clarify",
        message=(
            f'I could not tell which field you mean by "{said}". '
            "Give me the label as it appears on the page, or click the field in the checklist."
        ),
    )

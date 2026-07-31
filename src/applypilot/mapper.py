"""Deciding which saved fact, if any, answers a field on the page.

The mapper is deliberately hard to satisfy. It would rather hand a question back
to the applicant than put a plausible-looking value in the wrong box, because
every entry on the regression list started life as a plausible-looking value.

The rules, all structural:

* Only the **visible label** is reasoned about. A page that names its State
  field ``countryRegion`` gets no vote.
* An alias must line up with the label as a whole phrase -- as the label, as the
  label's opening followed by a qualifier, or as the label's ending behind
  nothing but filler. "Position" does not answer "Position Location".
* The most specific subject in a label wins it. A question carrying the word
  "sponsorship" belongs to sponsorship, never to the "country" it also mentions.
* A modifier makes a different field. "Home Phone" is not "Phone".
* A trailing digit makes a different field. "Address Line 1" is not "Line 2".
* Structured history answers only inside a history block, or behind a label that
  can mean nothing else.
* A follow-up question is never inferred -- but an answer given to that exact
  question before is used.
"""

from __future__ import annotations

from dataclasses import dataclass

from .facts import (
    BY_KEY,
    DEMOGRAPHIC_KEYS,
    FACTS,
    HISTORY_ONLY_LABELS,
    SUPPLEMENTARY_LABELS,
    TOPIC_OWNERS,
    FactScope,
    FactSpec,
    alias_variants,
)
from .matching import best_option
from .models import (
    CHOICE_CONTROLS,
    Answer,
    AnswerSource,
    ControlKind,
    FieldObservation,
    PendingQuestion,
    Profile,
)
from .text import (
    CONNECTORS,
    DISTINGUISHING_MODIFIERS,
    NEUTRAL_QUALIFIERS,
    STOPWORDS,
    alternatives,
    content_tokens,
    has_question_shape,
    is_conditional,
    leading_phrase_remainder,
    normalise,
    numeric_suffix,
    tokens,
    trailing_phrase_prefix,
)

#: How specific a subject word is. When a label mentions several subjects, only
#: the most specific one gets to own the label. This is what stops a saved
#: "Country" answering a sponsorship question that happens to say "country".
TOPIC_RANK: dict[str, int] = {
    # Generic attributes of a person -- easily mentioned in passing.
    "country": 1, "state": 1, "province": 1, "city": 1, "zip": 1,
    "postal": 1, "postcode": 1, "address": 1, "street": 1,
    # Named things.
    "email": 2, "phone": 2, "telephone": 2, "mobile": 2, "degree": 2,
    "major": 2, "discipline": 2, "study": 2, "school": 2, "university": 2,
    "college": 2, "institution": 2, "employer": 2, "organization": 2,
    "organisation": 2, "title": 2, "notice": 2, "start": 2, "resume": 2,
    "cv": 2, "cover": 2, "linkedin": 2, "github": 2, "portfolio": 2,
    "website": 2, "referral": 2, "hear": 2, "source": 2, "pay": 2,
    "rate": 2, "wage": 2, "18": 2, "age": 2, "before": 2,
    "previously": 2, "formerly": 2, "remote": 2, "onsite": 2, "hybrid": 2,
    # Subjects that dominate any sentence they appear in.
    "sponsorship": 3, "sponsor": 3, "visa": 3, "immigration": 3, "h1b": 3,
    "authorized": 3, "authorised": 3, "authorization": 3, "authorisation": 3,
    "eligible": 3, "eligibility": 3, "veteran": 3, "military": 3,
    "disability": 3, "disabled": 3, "race": 3, "ethnicity": 3, "ethnic": 3,
    "hispanic": 3, "latino": 3, "gender": 3, "clearance": 3, "drug": 3,
    "background": 3, "relocate": 3, "relocation": 3, "salary": 3,
    "compensation": 3, "gpa": 3, "citizenship": 3, "citizen": 3,
    "nationality": 3,
}

#: Headings that mark a block as being about one education or employment entry.
_HISTORY_SECTION_WORDS = frozenset(
    {
        "education", "educational", "school", "schools", "academic", "degree",
        "degrees", "qualification", "qualifications", "experience", "employment",
        "work", "history", "job", "jobs", "position", "positions", "career",
        "professional",
    }
)

SCORE_EXACT = 100
SCORE_SAME_WORDS = 98
SCORE_LEADING_EXACT = 96
SCORE_LEADING_QUALIFIED = 90
SCORE_TRAILING_FILLER = 88
#: A sentence question owned by this fact's own subject. Lower than every
#: phrase rule, because a sentence has room to be about something else.
SCORE_QUESTION_TOPIC = 76
#: Attribute-derived labels get one narrow path in and a visible confidence hit.
SCORE_ATTRIBUTE_EXACT = 55

MIN_SCORE = 50


@dataclass(frozen=True)
class FactMatch:
    spec: FactSpec
    score: int
    alias: str
    reason: str

    @property
    def confidence(self) -> float:
        return min(1.0, self.score / 100.0)


def _winning_topics(label: str) -> frozenset[str]:
    """The most specific subject words present in *label*."""
    present = {t: TOPIC_RANK.get(t, 1) for t in tokens(label) if t in TOPIC_OWNERS}
    if not present:
        return frozenset()
    top = max(present.values())
    return frozenset(t for t, rank in present.items() if rank == top)


def _topic_conflict(spec: FactSpec, label: str) -> str:
    winners = _winning_topics(label)
    if not winners:
        return ""
    for topic in winners:
        if spec.key in TOPIC_OWNERS.get(topic, frozenset()):
            return ""
    owner_names = ", ".join(sorted(winners))
    return f"the label is about {owner_names}"


#: Words that modify a field name but are ordinary verbs and nouns inside a
#: sentence. "Work Phone" is a different field from "Phone"; "authorized to
#: work" is not a different kind of anything.
_AMBIGUOUS_IN_SENTENCES = frozenset(
    {"work", "business", "office", "next", "second", "other", "partner", "parent"}
)


def _modifier_conflict(alias: str, label: str, *, sentence: bool = False) -> str:
    label_words = set(tokens(label))
    alias_words = set(tokens(alias))
    guarded = DISTINGUISHING_MODIFIERS
    if sentence:
        guarded = guarded - _AMBIGUOUS_IN_SENTENCES
    stray = (label_words & guarded) - alias_words
    if stray:
        return f"the label says {', '.join(sorted(stray))}, which makes it a different field"
    return ""


def _digit_conflict(alias: str, label: str) -> str:
    label_digits = numeric_suffix(label)
    alias_digits = numeric_suffix(alias)
    if label_digits != alias_digits:
        return "the trailing number differs, so these are different fields"
    return ""


def _question_score(alias: str, label: str, winners: frozenset[str]) -> tuple[int, str]:
    """Score a sentence question that this fact's own subject dominates.

    A sentence has room to mention several things, so phrase position tells you
    very little. What does tell you something is which subject the sentence is
    *about*: the most specific subject word present. This path only opens once
    that word already belongs to the fact, and it still requires the alias to be
    spelled out somewhere in the sentence.
    """
    alias_words = set(tokens(alias))
    if not alias_words & winners:
        return 0, ""
    alias_content = set(content_tokens(alias))
    if not alias_content or not alias_content <= set(content_tokens(label)):
        return 0, ""
    return SCORE_QUESTION_TOPIC + min(len(alias_content), 4), (
        f"the question is about {', '.join(sorted(alias_words & winners))}"
    )


def _alias_score(alias: str, label: str) -> tuple[int, str]:
    alias_norm = normalise(alias)
    label_norm = normalise(label)
    if not alias_norm or not label_norm:
        return 0, ""

    if alias_norm == label_norm:
        return SCORE_EXACT, "the label is exactly this field"

    if content_tokens(alias_norm) and content_tokens(alias_norm) == content_tokens(label_norm):
        return SCORE_SAME_WORDS, "the label asks this in different words"

    remainder = leading_phrase_remainder(label_norm, alias_norm)
    if remainder is not None:
        if not remainder:
            return SCORE_LEADING_EXACT, "the label is exactly this field"
        if remainder[0] in CONNECTORS:
            # "Country of Residence": everything after the connector qualifies
            # the field rather than naming a different one.
            return max(MIN_SCORE, SCORE_LEADING_QUALIFIED - len(remainder)), (
                "the rest of the label qualifies this field"
            )
        # "Position Location": the next word is a new subject, not a qualifier.
        return 0, ""

    prefix = trailing_phrase_prefix(label_norm, alias_norm)
    if prefix is not None:
        if all(word in STOPWORDS or word in NEUTRAL_QUALIFIERS for word in prefix):
            return max(MIN_SCORE, SCORE_TRAILING_FILLER - len(prefix)), (
                "the label ends with this field name"
            )
        return 0, ""

    return 0, ""


def _in_history_block(field: FieldObservation) -> bool:
    if field.group:
        return True
    section_words = set(tokens(field.section))
    return bool(section_words & _HISTORY_SECTION_WORDS)


def _history_allowed(spec: FactSpec, field: FieldObservation) -> str:
    label_norm = normalise(field.display_label)
    unmistakable = label_norm in HISTORY_ONLY_LABELS
    in_block = _in_history_block(field)
    if not unmistakable and not in_block:
        return (
            "history fields are short field names inside an education or "
            "employment block, and this label is neither"
        )
    if has_question_shape(field.display_label) and not in_block:
        return "history fields never answer a sentence question"
    return ""


def match_facts(field: FieldObservation) -> list[FactMatch]:
    """Every fact that could legitimately answer *field*, best first."""
    label = field.display_label
    if label:
        return _match_against_label(field, label, attribute_mode=False)
    if field.attr_label:
        # No visible label at all. The control's own naming is the last resort
        # and only an exact hit counts, because employers name fields carelessly.
        return _match_against_label(field, field.attr_label, attribute_mode=True)
    return []


def _match_against_label(
    field: FieldObservation, label: str, *, attribute_mode: bool
) -> list[FactMatch]:
    matches: dict[str, FactMatch] = {}
    # Judged from the raw label: normalising drops the question mark, and
    # whether something is a sentence must not depend on where it was checked.
    sentence = has_question_shape(label)
    for variant in alternatives(label):
        winners = _winning_topics(variant)
        for spec in FACTS:
            if spec.scope is FactScope.HISTORY:
                if attribute_mode:
                    continue
                if _history_allowed(spec, field):
                    continue
            if _topic_conflict(spec, variant):
                continue
            for alias in alias_variants(spec):
                if _digit_conflict(alias, variant):
                    continue
                score, reason = 0, ""
                if not _modifier_conflict(alias, variant):
                    score, reason = _alias_score(alias, variant)
                if score < MIN_SCORE and sentence and not attribute_mode:
                    if _modifier_conflict(alias, variant, sentence=True):
                        continue
                    score, reason = _question_score(alias, variant, winners)
                if score < MIN_SCORE:
                    continue
                if attribute_mode:
                    if score < SCORE_LEADING_EXACT:
                        continue
                    score = SCORE_ATTRIBUTE_EXACT
                    reason = "matched on the control's name because it has no visible label"
                current = matches.get(spec.key)
                if current is None or score > current.score:
                    matches[spec.key] = FactMatch(
                        spec=spec, score=score, alias=alias, reason=reason
                    )
    ranked = sorted(matches.values(), key=lambda m: (-m.score, -len(m.alias)))
    return ranked


def best_fact(field: FieldObservation) -> FactMatch | None:
    """The one fact to use, or None when the page is asking something else."""
    ranked = match_facts(field)
    if not ranked:
        return None
    top = ranked[0]
    contenders = [m for m in ranked if m.score == top.score]
    if len(contenders) > 1:
        # Two facts fit equally well. That is a question, not a coin toss.
        return None
    return top


# --------------------------------------------------------------------------
# Turning a fact into the value this particular control wants
# --------------------------------------------------------------------------


def _record_value(profile: Profile, spec: FactSpec, field: FieldObservation) -> str:
    records = profile.education if spec.record == "education" else profile.experience
    if not records:
        return ""
    index = field.group_index if 0 <= field.group_index < len(records) else 0
    record = records[index]
    raw = getattr(record, spec.record_field, "")
    if isinstance(raw, bool):
        return "Yes" if raw else "No"
    return str(raw or "")


def fact_value(profile: Profile, spec: FactSpec, field: FieldObservation) -> str:
    if spec.record:
        return _record_value(profile, spec, field)
    return profile.fact(spec.key)


def is_supplementary(field: FieldObservation, spec: FactSpec | None) -> bool:
    """True when leaving this blank is better than asking about it."""
    if normalise(field.display_label) in SUPPLEMENTARY_LABELS:
        return True
    return bool(spec and spec.supplementary)


@dataclass
class Resolution:
    """What the mapper decided for one field."""

    field: FieldObservation
    answer: Answer | None = None
    question: PendingQuestion | None = None
    skipped: str = ""
    fact_key: str = ""


def resolve_field(
    field: FieldObservation,
    profile: Profile,
    learned: dict[str, str] | None = None,
) -> Resolution:
    """Decide what to do with one field: fill it, ask about it, or leave it."""
    learned = learned or {}
    label = field.display_label or field.attr_label
    label_key = normalise(label)

    if field.control is ControlKind.PASSWORD:
        return Resolution(field=field, skipped="passwords are never filled from the profile")
    if field.disabled or field.readonly:
        return Resolution(field=field, skipped="the control is not editable")

    # Answers given to this exact question before come first, so that making a
    # follow-up conditional never buries an answer already provided.
    learned_value = learned.get(label_key)
    if learned_value:
        answer = _shape_answer(
            field, learned_value, AnswerSource.LEARNED, "", 0.95,
            "you answered this exact question before",
        )
        if answer:
            return Resolution(field=field, answer=answer)
        return Resolution(
            field=field,
            question=_ask(field, "", "your saved answer is not one of the options offered here"),
        )

    if is_conditional(label):
        # A follow-up depends on an answer given above it; a general fact about
        # the applicant is not that answer.
        if field.required:
            return Resolution(
                field=field,
                question=_ask(field, "", "this is a follow-up to the question above it"),
            )
        return Resolution(field=field, skipped="follow-up question, left for you")

    match = best_fact(field)
    spec = match.spec if match else None

    if spec and spec.key in DEMOGRAPHIC_KEYS and not profile.answer_demographics:
        return Resolution(
            field=field,
            question=_ask(field, spec.key, "voluntary question -- you decide each time"),
            fact_key=spec.key,
        )

    value = fact_value(profile, spec, field) if spec else ""
    if spec and value:
        answer = _shape_answer(
            field, value, _source_for(spec), spec.key,
            match.confidence if match else 0.6,
            match.reason if match else "",
        )
        if answer:
            return Resolution(field=field, answer=answer, fact_key=spec.key)
        return Resolution(
            field=field,
            question=_ask(
                field, spec.key,
                f"none of the options offered here match your saved answer '{value}'",
            ),
            fact_key=spec.key,
        )

    if field.required:
        return Resolution(
            field=field,
            question=_ask(field, spec.key if spec else "", "required and not answered yet"),
            fact_key=spec.key if spec else "",
        )

    if is_supplementary(field, spec):
        return Resolution(field=field, skipped="optional extra, left blank on purpose")

    return Resolution(field=field, skipped="optional and nothing saved answers it")


def _source_for(spec: FactSpec) -> AnswerSource:
    if spec.record:
        return AnswerSource.HISTORY
    if spec.kind == "file":
        return AnswerSource.DOCUMENT
    return AnswerSource.PROFILE


def _shape_answer(
    field: FieldObservation,
    value: str,
    source: AnswerSource,
    fact_key: str,
    confidence: float,
    reason: str,
) -> Answer | None:
    """Turn a saved value into something this control can actually accept."""
    if field.control in CHOICE_CONTROLS and field.options:
        chosen = best_option(value, field.options)
        if chosen is None:
            return None
        value = chosen.option.label
        picked = f"matched the option '{chosen.option.label}' ({chosen.reason})"
        reason = f"{reason}; {picked}".strip("; ")
    elif field.control is ControlKind.CHECKBOX:
        value = "Yes" if normalise(value) in {"yes", "true", "1", "y"} else "No"
    return Answer(
        fingerprint=field.fingerprint,
        label=field.display_label or field.attr_label,
        value=value,
        source=source,
        fact_key=fact_key,
        confidence=confidence,
        reason=reason,
    )


def _ask(field: FieldObservation, fact_key: str, reason: str) -> PendingQuestion:
    return PendingQuestion(
        fingerprint=field.fingerprint,
        label=field.display_label or field.attr_label,
        control=field.control,
        options=list(field.options),
        required=field.required,
        fact_key=fact_key,
        reason=reason,
        section=field.section,
    )


def resolve_page(
    fields: list[FieldObservation],
    profile: Profile,
    learned: dict[str, str] | None = None,
) -> list[Resolution]:
    """Resolve every visible, fillable field on a page."""
    out: list[Resolution] = []
    for field in fields:
        if not field.visible:
            continue
        out.append(resolve_field(field, profile, learned))
    return out


def describe_match(field: FieldObservation) -> str:
    """Plain-language explanation, for the panel and for debugging."""
    match = best_fact(field)
    if not match:
        ranked = match_facts(field)
        if ranked:
            names = ", ".join(m.spec.key for m in ranked[:3])
            return f"ambiguous between {names}"
        return "no saved fact answers this"
    label = BY_KEY[match.spec.key].prompt or match.spec.key
    return f"{label} ({match.reason}, score {match.score})"

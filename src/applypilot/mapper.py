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

import re
from dataclasses import dataclass
from datetime import date

from .facts import (
    BY_KEY,
    DEMOGRAPHIC_KEYS,
    FACTS,
    HISTORY_ONLY_LABELS,
    SUPPLEMENTARY_LABELS,
    TOPIC_OWNERS,
    FactScope,
    FactSpec,
    accepts,
    alias_variants,
)
from .matching import best_option
from .models import (
    CHOICE_CONTROLS,
    Answer,
    AnswerSource,
    ControlKind,
    FieldObservation,
    Operation,
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
    looks_like_placeholder,
    normalise,
    numeric_suffix,
    pretty_label,
    tokens,
    trailing_phrase_prefix,
    without_request,
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
    "website": 2, "huggingface": 2, "hf": 2, "referral": 2, "hear": 2, "source": 2, "pay": 2,
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

#: Headings that mark a block as being about one education entry.
_EDUCATION_SECTION_WORDS = frozenset(
    {
        "education", "educational", "school", "schools", "academic", "degree",
        "degrees", "qualification", "qualifications", "university", "college",
        "studies", "study",
    }
)

#: Headings that mark a block as being about one employment entry.
_EMPLOYMENT_SECTION_WORDS = frozenset(
    {
        "experience", "employment", "work", "history", "job", "jobs", "position",
        "positions", "career", "professional", "employer", "employers",
    }
)

#: Either kind.
_HISTORY_SECTION_WORDS = _EDUCATION_SECTION_WORDS | _EMPLOYMENT_SECTION_WORDS

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


#: Facts holding a piece of contact or identity data, which no sentence is ever
#: asking for by burying its name in the middle.
#:
#: A form wanting your phone number writes "Phone". It does not write "Do you
#: have a minimum of 2 years of mobile engineering experience?" -- but "mobile"
#: is how half the world says phone, so that question was read as asking for
#: one, on a control that would have typed the number straight in. The same
#: went for "AI tools (such as Github Copilot...)" and "the New York City
#: area".
#:
#: Measured across the corpus rather than guessed at: the sentence path wins
#: about sixty matches and is right every time the fact describes a
#: circumstance -- sponsorship, referral source, previous employment, veteran
#: status. Every match it won for a fact in this set was wrong. Blocking them
#: can only turn a fill into a question, never the reverse.
_NEVER_A_SENTENCE_TOPIC = frozenset(
    {
        "full_name", "first_name", "middle_name", "last_name", "preferred_name",
        "email", "phone", "phone_country_code",
        "street_address", "address_line_2", "city", "state", "postal_code",
        "linkedin", "github", "website", "huggingface",
        "resume", "cover_letter", "signature",
    }
)


#: The facts that are a file rather than a value, and the words a form uses
#: when it is asking for each.
_DOCUMENT_FACTS: tuple[tuple[str, str], ...] = (
    ("cover_letter", r"cover\s*letter|covering\s*letter|motivation\s*letter"),
    ("resume", r"\bresum|\bcv\b|curriculum\s+vitae"),
)


def document_wanted(field: FieldObservation) -> str:
    """Which document a file control is asking for, read from what it says.

    A dropzone is labelled with the sentence that explains it -- "Make
    completing your job application easier by uploading your resume or CV" --
    and that is not a phrase any alias lines up with, nor a question, so none
    of the ordinary rules reached it and the resume went unattached on a form
    that said what it wanted in plain words.

    Only for a control that takes a file. Nothing is typed into one, so the
    worst a wrong answer can do is attach a document to the wrong slot -- and
    the cover letter is looked for first, because a page offering both says
    "cover letter" on one of them and "resume or CV" on the other.
    """
    if field.control is not ControlKind.FILE:
        return ""
    text = " ".join(
        part for part in (field.display_label, field.attr_label, field.section) if part
    )
    for key, pattern in _DOCUMENT_FACTS:
        if re.search(pattern, text, re.IGNORECASE):
            return key
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


def _wrong_kind_of_block(spec: FactSpec, field: FieldObservation) -> str:
    """An education record does not answer a question in an employment block.

    Without this, "Start year" fitted both an education entry and a job equally
    well, and an even fit is refused -- so a field that had an obvious answer
    was handed back as a question.
    """
    words = set(tokens(field.section))
    education = bool(words & _EDUCATION_SECTION_WORDS)
    employment = bool(words & _EMPLOYMENT_SECTION_WORDS)
    if spec.record == "experience" and education and not employment:
        return "this block is about education, not employment"
    if spec.record == "education" and employment and not education:
        return "this block is about employment, not education"
    return ""


def _history_allowed(spec: FactSpec, field: FieldObservation) -> str:
    label_norm = normalise(field.display_label)
    # A label written "Current/Most Recent Company Name" keeps its slash
    # through normalising, so an exact-set test never saw it. Reading it the
    # way every other rule does -- one form per branch of the slash -- makes
    # both spellings the same question, which is what the page meant.
    unmistakable = label_norm in HISTORY_ONLY_LABELS or any(
        variant in HISTORY_ONLY_LABELS for variant in alternatives(field.display_label)
    )
    in_block = _in_history_block(field)
    wrong_kind = _wrong_kind_of_block(spec, field)
    if wrong_kind:
        return wrong_kind
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
    # A label of "*" carries no words once normalised. Treating it as a label
    # anyway is what let a whole form come back matching nothing at all.
    if label and normalise(label):
        matches = _match_against_label(field, label, attribute_mode=False)
        if matches:
            return matches
        # "Please identify your Veteran status" is the veteran status field.
        # The request in front of it is manners, not part of the name, and a
        # whole self-identification section went unasked because of it. Only
        # tried when the label as written matched nothing, so a field that
        # genuinely begins with one of those words is unaffected.
        # A block heading finishes a label that cannot stand on its own. A
        # field called "Number" sitting under "Phones (1)" is a phone number,
        # and saying so needs both halves -- on its own "Number" is nothing at
        # all, which is why a saved phone sat there while the form asked for it.
        for qualified in _section_qualified(field.section, label):
            matches = _match_against_label(field, qualified, attribute_mode=False)
            if matches:
                return matches

        plain = without_request(label)
        if plain != label and normalise(plain):
            matches = _match_against_label(field, plain, attribute_mode=False)
            if matches:
                return matches
        # A label that answers to nothing is, by definition, telling us nothing.
        # The veteran question on one real application is headed "(VEVRAA)
        # Veteran's Self-Identification Form" and labelled with three hundred
        # characters of statute -- neither of which is the name of a field --
        # while the control's own name said "veteran" the whole time, and the
        # section went unasked. A name that means something beats a label that
        # does not, on the same narrow terms a field with no label at all gets:
        # an exact hit only, and the confidence penalty that goes with it.
        if field.attr_label:
            return _match_against_label(field, field.attr_label, attribute_mode=True)
        return matches
    if field.attr_label:
        # No visible label at all. The control's own naming is the last resort
        # and only an exact hit counts, because employers name fields carelessly.
        return _match_against_label(field, field.attr_label, attribute_mode=True)
    return []


#: How many words a label may have before its block heading stops being the
#: missing half of it. "Number" needs finishing; a sentence does not.
_NEEDS_FINISHING = 3


def _section_qualified(section: str, label: str) -> list[str]:
    """The label with its block heading in front, singular and plural.

    A repeating block is headed "Phones (1)" and its fields are called "Type"
    and "Number". Neither means anything alone; together with the heading they
    are unmistakable. The count is dropped, and the heading is tried both as it
    appears and without a trailing s, because a block of phones holds a phone
    number rather than a phones number.
    """
    # A heading read off a page carries its furniture with it: the count of
    # entries, a required marker, the number of the block. "Phones (1)*
    # required. 2" is the heading "Phones" with all of that stuck to it, and
    # stripping only a count from the end left the whole string unusable.
    head = re.split(r"[(*\d]", section or "", maxsplit=1)[0]
    head = head.strip(" \t-–—:,.").strip()
    if not head or not label or len(tokens(label)) > _NEEDS_FINISHING:
        return []
    if normalise(head) == normalise(label):
        return []
    singular = head[:-1] if len(head) > 3 and head.endswith("s") else head
    out = [f"{singular} {label}"]
    if singular != head:
        out.append(f"{head} {label}")
    return out


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
                    if spec.key in _NEVER_A_SENTENCE_TOPIC:
                        continue
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


def _newest_first(records: list) -> list:
    """The records in the order a form expects them: latest first.

    The order they happen to be stored in is the order they were typed in, and
    that is not an answer to anything. Two things went wrong for the same
    reason: "Current/Last Employer" came back with the job before the current
    one, and a form with room for a single education entry was given the school
    attended before the most recent one -- both because those were written down
    first.

    Every form that offers several of these lists them newest first, and a form
    that offers only one is asking for the newest. Sorting once serves both:
    entry nought is the current job or the last school, entry one the one
    before it.
    """

    def when(record) -> tuple:
        # Still going beats a finish date, and a later finish beats an earlier.
        return (
            1 if getattr(record, "current", False) else 0,
            str(getattr(record, "end_date", "") or "~"),
            str(getattr(record, "start_date", "") or ""),
        )

    return sorted(records, key=when, reverse=True)


def _record_value(profile: Profile, spec: FactSpec, field: FieldObservation) -> str:
    stored = profile.education if spec.record == "education" else profile.experience
    if not stored:
        return ""
    records = _newest_first(stored)
    index = field.group_index if 0 <= field.group_index < len(records) else 0
    record = records[index]
    raw = getattr(record, spec.record_field, "")
    if isinstance(raw, bool):
        return "Yes" if raw else "No"
    return str(raw or "")


#: Date shapes a form asks for, read off the control rather than assumed.
_DATE_SHAPES = (
    (r"y{4}\W*m{2}\W*d{2}", "%Y-%m-%d"),
    (r"d{1,2}\W*m{1,2}\W*y{4}", "%d/%m/%Y"),
    (r"m{1,2}\W*d{1,2}\W*y{4}", "%m/%d/%Y"),
    (r"m{1,2}\W*d{1,2}\W*y{2}", "%m/%d/%y"),
)


def format_date_for(field: FieldObservation, value: date) -> str:
    """Write a date the way this particular control asks for it."""
    # A native date input only accepts the ISO form, whatever it displays.
    if field.input_type == "date":
        return value.isoformat()
    # Each hint is tested on its own. Running them together once produced a
    # "yyyy mm/dd" sequence out of two copies of "MM/DD/YYYY" and wrote the
    # date backwards.
    for hint in (field.placeholder, field.attr_label):
        text = (hint or "").lower()
        if not text:
            continue
        for pattern, form in _DATE_SHAPES:
            if re.search(pattern, text):
                return value.strftime(form)
    return value.strftime("%m/%d/%Y")


def computed_value(profile: Profile, spec: FactSpec, field: FieldObservation) -> str:
    """A value worked out now rather than stored.

    Today's date is not something to hand back as a question, and neither is a
    signature line that wants the name already in the profile.
    """
    if spec.computed == "today":
        return format_date_for(field, date.today())
    if spec.computed == "full_name":
        return profile.fact("full_name")
    return ""


def fact_value(profile: Profile, spec: FactSpec, field: FieldObservation) -> str:
    if spec.record:
        return _record_value(profile, spec, field)
    stored = profile.fact(spec.key)
    if stored:
        return stored
    if spec.computed:
        return computed_value(profile, spec, field)
    return ""


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
    #: An answer the page is already holding that nothing here put there, and
    #: that the profile has no answer of its own for. Typing a county into a
    #: form by hand used to be respected and then forgotten, so the next form
    #: asked again -- and the one after that. The value is offered back rather
    #: than taken: it is theirs, and a form can hold a value for reasons that
    #: have nothing to do with them.
    learnable: str = ""


def _worth_learning(
    field: FieldObservation,
    spec: FactSpec | None,
    profile: Profile,
    page_has_password: bool,
    learned: dict[str, str],
) -> str:
    """The value on the page worth offering to remember, or "".

    Empty unless the page is holding something, the profile has nothing that
    already covers it, and the field is one whose answer means the same thing
    on the next form. A password is never learned; nor is anything a page fills
    in for itself.
    """
    if not _already_answered(field):
        return ""
    if is_credential(field, page_has_password) or field.control is ControlKind.FILE:
        return ""
    value = (field.value or "").strip()
    if not value or looks_like_placeholder(value):
        return ""
    # Read back from a control the page owns and populates itself -- a total, a
    # generated reference, today's date already written in.
    if field.readonly or field.disabled:
        return ""
    if spec is not None:
        if not accepts(spec, value):
            return ""
        if (profile.fact(spec.key) or "").strip().lower() == value.lower():
            return ""
    # Already remembered against this question's own wording. Offering it again
    # every time the form is opened is how a useful prompt becomes furniture.
    remembered = learned.get(normalise(field.display_label or field.attr_label), "")
    if remembered.strip().lower() == value.lower():
        return ""
    return value


#: A box a form asks you to tick to agree to something. Matched on wording,
#: because forms mark these no other way, and kept narrow on purpose: "I agree",
#: "I certify", "I have read". A question about whether you have ever worked
#: here is not an agreement, whatever else its sentence happens to contain.
_AGREEMENT_RE = re.compile(
    r"\b((i|you)\s+(have\s+read|agree|accept|consent|acknowledge|certify|confirm)"
    r"|by\s+(checking|ticking|clicking|submitting)"
    r"|agree\s+to\s+the\s+(terms|conditions)"
    r"|accept\s+the\s+(terms|conditions)"
    r"|terms\s+(and|&)\s+conditions"
    r"|arbitration\s+agreement"
    r"|privacy\s+(policy|notice|statement)"
    r"|code\s+of\s+conduct)\b",
    re.IGNORECASE,
)


#: The name a form gives the box you would choose an account name in. A small
#: closed vocabulary, anchored at the start of the label so that a question
#: merely mentioning logging in is not caught by it.
_CREDENTIAL_RE = re.compile(
    r"^(login|log\s*in|username|user\s*name|user\s*id|userid"
    r"|screen\s*name|account\s*name|sign[-\s]?in\s*(id|name))\b",
    re.IGNORECASE,
)


#: Left blank because what is saved is not on offer here, and the form does not
#: insist on this one. Stopping over an optional box the employer is content to
#: leave empty holds up everything behind it for nothing.
_DOES_NOT_FIT = "nothing saved fits the options this one offers"


def is_credential(field: FieldObservation, page_has_password: bool) -> bool:
    """True when this box is where you would choose an account name.

    Only on a page that also holds a password: an account name and a password
    are the two halves of one thing, and a box called "Login" on a page with no
    password to go with it is something else.

    This matters because choosing an account name is not a fact about anybody.
    It is the first half of creating an account, and creating an account
    accepts an employer's terms -- which is not ours to do. Asking for it
    anyway put a required question on screen that could never be answered, and
    everything else waited behind it.
    """
    if not page_has_password:
        return False
    if field.control in CHOICE_CONTROLS or field.control is ControlKind.CHECKBOX:
        return False
    label = field.display_label or field.attr_label or field.label or ""
    return bool(_CREDENTIAL_RE.match(label.strip()))


#: The facts that are a link to somewhere, the words a form uses to ask for
#: each, and what to call it when several are written out together.
_LINK_FACTS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("github", ("github",), "GitHub"),
    ("website", ("portfolio", "website", "personal site", "web site"), "Portfolio"),
    ("linkedin", ("linkedin",), "LinkedIn"),
    ("huggingface", ("huggingface", "hugging face"), "Hugging Face"),
)

#: A box asking for somewhere to look, rather than for one particular address.
_ASKS_FOR_LINKS = re.compile(r"\b(links?|urls?|profiles?)\b", re.IGNORECASE)


def composed_links(field: FieldObservation, profile: Profile) -> str:
    """Several saved links written out as one answer.

    "Please provide links to your GitHub, portfolio, demo, or AI projects" is
    one box wanting several things, and no single fact answers it -- so it was
    left blank while every address it asked for sat in the profile.

    Only addresses that are saved, each labelled with what it is, and only when
    the question names more than one of them. A box asking for a GitHub URL and
    nothing else is still the GitHub field and is left to the ordinary path.
    Nothing here writes anything the applicant did not enter themselves.
    """
    if field.control not in {ControlKind.TEXT, ControlKind.TEXTAREA, ControlKind.URL}:
        return ""
    label = normalise(field.display_label)
    if not label or not _ASKS_FOR_LINKS.search(label):
        return ""

    named = [
        (key, title)
        for key, words, title in _LINK_FACTS
        if any(word in label for word in words)
    ]
    if len(named) < 2:
        return ""

    parts = [f"{title}: {profile.fact(key)}" for key, title in named if profile.fact(key)]
    if not parts:
        return ""
    # A textarea has room for a line each; a single-line box does not.
    separator = "\n" if field.control is ControlKind.TEXTAREA else " · "
    return separator.join(parts)


def _already_answered(field: FieldObservation) -> bool:
    """True when the page is already holding an answer for this field.

    A tick box is answered by being ticked or not, so it never counts as
    answered by sitting there; and a value that is only the control's own
    placeholder is not an answer either.
    """
    if field.control is ControlKind.CHECKBOX:
        return bool(field.checked)
    value = (field.value or "").strip()
    return bool(value) and not looks_like_placeholder(value)


def is_agreement(field: FieldObservation) -> bool:
    """True when this is a box asking you to agree to something."""
    if field.control is not ControlKind.CHECKBOX:
        return False
    return bool(_AGREEMENT_RE.search(field.display_label or field.label or ""))


def _unnamed_document_upload(fields: list[FieldObservation]) -> str:
    """The fingerprint of the file control that must be the resume, or "".

    Empty when the page names one already, when it names none but offers
    several, or when there is nothing to attach to. Guessing between two
    unlabelled uploads is how a resume ends up in a transcript box.
    """
    uploads = [f for f in fields if f.visible and f.control is ControlKind.FILE]
    if len(uploads) != 1:
        return ""
    only = uploads[0]
    return "" if document_wanted(only) else only.fingerprint


def resolve_field(
    field: FieldObservation,
    profile: Profile,
    learned: dict[str, str] | None = None,
    page_has_password: bool = False,
    assume_resume: bool = False,
) -> Resolution:
    """Decide what to do with one field: fill it, ask about it, or leave it."""
    learned = learned or {}
    label = field.display_label or field.attr_label
    label_key = normalise(label)

    if field.control is ControlKind.PASSWORD:
        return Resolution(field=field, skipped="passwords are never filled from the profile")
    if is_credential(field, page_has_password):
        return Resolution(
            field=field,
            skipped="choosing an account name is yours, along with the password",
        )
    if field.disabled or field.readonly:
        return Resolution(field=field, skipped="the control is not editable")

    # Answers given to this exact question before come first, so that making a
    # follow-up conditional never buries an answer already provided.
    learned_value = learned.get(label_key)
    if learned_value:
        known = best_fact(field)
        answer = _shape_answer(
            field, learned_value, AnswerSource.LEARNED, known.spec.key if known else "", 0.95,
            "you answered this exact question before",
        )
        if answer:
            return Resolution(field=field, answer=answer)
        if not field.required:
            return Resolution(field=field, skipped=_DOES_NOT_FIT)
        return Resolution(
            field=field,
            question=_ask(
                field, "", "your saved answer is not one of the options offered here", profile
            ),
        )

    links = composed_links(field, profile)
    if links:
        return Resolution(
            field=field,
            answer=Answer(
                fingerprint=field.fingerprint,
                label=pretty_label(field.display_label),
                value=links,
                source=AnswerSource.PROFILE,
                fact_key="",
                confidence=0.9,
                reason="the addresses you have saved, for each thing this asks about",
            ),
        )

    if is_agreement(field):
        # Nothing in the fact catalogue answers one of these, and nothing
        # should: what is being agreed to is different every time. So it was
        # falling through to "optional and nothing saved answers it" and being
        # left blank -- which is how a step got refused with an arbitration
        # agreement unticked and nothing on screen saying why.
        #
        # Either it is asked, or the applicant has said in advance that ticking
        # these is fine. What never happens is a saved Yes from somewhere else
        # in the profile leaking in: this is answered by the setting or by the
        # person, and by nothing else.
        if profile.accept_agreements:
            return Resolution(
                field=field,
                answer=Answer(
                    fingerprint=field.fingerprint,
                    label=pretty_label(field.display_label or field.label),
                    value="Yes",
                    source=AnswerSource.PROFILE,
                    fact_key="",
                    confidence=1.0,
                    reason=(
                        "you chose to accept the agreements an application requires: "
                        f'"{pretty_label(field.display_label or field.label)}"'
                    ),
                ),
            )
        return Resolution(
            field=field,
            question=_ask(field, "", "an agreement -- yours to read and accept", profile),
        )

    if is_conditional(label):
        # A follow-up depends on an answer given above it; a general fact about
        # the applicant is not that answer.
        if field.required:
            return Resolution(
                field=field,
                question=_ask(field, "", "this is a follow-up to the question above it", profile),
            )
        return Resolution(field=field, skipped="follow-up question, left for you")

    match = best_fact(field)
    spec = match.spec if match else None

    # A dropzone explains itself in a sentence rather than naming itself, and
    # no phrase rule lines up with one. What it is asking for is still plain to
    # read, and a file control can only ever be asking for a document.
    if spec is None:
        wanted = document_wanted(field)
        if not wanted and assume_resume:
            wanted = "resume"
        if wanted:
            spec = BY_KEY[wanted]
            match = FactMatch(
                spec=spec,
                score=SCORE_LEADING_QUALIFIED,
                alias=wanted,
                reason="a file control asking for this document in so many words",
            )

    if spec and spec.key in DEMOGRAPHIC_KEYS and not profile.answer_demographics:
        return Resolution(
            field=field,
            question=_ask(field, spec.key, "voluntary question -- you decide each time", profile),
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
        # A saved answer that does not fit is worth stopping for only if the
        # form insists on this field. "How did you hear about us?" is optional
        # and its list held nothing resembling what was saved, so it became a
        # question that had to be cleared before anything else could happen --
        # over a box the employer was happy to leave empty.
        if not field.required:
            return Resolution(field=field, skipped=_DOES_NOT_FIT, fact_key=spec.key)
        return Resolution(
            field=field,
            question=_ask(
                field, spec.key,
                f"none of the options offered here match your saved answer '{value}'",
                profile,
            ),
            fact_key=spec.key,
        )

    # A document a form offers to take is never an optional extra.
    #
    # Plenty of applications mark the resume upload optional, and it was then
    # skipped in silence -- on a page whose own words were "make completing
    # your job application easier by uploading your resume". Attaching the
    # resume is the point of the exercise, so it is put forward whether or not
    # the form insists, and the panel attaches the one on file without asking
    # anybody anything.
    if spec is not None and spec.key in {key for key, _ in _DOCUMENT_FACTS}:
        if _already_answered(field):
            return Resolution(field=field, skipped="already attached on the page")
        return Resolution(
            field=field,
            question=_ask(field, spec.key, "a document this form will take", profile),
            fact_key=spec.key,
        )

    if field.required:
        # Unless it is already answered. A required field the page is holding a
        # value for wants nothing from anybody -- and asking anyway put "Login:
        # required and not answered yet" on screen while the login sat in the
        # box, which reads as the tool being unable to see the page at all.
        if _already_answered(field):
            return Resolution(
                field=field,
                skipped="already answered on the page",
                fact_key=spec.key if spec else "",
                learnable=_worth_learning(field, spec, profile, page_has_password, learned),
            )
        return Resolution(
            field=field,
            question=_ask(
                field, spec.key if spec else "", "required and not answered yet", profile
            ),
            fact_key=spec.key if spec else "",
        )

    if _already_answered(field):
        return Resolution(
            field=field,
            skipped="already answered on the page",
            fact_key=spec.key if spec else "",
            learnable=_worth_learning(field, spec, profile, page_has_password, learned),
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
        # The fact decides which extra vocabulary is in play: "MS" is a state to
        # an address field and a Master's degree to an education one.
        chosen = best_option(value, field.options, fact_key)
        if chosen is None:
            return None
        value = chosen.option.label
        picked = f"matched the option '{chosen.option.label}' ({chosen.reason})"
        reason = f"{reason}; {picked}".strip("; ")
    elif "year" in normalise(field.display_label).split() and re.search(r"(19|20)\d{2}", value):
        # "Graduation Year" wants 2025, not "Jul 2025".
        value = re.search(r"(19|20)\d{2}", value).group(0)
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


def _ask(
    field: FieldObservation,
    fact_key: str,
    reason: str,
    profile: Profile | None = None,
) -> PendingQuestion:
    saved = ""
    if profile is not None and fact_key:
        spec = BY_KEY.get(fact_key)
        if spec is not None:
            saved = fact_value(profile, spec, field)
    return PendingQuestion(
        fingerprint=field.fingerprint,
        label=pretty_label(field.display_label or field.attr_label),
        control=field.control,
        operation=field.operation,
        options=usable_options(field),
        required=field.required,
        fact_key=fact_key,
        reason=reason,
        section=_entry_context(field),
        frame=field.frame,
        saved_value=saved,
        options_pending=needs_its_options_opened(field),
    )


def _entry_context(field: FieldObservation) -> str:
    """Which entry of a repeating block this is.

    Three fields all labelled "GPA" with nothing to tell them apart is not a
    list anyone can act on.
    """
    if field.group:
        return f"{field.section or 'Entry'} {field.group_index + 1}".strip()
    return field.section


def usable_options(field: FieldObservation) -> list:
    """The options a control offers, with its placeholder rows removed."""
    return [o for o in field.options if not o.disabled and not looks_like_placeholder(o.label)]


def needs_its_options_opened(field: FieldObservation) -> bool:
    """True when this control's choices are not known yet.

    A custom dropdown keeps its options behind a popup it owns, and some native
    selects hold nothing until they are touched. Either way there is nothing to
    show, and handing back a text box for someone to type a dropdown answer into
    is not an acceptable substitute.

    The control now says which it is rather than being guessed at from how many
    options happen to be lying about. That distinction was invisible before:
    across 89 real forms, 338 controls hold no options until opened and only 10
    hold none until something is typed, and the two want opposite treatment.
    """
    if field.operation in {Operation.LIST_ON_OPEN, Operation.TYPE_TO_SEARCH}:
        return len(usable_options(field)) < 2
    if field.operation is Operation.LIST_PRESENT:
        # It has said its choices are readable. If they are not, believe the
        # control over the count -- an empty list here is an empty list.
        return False
    if field.control not in CHOICE_CONTROLS:
        return False
    return len(usable_options(field)) < 2


def resolve_page(
    fields: list[FieldObservation],
    profile: Profile,
    learned: dict[str, str] | None = None,
) -> list[Resolution]:
    """Resolve every visible, fillable field on a page."""
    # Whether there is a password anywhere here is what tells an account name
    # apart from an ordinary box that happens to be called "Login", so it has
    # to be known before any one field is looked at.
    page_has_password = any(f.control is ControlKind.PASSWORD for f in fields)

    # Which file control is the resume, when none of them says so.
    #
    # A dropzone is often drawn with no label at all, or with nothing but the
    # file types it takes. Across the corpus that was twenty-eight uploads left
    # unattached -- the most important field on an application, on forms that
    # were otherwise filled. A bare file control on a job application is the
    # CV; a form wanting anything else says which.
    #
    # Only ever one of them, and only when no other file control has already
    # claimed it by name, so a page offering a resume and a portfolio still
    # gets the resume in the resume box and nothing in the other.
    unnamed = _unnamed_document_upload(fields)

    out: list[Resolution] = []
    for field in fields:
        if not field.visible:
            continue
        assume = field.fingerprint == unnamed
        out.append(resolve_field(field, profile, learned, page_has_password, assume))
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

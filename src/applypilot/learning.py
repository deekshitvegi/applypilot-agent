"""Deciding whether something typed on a page is worth remembering.

Learning is how the agent stops asking the same thing twice, and it is also how
rubbish gets into the profile and is written back into later applications. Once
an employer's internal option id, a placeholder row or a mis-scanned label is
saved as an answer, it becomes an answer everywhere.

So the bar is: a human-readable question, a human-readable value, and a control
where the value means what it appears to mean.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .facts import DEMOGRAPHIC_KEYS
from .mapper import best_fact
from .models import (
    CHOICE_CONTROLS,
    ControlKind,
    FieldObservation,
    LearnedAnswer,
)
from .text import looks_like_placeholder, normalise

#: Controls whose contents are numeric by nature. Everywhere else a bare number
#: is an employer's internal option id, not an answer.
NUMERIC_FRIENDLY = {ControlKind.TEL, ControlKind.NUMBER, ControlKind.DATE}

#: Field names where digits are the answer.
NUMERIC_FRIENDLY_TOPICS = frozenset(
    {"phone", "postal_code", "phone_country_code", "salary_expectation", "education.gpa"}
)

#: Chrome and the page put these on screen; none of them is a question about the
#: applicant. Matched on the whole normalised label, never as a substring.
PAGE_FURNITURE = frozenset(
    {
        "search", "search jobs", "keyword", "keywords", "filter", "filters",
        "sort", "sort by", "sorted by", "page", "page size", "results per page",
        "language", "select language", "choose language", "current date",
        "today", "date", "time", "timezone", "notification", "notifications",
        "menu", "main menu", "navigation", "skip to content", "skip to main content",
        "close", "open", "back", "next", "previous", "cancel", "submit", "save",
        "sign in", "log in", "sign up", "register", "subscribe", "email alerts",
        "job alerts", "share", "print", "help", "settings", "account",
        "username", "user id", "password", "confirm password", "new password",
    }
)

#: Values that are really some other element's label. The mis-scan that turned
#: "Email Address:" into "Notification:" is the reason this exists.
_LABEL_SHAPED = re.compile(r":\s*$")
# Hex-looking blobs, but only when a letter is present: an all-digit string is a
# phone number or a postcode as often as it is an id, and gets judged below.
_OPAQUE_ID = re.compile(r"^(?=.*[a-f])[0-9a-f]{8,}$|^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)
_ONLY_DIGITS = re.compile(r"^[\d\s()+\-.]+$")


@dataclass(frozen=True)
class LearningDecision:
    learn: bool
    reason: str


def judge(
    field: FieldObservation,
    value: str,
    *,
    page_labels: frozenset[str] | None = None,
    allow_demographics: bool = False,
) -> LearningDecision:
    """Decide whether *value* on *field* is a reusable answer."""
    page_labels = page_labels or frozenset()
    question = field.display_label or field.attr_label
    raw_value = value or ""

    if not field.has_visible_label:
        return LearningDecision(False, "no visible label, so there is no question to key it by")

    norm_question = normalise(question)
    norm_value = normalise(raw_value)

    if not norm_question:
        return LearningDecision(False, "the question is empty")
    if len(norm_question) > 300:
        return LearningDecision(False, "the question is too long to be a question")
    if not re.search(r"[a-z]", norm_question):
        return LearningDecision(False, "the question has no words in it")
    if norm_question in PAGE_FURNITURE:
        return LearningDecision(False, "that is page furniture, not a question about you")

    if field.control in {ControlKind.PASSWORD, ControlKind.FILE}:
        return LearningDecision(False, "credentials and attachments are never learned")

    if looks_like_placeholder(raw_value):
        return LearningDecision(False, "that is the control's placeholder, not an answer")
    if not norm_value:
        return LearningDecision(False, "the value is empty")
    if norm_value == norm_question:
        return LearningDecision(False, "the value is a copy of the question")
    if _LABEL_SHAPED.search(raw_value.strip()):
        return LearningDecision(False, "the value reads as another field's label")
    if normalise(raw_value) in page_labels - {norm_question}:
        return LearningDecision(False, "the value is another field's label on this page")
    if _OPAQUE_ID.match(raw_value.strip()):
        return LearningDecision(False, "that is an internal identifier, not a readable answer")

    if _ONLY_DIGITS.match(raw_value.strip()):
        # Numbers are a real answer for a phone or a postcode and an internal
        # option id everywhere else.
        match = best_fact(field)
        friendly_fact = bool(match and match.spec.key in NUMERIC_FRIENDLY_TOPICS)
        if field.control in CHOICE_CONTROLS and not friendly_fact:
            return LearningDecision(
                False, "a number chosen from a dropdown is that employer's option id"
            )
        if field.control not in NUMERIC_FRIENDLY and not friendly_fact:
            return LearningDecision(
                False, "a bare number here is more likely an internal id than an answer"
            )

    if field.control in CHOICE_CONTROLS and field.options:
        labels = {normalise(o.label) for o in field.options}
        if norm_value not in labels:
            return LearningDecision(
                False, "the value is not one of the options this control offers"
            )

    match = best_fact(field)
    if match and match.spec.key in DEMOGRAPHIC_KEYS and not allow_demographics:
        return LearningDecision(False, "voluntary questions are not remembered unless you say so")

    return LearningDecision(True, "a readable question with a readable answer")


def build(field: FieldObservation, value: str, host: str = "") -> LearnedAnswer:
    question = field.display_label or field.attr_label
    return LearnedAnswer(
        question=question,
        normalised=normalise(question),
        value=value.strip(),
        control=field.control,
        host=host,
    )


def page_label_set(fields: list[FieldObservation]) -> frozenset[str]:
    """Every visible label on the page, for spotting a mis-scanned value."""
    return frozenset(normalise(f.display_label) for f in fields if f.has_visible_label)

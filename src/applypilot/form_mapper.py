from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import (
    CandidateProfile,
    FormField,
    FormFillAction,
    FormFillPlan,
    ReusableAnswer,
    UnknownField,
)

BLOCKED_PATTERNS = (
    "password",
    "social security",
    "ssn",
    "credit card",
    "bank account",
    "routing number",
    "payment",
    "captcha",
    "verification code",
    "one-time code",
    "mfa",
)


def plan_form_fill(
    page_url: str,
    fields: list[FormField],
    profile: CandidateProfile,
    answers: list[ReusableAnswer],
    source_url: str = "",
    resume_text: str = "",
    adapter: str = "generic",
) -> FormFillPlan:
    actions: list[FormFillAction] = []
    unknown: list[UnknownField] = []
    blocked: list[UnknownField] = []
    seen_checkbox_unknowns: set[str] = set()
    resume_checkbox_groups = {
        resume_group_key(field)
        for field in fields
        if field.field_type == "checkbox"
        and is_resume_evidence_group(field.group_label or field.label)
        and any(
            resume_mentions_option(candidate.option_label, resume_text)
            for candidate in fields
            if resume_group_key(candidate) == resume_group_key(field)
        )
    }

    for field in fields:
        label = normalize(f"{field.label} {field.name}")
        if field.field_type == "password" or any(pattern in label for pattern in BLOCKED_PATTERNS):
            blocked.append(
                UnknownField(
                    field_id=field.id,
                    label=field.label,
                    required=field.required,
                    reason="Sensitive or authentication fields require the user.",
                )
            )
            continue

        # The captured job-board URL is authoritative for referral source.
        mapped = map_source_field(label, field, source_url)
        if mapped is None:
            mapped = map_profile_field(label, field, profile)
        if mapped is None:
            # Reusable answers handle employer-specific questions. Canonical
            # profile fields remain the source of truth so a bad page mapping
            # cannot poison identity, contact, or work-policy data.
            mapped = map_exact_reusable_answer(label, field, answers)
        if mapped is None:
            mapped = map_reusable_answer(label, field, answers)
        if (
            mapped is None
            and field.field_type == "checkbox"
            and resume_group_key(field) in resume_checkbox_groups
        ):
            mapped = (
                "true" if resume_mentions_option(field.option_label, resume_text) else "false",
                "resume.explicit_skill",
                1.0,
            )

        if mapped is not None:
            value, source, confidence = mapped
            if field.field_type == "checkbox":
                value = checkbox_value(value, field)
            actions.append(
                FormFillAction(
                    field_id=field.id,
                    value=coerce_option(value, field),
                    source=source,
                    confidence=confidence,
                )
            )
        elif not field.value and field.field_type != "file":
            unknown_key = normalize(field.group_label) if field.field_type == "checkbox" else ""
            if unknown_key and unknown_key in seen_checkbox_unknowns:
                continue
            if unknown_key:
                seen_checkbox_unknowns.add(unknown_key)
            unknown.append(
                UnknownField(
                    field_id=field.id,
                    label=field.group_label or field.label,
                    required=field.required,
                    reason="No verified reusable answer is available.",
                )
            )

    return FormFillPlan(
        page_url=page_url,
        adapter=adapter,
        actions=actions,
        unknown_fields=unknown,
        blocked_fields=blocked,
    )


def map_profile_field(
    label: str, field: FormField, profile: CandidateProfile
) -> tuple[str, str, float] | None:
    first_name, last_name = split_name(profile.legal_name)
    if any(
        pattern_matches(label, pattern)
        for pattern in ("phone country code", "mobile country code", "country calling code")
    ):
        country_code = phone_country_code(profile.phone, profile.country)
        return (country_code, "profile.phone", 0.98) if country_code else None
    if field.field_type == "checkbox" and field.group_label and (
        pattern_matches(label, "relocate") or pattern_matches(label, "relocation")
    ):
        if profile.willing_to_relocate is False:
            option = normalize(field.option_label)
            unable = any(
                phrase in option
                for phrase in ("unable to relocate", "only work remotely", "cannot relocate")
            )
            return ("true" if unable else "false", "profile.willing_to_relocate", 0.98)
        # A general willingness to relocate does not identify a preferred city.
        return None
    mappings: list[tuple[tuple[str, ...], str | bool | None, str]] = [
        (("first name", "given name"), first_name, "profile.legal_name"),
        (("last name", "family name", "surname"), last_name, "profile.legal_name"),
        (("full name", "legal name"), profile.legal_name, "profile.legal_name"),
        (("preferred name",), profile.preferred_name, "profile.preferred_name"),
        (("pronoun",), profile.pronouns, "profile.pronouns"),
        (("email", "email address"), profile.email, "profile.email"),
        (("phone", "mobile"), profile.phone, "profile.phone"),
        (("street address", "address line 1"), profile.address_line_1, "profile.address_line_1"),
        (("address line 2", "apartment", "suite"), profile.address_line_2, "profile.address_line_2"),
        (("city",), profile.city, "profile.city"),
        (("state", "province", "region"), profile.region, "profile.region"),
        (("zip", "postal code", "postcode"), profile.postal_code, "profile.postal_code"),
        (("country",), profile.country, "profile.country"),
        (("linkedin",), profile.linkedin_url, "profile.linkedin_url"),
        (("github",), profile.github_url, "profile.github_url"),
        (("portfolio", "personal website", "website"), profile.portfolio_url, "profile.portfolio_url"),
        (
            ("current title", "current job title", "current position", "current role"),
            profile.current_title,
            "profile.current_title",
        ),
        (("years of experience",), profile.years_of_experience, "profile.years_of_experience"),
        (("authorized to work", "work authorization"), profile.work_authorization, "profile.work_authorization"),
        (("sponsorship", "sponsor"), profile.requires_sponsorship, "profile.requires_sponsorship"),
        (("relocate", "relocation"), profile.willing_to_relocate, "profile.willing_to_relocate"),
        (("travel",), profile.willing_to_travel, "profile.willing_to_travel"),
        (("18 years", "at least 18"), profile.age_18_or_older, "profile.age_18_or_older"),
        (("background check",), profile.background_check_consent, "profile.background_check_consent"),
        (("notice period", "available to start", "start date", "start-date"), profile.notice_period, "profile.notice_period"),
        (("salary", "compensation", "pay expectation"), profile.desired_salary, "profile.desired_salary"),
        (("gender", "gender identity", "sex"), profile.gender_identity, "profile.gender_identity"),
        (("race", "ethnicity", "ethnic background"), profile.race_ethnicity, "profile.race_ethnicity"),
        (("veteran", "protected veteran"), profile.veteran_status, "profile.veteran_status"),
        (("disability", "disabled"), profile.disability_status, "profile.disability_status"),
    ]

    for patterns, raw_value, source in mappings:
        if any(pattern_matches(label, pattern) for pattern in patterns) and raw_value not in (None, ""):
            value = boolean_value(raw_value, field)
            return value, source, 0.98
    return None


def map_reusable_answer(
    label: str, field: FormField, answers: list[ReusableAnswer]
) -> tuple[str, str, float] | None:
    comparison_label = normalize(field.group_label) or label
    best: tuple[float, ReusableAnswer] | None = None
    for answer in answers:
        candidate = normalize(answer.question)
        # Generic prompts must never fuzzy-match a real question. Short but
        # specific ones ("Name", "City") are handled by the exact matcher
        # above, so skipping them here costs nothing.
        if candidate in {"select", "choose", "field", "question", "answer"} or len(candidate) < 6:
            continue
        score = SequenceMatcher(None, comparison_label, candidate).ratio()
        # A containment boost is only meaningful when the two questions are of
        # comparable length. Otherwise a short saved question hijacks any long
        # employer question that happens to contain the word: "Country" was
        # answering "...require visa sponsorship to work in the country in
        # which this role is based?" with "United States".
        if candidate in comparison_label or comparison_label in candidate:
            # Length alone was too blunt: it rejected "State" for "State /
            # Territory". What actually distinguishes the bad case is that the
            # longer text is a *sentence*. A short saved answer may complete a
            # short label, but never claim a full employer question.
            longer = candidate if len(candidate) > len(comparison_label) else comparison_label
            shorter = comparison_label if longer is candidate else candidate
            comparable_length = len(longer) and len(shorter) / len(longer) >= 0.5
            if len(longer.split()) <= 6 or comparable_length:
                score = max(score, 0.95)
        if best is None or score > best[0]:
            best = (score, answer)
    if best is None or best[0] < 0.72:
        return None
    return boolean_value(best[1].answer, field), f"answer.{best[1].id}", best[0]


def map_exact_reusable_answer(
    label: str, field: FormField, answers: list[ReusableAnswer]
) -> tuple[str, str, float] | None:
    # The side panel saves an answer under exactly the label it showed the
    # user (``group_label or label``). Matching only against the combined
    # "label name" form missed those, so a saved answer for a short question
    # like "Name" or "Phone" never mapped and the panel asked for it forever.
    candidates = {
        value
        for value in (normalize(field.group_label), normalize(field.label), label)
        if value
    }
    for answer in reversed(answers):
        if normalize(answer.question) in candidates:
            return boolean_value(answer.answer, field), f"answer.{answer.id}", 1.0
    return None


def coerce_option(value: str, field: FormField) -> str:
    if not field.options:
        return value
    normalized_value = normalize(value)
    semantic = semantic_choice(normalized_value)
    if semantic:
        for option in field.options:
            if semantic_choice(normalize(f"{option.value} {option.label}")) == semantic:
                return usable_option_value(option.value, option.label)
    for option in field.options:
        if normalized_value in {normalize(option.value), normalize(option.label)}:
            return usable_option_value(option.value, option.label)
    for option in field.options:
        option_text = normalize(f"{option.value} {option.label}")
        if normalized_value.isdigit() and normalized_value in option_text.split():
            return usable_option_value(option.value, option.label)
    # Containment alone is ambiguous: "United States" is inside both "United
    # States of America" and "United States Minor Outlying Islands", and
    # taking the first match picked the wrong country on a live Workday form.
    # Rank the containing options so the closest one wins.
    contained = [
        (
            SequenceMatcher(None, normalized_value, normalize(option.label or option.value)).ratio(),
            option,
        )
        for option in field.options
        if normalized_value in normalize(f"{option.value} {option.label}")
        or normalize(f"{option.value} {option.label}") in normalized_value
    ]
    if contained:
        best_option = max(contained, key=lambda item: item[0])[1]
        return usable_option_value(best_option.value, best_option.label)
    fuzzy = max(
        (
            (
                SequenceMatcher(
                    None, normalized_value, normalize(option.label or option.value)
                ).ratio(),
                option,
            )
            for option in field.options
        ),
        key=lambda item: item[0],
    )
    if fuzzy[0] >= 0.82:
        return usable_option_value(fuzzy[1].value, fuzzy[1].label)
    return value


def usable_option_value(value: str, label: str) -> str:
    return label if normalize(value) in {"", "on"} else value


def semantic_choice(value: str) -> str:
    if any(phrase in value for phrase in ("prefer not", "decline", "do not wish")):
        return "decline"
    tokens = set(value.split())
    if value in {"yes", "true", "1"} or "yes" in tokens:
        return "yes"
    if (
        value in {"no", "false", "0"}
        or "no" in tokens
        or "do not have" in value
        or "not a protected veteran" in value
    ):
        return "no"
    return ""


def boolean_value(value: str | bool, field: FormField) -> str:
    if isinstance(value, bool):
        if field.field_type == "checkbox":
            return "true" if value else "false"
        return "Yes" if value else "No"
    return value


def checkbox_value(value: str, field: FormField) -> str:
    normalized = normalize(value)
    if normalized in {"yes", "true", "1", "on"}:
        return "true"
    if normalized in {"no", "false", "0", "off"}:
        return "false"
    choices = [normalize(item) for item in re.split(r"[,;|\n]+", value) if item.strip()]
    label = normalize(f"{field.option_label or field.label} {field.name}")
    return "true" if any(choice and choice in label for choice in choices) else "false"


def map_source_field(
    label: str, field: FormField, source_url: str
) -> tuple[str, str, float] | None:
    if not any(
        pattern_matches(label, pattern)
        for pattern in ("how did you find", "how did you hear", "source of application")
    ):
        return None
    source = normalize(source_url)
    if "linkedin com" in source:
        return coerce_option("LinkedIn", field), "job.source_url", 1.0
    if "indeed com" in source:
        return coerce_option("Indeed", field), "job.source_url", 1.0
    if "dice com" in source:
        return coerce_option("Dice", field), "job.source_url", 1.0
    return None


def is_resume_evidence_group(label: str) -> bool:
    normalized = normalize(label)
    return any(
        marker in normalized
        for marker in (
            "development languages",
            "programming languages",
            "tools you have hands on experience",
            "tools do you have experience",
            "cloud environments",
            "cloud platforms",
        )
    )


def resume_group_key(field: FormField) -> str:
    label = normalize(field.group_label or field.label)
    option = normalize(field.option_label)
    if option and label.endswith(option):
        label = label[: -len(option)].strip()
    return label


def resume_mentions_option(option: str, resume_text: str) -> bool:
    option = option.strip()
    if not option or not resume_text:
        return False
    lowered = resume_text.lower()
    special_patterns = {
        "c++": r"(?<!\w)c\+\+(?!\w)",
        "c#": r"(?<!\w)c#(?!\w)",
        "go": r"\b(?:Go|Golang)\b",
        "github ci": r"\bgithub\s+(?:ci|actions)\b",
        "gcp": r"\b(?:gcp|google\s+cloud(?:\s+platform)?)\b",
        "aws": r"\b(?:aws|amazon\s+web\s+services)\b",
        "azure": r"\b(?:(?:microsoft\s+)?azure)\b",
    }
    special = special_patterns.get(option.lower())
    if special:
        flags = 0 if option.lower() == "go" else re.IGNORECASE
        return re.search(special, resume_text, flags) is not None
    normalized_option = normalize(option)
    if len(normalized_option) < 2:
        return False
    expression = r"\b" + r"\s+".join(map(re.escape, normalized_option.split())) + r"\b"
    return re.search(expression, lowered) is not None


def split_name(name: str) -> tuple[str, str]:
    parts = name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def phone_country_code(phone: str, country: str) -> str:
    compact = re.sub(r"[^0-9+]", "", phone)
    match = re.match(r"^\+(\d{1,3})", compact)
    if match:
        digits = match.group(1)
        # NANP numbers use +1; taking three digits would consume the area code.
        if digits.startswith("1"):
            return "+1"
        return f"+{digits}"
    normalized_country = normalize(country)
    if normalized_country in {"united states", "usa", "us", "canada"}:
        return "+1"
    return ""


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def pattern_matches(label: str, pattern: str) -> bool:
    normalized_pattern = normalize(pattern)
    expression = r"\b" + r"\s+".join(map(re.escape, normalized_pattern.split())) + r"\b"
    return re.search(expression, label) is not None

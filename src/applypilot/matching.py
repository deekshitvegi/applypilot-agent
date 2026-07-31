"""Choosing an option the page itself offers.

The rule is closeness, not containment. "United States" must not select
"United States Minor Outlying Islands" merely because the string appears inside
it, and a control's own "No Selection" row is never an answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Option
from .text import contains_phrase, looks_like_placeholder, normalise, squash, tokens

# Synonyms are grouped by subject rather than pooled together, because short
# forms collide across subjects: MS is Mississippi to an address field and a
# Master's degree to an education field, and a single table has to pick one.
# Which groups apply is decided by the fact being answered.

_GENERAL: dict[str, tuple[str, ...]] = {
    "yes": ("y", "true", "yes i am", "yes i do", "yes i will", "i do", "i am", "affirmative"),
    "no": ("n", "false", "no i am not", "no i do not", "no i will not", "i do not", "negative"),
    "i don't wish to answer": (
        "prefer not to say",
        "prefer not to answer",
        "i do not wish to answer",
        "decline to self identify",
        "decline to answer",
        "i don't wish to provide this information",
        "choose not to disclose",
        "not disclosed",
    ),
}

_COUNTRY: dict[str, tuple[str, ...]] = {
    "united states": ("usa", "us", "u s", "u s a", "united states of america", "america"),
    "united kingdom": ("uk", "u k", "great britain", "britain", "england"),
}

_DEGREE: dict[str, tuple[str, ...]] = {
    # A resume says "M.S."; a dropdown offers "Master's Degree".
    "master's degree": (
        "ms", "m s", "msc", "m sc", "masters", "master", "master's", "ma", "m a",
        "mba", "m b a", "mtech", "m tech", "meng", "m eng", "master of science",
        "master of arts", "postgraduate", "post graduate",
    ),
    "bachelor's degree": (
        "bs", "b s", "bsc", "b sc", "bachelors", "bachelor", "bachelor's", "ba",
        "b a", "btech", "b tech", "beng", "b eng", "bachelor of science",
        "bachelor of arts", "undergraduate",
    ),
    "doctorate (phd)": ("phd", "ph d", "doctorate", "doctoral", "dphil", "doctor of philosophy"),
    "associate's degree": ("as", "aa", "associate", "associates", "associate's"),
    "high school diploma": ("high school", "hs diploma", "secondary school", "ged"),
}

_GENDER: dict[str, tuple[str, ...]] = {"male": ("man", "m"), "female": ("woman", "f")}

#: A form can ask for "Texas" or offer "TX"; both name the same place.
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}

_STATE: dict[str, tuple[str, ...]] = {
    name.lower(): (code.lower(),) for code, name in US_STATES.items()
}

SYNONYM_GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "general": _GENERAL,
    "country": _COUNTRY,
    "degree": _DEGREE,
    "gender": _GENDER,
    "state": _STATE,
}

#: Which extra vocabulary a given fact unlocks. Everything else gets "general"
#: only, so no address field can ever read "MS" as a Master's degree.
FACT_GROUPS: dict[str, tuple[str, ...]] = {
    "country": ("country",),
    "citizenship": ("country",),
    "state": ("state",),
    "education.degree": ("degree",),
    "gender": ("gender",),
}


def _reverse(groups: tuple[str, ...]) -> dict[str, str]:
    table: dict[str, str] = {}
    for group in groups:
        for canonical, forms in SYNONYM_GROUPS.get(group, {}).items():
            table.setdefault(squash(canonical), canonical)
            for form in forms:
                table.setdefault(squash(form), canonical)
    return table


def groups_for(fact_key: str) -> tuple[str, ...]:
    return ("general", *FACT_GROUPS.get(fact_key, ()))


def expand_state(text: str) -> str:
    """Turn a two-letter state code into the state's name, or leave it alone."""
    code = text.strip().upper()
    return US_STATES.get(code, text.strip())


def canonical_value(value: str, groups: tuple[str, ...] = ("general",)) -> str:
    """Fold a value onto its canonical spelling within the subjects that apply."""
    return _reverse(groups).get(squash(value), normalise(value))


#: Beyond this many extra characters, a containment match is a different thing
#: wearing a similar name. Asking beats guessing.
MAX_CONTAINMENT_LENGTH_GAP = 12

#: Anything below this is not offered as a selection.
ACCEPT_THRESHOLD = 400


@dataclass(frozen=True)
class OptionMatch:
    option: Option
    score: int
    reason: str


def _score(desired: str, option_label: str, groups: tuple[str, ...]) -> tuple[int, str]:
    want_norm = normalise(desired)
    have_norm = normalise(option_label)
    if not have_norm:
        return 0, "empty option"

    if want_norm == have_norm:
        return 1000, "exact label"

    if squash(desired) == squash(option_label):
        return 950, "exact ignoring punctuation"

    want_canon = canonical_value(desired, groups)
    have_canon = canonical_value(option_label, groups)
    if want_canon and want_canon == have_canon:
        return 900, "same value under a different spelling"

    want_tokens = tokens(want_norm)
    have_tokens = tokens(have_norm)
    if want_tokens and want_tokens == have_tokens:
        return 880, "same words"

    gap = abs(len(have_norm) - len(want_norm))

    if have_tokens[: len(want_tokens)] == want_tokens and want_tokens:
        # "United States" against "United States Minor Outlying Islands" lands
        # here; the gap penalty is what keeps it from being chosen.
        if gap > MAX_CONTAINMENT_LENGTH_GAP:
            return 0, f"option is {gap} characters longer than the value asked for"
        return 700 - gap, "option begins with the value"

    if want_tokens[: len(have_tokens)] == have_tokens and have_tokens:
        if gap > MAX_CONTAINMENT_LENGTH_GAP:
            return 0, f"value is {gap} characters longer than the option"
        return 650 - gap, "value begins with the option"

    if contains_phrase(have_norm, want_norm):
        if gap > MAX_CONTAINMENT_LENGTH_GAP:
            return 0, f"option is {gap} characters longer than the value asked for"
        return 560 - gap, "option contains the value"

    if contains_phrase(want_norm, have_norm):
        if gap > MAX_CONTAINMENT_LENGTH_GAP:
            return 0, f"value is {gap} characters longer than the option"
        return 520 - gap, "value contains the option"

    want_set, have_set = set(want_tokens), set(have_tokens)
    if want_set and want_set <= have_set and gap <= MAX_CONTAINMENT_LENGTH_GAP:
        return 460 - gap, "option includes every word of the value"

    return 0, "no relation"


def rank_options(
    desired: str, options: list[Option], fact_key: str = ""
) -> list[OptionMatch]:
    """Every usable option, best first. Placeholders and disabled rows drop out."""
    groups = groups_for(fact_key)
    ranked: list[OptionMatch] = []
    for option in options:
        if option.disabled:
            continue
        if looks_like_placeholder(option.label):
            # A control's own "- Select -" row is furniture, never an answer.
            continue
        score, reason = _score(desired, option.label, groups)
        if score <= 0:
            continue
        ranked.append(OptionMatch(option=option, score=score, reason=reason))
    ranked.sort(key=lambda m: (-m.score, len(m.option.label)))
    return ranked


def best_option(
    desired: str, options: list[Option], fact_key: str = ""
) -> OptionMatch | None:
    """The single option to select, or None when nothing is close enough.

    An ambiguous tie is treated as nothing: two options scoring the same is a
    question for the applicant, not a coin flip.
    """
    ranked = rank_options(desired, options, fact_key)
    if not ranked:
        return None
    top = ranked[0]
    if top.score < ACCEPT_THRESHOLD:
        return None
    if len(ranked) > 1 and ranked[1].score == top.score:
        return None
    return top


def real_options(options: list[Option]) -> list[Option]:
    """Options with the control's placeholder rows removed."""
    return [o for o in options if not o.disabled and not looks_like_placeholder(o.label)]

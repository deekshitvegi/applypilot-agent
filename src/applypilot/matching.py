"""Choosing an option the page itself offers.

The rule is closeness, not containment. "United States" must not select
"United States Minor Outlying Islands" merely because the string appears inside
it, and a control's own "No Selection" row is never an answer.
"""

from __future__ import annotations

import re
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

#: A number falling inside a band the option describes. Comfortably accepted:
#: the arithmetic either holds or it does not, so there is nothing here to be
#: half sure about. Two bands both containing the number would be a tie, and a
#: tie is still a question rather than a coin flip.
BAND_SCORE = 700


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


#: A band of numbers an option can stand for. Written out rather than guessed
#: at: every shape here is one a real form uses.
_BAND_PATTERNS = (
    # 18-24, 25 to 35, 51 - 100
    (r"^(\d+(?:\.\d+)?)\s*(?:-|--|to|through|thru|and)\s*(\d+(?:\.\d+)?)$", "between"),
    # 50+, 50 or more, over 50, 51 and above, at least 51
    (r"^(?:over|above|more\s+than|greater\s+than)\s+(\d+(?:\.\d+)?)$", "above"),
    (r"^(\d+(?:\.\d+)?)\s*\+$", "from"),
    (r"^(\d+(?:\.\d+)?)\s+(?:or|and)\s+(?:more|above|over|older|greater|higher)$", "from"),
    (r"^(?:at\s+least|minimum\s+of|no\s+less\s+than)\s+(\d+(?:\.\d+)?)$", "from"),
    # Under 18, less than 18, up to 24, 24 or fewer
    (r"^(?:under|below|less\s+than|fewer\s+than|younger\s+than)\s+(\d+(?:\.\d+)?)$", "below"),
    (r"^(?:up\s+to|at\s+most|maximum\s+of|no\s+more\s+than)\s+(\d+(?:\.\d+)?)$", "upto"),
    (r"^(\d+(?:\.\d+)?)\s+(?:or|and)\s+(?:less|fewer|under|below|younger)$", "upto"),
)

_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")

#: A unit a form puts after a band -- "5 to 10 years". Named rather than
#: allowed generally, so "25-35 Main Street" stays an address.
_BAND_UNIT_RE = re.compile(
    r"\s+(years?|yrs?|months?|mos?|weeks?|days?|hours?|hrs?|people|employees|"
    r"members|staff|percent|%|of\s+experience|years?\s+of\s+experience)$",
    re.IGNORECASE,
)


def _as_number(text: str) -> float | None:
    match = _NUMBER_RE.match(str(text or ""))
    return float(match.group(1)) if match else None


def band_contains(label: str, value: float) -> bool:
    """True when an option stands for a band of numbers that *value* falls in.

    A saved "25" answers a question offering "18-24 / 25-35 / 36-50", which is
    the same fact asked at a different resolution. The arithmetic is done here
    rather than guessed at by a model, and only a label that is *entirely* a
    band counts -- "Region 25-35" is a place, not a range.
    """
    text = _BAND_UNIT_RE.sub("", normalise(label)).strip()
    for pattern, shape in _BAND_PATTERNS:
        found = re.match(pattern, text, re.IGNORECASE)
        if not found:
            continue
        first = float(found.group(1))
        if shape == "between":
            return first <= value <= float(found.group(2))
        if shape == "above":
            return value > first
        if shape == "from":
            return value >= first
        if shape == "below":
            return value < first
        if shape == "upto":
            return value <= first
    return False


def rank_options(
    desired: str, options: list[Option], fact_key: str = ""
) -> list[OptionMatch]:
    """Every usable option, best first. Placeholders and disabled rows drop out."""
    groups = groups_for(fact_key)
    number = _as_number(desired)
    ranked: list[OptionMatch] = []
    for option in options:
        if option.disabled:
            continue
        if looks_like_placeholder(option.label):
            # A control's own "- Select -" row is furniture, never an answer.
            continue
        score, reason = _score(desired, option.label, groups)
        if score <= 0 and number is not None and band_contains(option.label, number):
            # The same fact, asked at a different resolution.
            score = BAND_SCORE
            reason = f"{desired} falls inside {option.label}"
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

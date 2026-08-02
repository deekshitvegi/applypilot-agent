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

#: A saved answer that opens by saying yes or no, offered a control that wants
#: only yes or no. Above the accept threshold because it is not a guess -- the
#: answer says which it is in its first word -- and below an ordinary wording
#: match, so a control that really does offer the full statute still wins it.
SAME_ANSWER_SHORTER = 500

#: The same answer, given in the form's own words. Below a wording match, so a
#: control offering the exact saved sentence still wins with it, and above the
#: threshold because agreeing on yes or no is not a guess.
SAME_MEANING = 450

#: An answer whose first word settles it. Kept to exactly that: a sentence that
#: merely contains "no" somewhere has settled nothing.
_OPENS_YES_NO = re.compile(r"^\s*(yes|no)\b", re.IGNORECASE)

#: Saying you would rather not answer. Checked first and never treated as
#: either answer: "I don't wish to answer" contains "don't", and counting that
#: as a No would answer a voluntary question on somebody's behalf.
_DECLINES = re.compile(
    r"\b(prefer\s+not|do\s*n[o']?t\s+wish|decline\s+to|choose\s+not\s+to|"
    r"rather\s+not\s+say|not\s+disclose|prefer\s+to\s+self)\b",
    re.IGNORECASE,
)

_SAYS_NO = re.compile(
    r"^no\b|\b(i\s+am\s+not|i'?m\s+not|i\s+do\s+not|i\s+don'?t|i\s+have\s+not|"
    r"i\s+haven'?t|do\s+not\s+have|does\s+not|am\s+not\s+a)\b",
    re.IGNORECASE,
)

_SAYS_YES = re.compile(
    r"^yes\b|\b(i\s+am|i'?m|i\s+have|i\s+identify|i\s+do|one\s+or\s+more)\b",
    re.IGNORECASE,
)


def _polarity(text: str) -> str:
    """Whether a sentence is saying yes, saying no, or declining to say.

    Equal-opportunity questions are asked in whole sentences and answered in
    whole sentences, and no two forms use the same ones. One offers "No, I am
    not a veteran under one of the classifications listed above"; the next
    offers "I am not a protected veteran". They are the same answer.

    Negative is tested before positive, because every negative sentence here
    contains a positive one: "I am not" contains "I am".
    """
    plain = normalise(text)
    if not plain or _DECLINES.search(plain):
        return "decline" if plain else ""
    if _SAYS_NO.search(plain):
        return "no"
    if _SAYS_YES.search(plain):
        return "yes"
    return ""


def _opens_with_yes_or_no(desired: str) -> str:
    """"No" or "yes" when the answer begins with it, otherwise "".

    Only when there is more to the answer than the word itself -- a saved
    answer of exactly "No" is matched perfectly well by the ordinary path, and
    this one exists for the long-form wordings the equal-opportunity questions
    use.
    """
    text = (desired or "").strip()
    match = _OPENS_YES_NO.match(text)
    if not match or len(text) <= len(match.group(1)) + 1:
        return ""
    return match.group(1).lower()


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


#: How money is written down, as opposed to how a number is. A currency mark
#: in front and separators between the thousands: "$100,000", "£75,000",
#: "₹12,00,000". None of it changes the number, and all of it defeated the
#: parser -- so a saved salary never became a number and never fell inside a
#: band, and every banded salary question on every form was refused.
_MONEY_DRESS_RE = re.compile(r"[$£€¥₹,\s]")


def _as_number(text: str) -> float | None:
    raw = str(text or "")
    match = _NUMBER_RE.match(raw)
    if match:
        return float(match.group(1))
    bare = _MONEY_DRESS_RE.sub("", raw)
    # Only when the dress was all that stood in the way. "25-35" is a band,
    # not a number, and must not become 2535 by having its middle removed.
    if bare and bare != raw and _NUMBER_RE.match(bare):
        return float(bare)
    return None


def band_contains(label: str, value: float) -> bool:
    """True when an option stands for a band of numbers that *value* falls in.

    A saved "25" answers a question offering "18-24 / 25-35 / 36-50", which is
    the same fact asked at a different resolution. The arithmetic is done here
    rather than guessed at by a model, and only a label that is *entirely* a
    band counts -- "Region 25-35" is a place, not a range.
    """
    text = _BAND_UNIT_RE.sub("", normalise(label)).strip()
    # A band of money is still a band. The currency marks and the separators
    # between thousands are how it is written, not part of the arithmetic.
    text = re.sub(r"[$£€¥₹]", "", text)
    text = re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", text).strip()
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
    wanted_polarity = _polarity(desired)
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
        # Said in the form's own words. Every option is scored the same way, so
        # two options meaning the same thing tie -- and a tie is refused, which
        # is the right answer when a form really is ambiguous.
        if (
            score <= 0
            and wanted_polarity in {"yes", "no"}
            and _polarity(option.label) == wanted_polarity
        ):
            score = SAME_MEANING
            reason = f'both say "{wanted_polarity}", in different words'
        if score <= 0:
            plain = _opens_with_yes_or_no(desired)
            if plain and normalise(option.label) == plain:
                # The same question, asked shorter. One form spells the veteran
                # question out in full and offers the statute back as the
                # answer; the next offers Yes and No. An answer beginning "No,
                # I am not..." has already said which it is, and refusing it
                # left a required question nobody could clear.
                score = SAME_ANSWER_SHORTER
                reason = f'"{desired[:40]}" begins by saying {option.label}'
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

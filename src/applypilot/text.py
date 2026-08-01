"""Label normalisation and phrase tests.

Every rule in this module is about the shape of a label, never about a
particular employer, question or applicant tracking system. The mapper leans on
these primitives to decide whether a saved fact is really an answer to the
question a page is asking.

Two token views exist on purpose:

``tokens``
    every word, prepositions included. Phrase tests ("is this alias the leading
    phrase of that label?") run over this view, because the word after a match
    is what tells you whether the rest of the label is a modifier of the alias
    or a different subject entirely.

``content_tokens``
    the same list minus stopwords. Set and coverage tests run over this view, so
    "What country are you in?" and "Country" compare equal.

Digits are never stripped. "Address Line 1" and "Address Line 2" are different
fields and the only thing that says so is the digit.
"""

from __future__ import annotations

import re
import unicodedata

# Words that carry no subject of their own. Prepositions are here so that they
# drop out of set comparisons, but they survive in ``tokens`` because the phrase
# rules need to see them.
STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "for", "in", "on", "at", "to", "from", "with", "by",
        "and", "or", "is", "are", "was", "were", "be", "been", "am", "do", "does",
        "did", "have", "has", "had", "will", "would", "can", "could", "shall",
        "should", "may", "might", "must", "you", "your", "yours", "i", "me", "my",
        "we", "us", "our", "this", "that", "these", "those", "it", "its", "as",
        "if", "then", "any", "all", "please", "kindly", "select", "choose", "enter",
        "provide", "specify", "what", "which", "who", "whom", "whose", "when",
        "where", "why", "how", "there", "here", "so", "not", "no", "yes",
    }
)

# Words that follow a preposition-like role: when an alias matches the start of a
# label and the very next word is one of these, the rest of the label is
# qualifying the alias rather than naming a different field.
CONNECTORS = frozenset(
    {"of", "for", "in", "at", "on", "to", "from", "with", "or", "and", "by", "as", "where", "you"}
)

# Words that make a label a *variant* of a field rather than the field itself.
# "Home Phone" is not "Phone"; "Previous Employer" is not "Employer". An alias
# that does not itself contain the modifier can never answer such a label.
DISTINGUISHING_MODIFIERS = frozenset(
    {
        "first", "last", "middle", "given", "family", "surname", "maiden",
        "preferred", "nick", "nickname", "former", "previous", "prior", "past",
        "next", "second", "secondary", "alternate", "alternative", "other",
        "emergency", "home", "work", "office", "business", "fax", "night",
        "evening", "daytime", "spouse", "partner", "parent", "guardian",
        "referrer", "referral", "manager", "supervisor", "recruiter",
        "confirm", "retype", "repeat", "verify",
        # "Date of Birth" must never be answered with today's date.
        "birth", "birthday", "dob",
    }
)

# Words that merely decorate a field name without changing which field it is.
NEUTRAL_QUALIFIERS = frozenset(
    {
        "legal", "full", "complete", "primary", "main", "current", "present",
        "personal", "contact", "candidate", "applicant", "employee", "official",
        "valid", "correct", "exact", "detail", "details", "info", "information",
        "field", "value", "text", "entry", "response", "answer",
    }
)

# Leading phrases that make a question a follow-up to some earlier answer. A
# saved general fact must never be inferred into one of these.
CONDITIONAL_PREFIXES = (
    "if yes", "if so", "if no", "if not", "if other", "if selected", "if checked",
    "if applicable", "if any", "if you answered", "if you selected", "if true",
    "if the answer", "if above", "if previously",
)

# Text a control shows when nothing has been chosen. Never an answer, never
# learned, never verified as a desired value.
PLACEHOLDER_PATTERNS = (
    r"^$",
    r"^-+$",
    r"^\.+$",
    r"^_+$",
    r"^no\s+selection$",
    r"^none\s+selected$",
    r"^nothing\s+selected$",
    r"^not\s+selected$",
    r"^select$",
    r"^select\b.*",
    r"^please\s+select.*",
    r"^choose\b.*",
    r"^pick\s+one$",
    r"^--.*--$",
    r"^\(.*\)$",
    r"^click\s+to\s+select.*",
    r"^type\s+to\s+search.*",
    r"^start\s+typing.*",
    r"^search\.\.\.$",
    r"^n/?a$",
    r"^tbd$",
    r"^optional$",
    r"^required$",
)

_PLACEHOLDER_RE = re.compile("|".join(f"(?:{p})" for p in PLACEHOLDER_PATTERNS), re.IGNORECASE)

# Decorations a form puts around a label without meaning to rename it.
_DECORATION_RE = re.compile(
    r"(\(\s*(required|optional|opt|mandatory)\s*\)|\brequired\b|\boptional\b|[*†‡•]|\bmust\s+be\s+filled\b)",
    re.IGNORECASE,
)

# Words that open a sentence question rather than name a field.
_INTERROGATIVE_OPENERS = frozenset(
    {
        "do", "does", "did", "are", "is", "was", "were", "have", "has", "had",
        "will", "would", "can", "could", "may", "might", "should", "must",
        "what", "which", "why", "how", "when", "where", "who", "please", "tell",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_TRAILING_DIGITS_RE = re.compile(r"(\d+)\s*$")


def normalise(text: str) -> str:
    """Fold a label to a comparable form, keeping digits and word order."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.replace("’", "'").replace("‘", "'")
    folded = re.sub(r"[‐-―]", "-", folded)
    folded = folded.lower()
    folded = _DECORATION_RE.sub(" ", folded)
    folded = folded.replace("&", " and ")
    folded = re.sub(r"\s+", " ", folded).strip()
    # A trailing question mark is decoration: "Country" and "Country?" are the
    # same question, and learned answers have to key the same way both times.
    return folded.strip(" :*-.,?!")


def tokens(text: str) -> list[str]:
    """Every word of *text*, prepositions and digits included."""
    return _TOKEN_RE.findall(normalise(text))


def content_tokens(text: str) -> list[str]:
    """The words of *text* that carry a subject."""
    return [t for t in tokens(text) if t not in STOPWORDS]


def alternatives(text: str) -> list[str]:
    """Expand ``A/B`` labels into the separate labels they stand for.

    "Country/Region of Residence" is two labels wearing one coat, and the saved
    Country answer belongs to the first of them.
    """
    norm = normalise(text)
    if "/" not in norm:
        return [norm]

    # A slash with spaces around it joins two whole phrases, either of which
    # names the field: "School / education institution" is a school and it is an
    # educational institution. Without this it matched neither.
    if " / " in norm:
        parts = [part.strip() for part in norm.split(" / ") if part.strip()]
        return parts or [norm]

    parts = norm.split(" ")
    slash_index = next((i for i, p in enumerate(parts) if "/" in p), None)
    if slash_index is None:
        return [norm]
    piece = parts[slash_index]
    sides = [s for s in piece.split("/") if s]
    # Only split when both sides read as words -- "24/7" and "9/2019" are values.
    if len(sides) < 2 or not all(re.fullmatch(r"[a-z][a-z'-]*", s) for s in sides):
        return [norm]
    out = []
    for side in sides:
        rebuilt = [*parts[:slash_index], side, *parts[slash_index + 1 :]]
        out.append(" ".join(rebuilt).strip())
    return out


def has_question_shape(text: str) -> bool:
    """True when a label reads as a sentence question rather than a field name."""
    norm = normalise(text)
    if not norm:
        return False
    if "?" in text:
        return True
    first = tokens(norm)[:1]
    return bool(first) and first[0] in _INTERROGATIVE_OPENERS


def is_conditional(text: str) -> bool:
    """True when a label is a follow-up to some earlier answer on the page."""
    norm = normalise(text)
    return any(norm.startswith(prefix) for prefix in CONDITIONAL_PREFIXES)


def looks_like_placeholder(text: str) -> bool:
    """True when text is a control's own 'nothing chosen yet' row."""
    if text is None:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    return bool(_PLACEHOLDER_RE.match(normalise(stripped) or stripped.lower()))


def numeric_suffix(text: str) -> str | None:
    """The trailing digits of a label, which separate 'Line 1' from 'Line 2'."""
    match = _TRAILING_DIGITS_RE.search(normalise(text))
    return match.group(1) if match else None


def contains_phrase(haystack: str, needle: str) -> bool:
    """Word-boundary containment. 'country' is not inside 'countryside'."""
    hay = tokens(haystack)
    ned = tokens(needle)
    if not ned or len(ned) > len(hay):
        return False
    return any(
        hay[start : start + len(ned)] == ned for start in range(len(hay) - len(ned) + 1)
    )


def leading_phrase_remainder(label: str, phrase: str) -> list[str] | None:
    """Tokens left over when *phrase* opens *label*, or None if it does not."""
    hay = tokens(label)
    ned = tokens(phrase)
    if not ned or len(ned) > len(hay):
        return None
    if hay[: len(ned)] != ned:
        return None
    return hay[len(ned) :]


def trailing_phrase_prefix(label: str, phrase: str) -> list[str] | None:
    """Tokens before *phrase* when it closes *label*, or None if it does not."""
    hay = tokens(label)
    ned = tokens(phrase)
    if not ned or len(ned) > len(hay):
        return None
    if hay[len(hay) - len(ned) :] != ned:
        return None
    return hay[: len(hay) - len(ned)]


def coverage(alias: str, label: str) -> float:
    """Share of the label's subject words that the alias accounts for."""
    label_content = set(content_tokens(label))
    if not label_content:
        return 0.0
    alias_content = set(content_tokens(alias))
    return len(alias_content & label_content) / len(label_content)


def pretty_label(text: str) -> str:
    """A label as it should be shown, with required markers taken off.

    Display only. The raw label is what decides whether a field is required, so
    it is never rewritten -- but "*GPA *" is nobody's idea of a question.
    """
    cleaned = re.sub(r"^[\s*†‡•:]+|[\s*†‡•:]+$", "", (text or "").strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def squash(text: str) -> str:
    """Comparison form with punctuation and spacing removed entirely."""
    return re.sub(r"[^a-z0-9]", "", normalise(text))

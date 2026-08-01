"""The catalogue of facts a profile can hold, and the vocabulary each one owns.

A fact is a thing that is true about the applicant. A label on a page is a way
of asking for one. This module is the only place that knows which phrasings
belong to which fact, and which words mark a question as being about something
else entirely.

Nothing here names an employer or an applicant tracking system.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FactScope(StrEnum):
    """Where a fact is allowed to answer."""

    ANY = "any"
    #: Only inside an education or employment block, or behind a label that can
    #: mean nothing else. Stops "Do you have a Bachelor's degree?" being answered
    #: with "M.S." and a non-compete question being answered with an employer.
    HISTORY = "history"


class Sensitivity(StrEnum):
    NORMAL = "normal"
    #: Voluntary self-identification. Never auto-answered unless the applicant
    #: saved that preference.
    DEMOGRAPHIC = "demographic"


@dataclass(frozen=True)
class FactSpec:
    key: str
    aliases: tuple[str, ...]
    kind: str = "text"
    #: Worked out at the time of filling rather than stored. Today's date is not
    #: something anyone should be asked to type into a form.
    computed: str = ""
    #: Words that make a label unmistakably about this fact. If a label carries
    #: a topic word owned by some other fact, this fact cannot answer it.
    topics: tuple[str, ...] = ()
    scope: FactScope = FactScope.ANY
    sensitivity: Sensitivity = Sensitivity.NORMAL
    #: Optional fields that are fine to leave blank when the profile has no
    #: value: asking for them turns a 13-question form into a 30-question one.
    supplementary: bool = False
    choices: tuple[str, ...] = ()
    prompt: str = ""
    help_text: str = ""
    record: str = ""
    record_field: str = ""
    onboarding_group: str = ""


def _f(key: str, *aliases: str, **kwargs: object) -> FactSpec:
    return FactSpec(key=key, aliases=tuple(aliases), **kwargs)  # type: ignore[arg-type]


YES_NO = ("Yes", "No")
PREFER_NOT = "I don't wish to answer"


FACTS: tuple[FactSpec, ...] = (
    # ---- identity -------------------------------------------------------
    _f(
        "full_name", "name", "full name", "legal name", "full legal name",
        "your name", "applicant name", "candidate name",
        prompt="Your full legal name", onboarding_group="identity",
    ),
    _f(
        "first_name", "first name", "given name", "forename", "first",
        "legal first name", "first (given) name",
        prompt="First name", onboarding_group="identity",
    ),
    _f(
        "middle_name", "middle name", "middle initial", "middle name or initial",
        supplementary=True, prompt="Middle name", onboarding_group="identity",
    ),
    _f(
        "last_name", "last name", "surname", "family name", "last",
        "legal last name", "last (family) name",
        prompt="Last name", onboarding_group="identity",
    ),
    _f(
        "preferred_name", "preferred name", "preferred first name", "nickname",
        "name you go by", "what do you go by",
        supplementary=True, prompt="Preferred name", onboarding_group="identity",
    ),
    _f(
        "pronouns", "pronouns", "your pronouns",
        supplementary=True, sensitivity=Sensitivity.DEMOGRAPHIC,
        prompt="Pronouns", onboarding_group="identity",
    ),
    # ---- contact --------------------------------------------------------
    _f(
        "email", "email", "email address", "e mail", "e mail address",
        "personal email", "contact email", "your email",
        kind="email", topics=("email",),
        prompt="Email address", onboarding_group="contact",
    ),
    _f(
        "phone", "phone", "phone number", "mobile", "mobile phone",
        "mobile number", "cell", "cell phone", "cell phone number",
        "telephone", "telephone number", "contact number", "contact phone",
        kind="tel", topics=("phone", "telephone", "mobile"),
        prompt="Phone number", onboarding_group="contact",
    ),
    _f(
        "phone_country_code", "phone country code", "country code", "dial code",
        supplementary=True, prompt="Phone country code", onboarding_group="contact",
    ),
    _f(
        "street_address", "address", "address line 1", "street address",
        "street", "street address line 1", "address 1", "mailing address",
        "home address", "current address", "residential address",
        topics=("address", "street"),
        prompt="Street address", onboarding_group="address",
    ),
    _f(
        "address_line_2", "address line 2", "address 2", "apartment", "apt",
        "suite", "unit", "apartment suite unit", "street address line 2",
        # Shares the "address" subject with street_address on purpose: the
        # trailing digit is what tells the two apart, not the topic.
        topics=("address",),
        supplementary=True, prompt="Apartment, suite or unit",
        onboarding_group="address",
    ),
    _f(
        "city", "city", "town", "city or town", "city town",
        "city of residence", "locality",
        topics=("city",), prompt="City", onboarding_group="address",
    ),
    _f(
        "state", "state", "province", "region", "state province",
        "state or province", "state region", "county state",
        "state of residence", "province of residence",
        topics=("state", "province"),
        prompt="State or province", onboarding_group="address",
    ),
    _f(
        "postal_code", "zip", "zip code", "zipcode", "postal code", "postalcode",
        "postcode", "zip postal code", "postal", "post code", "pin code", "pincode",
        topics=("zip", "zipcode", "postal", "postalcode", "postcode", "pincode"),
        prompt="ZIP or postal code", onboarding_group="address",
    ),
    _f(
        "country", "country", "country of residence", "country name",
        "nation", "country you live in", "country you are in",
        "country you reside in", "country region", "country or region",
        topics=("country",),
        prompt="Country", onboarding_group="address",
    ),
    _f(
        "linkedin", "linkedin", "linkedin profile", "linkedin url",
        "linkedin profile url", "linkedin page",
        topics=("linkedin",), supplementary=True,
        prompt="LinkedIn profile URL", onboarding_group="links",
    ),
    _f(
        "github", "github", "github url", "github profile", "github profile url",
        topics=("github",), supplementary=True,
        prompt="GitHub profile URL", onboarding_group="links",
    ),
    _f(
        "website", "website", "portfolio", "personal website", "website url",
        "portfolio url", "personal site", "web site",
        topics=("website", "portfolio"), supplementary=True,
        prompt="Personal website or portfolio", onboarding_group="links",
    ),
    # ---- eligibility ----------------------------------------------------
    _f(
        "work_authorization",
        "are you legally authorized to work", "legally authorized to work",
        "authorized to work", "work authorization", "work authorisation",
        "authorization to work", "eligible to work", "legally eligible to work",
        "right to work", "work eligibility",
        kind="choice", choices=YES_NO,
        topics=(
            "authorized", "authorised", "authorization", "authorisation",
            "eligible", "eligibility",
        ),
        prompt="Are you legally authorised to work in the country of the role?",
        onboarding_group="eligibility",
    ),
    _f(
        "requires_sponsorship",
        "will you require sponsorship", "do you require sponsorship",
        "require sponsorship", "need sponsorship", "visa sponsorship",
        "require visa sponsorship", "sponsorship", "immigration sponsorship",
        "require immigration sponsorship", "sponsorship for employment",
        "will you now or in the future require sponsorship",
        kind="choice", choices=YES_NO,
        topics=("sponsorship", "sponsor", "visa", "immigration", "h1b", "h 1b"),
        prompt="Will you now or in the future require visa sponsorship?",
        onboarding_group="eligibility",
    ),
    _f(
        "citizenship", "citizenship", "citizenship status", "nationality",
        "country of citizenship", "citizen of",
        topics=("citizenship", "citizen", "nationality"),
        prompt="Citizenship status", onboarding_group="eligibility",
        supplementary=True,
    ),
    _f(
        "over_18", "are you 18 or older", "are you at least 18",
        "18 years of age or older", "at least 18 years old",
        "are you over 18", "over 18", "18 or older", "age verification",
        kind="choice", choices=YES_NO,
        topics=("18", "age"),
        prompt="Are you 18 years of age or older?", onboarding_group="eligibility",
    ),
    _f(
        "background_check_consent",
        "background check", "consent to a background check",
        "do you consent to a background check", "background screening",
        "criminal background check", "background investigation",
        kind="choice", choices=YES_NO,
        topics=("background",),
        prompt="Do you consent to a background check if an offer is made?",
        onboarding_group="eligibility",
    ),
    _f(
        "drug_test_consent", "drug test", "drug screening", "pre employment drug test",
        kind="choice", choices=YES_NO, topics=("drug",), supplementary=True,
        prompt="Do you consent to a pre-employment drug screening?",
        onboarding_group="eligibility",
    ),
    _f(
        "security_clearance", "security clearance", "clearance",
        "do you hold a security clearance", "active security clearance",
        topics=("clearance",), supplementary=True,
        prompt="Security clearance", onboarding_group="eligibility",
    ),
    # ---- preferences ----------------------------------------------------
    _f(
        "willing_to_relocate", "are you willing to relocate", "willing to relocate",
        "open to relocation", "relocation", "would you relocate",
        "willing to relocate for this role",
        kind="choice", choices=YES_NO,
        topics=("relocate", "relocation"),
        prompt="Are you willing to relocate?", onboarding_group="preferences",
    ),
    _f(
        "notice_period", "notice period", "notice", "how much notice",
        "when can you start", "earliest start date", "availability to start",
        "available start date", "start date availability",
        # "start" is not owned here: it is the ordinary word in "Start date"
        # and "Start year", and owning it blocked both history start dates from
        # ever resolving.
        topics=("notice",),
        prompt="Notice period or earliest start date", onboarding_group="preferences",
    ),
    _f(
        "salary_expectation", "salary expectation", "salary expectations",
        "expected salary", "desired salary", "desired compensation",
        "compensation expectation", "compensation expectations",
        "salary requirement", "salary requirements", "expected compensation",
        "what are your salary expectations", "desired pay",
        topics=("salary", "compensation", "pay", "wage", "rate"),
        prompt="Salary expectation", onboarding_group="preferences",
    ),
    _f(
        "work_arrangement", "work arrangement", "remote or onsite",
        "work preference", "preferred work location type", "work model",
        topics=("remote", "onsite", "hybrid"), supplementary=True,
        prompt="Preferred work arrangement", onboarding_group="preferences",
    ),
    _f(
        "referral_source", "how did you hear about", "how did you hear about us",
        "how did you find this", "referral source", "source",
        "where did you hear about this role",
        topics=("hear", "referral", "source"), supplementary=True,
        prompt="How you usually hear about roles", onboarding_group="preferences",
    ),
    _f(
        "previously_employed", "have you ever been employed by",
        "previously employed by", "former employee",
        "have you worked here before", "are you a former employee",
        kind="choice", choices=YES_NO,
        topics=("formerly", "previously", "before"),
        prompt="Have you previously worked for the companies you apply to?",
        onboarding_group="preferences", supplementary=True,
    ),
    # ---- voluntary self-identification ----------------------------------
    _f(
        "gender", "gender", "gender identity", "what is your gender",
        kind="choice", topics=("gender",), sensitivity=Sensitivity.DEMOGRAPHIC,
        choices=("Male", "Female", "Non-binary", PREFER_NOT),
        prompt="Gender", onboarding_group="voluntary",
    ),
    _f(
        "race_ethnicity", "race", "ethnicity", "race ethnicity",
        "race or ethnicity", "ethnic background", "hispanic or latino",
        kind="choice", topics=("race", "ethnicity", "ethnic", "hispanic", "latino"),
        sensitivity=Sensitivity.DEMOGRAPHIC,
        prompt="Race / ethnicity", onboarding_group="voluntary",
    ),
    _f(
        "veteran_status", "veteran status", "veteran", "protected veteran",
        "are you a protected veteran", "military service",
        kind="choice", topics=("veteran", "military"),
        sensitivity=Sensitivity.DEMOGRAPHIC,
        prompt="Veteran status", onboarding_group="voluntary",
    ),
    _f(
        "disability_status", "disability", "disability status",
        "do you have a disability", "voluntary self identification of disability",
        kind="choice", topics=("disability", "disabled"),
        sensitivity=Sensitivity.DEMOGRAPHIC,
        prompt="Disability status", onboarding_group="voluntary",
    ),
    # ---- things the agent works out for itself --------------------------
    _f(
        "current_date", "current date", "today's date", "todays date", "date",
        "date signed", "signature date", "date of signature", "today",
        "date completed", "application date",
        kind="date", computed="today",
        # "Date of Birth" is guarded off by the birth modifier, and "Start Date"
        # and "End Date" by their own leading words, so this only claims a date
        # field that names no other subject.
    ),
    _f(
        "signature", "signature", "electronic signature", "e signature",
        "type your name to sign", "sign here", "signed by",
        computed="full_name",
    ),
    # ---- documents ------------------------------------------------------
    _f(
        "resume", "resume", "cv", "resume cv", "curriculum vitae",
        "upload resume", "attach resume", "resume upload",
        kind="file", topics=("resume", "cv"),
        # Not a setup question: it is uploaded in Settings, and asking for it as
        # a line of text to type is no use to anyone.
        prompt="Resume",
    ),
    _f(
        "cover_letter", "cover letter", "covering letter", "upload cover letter",
        kind="file", topics=("cover",), supplementary=True,
        prompt="Cover letter", onboarding_group="documents",
    ),
    # ---- structured history (scoped) ------------------------------------
    _f(
        "education.school", "school", "university", "college", "institution",
        "school name", "university name", "college name", "institution name",
        "name of school", "educational institution",
        scope=FactScope.HISTORY, record="education", record_field="school",
        topics=("school", "university", "college", "institution"),
    ),
    _f(
        "education.degree", "degree", "degree type", "degree earned",
        "level of education", "education level", "highest degree",
        scope=FactScope.HISTORY, record="education", record_field="degree",
        topics=("degree",),
    ),
    _f(
        "education.field_of_study", "field of study", "major", "discipline",
        "area of study", "course of study", "concentration", "subject",
        scope=FactScope.HISTORY, record="education", record_field="field_of_study",
        topics=("major", "discipline", "study"),
    ),
    _f(
        "education.start_date", "education start date", "school start date",
        "start date", "start year", "from year", "from",
        scope=FactScope.HISTORY, record="education", record_field="start_date",
    ),
    _f(
        "education.end_date", "education end date", "graduation date",
        "graduation year", "year of graduation", "year completed",
        "completion year", "end date", "to", "expected graduation",
        scope=FactScope.HISTORY, record="education", record_field="end_date",
    ),
    _f(
        "education.gpa", "gpa", "grade point average", "cgpa",
        scope=FactScope.HISTORY, record="education", record_field="gpa",
        supplementary=True, topics=("gpa",),
    ),
    _f(
        "experience.company", "company", "employer", "company name",
        "employer name", "organization", "organisation", "name of employer",
        scope=FactScope.HISTORY, record="experience", record_field="company",
        topics=("employer", "organization", "organisation"),
    ),
    _f(
        "experience.title", "title", "job title", "position", "role",
        "position title", "job position",
        scope=FactScope.HISTORY, record="experience", record_field="title",
        topics=("title",),
    ),
    _f(
        "experience.location", "location", "job location", "work location",
        scope=FactScope.HISTORY, record="experience", record_field="location",
    ),
    _f(
        "experience.start_date", "employment start date", "start date",
        "start year", "from year", "from",
        scope=FactScope.HISTORY, record="experience", record_field="start_date",
    ),
    _f(
        "experience.end_date", "employment end date", "end date",
        "end year", "to year", "to",
        scope=FactScope.HISTORY, record="experience", record_field="end_date",
    ),
    _f(
        "experience.current", "i currently work here", "current position",
        "currently employed here", "present",
        kind="choice", choices=YES_NO,
        scope=FactScope.HISTORY, record="experience", record_field="current",
    ),
    _f(
        "experience.description", "description", "responsibilities",
        "job description", "duties", "summary of responsibilities",
        scope=FactScope.HISTORY, record="experience", record_field="description",
        supplementary=True,
    ),
)


BY_KEY: dict[str, FactSpec] = {spec.key: spec for spec in FACTS}


def _build_topic_index() -> dict[str, frozenset[str]]:
    index: dict[str, set[str]] = {}
    for spec in FACTS:
        for topic in spec.topics:
            index.setdefault(topic, set()).add(spec.key)
    return {topic: frozenset(keys) for topic, keys in index.items()}


#: word -> the fact keys allowed to answer a label containing that word.
TOPIC_OWNERS: dict[str, frozenset[str]] = _build_topic_index()

#: Fact keys the applicant answers during onboarding, in the order asked.
ONBOARDING_ORDER: tuple[str, ...] = tuple(
    spec.key for spec in FACTS if spec.onboarding_group and not spec.supplementary
)

#: Keys that make up a structured record rather than a single value.
RECORD_FACTS: dict[str, list[FactSpec]] = {}
for _spec in FACTS:
    if _spec.record:
        RECORD_FACTS.setdefault(_spec.record, []).append(_spec)


HISTORY_ONLY_LABELS: frozenset[str] = frozenset(
    {
        "school", "university", "college", "institution", "school name",
        "university name", "college name", "institution name",
        "field of study", "major", "discipline", "area of study",
        "employer", "employer name", "degree", "gpa",
    }
)
"""Labels that can mean nothing but a history field, so they resolve without a
surrounding education or employment block. Everything else in
:data:`FactScope.HISTORY` needs the block, because "Company", "Position",
"Location" and "Start Date" are all things a page can ask for other reasons."""


DEMOGRAPHIC_KEYS: frozenset[str] = frozenset(
    spec.key for spec in FACTS if spec.sensitivity is Sensitivity.DEMOGRAPHIC
)


SUPPLEMENTARY_KEYS: frozenset[str] = frozenset(spec.key for spec in FACTS if spec.supplementary)


#: Extra field names that are optional decoration on nearly every form. When a
#: page marks one of these optional and the profile has nothing for it, it stays
#: blank instead of becoming a question.
SUPPLEMENTARY_LABELS: frozenset[str] = frozenset(
    {
        "middle name", "middle initial", "preferred name", "nickname",
        "home phone", "work phone", "office phone", "phone extension",
        "extension", "ext", "fax", "fax number", "county", "district",
        "address line 2", "apartment", "apt", "suite", "unit",
        "second email", "alternate email", "alternate phone", "pronouns",
        "salutation", "prefix", "suffix", "title prefix", "how did you hear about us",
    }
)


def alias_variants(spec: FactSpec) -> tuple[str, ...]:
    """Every phrasing of *spec*, longest first so specific beats generic."""
    return tuple(sorted(spec.aliases, key=lambda a: (-len(a.split()), -len(a))))

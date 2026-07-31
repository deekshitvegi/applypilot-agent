"""Recognising whose hiring system a page belongs to.

Two things come out of this: which applicant tracking system is in front of us,
and -- far more importantly -- whether the host is the employer, a job board, an
aggregator, or somebody else entirely.

That second question is answered here, from the URL, and never by a model. Asked
whether a listing "belongs to the expected employer", a model once said no,
correctly, and the runner halted on a page it was always going to start from.
Describing a page is a model's job. Deciding whether to stop is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .models import HostRole
from .text import normalise, squash


@dataclass(frozen=True)
class Adapter:
    name: str
    #: Host suffixes that identify this system, e.g. ".greenhouse.io".
    hosts: tuple[str, ...] = ()
    #: Hints the page itself reports, e.g. "marker:workday".
    markers: tuple[str, ...] = ()
    #: Paths that identify a single posting rather than a list of them.
    posting_paths: tuple[str, ...] = ()
    notes: str = ""


#: Systems an employer runs its own hiring on. A page on one of these is the
#: employer's page, whatever the domain happens to be called.
ATS_ADAPTERS: tuple[Adapter, ...] = (
    Adapter(
        "greenhouse", (".greenhouse.io", ".greenhouse.dev"), ("marker:greenhouse",), ("/jobs/",)
    ),
    Adapter("lever", (".lever.co",), ("marker:lever",), ("/",)),
    Adapter("ashby", (".ashbyhq.com",), ("marker:ashby",), ("/",)),
    Adapter(
        "workday",
        (".myworkdayjobs.com", ".myworkdaysite.com", ".workday.com", ".wd1.myworkdayjobs.com"),
        ("marker:workday",),
        ("/job/",),
    ),
    Adapter("smartrecruiters", (".smartrecruiters.com",), ("marker:smartrecruiters",), ("/",)),
    Adapter(
        "workable",
        (".workable.com",),
        ("marker:workable",),
        ("/j/",),
        notes="apply.workable.com/<slug> is one company's board, not the company",
    ),
    Adapter("recruitee", (".recruitee.com",), ("marker:recruitee",), ("/o/",)),
    Adapter(
        "successfactors",
        (".successfactors.com", ".successfactors.eu", ".sapsf.com", ".sapsf.eu"),
        ("marker:successfactors",),
        ("/job/",),
    ),
    Adapter(
        "phenom",
        (".phenompeople.com",),
        ("marker:phenom",),
        ("/job/",),
        notes="usually served from the employer's own careers.<company>.com",
    ),
    Adapter("icims", (".icims.com",), ("marker:icims",), ("/jobs/",)),
    Adapter("taleo", (".taleo.net", ".taleo.com"), ("marker:taleo",), ("/job/",)),
    Adapter("jobvite", (".jobvite.com",), ("marker:jobvite",), ("/job/",)),
    Adapter("breezy", (".breezy.hr",), (), ("/p/",)),
    Adapter("bamboohr", (".bamboohr.com", ".bamboohr.co.uk"), (), ("/jobs/view.php",)),
    Adapter("adp", (".adp.com",), ("marker:adp",), ("/mascsr/",)),
    Adapter("oracle", (".oraclecloud.com",), (), ("/job/",)),
    Adapter("jazzhr", (".applytojob.com", ".jazz.co"), (), ("/apply/",)),
    Adapter("teamtailor", (".teamtailor.com",), (), ("/jobs/",)),
    Adapter("personio", (".personio.de", ".jobs.personio.com"), (), ("/job/",)),
    Adapter("dayforce", (".dayforcehcm.com",), (), ("/CandidatePortal/",)),
    Adapter("ukg", (".ultipro.com", ".ukg.net"), (), ("/JobBoard/",)),
    Adapter("paylocity", (".paylocity.com",), (), ("/Details/",)),
    Adapter("paycom", (".paycomonline.net",), (), ("/jobs/",)),
    Adapter("rippling", (".rippling-ats.com", ".ats.rippling.com"), (), ("/jobs/",)),
    Adapter("gem", (".gem.com",), (), ("/jobs/",)),
)

#: Places to find jobs. The expected place to start, never the destination.
BOARD_HOSTS: tuple[str, ...] = (
    "linkedin.com",
    "indeed.com",
    "indeed.co.uk",
    "dice.com",
    "glassdoor.com",
    "glassdoor.co.uk",
    "ziprecruiter.com",
    "monster.com",
    "simplyhired.com",
    "careerbuilder.com",
    "wellfound.com",
    "angel.co",
    "builtin.com",
    "otta.com",
    "hired.com",
    "welcometothejungle.com",
    "seek.com.au",
    "naukri.com",
    "stackoverflow.com",
    "remoteok.com",
    "weworkremotely.com",
    "levels.fyi",
    "google.com",
)

#: Services that repackage other people's listings. Never the employer.
AGGREGATOR_HOSTS: tuple[str, ...] = (
    "jackandjill.ai",
    "jobright.ai",
    "simplify.jobs",
    "huntr.co",
    "teal.com",
    "tealhq.com",
    "sonara.ai",
    "lazyapply.com",
)

#: Two-part public suffixes that would otherwise look like a registrable domain.
_COMPOUND_SUFFIXES = (
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.in", "co.jp", "com.au", "com.br",
    "co.nz", "com.mx", "com.sg", "co.za", "com.tr", "com.cn",
)


def host_of(url: str) -> str:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def registrable_domain(host: str) -> str:
    """The part of a host an owner actually controls."""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    tail = ".".join(labels[-2:])
    if tail in _COMPOUND_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail


def _host_matches(host: str, suffix: str) -> bool:
    """Suffix match on label boundaries.

    ``example.com.evil.test`` does not match ``example.com``: the check is on
    whole labels, so a lookalike host is a different host.
    """
    suffix = suffix.lstrip(".")
    return host == suffix or host.endswith("." + suffix)


def detect_adapter(url: str, hints: list[str] | None = None) -> Adapter | None:
    """Which hiring system is serving this page."""
    host = host_of(url)
    for adapter in ATS_ADAPTERS:
        if any(_host_matches(host, suffix) for suffix in adapter.hosts):
            return adapter
    # A system an employer serves from its own domain -- Phenom on
    # careers.<company>.com is the common case -- can only be known from the
    # page itself.
    hint_set = {h.lower() for h in (hints or [])}
    for adapter in ATS_ADAPTERS:
        if hint_set & {m.lower() for m in adapter.markers}:
            return adapter
        if any(
            any(_host_matches(hint, suffix) for suffix in adapter.hosts)
            for hint in hint_set
            if "marker:" not in hint
        ):
            return adapter
    return None


def company_slug(name: str) -> str:
    """A company name reduced to something comparable with a domain."""
    stripped = re.sub(
        r"\b(inc|llc|ltd|limited|corp|corporation|company|co|plc|gmbh|sa|nv|ag|group|holdings|technologies|technology|labs|systems|solutions)\b",
        " ",
        normalise(name),
    )
    return squash(stripped)


@dataclass
class HostIdentity:
    url: str
    host: str
    domain: str
    role: HostRole
    adapter: str
    reason: str
    hints: list[str] = field(default_factory=list)

    @property
    def is_employer(self) -> bool:
        return self.role is HostRole.EMPLOYER


def classify_host(
    url: str, expected_company: str = "", hints: list[str] | None = None
) -> HostIdentity:
    """Decide, from the URL alone, whose page this is.

    A recognised hiring system is the employer. A recognised job board is where
    a search starts. Everything else is unknown, and only an unknown host is
    worth stopping on.
    """
    host = host_of(url)
    domain = registrable_domain(host)
    adapter = detect_adapter(url, hints)

    if adapter is not None:
        return HostIdentity(
            url=url,
            host=host,
            domain=domain,
            role=HostRole.EMPLOYER,
            adapter=adapter.name,
            reason=f"{adapter.name} is a hiring system an employer runs its own applications on",
            hints=list(hints or []),
        )

    for board in BOARD_HOSTS:
        if _host_matches(host, board):
            return HostIdentity(
                url, host, domain, HostRole.BOARD, "generic",
                f"{board} is a job board, which is where a search starts",
                list(hints or []),
            )

    for site in AGGREGATOR_HOSTS:
        if _host_matches(host, site):
            return HostIdentity(
                url, host, domain, HostRole.AGGREGATOR, "generic",
                f"{site} repackages other people's listings and is not the employer",
                list(hints or []),
            )

    slug = company_slug(expected_company)
    if slug and slug in squash(domain):
        return HostIdentity(
            url, host, domain, HostRole.EMPLOYER, "generic",
            f"{domain} is {expected_company}'s own domain",
            list(hints or []),
        )

    return HostIdentity(
        url, host, domain, HostRole.THIRD_PARTY, "generic",
        f"{domain or 'this host'} is not a hiring system, a job board, or the employer's domain",
        list(hints or []),
    )

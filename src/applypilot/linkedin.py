"""Reading LinkedIn's own data export.

LinkedIn will give you a copy of your own data: Settings and Privacy → Data
privacy → Get a copy of your data. The archive that arrives holds your
positions, your education and your skills as plain CSV, which is more than a
resume usually spells out.

This reads that archive. It does not sign in to LinkedIn, and it does not read
any page: signing in with LinkedIn returns a name, an email and a picture and
nothing else, so it would save nobody any work, and scraping a profile page is
against their terms. The export is the applicant's own data by the route
LinkedIn provides for it.

As with a resume, nothing here is inferred. A column the archive does not fill
comes back empty.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from .models import EducationRecord, ExperienceRecord
from .resume import ResumeExtract

#: Filenames inside the archive, matched loosely because LinkedIn has changed
#: the casing and spacing of these over the years.
_WANTED = {
    "profile": ("profile",),
    "positions": ("positions",),
    "education": ("education",),
    "skills": ("skills",),
    "emails": ("email addresses", "emailaddresses", "email"),
    "phones": ("phonenumbers", "phone numbers"),
}


class NotALinkedInExport(ValueError):
    """The file is not one of LinkedIn's archives."""


def _read_tables(data: bytes) -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise NotALinkedInExport(
            "that is not a .zip archive -- upload the file LinkedIn emails you"
        ) from exc

    for name in archive.namelist():
        stem = Path(name).stem.strip().lower()
        if not name.lower().endswith(".csv"):
            continue
        for key, spellings in _WANTED.items():
            if any(stem == spelling or stem.startswith(spelling) for spelling in spellings):
                with archive.open(name) as handle:
                    text = handle.read().decode("utf-8-sig", errors="replace")
                rows = list(csv.DictReader(io.StringIO(text)))
                tables.setdefault(key, []).extend(rows)
                break
    if not tables:
        raise NotALinkedInExport(
            "no LinkedIn data files were found in that archive -- it should contain "
            "Positions.csv and Education.csv"
        )
    return tables


def _get(row: dict[str, str], *names: str) -> str:
    """LinkedIn renames its columns; try the spellings it has used."""
    for name in names:
        for key, value in row.items():
            if (key or "").strip().lower() == name.lower():
                return (value or "").strip()
    return ""


def _positions(rows: list[dict[str, str]]) -> list[ExperienceRecord]:
    records = []
    for row in rows:
        company = _get(row, "Company Name", "Company")
        title = _get(row, "Title", "Position")
        if not company and not title:
            continue
        finished = _get(row, "Finished On", "End Date")
        records.append(
            ExperienceRecord(
                company=company,
                title=title,
                location=_get(row, "Location"),
                start_date=_get(row, "Started On", "Start Date"),
                end_date=finished,
                current=not finished,
                description=_get(row, "Description"),
            )
        )
    return records


def _education(rows: list[dict[str, str]]) -> list[EducationRecord]:
    records = []
    for row in rows:
        school = _get(row, "School Name", "School")
        degree = _get(row, "Degree Name", "Degree")
        if not school and not degree:
            continue
        records.append(
            EducationRecord(
                school=school,
                degree=degree,
                # LinkedIn keeps the subject inside the degree line rather than
                # in a column of its own, so it is left for the applicant to
                # fill rather than guessed at.
                field_of_study=_get(row, "Field Of Study", "Field of Study"),
                start_date=_get(row, "Start Date", "Started On"),
                end_date=_get(row, "End Date", "Finished On"),
            )
        )
    return records


def extract(data: bytes) -> ResumeExtract:
    """Read a LinkedIn archive into the same records a resume produces."""
    tables = _read_tables(data)
    result = ResumeExtract()

    for row in tables.get("profile", [])[:1]:
        first = _get(row, "First Name")
        last = _get(row, "Last Name")
        result.name = " ".join(part for part in (first, last) if part)
        result.location = _get(row, "Geo Location", "Location")
        websites = _get(row, "Websites")
        if websites:
            for piece in websites.replace("[", "").replace("]", "").split(","):
                url = piece.split(":", 1)[-1].strip()
                if url.startswith("http"):
                    result.website = url
                    break

    for row in tables.get("emails", []):
        if _get(row, "Primary").lower() in {"yes", "true"} or not result.email:
            result.email = _get(row, "Email Address", "Email")
        if _get(row, "Primary").lower() in {"yes", "true"}:
            break

    for row in tables.get("phones", [])[:1]:
        result.phone = _get(row, "Number", "Phone Number")

    result.experience = _positions(tables.get("positions", []))
    result.education = _education(tables.get("education", []))
    result.skills = [
        name for name in (_get(row, "Name", "Skill") for row in tables.get("skills", [])) if name
    ][:60]

    if not result.experience:
        result.notes.append("no positions were found in the archive")
    if not result.education:
        result.notes.append("no education entries were found in the archive")
    if result.education and not any(record.field_of_study for record in result.education):
        result.notes.append(
            "LinkedIn does not export a separate field of study, so add that in the "
            "education entries below"
        )
    return result

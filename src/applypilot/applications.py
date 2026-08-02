"""The record of what has been applied to.

Kept locally and encrypted like everything else. Status only ever moves to
``submitted`` on the strength of a confirmation signal from the page itself --
pressing the button is not evidence that anything was received.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from .adapters import classify_host
from .models import ApplicationRecord, PageObservation
from .store import Store

EXPORT_COLUMNS = (
    "applied_on", "company", "role", "status", "route", "url", "notes", "updated_at"
)


def record_for(
    store: Store, observation: PageObservation, company: str, role: str
) -> ApplicationRecord:
    """Find or start the record for the application being worked on."""
    existing = store.find_application_by_url(observation.url)
    if existing is not None:
        if company and not existing.company:
            existing.company = company
        if role and not existing.role:
            existing.role = role
        return store.upsert_application(existing)

    identity = classify_host(observation.url, company)
    return store.upsert_application(
        ApplicationRecord(
            company=company,
            role=role,
            url=observation.url,
            route=identity.adapter if identity.adapter != "generic" else identity.role.value,
            status="discovered",
        )
    )


def mark(store: Store, record: ApplicationRecord, status: str, note: str = "") -> ApplicationRecord:
    record.status = status  # type: ignore[assignment]
    if note:
        record.notes = f"{record.notes}\n{note}".strip()
    if status == "submitted" and record.applied_on is None:
        record.applied_on = date.today()
    return store.upsert_application(record)


def mark_submitted(
    store: Store, record: ApplicationRecord, confirmation: str
) -> tuple[ApplicationRecord, str]:
    """Only an on-page confirmation makes an application submitted.

    Without one the record says ready-to-submit and says why, rather than
    claiming something that was never observed.
    """
    if not confirmation:
        return (
            mark(store, record, "ready_to_submit", "no confirmation was shown on the page"),
            "I pressed submit but the page showed no confirmation, so I have not "
            "recorded this as submitted. Check the page.",
        )
    return (
        mark(store, record, "submitted", f"confirmed on the page: {confirmation}"),
        f"Submitted -- the page confirmed it: {confirmation}",
    )


def export_csv(store: Store) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in store.list_applications():
        writer.writerow(
            {
                "applied_on": record.applied_on.isoformat() if record.applied_on else "",
                "company": record.company,
                "role": record.role,
                "status": record.status,
                "route": record.route,
                "url": record.url,
                "notes": (record.notes or "").replace("\n", " ").strip(),
                "updated_at": record.updated_at.isoformat(timespec="seconds"),
            }
        )
    return buffer.getvalue()


def summary(store: Store) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in store.list_applications():
        counts[record.status] = counts.get(record.status, 0) + 1
    counts["total"] = sum(v for k, v in counts.items() if k != "total")
    return counts

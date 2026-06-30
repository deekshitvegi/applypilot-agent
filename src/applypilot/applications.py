from __future__ import annotations

from .models import (
    ApplicationCreate,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    ApplicationTransition,
    utc_now,
)


ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    "discovered": {"analyzed", "blocked", "abandoned"},
    "analyzed": {"materials_ready", "filling", "blocked", "abandoned"},
    "materials_ready": {"filling", "review_required", "blocked", "abandoned"},
    "filling": {"materials_ready", "review_required", "blocked", "abandoned"},
    "review_required": {"submitted", "materials_ready", "filling", "blocked", "abandoned"},
    "blocked": {"analyzed", "materials_ready", "filling", "abandoned"},
    "submitted": set(),
    "abandoned": set(),
}


class InvalidApplicationTransition(ValueError):
    pass


def create_application(request: ApplicationCreate) -> ApplicationRecord:
    record = ApplicationRecord(job=request.job, route=request.route)
    record.events.append(
        ApplicationEvent(
            event_type="application.created",
            message="Application session created from the active job.",
        )
    )
    return record


def transition_application(
    record: ApplicationRecord, transition: ApplicationTransition
) -> ApplicationRecord:
    if transition.status == record.status:
        return record
    if transition.status not in ALLOWED_TRANSITIONS[record.status]:
        raise InvalidApplicationTransition(
            f"Cannot transition application from {record.status} to {transition.status}"
        )

    previous = record.status
    record.status = transition.status
    record.updated_at = utc_now()
    record.blocked_reason = transition.message if transition.status == "blocked" else ""
    record.events.append(
        ApplicationEvent(
            event_type="application.transitioned",
            message=transition.message,
            metadata={"from": previous, "to": transition.status, **transition.metadata},
        )
    )
    return record

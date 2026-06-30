import pytest

from applypilot.applications import (
    InvalidApplicationTransition,
    create_application,
    transition_application,
)
from applypilot.models import ApplicationCreate, ApplicationTransition, JobContext


def test_application_lifecycle_records_audit_events() -> None:
    application = create_application(
        ApplicationCreate(
            job=JobContext(
                title="Software Engineer",
                company="Example Robotics",
                description="Build reliable Python automation.",
            )
        )
    )

    for status in ["analyzed", "materials_ready", "filling", "review_required", "submitted"]:
        application = transition_application(
            application,
            ApplicationTransition(status=status, message=f"Moved to {status}"),
        )

    assert application.status == "submitted"
    assert len(application.events) == 6
    assert application.events[-1].metadata["to"] == "submitted"


def test_terminal_application_cannot_transition() -> None:
    application = create_application(
        ApplicationCreate(job=JobContext(description="Test job description"))
    )
    application.status = "submitted"

    with pytest.raises(InvalidApplicationTransition):
        transition_application(
            application,
            ApplicationTransition(status="filling", message="Try again"),
        )


def test_blocked_application_can_recover() -> None:
    application = create_application(
        ApplicationCreate(job=JobContext(description="Test job description"))
    )
    application = transition_application(
        application,
        ApplicationTransition(status="blocked", message="Unknown required question"),
    )
    application = transition_application(
        application,
        ApplicationTransition(status="filling", message="Answer remembered"),
    )

    assert application.status == "filling"
    assert application.blocked_reason == ""

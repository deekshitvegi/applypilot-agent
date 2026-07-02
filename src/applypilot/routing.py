from __future__ import annotations

from .adapters import is_recognized_ats_url
from .models import ApplicationRouteDecision, JobApplicationOptions


def choose_application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    """Prefer a verified employer/ATS application over an aggregator form."""
    verified = options.company_url_verified or is_recognized_ats_url(
        options.company_application_url
    )
    if options.company_application_url and verified:
        return ApplicationRouteDecision(
            route="company_site",
            target_url=options.company_application_url,
            reason="A verified company or ATS application URL is available.",
        )

    if options.company_application_url and not verified:
        return ApplicationRouteDecision(
            route="manual_review",
            target_url=options.company_application_url,
            reason="The external application URL must be verified before it is opened.",
        )

    if options.external_apply_available:
        return ApplicationRouteDecision(
            route="company_button",
            target_url=options.source_url,
            reason="The job page provides a primary employer Apply button.",
        )

    if options.easy_apply_available:
        return ApplicationRouteDecision(
            route="easy_apply",
            target_url=options.source_url,
            reason="No company application URL is available; Easy Apply is the fallback.",
        )

    return ApplicationRouteDecision(
        route="unavailable",
        reason="No application route is currently available.",
    )

from __future__ import annotations

from .models import ApplicationRouteDecision, JobApplicationOptions


def choose_application_route(options: JobApplicationOptions) -> ApplicationRouteDecision:
    """Prefer a verified employer/ATS application over an aggregator form."""
    if options.company_application_url and options.company_url_verified:
        return ApplicationRouteDecision(
            route="company_site",
            target_url=options.company_application_url,
            reason="A verified company or ATS application URL is available.",
        )

    if options.company_application_url and not options.company_url_verified:
        return ApplicationRouteDecision(
            route="manual_review",
            target_url=options.company_application_url,
            reason="The external application URL must be verified before it is opened.",
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

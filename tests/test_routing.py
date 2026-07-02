from applypilot.models import JobApplicationOptions
from applypilot.routing import choose_application_route


def test_verified_company_site_wins_over_easy_apply() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.linkedin.com/jobs/view/example",
            company_application_url="https://careers.example.com/jobs/123/apply",
            company_url_verified=True,
            easy_apply_available=True,
        )
    )

    assert decision.route == "company_site"
    assert decision.target_url == "https://careers.example.com/jobs/123/apply"


def test_easy_apply_is_fallback_without_company_url() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.linkedin.com/jobs/view/example",
            easy_apply_available=True,
        )
    )

    assert decision.route == "easy_apply"


def test_linkedin_external_apply_button_wins_over_easy_apply_fallback() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.linkedin.com/jobs/view/example",
            external_apply_available=True,
            easy_apply_available=False,
        )
    )

    assert decision.route == "company_button"
    assert decision.target_url == "https://www.linkedin.com/jobs/view/example"


def test_generic_portal_apply_button_routes_to_employer_application() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.dice.com/job-detail/example",
            external_apply_available=True,
        )
    )

    assert decision.route == "company_button"
    assert decision.target_url == "https://www.dice.com/job-detail/example"


def test_unverified_external_url_requires_review() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.linkedin.com/jobs/view/example",
            company_application_url="https://short.example/abc",
            company_url_verified=False,
            easy_apply_available=True,
        )
    )

    assert decision.route == "manual_review"


def test_recognized_ats_url_is_verified_automatically() -> None:
    decision = choose_application_route(
        JobApplicationOptions(
            source_url="https://www.linkedin.com/jobs/view/example",
            company_application_url="https://jobs.lever.co/example/123",
            company_url_verified=False,
            easy_apply_available=True,
        )
    )

    assert decision.route == "company_site"

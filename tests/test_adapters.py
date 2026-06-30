from applypilot.adapters import detect_adapter, is_recognized_ats_url


def test_detects_supported_job_platforms() -> None:
    assert detect_adapter("https://www.linkedin.com/jobs/view/123") == "linkedin"
    assert detect_adapter("https://boards.greenhouse.io/example/jobs/123") == "greenhouse"
    assert detect_adapter("https://jobs.lever.co/example/123") == "lever"
    assert detect_adapter("https://example.wd5.myworkdayjobs.com/jobs/job/123") == "workday"
    assert detect_adapter("https://careers.example.com/jobs/123") == "generic"


def test_only_https_recognized_ats_urls_are_auto_verified() -> None:
    assert is_recognized_ats_url("https://jobs.lever.co/example/123") is True
    assert is_recognized_ats_url("http://jobs.lever.co/example/123") is False
    assert is_recognized_ats_url("https://lever.example.com/phishing") is False

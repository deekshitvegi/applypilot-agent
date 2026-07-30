"""Session-scoped sign-in details.

The risk that matters is not storage but aiming: releasing a credential for
the wrong site. These tests pin exact-host matching and the absence of any
persistence.
"""

from __future__ import annotations

import pytest

from applypilot.session_credentials import SessionCredentialVault, normalize_host


def vault() -> SessionCredentialVault:
    store = SessionCredentialVault()
    store.save("myworkdayjobs.com", "candidate@example.test", "correct horse")
    return store


def test_releases_the_credential_for_the_matching_host() -> None:
    match = vault().resolve("https://swinerton.wd1.myworkdayjobs.com/en-US/Careers/job/123")

    assert match is not None
    assert match.username == "candidate@example.test"
    assert match.password == "correct horse"


@pytest.mark.parametrize(
    "url",
    [
        "https://myworkdayjobs.com.evil.test/login",   # suffix impersonation
        "https://notmyworkdayjobs.com/login",          # substring, different host
        "https://jobs.lever.co/apply",                 # unrelated employer site
        "https://www.jackandjill.ai/",                 # the aggregator seen live
        "",
    ],
)
def test_never_releases_a_credential_to_another_site(url: str) -> None:
    assert vault().resolve(url) is None


def test_the_most_specific_host_wins() -> None:
    store = SessionCredentialVault()
    store.save("myworkdayjobs.com", "generic@example.test", "generic")
    store.save("swinerton.wd1.myworkdayjobs.com", "specific@example.test", "specific")

    match = store.resolve("https://swinerton.wd1.myworkdayjobs.com/job/1")

    assert match is not None
    assert match.username == "specific@example.test"


def test_listing_never_exposes_a_password() -> None:
    listed = vault().hosts()

    assert listed == [{"host": "myworkdayjobs.com", "username": "candidate@example.test"}]
    assert "password" not in str(listed)


def test_credentials_do_not_survive_the_session() -> None:
    store = vault()
    assert store.clear() == 1
    assert store.resolve("https://myworkdayjobs.com/login") is None
    # A fresh vault is what a restarted companion gets: nothing carried over.
    assert SessionCredentialVault().resolve("https://myworkdayjobs.com/login") is None


def test_incomplete_details_are_rejected() -> None:
    store = SessionCredentialVault()
    for host, username, password in [
        ("", "user", "pass"),
        ("example.test", "", "pass"),
        ("example.test", "user", ""),
    ]:
        with pytest.raises(ValueError):
            store.save(host, username, password)


def test_host_normalization_ignores_scheme_www_and_port() -> None:
    assert normalize_host("https://www.Example.test:443/login") == "example.test"
    assert normalize_host("example.test") == "example.test"

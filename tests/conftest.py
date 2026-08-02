"""Browser test plumbing.

The tests load the extension's own injected files -- the same bytes Chrome
loads -- so what is under test is the shipping code and not a copy of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EXTENSION = Path(__file__).resolve().parents[1] / "extension"
INJECTED_DIR = EXTENSION / "injected"

#: Load order matters: each file reads the namespaces below it at load time.
#: placeholders.js is not in injected/ because the panel loads it too -- one
#: list of what counts as a control's own "Choose one" row, rather than a copy
#: in each place that can drift.
INJECTED_ORDER = ("dom.js", "surface.js", "verify.js", "scan.js", "act.js")
SHARED_FIRST = (EXTENSION / "placeholders.js",)


@pytest.fixture(scope="session")
def playwright_browser():
    sync_api = pytest.importorskip(
        "playwright.sync_api", reason="run `python -m playwright install chromium`"
    )
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def open_fixture(playwright_browser):
    """Open a fixture with the real injected functions loaded into it."""
    contexts = []

    def _open(name: str):
        context = playwright_browser.new_context()
        contexts.append(context)
        page = context.new_page()
        # Keep the run hermetic: a fixture may reference an off-site iframe for
        # its markup, but nothing is fetched.
        page.route("http://**", lambda route: route.abort())
        page.route("https://**", lambda route: route.abort())
        page.goto((FIXTURES / name).as_uri())
        for shared in SHARED_FIRST:
            page.add_script_tag(path=str(shared))
        for filename in INJECTED_ORDER:
            page.add_script_tag(path=str(INJECTED_DIR / filename))
        return page

    yield _open

    for context in contexts:
        context.close()


@pytest.fixture
def scan(open_fixture):
    """Open a fixture and return (page, observation)."""

    def _scan(name: str):
        page = open_fixture(name)
        return page, page.evaluate("() => ApplyPilot.scan.run()")

    return _scan

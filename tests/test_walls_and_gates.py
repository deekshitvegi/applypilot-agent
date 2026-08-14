"""Pages that are a wall, told apart from pages this tool failed to read.

Both of these came back as "no controls found", which reads as a fault in the
reading. Neither was.

One large ATS puts "Create Account/Sign In, step 1 of 6" in front of every
application and offers nothing but two sign-in buttons -- no fields at all.
Another serves a whole-page bot check instead of the form. In both cases the
page was understood perfectly: there is nothing there for anybody who will not
make an account or answer a challenge, and this does neither.

Saying so is the difference between stopping with a reason and stopping with a
shrug -- and a shrug sent people looking for a bug in the scanner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.browser


ACCOUNT_GATE = """
<!doctype html><meta charset=utf-8><title>Apply</title>
<main>
  <h1>AI Infrastructure Software Engineer</h1>
  <p>current step 1 of 6 Create Account/Sign In</p>
  <button>Sign in with Google</button>
  <button>Sign in with email</button>
  <a href="/job">Back to Job Posting</a>
</main>
"""

#: The same wall, but a form has been reached. A "Sign in" link in a header is
#: on a great many real applications and must not turn them into walls.
FORM_WITH_A_SIGN_IN_LINK = """
<!doctype html><meta charset=utf-8><title>Apply</title>
<header><a href="/login">Sign in</a></header>
<form>
  <label for="a">First Name</label><input id="a">
  <label for="b">Last Name</label><input id="b">
  <label for="c">Email</label><input id="c" type="email">
  <label for="d">Phone</label><input id="d">
  <label for="e">Resume</label><input id="e" type="file">
</form>
"""

BOT_CHECK = """
<!doctype html><meta charset=utf-8><title>Apply</title>
<body>
<iframe src="https://geo.captcha-delivery.com/captcha/?initialCid=AHrlqAAA&hash=E5A9F"></iframe>
</body>
"""

LISTING_SAYING_INTERESTED = """
<!doctype html><meta charset=utf-8><title>Outside Plant Technician</title>
<main>
  <h1>Outside Plant Technician</h1>
  <a href="/oneclick-ui/company/X/publication/abc">I'm interested</a>
  <a href="/other">Not interested in this one</a>
</main>
"""


def scan_html(open_html, markup):
    page = open_html(markup)
    return page.evaluate("() => ApplyPilot.scan.run()")


EXTENSION = Path(__file__).resolve().parents[1] / "extension"
INJECTED_DIR = EXTENSION / "injected"
INJECTED_ORDER = ("dom.js", "surface.js", "verify.js", "scan.js", "act.js")
SHARED_FIRST = (EXTENSION / "placeholders.js",)


@pytest.fixture
def open_html(playwright_browser):
    """Set page markup directly, with the real injected functions loaded."""
    context = playwright_browser.new_context(bypass_csp=True)

    def _open(markup: str):
        page = context.new_page()
        # Hermetic: the bot-check markup names an off-site iframe, and its src
        # is the whole point, but nothing is fetched.
        page.route("http://**", lambda route: route.abort())
        page.route("https://**", lambda route: route.abort())
        page.set_content(markup)
        for shared in SHARED_FIRST:
            page.add_script_tag(path=str(shared))
        for filename in INJECTED_ORDER:
            page.add_script_tag(path=str(INJECTED_DIR / filename))
        return page

    yield _open
    context.close()


def test_a_page_that_only_offers_a_way_in_is_a_wall(open_html):
    observation = scan_html(open_html, ACCOUNT_GATE)
    assert observation["kind"] == "sign_in"


def test_a_form_with_a_sign_in_link_above_it_is_still_a_form(open_html):
    """Filling it is the whole job; calling it a wall would stop that."""
    observation = scan_html(open_html, FORM_WITH_A_SIGN_IN_LINK)
    assert observation["kind"] == "application"


def test_a_whole_page_bot_check_is_reported_as_a_challenge(open_html):
    """Not a widget beside a form -- served instead of the page.

    There is no size test worth doing on one of these: if it is on the page at
    all, it is the page.
    """
    observation = scan_html(open_html, BOT_CHECK)
    assert observation["captcha"] == "challenge"


def test_an_apply_button_is_not_always_called_apply(open_html):
    """"I'm interested" opens an application on a large ATS.

    It matched nothing, so those postings scanned as a page with no way into
    them -- and were reported as a form with no controls.
    """
    observation = scan_html(open_html, LISTING_SAYING_INTERESTED)
    texts = [c["text"] for c in observation.get("apply_controls") or []]
    assert any("interested" in t.lower() for t in texts)


def test_not_interested_is_not_an_apply_control(open_html):
    """The pattern is anchored, so the opposite word cannot match it."""
    observation = scan_html(open_html, LISTING_SAYING_INTERESTED)
    texts = [c["text"].lower() for c in observation.get("apply_controls") or []]
    assert not any(t.startswith("not interested") for t in texts)

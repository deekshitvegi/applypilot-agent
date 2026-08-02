"""Regression 79: a whole page filled in one trip into it.

Filling used to cost two messages per field -- one asking whether the tab was on
screen, one doing the work -- plus a full search of the document to find the
control, and a flat wait before reading anything back. Thirty fields paid all of
that thirty times.

What must not change is what the results mean. These tests exist to hold the
guarantees still while the speed moves: order is kept, every result is the
page's own state read afterwards, and a control that never takes its value is
still reported as failed.
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.browser

FORM = """
  <main>
    <label class="main-label">First name</label><input name="first">
    <label class="main-label">Last name</label><input name="last">
    <label class="main-label">City</label><input name="city">
    <label class="main-label">Country</label>
    <select name="country">
      <option value="">Choose</option><option>India</option><option>United States</option>
    </select>
    <label class="main-label">Locked</label>
    <input name="locked">
  </main>
"""


def build(page):
    page.evaluate("(html) => { document.body.innerHTML = html; }", FORM)
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    return {f["name"]: f["fingerprint"] for f in observation["fields"]}


def test_a_page_is_filled_in_one_call(open_fixture):
    page = open_fixture("repeating_entries.html")
    marks = build(page)

    results = page.evaluate(
        "async (a) => await ApplyPilot.act.performMany(a)",
        [
            {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
            {"kind": "fill", "fingerprint": marks["last"], "value": "Vegi"},
            {"kind": "fill", "fingerprint": marks["city"], "value": "Denton"},
            {
                "kind": "choose",
                "fingerprint": marks["country"],
                "option_label": "United States",
            },
        ],
    )
    assert [r["outcome"] for r in results] == ["verified"] * 4, results
    assert page.evaluate("() => document.querySelector('[name=first]').value") == "Deekshitth"
    assert page.evaluate("() => document.querySelector('[name=country]').value") == "United States"


def test_every_result_still_comes_from_the_page(open_fixture):
    """Not from the value we asked for: the signal names where it was read."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)

    results = page.evaluate(
        "async (a) => await ApplyPilot.act.performMany(a)",
        [
            {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
            {"kind": "choose", "fingerprint": marks["country"], "option_label": "India"},
        ],
    )
    assert results[0]["signal"] == "native_value"
    assert results[1]["signal"] == "native_select"
    assert all(r["observed"] for r in results)


def test_a_control_that_refuses_is_still_reported_as_failed(open_fixture):
    """One bad field does not take the rest of the page down with it."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)
    # A control that throws away whatever it is given, the way a picker that
    # only accepts its own options does.
    page.evaluate(
        """() => {
          const el = document.querySelector('[name=locked]');
          el.addEventListener('input', () => { el.value = ''; });
        }"""
    )

    results = page.evaluate(
        "async (a) => await ApplyPilot.act.performMany(a)",
        [
            {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
            {"kind": "fill", "fingerprint": marks["locked"], "value": "nope"},
            {"kind": "fill", "fingerprint": marks["last"], "value": "Vegi"},
        ],
    )
    assert results[0]["outcome"] == "verified"
    assert results[1]["outcome"] != "verified", results[1]
    assert results[2]["outcome"] == "verified", "the rest of the page still gets filled"
    assert page.evaluate("() => document.querySelector('[name=locked]').value") == ""


def test_the_order_they_were_planned_in_is_kept(open_fixture):
    """A form where one answer changes the next one depends on this."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)
    page.evaluate(
        """() => {
          window.seen = [];
          for (const el of document.querySelectorAll('input,select')) {
            el.addEventListener('change', () => window.seen.push(el.name));
          }
        }"""
    )
    page.evaluate(
        "async (a) => await ApplyPilot.act.performMany(a)",
        [
            {"kind": "fill", "fingerprint": marks["city"], "value": "Denton"},
            {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
            {"kind": "fill", "fingerprint": marks["last"], "value": "Vegi"},
        ],
    )
    # A fill dispatches more than one event per control; what matters is that
    # the controls were reached in the order they were planned.
    seen = page.evaluate("() => window.seen")
    order = [name for i, name in enumerate(seen) if i == 0 or seen[i - 1] != name]
    assert order == ["city", "first", "last"], seen


def test_a_remembered_control_is_checked_before_it_is_used(open_fixture):
    """The lookup is cached. A cache that lied would be worse than a slow one."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)

    page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
    )
    # Rebuild the page so the remembered element is gone and a different
    # control now sits where it was.
    page.evaluate(
        """() => {
          document.body.innerHTML =
            '<main><label class="main-label">Company</label><input name="company"></main>';
        }"""
    )
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
    )
    assert result["outcome"] == "failed", result
    assert page.evaluate("() => document.querySelector('[name=company]').value") == ""


def test_a_page_that_answers_at_once_is_not_waited_on(open_fixture):
    """There was a flat 120ms before every read-back, paid by every field."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)

    started = time.perf_counter()
    page.evaluate(
        "async (a) => await ApplyPilot.act.performMany(a)",
        [
            {"kind": "fill", "fingerprint": marks["first"], "value": "Deekshitth"},
            {"kind": "fill", "fingerprint": marks["last"], "value": "Vegi"},
            {"kind": "fill", "fingerprint": marks["city"], "value": "Denton"},
        ],
    )
    spent = (time.perf_counter() - started) * 1000
    assert spent < 360, f"three instant fields took {spent:.0f}ms"


def test_a_page_that_needs_a_moment_still_gets_one(open_fixture):
    """Dropping the wait must not turn a slow page into a failure."""
    page = open_fixture("repeating_entries.html")
    marks = build(page)
    page.evaluate(
        """() => {
          const el = document.querySelector('[name=city]');
          el.addEventListener('input', () => {
            const wanted = el.value;
            el.value = '';
            setTimeout(() => { el.value = wanted; }, 400);
          }, { once: true });
        }"""
    )
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "fill", "fingerprint": marks["city"], "value": "Denton"},
    )
    assert result["outcome"] == "verified", result
    assert result["observed"] == "Denton"

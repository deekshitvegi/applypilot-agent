"""Where does the time actually go when a page is filled?

Builds a form the size of a real application step, then drives the shipped
injected functions the way the panel drives them: one call per field, each with
its own trip into the page.
"""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("extension/injected")
FILES = ["dom.js", "surface.js", "verify.js", "scan.js", "act.js"]

FIELDS = 30

FORM = """<!doctype html><meta charset=utf-8><title>Bench</title><main>
%s
</main>""" % "\n".join(
    f"""<div class="form-group">
      <label class="main-label">Question number {i}</label>
      <input name="q{i}">
    </div>"""
    for i in range(FIELDS)
)


def load(page):
    for name in FILES:
        page.add_script_tag(content=(ROOT / name).read_text(encoding="utf-8"))


def timed(label, fn):
    started = time.perf_counter()
    value = fn()
    ms = (time.perf_counter() - started) * 1000
    print(f"  {label:<46} {ms:8.1f} ms")
    return value, ms


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(bypass_csp=True)
    page.set_content(FORM)
    load(page)

    print(f"\nA form with {FIELDS} text fields.\n")

    observation, scan_ms = timed("one scan.run()", lambda: page.evaluate("() => ApplyPilot.scan.run()"))
    fields = observation["fields"]
    print(f"  ({len(fields)} fields seen)\n")

    actions = [
        {"kind": "fill", "fingerprint": f["fingerprint"], "value": f"answer {i}"}
        for i, f in enumerate(fields)
    ]

    # How the panel does it today: one round trip per field.
    started = time.perf_counter()
    per_field = []
    for action in actions:
        one = time.perf_counter()
        page.evaluate("async (a) => await ApplyPilot.act.perform(a)", action)
        per_field.append((time.perf_counter() - one) * 1000)
    one_at_a_time = (time.perf_counter() - started) * 1000

    print(f"  one call per field, {len(actions)} fields         {one_at_a_time:8.1f} ms")
    print(f"    slowest single field                       {max(per_field):8.1f} ms")
    print(f"    median single field                        "
          f"{sorted(per_field)[len(per_field) // 2]:8.1f} ms")

    # Everything in one trip into the page instead.
    page.evaluate("() => { for (const el of document.querySelectorAll('input')) el.value = ''; }")
    _, batched = timed(
        "the same fields in one call",
        lambda: page.evaluate(
            """async (actions) => {
              const out = [];
              for (const a of actions) out.push(await ApplyPilot.act.perform(a));
              return out;
            }""",
            actions,
        ),
    )

    print(f"\n  round-trip overhead alone      "
          f"{one_at_a_time - batched:8.1f} ms  "
          f"({(one_at_a_time - batched) / max(one_at_a_time, 1) * 100:.0f}% of the total)")
    print(f"  per round trip                 {(one_at_a_time - batched) / len(actions):8.1f} ms\n")

    browser.close()

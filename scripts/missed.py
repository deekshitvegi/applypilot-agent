"""Controls a person can see that the scan never mentions.

The complaint is not that the wrong value goes in. It is that a field is
sitting there on the page, plainly visible, and the panel neither fills it nor
asks about it -- it behaves as though the field does not exist. A pixel-based
agent does not have that failure, because it is looking at the same picture the
applicant is.

So this counts the gap. Every control a browser considers on-screen, against
every control the scan reported, on real application forms. What comes back is
a list of the ones nobody was ever offered, with enough about each to say why
it was dropped.

    python scripts/missed.py --limit 20
    python scripts/missed.py --url https://boards.greenhouse.io/.../jobs/123
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECTED_DIR = ROOT / "extension" / "injected"
SHARED_FIRST = [ROOT / "extension" / "placeholders.js"]
INJECTED_ORDER = ["dom.js", "surface.js", "verify.js", "scan.js", "act.js"]
TARGETS = ROOT / "corpus" / "targets.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

#: What a person would call a question on a form. Deliberately generous: the
#: point is to find what we are missing, so anything a browser lays out and a
#: person could type in, pick from or tick belongs in the count.
VISIBLE_CONTROLS = """
() => {
  const out = [];
  const skip = new Set(["hidden", "submit", "button", "image", "reset"]);

  function labelFor(el) {
    if (el.labels && el.labels[0] && el.labels[0].innerText) {
      return el.labels[0].innerText.trim().slice(0, 60);
    }
    for (const attr of ["aria-label", "placeholder", "name", "id"]) {
      const said = el.getAttribute(attr);
      if (said) return said.trim().slice(0, 60);
    }
    const wrap = el.closest("label, .field, [class*=field], [class*=form-group]");
    if (wrap && wrap.innerText) return wrap.innerText.trim().slice(0, 60);
    return "";
  }

  function walk(root) {
    const found = root.querySelectorAll(
      "input, select, textarea, [role=combobox], [role=checkbox], [role=switch], [contenteditable=true]"
    );
    for (const el of found) {
      const type = (el.getAttribute("type") || el.type || "").toLowerCase();
      if (skip.has(type)) continue;
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const drawn =
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        (rect.width > 1 || rect.height > 1 || type === "file" ||
         type === "checkbox" || type === "radio");
      if (!drawn) continue;
      out.push({
        tag: (el.tagName || "").toLowerCase(),
        type: type,
        label: labelFor(el),
        name: el.getAttribute("name") || el.getAttribute("id") || "",
        required: Boolean(el.required || el.getAttribute("aria-required") === "true"),
        w: Math.round(rect.width),
        h: Math.round(rect.height),
      });
    }
    for (const el of root.querySelectorAll("*")) {
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  }
  walk(document);
  return out;
}
"""


def load_scripts() -> list[str]:
    scripts = [p.read_text(encoding="utf-8") for p in SHARED_FIRST]
    scripts += [(INJECTED_DIR / n).read_text(encoding="utf-8") for n in INJECTED_ORDER]
    return scripts


def key_of(control: dict) -> str:
    """Something stable enough to match the two lists on."""
    return (control.get("name") or control.get("label") or "").strip().lower()


def look(page, target: dict, scripts: list[str], timeout: int) -> dict:
    page.goto(target["url"], timeout=timeout, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    for source in scripts:
        page.add_script_tag(content=source)

    seen = page.evaluate(VISIBLE_CONTROLS)
    observation = page.evaluate("() => ApplyPilot.scan.run()")
    scanned = observation.get("fields") or []

    scanned_keys = set()
    for field in scanned:
        for candidate in (
            field.get("attr_label"),
            field.get("display_label"),
            field.get("label"),
        ):
            if candidate:
                scanned_keys.add(str(candidate).strip().lower())

    missed = []
    for control in seen:
        key = key_of(control)
        if not key:
            missed.append(control)
            continue
        if key in scanned_keys:
            continue
        if any(key in s or s in key for s in scanned_keys if s):
            continue
        missed.append(control)

    return {
        "company": target.get("company", ""),
        "ats": target.get("ats", ""),
        "url": target.get("url", ""),
        "kind": observation.get("kind", ""),
        "on_page": len(seen),
        "scanned": len(scanned),
        "missed": missed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--url", default="")
    parser.add_argument("--ats", default="")
    parser.add_argument("--timeout", type=int, default=45000)
    args = parser.parse_args()

    if args.url:
        targets = [{"ats": "given", "company": "given", "url": args.url}]
    else:
        targets = json.loads(TARGETS.read_text(encoding="utf-8"))
        if args.ats:
            targets = [t for t in targets if t.get("ats") in set(args.ats.split(","))]
        targets = targets[: args.limit]

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    scripts = load_scripts()
    on_page = scanned = 0
    shapes: collections.Counter = collections.Counter()
    examples: dict[str, dict] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(bypass_csp=True, user_agent=USER_AGENT)
        for index, target in enumerate(targets, 1):
            page = context.new_page()
            head = f"[{index}/{len(targets)}] {target.get('ats')}/{target.get('company')}"
            try:
                result = look(page, target, scripts, args.timeout)
            except (PlaywrightTimeout, PlaywrightError) as err:
                print(f"  {head}: could not open -- {str(err).splitlines()[0][:60]}")
                continue
            finally:
                page.close()

            on_page += result["on_page"]
            scanned += result["scanned"]
            gap = len(result["missed"])
            print(
                f"  {head}: {result['on_page']} on the page, "
                f"{result['scanned']} scanned, {gap} never offered"
            )
            for control in result["missed"]:
                shape = f"{control['tag']}[{control['type'] or '-'}]"
                shapes[shape] += 1
                examples.setdefault(shape, control)
        browser.close()

    print(f"\n{on_page} controls a person can see")
    print(f"{scanned} the scan reported")
    if on_page:
        print(f"{on_page - scanned} unaccounted for ({100 * (on_page - scanned) // on_page}%)")
    print("\nwhat the missed ones look like:")
    for shape, count in shapes.most_common(20):
        sample = examples[shape]
        print(f"  {count:4}  {shape:22} e.g. {sample['label'][:44]!r} "
              f"({sample['w']}x{sample['h']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Move all three versions together, because doing it by hand does not work.

The version lives in three files and CI fails the build unless they agree. Two
of them are next to each other in every change; pyproject.toml is not, and it
sat at 1.75.0 for seven releases while the other two moved. Every one of those
pushes turned the build red and sent somebody an email about it.

    python scripts/bump.py            # 1.82.0 -> 1.83.0
    python scripts/bump.py --patch    # 1.82.0 -> 1.82.1
    python scripts/bump.py --set 2.0.0
    python scripts/bump.py --check    # what CI checks, before pushing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "extension" / "manifest.json"
INIT = ROOT / "src" / "applypilot" / "__init__.py"
PYPROJECT = ROOT / "pyproject.toml"


def read() -> dict[str, str]:
    return {
        "extension/manifest.json": json.loads(MANIFEST.read_text(encoding="utf-8"))["version"],
        "src/applypilot/__init__.py": re.search(
            r'__version__ = "([^"]+)"', INIT.read_text(encoding="utf-8")
        ).group(1),
        "pyproject.toml": re.search(
            r'^version = "([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.M
        ).group(1),
    }


def write(version: str) -> None:
    for path, pattern, replacement in (
        (MANIFEST, r'"version": "[^"]+"', f'"version": "{version}"'),
        (INIT, r'__version__ = "[^"]+"', f'__version__ = "{version}"'),
        (PYPROJECT, r'^version = "[^"]+"', f'version = "{version}"'),
    ):
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(pattern, replacement, text, count=1, flags=re.M), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", action="store_true", help="bump the last number instead")
    parser.add_argument("--set", dest="exact", default="", help="an exact version")
    parser.add_argument("--check", action="store_true", help="only report whether they agree")
    args = parser.parse_args()

    current = read()
    if args.check:
        for path, version in current.items():
            print(f"  {version:10} {path}")
        if len(set(current.values())) == 1:
            print("\nall three agree")
            return 0
        print("\nthese do not agree -- CI fails on exactly this", file=sys.stderr)
        return 1

    highest = max(current.values(), key=lambda v: [int(p) for p in v.split(".")])
    if args.exact:
        version = args.exact
    else:
        major, minor, patch = (int(p) for p in highest.split("."))
        version = f"{major}.{minor}.{patch + 1}" if args.patch else f"{major}.{minor + 1}.0"

    write(version)
    for path, was in current.items():
        print(f"  {was:10} -> {version:10} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

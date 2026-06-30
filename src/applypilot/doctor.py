from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .config import Settings, settings
from .store import ProfileStore


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


def run_checks(config: Settings, root: Path | None = None) -> list[DoctorCheck]:
    root = root or Path.cwd()
    checks = [
        DoctorCheck(
            name="python",
            ok=sys.version_info >= (3, 11),
            detail=f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        DoctorCheck(
            name="environment",
            ok=(root / ".env").exists(),
            detail="Local .env exists" if (root / ".env").exists() else "Run the setup script",
        ),
        _provider_check(config),
        DoctorCheck(
            name="extension",
            ok=_extension_is_complete(root / "extension"),
            detail="Chrome/Edge extension files are complete",
        ),
        DoctorCheck(
            name="dependencies",
            ok=_dependencies_are_available(),
            detail="Python runtime dependencies are importable",
        ),
        _database_check(config.database_path),
        _server_check(config),
    ]
    return checks


def _extension_is_complete(directory: Path) -> bool:
    required = {
        "manifest.json",
        "service-worker.js",
        "sidepanel.html",
        "sidepanel.js",
        "sidepanel.css",
        "options.html",
        "options.js",
        "options.css",
    }
    return directory.is_dir() and required.issubset(
        {path.name for path in directory.iterdir() if path.is_file()}
    )


def _dependencies_are_available() -> bool:
    return all(
        importlib.util.find_spec(module) is not None
        for module in (
            "fastapi",
            "google.genai",
            "httpx",
            "cryptography",
            "docx",
            "pypdf",
            "reportlab",
        )
    )


def _provider_check(config: Settings) -> DoctorCheck:
    try:
        local = ProfileStore(config.database_path).get_provider_config()
    except (OSError, ValueError):
        local = None
    if local is not None:
        return DoctorCheck(
            "ai_provider",
            True,
            f"{local.provider.title()} configured for {local.model} in encrypted local storage",
            required=False,
        )
    environment_keys = {
        "gemini": config.gemini_api_key,
        "openai": config.openai_api_key,
        "anthropic": config.anthropic_api_key,
    }
    configured = next((name for name, key in environment_keys.items() if key), "")
    if configured:
        return DoctorCheck(
            "ai_provider",
            True,
            f"{configured.title()} configured from the local environment",
            required=False,
        )
    return DoctorCheck(
        "ai_provider",
        False,
        "No provider configured yet; connect one securely in the side panel",
        required=False,
    )


def _database_check(database_path: Path) -> DoctorCheck:
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        probe = database_path.parent / ".applypilot-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return DoctorCheck("storage", True, f"Local storage is writable: {database_path.parent}")
    except OSError as exc:
        return DoctorCheck("storage", False, f"Local storage is not writable: {exc}")


def _server_check(config: Settings) -> DoctorCheck:
    try:
        with urlopen(f"http://{config.host}:{config.port}/health", timeout=0.75) as response:
            payload = json.loads(response.read())
        ok = payload.get("status") == "ok" and payload.get("mode") == "local"
        detail = f"Local service is running (version {payload.get('version', 'unknown')})"
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        ok = False
        detail = "Local service is not running; start it after configuration"
    return DoctorCheck("service", ok, detail, required=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the local ApplyPilot installation")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    arguments = parser.parse_args()
    checks = run_checks(settings)

    if arguments.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        for check in checks:
            marker = "PASS" if check.ok else ("WARN" if not check.required else "FAIL")
            print(f"[{marker}] {check.name}: {check.detail}")

    if any(check.required and not check.ok for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

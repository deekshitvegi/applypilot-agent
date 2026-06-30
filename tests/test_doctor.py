from pathlib import Path

from applypilot.config import Settings
from applypilot.doctor import run_checks


EXTENSION_FILES = {
    "manifest.json",
    "service-worker.js",
    "sidepanel.html",
    "sidepanel.js",
    "sidepanel.css",
    "options.html",
    "options.js",
    "options.css",
}


def create_installation(root: Path) -> None:
    (root / ".env").write_text("GEMINI_API_KEY=test\n", encoding="utf-8")
    extension = root / "extension"
    extension.mkdir()
    for filename in EXTENSION_FILES:
        (extension / filename).write_text("test", encoding="utf-8")


def test_doctor_required_checks_pass_for_configured_installation(tmp_path: Path) -> None:
    create_installation(tmp_path)
    config = Settings(
        database_path=tmp_path / "data" / "applypilot.sqlite3",
        gemini_api_key="configured-test-key",
        host="127.0.0.1",
        port=1,
    )

    checks = run_checks(config, tmp_path)

    required = [check for check in checks if check.required]
    assert all(check.ok for check in required)
    assert next(check for check in checks if check.name == "service").required is False


def test_doctor_reports_missing_provider_without_revealing_values(tmp_path: Path) -> None:
    create_installation(tmp_path)
    config = Settings(
        database_path=tmp_path / "data" / "applypilot.sqlite3",
        gemini_api_key="",
        host="127.0.0.1",
        port=1,
    )

    checks = run_checks(config, tmp_path)
    provider = next(check for check in checks if check.name == "ai_provider")

    assert provider.ok is False
    assert provider.required is False
    assert "side panel" in provider.detail

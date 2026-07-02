from html.parser import HTMLParser
from pathlib import Path


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        element_id = dict(attrs).get("id")
        if element_id:
            self.ids.append(element_id)


def test_simplified_sidepanel_has_unique_required_targets() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = _IdCollector()
    parser.feed((root / "extension" / "sidepanel.html").read_text(encoding="utf-8"))

    assert len(parser.ids) == len(set(parser.ids))
    assert {
        "settings-drawer",
        "settings-backdrop",
        "preferences-pane",
        "profile-pane",
        "chat-question-slot",
        "unknown-answer-form",
        "cover-letter-policy",
        "cover-letter-file",
        "cover-letter-status",
    }.issubset(parser.ids)

    script = (root / "extension" / "sidepanel.js").read_text(encoding="utf-8")
    assert "persistUnknownAnswer(message, { appendUser: false })" in script
    assert "/api/resumes/active/file-status" in script
    assert "looksLikeChatQuestion(message)" in script
    assert "correctLastSavedAnswer(correction)" in script
    assert "change my last answer to" in script


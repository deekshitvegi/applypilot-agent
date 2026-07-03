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
        "preview-generated-cover-letter",
    }.issubset(parser.ids)

    script = (root / "extension" / "sidepanel.js").read_text(encoding="utf-8")
    assert "persistUnknownAnswer(message, { appendUser: false })" in script
    assert "/api/resumes/active/file-status" in script
    assert "looksLikeChatQuestion(message)" in script
    assert "correctLastSavedAnswer(correction)" in script
    assert "change my last answer to" in script
    assert "ask each unanswered application question here, one at a time" in script
    assert "(?:rest|next|remaining fields?|whole thing)" in script
    assert "The application frame changed; rescanning" in script
    assert "frameRetry: true" in script
    assert "I couldn't continue the form scan" in script
    assert "executeExplicitPageAnswers(message)" in script
    assert "and verified ${verified.length} on the page" in script
    assert "Preview generated cover letter" in script
    assert 'elements.chatInput.addEventListener("keydown"' in script
    assert "elements.chatForm.requestSubmit()" in script
    assert "directOptionMatches" in script
    assert "whole thing" in script
    assert "handleModelFormCommand(message)" in script
    assert 'api("/api/forms/agent-plan"' in script
    assert "executeFormAgentDecision" in script
    assert "pendingAgentQuestion" in script
    assert "runModelAutomationPass" in script
    assert "Resolving the remaining questions from your verified profile" in script
    assert "saveReasoningProvider" in script
    assert 'api("/api/provider/reasoning"' in script
    assert "renderChoiceCardsForMessage" in script
    assert "unresolvedFieldsForAgent" in script
    assert "resolveNarrativeUnknowns" in script
    assert "for (let pass = 0; pass < 3; pass += 1)" in script
    assert script.index("handlePageActionCommand(message)") < script.index("handleModelFormCommand(message)")
    assert "applyChoiceGroup" in script
    assert "Select all" in script
    assert script.index('/api/questions/refine') < script.index('SIEM: 0 months')

    worker = (root / "extension" / "service-worker.js").read_text(encoding="utf-8")
    assert "nearbyInstructions" in worker
    assert "fieldType === \"textarea\" ? nearbyInstructions(control)" in worker
    assert "[role='checkbox']" in worker
    assert "customCombobox || customChoice" in worker
    assert "control.hasAttribute(\"aria-checked\")" in worker
    assert "isPlainChoiceButton" in worker
    assert "applypilotChoiceKind" in worker
    assert "individualChoiceLabel" in worker
    assert "candidate.textContent || \"\"" in worker
    assert "isYesNoBackingInput" in worker
    assert 'rawValue.toLowerCase() === "on"' in worker
    assert "filled_ids: filledIds" in worker


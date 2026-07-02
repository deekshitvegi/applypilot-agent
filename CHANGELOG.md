# Changelog

## 0.5.4 - 2026-07-01

- Fixed LinkedIn `/safety/go` links by preserving LinkedIn's in-page click
  context instead of opening the internal safety endpoint as a new tab.
- Waited for a genuine non-LinkedIn employer destination before treating the
  safety handoff as complete.

## 0.5.3 - 2026-07-01

- Fixed LinkedIn's safety reminder when its **Continue applying** control is
  rendered outside a standard dialog container.
- Opened the continuation destination directly through the extension when the
  reminder exposes a link, avoiding delayed-click popup blocking.
- Kept a safe click-handler fallback for reminder controls without a link.

## 0.5.2 - 2026-07-01

- Added deterministic handling for LinkedIn's job-search safety reminder so
  **Continue applying** completes the employer-site handoff.
- Generalized primary Apply-button detection for LinkedIn, Indeed, Dice,
  employer job pages, and other portals that use buttons or same-page routing.
- Added a multi-step application loop that rescans every page, fills known
  answers, asks for unknowns, and advances through Next and Review while
  preserving the configured final-submit approval boundary.
- Added delayed-render retries for JavaScript job pages and employer forms.
- Opened the employer page and its application form before slower local-AI
  résumé preparation, and kept Ollama models warm for 30 minutes.

## 0.5.1 - 2026-07-01

- Fixed LinkedIn external Apply buttons implemented with JavaScript so the
  runner opens the employer application before scanning or filling fields.
- Prevented ordinary LinkedIn job pages and unrelated dialogs from being
  mistaken for application forms or exposing a final-submit action.
- Cleared stale form state whenever a new job is captured or no application
  form is detected.

## 0.5.0 - 2026-06-30

- Added a fully local Ollama provider with no API key or cloud quota, using
  Qwen3 8B by default and schema-validated structured responses.
- Added a guided questionnaire that discovers every unanswered visible field,
  captures custom dropdown and radio options, remembers each answer, fills the
  page, and resumes the active runner automatically.
- Preserved the source job description and application state across LinkedIn,
  employer career pages, Apply-button redirects, and side-panel reloads.
- Added optional browser-assisted login that can continue after the browser
  password manager fills credentials without exposing passwords to the model.
- Improved the one-action company-site runner, human-readable field labels,
  custom-control filling, CAPTCHA/MFA pauses, and deterministic fallback when
  AI preparation is unavailable.
- Made field analysis non-invasive and form-scoped so custom dropdowns remain
  closed, header controls are ignored, required questions are shown first, and
  optional blanks are reviewed only when requested.
- Simplified the side panel around one **Start applying** action, moved provider
  and automation preferences into collapsed Settings, added a focused offline
  recovery screen, and fixed narrow-panel horizontal overflow.
- Added a Windows background launcher plus enable/disable startup scripts so
  users do not need to understand or manually start a separate backend.
- Added friendly Gemini quota messages and one automatic retry when Google
  provides a reset delay of at most 60 seconds.
- Fixed profile matching so location values cannot be mistaken for work
  authorization answers, and included optional unanswered fields in analysis.

## 0.4.1 - 2026-06-30

- Replaced leaked internal field identifiers with human-readable labels and
  highlighted any question whose label a job site hides from the scanner.
- Improved native and custom dropdown matching plus remembered checkbox-group
  answers for office-location and similar multi-select questions.
- Made deterministic page filling available from chat without an AI key and
  rendered AI responses as clean, safe text and lists rather than raw Markdown.
- Clarified when an encrypted provider key is active, added reviewed AI drafts
  for narrative application questions, and expanded website/start-date mapping.

## 0.4.0 - 2026-06-30

- Fixed job capture and form scanning across navigation by adding explicit,
  user-granted persistent job-site access.
- Added a complete editable profile with encrypted, optional gender, race or
  ethnicity, veteran, and disability self-identification fields.
- Added deterministic cross-page autofill for common profile fields without an
  AI call, including safer semantic mapping for yes/no/decline choices.
- Added evidence-grounded job-fit scoring, gap analysis, a minimum automatic
  fit threshold, and one-pass job preparation that produces a tailored résumé.
- Added independent ask/always-allow policies for final submission and tailored
  résumé attachment.
- Added a LinkedIn-to-company application runner with a visible warning,
  queue continuation, stop control, and a 10-job safety cap.

## 0.3.0 - 2026-06-30

- Added encrypted in-panel setup for Gemini, OpenAI, and Anthropic credentials.
- Added provider-independent structured resume evidence, tailoring, and chat.
- Added multimodal chat with up to three validated image attachments.
- Replaced the original stacked dark interface with a compact, conventional
  workflow and a substantially larger chat workspace.

## 0.2.0 - 2026-06-30

- Added encrypted candidate profiles, reusable answers, resumes, applications,
  and tailored artifacts.
- Added Gemini chat, evidence extraction, and grounded resume tailoring.
- Added DOCX/PDF/TXT resume ingestion and ATS-friendly DOCX/PDF output.
- Added Chrome side-panel onboarding, active-job capture, route planning, chat,
  form analysis, filling, remembered unknown answers, document attachment, and
  explicit final-submit approval.
- Added company-site-first routing and LinkedIn, Greenhouse, Lever, Workday,
  generic HTML, and JobPosting JSON-LD adapters.
- Added an encrypted application state machine and audit history.
- Added a public stateless Render demo and synthetic ATS test page.
- Added setup, start, extension packaging, CI, and MIT licensing.
- Added Windows/macOS/Linux setup and start scripts plus secret-safe local
  installation diagnostics.

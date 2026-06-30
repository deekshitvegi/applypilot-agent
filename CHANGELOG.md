# Changelog

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

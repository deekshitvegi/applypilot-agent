# Changelog

## 0.9.0 - 2026-07-02

- Added custom ARIA radio and pressed-button support for segmented Yes/No,
  referral-source, sponsorship, and similar ATS controls.
- Improved résumé-evidence checkbox matching when an ATS exposes the full
  question on every option instead of a clean group label.
- Added grounded answer refinement so shorthand such as “0 months for all” is
  converted into the employer-requested category format without inventing facts.
- Added automatic ATS-readable DOCX reconstruction from saved résumé text when
  an older upload lacks original file bytes, eliminating forced re-upload.
- Added truthful AI-generated, job-specific cover-letter DOCX files with an
  explicit always-generate preference alongside saved/never/ask choices.
- Made “fill the rest” rescan and fill the active form instead of becoming an
  advisory chat response.

## 0.8.3 - 2026-07-02

- Distinguished questions and help requests from answers while an application
  question is pending, so unrelated chat is no longer saved accidentally.
- Added explicit `/answer`, `answer:`, and `my answer is` forms for ambiguous
  replies without requiring an AI request.
- Added conversational correction through “change my last answer to …”, which
  updates encrypted reusable memory and refills the current page.
- Made every saved-answer confirmation show both the question and exact stored
  value so mistakes are visible immediately.

## 0.8.2 - 2026-07-02

- Made a normal chat reply answer the currently pending application question,
  save it as a reusable encrypted answer, fill the page, and continue the run.
- Added an original-file availability check for résumés uploaded before raw-file
  storage existed, with a direct one-time re-upload instruction in the correct
  settings tab.
- Preserved detailed local file-download errors instead of replacing them with
  a generic attachment failure.

## 0.8.1 - 2026-07-02

- Fixed styled Yes/No radio groups that do not share a conventional HTML name,
  including work authorization and sponsorship questions.
- Made the captured LinkedIn/Indeed/Dice source override stale generic referral
  answers so source-of-application questions select the correct job board.
- Attached the configured original or tailored résumé immediately after form
  discovery instead of waiting until every missing question was answered.
- Added encrypted local cover-letter upload with never, ask-each-time, and
  always-attach preferences; résumé and cover-letter fields are identified
  separately by their visible labels.
- Expanded explicit cloud résumé aliases while continuing to leave unsupported
  skills unselected.

## 0.8.0 - 2026-07-02

- Reworked the side panel around one primary application conversation: current
  job controls, live activity, chat, and inline missing-question prompts.
- Moved provider configuration and automation preferences into a dedicated
  Settings drawer instead of showing them in the normal workflow.
- Added a separate Profile & résumé settings tab and hid manual job/form tools
  inside a collapsed troubleshooting section.
- Made new application questions appear in chat, echo the user's answer, explain
  that it was saved, and continue to the next question automatically.
- Replaced the ambiguous overflow menu with a conventional Settings control.

## 0.7.4 - 2026-07-02

- Added grouped radio and checkbox understanding, including styled controls
  whose native input is visually hidden.
- Added deterministic work-authorization, sponsorship, background-policy, and
  captured-source mapping without an AI request.
- Added evidence-only résumé matching for programming-language, tool, and cloud
  checkbox groups; unsupported choices remain unselected.
- Deduplicated unanswered multi-select groups so relocation and proficiency are
  asked once and remembered instead of appearing as unrelated fields.
- Made conversational commands such as “fill that part” rescan and update the
  live application rather than falling through to ordinary AI chat.
- Expanded the synthetic ATS with styled radio and checkbox regression fields.

## 0.7.3 - 2026-07-02

- Added nested-frame and open-shadow-root discovery for employer Apply controls
  and application fields.
- Added button-like input support for job sites that do not use normal links or
  buttons.
- Made AI-planned controls resilient to page re-renders by safely re-identifying
  the selected visible label before clicking.
- Changed the balanced Ollama default to `qwen3:4b`, disabled slow thinking for
  structured actions, limited context, and reduced model memory residency from
  30 minutes to 45 seconds.

## 0.7.2 - 2026-07-02

- Added explicit application-stage state so the runner stops searching for an
  Apply button after an employer form has opened.
- Fixed generic portal scanning to inspect the main application region instead
  of accidentally selecting an unrelated form container.
- Prevented repeated Apply-button errors between multi-step form pages, blocked
  premature **Next** actions while required fields are empty, and stopped safe
  navigation when the page does not change.

## 0.7.1 - 2026-07-02

- Added explicit consent wording for hands-off normal login using credentials
  already filled by the browser password manager.
- Waited for delayed password-manager autofill and supported multi-step
  username/Next/password login flows before resuming the application.
- Kept CAPTCHA, MFA, verification codes, empty credentials, and ambiguous
  authentication controls as mandatory user/security handoffs.

## 0.7.0 - 2026-07-01

- Added an AI page-planning fallback that observes visible controls and page
  context when deterministic application steps are ambiguous.
- Kept final Submit, destructive actions, credentials, CAPTCHA, and MFA outside
  the AI planner's allowed actions.
- Resolved duplicate and nested Apply controls on Ashby and similar job pages.
- Added truthful local chat status answers such as “are you applying?” instead
  of sending those questions to a generic model response.
- Added encrypted original-résumé file storage and per-application preferences
  for original, tailored, or ask-each-time attachment.
- Kept authentication in the guarded browser-assisted login path: existing
  password-manager values may be submitted when enabled, while CAPTCHA, MFA,
  verification codes, empty credentials, and ambiguous login controls pause.

## 0.6.0 - 2026-07-01

- Enforced a strict queue invariant: the runner advances only after explicit
  on-page submission confirmation; low-fit and uncertain applications pause.
- Added LinkedIn “application sent” confirmation phrases and removed unsafe
  URL-only submission inference.
- Added a local CSV application-history export with timestamps, status, job,
  company, route, URL, and latest audit event.
- Added live runner activity to chat and deterministic chat commands such as
  `remember expected salary is 120000` that save and reuse field answers.
- Collapsed the legacy profile, résumé, capture, and form buttons under
  **Manual controls**, leaving the primary runner, Settings, and chat focused.
- Improved LinkedIn job-title and company extraction for application history.

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

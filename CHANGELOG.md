# Changelog

## 0.11.4 - 2026-07-04

- Scoped short chat replies such as Yes, No, and Experienced to exactly one
  pending or explicitly referenced application question.
- Reworked choice-card relevance so short option names can no longer match
  unrelated questions by substring (for example, `No` inside `now` or `Go`
  inside ordinary prose).
- Focused model clarification cards on one question instead of displaying up
  to four loosely related groups at once.
- Added selected-state tracking for custom segmented Yes/No buttons that do
  not expose native radio or ARIA state.
- Made repeated radio/button fills idempotent, preventing a verified answer
  from being clicked again and toggled off during replan or file upload.
- Added conversational support for "open to relocating anywhere in the US".

## 0.11.3 - 2026-07-03

- Ranked application-entry controls before truncating large page snapshots, so
  a visible Apply button cannot be displaced by dozens of unrelated links.
- Expanded Apply detection to custom anchors, accessible buttons, shadow DOM,
  nested frames, and labels that include extra accessibility text.
- Page-action frame selection now strongly prefers the frame containing the
  application entry instead of the frame with the largest navigation menu.
- Stop now preserves the captured job while clearing stale navigation state;
  Start re-inspects the live page and can resume from an employer listing or
  partially completed application without returning to LinkedIn.
- Gemini assist validation now uses a minimal model-access request rather than
  a complex form-action schema, preventing valid keys from failing setup due
  to an unrelated structured-output grammar.
- Gemini connection failures now report Google's safe error category and
  detail for disabled APIs, project permissions, key restrictions, regional
  free-tier availability, model access, and rate limits without exposing keys.

## 0.11.2 - 2026-07-03

- Added in-chat choice cards that mirror visible ATS radio, select, and
  checkbox questions, including multi-select and Select all controls.
- Choice-card answers are executed, verified against the live page, and stored
  as reusable answers for equivalent future questions.
- Added an evidence-first application loop: deterministic profile fields fill
  immediately, the model receives only unresolved controls, and up to three
  observe/action/verification passes run before asking the user.
- Added truthful job-specific drafting for unresolved narrative questions from
  the saved profile, résumé, and captured job description.
- Live fields now appear before compact profile, résumé, answer-memory, and job
  context so small local models retain both the browser tools and evidence.
- Explicit page commands now run through the verified action executor before
  general chat, preventing a prose response from swallowing a requested click.
- Added general multi-select reasoning for broad preferences such as
  "anywhere" or "all of these".
- Gemini assist now runs a real structured-action probe before a key is saved;
  rejected keys or inaccessible models can no longer appear Connected.
- Checkbox plans may safely return the explicitly named option label as well as
  `true`, improving compatibility with small local models.
- Optional Gemini assist now handles résumé tailoring, unfamiliar page/form
  decisions, job-specific application answers, and generated cover letters;
  local Ollama remains the automatic fallback.

## 0.11.1 - 2026-07-03

- Added semantic grounding validation so model confidence can never override a
  conflicting canonical profile value such as email, title, authorization, or
  sponsorship.
- Added expected field-label/type fingerprints to every fill action, preventing
  stale numeric field IDs from writing an answer into a different question
  after an ATS re-renders the form.
- Reapplied canonical profile actions after résumé/cover-letter uploads, which
  can cause Ashby and other reactive forms to reset selected controls.
- Removed contaminated canonical page answers on startup and made the editable
  candidate profile the single source of truth for those fields.
- Added conversational field focus so `change it to ...` and `it was ...`
  execute against the last explicitly referenced question.
- Added selective Ollama + Gemini routing: local Ollama handles unlimited chat
  and fallback work, while Gemini is reserved for résumé tailoring and
  unfamiliar page/form decisions. Gemini failures fall back to Ollama.

## 0.11.0 - 2026-07-03

- Added a genuine model-driven form agent: Gemini, Ollama, OpenAI, or Anthropic
  receives the current structured fields, user instruction, profile, saved
  answers, résumé evidence, and active job, then returns typed field actions.
- Added a guarded observe → reason → act → verify → repair loop. Model actions
  are validated against live field IDs and visible options, executed by the
  extension, verified on-page, and repaired once using the latest page state.
- Persisted only verified model actions; hallucinated, unavailable, sensitive,
  authentication, file, and low-confidence actions are rejected before use.
- Added conversational clarification memory so a model can ask one focused
  question and correctly interpret the user's next reply as the answer.
- Wired the structured planner into the autonomous Start applying runner after
  the fast deterministic pass, so unfamiliar remaining controls are reasoned
  over instead of being handed directly to the old questionnaire.
- Kept deterministic profile autofill as the fast, free fallback when no model
  is configured, a provider is rate-limited, or structured planning fails.
- Verified the structured action schema against local `qwen3:4b` in addition to
  automated provider and API tests.

## 0.10.2 - 2026-07-03

- Added an Ashby-safe control model based on the live TENEX application: visible
  Yes/No buttons are treated as one field and their hidden backing checkbox is
  no longer scanned or filled separately.
- Fixed Ashby radio groups whose every input uses the generic value `on`; the
  visible option label now drives LinkedIn, Linux, consent, and similar choices.
- Added fuzzy visible-option matching for employer typos such as `Expereinced`.
- Made exact page corrections override stale profile defaults and prevented a
  saved `Current Employee` answer from overriding a captured LinkedIn source.
- Added natural commands for changing referral source, confirming background
  policy review, applying `it is ...` answers, `answer these`, and `do it`.
- Page-action reports now distinguish saved requests from selections actually
  verified by the extension rather than claiming every planned update worked.

## 0.10.1 - 2026-07-03

- Fixed ordinary segmented ATS buttons whose visible Yes/No text was not
  exposed through an HTML value or ARIA attribute.
- Routed concise visible-option replies such as `Experienced` directly to the
  matching application question instead of generic AI chat.
- Recognized `fill out the whole thing` as a form action and allowed `add that
  to the application` to reapply the last verified page answer.
- Made Enter send chat messages and Shift+Enter insert a new line.
- Expanded autocomplete option discovery for city/state controls that render
  visible suggestions without standard listbox roles.

## 0.10.0 - 2026-07-02

- Turned explicit chat corrections into immediate page actions: one message can
  select multiple technologies, clouds, referral sources, relocation choices,
  work authorization, and sponsorship answers, then remember and refill them.
- Added support for ATS Yes/No segmented controls implemented as ordinary
  buttons without native radio roles or ARIA state.
- Added an in-extension preview for the generated job-specific cover letter and
  a clear activity message showing where to open it after attachment.

## 0.9.4 - 2026-07-02

- Added plain-text Ollama cover-letter generation when the local server rejects
  a structured JSON grammar.
- Made cover-letter generation non-blocking so a model/document failure is
  reported in activity chat while form filling continues.
- Added custom ARIA checkbox support and fixed filtering that accidentally
  excluded button-based radio/checkbox widgets from form scans.
- Generalized question grouping across native inputs, ARIA choices, and pressed
  buttons so technology, authorization, sponsorship, and source controls can be
  mapped and clicked consistently.

## 0.9.3 - 2026-07-02

- Detected employer iframe replacement between scanning and filling, then
  rescanned and retried once against the new frame instead of failing.
- Added guarded scan/fill UI handlers so a disappearing application frame is
  reported in chat rather than becoming an uncaught extension promise error.

## 0.9.2 - 2026-07-02

- Ignored generic reusable labels such as “Select,” preventing an old “No” from
  being applied to unrelated proficiency controls such as Linux experience.
- Deduplicated reusable answers by normalized question whenever an answer is
  saved or corrected.
- Routed “fill the next,” “fill the rest,” and “ask me the remaining questions”
  into the active form workflow instead of advisory AI chat.
- Made automatic and manual fill flows ask every unknown required question in
  chat one at a time; AI now refines user-provided answers rather than silently
  inventing responses.

## 0.9.1 - 2026-07-02

- Made the configured AI provider refine free-text application answers before
  they are saved; deterministic formatting is now fallback-only.
- Included nearby employer instructions in textarea questions so the model sees
  requested categories, units, and formatting rather than only a short heading.

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

# Changelog

## 0.17.2 - 2026-07-30

- **A dropdown no longer claims the whole page as its options.** When a custom
  dropdown exposed no identifiable popup, option enumeration fell back to
  querying the entire document, so on a live Ashby form the Location and School
  dropdowns each reported 27 "options" assembled from a salary chip, Yes/No
  buttons, relocation checkboxes and the EEO race list. The panel then offered
  all of them together as a single question. Options are now read only from a
  popup the control actually owns; a dropdown whose choices cannot be seen
  reports none rather than inventing them, and the remaining questions keep
  their own separate, correct choices.

## 0.17.1 - 2026-07-30

- **The résumé now answers optional questions.** On a live Ashby form, School,
  Degree, Field of Study, Location and Website were left blank and never even
  asked about. Every one was optional, and the model pass was both gated on and
  scoped to *required* unknowns, so on a form whose only gaps were optional the
  résumé was never consulted at all - precisely what users upload it for. The
  model is now offered every unanswered question. Verified against the live
  Gemini key: Degree and Field of Study come back grounded in the résumé, while
  a portfolio URL the résumé does not contain is still left empty rather than
  invented.
- **Demographic questions are never inferred.** Gender, race, veteran and
  disability questions are excluded from the model pass and answered only from
  a preference the user saved themselves.
- Progress between model passes is measured over every question being worked
  on, so an optional-only form no longer looks like zero progress and stop
  after one pass.

## 0.17.0 - 2026-07-30

- **Session sign-in details.** Settings now accepts a site, username and
  password that the agent uses to sign in for the rest of the session. They are
  held in memory by the local companion only: never written to the database,
  never logged, never echoed in narration, and gone when the agent restarts.
  They are released only on an exact host match - a lookalike such as
  `myworkdayjobs.com.evil.test` gets nothing - and only on a page already
  confirmed to be that site's sign-in form. Signing **in** only; creating an
  account is still never automated, because it accepts an employer's terms on
  the user's behalf.
- The browser password manager remains the default path and is unchanged.

## 0.16.4 - 2026-07-30

- **A country name is no longer written into a state dropdown.** Workday names
  its State field `countryRegion`, so a saved "Country" answer claimed it by
  bare substring match and the run reported 'State: No dropdown option matched
  "United States of America"' while the required field stayed empty. Saved
  answers now match only at word boundaries - a whole-word prefix or suffix -
  so "State" still completes "State / Territory" but "Country" can claim
  neither `countryRegion` nor "...work in the country in which this role is
  based?". Matching also considers the label the user sees, not only the
  name-augmented form, so a field whose name contradicts its label cannot drag
  in the wrong answer.

## 0.16.3 - 2026-07-30

- **Answering a question in chat now fills the field and is remembered.**
  "state texas", "set my state to Texas" and "phone device type mobile"
  produced conversational prose while the required dropdown stayed empty and
  blocked the application. Naming a visible field and its value is now a
  scoped action, so the value is selected from the employer's own options,
  verified on the page, and saved as a reusable answer for next time. A value
  the page does not offer is still never invented.
- **A saved answer whose wording differs slightly now matches.** The page
  labelled a field "State" while the saved answer was "State / Territory", and
  0.15.4's length guard rejected the pair. Matching now allows a short answer
  to complete a short label while still refusing to let one claim a full
  employer question.
- **Stopped reporting a correct selection as a failure.** The page had accepted
  "United States of America" for a saved "United States" and the run reported
  "I could not complete: Country".

## 0.16.2 - 2026-07-30

Found by surveying ten kinds of job site rather than fixing one report at a time.

- **The page classifier would have stopped every run at its starting point.**
  Asked to judge a LinkedIn listing, the model reasonably answered "this is not
  the employer", and the runner treated that as a third-party redirect and
  halted. SmartRecruiters, Indeed and Dice were rejected the same way. Host
  identity is now decided deterministically from the URL - a recognised ATS is
  the employer's application host, a job board is the expected starting point -
  and only an unrecognised host can be a third party worth stopping on. The
  model still explains what it sees; it no longer decides whether to stop.
- **A stuck page no longer loops forever.** "AI page planner selected apply" /
  "the observed page has not changed" repeated indefinitely because the guard
  reset whenever the run resumed. Pages that already defeated the planner are
  remembered for the run, and after two attempts the agent stops and asks the
  user to open the form manually.
- **Job-board search pages are no longer scanned as forms.** Dice reported 22
  phantom fields and an application surface from its filter controls. Board
  scoping now covers Dice, Glassdoor, ZipRecruiter, Monster and SimplyHired
  alongside Indeed, and surface detection refuses board pages outright.

## 0.16.1 - 2026-07-30

- **Fixed the wrong country being selected.** On a live Workday form "United
  States" chose "United States Minor Outlying Islands (+1)", because option
  matching returned the first option that merely contained the value. Matching
  options are now ranked by closeness, so the intended country wins. A wrong
  country reaching an employer is exactly the kind of unverified answer that
  must never happen.
- **"No fillable fields were found" on a page full of fields.** When a site
  moves its form outside the container the adapter scopes to, the scan now
  falls back to the whole document instead of reporting an empty page.

## 0.16.0 - 2026-07-30

- **The agent now works out what page it is on before acting.** Following an
  employer Apply link landed on jackandjill.ai - a recruiting platform, not the
  employer - and the action planner kept clicking there until it hit a guard
  and reported the unhelpful "The AI planner cannot click final or destructive
  controls". A new classification step runs first and returns a typed page kind
  (application form, job listing, login required, account signup required,
  third-party redirect, confirmation, blocked, unrelated) plus a plain-language
  summary of what it sees.
- **The run stops with an explanation instead of blundering on.** A page that
  demands a new account, needs a sign-in, is already submitted, or is blocked
  becomes a clear handoff. A page that does not belong to the expected employer
  stops with "That Apply link led to ... not the employer's own application. I
  stopped rather than submit your details to someone else."
- Page text is passed to the model as untrusted data, and the classifier can
  only choose from a fixed set of kinds - it never picks a control.

## 0.15.6 - 2026-07-30

- **Fixed a regression from 0.15.5: application forms treated as sign-in
  pages.** Employer application URLs such as ADP's `.../postLogin.html`
  contain "login", and application forms ask for an email address, so the
  new two-step-login detection matched them. The runner then looped
  "Submitted a password-manager-filled login step" against "Login fields were
  not filled" on a form it should simply have filled. A page asking for name,
  phone, address, résumé or demographics is now recognised as an application
  whatever its URL says; only a real password field overrides that. Two-step
  sign-in detection is unaffected - both directions are verified against the
  live ADP sign-in page and a live Greenhouse application form.

## 0.15.5 - 2026-07-30

- **Sign-in pages built as web components are recognised again.** An ADP
  application link redirects to a sign-in page whose entire form lives in a
  shadow root, so the login check - which queried only the light DOM - found
  nothing and the runner treated a credential form as an application form.
  Login detection now traverses shadow roots, as the field scanner already did.
- **Two-step sign-ins are detected.** ADP asks for a User ID first and only
  requests the password on the next screen, so keying detection off a password
  field missed it entirely. A visible username/user-ID field on a page whose
  path or title says sign-in is now enough. Credentials are still never typed
  or stored: the browser password manager owns them.

## 0.15.4 - 2026-07-30

- **A saved answer no longer hijacks an unrelated employer question.** On
  Anthropic's Greenhouse form, a saved "Country -> United States" was filling
  the visa-sponsorship question, because the phrase "the country in which this
  role is based" contains "country" and the matcher's containment shortcut
  scored any such overlap 0.95. Answering a sponsorship question with a
  country name is both wrong and unsafe. The shortcut now applies only when
  the two questions are of comparable length, so a short saved question cannot
  claim a long one; genuinely similar questions still match.

## 0.15.3 - 2026-07-30

- **The Gemini schemaless retry now actually fires.** 0.15.0 added a fallback
  for structured-output schemas Gemini refuses, but it only triggered when the
  error text named the schema. Google in practice returns a bare "Request
  contains an invalid argument", so the retry never ran and every AI planning
  pass still failed. Any `INVALID_ARGUMENT` on a schema-bearing request now
  earns one schemaless retry; the reply is still validated against the same
  Pydantic model. Key, quota and permission errors use other codes and still
  fail fast.

## 0.15.2 - 2026-07-30

- **Fields cleared by a form that rebuilds itself are now filled again.** On a
  multi-step employer form, choosing Country rebuilt the address block and
  discarded Address Line 1-3 and City moments after they were filled. The
  rescan reported them empty - which was truthful - but the run gave up
  instead of simply filling them again. The agent now re-plans and re-fills
  until the page stops changing, stopping if the same pending set repeats so a
  page that genuinely rejects a value cannot cause a loop.
- **Selects and text inputs are now idempotent.** Re-selecting a value that is
  already chosen still fires `change`, so a form that rebuilds on country
  change would discard the retry's own work on every pass. A control already
  holding the requested value is left untouched and reported verified, which
  is what makes the retry converge.

## 0.15.1 - 2026-07-30

- **Stopped pausing on the invisible reCAPTCHA badge.** A run halted with
  "Paused: CAPTCHA, MFA, or a verification code requires you" on an ordinary
  employer application form. The detector matched any visible captcha iframe,
  and the reCAPTCHA v3 badge — present on a large share of career sites, and
  requiring no interaction whatsoever — is a visible 256x60 iframe. Every such
  application was blocked before it began.
- A pause now requires a challenge the user can actually solve: a visible
  one-time-code field, the reCAPTCHA/hCaptcha image challenge (`bframe`), or a
  checkbox widget of interactive size. Invisible badges and `size=invisible`
  anchors are ignored. CAPTCHA, MFA and verification codes are still never
  bypassed or solved — they remain user handoffs.

## 0.15.0 - 2026-07-30

- **Easy Apply listings now route to the employer's own application page.**
  Previously a LinkedIn job offering only Easy Apply had no company URL to
  discover, so the agent fell back to the aggregator's form. ApplyPilot now
  derives candidate ATS boards from the company name, verifies each one really
  belongs to that employer, finds the matching posting, and applies there.
  Verified live: an Easy-Apply-only listing for Anthropic "Research Engineer"
  now routes to the real Greenhouse posting instead of Easy Apply.
- Discovery is general, never per-employer: slugs come from the company name
  with legal suffixes and YC batch tags stripped, candidates only target
  recognised ATS hosts, a board whose page does not name the company is
  rejected so a slug collision cannot send an application to the wrong
  employer, and an unverified guess is never returned. Non-HTTPS, loopback and
  private-network targets are refused before any fetch.
- Easy Apply remains the fallback when no company page can be verified, and
  Settings - Where to apply still lets you prefer Easy Apply outright.

## 0.14.3 - 2026-07-30

- **The panel now shows the local agent's version and warns when it does not
  match.** A companion left running on older code silently ignores every
  backend fix, with no visible signal — which made a fixed answer-matching bug
  look unfixed. The header now reads "Local agent connected · v0.14.3", turns
  amber on a mismatch, and the agent says in chat that it needs restarting.

## 0.14.2 - 2026-07-30

- **Fixed the AI field planner dying on Gemini.** `FormAgentDecision` nests
  `FormAgentAction`, which Pydantic serialises as `$defs`/`$ref`; Gemini
  rejects that structured-output schema with `INVALID_ARGUMENT`, so every
  planning pass failed and every question fell back to the user. Gemini calls
  now retry once without the schema, asking for plain JSON of the same shape.
  Model output stays untrusted: the reply is still validated against the same
  Pydantic model before anything uses it. Key, quota and permission failures
  are unaffected and still fail fast.
- Stopped reporting unrelated Gemini failures as "Gemini rejected the
  connection test"; a failed planning call no longer claims a connection test
  ran.

## 0.14.1 - 2026-07-30

- **Fixed the same question being asked forever.** Saving an answer for a
  short question — "Name", "City", "Phone" — never mapped back to the field,
  so the panel re-announced it after every save. Two causes: saved answers were
  compared against a combined "label name" string rather than the label the
  panel actually displayed, and the fuzzy matcher discarded every question
  shorter than six characters before comparing. Exact matching now tries each
  label form the panel could have shown.
- **A missing tailored résumé no longer pauses the whole application.** When
  résumé preference is "tailored" but no AI model is connected, ApplyPilot now
  attaches the original uploaded résumé and explains why, instead of stopping
  the run with "A tailored résumé is unavailable".
- The agent now says plainly when it has no AI model connected and therefore
  cannot read the résumé to answer remaining questions itself, instead of
  silently returning them as manual questions.

## 0.14.0 - 2026-07-30

Verified against live LinkedIn, Indeed, Greenhouse and Lever pages by running
the extension's real injected functions inside those pages.

- **Fixed a false "verified" on custom dropdowns.** The executor types into a
  combobox's own input to filter its option list. The verification rescan then
  read that self-written text back and reported success — including for
  options the employer's page never accepted — overwriting the failure the
  executor had already recorded. Reproduced on a live Greenhouse (react-select)
  question. Selected state for a custom dropdown now comes only from signals
  the page owns: `aria-activedescendant`, `aria-selected`, the widget's own
  rendered value element, a hidden backing input, or a value the page wrote
  after ApplyPilot cleared its filter text. A dropdown whose only signal is
  loose text in its own input is reported unreadable and can never be verified.
- Filter text is now restored when no option matches, so a later scan cannot
  mistake an abandoned keystroke for an answer.
- **Custom dropdowns now open the way a real user opens them** (a full pointer
  sequence rather than a bare `click()`), and filter input no longer dispatches
  `blur`, which had been closing the very menu the executor was about to read.
- **The scanner can now enumerate a custom dropdown's real choices**, opening
  it, reading the employer's own options, and closing it again. Required
  dropdowns previously advertised zero options, leaving the planner blind.
- **Job boards are no longer mistaken for application forms.** Indeed search
  pages reported an application surface and produced 21 phantom fields (save
  toggles and job cards read as radio groups). Search, filter and site-chrome
  controls are now excluded, and Indeed scanning is scoped to a real apply
  surface.
- **Job descriptions no longer capture bundled JavaScript.** An Indeed search
  page returned 1.2 MB of script source as the description; script, style and
  template text is now stripped everywhere.
- **Company name is now extracted reliably**, falling back through structured
  data, `og:site_name`, logo alt text and the document title. It had been empty
  on every site tested, which left the application history without employers.
- **Grouped checkbox questions keep their real question.** A Lever pronoun
  question was split into eleven fields labelled `He/himShe/herThey/them
  Xe/xem`; it is now one question with eleven options.
- Added adapters for Indeed, Ashby, SmartRecruiters, iCIMS, Jobvite, Dice,
  Glassdoor, ZipRecruiter, Monster and SimplyHired, plus recognised ATS hosts
  for Workable, BambooHR, Breezy, Teamtailor, Recruitee, SuccessFactors, Taleo,
  Oracle Cloud, Paylocity and Dayforce.
- The agent now narrates fill outcomes in the conversation, naming the answers
  it confirmed and the ones the page would not confirm, instead of leaving that
  detail in a silent status panel.

## 0.13.0 - 2026-07-04

- Redesigned the side panel around one agent surface: the job you are on, a
  live one-line status, Start/Stop, and a full-height conversation where the
  agent narrates each step as a timeline. Removed the duplicated cards.
- Rewrote every setting in plain language and grouped them into "Your AI
  model", "How I apply", and "Your data", each control with a one-line
  explanation; on/off choices are now toggle switches.
- Added an application-route choice: apply on the company's own website
  (default) or use LinkedIn Easy Apply when it exists.
- Fixed pasted question text being read as a command: "add github ci" followed
  by a question containing "select all …" selected every option in the group.
  Option matching now strips the referenced question text first.
- Added exclusive-set corrections: "not all, just GitHub CI and Docker"
  selects exactly the named options and clears the rest of that group instead
  of falling through to a model prose reply.
- Chat results now name each option ("GitHub CI — selected") instead of
  repeating the group question with a raw true value.
- The agent's live narration is first-person and specific ("I found the
  employer's Apply button on this page — clicking it now…").
- One chat message can now carry several intents ("fill my phone number …
  check the background policy … I'm able to relocate anywhere … I only know
  docker and github ci … click submit"): each part becomes its own scoped,
  verified action. "I only know X and Y" and "remove the rest" replace a
  group's selection exclusively, evaluated per clause so casual words like
  "just" in ordinary sentences never clear selections.
- "Fill my phone number/email/LinkedIn/GitHub" fills the matching visible
  field from the saved profile, or tells you the profile value is missing.
- Submit requests in chat get an explicit answer describing the approval
  flow instead of being silently ignored; the final Submit is never pressed
  from a chat message.
- Added a plain-English, step-by-step setup guide to the README for
  non-developers.

## 0.12.0 - 2026-07-04

- Replaced attempted-action verification with an authoritative post-action
  rescan: the executor records the page-owned pre-state, performs one scoped
  action, waits for the page to settle, rescans the live DOM, and reports
  `verified` only when the requested visible option is actually selected.
- Removed the self-written `data-applypilot-selected` marker entirely. Selected
  state now comes only from signals the page owns: native `checked`, ARIA
  checked/pressed/selected, page `data-state`/`data-selected`, page CSS state
  classes, and hidden backing inputs behind segmented Yes/No buttons.
- Controls that expose no page-owned state are now reported honestly as
  "attempted but not confirmed" instead of "verified", are never persisted as
  reusable answers, and are never auto-clicked a second time.
- Added stable field fingerprints (normalized question, control type, option
  labels, and name) so actions survive React-style re-renders that replace
  elements and rotate numeric IDs; stale-ID actions re-resolve by fingerprint.
- Made every fill idempotent: an option that a fresh scan already shows as
  selected is never clicked again, so replans, repeated answers, and file
  uploads can no longer toggle a segmented control off.
- Merged the form scanner and executor into one injected `runFormPass` so the
  scan that verifies is exactly the scan that plans, and fills return the
  fresh post-action field state.
- Routed relocation, sponsorship, authorization, and multi-select instructions
  through a deterministic scoped-intent parser that binds each statement to
  specific visible questions; "open to relocating anywhere" selects every
  offered location and clears "unable to relocate".
- Guaranteed that an explicit instruction about the visible form always ends
  in a scoped browser action, a choice card, or a focused clarification —
  never generic chat prose; bare replies that match several questions now ask
  which question is meant instead of guessing.
- The user's own canonical statements (sponsorship, authorization, relocation)
  update the encrypted profile even when a page control cannot be confirmed.
- Added browser-level regression tests (Playwright + the real injected
  extension code) covering segmented Yes/No buttons with hidden backing state,
  silent controls, toggle-off buttons, React-style re-renders, multi-select
  checkbox groups, shadow-root options, and file uploads that reset answers.

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

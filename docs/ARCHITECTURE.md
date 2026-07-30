# ApplyPilot architecture

## Shape of the system

```text
Job page / ATS
      |
Chrome extension content script
      |
ApplyPilot side panel  <---->  User review and chat
      |
Local FastAPI orchestrator
      |---- Candidate profile and answer memory (local SQLite)
      |---- Job-page normalization and site adapters
      |---- Resume evidence extraction and tailoring
      |---- Application planning and validation
      `---- AI provider (local Ollama or encrypted remote credential)
```

The browser extension owns page interaction. The local service owns reasoning,
personal data, document generation, audit history, and validation. A remote
provider credential entered in the dedicated side-panel form is sent only to
the loopback service, encrypted immediately, and never persisted in extension
storage or returned by the API. Ollama uses a fixed loopback endpoint and
requires no credential.

Common application fields are mapped deterministically from the encrypted
profile and reusable-answer store; this path does not call an AI model. The AI
provider handles job-fit analysis, free-text assistance, evidence extraction,
job-specific résumé tailoring, and structured form-action reasoning. The action
planner never receives an unrestricted browser tool. It can select only field
IDs and visible choices supplied by the extension.

```text
detect form
    |
    +--> deterministic profile/source/résumé fill (no model)
    |
    +--> draft evidence-supported narrative answers
    |
    `--> unresolved fields only -> model typed actions -> validate/execute
                                   ^                         |
                                   `---- rescan/verify ------+
                                         (up to 3 passes)
                                              |
                                 genuinely unknown -> native chat question
```

Only verified actions are written to reusable memory. Password, CAPTCHA, MFA,
payment, file-upload, destructive, low-confidence, and unavailable actions are
rejected before execution. If the provider is unavailable or rate-limited, the
deterministic mapper remains operational.

## Verified control layer

One injected function (`runFormPass` in the extension service worker) owns
both observation and execution, so the scan that verifies is exactly the scan
that plans. Every field carries a stable **fingerprint** built from its
normalized question label, control type, visible option labels, and name —
never a numeric DOM index — so an action still resolves after a reactive
re-render replaces the elements.

Execution follows `pre-state → one scoped action → bounded wait → fresh
rescan → compare`:

1. The authoritative pre-state is read from page-owned signals only: native
   `checked`/`value`, ARIA checked/pressed/selected, page `data-state` or
   `data-selected`, page CSS state classes, or a hidden backing input behind
   segmented Yes/No buttons. ApplyPilot never writes any of these signals, so
   it cannot verify its own claim.
2. If the target value is already authoritatively selected, nothing is
   clicked (idempotence — a second click could toggle a custom control off).
3. Otherwise exactly one scoped action runs, followed by a bounded observation
   window for framework updates, re-resolving by fingerprint if the DOM was
   replaced.
4. A full fresh rescan then compares the page-owned semantic value with the
   target and produces one of four explicit outcomes per action:
   - `verified` — the fresh scan shows the requested value;
   - `unverified` — the action ran but the control exposes no page-owned
     state to confirm it (reported to the user, never persisted, never
     auto-repeated);
   - `failed` — the fresh scan shows a different value, with evidence;
   - `skipped` — file/password controls that are handled elsewhere.

### Custom dropdowns

A combobox is the one control ApplyPilot must write to in order to read: the
executor types into the widget's own input to filter its option list. That text
is therefore **never** evidence. A custom dropdown is confirmed only from
signals the page owns — `aria-activedescendant`, an `aria-selected` option, the
widget's own rendered value element, a hidden backing input, or a value the
page wrote *after* ApplyPilot cleared its filter text. When no option matches,
the filter text is restored so no later scan can mistake it for an answer, and
a dropdown whose only signal is loose text in its own input is reported
unreadable rather than verified.

Because these widgets commit on the pointer sequence a real user produces,
opening one dispatches `pointerdown`/`mousedown`/`mouseup`/`click` rather than a
bare `click()`, and filter input never dispatches `blur` — that would close the
menu being read. A scan pass can additionally **enumerate** an optionless
dropdown by opening it, reading the employer's real choices, and closing it, so
the planner never has to guess at a required question.

`filled_ids` therefore means "a fresh scan observed the requested value", not
"a click was issued". Only verified values become reusable answers or
canonical profile facts. File uploads trigger a complete re-observation, and
fields the page reset are restored through the same idempotent path.

## Chat command routing

Explicit user instructions are interpreted by a deterministic scoped-intent
parser before any model call. Canonical statements (sponsorship,
authorization, relocation — including "anywhere" over a multi-select), named
options ("add GitHub CI"), source corrections, and short option replies are
bound to specific visible questions and executed through the verified control
layer. A bare reply that fits several questions produces a clarification
question, not a guess. If neither the parser nor the model agent can act on an
actionable form instruction, the panel asks a focused question — an explicit
request about the visible form never falls through to generic chat prose.

When local Ollama is active and a Gemini key exists in the local environment,
the manager selectively routes résumé tailoring, unfamiliar page/form
reasoning, unique application-answer drafting, and generated cover letters to
Gemini. Routine chat remains local, deterministic fields use no model, and any
Gemini provider failure falls back to Ollama.

Ambiguous choice fields are rendered from the current page scan as chat choice
cards. The user selects the employer's exact options, and the same constrained
executor, page verification, and reusable-memory path handles the result. The
model never invents the option list.

## Company-site-first routing

The source listing is not assumed to be the application destination. For every
job, the orchestrator attempts to resolve and verify an official company career
page or recognized ATS URL first. This remains the preferred route even when
the listing exposes LinkedIn Easy Apply.

```text
Job listing
    |---- verified company/ATS URL ----> company application (preferred)
    |---- Easy Apply only -------------> resolve the employer's own board
    |                                     |-- verified -> company application
    |                                     `-- unverified -> Easy Apply
    `---- ambiguous or unsafe URL ------> ask the user
```

A listing that exposes only Easy Apply is not accepted as the destination.
`company_route.py` derives candidate board slugs from the company name (legal
suffixes and batch tags removed), tries only recognised ATS hosts over HTTPS,
and **verifies the board actually names that company** before trusting it — a
slug collision must never send an application to the wrong employer. The
matching posting is located by title similarity; when only the board verifies,
that is still preferred over the aggregator. An unverified guess is never
returned, and loopback/private targets are refused before any fetch.

Redirects are recorded and revalidated. Unknown domains, shortened URLs, and
URLs that request unusual credentials or payment stop the agent for review.

## Application state machine

```text
DISCOVERED -> ANALYZED -> MATERIALS_READY -> FILLING -> REVIEW_REQUIRED
                                                        |
                                user approves ----------+
                                                        v
                                                    SUBMITTED
```

`BLOCKED` is entered for CAPTCHA, MFA, an unknown required question, a site
change, or a validation failure. The agent pauses and explains the exact action
needed in the side panel.

Each transition is appended to an encrypted local audit record. A required
unknown question can be answered in the side panel and stored as a reusable
answer; the form is then replanned. The final submit action requires an explicit
side-panel confirmation, refuses to act when CAPTCHA/MFA is visible, targets
only a unique known submit label, and waits for an employer-site confirmation
signal before recording `SUBMITTED`.

## Site adapters

Every supported application surface implements the same small contract:

1. detect whether the adapter applies;
2. extract job title, company, description, location, and form fields;
3. map known profile answers to visible inputs;
4. report unknown or ambiguous questions;
5. validate the filled form;
6. apply the user's ask-before-submit or always-allow policy.

The generic form mapper runs before site-specific logic. It handles standard
HTML and common custom controls, maps high-confidence profile fields and
reusable answers, blocks payment fields, and returns every unanswered visible
question. A guided queue asks, remembers, replans, fills, and resumes the
runner. Login credentials remain browser-managed; the extension checks only
whether login fields are already populated before clicking an allowed login.
Site adapters add stronger selectors and multi-step navigation without changing
the submission-policy boundary.

Current adapter coverage:

- **LinkedIn:** job extraction, Easy Apply detection, external company-route
  discovery, and modal-scoped field scanning.
- **Greenhouse:** job/application extraction and application-form scoping.
- **Lever:** posting extraction and application-form scoping.
- **Workday:** job extraction and active application-page scoping.
- **Indeed, Dice, Glassdoor, ZipRecruiter, Monster, SimplyHired:** job boards.
  Their own pages are read as listings and are never treated as application
  forms; scanning is scoped to a genuine apply surface.
- **Ashby, SmartRecruiters, iCIMS, Jobvite, Workable** and other recognised ATS
  hosts route as employer application destinations.
- **Generic:** standards-based JobPosting JSON-LD plus visible HTML controls.

A **job board is never an application destination.** Search and filter inputs,
site chrome, and saved-job toggles are excluded from surface detection, so a
results page cannot be mistaken for a form to fill.

## Resume tailoring rules

- The base resume is parsed into evidence-backed facts.
- Tailoring may reorder, select, and rephrase existing evidence.
- It may not invent employers, dates, degrees, metrics, tools, or experience.
- A generated claim retains links to its source evidence for review.
- Each job gets a separate generated document and audit record.
- Generated DOCX/PDF files use a single-column US Letter layout and remain in
  the local service. The extension can attach a generated DOCX to a detected
  resume file input without exposing the provider key or local file paths.

## Delivery milestones

1. **Foundation:** local API, profile memory, side panel, tests, and privacy
   boundaries.
2. **Onboarding:** complete questionnaire, encrypted local sensitive fields,
   resume import, and answer editing.
3. **Job understanding:** page extraction, normalized job model, fit analysis,
   and chat grounded in the active job.
4. **Resume tailoring:** evidence model, DOCX/PDF output, diff preview, and user
   approval.
5. **Application engine:** field mapping, synthetic ATS test harness, validation,
   screenshots, and audit log.
6. **Site adapters:** LinkedIn Easy Apply and employer ATS adapters, built and
   tested individually because their DOMs change independently.
7. **Hardening:** retries, recovery, observability, packaging, privacy review,
   and end-to-end tests.

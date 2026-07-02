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
provider is reserved for job-fit analysis, free-text assistance, evidence
extraction, and job-specific résumé tailoring.

## Company-site-first routing

The source listing is not assumed to be the application destination. For every
job, the orchestrator attempts to resolve and verify an official company career
page or recognized ATS URL first. This remains the preferred route even when
the listing exposes LinkedIn Easy Apply.

```text
Job listing
    |---- verified company/ATS URL ----> company application (preferred)
    |---- no verified external URL ----> Easy Apply (fallback)
    `---- ambiguous or unsafe URL ------> ask the user
```

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
- **Generic:** standards-based JobPosting JSON-LD plus visible HTML controls.

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

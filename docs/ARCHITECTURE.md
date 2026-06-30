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
      `---- AI provider (server-side key only)
```

The browser extension owns page interaction. The local service owns reasoning,
personal data, document generation, audit history, and validation. Keeping the
AI key out of the extension prevents it from being exposed in browser assets.

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

## Site adapters

Every supported application surface implements the same small contract:

1. detect whether the adapter applies;
2. extract job title, company, description, location, and form fields;
3. map known profile answers to visible inputs;
4. report unknown or ambiguous questions;
5. validate the filled form;
6. stop at review before final submission.

The generic form mapper runs before site-specific logic. It handles standard
HTML controls, maps high-confidence profile fields and reusable answers, blocks
password/payment/authentication fields, and returns unknown required questions.
Site adapters add stronger selectors and multi-step navigation without changing
the review-before-submit boundary.

The first adapters will target a synthetic test ATS, one common employer ATS,
and LinkedIn Easy Apply. The company/ATS route remains preferred. Generic form
support comes after these are reliable.

## Resume tailoring rules

- The base resume is parsed into evidence-backed facts.
- Tailoring may reorder, select, and rephrase existing evidence.
- It may not invent employers, dates, degrees, metrics, tools, or experience.
- A generated claim retains links to its source evidence for review.
- Each job gets a separate generated document and audit record.

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

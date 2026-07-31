# Changelog

Versions in `pyproject.toml`, `extension/manifest.json` and
`src/applypilot/__init__.py` move together, and a test asserts it.

## 1.0.0

Rebuilt from nothing. The previous tree is gone; the history is not.

### The rule everything is built around

"Verified" now means one thing: a fresh read found the requested value in state
the page itself owns. Four outcomes are reported and kept distinct — attempted,
accepted, verified, failed — and a failure is never overwritten by a later,
weaker claim of success.

### Matching

- Structural rather than substring. An alias has to line up with the whole
  visible label, so "Position" no longer answers "Position Location".
- When a label names several subjects the most specific one owns it, so a saved
  Country stops answering a question about visa sponsorship.
- Modifiers and trailing digits make a different field: "Home Phone" is not
  "Phone", "Address Line 1" is not "Address Line 2".
- Only the visible label is read. A form naming its State control
  `countryRegion` gets no vote.
- Structured history answers inside an education or employment block, or behind
  a label that can mean nothing else.
- Options are ranked by closeness with a length-gap ceiling; placeholder rows are
  never answers; a tie is a question.
- Value vocabulary is scoped by fact, so `MS` is Mississippi to an address field
  and a Master's degree to an education one.

### Reading pages

- Traversal pierces shadow roots, in document order.
- Page kind comes from the controls present, never the URL.
- An application no longer needs a `<form>` element.
- A list of jobs offers no fields, including boards that link to opaque paths.
- The invisible reCAPTCHA badge is a badge.
- Options come only from a list the control owns.

### Getting to the right page

- Host identity is decided from the URL. A model never decides to stop.
- Adapters for Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable,
  Recruitee, SuccessFactors, Phenom, iCIMS, Taleo, Jobvite, ADP and others.
  Workable and Phenom were falling back to generic; both are recognised now,
  Phenom from the page when it is served from the employer's own domain.
- The posting's own apply control beats a board search, and a board match on the
  company alone is never followed.

### The rest

- Guided onboarding, with the legal questions grouped so they are answered once.
- Résumé extraction into editable education and work records.
- Learning hygiene: option ids, placeholders, page furniture and mis-scanned
  labels are refused.
- Side panel with one Start/Stop, one question at a time, and a checklist that
  scrolls to and highlights a field.
- Chat instructions that always end in a scoped action, a choice card or one
  focused question.
- Local encrypted application history, exportable as CSV.
- Session sign-in authorisation that holds no secret and matches hosts exactly.
- `/health` reports the running version and the panel warns on drift.
- A live-site check that reads real employer pages before every push.

Everything in `docs/REGRESSIONS.md` has a test.

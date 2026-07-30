# CLAUDE.md — permanent rules for ApplyPilot

Standing rules for any session working on this repository. These do not
expire. Current status, open work, and next steps live in `HANDOFF.md`, not
here.

ApplyPilot is a public, local-first job-application **browser agent**: a
Chrome side-panel extension plus a private FastAPI companion on the user's own
computer. It is not a chatbot around an autofill script.

## 1. The verification invariant

This is the project's central rule; everything else is secondary to it.

- **"Verified" means a fresh rescan observed the requested value in state the
  page itself owns.** Never that a click was issued, never a marker or
  attribute ApplyPilot wrote itself.
- Authoritative signals only: native `checked`/`value`, ARIA
  checked/pressed/selected set by the page, page-owned `data-*` state,
  page CSS state classes, associated hidden inputs, validation state.
- **Never write a state attribute and then read it back as proof.** A prior
  release did exactly this (`data-applypilot-selected`) and produced false
  success reports. Do not reintroduce that pattern in any form.
- Keep the four outcomes distinct and report them honestly: **attempted**,
  **page accepted/changed**, **verified desired value**, **failed/ambiguous
  with evidence**. `filled_ids` means verified, not attempted.
- If no authoritative signal exists, report "attempted but not verified" and
  ask the user to check. Never claim success you cannot observe. Never
  persist an unverified value as a reusable answer.
- Actions are **idempotent**: if the target is already authoritatively
  selected, do not click it. Clicking a selected custom toggle turns it off.
- Identify controls by **stable fingerprints** (frame, normalized question
  label, control type, option labels, name/accessible identity) — never by
  DOM index or a numeric `ap-N` id that a re-render can rotate.

## 2. Architecture boundaries

- `extension/service-worker.js` is the **only** browser-action boundary. All
  page reading and interaction happens through its injected functions.
- `extension/sidepanel.js` owns workflow state, chat routing, and UI.
- `src/applypilot/` owns reasoning, personal data, documents, and history.
- **Deterministic code owns identity, safety, execution, and verification.
  Models only interpret wording and choose among visible options.** Model
  output is untrusted: validate every proposal against live field IDs and
  visible options before executing, and verify from a fresh observation.
- Prefer a small explicit state machine and typed observations/actions over
  adding more prompt text.
- **Fix general mechanisms, never individual sites.** Do not hardcode
  question strings, employer names, or one ATS's DOM. If a real page breaks
  something, generalize the control/verification layer.
- An explicit user instruction about a visible form must end in a scoped
  browser action, a choice card, or one focused clarification — **never**
  generic chat prose.
- Bind a bare reply to exactly one pending question/fingerprint. If several
  questions match, ask which one; do not guess or fan out.

## 3. Safety and truthfulness

- Never fabricate qualifications, experience, skills, metrics, employers,
  degrees, dates, or certifications. Tailoring may reorder and rephrase real
  evidence only.
- Never bypass CAPTCHA, MFA, verification codes, rate limits, or anti-bot
  systems. Those are always user handoffs.
- Never store, read, or type passwords. The browser password manager owns
  credentials; ApplyPilot may only detect that fields are filled and click an
  allowed login control when the user enabled that.
- Never click final Submit outside the saved submission policy, and never
  report `submitted` without an on-page confirmation signal.
- Never auto-answer demographic questions unless the user explicitly saved
  that preference. "Prefer not to answer" must be a saved choice, not an
  inference.
- Never submit payment, banking, purchasing, or destructive actions.
- Report outcomes faithfully. Do not say "verified", "attached", "saved", or
  "submitted" unless the corresponding state was actually observed.

## 4. Privacy

- All personal data stays local and encrypted. This is a **public**
  repository.
- Never commit: `.env`, API keys, résumés, cover letters, profile data,
  SQLite databases or their key files, browser profiles, generated
  application documents, `tmp/` logs, or screenshots containing personal
  information.
- Provider keys are encrypted in the local store; the extension must never
  receive a decrypted key. Never log or echo key values.
- The user's live workspace with real data is a **separate folder** from this
  clone. Do not inspect, migrate, or disturb its `.env`, `data/`
  (`applypilot.sqlite3` plus its `.key`), or documents.

## 5. Git and authorship

The repository must read as the owner's own engineering project.

- **Never** add `Claude`, `Anthropic`, `Codex`, `OpenAI`, "AI generated", or
  similar to branch names, commit subjects, PR titles/bodies, release notes,
  README text, code comments, badges, or contributor metadata.
- **Never** add `Co-authored-by`, `Generated-by`, bot trailers, or
  Claude/Anthropic email addresses to commits.
- Commit as the repository owner:
  `Deekshitth Vegi <65802453+deekshitvegi@users.noreply.github.com>`.
  Verify author configuration before committing; if you cannot use the
  owner's identity safely, stop and ask.
- Use neutral branch names describing the product change
  (`fix/verified-control-state`, `feat/browser-action-loop`). No `claude/`
  or `codex/` prefixes.
- Never rewrite or force-push `main`. Work on a branch, run checks, push,
  open a normal PR, let CI pass.
- **Do not merge your own PR unless the user explicitly asks for that PR.**
  Ask; the merge is the user's decision.
- Preserve unrelated user changes; never run destructive Git commands.

## 6. Testing and delivery

- Run the full suite before pushing:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q
  .\.venv\Scripts\python.exe -m ruff check .
  node --check extension\service-worker.js
  node --check extension\sidepanel.js
  .\.venv\Scripts\python.exe -m json.tool extension\manifest.json
  ```
- Browser-level tests live in `tests/test_browser_verification.py` and drive
  the **real injected extension functions** in headless Chromium via
  Playwright against fixtures in `tests/fixtures/`. They must assert
  **page-owned DOM state**, never an action function's return value.
- **Run `python scripts/live_check.py` before every push.** It drives the real
  injected functions and the running companion against live employer pages
  (an ADP two-step sign-in, Greenhouse, Lever, Ashby) and asserts what has
  regressed before: sign-in pages detected, application forms *not* detected
  as sign-in pages, and known fields actually filling. Fixture tests alone
  did not catch a change that made every application look like a login page.
- **Restart the companion after any Python change, then confirm `/health`
  matches `extension/manifest.json`.** A running service keeps serving the
  code it started with, so a backend fix silently does nothing until it is
  restarted - this has wasted entire debugging sessions.
- Add a regression fixture/test for every repaired behavior, especially any
  bug the user reports from a live page.
- Passing tests are not proof of live correctness. Do not call something
  fixed on a real ATS until it has been observed working there.
- Update `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, and the version
  in `pyproject.toml`, `extension/manifest.json`, and
  `src/applypilot/__init__.py` together whenever behavior changes.
- After backend changes, restart the local companion and report the
  `/health` version. Tell the user exactly how to reload the extension
  (`chrome://extensions` → Reload → refresh the job page → reopen the panel)
  and reproduce the fixed flow — **code changes never reach a running
  extension until it is reloaded.**

## 7. Product and UI principles

- The primary surface stays calm and understandable to a non-developer: one
  Start/Stop control, current activity, one pending question, and chat.
  Provider, permission, résumé, profile, and automation settings belong
  behind Settings.
- Settings must be written in plain language, grouped, and each control
  explained in one line. Assume the reader is not an engineer.
- The chat is an agent control surface, not a help desk. It narrates what the
  agent is doing in the first person so the user can interrupt and correct
  mid-run.
- The user is free and private by default: deterministic autofill plus local
  Ollama, with optional cloud keys used selectively.
- Simplify (simplify.jobs) is a **UX benchmark only**. Never copy its
  implementation, branding, copy, or visual identity.
- Verify UI work by actually rendering it and looking at screenshots in both
  light and dark mode before calling it done.

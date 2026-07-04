# ApplyPilot Project Handoff

> Temporary handoff file for the next coding assistant.
>
> Read this entire file before changing code. Once you have inspected the
> repository and can accurately restate the product goal, architecture, current
> behavior, and remaining defects, delete this file. Include that deletion in
> your eventual pull request so this temporary handoff does not remain on
> `main`.

## Your role

You are taking over implementation of **ApplyPilot**, a public, local-first job
application browser agent. Continue from the current `main` branch. Do not
restart the project, replace it with a mockup, or add more one-off rules for the
specific job application used during testing. Diagnose and improve the general
agent/executor architecture.

Before editing:

1. Read this file completely.
2. Read `README.md`, `docs/ARCHITECTURE.md`, and `CHANGELOG.md`.
3. Inspect the extension, API, models, form mapper, provider manager, storage,
   tests, and synthetic ATS.
4. Run the existing test suite.
5. Explain to the user what is actually failing and what architectural change
   you intend to make.
6. Delete this file only after you understand it. Do not merely read the first
   section and delete it.

## Repository and current baseline

- Repository: <https://github.com/deekshitvegi/applypilot-agent>
- Expected branch at handoff: `main`
- Current release at handoff: `0.11.4`
- Current merged head at handoff: PR #29, commit `3fec16e`
- Local workspace on the original machine:
  `C:\Users\deeks\OneDrive\Desktop\DV\Python\Jobs Applying Agent`
- Local API: `http://127.0.0.1:8765`
- Start the companion on Windows:
  `powershell -ExecutionPolicy Bypass -File .\scripts\start-background.ps1`
- Extension source: `extension/`
- Load unpacked from `extension/` using `chrome://extensions` or
  `edge://extensions`.
- Existing verification at handoff: 85 Python tests, Ruff checks, and Node
  syntax checks pass. Passing tests do **not** mean the live ATS interaction is
  correct; the current tests do not adequately verify custom-control behavior.

Never commit `.env` files, API keys, resumes, cover letters, personal profile
data, SQLite databases, browser data, generated application documents, or
screenshots containing personal information. This is a public repository.

## Original Windows PC inventory

The original development/test machine contains useful local state that is not
in GitHub. Inspect it only as needed, preserve it, and never copy private files
into the public repository.

### Workspace and runtimes

- Operating environment: Windows with PowerShell; the user reported 16 GB RAM.
- Workspace:
  `C:\Users\deeks\OneDrive\Desktop\DV\Python\Jobs Applying Agent`
- The workspace is inside OneDrive. Avoid simultaneous bulk moves/deletes and
  allow for sync delays or file-locking when editing generated/local files.
- Python virtual environment: `.venv\`
- Virtual-environment interpreter: `.venv\Scripts\python.exe`
- Python runtime observed at handoff: Python 3.11.0
- Node runtime observed at handoff: v23.11.0
- Git observed at handoff: 2.49.0.windows.1
- GitHub CLI observed at handoff: 2.95.0
- Important Python packages observed at handoff:
  - `google-genai` 1.75.0
  - `fastapi` 0.138.2
  - `uvicorn` 0.49.0
- `pip show applypilot-agent` still reports old installed metadata `0.2.0`,
  while the checked-out application and `/health` report `0.11.4`. Imports are
  currently using the workspace code, but after packaging/version changes run
  the setup or editable-install step so installed metadata is refreshed. Do
  not “fix” this by downgrading the source version.

### Local companion and startup

- ApplyPilot local service: `http://127.0.0.1:8765`
- Health endpoint: `http://127.0.0.1:8765/health`
- Health observed while this inventory was written:
  `{"status":"ok","service":"applypilot","mode":"local","version":"0.11.4","revision":"local"}`
- Start foreground: `.\scripts\start.ps1`
- Start hidden/background: `.\scripts\start-background.ps1`
- Diagnose setup: `.\scripts\doctor.ps1`
- Setup: `.\scripts\setup.ps1`
- A Windows Startup shortcut already exists at the user's Startup folder as
  `ApplyPilot.lnk`. It invokes `scripts\start-background.ps1` when the user
  signs in. There is no ApplyPilot Scheduled Task; do not create a duplicate
  startup mechanism unless the user asks.
- The local process has stopped unexpectedly during testing, producing
  `Failed to fetch` in the extension. If this recurs, inspect process lifetime,
  startup behavior, and ignored logs before merely restarting it. Keep this
  separate from page-action verification bugs.

### Local AI/Ollama

- Ollama executable:
  `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`
- Ollama API: `http://127.0.0.1:11434`
- Ollama version observed at handoff: 0.31.1
- Models already downloaded locally:
  - `qwen3:4b` — approximately 2.5 GB; current recommended text/reasoning model
    for this 16 GB machine;
  - `gemma3:4b` — approximately 3.3 GB; used for local image understanding;
  - `qwen3:8b` — approximately 5.2 GB; available but slower and more
    memory-intensive on this machine.
- Do not redownload models unnecessarily. Do not commit model files. Account
  for Ollama memory use when browser, Codex/Claude, and the local service are
  running together.

### Private local configuration and data

- `.env` exists at the repository root and is ignored by Git. It may contain
  local configuration or secrets. Do not print it, quote it, attach it, commit
  it, or expose any value from it. Use `.env.example` for public documentation.
- Local database: `data\applypilot.sqlite3` (about 1.9 MB at handoff).
- Local encryption key: `data\applypilot.sqlite3.key`.
- Preserve the database and its key together. They contain the user's local
  profile/application/provider/document state. Do not inspect their contents,
  migrate them destructively, replace them, or upload them without explicit
  user approval and a backup/migration plan.
- Provider keys entered through ApplyPilot are intended to be encrypted in the
  local store. The extension must never receive the decrypted key.
- The user's resume, generated resumes, cover letters, reusable answers,
  application history, and personal profile belong only in ignored local
  storage—not GitHub.
- Ignored local directories/files include `.venv/`, `.env`, `data/`, `build/`,
  `dist/`, `tmp/`, browser profiles, databases, resumes, and applications.
- `tmp/` contains historical service/preview stdout and stderr logs. They may
  help diagnose crashes, but treat them as potentially sensitive and never
  commit them.
- `dist/applypilot-extension.zip` is a locally generated extension package.
  Rebuild it with `scripts\package-extension.ps1`; do not assume an old ZIP
  contains the latest source.

### Browser extension and browser-owned state

- The unpacked extension source directory is:
  `C:\Users\deeks\OneDrive\Desktop\DV\Python\Jobs Applying Agent\extension`
- Chrome/Edge must load that **folder**, not the old ZIP. After extension code
  changes, use Reload on `chrome://extensions`/`edge://extensions`, then refresh
  the job/application page and reopen the side panel.
- Site-access permission is optional host permission requested by the extension.
  Verify it is enabled for the current job site and any cross-origin embedded
  application frame.
- Browser passwords, login sessions, cookies, extension local/session storage,
  and site state live in the user's browser profile and are not in GitHub.
  Never export, copy, or inspect passwords/cookies.
- The browser password manager may populate login fields when the user enabled
  browser-assisted login. ApplyPilot may detect filled state and click a unique
  allowed login/continue control, but must not read or store credentials.

### Hosted/public resources

- GitHub repository: <https://github.com/deekshitvegi/applypilot-agent>
- Render demo: <https://applypilot-agent.onrender.com>
- Synthetic hosted ATS: <https://applypilot-agent.onrender.com/demo/ats>
- Render is configured by `render.yaml` as a public `APPLYPILOT_DEMO_MODE=true`
  service with temporary `/tmp` storage. It is for product/demo testing, not
  personal profiles, real resumes, private provider keys, or real applications.
- The Render free instance may spin down and start slowly. Do not confuse the
  hosted demo with the private local companion used by the extension.

### Useful repository scripts and generated areas

- `scripts\setup.ps1` / `setup.sh`: install/setup local environment.
- `scripts\start.ps1` / `start.sh`: run the local companion in foreground.
- `scripts\start-background.ps1`: hidden Windows startup.
- `scripts\enable-autostart.ps1` and `disable-autostart.ps1`: manage the
  existing Windows Startup shortcut.
- `scripts\doctor.ps1`: local readiness checks.
- `scripts\package-extension.ps1`: generate the extension ZIP in `dist/`.
- `scripts\render_sample_resume.py`: development document rendering helper.
- `build/`, `dist/`, and `tmp/` are generated/ignored. Source changes belong in
  `src/`, `extension/`, `tests/`, `docs/`, and public configuration files.

## Product vision

The user does not want a chatbot wrapped around an autofill script. They want a
real browser agent that observes the current page, understands the current job
and application stage, chooses a safe action, executes it, verifies the actual
page result, repairs failures, and continues.

The intended experience is inspired by the speed and simplicity of
[Simplify Copilot](https://simplify.jobs/copilot), but ApplyPilot must add a
more agentic workflow. Use Simplify as a UX benchmark only. Do not copy its
proprietary implementation, branding, text, or visual identity.

The desired workflow is:

1. The user completes one reusable local candidate profile and uploads a base
   resume. Common fields such as name, email, phone, location, work
   authorization, sponsorship, race/ethnicity choices, disability, veteran
   status, links, and other saved preferences should fill without an LLM call.
2. The user opens a job on LinkedIn, Indeed, Dice, a company careers page, or
   another job portal and chooses **Start applying** once.
3. ApplyPilot captures and remembers the job title, company, job description,
   source URL, and source site before navigating away.
4. ApplyPilot should prefer the employer/company application route over
   LinkedIn Easy Apply when an official route is available, even if Easy Apply
   also exists. Easy Apply must still work when it is the selected/available
   route.
5. The job description must remain attached to the application context across
   redirects, safety reminders, employer landing pages, login pages, ATS pages,
   popups, multiple tabs, and multi-step forms.
6. ApplyPilot analyzes the resume and job description and prepares the best
   **truthful** tailored resume. It must never invent experience, skills,
   metrics, employers, degrees, dates, or certifications.
7. The user can choose original resume, tailored resume, or ask each time.
   Cover-letter policy must likewise support never, generate/attach, use a
   saved letter, or ask each time.
8. The agent opens the application, detects whether the page is a job listing,
   login, form step, review step, safety interstitial, CAPTCHA/MFA handoff, or
   confirmation, and takes the correct next action.
9. Normal login may continue only with explicit user consent and browser-managed
   credentials. ApplyPilot must not capture or store passwords. CAPTCHA, MFA,
   verification codes, and security challenges remain user handoffs; do not
   bypass them.
10. The agent fills known fields immediately. It reasons over unfamiliar
    fields using verified profile facts, saved answers, resume evidence, source
    context, and visible options.
11. If an answer is genuinely unknown, the side-panel chat asks exactly one
    focused question. For radio, dropdown, checkbox, or multi-select questions,
    present the same visible options as a native choice card. A user's answer
    must be bound to that exact question, applied, visibly verified, and saved
    for semantically equivalent future questions.
12. The chat is an agent control surface. Commands such as “select LinkedIn,”
    “I do not require sponsorship,” “add GitHub CI,” “use Experienced,” “I am
    open to relocating anywhere in the US,” or “change my last answer to …”
    must change the live page rather than produce generic advice.
13. The chat should narrate concise live activity—reading job, opening employer
    site, filling profile, preparing resume, asking for one missing answer,
    waiting for login, reviewing, submitting—so the user can interrupt or
    correct the agent.
14. The submission policy must support ask before final submission or always
    allow. The agent may only report `submitted` after observing a reliable
    employer-site confirmation. Never infer submission from a button click or
    missing form.
15. After confirmed submission, record company, role, source, URL, date/time,
    resume type/artifact, status, and audit events in local application history.
    Email response tracking is a future optional OAuth integration, not part of
    the immediate repair.
16. The user should be able to stop and resume without returning to LinkedIn or
    losing the captured job/application state.
17. The primary mode should be as free and private as practical: deterministic
    autofill plus local Ollama for unlimited work, with optional Gemini assist
    used selectively for stronger resume tailoring and unfamiliar page/form
    reasoning. Gemini/OpenAI/Anthropic keys are entered in the local UI and
    encrypted locally. Never commit or log them.

The public UI should feel calm, simple, and understandable to a non-developer.
Advanced provider, permissions, resume, profile, and automation preferences
belong behind Settings. The primary surface should emphasize one Start/Stop
control, current activity, one pending question, and chat.

## Existing architecture

The project deliberately separates reasoning from page interaction:

- `extension/service-worker.js`
  - injects read-only scanners and guarded action functions into the active tab
    and frames;
  - captures jobs, scans forms, discovers page controls, clicks allowed
    controls, fills fields, attaches files, advances steps, submits, and checks
    confirmations;
  - must be the only browser-action boundary.
- `extension/sidepanel.js`
  - owns workflow state, chat routing, profile/resume/settings UI, application
    loop, model requests, answer memory, choice cards, and activity messages.
- `src/applypilot/main.py`
  - exposes the local FastAPI endpoints for profile, resumes, evidence,
    tailoring, forms, chat, providers, files, and application history.
- `src/applypilot/form_mapper.py`
  - performs deterministic high-confidence mapping from the canonical profile
    and saved answers to structured fields.
- `src/applypilot/ai.py`
  - provider abstraction and routing for Ollama, Gemini, OpenAI, and Anthropic;
  - evidence extraction, job fit, resume tailoring, form decisions, page
    actions, answer drafting, cover letters, and chat.
- `src/applypilot/store.py`
  - encrypted local persistence for profile, answers, providers, documents,
    jobs, applications, and history.
- `src/applypilot/documents.py`
  - generates ATS-readable DOCX/PDF resume and cover-letter artifacts.
- `tests/`
  - unit/API/static extension tests; these need stronger browser-level coverage.
- `docs/ARCHITECTURE.md`
  - intended boundaries, workflow, safety model, and adapter contract.

The intended agent loop is:

`observe -> classify stage -> plan -> validate action -> act -> wait for page -> re-observe -> verify desired semantic state -> repair or continue`

Model output is untrusted. Models may propose only structured field/page actions
using controls present in the latest observation. The deterministic executor
must validate every proposal and verify the result from a fresh observation.

## What has already been built

The repository includes substantial working infrastructure:

- public local-first browser extension and local companion;
- reusable candidate onboarding/profile and editable saved answers;
- encrypted local provider configuration and document storage;
- Gemini, Ollama, OpenAI, and Anthropic provider options;
- optional hybrid Ollama + Gemini routing;
- base resume parsing, evidence extraction, job fit analysis, truthful resume
  tailoring, DOCX/PDF generation, and downloads;
- original/tailored/ask-each-time resume policy;
- optional saved/generated cover-letter policy and preview;
- job capture and route discovery for LinkedIn plus generic employer pages;
- adapters/signals for LinkedIn, Greenhouse, Lever, Workday, and generic pages;
- shadow-root and multi-frame scanning attempts;
- standard inputs, selects, textareas, file fields, native radios/checkboxes,
  ARIA controls, custom comboboxes, and segmented Yes/No detection;
- structured form agent and guarded page-action planner;
- evidence-first deterministic fill followed by unresolved-only model passes;
- in-chat choice cards and reusable answer memory;
- browser-assisted login consent without credential storage;
- ask-before-submit and always-allow settings;
- local CSV application history and audit events;
- synthetic ATS demo and automated tests;
- Render demo/deployment metadata for the public project UI.

Recent releases attempted to improve custom controls, page routing, provider
diagnostics, resume recovery, choice cards, and resume state. Read the full
`CHANGELOG.md`; do not assume the latest attempted fix is correct merely because
it is recent.

## Current critical failure

The extension still claims that actions were verified when the visible ATS page
did not change. The latest live reproduction is:

1. User says: `i dont require sponsorship`
2. ApplyPilot shows the sponsorship Yes/No card.
3. User chooses No.
4. ApplyPilot reports:
   `Verified: Will you now or in the future require sponsorship? -> No`
5. The actual application page remains unchanged.
6. Repeating the answer produces the same false verification.
7. User says: `add github ci` for the visible tools multi-select.
8. ApplyPilot reports one answer saved and verified, but the live checkbox does
   not change.
9. User says they are open to relocating anywhere in the USA.
10. Chat returns generic profile commentary and says no action is needed instead
    of selecting all valid relocation locations and clearing “unable to
    relocate.”

Earlier reproductions also showed:

- authorization and sponsorship both becoming Yes when the intended canonical
  answers are authorization Yes and sponsorship No;
- reapplying the same answer toggling a segmented control off;
- one short answer causing several unrelated choice groups to appear;
- generic chat prose swallowing explicit browser-action requests;
- numeric/stale field IDs pointing at a different control after reactive ATS
  re-renders;
- file uploads causing reactive forms to reset prior answers;
- visible Apply buttons omitted from page snapshots or located in a different
  frame;
- Stop/Start resuming from the wrong assumed application stage;
- `Failed to fetch` when the local companion process is not running. Treat this
  as a service-lifecycle problem, not an ATS reasoning problem.

### Important warning about v0.11.4

`extension/service-worker.js` currently uses a locally written
`data-applypilot-selected` marker to remember a custom choice after clicking it.
The scanner then treats that marker as selected. This is **not authoritative
verification**: ApplyPilot itself wrote the marker, so it can “verify” its own
claim even if the page framework rejected the click or did not update its real
state. This likely explains the latest false-positive transcript.

Do not preserve that marker as proof. It can be used only as transient attempt
metadata, if at all. Verification must come from page-owned/native state after a
fresh observation: checked/value state, ARIA state set by the page, framework
state exposed in the DOM, selected CSS/data state owned by the page, associated
hidden inputs, validation state, or another reliable semantic signal. If no
authoritative signal exists, report “action attempted but not verified” and ask
for a user check—never claim success.

Likewise, `filled_ids` must not mean “the executor issued a click.” It must mean
“a fresh scan observed the requested semantic value.” Separate result concepts:

- attempted action;
- page accepted/changed;
- verified desired value;
- failed/ambiguous with evidence.

## Required engineering direction

Do not solve only the TENEX/Ashby form or hardcode the exact question strings.
Build a reusable control and verification layer.

At minimum:

1. Introduce stable **field fingerprints** based on frame identity, normalized
   question/group label, field type, option labels, name/accessible identity,
   and nearby structure. Do not rely on `ap-6`, `ap-12`, or DOM index after a
   re-render.
2. Model each control group with explicit semantics:
   - single-select radio/segmented choice;
   - multi-select checkbox group;
   - boolean toggle with Yes/No mapping;
   - select/custom combobox;
   - text/textarea/number/date;
   - file upload;
   - page-navigation action;
   - final submission action.
3. Before acting, record the authoritative pre-state and target value.
4. Execute exactly one scoped action against the latest matching fingerprint.
5. Wait for mutation/navigation/framework updates using bounded observation,
   not only a fixed immediate check.
6. Rescan from the page after the action. Resolve the same fingerprint in the
   new DOM and compare its **page-owned semantic value** with the target.
7. Return verified only when the post-state equals the target. If the DOM
   re-rendered, recover by fingerprint. If state is unknowable, return
   ambiguous—not success.
8. Make actions idempotent: if the target is already authoritatively selected,
   do not click it. Never click a selected toggle merely because an internal
   marker is missing.
9. Ensure file uploads trigger a complete post-upload re-observation and reapply
   only fields whose page-owned state actually reset.
10. Route explicit user commands to the browser action interpreter before
    general chat. Generic prose must never be the fallback for a safely
    executable request about a visible field.
11. Bind bare replies to one `pending_question_id`/fingerprint, not fuzzy text.
    If there is no single pending question, ask which question the answer is
    for rather than guessing.
12. When the user references several questions in one message, parse them into
    separate scoped assignments and verify each independently.
13. Use the canonical profile as the source of truth for authorization,
    sponsorship, relocation willingness, name, email, phone, current title, and
    similar facts. The model may map wording/options but must not contradict
    canonical values.
14. Build browser-level regression fixtures for:
    - custom segmented Yes/No buttons with hidden backing state;
    - buttons that toggle off when clicked twice;
    - React-style re-render that replaces elements and changes numeric IDs;
    - multi-select checkboxes;
    - options inside iframes and shadow roots;
    - file upload resetting another field;
    - one bare Yes/No reply with two visible Yes/No questions;
    - relocation “anywhere” mapping to every valid location except “unable.”
15. Add assertions that the visible/page-owned state changed, not merely that an
    action function returned success.

Prefer a small explicit state machine and typed observations/actions over more
prompt text. Models should handle interpretation; deterministic code should
handle identity, safety, execution, and verification.

## Safety and truthfulness boundaries

- Never fabricate qualifications or answers.
- Never bypass CAPTCHA, MFA, verification codes, rate limits, anti-bot systems,
  or employer security controls.
- Never store or expose passwords. Browser password managers own credentials.
- Never auto-answer sensitive demographic questions unless the user explicitly
  saved that preference. “Prefer not to answer” can be a saved choice, but do
  not infer it.
- Never click final submit unless allowed by the saved submission policy.
- Never report submission without a page confirmation signal.
- Never submit payment, banking, purchasing, or destructive actions.
- Never use an API key from chat, source control, screenshots, or logs.
- Keep all personal data local and encrypted.

## GitHub and authorship rules

The repository must present as the user's public engineering project—not an AI
assistant's repository.

1. Do **not** add `Claude`, `Anthropic`, `Codex`, `OpenAI`, “AI generated,” or
   similar labels to branch names, commit subjects, PR titles, release notes,
   README text, code comments, badges, or contributor metadata unless the user
   explicitly asks for attribution.
2. Do not use branch prefixes such as `claude/` or `codex/`. Use neutral names
   such as `fix/verified-control-state` or `feat/browser-action-loop`.
3. Do not add `Co-authored-by`, `Generated-by`, “Made with Claude,” bot trailers,
   signatures, or Claude/Anthropic email addresses to commits.
4. Do not change the repository's owner identity to a Claude identity. Commits
   must use the repository owner's GitHub identity. On this repository, the
   established GitHub identity is:
   - name: `Deekshitth Vegi`
   - email: `65802453+deekshitvegi@users.noreply.github.com`
5. Before committing, verify author configuration. If you cannot safely use the
   owner's authenticated identity, stop and ask the user rather than committing
   as Claude.
6. Use neutral, conventional commit and PR language describing the product
   change only.
7. Do not rewrite or force-push `main`. Work on a branch, run checks, push, open
   a normal PR, let checks pass, and merge through the user's authenticated
   GitHub account.
8. Preserve unrelated user changes and never run destructive Git commands.

The user specifically does not want Claude to appear in GitHub's Contributors
list. Follow every authorship rule above.

## Working and delivery expectations

- Be honest about what is and is not working. Do not call the application
  complete until live end-to-end tests succeed on representative flows.
- Do not report “verified,” “attached,” “submitted,” or “saved” unless the
  corresponding authoritative state was observed.
- Keep the user updated during long work.
- Prefer generalized architecture and tests over quick selectors for one site.
- Preserve public usability: another person should be able to clone, run setup,
  load the extension, choose Ollama or a cloud key, create a local profile, and
  use the same workflow without this user's private data.
- Update README, architecture docs, changelog, and version when behavior changes.
- Run the full test/lint/syntax suite and add browser-level tests for repaired
  behavior.
- Push completed steps to GitHub with neutral names.
- Restart the local companion after backend changes and report the health/version
  response.
- Tell the user exactly how to reload and reproduce the fixed flow.

## If the user returns the project to Codex

Before your final handoff, create a temporary `RETURN_HANDOFF.md` containing:

1. exact starting and ending commits;
2. branch and PR URL(s), merge status, and release version;
3. concise architecture changes and why they were made;
4. every changed file and its responsibility;
5. tests added plus exact commands/results;
6. live sites/fixtures tested and observed outcomes;
7. remaining known defects and honest limitations;
8. database/configuration/schema or setup changes;
9. local companion health, extension reload instructions, and current Git status;
10. any decisions you need Codex to preserve;
11. a safe reproduction for anything still broken;
12. confirmation that no secret or personal file was committed.

Do **not** delete `RETURN_HANDOFF.md`; it is meant for Codex. Tell the user to
give Codex this exact instruction:

> Open the ApplyPilot repository, read `RETURN_HANDOFF.md` completely, inspect
> the referenced commits and tests, continue from the current branch/main as
> instructed, and delete `RETURN_HANDOFF.md` once you have understood and
> incorporated the handoff.

If the project is staying with you, do not create `RETURN_HANDOFF.md` yet.

## Definition of the next successful milestone

The next milestone is not “the model produced an answer.” It is this live,
observable behavior:

1. Start from a captured job and reach its employer application.
2. The canonical profile fills authorization Yes and sponsorship No.
3. The visible ATS controls actually show those values.
4. A fresh rescan independently observes those values from page-owned state.
5. Replanning and uploading a document do not toggle or erase them; if the site
   resets them, ApplyPilot detects and restores them once.
6. “Add GitHub CI” visibly selects only GitHub CI and a fresh rescan verifies it.
7. “I am open to relocating anywhere in the US” selects all offered relocation
   locations and clears the “unable to relocate” option, then verifies each.
8. No unrelated question cards appear.
9. Activity messages distinguish attempted, verified, ambiguous, and failed.
10. The agent proceeds to the next application stage without falsely submitting
    or falsely claiming success.

Only after this works reliably should work continue on broader queueing, email
status tracking, or polishing claims that the system is universally autonomous.


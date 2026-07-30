# ApplyPilot Agent

[![CI](https://github.com/deekshitvegi/applypilot-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/deekshitvegi/applypilot-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-6d5dfc.svg)](LICENSE)

**[Open the live demo](https://applypilot-agent.onrender.com)**

**[Test the synthetic employer ATS](https://applypilot-agent.onrender.com/demo/ats)**

ApplyPilot is a local-first job-application copilot. It is designed to read the
job currently open in the user's browser, tailor application materials, fill
repeatable questions, and keep the user in control through a browser side
panel.

The normal side-panel experience is intentionally conversational: start the
current application, follow live progress in chat, and answer any genuinely new
question directly in the chat composer. ApplyPilot stores that verified answer
locally, fills it, and reuses it on matching future applications. Questions and
help requests remain ordinary chat; `/answer ...` forces an ambiguous reply to
be treated as an answer, and `change my last answer to ...` corrects a mistake.
Free-text answers are first rewritten by the configured provider against the
employer's visible instructions; a narrow deterministic formatter is used only
when that provider is unavailable.
Commands such as `fill the rest`, `fill the next`, and `ask me the remaining
questions` operate on the current form and start the one-at-a-time question
flow instead of producing advisory chat.
Explicit corrections are executable too. For example, a single message can say
`add GitHub CI, add GCP, source is LinkedIn, authorized yes, sponsorship no`;
ApplyPilot applies every matching choice on the current page, stores the
verified answers locally, and reuses them later. It never converts an unrelated
question or ordinary chat message into a saved application answer.
When a visible question has a unique option, a concise reply such as
`Experienced` is applied directly. Enter sends the message; Shift+Enter adds a
line break.
On Ashby, ApplyPilot uses visible option labels rather than the platform's
generic internal `on` value, verifies each requested selection, and treats the
two Yes/No buttons plus their hidden backing input as one logical field.
"Verified" always means a fresh rescan observed the requested value in state
the page itself owns (native checked state, ARIA, page data attributes, state
classes, or a hidden backing input) — never that a click was merely issued.
Fields are identified by stable fingerprints (question, control type, and
option labels), so answers survive reactive re-renders that replace elements,
and an already-selected option is never clicked again, which keeps repeated
answers and file uploads from toggling a custom control back off. Controls
that expose no page-owned state are reported as "attempted but not confirmed"
so you can check them yourself; ApplyPilot never claims success it cannot
observe.
Action-oriented chat now uses the configured model as a real form agent. The
model sees structured live fields and returns typed actions; ApplyPilot
validates the field IDs and choices, executes them, verifies the page, and gives
the model one repair attempt when a requested action does not stick. Only
verified actions enter reusable memory. Deterministic autofill remains the free
fallback and final submission still follows the separate user approval policy.
The same reasoning loop is part of **Start applying**. It follows one fast
path: detect the form, fill profile and résumé-backed fields without AI, draft
evidence-supported job-specific responses, then give only the unresolved
controls to the model for up to three observe/action/verification passes. It
asks one chat question only when the profile, résumé, saved answers, source URL,
and visible options genuinely do not establish the answer.
When Ollama is selected and `GEMINI_API_KEY` is available locally, ApplyPilot
uses a low-quota hybrid automatically: Ollama handles unlimited chat and acts
as fallback, while Gemini is reserved for résumé tailoring, unfamiliar
page/form decisions, unique application responses, and generated cover
letters. Routine profile autofill never consumes a Gemini request.
You can also configure this without editing `.env`: open **Settings → AI
provider**, keep **Ollama** selected, and save the key under **Optional Gemini
assist**. The secondary key is encrypted separately in the local database.
ApplyPilot verifies the key with a small structured-action probe before showing
it as connected. When a page choice is ambiguous, chat mirrors the employer's
exact options as clickable single- or multi-select cards; applying a card
updates the live form and remembers the verified selection.
Provider
choices, automation preferences, profile editing,
résumé replacement, and troubleshooting tools stay behind the Settings button.

This is an open-source project intended for public use. Personal data remains
local and is never part of the repository.

## What users install

ApplyPilot has two user-facing pieces:

1. **ApplyPilot Companion** — the private local engine that stores the profile,
   prepares résumés, and runs local AI. Windows starts it automatically after
   the one-time setup.
2. **ApplyPilot browser extension** — the side panel that reads and fills the
   job page currently open in Chrome or Edge.

Users do not deploy or manage separate frontend and backend services. The
companion runs quietly on their own computer; the public Render deployment is
only a no-data demonstration for people viewing the GitHub project.

## Application strategy

ApplyPilot prefers the employer's official careers page or applicant tracking
system (ATS), including when a LinkedIn listing also offers Easy Apply. It
verifies that the destination belongs to the employer or a recognized ATS,
opens the external application in the user's existing browser session, and
continues the assisted flow there. This includes LinkedIn's JavaScript-based
external **Apply** button, even when its destination is not present as a normal
page link. LinkedIn Easy Apply is a fallback when no company application route
is available.

The same page-understanding loop also works from other job portals — Indeed,
Dice, Glassdoor, ZipRecruiter, Monster and SimplyHired — and from
employer-hosted job pages on Greenhouse, Lever, Workday, Ashby,
SmartRecruiters, iCIMS, Jobvite and Workable. A job board is always treated as
a place to *read* a listing, never as an application form: its search boxes,
filters and saved-job toggles are ignored. On multi-step applications,
ApplyPilot rescans each step, fills reusable answers, asks only for missing
information, and advances through **Next** and **Review**. The configured
ask/always-allow policy still controls the final submission.

The runner tracks whether it is viewing a listing, an application form, a
login step, a review step, or a confirmed result. Once a form is detected, its
fields take precedence over any remaining **Apply** links on the page. ApplyPilot
will not advance while visible required fields are empty, and it stops if a
control leaves the page unchanged instead of repeating the same action.
If an ATS replaces its embedded application iframe during the run, ApplyPilot
rescans the replacement frame and retries the pending fill once.

LinkedIn's job-search safety reminder is handled as part of the employer-site
handoff: ApplyPilot resolves **Continue applying** and opens the disclosed
destination without relying on the selected AI provider. LinkedIn-internal
`/safety/go` links remain inside LinkedIn's page context until they redirect to
the employer, preventing context-free “Page not found” tabs.

## Product boundaries

- The user chooses whether ApplyPilot asks before every final submission or
  submits automatically for the current browser.
- ApplyPilot uses the user's existing browser session and password manager. It
  never stores LinkedIn or employer passwords.
- It never bypasses CAPTCHA, MFA, rate limits, or anti-bot controls.
- Personal answers, resumes, generated files, and browser profiles stay out of
  Git through `.gitignore`.
- Site-specific automation must respect the site's current terms and the
  user's authorization.

## MVP status

This repository currently contains:

- a FastAPI service with onboarding, reusable-answer, résumé, multi-provider chat, and
  evidence-grounded tailoring endpoints;
- encrypted local SQLite persistence with a separate local encryption key;
- DOCX, PDF, and TXT résumé extraction;
- encrypted optional cover-letter storage with never, ask-each-time, and
  always-attach preferences, plus grounded job-specific cover-letter generation;
- a Chrome Manifest V3 side panel for onboarding, résumé upload, active-job
  capture, chat, and tailoring preview;
- a fully editable encrypted profile, including optional voluntary
  self-identification answers that are never inferred;
- deterministic cross-page autofill for common fields without using an LLM;
- evidence-grounded fit scoring, gap analysis, minimum-fit filtering, and a
  job-specific résumé preparation pipeline;
- ask-each-time and always-allow policies for tailored résumé attachment and
  final submission, plus LinkedIn queue continuation with a 10-job run cap;
- a company-site-first route planner;
- a generic form scanner/filler that maps verified profile answers, guides the
  user through every unanswered visible question, and remembers new answers;
- grouped radio/checkbox support for styled application controls, with captured
  job-source mapping and evidence-only résumé matching for technology choices;
- custom ARIA radio and pressed-button support for ATS sites that render Yes/No
  and referral-source choices without native radio inputs;
- plain segmented Yes/No button support for ATS controls that expose neither
  native radio inputs nor useful ARIA state;
- custom ARIA checkbox support for technology and location groups, including
  ATS controls rendered as accessible buttons rather than native inputs;
- separate résumé and cover-letter field detection so the selected résumé is
  attached early and a cover letter is included only under the user's policy;
- non-blocking document generation: an Ollama/cover-letter failure is reported
  without aborting deterministic form filling;
- generated cover-letter preview inside the side-panel Settings screen after
  the document has been prepared, without exposing it outside the local agent;
- automatic ATS-readable reconstruction from saved résumé text when a legacy
  upload no longer has attachable original bytes;
- optional browser-assisted login that clicks a unique login/continue control
  only after the browser password manager has filled credentials;
- a synthetic employer ATS for safe end-to-end testing;
- adapter detection and job extraction for LinkedIn, Greenhouse, Lever, and
  Workday, with recognized ATS links auto-verified and unknown external links
  held for review;
- encrypted per-job application sessions and audit events;
- downloadable local CSV application history with timestamps and confirmed
  submission status;
- live runner activity in chat plus remembered-answer commands for updating
  the current form and future applications;
- a guarded AI page planner for unfamiliar application sequences, with final
  submission always governed separately by the user's approval policy;
- application-entry discovery that ranks visible Apply controls ahead of
  unrelated navigation, including controls inside shadow roots and job-site
  frames;
- resumable Stop/Start behavior that keeps the captured job but re-inspects the
  live employer page instead of trusting a stale workflow step;
- a structured model form agent with validated field tools, clarification
  questions, page-state verification, and one-step repair after failed actions;
- encrypted original-résumé storage with original, tailored, and ask-each-time
  attachment preferences;
- guided blocked-question recovery that captures page options, remembers each
  answer, replans, fills, and resumes the active application runner;
- question-scoped chat answers: a short Yes/No reply is applied only to the
  pending question, while custom segmented controls retain their verified
  state across replans instead of being toggled twice;
- an explicit two-step final-submit approval that pauses for CAPTCHA/MFA and
  records `submitted` only after the site displays a confirmation signal;
- ATS-friendly DOCX and PDF generation from the evidence-grounded tailored
  draft, with download controls and local DOCX attachment to detected file
  inputs;
- tests for encryption, resume extraction, evidence validation, routing, and
  APIs, plus browser-level Playwright regression tests that run the real
  injected extension code against fixture forms for segmented Yes/No buttons,
  hidden backing state, toggle-off controls, React-style re-renders,
  multi-select checkbox groups, shadow-root options, and uploads that reset
  earlier answers;
- architecture and delivery milestones in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

This is a working MVP, not a claim of universal ATS compatibility. Employer
sites change frequently; unknown layouts stop safely and need a new adapter or
manual completion. CAPTCHA, MFA, verification codes, and ambiguous submit
controls always remain user handoffs.

## Hosted demo

The repository includes a Render Blueprint for a stateless public demo. The
hosted instance demonstrates service health and company-site-first routing, but
it disables candidate profile storage. Real resumes, answers, and browser
automation stay in the local service.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/deekshitvegi/applypilot-agent)

Render automatically rebuilds the service from `main` after it is linked to the
repository. Free instances can take about a minute to wake after being idle.

## Set it up on your computer (no coding needed)

ApplyPilot has two parts: a small private helper app that keeps your profile
and résumé encrypted on your own computer, and a browser extension that works
on job pages. Ten minutes, once:

1. **Install Python** (the helper runs on it). Download it from
   [python.org/downloads](https://www.python.org/downloads/) and, during
   installation, tick **"Add python.exe to PATH"**.
2. **Download ApplyPilot.** On this GitHub page choose **Code → Download
   ZIP**, then right-click the ZIP and **Extract All** somewhere easy, such as
   `Documents\ApplyPilot`.
3. **Run the setup script.** Open the extracted folder, right-click inside it
   while holding Shift, choose **Open PowerShell window here**, and run
   `.\scripts\setup.ps1`. This installs the helper, starts it, and makes it
   start automatically when you sign in to Windows.
4. **Load the extension.** In Chrome or Edge open `chrome://extensions`
   (or `edge://extensions`), switch on **Developer mode** (top right), click
   **Load unpacked**, and pick the `extension` folder inside ApplyPilot.
   Pin ApplyPilot to the toolbar so it is one click away.
5. **Tell it about you.** Click the ApplyPilot icon, open **Settings →
   Profile & résumé**, answer the profile questions once, and upload your
   résumé. Everything stays on your computer.
6. **Pick the AI.** In **Settings → Preferences**, keep the free option
   ("Free & private — runs on this computer") if you installed Ollama (see
   below), or paste a Google Gemini key. Then press **Save**.
7. **Apply.** Open any job on LinkedIn, Indeed, Dice, or a company careers
   page and press **Start applying**. ApplyPilot narrates every step in the
   chat, asks only when it truly needs you, and never presses the final
   Submit button without your permission unless you turn that on.

If the panel says the helper is not running, run `.\scripts\start.ps1` in the
ApplyPilot folder (or just sign out and back in — it starts automatically).

## Run locally (developers)

Requirements: Python 3.11+ and Chrome/Edge with extension developer mode.

### Windows quick start

Run the one-time setup:

```powershell
.\scripts\setup.ps1
```

This installs the Python package, starts the private companion, and registers
ApplyPilot to start automatically when the user signs in. Then:

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select the repository's `extension` folder.
4. Open a job listing and click ApplyPilot.

To disable automatic startup later, run
`.\scripts\disable-autostart.ps1`.

Quick setup on macOS/Linux:

```bash
./scripts/setup.sh
```

The companion can also be started manually when needed:

```powershell
.\scripts\start.ps1
```

Before loading the extension, check the local installation without revealing
the key:

```powershell
.\scripts\doctor.ps1
```

On macOS/Linux, run `.venv/bin/applypilot-doctor` and `./scripts/start.sh`.

Manual setup:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
applypilot
```

### Free local AI with Ollama

ApplyPilot can run Qwen3 entirely on your computer with no API key, request
limit, or cloud call. Install Ollama and download the model:

```powershell
winget install --id Ollama.Ollama --exact
ollama pull qwen3:4b
ollama pull gemma3:4b
```

In the side panel settings, choose **Free & private — runs on this computer
(Ollama)**, keep `qwen3:4b`, and press **Save**. The first response is slower
while the model loads.
Qwen3 handles text, reasoning, and résumé work; image attachments automatically
use the local `gemma3:4b` vision model. ApplyPilot limits the local context and
unloads the model after a short idle period so it does not occupy several
gigabytes of RAM for the rest of the browser session.

Alternatively, choose Gemini, OpenAI, or Anthropic, paste a newly generated
API key, and choose **Save securely**. The local agent encrypts the credential;
the extension never stores it or receives it back. After saving, the key field
is intentionally blank and marked **Saved key is active**; the **Connected**
badge means AI features are using that encrypted key. **Disconnect** deletes it
and turns off AI chat and AI drafting. Common-field scanning, mapping, and
filling still work without any API key. Environment variables remain available
for headless setups:

Gemini assist is tested with a minimal live model request before it is saved.
If Google rejects the request, ApplyPilot displays the safe reason returned by
Google (for example a disabled Generative Language API, project permission,
key restriction, unavailable regional free tier, inaccessible model, or
quota) while redacting key-shaped values. A failed test does not save the key.

```dotenv
GEMINI_API_KEY=your_new_key_here
# Or: OPENAI_API_KEY=...
# Or: ANTHROPIC_API_KEY=...
```

Never paste a key into an issue, commit, hosted demo, or ordinary chat message.
Only use the dedicated provider form while connected to the local agent.

The API will be available at `http://127.0.0.1:8765`. Check it with:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

For a safe form-filling test, open the synthetic ATS link above, capture the
job in the side panel, and choose **Run current job**. ApplyPilot analyzes the
page, asks each unanswered question in human-readable form, remembers the
answers, and fills the form. The page includes styled authorization radios,
technology checkboxes, and a policy acknowledgement to exercise grouped-field
handling. It intercepts submission and stores nothing.

The extension defaults to the local service. Its settings page can point to a
hosted demo URL; Chrome will ask for permission to contact that exact origin.

If the panel says **Agent is offline**, run
`.\scripts\start-background.ps1`, then choose **Try again**. Provider and
automation controls remain hidden while offline so users are not asked to
configure something that cannot yet be saved.

Profile values, reusable answers, résumés, provider credentials, and application
history are encrypted in `data/applypilot.sqlite3`. The local encryption key is
stored separately in `data/applypilot.sqlite3.key`; both paths are ignored by
Git. Saved profile values are reused across supported application pages and do
not require an AI provider. ApplyPilot never sends employer passwords to an AI
model. With login assistance enabled, it can click a unique login button after
Chrome's password manager has filled the fields; CAPTCHA, MFA, and verification
codes still pause the runner.

## Development

```powershell
pytest
ruff check .
.\scripts\package-extension.ps1
```

The browser-level control tests use Playwright. Install a browser once with
`python -m playwright install chromium` (they also fall back to an installed
Edge or Chrome, and skip with a notice when no Chromium-based browser is
available).

Do not put real candidate information, API keys, session cookies, or generated
resumes in GitHub. The repository can hold code and synthetic test fixtures
only.

## License

MIT. See [`LICENSE`](LICENSE).

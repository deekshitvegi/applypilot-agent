# ApplyPilot Agent

[![CI](https://github.com/deekshitvegi/applypilot-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/deekshitvegi/applypilot-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-6d5dfc.svg)](LICENSE)

**[Open the live demo](https://applypilot-agent.onrender.com)**

**[Test the synthetic employer ATS](https://applypilot-agent.onrender.com/demo/ats)**

ApplyPilot is a local-first job-application copilot. It is designed to read the
job currently open in the user's browser, tailor application materials, fill
repeatable questions, and keep the user in control through a browser side
panel.

This is an open-source project intended for public use. Personal data remains
local and is never part of the repository.

## Application strategy

ApplyPilot prefers the employer's official careers page or applicant tracking
system (ATS), including when a LinkedIn listing also offers Easy Apply. It
verifies that the destination belongs to the employer or a recognized ATS,
opens the external application in the user's existing browser session, and
continues the assisted flow there. LinkedIn Easy Apply is a fallback when no
verified company application route is available.

## Product boundaries

- The user reviews every application before the final submission.
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
- a generic form scanner/filler that maps verified profile answers, leaves
  passwords and authentication fields untouched, and reports unknown required
  questions;
- a synthetic employer ATS for safe end-to-end testing;
- adapter detection and job extraction for LinkedIn, Greenhouse, Lever, and
  Workday, with recognized ATS links auto-verified and unknown external links
  held for review;
- encrypted per-job application sessions and audit events;
- blocked-question recovery that remembers a new answer and replans the form;
- an explicit two-step final-submit approval that pauses for CAPTCHA/MFA and
  records `submitted` only after the site displays a confirmation signal;
- ATS-friendly DOCX and PDF generation from the evidence-grounded tailored
  draft, with download controls and local DOCX attachment to detected file
  inputs;
- tests for encryption, resume extraction, evidence validation, routing, and APIs;
- architecture and delivery milestones in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

This is a working MVP, not a claim of universal ATS compatibility. Employer
sites change frequently; unknown layouts stop safely and need a new adapter or
manual completion. CAPTCHA, MFA, credential entry, and ambiguous submit controls
always remain user handoffs.

## Hosted demo

The repository includes a Render Blueprint for a stateless public demo. The
hosted instance demonstrates service health and company-site-first routing, but
it disables candidate profile storage. Real resumes, answers, and browser
automation stay in the local service.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/deekshitvegi/applypilot-agent)

Render automatically rebuilds the service from `main` after it is linked to the
repository. Free instances can take about a minute to wake after being idle.

## Run locally

Requirements: Python 3.11+ and Chrome/Edge with extension developer mode.

Quick setup on Windows:

```powershell
.\scripts\setup.ps1
```

Quick setup on macOS/Linux:

```bash
./scripts/setup.sh
```

Start the local service:

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

In the side panel, choose Gemini, OpenAI, or Anthropic, paste a newly generated
API key, and choose **Save securely**. The local agent encrypts the credential;
the extension never stores it or receives it back. After saving, the key field
is intentionally blank and marked **Saved key is active**; the **Connected**
badge means AI features are using that encrypted key. **Remove key** deletes it
and turns off AI chat and AI drafting. Common-field scanning, mapping, and
filling still work without any API key. Environment variables remain available
for headless setups:

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

To load the browser side panel:

1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select the `extension` directory.
4. Pin ApplyPilot and click its toolbar icon on a job page.

For a safe form-filling test, open the synthetic ATS link above, capture the
job in the side panel, choose **Analyze visible fields**, inspect the plan, then
choose **Fill known fields**. The page intercepts submission and stores nothing.

The extension defaults to the local service. Its settings page can point to a
hosted demo URL; Chrome will ask for permission to contact that exact origin.

Profile values, reusable answers, résumés, provider credentials, and application
history are encrypted in `data/applypilot.sqlite3`. The local encryption key is
stored separately in `data/applypilot.sqlite3.key`; both paths are ignored by
Git. Saved profile values are reused across supported application pages and do
not require an AI provider. ApplyPilot never stores employer passwords and
pauses when login, CAPTCHA, or MFA is required.

## Development

```powershell
pytest
ruff check .
.\scripts\package-extension.ps1
```

Do not put real candidate information, API keys, session cookies, or generated
resumes in GitHub. The repository can hold code and synthetic test fixtures
only.

## License

MIT. See [`LICENSE`](LICENSE).

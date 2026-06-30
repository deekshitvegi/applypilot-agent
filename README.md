# ApplyPilot Agent

**[Open the live demo](https://applypilot-agent.onrender.com)**

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

## First checkpoint

This repository currently contains:

- a FastAPI service with health, candidate-profile, and onboarding endpoints;
- local SQLite persistence for reusable application answers;
- a Chrome Manifest V3 side panel that connects to the local service;
- tests for the profile store and onboarding question flow;
- architecture and delivery milestones in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
applypilot
```

The API will be available at `http://127.0.0.1:8765`. Check it with:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

To load the browser side panel:

1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select the `extension` directory.
4. Pin ApplyPilot and click its toolbar icon on a job page.

The extension defaults to the local service. Its settings page can point to a
hosted demo URL; Chrome will ask for permission to contact that exact origin.

## Development

```powershell
pytest
ruff check .
```

Do not put real candidate information, API keys, session cookies, or generated
resumes in GitHub. The repository can hold code and synthetic test fixtures
only.

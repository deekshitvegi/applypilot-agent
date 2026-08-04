# ApplyPilot

A Chrome side panel and a local service that fill job applications from your own
profile — and tell you the truth about what actually went onto the page.

Everything personal stays on your computer, encrypted, with the key in a
separate file. The service listens on `127.0.0.1` and nowhere else.

---

## The rule the whole thing is built around

**"Verified" means a fresh read of the page found the value you asked for, in
state the page itself owns.** It never means a click was issued, and it never
means the agent read back something it wrote.

Four outcomes, kept distinct and reported as they are:

| Outcome | What it means |
|---|---|
| **verified** | A rescan read the value from a native property, a hidden backing input, ARIA the page set, its own state attribute or class, or the widget's own rendered value. |
| **accepted** | The page changed, but not to what was asked for. |
| **attempted** | Something was done and the page exposes nothing to check it by. You are told to look. |
| **failed** | The page did not take it, with the evidence. |

A combobox's own text box is not on that list. Typing in it filters a list; it
is not a selection.

---

## Getting started

### 1. Set up

```powershell
cd C:\Users\deeks\Desktop\DV\Projects\applypilot-agent
.\scripts\setup.ps1
```

On macOS or Linux, `./scripts/setup.sh`.

### 2. Start the local service

```powershell
.\scripts\start.ps1
```

Leave it running. It prints the version and where your data lives.

Or have it start itself when you sign in, so opening Chrome is all you ever do:

```powershell
.\scripts\install-autostart.ps1
```

That puts one shortcut in your own Startup folder and starts the service
straight away. It runs `pythonw.exe`, so there is no console window and nothing
in the taskbar. Undo it with `.\scripts\install-autostart.ps1 -Remove`, which
deletes that one shortcut and nothing else.

Either way the service listens on `127.0.0.1` only.

### 3. Load the extension, the first time

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. **Load unpacked**
4. Choose the `extension` folder in this repository
5. Pin ApplyPilot to the toolbar and click it to open the side panel

### 4. What to enter first

The panel opens on **Set up your answers**. In order:

1. **Upload your résumé** (`.docx`). It reads your education and work history
   into editable records and fills in your name, email, phone and location. It
   takes only what the document says — anything it did not state stays blank.
2. **Answer the legal questions.** Work authorisation, sponsorship, 18-or-over,
   background-check consent. These are the ones every form asks, and answering
   them once is what stops them coming back.
3. **Paste your Gemini key** in Settings, if you want one. Matching your saved
   answers to a form works without it; a key is only used for wording and for
   picking between options the page itself offered.

Then open a job page and press **Start**.

### After any change to the Python code

```powershell
.\scripts\start.ps1     # restart it
```

A running service keeps serving the code it started with. The panel shows both
versions and warns when they differ, and `.\scripts\doctor.ps1` checks the same
thing from the terminal.

---

## What it does

**Ask once, answer forever.** Any phrasing of the same question resolves to the
same fact. "Country", "What country are you in?" and "Country/Region of
Residence" all answer *United States*, whether the control is a dropdown, a
radio group or a text box.

**Structured history.** Education and work entries as ordered records, extracted
from your résumé and editable. Repeating sections get an entry each, and the
"Add another" press is confirmed by the form actually growing.

**Custom dropdowns.** Opened with a real pointer sequence, read from the list
that control owns, selected, and verified from the page's own state.

**Routing.** The employer's own site is the destination. Host identity is
decided from the URL — a recognised hiring system is the employer, a job board
is where you started, and only an unknown host is worth stopping on. A model
never gets to make that call.

**Panel.** One Start/Stop, what it is doing right now, one question at a time,
and a checklist where clicking a row scrolls to that field and highlights it.

**Tracking.** A local, encrypted history of what you have applied to, exportable
as CSV. Nothing is recorded as submitted without the page saying so.

---

## What it will not do

- Fabricate anything. Tailoring reorders and rewords real records from your
  profile; there is no path by which an employer, a date, a degree or a metric
  can appear that was not already there.
- Touch a CAPTCHA, an MFA prompt or a verification code.
- Create an account — that accepts an employer's terms on your behalf. On a
  registration page it fills everything *except* the credentials, leaving you a
  password and a button.
- Press final Submit outside the policy you set, or call something submitted
  without an on-page confirmation.
- Answer the voluntary demographic questions unless you turn that on.

See [SECURITY.md](SECURITY.md) for how sign-in and your data are handled.

---

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest              # unit and browser tests
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe scripts\live_check.py  # real sites, before every push
.\scripts\doctor.ps1                              # versions and setup
```

The browser tests drive the **real injected functions** in headless Chromium and
assert against page-owned DOM state, never a function's return value.

`live_check.py` reads real employer pages and reports what the agent makes of
them. It fills nothing and submits nothing. Fixture tests are not enough on
their own: a change that made every application look like a login page once
passed every fixture in the suite.

Passing tests are not proof of live correctness. Nothing is called fixed on a
real applicant tracking system until it has been seen working there.

---

## Layout

```
extension/
  manifest.json        MV3
  service-worker.js    the only code that touches a page
  injected/            dom, surface, scan, verify, act -- loaded unchanged by the tests
  sidepanel.*          the panel
  options.*            settings, profile, learned answers, history
src/applypilot/
  text.py              label normalisation and phrase tests
  facts.py             what a profile can hold, and the words each fact owns
  mapper.py            which saved fact answers which field
  matching.py          choosing an option the page offered
  learning.py          what is worth remembering from a form
  surface / adapters / routing.py   whose page this is and where to go next
  runloop.py           the state machine
  main.py              the local API
docs/
  ARCHITECTURE.md      how the pieces fit and why
  REGRESSIONS.md       every mistake this has made, and what stops it now
scripts/               setup, start, doctor, live check, packaging
```

---

## Licence

MIT. See [LICENSE](LICENSE).

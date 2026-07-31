# Architecture

Two processes with one hard boundary between them.

```
  Chrome                                    your computer
  ┌───────────────────────────────┐         ┌──────────────────────────────┐
  │  side panel                   │  http   │  FastAPI on 127.0.0.1        │
  │   UI, chat, checklist         │◄───────►│   profile, saved answers,    │
  │   (never touches a page)      │         │   history, mapping, routing  │
  │            │ runtime message  │         │            │                 │
  │            ▼                  │         │            ▼                 │
  │  service worker               │         │  SQLite, encrypted           │
  │   the only browser boundary   │         │  key in a separate file      │
  │            │ chrome.scripting │         └──────────────────────────────┘
  │            ▼                  │
  │  injected/  dom surface scan  │
  │             verify act        │
  └───────────────────────────────┘
```

## Where authority lives

Deterministic code owns **identity, safety, execution and verification**. A
model only ever does two things: describe a page in words, or pick among options
that were already scraped off that page.

Every model reply is re-validated against live data before anything acts on it —
a chosen option must be one the page actually offered, a named control must be
one currently on the page. A reply that does not match is discarded with a
reason rather than repaired into something plausible.

This split exists because of a specific failure. Asked whether a listing
"belonged to the expected employer", a model answered no — correctly, since the
page was a job board — and the runner halted on the page it was always going to
start from. Describing a page is a model's job. Deciding whether to stop is not.

## The injected functions

`extension/injected/` holds five files, loaded in order into the isolated world
by `chrome.scripting.executeScript`. The browser tests load the same files with
`page.add_script_tag`, so what the tests drive is what ships.

| File | Owns |
|---|---|
| `dom.js` | shadow-piercing traversal in document order, visibility, visible-label resolution, stable fingerprints, repeat-block detection |
| `surface.js` | what kind of page this is, which controls could belong to an application, CAPTCHA state |
| `verify.js` | reading a control's value from state the page owns; the four verdicts |
| `scan.js` | building typed observations; no side effects, so it never opens a dropdown to see inside |
| `act.js` | filling, choosing, checking, attaching, adding a repeat entry — all idempotent |

`scan.js` has no side effects on purpose. A control's options are read at the
moment of choosing, from the popup that control owns, so no list of options can
be assembled out of unrelated things lying around the document.

## Verification

The signals, in the order `verify.js` prefers them:

1. native `checked` / `value` / selected option / file list
2. a hidden backing input inside the widget — what will actually be submitted
3. ARIA checked / pressed / selected, set by the page
4. `aria-activedescendant` → the option the page says is current
5. the page's own `data-*` state attribute
6. the page's own CSS state class
7. the widget's own rendered value element

A combobox's text box is deliberately absent. Anything the executor typed into
is marked and can never be read back. When nothing authoritative exists the
verdict is `attempted`, said plainly, with a request to look.

## Identity, not position

A control is identified by a fingerprint over frame, normalised visible label,
control kind, option labels, control name, and which entry of a repeating block
it belongs to. Never by index — a page that re-renders moves every index, and
several of them re-render as soon as you touch a country field.

The first entry of a repeating section carries no block marker, so adding a
second entry beside it does not change the identity of the first.

## Deciding what a page is

By the controls present. Never by the URL — an application served from
`postLogin.html` is an application, and a sign-in whose form lives in a shadow
root is a sign-in even with no password field on it.

```
registration?   two password fields, or one labelled Choose/Retype/Confirm
sign-in?        one password field and little else, or a lone username-shaped
                field with a Next button and nothing to attach or write
confirmation?   no controls and the page says the application was received
application?    five labelled controls, or a file input and two -- and not a
                page listing dozens of other jobs
list of jobs?   six or more posting links; its controls are filters
listing?        a single posting with its own apply control
```

An application does not need a `<form>` element. A complete 21-field application
rendered without one was seen and refused, so the test is what is on screen.

## Where to apply

The employer's own site. Host role comes from the URL: a recognised hiring
system is the employer, a recognised board is where a search starts, an
aggregator is neither, and an unknown host is the only thing worth stopping on.
Some systems are served from the employer's own domain, so the page reports
hints — script hosts and distinctive markup — and the adapter is matched from
those too.

Routes are scored by where they came from. The posting's own apply control wins
outright; a board match on both company and role can be followed; a board match
on the company alone cannot, because company slugs are shared between parents
and subsidiaries; a URL assembled from a pattern is last, because hand-built
apply endpoints redirect to careers home pages.

## The mapper

`mapper.py` decides which saved fact answers a field, and it is deliberately hard
to satisfy. It would rather hand a question back than put a plausible value in
the wrong box.

- Only the visible label is reasoned about.
- An alias must line up with the whole label — as the label, as its opening
  followed by a connector, or as its ending behind nothing but filler.
- The most specific subject in a label wins it.
- A modifier makes a different field; a trailing digit makes a different field.
- History answers inside a history block, or behind a label that can mean nothing
  else.
- Sentence questions get a separate, lower-scoring path that opens only once the
  sentence's dominant subject already belongs to the fact.
- Two facts fitting equally well is a question, not a coin toss.

`docs/REGRESSIONS.md` maps each of these to the failure that motivated it.

## Storage

SQLite holds opaque encrypted blobs. The key is a file beside the database and
never a column inside it. Ids and timestamps stay in the clear so the panel can
list applications without decrypting them all; nothing identifying is ever a
plain column.

## Versions move together

`pyproject.toml`, `extension/manifest.json` and `src/applypilot/__init__.py`
carry the same version, and a test asserts it. `/health` reports what the service
is actually running; the panel compares it with the extension's and says so when
they differ. A running service keeps serving the code it started with, and that
has cost more time than any bug in it.

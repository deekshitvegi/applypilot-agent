# Changelog

Versions in `pyproject.toml`, `extension/manifest.json` and
`src/applypilot/__init__.py` move together, and a test asserts it.

## 1.12.0

- **A dependent field is filled once it becomes answerable.** State holds nothing
  but "Choose" until a Country is chosen, so retrying State was useless — the
  answer did not exist yet. After any choice, the page is read again and the
  fields that now have options are filled.
- **A page takes seconds, not minutes.** Every control was given six seconds to
  come back from a search, including ones with nothing to type into, and a
  control that had already refused a value was asked again on every pass.
- **The résumé is not a setup question.** It is a document, uploaded in Settings;
  asking for it as a line of text to type was no use to anyone.

## 1.11.0

All three found by driving the live application, and confirmed there.

- **The school picker fills.** Its search box sits two levels above where the
  search for it stopped, so a control that types perfectly well was never typed
  into — and the answer was reported missing from a list that had never been
  searched.
- **"+ Add other education" gets pressed.** It is a bare span with no role and
  no href, so the search for clickable controls never saw it and the extra
  entries were never added.
- **The résumé attaches.** Its file input is `display:none` behind a styled
  dropzone, so the scan skipped it and there was no file control to attach to.

## 1.10.1

Fixes a regression introduced in 1.7.0.

- **The page watcher no longer fights the fill.** Filling a form changes the
  page, and the watcher reacted to that as though someone else had done it —
  re-planning on top of work in progress, over and over, so nothing ever
  finished and the panel sat there looking busy. It now stays out of the way
  while anything is in flight, waits for the page to settle across two checks,
  and ignores a page it has already planned against.

## 1.10.0

Read off the live application rather than guessed at.

- **A dropdown appended to `<body>` is found.** The school picker keeps a hidden
  select with no options for its value, shows a `role="combobox"` span, and hangs
  its dropdown — search box inside it — off the end of the document. A control
  that says it is open, with exactly one open list on the page, owns that list.
- **A name in bracket notation is read from its last meaningful part**, so
  `custom[eeo][race]` is a question about race.
- **A label belongs to its own field's row.** A field labelled with a bare
  asterisk was taking the label of the field above it and answering as that
  field.
- **A widget showing the field's own name is showing a placeholder**, not an
  answer.

## 1.9.0

- **A picker that searches a remote list is typed into properly and waited for.**
  Each character gets the events a real key press produces; a list that opens
  saying "Please enter 1 or more characters" is recognised as empty and gets the
  filter typed into it; and the search is given time to come back. When the
  answer really is absent, the failure now says what was on offer.
- **A widget's own value is no longer read as the field's label.** The picker
  renders the chosen school immediately before its input, so selecting anything
  changed the control's identity and every later action reported it as gone —
  the selection had worked, the control had just stopped being findable.
- Prompts like "Please enter…", "No results" and "Loading" are placeholders, so
  they are never offered as answers or counted as options.

## 1.8.0

- **Only the step on screen is offered.** A wizard keeps every step in the
  document, and the check for a styled control was returning true outright
  instead of going on to look at whether an ancestor was hidden — so every
  checkbox and radio in the document counted as visible. The panel offered a
  veteran form and a login choice from steps that were not showing, while the
  text fields on the step that *was* showing were judged hidden and left out.
  Found by driving a real application rather than a fixture.

## 1.7.0

- **A search-as-you-type control is opened with the answer typed into it.** A
  school picker that shows "Please enter 1 or more characters" offers nothing at
  all until something is typed, so opening it and reading an empty list was
  never going to work.
- **A control whose options did not cover the saved answer is opened again.** A
  dependent dropdown is usually read before the field it depends on is filled,
  so the options seen at scan time were the wrong ones.
- **When nothing matches, the panel says what was on offer** and how many, so a
  mismatch can be looked at rather than just wondered about.
- **"Add other education" gets pressed.** A form that starts with one education
  block and one job would only ever hold the most recent of each, however many
  are on file.
- **The panel notices when you move the page yourself.** Pressing Continue by
  hand used to leave it showing the previous step's plan until it was stopped
  and started again.

## 1.6.0

- **A section heading does not have to be a heading tag.** A form styling
  "Education" and "Work experience" as coloured divs looked, to the scanner, as
  though it had no sections at all — which blocked every education and
  employment field from resolving on a page whose answers were all saved.
- **A history record only answers inside its own kind of block.** "Start year"
  fitted an education entry and a job equally well, and an even fit is refused,
  so a field with an obvious answer came back as a question.
- **"start" is no longer owned by the notice-period question.** It is the
  ordinary word in "Start date" and "Start year", and owning it had been
  blocking both history start dates from ever resolving.
- **Your résumé is attached automatically** when a form asks for one, with a
  toggle in Settings. Attaching is verified from the control's own file list.
- **Education and work history have their own Save buttons.** One Save at the
  bottom of a long page did not read as saving the sections above it.
- Work history is described as one bullet point per line, which is how it is
  written out again.

## 1.5.0

- **A field the page fills in for itself is corrected.** Choosing a country made
  one form pick the first state in the list, so a saved Texas came out as
  Alabama and nothing said so. Filling now keeps going while the page keeps
  changing its mind, and says which fields it had to set again.
- **What you did in each role is visible and editable** in Settings. It was read
  out of your résumé and kept — it is what a tailored résumé reorders — but
  there was no way to see or correct it.

## 1.4.0

- **"Fill this in for me" is the first thing in Settings**, with two routes:
  your résumé (.docx) and your **LinkedIn data export** (.zip). Both only add
  what the file actually says and never overwrite what you entered yourself.
- The LinkedIn export carries every position, every school and your skills —
  usually more than a résumé spells out. There is deliberately no "Sign in with
  LinkedIn": it returns a name, an email and a picture and nothing else, so it
  would save nobody any work, and reading a profile page instead is against
  LinkedIn's terms.
- A three-part location such as "Austin, Texas, United States" is read as city,
  state and country rather than putting "Texas, United States" in the state.

## 1.3.0

- **A slashed label names the field twice.** "School / education institution"
  matched neither reading and was left empty on a form that had the school in
  the profile all along. Either side of a spaced slash now names the field.
- **Questions read as questions.** Required markers are stripped from what is
  shown, so "*GPA *" is "GPA *", and a field in a repeating block says which
  entry it belongs to rather than appearing three identical times.
- **Answering a history question saves into the right record.** A key such as
  `education.gpa` was written into the flat set of facts, where nothing read it,
  so answering it once did not stop it being asked again.
- **Setup asks what matters first.** It was stalling on "Middle name" at 28 of
  37 while work authorisation was still unanswered. Optional questions come last.
- **Résumé upload is in Settings**, not only during first-time setup, so it can
  be redone whenever the document changes.
- "Graduation Year" and "Start year" resolve, and a year-shaped field gets the
  year rather than "Jul 2025".

## 1.2.0

- **A required marker is no longer read as a field name.** On a form that puts
  its asterisk in its own element between the name and the control, every field
  came back labelled `*`, nothing matched, and the panel reported there was
  nothing it could fill on a form asking for a first name and an address. The
  asterisk is skipped when reading a label and looked for separately when
  deciding whether a field is required.
- **Fill and continue on its own**, as a toggle in the panel. It works through
  the steps, stops at the first thing it cannot answer, and never presses final
  Submit -- that stays governed by the submission policy in Settings.
- **The report is grouped the way it reads**: "Needs you" with the whole
  question, and "Completed" collapsed underneath. One primary control at the
  bottom says what happens next.
- A dependent dropdown holding only "Choose" is no longer offered as a question
  with no answers; it fills on the next pass once the field it depends on is in.
- "Zipcode" and "Pincode" answer the postal code.
- A busy model reads as busy, not as a broken key.

## 1.1.0

Fixes from the first run on a real application.

- **A dropdown is never handed back as a text box.** Options that load only when
  a control is touched are opened and read before anyone is asked, and a saved
  answer that matches one of them is chosen rather than asked about.
- **Actions run in the frame their control lives in.** Applications are very
  often inside one; every field in one used to come back missing.
- **Option labels no longer identify a dropdown.** A control that populated when
  opened changed fingerprint at that moment, so every action on it afterwards
  reported it as gone.
- **Today's date is filled, not asked**, in the shape the control asks for.
  "Date of Birth" is guarded off.
- **Buttons say when they are working and cannot be pressed twice.** Pressing
  Save with no feedback skipped four questions in a row.
- **The panel is rebuilt around one thing at a time.** The question owns the
  card, options are shown as options with the suggested one marked, and the
  checklist and activity log collapse behind summaries.
- The model can now suggest one of the page's own options for a question nothing
  saved covers. Its answer is checked against that same list before it is
  offered, and a suggestion is never filled in without being accepted.

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

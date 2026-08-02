# Changelog

Versions in `pyproject.toml`, `extension/manifest.json` and
`src/applypilot/__init__.py` move together, and a test asserts it.

## 1.38.0

- **The required tick list is finally asked about.** Last version asked the
  block's siblings for the marker. Where the block is a fieldset -- which is how
  the real page builds these -- the question is the block's own first child, so
  there was nothing beside it to find and the list stayed optional. A group is
  asked about both ways now. Checked against the live page rather than guessed
  at, which is also where I learned each box is tied to its label by for and id
  rather than by wrapping.

## 1.37.0

- **The required tick list is asked about.** Last version grouped it correctly
  into one question and then skipped it as optional: the marker belongs to the
  question above the whole list, which from any single box is one level further
  up than the marker search reaches. Required is asked of the list itself now,
  and of a group of buttons the same way.
- **"Please provide links to your GitHub, portfolio, demo, or AI projects" gets
  filled.** It is about GitHub and about a portfolio at once, so neither fact
  could claim it and it sat blank while every address it asked for was in your
  profile. Each saved address the question names is written out with what it is
  -- one per line in a textarea. Only what you entered, only what was asked for,
  and a box wanting a GitHub URL alone is still the GitHub field.

## 1.36.0

- **"Which of these have you used?" is one question.** A list of tick boxes was
  read as one question per box -- eight fields called OpenAI, Anthropic, Llama
  and so on, none of them answering to any saved fact and none carrying the
  requirement, which belongs to the question above them. So the whole list was
  left blank and never asked about. The boxes are its options now, ticking one
  is verified from the boxes themselves, and anything already ticked is left
  alone.
- A lone tick box is still its own question. A page whose every input happens to
  be a tick box has some ancestor holding all of them, and that ancestor is not
  a question.

## 1.35.0

- **Hugging Face actually appears in Settings.** It went into the catalogue last
  version but the answers grid on the options page is a hand-written list, so it
  showed up everywhere except where you would go to fill it in.
- **"Do you need a work visa?" is answered.** The sponsorship fact knew every
  phrasing containing the word sponsorship; one form asks it plainly without.
- **"By checking this box, you consent to..." is an agreement.** Only the first
  person was recognised, so a required consent box phrased at you rather than as
  you was left blank and never asked about.

## 1.34.0

- **A Hugging Face profile has somewhere to live.** Its own fact, alongside
  GitHub and your personal site, and it appears in Settings under Links like
  the others. A form asking for "Hugging Face profile" reaches it; one asking
  for GitHub still reaches GitHub.

## 1.33.0

- **A required marker drawn by CSS still counts.** The red asterisk on one
  applicant tracking system is not in the text at all -- the label reads "Have
  you used Node.js professionally?" and carries a class saying it is required.
  The marker search looked at text, found none, and every screening question on
  the form read as optional: left blank, never asked about. A neighbouring
  element whose class says required now counts as the marker.

## 1.32.0

- **Questions answered by pressing a button are questions now.** One widely
  used applicant tracking system draws every Yes/No as two bare buttons -- no
  role, no name, no value, only class names -- so a whole section of a form was
  invisible rather than unanswered. A row of buttons with short labels is a
  choice; pressing one is how it is answered; and what is chosen is read back
  from the page, by aria where the page says so and otherwise by the one class
  the chosen button carries that its siblings do not. Back beside Next is the
  same shape and is excluded by wording. Checked on the live page: all seven of
  its questions found, with their real wording and options.

## 1.31.0

- **The agreements switch saves, and lasts one session.** It had been added to
  the profile and to the options page but not to the settings endpoint, so it
  was dropped in transit both ways and unticked itself on save. It now goes
  through like every other preference &mdash; and deliberately lives in memory
  rather than on disk, so it switches itself off when the service restarts. A
  decision with legal weight is one you make when you sit down to apply, not one
  left running for months because of an afternoon's clicking. Nothing about it
  is written down.

## 1.30.0

- **A tick box is answered by ticking it.** It carries no options of its own, so
  it was going down the same path as a free-text field -- and an agreement came
  back as somewhere to type, which is not how anyone accepts an arbitration
  clause. Yes and No, as two things to press.
- **"Tick the agreements an application requires" is in Settings.** Off until
  you turn it on. On, agreements are accepted and the wording of each goes into
  the activity log, so there is a record of what was agreed to rather than a
  silent tick. Off, each one is handed back for you to read. The setting reaches
  agreements and nothing else -- a saved Yes from elsewhere in your profile has
  never been able to answer one of these and still cannot.

## 1.29.0

- **An agreement is asked, not skipped.** "I have read and agree to the terms of
  the Mutual Arbitration Agreement" matched no saved fact -- correctly, since
  what is being agreed to differs every time -- so it fell through to "optional"
  and was left unticked, and the step was refused with nothing explaining why.
  It now comes back as a question every time. It is never answered from a saved
  value, however much its wording resembles a Yes/No already on file.
- **Settings is three tabs instead of one long scroll.** About you, Settings,
  Your data. Which tab you were on survives a reload. Everything is tighter
  too: smaller type, less padding, less air between sections.

## 1.28.0

- **The "Other info" step asks its questions.** Two radio groups there thought
  the question they were asking was "I have an account Login I'm applying for
  the first time" -- the sign-in choice from the top of the page, hidden, four
  levels away. Looking for a group's question walked outward until it found any
  text at all, and that text carries no asterisk, so both were read as optional,
  left blank, continued past and refused. The question is now looked for inside
  the block where it lives, before anything walks outward; and text nobody can
  see is never a label. Checked on the live page: both now carry their real
  question and are correctly required.

## 1.27.0

- **A step that refuses to move on is read again, not given up on.** Several
  required questions say so nowhere a machine can see until Continue is pressed
  and refused -- that is the moment the form prints "Please select an option"
  against each of them. The rule for reading those was already there; it never
  got to run, because the panel pressed Continue, saw the page had not moved,
  announced it had stopped and returned without looking again. It looks now,
  while the complaints are on screen, and hands back what the form is asking
  for instead of saying nothing.

## 1.26.0

- **A question with options is asked with those options.** The veteran question
  was being handed back as a box to type into, and typing the exact wording of a
  radio button selects nothing at all -- which is why it kept failing however
  carefully it was typed. Whether a question is answered by choosing or by
  typing now follows from what the control is, not from whether its options
  happened to survive the trip; and if they did not, they are read from the
  control on the page.
- **Buttons are made of the surface rather than painted on it.** A solid block
  of colour is the one thing soft UI cannot absorb. A button is the same
  material, raised, with the accent carried by its lettering: depth says it can
  be pressed, colour says it is the one to press. Start keeps its fill, and only
  Start.

## 1.25.0

- **Light or dark, your choice.** Settings has a Theme control: follow the
  browser, or pin it. It applies to the panel as well, and changing it in one
  reaches the other without reopening either. With nothing chosen it follows the
  browser exactly as before. Kept in the browser's own storage rather than your
  profile -- it is a display preference, not something about you.

## 1.24.0

Measured on the live application rather than a fixture, which is the only reason
any of this was found.

- **Reading a page: 7530ms to 78ms.** Every part of a scan measured around a
  millisecond, yet a whole scan took seven and a half seconds. The tolerant
  block matching added in 1.15.0 was climbing to the top of the page and
  comparing every section against every other one. A control whose name states
  its entry number needs no walk at all now; where a walk is still needed it
  stops at any block holding more than a couple of dozen controls, and what a
  block asks is remembered for the length of one document walk.
- **A four-field fill on that page: 12839ms to 134ms.** Finding one control went
  from 416ms to 4ms, reading it back from 414ms to 1ms.
- **The veteran question is asked.** Its label there is "(VEVRAA) Veteran's
  Self-Identification Form" over three hundred characters of statute -- neither
  of which names a field -- while the control was called "veteran" all along. A
  label that answers to nothing gives way to the name.

## 1.23.0

- **The veteran question, read off the live page.** Its label there is not
  "Please identify your Veteran status" at all -- it is three hundred characters
  of VEVRAA statute, which names no field and matched nothing, while the
  control's own name said "veteran" plainly. A label that is prose rather than a
  name now gives way to the name, on the same narrow terms as a field with no
  label at all. The bar sits well above a sentence, so a long question that does
  name its subject is still read as a question.

## 1.22.0

- **The same question asked a different way gets the same answer.** A saved "25"
  now answers a form offering "18-24 / 25-35 / 36-50", and a saved GPA of 3.34
  answers "3.0-3.5". Ranges, "50+", "under 18" and "5 to 10 years" are all
  understood. The arithmetic is done deterministically rather than guessed at,
  only a label that is entirely a band counts -- "Building 25-35" is still a
  place -- and two bands that both contain the number is a tie, which is still a
  question rather than a coin flip.
- **The veteran question gets asked.** "Please identify your Veteran status" did
  not look like the veteran status field, because the request in front of it was
  being read as part of the name. A leading request is stripped and the label
  tried again, but only when the label as written matched nothing.
- **"Please select an option" works now.** The rule added in 1.17.0 never fired
  on the real page: it looked for a complaint by class name, and that form uses
  a plain red span. It reads the wording instead -- narrowly, because
  "*Please Check the box below:" is a label, not a complaint -- and stops
  looking at the first ancestor belonging to a different question.

## 1.21.0

- **Filling a page is 40x faster.** Measured on a form of thirty fields:
  **5122ms before, 120ms after**. None of it was where it looked.
  - A flat 120ms wait before every read-back, paid by every field, on pages that
    had already finished reacting. The page is read as soon as it has caught up
    now; only a genuinely slow one waits, and it still gets as long as it needs.
  - Finding a control meant searching the whole document, twice per field. Where
    a fingerprint was last found is remembered -- and re-derived from the live
    page before it is trusted, so a stale entry costs a slower lookup and never
    the wrong control.
  - Two messages per field, one of them only asking whether the tab was visible.
    A page's actions make one trip now, grouped by frame.
- Nothing about what "verified" means changed. Actions still run one at a time
  in the planned order, and every result is still the page's own state read back
  afterwards. `scripts/bench_fill.py` re-runs the measurement.

## 1.20.0

- **Soft UI.** Both the panel and Settings sit on a single colour with no
  borders anywhere. Depth comes from one light source at the top left, and it
  carries meaning rather than decoration: raised means press me, sunken means
  fill me in. The question being asked is the thing standing highest off the
  surface; an answer you have picked stays pressed in.
- Text keeps full contrast throughout, and every state that depth signals is
  also carried by colour and weight -- soft UI is a way of shaping surfaces, and
  it must not become the reason something cannot be read.

## 1.19.0

- **The race question stops coming back.** A form that asks "Are you Hispanic or
  Latino?" and "Race category" separately was answering both from one saved
  value: picking a race wrote "Asian" where a Yes/No belonged, then answering
  the Yes/No wrote "No" over the race -- so each answer made the other question
  wrong again, however many times either was answered. Two questions, two facts.
  A combined "Race / Ethnicity" question still works as one.

## 1.18.0

- **The panel and Settings look like something a person designed.** Space
  instead of boxes inside boxes, body text at a readable size, one accent colour
  used only where something is the main action or a warning, and the question
  being asked is the only thing on screen with a border. The activity list reads
  as a transcript rather than a wall of coloured blocks. Both follow the
  browser's own light or dark setting.
- **A question that appears because of your answer gets asked.** Answering one
  EEO question adds another below it; the list had been captured before the
  answer went in, so the new one was never in it and the step was continued past
  with a required field blank. An answer that goes onto the page is now followed
  by a fresh look at it.

## 1.17.0

- **A step is not finished while the form is still asking for things.** Some
  required questions say so nowhere a machine can see: no attribute, and the
  asterisk sits in a paragraph above the buttons rather than on a label of their
  own. They were read as optional, left blank, continued past and rejected --
  with nothing in the panel to answer. A form saying "Please select an option"
  about a control now counts as the strongest evidence there is that it is
  required, and those questions come back to you.
- An agreement is still never ticked on your behalf. It is asked.
- **"The page did not answer in time (highlight)" is gone.** Scrolling to a
  field shared the deadline for real work; it is a courtesy now, with a short
  deadline and no complaint when it does not land.

## 1.16.0

- **The next step gets worked on.** Two things stopped it. The panel sampled the
  new page once, immediately after pressing Continue, decided it had not changed
  and stopped driving -- and the step then arrived to a panel with nothing
  behind it. And the stall guard counted every look at a page, while filling one
  plans it several times over by design, so every page declared itself stuck on
  the third look. Continuing now waits for the page to actually become a
  different page, and only an attempt to move on counts towards the guard.
- **The panel no longer slows the page down while idle.** It scanned every frame
  of the application every two and a half seconds for as long as it was open. It
  asks a cheap question first now and scans only when something has moved.
- **Nothing spins forever.** Every request to the page has a deadline and says
  what timed out, instead of leaving Start going round and round.

## 1.15.0

- **Every education and every job gets its own entry, with its own record.**
  The first entry of a repeating block carries something the others do not --
  "This is my most recent education" -- and later ones carry a remove button the
  first lacks, so comparing blocks for an exact match found no twins at all.
  Every entry then reported itself as the first one, which meant the same school
  was filled into all of them, and the count of entries never rose, so adding
  announced it had failed while entries appeared on screen. The entry number
  stated in a control's own name is believed first now, and blocks that ask
  mostly the same questions count as repeats. However many records are on file,
  that many entries get made and each takes its own.
- **The extension no longer slows the page down.** Waiting for something to
  happen meant asking every sixty milliseconds -- two hundred walks of the whole
  document over a twelve-second wait, one of them a full page scan each time.
  Polling eases off the longer it waits, and nothing on a loop scans any more.
- **Texas is not tried against an empty list.** A choice with nothing real on
  offer yet goes last, so Country is set before State is reached. Nothing in the
  rule knows what a State is.

## 1.14.0

- **"Back Next" is gone.** The row at the foot of a form holds two buttons, and
  read as one element it says "Back Next". That was being offered as the way
  onward and then could not be pressed, because nothing on the page is called
  that. An element with a control inside it is a container now, not a control.
- **Adding another education or work entry works.** Two things were wrong.
  Scanning looked at every kind of element -- a real application uses a bare
  span for "+ Add other education" -- while pressing looked only at buttons and
  links, so a control the panel had just listed came back as missing. And the
  check for whether an entry appeared waited three seconds and counted only
  fields already drawn, so a slow application looked like a click that had done
  nothing. One list of controls for both, every field counted whether drawn or
  not, and a page that fetches gets time to answer.
- Gemini 3.5 Flash-Lite is the default model, and the name is editable in
  Settings.

## 1.13.0

- **Filling is fast again.** The five injected files were being fetched and
  evaluated before *every single action*, so each field carried the cost of
  loading the whole toolkit. A tab is injected once now and remembered until it
  navigates.
- **Switching tabs no longer breaks the run.** A hidden tab stops laying itself
  out, so every control measured as invisible and every action came back "the
  control is no longer on the page". Work waits for the page to be on screen and
  says so.
- **"Add other education" presses once.** Dispatching a click *and* calling
  click() ran the handler twice and added two entries.
- The model name is settable in Settings, so any model your key can reach will
  do. A small fast one is the right choice: the model is only ever asked to
  suggest an option a form already offers.

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

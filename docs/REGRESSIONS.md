# Regressions

Every entry here happened on a real application. Each one names the mistake, the
general mechanism that prevents it, and the test that would catch it coming
back. None of the fixes names an employer, a question or one system's DOM.

Numbering is stable. Tests refer to these numbers.

---

## Wrong data into the wrong field

**1. A short answer claimed a long question.**
A saved *Country → United States* answered *"…require visa sponsorship to work
in the country in which this role is based?"*

*Mechanism.* When a label mentions several subjects, the most specific one owns
it. Subject words are ranked, and only a fact owning a top-ranked word may
answer. "Sponsorship" outranks "country" in any sentence containing both.
Matching is on word boundaries throughout, never bare substring.
→ `test_mapper_regressions.py::test_country_does_not_answer_a_sponsorship_question`

**2. A State field named `countryRegion` was filled with a country.**
*Mechanism.* Only the **visible label** is reasoned about. A control's `name`,
`id` and `placeholder` are used only when there is no visible label at all, and
then only on an exact alias match with a visible confidence penalty.
→ `test_visible_label_beats_the_controls_own_name`

**3. Work history claimed any label containing "company", "position" or
"degree".** A sponsorship question answered "HCLTech"; a non-compete question
answered with a past employer; *"Do you have a Bachelor's degree?"* answered
"M.S."
*Mechanism.* History facts resolve only inside an education or employment block,
or behind a label that can mean nothing else ("School", "Field of Study",
"Employer"). Outside a block they never answer a sentence question.
→ `test_history_never_answers_a_sentence_question`, `test_company_outside_a_history_block_is_not_filled`

**4. "Position Location", a search filter, was filled with a job title.**
*Mechanism.* An alias must line up with the whole label: as the label, as its
opening followed by a connector, or as its ending behind nothing but filler.
"Position" opens "Position Location" but the next word is a new subject, not a
qualifier. (A search page also offers no fields at all — see 23.)
→ `test_position_location_is_not_a_job_title`

**5. "United States" selected "United States Minor Outlying Islands".**
*Mechanism.* Options are ranked by closeness, with an exact match beating every
containment match and a length-gap ceiling above which containment is refused
outright. A tie for first place is a question, not a coin toss.
→ `test_united_states_does_not_select_minor_outlying_islands`

**6. "Address Line 1" filled "Address Line 2".**
*Mechanism.* Digits are never stripped in normalisation, and a mismatched
trailing number is a hard reject.
→ `test_address_line_1_and_2_are_different_fields`

**7. "If yes, what department and what country?" was filled with a country.**
*Mechanism.* A label opening with a conditional phrase is never answered from a
general fact. An answer given to that exact question before is still used — see 16.
→ `test_conditional_follow_up_is_not_answered_from_a_general_fact`

**8. A dropdown's own "No Selection" row was chosen as an answer.**
*Mechanism.* Placeholder-shaped rows are removed before ranking and can never be
learned or verified as a desired value.
→ `test_placeholder_rows_are_never_selected`

**9. Rubbish was learned and written into later applications.**
Employer option ids (`Country → 28468`), placeholders (`- Select -`), page
furniture (`Current Date`, a language selector) and one mis-scan
(`Email Address: → Notification:`).
*Mechanism.* A hygiene gate: a readable question, a readable value, and a
control where the value means what it appears to. Bare numbers are refused
except where digits are the answer (phone, postcode); a value matching another
label on the page is refused; a value a choice control does not offer is refused.
→ `test_learning.py` (whole file)

---

## False verification

**10. A combobox's own filter text was read back as proof of a selection** — and
it overwrote the failure already recorded for that field.
*Mechanism.* A combobox's text box is excluded from verification signals, and any
box the executor typed into is marked so it can never be read back. Separately, a
recorded failure is only ever replaced by a `verified` result carrying an
authoritative signal.
→ `test_browser_injected.py::test_a_combobox_that_never_commits_is_not_reported_as_verified`,
`test_runloop_and_chat.py::test_a_failure_survives_an_unverifiable_success`

**11. A dropdown with no popup reported 27 "options"** scraped from the whole
document — a salary chip, unrelated Yes/No buttons, the EEO race list.
*Mechanism.* Options come only from a list the control points at or owns. No
owned popup means no options, reported as such.
→ `test_a_control_with_no_popup_of_its_own_reports_no_options`

**12. Sign-in reported success because a password field was non-empty** — a
password the applicant had typed themselves.
*Mechanism.* The only evidence of a sign-in is the sign-in form no longer being
on the page.
→ `act.js::signInSettled`, `test_service.py` sign-in checks

---

## Getting stuck

**13. Selecting Country rebuilt the address block and discarded fields filled
seconds earlier;** the run reported them empty.
*Mechanism.* Every action is idempotent — anything already holding the value is
left alone — so the page can be re-planned and re-filled without the retry
undoing its own work. Identity survives the rebuild because a fingerprint is
built from label, kind, options and repeat block, never from position.
→ `test_a_rebuild_clears_earlier_work_and_refilling_is_verified`

**14. "The observed page has not changed" looped forever** because the guard
reset on resume.
*Mechanism.* The stall guard lives in the saved run. Resuming does not clear it;
only the page actually changing, or the applicant stepping in, does.
→ `test_resuming_does_not_hand_a_stuck_run_fresh_retries`

**15. Short questions could never match**, so the same field was asked about
forever. The matcher discarded labels under six characters and compared against
a combined "label name" string.
*Mechanism.* No length filter anywhere, and comparison against the visible label
alone.
→ `test_short_labels_resolve`

**16. Making "If yes…" fields conditional skipped all mapping**, including a
saved answer, so answering one never satisfied it.
*Mechanism.* Answers given to that exact question are looked up *before* the
conditional gate.
→ `test_conditional_follow_up_uses_an_answer_given_to_that_exact_question`

**17. The questionnaire wrote nothing until every question was answered**, so
every field stayed empty and was asked about again.
*Mechanism.* Answers go onto the page as they are resolved.
→ `test_answers_are_planned_even_when_other_questions_are_outstanding`

---

## Misreading pages

**18. The invisible reCAPTCHA badge was treated as a challenge**, blocking every
application on every site carrying one.
*Mechanism.* A badge is a badge. Only an on-screen checkbox or puzzle counts as
a challenge, and neither is ever solved.
→ `test_the_invisible_recaptcha_badge_is_not_a_challenge`

**19. An application at `.../postLogin.html` was detected as a sign-in page.**
*Mechanism.* Page kind is decided from the controls present. Never the URL.
→ `test_an_application_served_from_a_post_login_url_is_an_application`

**20. A two-step sign-in in a shadow root, asking for a User ID with no password
field, was mistaken for an application form.**
*Mechanism.* Traversal pierces shadow roots. A page with a username-shaped field,
a sign-in button, and almost nothing else to fill in is a sign-in.
→ `test_a_two_step_sign_in_inside_a_shadow_root_is_detected`

**21. An account-registration page was treated as a sign-in**, stalling on a
password manager for an account that did not exist.
*Mechanism.* Two password fields, or a password field labelled "Choose"/"Retype"/
"Confirm", makes it a registration. Everything except the credentials is filled.
→ `test_an_account_registration_page_is_not_a_sign_in`

**22. A model was asked whether a listing "belonged to the expected employer",
said no — correctly — and the runner halted.**
*Mechanism.* Host identity is decided from the URL. A recognised hiring system is
the employer; a recognised board is where a search starts; only an unknown host
is worth stopping on. A model describes a page and never decides to stop.
→ `test_routing.py::test_a_listing_on_a_board_never_stops_the_run`

**23. Search pages were scanned as forms** — 22 phantom fields from one board's
filters, 11 from another's, 5 from a third's subscribe box.
*Mechanism.* A list of jobs offers no fields at all. Posting links are counted
even when the path says nothing about jobs, so a board linking to
`/company/<uuid>` is still recognised as a list.
→ `test_a_search_results_page_offers_no_fields`, `test_a_board_linking_to_opaque_urls_still_reads_as_a_list`

**24. Company discovery matched a Greek subsidiary** sharing the first word of
its parent's name, beating the listing's own Apply link.
*Mechanism.* Routes are scored by origin. The posting's own apply control always
wins; a board match on the company alone is below the threshold to follow at all;
a URL assembled from a pattern is a last resort, because a hand-built apply
endpoint redirects to a careers home page often enough to matter.
→ `test_a_company_only_board_match_never_beats_the_listings_own_apply_link`

---

## Asking too much, asking too little

**25. Optional fields were excluded entirely**, so School, Degree, Field of Study
and Location were neither filled nor asked about — silently dropped.

**26. Then including every optional blank** turned a 13-question form into 30,
asking for Middle Name, Home Phone, Phone Extension and County.

*Mechanism for both.* Anything required is always asked. Anything optional is
filled if the profile can fill it, and left blank if it cannot. Supplementary
extras stay blank and never become questions, but they do appear in the
checklist as skipped, so nothing is invisible.
→ `test_optional_fields_that_the_profile_can_fill_are_filled`,
`test_optional_decoration_is_left_blank_rather_than_asked`

---

## Found while building this

**27. A board's filter controls became its questions** because its postings link
to opaque paths. Same shape as 23; fixed by the same mechanism, found on a live
site rather than in a fixture.

**28. A tab bar four levels above a file input was read as its label.**
*Mechanism.* The walk for a nearby label stops as soon as it meets navigation or
a run of links, and is bounded to three levels. Section detection is bounded
too, because the section is what decides whether a history record may answer.

**29. Value vocabulary collided across subjects.** Pooling synonyms made `MS`
mean Mississippi to an education field and Master's to an address field,
whichever loaded last.
*Mechanism.* Synonyms are grouped by subject and unlocked by the fact being
answered. States are only in play for a state; degrees only for a degree.

---

## Found on a real application

**30. A dropdown was handed back as a text box.** A required select whose
options load only when it is touched looked, to a scan, like a choice with no
choices — so the panel asked the applicant to type the answer to a dropdown.
*Mechanism.* A choice control with fewer than two usable options is marked as
needing its options opened. The panel opens it, reads what it owns, and only
then asks — and if a saved answer matches one of them, it does not ask at all.
Native selects are touched to populate before being read, and before being
chosen from.
→ `test_lazy_dropdowns.py::test_such_a_question_is_flagged_as_needing_its_options_opened`

**31. The applicant was asked for today's date.**
*Mechanism.* Facts may be computed rather than stored. The current date is
written in the shape the control asks for, read off its own placeholder. "Date
of Birth" is guarded off by the birth modifier, and "Start Date" and "End Date"
by their own leading words.
→ `test_the_current_date_is_filled_not_asked`, `test_a_date_of_birth_is_never_filled_with_today`

**32. Option labels in a fingerprint made identity unstable.** A dropdown that
populated when opened changed fingerprint at that moment, so every action on it
afterwards reported the control as gone.
*Mechanism.* Option labels identify a radio group, whose buttons are all present
from the start. They no longer identify a dropdown.
→ `test_a_saved_answer_matching_an_opened_option_is_chosen_not_asked`

**33. Actions only ever ran in the top frame.** Applications are very often
inside a frame; every field in one came back as missing, or matched something
else that happened to be up top.
*Mechanism.* Each field reports its frame, and each action runs in it. Controls
named by their text are tried across every frame.

**34. Pressing Save gave no sign it had worked, so it got pressed again** — and
each press advanced past a question. Four went by unanswered.
*Mechanism.* Every control shows that it is working and cannot be pressed while
it is. A question only advances after the value is actually on the page, and a
failed fill keeps the question up with the reason.

**35. Two copies of a date hint produced a backwards date.** `MM/DD/YYYY` joined
to itself contains "yyyy mm/dd", which matched the ISO pattern.
*Mechanism.* Each hint is tested on its own.

**36. Every field on a form came back labelled `*`.** The required marker sits
in its own element between the field name and the control, so the nearest thing
before each input was a lone asterisk. Nothing matched any saved answer and the
panel reported there was nothing it could fill, on a form asking for a first
name, an email and an address.
*Mechanism.* Text that is only a required marker is skipped by every label
strategy, and the walk carries on past it. Because the asterisk was also the
only thing saying a field was required, that signal is now looked for
separately, among the short decorative elements sitting beside the control.
A label that normalises to nothing falls back to the control's own attributes.
→ `test_asterisk_labels.py::test_a_required_marker_is_not_read_as_the_field_name`

**37. A dependent dropdown was offered as a question with no answers.** State
holds nothing but "Choose" until a country is picked.
*Mechanism.* Placeholder rows never reach a question, so such a control has no
options and is marked as needing them opened rather than asked about. It fills
on the next pass, once the field it depends on is in.
→ `test_state_becomes_answerable_once_country_is_chosen`

**38. A slashed label named the field twice and matched neither.**
"School / education institution" is a school and it is an educational
institution; read as one phrase it is neither, so the field stayed empty on a
form that had the school in the profile all along.
*Mechanism.* A slash with spaces around it joins two whole phrases, and each
side is tried as a reading of the label. A slash without spaces keeps the older
word-level behaviour, so "Country/Region of Residence" still resolves.
→ `test_asterisk_labels.py::test_a_spaced_slash_label_resolves_from_either_side`

**39. Answering a history question did not stop it being asked.** A key such as
`education.gpa` was saved into the flat set of facts, where nothing reads it.
*Mechanism.* A history key is written into the record it belongs to, chosen by
which entry of the repeating block the field was in.

**40. Three fields all labelled "GPA", with nothing to tell them apart.**
*Mechanism.* A field in a repeating block reports which entry it is, and the
question and the report both show it. Required markers are stripped from what is
displayed, so a label reads as a question rather than as "*GPA *".

**41. Setup stalled on "Middle name" while work authorisation was unanswered.**
*Mechanism.* The next question asked is the first that is not optional. Optional
ones are only offered once everything that matters is done.

**42. The page set a field itself, after ours, and the wrong value stood.**
Choosing a country made a form pick the first state in its list. A saved Texas
came out as Alabama, and nothing reported it, because the re-fill pass only
looked at fields that had been verified and then lost -- not at fields the page
had filled in with something else of its own accord.
*Mechanism.* After filling, the page is re-read and anything not holding what
was asked for is set again, for up to three further passes. Filling is
idempotent, so a pass that finds nothing wrong costs nothing, and the panel says
which fields the page changed.
→ `test_asterisk_labels.py::test_a_field_the_page_sets_for_itself_is_corrected_on_the_next_pass`

**43. A section heading that is not a heading tag.** A form styled "Education"
and "Work experience" as coloured divs. Reading only h1-h5 found no section, so
every education and employment field was blocked from resolving on a page whose
answers were all in the profile already.
*Mechanism.* A plain block counts as a heading once the walk is above a
container holding several fields. Below that, the short text before a control is
that control's own label, not a section name.
→ `test_styled_headings.py::test_a_styled_div_is_recognised_as_the_section_heading`

**44. A history record answered in the wrong kind of block.** "Start year" fitted
an education entry and a job equally well, and an even fit is refused, so a
field with an obvious answer came back as a question.
*Mechanism.* Education records answer in education blocks and employment records
in employment blocks; the heading says which.

**45. A generic word owned by a specific fact blocked two others.** The
notice-period question owned "start", which is the ordinary word in "Start date"
and "Start year", so neither history start date could ever resolve.
*Mechanism.* Only words that dominate a label are owned. "start" is not one.

**46. Questions from steps that were not on screen.** A wizard keeps every step
in the document and shows one at a time. The check for a styled control returned
true outright instead of going on to look at whether any ancestor was hidden, so
every checkbox and radio in the document counted as visible. The panel offered a
veteran form and a login choice from steps that were not showing, while the text
fields on the step that *was* showing were correctly judged hidden and left out
-- a page of questions from nowhere, and nothing filled.
*Mechanism.* A checkbox, radio or file input drawn as a 1px transparent control
is measured by the box drawn for it, and then the ancestor checks still run. Not
being on screen is not something a control type can exempt itself from.
→ `test_hidden_steps.py::test_only_the_step_on_screen_is_offered`

**47. A picker searching a remote list reported the answer missing.** The school
field said `"University of North Texas" is not among the options this control
opened`, while typing the same thing by hand found it every time.
*Mechanism.* Three things. Setting the whole value at once and firing one input
event is enough for a widget filtering a list it already holds and not for one
running a search per keystroke, so each character now gets the events a real key
press produces. A list that has opened is not a list with anything in it -- this
one opens saying "Please enter 1 or more characters", and returning as soon as
that appeared meant the filter was never typed. And the result was read a
fraction of a second later, before the search had come back; it is now waited
for. When the answer really is absent, the failure says what was on offer.
→ `test_async_picker.py::test_opening_with_the_answer_typed_finds_it`

**48. A widget's own value became the field's label.** The same picker renders
the chosen school immediately before its input, so the search for a nearby label
walked straight into it. The control's identity changed the moment anything was
selected, and every action afterwards reported it as no longer on the page --
the selection had worked, the control had simply stopped being findable.
*Mechanism.* A widget's own furniture -- its value display, placeholder, arrow,
menu -- is skipped when looking for a label.
→ `test_async_picker.py::test_choosing_from_it_is_verified_from_the_pages_own_state`

**49. A dropdown hung off <body> could never be found.** The school picker keeps
a hidden select with no options at all for its value, shows a span with
role="combobox", and appends its dropdown -- search box inside it -- to the end
of the document. Looking for a control's list inside that control found nothing,
so the field could never be filled, and there was nothing to type into because
the search box did not exist until the list opened somewhere else.
*Mechanism.* A control that says it is expanded, with exactly one open list on
the page, owns that list. Both halves must hold, so regression 11 stands: a
control that is not open still owns nothing. The filter box is looked for in the
dropdown and in the dropdown's own container, because it usually sits beside the
results rather than inside them.
→ `test_detached_dropdown.py::test_a_dropdown_hung_off_the_body_is_still_this_controls_own`

**50. A name in bracket notation matched nothing.** `custom[eeo][race]` is a
question about race and `custom[education][0][school]` is a school, but read
whole they are neither.
*Mechanism.* The last meaningful bracketed segment is used, indices skipped.

**51. A field labelled with a bare asterisk took the label of the field above
it** and answered as that field.
*Mechanism.* A label belongs to a field's own row. A neighbour holding a control
of its own is another field's row, and once the walk reaches a container with
several visible controls it has left the row entirely. A widget's own hidden
backing input is part of one field, not a second one.

**52. A widget showing the field's own name in its value box was read as having
that value.** "School / education institution" came back as the chosen school.
*Mechanism.* A rendered value equal to the control's own label is a placeholder.

**53. The page watcher fought the fill and nothing finished.** Filling a form
changes the page, and the watcher added to notice *someone else* changing it
reacted to our own work: it re-planned on top of a fill in progress, over and
over, so no field was ever completed and the panel sat there looking busy.
*Mechanism.* Everything the panel initiates is counted as work in flight, and
the watcher does nothing while any of it is. It also waits for the page to hold
the same shape across two checks before acting, and ignores a page it has
already planned against. A watcher that cannot tell its own effects from the
world's is worse than no watcher.

**54. The search box was two levels above where it was looked for.** A dropdown
is laid out `[search] [results [list]]`. Walking up from the list one level
reached the results wrapper, not the dropdown, so a picker that types perfectly
well was never typed into at all -- and the answer was reported missing from a
list that had never been searched. Confirmed against the live control: the old
rule found nothing, the new one finds the box at the third level up.
*Mechanism.* The walk from the list goes up to four levels, stopping at body.
→ `test_detached_dropdown.py::test_the_search_box_is_found_several_levels_above_the_results`

**55. "+ Add other education" is a bare span.** No role, no href, no button. The
search for clickable controls looked only at buttons, links and role=button, so
there was nothing to press and the extra entries were never added.
*Mechanism.* Any visible element whose own text matches is a candidate, and only
the innermost element carrying that text counts, so a wrapper does not answer to
it as well.

**56. The résumé upload is a file input that is display:none.** It sits behind a
styled dropzone, which is the whole pattern, and the scan skipped it as hidden --
so there was never a file control to attach anything to.
*Mechanism.* A file input hidden outright still counts when something visible
wraps it. Attaching to it is how the widget is meant to work, and the attachment
is still verified from the input's own file list afterwards.

**57. A dependent field could never be answered, however many times it was
retried.** State holds nothing but "Choose" until a Country is chosen, and the
page then picks the first state in the list for you. Retrying State was useless:
the answer did not exist yet.
*Mechanism.* After any choice is made, the page is read again and the fields
that now have options are filled. Correcting a value is not the same as waiting
for it to become answerable.

**58. One page took ten minutes.** Every control was given six seconds to come
back from a search, including controls with nothing to type into, and a control
that had already refused a value was asked for it again on every pass. With the
auto-continue loop repeating the whole cycle, the waits added up.
*Mechanism.* A control with no filter box is not waited on, and a value a
control has already refused is not offered to it again in the same run.

**59. The resume was asked for as a line of text to type.** It is a document; it
is uploaded in Settings.
*Mechanism.* It is no longer a setup question.

**60. Every action reloaded the whole toolkit.** The five injected files were
fetched and evaluated before each individual action, so filling one field
carried the cost of loading everything, and a form took minutes.
*Mechanism.* A tab is injected once and remembered until it navigates.

**61. A background tab reported every control as gone.** A hidden tab stops
laying itself out, so everything measures as invisible and every action comes
back "the control is no longer on the page" -- a screenful of them on switching
windows.
*Mechanism.* Work waits for the page to be on screen and says so, rather than
failing against a page nobody is looking at.

**62. A click that fired twice added two entries.** Dispatching a click event
*and* calling click() ran the handler once each.
*Mechanism.* One click: the native call when it exists, a dispatched event when
it does not.

**63. The row at the foot of a form was offered as the way onward.** A
container holding Back and Next reads, as one element, "Back Next" -- and that
was offered as the next step, then could not be pressed, because no control on
the page is called that.
*Mechanism.* An element with a control inside it is a container, not a control,
and is skipped in favour of the control.

**64. A control the panel had just listed could not be pressed.** Scanning
looked at every kind of element, because a real application uses a bare span for
"+ Add other education"; pressing looked at buttons and links only. The two
disagreed and the answer was "no control on this page reads that".
*Mechanism.* One list of controls, used by both.

**65. An entry that arrived slowly was reported as never added.** The wait was
three seconds and counted only controls already drawn, so an application that
renders a new entry from the server -- or renders it collapsed -- looked like a
click that had done nothing, and adding stopped.
*Mechanism.* Every field in the page counts, drawn or not, and a page that
fetches gets time to answer.

**66. Every entry of a list reported itself as the first one.** The first entry
of a repeating block carries something the others do not -- "This is my most
recent education" -- and later ones carry a remove button the first lacks.
Comparing blocks for an exact match found no twins anywhere.
*Mechanism.* The index the page states in a control's own name is believed
first; structure is the fallback, and blocks that ask mostly the same questions
are repeats of each other.

**67. The same school was filled into every education entry.** A consequence of
66: with every entry numbered zero, every entry took the first record on file.
*Mechanism.* Covered by 66's test, which asserts the second entry takes the
second record and a third takes the third.

**68. Adding stopped after announcing it had failed, while entries appeared.**
Also a consequence of 66: the count of entries never rose, whatever was added.
*Mechanism.* Covered by 66's test.

**69. The extension made the page slow, and it was blamed on the site.** A
predicate asked every sixty milliseconds for twelve seconds is two hundred walks
of the whole document, and one of them ran a full page scan each time.
*Mechanism.* Polling eases off the longer it waits, and no poll runs a scan: a
cheap reading of the page's shape says whether anything moved.

**70. Texas was tried three times against a list holding only "Choose".** The
State list does not exist until a Country is picked.
*Mechanism.* A choice offering nothing usable yet goes last, so everything that
can be answered is answered first. Nothing in the rule knows what a State is.

**71. Every page declared itself stuck on the third look.** The stall guard
counted observations, and filling a page plans it several times over by design:
once at the start, again after every choice, and again on each correction pass.
Three of those and the run was blocked -- which is how it reached a new step,
announced it had stopped, and then sat on a plan it would not act on.
*Mechanism.* Only an attempt to move the page on counts towards the guard.

**72. The panel made the page slow while doing nothing at all.** The watcher
scanned every frame of the application every two and a half seconds for as long
as the panel was open.
*Mechanism.* A cheap reading of the page answers "has anything moved?"; a full
scan happens only when it has.

**73. A reply that never came left a button spinning for minutes.** Nothing
asked of the page had a deadline, so one lost answer meant reloading the
extension.
*Mechanism.* Every request to the page has a deadline and says what timed out.

**74. Continuing sampled the next step once, immediately, and gave up.** The
click knows the page moved, but the new step's fields can still be on their way.
The panel declared the page stuck and stopped driving, and the next step then
arrived to an empty panel -- "it did go to the next page but it's not doing
anything".
*Mechanism.* Wait for the page to actually become a different page.

**75. A whole step read as optional, so nothing was asked.** Three required
questions carried no `required` attribute, no aria-required, and their asterisk
sat in a paragraph above the buttons rather than on a label of their own. They
were left blank, continued past, and rejected by the form -- with nothing in the
panel to answer, because nothing knew anything was missing.
*Mechanism.* A form saying "Please select an option" about a control is the
strongest evidence there is that the control is required, and it outranks any
label decoration claiming otherwise.

**76. Scrolling to a field could fail the run.** Highlighting shared the
deadline for real work, so a slow page filled the activity list with "the page
did not answer in time (highlight)".
*Mechanism.* Showing someone where a field is is a courtesy: short deadline, and
its failure is never reported.

**77. A new required question appeared and nobody was ever asked it.** Answering
one EEO question adds another below it. The list of questions was captured
before the answer went in, so the new one was never in it, and the step was
continued past with a required field unanswered.
*Mechanism.* An answer that goes onto the page is followed by a fresh look at
it, and a new plan if the page is no longer the same page.

**78. Two EEO questions shared one saved answer, so both were asked forever.**
A form asks "Are you Hispanic or Latino?" and "Race category" separately, and
one fact owned both. Picking a race wrote "Asian" where a Yes/No belonged;
answering the Yes/No wrote "No" over the race. Each answer made the other
question wrong again, however many times either was answered.
*Mechanism.* Two questions, two facts. A combined "Race / Ethnicity" question,
which plenty of forms still ask, stays with race.

**79. Filling a page was slow, and none of it was where it looked.** Measured on
a form of thirty fields: 5.1 seconds, 175ms per field. Three causes, in the
order they mattered.
*A flat wait before every read-back.* 120ms, paid thirty times, on pages that
had almost always finished reacting immediately. Now the page is read as soon as
it has caught up, and only a page that is genuinely slow waits.
*A whole document search to find each control.* Classifying the page and
building an observation for every control on it, twice per field. Where a
fingerprint was last found is remembered -- and the remembered element's
fingerprint is worked out again before it is used, so a stale entry can only
cost a slower lookup, never the wrong control.
*Two messages per field.* One asking whether the tab was on screen, one doing
the work. A page's actions now make one trip, grouped by frame, still in the
planned order, still each verified from the page's own state.
Measured after: 5122ms to 120ms. `scripts/bench_fill.py` re-runs it.

**80. The same fact, asked at a different resolution, was asked again.** A saved
"25" met a form offering "18-24 / 25-35 / 36-50" and matched nothing, so a
question already answered came back.
*Mechanism.* A saved number selects the band that contains it -- ranges, "50+",
"under 18", "5 to 10 years". The arithmetic is done deterministically, not
guessed at, and only a label that is entirely a band counts, so "Building 25-35"
is still a place. Two bands both containing the number is a tie, and a tie is
still a question.

**81. A whole self-identification section went unasked.** "Please identify your
Veteran status" did not look like the veteran status field, because the request
in front of it was being read as part of the name.
*Mechanism.* A leading request phrase is stripped and the label tried again --
only when the label as written matched nothing, so a field genuinely called
"Select" is unaffected.

**82. Every field on a step looked required.** The rule added for 75 read
"*Please Check the box below:" -- a label -- as a form complaining. And the
search for a complaint climbed blindly, so one red line anywhere above a group
marked all of it.
*Mechanism.* The wording is narrow: a complaint says what is missing, not what
to do. And the search stops at the first ancestor holding a control that belongs
to a different question.

**83. A label that is a paragraph, not a name.** Read off the live page: the
veteran radios on one real application are labelled with three hundred
characters of VEVRAA statute, which names no field and matched nothing -- while
the control's own name said "veteran" plainly. The whole self-identification
section went unasked.
*Mechanism.* Prose that answers to nothing is worth less than a name, so the
name gets its turn on the same narrow terms as a field with no label at all. The
bar sits well above a sentence, so a long question that does name its subject is
still read as a question.

**84. Reading a page took seven and a half seconds, and it was my own doing.**
Measured on the live application, not a fixture. Every part a scan uses was
around a millisecond, yet finding one control took 416ms and a whole scan 7530ms.
The tolerant twin matching added for 66 climbed to the top of the page and
compared every sibling section against every other, recomputing what each one
asks each time.
*Mechanism.* A control whose name states its entry number needs no walk at all.
Where a walk is still needed it stops at any block holding more than a couple of
dozen controls -- a repeating entry is a handful of questions, not a page -- and
what a block asks is remembered for the length of one document walk.
Measured on the live page: scan 7530ms to 78ms, lookup 416ms to 4ms, read-back
414ms to 1ms, and a four-field fill 12839ms to 134ms.

**85. A control's own name was ignored when its label meant nothing.** Read off
the live page: the veteran radios are headed "(VEVRAA) Veteran's
Self-Identification Form" and labelled with three hundred characters of statute.
Neither is the name of a field, both matched nothing, and the question went
unasked -- while the control was called "veteran" the whole time.
*Mechanism.* A label that answers to nothing is telling us nothing, so the name
gets its turn on the same narrow terms a field with no label at all gets: an
exact hit only, with the confidence penalty that goes with it.

**86. A five-option question was handed back as a box to type into.** Whether a
question was answered by choosing or by typing was decided by whether options
happened to be present on the object, not by what the control is. Anything that
emptied that list silently turned a radio group into free text -- and typing the
exact wording of a radio button selects nothing at all, so the answer failed
with "that did not go onto the page" however carefully it was typed.
*Mechanism.* What a control is decides how it is answered. A choice control is
answered by choosing, and if its options did not arrive with the question they
are read from the control on the page rather than giving up and offering a box.

**87. The one moment a form says what it wanted was thrown away.** Several
required questions say so nowhere a machine can see until Continue is pressed
and refused -- that is when the form prints "Please select an option" against
each of them. Read off the live page: before Continue those elements are
display:none, so a scan taken beforehand is right to call the fields optional.
The run pressed Continue, saw the page had not moved, announced it had stopped,
and returned without looking again -- so the complaints appeared on screen, were
never read, and three required questions stayed unasked and invisible.
*Mechanism.* A Continue that does not move the page on is followed by a fresh
look and a fresh plan, because that is exactly when the page has stated its
case. What it asks for is then handed back to be answered.

**88. A question two radio groups were asking turned out to be the sign-in
choice from the top of the page.** Read off the live application. Looking for a
radio group's question walked outward four levels through previous siblings, and
on that page it reached past the question entirely and came back with "I have an
account Login I'm applying for the first time". That text carries no asterisk,
so both groups were read as optional, left blank, continued past and refused --
which is the whole of "it is not asking me questions to fill them".
*Mechanism.* The question is looked for inside the block, above the buttons,
where it actually lives, before anything walks outward at all; and text nobody
can see is never a label, which is what let a hidden sign-in prompt become one.

**89. An agreement was silently left blank.** Nothing in the fact catalogue
answers "I have read and agree to the terms of the Mutual Arbitration
Agreement", and nothing should -- what is being agreed to differs every time.
So it fell through to "optional and nothing saved answers it", was left
unticked, and the step was refused with nothing on screen saying why.
*Mechanism.* An agreement is always asked and never answered from a saved value,
however much its wording resembles a Yes/No the profile happens to hold. A
checkbox is not an agreement merely for being a checkbox: "This is my most
recent education" and "Have you ever been employed by us before?" are not.

**90. A tick box was asked as a box to type into.** A checkbox carries no
options of its own, so it went down the same path as a free-text field -- and an
arbitration agreement came back as somewhere to type, which is not how anyone
accepts one.
*Mechanism.* A tick box is answered by ticking it or not, so those are the two
things offered.

**91. A setting unticked itself the moment it was saved.** The agreements switch
was added to the profile and to the options page but not to the settings
endpoint, so it was dropped in transit both ways: the save carried nothing and
the reload read nothing back.
*Mechanism.* It goes through /settings like every other preference -- and lives
in memory for the length of the session rather than on disk, because something
with legal weight should be chosen when you sit down to apply rather than left
switched on for months. There are tests for saving it, unsaving it, leaving it
alone while saving something else, and for the saved profile never learning
about it at all.

**92. A whole section of questions was never seen at all.** One widely used
applicant tracking system draws every Yes/No question as two bare <button>
elements: no role, no name, no value, not even an aria-checked, only class
names. Nothing about them says "control", so the scanner -- which collects
inputs, selects, textareas and things claiming a widget role -- walked straight
past seven required questions. They were not unanswered; they were invisible.
*Mechanism.* A container whose visible children are all buttons, two or more of
them, each with a short label, is a choice. The hidden input the widget keeps
beside its buttons is part of it and not another child, which is what the first
attempt got wrong -- checked against the live page, where requiring every child
to be a button found nothing at all. Navigation is excluded by wording, because
Back beside Next is the same shape and is not a question. What is chosen is read
from the page: aria where the page says so, otherwise the one class the chosen
button carries that its siblings do not.

**93. Every screening question on a form read as optional.** The red asterisk on
one applicant tracking system is drawn by CSS, not written in the text -- the
label says only "Have you used Node.js professionally?" and carries a class
saying it is required. So the marker search, which looked at text, found
nothing, and seven required questions were left blank without ever being asked
about.
*Mechanism.* A neighbouring element whose class says required counts as the
marker, the same as a written asterisk would, and "not-required" still does not.

**94. A field added to the catalogue never reached Settings.** The answers grid
on the options page is a list written out by hand, so a new fact appeared
everywhere except the one place anyone would go to fill it in.
*Mechanism.* Hugging Face is in that list. The list itself is still by hand, and
that is worth remembering next time a fact is added.

**95. "Do you need a work visa?" answered to nothing.** The sponsorship fact
knew every phrasing that contains the word sponsorship, and one applicant
tracking system asks it plainly without.
*Mechanism.* The plain phrasings are aliases of the same fact.

**96. An agreement phrased at you rather than as you was not one.** "By checking
this box, you consent to..." is exactly the same act as "I consent to...", and
only the second was recognised, so the first was left blank on a required box.
*Mechanism.* Both persons count, as does "by checking" and "by submitting".

**97. A list of tick boxes was read as one question per box.** "Which of these
have you used?" followed by eight boxes became eight fields, each a checkbox
called "OpenAI" answering to no saved fact and carrying no requirement of its
own -- the asterisk belongs to the question above them. The whole list was left
blank and never asked about.
*Mechanism.* The tightest block holding two or more tick boxes and no other kind
of control is the question; the boxes are its options. Tightest first, and a box
belongs to one list only -- a page whose every input happens to be a tick box
has some ancestor holding all of them, usually the body, and that ancestor is
not a question. Two earlier attempts at this were reverted: the first would not
parse, and the second climbed greedily and made a neighbouring Yes/No question
come back wearing this one's name. Both cases are now tests.

**98. A required list of tick boxes read as optional.** The marker belongs to
the question above the whole list, which from any single box is two levels up --
one further than the marker search reaches. So the list was grouped correctly,
shown as one question, and then skipped as an optional extra nobody had to
answer.
*Mechanism.* Required is asked of the list's own container, not of a box inside
it. The same now goes for a group of buttons.

**99. One box asking for several addresses was left blank.** "Please provide
links to your GitHub, portfolio, demo, or AI projects" is about GitHub and about
a portfolio, so neither fact can claim it -- and every address it asked for was
sitting in the profile.
*Mechanism.* A box that asks for links and names more than one of them gets each
saved address written out with what it is. Only addresses already entered, only
the ones the question names, and a box asking for a GitHub URL alone is still
the GitHub field and takes the ordinary path.

**100. The marker inside a fieldset was never looked at.** A required list of
tick boxes read as optional even after the previous fix, because that fix asked
the block's siblings. Where the block is a fieldset -- which is how one real
applicant tracking system builds these -- the question is the block's own first
child, so there was nothing beside it to find.
*Mechanism.* A group is asked about both ways: the heading beside the block, and
the heading inside it. Read off the live page, along with the fact that each box
is tied to its label by for and id rather than by wrapping, which the fixture
now does too.

**101. A question with several true answers allowed one.** "Which of these have
you used?" was offered as a list where picking Anthropic unpicked OpenAI, on a
question whose whole point is that several are true at once.
*Mechanism.* A multiselect toggles: pressing an option adds it, pressing it
again takes it away, and each pick is its own action against the same control.
Ticking is idempotent, so nothing already ticked is toggled back off. A question
with one answer still replaces rather than accumulates.

**102. A form restating what it was given read as a failure.** One writes a
phone number back as "+1 940 843 6087" after being handed "9408436087"; another
lists its states as "TX - Texas". The value went in and was accepted both times,
and both were reported as failures -- four red crosses on a page that was
correctly filled.
*Mechanism.* A code in front of the name counts as the name, and a dialling code
in front of a whole number counts as the number. Nothing about verified is
loosened: it is still a fresh read of state the page owns, and the page still
has to hold the answer that was asked for. Ten tests hold the other side of it,
including that one end of a range is not the answer to anything and that a form
showing back fewer digits than it was given has dropped some.

**103. An address line that threw the address away.** Several applicant tracking
systems build the first address line as a list of places rather than a text box.
Filling it typed the address and then looked away, and looking away is exactly
what discards free text there -- so the address, and the city and postcode the
list fills in for itself, all came back empty on a page that had just been
filled, and all three were reported as failures.
*Mechanism.* Where a control says in its own attributes that it offers
suggestions, its suggestions are used before looking away. Only a suggestion
that is what was asked for: a list coming back with somewhere else entirely is
not an answer, and the applicant is better told than guessed at. An ordinary
text box says nothing about suggestions, so nothing waits for any.

**104. A picker that declares nothing about itself.** The rule added for 103
looked for a control that says it offers suggestions -- a role, an aria
attribute. Several say nothing at all, and the only sign of what they are is
what they do: the text is gone the moment focus leaves.
*Mechanism.* A box that empties itself has rejected what it was given, which is
proof enough to try again through its list. It costs nothing anywhere else,
because a box that kept the value never reaches that path.

**105. A label that could not stand on its own.** A repeating block headed
"Phones (1)" holds fields called "Type" and "Number". "Number" matches no fact
at all, so a saved phone number sat in the profile while the form asked for it
in red.
*Mechanism.* The block heading finishes the label: "Phones (1)" and "Number"
together are a phone number. The count is dropped and the heading is tried both
as it appears and without a trailing s, because a block of phones holds a phone
number. Only reached when the label alone matched nothing, and only for a label
short enough to be missing half of itself -- a sentence says what it is about.

**106. The heading was never clean enough to use.** The rule added for 105 took
a heading and stripped a count from the end of it. A heading read off a real
page is "Phones (1)* required. 2" -- the count, the required marker and the
block number all stuck to it -- so nothing was stripped and the phone number
still went unfilled.
*Mechanism.* The heading is taken up to the first bracket, marker or digit.

**107. A dropdown handed back as a text box, again.** Where a select's choices
could not be read -- one that holds nothing but "— Make a Selection —" until the
page fills it -- the panel fell through to a text input. Typing into a dropdown
does nothing at all, so every one of those was unanswerable.
*Mechanism.* A choice control never renders a text box. When its options cannot
be read the panel says so, hides Save, and scrolls the control into view, so the
one thing that does work is the thing offered.

**108. A form inside a frame read as an unrecognised page.** Frames are merged
by taking the top frame's verdict and letting a child override it -- but only if
the child said exactly "application". A page whose form sits in a frame and
calls itself a registration, which is what a page asking you to make an account
is, had its verdict discarded, and the empty top frame's "unknown" stood. Every
one of its thirty-three fields was then skipped.
*Mechanism.* The frame holding the fields decides what the page is, whatever it
decided. An empty frame still changes nothing.

**109. Asked about a field the page had already answered.** "Login: required and
not answered yet" appeared while the login sat in the box. A required field the
page is holding a value for wants nothing from anybody, and asking anyway reads
as the tool being unable to see the page at all.
*Mechanism.* A required field already holding a real value is left alone. A tick
box counts as answered by being ticked, never by sitting there, and a value that
is only the control's own placeholder is not an answer.

**110. "— Make a Selection —" counted as an answer.** It is the commonest
placeholder there is and was in neither list.
*Mechanism.* It is in both now, along with "Select one" -- the service and the
injected side each keep their own copy and they have to agree.

**111. A question nobody could answer stopped the whole fill.** The panel's
main button ranked asking above filling: if any required question was still
outstanding it became a scroll-to-the-question and the plan's ready actions
were never carried out, under a note reading "I have filled everything else I
can" when nothing at all had been filled. On an account-creation form the
outstanding question was "Login" -- an account this tool refuses to create on
purpose -- so the count never reached zero, the button never came back, and
twenty-two fields with answers waiting were never touched on any run.
*Mechanism.* Filling comes before asking. Actions and questions cover disjoint
fields, so holding one back for the other buys nothing. The decision now lives
in `extension/cta.js` as a pure function with the order of precedence pinned by
test rather than left to be read off the source.

**112. Fields with an answer waiting were counted as done.** They were reported
as "attempted" -- a state meaning a control was acted on -- so they landed in
the completed list showing their value, reading as though the page were holding
it. Twenty-two of them appeared under a heading that said "Completed (0) · 33
left blank".
*Mechanism.* A separate "planned" state, shown as "will fill: X", counted in its
own column of the heading. A value on its own reads as a value the page owns, so
nothing not yet carried out is allowed to display as a bare value.

**113. Asked for an account name it was never going to use.** "Login" is a
required field, and required-and-unanswered is normally a question -- so the
panel asked for one, on a page whose own header said creating the account was
not its to do. No answer could ever clear it. Pressing Skip cleared it until
the next plan, which asked again.
*Mechanism.* A box you would choose an account name in is the first half of a
credential, and the password was always left alone; now the name is too. Two
signals together: the label opens with a word from the small closed set that
names an account -- login, username, user id, screen name -- and there is a
password somewhere on the same page. Without the password it is some other kind
of box and is not touched. An email address beside a password is still filled:
typing an address begins creating nothing.

**114. An optional box nothing saved fits held up the whole page.** "How did
you hear about us?" is optional, and its list of sources held nothing
resembling the saved answer. A saved answer that does not fit became a question
regardless of whether the form wanted the field, so it had to be cleared before
anything else could happen -- over a box the employer was content to leave
empty.
*Mechanism.* Required is the whole difference. A field the form insists on is
still worth stopping for; an optional one nothing saved fits is left blank, the
same as any other optional field with no answer.

**115. A page that rebuilt itself took every fingerprint with it.** This form
offers to read your resume and says plainly that it will replace what is
already in the form. When it did, everything planned beforehand pointed at
controls that no longer existed and came back "the control is no longer on the
page" -- including pressing Save on a question, which left the answer
unsaveable however many times it was pressed.
*Mechanism.* A fingerprint is derived from what a control looks like, so a page
that replaces its markup mints new ones for the same boxes. On that failure
alone, look again and find the same field in the page as it is now -- matching
on what the form calls it, and required to agree on the section, the kind of
control, and which entry of a repeating block it is. One match and the action
is retried unchanged; anything else and the failure stands. The value is never
reconsidered, only where it goes.

**116. A fact's own word buried in a long question stole the question.** "Do
you have a minimum of 2 years of mobile engineering experience?" was read as
asking for a phone number, because "mobile" is how half the world says phone.
"AI tools (such as Github Copilot...)" was read as asking for a GitHub profile,
and "the New York City or San Francisco area" as asking which city you live in.
One of those sat on a free-text box, where nothing catches it later: a choice
that does not fit its options is refused, but a text box takes whatever it is
given, so the phone number would simply have been typed onto the form.
*Mechanism.* Facts holding a piece of contact or identity data -- names, email,
phone, address, profile links, documents -- can no longer win a match at
sentence level. Measured over 35 real forms rather than guessed at: that path
wins about sixty matches and is right every time the fact describes a
circumstance, and was wrong every time it did not. Blocking them can only turn
a fill into a question, never the reverse.

**117. "Location" was the commonest label the matcher could not read.** Twenty
fields across the corpus -- "Location (City)", "Current location" -- on forms
that were otherwise filled, because `city` had no wording for it.
*Mechanism.* Qualified wordings only, never the bare word: "Location" on its
own belongs to whatever block it sits in, and inside a job it is where that job
was rather than where you live. Claiming it took an employment record's own
field away from it. It is kept out of `topics` for the same reason -- a label
containing the word may be about the role's location, not yours.

**118. Every Yes/No question on a form came back labelled "Yes".** A radio sits
inside its own `<label>`, and the word "Yes" lives in a span in there with it.
That span holds no control, is perfectly visible and is short, so the search for
the question inside the block found the answer first and stopped. The result is
a label nobody can answer and the panel cannot even show -- and on one form
that was every custom question it had, including work authorisation and
sponsorship, both of which the profile could have answered outright.
*Mechanism.* What each choice calls itself is not what the group is asking. The
search for the question now skips anything sitting inside a choice's own label,
so it falls through to the block heading a level further out, which is where the
question actually is. Found by capturing 35 real forms, not by meeting it.

**119. The asterisk family is wider than the one on a keyboard.** Two of the
largest boards mark a required field with U+2731 HEAVY ASTERISK, which reads as
a star and behaves as a letter. Thirty-nine labels across the corpus carried one
into matching and into what the panel showed, so "Current location ✱" never met
"current location".
*Mechanism.* The decoration set covers the family, not one character of it.

**120. "Most recent employer" was a different field from "current employer".**
Only one job can be either, and they mean the same one. "Current" was already a
word that decorates a field name without changing which field it is; "most" and
"recent" were not, so a label using them matched nothing at all. Their opposites
-- previous, prior, past, former -- stay distinguishing, because those really
are a different job.
*Mechanism.* "Most" and "recent" join the neutral qualifiers. Separately, a
label written "Current/Most Recent Company Name" keeps its slash through
normalising, so an exact-set test never saw it; the unmistakable-history test
now reads it the way every other rule does, one form per branch of the slash.

**121. A dropdown was handed back as a box to type in, because it was holding
no options.** Three hundred and twenty controls across the corpus call
themselves a combobox and three hundred and ten of them hold nothing at all
when the page is read -- their choices exist only once the control is opened.
Counting the options that happen to be lying about cannot tell that apart from
a control that genuinely has none, so the question became "type your answer",
for an answer that was only ever going to be picked from a list.
*Mechanism.* A control now says how it has to be worked, separately from what
it is made of: a list readable now, a list that exists once opened, a box that
offers nothing until something is typed, a calendar, a group of choices already
drawn, free text, long text, a file -- or `unknown`, which is what a control
whose signals do not add up gets instead of a guess. Every value is read from
something the page publishes about itself. Across 89 real forms nothing came
back unknown, and the two kinds of combobox split 310 to 10. It is deliberately
not part of the fingerprint: a list that has been opened once holds its choices
afterwards, and a control must not change identity by being read.

**122. A picker built as a search box was thrown away with the site's search.**
Anything typed `search` was treated as furniture. A phone country code -- a
filter over 244 entries -- is built exactly that way, so it was never offered
at all.
*Mechanism.* A box the form gave a name to is a question, whatever it is typed
as. The site's own search box has a placeholder and no label, because nothing
on the page is asking for it.

**123. A picker's own suggestions were thrown away.** Only a native `<select>`
had its choices read. A widget pointing at a listbox with `aria-controls` --
which is how a place picker shows what it found, and how a long list is kept
beside a control -- reported no options at all, so the only thing left to offer
was a box to type into, for a control whose whole purpose is that you pick from
what it found.
*Mechanism.* The list a control points at is read when it is already in the
page. The id is looked up rather than selected for: a page that generates ids
hands out things like ":r0:", which is a perfectly good id and not a usable
selector.

**124. A picker filled correctly was reported unverified.** A combobox's own
text box is not evidence -- typing into it filters a list, and reading it back
is how a rescan once called an option verified that the page had never accepted.
But choosing a suggestion is how a picker is answered at all, and the widget
writes its own wording back: handed "Denton, Texas" it comes back holding
"Denton, Texas, United States". Every such fill sat correctly filled on screen
and was reported as unverified.
*Mechanism.* The exact text typed is remembered, not just the fact of typing.
A box still reading back as that text is our own echo and proves nothing; a box
the page has since rewritten is the page answering. The safety property is
unchanged and was checked on the live control: a place the picker does not know
stays `attempted` with no signal. Only suggestion controls are marked -- an
ordinary text box holding what it was given is the whole of the evidence there,
and marking it took that away.

**125. A short opening step was read as an unrecognised page.** One large
system opens its application with four boxes -- first name, last name, email,
mobile -- every one of them drawn by a web component, so the light document
holds nothing at all. A page needed five labelled controls to count as an
application, and four is not five, so the whole thing was skipped. This is the
"unrecognised page" that filled nothing.
*Mechanism.* Counting alone cannot see a short first step, so what the page is
asking for settles it. A page wanting your name and your email and a way to
telephone you is collecting a person, not running a search or a newsletter, and
no page asks all three by accident. Three distinct subjects out of name, email,
phone, address and resume, across at least three labelled controls, is an
application. Sign-in and registration are decided before this and are unmoved.

**126. One frame failing lost the whole page's work, silently.** A page's
actions are grouped by the frame their controls live in and sent one trip per
frame. Any one of those trips throwing rejected the whole handler, so every
result from every other frame was discarded too. The panel caught the error,
reported it as a single line, and went on showing all twenty-two fields as
"ready to fill" -- which is exactly what a page that had never been filled
looks like. An application that rebuilds itself does this, because its frame id
does not survive the rebuild.
*Mechanism.* Each frame is attempted on its own. A frame that has gone away is
retried by asking every frame instead: a fingerprint only resolves where its
control actually is, so nothing can land in the wrong place, and answers of
"the control is no longer on the page" from the other frames are dropped rather
than reported. Whatever landed is returned even when something else failed; the
error is only raised when nothing landed at all. A frame id that is not a number
is treated as the top frame rather than sent to `executeScript` as NaN, which
threw.
*And it says so.* "The page did not answer in time" on its own reads like a
hiccup. It is every field on the page not being filled, so it is now reported
as that.

**127. Pressing Start on a page that wants an account did nothing at all.**
The run filled only when the page was classified exactly "application". A form
that asks you to create an account classifies as "registration" -- which is
most of the account-creation forms there are -- so it was scanned, planned, and
then walked straight past. Silently: no error, no activity, twenty-two answers
ready and showing on screen, and the panel's own header saying it would fill
everything except the password.
*Mechanism.* Whether there is anything to fill, not what the page is called.
The plan already knows: it holds nothing to do on a job list or a posting, and
something to do wherever there is. Decided by the same function the button
uses, so there is no second rule to drift from the first.

**128. "Current/Last Employer" answered with the job before the current one.**
A history fact outside a repeating block took the first record stored, and the
order things were written down in is not an answer to which job you are in now.
*Mechanism.* A form asking for one employer without a block to put several in
is asking for the current one, and one school means the last one attended. The
record marked current wins; failing that, the latest to finish. Inside a block
the page has said which entry it means, and that is still obeyed.

**129. A veteran answer spelled out in full was refused by a Yes/No control.**
One form asks the question in a sentence and offers the statute back as the
answer; the next asks the same thing and offers Yes and No. The saved wording
"No, I am not a veteran under one of the classifications listed above" was not
among Yes and No, so a required question was left that nobody could clear.
*Mechanism.* An answer that opens by saying which it is has already answered a
Yes/No control. Only the first word counts -- a sentence merely containing "no"
somewhere has settled nothing, and "Notarised" is not "No". Scored below an
ordinary wording match, so a control that really does offer the full statute
still gets the full statute.

**130. Money written the way people write money was not a number.** A currency
mark defeated the number parser and the separators between thousands defeated
the band parser, so a saved salary never became a number and never fell inside
a band. Every banded salary question on every form was refused -- "$100000" is
not among "$50,000 - $74,999", "$75,000 - $99,999", "$100,000 - $124,999".
*Mechanism.* The dress is not the number. Currency marks and thousands
separators are removed before parsing, on both sides, and only where they were
all that stood in the way: "25-35" is a band and must not become 2535 by having
its middle taken out. "Region 25-35" is still a place.

**131. Three questions every form asks had nothing to answer them with.**
"Willingness to Travel" had no fact at all. "Higher Education Level" is a level
rather than the name of a school or the title of a degree, so no education
record field answered it. "Willingness to Relocate" was not among the wordings
for relocating, though "Willing to relocate" was.

**132. A required field could fail forever without ever being asked about.**
An action that failed was planned again from the same saved answer on the next
look, failed again, and never became a question. Two required fields sat under
"Needs you" with a red cross against them and no way to answer either -- a dead
end visible on screen and impossible to clear from the panel.
*Mechanism.* A control that refused an answer refuses it every time, so the
fingerprints the page turned down are sent with the next plan and asked about
instead of tried again. The question says what was tried -- "the control would
not take X, please pick one" -- and carries the control's own choices, because
"this needs you" over a control is not a question anybody can act on. Nothing
refused, nothing changes.

**133. The panel offered a control's own "Choose one" row as an answer to
pick.** There were three copies of the list of what counts as a placeholder --
service, injected verifier, panel. Two were kept up to date and the panel's was
not. Worse, it tested the label exactly as written: the em dashes a form
decorates with are not part of the word, so "— Make a Selection —" was not
"make a selection", matched nothing, and was drawn as a button. Pressing it did
nothing, because it is not an answer. It is the control asking.
*Mechanism.* One list, in `extension/placeholders.js`, with no dependencies so
the panel and the page can both load it. Decoration is taken off before
matching: every kind of dash, and the marks a form marks required with. The
Python side and the JavaScript side are held to the same answers by test, so
they cannot drift again without something going red.

**134. Two new facts could never be given a value.** "Willingness to Travel"
and "Higher Education Level" were added as supplementary, which means both
"leave blank rather than ask" and "do not ask for this during setup" -- so they
were skipped on every form and there was nowhere to fill them in. Every form
asks both.

**135. Every custom question on a form came back with no label.** The search for
a label sitting before a control gave up after three levels. A form that wraps
each control in four or five nested divs put the question further out than
that, so eight required questions had no label at all -- and fell back to the
random name the form had given the input, so the applicant was asked
"q Rd OBSq YRu H" and "0 SEV4 Jb VVXa".
*Mechanism.* The walk goes further out. What keeps it honest was never the
depth: it stops the moment it reaches a container holding more than one
control, because from there the neighbours are other fields. Six of the eight
now read their real question -- "What is your desired base salary?", "Which AWS
services have you used to deploy and operate production workloads?".

**136. A widget's own "Select" was read as the question it was asking.** Two
required questions -- about work authorisation and about sponsorship -- came
back as a field called "Select", which answers nothing. That text is the
control saying it is waiting.
*Mechanism.* The shared placeholder list already knows what a "choose
something" prompt looks like, and no acceptance point in the label search takes
one now.

**137. A name a program made up was offered to the applicant as a question.**
Some forms give every control an id like "R0sWBoTw0J3"; split into words that
reads as "R0s WBo Tw0 J3", which looked enough like a label to be used as one.
*Mechanism.* Long, and mixing digits with both cases, is not something a person
names a field. Saying nothing is worse than saying the truth and better than
saying that. "field-51", "firstName" and "phone_number" all still count.

**138. The same answer, refused because the form worded it differently.**
Equal-opportunity questions are asked in whole sentences and answered in whole
sentences, and no two forms use the same ones. One offers "No, I am not a
veteran under one of the classifications listed above"; the next offers "I am
not a protected veteran". They are the same answer. One offers "No"; another
offers "No, I don't have a disability". Every form wording these differently
from the one the answer was saved on left a required question unanswerable.
*Mechanism.* Whether a sentence says yes, says no, or declines to say. Negative
is tested before positive because every negative sentence contains a positive
one -- "I am not" contains "I am". Declining is tested before either: "I don't
wish to answer" contains "don't", and reading that as No would put an answer on
a form that the applicant deliberately withheld. Scored below a wording match,
so a control offering the exact saved sentence still wins with it, and two
options meaning the same thing tie -- which is refused, because a tie is a
question for the applicant and not a coin flip.

**139. A saved answer was typed into a list without ever reading the list.**
Having an answer is not the same as knowing the control will take it. A veteran
question on a live application is a box that filters a list; handed the saved
answer in full it answered "No results were found" and the field stayed empty,
with the answer visible in the box above a list saying there was no such thing.
The same control, opened and read, offers that exact sentence as a row.
*Mechanism.* A control whose choices have not been read is opened and read
before anything is chosen -- which is the path a question already took. It
carries the saved answer with it, so where the answer is among what the control
offers it is chosen and nobody is asked anything. Only controls whose options
could not be read in the first place go this way; a list already on the page is
still chosen from straight away, and a text box never goes near it.
*And a filter gets a filter.* Where a box really must be typed into, the whole
answer is tried first and then shorter beginnings of it -- "No, I am", "No" --
which is what a person types. Whatever the list then offers is matched against
the whole answer, never against the fragment typed to reveal it.

**140. A form with one education slot was given the school before the most
recent one.** Inside a repeating block, records were indexed in the order they
happen to be stored -- which is the order they were typed in. Every form that
offers several of these lists them newest first, and a form that offers only
one is asking for the newest.
*Mechanism.* Sorted once, latest first: still going beats a finish date, and a
later finish beats an earlier. Entry nought is the current job or the last
school, entry one the one before it. The same sort answers a lone
"Current/Last Employer" with no block around it at all.

**141. The build was red and the only place that said so was an inbox.** Six
lint findings, all from this week's changes. The check that fails a build if
anything personal is committed also walked the virtualenv, where one library
ships a .docx template -- so anyone running the same checks locally before
pushing got a failure that CI would never see, and stopped running them.
*Mechanism.* It looks at what is actually ours. Being unable to run the gate is
how a red build reaches somebody's inbox instead of the terminal in front of
the person who caused it.

**142. The report said what was left blank and offered no way to answer it.**
"Have you previously worked for, or been on assignment with Toyota?" is
optional and nothing saved answers it, so it was correctly left alone -- but it
is the applicant's own answer, they are looking straight at it, and the only
thing pressing the row did was scroll to it.
*Mechanism.* Pressing a row that is not filled asks that question, with
whatever the control itself offers to choose from; a list nobody has read yet
is opened first, the same as any other. A row already filled still scrolls to
the field, which is the only thing there is to do with it. No fact key goes
with the answer: a question about one employer belongs to that question rather
than to the profile, so it is remembered against this wording and used again
wherever it is asked.

**143. The resume upload was labelled "or", and skipped.** An upload area
offering LinkedIn, Dropbox, "or", and a Select File button gave the file
control the label "or" -- the word between two buttons. Nothing matched it, it
was read as an optional extra, and the resume was never attached.
*Three things, in order.* A word on its own that joins rather than names is not
a label. Then the search reached further out and found the LinkedIn widget's
script, because `textContent` includes the source of any `<script>` inside --
the field came back called "api_key: 78vjko9pszx261 extensions:AwliWidget@...";
only what a person can read counts now. Then the real label turned out to be
the sentence that explains the dropzone, "Make completing your job application
easier by uploading your resume or CV", which is neither a phrase any alias
lines up with nor a question, so no rule reached it. A file control can only be
asking for a document, and which one is plain to read; the cover letter is
looked for first, because a page offering both says "cover letter" on one and
"resume or CV" on the other.
*And a document a form will take is never an optional extra.* Plenty of
applications leave the resume unmarked, and it was skipped in silence.
Attaching it is the point of the exercise, so it is put forward whether or not
the form insists.

**144. A nationality question offering 199 countries refused the country the
answer named.** The saved citizenship is "US Citizen" and the option is "United
States of America (USA)". Two things stood between them: the status word after
the place, and the code the form writes after the name.
*Mechanism.* A citizenship answer is a place and a status together -- "US
Citizen", "US Permanent Resident" -- and a form asking for nationality offers
only the places, so the status word comes off. Only for a fact that is about
somewhere: taking "resident" out of "Resident Engineer" would change what it
says. Separately, a short bracketed code after a name says the same thing twice
and is not part of the name, so it is ignored when nothing else matches. Only a
short one -- "Content (e.g. videos, ads, billboards etc)" is a thing a form is
offering, not a name with a code after it.

**145. There was no way to tell whether a change helped.** Every claim about a
form getting better rested on rerunning something by hand and remembering what
it said last time. `scripts/scoreboard.py` writes one row per application per
run -- fields, filled, asked, left blank -- and one row per unanswered field
with the kind of control it is and the options it offers. Two runs either side
of a change say plainly whether it helped, hurt, or did nothing.
*It earned its keep immediately.* The largest cluster of unanswered fields
looked like twenty-eight resume uploads nobody was attaching. A rule was
written for it; the scoreboard reported no change at all. Nineteen of those
forms draw a second, unnamed dropzone beside a named "Resume" input which was
already being matched -- so the cluster was mostly duplicates, and the rule was
solving a problem that did not exist. The rule is kept because a page with one
unlabelled upload is a real shape, but it is worth nothing today and the
numbers say so.

**146. A question the applicant's own CV answers went unanswered.** Across 68
real applications, 130 required Yes/No questions were left for a person -- "Do
you have hands-on engineering experience with Python and ML frameworks?", "Are
you based in a US timezone?". The model was only ever shown a saved answer to
compare the options against, and for these there is none. Their history answers
them.
*Mechanism.* Where nothing saved answers a question, the model is given what
the applicant wrote down -- skills, degrees, roles, bullet points -- and asked
which of the employer's own options those lines support. It is not deciding
anything about them; it is reading their words.
*What keeps it honest.* It must quote the line it read, and the quote is
checked against the evidence before the answer is offered. A quote that is not
there is refused. So is an answer with no quote, and so is an option the page
never offered. The prompt forbids inferring, estimating, and answering from
what is usual for someone with that background, and says why: a wrong answer
here goes on a real application in the applicant's name.

**147. The model's correct answers were thrown away by our own prompt.** The
options are listed to it numbered -- "1. Yes", "2. No" -- and it answered
"1. Yes". The check that an answer names one of the page's own options compared
that against "Yes" and rejected it, so every model answer was refused while its
own reasoning said the opposite: "The applicant's professional role at HCLTech
explicitly involves using Python", suggested = none.
*Mechanism.* The enumerator this file adds is taken off before the check. That
is not loosening it -- it is undoing our own formatting. "Maybe" and
"3. Perhaps" are still refused.
*And it says what it saw.* A reply naming something the control does not offer
now reports what was named. Before, that was indistinguishable from a refusal,
which is how this survived: both came back as the model's own sentence.

**148. The model was never told where the applicant lives.** "Are you based in
a US or equivalent timezone?" went unanswered on form after form, while the
profile held Denton, Texas, United States. The evidence put in front of the
model was skills, education and jobs -- and nothing else. It refused correctly:
it had genuinely not been shown an address.
*Mechanism.* Where they live, and what they may do about it -- authorisation,
sponsorship, relocation, notice, travel, highest education -- are part of the
evidence now. The lines are theirs; none of them is computed.

**149. One rule sat across two different things, and blocked both.** The
prompt said "do not infer". That stopped the model rounding two years of Python
up into eight, which is the point. It also stopped it reading "Denton, Texas"
as living in the United States, because that needs one fact about the world.
The asymmetry showed it: "willing to work anywhere except Arkansas" answered a
question about a Little Rock office, since Arkansas was named in the line --
but the same preference could not answer one about NYC.
*Mechanism.* The two are separated. Common knowledge -- that a city sits in a
country, that a master's is above a bachelor's -- may join what they wrote to
what is asked. It may never supply a fact about them. A question about their
years, their tools, or a clearance is still refused outright.

**150. It would not say it was excited.** Employers write "Are you excited and
able to work from our NYC office?", and the model refused: no line said the
applicant was excited. True, and useless -- it is the same question as "can you
work from NYC", which a stated willingness answers.
*Mechanism.* Enthusiasm wording is named as the dressing it is. A contradiction
is still answered honestly rather than agreeably: someone who will only work
remotely answers No to an office question, rather than the prompt reaching for
the pleasant option.
→ `test_answer_from_evidence.py::test_common_knowledge_may_join_a_line_to_the_question`,
`test_where_they_live_is_part_of_what_the_model_is_shown`

**151. A yes-or-no answer rotted four facts, permanently.** A profile held
`referral_source = "Yes"`, `citizenship = "Yes"`, a degree of "Yes" and a
preferred name of "No". Each got there the same way: a yes-or-no question
matched a fact that means something open, and the answer was written into it.
Nothing looked wrong on the page that saved it. Afterwards "How Did You Hear
About Us?" was answered "Yes" against eleven options -- Colleges & Universities,
Company Website, Job Board -- on every form, because a saved answer is trusted
ahead of asking. Found in a report bundle from a real Toyota application.
*Mechanism.* A bare yes or no may only be saved where a yes or no is what the
fact means, which its own spec already says: either it lists them as choices,
or its prompt is phrased as that question. "Are you Hispanic or Latino?" still
takes "No"; "Citizenship status" does not. Enforced at both write paths, and
again before a value is offered, so no button appears that would only error.

**152. An answer typed by hand was respected and then forgotten.** A required
field the page already held a value for was skipped, correctly -- and that was
all. The county someone typed themselves was thrown away, so the next form
asked for it, and the one after that. A tool that learns is one that stops
asking.
*Mechanism.* A skipped field carries what the page was holding, when the
profile has nothing of its own for it and nothing was already remembered
against that question's wording. Its row gets a Keep button. Passwords, account
names, uploads and anything a page wrote for itself are never offered. Taking
them all without asking is a Settings toggle, off by default: moving values off
a page into a profile is not something to start doing quietly.
→ `test_keeping_page_answers.py`

**153. "Saved" was said about answers that were not saved.** The service
declines to remember some answers, for fourteen reasons that are each
defensible: a voluntary question, a value that is not one of the control's own
options, a bare number that is really an option id, a question with no visible
label to key it by. Every one of them returned `learned: false` -- and the
panel threw the reply away and flashed "Saved". Nothing was saved, the next
scan found nothing saved, and the same question was asked again. Reported as
"even after I answer a question it keeps asking me again and again", which is
exactly what it does, for as long as anyone keeps answering.
*Mechanism.* The reply is read. A refusal says so, with its reason, and goes in
the journal below. The fact path throws on a value a fact cannot hold, and that
is caught and reported the same way rather than passing for success.

**154. A report was a photograph of a page, and the faults are sequences.** A
question answered three times that keeps returning, an instruction typed into
the chat that changed nothing, an answer taken and then not kept -- none of
them can be seen in the state of a page at one moment. A snapshot of a looping
question is identical to a snapshot of one being asked for the first time,
which is why these went unreported however many bundles were sent.
*Mechanism.* The panel keeps a journal: every question put to somebody and how
many times, every answer with whether it landed on the page, every answer not
kept and why, every chat instruction with what came of it, and every fill with
what verified. It goes in the bundle, with the repeats counted out separately.
A question on its second time round says so on screen as well.
*And it is bounded.* Four hundred entries, oldest dropped, so a form left open
all afternoon does not grow without end.
→ `test_session_journal.py`

**155. A quote can be real and still say nothing.** The grounding rule was that
the model must quote the line it read, and the quote is checked against the
evidence. Asked -- required, on a real application -- whether the applicant had
built and deployed production-level applications using React and TypeScript,
the model answered Yes and quoted "Role: Software Developer Intern at Josh
Innovations (Jun 2021 to Oct 2021)". A real line, real dates, no React in it.
The check confirmed the quote existed. It never confirmed the quote was about
the question, so a qualification was claimed with nothing behind it.
*Mechanism.* The question's own subjects are found, and those that appear
anywhere in the evidence must appear in the quoted line too. Narrow on purpose:
a question about a timezone names nothing any profile contains, so it cannot be
settled this way and is left to the rules above -- which is what keeps "Are you
based in a US timezone?" answerable from an address.
*Endings, not prefixes.* "sponsor" and "sponsorship" are one subject; "require"
and "requires" are one subject; "timezone" and "time" are not, and a plain
prefix rule made them one -- "time" appears in half of all job descriptions.

**156. The model could not tell what year it was.** Every role on file reads
"Jun 2025 to now". Asked how many years of relevant experience the applicant
had, against options 7+ / 5-7 / 2-4 / 0-1, it answered **0-1** for somebody
with about two years of it. Not a guess it should have made, and not one it
could have got right: nothing in front of it dated "now".
*Mechanism.* Today's date leads the evidence. It is a fact about the world, not
about the applicant, so it appears only where there is a history for it to
date -- an empty profile still reports nothing recorded.
→ `test_answer_from_evidence.py::test_a_quote_that_does_not_mention_what_was_asked_is_refused`

**157. A required field failed on every application one ATS serves, and no
replay could have found it.** Filling 125 real applications produced eleven
failures spread across four unrelated employers -- one each, always the same
control: a required "Current location" box that reported, correctly, that the
page held nothing after it was written to.

    <div class="application-field">
      <input type="text" name="location" required>
      <input type="hidden" name="selectedLocation">
      <div class="...dropdown-container">

The visible box announces nothing -- no role, no aria-autocomplete, no
placeholder to read -- so it scanned as ordinary text. The hidden input beside
it is what the form submits, and it stays empty until a suggestion is picked.
*Mechanism.* A text box paired with a hidden input named for the same thing is
worked as a search: type, wait, pick. The pair has to share a name, or a CSRF
token sitting beside a text box would turn it into a search that offers
nothing.
*How it was found.* Every other script in scripts/ reads. corpus.py saves a
page's shape, scoreboard.py replays those shapes -- and a replay cannot fail to
write to a page, because it never writes to one. The 62% those runs reported
was a claim about a replay. apply.py fills, and found this on its first pass.
→ `test_control_shapes.py::test_a_text_box_backed_by_a_hidden_input_is_a_search`

**158. A job description was a dead end.** 58 of 125 real job URLs landed on a
posting with an Apply button rather than on a form -- including all 18 served
by one large ATS, which reported six fields across eighteen applications. The
panel's button read "Scan this page", which scanned, found the same nothing,
and offered to scan again. The form was one click away every time, and the
click was never offered to anybody.
*Mechanism.* A page that is not an application and carries an apply control
offers to open it. Ranked below filling, so a form with work on it is never
navigated away from, and below outstanding questions, so an answer in progress
is not walked away from either. An application carrying its own "Apply" submit
is not re-opened.
*More than one hop.* The path is a listing, then a choice of how to apply, then
often a sign-in wall, then the form. The harness walks up to four, preferring
the plainest way in: "Apply Manually" over "Autofill with Resume", which wants
an account this will not create.
*Where it stops.* That ATS puts account creation in front of every form. The
walk reaches the registration page and fills everything on it except the
credentials, which is exactly as far as anybody should go uninvited.

**159. LinkedIn will not say where its Apply button goes.** 27 of 40 postings
were recorded as "external (behind a login or bespoke)" with no destination at
all. Opening them in a browser settled it: every one resolves to
linkedin.com/signup/cold-join. The destination is genuinely unavailable to a
guest, and reading it out of a signed-in session at volume is scraping an
account into a suspension.
*Mechanism.* The company name is public on the guest page, and the hiring
systems publish their own openings at a slug derived from it. So the name is
the key: the employer's own board hands over the apply URL directly, with no
login and no redirect to follow. 5 of 40 companies answered, giving 15 real
forms, 12 of which filled.
→ `test_cta_decision.py::test_a_listing_offers_to_open_the_application`

**160. A wall was reported as a page nobody could read.** Two different pages
came back "no controls found", which reads as a fault in the reading. Neither
was. One ATS puts "Create Account/Sign In, step 1 of 6" in front of every
application and offers two sign-in buttons and no fields at all. Another serves
a whole-page bot check instead of the form. Both were understood perfectly:
there is nothing there for anybody who will not make an account or answer a
challenge, and this does neither.
*Mechanism.* A page offering a way in and nothing to fill is `sign_in` -- a
kind that already existed and that nothing had ever returned. Strict on both
halves: there must be a sign-in control and no question to answer, so a form
with a "Sign in" link in its header stays a form. Whole-page bot checks are
named by their host (DataDome, PerimeterX, Cloudflare, Kasada, Arkose) and need
no size test: if one is on the page, it is the page.
*Naming a challenge is not working around one.* It is the difference between
stopping with a reason and stopping with a shrug.

**161. An Apply button that was not called Apply.** One large ATS labels it
"I'm interested". The pattern matched only "apply", so those postings scanned
as a page with no way into them and were reported as a form with no controls.
*Mechanism.* The pattern covers the phrasings that begin an application, still
anchored at the start so "Not interested" cannot match, and still with no
overlap on SUBMIT_TEXT -- a word that finishes an application must never appear
on the list that opens one.

**162. A click that worked was read as a click that failed.** Driving a real
browser, pressing a control that navigates destroys the execution context, and
the harness caught that as an error and returned the observation from *before*
the click. So an ATS that navigates on Apply reported the listing it had
already left -- every one of its eighteen applications, as a page with nothing
on it, after the walk had in fact reached the right page.
*Mechanism.* A destroyed context after a click is what success looks like from
outside. It waits for the new page and scans that instead.
→ `test_walls_and_gates.py`

**163. The resume upload was invisible, on every form that matters.** A file
input is 1x1 pixels with a styled dropzone drawn around it -- that is how
nearly every modern application does uploads. Visibility already allowed for
that and measured the drawn thing instead: it took the input's label if it had
one, and gave up when the label measured 1x1. A screen-reader-only label is 1x1
by design. So on sixty applications the file control was read as not on the
page at all, `/plan` had nothing to attach to, and nobody was ever asked to
attach anything.
*Mechanism.* Whichever of label or nearest ancestors is actually drawn, rather
than the first one that exists.

**164. And attaching it reported failure when it had worked.** The upload
succeeds, the page removes the file input entirely and renders the filename in
its place -- so the fingerprint resolves to nothing and the check said "the
control is no longer on the page". True, and exactly backwards: the control is
gone because it worked.
*Mechanism.* Two further readings, in order. A file control anywhere holding a
file of that name -- still the page's own state, only the handle changed. Then,
only when every file control has gone, the page's own rendered text naming the
file. The second is narrow on purpose: while an empty upload is still sitting
there, nothing has been accepted and a filename printed somewhere proves
nothing.
*And it waits.* Two hundred milliseconds is enough for a control that keeps its
own list and nowhere near enough for one that sends the document to a server
and redraws when it returns.
→ `test_control_shapes.py::test_a_one_pixel_file_input_behind_a_dropzone_is_on_the_page`

**165. Seven questions real forms ask that nothing here could answer.** Taken
from what the corpus asked and the matcher matched to nothing: whether you have
interviewed there before, the earliest date you could start, how many days a
week you would come into an office, years of professional experience, and a
paragraph of anything else worth saying. Each was handed back to the applicant
on every form that asked it.
*Not guessed at.* Two more were written and removed the same afternoon --
current employer and current job title -- because the employment record already
answers those, and a flat fact took the question away from the record that had
the better answer. Nine tests said so.

**166. "Cannot be told apart from outside a login" was true of the five that
were asked.** LinkedIn resolves every posting to a sign-up wall, so a company
name is all there is to work from, and probing five systems answered for 5
companies out of 40. The other 35 were written off as Workday, iCIMS, Oracle or
bespoke.
*Mechanism.* Ask more systems, under more spellings. A company's board is filed
under a name nobody can reason out -- Match Group is matchgroup on one system
and match on another -- so the shapes get tried rather than deduced. Workday is
asked properly: its front page answers 406 to anything that does not look like
a browser, while the feed underneath is a plain POST that answers to anyone,
and the site name that could not be guessed is tried from the shapes real
tenants use. 13 of 36 companies, no login anywhere.
*And five systems were left out on purpose.* Jobvite, iCIMS, Taleo,
SuccessFactors and BambooHR serve an empty page shell that says 200 for a
company they have never heard of -- jobs.jobvite.com/nvidia answers as readily
as the real one, and NVIDIA is on Workday. Believing those reported the wrong
system with total confidence, which is worse than reporting nothing.

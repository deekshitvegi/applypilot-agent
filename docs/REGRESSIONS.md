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

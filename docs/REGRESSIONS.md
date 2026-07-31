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

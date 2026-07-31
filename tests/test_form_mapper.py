from applypilot.form_mapper import plan_form_fill
from applypilot.models import CandidateProfile, FormField, FormOption, ReusableAnswer


def test_maps_profile_answers_and_blocks_passwords() -> None:
    profile = CandidateProfile(
        legal_name="Test Candidate",
        email="candidate@example.test",
        requires_sponsorship=False,
    )
    fields = [
        FormField(id="first", label="First name", required=True),
        FormField(id="last", label="Last name", required=True),
        FormField(id="email", label="Email address", field_type="email", required=True),
        FormField(
            id="sponsor",
            label="Will you require employment sponsorship?",
            field_type="select",
            options=[FormOption(value="yes", label="Yes"), FormOption(value="no", label="No")],
            required=True,
        ),
        FormField(id="essay", label="Why are you interested?", field_type="textarea", required=True),
        FormField(id="password", label="Account password", field_type="password"),
    ]

    plan = plan_form_fill("https://careers.example.test/apply", fields, profile, [])

    values = {action.field_id: action.value for action in plan.actions}
    assert values == {
        "first": "Test",
        "last": "Candidate",
        "email": "candidate@example.test",
        "sponsor": "no",
    }
    assert [field.field_id for field in plan.unknown_fields] == ["essay"]
    assert [field.field_id for field in plan.blocked_fields] == ["password"]
    assert plan.submit_allowed is False
    assert plan.confirmation_required is True


def test_uses_similar_reusable_answer() -> None:
    field = FormField(
        id="clearance",
        label="Are you willing to obtain a security clearance?",
        required=True,
    )
    answer = ReusableAnswer(
        question="Would you be willing to obtain a security clearance?",
        answer="Yes",
    )

    plan = plan_form_fill("https://example.test", [field], CandidateProfile(), [answer])

    assert plan.actions[0].value == "Yes"
    assert plan.actions[0].source == f"answer.{answer.id}"


def test_ignores_generic_saved_select_answer_for_specific_radio_question() -> None:
    field = FormField(
        id="linux",
        label="Regarding Linux, select the option that best fits your experience",
        field_type="radio",
        required=True,
        options=[
            FormOption(value="new", label="I am new to Linux"),
            FormOption(value="intermediate", label="Intermediate"),
        ],
    )
    generic = ReusableAnswer(question="Select", answer="No")

    plan = plan_form_fill("https://example.test", [field], CandidateProfile(), [generic])

    assert not plan.actions
    assert plan.unknown_fields[0].field_id == "linux"


def test_maps_voluntary_demographics_without_an_ai_provider() -> None:
    profile = CandidateProfile(
        race_ethnicity="Prefer not to answer",
        veteran_status="No",
        disability_status="Yes",
    )
    fields = [
        FormField(
            id="race",
            label="Race / ethnicity",
            field_type="select",
            options=[
                FormOption(value="decline", label="I prefer not to answer"),
                FormOption(value="asian", label="Asian"),
            ],
        ),
        FormField(
            id="veteran",
            label="Protected veteran status",
            field_type="select",
            options=[
                FormOption(value="protected", label="Yes, I am a protected veteran"),
                FormOption(value="not-protected", label="No, I am not a protected veteran"),
            ],
        ),
        FormField(
            id="disability",
            label="Disability status",
            field_type="select",
            options=[
                FormOption(value="yes", label="Yes, I have a disability"),
                FormOption(value="no", label="No, I do not have a disability"),
            ],
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "race": "decline",
        "veteran": "not-protected",
        "disability": "yes",
    }


def test_maps_a_saved_multi_choice_answer_to_checkbox_group() -> None:
    answer = ReusableAnswer(
        question="Which office location(s) are you interested in?",
        answer="Remote, US",
    )
    fields = [
        FormField(
            id="redwood",
            label="Which office location(s) are you interested in? Redwood City, CA",
            field_type="checkbox",
        ),
        FormField(
            id="remote",
            label="Which office location(s) are you interested in? Remote, US",
            field_type="checkbox",
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, CandidateProfile(), [answer])

    assert {action.field_id: action.value for action in plan.actions} == {
        "redwood": "false",
        "remote": "true",
    }


def test_united_states_does_not_get_mistaken_for_state_field() -> None:
    profile = CandidateProfile(
        region="Illinois",
        work_authorization="Yes, I am authorized to work in the United States.",
    )
    fields = [
        FormField(
            id="authorization",
            label="Are you legally authorized to work in the United States?",
            field_type="select",
            required=True,
            options=[FormOption(value="yes", label="Yes"), FormOption(value="no", label="No")],
        ),
        FormField(
            id="state",
            label="In what US state do you currently reside in?",
            field_type="select",
            required=True,
            options=[FormOption(value="IL", label="Illinois")],
        ),
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "authorization": "yes",
        "state": "IL",
    }


def test_optional_unanswered_questions_are_included_for_guided_review() -> None:
    fields = [
        FormField(id="hispanic", label="Are you Hispanic/Latino?", field_type="select"),
        FormField(id="portfolio", label="Website", field_type="url"),
    ]

    plan = plan_form_fill("https://example.test", fields, CandidateProfile(), [])

    assert [(field.field_id, field.required) for field in plan.unknown_fields] == [
        ("hispanic", False),
        ("portfolio", False),
    ]


def test_phone_country_code_is_not_filled_with_the_whole_phone_number() -> None:
    profile = CandidateProfile(phone="+1 (940) 843-6087", country="United States")
    fields = [
        FormField(
            id="phone-code",
            label="Mobile Phone Country Code",
            field_type="select",
            options=[
                FormOption(value="US", label="US +1 United States"),
                FormOption(value="IN", label="IN +91 India"),
            ],
        )
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert plan.actions[0].value == "US"
    assert plan.actions[0].source == "profile.phone"


def test_maps_grouped_authorization_and_sponsorship_radios() -> None:
    profile = CandidateProfile(
        work_authorization="Yes, I am authorized to work in the United States.",
        requires_sponsorship=False,
    )
    fields = [
        FormField(
            id="authorized",
            label="Are you legally authorized to work in the United States?",
            group_label="Are you legally authorized to work in the United States?",
            name="authorized",
            field_type="radio",
            required=True,
            options=[FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")],
        ),
        FormField(
            id="sponsorship",
            label="Will you now or in the future require sponsorship?",
            group_label="Will you now or in the future require sponsorship?",
            name="sponsorship",
            field_type="radio",
            required=True,
            options=[FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")],
        ),
    ]

    plan = plan_form_fill("https://careers.example.test", fields, profile, [])

    assert {action.field_id: action.value for action in plan.actions} == {
        "authorized": "Yes",
        "sponsorship": "No",
    }


def test_maps_referral_source_from_captured_job_url() -> None:
    field = FormField(
        id="source",
        label="How did you find out about this position?",
        field_type="radio",
        options=[
            FormOption(value="indeed", label="Indeed"),
            FormOption(value="linkedin", label="LinkedIn"),
            FormOption(value="other", label="Other"),
        ],
    )

    plan = plan_form_fill(
        "https://careers.example.test",
        [field],
        CandidateProfile(),
        [],
        source_url="https://www.linkedin.com/jobs/view/123",
    )

    assert plan.actions[0].value == "linkedin"
    assert plan.actions[0].source == "job.source_url"


def test_captured_source_overrides_stale_reusable_referral_answer() -> None:
    field = FormField(
        id="source",
        label="How did you find out about this position?",
        field_type="radio",
        options=[
            FormOption(value="employee", label="Current Employee"),
            FormOption(value="linkedin", label="LinkedIn"),
        ],
    )
    stale = ReusableAnswer(
        question="How did you find out about this position?",
        answer="Current Employee",
    )

    plan = plan_form_fill(
        "https://careers.example.test",
        [field],
        CandidateProfile(),
        [stale],
        source_url="https://www.linkedin.com/jobs/view/123",
    )

    assert plan.actions[0].value == "linkedin"
    assert plan.actions[0].source == "job.source_url"


def test_generic_radio_on_values_use_the_visible_option_label() -> None:
    field = FormField(
        id="source",
        label="How did you find out about this position?",
        field_type="radio",
        options=[
            FormOption(value="on", label="Current Employee"),
            FormOption(value="on", label="LinkedIn"),
        ],
    )

    plan = plan_form_fill(
        "https://jobs.ashbyhq.com/example/application",
        [field],
        CandidateProfile(),
        [],
        source_url="https://www.linkedin.com/jobs/view/123",
    )

    assert plan.actions[0].value == "LinkedIn"


def test_correctly_spelled_answer_matches_misspelled_visible_option() -> None:
    field = FormField(
        id="linux",
        label="Regarding Linux, select your present Linux experience",
        group_label="Regarding Linux, select your present Linux experience",
        field_type="radio",
        options=[
            FormOption(value="on", label="Intermediate"),
            FormOption(value="on", label="Expereinced"),
            FormOption(value="on", label="Expert"),
        ],
    )
    answer = ReusableAnswer(question=field.group_label, answer="Experienced")

    plan = plan_form_fill(
        "https://jobs.ashbyhq.com/example/application",
        [field],
        CandidateProfile(),
        [answer],
    )

    assert plan.actions[0].value == "Expereinced"


def test_canonical_profile_value_rejects_corrupt_exact_page_answer() -> None:
    question = "Are you legally authorized to work in the United States?"
    field = FormField(
        id="authorized",
        label=question,
        group_label=question,
        field_type="radio",
        options=[FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")],
    )
    profile = CandidateProfile(work_authorization="No")
    correction = ReusableAnswer(question=question, answer="Yes")

    plan = plan_form_fill(
        "https://jobs.ashbyhq.com/example/application",
        [field],
        profile,
        [correction],
    )

    assert plan.actions[0].value == "No"
    assert plan.actions[0].source == "profile.work_authorization"


def test_selects_only_resume_supported_skill_checkboxes() -> None:
    group = "What development languages are you most experienced with?"
    fields = [
        FormField(
            id="python",
            label=f"{group} Python",
            group_label=group,
            option_label="Python",
            field_type="checkbox",
            required=True,
        ),
        FormField(
            id="ruby",
            label=f"{group} Ruby",
            group_label=group,
            option_label="Ruby",
            field_type="checkbox",
            required=True,
        ),
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(),
        [],
        resume_text="Built production APIs and AI agents using Python.",
    )

    assert {action.field_id: action.value for action in plan.actions} == {
        "python": "true",
        "ruby": "false",
    }
    assert not plan.unknown_fields


def test_cloud_aliases_require_explicit_resume_evidence() -> None:
    group = "What Cloud environments are you most experienced deploying code to?"
    fields = [
        FormField(
            id=name.lower(),
            label=f"{group} {name}",
            group_label=group,
            option_label=name,
            field_type="checkbox",
        )
        for name in ("GCP", "Azure", "AWS")
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(),
        [],
        resume_text="Deployed services on Google Cloud Platform and Amazon Web Services.",
    )

    assert {action.field_id: action.value for action in plan.actions} == {
        "gcp": "true",
        "azure": "false",
        "aws": "true",
    }


def test_resume_skill_group_works_when_scanner_only_has_full_checkbox_labels() -> None:
    question = "Please select all tools you have hands on experience with"
    fields = [
        FormField(
            id="docker",
            label=f"{question} Docker",
            option_label="Docker",
            field_type="checkbox",
        ),
        FormField(
            id="jenkins",
            label=f"{question} Jenkins",
            option_label="Jenkins",
            field_type="checkbox",
        ),
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(),
        [],
        resume_text="Built and deployed Docker containers.",
    )

    assert {action.field_id: action.value for action in plan.actions} == {
        "docker": "true",
        "jenkins": "false",
    }


def test_relocation_willingness_does_not_select_every_city() -> None:
    group = "Which city would you be interested in for a relocation package?"
    fields = [
        FormField(
            id="san-jose",
            label=f"{group} San Jose",
            group_label=group,
            option_label="San Jose, CA",
            field_type="checkbox",
            required=True,
        ),
        FormField(
            id="kansas-city",
            label=f"{group} Kansas City",
            group_label=group,
            option_label="Kansas City, MO",
            field_type="checkbox",
            required=True,
        ),
    ]

    plan = plan_form_fill(
        "https://careers.example.test",
        fields,
        CandidateProfile(willing_to_relocate=True),
        [],
    )

    assert not plan.actions
    assert [(item.field_id, item.label) for item in plan.unknown_fields] == [
        ("san-jose", group)
    ]


def test_saved_short_question_answer_is_reused_instead_of_asked_again() -> None:
    # Live regression: the panel asked "Name" over and over. It saves an
    # answer under the label it displayed ("Name"), but matching compared
    # against the combined "label name" form and the fuzzy matcher dropped
    # every question shorter than six characters, so the answer could never
    # map and the same question was re-announced after every save.
    # Field shapes copied from a live Ashby application form, where the name
    # attribute widened the comparison label to "email systemfield email".
    fields = [
        FormField(id="ap-1", label="Name", name="_systemfield_name", required=True),
        FormField(
            id="ap-2", label="Email", name="_systemfield_email",
            field_type="email", required=True,
        ),
    ]
    answers = [
        ReusableAnswer(id="a1", question="Name", answer="Deekshitth Vegi"),
        ReusableAnswer(id="a2", question="Email", answer="candidate@example.test"),
    ]

    plan = plan_form_fill(
        "https://careers.example.test/apply", fields, CandidateProfile(), answers
    )

    values = {action.field_id: action.value for action in plan.actions}
    assert values == {"ap-1": "Deekshitth Vegi", "ap-2": "candidate@example.test"}
    assert plan.unknown_fields == []


def test_saved_answer_matches_the_group_label_the_panel_displayed() -> None:
    # The panel shows `group_label or label`; a saved answer keyed to that
    # exact text must map back to the field.
    fields = [
        FormField(
            id="ap-9",
            label="Preferred pronouns He/him",
            group_label="Preferred pronouns",
            name="pronouns",
            field_type="text",
            required=True,
        ),
    ]
    answers = [ReusableAnswer(id="p1", question="Preferred pronouns", answer="He/him")]

    plan = plan_form_fill(
        "https://careers.example.test/apply", fields, CandidateProfile(), answers
    )

    assert {action.field_id: action.value for action in plan.actions} == {"ap-9": "He/him"}


def test_short_saved_answer_does_not_hijack_a_long_employer_question() -> None:
    # Live regression from Anthropic's Greenhouse form. A saved
    # "Country -> United States" answered the sponsorship question, because
    # the phrase "the country in which this role is based" contains "country"
    # and the containment shortcut scored that 0.95. Answering a sponsorship
    # question with a country name is both wrong and unsafe.
    sponsorship = (
        "Will you now or will you in the future require employment visa "
        "sponsorship to work in the country in which this role is based?"
    )
    fields = [
        FormField(id="ap-22", label=sponsorship, field_type="text", required=True),
        FormField(id="ap-4", label="Country", field_type="text", required=True),
    ]
    answers = [ReusableAnswer(id="c1", question="Country", answer="United States")]

    plan = plan_form_fill(
        "https://job-boards.greenhouse.test/apply", fields, CandidateProfile(), answers
    )

    values = {action.field_id: action.value for action in plan.actions}
    assert values.get("ap-4") == "United States"
    assert "ap-22" not in values
    assert [field.field_id for field in plan.unknown_fields] == ["ap-22"]


def test_comparable_length_questions_still_match_loosely() -> None:
    # The containment shortcut must still work where it is genuinely useful.
    fields = [FormField(id="ap-1", label="Postal Code", field_type="text", required=True)]
    answers = [ReusableAnswer(id="p1", question="Postal Code (ZIP)", answer="76208")]

    plan = plan_form_fill(
        "https://job-boards.greenhouse.test/apply", fields, CandidateProfile(), answers
    )

    assert {a.field_id: a.value for a in plan.actions} == {"ap-1": "76208"}


def test_country_picks_the_closest_option_not_the_first_containing_one() -> None:
    # Live regression from a Workday form: "United States" selected "United
    # States Minor Outlying Islands (+1)" because containment matched the
    # first option in list order. The wrong country reached the employer.
    profile = CandidateProfile(country="United States")
    fields = [
        FormField(
            id="country",
            label="Country",
            field_type="select",
            required=True,
            options=[
                FormOption(value="UMI", label="United States Minor Outlying Islands (+1)"),
                FormOption(value="USA", label="United States of America (+1)"),
            ],
        )
    ]

    plan = plan_form_fill("https://swinerton.wd1.myworkdayjobs.test", fields, profile, [])

    assert plan.actions[0].value == "USA"


def test_exact_option_still_beats_a_longer_near_match() -> None:
    profile = CandidateProfile(country="India")
    fields = [
        FormField(
            id="country",
            label="Country",
            field_type="select",
            required=True,
            options=[
                FormOption(value="IO", label="British Indian Ocean Territory"),
                FormOption(value="IN", label="India"),
            ],
        )
    ]

    plan = plan_form_fill("https://example.test", fields, profile, [])

    assert plan.actions[0].value == "IN"


def test_saved_state_answer_fills_a_state_territory_field() -> None:
    # Live regression: the page labels the field "State", the saved answer is
    # "State / Territory". The agent told the user "your state is set to Texas"
    # while leaving the required dropdown empty and blocking the application.
    fields = [
        FormField(
            id="state",
            label="State",
            field_type="select",
            required=True,
            options=[FormOption(value="TX", label="Texas"), FormOption(value="CA", label="California")],
        )
    ]
    answers = [ReusableAnswer(id="s1", question="State / Territory", answer="Texas")]

    plan = plan_form_fill("https://careers.example.test/apply", fields, CandidateProfile(), answers)

    assert {a.field_id: a.value for a in plan.actions} == {"state": "TX"}
    assert plan.unknown_fields == []


def test_a_short_answer_still_cannot_claim_a_full_sentence_question() -> None:
    # The guard above must not undo the sponsorship fix.
    sponsorship = (
        "Will you now or will you in the future require employment visa "
        "sponsorship to work in the country in which this role is based?"
    )
    fields = [FormField(id="sp", label=sponsorship, field_type="text", required=True)]
    answers = [ReusableAnswer(id="c1", question="Country", answer="United States")]

    plan = plan_form_fill("https://careers.example.test/apply", fields, CandidateProfile(), answers)

    assert plan.actions == []
    assert [f.field_id for f in plan.unknown_fields] == ["sp"]


def test_workday_state_field_is_not_filled_with_the_country() -> None:
    # Live regression: Workday names its State field "countryRegion", so the
    # saved "Country -> United States" claimed it by bare substring match and
    # the run reported 'State: No dropdown option matched "United States of
    # America"'. A country name must never reach a state dropdown.
    fields = [
        FormField(
            id="state", label="State", name="countryRegion", field_type="select", required=True,
            options=[FormOption(value="TX", label="Texas"),
                     FormOption(value="CA", label="California")],
        ),
        FormField(
            id="country", label="Country", name="country", field_type="select", required=True,
            options=[FormOption(value="USA", label="United States of America")],
        ),
    ]
    answers = [
        ReusableAnswer(id="c1", question="Country", answer="United States"),
        ReusableAnswer(id="s1", question="State / Territory", answer="Texas"),
    ]

    plan = plan_form_fill("https://swinerton.wd1.myworkdayjobs.test", fields, CandidateProfile(), answers)

    assert {a.field_id: a.value for a in plan.actions} == {"state": "TX", "country": "USA"}
    assert plan.unknown_fields == []


def history_profile() -> CandidateProfile:
    from applypilot.models import EducationEntry, ExperienceEntry

    return CandidateProfile(
        education=[
            EducationEntry(school="University of North Texas", degree="M.S.",
                           field_of_study="Artificial Intelligence"),
            EducationEntry(school="IIITDM Kurnool", degree="B.Tech.",
                           field_of_study="Mechanical Engineering"),
        ],
        experience=[
            ExperienceEntry(company="HCLTech", title="Artificial Intelligence Engineer"),
            ExperienceEntry(company="Innomatics Research Labs", title="Data Scientist Trainee"),
        ],
    )


def test_repeating_education_and_experience_blocks_are_filled_in_order() -> None:
    # The gap against a mature autofill tool: employer forms ask for history
    # one block at a time ("1 of 2 Education"), and every block was left blank
    # because the profile had no structured history at all.
    fields = []
    for index in (1, 2):
        fields += [
            FormField(id=f"edu{index}-school", label="School"),
            FormField(id=f"edu{index}-degree", label="Degree"),
            FormField(id=f"edu{index}-field", label="Field of Study"),
        ]
    for index in (1, 2):
        fields += [
            FormField(id=f"exp{index}-company", label="Company"),
            FormField(id=f"exp{index}-title", label="Job Title"),
        ]

    plan = plan_form_fill("https://jobs.ashbyhq.test/x", fields, history_profile(), [])

    assert {a.field_id: a.value for a in plan.actions} == {
        "edu1-school": "University of North Texas",
        "edu1-degree": "M.S.",
        "edu1-field": "Artificial Intelligence",
        "edu2-school": "IIITDM Kurnool",
        "edu2-degree": "B.Tech.",
        "edu2-field": "Mechanical Engineering",
        "exp1-company": "HCLTech",
        "exp1-title": "Artificial Intelligence Engineer",
        "exp2-company": "Innomatics Research Labs",
        "exp2-title": "Data Scientist Trainee",
    }
    assert plan.unknown_fields == []


def test_more_blocks_than_saved_history_are_asked_not_invented() -> None:
    # A third education block has no third school to draw on, so it must come
    # back as a question rather than be filled with someone else's data.
    fields = [FormField(id=f"edu{i}-school", label="School", required=True) for i in (1, 2, 3)]

    plan = plan_form_fill("https://jobs.ashbyhq.test/x", fields, history_profile(), [])

    assert [a.field_id for a in plan.actions] == ["edu1-school", "edu2-school"]
    assert [u.field_id for u in plan.unknown_fields] == ["edu3-school"]


def test_history_never_answers_a_legal_or_eligibility_question() -> None:
    # Live regression from a Bausch + Lomb application: the repeating-history
    # mapper claimed any label containing "company", "position" or "degree",
    # so a sponsorship question was answered "HCLTech", a non-compete question
    # with a past employer, and a "Bachelor's degree?" question with "M.S.".
    # Wrong answers to legal questions must never reach an employer.
    from applypilot.models import EducationEntry, ExperienceEntry

    profile = CandidateProfile(
        education=[EducationEntry(school="University of North Texas", degree="M.S.")],
        experience=[
            ExperienceEntry(company="HCLTech", title="AI Engineer"),
            ExperienceEntry(company="Innomatics Research Labs", title="Data Scientist Trainee"),
        ],
    )
    yes_no = [FormOption(value="Yes", label="Yes"), FormOption(value="No", label="No")]
    questions = [
        "Do you now or will you in the future require company sponsorship for employment?",
        "Are you under any non-compete agreement with a previous employer?",
        "Are you under any confidentiality agreement?",
        "Do you have a Bachelor's degree or higher?",
    ]
    fields = [
        FormField(id=f"q{i}", label=text, field_type="select", required=True, options=yes_no)
        for i, text in enumerate(questions)
    ]
    # Real history labels alongside them must still fill.
    fields += [
        FormField(id="company", label="Company"),
        FormField(id="school", label="School"),
    ]

    plan = plan_form_fill("https://careers.example.test/apply", fields, profile, [])

    values = {action.field_id: action.value for action in plan.actions}
    assert values == {"company": "HCLTech", "school": "University of North Texas"}
    assert [field.field_id for field in plan.unknown_fields] == ["q0", "q1", "q2", "q3"]


def test_address_line_1_answer_does_not_fill_address_line_2() -> None:
    # Live regression: "Address Line 1" and "Address Line 2" are 93% similar,
    # so the saved street address was copied into the second line too.
    fields = [
        FormField(id="a1", label="Address Line 1"),
        FormField(id="a2", label="Address Line 2"),
    ]
    answers = [ReusableAnswer(id="a", question="Address Line 1", answer="1710 Northstar Rd")]

    plan = plan_form_fill("https://careers.example.test/apply", fields, CandidateProfile(), answers)

    assert {a.field_id: a.value for a in plan.actions} == {"a1": "1710 Northstar Rd"}
    assert [f.field_id for f in plan.unknown_fields] == ["a2"]


def test_conditional_follow_up_fields_are_left_for_the_user() -> None:
    # "If yes, what department and what country?" only applies when a previous
    # answer was yes; it was being filled with the saved country.
    profile = CandidateProfile(country="United States")
    fields = [
        FormField(id="country", label="Country", required=True),
        FormField(id="dept", label="If yes, what department and what country?"),
        FormField(id="visa", label="If yes, please indicate Visa status"),
    ]

    plan = plan_form_fill("https://careers.example.test/apply", fields, profile, [])

    assert {a.field_id: a.value for a in plan.actions} == {"country": "United States"}
    assert sorted(f.field_id for f in plan.unknown_fields) == ["dept", "visa"]


def test_a_placeholder_option_is_never_selected() -> None:
    # A dropdown's "No Selection" row is not an answer; choosing it submits a
    # non-answer that reads as a deliberate one.
    profile = CandidateProfile(requires_sponsorship=False)
    field = FormField(
        id="sponsor",
        label="Do you now or will you in the future require company sponsorship?",
        field_type="select", required=True,
        options=[FormOption(value="", label="No Selection"),
                 FormOption(value="Yes", label="Yes"),
                 FormOption(value="No", label="No")],
    )

    plan = plan_form_fill("https://careers.example.test/apply", [field], profile, [])

    assert plan.actions[0].value == "No"

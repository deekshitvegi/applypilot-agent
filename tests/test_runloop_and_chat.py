"""Regressions 10 (the overwritten failure), 14 (the guard that reset), 17
(the questionnaire that wrote nothing), and the chat rules."""

from __future__ import annotations

import pytest

from applypilot import chat, runloop
from applypilot.models import (
    ActionResult,
    ControlKind,
    FieldObservation,
    Option,
    Outcome,
    PageObservation,
    Profile,
    RunState,
)


def field(label, control=ControlKind.TEXT, options=None, required=False, fingerprint=None):
    return FieldObservation(
        fingerprint=fingerprint or f"fp:{label}",
        label=label,
        control=control,
        options=[Option(label=o, value=o) for o in (options or [])],
        required=required,
        options_source="native" if options else "none",
    )


@pytest.fixture
def profile():
    return Profile(
        facts={
            "full_name": "Deekshitth Vegi",
            "email": "someone@example.com",
            "phone": "5125550147",
            "state": "Texas",
            "country": "United States",
            "requires_sponsorship": "No",
        }
    )


# ---------------------------------------------------------------------------
# 10. A recorded failure is not overwritten by a weaker claim of success.
# ---------------------------------------------------------------------------


def test_a_failure_survives_an_unverifiable_success():
    failed = ActionResult(
        fingerprint="a", outcome=Outcome.FAILED, signal="hidden_backing_input",
        evidence="the page holds nothing for this control",
    )
    unverifiable = ActionResult(
        fingerprint="a", outcome=Outcome.VERIFIED, signal="none",
        evidence="read back from the box the executor typed into",
    )
    assert runloop.merge_result(failed, unverifiable) is failed


def test_a_failure_is_replaced_by_an_authoritative_success():
    failed = ActionResult(fingerprint="a", outcome=Outcome.FAILED, signal="native_value")
    verified = ActionResult(
        fingerprint="a", outcome=Outcome.VERIFIED, signal="hidden_backing_input"
    )
    assert runloop.merge_result(failed, verified) is verified


def test_an_attempt_does_not_downgrade_a_verified_result():
    verified = ActionResult(fingerprint="a", outcome=Outcome.VERIFIED, signal="native_value")
    attempted = ActionResult(fingerprint="a", outcome=Outcome.ATTEMPTED, signal="none")
    assert runloop.merge_result(verified, attempted) is verified


def test_the_four_verdicts_stay_distinct():
    results = [
        ActionResult(fingerprint="a", outcome=Outcome.VERIFIED, signal="native_value"),
        ActionResult(fingerprint="b", outcome=Outcome.ACCEPTED, signal="rendered_value"),
        ActionResult(fingerprint="c", outcome=Outcome.ATTEMPTED, signal="none"),
        ActionResult(fingerprint="d", outcome=Outcome.FAILED, signal="native_select"),
    ]
    summary = runloop.summarise(results, [])
    assert "1 verified" in summary
    assert "accepted but not what I asked for" in summary
    assert "filled but not verifiable" in summary
    assert "1 failed" in summary


# ---------------------------------------------------------------------------
# 14. The stall guard is part of the run, so resuming does not reset it.
# ---------------------------------------------------------------------------


def test_an_unchanging_page_eventually_stops_the_run():
    state = RunState(phase="filling")
    for _ in range(runloop.STALL_LIMIT + 1):
        runloop.note_observation(state, "same-signature")
    assert runloop.is_stalled(state)


def test_resuming_does_not_hand_a_stuck_run_fresh_retries():
    state = RunState(phase="filling")
    for _ in range(runloop.STALL_LIMIT + 1):
        runloop.note_observation(state, "same-signature")

    for _ in range(3):
        state = runloop.resume(state)
        assert state.phase == "blocked", "a stuck run must stay stuck across resumes"
        assert runloop.is_stalled(state)

    assert "stopped rather than keep trying" in state.message


def test_the_page_actually_changing_clears_the_guard():
    state = RunState(phase="filling")
    for _ in range(runloop.STALL_LIMIT + 1):
        runloop.note_observation(state, "same-signature")
    runloop.note_observation(state, "a-different-signature")
    assert not runloop.is_stalled(state)


def test_the_applicant_stepping_in_clears_the_guard():
    state = RunState(phase="filling")
    for _ in range(runloop.STALL_LIMIT + 1):
        runloop.note_observation(state, "same")
    state = runloop.resume(state)
    assert state.phase == "blocked"
    state = runloop.clear_stall(state)
    assert state.phase == "scanning"
    assert not runloop.is_stalled(state)


# ---------------------------------------------------------------------------
# 17. Answers go onto the page as they are resolved, not once every question
#     has one.
# ---------------------------------------------------------------------------


def test_answers_are_planned_even_when_other_questions_are_outstanding(profile):
    observation = PageObservation(
        url="https://boards.greenhouse.io/acme/jobs/1",
        fields=[
            field("Name", required=True),
            field("Email", required=True),
            field("Describe your proudest project", ControlKind.TEXTAREA, required=True),
            field("Will you require visa sponsorship?", ControlKind.SELECT, ["Yes", "No"], True),
        ],
    )
    plan = runloop.plan_page(observation, profile)
    assert len(plan.questions) == 1
    assert {a.value for a in plan.answers} == {
        "Deekshitth Vegi", "someone@example.com", "No"
    }
    assert len(plan.actions) == 3, "the answers we have go on the page now"


def test_the_checklist_says_where_every_field_stands(profile):
    observation = PageObservation(
        fields=[
            field("Name", required=True),
            field("Describe your proudest project", ControlKind.TEXTAREA, required=True),
            field("Middle Name"),
        ]
    )
    plan = runloop.plan_page(observation, profile)
    results = [
        ActionResult(
            fingerprint="fp:Name", outcome=Outcome.VERIFIED, signal="native_value",
            observed="Deekshitth Vegi", evidence="read back from native_value",
        )
    ]
    checklist = {item.label: item for item in runloop.build_checklist(observation, plan, results)}
    assert checklist["Name"].state == "verified"
    assert checklist["Describe your proudest project"].state == "needs_you"
    assert checklist["Middle Name"].state == "skipped"


def test_a_captcha_challenge_blocks_and_says_so(profile):
    observation = PageObservation(fields=[field("Name")], captcha="challenge")
    plan = runloop.plan_page(observation, profile)
    assert any("will not touch it" in note for note in plan.notes)
    state = RunState()
    assert runloop.next_phase(state, observation, plan, []) == "blocked"


def test_a_captcha_badge_does_not_block(profile):
    observation = PageObservation(
        fields=[field("Name")], captcha="badge_only", submit_controls=[{"text": "Submit"}]
    )
    plan = runloop.plan_page(observation, profile)
    assert plan.notes == []
    assert runloop.next_phase(RunState(), observation, plan, []) != "blocked"


# ---------------------------------------------------------------------------
# Chat: an instruction about a visible field always ends in something scoped.
# ---------------------------------------------------------------------------


def test_change_my_last_answer_to_no(profile):
    fields = [field("Will you require sponsorship?", ControlKind.SELECT, ["Yes", "No"])]
    outcome = chat.interpret(
        "change my last answer to No", fields,
        profile=profile, last_fingerprint=fields[0].fingerprint,
    )
    assert outcome.kind == "action"
    assert outcome.action.kind == "choose"
    assert outcome.action.option_label == "No"


def test_state_texas(profile):
    fields = [field("State / Province", ControlKind.SELECT, ["Texas", "Utah"])]
    outcome = chat.interpret("state texas", fields, profile=profile)
    assert outcome.kind == "action"
    assert outcome.action.option_label == "Texas"
    assert outcome.fingerprint == fields[0].fingerprint


def test_middle_name_kumar(profile):
    fields = [field("First Name"), field("Middle Name"), field("Last Name")]
    outcome = chat.interpret("middle name Kumar", fields, profile=profile)
    assert outcome.kind == "action"
    assert outcome.action.kind == "fill"
    assert outcome.action.value == "Kumar"
    assert outcome.fingerprint == "fp:Middle Name"


def test_an_instruction_about_a_visible_field_is_never_just_prose(profile):
    fields = [
        field("First Name"),
        field("Country", ControlKind.SELECT, ["United States", "Canada"]),
        field("Willing to relocate?", ControlKind.RADIO, ["Yes", "No"]),
    ]
    for said in (
        "first name Deekshitth",
        "country United States",
        "set country to Canada",
        "willing to relocate? Yes",
        "change my last answer to No",
    ):
        outcome = chat.interpret(
            said, fields, profile=profile, last_fingerprint="fp:Willing to relocate?"
        )
        assert outcome.is_scoped, f"{said!r} produced {outcome.kind}: {outcome.message}"


def test_a_value_the_control_does_not_offer_becomes_a_choice_card(profile):
    fields = [field("State", ControlKind.SELECT, ["Texas", "Tennessee", "Utah"])]
    outcome = chat.interpret("state Tejas", fields, profile=profile)
    assert outcome.kind == "choices"
    assert outcome.options
    assert "which of these" in outcome.message.lower()


def test_an_unrecognisable_instruction_asks_one_focused_question(profile):
    fields = [field("First Name")]
    outcome = chat.interpret("do the thing with the stuff", fields, profile=profile)
    assert outcome.kind == "clarify"
    assert "which field" in outcome.message.lower()


def test_a_fact_no_field_asks_for_is_saved_for_next_time(profile):
    fields = [field("First Name")]
    outcome = chat.interpret("salary expectation 175000", fields, profile=profile)
    assert outcome.kind == "control"
    assert outcome.fact_key == "salary_expectation"
    assert outcome.value == "175000"


def test_stop_is_a_control_not_a_conversation(profile):
    outcome = chat.interpret("stop", [], profile=profile)
    assert outcome.kind == "control"
    assert outcome.value == "stop"


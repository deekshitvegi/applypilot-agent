"""The state machine that works through an application.

Small on purpose. Everything interesting lives in the mapper, the injected
functions and the routing rules; what is left here is deciding what to do next
and remembering honestly what has already happened.

Two things in this file exist because of specific failures:

* a result that failed is not overwritten by a later, weaker claim of success;
* the stall guard is part of the saved run, so stopping and resuming does not
  hand a stuck run a fresh set of retries and let it loop forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .mapper import Resolution, _entry_context, resolve_page, usable_options
from .models import (
    ActionResult,
    Answer,
    ChecklistItem,
    FieldObservation,
    Operation,
    Outcome,
    PageObservation,
    PendingQuestion,
    PlannedAction,
    Profile,
    RunState,
)
from .models import ControlKind as CK
from .text import pretty_label

#: Every signal verify.js can return except "none". A result carrying one of
#: these was read from state the page owns.
AUTHORITATIVE_SIGNALS = frozenset(
    {
        "native_select",
        "native_checked",
        "native_value",
        "native_file_list",
        "hidden_backing_input",
        "aria_state",
        "aria_selected_option",
        "aria_activedescendant",
        "page_data_state",
        "page_class_state",
        "rendered_value",
    }
)

_OUTCOME_RANK = {
    Outcome.ATTEMPTED: 0,
    Outcome.ACCEPTED: 1,
    Outcome.FAILED: 2,
    Outcome.VERIFIED: 3,
}

#: How many times the same page may be observed unchanged before the run stops
#: and asks for help instead of trying the same thing again.
STALL_LIMIT = 3

#: How many times a single field may be re-filled after the page rebuilds it.
REFILL_LIMIT = 3


def merge_result(previous: ActionResult | None, new: ActionResult) -> ActionResult:
    """Combine two readings of the same control, honestly.

    A failure that has been recorded stands until something authoritative says
    otherwise. It was once overwritten by a "success" that had read back the
    agent's own typing, which turned a field the page had rejected into a field
    the run reported as done.
    """
    if previous is None:
        return new
    if previous.outcome is Outcome.FAILED:
        if new.outcome is Outcome.VERIFIED and new.signal in AUTHORITATIVE_SIGNALS:
            return new
        return previous
    if _OUTCOME_RANK[new.outcome] >= _OUTCOME_RANK[previous.outcome]:
        return new
    return previous


def merge_all(results: list[ActionResult]) -> list[ActionResult]:
    merged: dict[str, ActionResult] = {}
    for result in results:
        merged[result.fingerprint] = merge_result(merged.get(result.fingerprint), result)
    return list(merged.values())


@dataclass
class Plan:
    actions: list[PlannedAction] = field(default_factory=list)
    questions: list[PendingQuestion] = field(default_factory=list)
    answers: list[Answer] = field(default_factory=list)
    skipped: list[tuple[FieldObservation, str]] = field(default_factory=list)
    needs_options: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _action_for(field_obs: FieldObservation, answer: Answer) -> PlannedAction:
    if field_obs.control is CK.CHECKBOX:
        kind = "check"
    elif field_obs.operation is Operation.TYPE_TO_SEARCH:
        # It offers nothing until something is typed, so opening it and
        # looking for a list finds an empty popup. Typing is how this one is
        # worked; the suggestion it raises is then picked and read back.
        kind = "fill"
    elif field_obs.control in {CK.SELECT, CK.RADIO, CK.COMBOBOX, CK.MULTISELECT}:
        kind = "choose"
    elif field_obs.control is CK.FILE:
        kind = "upload"
    else:
        kind = "fill"
    return PlannedAction(
        kind=kind,
        fingerprint=field_obs.fingerprint,
        value=answer.value,
        option_label=answer.value if kind == "choose" else "",
        reason=answer.reason,
    )


def plan_page(
    observation: PageObservation,
    profile: Profile,
    learned: dict[str, str] | None = None,
) -> Plan:
    """Decide what to do with every field on the page.

    Answers are written as they are resolved rather than held back until every
    question has one -- a questionnaire that wrote nothing until it was complete
    left every field empty and asked about all of them again.
    """
    result = Plan()
    resolutions: list[Resolution] = resolve_page(observation.fields, profile, learned)

    for resolution in resolutions:
        observed = resolution.field
        if resolution.answer is not None:
            result.answers.append(resolution.answer)
            result.actions.append(_action_for(observed, resolution.answer))
            continue
        if resolution.question is not None:
            question = resolution.question
            if question.options_pending:
                # Its choices live behind a popup only that control owns, and
                # some native selects hold nothing until they are touched.
                # Either way they get opened and read before anyone is asked --
                # handing back a text box to type a dropdown answer into is not
                # an answer to the question.
                result.needs_options.append(observed.fingerprint)
            result.questions.append(question)
            continue
        result.skipped.append((observed, resolution.skipped))

    if observation.captcha == "challenge":
        result.notes.append(
            "There is a CAPTCHA on this page waiting for a person. I will not touch it."
        )
    result.actions = _answerable_first(result.actions, observation)
    return result


def _answerable_first(
    actions: list[PlannedAction],
    observation: PageObservation,
) -> list[PlannedAction]:
    """Fields that can be answered now, before the ones that cannot yet.

    A State list holds nothing but "Choose" until a Country is picked, so
    reaching it first meant three goes at putting Texas into a list of one
    placeholder -- three failures on screen -- before Country was set and the
    list finally existed.

    Nothing here knows about States or Countries. A control offering no real
    option yet is a control whose turn has not come, whatever it asks about.
    """
    fields = {f.fingerprint: f for f in observation.fields}

    def waiting(action: PlannedAction) -> bool:
        observed = fields.get(action.fingerprint)
        if observed is None or observed.control not in {CK.SELECT, CK.COMBOBOX, CK.MULTISELECT}:
            return False
        # Nothing real on offer yet -- either the list is waiting on another
        # field, or its choices have still to be opened. Either way it is not
        # the thing to do first, and only the order changes: nothing is dropped.
        return not usable_options(observed)

    return [a for a in actions if not waiting(a)] + [a for a in actions if waiting(a)]


def build_checklist(
    observation: PageObservation,
    plan: Plan,
    results: list[ActionResult],
) -> list[ChecklistItem]:
    """One row per field, saying exactly where it stands."""
    by_fingerprint = {r.fingerprint: r for r in results}
    questions = {q.fingerprint for q in plan.questions}
    skipped = {f.fingerprint: reason for f, reason in plan.skipped}
    answers = {a.fingerprint: a for a in plan.answers}

    items: list[ChecklistItem] = []
    for observed in observation.fields:
        if not observed.visible:
            continue
        result = by_fingerprint.get(observed.fingerprint)
        label = pretty_label(observed.display_label or observed.attr_label)
        where = _entry_context(observed)
        if result is not None:
            state = {
                Outcome.VERIFIED: "verified",
                Outcome.ACCEPTED: "attempted",
                Outcome.ATTEMPTED: "attempted",
                Outcome.FAILED: "failed",
            }[result.outcome]
            items.append(
                ChecklistItem(
                    fingerprint=observed.fingerprint,
                    label=label,
                    section=where,
                    state=state,
                    value=result.observed or result.requested,
                    detail=result.evidence,
                    required=observed.required,
                )
            )
        elif observed.fingerprint in questions:
            question = next(q for q in plan.questions if q.fingerprint == observed.fingerprint)
            items.append(
                ChecklistItem(
                    fingerprint=observed.fingerprint,
                    label=label,
                    section=where,
                    state="needs_you",
                    detail=question.reason,
                    required=observed.required,
                )
            )
        elif observed.fingerprint in skipped:
            items.append(
                ChecklistItem(
                    fingerprint=observed.fingerprint,
                    label=label,
                    section=where,
                    state="skipped",
                    detail=skipped[observed.fingerprint],
                    required=observed.required,
                )
            )
        elif observed.fingerprint in answers:
            items.append(
                ChecklistItem(
                    fingerprint=observed.fingerprint,
                    label=label,
                    section=where,
                    state="planned",
                    value=answers[observed.fingerprint].value,
                    detail="planned but not carried out yet",
                    required=observed.required,
                )
            )
    return items


def note_observation(state: RunState, signature: str) -> RunState:
    """Record that the page was looked at, and whether anything moved."""
    if signature and signature == state.last_signature:
        state.no_progress_count += 1
    else:
        state.no_progress_count = 0
        state.last_signature = signature
        if signature and signature not in state.seen_signatures:
            state.seen_signatures.append(signature)
    return state


def is_stalled(state: RunState) -> bool:
    return state.no_progress_count >= STALL_LIMIT


def resume(state: RunState) -> RunState:
    """Pick a run back up without handing it a fresh set of retries.

    The stall guard used to live in a local variable, so stopping and starting
    again reset it and the same two steps repeated for as long as anyone let
    them. It is part of the saved run now, and only the page actually changing
    clears it.
    """
    state.extra["resumed"] = int(state.extra.get("resumed", 0)) + 1
    if is_stalled(state):
        state.phase = "blocked"
        state.message = (
            "This page has not changed after several attempts, so I have stopped rather "
            "than keep trying the same thing. Tell me what to do differently, or take "
            "over on the page and I will pick up from whatever it looks like then."
        )
    elif state.phase in {"idle", "done"}:
        state.phase = "scanning"
    return state


def clear_stall(state: RunState) -> RunState:
    """Called when the applicant has actually done something to move things on."""
    state.no_progress_count = 0
    state.last_signature = ""
    if state.phase == "blocked":
        state.phase = "scanning"
        state.message = ""
    return state


def summarise(results: list[ActionResult], questions: list[PendingQuestion]) -> str:
    """One sentence about where things stand, using the four verdicts as-is."""
    counts = dict.fromkeys(Outcome, 0)
    for result in results:
        counts[result.outcome] += 1
    parts = []
    if counts[Outcome.VERIFIED]:
        parts.append(f"{counts[Outcome.VERIFIED]} verified")
    if counts[Outcome.ACCEPTED]:
        parts.append(f"{counts[Outcome.ACCEPTED]} accepted but not what I asked for")
    if counts[Outcome.ATTEMPTED]:
        parts.append(f"{counts[Outcome.ATTEMPTED]} filled but not verifiable")
    if counts[Outcome.FAILED]:
        parts.append(f"{counts[Outcome.FAILED]} failed")
    if questions:
        parts.append(f"{len(questions)} waiting on you")
    return ", ".join(parts) if parts else "nothing to do on this page"


def next_phase(
    state: RunState,
    observation: PageObservation,
    plan: Plan,
    results: list[ActionResult],
) -> str:
    """Where the run goes next."""
    if observation.captcha == "challenge":
        return "blocked"
    if is_stalled(state):
        return "blocked"
    if plan.questions:
        return "waiting_for_you"
    if any(r.outcome is Outcome.FAILED for r in results):
        return "filling"
    if observation.next_controls:
        return "advancing"
    if observation.submit_controls:
        return "ready_to_submit"
    return "done"

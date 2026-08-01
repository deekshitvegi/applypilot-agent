"""Regression 75: a step whose questions were all read as optional.

None of them is marked required in any way a machine can see until the form has
been submitted once -- no attribute, and the asterisk lives in a paragraph above
the buttons rather than on a label of their own. So they were left blank,
continued past, rejected by the form, and never asked about.

What the page says when it rejects them is the evidence.
"""

from __future__ import annotations

import pytest

from applypilot.models import PageObservation, Profile
from applypilot.runloop import plan_page

pytestmark = pytest.mark.browser


def observe(page) -> PageObservation:
    return PageObservation.model_validate(page.evaluate("() => ApplyPilot.scan.run()"))


def press_next(page) -> None:
    page.evaluate("() => document.getElementById('next').click()")


def test_before_the_form_complains_nothing_is_known_to_be_required(open_fixture):
    """The starting condition, and why nothing was asked."""
    page = open_fixture("validated_questions.html")
    assert not any(f.required for f in observe(page).fields)


def test_a_form_saying_it_wants_an_answer_makes_the_field_required(open_fixture):
    page = open_fixture("validated_questions.html")
    press_next(page)

    required = {f.name for f in observe(page).fields if f.required}
    assert required == {"employed_before", "arbitration"}, required


def test_every_required_field_is_asked_about_and_none_left_blank(open_fixture):
    """"7 left blank" and no question is the failure this prevents."""
    page = open_fixture("validated_questions.html")
    press_next(page)

    plan = plan_page(observe(page), Profile())
    observation = observe(page)
    names = {f.fingerprint: f.name for f in observation.fields}

    asked = {names.get(q.fingerprint) for q in plan.questions}
    assert "employed_before" in asked, asked
    assert "arbitration" in asked, asked

    left_blank = {names.get(f.fingerprint) for f, _ in plan.skipped}
    assert "employed_before" not in left_blank
    assert "arbitration" not in left_blank
    # The genuinely optional one is still left alone.
    assert "extra" in left_blank, left_blank


def test_an_agreement_is_asked_and_never_ticked_on_your_behalf(open_fixture):
    page = open_fixture("validated_questions.html")
    press_next(page)

    plan = plan_page(observe(page), Profile())
    names = {f.fingerprint: f.name for f in observe(page).fields}
    assert "arbitration" not in {names.get(a.fingerprint) for a in plan.actions}
    assert page.evaluate("() => document.querySelector('[name=arbitration]').checked") is False


def test_an_answered_question_stops_being_complained_about(open_fixture):
    page = open_fixture("validated_questions.html")
    press_next(page)
    page.evaluate("() => document.querySelector('[value=No]').click()")
    press_next(page)

    required = {f.name for f in observe(page).fields if f.required}
    assert "employed_before" not in required, required
    assert "arbitration" in required


def test_the_complaints_only_exist_after_a_refused_continue(open_fixture):
    """Which is the one moment the panel has to look again.

    Read off the live application: before Next is pressed the complaint element
    is display:none and nothing on the page says those questions are required.
    Pressing Next is what makes the form state its case -- and stopping there
    without looking again is how a step ended up announcing it had stopped while
    three required questions sat unasked and invisible.
    """
    page = open_fixture("validated_questions.html")
    before = {f.name for f in observe(page).fields if f.required}
    assert before == set(), before

    press_next(page)
    after = {f.name for f in observe(page).fields if f.required}
    assert after == {"employed_before", "arbitration"}, after

    plan = plan_page(observe(page), Profile())
    observation = observe(page)
    names = {f.fingerprint: f.name for f in observation.fields}
    asked = {names.get(q.fingerprint) for q in plan.questions}
    assert {"employed_before", "arbitration"} <= asked, asked

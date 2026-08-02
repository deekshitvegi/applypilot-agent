"""Regression 109: asking about a field the page had already answered.

"Login: required and not answered yet" appeared while the login sat in the box,
which reads as the tool being unable to see the page at all. A required field
the page is holding a value for wants nothing from anybody.
"""

from __future__ import annotations

from applypilot.mapper import resolve_field
from applypilot.models import ControlKind, FieldObservation, Profile


def field(**kw) -> FieldObservation:
    base = {
        "fingerprint": "f", "label": "Login", "display_label": "Login",
        "control": ControlKind.TEXT, "visible": True, "required": True,
    }
    base.update(kw)
    return FieldObservation(**base)


def test_a_filled_required_field_is_not_asked_about():
    r = resolve_field(field(value="deekshitvegibunnyus@gmail.com"), Profile())
    assert r.question is None
    assert r.skipped == "already answered on the page"


def test_an_empty_required_field_is_still_asked_about():
    r = resolve_field(field(value=""), Profile())
    assert r.question is not None
    assert "not answered yet" in r.question.reason


def test_a_placeholder_is_not_an_answer():
    """"— Make a Selection —" sitting in a box is not an answer."""
    from applypilot.mapper import _already_answered

    assert _already_answered(field(value="— Make a Selection —")) is False
    assert _already_answered(field(value="Please select")) is False
    assert _already_answered(field(value="Denton")) is True


def test_whitespace_is_not_an_answer():
    assert resolve_field(field(value="   "), Profile()).question is not None


def test_a_tick_box_is_answered_by_being_ticked_not_by_holding_text():
    """A checkbox always carries a value string; only checked means answered."""
    from applypilot.mapper import _already_answered

    box = {"label": "Send me job alerts", "display_label": "Send me job alerts",
           "control": ControlKind.CHECKBOX}
    assert _already_answered(field(**box, checked=True, value="on")) is True
    assert _already_answered(field(**box, checked=False, value="on")) is False

"""Choosing an account name is not a fact about anybody.

A page that wants an account gets everything filled except the credentials,
so that only a password and the button are left. That has always covered the
password box. It has to cover the box you would type the account name into as
well, because asking for one is asking someone to start creating the account.
"""

from __future__ import annotations

from applypilot.mapper import resolve_page
from applypilot.models import ControlKind, FieldObservation, Profile


def field(label, control=ControlKind.TEXT, section="", **extra):
    return FieldObservation(
        fingerprint=label.lower().replace(" ", "-"),
        label=label,
        display_label=label,
        control=control,
        section=section,
        visible=True,
        **extra,
    )


PROFILE = Profile(
    facts={
        "first_name": "Deekshitth",
        "last_name": "Vegi",
        "email": "deekshitvegibunny@gmail.com",
    }
)


def resolved(fields):
    out = {}
    for resolution in resolve_page(fields, PROFILE):
        out[resolution.field.label] = resolution
    return out


REGISTRATION = [
    field("Login", section="Create a login", required=True),
    field("Password", control=ControlKind.PASSWORD, section="Create a login", required=True),
    field("First Name", section="Enter your information", required=True),
]


# ---------------------------------------------------------------------------
# 113. The box you choose an account name in is left alone, not asked about.
# ---------------------------------------------------------------------------


def test_the_account_name_box_is_left_to_the_person():
    out = resolved(REGISTRATION)
    login = out["Login"]
    assert login.question is None, "asking for an account name blocks the whole page"
    assert login.answer is None, "an account name is not ours to choose"
    assert "yours" in login.skipped


def test_a_required_account_name_still_raises_no_question():
    """The point of the fix.

    "Login" is required, and required-and-unanswered is normally a question.
    It cannot be one here: no answer exists, so the question could never be
    cleared and everything behind it waited forever.
    """
    out = resolved(REGISTRATION)
    assert out["Login"].question is None


def test_everything_else_on_the_page_is_still_filled():
    out = resolved(REGISTRATION)
    assert out["First Name"].answer is not None
    assert out["First Name"].answer.value == "Deekshitth"


def test_the_password_is_still_left_alone():
    out = resolved(REGISTRATION)
    assert out["Password"].answer is None
    assert "password" in out["Password"].skipped.lower()


# ---------------------------------------------------------------------------
# The two signals are required together.
# ---------------------------------------------------------------------------


def test_a_login_box_with_no_password_anywhere_is_not_a_credential():
    """Without a password to pair with, "Login" is some other kind of box.

    Whatever it turns out to be, it is not half of an account, so it is not
    silently swallowed.
    """
    out = resolved([field("Login", required=True)])
    assert out["Login"].skipped != "choosing an account name is yours, along with the password"


def test_a_question_that_merely_mentions_logging_in_is_untouched():
    fields = [
        field("How did you log in to our system before?", required=True),
        field("Password", control=ControlKind.PASSWORD),
    ]
    out = resolved(fields)
    asked = out["How did you log in to our system before?"]
    assert asked.skipped != "choosing an account name is yours, along with the password"


def test_the_usual_spellings_are_all_recognised():
    for label in ("Username", "User Name", "User ID", "Userid", "Screen Name", "Log In"):
        fields = [field(label, required=True), field("Password", control=ControlKind.PASSWORD)]
        out = resolved(fields)
        assert out[label].question is None, label
        assert "yours" in out[label].skipped, label


def test_an_email_box_is_still_filled_even_beside_a_password():
    """Filling an email address does not begin creating anything."""
    fields = [
        field("Email", section="Create a login", required=True),
        field("Password", control=ControlKind.PASSWORD, section="Create a login"),
    ]
    out = resolved(fields)
    assert out["Email"].answer is not None

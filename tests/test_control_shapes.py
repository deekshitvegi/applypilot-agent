"""What a control is made of, and what you would have to do to answer it.

Regression 121. Three hundred and twenty controls across the corpus call
themselves a combobox; three hundred and ten of them hold no options at all
when the page is read. Treating those as "a list with nothing in it" is what
put a text box on screen for a dropdown question -- asking somebody to type an
answer that was only ever going to be picked from a list the control had not
been opened to show yet.

Every shape in the fixture is copied from a real form.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser

#: label -> how it has to be worked
EXPECTED = {
    "Country": "list_present",
    "Are you open to relocation?": "list_on_open",
    "Location": "type_to_search",
    "Phone country code": "list_present",
    "When can you start a new role?": "date_picker",
    "Are you legally authorized to work in the United States?": "choice_group",
    "First Name": "free_text",
    "Why do you want to work here?": "long_text",
    "Resume": "file",
}


def by_label(observation):
    out = {}
    for field in observation["fields"]:
        label = (field.get("display_label") or field.get("label") or "").strip()
        label = label.rstrip("*").strip()
        out.setdefault(label, field)
    return out


@pytest.mark.parametrize("label,operation", sorted(EXPECTED.items()))
def test_each_shape_is_recognised_for_what_it_takes_to_answer(scan, label, operation):
    _, observation = scan("control_shapes.html")
    found = by_label(observation)
    assert label in found, f"no field labelled {label!r}; saw {sorted(found)}"
    assert found[label].get("operation") == operation


def test_the_two_comboboxes_are_told_apart(scan):
    """The distinction the whole thing exists for.

    Both are an input calling itself a combobox with no options on it. One
    opens onto a list; the other offers nothing until you type, and says so in
    its placeholder. They want opposite treatment.
    """
    found = by_label(scan("control_shapes.html")[1])
    opens = found["Are you open to relocation?"]
    types = found["Location"]
    assert opens["control"] == types["control"] == "combobox"
    assert opens["operation"] == "list_on_open"
    assert types["operation"] == "type_to_search"


def test_a_text_box_backed_by_a_hidden_input_is_a_search(scan):
    """The shape that failed eleven times across four employers.

        <input type="text" name="location" required>
        <input type="hidden" name="selectedLocation">

    Nothing on the visible box announces it: no role, no aria-autocomplete, no
    placeholder to read. Typing into it and stopping leaves the hidden one
    empty, and the hidden one is what the form submits -- so a verified read
    correctly reported that the page held nothing, on a required field, on
    every application that ATS serves.
    """
    found = by_label(scan("control_shapes.html")[1])
    assert found["Current location"]["operation"] == "type_to_search"


def test_an_unrelated_hidden_input_does_not_make_a_search(scan):
    """A CSRF token beside a text box is not that box's answer.

    The pair has to be named for the same thing -- location and
    selectedLocation -- or every form with a hidden token in it would have its
    text boxes worked as searches that offer nothing.
    """
    found = by_label(scan("control_shapes.html")[1])
    assert found["Middle Name"]["operation"] == "free_text"


def test_nothing_on_a_real_form_shape_comes_back_unrecognised(scan):
    _, observation = scan("control_shapes.html")
    unknown = [
        f.get("display_label") or f.get("label")
        for f in observation["fields"]
        if f.get("operation") in (None, "unknown")
    ]
    assert not unknown, f"unrecognised: {unknown}"


def test_a_drawn_list_is_still_asked_to_open_before_anyone_is_asked(scan):
    """A control holding no options is not a control with no options."""
    from applypilot.mapper import needs_its_options_opened
    from applypilot.models import PageObservation

    observation = PageObservation.model_validate(scan("control_shapes.html")[1])
    fields = {
        (f.display_label or f.label).strip().rstrip("*").strip(): f
        for f in observation.fields
    }
    assert needs_its_options_opened(fields["Are you open to relocation?"]) is True
    assert needs_its_options_opened(fields["Location"]) is True
    # This one has said its choices are readable, so it is not poked.
    assert needs_its_options_opened(fields["Country"]) is False


def test_a_one_pixel_file_input_behind_a_dropzone_is_on_the_page(scan):
    """How every modern form does uploads, and it was invisible to us.

    The real input is 1x1 with a styled dropzone drawn around it. The old test
    took the input's label if it had one and gave up when that measured 1x1 --
    and a screen-reader-only label is 1x1 by design. So the resume upload on
    one of the largest hiring systems in the world read as not on the page at
    all, across sixty applications, and nobody was ever asked to attach
    anything because nothing had been found to attach it to.
    """
    found = by_label(scan("control_shapes.html")[1])
    assert "Attach a resume" in found, f"saw {sorted(found)}"
    assert found["Attach a resume"]["control"] == "file"

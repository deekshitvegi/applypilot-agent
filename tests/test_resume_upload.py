"""A dropzone explains itself in a sentence, and a resume is never optional.

Regression 143. On a live Toyota application the resume upload came back
labelled "or" -- the word between the LinkedIn button and the Select File
button -- so nothing matched it, it was read as an optional extra, and the
resume was never attached.
"""

from __future__ import annotations

import pytest

from applypilot.mapper import document_wanted, resolve_field
from applypilot.models import ControlKind, FieldObservation, Profile

DROPZONE = (
    "Upload options Make completing your job application easier by uploading "
    "your resume or CV. Upload either DOC, DOCX, HTML, PDF, or TXT file types (1MB max)"
)


def control(label: str, kind=ControlKind.FILE, required=False) -> FieldObservation:
    return FieldObservation(
        fingerprint="f", label=label, display_label=label,
        control=kind, visible=True, required=required,
    )


@pytest.mark.parametrize(
    "label,expected",
    [
        (DROPZONE, "resume"),
        ("Please upload your resume (Max size: 5 MB)", "resume"),
        ("Attach your CV", "resume"),
        ("Curriculum Vitae", "resume"),
        ("Cover letter", "cover_letter"),
        ("Upload a covering letter", "cover_letter"),
    ],
)
def test_a_file_control_is_read_for_which_document_it_wants(label, expected):
    assert document_wanted(control(label)) == expected


def test_a_dropzone_that_names_no_document_is_not_guessed_at():
    assert document_wanted(control("Drop or select (.doc / .docx / .pdf)")) == ""


@pytest.mark.parametrize("kind", [ControlKind.TEXT, ControlKind.TEXTAREA, ControlKind.SELECT])
def test_nothing_but_a_file_control_is_read_this_way(kind):
    """A sentence mentioning a CV is not a request for one.

    Only a file control goes down this path, because nothing is typed into one
    and the worst a wrong answer can do is attach a document to the wrong slot.
    """
    assert document_wanted(control("Have you read our CV guidelines?", kind)) == ""
    assert document_wanted(control("Tell us about a time you resumed a project", kind)) == ""


# ---------------------------------------------------------------------------
# A document a form will take is never an optional extra.
# ---------------------------------------------------------------------------


def test_an_optional_resume_upload_is_still_put_forward():
    """The failure exactly as it happened.

    Plenty of applications do not mark the resume required, and it was skipped
    in silence -- on a page whose own words were "make completing your job
    application easier by uploading your resume".
    """
    resolution = resolve_field(control(DROPZONE, required=False), Profile())
    assert resolution.question is not None, f"skipped: {resolution.skipped}"
    assert resolution.fact_key == "resume"


def test_one_already_attached_is_left_alone():
    field = control(DROPZONE)
    field = field.model_copy(update={"value": "alex_rivera_resume.pdf"})
    resolution = resolve_field(field, Profile())
    assert resolution.question is None
    assert "already attached" in resolution.skipped


def test_an_ordinary_optional_field_is_still_left_blank():
    """The rule is about documents, not about optional fields in general."""
    resolution = resolve_field(control("Willingness to Travel", ControlKind.TEXT), Profile())
    assert resolution.question is None
    assert resolution.skipped

"""Importing LinkedIn's own data export.

Nothing here signs in to LinkedIn or reads a page. This is the archive LinkedIn
sends when you ask for a copy of your data, which is the applicant's own data by
the route LinkedIn provides for it.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from applypilot import linkedin, onboarding
from applypilot.models import EducationRecord, Profile


def make_archive(**overrides: str) -> bytes:
    files = {
        "Profile.csv": (
            "First Name,Last Name,Geo Location,Websites\n"
            "Alex,Rivera,\"Austin, Texas, United States\",[PERSONAL:https://alex.example]\n"
        ),
        "Email Addresses.csv": (
            "Email Address,Confirmed,Primary,Updated On\n"
            "old@example.test,Yes,No,01 Jan 2020\n"
            "alex@example.test,Yes,Yes,01 Jan 2024\n"
        ),
        "PhoneNumbers.csv": "Extension,Number,Type\n,5125550147,MOBILE\n",
        "Positions.csv": (
            "Company Name,Title,Description,Location,Started On,Finished On\n"
            "Northwind Labs,Machine Learning Engineer,Built retrieval pipelines.,\"Austin, TX\",Jun 2022,\n"
            "Contoso,Data Analyst,Reported on churn.,\"Dallas, TX\",Jan 2020,May 2022\n"
        ),
        "Education.csv": (
            "School Name,Start Date,End Date,Notes,Degree Name,Activities\n"
            "University of Example,2018,2020,,Master's Degree,\n"
        ),
        "Skills.csv": "Name\nPython\nSQL\nPyTorch\n",
    }
    files.update(overrides)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_positions_and_education_come_through():
    extracted = linkedin.extract(make_archive())

    assert [x.company for x in extracted.experience] == ["Northwind Labs", "Contoso"]
    assert extracted.experience[0].title == "Machine Learning Engineer"
    assert extracted.experience[0].current is True, "no finish date means still there"
    assert extracted.experience[1].current is False
    assert extracted.experience[1].end_date == "May 2022"

    assert [e.school for e in extracted.education] == ["University of Example"]
    assert extracted.education[0].degree == "Master's Degree"


def test_the_primary_email_wins():
    extracted = linkedin.extract(make_archive())
    assert extracted.email == "alex@example.test"


def test_name_phone_location_and_website_come_through():
    extracted = linkedin.extract(make_archive())
    assert extracted.name == "Alex Rivera"
    assert extracted.phone == "5125550147"
    assert extracted.location == "Austin, Texas, United States"
    assert extracted.website == "https://alex.example"


def test_a_missing_field_of_study_is_said_rather_than_invented():
    extracted = linkedin.extract(make_archive())
    assert extracted.education[0].field_of_study == ""
    assert any("field of study" in note for note in extracted.notes)


def test_it_merges_without_overwriting_what_you_already_entered():
    profile = Profile(
        facts={"email": "mine@example.test"},
        education=[EducationRecord(school="Somewhere I typed myself")],
    )
    profile, added = onboarding.apply_resume(profile, linkedin.extract(make_archive()))

    assert profile.facts["email"] == "mine@example.test", "what you entered wins"
    assert [e.school for e in profile.education] == ["Somewhere I typed myself"]
    assert profile.experience, "work history was empty, so it was filled"
    assert any("work history" in item for item in added)


def test_something_that_is_not_a_zip_is_refused_with_a_reason():
    with pytest.raises(linkedin.NotALinkedInExport, match="not a .zip"):
        linkedin.extract(b"this is not a zip file")


def test_a_zip_without_linkedin_files_is_refused_with_a_reason():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("holiday-photo.jpg", "not csv")
    with pytest.raises(linkedin.NotALinkedInExport, match="Positions.csv"):
        linkedin.extract(buffer.getvalue())


def test_the_endpoint_imports_and_reports_what_it_read(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("APPLYPILOT_DATA_DIR", str(tmp_path / "data"))
    import applypilot.config as config
    import applypilot.main as main

    importlib.reload(config)
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        response = client.post(
            "/import/linkedin",
            files={"file": ("Basic_LinkedInDataExport.zip", make_archive(), "application/zip")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["experience"]) == 2
        assert body["skills"] == ["Python", "SQL", "PyTorch"]

        profile = client.get("/profile").json()
        assert profile["facts"]["full_name"] == "Alex Rivera"
        assert profile["facts"]["state"] == "Texas"

        refused = client.post(
            "/import/linkedin",
            files={"file": ("resume.docx", b"not a zip", "application/octet-stream")},
        )
        assert refused.status_code == 400
        assert "Get a copy of your data" in refused.json()["detail"]

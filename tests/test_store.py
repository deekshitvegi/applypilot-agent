from pathlib import Path

from applypilot.models import CandidateProfile
from applypilot.store import ProfileStore


def test_profile_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.sqlite3")
    profile = CandidateProfile(
        legal_name="Test Candidate",
        email="candidate@example.test",
        custom_answers={"Are you at least 18 years old?": "Yes"},
    )

    store.save(profile)

    assert store.load() == profile


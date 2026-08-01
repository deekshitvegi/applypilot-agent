"""Regressions 66 to 69: several educations, several jobs, in the right order.

Read off a live application. The first entry of each list carries a checkbox the
others do not, and the later ones carry a remove button the first does not.
Comparing blocks for an exact match therefore found no twins at all, so:

* every entry reported itself as the first one;
* every entry was filled from the first record on file -- the same school twice;
* the count of entries never rose, so the run said "did not add an entry, so I
  stopped adding" while entries piled up on screen.

And a State list holds nothing until a Country is picked, so reaching it first
spent three failures on a list of one placeholder.
"""

from __future__ import annotations

import pytest

from applypilot.models import (
    EducationRecord,
    ExperienceRecord,
    PageObservation,
    PlannedAction,
    Profile,
)
from applypilot.runloop import plan_page

pytestmark = pytest.mark.browser


@pytest.fixture
def profile() -> Profile:
    return Profile(
        education=[
            EducationRecord(
                school="University of North Texas",
                degree="Master's degree",
                field_of_study="Artificial Intelligence",
                end_date="2025",
            ),
            EducationRecord(
                school="IIITDM Kurnool",
                degree="Bachelor's degree",
                field_of_study="Mechanical Engineering",
                end_date="2023",
            ),
        ],
        experience=[
            ExperienceRecord(company="HCLTech", title="Artificial Intelligence Engineer"),
            ExperienceRecord(company="Innomatics Research Labs", title="Data Science Intern"),
        ],
    )


def observe(page) -> PageObservation:
    return PageObservation.model_validate(page.evaluate("() => ApplyPilot.scan.run()"))


def entries_of(observation: PageObservation, needle: str) -> dict[int, str]:
    """Which entry each control saying `needle` belongs to."""
    out = {}
    for observed in observation.fields:
        if needle.lower() in (observed.name or "").lower():
            out[observed.group_index] = observed.name
    return out


def test_an_extra_checkbox_in_the_first_entry_does_not_hide_the_rest(open_fixture):
    page = open_fixture("repeating_entries.html")
    observation = observe(page)

    schools = entries_of(observation, "[school]")
    assert sorted(schools) == [0, 1], schools
    companies = entries_of(observation, "[company]")
    assert sorted(companies) == [0, 1], companies


def test_each_entry_is_filled_from_its_own_record(open_fixture, profile):
    """Both schools came out "University of North Texas" before this."""
    page = open_fixture("repeating_entries.html")
    plan = plan_page(observe(page), profile)

    by_fingerprint = {a.fingerprint: a for a in plan.actions}
    observation = observe(page)
    named = {
        f.name: by_fingerprint[f.fingerprint].value
        for f in observation.fields
        if f.fingerprint in by_fingerprint and f.name
    }
    assert named.get("custom[education][0][school]") == "University of North Texas"
    assert named.get("custom[education][1][school]") == "IIITDM Kurnool"
    assert named.get("custom[experience][0][company]") == "HCLTech"
    assert named.get("custom[experience][1][company]") == "Innomatics Research Labs"


def test_the_entry_count_rises_when_an_entry_is_added(open_fixture):
    """It never rose, so adding stopped after saying it had failed."""
    page = open_fixture("repeating_entries.html")

    def highest(needle):
        return max(entries_of(observe(page), needle), default=-1)

    assert highest("[school]") == 1
    result = page.evaluate(
        "async () => await ApplyPilot.act.addRepeat('+ Add other education')"
    )
    assert result["outcome"] == "verified", result
    assert highest("[school]") == 2
    # The other list is untouched by the education control.
    assert highest("[company]") == 1


def test_a_third_entry_takes_the_third_record(open_fixture, profile):
    page = open_fixture("repeating_entries.html")
    page.evaluate("async () => await ApplyPilot.act.addRepeat('+ Add other education')")

    profile.education.append(EducationRecord(school="Somewhere Else", end_date="2019"))
    observation = observe(page)
    plan = plan_page(observation, profile)

    by_fingerprint = {a.fingerprint: a for a in plan.actions}
    named = {
        f.name: by_fingerprint[f.fingerprint].value
        for f in observation.fields
        if f.fingerprint in by_fingerprint and f.name
    }
    assert named.get("custom[education][2][school]") == "Somewhere Else"


def test_blocks_with_no_numbering_are_still_counted(open_fixture):
    """Not every form says which entry a control belongs to."""
    page = open_fixture("repeating_entries.html")
    page.evaluate(
        """() => {
          for (const el of document.querySelectorAll('[name^="custom[education]"]')) {
            el.setAttribute('name', el.getAttribute('name').replace(/\\[\\d+\\]/, ''));
          }
        }"""
    )
    observation = observe(page)
    schools = {f.group_index for f in observation.fields if "school" in (f.name or "")}
    assert schools == {0, 1}, schools


def test_a_list_with_nothing_in_it_yet_is_never_typed_into(open_fixture, profile):
    """State offers only "Choose" until Country is picked.

    It stays a question with its options still to be opened -- never a text box
    to type "Texas" into -- and Country, which can be answered now, is filled.
    """
    page = open_fixture("repeating_entries.html")
    profile.facts["country"] = "United States"
    profile.facts["state"] = "Texas"

    observation = observe(page)
    plan = plan_page(observation, profile)
    names = {f.fingerprint: f.name for f in observation.fields}

    assert "country" in [names.get(a.fingerprint) for a in plan.actions]
    state = next(q for q in plan.questions if names.get(q.fingerprint) == "state")
    assert state.options == [], "a placeholder row is never offered as an answer"
    assert state.options_pending is True
    assert state.fingerprint in plan.needs_options


def test_an_action_on_an_empty_list_is_left_until_the_others_are_done(open_fixture, profile):
    """Ordering, on its own: nothing here knows what a State is."""
    from applypilot.runloop import _answerable_first

    page = open_fixture("repeating_entries.html")
    observation = observe(page)
    profile.facts["country"] = "United States"
    plan = plan_page(observation, profile)

    names = {f.fingerprint: f.name for f in observation.fields}
    state = next(f for f in observation.fields if f.name == "state")
    country = next(a for a in plan.actions if names.get(a.fingerprint) == "country")

    pretend = PlannedAction(kind="choose", fingerprint=state.fingerprint, option_label="Texas")
    ordered = _answerable_first([pretend, country], observation)
    assert [names.get(a.fingerprint) for a in ordered] == ["country", "state"]


def test_picking_the_country_first_makes_the_state_answerable(open_fixture, profile):
    page = open_fixture("repeating_entries.html")
    profile.facts["country"] = "United States"
    profile.facts["state"] = "Texas"

    observation = observe(page)
    country = next(f for f in observation.fields if f.name == "country")
    picked = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": country.fingerprint, "option_label": "United States"},
    )
    assert picked["outcome"] == "verified", picked

    state = next(f for f in observe(page).fields if f.name == "state")
    result = page.evaluate(
        "async (a) => await ApplyPilot.act.perform(a)",
        {"kind": "choose", "fingerprint": state.fingerprint, "option_label": "Texas"},
    )
    assert result["outcome"] == "verified", result
    assert page.evaluate("() => document.querySelector('select[name=state]').value") == "Texas"

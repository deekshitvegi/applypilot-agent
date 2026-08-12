"""Answering a question about the applicant from what the applicant wrote.

Across 68 real applications, 130 required Yes/No questions went unanswered --
"Do you have hands-on engineering experience with Python and ML frameworks?",
"Are you based in a US timezone?". They were unanswered because the model was
only ever shown a saved answer to compare against, and for these there is none.
Their CV answers them.

The rule that keeps this honest: the model must quote the line it read, and the
quote is checked against the evidence before the answer is offered. A claim
with nothing behind it is refused rather than shown.
"""

from __future__ import annotations

from applypilot import ai
from applypilot.models import Option, Profile

PROFILE = Profile(
    skills=["Python", "PyTorch", "LangChain", "AWS", "Docker"],
    education=[
        {
            "school": "University of North Texas",
            "degree": "Master's Degree",
            "field_of_study": "Artificial Intelligence",
            "start_date": "2023-08",
            "end_date": "2025-05",
        }
    ],
    experience=[
        {
            "company": "HCLTech",
            "title": "AI Engineer",
            "start_date": "2024-02",
            "end_date": "",
            "current": True,
            "description": (
                "- Built retrieval pipelines in Python with PyTorch\n"
                "- Deployed inference services on AWS ECS"
            ),
        }
    ],
)

YES_NO = [Option(label="Yes", value="Yes"), Option(label="No", value="No")]


def run(coro):
    """Drive a coroutine that never really waits.

    These call a stand-in model that answers immediately, so nothing here
    suspends on anything. Driving it by hand avoids an event loop entirely --
    which matters because the browser tests leave one running, and a nested
    loop is an error rather than a wait.
    """
    try:
        coro.send(None)
    except StopIteration as done:
        return done.value
    raise AssertionError("this awaited something real; it was not meant to")


class FakeModel(ai.Model):
    """A model that says whatever the test needs, without a network."""

    def __init__(self, reply: str) -> None:
        super().__init__(api_key="test-key")
        self.reply = reply
        self.prompt = ""

    async def ask(self, prompt: str, *, temperature: float = 0.1) -> str:
        self.prompt = prompt
        return self.reply


def answer(model: FakeModel, question: str, evidence: str | None = None):
    return run(
        ai.answer_from_evidence(
            model,
            question,
            YES_NO,
            ai.evidence_from(PROFILE) if evidence is None else evidence,
        )
    )


# ---------------------------------------------------------------------------
# The evidence is theirs, and only theirs.
# ---------------------------------------------------------------------------


def test_the_evidence_is_the_applicant_s_own_words():
    lines = ai.evidence_from(PROFILE)
    assert "Python, PyTorch" in lines
    assert "AI Engineer at HCLTech" in lines
    assert "Built retrieval pipelines in Python with PyTorch" in lines


def test_an_empty_profile_says_so_rather_than_inventing():
    assert ai.evidence_from(Profile()) == "(nothing recorded)"


# ---------------------------------------------------------------------------
# What it answers, and what it refuses.
# ---------------------------------------------------------------------------


def test_a_question_the_history_answers_is_answered():
    model = FakeModel(
        '{"option": "Yes", '
        '"quote": "Built retrieval pipelines in Python with PyTorch", '
        '"why": "the applicant lists exactly this work"}'
    )
    chosen, why = answer(
        model, "Do you have hands-on engineering experience with Python and ML frameworks?"
    )
    assert chosen is not None and chosen.label == "Yes"
    assert "from your own history" in why


def test_a_quote_that_is_not_in_the_evidence_is_refused():
    """The whole grounding rests on this.

    Without the check, "quote the line" is a request the model can decline
    silently, and an invented qualification reads exactly like a real one.
    """
    model = FakeModel(
        '{"option": "Yes", "quote": "Led a team of 40 engineers", "why": "leadership"}'
    )
    chosen, why = answer(model, "Do you have management experience?")
    assert chosen is None
    assert "could not point at anything you wrote" in why


def test_an_answer_with_no_quote_at_all_is_refused():
    model = FakeModel('{"option": "Yes", "why": "seems likely"}')
    chosen, _ = answer(model, "Do you have 10 years of experience?")
    assert chosen is None


def test_saying_nothing_settles_it_is_a_valid_answer():
    model = FakeModel(
        '{"option": null, "why": "nothing recorded says where they are willing to work"}'
    )
    chosen, why = answer(model, "Are you willing to relocate to Berlin?")
    assert chosen is None
    assert "nothing recorded" in why


def test_an_option_the_page_never_offered_is_refused():
    model = FakeModel('{"option": "Maybe", "quote": "Skills listed: Python", "why": "x"}')
    chosen, _ = answer(model, "Do you know Python?")
    assert chosen is None


def test_a_control_with_nothing_to_choose_between_is_left_alone():
    model = FakeModel('{"option": "Yes", "quote": "Skills listed: Python", "why": "x"}')
    chosen, why = run(ai.answer_from_evidence(model, "Anything?", [], "Skills listed: Python"))
    assert chosen is None
    assert "no options" in why


def test_the_prompt_forbids_estimating():
    model = FakeModel('{"option": null, "why": "-"}')
    answer(model, "How many years?", "Skills listed: Python")
    assert "do not estimate" in model.prompt
    assert "in the applicant's name" in model.prompt

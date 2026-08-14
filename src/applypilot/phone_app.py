"""The question queue, and the small web app a phone answers it from.

Telegram works and it sends the question to somebody else's servers on the way.
This does not: the page is served by the service already running on the
applicant's own machine, the phone reaches it over the home network, and the
question and the answer never leave the building.

Added to a phone's home screen it behaves like an app, because that is what a
progressive web app is -- a page with a manifest saying so. It keeps a
connection open while it is on screen, so a question appears the moment it is
asked, and asks the phone to make a noise about it.

What it cannot do is wake a phone that is locked with the app closed. That
needs a push service, which means somebody else's servers again, and the whole
point of this file is not having any. The honest shape of the compromise is in
`phone_push.py`, where the push carries no content at all -- only a nudge to
open the app, which then asks this service what the question was.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class Pending:
    """One question waiting for an answer, and the answer when it comes."""

    id: str
    label: str
    options: tuple[str, ...] = ()
    host: str = ""
    fact_key: str = ""
    asked_at: float = field(default_factory=time.time)
    answer: str = ""
    answered: bool = False
    #: Set when the applicant said to leave it blank, which is an answer about
    #: the question and not an absence of one.
    skipped: bool = False

    def as_json(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "options": list(self.options),
            "host": self.host,
            "waiting_for": int(time.time() - self.asked_at),
        }


class Queue:
    """Questions waiting on a person, oldest first.

    One at a time on purpose. A phone showing eleven questions at once is a
    form, and the applicant already has one of those open on a laptop; the
    point of this is answering the one thing that is blocking a run.
    """

    def __init__(self) -> None:
        self._pending: list[Pending] = []
        self._lock = threading.Lock()
        #: Raised whenever anything changes, so a waiting request can return
        #: at once instead of asking again in a second.
        self._changed = threading.Condition(self._lock)
        self._next = 1

    def ask(self, label: str, options: tuple[str, ...], host: str, fact_key: str) -> Pending:
        with self._changed:
            self._next += 1
            question = Pending(
                id=f"q{self._next}",
                label=label,
                options=options,
                host=host,
                fact_key=fact_key,
            )
            self._pending.append(question)
            self._changed.notify_all()
            return question

    def current(self) -> Pending | None:
        with self._lock:
            for question in self._pending:
                if not question.answered:
                    return question
            return None

    def wait_for_change(self, since: str, timeout: float = 25.0) -> Pending | None:
        """Block until the question on offer is not *since*, or time runs out.

        A phone polling every second is a phone with a flat battery. Holding
        the request open costs nothing and answers the instant there is
        something to say.
        """
        deadline = time.time() + timeout
        with self._changed:
            while True:
                current = next((q for q in self._pending if not q.answered), None)
                if (current.id if current else "") != since:
                    return current
                remaining = deadline - time.time()
                if remaining <= 0:
                    return current
                self._changed.wait(remaining)

    def answer(self, question_id: str, reply: str) -> Pending | None:
        """Record what was said, and what it means for the question asked.

        A reply the control does not offer is refused here rather than passed
        on. Putting a value into a control that has never heard of it fails,
        and calling that answered is the failure this whole project exists to
        stop.
        """
        with self._changed:
            question = next((q for q in self._pending if q.id == question_id), None)
            if question is None:
                return None
            said = (reply or "").strip()
            if said.lower() in {"", "skip", "-", "none", "pass"}:
                question.answered = True
                question.skipped = True
                question.answer = ""
            elif question.options:
                match = next(
                    (o for o in question.options if o.strip().lower() == said.lower()), ""
                )
                if not match and said.isdigit():
                    index = int(said) - 1
                    if 0 <= index < len(question.options):
                        match = question.options[index]
                if not match:
                    return question  # unchanged: not one of the options
                question.answer = match
                question.answered = True
            else:
                question.answer = said
                question.answered = True
            self._changed.notify_all()
            return question

    def forget_answered(self, keep: int = 40) -> None:
        with self._lock:
            answered = [q for q in self._pending if q.answered]
            if len(answered) > keep:
                drop = {id(q) for q in answered[: len(answered) - keep]}
                self._pending = [q for q in self._pending if id(q) not in drop]


#: One queue for the service. Nothing here is written to disk: a question that
#: outlives the run that asked it is a question about a page nobody is on.
QUEUE = Queue()

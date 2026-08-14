"""Asking a question when nobody is at the machine, and taking the answer.

An unattended run stops at the first thing it cannot answer and waits, which
turns an afternoon of filling into one form. The stop is right -- nothing here
invents an answer -- but the waiting does not have to be silent.

So the question goes to a phone and the answer comes back. What is sent is the
question, the options it offers, and the name of the site asking it. Never the
profile, never what has already been filled in, never a document. That
distinction is the whole design: the applicant's history stays on the machine
it was always on, and what crosses the wire is a sentence any careers page
shows to the public anyway.

Turned off unless a token is set. Nothing is sent by default and nothing is
sent to anybody who has not written to the bot first, which is Telegram's own
rule and a useful one: a chat id cannot be guessed at.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 20

#: How long an answer is waited for before the run gives up on it and leaves
#: the question for whoever comes back to the machine. Long enough for somebody
#: to notice a notification and reply; short enough that a phone left face-down
#: does not hold a run open all night.
DEFAULT_WAIT = 900


class NotifyUnavailable(RuntimeError):
    """No token, no chat, or the provider said no."""


@dataclass
class Question:
    """What gets asked. Deliberately small."""

    label: str
    options: tuple[str, ...] = ()
    host: str = ""
    #: Set when the answer comes back.
    answer: str = ""
    asked_at: float = field(default_factory=time.time)

    def as_message(self) -> str:
        lines = [self.label.strip() or "(a question with no wording)"]
        if self.host:
            lines.append(f"— on {self.host}")
        if self.options:
            lines.append("")
            lines.append("Reply with one of:")
            lines.extend(f"  {i + 1}. {option}" for i, option in enumerate(self.options[:20]))
            lines.append("")
            lines.append("A number or the words, either way. Reply 'skip' to leave it blank.")
        else:
            lines.append("")
            lines.append("Reply with your answer, or 'skip' to leave it blank.")
        return "\n".join(lines)

    def understand(self, reply: str) -> str:
        """What *reply* means for this question.

        A number picks an option, because typing "I don't wish to answer" on a
        phone is nobody's idea of a good time. Anything else is taken as the
        answer itself, and matched against the options where there are any --
        an answer this control cannot accept is worse than no answer.
        """
        said = (reply or "").strip()
        if not said:
            return ""
        if said.lower() in {"skip", "-", "none", "pass"}:
            return ""
        if self.options:
            if said.isdigit():
                index = int(said) - 1
                if 0 <= index < len(self.options):
                    return self.options[index]
                return ""
            for option in self.options:
                if option.strip().lower() == said.lower():
                    return option
            # A near miss is still a miss: putting a value into a control that
            # does not offer it fails, and reporting that as answered is worse
            # than reporting it as unanswered.
            return ""
        return said


class Phone:
    """A Telegram bot, used as a way to ask one question at a time."""

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()
        #: Telegram hands out updates once; this is where we resume from.
        self.offset = 0

    @property
    def available(self) -> bool:
        return bool(self.token and self.chat_id)

    def _call(self, method: str, **params) -> dict:
        if not self.token:
            raise NotifyUnavailable("no bot token has been set")
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params).encode()
        try:
            with urllib.request.urlopen(url, data=data, timeout=TIMEOUT) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise NotifyUnavailable(f"Telegram refused the request ({exc.code})") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise NotifyUnavailable(f"could not reach Telegram: {exc}") from exc
        if not payload.get("ok"):
            raise NotifyUnavailable(str(payload.get("description") or "Telegram said no"))
        return payload.get("result") or {}

    def find_chat(self) -> str:
        """The chat of whoever wrote to the bot most recently.

        A bot cannot start a conversation -- the person has to message it
        first. That is Telegram's rule and it is a good one: it means a chat id
        cannot be guessed, so nothing here can message a stranger.
        """
        updates = self._call("getUpdates", timeout=0)
        for update in reversed(updates if isinstance(updates, list) else []):
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            if chat.get("id"):
                self.chat_id = str(chat["id"])
                return self.chat_id
        return ""

    def send(self, text: str) -> None:
        if not self.chat_id:
            raise NotifyUnavailable("nobody has written to the bot yet")
        self._call("sendMessage", chat_id=self.chat_id, text=text)

    def next_reply(self) -> str:
        """The next thing the applicant typed, or "" if they have not yet."""
        try:
            updates = self._call("getUpdates", offset=self.offset, timeout=0)
        except NotifyUnavailable:
            return ""
        for update in updates if isinstance(updates, list) else []:
            self.offset = max(self.offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            if str(chat.get("id")) != self.chat_id:
                continue
            text = (message.get("text") or "").strip()
            if text:
                return text
        return ""

    def ask(self, question: Question, wait: int = DEFAULT_WAIT, poll: float = 3.0) -> str:
        """Send *question* and wait for what it means, or "" on no answer.

        Returning "" for silence is deliberate. A question nobody answered is
        exactly a question nobody answered, and the run leaves it for whoever
        comes back to the machine rather than filling something in.
        """
        # Clear anything said before the question was asked, so a reply to the
        # last one is never read as a reply to this one.
        while self.next_reply():
            pass

        self.send(question.as_message())
        deadline = time.time() + max(0, wait)
        while time.time() < deadline:
            reply = self.next_reply()
            if reply:
                question.answer = question.understand(reply)
                if question.answer:
                    self.send(f"Saved: {question.answer}")
                elif reply.strip().lower() in {"skip", "-", "none", "pass"}:
                    self.send("Left blank.")
                else:
                    self.send(
                        "That is not one of the options this control offers, so I have "
                        "left it. Reply with a number from the list."
                    )
                return question.answer
            time.sleep(poll)
        return ""

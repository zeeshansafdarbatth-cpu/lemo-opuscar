"""What the assistant can do for her. Claude chooses these; the Toolbox carries them out.

Everything here acts only on people in her contact list, so nobody outside it can be
called, texted or connected, however a request is worded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .activity import ActivityLog
from .brain_types import Contact, Decision
from .config import Config
from .dispatcher import Dispatcher
from .personal import Notebook, Reminders
from .telephony import Phone

log = logging.getLogger(__name__)


def _strict(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": properties,
                         "required": required if required is not None else list(properties),
                         "additionalProperties": False},
    }


PERSON = {"type": "string", "description": "id of a person from her contact list"}

TOOLS = [
    _strict("connect_call",
            "Connect her right now in a live phone call with someone on her list, so she can talk to them herself. "
            "Use when she wants to speak to someone. Tell her you are connecting her; the call starts after you speak.",
            {"person_id": PERSON}),
    _strict("get_help",
            "Ask people on her list to help or come, without her waiting on the line. The dispatcher texts and calls "
            "them one after another, retries when they don't answer, and calls her back with who said yes. "
            "Use for errands, rides, repairs, deliveries, and in an emergency (urgency 'emergency' calls everyone at once).",
            {"contacts": {"type": "array", "description": "best first, backups after", "items": {
                "type": "object", "additionalProperties": False, "required": ["person_id", "message"],
                "properties": {"person_id": PERSON, "message": {"type": "string", "description":
                    "What this person hears and reads, in their language and script: on behalf of her, what is needed, "
                    "when, ending with: press 1 or reply 1 if you can help, 2 if you cannot."}}}},
             "urgency": {"type": "string", "enum": ["normal", "emergency"]},
             "summary": {"type": "string", "description": "Short English line, e.g. 'Ride to Dr. Khan at 5pm'"}}),
    _strict("send_message",
            "Send a text message from her to someone on her list (no reply needed).",
            {"person_id": PERSON, "text": {"type": "string", "description": "The message, in the recipient's language"}}),
    _strict("set_reminder",
            "Set a reminder she asks for. At that time the assistant phones her and says it.",
            {"when": {"type": "string", "description": "Local date and time, ISO format, e.g. 2026-11-06T17:00"},
             "text": {"type": "string", "description": "What to say to her then, in her language"},
             "repeat": {"type": "string", "enum": ["none", "daily", "weekly"]}}),
    _strict("cancel_reminder", "Cancel one of her reminders.", {"reminder_id": {"type": "integer"}}),
    _strict("remember",
            "Write something in her private notebook because she asked you to remember it "
            "(where she kept something, a name, a number, a recipe, something to tell someone).",
            {"note": {"type": "string"}}),
    _strict("forget", "Remove a note from her notebook when she asks or it's no longer true.", {"note_id": {"type": "integer"}}),
    _strict("end_call", "Hang up after your reply, when she has said goodbye or has nothing more.", {}),
]


@dataclass
class Outcome:
    """What the call should do after the assistant speaks."""
    connect_to: str | None = None
    hang_up: bool = False


class Toolbox:
    def __init__(self, cfg: Config, dispatcher: Dispatcher, phone: Phone, notebook: Notebook,
                 reminders: Reminders, activity: ActivityLog, now):
        self.cfg, self.dispatcher, self.phone = cfg, dispatcher, phone
        self.notebook, self.reminders, self.activity, self.now = notebook, reminders, activity, now

    async def run(self, name: str, args: dict, outcome: Outcome) -> str:
        try:
            return await getattr(self, f"_{name}")(outcome, **args)
        except (AttributeError, TypeError) as e:
            return f"ERROR: bad tool call {name}: {e}"

    async def _connect_call(self, outcome: Outcome, person_id: str) -> str:
        p = self.cfg.person(person_id)
        if not p:
            return f"ERROR: {person_id} is not on her list. You can only connect her to people on her list."
        outcome.connect_to, outcome.hang_up = p.id, False
        return f"Will connect her to {p.name} right after you speak. Keep your reply to one short sentence."

    async def _get_help(self, outcome: Outcome, contacts: list[dict], urgency: str, summary: str) -> str:
        known = [Contact(helper_id=c["person_id"], message=c["message"]) for c in contacts if self.cfg.person(c["person_id"])]
        if urgency == "emergency":
            listed = {c.helper_id for c in known}
            base = known[0].message if known else f"Emergency: {self.cfg.mom.name} needs help now. Please go to her or call her. Press 1 or reply 1 if you are going."
            known += [Contact(helper_id=p.id, message=base) for p in self.cfg.family if p.id not in listed]
        if not known:
            return "ERROR: none of those people are on her list."
        decision = Decision(action="emergency" if urgency == "emergency" else "dispatch",
                            say_to_mom="", contacts=known, summary=summary)
        self.dispatcher.start(decision)
        outcome.hang_up = True
        names = ", ".join(self.cfg.person(c.helper_id).name for c in known)
        how = "all at once, repeatedly" if urgency == "emergency" else "in this order, with retries"
        return f"Started. Contacting {names} {how}. She'll get a call back with who said yes. The call will end after your reply."

    async def _send_message(self, outcome: Outcome, person_id: str, text: str) -> str:
        p = self.cfg.person(person_id)
        if not p:
            return f"ERROR: {person_id} is not on her list."
        await self.phone.sms(p.phone, f"{self.cfg.mom.name}: {text}")
        self.activity.add("message", f"Sent a text from her to {p.name}")
        return f"Sent to {p.name}."

    async def _set_reminder(self, outcome: Outcome, when: str, text: str, repeat: str) -> str:
        try:
            at = datetime.fromisoformat(when)
        except ValueError:
            return "ERROR: 'when' must be an ISO date and time like 2026-11-06T17:00"
        if at <= self.now() and repeat == "none":
            return "ERROR: that time has already passed. Check the date with her."
        r = self.reminders.add(at, text, repeat)
        return f"Reminder #{r.id} set for {r.due:%A %d %B at %H:%M}{'' if repeat == 'none' else f', repeating {repeat}'}."

    async def _cancel_reminder(self, outcome: Outcome, reminder_id: int) -> str:
        return "Cancelled." if self.reminders.cancel(reminder_id) else f"ERROR: no reminder #{reminder_id}."

    async def _remember(self, outcome: Outcome, note: str) -> str:
        n = self.notebook.add(note, self.now())
        return f"Saved as note #{n['id']}."

    async def _forget(self, outcome: Outcome, note_id: int) -> str:
        return "Removed." if self.notebook.remove(note_id) else f"ERROR: no note #{note_id}."

    async def _end_call(self, outcome: Outcome) -> str:
        if not outcome.connect_to:
            outcome.hang_up = True
        return "The call will end after your reply."

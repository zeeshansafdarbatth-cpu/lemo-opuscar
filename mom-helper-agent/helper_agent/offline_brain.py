"""A simple keyword brain for trying the line without an API key, and for tests.
It is not smart and replies in English: the real assistant is ClaudeBrain."""

from __future__ import annotations

import re
from datetime import timedelta

from .brain import ClaudeBrain, Turn
from .config import Config
from .tools import Outcome, Toolbox

EMERGENCY = ("fell", "fallen", "fall down", "chest", "breathe", "breathing", "emergency", "ambulance", "bleeding", "stroke", "help me",
             "گر گئی", "گری", "ڈگ", "ڈِگ", "سینے", "سانس", "ایمرجنسی", "ایمبولینس", "خون", "بچاؤ")
BYE = ("bye", "nothing", "that's all", "thank you", "khuda hafiz", "allah hafiz", "خدا حافظ", "اللہ حافظ", "بس", "شکریہ")
TALK = ("talk", "speak", "connect", "baat", "بات", "ملاؤ", "ملا دو")
REMIND = ("remind", "یاد دلا")
REMEMBER = ("remember", "یاد رکھ")


class KeywordBrain:
    def __init__(self, cfg: Config, toolbox: Toolbox):
        self.cfg, self.toolbox = cfg, toolbox

    async def respond(self, call_id: str, heard: str, context: str) -> Turn:
        text = heard.lower()
        mom, out = self.cfg.mom, Outcome()
        words = set(re.findall(r"\w+", text))

        def mentioned(people):
            return [p for p in people if p.name.lower() in text or (p.spoken_name and p.spoken_name in heard)
                    or (p.speed_dial and f"pressed {p.speed_dial}" in text)]

        if any(k in text for k in EMERGENCY):
            await self.toolbox.run("get_help", {"contacts": [], "urgency": "emergency", "summary": f"EMERGENCY: {heard}"}, out)
            return Turn(f"I'm getting your family right now, {mom.call_her}. If you can, call {self.cfg.settings.emergency_number}.", hang_up=True)
        if any(k in text for k in BYE):
            return Turn(f"Goodbye {mom.call_her}, take care.", hang_up=True)
        if any(k in text for k in REMIND):
            when = self.toolbox.now() + timedelta(minutes=1)
            await self.toolbox.run("set_reminder", {"when": when.isoformat(timespec="minutes"), "text": heard, "repeat": "none"}, out)
            return Turn("Okay, I'll remind you in a minute.")
        if any(k in text for k in REMEMBER):
            await self.toolbox.run("remember", {"note": heard}, out)
            return Turn("I've written that down for you.")
        named = mentioned(self.cfg.everyone)
        if named and any(k in text for k in TALK):
            await self.toolbox.run("connect_call", {"person_id": named[0].id}, out)
            return Turn(f"Connecting you to {named[0].name}.", connect_to=out.connect_to)

        def score(p):
            hay = f"{p.name} {p.role} {p.helps_with}".lower()
            return sum(1 for w in words if len(w) > 2 and w in hay)

        ranked = named or sorted((p for p in self.cfg.helpers if score(p)), key=score, reverse=True)
        if not ranked:
            return Turn(f"What can I do for you, {mom.call_her}?")
        backups = [p for p in self.cfg.family if p not in ranked][:1]
        msg = f"Hello, this is a call for {mom.name}. She said: \"{heard}\". Press 1 or reply 1 if you can help, 2 if you can't."
        await self.toolbox.run("get_help", {"contacts": [{"person_id": p.id, "message": msg} for p in [*ranked, *backups]],
                                            "urgency": "normal", "summary": heard[:80]}, out)
        return Turn(f"Okay {mom.call_her}, I'm calling {ranked[0].name} now. I'll call you back.", hang_up=True)

    safe_fallback = ClaudeBrain.safe_fallback

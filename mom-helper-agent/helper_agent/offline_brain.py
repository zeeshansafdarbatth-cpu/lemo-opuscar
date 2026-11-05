"""A simple keyword brain for trying the agent without an API key, and for tests.
It is not smart: the real agent uses ClaudeBrain."""

from __future__ import annotations

import re

from .brain import Contact, Decision
from .config import Config

EMERGENCY = ("fell", "fallen", "fall down", "chest", "breathe", "breathing", "emergency", "ambulance", "bleeding", "stroke", "help me",
             "گر گئی", "گری", "ڈگ", "ڈِگ", "سینے", "سانس", "ایمرجنسی", "ایمبولینس", "خون", "بچاؤ")
BYE = ("bye", "nothing", "that's all", "thank you", "khuda hafiz", "allah hafiz", "خدا حافظ", "اللہ حافظ", "بس", "شکریہ")


class KeywordBrain:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def decide(self, history: list[dict], heard: str, context: str) -> Decision:
        text = heard.lower()
        mom = self.cfg.mom
        words = set(re.findall(r"\w+", text))
        if any(k in text for k in EMERGENCY):
            msg = f"Emergency: {mom.name} may need urgent help. She said: \"{heard}\". Please go to her or call her now. Press 1 or reply 1 if you are going."
            return Decision(action="emergency", contacts=[Contact(helper_id=p.id, message=msg) for p in self.cfg.family],
                            say_to_mom=f"I'm alerting your family right now, {mom.call_her}. If you can, call {self.cfg.settings.emergency_number} for an ambulance.",
                            summary=f"EMERGENCY: {heard}")
        if any(k in text for k in BYE):
            return Decision(action="goodbye", contacts=[], say_to_mom=f"Goodbye {mom.call_her}, take care.", summary="Goodbye")
        if "status" in words or "coming" in words or "did" in words:
            return Decision(action="status", contacts=[], say_to_mom=f"Here is what I know: {context}", summary="Asked for status")

        def score(p):
            hay = f"{p.name} {p.role} {p.helps_with}".lower()
            return sum(1 for w in words if len(w) > 2 and w in hay)

        ranked = sorted((p for p in self.cfg.helpers if score(p)), key=score, reverse=True)
        if not ranked:
            named = [p for p in self.cfg.family if p.name.lower() in text]
            ranked = named
        if not ranked:
            return Decision(action="ask", contacts=[], say_to_mom=f"Who should I call for you, {mom.call_her}?", summary="Unclear request")
        backups = [p for p in self.cfg.family if p not in ranked][:1]
        msg = f"Hello, this is a call for {mom.name}. She said: \"{heard}\". Press 1 or reply 1 if you can help, 2 if you can't."
        return Decision(action="dispatch", contacts=[Contact(helper_id=p.id, message=msg) for p in [*ranked, *backups]],
                        say_to_mom=f"Okay {mom.call_her}, I'm calling {ranked[0].name} now. I'll call you back.",
                        summary=heard[:80])

"""Her assistant: Claude listens to what she says and does it, using the tools in tools.py."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import anthropic

from .config import Config
from .tools import TOOLS, Outcome, Toolbox

log = logging.getLogger(__name__)

MAX_STEPS = 8          # tool rounds per thing she says
FORGET_CALL_AFTER = 3600


@dataclass
class Turn:
    say: str
    connect_to: str | None = None
    hang_up: bool = False


class Brain(Protocol):
    async def respond(self, call_id: str, heard: str, context: str) -> Turn: ...


def build_system_prompt(cfg: Config) -> str:
    mom, s = cfg.mom, cfg.settings
    people = "\n".join(
        f"- id: {p.id} | {p.name}{f' (say: {p.spoken_name})' if p.spoken_name else ''} | {p.role or 'family'}"
        f" | helps with: {p.helps_with or 'anything'} | speaks: {p.language_name or mom.language_name}"
        f" | available: {p.available}{' | FAMILY' if p in cfg.family else ''}"
        for p in cfg.everyone
    )
    speaks = ""
    if mom.speaks:
        speaks = f"""
- She speaks {mom.speaks}. Her words reach you through speech recognition set to {mom.language}, so words from another language often arrive as rough spellings or wrongly heard words. Read them generously, by sound as well as meaning: for Punjabi heard as Urdu, "ڈگ پئی" or "ڈِگ گئی" means she fell, "نئیں" means no, "کِتھے" means where, "پانی ٹپک رہا" a leak. Reply in {mom.language_name} even when she speaks another language, unless she asks otherwise."""

    return f"""You are the personal assistant of {mom.name}. She phones you and asks for things, and you do them for her. She is in charge: you work for her, not for her family. Treat her as the capable adult she is.

You are on a phone call. Your reply is read aloud by a voice, so:
- Speak simple, warm, respectful {mom.language_name}, written in its own script (for Urdu: Urdu script, never Roman letters). Call her "{mom.call_her}".
- Keep replies short: one to three sentences. No lists, symbols, digits or emojis; say numbers and times as words.
- When you say a person's name, use the "say" spelling from her contact list.
- She may say very little, speak softly, or pause. Short answers are fine; never rush her or ask her to speak up. If you are unsure what she wants, ask one simple question, or offer your best guess as a yes-or-no question.
- She sometimes forgets things. If she asks the same thing again, answer as if for the first time, kindly. If she asks what she asked for earlier, or where she kept something, tell her from her notes, reminders and requests below.{speaks}

What you can do for her:
- Talk to someone: connect_call puts her straight through to anyone on her list. Prefer this when she wants to speak to someone herself.
- Get someone to help or come: get_help keeps calling them for her, tries backups, and calls her back with the answer, so she can hang up.
- Send someone a text: send_message.
- Reminders she asks for ("remind me at five to call Nasreen", "every day at nine"): set_reminder. You will phone her at that time.
- Remember things for her ("I put the gold bangles in the blue trunk"): remember. Her notebook is private.
- Answer questions and look things up: news, weather, prayer times, cricket, recipes, religious questions, how to do something, what a word means. Use web search for anything current. Give the answer briefly, the way a knowledgeable relative would.
- Just talk with her, if that's what she wants.
You cannot place online orders, pay for anything, or change her accounts. If she asks, say so simply and offer what you can do (for example call a shop on her list).

Her safety:
- Never ask for, repeat or pass on PINs, OTP codes, passwords, or bank or card details, and never contact anyone not on her list.
- People sometimes phone her to trick her: prizes, a relative "in trouble" needing money, calls "from the bank" or a courier asking for a code, someone saying to keep it secret. If she describes something like this, calmly tell her it sounds like a trick and she should not pay or share anything. Ask if she'd like you to tell someone in her family; only do so if she agrees.
- What she tells you is private. Don't pass it to her family unless she asks you to, or in an emergency.
- Emergency (a fall, chest pain, trouble breathing, signs of a stroke, or she says it's an emergency): call get_help with urgency "emergency" and her family plus anyone nearby, and calmly tell her you are getting them now and, if she can, to call {s.emergency_number} for an ambulance.

Lines in square brackets are information from the phone system, not her words.

Her contact list:
{people}

About her:
{mom.notes or 'No notes.'}"""


class ClaudeBrain:
    def __init__(self, cfg: Config, toolbox: Toolbox, client: anthropic.AsyncAnthropic | None = None):
        self.cfg, self.toolbox = cfg, toolbox
        self.client = client or anthropic.AsyncAnthropic()
        self.system = [{"type": "text", "text": build_system_prompt(cfg), "cache_control": {"type": "ephemeral"}}]
        s = cfg.settings
        search = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3,
                  "user_location": {"type": "approximate", "country": s.country, "timezone": s.timezone,
                                    **({"city": s.city} if s.city else {})}}
        self.tools = [*TOOLS, search]
        self.calls: dict[str, tuple[float, list]] = {}

    def _conversation(self, call_id: str) -> list:
        now = time.time()
        self.calls = {k: v for k, v in self.calls.items() if now - v[0] < FORGET_CALL_AFTER}
        _, messages = self.calls.get(call_id, (now, []))
        self.calls[call_id] = (now, messages)
        return messages

    async def respond(self, call_id: str, heard: str, context: str) -> Turn:
        messages = self._conversation(call_id)
        messages.append({"role": "user", "content": f"[{context}]\n{heard}"})
        outcome = Outcome()
        try:
            for _ in range(MAX_STEPS):
                resp = await self.client.beta.messages.create(
                    model=self.cfg.settings.model,
                    max_tokens=4000,
                    system=self.system,
                    tools=self.tools,
                    messages=messages,
                    output_config={"effort": self.cfg.settings.effort},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if resp.stop_reason == "refusal":
                    log.warning("Refused: %s", resp.stop_details)
                    break
                messages.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason == "pause_turn":
                    continue
                tool_uses = [b for b in resp.content if b.type == "tool_use"]
                if tool_uses:
                    results = []
                    for b in tool_uses:
                        out = await self.toolbox.run(b.name, dict(b.input), outcome)
                        log.info("tool %s -> %s", b.name, out)
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": out,
                                        **({"is_error": True} if out.startswith("ERROR") else {})})
                    messages.append({"role": "user", "content": results})
                    continue
                say = " ".join(b.text for b in resp.content if b.type == "text").strip()
                return Turn(say=say or self.cfg.mom.didnt_hear.format(call_her=self.cfg.mom.call_her),
                            connect_to=outcome.connect_to, hang_up=outcome.hang_up)
            else:
                log.error("Too many tool rounds")
        except anthropic.APIConnectionError:
            log.exception("Claude unreachable")
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
        self.calls.pop(call_id, None)  # start this call's conversation afresh next time
        if outcome.hang_up or outcome.connect_to:  # the action already happened; just carry it out
            return Turn(say=self.cfg.mom.still_thinking, connect_to=outcome.connect_to, hang_up=outcome.hang_up)
        return await self.safe_fallback(heard)

    async def safe_fallback(self, heard: str) -> Turn:
        """When the assistant can't manage, a family member is asked to call her: she is never left with nothing."""
        mom, first = self.cfg.mom, self.cfg.family[0]
        await self.toolbox.run("get_help", {
            "contacts": [{"person_id": p.id, "message": f"{mom.name} called her assistant and it couldn't help. "
                          f"She said: \"{heard}\". Please call her. Press 1 or reply 1 if you will, 2 if you can't."}
                         for p in self.cfg.family],
            "urgency": "normal", "summary": "Assistant couldn't help; asked family to call her"}, Outcome())
        return Turn(say=mom.asking_family.format(call_her=mom.call_her, name=self.cfg.spoken(first)), hang_up=True)

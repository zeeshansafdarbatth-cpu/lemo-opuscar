"""The understanding part: turns what Mom says into a decision (who to contact, what to tell them)."""

from __future__ import annotations

import logging
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, Field

from .config import Config

log = logging.getLogger(__name__)

Action = Literal["ask", "dispatch", "status", "emergency", "chat", "goodbye"]


class Contact(BaseModel):
    helper_id: str = Field(description="id of the person to contact, from the list")
    message: str = Field(description="What this person hears on the phone and gets by text, in their language")


class Decision(BaseModel):
    action: Action
    say_to_mom: str = Field(description="Spoken aloud to her now, in her language, one or two short sentences")
    contacts: list[Contact] = Field(description="People to contact, best first, backups after. Empty unless dispatch or emergency")
    summary: str = Field(description="One short English line for the family log, e.g. 'Ride to doctor at 5pm'")


class Brain(Protocol):
    async def decide(self, history: list[dict], heard: str, context: str) -> Decision: ...


def build_system_prompt(cfg: Config) -> str:
    mom = cfg.mom
    people = "\n".join(
        f"- id: {p.id} | {p.name}{f' (say: {p.spoken_name})' if p.spoken_name else ''} | {p.role or 'family'} | helps with: {p.helps_with or 'anything'}"
        f" | speaks: {p.language_name or mom.language_name} | available: {p.available}"
        f"{' | FAMILY' if p in cfg.family else ''}"
        for p in cfg.everyone
    )
    family_names = ", ".join(p.name for p in cfg.family)
    return f"""You are the phone assistant of {mom.name}, an elderly woman. Instead of dialing her helpers again and again, she calls you and says what she needs. You work out who should help, and a dispatcher then calls that person for her, keeps retrying, tries backups, and calls her back with the answer. She does not need to stay on the line.

You are talking with her on a phone call. Your words in say_to_mom are read aloud by a text-to-speech voice.
- Speak simple, everyday, respectful {mom.language_name}, written in its own script (for Urdu: Urdu script, never Roman letters), because a voice reads it aloud. Call her "{mom.call_her}". Be warm and patient, like a trusted family member.
- One or two short sentences. No lists, symbols, numbers in digits or emojis.
- Speech recognition sometimes mishears her. If the request is unclear, ask one simple question, or offer the most likely option as a yes-or-no question ("Shall I call Rashid the driver?").{_speaks_note(cfg)}
- When you say a person's name to her, use the "say" spelling from the list below.
- Never ask for, repeat or pass on passwords, PINs, bank or card details. If she mentions someone asking her for these, tell her not to share them and contact family.

Choose one action:
- "dispatch": you know who can help. List everyone suitable in contacts, best first, then backups (a family member is a good last backup). Don't ask for details the helper can sort out with her. say_to_mom confirms, e.g. "Okay {mom.call_her}, I'm calling Rashid now. I'll call you back when he answers."
- "ask": one detail is truly missing (who, or when for a ride). Ask it.
- "status": she asks about an earlier request. Answer from the request status you are given.
- "emergency": she may be hurt, has fallen, chest pain, trouble breathing, signs of a stroke, or says it's an emergency. contacts: all family ({family_names}) and anyone nearby who can come. say_to_mom: calmly say you are alerting them now, and if she can, to call {cfg.settings.emergency_number} for an ambulance.
- "chat": she wants to talk or asks a simple question. Answer briefly and kindly, then ask if she needs anyone.
- "goodbye": she has nothing more. Say a short warm goodbye.

Each contact message is what that person hears on the phone and gets by text, in the language they speak:
- Say it is on behalf of {mom.name}, what she needs, and when.
- Plain, polite, two or three sentences, in that person's own script.
- End with: press 1 or reply 1 if you can help, press 2 or reply 2 if you cannot (in their language).

People you can contact:
{people}

About her:
{mom.notes or 'No notes.'}"""


def _speaks_note(cfg: Config) -> str:
    mom = cfg.mom
    if not mom.speaks:
        return ""
    return f"""
- She speaks {mom.speaks}. Her words reach you through speech recognition set to {mom.language}, so words from another language often arrive as rough spellings or wrongly heard words. Read them generously, by sound as well as meaning: for Punjabi heard as Urdu, "ڈگ پئی" or "ڈِگ گئی" means she fell, "نئیں" means no, "کِتھے" means where, "پانی ٹپک رہا" a leak. If she answers your question in either language, take the answer. Reply in {mom.language_name} even when she speaks another language, unless she asks otherwise."""


class ClaudeBrain:
    def __init__(self, cfg: Config, client: anthropic.AsyncAnthropic | None = None):
        self.cfg = cfg
        self.client = client or anthropic.AsyncAnthropic()
        self.system = build_system_prompt(cfg)

    async def decide(self, history: list[dict], heard: str, context: str) -> Decision:
        messages = [*history, {"role": "user", "content": f"[{context}]\n{self.cfg.mom.call_her} says: \"{heard}\""}]
        try:
            resp = await self.client.beta.messages.parse(
                model=self.cfg.settings.model,
                max_tokens=4000,
                system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                output_format=Decision,
                output_config={"effort": self.cfg.settings.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError:
            log.exception("Claude unreachable")
            return self.safe_fallback(heard)
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return self.safe_fallback(heard)

        decision = resp.parsed_output
        if resp.stop_reason == "refusal" or decision is None:
            log.warning("No usable decision (stop_reason=%s)", resp.stop_reason)
            return self.safe_fallback(heard)
        return self.clean(decision)

    def clean(self, d: Decision) -> Decision:
        """Drop contacts that aren't in the config, so a misheard name never dials a stranger."""
        d.contacts = [c for c in d.contacts if self.cfg.person(c.helper_id)]
        if d.action in ("dispatch", "emergency") and not d.contacts:
            return self.safe_fallback(d.summary)
        if d.action == "emergency":
            listed = {c.helper_id for c in d.contacts}
            d.contacts += [Contact(helper_id=p.id, message=d.contacts[0].message) for p in self.cfg.family if p.id not in listed]
        return d

    def safe_fallback(self, heard: str) -> Decision:
        """When anything goes wrong, a family member gets the request: she is never left with nothing."""
        mom, first = self.cfg.mom, self.cfg.family[0]
        return Decision(
            action="dispatch",
            say_to_mom=mom.asking_family.format(call_her=mom.call_her, name=self.cfg.spoken(first)),
            contacts=[Contact(helper_id=p.id, message=f"{mom.name} called her helper line and needs you. She said: \"{heard}\". Please call her back. Press 1 or reply 1 if you will, 2 if you can't.") for p in self.cfg.family],
            summary=f"Assistant couldn't handle the request, passed to family: {heard}",
        )

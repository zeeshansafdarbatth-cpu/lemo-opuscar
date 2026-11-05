"""Loads config.yaml: who Mom is, who her family and helpers are, and how hard to try."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


def normalize_phone(number: str) -> str:
    """Keep the leading + and digits only, so '+92 300-123 4567' matches '+923001234567'."""
    number = number.strip()
    digits = re.sub(r"\D", "", number)
    return ("+" if number.startswith("+") else "") + digits


class Person(BaseModel):
    id: str
    name: str
    # The name as it should be spoken to Mom, in her script (e.g. "راشد"), so the voice says it right.
    spoken_name: str | None = None
    phone: str
    role: str = ""
    helps_with: str = ""
    # Language for talking to this person: Twilio code (e.g. "ur-PK") and plain name (e.g. "Urdu").
    language: str | None = None
    language_name: str | None = None
    voice: str | None = None
    available: str = "any time"
    # A keypad digit Mom can press instead of speaking (e.g. "1" for the driver).
    speed_dial: str | None = None


class Mom(BaseModel):
    name: str
    call_her: str = Field(description="What the assistant calls her, e.g. 'Ammi'")
    phones: list[str]
    # Twilio code used to listen to her and speak to her, e.g. "ur-PK".
    language: str = "en-US"
    # The language the assistant speaks to her, and the script to write it in.
    language_name: str = "English"
    # The languages she may speak, if more than one (e.g. "Punjabi and Urdu, often mixed").
    speaks: str = ""
    voice: str | None = None
    notes: str = ""
    # Fixed things she hears. Write them in her language.
    greeting: str = "Hello {call_her}, how can I help?"
    said_yes: str = "{call_her}, good news. {name} said yes and will help you."
    nobody_reached: str = "{call_her}, I could not reach {names}. I have told {family}, and they will call you soon."
    asking_family: str = "{call_her}, I'm asking {name} to call you now."
    didnt_hear: str = "Sorry {call_her}, I didn't hear you. Please tell me again."
    still_thinking: str = "One moment."
    stranger: str = "Sorry, this line is private. Goodbye."
    and_word: str = "and"
    # Fixed things helpers hear after pressing a key.
    helper_thanks: str = "Thank you."
    helper_already_handled: str = "Thank you, this request has already been handled."


class Settings(BaseModel):
    attempts_per_helper: int = 3
    seconds_between_attempts: int = 120
    ring_seconds: int = 25
    wait_for_answer_seconds: int = 90
    call_mom_with_result: bool = True
    text_mom_with_result: bool = False
    text_family_every_request: bool = False
    emergency_number: str = "112"
    allow_unknown_callers: bool = False
    # Where she lives: for local news, weather, prayer times, and the clock reminders use.
    city: str = ""
    country: str = "PK"
    timezone: str = "Asia/Karachi"
    # False: the family dashboard shows what the assistant did (calls, help requests), never what she said.
    share_conversations: bool = False
    model: str = "claude-opus-5-5"
    effort: str = "low"
    # "twilio": Twilio's built-in voices. "elevenlabs": ElevenLabs voices (needs ELEVENLABS_API_KEY).
    speech: str = "twilio"
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_v3"


class Config(BaseModel):
    mom: Mom
    family: list[Person]
    helpers: list[Person] = []
    settings: Settings = Settings()

    @property
    def everyone(self) -> list[Person]:
        return [*self.family, *self.helpers]

    def person(self, person_id: str) -> Person | None:
        return next((p for p in self.everyone if p.id == person_id), None)

    def person_by_phone(self, phone: str) -> Person | None:
        target = normalize_phone(phone)
        return next((p for p in self.everyone if normalize_phone(p.phone) == target), None)

    def person_by_speed_dial(self, digit: str) -> Person | None:
        return next((p for p in self.everyone if p.speed_dial == digit), None)

    def is_mom(self, phone: str) -> bool:
        target = normalize_phone(phone)
        return any(normalize_phone(p) == target for p in self.mom.phones)

    def spoken(self, person: Person) -> str:
        return person.spoken_name or person.name

    def lang_for(self, person: Person) -> str:
        return person.language or self.mom.language


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as f:
        cfg = Config.model_validate(yaml.safe_load(f))
    ids = [p.id for p in cfg.everyone]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate person ids in config: {sorted(dupes)}")
    if not cfg.family:
        raise ValueError("Add at least one family member: they are the last resort when nobody answers.")
    return cfg

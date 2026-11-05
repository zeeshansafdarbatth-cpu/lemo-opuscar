"""How the agent's words become speech on a call.

TwilioVoice  uses Twilio's built-in voices (<Say>). Simple, but not every language has a voice.
ElevenLabsVoice  makes the audio with ElevenLabs (natural Urdu and Punjabi voices), keeps a copy
                 on disk, and has Twilio play it (<Play>). Falls back to <Say> if ElevenLabs fails.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import urllib.request
from pathlib import Path
from typing import Protocol

from twilio.twiml.voice_response import VoiceResponse

log = logging.getLogger(__name__)


class Voice(Protocol):
    async def speak(self, verb, text: str, language: str, voice: str | None = None) -> None:
        """Append speech for `text` to a TwiML verb (VoiceResponse or Gather)."""


class TwilioVoice:
    async def speak(self, verb, text, language, voice=None):
        verb.say(text, language=language, **({"voice": voice} if voice else {}))


class ElevenLabsVoice:
    API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_22050_32"

    def __init__(self, api_key: str, voice_id: str, model: str, public_url: str, cache_dir: str | Path = "data/audio"):
        self.api_key, self.voice_id, self.model = api_key, voice_id, model
        self.base = public_url.rstrip("/")
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)

    def key(self, text: str, voice_id: str) -> str:
        return hashlib.sha256(f"{self.model}|{voice_id}|{text}".encode()).hexdigest()[:32]

    def path(self, key: str) -> Path | None:
        if not key.isalnum():
            return None
        p = self.cache / f"{key}.mp3"
        return p if p.exists() else None

    def _synthesize(self, text: str, voice_id: str) -> bytes:
        req = urllib.request.Request(
            self.API.format(voice_id=voice_id),
            data=json.dumps({"text": text, "model_id": self.model}).encode(),
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read()

    async def speak(self, verb, text, language, voice=None):
        # `voice` here is a Twilio voice name; ElevenLabs always uses the configured voice id.
        key = self.key(text, self.voice_id)
        if not self.path(key):
            try:
                audio = await asyncio.to_thread(self._synthesize, text, self.voice_id)
                (self.cache / f"{key}.mp3").write_bytes(audio)
            except Exception:
                log.exception("ElevenLabs failed; using Twilio's voice instead")
                verb.say(text, language=language)
                return
        verb.play(f"{self.base}/audio/{key}.mp3")


async def spoken_twiml(speaker: Voice, text: str, language: str, voice: str | None = None, repeat: int = 1) -> str:
    """A whole call's TwiML that just says `text` (repeated, so it isn't missed)."""
    r = VoiceResponse()
    r.pause(length=1)
    for i in range(repeat):
        if i:
            r.pause(length=1)
        await speaker.speak(r, text, language, voice)
    return str(r)

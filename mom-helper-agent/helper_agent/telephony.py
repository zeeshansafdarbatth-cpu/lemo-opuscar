"""Phone calls and texts. TwilioPhone makes real ones; ConsolePhone prints them for testing."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Phone(Protocol):
    async def call(self, to: str, *, url: str | None = None, twiml: str | None = None,
                   status_callback: str | None = None, ring_seconds: int = 25) -> str: ...
    async def sms(self, to: str, body: str) -> None: ...


class TwilioPhone:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        from twilio.rest import Client
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    async def call(self, to, *, url=None, twiml=None, status_callback=None, ring_seconds=25):
        kwargs = {"to": to, "from_": self.from_number, "timeout": ring_seconds}
        if url:
            kwargs["url"] = url
        if twiml:
            kwargs["twiml"] = twiml
        if status_callback:
            kwargs["status_callback"] = status_callback
            kwargs["status_callback_event"] = ["completed"]
        call = await asyncio.to_thread(self.client.calls.create, **kwargs)
        log.info("Calling %s (sid %s)", to, call.sid)
        return call.sid

    async def sms(self, to, body):
        try:
            await asyncio.to_thread(self.client.messages.create, to=to, from_=self.from_number, body=body)
            log.info("Texted %s", to)
        except Exception:  # a failed text must never stop the calls
            log.exception("Text to %s failed", to)


class ConsolePhone:
    """Prints instead of dialing. Records everything so tests can check it."""

    def __init__(self):
        self.calls: list[dict] = []
        self.texts: list[dict] = []

    async def call(self, to, *, url=None, twiml=None, status_callback=None, ring_seconds=25):
        sid = f"CA{len(self.calls):04d}"
        self.calls.append({"to": to, "url": url, "twiml": twiml, "sid": sid})
        print(f"  📞 calling {to}" + (f"  ({url})" if url else ""))
        return sid

    async def sms(self, to, body):
        self.texts.append({"to": to, "body": body})
        print(f"  💬 text to {to}: {body}")

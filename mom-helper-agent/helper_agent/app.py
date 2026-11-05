"""The web server Twilio talks to.

Mom calls the agent's number  -> /voice/mom/incoming -> she speaks -> /voice/mom/heard
The agent calls a helper       -> /voice/helper/{task}  -> key press -> /voice/helper/{task}/answer
A helper texts back            -> /sms/incoming
The family checks in           -> /dashboard  (password: DASHBOARD_PASSWORD)
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import secrets
import time
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import Gather, VoiceResponse

from .activity import ActivityLog
from .brain import Brain, Decision
from .config import Config
from .dispatcher import Dispatcher, interpret_reply
from .telephony import Phone
from .voice import ElevenLabsVoice, TwilioVoice, Voice

log = logging.getLogger(__name__)

THINK_SECONDS = 9  # Twilio gives a webhook 15s; past this we say "one moment" and keep waiting.
MAX_TURNS = 12


def twiml(r) -> Response:
    return Response(str(r), media_type="application/xml")


def create_app(cfg: Config, brain: Brain, phone: Phone, public_url: str,
               activity: ActivityLog | None = None, twilio_auth_token: str | None = None,
               dashboard_password: str | None = None, speaker: Voice | None = None) -> FastAPI:
    app = FastAPI(title="Mom's helper line")
    activity = activity or ActivityLog()
    speaker = speaker or TwilioVoice()
    dispatcher = Dispatcher(cfg, phone, public_url, activity, speaker)
    app.state.dispatcher = dispatcher
    validator = RequestValidator(twilio_auth_token) if twilio_auth_token else None
    base = public_url.rstrip("/")
    mom = cfg.mom
    conversations: dict[str, list[dict]] = {}
    thinking: dict[str, asyncio.Task] = {}
    misses: dict[str, int] = {}

    async def twilio_form(request: Request) -> dict:
        """Form fields of a Twilio webhook, after checking it really came from Twilio."""
        form = dict(await request.form())
        if validator:
            url = base + request.url.path + (f"?{request.url.query}" if request.url.query else "")
            if not validator.validate(url, form, request.headers.get("X-Twilio-Signature", "")):
                raise HTTPException(403, "Bad Twilio signature")
        return form

    async def say(r, text, lang=mom.language, voice=mom.voice):
        await speaker.speak(r, text, lang, voice)

    # Names help speech recognition pick out who she means.
    hints = ", ".join(dict.fromkeys(w for p in cfg.everyone for w in (p.name, p.role) if w))

    async def listen(r, prompt: str | None):
        g = Gather(input="speech dtmf", action=f"{base}/voice/mom/heard", method="POST",
                   language=mom.language, speech_timeout="auto", timeout=8, num_digits=1, hints=hints)
        if prompt:
            await say(g, prompt)
        r.append(g)
        r.redirect(f"{base}/voice/mom/heard?silent=1", method="POST")

    # ---- Mom's calls ----------------------------------------------------

    @app.post("/voice/mom/incoming")
    async def mom_incoming(form: dict = Depends(twilio_form)):
        r = VoiceResponse()
        caller = form.get("From", "")
        if not cfg.settings.allow_unknown_callers and not cfg.is_mom(caller):
            activity.add("stranger", f"Call from unknown number {caller} refused")
            await say(r, mom.stranger)
            r.hangup()
            return twiml(r)
        sid = form.get("CallSid", "")
        conversations[sid], misses[sid] = [], 0
        activity.add("mom_called", "Mom called the helper line")
        await listen(r, mom.greeting.format(call_her=mom.call_her))
        return twiml(r)

    @app.post("/voice/mom/heard")
    async def mom_heard(request: Request, form: dict = Depends(twilio_form)):
        sid = form.get("CallSid", "")
        r = VoiceResponse()
        history = conversations.setdefault(sid, [])

        if sid not in thinking:  # a fresh utterance (not a "still thinking" redirect)
            heard = (form.get("SpeechResult") or "").strip()
            digit = (form.get("Digits") or "").strip()
            if digit and (p := cfg.person_by_speed_dial(digit)):
                heard = f"(pressed {digit} on the keypad, the button for {p.name}) I need {p.name}."
            if not heard:
                misses[sid] = misses.get(sid, 0) + 1
                if misses[sid] >= 3:
                    # She's struggling: get a person to ring her rather than loop forever.
                    fallback = _family_fallback(cfg)
                    dispatcher.start(fallback)
                    await say(r, fallback.say_to_mom)
                    r.hangup()
                    return twiml(r)
                await listen(r, mom.didnt_hear.format(call_her=mom.call_her))
                return twiml(r)
            misses[sid] = 0
            activity.add("mom_said", heard)
            context = f"Time now: {datetime.now():%A %d %B, %H:%M}. Earlier requests: {dispatcher.status_summary()}"
            thinking[sid] = asyncio.create_task(brain.decide(list(history), heard, context))
            history.append({"role": "user", "content": f"[{context}]\n{mom.call_her} says: \"{heard}\""})

        done, _ = await asyncio.wait({thinking[sid]}, timeout=THINK_SECONDS)
        if not done:
            await say(r, mom.still_thinking)
            r.redirect(f"{base}/voice/mom/heard", method="POST")
            return twiml(r)

        try:
            decision: Decision = thinking.pop(sid).result()
        except Exception:
            log.exception("Brain failed")
            decision = _family_fallback(cfg)
        history.append({"role": "assistant", "content": decision.model_dump_json()})
        activity.add("agent_said", decision.say_to_mom, action=decision.action)

        if decision.action in ("dispatch", "emergency"):
            dispatcher.start(decision)
        await say(r, decision.say_to_mom)

        if decision.action in ("dispatch", "emergency", "goodbye") or len(history) >= MAX_TURNS * 2:
            r.hangup()  # the dispatcher calls her back with the answer
        else:
            await listen(r, None)
        return twiml(r)

    # ---- Calls to helpers -----------------------------------------------

    @app.post("/voice/helper/{task_id}")
    async def helper_call(task_id: str, person: str, attempt: int = 1, form: dict = Depends(twilio_form)):
        task, p = dispatcher.tasks.get(task_id), cfg.person(person)
        r = VoiceResponse()
        if not task or not p or task.status != "working":
            await say(r, mom.helper_already_handled, lang=cfg.lang_for(p) if p else mom.language)
            r.hangup()
            return twiml(r)
        message = next((c.message for c in task.decision.contacts if c.helper_id == p.id), task.decision.summary)
        g = Gather(input="dtmf", num_digits=1, timeout=10, method="POST",
                   action=f"{base}/voice/helper/{task_id}/answer?person={p.id}&attempt={attempt}")
        for _ in range(2):
            await say(g, message, lang=cfg.lang_for(p), voice=p.voice)
            g.pause(length=2)
        r.append(g)
        r.hangup()  # no key press: the status callback counts it as no answer
        return twiml(r)

    @app.post("/voice/helper/{task_id}/answer")
    async def helper_answer(task_id: str, person: str, attempt: int = 1, form: dict = Depends(twilio_form)):
        digit = form.get("Digits", "")
        reply = {"1": "yes", "2": "no"}.get(digit)
        p = cfg.person(person)
        r = VoiceResponse()
        if reply:
            dispatcher.record_reply(task_id, person, reply)
            await say(r, mom.helper_thanks, lang=cfg.lang_for(p), voice=p.voice)
        else:
            dispatcher.record_no_answer(task_id, person, attempt)
        r.hangup()
        return twiml(r)

    @app.post("/voice/helper/{task_id}/status")
    async def helper_status(task_id: str, person: str, attempt: int = 1, form: dict = Depends(twilio_form)):
        # Arrives when the call ends. If they pressed 1 or 2 the dispatcher has already moved on
        # (to the next person, or finished), so the dispatcher ignores this.
        dispatcher.record_no_answer(task_id, person, attempt)
        return Response(status_code=204)

    # ---- Text replies -----------------------------------------------------

    @app.post("/sms/incoming")
    async def sms_incoming(form: dict = Depends(twilio_form)):
        sender, body = form.get("From", ""), (form.get("Body") or "").strip()
        p = cfg.person_by_phone(sender)
        r = MessagingResponse()
        if not p:
            activity.add("stranger_text", f"Text from unknown number {sender}: {body!r}")
            return twiml(r)
        task = dispatcher.open_task_for(p.id)
        if not task:
            activity.add("text", f"{p.name} texted: {body!r}")
            return twiml(r)
        reply = interpret_reply(body)
        dispatcher.record_reply(task.id, p.id, reply, raw=body)
        if reply is None:
            r.message("Please reply 1 if you can help, or 2 if you can't.")
        return twiml(r)

    # ---- Family dashboard -------------------------------------------------

    security = HTTPBasic(auto_error=True)

    def family_only(creds: HTTPBasicCredentials = Depends(security)):
        if not dashboard_password or not secrets.compare_digest(creds.password.encode(), dashboard_password.encode()):
            raise HTTPException(401, "Wrong password", headers={"WWW-Authenticate": "Basic"})

    @app.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(family_only)])
    async def dashboard():
        icons = {"request": "📝", "calling": "📞", "no_answer": "🔕", "declined": "🙅", "confirmed": "✅",
                 "failed": "⚠️", "told_mom": "👵", "mom_called": "☎️", "mom_said": "🗣️", "agent_said": "🤖",
                 "stranger": "🚫", "late_yes": "➕", "unclear_reply": "❓"}
        rows = "".join(
            f"<tr class='{e['kind']}'><td>{time.strftime('%a %d %b %H:%M', time.localtime(e['time']))}</td>"
            f"<td>{icons.get(e['kind'], '•')}</td><td>{html.escape(e['text'])}</td></tr>"
            for e in activity.recent(200))
        open_tasks = "".join(f"<li>{html.escape(t.describe(cfg))}</li>"
                             for t in dispatcher.tasks.values() if t.status == "working") or "<li>Nothing in progress</li>"
        return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv=refresh content=30><title>{html.escape(mom.name)}'s helper line</title>
<style>body{{font:16px system-ui;margin:16px;max-width:860px;background:#fafaf7;color:#222}}
td{{padding:6px 8px;border-bottom:1px solid #e5e5e0;vertical-align:top}}table{{border-collapse:collapse;width:100%}}
td:first-child{{white-space:nowrap;color:#777}}.failed td,.stranger td{{background:#fff1ee}}.confirmed td{{background:#eefbef}}
@media(prefers-color-scheme:dark){{body{{background:#161616;color:#eee}}td{{border-color:#333}}
.failed td,.stranger td{{background:#3a1f1a}}.confirmed td{{background:#1a3320}}}}</style>
<h1>{html.escape(mom.name)}'s helper line</h1><h2>In progress</h2><ul>{open_tasks}</ul>
<h2>Activity</h2><table>{rows}</table>"""

    @app.get("/audio/{key}.mp3")
    async def audio(key: str):
        path = speaker.path(key) if isinstance(speaker, ElevenLabsVoice) else None
        if not path:
            raise HTTPException(404)
        return FileResponse(path, media_type="audio/mpeg")

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


def _family_fallback(cfg: Config) -> Decision:
    from .brain import Contact
    first = cfg.family[0]
    return Decision(
        action="dispatch",
        say_to_mom=cfg.mom.asking_family.format(call_her=cfg.mom.call_her, name=cfg.spoken(first)),
        contacts=[Contact(helper_id=p.id, message=f"{cfg.mom.name} called her helper line and needs you. "
                          "Please call her back. Press 1 or reply 1 if you will, 2 if you can't.") for p in cfg.family],
        summary="Mom needs a call back (assistant couldn't understand)",
    )


def app_from_env() -> FastAPI:
    """Entry point for uvicorn: `uvicorn helper_agent.app:app_from_env --factory`."""
    from .brain import ClaudeBrain
    from .config import load_config
    from .telephony import TwilioPhone

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    env = os.environ
    for key in ("PUBLIC_URL", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER", "DASHBOARD_PASSWORD"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}: copy .env.example to .env and fill it in.")
    cfg = load_config(env.get("CONFIG", "config.yaml"))
    speaker = TwilioVoice()
    if cfg.settings.speech == "elevenlabs":
        if not env.get("ELEVENLABS_API_KEY") or not cfg.settings.elevenlabs_voice_id:
            raise SystemExit("speech is 'elevenlabs': set ELEVENLABS_API_KEY and settings.elevenlabs_voice_id.")
        speaker = ElevenLabsVoice(env["ELEVENLABS_API_KEY"], cfg.settings.elevenlabs_voice_id,
                                  cfg.settings.elevenlabs_model, env["PUBLIC_URL"], env.get("AUDIO_CACHE", "data/audio"))
    return create_app(
        cfg,
        brain=ClaudeBrain(cfg),
        phone=TwilioPhone(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_NUMBER"]),
        public_url=env["PUBLIC_URL"],
        activity=ActivityLog(env.get("ACTIVITY_LOG", "data/activity.jsonl")),
        twilio_auth_token=env["TWILIO_AUTH_TOKEN"],
        dashboard_password=env["DASHBOARD_PASSWORD"],
        speaker=speaker,
    )

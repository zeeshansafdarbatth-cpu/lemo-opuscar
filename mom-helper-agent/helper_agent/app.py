"""The web server Twilio talks to.

She calls her assistant            -> /voice/mom/incoming -> she speaks -> /voice/mom/heard
She asks to talk to someone        -> <Dial> them, then /voice/mom/after_dial
A reminder she set comes due       -> the assistant calls her -> /voice/mom/reminder/{id}
The assistant calls a helper       -> /voice/helper/{task}  -> key press -> /voice/helper/{task}/answer
A helper texts back                -> /sms/incoming
The family checks requests         -> /dashboard (password: DASHBOARD_PASSWORD). Her conversations, notes
                                      and reminders are private and never shown there.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import Gather, VoiceResponse

from .activity import ActivityLog
from .brain import Brain, Turn
from .config import Config
from .dispatcher import Dispatcher, interpret_reply
from .personal import Notebook, Reminder, Reminders, run_reminders
from .telephony import Phone
from .tools import Toolbox
from .voice import ElevenLabsVoice, TwilioVoice, Voice

log = logging.getLogger(__name__)

THINK_SECONDS = 9  # Twilio gives a webhook 15s; past this we say "one moment" and keep waiting.
MAX_TURNS = 20
REMINDER_RETRY_SECONDS = 600


def twiml(r) -> Response:
    return Response(str(r), media_type="application/xml")


def create_app(cfg: Config, make_brain: Callable[[Toolbox], Brain], phone: Phone, public_url: str,
               activity: ActivityLog | None = None, twilio_auth_token: str | None = None,
               dashboard_password: str | None = None, speaker: Voice | None = None,
               notebook: Notebook | None = None, reminders: Reminders | None = None,
               now: Callable[[], datetime] | None = None, reminder_check_seconds: float = 20) -> FastAPI:
    activity = activity or ActivityLog()
    speaker = speaker or TwilioVoice()
    notebook = notebook or Notebook()
    reminders = reminders or Reminders()
    tz = ZoneInfo(cfg.settings.timezone)
    now = now or (lambda: datetime.now(tz).replace(tzinfo=None))
    base = public_url.rstrip("/")
    mom, share = cfg.mom, cfg.settings.share_conversations

    dispatcher = Dispatcher(cfg, phone, public_url, activity, speaker)
    toolbox = Toolbox(cfg, dispatcher, phone, notebook, reminders, activity, now)
    brain = make_brain(toolbox)

    async def ring_reminder(r: Reminder, attempt: int = 1):
        due_reminders[r.id] = r.text
        await phone.call(mom.phones[0], url=f"{base}/voice/mom/reminder/{r.id}",
                         status_callback=f"{base}/voice/mom/reminder/{r.id}/status?attempt={attempt}",
                         ring_seconds=40)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.create_task(run_reminders(reminders, now, ring_reminder, every=reminder_check_seconds))
        yield
        loop.cancel()

    app = FastAPI(title=f"{mom.name}'s assistant", lifespan=lifespan)
    app.state.dispatcher, app.state.brain, app.state.reminders, app.state.notebook = dispatcher, brain, reminders, notebook
    validator = RequestValidator(twilio_auth_token) if twilio_auth_token else None
    thinking: dict[str, asyncio.Task] = {}
    turns: dict[str, int] = {}
    misses: dict[str, int] = {}
    call_notes: dict[str, str] = {}      # call sid -> something the assistant should know about this call
    due_reminders: dict[int, str] = {}   # reminder id -> text, while its call is being placed

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
    hints = ", ".join(dict.fromkeys(w for p in cfg.everyone for w in (p.name, p.spoken_name, p.role) if w))

    async def listen(r, prompt: str | None = None):
        # She speaks softly and takes her time: wait longer than usual before giving up.
        g = Gather(input="speech dtmf", action=f"{base}/voice/mom/heard", method="POST", language=mom.language,
                   speech_timeout="auto", timeout=12, num_digits=1, hints=hints)
        if prompt:
            await say(g, prompt)
        r.append(g)
        r.redirect(f"{base}/voice/mom/heard?silent=1", method="POST")

    def context(sid: str) -> str:
        parts = [f"Time now: {now():%A %d %B %Y, %H:%M}",
                 f"Her notebook: {notebook.describe()}",
                 f"Her reminders: {reminders.describe()}",
                 f"Help requests today: {dispatcher.status_summary()}"]
        if note := call_notes.pop(sid, None):
            parts.append(note)
        return ". ".join(parts)

    async def think_then_act(sid: str, r: VoiceResponse, heard: str | None = None) -> Response:
        """Start (or keep waiting for) the assistant's response, then speak it and carry out the call action."""
        if heard is not None:
            if share:
                activity.add("mom_said", heard)
            turns[sid] = turns.get(sid, 0) + 1
            thinking[sid] = asyncio.create_task(brain.respond(sid, heard, context(sid)))
        done, _ = await asyncio.wait({thinking[sid]}, timeout=THINK_SECONDS)
        if not done:
            await say(r, mom.still_thinking)
            r.redirect(f"{base}/voice/mom/heard", method="POST")
            return twiml(r)
        try:
            turn: Turn = thinking.pop(sid).result()
        except Exception:
            log.exception("Assistant failed")
            turn = Turn(say=mom.didnt_hear.format(call_her=mom.call_her))
        if share:
            activity.add("agent_said", turn.say)
        await say(r, turn.say)
        if turn.connect_to and (p := cfg.person(turn.connect_to)):
            activity.add("connected", f"Connected her to {p.name}")
            dial = r.dial(action=f"{base}/voice/mom/after_dial?person={p.id}", method="POST", timeout=30)
            dial.number(p.phone)
        elif turn.hang_up or turns.get(sid, 0) >= MAX_TURNS:
            r.hangup()
        else:
            await listen(r)
        return twiml(r)

    # ---- Her calls ------------------------------------------------------

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
        misses[sid], turns[sid] = 0, 0
        await listen(r, mom.greeting.format(call_her=mom.call_her))
        return twiml(r)

    @app.post("/voice/mom/heard")
    async def mom_heard(form: dict = Depends(twilio_form)):
        sid = form.get("CallSid", "")
        r = VoiceResponse()
        if sid in thinking:  # a "one moment" redirect: keep waiting for the same answer
            return await think_then_act(sid, r)
        speech = (form.get("SpeechResult") or "").strip()
        digit = (form.get("Digits") or "").strip()
        if digit and (p := cfg.person_by_speed_dial(digit)):
            heard = f"[She pressed {digit} on the keypad, her button for {p.name}.]"
        elif speech:
            heard = f"{mom.call_her}: \"{speech}\""
        else:
            misses[sid] = misses.get(sid, 0) + 1
            if misses[sid] >= 3:
                # She called but can't be heard: get a person to ring her rather than loop forever.
                turn = await brain.safe_fallback("(could not be heard)")
                await say(r, turn.say)
                r.hangup()
                return twiml(r)
            await listen(r, mom.didnt_hear.format(call_her=mom.call_her))
            return twiml(r)
        misses[sid] = 0
        return await think_then_act(sid, r, heard)

    @app.post("/voice/mom/after_dial")
    async def after_dial(person: str, form: dict = Depends(twilio_form)):
        sid, status = form.get("CallSid", ""), form.get("DialCallStatus", "")
        r = VoiceResponse()
        p = cfg.person(person)
        if status == "completed" or not p:
            r.hangup()
            return twiml(r)
        return await think_then_act(sid, r, f"[The call to {p.name} was not answered ({status}). She is still on the line.]")

    @app.post("/voice/mom/reminder/{reminder_id}")
    async def reminder_call(reminder_id: int, form: dict = Depends(twilio_form)):
        sid = form.get("CallSid", "")
        text = due_reminders.pop(reminder_id, None) or (r.text if (r := reminders.get(reminder_id)) else "")
        call_notes[sid] = f"This is a call you placed to give her a reminder she set: \"{text}\""
        misses[sid], turns[sid] = 0, 0
        resp = VoiceResponse()
        await listen(resp, text)
        return twiml(resp)

    @app.post("/voice/mom/reminder/{reminder_id}/status")
    async def reminder_status(reminder_id: int, attempt: int = 1, form: dict = Depends(twilio_form)):
        status = form.get("CallStatus", "")
        if status in ("no-answer", "busy", "failed") and attempt == 1 and reminder_id in due_reminders:
            async def retry(text=due_reminders[reminder_id]):
                await asyncio.sleep(REMINDER_RETRY_SECONDS)
                await ring_reminder(Reminder(id=reminder_id, when="", text=text), attempt=2)
            asyncio.create_task(retry())
        elif attempt >= 2:
            due_reminders.pop(reminder_id, None)
        return Response(status_code=204)

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
        reply = {"1": "yes", "2": "no"}.get(form.get("Digits", ""))
        p = cfg.person(person)
        r = VoiceResponse()
        if reply and p:
            dispatcher.record_reply(task_id, person, reply)
            await say(r, mom.helper_thanks, lang=cfg.lang_for(p), voice=p.voice)
        else:
            dispatcher.record_no_answer(task_id, person, attempt)
        r.hangup()
        return twiml(r)

    @app.post("/voice/helper/{task_id}/status")
    async def helper_status(task_id: str, person: str, attempt: int = 1, form: dict = Depends(twilio_form)):
        # Arrives when the call ends. If they pressed 1 or 2 the dispatcher has already moved on, and ignores this.
        dispatcher.record_no_answer(task_id, person, attempt)
        return Response(status_code=204)

    # ---- Text replies -----------------------------------------------------

    @app.post("/sms/incoming")
    async def sms_incoming(form: dict = Depends(twilio_form)):
        sender, body = form.get("From", ""), (form.get("Body") or "").strip()
        p = cfg.person_by_phone(sender)
        r = MessagingResponse()
        if not p or cfg.is_mom(sender):
            return twiml(r)
        task = dispatcher.open_task_for(p.id)
        if not task:
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
                 "failed": "⚠️", "told_mom": "👵", "mom_said": "🗣️", "agent_said": "🤖", "connected": "🔗",
                 "message": "💬", "stranger": "🚫", "late_yes": "➕", "unclear_reply": "❓"}
        rows = "".join(
            f"<tr class='{e['kind']}'><td>{time.strftime('%a %d %b %H:%M', time.localtime(e['time']))}</td>"
            f"<td>{icons.get(e['kind'], '•')}</td><td>{html.escape(e['text'])}</td></tr>"
            for e in activity.recent(200))
        open_tasks = "".join(f"<li>{html.escape(t.describe(cfg))}</li>"
                             for t in dispatcher.tasks.values() if t.status == "working") or "<li>Nothing in progress</li>"
        privacy = "" if share else "<p class=note>Her conversations, notes and reminders are private and not shown here.</p>"
        return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv=refresh content=30><title>{html.escape(mom.name)}'s assistant</title>
<style>body{{font:16px system-ui;margin:16px;max-width:860px;background:#fafaf7;color:#222}}
td{{padding:6px 8px;border-bottom:1px solid #e5e5e0;vertical-align:top}}table{{border-collapse:collapse;width:100%}}
td:first-child{{white-space:nowrap;color:#777}}.failed td,.stranger td{{background:#fff1ee}}.confirmed td{{background:#eefbef}}
.note{{color:#777}}@media(prefers-color-scheme:dark){{body{{background:#161616;color:#eee}}td{{border-color:#333}}
.failed td,.stranger td{{background:#3a1f1a}}.confirmed td{{background:#1a3320}}}}</style>
<h1>{html.escape(mom.name)}'s assistant</h1>{privacy}<h2>In progress</h2><ul>{open_tasks}</ul>
<h2>What the assistant did</h2><table>{rows}</table>"""

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
    data = env.get("DATA_DIR", "data")
    speaker = TwilioVoice()
    if cfg.settings.speech == "elevenlabs":
        if not env.get("ELEVENLABS_API_KEY") or not cfg.settings.elevenlabs_voice_id:
            raise SystemExit("speech is 'elevenlabs': set ELEVENLABS_API_KEY and settings.elevenlabs_voice_id.")
        speaker = ElevenLabsVoice(env["ELEVENLABS_API_KEY"], cfg.settings.elevenlabs_voice_id,
                                  cfg.settings.elevenlabs_model, env["PUBLIC_URL"], f"{data}/audio")
    return create_app(
        cfg,
        make_brain=lambda toolbox: ClaudeBrain(cfg, toolbox),
        phone=TwilioPhone(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_NUMBER"]),
        public_url=env["PUBLIC_URL"],
        activity=ActivityLog(f"{data}/activity.jsonl"),
        twilio_auth_token=env["TWILIO_AUTH_TOKEN"],
        dashboard_password=env["DASHBOARD_PASSWORD"],
        speaker=speaker,
        notebook=Notebook(f"{data}/notebook.json"),
        reminders=Reminders(f"{data}/reminders.json"),
    )

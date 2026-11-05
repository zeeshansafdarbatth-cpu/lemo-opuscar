import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from helper_agent.activity import ActivityLog
from helper_agent.app import create_app
from helper_agent.brain import ClaudeBrain, build_system_prompt
from helper_agent.brain_types import Contact, Decision
from helper_agent.config import load_config
from helper_agent.dispatcher import Dispatcher, Task, interpret_reply
from helper_agent.offline_brain import KeywordBrain
from helper_agent.personal import Notebook, Reminders
from helper_agent.telephony import ConsolePhone
from helper_agent.tools import Outcome, Toolbox

CONFIG = Path(__file__).parent.parent / "config.example.yaml"
NOW = datetime(2026, 11, 6, 10, 0)


@pytest.fixture
def cfg():
    c = load_config(CONFIG)
    c.settings.attempts_per_helper = 3
    c.settings.seconds_between_attempts = 0.05
    c.settings.wait_for_answer_seconds = 0.2
    return c


def dispatch(*ids, action="dispatch"):
    return Decision(action=action, summary="Ride to the doctor",
                    contacts=[Contact(helper_id=i, message=f"msg for {i}") for i in ids])


def calls_to(phone, cfg, pid):
    return [c for c in phone.calls if c["to"] == cfg.person(pid).phone]


def calls_to_mom(phone, cfg):
    return [c for c in phone.calls if c["to"] == cfg.mom.phones[0]]


def make_toolbox(cfg, phone=None, now=lambda: NOW):
    phone = phone or ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    return Toolbox(cfg, d, phone, Notebook(), Reminders(), ActivityLog(), now), d, phone


async def answer_when_called(d, phone, cfg, pid, reply, on_attempt=1):
    """Plays a helper who answers the Nth call with `reply`; earlier calls ring out."""
    seen = 0
    while True:
        await asyncio.sleep(0.01)
        n = len(calls_to(phone, cfg, pid))
        while seen < n:
            seen += 1
            task = next(iter(d.tasks.values()))
            if seen == on_attempt:
                d.record_reply(task.id, pid, reply)
                return
            d.record_no_answer(task.id, pid, seen)


# ---- the dispatcher: persistence on her behalf ------------------------------


async def test_retries_until_helper_answers(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    helper = asyncio.create_task(answer_when_called(d, phone, cfg, "driver", "yes", on_attempt=3))
    task = d.start(dispatch("driver", "son"))
    await d.wait_idle()
    await helper
    assert task.status == "done" and task.helped_by == "driver"
    assert len(calls_to(phone, cfg, "driver")) == 3 and not calls_to(phone, cfg, "son")
    assert cfg.mom.said_yes.format(call_her=cfg.mom.call_her, name="راشد") in calls_to_mom(phone, cfg)[-1]["twiml"]


async def test_moves_to_backup_after_decline(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    a = asyncio.create_task(answer_when_called(d, phone, cfg, "driver", "no"))
    b = asyncio.create_task(answer_when_called(d, phone, cfg, "son", "yes"))
    task = d.start(dispatch("driver", "son"))
    await d.wait_idle()
    await asyncio.gather(a, b)
    assert task.helped_by == "son" and len(calls_to(phone, cfg, "driver")) == 1


async def test_nobody_answers_alerts_family_and_tells_her(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("driver", "maid"))
    await d.wait_idle()
    assert task.status == "failed"
    assert len(calls_to(phone, cfg, "driver")) == 3 and len(calls_to(phone, cfg, "maid")) == 3
    assert any(t["to"] == cfg.person("son").phone and "Nobody said yes" in t["body"] for t in phone.texts)
    assert "راشد اور شازیہ" in calls_to_mom(phone, cfg)[-1]["twiml"]


async def test_text_reply_counts_while_waiting_between_calls(cfg):
    cfg.settings.seconds_between_attempts = 5
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("driver"))
    await asyncio.sleep(0.3)
    assert d.open_task_for("driver") is task
    d.record_reply(task.id, "driver", interpret_reply("Ji haan, aa raha hoon"))
    await asyncio.wait_for(d.wait_idle(), 2)
    assert task.status == "done" and len(calls_to(phone, cfg, "driver")) == 1


async def test_stale_call_status_does_not_skip_next_helper(cfg):
    cfg.settings.wait_for_answer_seconds = 0.5
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("driver", "son"))
    await asyncio.sleep(0.05)
    d.record_reply(task.id, "driver", "no")
    d.record_no_answer(task.id, "driver", 1)
    await asyncio.sleep(0.1)
    assert task.current == "son"
    d.record_reply(task.id, "son", "yes")
    await d.wait_idle()
    assert task.helped_by == "son" and len(calls_to(phone, cfg, "son")) == 1


async def test_emergency_calls_everyone_at_once(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("nurse", "son", action="emergency"))
    await asyncio.sleep(0.05)
    assert calls_to(phone, cfg, "nurse") and calls_to(phone, cfg, "son")
    d.record_reply(task.id, "nurse", "yes")
    await d.wait_idle()
    assert task.helped_by == "nurse"


def test_interpret_reply():
    assert interpret_reply("1") == "yes" and interpret_reply("Yes coming") == "yes"
    assert interpret_reply("nahi, sorry") == "no" and interpret_reply("2") == "no"
    assert interpret_reply("who is this?") is None


# ---- her tools ----------------------------------------------------------------


async def test_tools_only_reach_people_on_her_list(cfg):
    tb, d, phone = make_toolbox(cfg)
    out = Outcome()
    assert (await tb.run("connect_call", {"person_id": "stranger"}, out)).startswith("ERROR") and not out.connect_to
    assert (await tb.run("send_message", {"person_id": "stranger", "text": "hi"}, out)).startswith("ERROR")
    r = await tb.run("get_help", {"contacts": [{"person_id": "stranger", "message": "x"}], "urgency": "normal", "summary": "s"}, out)
    assert r.startswith("ERROR") and not d.tasks
    assert not phone.calls and not phone.texts


async def test_emergency_always_includes_family(cfg):
    tb, d, _ = make_toolbox(cfg)
    await tb.run("get_help", {"contacts": [{"person_id": "nurse", "message": "come"}], "urgency": "emergency", "summary": "fall"}, Outcome())
    task = next(iter(d.tasks.values()))
    assert {c.helper_id for c in task.decision.contacts} == {"nurse", "son"}
    for t in list(d._running):
        t.cancel()


async def test_reminders_and_notebook(cfg, tmp_path):
    tb, _, _ = make_toolbox(cfg)
    tb.reminders, tb.notebook = Reminders(tmp_path / "r.json"), Notebook(tmp_path / "n.json")
    out = Outcome()
    assert "set for Friday 06 November at 17:00" in await tb.run("set_reminder", {"when": "2026-11-06T17:00", "text": "call Nasreen", "repeat": "none"}, out)
    assert (await tb.run("set_reminder", {"when": "2026-11-05T09:00", "text": "x", "repeat": "none"}, out)).startswith("ERROR")
    await tb.run("set_reminder", {"when": "2026-11-06T09:00", "text": "medicine", "repeat": "daily"}, out)
    await tb.run("remember", {"note": "gold bangles in the blue trunk"}, out)
    # Saved to disk, so a restart keeps them.
    assert "blue trunk" in Notebook(tmp_path / "n.json").describe()
    reloaded = Reminders(tmp_path / "r.json")
    due = reloaded.pop_due(datetime(2026, 11, 6, 17, 1))
    assert {r.text for r in due} == {"call Nasreen", "medicine"}
    assert "Sat 07 Nov 09:00 every day: medicine" in reloaded.describe()  # daily one moved to tomorrow
    assert "Nasreen" not in reloaded.describe()


# ---- the Claude tool loop (with a scripted fake API) --------------------------


class FakeClaude:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.beta = NS(messages=NS(create=self.create))

    async def create(self, **kw):
        self.requests.append(kw)
        return self.responses.pop(0)


def msg(stop, *blocks):
    return NS(stop_reason=stop, stop_details=None, content=list(blocks))


async def test_claude_loop_runs_tools_then_speaks(cfg):
    tb, _, _ = make_toolbox(cfg)
    fake = FakeClaude([
        msg("tool_use", NS(type="tool_use", id="tu1", name="remember", input={"note": "keys in drawer"})),
        msg("tool_use", NS(type="tool_use", id="tu2", name="connect_call", input={"person_id": "son"})),
        msg("end_turn", NS(type="text", text="امی جی، میں ذیشان سے ملا رہی ہوں۔")),
    ])
    brain = ClaudeBrain(cfg, tb, client=fake)
    turn = await brain.respond("CA1", 'امی جی: "ذیشان سے بات کراؤ"', "ctx")
    assert turn.connect_to == "son" and "ذیشان" in turn.say and not turn.hang_up
    assert "keys in drawer" in tb.notebook.describe()
    req = fake.requests[-1]
    assert req["model"] == "claude-opus-5-5" and req["fallbacks"] == "default"
    assert any(t.get("type") == "web_search_20260209" for t in req["tools"])
    results = req["messages"][-2]["content"]  # tool results sent back (the final reply follows them)
    assert results[0]["tool_use_id"] == "tu2"


async def test_claude_loop_resumes_paused_search(cfg):
    tb, _, _ = make_toolbox(cfg)
    fake = FakeClaude([msg("pause_turn", NS(type="server_tool_use")), msg("end_turn", NS(type="text", text="بارش ہوگی۔"))])
    turn = await ClaudeBrain(cfg, tb, client=fake).respond("CA2", "weather?", "ctx")
    assert turn.say == "بارش ہوگی۔" and len(fake.requests) == 2


async def test_claude_refusal_gets_family_to_call(cfg):
    tb, d, _ = make_toolbox(cfg)
    turn = await ClaudeBrain(cfg, tb, client=FakeClaude([msg("refusal")])).respond("CA3", "x", "ctx")
    assert turn.hang_up and "ذیشان" in turn.say and d.tasks
    for t in list(d._running):
        t.cancel()


def test_system_prompt(cfg):
    prompt = build_system_prompt(cfg)
    for p in cfg.everyone:
        assert f"id: {p.id}" in prompt
    assert cfg.mom.call_her in prompt and "1122" in prompt and "Rashid (say: راشد)" in prompt
    assert "Punjabi and Urdu" in prompt and "She is in charge" in prompt and "private" in prompt


# ---- the phone line ------------------------------------------------------------


@pytest.fixture
def server(cfg):
    phone = ConsolePhone()
    app = create_app(cfg, lambda tb: KeywordBrain(cfg, tb), phone, "https://helper.example",
                     dashboard_password="pw", now=lambda: NOW)
    with TestClient(app) as client:
        yield client, app, phone


def mom_says(client, cfg, sid, speech=None, digits=None):
    client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": sid})
    data = {"CallSid": sid, **({"SpeechResult": speech} if speech else {}), **({"Digits": digits} if digits else {})}
    return client.post("/voice/mom/heard", data=data)


def test_stranger_is_refused(server, cfg):
    client, _, _ = server
    r = client.post("/voice/mom/incoming", data={"From": "+15550000000", "CallSid": "CA1"})
    assert cfg.mom.stranger in r.text and "<Hangup" in r.text


def test_greeting_listens_patiently_in_urdu(server, cfg):
    client, _, _ = server
    r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA1"})
    assert cfg.mom.greeting.format(call_her=cfg.mom.call_her) in r.text
    assert 'language="ur-PK"' in r.text and 'timeout="12"' in r.text and "راشد" in r.text


def test_help_request_and_helper_presses_1(server, cfg):
    client, app, _ = server
    r = mom_says(client, cfg, "CA1", "I need a ride to the doctor")
    assert "calling Rashid" in r.text and "<Hangup" in r.text
    task = next(iter(app.state.dispatcher.tasks.values()))
    r = client.post(f"/voice/helper/{task.id}?person=driver&attempt=1", data={})
    assert "Press 1" in r.text
    client.post(f"/voice/helper/{task.id}/answer?person=driver&attempt=1", data={"Digits": "1"})
    for _ in range(50):
        if task.status != "working":
            break
        client.get("/health")
        time.sleep(0.02)
    assert task.helped_by == "driver"


def test_connects_her_to_someone_live(server, cfg):
    client, _, _ = server
    r = mom_says(client, cfg, "CA2", "I want to talk to Zeeshan")
    assert "<Dial" in r.text and cfg.person("son").phone in r.text and "after_dial?person=son" in r.text
    r = client.post("/voice/mom/after_dial?person=son", data={"CallSid": "CA2", "DialCallStatus": "completed"})
    assert "<Hangup" in r.text
    r = client.post("/voice/mom/after_dial?person=son", data={"CallSid": "CA2", "DialCallStatus": "no-answer"})
    assert r.status_code == 200 and "<Say" in r.text  # the assistant offers what to do next


def test_speed_dial_key(server, cfg):
    client, _, _ = server
    r = mom_says(client, cfg, "CA3", digits="1")
    assert "calling Rashid" in r.text


def test_three_silences_get_family_to_call(server, cfg):
    client, app, _ = server
    client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA4"})
    for _ in range(2):
        r = client.post("/voice/mom/heard?silent=1", data={"CallSid": "CA4"})
        assert cfg.mom.didnt_hear.format(call_her=cfg.mom.call_her) in r.text
    r = client.post("/voice/mom/heard?silent=1", data={"CallSid": "CA4"})
    assert cfg.mom.asking_family.format(call_her=cfg.mom.call_her, name="ذیشان") in r.text
    assert app.state.dispatcher.tasks


def test_reminder_call(cfg):
    phone = ConsolePhone()
    reminders = Reminders()
    reminders.add(NOW - timedelta(minutes=1), "دوائی کا وقت ہو گیا ہے")
    app = create_app(cfg, lambda tb: KeywordBrain(cfg, tb), phone, "https://helper.example",
                     reminders=reminders, now=lambda: NOW, reminder_check_seconds=0.01)
    with TestClient(app) as client:
        for _ in range(50):
            if phone.calls:
                break
            time.sleep(0.02)
        assert "/voice/mom/reminder/1" in phone.calls[0]["url"]
        r = client.post("/voice/mom/reminder/1", data={"CallSid": "CA5"})
        assert "دوائی کا وقت ہو گیا ہے" in r.text and "<Gather" in r.text
    assert not reminders.items


def test_dashboard_keeps_her_words_private(server, cfg):
    client, _, _ = server
    mom_says(client, cfg, "CA6", "I need a ride to the doctor")
    assert client.get("/dashboard").status_code == 401
    page = client.get("/dashboard", auth=("family", "pw")).text
    assert "private" in page and "Calling Rashid" in page
    assert "🗣️" not in page and "🤖" not in page  # nothing she said, nothing the assistant said to her


def test_sms_reply(server, cfg):
    client, app, _ = server
    d = app.state.dispatcher
    task = d.tasks["manual"] = Task(id="manual", decision=dispatch("driver"))
    task.contacted.add("driver")
    task.current = "driver"
    client.post("/sms/incoming", data={"From": cfg.person("driver").phone, "Body": "YES"})
    assert task.inbox.get_nowait()[:2] == ("yes", "driver")


def test_twilio_signature_checked(cfg):
    app = create_app(cfg, lambda tb: KeywordBrain(cfg, tb), ConsolePhone(), "https://helper.example", twilio_auth_token="secret")
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0]}, headers={"X-Twilio-Signature": "bad"})
        assert r.status_code == 403


async def test_punjabi_emergency_offline(cfg):
    tb, d, _ = make_toolbox(cfg)
    turn = await KeywordBrain(cfg, tb).respond("CA7", "میں باتھ روم وچ ڈگ پئی آں", "")
    assert turn.hang_up and next(iter(d.tasks.values())).decision.action == "emergency"
    for t in list(d._running):
        t.cancel()


def test_elevenlabs_voice_plays_cached_audio(cfg, tmp_path):
    from helper_agent.voice import ElevenLabsVoice
    voice = ElevenLabsVoice("key", "voice123", "eleven_v3", "https://helper.example", tmp_path)
    made = []
    voice._synthesize = lambda text, vid: made.append(text) or b"ID3fake"
    app = create_app(cfg, lambda tb: KeywordBrain(cfg, tb), ConsolePhone(), "https://helper.example", speaker=voice)
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA9"})
        assert "<Play>https://helper.example/audio/" in r.text and "<Say" not in r.text
        url = r.text.split("<Play>")[1].split("</Play>")[0]
        assert client.get(url.replace("https://helper.example", "")).content == b"ID3fake"
        client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA10"})
        assert len(made) == 1
        assert client.get("/audio/..%2Fsecret.mp3").status_code == 404


def test_elevenlabs_failure_falls_back_to_twilio_voice(cfg, tmp_path):
    from helper_agent.voice import ElevenLabsVoice
    voice = ElevenLabsVoice("key", "voice123", "eleven_v3", "https://helper.example", tmp_path)

    def boom(text, vid):
        raise OSError("network down")
    voice._synthesize = boom
    app = create_app(cfg, lambda tb: KeywordBrain(cfg, tb), ConsolePhone(), "https://helper.example", speaker=voice)
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA11"})
        assert "<Say" in r.text

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helper_agent.activity import ActivityLog
from helper_agent.app import create_app
from helper_agent.brain import ClaudeBrain, Contact, Decision, build_system_prompt
from helper_agent.config import load_config
from helper_agent.dispatcher import Dispatcher, interpret_reply
from helper_agent.offline_brain import KeywordBrain
from helper_agent.telephony import ConsolePhone

CONFIG = Path(__file__).parent.parent / "config.example.yaml"


@pytest.fixture
def cfg():
    c = load_config(CONFIG)
    c.settings.attempts_per_helper = 3
    c.settings.seconds_between_attempts = 0.05
    c.settings.wait_for_answer_seconds = 0.2
    return c


def dispatch(*ids, action="dispatch"):
    return Decision(action=action, say_to_mom="ok", summary="Ride to the doctor",
                    contacts=[Contact(helper_id=i, message=f"msg for {i}") for i in ids])


def calls_to(phone, cfg, pid):
    return [c for c in phone.calls if c["to"] == cfg.person(pid).phone]


async def answer_when_called(d, phone, cfg, pid, reply, on_attempt=1):
    """Plays a helper who answers the Nth call with `reply` ('yes'/'no'); earlier calls ring out."""
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


async def test_retries_until_helper_answers(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    helper = asyncio.create_task(answer_when_called(d, phone, cfg, "driver", "yes", on_attempt=3))
    task = d.start(dispatch("driver", "son"))
    await d.wait_idle()
    await helper
    assert task.status == "done" and task.helped_by == "driver"
    assert len(calls_to(phone, cfg, "driver")) == 3
    assert not calls_to(phone, cfg, "son")
    mom_call = calls_to_mom(phone, cfg)
    assert mom_call and cfg.mom.said_yes.format(call_her=cfg.mom.call_her, name="راشد") in mom_call[-1]["twiml"]


def calls_to_mom(phone, cfg):
    return [c for c in phone.calls if c["to"] == cfg.mom.phones[0]]


async def test_moves_to_backup_after_decline(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    a = asyncio.create_task(answer_when_called(d, phone, cfg, "driver", "no"))
    b = asyncio.create_task(answer_when_called(d, phone, cfg, "son", "yes"))
    task = d.start(dispatch("driver", "son"))
    await d.wait_idle()
    await asyncio.gather(a, b)
    assert task.helped_by == "son"
    assert len(calls_to(phone, cfg, "driver")) == 1  # a "no" is not retried


async def test_nobody_answers_alerts_family_and_tells_mom(cfg):
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("driver", "maid"))
    await d.wait_idle()
    assert task.status == "failed"
    assert len(calls_to(phone, cfg, "driver")) == 3 and len(calls_to(phone, cfg, "maid")) == 3
    family_phone = cfg.person("son").phone
    assert any(t["to"] == family_phone and "Nobody said yes" in t["body"] for t in phone.texts)
    assert "راشد اور شازیہ" in calls_to_mom(phone, cfg)[-1]["twiml"]


async def test_text_reply_counts_while_waiting_between_calls(cfg):
    cfg.settings.seconds_between_attempts = 5
    phone = ConsolePhone()
    d = Dispatcher(cfg, phone, "https://x", ActivityLog())
    task = d.start(dispatch("driver"))
    await asyncio.sleep(0.3)  # first call rang out, now waiting before the second
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
    d.record_no_answer(task.id, "driver", 1)  # the call-ended signal for the same call
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
    assert interpret_reply("1") == "yes"
    assert interpret_reply("Yes coming") == "yes"
    assert interpret_reply("nahi, sorry") == "no"
    assert interpret_reply("2") == "no"
    assert interpret_reply("who is this?") is None


def test_claude_brain_drops_unknown_people(cfg):
    brain = ClaudeBrain(cfg, client=object())
    d = brain.clean(dispatch("driver", "stranger"))
    assert [c.helper_id for c in d.contacts] == ["driver"]
    d = brain.clean(dispatch("stranger"))
    assert {c.helper_id for c in d.contacts} == {"son"}  # falls back to family
    d = brain.clean(dispatch("nurse", action="emergency"))
    assert {c.helper_id for c in d.contacts} == {"nurse", "son"}  # family always in an emergency


def test_system_prompt_lists_everyone(cfg):
    prompt = build_system_prompt(cfg)
    for p in cfg.everyone:
        assert f"id: {p.id}" in prompt
    assert cfg.mom.call_her in prompt and "1122" in prompt
    assert "Punjabi and Urdu" in prompt and "Urdu script" in prompt
    assert "Rashid (say: راشد)" in prompt


# ---- webhooks --------------------------------------------------------------


@pytest.fixture
def server(cfg):
    phone = ConsolePhone()
    app = create_app(cfg, KeywordBrain(cfg), phone, "https://helper.example", dashboard_password="pw")
    with TestClient(app) as client:
        yield client, app, phone


def test_stranger_is_refused(server, cfg):
    client, _, _ = server
    r = client.post("/voice/mom/incoming", data={"From": "+15550000000", "CallSid": "CA1"})
    assert cfg.mom.stranger in r.text and "<Hangup" in r.text


def test_mom_call_dispatches_and_helper_presses_1(server, cfg):
    client, app, phone = server
    r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA1"})
    assert cfg.mom.greeting.format(call_her=cfg.mom.call_her) in r.text
    assert 'language="ur-PK"' in r.text and "Rashid" in r.text  # Urdu recognition, names as hints
    r = client.post("/voice/mom/heard", data={"CallSid": "CA1", "SpeechResult": "I need a ride to the doctor"})
    assert "calling Rashid" in r.text and "<Hangup" in r.text
    d = app.state.dispatcher
    task = next(iter(d.tasks.values()))
    r = client.post(f"/voice/helper/{task.id}?person=driver&attempt=1", data={})
    assert "Press 1" in r.text and "<Gather" in r.text
    client.post(f"/voice/helper/{task.id}/answer?person=driver&attempt=1", data={"Digits": "1"})
    client.post(f"/voice/helper/{task.id}/status?person=driver&attempt=1", data={"CallStatus": "completed"})
    for _ in range(50):
        if task.status != "working":
            break
        client.get("/health")  # let the background task run
        import time; time.sleep(0.02)
    assert task.status == "done" and task.helped_by == "driver"


def test_speed_dial_key(server, cfg):
    client, _, _ = server
    client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA2"})
    r = client.post("/voice/mom/heard", data={"CallSid": "CA2", "Digits": "1"})
    assert "calling Rashid" in r.text


def test_three_silences_get_family_to_call(server, cfg):
    client, app, _ = server
    client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA3"})
    for _ in range(2):
        r = client.post("/voice/mom/heard?silent=1", data={"CallSid": "CA3"})
        assert cfg.mom.didnt_hear.format(call_her=cfg.mom.call_her) in r.text
    r = client.post("/voice/mom/heard?silent=1", data={"CallSid": "CA3"})
    assert cfg.mom.asking_family.format(call_her=cfg.mom.call_her, name="ذیشان") in r.text
    assert app.state.dispatcher.tasks


def test_sms_reply(server, cfg):
    client, app, _ = server
    d = app.state.dispatcher
    task = d.tasks["manual"] = __import__("helper_agent.dispatcher", fromlist=["Task"]).Task(id="manual", decision=dispatch("driver"))
    task.contacted.add("driver"); task.current = "driver"
    client.post("/sms/incoming", data={"From": cfg.person("driver").phone, "Body": "YES"})
    assert task.inbox.get_nowait()[:2] == ("yes", "driver")


def test_dashboard_needs_password(server):
    client, _, _ = server
    assert client.get("/dashboard").status_code == 401
    r = client.get("/dashboard", auth=("family", "pw"))
    assert r.status_code == 200 and "helper line" in r.text


def test_twilio_signature_checked(cfg):
    app = create_app(cfg, KeywordBrain(cfg), ConsolePhone(), "https://helper.example", twilio_auth_token="secret")
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0]}, headers={"X-Twilio-Signature": "bad"})
        assert r.status_code == 403


def test_punjabi_emergency_offline(cfg):
    d = asyncio.run(KeywordBrain(cfg).decide([], "میں باتھ روم وچ ڈگ پئی آں", ""))
    assert d.action == "emergency"


def test_elevenlabs_voice_plays_cached_audio(cfg, tmp_path):
    from helper_agent.voice import ElevenLabsVoice
    voice = ElevenLabsVoice("key", "voice123", "eleven_v3", "https://helper.example", tmp_path)
    calls = []
    voice._synthesize = lambda text, vid: calls.append(text) or b"ID3fake"
    app = create_app(cfg, KeywordBrain(cfg), ConsolePhone(), "https://helper.example", speaker=voice)
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA9"})
        assert "<Play>https://helper.example/audio/" in r.text and "<Say" not in r.text
        url = r.text.split("<Play>")[1].split("</Play>")[0]
        assert client.get(url.replace("https://helper.example", "")).content == b"ID3fake"
        client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA10"})
        assert len(calls) == 1  # the greeting is made once, then reused
        assert client.get("/audio/..%2Fsecret.mp3").status_code == 404


def test_elevenlabs_failure_falls_back_to_twilio_voice(cfg, tmp_path):
    from helper_agent.voice import ElevenLabsVoice
    voice = ElevenLabsVoice("key", "voice123", "eleven_v3", "https://helper.example", tmp_path)
    def boom(text, vid):
        raise OSError("network down")
    voice._synthesize = boom
    app = create_app(cfg, KeywordBrain(cfg), ConsolePhone(), "https://helper.example", speaker=voice)
    with TestClient(app) as client:
        r = client.post("/voice/mom/incoming", data={"From": cfg.mom.phones[0], "CallSid": "CA11"})
        assert "<Say" in r.text

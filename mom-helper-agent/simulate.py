"""Try her assistant in the terminal, no phone account needed.

    python simulate.py                 # uses Claude if ANTHROPIC_API_KEY (or `ant auth login`) is set
    python simulate.py --offline       # simple keyword brain, no API needed

You type what Mom says. When the agent "calls" a helper you play the helper:
1 = coming, 2 = can't, Enter = doesn't answer.
"""

from __future__ import annotations

import argparse
import html
import re
import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlparse

from helper_agent.activity import ActivityLog
from helper_agent.config import load_config
from helper_agent.dispatcher import Dispatcher
from helper_agent.personal import Notebook, Reminders, run_reminders
from helper_agent.tools import Toolbox


class SimPhone:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dispatcher: Dispatcher | None = None
        self.lock = asyncio.Lock()

    async def sms(self, to, body):
        who = self.cfg.person_by_phone(to)
        print(f"   💬 text to {who.name if who else to}: {body}")

    async def call(self, to, *, url=None, twiml=None, status_callback=None, ring_seconds=25):
        who = self.cfg.person_by_phone(to)
        name = who.name if who else ("Mom" if self.cfg.is_mom(to) else to)
        if twiml:  # a message read out (to Mom or family)
            m = re.search(r"<Say[^>]*>(.*?)</Say>", twiml, re.S)
            text = html.unescape(m.group(1)) if m else twiml
            print(f"   📞 calls {name} and says: {text}")
            return "sim"
        path = urlparse(url)
        q = parse_qs(path.query)
        task_id, person, attempt = path.path.rsplit("/", 1)[-1], q["person"][0], int(q["attempt"][0])
        asyncio.create_task(self._ring(task_id, person, attempt, name))
        return "sim"

    async def _ring(self, task_id, person, attempt, name):
        async with self.lock:
            if self.dispatcher.tasks[task_id].status != "working":
                return
            try:
                ans = await asyncio.to_thread(input, f"   📞 {name}'s phone rings (try {attempt}). You are {name}: 1=coming, 2=can't, Enter=no answer > ")
            except EOFError:
                ans = ""
        reply = {"1": "yes", "2": "no"}.get(ans.strip())
        if reply:
            self.dispatcher.record_reply(task_id, person, reply)
        else:
            self.dispatcher.record_no_answer(task_id, person, attempt)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml" if os.path.exists("config.yaml") else "config.example.yaml")
    ap.add_argument("--offline", action="store_true", help="keyword brain instead of Claude")
    args = ap.parse_args()

    cfg = load_config(args.config)
    s = cfg.settings
    s.seconds_between_attempts, s.wait_for_answer_seconds = 3, 60  # faster for a demo
    now = lambda: datetime.now(ZoneInfo(s.timezone)).replace(tzinfo=None)

    phone = SimPhone(cfg)
    dispatcher = Dispatcher(cfg, phone, "http://sim", ActivityLog())
    phone.dispatcher = dispatcher
    notebook, reminders = Notebook(), Reminders()
    toolbox = Toolbox(cfg, dispatcher, phone, notebook, reminders, ActivityLog(), now)
    if args.offline:
        from helper_agent.offline_brain import KeywordBrain
        brain = KeywordBrain(cfg, toolbox)
    else:
        from helper_agent.brain import ClaudeBrain
        brain = ClaudeBrain(cfg, toolbox)

    async def ring(r):
        print(f"\n   ⏰ the assistant phones {cfg.mom.call_her}: {r.text}")
    reminder_loop = asyncio.create_task(run_reminders(reminders, now, ring, every=5))

    mom = cfg.mom
    call = 1
    print(f"\n☎️  {mom.name} calls her assistant. (Type what she says. 'quit' to stop.)\n")
    print(f"🤖 {mom.greeting.format(call_her=mom.call_her)}")
    while True:
        try:
            heard = (await asyncio.to_thread(input, f"👵 {mom.call_her}: ")).strip()
        except EOFError:
            break
        if heard.lower() in ("quit", "exit"):
            break
        if not heard:
            continue
        context = (f"Time now: {now():%A %d %B %Y, %H:%M}. Her notebook: {notebook.describe()}. "
                   f"Her reminders: {reminders.describe()}. Help requests today: {dispatcher.status_summary()}")
        turn = await brain.respond(f"call{call}", f"{mom.call_her}: \"{heard}\"", context)
        print(f"🤖 {turn.say}")
        if turn.connect_to or turn.hang_up:
            if turn.connect_to:
                print(f"   🔗 (she is now talking with {cfg.person(turn.connect_to).name} in a live call)")
            else:
                print("   (call ends; the assistant works in the background)")
            await dispatcher.wait_idle()
            call += 1
            print(f"\n☎️  {mom.call_her} calls again later.\n🤖 {mom.greeting.format(call_her=mom.call_her)}")
    reminder_loop.cancel()


if __name__ == "__main__":
    asyncio.run(main())

"""Try the helper line in the terminal, no phone account needed.

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
from urllib.parse import parse_qs, urlparse

from helper_agent.activity import ActivityLog
from helper_agent.config import load_config
from helper_agent.dispatcher import Dispatcher


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
            ans = await asyncio.to_thread(input, f"   📞 {name}'s phone rings (try {attempt}). You are {name}: 1=coming, 2=can't, Enter=no answer > ")
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
    if args.offline:
        from helper_agent.offline_brain import KeywordBrain
        brain = KeywordBrain(cfg)
    else:
        from helper_agent.brain import ClaudeBrain
        brain = ClaudeBrain(cfg)

    phone = SimPhone(cfg)
    dispatcher = Dispatcher(cfg, phone, "http://sim", ActivityLog())
    phone.dispatcher = dispatcher

    mom = cfg.mom
    print(f"\n☎️  {mom.name} calls the helper line. (Type what she says. 'quit' to stop.)\n")
    print(f"🤖 {mom.greeting.format(call_her=mom.call_her)}")
    history: list[dict] = []
    while True:
        heard = (await asyncio.to_thread(input, f"👵 {mom.call_her}: ")).strip()
        if heard.lower() in ("quit", "exit"):
            break
        if not heard:
            continue
        context = f"Time now: {datetime.now():%A %d %B, %H:%M}. Earlier requests: {dispatcher.status_summary()}"
        decision = await brain.decide(history, heard, context)
        history += [{"role": "user", "content": f"[{context}]\n{mom.call_her} says: \"{heard}\""},
                    {"role": "assistant", "content": decision.model_dump_json()}]
        print(f"🤖 {decision.say_to_mom}")
        if decision.action in ("dispatch", "emergency"):
            print("   (call ends; the agent works in the background)")
            dispatcher.start(decision)
            await dispatcher.wait_idle()
            history.clear()
            print(f"\n☎️  {mom.call_her} calls again later.\n🤖 {mom.greeting.format(call_her=mom.call_her)}")
        elif decision.action == "goodbye":
            break


if __name__ == "__main__":
    asyncio.run(main())

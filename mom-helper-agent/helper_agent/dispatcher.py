"""The persistent part: calls helpers for Mom, retries, moves to backups, and reports back.

For each request it works down the contact list. Each person gets a text, then up to
`attempts_per_helper` calls. A "yes" (key 1 on the call, or a text reply) from anyone
contacted ends the search; a "no" moves on to the next person. If nobody says yes,
family is alerted. Either way Mom gets a call back with the result.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import re
import time
from dataclasses import dataclass, field

from .activity import ActivityLog
from .brain import Decision
from .config import Config, Person
from .telephony import Phone, say_twiml

log = logging.getLogger(__name__)

_ids = itertools.count(1)

YES_WORDS = {"1", "yes", "y", "ok", "okay", "coming", "sure", "haan", "han", "ji", "jee", "theek", "acha", "done", "si", "oui", "ja"}
NO_WORDS = {"2", "no", "n", "nahi", "nahin", "cant", "can't", "cannot", "busy", "sorry", "non", "nein"}


def interpret_reply(text: str) -> str | None:
    """'yes' / 'no' from a key press or a text reply, None if unclear."""
    words = re.findall(r"[\w']+", text.lower())
    if not words:
        return None
    if words[0] in NO_WORDS or any(w in NO_WORDS for w in words[:3]):
        return "no"
    if words[0] in YES_WORDS or any(w in YES_WORDS for w in words[:3]):
        return "yes"
    return None


@dataclass
class Task:
    id: str
    decision: Decision
    status: str = "working"  # working | done | failed
    helped_by: str | None = None
    current: str | None = None
    attempt: int = 0
    contacted: set[str] = field(default_factory=set)
    created: float = field(default_factory=time.time)
    # (reply, person_id, attempt) with reply in yes | no | no_answer
    inbox: asyncio.Queue = field(default_factory=asyncio.Queue)

    def describe(self, cfg: Config) -> str:
        if self.status == "done":
            return f"'{self.decision.summary}': {cfg.person(self.helped_by).name} said yes"
        if self.status == "failed":
            return f"'{self.decision.summary}': nobody said yes, family was told"
        who = cfg.person(self.current).name if self.current else "someone"
        return f"'{self.decision.summary}': still trying, now contacting {who}"


class Dispatcher:
    def __init__(self, cfg: Config, phone: Phone, public_url: str, activity: ActivityLog):
        self.cfg, self.phone, self.activity = cfg, phone, activity
        self.base = public_url.rstrip("/")
        self.tasks: dict[str, Task] = {}
        self._running: set[asyncio.Task] = set()

    # ---- starting work -------------------------------------------------

    def start(self, decision: Decision) -> Task:
        task = Task(id=f"t{next(_ids)}", decision=decision)
        self.tasks[task.id] = task
        self.activity.add("request", decision.summary, task=task.id, action=decision.action)
        runner = asyncio.create_task(self._run(task))
        self._running.add(runner)
        runner.add_done_callback(self._running.discard)
        return task

    def status_summary(self, within_hours: float = 12) -> str:
        recent = [t for t in self.tasks.values() if time.time() - t.created < within_hours * 3600]
        return "; ".join(t.describe(self.cfg) for t in recent) or "none"

    async def wait_idle(self):
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)

    # ---- replies from helpers (webhooks) --------------------------------

    def record_reply(self, task_id: str, person_id: str, reply: str | None, raw: str = ""):
        task = self.tasks.get(task_id)
        person = self.cfg.person(person_id)
        if not task or not person:
            return
        if reply is None:
            if raw:
                self.activity.add("unclear_reply", f"{person.name} replied: {raw!r}", task=task_id)
            return
        if task.status != "working":
            if reply == "yes" and task.helped_by != person_id:
                self.activity.add("late_yes", f"{person.name} also said yes, after the request was settled", task=task_id)
            return
        if reply == "no" and person_id != task.current:
            return  # an earlier helper declining late changes nothing
        task.inbox.put_nowait((reply, person_id, None))

    def record_no_answer(self, task_id: str, person_id: str, attempt: int | None = None):
        """The call ended without a key press. Ignored unless it's the call we're waiting on."""
        task = self.tasks.get(task_id)
        if (task and task.status == "working" and task.current == person_id
                and (attempt is None or attempt == task.attempt)):
            task.inbox.put_nowait(("no_answer", person_id, attempt or task.attempt))

    def open_task_for(self, person_id: str) -> Task | None:
        """The newest unsettled request this person was contacted about (for text replies)."""
        open_tasks = [t for t in self.tasks.values() if person_id in t.contacted and t.status == "working"]
        return max(open_tasks, key=lambda t: t.created, default=None)

    # ---- the work -------------------------------------------------------

    async def _run(self, task: Task):
        try:
            if task.decision.action == "emergency":
                await self._run_emergency(task)
            else:
                await self._run_in_order(task)
        except Exception:
            log.exception("Task %s crashed", task.id)
            task.status = "failed"
            await self._alert_family(task, "The helper line hit an error while handling this request")

    async def _run_in_order(self, task: Task):
        s = self.cfg.settings
        for contact in task.decision.contacts:
            person = self.cfg.person(contact.helper_id)
            await self._text(task, person, contact.message)
            for attempt in range(1, s.attempts_per_helper + 1):
                await self._call(task, person, attempt)
                got = await self._wait(task, s.wait_for_answer_seconds)
                if got is None or got[0] == "no_answer":
                    self.activity.add("no_answer", f"{person.name} didn't answer (try {attempt})", task=task.id)
                    if attempt == s.attempts_per_helper:
                        break
                    # Between calls, a text reply still counts; stray call statuses don't.
                    got = await self._wait(task, s.seconds_between_attempts, ignore_no_answer=True)
                if got and got[0] == "yes":
                    return await self._success(task, got[1])
                if got and got[0] == "no":
                    self.activity.add("declined", f"{person.name} can't help", task=task.id)
                    break
        await self._give_up(task)

    async def _run_emergency(self, task: Task):
        """Everyone at once, repeatedly, until someone says yes."""
        s = self.cfg.settings
        people = [(self.cfg.person(c.helper_id), c.message) for c in task.decision.contacts]
        await asyncio.gather(*(self._text(task, p, m) for p, m in people))
        task.current = None  # nobody in particular: only a "yes" from anyone matters
        for attempt in range(1, s.attempts_per_helper + 1):
            await asyncio.gather(*(self._call(task, p, attempt, emergency=True) for p, _ in people))
            got = await self._wait(task, s.wait_for_answer_seconds + s.seconds_between_attempts, ignore_no_answer=True)
            if got and got[0] == "yes":
                return await self._success(task, got[1])
        await self._give_up(task)

    async def _wait(self, task: Task, seconds: float, ignore_no_answer: bool = False):
        """Next (reply, person_id) from the inbox, or None after `seconds`."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            try:
                got = await asyncio.wait_for(task.inbox.get(), timeout=left)
            except asyncio.TimeoutError:
                return None
            if got[0] == "no_answer" and (ignore_no_answer or (got[1], got[2]) != (task.current, task.attempt)):
                continue  # not about the call we're waiting on
            return got[:2]
        return None

    # ---- contacting people ----------------------------------------------

    async def _text(self, task: Task, person: Person, message: str):
        task.contacted.add(person.id)
        task.current = person.id
        await self.phone.sms(person.phone, message)

    async def _call(self, task: Task, person: Person, attempt: int, emergency: bool = False):
        task.contacted.add(person.id)
        if not emergency:
            task.current, task.attempt = person.id, attempt
        self.activity.add("calling", f"Calling {person.name} (try {attempt})", task=task.id)
        q = f"?person={person.id}&attempt={attempt}"
        try:
            await self.phone.call(
                person.phone,
                url=f"{self.base}/voice/helper/{task.id}{q}",
                status_callback=f"{self.base}/voice/helper/{task.id}/status{q}",
                ring_seconds=self.cfg.settings.ring_seconds,
            )
        except Exception:
            log.exception("Call to %s failed", person.name)
            self.record_no_answer(task.id, person.id, attempt)

    # ---- endings --------------------------------------------------------

    async def _success(self, task: Task, helper_id: str):
        task.status, task.helped_by = "done", helper_id
        helper = self.cfg.person(task.helped_by)
        self.activity.add("confirmed", f"{helper.name} said yes: {task.decision.summary}", task=task.id)
        mom = self.cfg.mom
        await self._tell_mom(mom.said_yes.format(call_her=mom.call_her, name=helper.name))
        if self.cfg.settings.text_family_every_request or task.decision.action == "emergency":
            for p in self.cfg.family:
                if p.id != helper.id:
                    await self.phone.sms(p.phone, f"[{mom.name}'s helper line] {task.decision.summary}: {helper.name} said yes.")

    async def _give_up(self, task: Task):
        task.status = "failed"
        names = [self.cfg.person(c.helper_id).name for c in task.decision.contacts]
        self.activity.add("failed", f"Nobody said yes: {task.decision.summary}", task=task.id)
        await self._alert_family(task, f"Nobody said yes ({', '.join(names)})")
        mom = self.cfg.mom
        await self._tell_mom(mom.nobody_reached.format(
            call_her=mom.call_her, names=" and ".join(names), family=" and ".join(p.name for p in self.cfg.family)))

    async def _alert_family(self, task: Task, why: str):
        mom = self.cfg.mom
        text = f"[{mom.name}'s helper line] {why}. She asked for: {task.decision.summary}. Please call her: {mom.phones[0]}"
        for p in self.cfg.family:
            await self.phone.sms(p.phone, text)
            await self.phone.call(p.phone, twiml=say_twiml(text, self.cfg.lang_for(p), p.voice, repeat=2),
                                  ring_seconds=self.cfg.settings.ring_seconds)

    async def _tell_mom(self, text: str):
        mom, s = self.cfg.mom, self.cfg.settings
        if s.call_mom_with_result:
            await self.phone.call(mom.phones[0], twiml=say_twiml(text, mom.language, mom.voice, repeat=2),
                                  ring_seconds=s.ring_seconds)
        if s.text_mom_with_result:
            await self.phone.sms(mom.phones[0], text)
        self.activity.add("told_mom", text)

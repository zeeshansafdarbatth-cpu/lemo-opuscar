"""Her own notebook and reminders. Private to her: not shown on the family dashboard."""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None

    def load(self) -> list[dict]:
        if self.path and self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return []

    def save(self, items: list[dict]):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)


class Notebook:
    """Things she asks the assistant to remember: where she kept something, a name, a recipe."""

    def __init__(self, path: str | Path | None = None):
        self.store = JsonStore(path)
        self.notes: list[dict] = self.store.load()
        self._ids = itertools.count(max((n["id"] for n in self.notes), default=0) + 1)

    def add(self, text: str, now: datetime) -> dict:
        note = {"id": next(self._ids), "text": text, "date": now.strftime("%d %b %Y")}
        self.notes.append(note)
        self.store.save(self.notes)
        return note

    def remove(self, note_id: int) -> bool:
        before = len(self.notes)
        self.notes = [n for n in self.notes if n["id"] != note_id]
        self.store.save(self.notes)
        return len(self.notes) < before

    def describe(self) -> str:
        return "; ".join(f"#{n['id']} ({n['date']}) {n['text']}" for n in self.notes[-60:]) or "none"


@dataclass
class Reminder:
    id: int
    when: str  # ISO local time
    text: str
    repeat: str = "none"  # none | daily | weekly

    @property
    def due(self) -> datetime:
        return datetime.fromisoformat(self.when)


class Reminders:
    """Reminders she sets herself. When one is due, the assistant calls her."""

    def __init__(self, path: str | Path | None = None):
        self.store = JsonStore(path)
        self.items = [Reminder(**r) for r in self.store.load()]
        self._ids = itertools.count(max((r.id for r in self.items), default=0) + 1)

    def _save(self):
        self.store.save([asdict(r) for r in self.items])

    def add(self, when: datetime, text: str, repeat: str = "none") -> Reminder:
        r = Reminder(id=next(self._ids), when=when.replace(second=0, microsecond=0, tzinfo=None).isoformat(),
                     text=text, repeat=repeat if repeat in ("daily", "weekly") else "none")
        self.items.append(r)
        self._save()
        return r

    def cancel(self, reminder_id: int) -> bool:
        before = len(self.items)
        self.items = [r for r in self.items if r.id != reminder_id]
        self._save()
        return len(self.items) < before

    def get(self, reminder_id: int) -> Reminder | None:
        return next((r for r in self.items if r.id == reminder_id), None)

    def pop_due(self, now: datetime) -> list[Reminder]:
        """Reminders due now. Repeating ones move to their next time; others are removed."""
        due = [r for r in self.items if r.due <= now]
        for r in due:
            if r.repeat == "none":
                self.items.remove(r)
            else:
                step = timedelta(days=1 if r.repeat == "daily" else 7)
                nxt = r.due
                while nxt <= now:
                    nxt += step
                r.when = nxt.isoformat()
        if due:
            self._save()
        return due

    def describe(self) -> str:
        upcoming = sorted(self.items, key=lambda r: r.due)[:20]
        return "; ".join(f"#{r.id} {r.due:%a %d %b %H:%M}{' every day' if r.repeat == 'daily' else ' every week' if r.repeat == 'weekly' else ''}: {r.text}"
                         for r in upcoming) or "none"


async def run_reminders(reminders: Reminders, now: Callable[[], datetime],
                        ring: Callable[[Reminder], Awaitable[None]], every: float = 20):
    """Background loop: rings her for each reminder when it comes due."""
    while True:
        for r in reminders.pop_due(now()):
            try:
                await ring(r)
            except Exception:
                log.exception("Reminder call failed")
        await asyncio.sleep(every)

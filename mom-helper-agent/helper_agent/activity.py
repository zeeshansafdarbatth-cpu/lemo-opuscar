"""A running record of everything the agent did, kept in a JSON-lines file for the family to read."""

from __future__ import annotations

import json
import time
from pathlib import Path


class ActivityLog:
    def __init__(self, path: str | Path | None = None, keep: int = 500):
        self.path = Path(path) if path else None
        self.keep = keep
        self.entries: list[dict] = []
        if self.path and self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()[-keep:]
            self.entries = [json.loads(line) for line in lines if line.strip()]

    def add(self, kind: str, text: str, **extra) -> dict:
        entry = {"time": time.time(), "kind": kind, "text": text, **extra}
        self.entries = [*self.entries[-(self.keep - 1):], entry]
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def recent(self, n: int = 100) -> list[dict]:
        return list(reversed(self.entries[-n:]))

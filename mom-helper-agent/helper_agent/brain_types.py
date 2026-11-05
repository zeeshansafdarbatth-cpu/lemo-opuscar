"""Shared data shapes for help requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Contact(BaseModel):
    helper_id: str
    message: str


class Decision(BaseModel):
    """A help request handed to the dispatcher."""
    action: Literal["dispatch", "emergency"]
    say_to_mom: str = ""
    contacts: list[Contact]
    summary: str

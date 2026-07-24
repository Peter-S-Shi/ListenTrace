from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KeywordCapture:
    practice_session_id: int
    capture_type: str
    text: str
    position: int
    id: int | None = None

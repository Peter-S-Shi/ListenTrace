from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuickPracticeItem:
    quick_practice_session_id: int
    subtitle_cue_id: int
    position: int
    recall_result: str | None = None
    heard_fragment: str | None = None
    transcript_revealed: bool = False
    shadowed_at: str | None = None
    completed_at: str | None = None
    id: int | None = None

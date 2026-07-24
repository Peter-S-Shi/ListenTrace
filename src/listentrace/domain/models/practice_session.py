from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.stage_key import StageKey


@dataclass(slots=True)
class PracticeSession:
    material_id: int
    mode: str = "intensive"
    status: str = SessionStatus.ACTIVE.value
    current_stage: str = StageKey.GLOBAL_COMPREHENSION.value
    transcript_revealed_at: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    last_resumed_at: str | None = None
    completed_at: str | None = None
    abandoned_at: str | None = None
    id: int | None = None

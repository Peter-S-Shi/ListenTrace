from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.stage_status import StageStatus


@dataclass(slots=True)
class SessionStageProgress:
    practice_session_id: int
    stage_key: str
    status: str = StageStatus.NOT_STARTED.value
    outcome_key: str | None = None
    skip_note: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    skipped_at: str | None = None
    updated_at: str | None = None

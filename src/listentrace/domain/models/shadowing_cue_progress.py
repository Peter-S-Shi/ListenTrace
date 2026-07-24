from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.shadowing_status import ShadowingStatus


@dataclass(slots=True)
class ShadowingCueProgress:
    practice_session_id: int
    subtitle_cue_id: int
    status: str = ShadowingStatus.NOT_STARTED.value
    practice_count: int = 0
    note: str | None = None
    last_practiced_at: str | None = None

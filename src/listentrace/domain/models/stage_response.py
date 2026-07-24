from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StageResponse:
    practice_session_id: int
    stage_key: str
    prompt_key: str
    response_text: str = ""
    id: int | None = None

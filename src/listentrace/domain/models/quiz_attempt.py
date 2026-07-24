from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.quiz_mode import QuizMode
from listentrace.domain.enums.quiz_status import QuizStatus


@dataclass(slots=True)
class QuizAttempt:
    material_id: int
    quiz_mode: str = QuizMode.MATERIAL.value
    status: str = QuizStatus.ACTIVE.value
    seed: int = 0
    requested_count: int = 0
    actual_count: int = 0
    correct_count: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    last_resumed_at: str | None = None
    completed_at: str | None = None
    abandoned_at: str | None = None
    id: int | None = None

from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.quick_practice_source import QuickPracticeSource
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus


@dataclass(slots=True)
class QuickPracticeSession:
    material_id: int
    source_type: str = QuickPracticeSource.SELECTED.value
    requested_count: int = 0
    actual_count: int = 0
    status: str = QuickPracticeStatus.ACTIVE.value
    started_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    abandoned_at: str | None = None
    id: int | None = None

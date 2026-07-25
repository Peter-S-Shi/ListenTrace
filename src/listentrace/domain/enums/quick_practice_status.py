from __future__ import annotations

from enum import Enum


class QuickPracticeStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

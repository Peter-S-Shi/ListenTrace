from __future__ import annotations

from enum import Enum


class QuickPracticeSource(str, Enum):
    RECOMMENDED = "recommended"
    SELECTED = "selected"

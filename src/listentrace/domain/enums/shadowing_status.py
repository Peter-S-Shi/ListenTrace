from __future__ import annotations

from enum import Enum


class ShadowingStatus(str, Enum):
    NOT_STARTED = "not_started"
    PRACTICED = "practiced"
    SKIPPED = "skipped"

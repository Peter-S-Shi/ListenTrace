from __future__ import annotations

from enum import Enum


class RecallResult(str, Enum):
    UNDERSTOOD = "understood"
    PARTLY_UNDERSTOOD = "partly_understood"
    MISSED = "missed"

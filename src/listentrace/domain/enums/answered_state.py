from __future__ import annotations

from enum import Enum


class AnsweredState(str, Enum):
    UNANSWERED = "unanswered"
    ANSWERED = "answered"

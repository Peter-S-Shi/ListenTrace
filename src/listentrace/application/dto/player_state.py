from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LoopMode(str, Enum):
    NONE = "none"
    CUE = "cue"
    RANGE = "range"


@dataclass(slots=True)
class PlayerTick:
    active_cue_index: int | None
    pause: bool = False
    seek_to_ms: int | None = None

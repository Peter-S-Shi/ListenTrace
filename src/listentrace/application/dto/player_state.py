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
    # DIAG-c21e (M12 Loop Audible Cutoff Round 2): distinguishes the Loop
    # boundary's seek from an ordinary one -- it must go through a
    # pause-before-reposition transition (PlaybackController.restart_loop),
    # not a live seek() while still Playing. See player_session.py.
    loop_restart: bool = False

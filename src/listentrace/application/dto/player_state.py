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
    # M12 Loop Audible Cutoff Round 3: a one-shot playback span (Replay Cue,
    # Play-cue, or a single Loop iteration) reaching its natural end is
    # always `pause=True` -- there is no separate "seek back" outcome for
    # Loop. `restart_at_ms` is a distinct, additional instruction: begin a
    # new span at this position, orchestrated by
    # PlaybackController.restart_span (a settle-delayed, cancellable
    # transition, not an immediate reposition). See player_session.py.
    restart_at_ms: int | None = None

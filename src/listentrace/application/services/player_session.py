from __future__ import annotations

from listentrace.application.dto.player_state import LoopMode, PlayerTick
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.domain.services.cue_index import CueIndex

# QtMultimedia position updates are not frame-exact and arrive on a timer (typically
# every 100-1000ms depending on backend), so loop/replay boundaries are treated as
# reached slightly early rather than requiring an exact match. Verified against the
# Milestone 1 playback spike's observed update cadence.
LOOP_END_TOLERANCE_MS = 50


class PlayerSession:
    """Pure, framework-free player presentation state: active cue, loop, and replay rules.

    Holds no reference to any playback backend. Callers feed position updates in via
    `on_position_changed` and apply the returned `PlayerTick`'s side effects (pause/seek)
    to their own playback adapter. This keeps cue-resolution and loop semantics testable
    without a running Qt event loop.
    """

    def __init__(self, cues: list[SubtitleCue]):
        self._cue_index = CueIndex(cues)
        self.transcript_visible = True
        self.loop_mode = LoopMode.NONE
        self.selected_range: tuple[int, int] | None = None
        self.active_cue_index: int | None = None

        self._loop_start_ms: int | None = None
        self._loop_end_ms: int | None = None
        self._loop_seek_pending = False
        self._replay_end_ms: int | None = None
        self._last_position_ms: int | None = None
        self._play_cue_target_index: int | None = None
        self._play_cue_reached_end = False

    @property
    def cues(self) -> list[SubtitleCue]:
        return self._cue_index.cues

    def on_position_changed(self, position_ms: int) -> PlayerTick:
        self._last_position_ms = position_ms
        self.active_cue_index = self._cue_index.active_cue_index(position_ms)

        if self._replay_end_ms is not None:
            if position_ms >= self._replay_end_ms - LOOP_END_TOLERANCE_MS:
                self._replay_end_ms = None
                if self._play_cue_target_index is not None:
                    self._play_cue_reached_end = True
                return PlayerTick(self.active_cue_index, pause=True)
            return PlayerTick(self.active_cue_index)

        if self.loop_mode is not LoopMode.NONE and self._loop_end_ms is not None:
            if self._loop_seek_pending:
                # Ignore further boundary checks until the seek we issued has actually
                # taken effect, so repeated position ticks near the edge cannot trigger
                # another seek before the first one lands.
                if position_ms < self._loop_end_ms - LOOP_END_TOLERANCE_MS:
                    self._loop_seek_pending = False
                return PlayerTick(self.active_cue_index)

            if position_ms >= self._loop_end_ms - LOOP_END_TOLERANCE_MS:
                self._loop_seek_pending = True
                return PlayerTick(self.active_cue_index, seek_to_ms=self._loop_start_ms)

        return PlayerTick(self.active_cue_index)

    def play_cue(self, cue_index: int) -> int | None:
        """Cue-scoped Play (M12 Round 1 Playback Contract S3.2/S11): the default
        Play action in cue-oriented contexts (Quiz, Quick Practice, Shadowing).

        Unlike `replay_cue`, this does not unconditionally restart at
        `cue.start` -- if the last known position is already paused somewhere
        inside `[cue.start, cue.end)` (the learner paused mid-cue and pressed
        Play again), it resumes from there instead of jumping back to the
        start. If the position is outside the cue's range (not yet started,
        or a previous play already reached `cue.end` and stopped), it starts
        at `cue.start` like `replay_cue`. Either way, playback never drifts
        past `cue.end` -- enforced by the same `_replay_end_ms` boundary
        `on_position_changed` already applies to `replay_cue`.

        Returns the position to seek to, or `None` if no seek is needed
        (resuming in place)."""
        cue = self._cue_index.cues[cue_index]
        # A position inside [cue.start, cue.end) is ambiguous on its own: it is
        # also exactly where playback sits right after naturally reaching
        # cue.end and stopping (the boundary tolerance stops it a hair early,
        # not exactly at cue.end). `_play_cue_reached_end` disambiguates a
        # genuine mid-cue pause from "this cue already finished, restart it".
        already_finished_this_cue = self._play_cue_reached_end and self._play_cue_target_index == cue_index
        resume_in_place = (
            not already_finished_this_cue
            and self._last_position_ms is not None
            and cue.start_ms <= self._last_position_ms < cue.end_ms
        )
        self.cancel_loop()
        self._replay_end_ms = cue.end_ms
        self._play_cue_target_index = cue_index
        self._play_cue_reached_end = False
        if resume_in_place:
            return None
        return cue.start_ms

    def replay_cue(self, cue_index: int) -> int:
        """Start a one-shot replay of `cue_index`. Returns the position to seek to."""
        cue = self._cue_index.cues[cue_index]
        self.cancel_loop()
        self._replay_end_ms = cue.end_ms
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        return cue.start_ms

    def loop_cue(self, cue_index: int) -> int:
        """Start looping a single cue. Returns the position to seek to."""
        cue = self._cue_index.cues[cue_index]
        self._replay_end_ms = None
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        self.loop_mode = LoopMode.CUE
        self._loop_start_ms = cue.start_ms
        self._loop_end_ms = cue.end_ms
        self._loop_seek_pending = False
        self.selected_range = (cue_index, cue_index)
        return self._loop_start_ms

    def loop_range(self, first_index: int, last_index: int) -> int:
        """Start looping a continuous cue range. Returns the position to seek to."""
        cues = self._cue_index.cues
        lo, hi = sorted((first_index, last_index))
        self._replay_end_ms = None
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        self.loop_mode = LoopMode.RANGE
        self._loop_start_ms = cues[lo].start_ms
        self._loop_end_ms = cues[hi].end_ms
        self._loop_seek_pending = False
        self.selected_range = (lo, hi)
        return self._loop_start_ms

    def cancel_loop(self) -> None:
        self.loop_mode = LoopMode.NONE
        self._loop_start_ms = None
        self._loop_end_ms = None
        self._loop_seek_pending = False

    def previous_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.previous_index(current_index)

    def next_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.next_index(current_index)

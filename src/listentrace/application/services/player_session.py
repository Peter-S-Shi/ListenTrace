from __future__ import annotations

from dataclasses import dataclass

from listentrace.application.dto.player_state import LoopMode, PlayerTick
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.domain.services.cue_index import CueIndex

# QtMultimedia position updates are not frame-exact and arrive on a timer (typically
# every 100-1000ms depending on backend), so a span's end is treated as reached
# slightly early only for the *debounce* below, not for the trigger itself (the
# trigger already tolerates a late/coarse tick via `>=`, see `_ActiveSpan` and
# `on_position_changed`). Verified against the Milestone 1 playback spike's
# observed update cadence.
LOOP_END_TOLERANCE_MS = 50


@dataclass(slots=True)
class _ActiveSpan:
    """A bounded, one-shot playback span currently in flight: `[start_ms, end_ms)`.

    M12 Loop Audible Cutoff Round 3: this is the single primitive behind
    `replay_cue`, `play_cue`, `loop_cue`, and `loop_range` alike. Two rounds of
    fixes tried to make Loop's boundary transition *behave* like Replay's
    (removing an early trigger, then pausing before repositioning) and human
    listening still reported a clipped tail either way -- because Loop's
    restart was still happening with no real elapsed time for the just-paused
    audio output to drain, unlike Replay's restart, which only ever happens
    after a human clicks a button. Round 3 stops trying to make Loop's
    transition *resemble* Replay's and instead makes it structurally the same
    thing: a span reaching its end is always one identical event (pause);
    only the question of "what happens after" (nothing vs. a genuinely
    settle-delayed restart, in `PlaybackController.restart_span`) differs.
    Internal to `PlayerSession` -- not part of its public interface.
    """

    start_ms: int
    end_ms: int


class PlayerSession:
    """Pure, framework-free player presentation state: active cue, loop, and replay rules.

    Holds no reference to any playback backend. Callers feed position updates in via
    `on_position_changed` and apply the returned `PlayerTick`'s side effects (pause,
    and optionally a settle-delayed restart) to their own playback adapter. This keeps
    cue-resolution and playback-span semantics testable without a running Qt event loop.

    Every one-shot bounded playback -- a single Replay Cue, a cue-scoped Play, one
    iteration of Loop Cue, or one iteration of Loop Range -- is the same underlying
    primitive: an `_ActiveSpan` that plays from `start_ms` to `end_ms` and then pauses.
    `loop_mode` decides only what happens *after* that pause: nothing (Replay/Play-cue),
    or -- while still enabled -- the same span begins again (Loop). A multi-cue Loop
    Range is one indivisible span from the first selected cue's start to the last
    selected cue's end; the cues in between have no boundary of their own here, so
    nothing about their internal timing is ever touched.
    """

    def __init__(self, cues: list[SubtitleCue]):
        self._cue_index = CueIndex(cues)
        self.transcript_visible = True
        self.loop_mode = LoopMode.NONE
        self.selected_range: tuple[int, int] | None = None
        self.active_cue_index: int | None = None

        self._active_span: _ActiveSpan | None = None
        self._span_restart_pending = False
        self._last_position_ms: int | None = None
        self._play_cue_target_index: int | None = None
        self._play_cue_reached_end = False

    @property
    def cues(self) -> list[SubtitleCue]:
        return self._cue_index.cues

    def on_position_changed(self, position_ms: int) -> PlayerTick:
        self._last_position_ms = position_ms
        self.active_cue_index = self._cue_index.active_cue_index(position_ms)

        if self._active_span is None:
            return PlayerTick(self.active_cue_index)

        if self._span_restart_pending:
            # Ignore further boundary checks until a real position update confirms
            # the pending restart has actually landed, so repeated ticks still
            # reporting the old (near-end) position cannot re-trigger completion
            # a second time before the first restart has taken effect.
            if position_ms < self._active_span.end_ms - LOOP_END_TOLERANCE_MS:
                self._span_restart_pending = False
            return PlayerTick(self.active_cue_index)

        if position_ms < self._active_span.end_ms:
            return PlayerTick(self.active_cue_index)

        # The span has reached its natural end -- exactly one outcome, always: pause.
        # (`>=` already tolerates a late/coarse tick landing past the boundary; no
        # early-trigger margin is needed or applied here.)
        span = self._active_span
        if self._play_cue_target_index is not None:
            self._play_cue_reached_end = True

        if self.loop_mode is LoopMode.NONE:
            self._active_span = None
            return PlayerTick(self.active_cue_index, pause=True)

        # Loop stays enabled: the same span plays again, but only once the caller
        # (PlaybackController.restart_span) has let the just-paused output settle --
        # restarting immediately reproduces the same clipped tail this refactor
        # exists to remove, regardless of whether the reposition happens while still
        # playing (Round 2 before) or right after a pause with no elapsed time
        # (Round 2's actual fix, still insufficient per human retest).
        self._span_restart_pending = True
        return PlayerTick(self.active_cue_index, pause=True, restart_at_ms=span.start_ms)

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
        past `cue.end` -- enforced by the same one-shot span boundary
        `on_position_changed` already applies to `replay_cue`.

        Returns the position to seek to, or `None` if no seek is needed
        (resuming in place)."""
        cue = self._cue_index.cues[cue_index]
        # A position inside [cue.start, cue.end) is ambiguous on its own: it is
        # also exactly where playback sits right after naturally reaching
        # cue.end and stopping. `_play_cue_reached_end` disambiguates a
        # genuine mid-cue pause from "this cue already finished, restart it".
        already_finished_this_cue = self._play_cue_reached_end and self._play_cue_target_index == cue_index
        resume_in_place = (
            not already_finished_this_cue
            and self._last_position_ms is not None
            and cue.start_ms <= self._last_position_ms < cue.end_ms
        )
        self.cancel_loop()
        self._active_span = _ActiveSpan(cue.start_ms, cue.end_ms)
        self._play_cue_target_index = cue_index
        self._play_cue_reached_end = False
        if resume_in_place:
            return None
        return cue.start_ms

    def replay_cue(self, cue_index: int) -> int:
        """Start a one-shot replay of `cue_index`. Returns the position to seek to."""
        cue = self._cue_index.cues[cue_index]
        self.cancel_loop()
        self._active_span = _ActiveSpan(cue.start_ms, cue.end_ms)
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        return cue.start_ms

    def loop_cue(self, cue_index: int) -> int:
        """Start looping a single cue: repeated one-shot replay of that cue's
        complete span until cancelled. Returns the position to seek to."""
        cue = self._cue_index.cues[cue_index]
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        self.loop_mode = LoopMode.CUE
        self._active_span = _ActiveSpan(cue.start_ms, cue.end_ms)
        self._span_restart_pending = False
        self.selected_range = (cue_index, cue_index)
        return self._active_span.start_ms

    def loop_range(self, first_index: int, last_index: int) -> int:
        """Start looping a continuous cue range: repeated one-shot replay of the
        *entire selected range as a single indivisible span* (first cue's start to
        last cue's end) until cancelled -- not sequential replay of each cue in
        turn. The cues between the first and last have no boundary of their own
        here, so their internal timing, pauses, and connected speech are never
        touched. Returns the position to seek to."""
        cues = self._cue_index.cues
        lo, hi = sorted((first_index, last_index))
        self._play_cue_target_index = None
        self._play_cue_reached_end = False
        self.loop_mode = LoopMode.RANGE
        self._active_span = _ActiveSpan(cues[lo].start_ms, cues[hi].end_ms)
        self._span_restart_pending = False
        self.selected_range = (lo, hi)
        return self._active_span.start_ms

    def cancel_loop(self) -> None:
        self.loop_mode = LoopMode.NONE
        self._active_span = None
        self._span_restart_pending = False

    def previous_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.previous_index(current_index)

    def next_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.next_index(current_index)

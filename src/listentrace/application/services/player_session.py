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

    def __init__(self, cues: list[SubtitleCue], loop_end_grace_ms: int):
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
        # Required, no default: 60-300ms is the frozen product-legal range for
        # an effective value, and a silent fallback (e.g. 0) would let a caller
        # that forgets to resolve one degrade quietly into the exact "no grace"
        # behavior already proven insufficient by human listening, instead of
        # failing loudly. Callers resolve this once, externally (global default
        # or per-Material override) -- this class never learns where it came
        # from, and never learns the Material's actual duration either; see
        # `_completion_end_ms` and `on_media_ended`.
        self._loop_end_grace_ms = loop_end_grace_ms
        # The grace value actually in effect for the CURRENTLY PLAYING Loop
        # iteration -- snapshotted once when that iteration begins (starting
        # a loop, or a restart landing) and never updated mid-iteration. Kept
        # deliberately distinct from `_loop_end_grace_ms`, which is simply
        # "whatever is live right now" -- see `set_loop_end_grace_ms`.
        self._active_iteration_grace_ms: int | None = None

    @property
    def cues(self) -> list[SubtitleCue]:
        return self._cue_index.cues

    def set_loop_end_grace_ms(self, value: int) -> None:
        """Update the live grace value (e.g. the learner adjusted Loop
        Settings while a Material is already open). Deliberately does NOT
        touch `_active_iteration_grace_ms` -- an iteration already in flight
        keeps the effective completion end it started with; only the
        iteration that begins after the next restart adopts this value (see
        `_begin_loop_iteration`)."""
        self._loop_end_grace_ms = value

    def _begin_loop_iteration(self) -> None:
        """Snapshot the grace value for the Loop iteration now beginning --
        called when a loop first starts, and again each time a restarted
        iteration is confirmed to have landed (see the debounce-clear branch
        in `on_position_changed`). This is the one place `_loop_end_grace_ms`
        (live) is allowed to flow into `_active_iteration_grace_ms` (frozen
        for the duration of that iteration)."""
        self._active_iteration_grace_ms = self._loop_end_grace_ms

    def _completion_end_ms(self, span: _ActiveSpan) -> int:
        """The *effective* completion end for `span`: its own logical end for
        Replay Cue/Play-cue, or logical end + the CURRENT iteration's frozen
        grace snapshot while looping. `span.end_ms` itself always stays the
        subtitle-defined logical end -- never mutated to bake grace in -- so
        the two concepts (Logical end, Effective completion end; see
        CONTEXT.md) can never be confused by a future reader of `span.end_ms`
        alone."""
        if self.loop_mode is not LoopMode.NONE:
            grace = self._active_iteration_grace_ms
            if grace is None:  # defensive: should always be set once looping
                grace = self._loop_end_grace_ms
            return span.end_ms + grace
        return span.end_ms

    def _complete_active_span(self) -> PlayerTick:
        """Complete `_active_span` deterministically. Shared by both legal
        completion paths for a bounded playback span: `on_position_changed`
        (a tick crosses the effective completion end) and `on_media_ended`
        (the underlying media's physical end arrives first -- e.g. because
        grace, or any cue's own logical end, exceeds the Material's actual
        duration). Always the same one outcome: pause; Loop additionally
        schedules a restart of the same span."""
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

    def on_position_changed(self, position_ms: int) -> PlayerTick:
        self._last_position_ms = position_ms
        self.active_cue_index = self._cue_index.active_cue_index(position_ms)

        if self._active_span is None:
            return PlayerTick(self.active_cue_index)

        completion_end_ms = self._completion_end_ms(self._active_span)

        if self._span_restart_pending:
            # Ignore further boundary checks until a real position update confirms
            # the pending restart has actually landed, so repeated ticks still
            # reporting the old (near-end) position cannot re-trigger completion
            # a second time before the first restart has taken effect.
            if position_ms < completion_end_ms - LOOP_END_TOLERANCE_MS:
                self._span_restart_pending = False
                self._begin_loop_iteration()
            return PlayerTick(self.active_cue_index)

        if position_ms < completion_end_ms:
            return PlayerTick(self.active_cue_index)

        # The span has reached its effective completion end -- exactly one
        # outcome, always: pause. (`>=` already tolerates a late/coarse tick
        # landing past the boundary; no early-trigger margin is needed or
        # applied here.)
        return self._complete_active_span()

    def on_media_ended(self) -> PlayerTick:
        """The underlying media reached its physical end (EndOfMedia) -- the
        second of the two legal ways a bounded playback span completes (see
        `_completion_end_ms`). Without this, a span whose effective
        completion end sits past the Material's actual duration would never
        receive a position tick that reaches it, leaving `_active_span`
        dangling forever. No-op if no span is active, or if a tick-driven
        completion for the current iteration is already pending (avoids a
        redundant second completion for the same iteration)."""
        if self._active_span is None or self._span_restart_pending:
            return PlayerTick(self.active_cue_index)
        return self._complete_active_span()

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
        self._begin_loop_iteration()
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
        self._begin_loop_iteration()
        self.selected_range = (lo, hi)
        return self._active_span.start_ms

    def cancel_loop(self) -> None:
        self.loop_mode = LoopMode.NONE
        self._active_span = None
        self._span_restart_pending = False
        self._active_iteration_grace_ms = None

    def previous_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.previous_index(current_index)

    def next_cue_index(self, current_index: int | None) -> int | None:
        return self._cue_index.next_index(current_index)

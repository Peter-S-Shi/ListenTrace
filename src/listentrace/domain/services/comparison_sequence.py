from __future__ import annotations

from enum import Enum

# A brief silence between source and learner playback so the two are clearly
# distinguishable, never overlapping (the product boundary explicitly forbids
# mixing both audio streams simultaneously).
COMPARISON_PAUSE_MS = 600


class ComparisonStep(Enum):
    PLAY_SOURCE = "play_source"
    WAIT = "wait"
    PLAY_RECORDING = "play_recording"
    DONE = "done"


class ComparisonSequencer:
    """Pure state machine for the fixed source-then-recording comparison sequence.

    Holds no reference to any playback backend. The caller (UI) drives it with
    lifecycle events — `start`, `on_source_finished`, `on_pause_elapsed`,
    `on_recording_finished` — and is responsible for actually playing/pausing
    audio and running the `COMPARISON_PAUSE_MS` timer in response to each
    returned step. `is_active` lets the caller refuse to start a second
    concurrent comparison (or a plain source/recording playback) while one is
    already in progress, which is how "never mix both streams" is enforced.
    """

    def __init__(self) -> None:
        self._step = ComparisonStep.DONE

    @property
    def step(self) -> ComparisonStep:
        return self._step

    @property
    def is_active(self) -> bool:
        return self._step is not ComparisonStep.DONE

    def start(self) -> ComparisonStep:
        self._step = ComparisonStep.PLAY_SOURCE
        return self._step

    def on_source_finished(self) -> ComparisonStep:
        if self._step is not ComparisonStep.PLAY_SOURCE:
            return self._step
        self._step = ComparisonStep.WAIT
        return self._step

    def on_pause_elapsed(self) -> ComparisonStep:
        if self._step is not ComparisonStep.WAIT:
            return self._step
        self._step = ComparisonStep.PLAY_RECORDING
        return self._step

    def on_recording_finished(self) -> ComparisonStep:
        if self._step is not ComparisonStep.PLAY_RECORDING:
            return self._step
        self._step = ComparisonStep.DONE
        return self._step

    def cancel(self) -> ComparisonStep:
        self._step = ComparisonStep.DONE
        return self._step

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

# M12 Loop Audible Cutoff Round 3: the deliberate gap `restart_span` waits before
# repositioning for a new Loop iteration. Two prior rounds established that neither
# *when* the boundary is detected (Round 1) nor pausing immediately before a
# synchronous reposition (Round 2) resolves the human-reported clipped tail -- a
# `pause()` call stops feeding new samples, but does not itself wait for whatever the
# OS audio output already has queued to finish draining; only real elapsed time does.
# Replay Cue's own restart (a later, separate user click) sounds clean precisely
# because a human's reaction time already provides that gap for free. This constant
# gives Loop's automatic restart the same kind of real settle time, deliberately, as
# an architectural choice -- not a boundary-detection tolerance, and not tuned by
# trial-and-error against `LOOP_END_TOLERANCE_MS`'s already-settled value. It cannot
# be proven correct by an automated test (audio quality is a human judgment); the
# value is a conservative estimate of typical consumer audio output latency and is
# meant to be confirmed or adjusted only by the Journey B2 human listening retest.
LOOP_RESTART_SETTLE_MS = 60


class PlaybackController(QObject):
    """Narrow adapter around QMediaPlayer so callers do not depend on Qt multimedia types."""

    position_changed = Signal(int)
    duration_changed = Signal(int)
    end_of_media = Signal()
    playback_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._pending_restart_generation = 0

        self._player.positionChanged.connect(lambda p: self.position_changed.emit(p))
        self._player.durationChanged.connect(lambda d: self.duration_changed.emit(d))
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def load(self, media_path: Path | str) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(media_path)))

    def unload(self) -> None:
        """Clear the loaded source and release its file handle. `stop()` alone
        does not do this — on Windows, a stopped `QMediaPlayer` still holds an
        exclusive lock on its source file until a different source is loaded or
        the source is explicitly cleared, which blocks deleting that file."""
        self._pending_restart_generation += 1
        self._player.stop()
        self._player.setSource(QUrl())

    def play(self) -> None:
        self._pending_restart_generation += 1
        self._player.play()

    def pause(self) -> None:
        self._pending_restart_generation += 1
        self._player.pause()

    def stop(self) -> None:
        self._pending_restart_generation += 1
        self._player.stop()

    def seek(self, position_ms: int) -> None:
        self._pending_restart_generation += 1
        self._player.setPosition(position_ms)

    def restart_span(self, position_ms: int) -> None:
        """Begin a new one-shot playback span at `position_ms`, replaying a
        just-completed Loop iteration. Pauses immediately (the same clean
        completion Replay Cue already uses -- see `player_session.py`), then
        repositions and resumes only after `LOOP_RESTART_SETTLE_MS` of real
        elapsed time, not immediately. See that constant for why the settle
        delay is the actual fix, not an incidental detail.

        Cancellable and self-superseding: any subsequent `play`/`pause`/
        `seek`/`stop`/`restart_span` call (including one that lands before
        this restart fires -- e.g. the learner clicks Stop Loop, Replay, or a
        different transport control during the settle gap) invalidates this
        specific pending restart, so a stale queued transition can never
        silently resume playback after the learner has already moved on.
        """
        self.pause()
        generation = self._pending_restart_generation
        QTimer.singleShot(
            LOOP_RESTART_SETTLE_MS, lambda: self._fire_pending_restart(generation, position_ms)
        )

    def _fire_pending_restart(self, generation: int, position_ms: int) -> None:
        if generation != self._pending_restart_generation:
            return  # superseded or cancelled while the settle delay was elapsing
        self.seek(position_ms)
        self.play()

    def cancel_pending_restart(self) -> None:
        """Invalidate any restart scheduled by `restart_span`, without otherwise
        touching playback state. Used where cancellation must be explicit and
        no other `play`/`pause`/`seek`/`stop` call already covers it (e.g. Stop
        Loop clicked with nothing else changing)."""
        self._pending_restart_generation += 1

    def set_volume(self, volume: float) -> None:
        self._audio_output.setVolume(volume)

    def set_muted(self, muted: bool) -> None:
        self._audio_output.setMuted(muted)

    def set_video_output(self, video_widget) -> None:
        self._player.setVideoOutput(video_widget)

    @property
    def position_ms(self) -> int:
        return self._player.position()

    @property
    def duration_ms(self) -> int:
        return self._player.duration()

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def is_muted(self) -> bool:
        return self._audio_output.isMuted()

    @property
    def media_status(self) -> QMediaPlayer.MediaStatus:
        return self._player.mediaStatus()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.end_of_media.emit()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.playback_error.emit(
                "The media file could not be loaded (invalid or unsupported content)."
            )

    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self.playback_error.emit(error_string)

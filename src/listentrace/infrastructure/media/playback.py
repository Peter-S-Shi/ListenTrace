from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


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

        self._player.positionChanged.connect(lambda p: self.position_changed.emit(p))
        self._player.durationChanged.connect(lambda d: self.duration_changed.emit(d))
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def load(self, media_path: Path | str) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(media_path)))

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(position_ms)

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

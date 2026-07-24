from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioDevice,
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)


@dataclass(slots=True)
class AudioInputDevice:
    """A narrow, Qt-free description of one audio-input device — the stable
    identity (`device_id`, hex-encoded) is what gets persisted/compared; Qt's own
    `QAudioDevice` never leaves this module."""

    device_id: str
    description: str
    is_default: bool


def _device_id(device: QAudioDevice) -> str:
    return bytes(device.id()).hex()


def list_audio_input_devices() -> list[AudioInputDevice]:
    return [
        AudioInputDevice(device_id=_device_id(device), description=device.description(), is_default=device.isDefault())
        for device in QMediaDevices.audioInputs()
    ]


class RecordingController(QObject):
    """Narrow adapter around Qt's audio-capture pipeline (`QMediaCaptureSession` +
    `QAudioInput` + `QMediaRecorder`) so callers do not depend on Qt multimedia
    types — mirrors `playback.PlaybackController`'s role for `QMediaPlayer`.

    Always records to WAV (see `set_output_format`); the caller supplies an
    absolute output path per take. Only one capture may be in progress on a
    given instance at a time, matching the product rule that only one recording
    operation may be active at all (the application layer additionally checks
    this across the whole database, not just this one adapter instance).
    """

    recording_error = Signal(str)
    recording_stopped = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._audio_input = QAudioInput(self)
        self._session = QMediaCaptureSession(self)
        self._session.setAudioInput(self._audio_input)
        self._recorder = QMediaRecorder(self)
        self._session.setRecorder(self._recorder)

        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        self._recorder.setMediaFormat(media_format)

        self._recorder.errorOccurred.connect(self._on_error)
        self._recorder.recorderStateChanged.connect(self._on_state_changed)

    def set_device(self, device_id: str) -> bool:
        """Point capture at the device with this id. Returns False (and leaves the
        previous device in place) if no currently-connected device matches —
        callers must not silently fall back to a different device."""
        for device in QMediaDevices.audioInputs():
            if _device_id(device) == device_id:
                self._audio_input.setDevice(device)
                return True
        return False

    def start(self, output_path: Path) -> None:
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))
        self._recorder.record()

    def stop(self) -> None:
        self._recorder.stop()

    @property
    def is_recording(self) -> bool:
        return self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState

    @property
    def duration_ms(self) -> int:
        return self._recorder.duration()

    def _on_state_changed(self, state: QMediaRecorder.RecorderState) -> None:
        if state == QMediaRecorder.RecorderState.StoppedState:
            self.recording_stopped.emit()

    def _on_error(self, error: QMediaRecorder.Error, error_string: str) -> None:
        if error != QMediaRecorder.Error.NoError:
            self.recording_error.emit(error_string)

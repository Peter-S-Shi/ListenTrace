from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from listentrace.infrastructure.media.playback import PlaybackController


@pytest.fixture()
def silent_wav_path(tmp_path):
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(struct.pack("<h", 0) * 8000)  # 1 second of silence
    return path


def _run_event_loop(app, timeout_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_playback_controller_loads_media_and_reports_duration(qapp, silent_wav_path):
    controller = PlaybackController()
    controller.set_volume(0.0)
    controller.load(silent_wav_path)

    _run_event_loop(qapp, 2000)

    assert controller.duration_ms == pytest.approx(1000, abs=200)


def test_playback_controller_reaches_end_of_media(qapp, silent_wav_path):
    controller = PlaybackController()
    controller.set_volume(0.0)

    reached_end = []
    controller.end_of_media.connect(lambda: reached_end.append(True))

    controller.load(silent_wav_path)
    QTimer.singleShot(200, controller.play)

    _run_event_loop(qapp, 3000)

    assert reached_end, "expected end_of_media to fire for a short clip within the timeout"


def test_playback_controller_seek_updates_position(qapp, silent_wav_path):
    controller = PlaybackController()
    controller.set_volume(0.0)
    controller.load(silent_wav_path)

    _run_event_loop(qapp, 1000)
    controller.seek(200)
    _run_event_loop(qapp, 200)

    assert controller.position_ms == pytest.approx(200, abs=50)

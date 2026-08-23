from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from listentrace.infrastructure.media.playback import LOOP_RESTART_SETTLE_MS, PlaybackController


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


# ---- restart_span (M12 Loop Audible Cutoff Round 3) ----
#
# These test the deep module's own interface directly -- PlaybackController
# is the one place that owns QMediaPlayer, so the pause-then-settle-then-
# resume sequence and its cancellation belong here, not duplicated per window.


def test_restart_span_pauses_immediately_and_defers_reposition_past_the_settle_delay(
    qapp, monkeypatch
):
    controller = PlaybackController()
    calls: list[object] = []
    monkeypatch.setattr(controller._player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(controller._player, "setPosition", lambda ms: calls.append(("seek", ms)))
    monkeypatch.setattr(controller._player, "play", lambda: calls.append("play"))

    controller.restart_span(250)

    assert calls == ["pause"], "reposition/resume must not happen in the same call"

    _run_event_loop(qapp, LOOP_RESTART_SETTLE_MS + 150)

    assert calls == ["pause", ("seek", 250), "play"]


def test_restart_span_is_superseded_by_a_later_playback_action(qapp, monkeypatch):
    """If anything else drives playback (a fresh seek, a new restart_span,
    Stop) before the settle delay elapses, the earlier pending restart must
    never fire -- otherwise a learner's subsequent action could be silently
    overridden by a stale scheduled transition."""
    controller = PlaybackController()
    calls: list[object] = []
    monkeypatch.setattr(controller._player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(controller._player, "setPosition", lambda ms: calls.append(("seek", ms)))
    monkeypatch.setattr(controller._player, "play", lambda: calls.append("play"))

    controller.restart_span(250)
    calls.clear()  # discard the first restart_span's own pause() call

    controller.seek(999)  # a different, later action supersedes it

    _run_event_loop(qapp, LOOP_RESTART_SETTLE_MS + 150)

    assert calls == [("seek", 999)], "the superseded restart_span must never fire seek(250)/play()"


def test_cancel_pending_restart_prevents_a_scheduled_restart_from_firing(qapp, monkeypatch):
    controller = PlaybackController()
    calls: list[object] = []
    monkeypatch.setattr(controller._player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(controller._player, "setPosition", lambda ms: calls.append(("seek", ms)))
    monkeypatch.setattr(controller._player, "play", lambda: calls.append("play"))

    controller.restart_span(250)
    controller.cancel_pending_restart()

    _run_event_loop(qapp, LOOP_RESTART_SETTLE_MS + 150)

    assert calls == ["pause"], "a cancelled restart must never reposition or resume"

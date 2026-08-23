from __future__ import annotations

import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QPushButton

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import LoopMode
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.player_window import PlayerWindow, _is_text_entry_widget


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "workspace.db")
    migrate(connection)
    yield connection
    connection.close()


def _run_event_loop(app, timeout_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _two_cue_result(media_path, media_kind="audio"):
    material = Material(id=1, title="Test Lesson", media_path=str(media_path), media_kind=media_kind)
    cues = [
        SubtitleCue(cue_index=1, start_ms=0, end_ms=500, text="hello"),
        SubtitleCue(cue_index=2, start_ms=500, end_ms=1000, text="world"),
    ]
    return PlayerLoadResult(material=material, cues=cues)


def _three_cue_result(media_path, media_kind="audio"):
    material = Material(id=1, title="Test Lesson", media_path=str(media_path), media_kind=media_kind)
    cues = [
        SubtitleCue(cue_index=1, start_ms=0, end_ms=500, text="one"),
        SubtitleCue(cue_index=2, start_ms=500, end_ms=1000, text="two"),
        SubtitleCue(cue_index=3, start_ms=1000, end_ms=1500, text="three"),
    ]
    return PlayerLoadResult(material=material, cues=cues)


def test_is_text_entry_widget_helper(qapp):
    assert _is_text_entry_widget(QLineEdit()) is True
    assert _is_text_entry_widget(QPushButton()) is False
    assert _is_text_entry_widget(None) is False


def test_player_window_initial_cue_index_selects_cue_without_crashing(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn, initial_cue_index=1)

    assert window._cue_list.currentRow() == 1
    assert window._editing_cue_index == 1
    assert window._save_annotation_button.isEnabled() is True
    assert window._save_note_button.isEnabled() is True

    window.close()


def test_player_window_out_of_range_initial_cue_index_is_ignored(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn, initial_cue_index=99)

    assert window._cue_list.currentRow() == -1
    assert window._editing_cue_index is None
    assert window._save_annotation_button.isEnabled() is False

    window.close()


def test_player_window_audio_mode_does_not_autoplay(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    _run_event_loop(qapp, 1500)

    assert window._audio_placeholder is not None
    assert window._video_widget is None
    assert window._playback.is_playing is False
    assert window._playback.position_ms == 0
    assert window._playback.duration_ms == pytest.approx(2000, abs=300)

    window.close()


def test_player_window_video_mode_creates_video_surface(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path, media_kind="video"), conn)

    assert window._video_widget is not None
    assert window._audio_placeholder is None

    window.close()


def test_player_window_play_pause_toggle(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._on_play_pause_clicked()
    _run_event_loop(qapp, 500)
    assert window._playback.is_playing is True
    assert window._play_pause_button.text() == "Pause"

    window._on_play_pause_clicked()
    assert window._playback.is_playing is False
    assert window._play_pause_button.text() == "Play"

    window.close()


def test_player_window_invalid_media_disables_all_playback_dependent_controls(qapp, conn, tmp_path):
    bad_path = tmp_path / "bad.mp3"
    bad_path.write_bytes(b"not a real mp3 file, just garbage bytes" * 20)

    window = PlayerWindow(_two_cue_result(bad_path), conn)
    _run_event_loop(qapp, 2000)

    assert "Playback error" in window._status_label.text()
    assert window._playback_usable is False

    for widget in (
        window._play_pause_button,
        window._seek_slider,
        window._previous_button,
        window._next_button,
        window._replay_button,
        window._loop_cue_button,
        window._loop_range_button,
        window._volume_slider,
        window._mute_button,
    ):
        assert widget.isEnabled() is False, f"{widget} should be disabled after a playback error"

    # Transcript visibility and returning to the library must remain usable.
    assert window._transcript_button.isEnabled() is True
    window._on_toggle_transcript()
    assert window._session.transcript_visible is False

    window.close()


def test_player_window_keyboard_shortcuts_suppressed_after_playback_error(qapp, conn, tmp_path):
    bad_path = tmp_path / "bad.mp3"
    bad_path.write_bytes(b"not a real mp3 file, just garbage bytes" * 20)

    window = PlayerWindow(_two_cue_result(bad_path), conn)
    _run_event_loop(qapp, 2000)
    assert window._playback_usable is False

    # Space must not attempt to resume playback once it has been marked unusable.
    was_playing = window._playback.is_playing
    space_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    window.keyPressEvent(space_event)
    assert window._playback.is_playing == was_playing  # unchanged

    # Escape and T must still work even though playback is unusable.
    window.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_T, Qt.KeyboardModifier.NoModifier)
    )
    assert window._session.transcript_visible is False

    window.close()


def test_player_window_cue_list_uses_contiguous_selection_mode(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    assert (
        window._cue_list.selectionMode()
        == QAbstractItemView.SelectionMode.ContiguousSelection
    )

    window.close()


def test_previous_cue_steps_one_at_a_time_even_if_active_cue_index_is_transiently_none(qapp, conn, tmp_path):
    """M12 Round 1 regression: reproduces the human-QA report that repeated
    Previous Cue clicks could jump straight back to the start (m02-03,
    m13-02). The root cause was that navigation read
    `self._session.active_cue_index`, which is briefly `None` right after a
    seek -- before the next position tick lands -- and
    `CueIndex.previous_index(None)` falls back to cue 0. Navigation must
    instead anchor on the stable, explicitly-tracked Selected Cue."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_three_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(2)  # start at the last cue
    assert window._editing_cue_index == 2

    # Simulate the exact race: a seek just happened and the next position tick
    # has not landed yet, so the playback-derived index is momentarily None.
    window._session.active_cue_index = None
    window._on_previous_cue()
    assert window._editing_cue_index == 1, "must step to the adjacent cue, not jump to the start"

    window._session.active_cue_index = None
    window._on_previous_cue()
    assert window._editing_cue_index == 0

    window.close()


def test_next_cue_updates_selected_cue_and_seeks_media_position(qapp, conn, tmp_path):
    """Round 1 S6: a navigation action must atomically move Selected Cue and
    Media Position together."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_three_cue_result(wav_path), conn)
    _run_event_loop(qapp, 300)  # let the async media load finish before seeking
    window._cue_list.setCurrentRow(0)

    window._on_next_cue()
    _run_event_loop(qapp, 300)

    assert window._editing_cue_index == 1
    assert window._playback.position_ms == pytest.approx(500, abs=150)
    window.close()


def test_player_window_replay_cue_pauses_at_cue_end(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)  # cue 0: 0-500ms
    window._on_replay_cue()

    _run_event_loop(qapp, 2000)

    assert window._playback.is_playing is False
    assert window._playback.position_ms == pytest.approx(500, abs=150)

    window.close()


def test_player_window_loop_cue_returns_to_start(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)  # cue 0: 0-500ms
    window._on_loop_cue_clicked()

    assert window._session.loop_mode is LoopMode.CUE

    _run_event_loop(qapp, 1800)  # long enough to cross the 500ms boundary at least once

    assert window._playback.is_playing is True
    assert window._playback.position_ms < 500

    window.close()


def test_player_window_loop_range_returns_to_first_cue_start(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.item(0).setSelected(True)
    window._cue_list.item(1).setSelected(True)
    window._on_loop_range_clicked()

    assert window._session.loop_mode is LoopMode.RANGE
    assert window._session.selected_range == (0, 1)

    _run_event_loop(qapp, 2200)  # long enough to cross the 1000ms range end at least once

    assert window._playback.is_playing is True
    assert window._playback.position_ms < 1000

    window.close()


def test_player_window_cancel_loop_stops_boundary_seeks(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)
    window._on_loop_cue_clicked()
    window._session.cancel_loop()

    assert window._session.loop_mode is LoopMode.NONE

    window.close()


def test_loop_button_toggles_label_between_loop_and_stop(qapp, conn, tmp_path):
    """M12 Round 1 Playback Contract S7.1 (m02-05, P3): the same control must
    show the state transition -- previously the button always read "Loop Cue"
    even while a loop was active, with no visible way to discover a cancel."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    assert window._loop_cue_button.text() == "Loop Cue"

    window._cue_list.setCurrentRow(0)
    window._on_loop_cue_clicked()
    assert window._loop_cue_button.text() == "Stop Loop"

    window._session.cancel_loop()
    window._sync_loop_button_text()
    assert window._loop_cue_button.text() == "Loop Cue"
    window.close()


def test_loop_button_resets_when_cancelled_via_escape_key(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)
    window._on_loop_cue_clicked()
    assert window._loop_cue_button.text() == "Stop Loop"

    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert window._session.loop_mode is LoopMode.NONE
    assert window._loop_cue_button.text() == "Loop Cue"
    window.close()


def test_clicking_loop_button_again_while_active_stops_the_loop(qapp, conn, tmp_path):
    """DIAG-8f31: the button's actual click handler must be a toggle. Every
    prior loop-cancel test drove `_session.cancel_loop()` directly, bypassing
    the real click path -- so the button never had coverage for what the
    human-reported bug actually does: click `Loop Cue`, then click the same
    button again (now reading `Stop Loop`)."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)

    window._on_loop_cue_clicked()
    assert window._session.loop_mode is LoopMode.CUE
    assert window._loop_cue_button.text() == "Stop Loop"

    window._on_loop_cue_clicked()  # simulates clicking "Stop Loop"
    assert window._session.loop_mode is LoopMode.NONE
    assert window._loop_cue_button.text() == "Loop Cue"

    window.close()


def test_loop_button_resets_when_replay_cue_cancels_the_active_loop(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)
    window._on_loop_cue_clicked()
    assert window._loop_cue_button.text() == "Stop Loop"

    window._on_replay_cue()
    assert window._session.loop_mode is LoopMode.NONE
    assert window._loop_cue_button.text() == "Loop Cue"
    window.close()


def test_manual_scroll_suspends_follow_and_shows_return_button(qapp, conn, tmp_path):
    """M12 Round 1 Playback Contract S8 (m02-01/m12-05, P4): a manual scroll
    away from the playing cue must suspend auto-follow and expose a
    lightweight recovery action, rather than fighting the learner's scroll on
    the next position tick."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    assert window._follow_playback is True
    assert window._return_to_playing_button.isHidden() is True

    window._on_transcript_scrollbar_changed(5)  # simulates a real user scroll
    assert window._follow_playback is False
    assert window._return_to_playing_button.isHidden() is False

    window.close()


def test_return_to_playing_cue_resumes_follow(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._on_transcript_scrollbar_changed(5)
    assert window._follow_playback is False

    window._on_return_to_playing_clicked()
    assert window._follow_playback is True
    assert window._return_to_playing_button.isHidden() is True
    window.close()


def test_programmatic_navigation_does_not_suspend_follow(qapp, conn, tmp_path):
    """Round 1 S8: Previous/Next Cue moves the list selection (and its
    built-in scroll-into-view) on purpose -- this must not be mistaken for a
    manual free-scroll that suspends Follow Playback."""
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._cue_list.setCurrentRow(0)
    window._on_next_cue()
    assert window._follow_playback is True
    window.close()


def test_central_widget_is_scrollable_and_workspace_fields_have_a_minimum_height(qapp, conn, tmp_path):
    """M12 Round 2 Layout Contract (m03-01/m03-04/m03-05, L1): reproduces the
    screenshotted human-QA finding that the workspace panel's QLineEdits and
    Save/Update/Delete buttons compressed to unreadable slivers when the
    window was shorter than the stacked content's combined height. Fixed by
    wrapping the content in a resizable QScrollArea (the window scrolls
    instead of squeezing every zero-minimum-height widget) plus an explicit
    minimum height on the fields/buttons that were reported as unreadable."""
    from PySide6.QtWidgets import QScrollArea

    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)
    window = PlayerWindow(_two_cue_result(wav_path), conn)

    central = window.centralWidget()
    assert isinstance(central, QScrollArea)
    assert central.widgetResizable() is True

    for field in (
        window._heard_as_edit,
        window._annotation_note_edit,
        window._item_meaning_edit,
        window._item_note_edit,
    ):
        assert field.minimumHeight() >= 28

    for button in (
        window._save_annotation_button,
        window._update_annotation_button,
        window._delete_annotation_button,
        window._save_note_button,
        window._delete_note_button,
        window._save_item_button,
        window._update_item_button,
        window._delete_item_button,
    ):
        assert button.minimumHeight() >= 28

    window.close()


def test_player_window_toggle_transcript_keeps_active_cue_tracking(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    window._on_toggle_transcript()

    assert window._session.transcript_visible is False
    assert window._cue_list.isVisible() is False

    window._on_position_changed(600)
    assert window._session.active_cue_index == 1

    window.close()


def test_player_window_mute_toggle(qapp, conn, tmp_path):
    wav_path = tmp_path / "lesson.wav"
    _make_wav(wav_path)

    window = PlayerWindow(_two_cue_result(wav_path), conn)
    assert window._playback.is_muted is False

    window._on_toggle_mute()
    assert window._playback.is_muted is True
    assert window._mute_button.text() == "Unmute"

    window._on_toggle_mute()
    assert window._playback.is_muted is False

    window.close()

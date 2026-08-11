from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.services import recording_service
from listentrace.application.services.player_session import PlayerSession
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.widgets.recording_panel import RecordingPanel, recording_change_bus
from listentrace.ui.windows.player_window import _format_time


class ShadowingPracticeWindow(QMainWindow):
    """Milestone 7 standalone entry point: cue-by-cue shadowing and recording on
    one material, with no `PracticeSession` involved (recordings created here
    have `practice_session_id = None`). Reuses `PlayerSession`/
    `PlaybackController` for source cue navigation/playback exactly like
    `GuidedSessionWindow` Stage 4, and the same `RecordingPanel` — the recording/
    playback/comparison/persistence/deletion logic is not reimplemented here.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        load_result: PlayerLoadResult,
        recordings_dir: Path,
        parent: QWidget | None = None,
        initial_cue_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._recordings_dir = recordings_dir
        self._material = load_result.material
        self._cues = load_result.cues
        self.setWindowTitle(f"ListenTrace — Shadowing Practice — {self._material.title}")
        self.resize(820, 680)

        self._playback = PlaybackController(self)
        self._player_session = PlayerSession(self._cues)
        self._playback_usable = True
        self._cue_index: int | None = 0 if self._cues else None
        if initial_cue_id is not None:
            for index, cue in enumerate(self._cues):
                if cue.id == initial_cue_id:
                    self._cue_index = index
                    break
        self._comparison_replay_pending = False

        central = QWidget(self)
        layout = QVBoxLayout(central)

        header_row = QHBoxLayout()
        title_label = QLabel(self._material.title)
        theme.apply_role(title_label, "title")
        header_row.addWidget(title_label)
        self._progress_label = QLabel("")
        theme.apply_role(self._progress_label, "caption")
        header_row.addWidget(self._progress_label, 1)
        layout.addLayout(header_row)

        self._status_label = QLabel("")
        theme.apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        practice_card, practice_column = theme.make_card()
        self._cue_label = QLabel("")
        self._cue_label.setWordWrap(True)
        practice_column.addWidget(self._cue_label)

        transport_row = QHBoxLayout()
        self._previous_button = QPushButton("Previous Cue")
        self._previous_button.clicked.connect(self._on_previous_clicked)
        theme.apply_role(self._previous_button, "secondary")
        self._next_button = QPushButton("Next Cue")
        self._next_button.clicked.connect(self._on_next_clicked)
        theme.apply_role(self._next_button, "secondary")
        self._play_button = QPushButton("Play")
        self._play_button.clicked.connect(self._on_play_clicked)
        theme.apply_role(self._play_button, "secondary")
        self._replay_button = QPushButton("Replay Cue")
        self._replay_button.clicked.connect(self._on_replay_clicked)
        theme.apply_role(self._replay_button, "secondary")
        self._loop_button = QPushButton("Loop Cue")
        self._loop_button.clicked.connect(self._on_loop_clicked)
        theme.apply_role(self._loop_button, "secondary")
        self._time_label = QLabel("00:00 / 00:00")
        for widget in (
            self._previous_button,
            self._next_button,
            self._play_button,
            self._replay_button,
            self._loop_button,
        ):
            transport_row.addWidget(widget)
        transport_row.addWidget(self._time_label)
        practice_column.addLayout(transport_row)

        self._recording_panel = RecordingPanel(connection, recordings_dir, self)
        self._recording_panel.request_play_source.connect(self._on_recording_panel_request_play_source)
        practice_column.addWidget(self._recording_panel, 1)
        layout.addWidget(practice_card, 1)

        bottom_row = QHBoxLayout()
        self._delete_material_recordings_button = QPushButton("Delete All Recordings for This Material")
        self._delete_material_recordings_button.clicked.connect(self._on_delete_material_recordings_clicked)
        theme.apply_role(self._delete_material_recordings_button, "danger")
        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.close)
        theme.apply_role(self._close_button, "quiet")
        bottom_row.addWidget(self._delete_material_recordings_button)
        bottom_row.addWidget(self._close_button)
        layout.addLayout(bottom_row)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        self._refresh()

    # ---- navigation / state ----

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _refresh(self) -> None:
        if not self._cues:
            self._cue_label.setText("No timed cues available.")
            self._progress_label.setText("")
            self._previous_button.setEnabled(False)
            self._next_button.setEnabled(False)
            self._set_playback_controls_enabled(False)
            self._recording_panel.set_context(self._material.id, None, None)
            return

        if self._cue_index is None:
            self._cue_index = 0
        self._cue_index = max(0, min(self._cue_index, len(self._cues) - 1))
        cue = self._cues[self._cue_index]

        self._progress_label.setText(f"Cue {self._cue_index + 1} of {len(self._cues)}")
        self._cue_label.setText(f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}")
        self._previous_button.setEnabled(self._cue_index > 0)
        self._next_button.setEnabled(self._cue_index < len(self._cues) - 1)
        self._set_playback_controls_enabled(self._playback_usable)

        if cue.id is not None:
            self._recording_panel.set_context(self._material.id, cue.id, None)

    def _on_previous_clicked(self) -> None:
        if self._cue_index is not None and self._cue_index > 0:
            self._cue_index -= 1
            self._refresh()

    def _on_next_clicked(self) -> None:
        if self._cue_index is not None and self._cue_index < len(self._cues) - 1:
            self._cue_index += 1
            self._refresh()

    def closeEvent(self, event) -> None:
        self._recording_panel.abort_active_recording()
        self._recording_panel.release_take_playback()
        self._playback.stop()
        super().closeEvent(event)

    # ---- material-wide deletion ----

    def _on_delete_material_recordings_clicked(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete All Recordings",
            f"Delete every recording for {self._material.title!r}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._recording_panel.release_take_playback()
        summary = recording_service.delete_takes_for_material(self._connection, self._recordings_dir, self._material.id)
        if not summary.all_succeeded:
            QMessageBox.warning(
                self,
                "Some Recordings Could Not Be Deleted",
                f"{len(summary.failed)} recording(s) could not be deleted and remain in the list.",
            )
        self._refresh()
        recording_change_bus.material_changed.emit(self._material.id)

    # ---- shared playback plumbing ----

    def _sync_play_button_text(self) -> None:
        self._play_button.setText("Pause" if self._playback.is_playing else "Play")

    def _set_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._play_button, self._replay_button, self._loop_button):
            widget.setEnabled(enabled)

    def _on_play_clicked(self) -> None:
        # M12 Round 1 Playback Contract: Shadowing is cue-oriented, so Play
        # must default to cue-scoped playback (this cue only) -- previously
        # this just resumed/started whole-media continuous playback.
        if self._playback.is_playing:
            self._playback.pause()
            self._sync_play_button_text()
            return
        if self._cue_index is None:
            return
        seek_to = self._player_session.play_cue(self._cue_index)
        if seek_to is not None:
            self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _on_replay_clicked(self) -> None:
        if self._cue_index is None:
            return
        seek_to = self._player_session.replay_cue(self._cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _on_loop_clicked(self) -> None:
        if self._cue_index is None:
            return
        seek_to = self._player_session.loop_cue(self._cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _on_recording_panel_request_play_source(self) -> None:
        if self._cue_index is None:
            return
        self._comparison_replay_pending = True
        seek_to = self._player_session.replay_cue(self._cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._player_session.on_position_changed(position_ms)
        if tick.pause:
            self._playback.pause()
            self._sync_play_button_text()
            if self._comparison_replay_pending:
                self._comparison_replay_pending = False
                self._recording_panel.notify_source_finished()
        if tick.seek_to_ms is not None:
            self._playback.seek(tick.seek_to_ms)
        self._time_label.setText(f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}")

    def _on_end_of_media(self) -> None:
        self._sync_play_button_text()
        if self._comparison_replay_pending:
            self._comparison_replay_pending = False
            self._recording_panel.notify_source_failed()

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._playback_usable = False
        self._set_playback_controls_enabled(False)
        self._comparison_replay_pending = False
        self._recording_panel.notify_source_failed()

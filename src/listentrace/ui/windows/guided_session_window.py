from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.practice_session_state import PracticeSessionState
from listentrace.application.errors import (
    CueNotFoundError,
    DiagnosisNotFoundError,
    KeywordCaptureNotFoundError,
    SessionValidationError,
)
from listentrace.application.services import label_preference_service
from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.keyword_capture_type import KeywordCaptureType
from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.shadowing_status import ShadowingStatus
from listentrace.domain.enums.stage_key import STAGE_ORDER, StageKey
from listentrace.domain.services import session_rules as rules
from listentrace.domain.services.text_range import whole_cue_range
from listentrace.infrastructure.db.learning_repository import list_annotations_for_cue
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui.annotation_highlighting import apply_range_highlighting
from listentrace.ui.text_offset_conversion import (
    SurrogatePairOffsetError,
    codepoint_index_to_qt_offset,
    qt_offset_to_codepoint_index,
)
from listentrace.ui.widgets.recording_panel import RecordingPanel
from listentrace.ui.windows.player_window import _OVERLAP_HIGHLIGHT, _color_badge_icon, _format_time

_STAGE_TITLES: dict[str, str] = {
    StageKey.GLOBAL_COMPREHENSION.value: "Global Comprehension",
    StageKey.KEYWORD_CAPTURE.value: "Keyword & Fragment Capture",
    StageKey.TRANSCRIPT_DIAGNOSIS.value: "Transcript Comparison & Error Diagnosis",
    StageKey.SHADOWING.value: "Sentence-Level Shadowing",
    StageKey.FINAL_SUMMARY.value: "Final Recall",
}

_STAGE1_PROMPTS: list[tuple[str, str]] = [
    ("who_is_speaking", "Who is speaking?"),
    ("where", "Where are they?"),
    ("intent", "What do they want or intend to do?"),
    ("result", "What is the result or outcome?"),
]


class GuidedSessionWindow(QMainWindow):
    """Milestone 5 guided intensive-listening session: five sequential stages built
    on the verified Milestone 3 player and Milestone 4 transcript workspace.

    Reuses `PlayerSession`/`PlaybackController` for cue timing, loop, replay, and
    playback-error handling, `ui.text_offset_conversion` for every Qt cursor
    position, `ui.annotation_highlighting` for transcript highlight painting, and
    `application.services.practice_session_service` for every lifecycle/stage/
    diagnosis rule — none of that established logic is reimplemented here.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        load_result: PlayerLoadResult,
        session_id: int,
        recordings_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._material = load_result.material
        self._cues = load_result.cues
        self._session_id = session_id
        self.setWindowTitle(f"ListenTrace — Guided Practice — {self._material.title}")
        self.resize(960, 760)

        self._playback = PlaybackController(self)
        self._player_session = PlayerSession(self._cues)
        self._playback_usable = True
        self._current_stage = StageKey.GLOBAL_COMPREHENSION.value
        self._state: PracticeSessionState | None = None
        self._diagnosis_cue_index: int | None = None
        self._editing_diagnosis_id: int | None = None
        self._current_diagnosis_evidence: list = []
        self._shadowing_index: int | None = 0 if self._cues else None
        self._editing_capture_id: int | None = None
        self._stage2_locked = False
        self._comparison_replay_pending = False
        self._initialized = False

        self._recording_panel = RecordingPanel(connection, recordings_dir, self)
        self._recording_panel.request_play_source.connect(self._on_recording_panel_request_play_source)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        header_row = QHBoxLayout()
        title_label = QLabel(self._material.title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_row.addWidget(title_label)
        self._stage_progress_label = QLabel("")
        header_row.addWidget(self._stage_progress_label, 1)
        layout.addLayout(header_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: red;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_stage1_panel())
        self._stack.addWidget(self._build_stage2_panel())
        self._stack.addWidget(self._build_stage3_panel())
        self._stack.addWidget(self._build_stage4_panel())
        self._stack.addWidget(self._build_stage5_panel())
        layout.addWidget(self._stack, 1)

        nav_row = QHBoxLayout()
        self._back_button = QPushButton("Back")
        self._back_button.clicked.connect(self._on_back_clicked)
        self._skip_button = QPushButton("Skip Stage")
        self._skip_button.clicked.connect(self._on_skip_stage_clicked)
        self._continue_button = QPushButton("Save and Continue")
        self._continue_button.clicked.connect(self._on_save_and_continue_clicked)
        self._close_button = QPushButton("Close and Resume Later")
        self._close_button.clicked.connect(self.close)
        self._abandon_button = QPushButton("Abandon Session")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)
        self._complete_button = QPushButton("Complete Session")
        self._complete_button.clicked.connect(self._on_complete_session_clicked)
        for button in (
            self._back_button,
            self._skip_button,
            self._continue_button,
            self._close_button,
            self._abandon_button,
            self._complete_button,
        ):
            nav_row.addWidget(button)
        layout.addLayout(nav_row)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        initial_session = svc.get_session(self._connection, self._session_id)
        self._show_stage(initial_session.current_stage if initial_session is not None else self._current_stage)
        self._initialized = True

    # ---- read-only / status helpers ----

    def _read_only(self) -> bool:
        return self._state is None or self._state.session.status != SessionStatus.ACTIVE.value

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    # ---- navigation ----

    def _show_stage(self, stage_key: str) -> None:
        session = svc.get_session(self._connection, self._session_id)
        if session is None:
            return

        if (
            session.status == SessionStatus.ACTIVE.value
            and stage_key == StageKey.TRANSCRIPT_DIAGNOSIS.value
            and session.transcript_revealed_at is None
        ):
            answer = QMessageBox.question(
                self,
                "Reveal Transcript",
                "Stages 1 and 2 will become read-only evidence for this session once the "
                "transcript is revealed. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if self._initialized:
            # Nothing to flush on the very first display: the outgoing stage's
            # widgets haven't been populated with real data yet at that point.
            self._save_current_stage_inputs()

        if stage_key != StageKey.SHADOWING.value:
            # Leaving Stage 4 (or navigating within the session generally) must
            # not leave a capture running unattended and unstoppable.
            self._recording_panel.abort_active_recording()

        if session.status == SessionStatus.ACTIVE.value:
            try:
                svc.enter_stage(self._connection, self._session_id, stage_key)
            except SessionValidationError as exc:
                self._show_status(str(exc))
                return

        self._current_stage = stage_key
        self._refresh_state()

    def _refresh_state(self) -> None:
        state = svc.load_session_state(self._connection, self._session_id)
        self._state = state
        self._populate_stage1(state)
        self._populate_stage2(state)
        self._populate_stage3(state)
        self._populate_stage4(state)
        self._populate_stage5(state)
        self._stack.setCurrentIndex(STAGE_ORDER.index(self._current_stage))
        self._sync_playback_button_texts()
        self._update_progress_label(state)
        self._update_nav_buttons(state)

    def _update_progress_label(self, state: PracticeSessionState) -> None:
        index = STAGE_ORDER.index(self._current_stage) + 1
        title = _STAGE_TITLES[self._current_stage]
        status = state.session.status
        suffix = "" if status == SessionStatus.ACTIVE.value else f"  [{status.upper()} — read-only]"
        self._stage_progress_label.setText(f"Stage {index} of 5: {title}{suffix}")

    def _update_nav_buttons(self, state: PracticeSessionState) -> None:
        read_only = state.session.status != SessionStatus.ACTIVE.value
        index = STAGE_ORDER.index(self._current_stage)
        self._back_button.setEnabled(index > 0)
        self._skip_button.setEnabled(not read_only)
        self._continue_button.setEnabled(not read_only)
        self._abandon_button.setEnabled(not read_only)
        statuses = {key: progress.status for key, progress in state.stage_progress.items()}
        self._complete_button.setEnabled(not read_only and rules.session_can_complete(statuses))

    def _save_current_stage_inputs(self) -> None:
        # Checked live rather than via `self._state`, which may be stale if the
        # session became read-only through some path other than this window's own
        # complete/abandon handlers (e.g. closeEvent firing right after either).
        session = svc.get_session(self._connection, self._session_id)
        if session is None or session.status != SessionStatus.ACTIVE.value:
            return
        if self._current_stage == StageKey.GLOBAL_COMPREHENSION.value:
            self._save_stage1_inputs()
        elif self._current_stage == StageKey.SHADOWING.value:
            self._save_shadowing_note()
        elif self._current_stage == StageKey.FINAL_SUMMARY.value:
            self._save_stage5_inputs()
        # Stage 2 (captures) and Stage 3 (diagnosis) persist immediately on each
        # action; there is nothing pending to flush for them here.

    def _stage_has_evidence(self, stage_key: str) -> bool:
        if self._state is None:
            return False
        if stage_key == StageKey.GLOBAL_COMPREHENSION.value:
            return rules.stage1_can_complete(self._state.stage_responses.get(stage_key, {}))
        if stage_key == StageKey.KEYWORD_CAPTURE.value:
            return len(self._state.keyword_captures) > 0
        if stage_key == StageKey.TRANSCRIPT_DIAGNOSIS.value:
            progress = self._state.stage_progress.get(stage_key)
            return rules.stage3_can_complete(
                len(self._state.session_diagnosis), progress.outcome_key if progress else None
            )
        if stage_key == StageKey.SHADOWING.value:
            return any(p.status != ShadowingStatus.NOT_STARTED.value for p in self._state.shadowing_progress)
        if stage_key == StageKey.FINAL_SUMMARY.value:
            return rules.stage5_can_complete(self._state.stage_responses.get(stage_key, {}).get("summary", ""))
        return False

    def _on_back_clicked(self) -> None:
        index = STAGE_ORDER.index(self._current_stage)
        if index > 0:
            self._show_stage(STAGE_ORDER[index - 1])

    def _on_skip_stage_clicked(self) -> None:
        stage = self._current_stage
        self._save_current_stage_inputs()
        if not self._stage_has_evidence(stage):
            answer = QMessageBox.question(
                self,
                "Skip Stage",
                "This stage has no evidence yet. Skip it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            svc.skip_stage(self._connection, self._session_id, stage)
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        index = STAGE_ORDER.index(stage)
        if index < len(STAGE_ORDER) - 1:
            self._show_stage(STAGE_ORDER[index + 1])
        else:
            self._refresh_state()

    def _on_save_and_continue_clicked(self) -> None:
        stage = self._current_stage
        self._save_current_stage_inputs()
        try:
            svc.complete_stage(self._connection, self._session_id, stage)
        except SessionValidationError:
            pass  # Leaving the stage in_progress is fine — this is not an exam.
        index = STAGE_ORDER.index(stage)
        if index < len(STAGE_ORDER) - 1:
            self._show_stage(STAGE_ORDER[index + 1])
        else:
            self._refresh_state()

    def _on_abandon_clicked(self) -> None:
        answer = QMessageBox.question(
            self,
            "Abandon Session",
            "Abandon this practice session? It will remain in history as read-only.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.abandon_session(self._connection, self._session_id)
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()
        QMessageBox.information(
            self, "Session Abandoned", "This session has been abandoned and is now read-only history."
        )
        self.close()

    def _on_complete_session_clicked(self) -> None:
        self._save_current_stage_inputs()
        try:
            svc.complete_session(self._connection, self._session_id)
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()
        QMessageBox.information(self, "Session Completed", "This intensive practice session is complete.")
        self.close()

    def closeEvent(self, event) -> None:
        self._save_current_stage_inputs()
        self._recording_panel.abort_active_recording()
        self._recording_panel.release_take_playback()
        self._playback.stop()
        super().closeEvent(event)

    # ---- shared playback plumbing (Stages 3 and 4) ----

    def _sync_playback_button_texts(self) -> None:
        text = "Pause" if self._playback.is_playing else "Play"
        if hasattr(self, "_diagnosis_play_button"):
            self._diagnosis_play_button.setText(text)
        if hasattr(self, "_shadowing_play_button"):
            self._shadowing_play_button.setText(text)

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._player_session.on_position_changed(position_ms)
        if tick.pause:
            self._playback.pause()
            self._sync_playback_button_texts()
            if self._comparison_replay_pending:
                self._comparison_replay_pending = False
                self._recording_panel.notify_source_finished()
        if tick.seek_to_ms is not None:
            self._playback.seek(tick.seek_to_ms)

        text = f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}"
        if hasattr(self, "_diagnosis_time_label"):
            self._diagnosis_time_label.setText(text)
        if hasattr(self, "_shadowing_time_label"):
            self._shadowing_time_label.setText(text)

    def _on_end_of_media(self) -> None:
        self._sync_playback_button_texts()

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._playback_usable = False
        self._set_diagnosis_playback_controls_enabled(False)
        self._set_shadowing_playback_controls_enabled(False)

    def _set_diagnosis_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._diagnosis_play_button, self._diagnosis_replay_button, self._diagnosis_loop_button):
            widget.setEnabled(enabled)

    def _set_shadowing_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._shadowing_play_button, self._shadowing_replay_button, self._shadowing_loop_button):
            widget.setEnabled(enabled)

    # ---- Stage 1: Global Comprehension ----

    def _build_stage1_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(
            QLabel(
                "Listen without the transcript. Answer what you can — an empty answer is fine, "
                "but you'll need to explicitly skip this stage if you leave everything blank."
            )
        )
        self._stage1_edits: dict[str, QTextEdit] = {}
        for prompt_key, label_text in _STAGE1_PROMPTS:
            layout.addWidget(QLabel(label_text))
            edit = QTextEdit()
            edit.setMaximumHeight(50)
            self._stage1_edits[prompt_key] = edit
            layout.addWidget(edit)
        layout.addStretch(1)
        return panel

    def _populate_stage1(self, state: PracticeSessionState) -> None:
        responses = state.stage_responses.get(StageKey.GLOBAL_COMPREHENSION.value, {})
        for prompt_key, edit in self._stage1_edits.items():
            edit.blockSignals(True)
            edit.setPlainText(responses.get(prompt_key, ""))
            edit.blockSignals(False)
        locked = state.session.transcript_revealed_at is not None
        enabled = state.session.status == SessionStatus.ACTIVE.value and not locked
        for edit in self._stage1_edits.values():
            edit.setReadOnly(not enabled)

    def _save_stage1_inputs(self) -> None:
        for prompt_key, edit in self._stage1_edits.items():
            try:
                svc.save_stage_response(
                    self._connection, self._session_id, StageKey.GLOBAL_COMPREHENSION.value, prompt_key, edit.toPlainText()
                )
            except SessionValidationError:
                return

    # ---- Stage 2: Keyword & Fragment Capture ----

    def _build_stage2_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(
            QLabel(
                "Capture any keywords, names, numbers, or fragments you catch — spelling doesn't "
                "need to be exact. At least one capture is required to complete this stage."
            )
        )

        add_row = QHBoxLayout()
        self._capture_type_combo = QComboBox()
        for capture_type in KeywordCaptureType:
            self._capture_type_combo.addItem(capture_type.value.replace("_", " "), capture_type.value)
        self._capture_text_edit = QLineEdit()
        self._capture_add_button = QPushButton("Add")
        self._capture_add_button.clicked.connect(self._on_add_capture_clicked)
        add_row.addWidget(self._capture_type_combo)
        add_row.addWidget(self._capture_text_edit, 1)
        add_row.addWidget(self._capture_add_button)
        layout.addLayout(add_row)

        self._capture_list = QListWidget()
        self._capture_list.currentItemChanged.connect(self._on_capture_selected)
        layout.addWidget(self._capture_list, 1)

        buttons_row = QHBoxLayout()
        self._capture_update_button = QPushButton("Update Selected")
        self._capture_update_button.clicked.connect(self._on_update_capture_clicked)
        self._capture_update_button.setEnabled(False)
        self._capture_delete_button = QPushButton("Delete Selected")
        self._capture_delete_button.clicked.connect(self._on_delete_capture_clicked)
        self._capture_delete_button.setEnabled(False)
        self._capture_move_up_button = QPushButton("Move Up")
        self._capture_move_up_button.clicked.connect(self._on_move_capture_up_clicked)
        self._capture_move_up_button.setEnabled(False)
        self._capture_move_down_button = QPushButton("Move Down")
        self._capture_move_down_button.clicked.connect(self._on_move_capture_down_clicked)
        self._capture_move_down_button.setEnabled(False)
        for button in (
            self._capture_update_button,
            self._capture_delete_button,
            self._capture_move_up_button,
            self._capture_move_down_button,
        ):
            buttons_row.addWidget(button)
        layout.addLayout(buttons_row)
        return panel

    def _populate_stage2(self, state: PracticeSessionState) -> None:
        self._editing_capture_id = None
        self._capture_list.blockSignals(True)
        self._capture_list.clear()
        for capture in state.keyword_captures:
            item = QListWidgetItem(f"[{capture.capture_type}] {capture.text}")
            item.setData(Qt.ItemDataRole.UserRole, capture.id)
            self._capture_list.addItem(item)
        self._capture_list.blockSignals(False)

        locked = state.session.transcript_revealed_at is not None
        enabled = state.session.status == SessionStatus.ACTIVE.value and not locked
        self._stage2_locked = not enabled
        self._capture_type_combo.setEnabled(enabled)
        self._capture_text_edit.setEnabled(enabled)
        self._capture_add_button.setEnabled(enabled)
        self._capture_update_button.setEnabled(False)
        self._capture_delete_button.setEnabled(False)
        self._capture_move_up_button.setEnabled(False)
        self._capture_move_down_button.setEnabled(False)

    def _on_capture_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._editing_capture_id = None
            self._capture_update_button.setEnabled(False)
            self._capture_delete_button.setEnabled(False)
            self._capture_move_up_button.setEnabled(False)
            self._capture_move_down_button.setEnabled(False)
            return
        capture_id = current.data(Qt.ItemDataRole.UserRole)
        self._editing_capture_id = capture_id
        locked = self._stage2_locked
        self._capture_update_button.setEnabled(not locked)
        self._capture_delete_button.setEnabled(not locked)
        row = self._capture_list.row(current)
        self._capture_move_up_button.setEnabled(not locked and row > 0)
        self._capture_move_down_button.setEnabled(not locked and row < self._capture_list.count() - 1)

        capture = next((c for c in (self._state.keyword_captures if self._state else []) if c.id == capture_id), None)
        if capture is not None:
            index = self._capture_type_combo.findData(capture.capture_type)
            if index >= 0:
                self._capture_type_combo.setCurrentIndex(index)
            self._capture_text_edit.setText(capture.text)

    def _on_add_capture_clicked(self) -> None:
        try:
            svc.add_keyword_capture(
                self._connection, self._session_id, self._capture_type_combo.currentData(), self._capture_text_edit.text()
            )
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        self._capture_text_edit.clear()
        self._refresh_state()

    def _on_update_capture_clicked(self) -> None:
        if self._editing_capture_id is None:
            return
        try:
            svc.update_keyword_capture(
                self._connection,
                self._session_id,
                self._editing_capture_id,
                self._capture_type_combo.currentData(),
                self._capture_text_edit.text(),
            )
        except (KeywordCaptureNotFoundError, SessionValidationError) as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_delete_capture_clicked(self) -> None:
        if self._editing_capture_id is None:
            return
        answer = QMessageBox.question(
            self, "Delete Capture", "Delete this capture?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_keyword_capture(self._connection, self._session_id, self._editing_capture_id)
        except KeywordCaptureNotFoundError as exc:
            self._show_status(str(exc))
        self._refresh_state()

    def _on_move_capture_up_clicked(self) -> None:
        self._move_capture(-1)

    def _on_move_capture_down_clicked(self) -> None:
        self._move_capture(1)

    def _move_capture(self, delta: int) -> None:
        if self._editing_capture_id is None or self._state is None:
            return
        ids = [c.id for c in self._state.keyword_captures]
        index = ids.index(self._editing_capture_id)
        new_index = index + delta
        if new_index < 0 or new_index >= len(ids):
            return
        ids[index], ids[new_index] = ids[new_index], ids[index]
        svc.reorder_keyword_captures(self._connection, self._session_id, ids)
        moved_id = self._editing_capture_id
        self._refresh_state()
        for i in range(self._capture_list.count()):
            item = self._capture_list.item(i)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == moved_id:
                self._capture_list.setCurrentItem(item)
                break

    # ---- Stage 3: Transcript Comparison & Error Diagnosis ----

    def _build_stage3_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)

        left_column = QVBoxLayout()
        left_column.addWidget(QLabel("Cues:"))
        self._diagnosis_cue_list = QListWidget()
        self._diagnosis_cue_list.currentItemChanged.connect(self._on_diagnosis_cue_selected)
        left_column.addWidget(self._diagnosis_cue_list, 1)

        transport_row = QHBoxLayout()
        self._diagnosis_play_button = QPushButton("Play")
        self._diagnosis_play_button.clicked.connect(self._on_diagnosis_play_clicked)
        self._diagnosis_replay_button = QPushButton("Replay Cue")
        self._diagnosis_replay_button.clicked.connect(self._on_diagnosis_replay_clicked)
        self._diagnosis_loop_button = QPushButton("Loop Cue")
        self._diagnosis_loop_button.clicked.connect(self._on_diagnosis_loop_clicked)
        self._diagnosis_time_label = QLabel("00:00 / 00:00")
        for button in (self._diagnosis_play_button, self._diagnosis_replay_button, self._diagnosis_loop_button):
            transport_row.addWidget(button)
        transport_row.addWidget(self._diagnosis_time_label)
        left_column.addLayout(transport_row)
        layout.addLayout(left_column, 1)

        right_column = QVBoxLayout()
        right_column.addWidget(QLabel("Transcript (select text to diagnose):"))
        self._diagnosis_transcript_view = QTextEdit()
        self._diagnosis_transcript_view.setReadOnly(True)
        self._diagnosis_transcript_view.setMaximumHeight(80)
        right_column.addWidget(self._diagnosis_transcript_view)

        label_row = QHBoxLayout()
        self._diagnosis_label_checkboxes: dict[str, QCheckBox] = {}
        for label in AnnotationLabel:
            checkbox = QCheckBox(label.value.replace("_", " "))
            checkbox.stateChanged.connect(self._on_diagnosis_label_checkbox_changed)
            self._diagnosis_label_checkboxes[label.value] = checkbox
            label_row.addWidget(checkbox)
        right_column.addLayout(label_row)

        heard_as_row = QHBoxLayout()
        heard_as_row.addWidget(QLabel("Heard as:"))
        self._diagnosis_heard_as_edit = QLineEdit()
        self._diagnosis_heard_as_edit.setEnabled(False)
        heard_as_row.addWidget(self._diagnosis_heard_as_edit)
        right_column.addLayout(heard_as_row)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Note:"))
        self._diagnosis_note_edit = QLineEdit()
        note_row.addWidget(self._diagnosis_note_edit)
        right_column.addLayout(note_row)

        diag_buttons_row = QHBoxLayout()
        self._save_diagnosis_button = QPushButton("Save Diagnosis")
        self._save_diagnosis_button.clicked.connect(self._on_save_diagnosis_clicked)
        self._delete_diagnosis_button = QPushButton("Delete")
        self._delete_diagnosis_button.clicked.connect(self._on_delete_diagnosis_clicked)
        self._delete_diagnosis_button.setEnabled(False)
        self._no_difficulty_button = QPushButton("No Notable Difficulty")
        self._no_difficulty_button.clicked.connect(self._on_no_difficulty_clicked)
        diag_buttons_row.addWidget(self._save_diagnosis_button)
        diag_buttons_row.addWidget(self._delete_diagnosis_button)
        diag_buttons_row.addWidget(self._no_difficulty_button)
        right_column.addLayout(diag_buttons_row)

        right_column.addWidget(QLabel("Session diagnosis on this cue:"))
        self._diagnosis_list = QListWidget()
        self._diagnosis_list.setMaximumHeight(100)
        self._diagnosis_list.currentItemChanged.connect(self._on_diagnosis_selected)
        right_column.addWidget(self._diagnosis_list)

        right_column.addWidget(QLabel("Existing material annotations (reference):"))
        self._diagnosis_reference_list = QListWidget()
        self._diagnosis_reference_list.setMaximumHeight(80)
        right_column.addWidget(self._diagnosis_reference_list)

        layout.addLayout(right_column, 1)
        return panel

    def _populate_stage3(self, state: PracticeSessionState) -> None:
        revealed = state.session.transcript_revealed_at is not None
        read_only = state.session.status != SessionStatus.ACTIVE.value

        self._diagnosis_cue_list.blockSignals(True)
        self._diagnosis_cue_list.clear()
        if revealed:
            for cue in self._cues:
                label = f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}"
                self._diagnosis_cue_list.addItem(QListWidgetItem(label))
        self._diagnosis_cue_list.blockSignals(False)
        self._diagnosis_cue_list.setEnabled(revealed)

        self._set_diagnosis_playback_controls_enabled(revealed and self._playback_usable and not read_only)
        self._save_diagnosis_button.setEnabled(revealed and not read_only)
        self._no_difficulty_button.setEnabled(revealed and not read_only)

        if revealed and self._cues:
            index = self._diagnosis_cue_index if self._diagnosis_cue_index is not None else 0
            index = max(0, min(index, len(self._cues) - 1))
            self._diagnosis_cue_list.setCurrentRow(index)
        else:
            self._diagnosis_cue_index = None
            self._diagnosis_transcript_view.setPlainText("")
            self._diagnosis_list.clear()
            self._diagnosis_reference_list.clear()
            self._clear_diagnosis_form()

    def _on_diagnosis_cue_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._diagnosis_cue_index = None
            return
        self._diagnosis_cue_index = self._diagnosis_cue_list.row(current)
        self._refresh_diagnosis_cue_panels()

    def _refresh_diagnosis_cue_panels(self) -> None:
        if self._diagnosis_cue_index is None or self._state is None:
            return
        cue = self._cues[self._diagnosis_cue_index]
        self._diagnosis_transcript_view.setPlainText(cue.text)

        evidence = [d for d in self._state.session_diagnosis if d.subtitle_cue_id == cue.id]
        self._current_diagnosis_evidence = evidence
        colors = label_preference_service.get_label_preferences(self._connection)
        apply_range_highlighting(self._diagnosis_transcript_view, cue.text, evidence, colors, _OVERLAP_HIGHLIGHT)

        self._diagnosis_list.blockSignals(True)
        self._diagnosis_list.clear()
        for item_evidence in evidence:
            heard_as_suffix = f" (heard as: {item_evidence.heard_as})" if item_evidence.heard_as else ""
            list_item = QListWidgetItem(f"[{item_evidence.label_key}] {item_evidence.selected_text}{heard_as_suffix}")
            list_item.setIcon(_color_badge_icon(colors.get(item_evidence.label_key, "#CCCCCC")))
            list_item.setData(Qt.ItemDataRole.UserRole, item_evidence.id)
            self._diagnosis_list.addItem(list_item)
        self._diagnosis_list.blockSignals(False)

        self._diagnosis_reference_list.clear()
        if cue.id is not None:
            for annotation in list_annotations_for_cue(self._connection, cue.id):
                self._diagnosis_reference_list.addItem(f"[{annotation.label_key}] {annotation.selected_text}")

        self._clear_diagnosis_form()

    def _clear_diagnosis_form(self) -> None:
        for checkbox in self._diagnosis_label_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self._diagnosis_heard_as_edit.clear()
        self._diagnosis_heard_as_edit.setEnabled(False)
        self._diagnosis_note_edit.clear()
        self._editing_diagnosis_id = None
        self._delete_diagnosis_button.setEnabled(False)

    def _on_diagnosis_label_checkbox_changed(self, _state: int) -> None:
        misheard = self._diagnosis_label_checkboxes[AnnotationLabel.MISHEARD.value].isChecked()
        self._diagnosis_heard_as_edit.setEnabled(misheard)

    def _on_diagnosis_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._editing_diagnosis_id = None
            self._delete_diagnosis_button.setEnabled(False)
            return
        evidence_id = current.data(Qt.ItemDataRole.UserRole)
        self._editing_diagnosis_id = evidence_id
        self._delete_diagnosis_button.setEnabled(True)

        evidence = next((d for d in self._current_diagnosis_evidence if d.id == evidence_id), None)
        if evidence is None or self._diagnosis_cue_index is None:
            return
        cue = self._cues[self._diagnosis_cue_index]

        for key, checkbox in self._diagnosis_label_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(key == evidence.label_key)
            checkbox.blockSignals(False)
        self._diagnosis_heard_as_edit.setEnabled(evidence.label_key == AnnotationLabel.MISHEARD.value)
        self._diagnosis_heard_as_edit.setText(evidence.heard_as or "")
        self._diagnosis_note_edit.setText(evidence.note or "")

        qt_start = codepoint_index_to_qt_offset(cue.text, evidence.selection_start)
        qt_end = codepoint_index_to_qt_offset(cue.text, evidence.selection_end)
        cursor = self._diagnosis_transcript_view.textCursor()
        cursor.setPosition(qt_start)
        cursor.setPosition(qt_end, QTextCursor.MoveMode.KeepAnchor)
        self._diagnosis_transcript_view.setTextCursor(cursor)

    def _current_diagnosis_selection_range(self, cue_text: str) -> tuple[int, int]:
        cursor = self._diagnosis_transcript_view.textCursor()
        qt_start, qt_end = cursor.selectionStart(), cursor.selectionEnd()
        if qt_start == qt_end:
            return whole_cue_range(cue_text)
        try:
            start = qt_offset_to_codepoint_index(cue_text, qt_start)
            end = qt_offset_to_codepoint_index(cue_text, qt_end)
        except SurrogatePairOffsetError:
            return whole_cue_range(cue_text)
        return start, end

    def _on_save_diagnosis_clicked(self) -> None:
        if self._diagnosis_cue_index is None:
            self._show_status("Select a cue first.")
            return
        cue = self._cues[self._diagnosis_cue_index]
        if cue.id is None:
            return
        checked_labels = [key for key, checkbox in self._diagnosis_label_checkboxes.items() if checkbox.isChecked()]
        if len(checked_labels) != 1:
            self._show_status("Select exactly one label to save a diagnosis.")
            return
        start, end = self._current_diagnosis_selection_range(cue.text)
        heard_as = self._diagnosis_heard_as_edit.text()
        note = self._diagnosis_note_edit.text()
        try:
            if self._editing_diagnosis_id is not None:
                svc.update_session_diagnosis(
                    self._connection,
                    self._session_id,
                    self._editing_diagnosis_id,
                    checked_labels[0],
                    start,
                    end,
                    heard_as=heard_as,
                    note=note,
                )
            else:
                svc.record_session_diagnosis(
                    self._connection,
                    self._session_id,
                    cue.id,
                    start,
                    end,
                    checked_labels[0],
                    heard_as=heard_as,
                    note=note,
                )
        except (CueNotFoundError, SessionValidationError, DiagnosisNotFoundError) as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_delete_diagnosis_clicked(self) -> None:
        if self._editing_diagnosis_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Diagnosis",
            "Delete this session diagnosis? The shared material annotation, if any, is not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_session_diagnosis(self._connection, self._session_id, self._editing_diagnosis_id)
        except (DiagnosisNotFoundError, SessionValidationError) as exc:
            self._show_status(str(exc))
        self._refresh_state()

    def _on_no_difficulty_clicked(self) -> None:
        try:
            svc.mark_stage3_no_difficulty(self._connection, self._session_id)
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        self._show_status("Marked: no notable difficulty found for this session.")
        self._refresh_state()

    def _on_diagnosis_play_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
        else:
            self._playback.play()
        self._sync_playback_button_texts()

    def _on_diagnosis_replay_clicked(self) -> None:
        if self._diagnosis_cue_index is None:
            return
        seek_to = self._player_session.replay_cue(self._diagnosis_cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_diagnosis_loop_clicked(self) -> None:
        if self._diagnosis_cue_index is None:
            return
        seek_to = self._player_session.loop_cue(self._diagnosis_cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    # ---- Stage 4: Sentence-Level Shadowing ----

    def _build_stage4_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(
            QLabel("Shadow each cue: listen, then repeat aloud. Mark it practiced when you're satisfied, or skip it.")
        )

        self._shadowing_progress_label = QLabel("")
        layout.addWidget(self._shadowing_progress_label)

        self._shadowing_cue_label = QLabel("")
        self._shadowing_cue_label.setWordWrap(True)
        self._shadowing_cue_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._shadowing_cue_label)

        transport_row = QHBoxLayout()
        self._shadowing_previous_button = QPushButton("Previous Cue")
        self._shadowing_previous_button.clicked.connect(self._on_shadowing_previous_clicked)
        self._shadowing_next_button = QPushButton("Next Cue")
        self._shadowing_next_button.clicked.connect(self._on_shadowing_next_clicked)
        self._shadowing_play_button = QPushButton("Play")
        self._shadowing_play_button.clicked.connect(self._on_shadowing_play_clicked)
        self._shadowing_replay_button = QPushButton("Replay Cue")
        self._shadowing_replay_button.clicked.connect(self._on_shadowing_replay_clicked)
        self._shadowing_loop_button = QPushButton("Loop Cue")
        self._shadowing_loop_button.clicked.connect(self._on_shadowing_loop_clicked)
        self._shadowing_time_label = QLabel("00:00 / 00:00")
        for button in (
            self._shadowing_previous_button,
            self._shadowing_next_button,
            self._shadowing_play_button,
            self._shadowing_replay_button,
            self._shadowing_loop_button,
        ):
            transport_row.addWidget(button)
        transport_row.addWidget(self._shadowing_time_label)
        layout.addLayout(transport_row)

        action_row = QHBoxLayout()
        self._mark_practiced_button = QPushButton("Mark Practiced")
        self._mark_practiced_button.clicked.connect(self._on_mark_practiced_clicked)
        self._skip_cue_button = QPushButton("Skip Cue")
        self._skip_cue_button.clicked.connect(self._on_skip_shadowing_cue_clicked)
        self._skip_remaining_button = QPushButton("Skip Remaining Cues")
        self._skip_remaining_button.clicked.connect(self._on_skip_remaining_shadowing_clicked)
        action_row.addWidget(self._mark_practiced_button)
        action_row.addWidget(self._skip_cue_button)
        action_row.addWidget(self._skip_remaining_button)
        layout.addLayout(action_row)

        self._shadowing_note_edit = QLineEdit()
        self._shadowing_note_edit.setPlaceholderText("Optional note for this cue")
        layout.addWidget(self._shadowing_note_edit)

        layout.addWidget(self._recording_panel)

        layout.addStretch(1)
        return panel

    def _populate_stage4(self, state: PracticeSessionState) -> None:
        read_only = state.session.status != SessionStatus.ACTIVE.value
        progress_by_cue = {p.subtitle_cue_id: p for p in state.shadowing_progress}
        resolved = sum(1 for p in state.shadowing_progress if p.status != ShadowingStatus.NOT_STARTED.value)
        total = len(state.shadowing_progress)
        self._shadowing_progress_label.setText(f"{resolved} / {total} resolved")

        if not self._cues:
            self._shadowing_cue_label.setText("No timed cues available.")
            self._shadowing_previous_button.setEnabled(False)
            self._shadowing_next_button.setEnabled(False)
            self._set_shadowing_playback_controls_enabled(False)
            self._mark_practiced_button.setEnabled(False)
            self._skip_cue_button.setEnabled(False)
            self._skip_remaining_button.setEnabled(False)
            self._shadowing_note_edit.setEnabled(False)
            self._recording_panel.set_context(self._material.id, None, self._session_id)
            return

        if self._shadowing_index is None:
            self._shadowing_index = 0
        self._shadowing_index = max(0, min(self._shadowing_index, len(self._cues) - 1))
        cue = self._cues[self._shadowing_index]
        progress = progress_by_cue.get(cue.id)
        status_text = progress.status if progress else ShadowingStatus.NOT_STARTED.value
        count_text = progress.practice_count if progress else 0
        self._shadowing_cue_label.setText(
            f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}\n"
            f"Status: {status_text}   Practiced: {count_text}x"
        )
        self._shadowing_note_edit.blockSignals(True)
        self._shadowing_note_edit.setText((progress.note or "") if progress else "")
        self._shadowing_note_edit.blockSignals(False)

        self._shadowing_previous_button.setEnabled(not read_only and self._shadowing_index > 0)
        self._shadowing_next_button.setEnabled(not read_only and self._shadowing_index < len(self._cues) - 1)
        self._set_shadowing_playback_controls_enabled(not read_only and self._playback_usable)
        self._mark_practiced_button.setEnabled(not read_only)
        self._skip_cue_button.setEnabled(not read_only)
        self._skip_remaining_button.setEnabled(
            not read_only and any(p.status == ShadowingStatus.NOT_STARTED.value for p in state.shadowing_progress)
        )
        self._shadowing_note_edit.setEnabled(not read_only)

        if cue.id is not None:
            self._recording_panel.set_context(self._material.id, cue.id, self._session_id)
        self._recording_panel.set_read_only(read_only)

    def _save_shadowing_note(self) -> None:
        if self._shadowing_index is None or self._read_only() or not self._cues:
            return
        cue = self._cues[self._shadowing_index]
        if cue.id is None:
            return
        try:
            svc.set_shadowing_note(self._connection, self._session_id, cue.id, self._shadowing_note_edit.text())
        except (CueNotFoundError, SessionValidationError):
            pass

    def _on_shadowing_previous_clicked(self) -> None:
        if self._shadowing_index is not None and self._shadowing_index > 0:
            self._save_shadowing_note()
            self._shadowing_index -= 1
            self._refresh_state()

    def _on_shadowing_next_clicked(self) -> None:
        if self._shadowing_index is not None and self._shadowing_index < len(self._cues) - 1:
            self._save_shadowing_note()
            self._shadowing_index += 1
            self._refresh_state()

    def _on_shadowing_play_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
        else:
            self._playback.play()
        self._sync_playback_button_texts()

    def _on_shadowing_replay_clicked(self) -> None:
        if self._shadowing_index is None:
            return
        seek_to = self._player_session.replay_cue(self._shadowing_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_shadowing_loop_clicked(self) -> None:
        if self._shadowing_index is None:
            return
        seek_to = self._player_session.loop_cue(self._shadowing_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_recording_panel_request_play_source(self) -> None:
        """The recording panel's "Compare" action asks for one source-cue
        replay; we drive it with the same one-shot `replay_cue` mechanism as
        the Replay Cue button, and tell the panel once it naturally finishes
        (via the `_comparison_replay_pending` flag checked in
        `_on_position_changed`)."""
        if self._shadowing_index is None:
            return
        self._comparison_replay_pending = True
        seek_to = self._player_session.replay_cue(self._shadowing_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_mark_practiced_clicked(self) -> None:
        if self._shadowing_index is None or not self._cues:
            return
        cue = self._cues[self._shadowing_index]
        if cue.id is None:
            return
        self._save_shadowing_note()
        try:
            svc.mark_shadowing_practiced(self._connection, self._session_id, cue.id)
        except (CueNotFoundError, SessionValidationError) as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_skip_shadowing_cue_clicked(self) -> None:
        if self._shadowing_index is None or not self._cues:
            return
        cue = self._cues[self._shadowing_index]
        if cue.id is None:
            return
        self._save_shadowing_note()
        try:
            svc.mark_shadowing_skipped(self._connection, self._session_id, cue.id)
        except (CueNotFoundError, SessionValidationError) as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_skip_remaining_shadowing_clicked(self) -> None:
        answer = QMessageBox.question(
            self,
            "Skip Remaining Cues",
            "Skip all remaining unresolved cues in this stage?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.skip_remaining_shadowing(self._connection, self._session_id)
        except SessionValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    # ---- Stage 5: Final Recall ----

    def _build_stage5_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(
            QLabel("Transcript hidden. Summarize the material in two or three sentences in the target language.")
        )
        self._final_summary_edit = QTextEdit()
        self._final_summary_edit.setMaximumHeight(100)
        layout.addWidget(self._final_summary_edit)

        layout.addWidget(QLabel("Your Stage 1/2 evidence (for reference — no transcript text shown):"))
        self._stage5_reference_view = QTextEdit()
        self._stage5_reference_view.setReadOnly(True)
        self._stage5_reference_view.setMaximumHeight(100)
        layout.addWidget(self._stage5_reference_view)
        layout.addStretch(1)
        return panel

    def _populate_stage5(self, state: PracticeSessionState) -> None:
        responses = state.stage_responses.get(StageKey.FINAL_SUMMARY.value, {})
        self._final_summary_edit.blockSignals(True)
        self._final_summary_edit.setPlainText(responses.get("summary", ""))
        self._final_summary_edit.blockSignals(False)
        self._final_summary_edit.setReadOnly(state.session.status != SessionStatus.ACTIVE.value)

        lines: list[str] = []
        stage1_responses = state.stage_responses.get(StageKey.GLOBAL_COMPREHENSION.value, {})
        for prompt_key, label_text in _STAGE1_PROMPTS:
            text = stage1_responses.get(prompt_key, "").strip()
            if text:
                lines.append(f"{label_text} {text}")
        if state.keyword_captures:
            captures_text = ", ".join(f"[{c.capture_type}] {c.text}" for c in state.keyword_captures)
            lines.append(f"Captures: {captures_text}")
        self._stage5_reference_view.setPlainText("\n".join(lines) if lines else "(no Stage 1/2 evidence recorded)")

    def _save_stage5_inputs(self) -> None:
        try:
            svc.save_stage_response(
                self._connection,
                self._session_id,
                StageKey.FINAL_SUMMARY.value,
                "summary",
                self._final_summary_edit.toPlainText(),
            )
        except SessionValidationError:
            pass

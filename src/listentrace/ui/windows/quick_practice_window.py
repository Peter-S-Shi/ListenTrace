from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import PlayerTick
from listentrace.application.dto.quick_practice import QuickPracticeItemState, QuickPracticeSessionState
from listentrace.application.errors import (
    CueNotFoundError,
    QuickPracticeDiagnosisNotFoundError,
    QuickPracticeValidationError,
)
from listentrace.application.services import label_preference_service
from listentrace.application.services import loop_grace_service
from listentrace.application.services import quick_practice_service as svc
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.enums.recall_result import RecallResult
from listentrace.domain.services.text_range import whole_cue_range
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.widgets.notebook_paper import GrainedDeskWidget
from listentrace.ui.annotation_highlighting import UNKNOWN_LABEL_COLOR, apply_range_highlighting
from listentrace.ui.text_offset_conversion import (
    SurrogatePairOffsetError,
    codepoint_index_to_qt_offset,
    qt_offset_to_codepoint_index,
)
from listentrace.ui.theme import SPACE_COMPACT, SPACE_NORMAL, apply_role, apply_surface
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.widgets.recording_panel import RecordingPanel
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
from listentrace.ui.windows.player_window import _OVERLAP_HIGHLIGHT, _color_badge_icon, _format_time

_STEP_LISTEN_RECALL = 0
_STEP_DIAGNOSE = 1
_STEP_REPLAY = 2
_STEP_SUMMARY = 3

_RECALL_LABELS: list[tuple[str, str]] = [
    (RecallResult.UNDERSTOOD.value, "Understood"),
    (RecallResult.PARTLY_UNDERSTOOD.value, "Partly Understood"),
    (RecallResult.MISSED.value, "Missed"),
]


class QuickPracticeWindow(QMainWindow):
    """M13 Reconstructed Quick Practice Workspace.

    Compact, forward-only cue practice micro-cycle:
    - Anchored Cue Context & Navigation Header
    - Step 1: Listen & Self-Assessment Recall Card
    - Step 2: Reveal & Error Diagnosis Workspace
    - Step 3: Replay & Shadowing Recording Studio
    - Step 4: Run Summary Dossier
    - Hero Primary Progression Action bar
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        load_result: PlayerLoadResult,
        quick_practice_session_id: int,
        recordings_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._material = load_result.material
        self._cue_by_id = {cue.id: cue for cue in load_result.cues if cue.id is not None}
        self._full_cue_index_by_id = {cue.id: index for index, cue in enumerate(load_result.cues) if cue.id is not None}
        self._session_id = quick_practice_session_id
        self.setWindowTitle(f"ListenTrace — Quick Practice — {self._material.title}")
        self.resize(920, 700)
        self.setMinimumSize(780, 560)

        self._playback = PlaybackController(self)
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(connection, self._material.id)
        self._player_session = PlayerSession(load_result.cues, loop_end_grace_ms=grace_ms)
        self._loop_settings_dialog: MaterialLoopSettingsDialog | None = None
        loop_grace_change_bus.global_default_changed.connect(self._on_loop_grace_global_default_changed)
        loop_grace_change_bus.material_override_changed.connect(self._on_loop_grace_material_override_changed)
        self._playback_usable = True
        self._state: QuickPracticeSessionState | None = None
        self._index = 0
        self._step = _STEP_LISTEN_RECALL
        self._editing_diagnosis_id: int | None = None
        self._current_diagnosis_evidence: list = []
        self._comparison_replay_pending = False

        self._recording_panel = RecordingPanel(connection, recordings_dir, self)
        self._recording_panel.request_play_source.connect(self._on_recording_panel_request_play_source)

        central = GrainedDeskWidget(self)
        apply_surface(central, "paper")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL)
        layout.setSpacing(SPACE_NORMAL)
        apply_surface(self, "paper")

        # -------------------------------------------------------------------
        # 1. Header & Micro-cycle Context
        # -------------------------------------------------------------------
        header = theme.make_surface_header(self._material.title)
        header_row = header.top_bar
        self._progress_label = QLabel("")
        apply_role(self._progress_label, "caption")
        header.title_row.addWidget(self._progress_label, 1)

        close_top_btn = QPushButton("Exit")
        apply_role(close_top_btn, "quiet")
        theme.set_button_icon(close_top_btn, "close", color_token="secondary")
        close_top_btn.clicked.connect(self.close)
        header_row.addWidget(close_top_btn)
        layout.addLayout(header_row)

        self._status_label = QLabel("")
        apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # -------------------------------------------------------------------
        # 2. Main Micro-Cycle Working Stage Stack
        # -------------------------------------------------------------------
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_listen_recall_panel())
        self._stack.addWidget(self._build_diagnose_panel())
        self._stack.addWidget(self._build_replay_panel())
        self._stack.addWidget(self._build_summary_panel())
        # M13 corrective: keep the active step card top-centered at a
        # comfortable working width rather than stretching a small task over
        # the full window, and keep the progression action directly below it
        # (see step_column below) instead of far away at the window edge.
        self._stack.setMaximumWidth(600)

        step_column = QVBoxLayout()
        step_column.addWidget(self._stack, 1)

        # -------------------------------------------------------------------
        # 3. Action Footer — spatially connected to the active step card,
        #    not stretched across the full window width.
        # -------------------------------------------------------------------
        nav_row = QHBoxLayout()
        nav_row.addStretch(1)

        self._close_button = QPushButton("Close and Finish")
        self._close_button.clicked.connect(self.close)
        apply_role(self._close_button, "quiet")
        nav_row.addWidget(self._close_button)

        self._step_action_button = QPushButton("")
        self._step_action_button.clicked.connect(self._on_step_action_clicked)
        self._step_action_button.setProperty("hero", "true")
        apply_role(self._step_action_button, "primary")
        nav_row.addWidget(self._step_action_button)
        step_column.addLayout(nav_row)

        centered_row = QHBoxLayout()
        centered_row.addStretch(1)
        centered_row.addLayout(step_column, 0)
        centered_row.addStretch(1)
        layout.addLayout(centered_row, 1)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        self._apply_step_button_roles()
        self._refresh_state()

    def _apply_step_button_roles(self) -> None:
        """Milestone 11 role assignments."""
        for attr in (
            "_listen_play_button",
            "_listen_replay_button",
            "_listen_loop_button",
            "_listen_loop_settings_button",
            "_replay_play_button",
            "_replay_replay_button",
            "_replay_loop_button",
            "_replay_loop_settings_button",
        ):
            if hasattr(self, attr):
                apply_role(getattr(self, attr), "secondary")
        apply_role(self._save_diagnosis_button, "secondary")
        apply_role(self._delete_diagnosis_button, "danger")
        apply_role(self._mark_shadowed_button, "secondary")

    # ---- state loading ----

    def _refresh_state(self) -> None:
        state = svc.load_session_state(self._connection, self._session_id)
        self._state = state
        self._index = max(0, min(self._index, max(len(state.items) - 1, 0)))
        if state.session.status != QuickPracticeStatus.ACTIVE.value and self._step != _STEP_SUMMARY:
            self._step = _STEP_SUMMARY
        self._render_current_step()

    def _current_item_state(self) -> QuickPracticeItemState | None:
        if self._state is None or not (0 <= self._index < len(self._state.items)):
            return None
        return self._state.items[self._index]

    def _current_cue(self):
        item_state = self._current_item_state()
        if item_state is None:
            return None
        return self._cue_by_id.get(item_state.item.subtitle_cue_id)

    def _current_full_cue_index(self) -> int | None:
        item_state = self._current_item_state()
        if item_state is None:
            return None
        return self._full_cue_index_by_id.get(item_state.item.subtitle_cue_id)

    def _is_last_item(self) -> bool:
        return self._state is not None and self._index == len(self._state.items) - 1

    def _render_current_step(self) -> None:
        if self._state is None:
            return
        total = len(self._state.items)
        if self._step == _STEP_SUMMARY:
            self._progress_label.setText(f"Quick Practice — {self._state.session.status.upper()}")
        else:
            self._progress_label.setText(f"Cue {self._index + 1} of {total}")
        self._stack.setCurrentIndex(self._step)
        self._sync_playback_button_texts()
        if self._step == _STEP_LISTEN_RECALL:
            self._populate_listen_recall()
        elif self._step == _STEP_DIAGNOSE:
            self._populate_diagnose()
        elif self._step == _STEP_REPLAY:
            self._populate_replay()
        else:
            self._populate_summary()

    # ---- shared playback plumbing ----

    def _on_open_loop_settings(self) -> None:
        if self._loop_settings_dialog is None:
            self._loop_settings_dialog = MaterialLoopSettingsDialog(
                self._connection, self._material.id, self._material.title, self
            )
        self._loop_settings_dialog.show()
        self._loop_settings_dialog.raise_()
        self._loop_settings_dialog.activateWindow()

    def _on_loop_grace_global_default_changed(self) -> None:
        self._refresh_loop_end_grace()

    def _on_loop_grace_material_override_changed(self, material_id: int) -> None:
        if material_id == self._material.id:
            self._refresh_loop_end_grace()

    def _refresh_loop_end_grace(self) -> None:
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(self._connection, self._material.id)
        self._player_session.set_loop_end_grace_ms(grace_ms)

    def _sync_playback_button_texts(self) -> None:
        text = "Pause" if self._playback.is_playing else "Play"
        for attr in ("_listen_play_button", "_replay_play_button"):
            if hasattr(self, attr):
                getattr(self, attr).setText(text)

    def _apply_player_tick(self, tick: PlayerTick) -> None:
        if tick.restart_at_ms is not None:
            self._playback.restart_span(tick.restart_at_ms)
        elif tick.pause:
            self._playback.pause()
            self._sync_playback_button_texts()

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._player_session.on_position_changed(position_ms)
        self._apply_player_tick(tick)
        if tick.pause and tick.restart_at_ms is None and self._comparison_replay_pending:
            self._comparison_replay_pending = False
            self._recording_panel.notify_source_finished()

        text = f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}"
        for attr in ("_listen_time_label", "_replay_time_label"):
            if hasattr(self, attr):
                getattr(self, attr).setText(text)

    def _on_end_of_media(self) -> None:
        tick = self._player_session.on_media_ended()
        self._apply_player_tick(tick)
        if tick.restart_at_ms is None:
            self._sync_playback_button_texts()
        if self._comparison_replay_pending:
            self._comparison_replay_pending = False
            self._recording_panel.notify_source_failed()

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._playback_usable = False
        self._set_playback_controls_enabled(False)
        self._comparison_replay_pending = False
        self._recording_panel.notify_source_failed()

    def _set_playback_controls_enabled(self, enabled: bool) -> None:
        for attr in (
            "_listen_play_button",
            "_listen_replay_button",
            "_listen_loop_button",
            "_listen_loop_settings_button",
            "_replay_play_button",
            "_replay_replay_button",
            "_replay_loop_button",
            "_replay_loop_settings_button",
        ):
            if hasattr(self, attr):
                getattr(self, attr).setEnabled(enabled)

    def _on_play_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
            self._sync_playback_button_texts()
            return
        index = self._current_full_cue_index()
        if index is None:
            return
        seek_to = self._player_session.play_cue(index)
        if seek_to is not None:
            self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_replay_clicked(self) -> None:
        index = self._current_full_cue_index()
        if index is None:
            return
        seek_to = self._player_session.replay_cue(index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_loop_clicked(self) -> None:
        index = self._current_full_cue_index()
        if index is None:
            return
        seek_to = self._player_session.loop_cue(index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    def closeEvent(self, event) -> None:
        session = svc.get_session(self._connection, self._session_id)
        session_is_active = session is not None and session.status == QuickPracticeStatus.ACTIVE.value
        if session_is_active:
            completed_count = sum(
                1 for item_state in (self._state.items if self._state else []) if item_state.item.completed_at is not None
            )
            if completed_count > 0:
                answer = QMessageBox.question(
                    self,
                    "Abandon Quick Practice Run",
                    "Close this Quick Practice run? Completed cues are kept as read-only history; "
                    "the run will be marked abandoned.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

        self._recording_panel.abort_active_recording()
        self._recording_panel.release_take_playback()
        self._playback.stop()
        if session_is_active:
            svc.close_session(self._connection, self._session_id)
        super().closeEvent(event)

    # ---- step navigation ----

    def _on_step_action_clicked(self) -> None:
        if self._step == _STEP_LISTEN_RECALL:
            self._on_recall_continue_clicked()
        elif self._step == _STEP_DIAGNOSE:
            self._step = _STEP_REPLAY
            self._render_current_step()
        elif self._step == _STEP_REPLAY:
            self._on_finish_item_clicked()

    # ---- Step 1+2: Listen & Recall ----

    def _build_listen_recall_panel(self) -> QWidget:
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        inst_lbl = QLabel("Step 1: Listen without transcript, then choose your comprehension level.")
        apply_role(inst_lbl, "subtitle")
        layout.addWidget(inst_lbl)

        # Audio Bar Card
        audio_card = QFrame()
        apply_role(audio_card, "inset_panel")
        transport_row = QHBoxLayout(audio_card)
        transport_row.setContentsMargins(8, 6, 8, 6)

        self._listen_play_button = QPushButton("Play")
        self._listen_play_button.clicked.connect(self._on_play_clicked)
        apply_role(self._listen_play_button, "secondary")

        self._listen_replay_button = QPushButton("Replay Cue")
        self._listen_replay_button.clicked.connect(self._on_replay_clicked)
        apply_role(self._listen_replay_button, "secondary")

        self._listen_loop_button = QPushButton("Loop Cue")
        self._listen_loop_button.clicked.connect(self._on_loop_clicked)
        apply_role(self._listen_loop_button, "secondary")

        self._listen_loop_settings_button = QPushButton("Loop Settings...")
        self._listen_loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._listen_loop_settings_button, "quiet")

        self._listen_time_label = QLabel("00:00 / 00:00")
        apply_role(self._listen_time_label, "monospace")

        for button in (
            self._listen_play_button,
            self._listen_replay_button,
            self._listen_loop_button,
            self._listen_loop_settings_button,
        ):
            transport_row.addWidget(button)
        transport_row.addStretch(1)
        transport_row.addWidget(self._listen_time_label)
        layout.addWidget(audio_card)

        # Recall Options Card
        recall_card, recall_layout = theme.make_card()
        apply_surface(recall_card, "paper")

        recall_hdr = QLabel("Comprehension Self-Assessment:")
        apply_role(recall_hdr, "caption")
        recall_layout.addWidget(recall_hdr)

        recall_row = QHBoxLayout()
        self._recall_group = QButtonGroup(self)
        self._recall_radio_buttons: dict[str, QRadioButton] = {}
        for value, label_text in _RECALL_LABELS:
            radio = QRadioButton(label_text)
            radio.setStyleSheet("font-size: 13px; font-weight: 500; padding: 6px;")
            radio.toggled.connect(self._on_recall_choice_changed)
            self._recall_group.addButton(radio)
            self._recall_radio_buttons[value] = radio
            recall_row.addWidget(radio)
        recall_layout.addLayout(recall_row)

        frag_hdr = QLabel("What words/phrases did you catch? (optional)")
        apply_role(frag_hdr, "caption")
        recall_layout.addWidget(frag_hdr)

        self._heard_fragment_edit = QLineEdit()
        self._heard_fragment_edit.setPlaceholderText("Enter words or sounds you caught...")
        recall_layout.addWidget(self._heard_fragment_edit)

        layout.addWidget(recall_card)
        layout.addStretch(1)
        return panel

    def _populate_listen_recall(self) -> None:
        cue = self._current_cue()
        for radio in self._recall_radio_buttons.values():
            radio.blockSignals(True)
            radio.setChecked(False)
            radio.blockSignals(False)
        self._heard_fragment_edit.clear()
        self._set_playback_controls_enabled(cue is not None and self._playback_usable)
        self._step_action_button.setText("Reveal and Continue")
        self._step_action_button.setEnabled(False)
        self._close_button.setEnabled(True)

    def _on_recall_choice_changed(self, *_args) -> None:
        self._step_action_button.setEnabled(self._selected_recall_result() is not None)

    def _selected_recall_result(self) -> str | None:
        for value, radio in self._recall_radio_buttons.items():
            if radio.isChecked():
                return value
        return None

    def _on_recall_continue_clicked(self) -> None:
        item_state = self._current_item_state()
        recall_result = self._selected_recall_result()
        if item_state is None or item_state.item.id is None or recall_result is None:
            return
        try:
            svc.record_recall(self._connection, item_state.item.id, recall_result, self._heard_fragment_edit.text())
        except QuickPracticeValidationError as exc:
            self._show_status(str(exc))
            return
        self._step = _STEP_DIAGNOSE
        self._refresh_state()

    # ---- Step 3: Reveal & Diagnose ----

    def _build_diagnose_panel(self) -> QWidget:
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        inst_lbl = QLabel("Step 2: Transcript revealed — compare and diagnose difficulty if useful.")
        apply_role(inst_lbl, "subtitle")
        layout.addWidget(inst_lbl)

        self._diagnosis_transcript_view = QTextEdit()
        self._diagnosis_transcript_view.setReadOnly(True)
        self._diagnosis_transcript_view.setMinimumHeight(70)
        self._diagnosis_transcript_view.setMaximumHeight(95)
        layout.addWidget(self._diagnosis_transcript_view)

        self._heard_fragment_reference_label = QLabel("")
        self._heard_fragment_reference_label.setWordWrap(True)
        apply_role(self._heard_fragment_reference_label, "caption")
        layout.addWidget(self._heard_fragment_reference_label)

        # A single QHBoxLayout row can't hold all five label names (the
        # longest, "connected reduced speech", forces the others to squish
        # or truncate at this card's width) -- a fixed-column grid keeps
        # every label fully readable regardless of window width.
        _LABEL_GRID_COLUMNS = 3
        label_grid = QGridLayout()
        label_grid.setHorizontalSpacing(SPACE_NORMAL)
        label_grid.setVerticalSpacing(SPACE_COMPACT)
        self._diagnosis_label_checkboxes: dict[str, QCheckBox] = {}
        for index, label in enumerate(AnnotationLabel):
            checkbox = QCheckBox(label.value.replace("_", " "))
            checkbox.stateChanged.connect(self._on_diagnosis_label_checkbox_changed)
            self._diagnosis_label_checkboxes[label.value] = checkbox
            row, column = divmod(index, _LABEL_GRID_COLUMNS)
            label_grid.addWidget(checkbox, row, column)
        layout.addLayout(label_grid)

        heard_as_row = QHBoxLayout()
        heard_lbl = QLabel("Heard as:")
        apply_role(heard_lbl, "caption")
        heard_as_row.addWidget(heard_lbl)
        self._diagnosis_heard_as_edit = QLineEdit()
        self._diagnosis_heard_as_edit.setEnabled(False)
        heard_as_row.addWidget(self._diagnosis_heard_as_edit)
        layout.addLayout(heard_as_row)

        note_row = QHBoxLayout()
        note_lbl = QLabel("Note:")
        apply_role(note_lbl, "caption")
        note_row.addWidget(note_lbl)
        self._diagnosis_note_edit = QLineEdit()
        note_row.addWidget(self._diagnosis_note_edit)
        layout.addLayout(note_row)

        buttons_row = QHBoxLayout()
        self._save_diagnosis_button = QPushButton("Save Diagnosis")
        self._save_diagnosis_button.clicked.connect(self._on_save_diagnosis_clicked)
        apply_role(self._save_diagnosis_button, "secondary")
        theme.set_button_icon(self._save_diagnosis_button, "save", color_token="secondary")

        self._delete_diagnosis_button = QPushButton("Delete Selected")
        self._delete_diagnosis_button.clicked.connect(self._on_delete_diagnosis_clicked)
        self._delete_diagnosis_button.setEnabled(False)
        apply_role(self._delete_diagnosis_button, "danger")
        theme.set_button_icon(self._delete_diagnosis_button, "delete", color_token="danger")

        buttons_row.addWidget(self._save_diagnosis_button)
        buttons_row.addWidget(self._delete_diagnosis_button)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        diag_hdr = QLabel("Diagnosis recorded on this cue during this run:")
        apply_role(diag_hdr, "caption")
        layout.addWidget(diag_hdr)

        self._diagnosis_list = QListWidget()
        apply_role(self._diagnosis_list, "ruled_list")
        theme.configure_long_text_list(self._diagnosis_list)
        self._diagnosis_list.setMaximumHeight(85)
        self._diagnosis_list.currentItemChanged.connect(self._on_diagnosis_selected)
        layout.addWidget(self._diagnosis_list)

        layout.addStretch(1)
        return panel

    def _populate_diagnose(self) -> None:
        cue = self._current_cue()
        item_state = self._current_item_state()
        if cue is None or item_state is None:
            return
        self._diagnosis_transcript_view.setPlainText(cue.text)
        fragment = item_state.item.heard_fragment
        self._heard_fragment_reference_label.setText(
            f"What you said you heard: {fragment}" if fragment else "You did not enter a heard fragment."
        )

        self._current_diagnosis_evidence = item_state.diagnosis
        colors = label_preference_service.get_label_preferences(self._connection)
        apply_range_highlighting(self._diagnosis_transcript_view, cue.text, item_state.diagnosis, colors, _OVERLAP_HIGHLIGHT)

        self._diagnosis_list.blockSignals(True)
        self._diagnosis_list.clear()
        for diag in item_state.diagnosis:
            heard_as_suffix = f" (heard as: {diag.heard_as})" if diag.heard_as else ""
            item = QListWidgetItem(f"[{diag.label_key}] {diag.selected_text}{heard_as_suffix}")
            item.setIcon(_color_badge_icon(colors.get(diag.label_key, UNKNOWN_LABEL_COLOR)))
            item.setData(Qt.ItemDataRole.UserRole, diag.id)
            self._diagnosis_list.addItem(item)
        self._diagnosis_list.blockSignals(False)

        self._clear_diagnosis_form()
        self._step_action_button.setText("Continue to Shadowing")
        self._step_action_button.setEnabled(True)

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
        cue = self._current_cue()
        if evidence is None or cue is None:
            return

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
        item_state = self._current_item_state()
        cue = self._current_cue()
        if item_state is None or item_state.item.id is None or cue is None:
            return
        checked_labels = [key for key, checkbox in self._diagnosis_label_checkboxes.items() if checkbox.isChecked()]
        if len(checked_labels) != 1:
            self._show_status("Select exactly one label to save a diagnosis.")
            return
        start, end = self._current_diagnosis_selection_range(cue.text)
        try:
            svc.record_item_diagnosis(
                self._connection,
                item_state.item.id,
                start,
                end,
                checked_labels[0],
                heard_as=self._diagnosis_heard_as_edit.text(),
                note=self._diagnosis_note_edit.text(),
            )
        except (CueNotFoundError, QuickPracticeValidationError) as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_delete_diagnosis_clicked(self) -> None:
        item_state = self._current_item_state()
        if item_state is None or item_state.item.id is None or self._editing_diagnosis_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Diagnosis",
            "Delete this diagnosis? The shared material annotation, if any, is not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_item_diagnosis(self._connection, item_state.item.id, self._editing_diagnosis_id)
        except (QuickPracticeDiagnosisNotFoundError, QuickPracticeValidationError) as exc:
            self._show_status(str(exc))
        self._refresh_state()

    # ---- Step 4: Replay & Shadow ----

    def _build_replay_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        apply_surface(scroll, "paper")

        panel = QWidget()
        apply_surface(panel, "paper")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_NORMAL)

        # Cue Card
        cue_card, cue_layout = theme.make_card()
        apply_surface(cue_card, "paper")

        inst_lbl = QLabel("Step 3: Replay the cue and shadow aloud.")
        apply_role(inst_lbl, "subtitle")
        cue_layout.addWidget(inst_lbl)

        self._replay_cue_label = QLabel("")
        self._replay_cue_label.setWordWrap(True)
        apply_role(self._replay_cue_label, "dominant_cue")
        cue_layout.addWidget(self._replay_cue_label)

        transport_row = QHBoxLayout()
        self._replay_play_button = QPushButton("Play")
        self._replay_play_button.clicked.connect(self._on_play_clicked)
        apply_role(self._replay_play_button, "secondary")

        self._replay_replay_button = QPushButton("Replay Cue")
        self._replay_replay_button.clicked.connect(self._on_replay_clicked)
        apply_role(self._replay_replay_button, "secondary")

        self._replay_loop_button = QPushButton("Loop Cue")
        self._replay_loop_button.clicked.connect(self._on_loop_clicked)
        apply_role(self._replay_loop_button, "secondary")

        self._replay_loop_settings_button = QPushButton("Loop Settings...")
        self._replay_loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._replay_loop_settings_button, "quiet")

        self._replay_time_label = QLabel("00:00 / 00:00")
        apply_role(self._replay_time_label, "monospace")

        transport_row.addWidget(self._replay_play_button)
        transport_row.addWidget(self._replay_replay_button)
        transport_row.addWidget(self._replay_loop_button)
        transport_row.addWidget(self._replay_loop_settings_button)
        transport_row.addStretch(1)
        transport_row.addWidget(self._replay_time_label)
        cue_layout.addLayout(transport_row)
        layout.addWidget(cue_card)

        # Recording Panel
        layout.addWidget(self._recording_panel)

        # Shadowed Action
        action_card, action_layout = theme.make_card()
        apply_surface(action_card, "paper")
        self._mark_shadowed_button = QPushButton("Mark Shadowed (Optional)")
        self._mark_shadowed_button.clicked.connect(self._on_mark_shadowed_clicked)
        apply_role(self._mark_shadowed_button, "secondary")
        theme.set_button_icon(self._mark_shadowed_button, "check", color_token="secondary")
        action_layout.addWidget(self._mark_shadowed_button)
        layout.addWidget(action_card)

        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def _populate_replay(self) -> None:
        cue = self._current_cue()
        item_state = self._current_item_state()
        if cue is None or item_state is None:
            return
        self._replay_cue_label.setText(f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}")
        self._set_playback_controls_enabled(self._playback_usable)
        if cue.id is not None:
            self._recording_panel.set_context(self._material.id, cue.id, None)

        is_last = self._is_last_item()
        self._step_action_button.setText("Finish Run" if is_last else "Next Cue")
        self._step_action_button.setEnabled(True)

    def _on_recording_panel_request_play_source(self) -> None:
        index = self._current_full_cue_index()
        if index is None:
            return
        self._comparison_replay_pending = True
        seek_to = self._player_session.replay_cue(index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_playback_button_texts()

    def _on_mark_shadowed_clicked(self) -> None:
        item_state = self._current_item_state()
        if item_state is None or item_state.item.id is None:
            return
        try:
            svc.mark_item_shadowed(self._connection, item_state.item.id)
        except QuickPracticeValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()

    def _on_finish_item_clicked(self) -> None:
        item_state = self._current_item_state()
        if item_state is None or item_state.item.id is None:
            return
        try:
            svc.complete_item(self._connection, item_state.item.id)
        except QuickPracticeValidationError as exc:
            self._show_status(str(exc))
            return

        if self._is_last_item():
            try:
                svc.complete_session(self._connection, self._session_id)
            except QuickPracticeValidationError as exc:
                self._show_status(str(exc))
                return
            self._step = _STEP_SUMMARY
            self._refresh_state()
            return

        self._index += 1
        self._step = _STEP_LISTEN_RECALL
        self._recording_panel.abort_active_recording()
        self._refresh_state()

    # ---- Summary Step ----

    def _build_summary_panel(self) -> QWidget:
        panel, layout = theme.make_card("Quick Practice Run Summary")
        apply_surface(panel, "paper")

        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        apply_role(self._summary_label, "subtitle")
        layout.addWidget(self._summary_label)
        layout.addStretch(1)
        return panel

    def _populate_summary(self) -> None:
        if self._state is None:
            return
        status = self._state.session.status
        if status != QuickPracticeStatus.COMPLETED.value:
            self._summary_label.setText(f"This Quick Practice run is {status}.")
            self._step_action_button.setEnabled(False)
            return
        summary = svc.build_completion_summary(self._connection, self._session_id)
        lines = [
            f"Cues completed: {summary.cues_completed}",
            f"Understood: {summary.understood_count}   Partly Understood: {summary.partly_understood_count}   "
            f"Missed: {summary.missed_count}",
            f"Diagnoses created: {summary.diagnoses_created}",
            f"Explicit shadowing actions: {summary.shadowing_actions}",
        ]
        if summary.cues_worth_revisiting:
            texts = []
            for cue_id in summary.cues_worth_revisiting:
                cue = self._cue_by_id.get(cue_id)
                if cue is not None:
                    texts.append(f"• {cue.text}")
            if texts:
                lines.append("")
                lines.append("Cues worth revisiting:")
                lines.extend(texts)
        self._summary_label.setText("\n".join(lines))
        self._step_action_button.setText("Done")
        self._step_action_button.setEnabled(True)
        try:
            self._step_action_button.clicked.disconnect()
        except Exception:
            pass
        self._step_action_button.clicked.connect(self.close)
        self._close_button.setEnabled(False)

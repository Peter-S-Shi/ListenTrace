from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import PlayerTick
from listentrace.application.dto.practice_session_state import PracticeSessionState
from listentrace.application.errors import (
    CueNotFoundError,
    DiagnosisNotFoundError,
    KeywordCaptureNotFoundError,
    SessionValidationError,
)
from listentrace.application.services import label_preference_service
from listentrace.application.services import loop_grace_service
from listentrace.application.services import practice_session_service as svc
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.keyword_capture_type import KeywordCaptureType
from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.shadowing_status import ShadowingStatus
from listentrace.domain.enums.stage_key import STAGE_ORDER, StageKey
from listentrace.domain.enums.stage_status import StageStatus
from listentrace.domain.services import session_rules as rules
from listentrace.domain.services.text_range import whole_cue_range
from listentrace.infrastructure.db.learning_repository import list_annotations_for_cue
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.annotation_highlighting import UNKNOWN_LABEL_COLOR, apply_range_highlighting
from listentrace.ui.text_offset_conversion import (
    SurrogatePairOffsetError,
    codepoint_index_to_qt_offset,
    qt_offset_to_codepoint_index,
)
from listentrace.ui.theme import (
    SPACE_COMPACT,
    SPACE_MEDIUM,
    SPACE_NORMAL,
    SPACE_PAGE,
    SPACE_SECTION,
    apply_role,
    apply_surface,
)
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.widgets.notebook_paper import GrainedDeskWidget, RuledTextEdit
from listentrace.ui.widgets.recording_panel import RecordingPanel
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
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

# StageStepper: minimum height for each step QPushButton so the 22px badge,
# label, internal margins, border, and focus ring are never vertically
# clipped (see final Pre-HG2 corrective pass #6).
_STEP_BUTTON_MIN_HEIGHT_PX = 44


class StageStepper(QFrame):
    """Session-local visual stepper indicating the 5 stages of guided intensive practice.

    Each stage step is a QPushButton, giving native keyboard focus, Tab/Shift-Tab
    traversal, Enter/Space activation, and the ability to be disabled (unreached
    future stages are disabled so mouse AND keyboard cannot jump to them).
    """

    stage_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stage_stepper")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_COMPACT)

        self._step_buttons: dict[str, QPushButton] = {}
        self._step_badges: dict[str, QLabel] = {}
        self._step_labels: dict[str, QLabel] = {}

        stage_meta = [
            (StageKey.GLOBAL_COMPREHENSION.value, "1", "1. Global Gist"),
            (StageKey.KEYWORD_CAPTURE.value, "2", "2. Keywords"),
            (StageKey.TRANSCRIPT_DIAGNOSIS.value, "3", "3. Diagnosis"),
            (StageKey.SHADOWING.value, "4", "4. Shadowing"),
            (StageKey.FINAL_SUMMARY.value, "5", "5. Final Recall"),
        ]

        for key, num_str, title in stage_meta:
            # Each stepper item is a QPushButton containing badge + label inside it.
            # Using a QPushButton provides native: keyboard focus, Tab navigation,
            # Enter/Space activation, and setEnabled() for blocking future stages.
            btn = QPushButton()
            btn.setObjectName(f"step_{key}")
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            # A QPushButton with a directly-assigned internal layout does not
            # reliably size-hint tall enough to contain a 22px badge plus its
            # margins/border/focus-ring -- it clipped the badge/label/border
            # on every stage across the reported screenshots. An explicit
            # minimum height makes the row's own height deterministic instead
            # of depending on a QPushButton size-hint quirk.
            btn.setMinimumHeight(_STEP_BUTTON_MIN_HEIGHT_PX)

            inner_layout = QHBoxLayout()
            inner_layout.setContentsMargins(8, 6, 8, 6)
            inner_layout.setSpacing(6)

            apply_role(btn, "stepper_item")

            badge = QLabel(num_str)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(22, 22)
            apply_role(badge, "stepper_item_badge")

            lbl = QLabel(title)
            apply_role(lbl, "stepper_item_label")

            inner_layout.addWidget(badge)
            inner_layout.addWidget(lbl)

            container = QWidget()
            container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            container.setLayout(inner_layout)

            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(container)

            btn.clicked.connect(lambda _checked=False, k=key: self.stage_clicked.emit(k))

            self._step_buttons[key] = btn
            self._step_badges[key] = badge
            self._step_labels[key] = lbl
            self._layout.addWidget(btn, 1)

    def update_stepper(self, current_stage: str, stage_progress: dict[str, Any], read_only: bool) -> None:
        for key, btn in self._step_buttons.items():
            badge = self._step_badges[key]
            label = self._step_labels[key]
            idx_str = str(STAGE_ORDER.index(key) + 1)

            progress = stage_progress.get(key)
            status = progress.status if progress else StageStatus.NOT_STARTED.value

            is_current = key == current_stage
            is_completed = status == StageStatus.COMPLETED.value
            is_skipped = status == StageStatus.SKIPPED.value

            # Navigation safety: disable future unreached stages (NOT_STARTED and
            # not the current stage).  read_only sessions disable all stages.
            is_reachable = is_current or is_completed or is_skipped or (
                status == StageStatus.IN_PROGRESS.value
            )
            btn.setEnabled(not read_only and is_reachable)

            if is_current:
                state, badge_text = "current", idx_str
            elif is_completed:
                state, badge_text = "completed", "✓"
            elif is_skipped:
                state, badge_text = "skipped", "–"
            else:
                state, badge_text = "not_started", idx_str

            theme.apply_variant(btn, state=state)
            theme.apply_variant(badge, state=state)
            theme.apply_variant(label, state=state)
            badge.setText(badge_text)


class GuidedSessionWindow(QMainWindow):
    """M13 Reconstructed Guided Intensive Practice Learning Workspace.

    Target Architecture:
    - Session Context Header + Session-Local Stage Stepper (1–5)
    - Stage 1: Calm Global Gist Paper Card
    - Stage 2: Keyword & Fragment Capture Workspace
    - Stage 3: Two-Column Diagnosis Workspace (Cue Nav Left | Diagnosis Paper Canvas Right)
    - Stage 4: Structured Shadowing Studio (Anchored Cue -> Recording Panel -> Takes -> Comparison)
    - Stage 5: Dominant Ruled Notebook Final Recall Journal & Reference Drawer
    - Bottom Action Grammar with Explainable Completion Checklist
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
        self.resize(1080, 750)
        self.setMinimumSize(880, 600)

        self._playback = PlaybackController(self)
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(connection, self._material.id)
        self._player_session = PlayerSession(self._cues, loop_end_grace_ms=grace_ms)
        self._playback_usable = True
        self._loop_settings_dialog: MaterialLoopSettingsDialog | None = None
        loop_grace_change_bus.global_default_changed.connect(self._on_loop_grace_global_default_changed)
        loop_grace_change_bus.material_override_changed.connect(self._on_loop_grace_material_override_changed)
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

        central = GrainedDeskWidget(self)
        apply_surface(central, "paper")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(SPACE_PAGE, SPACE_PAGE, SPACE_PAGE, SPACE_PAGE)
        layout.setSpacing(SPACE_SECTION)
        apply_surface(self, "paper")

        # -------------------------------------------------------------------
        # 1. Header & Stage Stepper
        # -------------------------------------------------------------------
        header = theme.make_surface_header(self._material.title)
        header_row = header.top_bar
        self._stage_progress_label = QLabel("")
        apply_role(self._stage_progress_label, "caption")
        header.title_row.addWidget(self._stage_progress_label, 1)

        close_top_btn = QPushButton("Exit Session")
        apply_role(close_top_btn, "quiet")
        theme.set_button_icon(close_top_btn, "close", color_token="secondary")
        close_top_btn.clicked.connect(self.close)
        header_row.addWidget(close_top_btn)
        layout.addLayout(header_row)

        self._stage_stepper = StageStepper(self)
        self._stage_stepper.stage_clicked.connect(self._on_stepper_stage_clicked)
        layout.addWidget(self._stage_stepper)

        self._status_label = QLabel("")
        apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # -------------------------------------------------------------------
        # 2. Stage Stack
        # -------------------------------------------------------------------
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_stage1_panel())
        self._stack.addWidget(self._build_stage2_panel())
        self._stack.addWidget(self._build_stage3_panel())
        self._stack.addWidget(self._build_stage4_panel())
        self._stack.addWidget(self._build_stage5_panel())
        layout.addWidget(self._stack, 1)

        # -------------------------------------------------------------------
        # 3. Completion Checklist & Navigation Actions
        # -------------------------------------------------------------------
        self._completion_status_label = QLabel("")
        self._completion_status_label.setWordWrap(True)
        apply_role(self._completion_status_label, "caption")
        layout.addWidget(self._completion_status_label)

        nav_row = QHBoxLayout()
        self._back_button = QPushButton("Back")
        self._back_button.clicked.connect(self._on_back_clicked)
        self._skip_button = QPushButton("Skip Stage")
        self._skip_button.clicked.connect(self._on_skip_stage_clicked)
        self._abandon_button = QPushButton("Abandon Session")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)

        nav_row.addWidget(self._back_button)
        nav_row.addWidget(self._skip_button)
        nav_row.addWidget(self._abandon_button)
        nav_row.addStretch(1)

        self._close_button = QPushButton("Close and Resume Later")
        self._close_button.clicked.connect(self.close)
        self._continue_button = QPushButton("Save and Continue")
        self._continue_button.clicked.connect(self._on_save_and_continue_clicked)
        self._complete_button = QPushButton("Complete Session")
        self._complete_button.clicked.connect(self._on_complete_session_clicked)

        nav_row.addWidget(self._close_button)
        nav_row.addWidget(self._continue_button)
        nav_row.addWidget(self._complete_button)
        layout.addLayout(nav_row)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        self._apply_presentation()

        initial_session = svc.get_session(self._connection, self._session_id)
        self._show_stage(initial_session.current_stage if initial_session is not None else self._current_stage)
        self._initialized = True

    def _apply_presentation(self) -> None:
        """Milestone 11 button-role assignment."""
        apply_role(self._back_button, "quiet")
        theme.set_button_icon(self._back_button, "back", color_token="secondary")
        apply_role(self._skip_button, "quiet")
        # M13 Due-Frame Polish, Axis 1: the due-frame board shows "Save &
        # Continue" as an ordinary paper/no-fill blue-outline action, not
        # the screen's one filled hero commit -- Guided Session has no
        # solid-filled action evidenced anywhere on that board (removed
        # the hero tag that had wrongly promoted this to look filled).
        apply_role(self._continue_button, "primary")
        theme.set_button_icon(self._continue_button, "save", color_token="accent")
        apply_role(self._close_button, "quiet")
        apply_role(self._abandon_button, "danger")
        apply_role(self._complete_button, "success")
        # M13 Due-Frame Polish, Axis 1: `success` has no filled variant --
        # see its QSS rule -- so its icon must match the outline's own
        # green text/border color, not a white on-fill tint.
        theme.set_button_icon(self._complete_button, "motif_star", color_token="success")

    # ---- read-only / status helpers ----

    def _read_only(self) -> bool:
        return self._state is None or self._state.session.status != SessionStatus.ACTIVE.value

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    # ---- navigation ----

    def _on_stepper_stage_clicked(self, stage_key: str) -> None:
        if self._current_stage == stage_key:
            return
        self._show_stage(stage_key)

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
            self._save_current_stage_inputs()

        if stage_key != StageKey.SHADOWING.value:
            self._recording_panel.abort_active_recording()

        if session.status == SessionStatus.ACTIVE.value:
            try:
                svc.enter_stage(self._connection, self._session_id, stage_key)
            except SessionValidationError as exc:
                self._show_status(str(exc))
                return

        # A prior failed attempt may have left a validation error banner on
        # screen; a successful stage transition means it's stale.
        self._show_status("")
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
        self._stage_stepper.update_stepper(self._current_stage, state.stage_progress, self._read_only())

    def _update_progress_label(self, state: PracticeSessionState) -> None:
        index = STAGE_ORDER.index(self._current_stage) + 1
        title = _STAGE_TITLES[self._current_stage]
        status = state.session.status
        suffix = "" if status == SessionStatus.ACTIVE.value else f"  [{status.upper()} — read-only]"
        self._stage_progress_label.setText(f"Stage {index} of 5: {title}{suffix}")

    def _update_nav_buttons(self, state: PracticeSessionState) -> None:
        read_only = state.session.status != SessionStatus.ACTIVE.value
        index = STAGE_ORDER.index(self._current_stage)
        is_last_stage = index == len(STAGE_ORDER) - 1

        self._continue_button.setText("Save Summary" if is_last_stage else "Save and Continue ▶")
        self._back_button.setEnabled(index > 0)
        self._skip_button.setEnabled(not read_only)
        self._continue_button.setEnabled(not read_only)
        self._abandon_button.setEnabled(not read_only)
        statuses = {key: progress.status for key, progress in state.stage_progress.items()}
        self._complete_button.setEnabled(not read_only and rules.session_can_complete(statuses))
        self._update_completion_status_label(state, read_only)

    def _update_completion_status_label(self, state: PracticeSessionState, read_only: bool) -> None:
        if read_only:
            self._completion_status_label.setText("")
            return
        resolved_statuses = (StageStatus.COMPLETED.value, StageStatus.SKIPPED.value)
        unresolved_titles = []
        for stage_key in STAGE_ORDER:
            progress = state.stage_progress.get(stage_key)
            status = progress.status if progress is not None else StageStatus.NOT_STARTED.value
            if status not in resolved_statuses:
                unresolved_titles.append(_STAGE_TITLES[stage_key])
        if unresolved_titles:
            count = len(unresolved_titles)
            names = ", ".join(unresolved_titles)
            self._completion_status_label.setText(f"{count} stage{'s' if count > 1 else ''} remaining: {names}.")
        else:
            self._completion_status_label.setText("All stages resolved — ready to complete.")


    def _save_current_stage_inputs(self) -> None:
        session = svc.get_session(self._connection, self._session_id)
        if session is None or session.status != SessionStatus.ACTIVE.value:
            return
        if self._current_stage == StageKey.GLOBAL_COMPREHENSION.value:
            self._save_stage1_inputs()
        elif self._current_stage == StageKey.SHADOWING.value:
            self._save_shadowing_note()
        elif self._current_stage == StageKey.FINAL_SUMMARY.value:
            self._save_stage5_inputs()

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
        except SessionValidationError as exc:
            # A failed completion attempt must never be silent, and must
            # never advance -- discarding this and continuing anyway let a
            # learner reach Stage 5 with Stages 3/4 never actually resolved
            # (final Pre-HG2 corrective pass #4).
            self._show_status(str(exc))
            self._refresh_state()
            return
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
        if hasattr(self, "_diagnosis_play_button"):
            self._diagnosis_play_button.setText(text)
        if hasattr(self, "_shadowing_play_button"):
            self._shadowing_play_button.setText(text)

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
        if hasattr(self, "_diagnosis_time_label"):
            self._diagnosis_time_label.setText(text)
        if hasattr(self, "_shadowing_time_label"):
            self._shadowing_time_label.setText(text)

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
        self._set_diagnosis_playback_controls_enabled(False)
        self._set_shadowing_playback_controls_enabled(False)
        self._comparison_replay_pending = False
        self._recording_panel.notify_source_failed()

    def _set_diagnosis_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._diagnosis_play_button, self._diagnosis_replay_button, self._diagnosis_loop_button):
            widget.setEnabled(enabled)

    def _set_shadowing_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._shadowing_play_button, self._shadowing_replay_button, self._shadowing_loop_button):
            widget.setEnabled(enabled)

    # ---- Stage 1: Global Comprehension ----

    def _build_stage1_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        apply_surface(scroll, "paper")

        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        header = QLabel(
            "Listen without the transcript. Answer what you can — an empty answer is fine, "
            "but you'll need to explicitly skip this stage if you leave everything blank."
        )
        header.setWordWrap(True)
        apply_role(header, "subtitle")
        layout.addWidget(header)

        self._stage1_lock_hint = QLabel("Read-only: the transcript has been revealed for this session.")
        self._stage1_lock_hint.setVisible(False)
        apply_role(self._stage1_lock_hint, "caption")
        layout.addWidget(self._stage1_lock_hint)

        self._stage1_edits: dict[str, QTextEdit] = {}
        for index, (prompt_key, label_text) in enumerate(_STAGE1_PROMPTS):
            if index > 0:
                # Canonical "unrelated group gap" (DESIGN.md §5.2) between one
                # prompt+answer group and the next, replacing a local
                # margin-top stylesheet hack on the label itself.
                layout.addSpacing(SPACE_MEDIUM)
            prompt_lbl = QLabel(label_text)
            apply_role(prompt_lbl, "form_label")
            layout.addWidget(prompt_lbl)
            edit = QTextEdit()
            edit.setMinimumHeight(60)
            edit.setMaximumHeight(90)
            self._stage1_edits[prompt_key] = edit
            layout.addWidget(edit)

        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

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
        self._stage1_lock_hint.setVisible(locked)

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
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        header = QLabel(
            "Capture any keywords, names, numbers, or fragments you catch — spelling doesn't "
            "need to be exact. At least one capture is required to complete this stage."
        )
        header.setWordWrap(True)
        apply_role(header, "subtitle")
        layout.addWidget(header)

        self._stage2_lock_hint = QLabel("Read-only: the transcript has been revealed for this session.")
        self._stage2_lock_hint.setVisible(False)
        apply_role(self._stage2_lock_hint, "caption")
        layout.addWidget(self._stage2_lock_hint)

        add_row = QHBoxLayout()
        self._capture_type_combo = QComboBox()
        for capture_type in KeywordCaptureType:
            self._capture_type_combo.addItem(capture_type.value.replace("_", " "), capture_type.value)
        self._capture_text_edit = QLineEdit()
        self._capture_text_edit.setPlaceholderText("Enter keyword or fragment...")
        self._capture_add_button = QPushButton("+ Add Capture")
        self._capture_add_button.clicked.connect(self._on_add_capture_clicked)
        apply_role(self._capture_add_button, "secondary")

        add_row.addWidget(self._capture_type_combo)
        add_row.addWidget(self._capture_text_edit, 1)
        add_row.addWidget(self._capture_add_button)
        layout.addLayout(add_row)

        # Capture list + empty-state hint overlay (the hint is shown when the list is empty)
        list_container = QWidget()
        list_container_layout = QVBoxLayout(list_container)
        list_container_layout.setContentsMargins(0, 0, 0, 0)
        list_container_layout.setSpacing(0)

        self._capture_list = QListWidget()
        apply_role(self._capture_list, "ruled_list")
        self._capture_list.currentItemChanged.connect(self._on_capture_selected)
        list_container_layout.addWidget(self._capture_list, 1)

        # Empty state: previously the hint sat underneath a full-height blank
        # list, leaving most of the stage a meaningless empty region instead
        # of the hint owning the space. Now the list is hidden/collapsed
        # while empty and the hint centers itself in the space instead.
        self._capture_empty_hint = QLabel("No captures yet — type a keyword or fragment above and click Add Capture.")
        self._capture_empty_hint.setWordWrap(True)
        self._capture_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(self._capture_empty_hint, "caption")
        self._capture_empty_hint.setVisible(True)
        list_container_layout.addWidget(self._capture_empty_hint, 1)

        layout.addWidget(list_container, 1)

        buttons_row = QHBoxLayout()
        self._capture_update_button = QPushButton("Update Selected")
        self._capture_update_button.clicked.connect(self._on_update_capture_clicked)
        self._capture_update_button.setEnabled(False)
        apply_role(self._capture_update_button, "secondary")

        self._capture_delete_button = QPushButton("Delete Selected")
        self._capture_delete_button.clicked.connect(self._on_delete_capture_clicked)
        self._capture_delete_button.setEnabled(False)
        apply_role(self._capture_delete_button, "danger")
        theme.set_button_icon(self._capture_delete_button, "delete", color_token="danger")

        self._capture_move_up_button = QPushButton("Move Up")
        self._capture_move_up_button.clicked.connect(self._on_move_capture_up_clicked)
        self._capture_move_up_button.setEnabled(False)
        apply_role(self._capture_move_up_button, "quiet")
        theme.set_button_icon(self._capture_move_up_button, "up", color_token="secondary")

        self._capture_move_down_button = QPushButton("Move Down")
        self._capture_move_down_button.clicked.connect(self._on_move_capture_down_clicked)
        self._capture_move_down_button.setEnabled(False)
        apply_role(self._capture_move_down_button, "quiet")
        theme.set_button_icon(self._capture_move_down_button, "down", color_token="secondary")

        buttons_row.addWidget(self._capture_update_button)
        buttons_row.addWidget(self._capture_delete_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self._capture_move_up_button)
        buttons_row.addWidget(self._capture_move_down_button)
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

        # Show empty-state hint only when there are no captures yet; hide/
        # collapse the list so the hint owns the space instead of sitting
        # beneath a large meaningless blank list region.
        has_captures = self._capture_list.count() > 0
        self._capture_empty_hint.setVisible(not has_captures)
        self._capture_list.setVisible(has_captures)
        self._capture_list.setMaximumHeight(16777215 if has_captures else 0)

        locked = state.session.transcript_revealed_at is not None
        enabled = state.session.status == SessionStatus.ACTIVE.value and not locked
        self._stage2_locked = not enabled
        self._stage2_lock_hint.setVisible(locked)
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
        # Two-Region Diagnosis Workspace: Cue Nav Left | Diagnosis Paper Canvas Right
        left_frame, left_column = theme.make_card()
        apply_surface(left_frame, "paper")

        cues_hdr = QLabel("CUES & AUDIO")
        # M13 Due-Frame Polish, Axis 3: the due-frame board renders every
        # Stage 3 panel header (this one, "Transcript & Diagnosis
        # Notebook") in blue-ink section-header style, not plain caption.
        apply_role(cues_hdr, "section_header")
        left_column.addWidget(cues_hdr)

        self._diagnosis_cue_list = QListWidget()
        apply_role(self._diagnosis_cue_list, "ruled_list")
        self._diagnosis_cue_list.setWordWrap(True)
        self._diagnosis_cue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._diagnosis_cue_list.currentItemChanged.connect(self._on_diagnosis_cue_selected)
        left_column.addWidget(self._diagnosis_cue_list, 1)

        transport_card, transport_layout = theme.make_card()
        apply_surface(transport_card, "paper")

        t_row = QHBoxLayout()
        self._diagnosis_play_button = QPushButton("Play")
        self._diagnosis_play_button.clicked.connect(self._on_diagnosis_play_clicked)
        apply_role(self._diagnosis_play_button, "secondary")

        self._diagnosis_replay_button = QPushButton("Replay Cue")
        self._diagnosis_replay_button.clicked.connect(self._on_diagnosis_replay_clicked)
        apply_role(self._diagnosis_replay_button, "secondary")

        self._diagnosis_loop_button = QPushButton("Loop Cue")
        self._diagnosis_loop_button.clicked.connect(self._on_diagnosis_loop_clicked)
        apply_role(self._diagnosis_loop_button, "secondary")

        t_row.addWidget(self._diagnosis_play_button)
        t_row.addWidget(self._diagnosis_replay_button)
        t_row.addWidget(self._diagnosis_loop_button)
        transport_layout.addLayout(t_row)

        t_util_row = QHBoxLayout()
        self._diagnosis_loop_settings_button = QPushButton("Loop Settings...")
        self._diagnosis_loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._diagnosis_loop_settings_button, "quiet")

        self._diagnosis_time_label = QLabel("00:00 / 00:00")
        apply_role(self._diagnosis_time_label, "monospace")

        t_util_row.addWidget(self._diagnosis_loop_settings_button)
        t_util_row.addStretch(1)
        t_util_row.addWidget(self._diagnosis_time_label)
        transport_layout.addLayout(t_util_row)

        left_column.addWidget(transport_card)

        right_frame, right_column = theme.make_card()
        apply_surface(right_frame, "paper")

        diag_hdr = QLabel("TRANSCRIPT & ERROR DIAGNOSIS (select text to diagnose):")
        apply_role(diag_hdr, "section_header")
        right_column.addWidget(diag_hdr)

        self._diagnosis_transcript_view = QTextEdit()
        self._diagnosis_transcript_view.setReadOnly(True)
        self._diagnosis_transcript_view.setMinimumHeight(75)
        self._diagnosis_transcript_view.setMaximumHeight(110)
        right_column.addWidget(self._diagnosis_transcript_view)

        # A single QHBoxLayout row can't hold all five label names (the
        # longest, "connected reduced speech", forces the others to squish
        # or truncate at this splitter pane's width) -- a fixed-column grid
        # keeps every label fully readable regardless of window/pane width.
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
        right_column.addLayout(label_grid)

        heard_as_row = QHBoxLayout()
        heard_lbl = QLabel("Heard as:")
        apply_role(heard_lbl, "caption")
        heard_as_row.addWidget(heard_lbl)
        self._diagnosis_heard_as_edit = QLineEdit()
        self._diagnosis_heard_as_edit.setEnabled(False)
        heard_as_row.addWidget(self._diagnosis_heard_as_edit)
        right_column.addLayout(heard_as_row)

        note_row = QHBoxLayout()
        note_lbl = QLabel("Note:")
        apply_role(note_lbl, "caption")
        note_row.addWidget(note_lbl)
        self._diagnosis_note_edit = QLineEdit()
        note_row.addWidget(self._diagnosis_note_edit)
        right_column.addLayout(note_row)

        diag_buttons_row = QHBoxLayout()
        self._save_diagnosis_button = QPushButton("Save Diagnosis")
        self._save_diagnosis_button.clicked.connect(self._on_save_diagnosis_clicked)
        apply_role(self._save_diagnosis_button, "secondary")
        theme.set_button_icon(self._save_diagnosis_button, "save", color_token="secondary")

        self._delete_diagnosis_button = QPushButton("Delete")
        self._delete_diagnosis_button.clicked.connect(self._on_delete_diagnosis_clicked)
        self._delete_diagnosis_button.setEnabled(False)
        apply_role(self._delete_diagnosis_button, "danger")
        theme.set_button_icon(self._delete_diagnosis_button, "delete", color_token="danger")

        self._no_difficulty_button = QPushButton("No Notable Difficulty")
        self._no_difficulty_button.clicked.connect(self._on_no_difficulty_clicked)
        apply_role(self._no_difficulty_button, "secondary")
        theme.set_button_icon(self._no_difficulty_button, "check", color_token="secondary")

        diag_buttons_row.addWidget(self._save_diagnosis_button)
        diag_buttons_row.addWidget(self._delete_diagnosis_button)
        diag_buttons_row.addWidget(self._no_difficulty_button)
        right_column.addLayout(diag_buttons_row)

        diag_evidence_lbl = QLabel("Session diagnosis on this cue:")
        apply_role(diag_evidence_lbl, "caption")
        right_column.addWidget(diag_evidence_lbl)
        self._diagnosis_list = QListWidget()
        apply_role(self._diagnosis_list, "ruled_list")
        self._diagnosis_list.setMaximumHeight(85)
        self._diagnosis_list.currentItemChanged.connect(self._on_diagnosis_selected)
        right_column.addWidget(self._diagnosis_list)

        ref_lbl = QLabel("Existing material annotations (reference):")
        apply_role(ref_lbl, "caption")
        right_column.addWidget(ref_lbl)
        self._diagnosis_reference_list = QListWidget()
        apply_role(self._diagnosis_reference_list, "ruled_list")
        self._diagnosis_reference_list.setMaximumHeight(65)
        right_column.addWidget(self._diagnosis_reference_list)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_frame)
        splitter.addWidget(right_frame)
        splitter.setSizes([380, 560])
        return splitter

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
            list_item.setIcon(_color_badge_icon(colors.get(item_evidence.label_key, UNKNOWN_LABEL_COLOR)))
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        apply_surface(scroll, "paper")

        panel = QWidget()
        apply_surface(panel, "paper")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(SPACE_COMPACT, SPACE_COMPACT, SPACE_COMPACT, SPACE_COMPACT)
        layout.setSpacing(SPACE_NORMAL)

        # 1. Source Cue Card
        cue_card, cue_layout = theme.make_card()
        apply_surface(cue_card, "paper")

        cue_header_row = QHBoxLayout()
        prompt_lbl = QLabel("Shadow each cue: listen, then repeat aloud.")
        apply_role(prompt_lbl, "subtitle")
        cue_header_row.addWidget(prompt_lbl)
        cue_header_row.addStretch(1)

        self._shadowing_progress_label = QLabel("")
        apply_role(self._shadowing_progress_label, "caption")
        cue_header_row.addWidget(self._shadowing_progress_label)
        cue_layout.addLayout(cue_header_row)

        self._shadowing_cue_label = QLabel("")
        self._shadowing_cue_label.setWordWrap(True)
        apply_role(self._shadowing_cue_label, "dominant_cue")
        cue_layout.addWidget(self._shadowing_cue_label)

        transport_row = QHBoxLayout()
        self._shadowing_previous_button = QPushButton("Previous Cue")
        self._shadowing_previous_button.clicked.connect(self._on_shadowing_previous_clicked)
        apply_role(self._shadowing_previous_button, "secondary")
        theme.set_button_icon(self._shadowing_previous_button, "back", color_token="secondary")

        self._shadowing_play_button = QPushButton("Play")
        self._shadowing_play_button.clicked.connect(self._on_shadowing_play_clicked)
        apply_role(self._shadowing_play_button, "secondary")

        self._shadowing_replay_button = QPushButton("Replay Cue")
        self._shadowing_replay_button.clicked.connect(self._on_shadowing_replay_clicked)
        apply_role(self._shadowing_replay_button, "secondary")

        self._shadowing_loop_button = QPushButton("Loop Cue")
        self._shadowing_loop_button.clicked.connect(self._on_shadowing_loop_clicked)
        apply_role(self._shadowing_loop_button, "secondary")

        self._shadowing_next_button = QPushButton("Next Cue")
        self._shadowing_next_button.clicked.connect(self._on_shadowing_next_clicked)
        apply_role(self._shadowing_next_button, "secondary")
        theme.set_button_icon(self._shadowing_next_button, "forward", color_token="secondary")

        self._shadowing_loop_settings_button = QPushButton("Loop Settings...")
        self._shadowing_loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._shadowing_loop_settings_button, "quiet")

        self._shadowing_time_label = QLabel("00:00 / 00:00")
        apply_role(self._shadowing_time_label, "monospace")

        transport_row.addWidget(self._shadowing_previous_button)
        transport_row.addWidget(self._shadowing_play_button)
        transport_row.addWidget(self._shadowing_replay_button)
        transport_row.addWidget(self._shadowing_loop_button)
        transport_row.addWidget(self._shadowing_next_button)
        transport_row.addWidget(self._shadowing_loop_settings_button)
        transport_row.addStretch(1)
        transport_row.addWidget(self._shadowing_time_label)
        cue_layout.addLayout(transport_row)
        layout.addWidget(cue_card)

        # 2. Integrated Recording Studio
        layout.addWidget(self._recording_panel)

        # 3. Actions & Notes Card
        action_card, action_layout = theme.make_card()
        apply_surface(action_card, "paper")

        self._shadowing_note_edit = QLineEdit()
        self._shadowing_note_edit.setPlaceholderText("Optional reflection note for this cue...")
        action_layout.addWidget(self._shadowing_note_edit)

        action_row = QHBoxLayout()
        self._mark_practiced_button = QPushButton("Mark Practiced")
        self._mark_practiced_button.clicked.connect(self._on_mark_practiced_clicked)
        apply_role(self._mark_practiced_button, "secondary")
        theme.set_button_icon(self._mark_practiced_button, "check", color_token="secondary")

        self._skip_cue_button = QPushButton("Skip Cue")
        self._skip_cue_button.clicked.connect(self._on_skip_shadowing_cue_clicked)
        apply_role(self._skip_cue_button, "quiet")

        self._skip_remaining_button = QPushButton("Skip Remaining Cues")
        self._skip_remaining_button.clicked.connect(self._on_skip_remaining_shadowing_clicked)
        apply_role(self._skip_remaining_button, "quiet")

        action_row.addWidget(self._mark_practiced_button)
        action_row.addWidget(self._skip_cue_button)
        action_row.addWidget(self._skip_remaining_button)
        action_row.addStretch(1)
        action_layout.addLayout(action_row)

        layout.addWidget(action_card)
        layout.addStretch(1)

        scroll.setWidget(panel)
        return scroll

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
        raw_status = progress.status if progress else ShadowingStatus.NOT_STARTED.value
        status_text = raw_status.replace("_", " ").upper()
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
        panel, layout = theme.make_notebook_surface(
            "Stage 5: Final Recall Journal",
            context_label=None,  # The spiral bar shows no "Study Dossier" stamp here
        )
        desc_label = QLabel("Transcript hidden. Summarize the material in two or three sentences in the target language.")
        desc_label.setWordWrap(True)
        apply_role(desc_label, "subtitle")
        layout.addWidget(desc_label)

        self._final_summary_edit = RuledTextEdit()
        self._final_summary_edit.setMinimumHeight(150)
        self._final_summary_edit.setMaximumHeight(240)
        layout.addWidget(self._final_summary_edit, 1)

        ref_title = QLabel("Your Stage 1/2 evidence (for reference — no transcript text shown):")
        apply_role(ref_title, "caption")
        layout.addWidget(ref_title)

        self._stage5_reference_view = QTextEdit()
        self._stage5_reference_view.setReadOnly(True)
        self._stage5_reference_view.setMaximumHeight(100)
        layout.addWidget(self._stage5_reference_view)
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

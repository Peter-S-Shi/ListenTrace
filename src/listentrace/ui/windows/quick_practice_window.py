from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
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
    QSplitter,
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
from listentrace.ui.theme import (
    SPACE_COMPACT,
    SPACE_NORMAL,
    SPACE_PAGE,
    SPACE_SECTION,
    FlowLayout,
    apply_role,
    apply_surface,
    apply_variant,
)
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.widgets.recording_panel import RecordingPanel
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
from listentrace.ui.windows.player_window import _OVERLAP_HIGHLIGHT, _format_time

_STEP_LISTEN_RECALL = 0
_STEP_DIAGNOSE = 1
_STEP_REPLAY = 2
_STEP_SUMMARY = 3

_RECALL_LABELS: list[tuple[str, str]] = [
    (RecallResult.UNDERSTOOD.value, "Understood"),
    (RecallResult.PARTLY_UNDERSTOOD.value, "Partly Understood"),
    (RecallResult.MISSED.value, "Missed"),
]

# M13 Axis 8: the real, existing 4-step micro-cycle -- names used by the
# persistent stepper only. No new step is invented; this mirrors
# `_STEP_*` exactly.
_STEPPER_LABELS: list[tuple[int, str]] = [
    (_STEP_LISTEN_RECALL, "Listen / Recall"),
    (_STEP_DIAGNOSE, "Diagnose"),
    (_STEP_REPLAY, "Replay / Shadow"),
    (_STEP_SUMMARY, "Summary"),
]

# Right support column pages -- fewer pages than steps, since Diagnose and
# Replay/Shadow deliberately share one "diagnosis evidence" reference page
# (the same real data stays visible and unduplicated across both steps).
_SUPPORT_PAGE_PRE_REVEAL = 0
_SUPPORT_PAGE_DIAGNOSIS_EVIDENCE = 1
_SUPPORT_PAGE_SUMMARY = 2


class QuickPracticeStepper(QFrame):
    """A non-interactive 4-step visual progress indicator (M13 Axis 8).

    Visually mirrors Guided Session's `StageStepper` pill/badge/label
    grammar (same `stepper_item_badge`/`stepper_item_label` `QLabel`
    roles, same current/completed/not_started color language) but is
    deliberately built from plain `QFrame` pills (`role=
    "stepper_item_static"`), not `QPushButton`s -- Quick Practice's
    real product behavior is strictly forward-only with no arbitrary
    stage jump, so this stepper has no click target, no focus ring, and
    emits no signal. `update_stepper()` is the single state-refresh seam;
    its `current_step` argument must always come from the window's real
    `_step`.
    """

    _PILL_MIN_HEIGHT_PX = 40

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE_COMPACT)

        self._pills: dict[int, QFrame] = {}
        self._badges: dict[int, QLabel] = {}
        self._labels: dict[int, QLabel] = {}

        for step, title in _STEPPER_LABELS:
            pill = QFrame()
            pill.setMinimumHeight(self._PILL_MIN_HEIGHT_PX)
            apply_role(pill, "stepper_item_static")
            inner = QHBoxLayout(pill)
            inner.setContentsMargins(8, 6, 8, 6)
            inner.setSpacing(6)

            badge = QLabel(str(step + 1))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(22, 22)
            apply_role(badge, "stepper_item_badge")

            label = QLabel(title)
            apply_role(label, "stepper_item_label")

            inner.addWidget(badge)
            inner.addWidget(label)

            self._pills[step] = pill
            self._badges[step] = badge
            self._labels[step] = label
            row.addWidget(pill, 1)

    def update_stepper(self, current_step: int) -> None:
        for step, pill in self._pills.items():
            badge = self._badges[step]
            label = self._labels[step]
            if step < current_step:
                state, badge_text = "completed", "✓"
            elif step == current_step:
                state, badge_text = "current", str(step + 1)
            else:
                state, badge_text = "not_started", str(step + 1)
            apply_variant(pill, state=state)
            apply_variant(badge, state=state)
            apply_variant(label, state=state)
            badge.setText(badge_text)


class QuickPracticeWindow(QMainWindow):
    """M13 Axis 8 Reconstructed Quick Practice Workspace.

    One stable left-two/right-one notebook workspace whose internal
    content changes by step, instead of four separate centered form
    cards:
    - Header + persistent 4-step stepper (Listen/Recall, Diagnose,
      Replay/Shadow, Summary)
    - Left-top: persistent cue/listening context (cue count, transport,
      transcript once revealed)
    - Left-bottom: the active step's processing/work area
    - Right: labels/diagnosis/evidence support, stable across steps
    - Footer: primary progression action

    The underlying compact, forward-only cue practice state machine
    (`_STEP_LISTEN_RECALL` -> `_STEP_DIAGNOSE` -> `_STEP_REPLAY` ->
    `_STEP_SUMMARY`) is unchanged from the pre-Axis-8 implementation --
    this Axis changes composition and presentation only.
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
        self.resize(1040, 720)
        self.setMinimumSize(880, 600)

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
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(SPACE_PAGE, SPACE_PAGE, SPACE_PAGE, SPACE_PAGE)
        root_layout.setSpacing(SPACE_SECTION)
        apply_surface(self, "paper")

        # -------------------------------------------------------------------
        # 1. Header
        # -------------------------------------------------------------------
        header = theme.make_surface_header(self._material.title)
        header_row = header.top_bar
        header.title_row.addStretch(1)

        close_top_btn = QPushButton("Exit")
        apply_role(close_top_btn, "quiet")
        theme.set_button_icon(close_top_btn, "close", color_token="secondary")
        close_top_btn.clicked.connect(self.close)
        header_row.addWidget(close_top_btn)
        root_layout.addLayout(header_row)

        self._status_label = QLabel("")
        apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        root_layout.addWidget(self._status_label)

        # -------------------------------------------------------------------
        # 2. Persistent 4-step progress stepper -- a distinct dimension from
        #    cue progress ("Cue n of N"), never collapsed into one label.
        # -------------------------------------------------------------------
        self._stepper = QuickPracticeStepper(self)
        root_layout.addWidget(self._stepper)

        self._progress_label = QLabel("")
        apply_role(self._progress_label, "caption")
        root_layout.addWidget(self._progress_label)

        # -------------------------------------------------------------------
        # 3. Stable Left-two / Right-one Workspace
        # -------------------------------------------------------------------
        self._workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._workspace_splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SPACE_SECTION)

        self._cue_context_card = self._build_cue_context_card()
        left_layout.addWidget(self._cue_context_card)

        self._work_stack = QStackedWidget()
        self._work_stack.addWidget(self._build_listen_recall_work())
        self._work_stack.addWidget(self._build_diagnose_work())
        self._work_stack.addWidget(self._build_replay_work())
        self._work_stack.addWidget(self._build_summary_work())
        left_layout.addWidget(self._work_stack, 1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(left_widget)
        self._workspace_splitter.addWidget(left_scroll)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACE_SECTION)

        self._support_stack = QStackedWidget()
        self._support_stack.addWidget(self._build_pre_reveal_support())
        self._support_stack.addWidget(self._build_diagnosis_evidence_support())
        self._support_stack.addWidget(self._build_summary_support())
        right_layout.addWidget(self._support_stack, 1)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right_widget)
        self._workspace_splitter.addWidget(right_scroll)

        # Left-two / Right-one, per the frozen Axis-8 composition. An
        # explicit initial `setSizes()` (not stretch factors alone) is
        # required here -- without it, right-column QLabels with word wrap
        # compute their wrapped height against a not-yet-settled splitter
        # width on the very first layout pass and clip a line of text.
        self._workspace_splitter.setStretchFactor(0, 2)
        self._workspace_splitter.setStretchFactor(1, 1)
        self._workspace_splitter.setSizes([680, 340])
        root_layout.addWidget(self._workspace_splitter, 1)

        # -------------------------------------------------------------------
        # 4. Persistent Action Footer
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
        root_layout.addLayout(nav_row)

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

    def _support_page_for_step(self, step: int) -> int:
        if step == _STEP_LISTEN_RECALL:
            return _SUPPORT_PAGE_PRE_REVEAL
        if step in (_STEP_DIAGNOSE, _STEP_REPLAY):
            return _SUPPORT_PAGE_DIAGNOSIS_EVIDENCE
        return _SUPPORT_PAGE_SUMMARY

    def _render_current_step(self) -> None:
        if self._state is None:
            return
        total = len(self._state.items)
        self._stepper.update_stepper(self._step)
        if self._step == _STEP_SUMMARY:
            self._progress_label.setText(f"Quick Practice — {self._state.session.status.upper()}")
        else:
            self._progress_label.setText(f"Cue {self._index + 1} of {total}")
        self._work_stack.setCurrentIndex(self._step)
        self._support_stack.setCurrentIndex(self._support_page_for_step(self._step))
        self._populate_cue_context()
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

    # ---- Left-top: persistent cue / listening context ----

    def _build_cue_context_card(self) -> QWidget:
        """The left-top persistent region (A8-03): cue identity, listening
        controls, and the transcript once revealed. One shared transport
        row (not per-step duplicates) -- `_listen_*`/`_replay_*` attribute
        names below are preserved aliases onto these same buttons, kept
        only because they're still the names the pre-Axis-8 test suite and
        `_sync_playback_button_texts`/`_set_playback_controls_enabled`
        already key off of.
        """
        card, layout = theme.make_card()
        apply_surface(card, "paper")

        transport_row = QHBoxLayout()
        self._transport_play_button = QPushButton("Play")
        self._transport_play_button.clicked.connect(self._on_play_clicked)
        apply_role(self._transport_play_button, "secondary")

        self._transport_replay_button = QPushButton("Replay Cue")
        self._transport_replay_button.clicked.connect(self._on_replay_clicked)
        apply_role(self._transport_replay_button, "secondary")

        self._transport_loop_button = QPushButton("Loop Cue")
        self._transport_loop_button.clicked.connect(self._on_loop_clicked)
        apply_role(self._transport_loop_button, "secondary")

        self._transport_loop_settings_button = QPushButton("Loop Settings...")
        self._transport_loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._transport_loop_settings_button, "quiet")

        self._transport_time_label = QLabel("00:00 / 00:00")
        apply_role(self._transport_time_label, "monospace")

        # Preserved aliases (see docstring above) -- same widgets, both names.
        self._listen_play_button = self._transport_play_button
        self._listen_replay_button = self._transport_replay_button
        self._listen_loop_button = self._transport_loop_button
        self._listen_loop_settings_button = self._transport_loop_settings_button
        self._listen_time_label = self._transport_time_label
        self._replay_play_button = self._transport_play_button
        self._replay_replay_button = self._transport_replay_button
        self._replay_loop_button = self._transport_loop_button
        self._replay_loop_settings_button = self._transport_loop_settings_button
        self._replay_time_label = self._transport_time_label

        for button in (
            self._transport_play_button,
            self._transport_replay_button,
            self._transport_loop_button,
            self._transport_loop_settings_button,
        ):
            transport_row.addWidget(button)
        transport_row.addStretch(1)
        transport_row.addWidget(self._transport_time_label)
        layout.addLayout(transport_row)

        # Transcript reference -- hidden pre-reveal (Step 1's "listen
        # without transcript" design intent), shown from Step 2 onward.
        # A8-03/A8-06: the single shared reference area for Diagnose AND
        # Replay/Shadow, so shadowing the cue never needs a second,
        # duplicated cue-text label the way the pre-Axis-8 Step 3 card had.
        self._diagnosis_transcript_view = QTextEdit()
        self._diagnosis_transcript_view.setReadOnly(True)
        self._diagnosis_transcript_view.setMinimumHeight(70)
        self._diagnosis_transcript_view.setMaximumHeight(110)
        layout.addWidget(self._diagnosis_transcript_view)

        return card

    def _populate_cue_context(self) -> None:
        cue = self._current_cue()
        # M13 Final Human-Gate Corrective (HG-07): Summary has no
        # meaningful transport/transcript content left to show (the run
        # is over), so the whole card collapses rather than surviving as
        # an empty framed paper strip with nothing visible inside it.
        self._cue_context_card.setVisible(self._step != _STEP_SUMMARY)
        transcript_visible = self._step in (_STEP_DIAGNOSE, _STEP_REPLAY)
        self._diagnosis_transcript_view.setVisible(transcript_visible)
        transport_visible = self._step != _STEP_SUMMARY
        for widget in (
            self._transport_play_button,
            self._transport_replay_button,
            self._transport_loop_button,
            self._transport_loop_settings_button,
            self._transport_time_label,
        ):
            widget.setVisible(transport_visible)

        if transcript_visible and cue is not None:
            item_state = self._current_item_state()
            self._diagnosis_transcript_view.setPlainText(cue.text)
            if item_state is not None:
                self._current_diagnosis_evidence = item_state.diagnosis
                colors = label_preference_service.get_label_preferences(self._connection)
                apply_range_highlighting(
                    self._diagnosis_transcript_view, cue.text, item_state.diagnosis, colors, _OVERLAP_HIGHLIGHT
                )
        elif not transcript_visible:
            self._diagnosis_transcript_view.clear()

        self._set_playback_controls_enabled(transport_visible and cue is not None and self._playback_usable)

    # ---- Right support column ----

    def _build_pre_reveal_support(self) -> QWidget:
        """A restrained, intentional empty state (A8-03) -- Step 1
        genuinely has no diagnosis/evidence data yet (the transcript
        hasn't even been revealed), so this deliberately stays calm
        rather than inventing content to fill the column."""
        panel, layout = theme.make_card("Evidence & Diagnosis")
        apply_surface(panel, "paper")
        hint = QLabel("Diagnosis and evidence will appear here once you reveal the transcript.")
        hint.setWordWrap(True)
        apply_role(hint, "caption")
        layout.addWidget(hint)
        layout.addStretch(1)
        return panel

    def _build_diagnosis_evidence_support(self) -> QWidget:
        """Shared by Diagnose and Replay/Shadow (A8-06 continuity) -- the
        same real evidence stays visible and unduplicated across both
        steps rather than being rebuilt or shown only once."""
        panel, layout = theme.make_card("Evidence & Diagnosis")
        apply_surface(panel, "paper")

        self._heard_fragment_reference_label = QLabel("")
        self._heard_fragment_reference_label.setWordWrap(True)
        apply_role(self._heard_fragment_reference_label, "ui_label")
        layout.addWidget(self._heard_fragment_reference_label)

        diag_hdr = QLabel("Diagnosis recorded on this cue during this run:")
        diag_hdr.setWordWrap(True)
        apply_role(diag_hdr, "ui_label")
        layout.addWidget(diag_hdr)

        self._diagnosis_list = QListWidget()
        apply_role(self._diagnosis_list, "ruled_list")
        theme.configure_long_text_list(self._diagnosis_list)
        self._diagnosis_list.currentItemChanged.connect(self._on_diagnosis_selected)
        layout.addWidget(self._diagnosis_list, 1)

        return panel

    def _build_summary_support(self) -> QWidget:
        panel, layout = theme.make_card("Run Status")
        apply_surface(panel, "paper")
        self._summary_status_label = QLabel("")
        apply_role(self._summary_status_label, "subtitle")
        self._summary_status_label.setWordWrap(True)
        layout.addWidget(self._summary_status_label)
        layout.addStretch(1)
        return panel

    # ---- Step 1: Listen & Recall (left-bottom work) ----

    def _build_listen_recall_work(self) -> QWidget:
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        inst_lbl = QLabel("Step 1: Listen without transcript, then choose your comprehension level.")
        apply_role(inst_lbl, "subtitle")
        layout.addWidget(inst_lbl)

        # M13 Axis 8 corrective (A8-05): two DISTINCT neutral notebook/note
        # surfaces for the learner's two separate processing tasks, not one
        # notebook holding both -- each a hand-sized `make_mini_notebook()`
        # page ("a hand-sized spiral notebook page for one control group"),
        # not a diagnosis-colored or generic form card. `DiagnosisNoteRow`
        # is deliberately NOT reused here -- that primitive carries
        # diagnosis/evidence semantics neither of these notes has.
        assessment_notebook, assessment_layout = theme.make_mini_notebook("Self-Assessment")

        recall_hdr = QLabel("Comprehension Self-Assessment:")
        apply_role(recall_hdr, "ui_label")
        assessment_layout.addWidget(recall_hdr)

        recall_row = QHBoxLayout()
        self._recall_group = QButtonGroup(self)
        self._recall_radio_buttons: dict[str, QRadioButton] = {}
        for value, label_text in _RECALL_LABELS:
            radio = QRadioButton(label_text)
            apply_role(radio, "ui_label")
            radio.toggled.connect(self._on_recall_choice_changed)
            self._recall_group.addButton(radio)
            self._recall_radio_buttons[value] = radio
            recall_row.addWidget(radio)
        assessment_layout.addLayout(recall_row)

        caught_words_notebook, caught_words_layout = theme.make_mini_notebook("Caught Words / Phrases")

        frag_hdr = QLabel("What words/phrases did you catch? (optional)")
        apply_role(frag_hdr, "ui_label")
        caught_words_layout.addWidget(frag_hdr)

        self._heard_fragment_edit = QLineEdit()
        self._heard_fragment_edit.setPlaceholderText("Enter words or sounds you caught...")
        caught_words_layout.addWidget(self._heard_fragment_edit)

        layout.addWidget(assessment_notebook)
        layout.addWidget(caught_words_notebook)
        layout.addStretch(1)
        return panel

    def _populate_listen_recall(self) -> None:
        for radio in self._recall_radio_buttons.values():
            radio.blockSignals(True)
            radio.setChecked(False)
            radio.blockSignals(False)
        self._heard_fragment_edit.clear()
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

    # ---- Step 2: Reveal & Diagnose (left-bottom work) ----

    def _build_diagnose_work(self) -> QWidget:
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        inst_lbl = QLabel("Step 2: Transcript revealed — compare and diagnose difficulty if useful.")
        apply_role(inst_lbl, "subtitle")
        layout.addWidget(inst_lbl)

        # M13 Axis 7: a wrapping FlowLayout, not the old rigid fixed-column
        # grid -- see guided_session_window.py's identical corrective for
        # the shared rationale.
        label_grid_widget = QWidget()
        label_grid = FlowLayout(label_grid_widget, h_spacing=SPACE_SECTION, v_spacing=SPACE_NORMAL)
        self._diagnosis_label_checkboxes: dict[str, QCheckBox] = {}
        for label in AnnotationLabel:
            checkbox = QCheckBox(label.value.replace("_", " "))
            apply_role(checkbox, "ui_label")
            checkbox.stateChanged.connect(self._on_diagnosis_label_checkbox_changed)
            self._diagnosis_label_checkboxes[label.value] = checkbox
            label_grid.addWidget(checkbox)
        layout.addWidget(label_grid_widget)

        heard_as_row = QHBoxLayout()
        heard_lbl = QLabel("Heard as:")
        apply_role(heard_lbl, "ui_label")
        heard_as_row.addWidget(heard_lbl)
        self._diagnosis_heard_as_edit = QLineEdit()
        self._diagnosis_heard_as_edit.setEnabled(False)
        heard_as_row.addWidget(self._diagnosis_heard_as_edit)
        layout.addLayout(heard_as_row)

        note_row = QHBoxLayout()
        note_lbl = QLabel("Note:")
        apply_role(note_lbl, "ui_label")
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

        layout.addStretch(1)
        return panel

    def _populate_diagnose(self) -> None:
        cue = self._current_cue()
        item_state = self._current_item_state()
        if cue is None or item_state is None:
            return
        fragment = item_state.item.heard_fragment
        self._heard_fragment_reference_label.setText(
            f"What you said you heard: {fragment}" if fragment else "You did not enter a heard fragment."
        )

        self._current_diagnosis_evidence = item_state.diagnosis
        self._refresh_diagnosis_evidence_list(item_state.diagnosis)
        self._clear_diagnosis_form()
        self._step_action_button.setText("Continue to Shadowing")
        self._step_action_button.setEnabled(True)

    def _refresh_diagnosis_evidence_list(self, diagnosis: list) -> None:
        colors = label_preference_service.get_label_preferences(self._connection)
        self._diagnosis_list.blockSignals(True)
        self._diagnosis_list.clear()
        for diag in diagnosis:
            heard_as_suffix = f" (heard as: {diag.heard_as})" if diag.heard_as else ""
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, diag.id)
            self._diagnosis_list.addItem(item)
            row = theme.DiagnosisNoteRow(
                f"[{diag.label_key}] {diag.selected_text}{heard_as_suffix}",
                colors.get(diag.label_key, UNKNOWN_LABEL_COLOR),
            )
            item.setSizeHint(theme.ruled_list_row_size_hint(row))
            self._diagnosis_list.setItemWidget(item, row)
        self._diagnosis_list.blockSignals(False)
        theme.ruled_list_ensure_visible_rows(self._diagnosis_list, visible_rows=1)

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

    # ---- Step 3: Replay & Shadow (left-bottom work) ----

    def _build_replay_work(self) -> QWidget:
        """M13 Axis 8 (A8-06): `RecordingPanel` hosted directly in the
        left-bottom processing region -- the real, evidenced structural
        overflow root cause (Axis 7's finding) was Quick Practice's old
        ~600px centered card, not `RecordingPanel` itself (which already
        renders with zero overflow in the full-width standalone Shadowing
        Practice window). Removing that narrow host, not patching
        `RecordingPanel`, is what eliminates the overflow."""
        panel = QWidget()
        apply_surface(panel, "paper")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_NORMAL)

        inst_lbl = QLabel("Step 3: Replay the cue and shadow aloud.")
        apply_role(inst_lbl, "subtitle")
        layout.addWidget(inst_lbl)

        layout.addWidget(self._recording_panel)

        action_card, action_layout = theme.make_card()
        apply_surface(action_card, "paper")
        self._mark_shadowed_button = QPushButton("Mark Shadowed (Optional)")
        self._mark_shadowed_button.clicked.connect(self._on_mark_shadowed_clicked)
        apply_role(self._mark_shadowed_button, "secondary")
        theme.set_button_icon(self._mark_shadowed_button, "check", color_token="secondary")
        action_layout.addWidget(self._mark_shadowed_button)
        layout.addWidget(action_card)

        layout.addStretch(1)
        return panel

    def _populate_replay(self) -> None:
        cue = self._current_cue()
        item_state = self._current_item_state()
        if cue is None or item_state is None:
            return
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

    # ---- Step 4: Summary (left-bottom work + right status) ----

    def _build_summary_work(self) -> QWidget:
        """M13 Axis 8 (A8-07): the completion state as a written-up study
        note rather than a mostly-empty generic card -- `_summary_label`
        (same widget name/content contract as before this Axis) now lives
        inside a ruled-notebook mini-notebook body instead of a plain flat
        card, and gains a prominent headline metric above it."""
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        self._summary_headline_label = QLabel("")
        apply_role(self._summary_headline_label, "dominant_cue")
        layout.addWidget(self._summary_headline_label)

        summary_notebook, summary_body = theme.make_mini_notebook("Run Summary")
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        apply_role(self._summary_label, "body")
        summary_body.addWidget(self._summary_label)
        summary_body.addStretch(1)
        layout.addWidget(summary_notebook, 1)

        return panel

    def _populate_summary(self) -> None:
        if self._state is None:
            return
        status = self._state.session.status
        if status != QuickPracticeStatus.COMPLETED.value:
            self._summary_headline_label.setText("")
            self._summary_label.setText(f"This Quick Practice run is {status}.")
            self._summary_status_label.setText(f"Status: {status}.")
            self._step_action_button.setEnabled(False)
            return
        summary = svc.build_completion_summary(self._connection, self._session_id)
        self._summary_headline_label.setText(f"Cues completed: {summary.cues_completed}")
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
        self._summary_status_label.setText("Status: completed.")
        self._step_action_button.setText("Done")
        self._step_action_button.setEnabled(True)
        try:
            self._step_action_button.clicked.disconnect()
        except Exception:
            pass
        self._step_action_button.clicked.connect(self.close)
        self._close_button.setEnabled(False)

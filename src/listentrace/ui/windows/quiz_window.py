from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import PlayerTick
from listentrace.application.dto.quiz_state import QuizState
from listentrace.application.errors import QuizQuestionNotFoundError, QuizValidationError
from listentrace.application.services import loop_grace_service
from listentrace.application.services import quiz_service as svc
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.answered_state import AnsweredState
from listentrace.domain.enums.question_type import QuestionType
from listentrace.domain.enums.quiz_status import QuizStatus
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.widgets.notebook_paper import GrainedDeskWidget
from listentrace.ui.theme import SPACE_COMPACT, SPACE_NORMAL, apply_role, apply_surface
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog
from listentrace.ui.windows.player_window import _format_time
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog

_TEXT_ANSWER_TYPES = frozenset({QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value})
_MAX_CHOICES = 4


class QuizOptionCard(QFrame):
    """Interactive answer option card composite replacing naked radio buttons."""

    def __init__(self, index: int, letter: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"quiz_option_card_{index}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)
        apply_role(self, "quiz_option")
        # Keyboard/focus accessibility: the card itself is the interactive
        # target (not just the nested radio button), so it needs its own
        # focus policy and a visible focus ring — Tab traversal and
        # Space/Return activation must work without a mouse.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._index = index
        self._letter = letter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self._radio = QRadioButton()
        self._radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._badge = QLabel(letter)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(24, 24)
        apply_role(self._badge, "quiz_option_badge")

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setStyleSheet("font-size: 13px; font-weight: 500;")

        # Non-color selected marker — shown in addition to the accent
        # border/background so selection is never conveyed by color alone.
        self._selected_marker = QLabel("")
        self._selected_marker.setFixedWidth(16)
        apply_role(self._selected_marker, "quiz_option_marker")

        layout.addWidget(self._radio, 0)
        layout.addWidget(self._badge, 0)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._selected_marker, 0)

        self.mousePressEvent = self._on_card_clicked
        self._radio.toggled.connect(self._on_radio_toggled)
        self._update_appearance(False)

    def _on_card_clicked(self, event) -> None:
        if self._radio.isEnabled():
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._radio.setChecked(True)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._radio.isEnabled():
                self._radio.setChecked(True)
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_radio_toggled(self, checked: bool) -> None:
        self._update_appearance(checked)

    def _update_appearance(self, checked: bool) -> None:
        selected = "true" if checked else "false"
        theme.apply_variant(self, selected=selected)
        theme.apply_variant(self._badge, selected=selected)
        theme.apply_variant(self._selected_marker, selected=selected)
        self._selected_marker.setText("✓" if checked else "")


class QuizWindow(QMainWindow):
    """M13 Reconstructed Quiz Learning Canvas.

    Reconstructs QuizWindow into a single-question focused Paper Study learning canvas:
    - Quiet Context Header & Question Progress Tag
    - Question Canvas with prompt text & question type badge
    - Demoted Cue Audio Playback utility bar
    - Option Cards with wrapped text & large click targets (replacing naked radio buttons)
    - Distinct Submit vs Next action hierarchy
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        load_result: PlayerLoadResult,
        attempt_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._material = load_result.material
        self._cues = load_result.cues
        self._cue_by_id = {cue.id: cue for cue in self._cues if cue.id is not None}
        self._cue_index_by_id = {cue.id: index for index, cue in enumerate(self._cues) if cue.id is not None}
        self._attempt_id = attempt_id
        self.setWindowTitle(f"ListenTrace — Quiz — {self._material.title}")
        self.resize(920, 680)
        self.setMinimumSize(780, 560)

        self._playback = PlaybackController(self)
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(connection, self._material.id)
        self._player_session = PlayerSession(self._cues, loop_end_grace_ms=grace_ms)
        self._playback_usable = True
        self._loop_settings_dialog: MaterialLoopSettingsDialog | None = None
        loop_grace_change_bus.global_default_changed.connect(self._on_loop_grace_global_default_changed)
        loop_grace_change_bus.material_override_changed.connect(self._on_loop_grace_material_override_changed)
        self._state: QuizState | None = None
        self._current_index = 0
        self._current_cue_index: int | None = None
        self._initialized = False

        central = GrainedDeskWidget(self)
        apply_surface(central, "paper")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL)
        layout.setSpacing(SPACE_NORMAL)
        apply_surface(self, "paper")

        # -------------------------------------------------------------------
        # 1. Header Row
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
        # 2. Main Question Canvas Card
        # -------------------------------------------------------------------
        canvas_card, canvas_layout = theme.make_card()
        apply_surface(canvas_card, "paper")
        # Deliberate comfortable reading width — a full-window-wide question
        # canvas leaves a large blank field once options are laid out; a
        # capped, centered width makes the canvas read as a designed object
        # rather than empty space with a few controls floating in it. Height
        # is left at its natural (Preferred) size rather than forced to fill
        # the window -- a card with 2-3 short options was previously stretched
        # to the window's full height, leaving a large empty region *inside*
        # the card's own border. Any leftover vertical space now lives
        # outside the card (see the trailing stretch below).
        canvas_card.setMaximumWidth(760)
        canvas_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Prompt & Type
        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        apply_role(self._question_label, "question_stem")
        canvas_layout.addWidget(self._question_label)

        # Demoted Cue Playback bar
        transport_card = QFrame()
        apply_role(transport_card, "inset_panel")
        t_layout = QHBoxLayout(transport_card)
        t_layout.setContentsMargins(8, 4, 8, 4)

        self._play_button = QPushButton("Play")
        self._play_button.clicked.connect(self._on_play_clicked)
        apply_role(self._play_button, "secondary")

        self._replay_button = QPushButton("Replay Cue")
        self._replay_button.clicked.connect(self._on_replay_clicked)
        apply_role(self._replay_button, "secondary")

        self._loop_button = QPushButton("Loop Cue")
        self._loop_button.clicked.connect(self._on_loop_clicked)
        apply_role(self._loop_button, "secondary")

        self._loop_settings_button = QPushButton("Loop Settings...")
        self._loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._loop_settings_button, "quiet")

        self._time_label = QLabel("00:00 / 00:00")
        apply_role(self._time_label, "monospace")

        for widget in (self._play_button, self._replay_button, self._loop_button, self._loop_settings_button):
            t_layout.addWidget(widget)
        t_layout.addStretch(1)
        t_layout.addWidget(self._time_label)
        canvas_layout.addWidget(transport_card)

        # Answer Stack
        self._answer_stack = QStackedWidget()
        self._answer_stack.addWidget(self._build_text_answer_panel())
        self._answer_stack.addWidget(self._build_choice_panel())
        canvas_layout.addWidget(self._answer_stack)

        canvas_row = QHBoxLayout()
        canvas_row.addStretch(1)
        canvas_row.addWidget(canvas_card, 0)
        canvas_row.addStretch(1)
        # Pin the card to its natural (top-aligned) height -- without this,
        # a Preferred-policy widget still gets stretched to fill its layout
        # cell once the cell is taller than its size hint, putting the dead
        # space right back inside the card.
        canvas_row.setAlignment(canvas_card, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(canvas_row)
        layout.addStretch(1)

        # -------------------------------------------------------------------
        # 3. Action Footer
        # -------------------------------------------------------------------
        nav_row = QHBoxLayout()
        self._previous_button = QPushButton("Previous")
        self._previous_button.clicked.connect(self._on_previous_clicked)
        self._abandon_button = QPushButton("Abandon Quiz")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)

        nav_row.addWidget(self._previous_button)
        nav_row.addWidget(self._abandon_button)
        nav_row.addStretch(1)

        self._close_button = QPushButton("Close and Resume Later")
        self._close_button.clicked.connect(self.close)
        self._next_button = QPushButton("Next Question")
        self._next_button.clicked.connect(self._on_next_clicked)
        self._submit_button = QPushButton("Submit Quiz")
        self._submit_button.clicked.connect(self._on_submit_clicked)
        self._review_button = QPushButton("View Consolidated Review")
        self._review_button.clicked.connect(self._on_view_review_clicked)

        nav_row.addWidget(self._close_button)
        nav_row.addWidget(self._next_button)
        nav_row.addWidget(self._submit_button)
        nav_row.addWidget(self._review_button)
        layout.addLayout(nav_row)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        self._apply_presentation()
        self._refresh_state()
        self._initialized = True

    def _apply_presentation(self) -> None:
        """Milestone 11 button-role assignment."""
        apply_role(self._previous_button, "secondary")
        theme.set_button_icon(self._previous_button, "back", color_token="secondary")
        apply_role(self._close_button, "quiet")
        apply_role(self._abandon_button, "danger")
        apply_role(self._review_button, "secondary")
        # _next_button / _submit_button roles are set dynamically in
        # _update_nav_buttons() based on question position.

    # ---- panel construction ----

    def _build_text_answer_panel(self) -> QWidget:
        panel, layout = theme.make_card()
        apply_surface(panel, "paper")

        self._masked_text_label = QLabel("")
        self._masked_text_label.setWordWrap(True)
        self._masked_text_label.setStyleSheet("font-family: monospace; font-size: 14px; padding: 6px 0;")
        layout.addWidget(self._masked_text_label)

        ans_lbl = QLabel("Your answer:")
        apply_role(ans_lbl, "caption")
        layout.addWidget(ans_lbl)

        self._answer_line_edit = QLineEdit()
        self._answer_line_edit.setPlaceholderText("Type your transcription answer here...")
        layout.addWidget(self._answer_line_edit)
        layout.addStretch(1)
        return panel

    def _build_choice_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        apply_surface(scroll, "paper")

        panel = QWidget()
        apply_surface(panel, "paper")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(SPACE_COMPACT)

        self._choice_button_group = QButtonGroup(panel)
        self._choice_button_group.setExclusive(True)
        self._choice_cards: list[QuizOptionCard] = []
        self._choice_radio_buttons: list[QRadioButton] = []
        self._choice_labels: list[QLabel] = []
        self._choice_rows: list[QHBoxLayout] = []

        letters = ["A", "B", "C", "D"]
        for index in range(_MAX_CHOICES):
            card = QuizOptionCard(index, letters[index], panel)
            self._choice_cards.append(card)
            self._choice_button_group.addButton(card._radio, index)
            self._choice_radio_buttons.append(card._radio)
            self._choice_labels.append(card._label)
            self._choice_rows.append(card.layout())
            layout.addWidget(card)

        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    # ---- state loading ----

    def _refresh_state(self) -> None:
        self._state = svc.load_quiz_state(self._connection, self._attempt_id)
        self._populate_question()
        self._update_progress_label()
        self._update_nav_buttons()

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    # ---- navigation ----

    def _show_question(self, index: int) -> None:
        if self._initialized:
            self._save_current_answer()
        if self._state is not None and self._state.questions:
            self._current_index = max(0, min(index, len(self._state.questions) - 1))
        self._refresh_state()

    def _on_previous_clicked(self) -> None:
        if self._current_index > 0:
            self._show_question(self._current_index - 1)

    def _on_next_clicked(self) -> None:
        if self._state is not None and self._current_index < len(self._state.questions) - 1:
            self._show_question(self._current_index + 1)

    def _save_current_answer(self) -> None:
        if self._state is None or self._state.attempt.status != QuizStatus.ACTIVE.value:
            return
        if not self._state.questions:
            return
        question = self._state.questions[self._current_index]
        try:
            if question.question_type in _TEXT_ANSWER_TYPES:
                text = self._answer_line_edit.text()
                raw = text if text.strip() else None
                svc.save_quiz_answer(self._connection, self._attempt_id, question.id, raw_answer_text=raw)
            else:
                checked_id = self._choice_button_group.checkedId()
                selected = checked_id if checked_id >= 0 else None
                svc.save_quiz_answer(
                    self._connection, self._attempt_id, question.id, selected_choice_index=selected
                )
        except (QuizValidationError, QuizQuestionNotFoundError):
            pass

    def _on_abandon_clicked(self) -> None:
        answer = QMessageBox.question(
            self,
            "Abandon Quiz",
            "Abandon this quiz? It will remain in history as read-only, without a score.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.abandon_quiz(self._connection, self._attempt_id)
        except QuizValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()
        QMessageBox.information(self, "Quiz Abandoned", "This quiz has been abandoned and is now read-only history.")
        self.close()

    def _on_submit_clicked(self) -> None:
        self._save_current_answer()
        self._state = svc.load_quiz_state(self._connection, self._attempt_id)
        unanswered = sum(
            1
            for question in self._state.questions
            if self._state.answers.get(question.id) is None
            or self._state.answers[question.id].answered_state != AnsweredState.ANSWERED.value
        )
        message = "Submit this quiz? Answers cannot be changed after submission."
        if unanswered:
            message = f"{unanswered} question(s) are still unanswered. " + message
        answer = QMessageBox.question(
            self, "Submit Quiz", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.submit_quiz(self._connection, self._attempt_id)
        except QuizValidationError as exc:
            self._show_status(str(exc))
            return
        self._refresh_state()
        self._open_review_dialog()
        self.close()

    def _on_view_review_clicked(self) -> None:
        self._open_review_dialog()

    def _open_review_dialog(self) -> None:
        try:
            dialog = QuizReviewDialog(self._connection, self._attempt_id, self)
        except QuizValidationError as exc:
            self._show_status(str(exc))
            return
        dialog.exec()

    def closeEvent(self, event) -> None:
        self._save_current_answer()
        self._playback.stop()
        super().closeEvent(event)

    # ---- question display ----

    def _populate_question(self) -> None:
        if self._state is None or not self._state.questions:
            self._question_label.setText("This quiz has no questions.")
            self._masked_text_label.setText("")
            self._current_cue_index = None
            self._set_playback_controls_enabled(False)
            self._answer_line_edit.setEnabled(False)
            for card in self._choice_cards:
                card.setVisible(False)
            return

        question = self._state.questions[self._current_index]
        answer = self._state.answers.get(question.id)
        self._current_cue_index = self._cue_index_by_id.get(question.subtitle_cue_id)
        read_only = self._state.attempt.status != QuizStatus.ACTIVE.value
        prompt = json.loads(question.prompt_payload)

        self._set_playback_controls_enabled(self._playback_usable)

        if question.question_type in _TEXT_ANSWER_TYPES:
            self._answer_stack.setCurrentIndex(0)
            if question.question_type == QuestionType.REVIEW_MISSED.value:
                hint = f"Reviewing a previously flagged ‘{prompt.get('label_key', '')}’ spot."
                if prompt.get("heard_as"):
                    hint += f" You had heard it as: “{prompt['heard_as']}”."
                self._question_label.setText(hint)
            else:
                self._question_label.setText("Type the missing or full transcript you hear:")
            self._masked_text_label.setText(prompt.get("masked_text", ""))
            self._answer_line_edit.setEnabled(True)
            self._answer_line_edit.blockSignals(True)
            self._answer_line_edit.setText(answer.raw_answer_text if answer is not None and answer.raw_answer_text else "")
            self._answer_line_edit.blockSignals(False)
            self._answer_line_edit.setReadOnly(read_only)
        else:
            self._answer_stack.setCurrentIndex(1)
            choices = prompt.get("choices", [])
            if question.question_type == QuestionType.KEYWORD_RECOGNITION.value:
                self._question_label.setText(
                    f"Did you hear “{prompt.get('target_text', '')}” in this cue?"
                )
            else:
                self._question_label.setText("Which transcript matches what you heard?")
            self._masked_text_label.setText("")
            selected_index = answer.selected_choice_index if answer is not None else None
            for index, radio in enumerate(self._choice_radio_buttons):
                label = self._choice_labels[index]
                card = self._choice_cards[index]
                if index < len(choices):
                    label.setText(choices[index])
                    card.setVisible(True)
                    radio.blockSignals(True)
                    radio.setChecked(index == selected_index)
                    radio.blockSignals(False)
                    radio.setEnabled(not read_only)
                else:
                    card.setVisible(False)
                    radio.blockSignals(True)
                    radio.setChecked(False)
                    radio.blockSignals(False)

    def _update_progress_label(self) -> None:
        if self._state is None:
            return
        total = len(self._state.questions)
        if total == 0:
            self._progress_label.setText("No questions")
            return
        answered = sum(
            1
            for question in self._state.questions
            if self._state.answers.get(question.id) is not None
            and self._state.answers[question.id].answered_state == AnsweredState.ANSWERED.value
        )
        status = self._state.attempt.status
        suffix = "" if status == QuizStatus.ACTIVE.value else f"  [{status.upper()} — read-only]"
        self._progress_label.setText(f"Question {self._current_index + 1} of {total}  ({answered} answered){suffix}")

    def _update_nav_buttons(self) -> None:
        if self._state is None:
            return
        total = len(self._state.questions)
        read_only = self._state.attempt.status != QuizStatus.ACTIVE.value
        on_last_question = self._current_index >= total - 1
        self._previous_button.setEnabled(self._current_index > 0)
        self._next_button.setEnabled(not on_last_question)
        self._abandon_button.setEnabled(not read_only)
        self._submit_button.setEnabled(not read_only and total > 0)
        self._review_button.setEnabled(self._state.attempt.status == QuizStatus.COMPLETED.value)

        # Presentation-only action grammar: while there is a next question,
        # "Next Question" is the strongest next step and "Submit Quiz" stays
        # quiet-but-available; on the final question, submission becomes the
        # dominant action. Ability to submit never changes — only which
        # button visually leads.
        if on_last_question:
            apply_role(self._next_button, "quiet")
            self._submit_button.setProperty("hero", "true")
            apply_role(self._submit_button, "primary")
            theme.set_button_icon(self._next_button, "forward", color_token="secondary")
            theme.set_button_icon(self._submit_button, "motif_star", color_token="ink_on_accent")
        else:
            apply_role(self._next_button, "primary")
            self._submit_button.setProperty("hero", None)
            apply_role(self._submit_button, "quiet")
            theme.set_button_icon(self._next_button, "forward", color_token="ink_on_accent")
            theme.set_button_icon(self._submit_button, "motif_star", color_token="secondary")

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

    def _sync_play_button_text(self) -> None:
        self._play_button.setText("Pause" if self._playback.is_playing else "Play")

    def _set_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._play_button, self._replay_button, self._loop_button):
            widget.setEnabled(enabled)

    def _on_play_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
        else:
            if self._current_cue_index is not None:
                seek_to = self._player_session.play_cue(self._current_cue_index)
                self._playback.seek(seek_to)
            self._playback.play()
        self._sync_play_button_text()

    def _on_replay_clicked(self) -> None:
        if self._current_cue_index is None:
            return
        seek_to = self._player_session.replay_cue(self._current_cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _on_loop_clicked(self) -> None:
        if self._current_cue_index is None:
            return
        seek_to = self._player_session.loop_cue(self._current_cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._sync_play_button_text()

    def _apply_player_tick(self, tick: PlayerTick) -> None:
        if tick.restart_at_ms is not None:
            self._playback.restart_span(tick.restart_at_ms)
        elif tick.pause:
            self._playback.pause()
            self._sync_play_button_text()

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._player_session.on_position_changed(position_ms)
        self._apply_player_tick(tick)
        self._time_label.setText(f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}")

    def _on_end_of_media(self) -> None:
        tick = self._player_session.on_media_ended()
        self._apply_player_tick(tick)
        if tick.restart_at_ms is None:
            self._sync_play_button_text()

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._playback_usable = False
        self._set_playback_controls_enabled(False)

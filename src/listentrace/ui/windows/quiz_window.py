from __future__ import annotations

import json
import sqlite3

from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.quiz_state import QuizState
from listentrace.application.errors import QuizQuestionNotFoundError, QuizValidationError
from listentrace.application.services import quiz_service as svc
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.answered_state import AnsweredState
from listentrace.domain.enums.question_type import QuestionType
from listentrace.domain.enums.quiz_status import QuizStatus
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.windows.player_window import _format_time
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog

_TEXT_ANSWER_TYPES = frozenset({QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value})
_MAX_CHOICES = 4


class QuizWindow(QMainWindow):
    """One quiz attempt, taken question-by-question. Reuses `PlayerSession`/
    `PlaybackController` for cue timing/replay/loop (the same established player
    timing behavior as the standalone player and the guided session), and
    `application.services.quiz_service` for every generation/scoring/lifecycle
    rule — none of that logic is reimplemented here.

    Correctness is never shown in this window, for any question, at any status:
    a completed attempt can only be inspected via `QuizReviewDialog` (the "View
    Consolidated Review" button), matching "the learner completes the full quiz
    first, submits it, and then receives one consolidated review."
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
        self.resize(820, 620)

        self._playback = PlaybackController(self)
        self._player_session = PlayerSession(self._cues)
        self._playback_usable = True
        self._state: QuizState | None = None
        self._current_index = 0
        self._current_cue_index: int | None = None
        self._initialized = False

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

        transport_row = QHBoxLayout()
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
        for widget in (self._play_button, self._replay_button, self._loop_button):
            transport_row.addWidget(widget)
        transport_row.addWidget(self._time_label)
        layout.addLayout(transport_row)

        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        layout.addWidget(self._question_label)

        self._answer_stack = QStackedWidget()
        self._answer_stack.addWidget(self._build_text_answer_panel())
        self._answer_stack.addWidget(self._build_choice_panel())
        layout.addWidget(self._answer_stack, 1)

        nav_row = QHBoxLayout()
        self._previous_button = QPushButton("Previous")
        self._previous_button.clicked.connect(self._on_previous_clicked)
        self._next_button = QPushButton("Next")
        self._next_button.clicked.connect(self._on_next_clicked)
        self._close_button = QPushButton("Close and Resume Later")
        self._close_button.clicked.connect(self.close)
        self._abandon_button = QPushButton("Abandon Quiz")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)
        self._submit_button = QPushButton("Submit Quiz")
        self._submit_button.clicked.connect(self._on_submit_clicked)
        self._review_button = QPushButton("View Consolidated Review")
        self._review_button.clicked.connect(self._on_view_review_clicked)
        for widget in (
            self._previous_button,
            self._next_button,
            self._close_button,
            self._abandon_button,
            self._submit_button,
            self._review_button,
        ):
            nav_row.addWidget(widget)
        layout.addLayout(nav_row)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)
        self._playback.set_volume(0.8)
        self._playback.load(self._material.media_path)

        self._apply_presentation()

        self._load_initial_state()
        self._initialized = True

    def _apply_presentation(self) -> None:
        """Milestone 11 button-role assignment: `Submit Quiz` is this
        window's single primary action -- correctness is never shown here
        (see the class docstring), so submission is the one decisive forward
        step. `Previous`/`Next` are ordinary navigation; `Close and Resume
        Later` is quiet; `Abandon Quiz` is destructive; `View Consolidated
        Review` is secondary (only enabled once the attempt is completed)."""
        theme.apply_role(self._previous_button, "secondary")
        theme.apply_role(self._next_button, "secondary")
        theme.apply_role(self._close_button, "quiet")
        theme.apply_role(self._abandon_button, "danger")
        theme.apply_role(self._submit_button, "primary")
        theme.apply_role(self._review_button, "secondary")

    # ---- panel construction ----

    def _build_text_answer_panel(self) -> QWidget:
        panel, layout = theme.make_card()
        self._masked_text_label = QLabel("")
        self._masked_text_label.setWordWrap(True)
        theme.apply_role(self._masked_text_label, "monospace")
        layout.addWidget(self._masked_text_label)
        layout.addWidget(QLabel("Your answer:"))
        self._answer_line_edit = QLineEdit()
        layout.addWidget(self._answer_line_edit)
        layout.addStretch(1)
        return panel

    def _build_choice_panel(self) -> QWidget:
        panel, layout = theme.make_card()
        self._choice_button_group = QButtonGroup(panel)
        self._choice_button_group.setExclusive(True)
        self._choice_radio_buttons: list[QRadioButton] = []
        for index in range(_MAX_CHOICES):
            radio = QRadioButton("")
            self._choice_button_group.addButton(radio, index)
            self._choice_radio_buttons.append(radio)
            layout.addWidget(radio)
        layout.addStretch(1)
        return panel

    # ---- state loading ----

    def _load_initial_state(self) -> None:
        attempt = svc.get_quiz_attempt(self._connection, self._attempt_id)
        if attempt is not None and attempt.status == QuizStatus.ACTIVE.value:
            self._state = svc.resume_quiz(self._connection, self._attempt_id)
        else:
            self._state = svc.load_quiz_state(self._connection, self._attempt_id)
        self._current_index = 0
        self._populate_question()
        self._update_progress_label()
        self._update_nav_buttons()

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
            for radio in self._choice_radio_buttons:
                radio.setVisible(False)
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
                self._question_label.setText(
                    "Type the missing word or phrase."
                    if prompt.get("mode") == "blank"
                    else "Listen and type the full sentence."
                )
            self._masked_text_label.setText(prompt.get("masked_text", ""))
            self._answer_line_edit.setEnabled(True)
            self._answer_line_edit.blockSignals(True)
            self._answer_line_edit.setText((answer.raw_answer_text or "") if answer is not None else "")
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
                if index < len(choices):
                    radio.setText(choices[index])
                    radio.setVisible(True)
                    radio.blockSignals(True)
                    radio.setChecked(index == selected_index)
                    radio.blockSignals(False)
                    radio.setEnabled(not read_only)
                else:
                    radio.setVisible(False)
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
        self._previous_button.setEnabled(self._current_index > 0)
        self._next_button.setEnabled(self._current_index < total - 1)
        self._abandon_button.setEnabled(not read_only)
        self._submit_button.setEnabled(not read_only and total > 0)
        self._review_button.setEnabled(self._state.attempt.status == QuizStatus.COMPLETED.value)

    # ---- shared playback plumbing ----

    def _sync_play_button_text(self) -> None:
        self._play_button.setText("Pause" if self._playback.is_playing else "Play")

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._player_session.on_position_changed(position_ms)
        if tick.pause:
            self._playback.pause()
            self._sync_play_button_text()
        if tick.seek_to_ms is not None:
            self._playback.seek(tick.seek_to_ms)
        self._time_label.setText(f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}")

    def _on_end_of_media(self) -> None:
        self._sync_play_button_text()

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._playback_usable = False
        self._set_playback_controls_enabled(False)

    def _set_playback_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._play_button, self._replay_button, self._loop_button):
            widget.setEnabled(enabled)

    def _on_play_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
        else:
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

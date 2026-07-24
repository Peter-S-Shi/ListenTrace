from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from listentrace.application.dto.quiz_review import QuizReviewItem
from listentrace.application.services import quiz_service
from listentrace.domain.enums.question_type import QuestionType
from listentrace.infrastructure.db.repository import get_cue_by_id
from listentrace.ui.windows.player_window import _color_badge_icon

_CORRECT_COLOR = "#16A34A"
_INCORRECT_COLOR = "#DC2626"
_TEXT_ANSWER_TYPES = frozenset({QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value})


class QuizReviewDialog(QDialog):
    """The one consolidated review shown after a quiz is submitted: every
    question's raw answer, correct answer, correct/incorrect result, source
    cue, question type, and a short scoring-rule explanation — all read from
    the quiz's own stored snapshots (`quiz_service.build_quiz_review`), never
    re-derived from live cue/annotation text."""

    def __init__(self, connection: sqlite3.Connection, attempt_id: int, parent=None) -> None:
        super().__init__(parent)
        self._connection = connection
        self._review = quiz_service.build_quiz_review(connection, attempt_id)
        self.setWindowTitle("Quiz Review")
        self.resize(680, 520)

        layout = QVBoxLayout(self)

        attempt = self._review.attempt
        total = len(self._review.items)
        correct = attempt.correct_count or 0
        summary = QLabel(f"Score: {correct} / {total} correct   (mode: {attempt.quiz_mode})")
        summary.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(summary)

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        body.addWidget(self._list, 1)

        self._detail_view = QTextEdit()
        self._detail_view.setReadOnly(True)
        body.addWidget(self._detail_view, 2)
        layout.addLayout(body, 1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        for item in self._review.items:
            marker = "[correct]" if item.is_correct else "[incorrect]"
            list_item = QListWidgetItem(f"{item.position + 1}. {item.question_type}  {marker}")
            list_item.setIcon(_color_badge_icon(_CORRECT_COLOR if item.is_correct else _INCORRECT_COLOR))
            list_item.setData(Qt.ItemDataRole.UserRole, item.question_id)
            self._list.addItem(list_item)

        if self._review.items:
            self._list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._detail_view.setPlainText("")
            return
        question_id = current.data(Qt.ItemDataRole.UserRole)
        item = next((i for i in self._review.items if i.question_id == question_id), None)
        if item is not None:
            self._detail_view.setPlainText(self._format_item(item))

    def _format_item(self, item: QuizReviewItem) -> str:
        cue = get_cue_by_id(self._connection, item.subtitle_cue_id)
        lines = [
            f"Type: {item.question_type}",
            f"Source cue: {cue.text if cue is not None else '(cue no longer available)'}",
            f"Result: {'Correct' if item.is_correct else 'Incorrect'}",
        ]
        if item.question_type in _TEXT_ANSWER_TYPES:
            lines.append(f"Your answer: {item.raw_answer_text or '(no answer)'}")
            lines.append(f"Correct answer: {item.correct_answer.get('answer_text', '')}")
        else:
            choices = item.prompt.get("choices", [])
            selected_index = item.selected_choice_index
            selected_text = (
                choices[selected_index]
                if selected_index is not None and 0 <= selected_index < len(choices)
                else "(no answer)"
            )
            correct_index = item.correct_answer.get("correct_choice_index")
            correct_text = choices[correct_index] if correct_index is not None and correct_index < len(choices) else ""
            lines.append(f"Your answer: {selected_text}")
            lines.append(f"Correct answer: {correct_text}")
        if item.explanation:
            lines.append("")
            lines.append(item.explanation)
        return "\n".join(lines)

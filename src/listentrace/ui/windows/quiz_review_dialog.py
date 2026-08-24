from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.quiz_review import QuizReviewItem
from listentrace.application.services import quiz_service
from listentrace.domain.enums.question_type import QuestionType
from listentrace.ui import theme
from listentrace.ui.theme import SPACE_COMPACT, SPACE_NORMAL, apply_role, apply_surface
from listentrace.ui.windows.player_window import _color_badge_icon

_CORRECT_COLOR = theme.css("quiz_correct")
_INCORRECT_COLOR = theme.css("quiz_incorrect")
_TEXT_ANSWER_TYPES = frozenset({QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value})


class QuizReviewDialog(QDialog):
    """M13 Reconstructed Quiz Review Workspace.

    The consolidated review shown after a quiz is submitted:
    - Top Score Dossier Card with score ratio & accuracy badge
    - Left Questions List with visual correct/incorrect icons & question types
    - Right Detailed Review Paper Canvas with Question prompt, Learner Answer,
      Correct Answer, Result badge, and Scoring Explanation
    """

    def __init__(self, connection: sqlite3.Connection, attempt_id: int, parent=None) -> None:
        super().__init__(parent)
        self._connection = connection
        self._review = quiz_service.build_quiz_review(connection, attempt_id)
        self.setWindowTitle("Quiz Review & Performance")
        self.resize(780, 560)
        self.setMinimumSize(640, 440)
        apply_surface(self, "paper")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL)
        layout.setSpacing(SPACE_NORMAL)

        # Score Dossier Header
        score_card, score_layout = theme.make_card()
        apply_surface(score_card, "paper")

        attempt = self._review.attempt
        total = len(self._review.items)
        correct = attempt.correct_count or 0
        accuracy = (correct / total * 100) if total > 0 else 0

        header_row = QHBoxLayout()
        summary_title = QLabel(f"Score: {correct} / {total} Correct ({accuracy:.0f}%)")
        apply_role(summary_title, "title")
        header_row.addWidget(summary_title)
        header_row.addStretch(1)

        mode_badge = QLabel(f"Mode: {attempt.quiz_mode.upper()}")
        mode_badge.setStyleSheet(
            "background: rgba(0, 0, 0, 0.08); padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;"
        )
        header_row.addWidget(mode_badge)
        score_layout.addLayout(header_row)
        layout.addWidget(score_card)

        # Main Splitter (Left: Question List | Right: Detail Canvas)
        list_frame, list_column = theme.make_card()
        apply_surface(list_frame, "paper")

        list_hdr = QLabel("QUESTIONS REVIEW:")
        apply_role(list_hdr, "caption")
        list_column.addWidget(list_hdr)

        self._list = QListWidget()
        apply_role(self._list, "ruled_list")
        self._list.setWordWrap(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        list_column.addWidget(self._list, 1)

        detail_frame, detail_column = theme.make_card()
        apply_surface(detail_frame, "paper")

        detail_hdr = QLabel("QUESTION ANALYSIS & FEEDBACK:")
        apply_role(detail_hdr, "caption")
        detail_column.addWidget(detail_hdr)

        self._detail_view = QTextEdit()
        self._detail_view.setReadOnly(True)
        self._detail_view.setStyleSheet("font-size: 13px; line-height: 1.4;")
        detail_column.addWidget(self._detail_view, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(list_frame)
        splitter.addWidget(detail_frame)
        splitter.setSizes([300, 440])
        layout.addWidget(splitter, 1)

        # Footer Actions
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        close_button = QPushButton("Close Review")
        close_button.clicked.connect(self.accept)
        apply_role(close_button, "primary")
        close_button.setMinimumHeight(32)
        footer_row.addWidget(close_button)
        layout.addLayout(footer_row)

        for item in self._review.items:
            marker = "[correct]" if item.is_correct else "[incorrect]"
            type_label = item.question_type.replace("_", " ").title()
            list_item = QListWidgetItem(f"{item.position + 1}. {type_label}  {marker}")
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
        type_str = item.question_type.replace("_", " ").upper()
        res_str = "✓ CORRECT" if item.is_correct else "✗ INCORRECT"

        lines = [
            f"Question Type: {type_str}",
            f"Result: {res_str}",
            f"Source Cue: \"{item.source_cue_text}\"",
            "─" * 40,
        ]

        if item.question_type in _TEXT_ANSWER_TYPES:
            lines.append(f"Your Answer:   {item.raw_answer_text or '(no answer)'}")
            lines.append(f"Correct Answer: {item.correct_answer.get('answer_text', '')}")
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
            lines.append(f"Your Answer:   {selected_text}")
            lines.append(f"Correct Answer: {correct_text}")

        if item.explanation:
            lines.append("─" * 40)
            lines.append(f"Feedback & Explanation:\n{item.explanation}")

        return "\n".join(lines)

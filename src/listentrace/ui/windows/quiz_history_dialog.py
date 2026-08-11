from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from listentrace.application.errors import QuizValidationError
from listentrace.application.services import quiz_service as svc
from listentrace.domain.enums.quiz_status import QuizStatus
from listentrace.ui import theme
from listentrace.ui.time_display import format_local_timestamp

_DELETE_CONFIRMATION_TEXT = (
    "Delete this quiz attempt record?\n\n"
    "This removes:\n"
    "• the attempt record, its questions, and your answers\n\n"
    "This does not delete:\n"
    "• annotations, saved language items, or keyword captures "
    "referenced by its questions (kept as independent assets)\n\n"
    "This cannot be undone."
)


class QuizHistoryDialog(QDialog):
    """Lists every quiz attempt (active, completed, abandoned) for one material,
    newest first. Opening one always goes through `QuizWindow`, which itself
    branches on status: an active attempt resumes, a completed/abandoned one
    opens read-only (with a "View Consolidated Review" button for completed
    attempts)."""

    def __init__(self, connection: sqlite3.Connection, material_id: int, material_title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Quiz History — {material_title}")
        self.resize(520, 400)
        self._connection = connection
        self._material_id = material_id
        self.selected_attempt_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Prior quiz attempts for this material:"))

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        buttons_row = QHBoxLayout()
        self._open_button = QPushButton("Open")
        self._open_button.clicked.connect(self._on_open_clicked)
        self._open_button.setEnabled(False)
        theme.apply_role(self._open_button, "primary")
        self._delete_button = QPushButton("Delete")
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._delete_button.setEnabled(False)
        theme.apply_role(self._delete_button, "danger")
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        theme.apply_role(close_button, "quiet")
        buttons_row.addWidget(self._open_button)
        buttons_row.addWidget(self._delete_button)
        buttons_row.addWidget(close_button)
        layout.addLayout(buttons_row)

        self._attempts_by_id: dict[int, object] = {}
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        attempts = svc.list_quiz_attempts_for_material(self._connection, self._material_id)
        self._attempts_by_id = {a.id: a for a in attempts}
        if not attempts:
            empty = QListWidgetItem("No quiz attempts yet.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return
        for attempt in attempts:
            label = (
                f"[{attempt.status}] {attempt.quiz_mode} quiz, {attempt.actual_count} questions, "
                f"started {format_local_timestamp(attempt.started_at)}"
            )
            if attempt.status == "completed":
                label += f", score {attempt.correct_count}/{attempt.actual_count}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, attempt.id)
            self._list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        attempt_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._open_button.setEnabled(attempt_id is not None)
        # M12 Round 3 History Ownership Contract: only a completed/abandoned
        # attempt is a historical record; an active quiz must be abandoned
        # first (see quiz_service.delete_quiz_attempt).
        attempt = self._attempts_by_id.get(attempt_id) if attempt_id is not None else None
        self._delete_button.setEnabled(attempt is not None and attempt.status != QuizStatus.ACTIVE.value)

    def _on_delete_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        attempt_id = item.data(Qt.ItemDataRole.UserRole)
        if attempt_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Quiz Attempt",
            _DELETE_CONFIRMATION_TEXT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_quiz_attempt(self._connection, attempt_id)
        except QuizValidationError as exc:
            QMessageBox.warning(self, "Cannot Delete Quiz Attempt", str(exc))
            return
        self._refresh()

    def _on_open_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        attempt_id = item.data(Qt.ItemDataRole.UserRole)
        if attempt_id is None:
            return
        self.selected_attempt_id = attempt_id
        self.accept()

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        attempt_id = item.data(Qt.ItemDataRole.UserRole)
        if attempt_id is None:
            return
        self.selected_attempt_id = attempt_id
        self.accept()

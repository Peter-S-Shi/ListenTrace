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
    QVBoxLayout,
)

from listentrace.application.services import quiz_service as svc
from listentrace.ui import theme


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
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        theme.apply_role(close_button, "quiet")
        buttons_row.addWidget(self._open_button)
        buttons_row.addWidget(close_button)
        layout.addLayout(buttons_row)

        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        attempts = svc.list_quiz_attempts_for_material(self._connection, self._material_id)
        if not attempts:
            empty = QListWidgetItem("No quiz attempts yet.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return
        for attempt in attempts:
            label = f"[{attempt.status}] {attempt.quiz_mode} quiz, {attempt.actual_count} questions, started {attempt.started_at}"
            if attempt.status == "completed":
                label += f", score {attempt.correct_count}/{attempt.actual_count}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, attempt.id)
            self._list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        self._open_button.setEnabled(current is not None and current.data(Qt.ItemDataRole.UserRole) is not None)

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

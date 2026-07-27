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

from listentrace.application.services import practice_session_service as svc
from listentrace.ui import theme


class SessionHistoryDialog(QDialog):
    """Lists every intensive-practice session (active, completed, abandoned) for one
    material, newest first, and lets the learner open one — resuming it if active,
    or reviewing it read-only otherwise (enforced by `GuidedSessionWindow` itself)."""

    def __init__(self, connection: sqlite3.Connection, material_id: int, material_title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Session History — {material_title}")
        self.resize(520, 400)
        self._connection = connection
        self._material_id = material_id
        self.selected_session_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Prior intensive practice sessions for this material:"))

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
        sessions = svc.list_sessions_for_material(self._connection, self._material_id)
        if not sessions:
            empty = QListWidgetItem("No practice sessions yet.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return
        for session in sessions:
            label = f"[{session.status}] started {session.started_at}"
            if session.completed_at:
                label += f", completed {session.completed_at}"
            if session.abandoned_at:
                label += f", abandoned {session.abandoned_at}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            self._list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        self._open_button.setEnabled(current is not None and current.data(Qt.ItemDataRole.UserRole) is not None)

    def _on_open_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return
        self.selected_session_id = session_id
        self.accept()

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return
        self.selected_session_id = session_id
        self.accept()

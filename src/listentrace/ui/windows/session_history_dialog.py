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

from listentrace.application.errors import SessionValidationError
from listentrace.application.services import practice_session_service as svc
from listentrace.domain.enums.session_status import SessionStatus
from listentrace.ui import theme
from listentrace.ui.time_display import format_local_timestamp

_DELETE_CONFIRMATION_TEXT = (
    "Delete this practice session record?\n\n"
    "This removes:\n"
    "• the session record, its stage progress and answers\n"
    "• diagnosis evidence recorded during this session\n\n"
    "This does not delete:\n"
    "• annotations, saved language items, or keyword captures (kept "
    "as independent assets)\n"
    "• any recordings made during this session (kept, no longer "
    "linked to this session)\n\n"
    "This cannot be undone."
)


class SessionHistoryDialog(QDialog):
    """Lists every intensive-practice session (active, completed, abandoned) for one
    material, newest first, and lets the learner open one — resuming it if active,
    or reviewing it read-only otherwise (enforced by `GuidedSessionWindow` itself)."""

    def __init__(self, connection: sqlite3.Connection, material_id: int, material_title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Session History — {material_title}")
        self.resize(560, 420)
        self._connection = connection
        self._material_id = material_id
        self.selected_session_id: int | None = None
        theme.apply_surface(self, "paper")

        layout = QVBoxLayout(self)
        title_hdr = QLabel("Prior intensive practice sessions for this material:")
        theme.apply_role(title_hdr, "subtitle")
        layout.addWidget(title_hdr)

        self._list = QListWidget()
        theme.apply_role(self._list, "ruled_list")
        theme.configure_long_text_list(self._list)
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
        theme.set_button_icon(self._delete_button, "delete", color_token="danger")
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        theme.apply_role(close_button, "quiet")
        buttons_row.addWidget(self._open_button)
        buttons_row.addWidget(self._delete_button)
        buttons_row.addWidget(close_button)
        layout.addLayout(buttons_row)

        self._sessions_by_id: dict[int, object] = {}
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        sessions = svc.list_sessions_for_material(self._connection, self._material_id)
        self._sessions_by_id = {s.id: s for s in sessions}
        if not sessions:
            empty = QListWidgetItem("No practice sessions yet.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return
        for session in sessions:
            label = f"[{session.status}] started {format_local_timestamp(session.started_at)}"
            if session.completed_at:
                label += f", completed {format_local_timestamp(session.completed_at)}"
            if session.abandoned_at:
                label += f", abandoned {format_local_timestamp(session.abandoned_at)}"
            item = QListWidgetItem(label)
            row = theme.make_status_row(label, session.status)
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        session_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._open_button.setEnabled(session_id is not None)
        # M12 Round 3 History Ownership Contract: only a completed/abandoned
        # session is a historical record; an active session must be
        # abandoned first (see practice_session_service.delete_session).
        session = self._sessions_by_id.get(session_id) if session_id is not None else None
        self._delete_button.setEnabled(session is not None and session.status != SessionStatus.ACTIVE.value)

    def _on_delete_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Session",
            _DELETE_CONFIRMATION_TEXT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_session(self._connection, session_id)
        except SessionValidationError as exc:
            QMessageBox.warning(self, "Cannot Delete Session", str(exc))
            return
        self._refresh()

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

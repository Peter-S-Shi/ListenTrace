from __future__ import annotations

import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from listentrace.application.errors import AnnotationValidationError
from listentrace.application.services import label_preference_service
from listentrace.domain.enums.annotation_label import AnnotationLabel


class LabelColorDialog(QDialog):
    def __init__(self, connection: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Label Colors")
        self._connection = connection
        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        preferences = label_preference_service.get_label_preferences(connection)

        for label in AnnotationLabel:
            row = QHBoxLayout()
            row.addWidget(QLabel(label.value.replace("_", " ")))
            color = preferences.get(label.value, "#FFFFFF")
            button = QPushButton(color)
            button.setStyleSheet(f"background-color: {color};")
            button.clicked.connect(
                lambda _checked=False, key=label.value, btn=button: self._pick_color(key, btn)
            )
            self._buttons[label.value] = button
            row.addWidget(button)
            layout.addLayout(row)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _pick_color(self, label_key: str, button: QPushButton) -> None:
        chosen = QColorDialog.getColor(QColor(button.text()), self, "Choose Color")
        if not chosen.isValid():
            return
        hex_color = chosen.name()
        try:
            label_preference_service.update_label_color(self._connection, label_key, hex_color)
        except AnnotationValidationError as exc:
            self._show_error(str(exc))
            return
        button.setText(hex_color)
        button.setStyleSheet(f"background-color: {hex_color};")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Invalid Color", message)

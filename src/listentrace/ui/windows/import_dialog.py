from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from listentrace.application.dto.import_results import ImportNeedsConfirmation, ImportSuccess
from listentrace.application.errors import MaterialValidationError
from listentrace.application.services.material_import_service import import_material
from listentrace.ui import theme


class ImportDialog(QDialog):
    def __init__(self, connection: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Material")
        self.resize(480, 220)

        self._connection = connection
        self.imported_material_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION)
        layout.setSpacing(theme.SPACE_NORMAL)

        form_card, form_column = theme.make_card(decorated=False)

        self._media_edit = QLineEdit()
        form_column.addLayout(self._path_row("Media file:", self._media_edit, self._browse_media))

        self._subtitle_edit = QLineEdit()
        form_column.addLayout(
            self._path_row("Subtitle file (SRT/WebVTT):", self._subtitle_edit, self._browse_subtitle)
        )

        self._title_edit = QLineEdit()
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Title:"))
        title_row.addWidget(self._title_edit)
        form_column.addLayout(title_row)

        self._language_edit = QLineEdit()
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Language (optional):"))
        language_row.addWidget(self._language_edit)
        form_column.addLayout(language_row)
        layout.addWidget(form_card)

        self._error_label = QLabel("")
        theme.apply_role(self._error_label, "error")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        button_row = QHBoxLayout()
        import_button = QPushButton("Import")
        import_button.clicked.connect(self._on_import_clicked)
        import_button.setProperty("hero", "true")
        theme.apply_role(import_button, "primary")
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        theme.apply_role(cancel_button, "quiet")
        button_row.addWidget(import_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

    def _path_row(self, label_text: str, line_edit: QLineEdit, on_browse) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(line_edit)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(on_browse)
        theme.apply_role(browse_button, "secondary")
        theme.set_button_icon(browse_button, "browse", color_token="secondary")
        row.addWidget(browse_button)
        return row

    def _browse_media(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select media file")
        if path:
            self._media_edit.setText(path)
            if not self._title_edit.text():
                self._title_edit.setText(Path(path).stem)

    def _browse_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select subtitle file", filter="Subtitles (*.srt *.vtt)"
        )
        if path:
            self._subtitle_edit.setText(path)

    def _on_import_clicked(self) -> None:
        self._error_label.setText("")

        media_path = self._media_edit.text().strip()
        subtitle_path = self._subtitle_edit.text().strip()
        title = self._title_edit.text().strip()
        language = self._language_edit.text().strip() or None

        if not media_path or not subtitle_path or not title:
            self._error_label.setText("Media file, subtitle file, and title are all required.")
            return

        try:
            result = import_material(self._connection, media_path, subtitle_path, title, language)
        except MaterialValidationError as exc:
            self._error_label.setText(str(exc))
            return

        if isinstance(result, ImportNeedsConfirmation):
            # Milestone 11: show only the bare filename of the existing
            # material's media, not its full absolute path -- same
            # elision pattern as MainWindow's/ExportDialog's Batch 0/3 fixes.
            existing_name = Path(result.existing_media_path).name
            answer = QMessageBox.question(
                self,
                "Possible Duplicate",
                f"A file with the same content was already imported as "
                f"'{existing_name}'.\n\nContinue importing this as a new material?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                result = import_material(
                    self._connection,
                    media_path,
                    subtitle_path,
                    title,
                    language,
                    confirm_duplicate_fingerprint=True,
                )
            except MaterialValidationError as exc:
                self._error_label.setText(str(exc))
                return

        assert isinstance(result, ImportSuccess)
        self.imported_material_id = result.material_id
        self.accept()

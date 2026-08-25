from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.errors import QuickPracticeValidationError
from listentrace.application.services import quick_practice_service as svc
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.domain.services import quick_practice_rules as rules
from listentrace.ui import theme
from listentrace.ui.windows.player_window import _format_time

_REASON_LABELS: dict[str, str] = {
    "marked_misheard": "marked misheard",
    "marked_known_not_heard": "marked known but not heard",
    "marked_connected_reduced_speech": "marked connected/reduced speech",
    "incorrect_quiz_evidence": "missed on a quiz",
    "recurring_diagnosis_history": "recurring diagnosis history",
    "little_or_no_shadowing_practice": "little/no shadowing practice",
}


def _cue_label(cue: SubtitleCue) -> str:
    return f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}"


class QuickPracticeStartDialog(QDialog):
    """Milestone 10: choose how to start a Quick Practice run — Recommended
    Practice (a deterministic, reason-based cue list; see `domain/services/
    quick_practice_recommendation.py`) or Selected Cues (one cue, a
    continuous range, or an explicit subset, with the material's own
    timeline order preserved regardless of click order)."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        material_id: int,
        material_title: str,
        cues: list[SubtitleCue],
        parent: QWidget | None = None,
        initial_selected_cue_ids: list[int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Quick Practice — {material_title}")
        self.resize(720, 520)
        self._connection = connection
        self._material_id = material_id
        self._cues = cues
        self.started_session_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION)
        layout.setSpacing(theme.SPACE_NORMAL)

        header_label = QLabel(f"Quick Practice — {material_title}")
        theme.apply_role(header_label, "title")
        layout.addWidget(header_label)

        regions_row = QHBoxLayout()
        regions_row.setSpacing(theme.SPACE_SECTION)

        # LEFT: PRACTICE SOURCE
        source_card, source_column = theme.make_card("Practice Source", decorated=False)
        self._source_group = QButtonGroup(self)
        self._recommended_radio = QRadioButton("Recommended Practice")
        self._selected_radio = QRadioButton("Selected Cues")
        self._source_group.addButton(self._recommended_radio)
        self._source_group.addButton(self._selected_radio)
        self._recommended_radio.toggled.connect(self._on_source_changed)
        source_column.addWidget(self._recommended_radio)
        source_column.addWidget(self._selected_radio)

        recommended_row = QHBoxLayout()
        recommended_row.addWidget(QLabel("Number of cues:"))
        self._count_combo = QComboBox()
        for count in rules.ALLOWED_RECOMMENDED_COUNTS:
            self._count_combo.addItem(str(count), count)
        self._count_combo.setCurrentIndex(rules.ALLOWED_RECOMMENDED_COUNTS.index(rules.DEFAULT_RECOMMENDED_COUNT))
        self._count_combo.currentIndexChanged.connect(self._refresh_recommended_preview)
        recommended_row.addWidget(self._count_combo)
        source_column.addLayout(recommended_row)
        source_column.addStretch(1)
        regions_row.addWidget(source_card, 0)

        # RIGHT: ACTIVE SELECTION / PREVIEW
        selection_column = QVBoxLayout()
        selection_column.setSpacing(theme.SPACE_SECTION)

        preview_card, preview_column = theme.make_card("Preview (transparent reasons — never a hidden score)", decorated=False)
        self._recommended_preview = QListWidget()
        theme.configure_long_text_list(self._recommended_preview)
        preview_column.addWidget(self._recommended_preview, 1)
        selection_column.addWidget(preview_card, 1)

        cues_card, cues_column = theme.make_card(
            "Cues (select one, a range, or several — material timeline order is preserved)",
            decorated=False,
        )
        self._cue_list = QListWidget()
        theme.configure_long_text_list(self._cue_list)
        self._cue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for cue in cues:
            item = QListWidgetItem(_cue_label(cue))
            item.setData(Qt.ItemDataRole.UserRole, cue.id)
            self._cue_list.addItem(item)
        cues_column.addWidget(self._cue_list, 1)
        selection_column.addWidget(cues_card, 1)

        regions_row.addLayout(selection_column, 1)
        layout.addLayout(regions_row, 1)

        if initial_selected_cue_ids:
            self._selected_radio.setChecked(True)
            initial_set = set(initial_selected_cue_ids)
            for i in range(self._cue_list.count()):
                item = self._cue_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) in initial_set:
                    item.setSelected(True)
        else:
            self._recommended_radio.setChecked(True)

        self._status_label = QLabel("")
        theme.apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._start_button = QPushButton("Start Quick Practice")
        self._start_button.clicked.connect(self._on_start_clicked)
        # M13 Due-Frame Polish, Axis 1: the due-frame board shows this
        # dialog's single "Start Quick Practice" action solid-filled -- the
        # genuine one-time launch commit, not an ordinary in-flow action.
        self._start_button.setProperty("hero", "true")
        theme.apply_role(self._start_button, "primary")
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        theme.apply_role(cancel_button, "quiet")
        button_row.addWidget(self._start_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

        self._on_source_changed()

    def _on_source_changed(self, *_args) -> None:
        is_recommended = self._recommended_radio.isChecked()
        self._count_combo.setEnabled(is_recommended)
        self._recommended_preview.setEnabled(is_recommended)
        self._cue_list.setEnabled(not is_recommended)
        if is_recommended:
            self._refresh_recommended_preview()

    def _refresh_recommended_preview(self, *_args) -> None:
        if not self._recommended_radio.isChecked():
            return
        count = self._count_combo.currentData()
        entries = svc.recommend_cues(self._connection, self._material_id, count)
        self._recommended_preview.clear()
        cue_by_id = {cue.id: cue for cue in self._cues}
        for entry in entries:
            cue = cue_by_id.get(entry.subtitle_cue_id)
            reason_texts = [_REASON_LABELS.get(r, r) for r in entry.reasons] if entry.reasons else ["safe fallback"]
            label = _cue_label(cue) if cue is not None else str(entry.subtitle_cue_id)
            row = theme.make_reason_tag_row(label, reason_texts)
            item = QListWidgetItem()
            item.setSizeHint(theme.ruled_list_row_size_hint(row))
            self._recommended_preview.addItem(item)
            self._recommended_preview.setItemWidget(item, row)
        if not entries:
            empty = QListWidgetItem("No usable cues available for Quick Practice.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recommended_preview.addItem(empty)

    def _on_start_clicked(self) -> None:
        self._status_label.setText("")
        try:
            if self._recommended_radio.isChecked():
                session = svc.start_recommended_session(
                    self._connection, self._material_id, self._count_combo.currentData()
                )
            else:
                # `selectedItems()` order is not guaranteed to match the visual
                # order in Qt's multi-selection widgets — sort by row instead,
                # so "preserve cue identity and ordering" means the material's
                # own timeline order, not whatever order the clicks landed in.
                selected_rows = sorted(self._cue_list.row(item) for item in self._cue_list.selectedItems())
                selected_ids = [self._cue_list.item(row).data(Qt.ItemDataRole.UserRole) for row in selected_rows]
                session = svc.start_selected_session(self._connection, self._material_id, selected_ids)
        except QuickPracticeValidationError as exc:
            self._status_label.setText(str(exc))
            return
        self.started_session_id = session.id
        self.accept()

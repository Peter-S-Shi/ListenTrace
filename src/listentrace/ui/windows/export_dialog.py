from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.export import (
    SCOPE_ALL,
    SCOPE_ONE_MATERIAL,
    SCOPE_SELECTED_MATERIALS,
    ExportBundle,
    ExportScope,
)
from listentrace.application.services import export_formatters, export_service, learning_history_service as history_svc
from listentrace.domain.services import date_range as date_range_rules
from listentrace.domain.services import export_privacy
from listentrace.infrastructure.export_io import atomic_write_text, sanitize_export_filename
from listentrace.ui import theme

# Duplicated (not imported) from `learning_history_window.py`'s own preset
# list to avoid a circular import (that module will import `ExportDialog`
# from here) — both lists must stay in sync with `domain/services/
# date_range.py`'s five presets.
_PRESET_LABELS: list[tuple[str, str]] = [
    ("Last 7 Days", date_range_rules.PRESET_LAST_7_DAYS),
    ("Last 30 Days", date_range_rules.PRESET_LAST_30_DAYS),
    ("Last 90 Days", date_range_rules.PRESET_LAST_90_DAYS),
    ("Custom Range", date_range_rules.PRESET_CUSTOM),
    ("All Time", date_range_rules.PRESET_ALL_TIME),
]

_CATEGORY_LABELS: dict[str, str] = {
    export_privacy.CATEGORY_MATERIAL_METADATA: "Material metadata",
    export_privacy.CATEGORY_SESSION_SUMMARIES: "Session summaries",
    export_privacy.CATEGORY_STAGE_RESPONSES: "Stage responses (raw learner text)",
    export_privacy.CATEGORY_SESSION_DIAGNOSIS_HISTORY: "Session diagnosis history",
    export_privacy.CATEGORY_CURRENT_ANNOTATIONS: "Current material annotations",
    export_privacy.CATEGORY_QUIZ_ATTEMPTS: "Quiz attempts",
    export_privacy.CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS: "Quiz questions and answers (raw text)",
    export_privacy.CATEGORY_SHADOWING_EVIDENCE: "Shadowing evidence",
    export_privacy.CATEGORY_RETAINED_RECORDING_METADATA: "Retained recording metadata",
    export_privacy.CATEGORY_LEARNER_NOTES: "Learner notes and summaries",
    export_privacy.CATEGORY_VOCABULARY: "Vocabulary and saved chunks",
    export_privacy.CATEGORY_QUICK_PRACTICE_EVIDENCE: "Quick Practice evidence",
}

_PRIVACY_LABELS: dict[str, str] = {
    export_privacy.PRIVACY_TRANSCRIPT_EXCERPTS: "Transcript excerpts",
    export_privacy.PRIVACY_LEARNER_NOTES: "Learner notes",
    export_privacy.PRIVACY_MISHEARING_TEXT: "Mishearing text",
    export_privacy.PRIVACY_VOCABULARY_MEANINGS: "Vocabulary meanings",
    export_privacy.PRIVACY_SOURCE_LABELS: "Source labels (sanitized)",
    export_privacy.PRIVACY_LOCAL_FILE_NAMES: "Local file names (bare filename only, never a path)",
}

_SCOPE_LABELS = [
    ("All Materials", SCOPE_ALL),
    ("One Material", SCOPE_ONE_MATERIAL),
    ("Selected Materials", SCOPE_SELECTED_MATERIALS),
]

_CHECKBOX_GRID_COLUMNS = 1

_STALE_PREVIEW_MESSAGE = (
    'Selections changed since this preview was generated — click "Generate Preview" again '
    "before saving or copying. Nothing below reflects the current selections."
)


class ExportDialog(QDialog):
    """Milestone 9: a local, user-controlled export of learning evidence.

    Nothing is copied or saved before an explicit user action — opening this
    dialog and even generating a preview never touches disk or the
    clipboard. Preview and saved output are guaranteed identical: both the
    Markdown/JSON previews and the eventual saved file(s) come from the same
    already-rendered strings (see `_bundle`/`_markdown_text`/`_json_text`),
    never regenerated between preview and save.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        parent: QWidget | None = None,
        initial_material_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        # Native maximize (and minimize) button -- this is a large, densely
        # scrollable workspace, not a small fixed dialog; the platform
        # window chrome should offer the same maximize affordance as any
        # other resizable window instead of a custom in-app control.
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setWindowTitle("Export Learning Evidence")
        # A compact starting size -- the outer scroll area (below) decouples
        # the dialog's actual minimum geometry from this content's natural
        # size, so this is a sensible default, not a content-driven minimum.
        self.resize(680, 560)
        self.setMinimumSize(480, 360)
        self._connection = connection
        self._bundle: ExportBundle | None = None
        self._markdown_text: str | None = None
        self._json_text: str | None = None
        self._evaluation_text: str | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Outer vertical scroll workspace -- on a short/small window every
        # region from Scope through Close must stay reachable by scrolling
        # instead of some controls falling below the viewport. Horizontal
        # scrolling is only a fallback (AsNeeded), never the primary
        # mechanism -- the compact checkbox/action grids below are what
        # actually keep normal practical widths free of it.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer_layout.addWidget(scroll, 1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(theme.SPACE_MEDIUM, theme.SPACE_MEDIUM, theme.SPACE_MEDIUM, theme.SPACE_MEDIUM)
        layout.setSpacing(theme.SPACE_NORMAL)
        scroll.setWidget(content)

        # ---- scope ----
        scope_card, scope_column = theme.make_card("Scope", decorated=False)
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self._scope_combo = QComboBox()
        for label, _ in _SCOPE_LABELS:
            self._scope_combo.addItem(label)
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        scope_row.addWidget(self._scope_combo)
        scope_column.addLayout(scope_row)

        self._material_list = QListWidget()
        theme.configure_long_text_list(self._material_list)
        self._material_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        materials = history_svc.list_all_materials(connection)
        preselect_row = None
        for row in materials:
            item = QListWidgetItem(row["title"] if row["status"] == "active" else f"{row['title']}  [archived]")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self._material_list.addItem(item)
            if initial_material_id is not None and row["id"] == initial_material_id:
                preselect_row = self._material_list.count() - 1
        scope_column.addWidget(self._material_list, 1)
        layout.addWidget(scope_card, 1)

        # ---- date range ----
        # Split into a preset row and its own custom-dates row (rather than
        # one long horizontal row) -- the label, combo, and two date pickers
        # together were wide enough on their own to dictate the dialog's
        # minimum width; the custom row is only visible for Custom Range
        # anyway, so it costs nothing when hidden.
        date_column = QVBoxLayout()
        date_preset_row = QHBoxLayout()
        date_preset_row.addWidget(QLabel("Date Range:"))
        self._preset_combo = QComboBox()
        for label, _ in _PRESET_LABELS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._update_custom_range_visibility)
        date_preset_row.addWidget(self._preset_combo)
        date_preset_row.addStretch(1)
        date_column.addLayout(date_preset_row)

        date_custom_row = QHBoxLayout()
        self._custom_start_edit = QDateEdit()
        self._custom_start_edit.setCalendarPopup(True)
        self._custom_end_edit = QDateEdit()
        self._custom_end_edit.setCalendarPopup(True)
        today = QDate.currentDate()
        self._custom_start_edit.setDate(today.addDays(-30))
        self._custom_end_edit.setDate(today)
        date_custom_row.addWidget(self._custom_start_edit)
        date_custom_row.addWidget(self._custom_end_edit)
        date_custom_row.addStretch(1)
        date_column.addLayout(date_custom_row)
        layout.addLayout(date_column)

        # ---- evidence categories ----
        # Milestone 11: a fixed-column grid instead of a single-row QHBoxLayout
        # -- a dozen checkboxes in one row forced the whole dialog to grow far
        # wider than any reasonable window, rather than wrapping. A plain
        # QCheckBox(text) has no word-wrap support at all (same limitation
        # Quiz's answer options hit), so the longest labels here ("Quiz
        # questions and answers (raw text)") still dictated the dialog's
        # minimum width on their own -- each row now pairs a bare checkbox
        # with a separately word-wrapped QLabel instead.
        categories_card, categories_column = theme.make_card("Evidence categories", decorated=False)
        categories_grid = QGridLayout()
        self._category_checkboxes: dict[str, QCheckBox] = {}
        for index, category in enumerate(export_privacy.EVIDENCE_CATEGORIES):
            checked = category in export_privacy.DEFAULT_CATEGORIES
            row, checkbox = self._make_wrapping_checkbox_row(_CATEGORY_LABELS[category], checked)
            self._category_checkboxes[category] = checkbox
            categories_grid.addWidget(row, index // _CHECKBOX_GRID_COLUMNS, index % _CHECKBOX_GRID_COLUMNS)
        categories_column.addLayout(categories_grid)
        layout.addWidget(categories_card)

        # ---- privacy review ----
        # The card title itself ("Privacy review — include these fields
        # (unchecked fields are redacted, not omitted)") was one long
        # unwrapped caption line forcing ~980px of width on its own --
        # matching the wireframe's own composition, the explanatory
        # sentence is a separate word-wrapped body line under a short
        # "Privacy Review" title instead.
        privacy_card, privacy_column = theme.make_card("Privacy Review", decorated=False)
        privacy_explanation = QLabel("Include these fields (unchecked fields are redacted, not omitted):")
        privacy_explanation.setWordWrap(True)
        theme.apply_role(privacy_explanation, "caption")
        privacy_column.addWidget(privacy_explanation)

        privacy_grid = QGridLayout()
        self._privacy_checkboxes: dict[str, QCheckBox] = {}
        for index, field_key in enumerate(export_privacy.PRIVACY_FIELDS):
            checked = field_key in export_privacy.DEFAULT_PRIVACY_FIELDS
            row, checkbox = self._make_wrapping_checkbox_row(_PRIVACY_LABELS[field_key], checked)
            self._privacy_checkboxes[field_key] = checkbox
            privacy_grid.addWidget(row, index // _CHECKBOX_GRID_COLUMNS, index % _CHECKBOX_GRID_COLUMNS)
        privacy_column.addLayout(privacy_grid)

        always_excluded = QLabel(
            "Always excluded, regardless of any selection: " + ", ".join(export_privacy.ALWAYS_EXCLUDED_DESCRIPTION)
        )
        always_excluded.setWordWrap(True)
        theme.apply_role(always_excluded, "muted")
        privacy_column.addWidget(always_excluded)
        layout.addWidget(privacy_card)

        # ---- preview ----
        preview_button_row = QHBoxLayout()
        self._generate_preview_button = QPushButton("Generate Preview")
        self._generate_preview_button.clicked.connect(self._on_generate_preview_clicked)
        theme.apply_role(self._generate_preview_button, "primary")
        preview_button_row.addWidget(self._generate_preview_button)
        self._size_label = QLabel("")
        theme.apply_role(self._size_label, "caption")
        preview_button_row.addWidget(self._size_label, 1)
        layout.addLayout(preview_button_row)

        self._preview_tabs = QTabWidget()
        self._markdown_preview = QPlainTextEdit()
        self._markdown_preview.setReadOnly(True)
        self._json_preview = QPlainTextEdit()
        self._json_preview.setReadOnly(True)
        self._evaluation_preview = QPlainTextEdit()
        self._evaluation_preview.setReadOnly(True)
        self._preview_tabs.addTab(self._markdown_preview, "Markdown")
        self._preview_tabs.addTab(self._json_preview, "JSON")
        self._preview_tabs.addTab(self._evaluation_preview, "Evaluation Template")
        layout.addWidget(self._preview_tabs, 2)

        # ---- save / copy ----
        # A single six-wide row forced the whole dialog to stay as wide as
        # six buttons side by side. A 2+-column grid still sums each
        # column's own widest button -- and "Save Evaluation Template..."
        # (~338px) and "Copy Evaluation Template" (~302px) are wide enough
        # that whichever two columns they land in still forces ~500-650px
        # total, however they're paired. A single column -- each of the six
        # actions on its own row, grouped Save-then-Copy per format -- is
        # the arrangement that actually removes the width pressure: the
        # minimum width becomes the one widest button alone, not a sum of
        # two, while still being a compact multi-row layout rather than one
        # six-wide row.
        actions_grid = QGridLayout()
        self._save_markdown_button = QPushButton("Save Markdown...")
        self._save_markdown_button.clicked.connect(self._on_save_markdown_clicked)
        self._save_json_button = QPushButton("Save JSON...")
        self._save_json_button.clicked.connect(self._on_save_json_clicked)
        self._save_template_button = QPushButton("Save Evaluation Template...")
        self._save_template_button.clicked.connect(self._on_save_template_clicked)
        self._copy_markdown_button = QPushButton("Copy Markdown")
        self._copy_markdown_button.clicked.connect(self._on_copy_markdown_clicked)
        self._copy_json_button = QPushButton("Copy JSON")
        self._copy_json_button.clicked.connect(self._on_copy_json_clicked)
        self._copy_template_button = QPushButton("Copy Evaluation Template")
        self._copy_template_button.clicked.connect(self._on_copy_template_clicked)
        save_buttons = (self._save_markdown_button, self._save_json_button, self._save_template_button)
        copy_buttons = (self._copy_markdown_button, self._copy_json_button, self._copy_template_button)
        ordered_buttons = (
            self._save_markdown_button,
            self._copy_markdown_button,
            self._save_json_button,
            self._copy_json_button,
            self._save_template_button,
            self._copy_template_button,
        )
        for row, button in enumerate(ordered_buttons):
            actions_grid.addWidget(button, row, 0)
        actions_grid.setColumnStretch(0, 1)
        for button in save_buttons:
            button.setEnabled(False)
            theme.apply_role(button, "secondary")
            theme.set_button_icon(button, "save", color_token="secondary")
        for button in copy_buttons:
            button.setEnabled(False)
            theme.apply_role(button, "secondary")
            theme.set_button_icon(button, "copy", color_token="secondary")
        layout.addLayout(actions_grid)

        self._status_label = QLabel("")
        theme.apply_role(self._status_label, "caption")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        theme.apply_role(close_button, "quiet")
        layout.addWidget(close_button)

        self._on_scope_changed()
        self._update_custom_range_visibility()
        if preselect_row is not None:
            self._scope_combo.setCurrentIndex(1)  # One Material
            self._material_list.setCurrentRow(preselect_row)

        # Any change that could affect export content must invalidate a
        # previously generated preview (see `_invalidate_preview`) — wired
        # last, after the preselection above, so restoring the initial
        # material selection does not itself trigger an invalidation of a
        # preview that does not exist yet.
        self._scope_combo.currentIndexChanged.connect(self._invalidate_preview)
        self._material_list.itemSelectionChanged.connect(self._invalidate_preview)
        self._preset_combo.currentIndexChanged.connect(self._invalidate_preview)
        self._custom_start_edit.dateChanged.connect(self._invalidate_preview)
        self._custom_end_edit.dateChanged.connect(self._invalidate_preview)
        for checkbox in self._category_checkboxes.values():
            checkbox.toggled.connect(self._invalidate_preview)
        for checkbox in self._privacy_checkboxes.values():
            checkbox.toggled.connect(self._invalidate_preview)

    # ---- layout helpers ----

    @staticmethod
    def _make_wrapping_checkbox_row(text: str, checked: bool) -> tuple[QWidget, QCheckBox]:
        """A bare `QCheckBox` paired with a separate word-wrapped `QLabel`.

        `QCheckBox` has no word-wrap support, so a long product label (e.g.
        "Quiz questions and answers (raw text)") forces the whole row's
        width instead of wrapping onto a second line. Clicking the label
        toggles the checkbox too, so the click target is unchanged for the
        learner even though the text moved out of the checkbox itself.
        """
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(theme.SPACE_COMPACT)
        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        label = QLabel(text)
        label.setWordWrap(True)
        label.mousePressEvent = lambda _event, box=checkbox: box.toggle()
        row_layout.addWidget(checkbox, 0)
        row_layout.addWidget(label, 1)
        return row, checkbox

    # ---- scope / date range wiring ----

    def _on_scope_changed(self) -> None:
        kind = _SCOPE_LABELS[self._scope_combo.currentIndex()][1]
        self._material_list.setEnabled(kind != SCOPE_ALL)
        self._material_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
            if kind == SCOPE_ONE_MATERIAL
            else QAbstractItemView.SelectionMode.ExtendedSelection
        )

    def _update_custom_range_visibility(self) -> None:
        is_custom = _PRESET_LABELS[self._preset_combo.currentIndex()][1] == date_range_rules.PRESET_CUSTOM
        self._custom_start_edit.setVisible(is_custom)
        self._custom_end_edit.setVisible(is_custom)

    def _current_scope(self) -> ExportScope | None:
        kind = _SCOPE_LABELS[self._scope_combo.currentIndex()][1]
        selected_ids = tuple(
            item.data(Qt.ItemDataRole.UserRole) for item in self._material_list.selectedItems()
        )
        if kind == SCOPE_ALL:
            return ExportScope(kind=SCOPE_ALL)
        if kind == SCOPE_ONE_MATERIAL:
            if len(selected_ids) != 1:
                self._status_label.setText("Select exactly one material for a One Material export.")
                return None
            return ExportScope(kind=SCOPE_ONE_MATERIAL, material_ids=selected_ids)
        if not selected_ids:
            self._status_label.setText("Select at least one material for a Selected Materials export.")
            return None
        return ExportScope(kind=SCOPE_SELECTED_MATERIALS, material_ids=selected_ids)

    def _current_date_range(self) -> date_range_rules.ResolvedDateRange | None:
        preset = _PRESET_LABELS[self._preset_combo.currentIndex()][1]
        custom_start = self._custom_start_edit.date().toPython() if preset == date_range_rules.PRESET_CUSTOM else None
        custom_end = self._custom_end_edit.date().toPython() if preset == date_range_rules.PRESET_CUSTOM else None
        try:
            return date_range_rules.resolve_date_range(
                preset, date.today(), custom_start_date=custom_start, custom_end_date=custom_end
            )
        except date_range_rules.DateRangeError as exc:
            self._status_label.setText(str(exc))
            return None

    def _selected_categories(self) -> frozenset[str]:
        return frozenset(key for key, box in self._category_checkboxes.items() if box.isChecked())

    def _selected_privacy_fields(self) -> frozenset[str]:
        return frozenset(key for key, box in self._privacy_checkboxes.items() if box.isChecked())

    # ---- preview generation ----

    def _invalidate_preview(self, *_args) -> None:
        """Called whenever any selection that affects export content changes
        (scope, material selection, date preset, custom dates, evidence
        categories, privacy fields) — clears the stored bundle/text so a
        stale preview can never be saved or copied; the displayed preview
        text is replaced with a visible stale notice rather than silently
        left showing outdated content, and every Save/Copy action is
        disabled until "Generate Preview" is clicked again."""
        if self._bundle is None and self._markdown_text is None:
            return  # nothing generated yet — no-op, avoids clobbering the initial empty state pointlessly
        self._bundle = None
        self._markdown_text = None
        self._json_text = None
        self._evaluation_text = None
        self._markdown_preview.setPlainText(_STALE_PREVIEW_MESSAGE)
        self._json_preview.setPlainText(_STALE_PREVIEW_MESSAGE)
        self._evaluation_preview.setPlainText(_STALE_PREVIEW_MESSAGE)
        self._size_label.setText("")
        self._status_label.setText("Selections changed — generate a new preview before saving or copying.")
        for button in (
            self._save_markdown_button,
            self._save_json_button,
            self._save_template_button,
            self._copy_markdown_button,
            self._copy_json_button,
            self._copy_template_button,
        ):
            button.setEnabled(False)

    def _on_generate_preview_clicked(self) -> None:
        scope = self._current_scope()
        if scope is None:
            return
        resolved_range = self._current_date_range()
        if resolved_range is None:
            return

        try:
            bundle = export_service.build_export(
                self._connection, scope, resolved_range, self._selected_categories(), self._selected_privacy_fields()
            )
        except Exception as exc:  # preview-generation failure must not crash the dialog
            QMessageBox.warning(self, "Cannot Generate Preview", f"Preview generation failed:\n{exc}")
            return

        self._bundle = bundle
        self._markdown_text = export_formatters.render_markdown(bundle)
        self._json_text = export_formatters.render_json(bundle)
        self._evaluation_text = export_formatters.render_evaluation_template(bundle)

        self._markdown_preview.setPlainText(self._markdown_text)
        self._json_preview.setPlainText(self._json_text)
        self._evaluation_preview.setPlainText(self._evaluation_text)

        self._size_label.setText(
            f"Markdown: ~{len(self._markdown_text.encode('utf-8')):,} bytes — "
            f"JSON: ~{len(self._json_text.encode('utf-8')):,} bytes"
        )
        self._status_label.setText(f"Preview generated for {len(bundle.materials)} material(s).")

        for button in (
            self._save_markdown_button,
            self._save_json_button,
            self._save_template_button,
            self._copy_markdown_button,
            self._copy_json_button,
            self._copy_template_button,
        ):
            button.setEnabled(True)

    def _suggested_name(self, suffix: str) -> str:
        assert self._bundle is not None
        stem = sanitize_export_filename(self._bundle.scope_description)
        today_str = date.today().isoformat()
        return f"{stem}_{today_str}.{suffix}"

    # ---- save actions (atomic; the already-generated text is written verbatim) ----

    def _save_text_to_file(self, text: str, suffix: str, file_filter: str) -> None:
        destination, _ = QFileDialog.getSaveFileName(self, "Save Export", self._suggested_name(suffix), file_filter)
        if not destination:
            return
        path = Path(destination)
        if path.exists():
            answer = QMessageBox.question(
                self,
                "Overwrite File",
                f"{path.name} already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save the file:\n{exc}")
            return
        # Milestone 11: the status label is visible chrome, not a place to
        # render a real absolute filesystem path -- show the bare filename
        # and put the full path in a tooltip only (same pattern as
        # MainWindow's database-path fix in Batch 0).
        self._status_label.setText(f"Saved: {path.name}")
        self._status_label.setToolTip(str(path))

    def _on_save_markdown_clicked(self) -> None:
        if self._markdown_text is not None:
            self._save_text_to_file(self._markdown_text, "md", "Markdown Files (*.md)")

    def _on_save_json_clicked(self) -> None:
        if self._json_text is not None:
            self._save_text_to_file(self._json_text, "json", "JSON Files (*.json)")

    def _on_save_template_clicked(self) -> None:
        if self._evaluation_text is not None:
            self._save_text_to_file(self._evaluation_text, "md", "Markdown Files (*.md);;Text Files (*.txt)")

    # ---- copy actions ----

    def _copy_to_clipboard(self, text: str, label: str) -> None:
        QApplication.clipboard().setText(text)
        self._status_label.setText(f"{label} copied to clipboard.")

    def _on_copy_markdown_clicked(self) -> None:
        if self._markdown_text is not None:
            self._copy_to_clipboard(self._markdown_text, "Markdown export")

    def _on_copy_json_clicked(self) -> None:
        if self._json_text is not None:
            self._copy_to_clipboard(self._json_text, "JSON export")

    def _on_copy_template_clicked(self) -> None:
        if self._evaluation_text is not None:
            self._copy_to_clipboard(self._evaluation_text, "Evaluation template")

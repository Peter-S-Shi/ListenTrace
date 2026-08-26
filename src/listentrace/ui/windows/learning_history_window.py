from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.learning_history import (
    ActivityItem,
    QuickPracticeHistoryEntry,
    RecordingEvidenceEntry,
    SessionHistoryEntry,
    ShadowingEvidenceEntry,
)
from listentrace.application.errors import PlayerOpenError, QuickPracticeValidationError
from listentrace.application.services import learning_history_service as history_svc
from listentrace.application.services import practice_session_service
from listentrace.application.services import quick_practice_service
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.services import date_range as date_range_rules
from listentrace.ui import theme
from listentrace.ui.widgets.notebook_paper import GrainedDeskWidget
from listentrace.ui.theme import SPACE_COMPACT, SPACE_NORMAL, SPACE_PAGE, SPACE_SECTION, apply_role, apply_surface
from listentrace.ui.time_display import format_local_timestamp
from listentrace.ui.widgets.simple_bar_chart import SimpleBarChart
from listentrace.ui.windows.export_dialog import ExportDialog
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow
from listentrace.ui.windows.player_window import PlayerWindow, _format_time
from listentrace.ui.windows.quick_practice_start_dialog import QuickPracticeStartDialog
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow
from listentrace.ui.windows.quiz_review_dialog import QuizReviewDialog
from listentrace.ui.windows.quiz_window import QuizWindow
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

_ALL_MATERIALS_LABEL = "All Materials"

_PRESET_LABELS: list[tuple[str, str]] = [
    ("Last 7 Days", date_range_rules.PRESET_LAST_7_DAYS),
    ("Last 30 Days", date_range_rules.PRESET_LAST_30_DAYS),
    ("Last 90 Days", date_range_rules.PRESET_LAST_90_DAYS),
    ("Custom Range", date_range_rules.PRESET_CUSTOM),
    ("All Time", date_range_rules.PRESET_ALL_TIME),
]

_ACTIVITY_TYPES = ("session", "quiz", "diagnosis", "shadowing", "recording", "quick_practice")


def _format_duration_ms(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "unknown duration"
    return _format_time(duration_ms)


def _format_accuracy(accuracy: float | None) -> str:
    return "no completed attempts yet" if accuracy is None else f"{accuracy:.0%}"


# Overview metric grid: (key, display label, tooltip-or-None, icon name).
# Same 10 metrics/semantics as before -- the icon is a purely presentational
# addition (M13 Due-Frame-First Visual Polish, Axis 5: the approved due-frame
# board gives the METRIC SUMMARY SHEET its own icon per metric). Long
# clarifying detail that doesn't fit a short label lives in the tooltip
# instead of inline text.
_OVERVIEW_METRICS: list[tuple[str, str, str | None, str]] = [
    ("materials_practiced", "Materials Practiced", None, "material"),
    ("completed_sessions", "Completed Sessions", None, "check"),
    ("active_sessions", "Active Sessions", None, "clock"),
    ("abandoned_sessions", "Abandoned Sessions", None, "x_circle"),
    ("completed_quizzes", "Completed Quizzes", None, "quiz"),
    ("avg_quiz_accuracy", "Avg Quiz Accuracy", "Across completed attempts only.", "chart"),
    ("session_diagnosis_evidence", "Session Diagnosis Evidence", None, "clipboard"),
    (
        "shadowing_practice_actions",
        "Shadowing Practice Actions",
        "Cumulative; approximate under a date filter — see docs.",
        "mic",
    ),
    ("retained_recordings", "Retained Recordings", None, "waveform"),
    ("quick_practices_completed", "Quick Practices Completed", None, "play"),
]


class LearningHistoryWindow(QMainWindow):
    """Milestone 8: a global learning-evidence center. Combines a learning
    log, lightweight summaries, transparent insights, and workflow
    navigation — it is deliberately not a general business-intelligence
    dashboard, and it never claims to score the learner's overall ability
    (see ROADMAP.md / ARCHITECTURE.md). Every list/metric here reads existing
    Milestone 3-7 evidence through `learning_history_service`; nothing is
    computed here beyond simple text formatting."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        recordings_dir: Path,
        parent: QWidget | None = None,
        initial_material_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ListenTrace — Learning History & Insights")
        self.resize(920, 700)
        self._connection = connection
        self._recordings_dir = recordings_dir
        self._child_window: QWidget | None = None

        central = GrainedDeskWidget(self)
        apply_surface(central, "paper")
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(SPACE_PAGE, SPACE_PAGE, SPACE_PAGE, SPACE_PAGE)
        outer_layout.setSpacing(SPACE_SECTION)
        apply_surface(self, "paper")

        header = theme.make_surface_header("Study Dossier — Learning History & Insights")
        outer_layout.addLayout(header.top_bar)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Material:"))
        self._material_combo = QComboBox()
        filter_row.addWidget(self._material_combo, 1)

        filter_row.addWidget(QLabel("Date Range:"))
        self._preset_combo = QComboBox()
        for label, _ in _PRESET_LABELS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        filter_row.addWidget(self._preset_combo)

        self._custom_start_edit = QDateEdit()
        self._custom_start_edit.setCalendarPopup(True)
        self._custom_end_edit = QDateEdit()
        self._custom_end_edit.setCalendarPopup(True)
        today = QDate.currentDate()
        self._custom_start_edit.setDate(today.addDays(-30))
        self._custom_end_edit.setDate(today)
        filter_row.addWidget(self._custom_start_edit)
        filter_row.addWidget(self._custom_end_edit)

        self._apply_button = QPushButton("Apply")
        self._apply_button.clicked.connect(self._on_reload_clicked)
        theme.apply_role(self._apply_button, "secondary")
        filter_row.addWidget(self._apply_button)
        self._quick_practice_button = QPushButton("Quick Practice...")
        self._quick_practice_button.clicked.connect(self._on_quick_practice_clicked)
        theme.apply_role(self._quick_practice_button, "secondary")
        filter_row.addWidget(self._quick_practice_button)
        self._export_button = QPushButton("Export Learning Evidence...")
        self._export_button.clicked.connect(self._on_export_clicked)
        theme.apply_role(self._export_button, "secondary")
        filter_row.addWidget(self._export_button)
        outer_layout.addLayout(filter_row)

        self._error_label = QLabel("")
        theme.apply_role(self._error_label, "error")
        self._error_label.setWordWrap(True)
        outer_layout.addWidget(self._error_label)

        # Left directory + right workspace (Acrobat-style section navigation)
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setChildrenCollapsible(False)

        # Left navigation directory
        self._section_list = QListWidget()
        # 168px with no wrapping truncated "Shadowing & Recordings" and forced
        # an unwanted horizontal scrollbar. Wrapping (plus a modest width
        # bump) lets every label read in full on two lines without reviving
        # the old horizontal-tabs layout.
        self._section_list.setMaximumWidth(190)
        self._section_list.setMinimumWidth(150)
        theme.configure_long_text_list(self._section_list)
        apply_surface(self._section_list, "surface_soft")
        apply_role(self._section_list, "nav_directory")
        for section_name in (
            "Overview",
            "Activity",
            "Sessions",
            "Diagnoses",
            "Quizzes",
            "Shadowing & Recordings",
            "Quick Practice",
        ):
            item = QListWidgetItem(section_name)
            self._section_list.addItem(item)
        self._section_list.currentRowChanged.connect(self._on_section_changed)
        body_splitter.addWidget(self._section_list)

        # Right section workspace (one page per directory entry)
        self._section_stack = QStackedWidget()
        self._section_stack.addWidget(self._build_overview_tab())
        self._section_stack.addWidget(self._build_activity_tab())
        self._section_stack.addWidget(self._build_sessions_tab())
        self._section_stack.addWidget(self._build_diagnoses_tab())
        self._section_stack.addWidget(self._build_quizzes_tab())
        self._section_stack.addWidget(self._build_shadowing_recordings_tab())
        self._section_stack.addWidget(self._build_quick_practice_tab())
        body_splitter.addWidget(self._section_stack)

        body_splitter.setSizes([180, 718])
        outer_layout.addWidget(body_splitter, 1)

        self.setCentralWidget(central)

        self._refresh_material_combo(initial_material_id)
        self._update_custom_range_visibility()
        self._reload()
        self._section_list.setCurrentRow(0)

    # ---- filters ----

    def _refresh_material_combo(self, preselect_material_id: int | None) -> None:
        self._material_combo.blockSignals(True)
        self._material_combo.clear()
        self._material_combo.addItem(_ALL_MATERIALS_LABEL, None)
        materials = history_svc.list_all_materials(self._connection)
        select_index = 0
        for row in materials:
            index = self._material_combo.count()
            label = row["title"] if row["status"] == "active" else f"{row['title']}  [archived]"
            self._material_combo.addItem(label, row["id"])
            if preselect_material_id is not None and row["id"] == preselect_material_id:
                select_index = index
        self._material_combo.setCurrentIndex(select_index)
        self._material_combo.blockSignals(False)
        self._material_combo.currentIndexChanged.connect(self._on_reload_clicked)

    def _selected_material_id(self) -> int | None:
        return self._material_combo.currentData()

    def _on_preset_changed(self) -> None:
        self._update_custom_range_visibility()

    def _update_custom_range_visibility(self) -> None:
        is_custom = self._current_preset() == date_range_rules.PRESET_CUSTOM
        self._custom_start_edit.setVisible(is_custom)
        self._custom_end_edit.setVisible(is_custom)

    def _current_preset(self) -> str:
        return _PRESET_LABELS[self._preset_combo.currentIndex()][1]

    def _resolve_current_range(self) -> date_range_rules.ResolvedDateRange | None:
        preset = self._current_preset()
        today_local = date.today()
        custom_start = self._custom_start_edit.date().toPython() if preset == date_range_rules.PRESET_CUSTOM else None
        custom_end = self._custom_end_edit.date().toPython() if preset == date_range_rules.PRESET_CUSTOM else None
        try:
            return history_svc.resolve_date_range(
                preset, today_local, custom_start_date=custom_start, custom_end_date=custom_end
            )
        except date_range_rules.DateRangeError as exc:
            self._error_label.setText(str(exc))
            return None

    def _on_reload_clicked(self) -> None:
        self._reload()

    def _on_section_changed(self, row: int) -> None:
        """Switch the right workspace stack to the selected section page."""
        if 0 <= row < self._section_stack.count():
            self._section_stack.setCurrentIndex(row)

    # ---- reload ----

    def _reload(self) -> None:
        self._error_label.setText("")
        resolved_range = self._resolve_current_range()
        if resolved_range is None:
            return
        material_id = self._selected_material_id()
        conn = self._connection

        self._populate_overview(conn, material_id, resolved_range)
        self._populate_activity(conn, material_id, resolved_range)
        self._populate_sessions(conn, material_id, resolved_range)
        self._populate_diagnoses(conn, material_id, resolved_range)
        self._populate_quizzes(conn, material_id, resolved_range)
        self._populate_shadowing_recordings(conn, material_id, resolved_range)
        self._populate_quick_practice(conn, material_id, resolved_range)

    # ---- Overview tab ----

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stats_card, stats_column = theme.make_card()
        # A raw multi-line QLabel read like a debug/status report rather than
        # a finished Study Dossier. A scan-oriented 2-column icon+metric tile
        # grid keeps exactly the same data/semantics, just recomposed to read
        # at a glance -- no new metrics, no score/ranking invented (M13
        # Due-Frame-First Visual Polish, Axis 5).
        self._overview_grid = QGridLayout()
        self._overview_grid.setHorizontalSpacing(SPACE_NORMAL)
        self._overview_grid.setVerticalSpacing(SPACE_NORMAL)
        self._overview_metric_labels: dict[str, QLabel] = {}
        for index, (key, name_text, tooltip, icon_name) in enumerate(_OVERVIEW_METRICS):
            tile, value_label = theme.make_metric_tile(icon_name, name_text, tooltip)
            row, col = divmod(index, 2)
            self._overview_grid.addWidget(tile, row, col)
            self._overview_metric_labels[key] = value_label
        self._overview_grid.setColumnStretch(0, 1)
        self._overview_grid.setColumnStretch(1, 1)
        stats_column.addLayout(self._overview_grid)
        layout.addWidget(stats_card)

        continue_card, continue_column = theme.make_card(
            "Continue Learning — active sessions (always shown, regardless of filters)"
        )
        self._continue_learning_list = QListWidget()
        theme.apply_role(self._continue_learning_list, "ruled_list")
        theme.configure_long_text_list(self._continue_learning_list)
        self._continue_learning_list.currentItemChanged.connect(self._on_continue_learning_selection_changed)
        continue_column.addWidget(self._continue_learning_list, 1)

        continue_buttons_row = QHBoxLayout()
        self._resume_button = QPushButton("Resume")
        self._resume_button.clicked.connect(self._on_resume_clicked)
        self._resume_button.setEnabled(False)
        theme.apply_role(self._resume_button, "primary")
        self._open_material_from_continue_button = QPushButton("Open Material")
        self._open_material_from_continue_button.clicked.connect(self._on_open_material_from_continue_clicked)
        self._open_material_from_continue_button.setEnabled(False)
        theme.apply_role(self._open_material_from_continue_button, "secondary")
        self._abandon_button = QPushButton("Abandon Session")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)
        self._abandon_button.setEnabled(False)
        theme.apply_role(self._abandon_button, "danger")
        continue_buttons_row.addWidget(self._resume_button)
        continue_buttons_row.addWidget(self._open_material_from_continue_button)
        continue_buttons_row.addWidget(self._abandon_button)
        continue_column.addLayout(continue_buttons_row)
        layout.addWidget(continue_card, 1)

        attention_card, attention_column = theme.make_card(
            "Needs Attention — transparent reasons, not a ranking (always shown, all materials)"
        )
        self._needs_attention_list = QListWidget()
        theme.apply_role(self._needs_attention_list, "ruled_list")
        theme.configure_long_text_list(self._needs_attention_list)
        self._needs_attention_list.itemDoubleClicked.connect(self._on_needs_attention_double_clicked)
        attention_column.addWidget(self._needs_attention_list, 1)
        layout.addWidget(attention_card, 1)

        return widget

    def _populate_overview(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        overview = history_svc.get_overview(conn, material_id, resolved_range)
        metric_values = {
            "materials_practiced": str(overview.materials_practiced),
            "completed_sessions": str(overview.completed_sessions),
            "active_sessions": str(overview.active_sessions),
            "abandoned_sessions": str(overview.abandoned_sessions),
            "completed_quizzes": str(overview.completed_quizzes),
            "avg_quiz_accuracy": _format_accuracy(overview.average_quiz_accuracy),
            "session_diagnosis_evidence": str(overview.session_diagnosis_evidence_count),
            "shadowing_practice_actions": str(overview.shadowing_practice_count),
            "retained_recordings": f"{overview.retained_recording_count} "
            f"({_format_duration_ms(overview.retained_recording_total_duration_ms)})",
            "quick_practices_completed": str(overview.quick_practices_completed),
        }
        for key, value_label in self._overview_metric_labels.items():
            value_label.setText(metric_values[key])

        self._continue_learning_entries = history_svc.list_continue_learning_sessions(conn)
        self._continue_learning_list.clear()
        for entry in self._continue_learning_entries:
            item = QListWidgetItem(
                f"{entry.material_title} — active, current stage: {entry.current_stage} "
                f"(last resumed {entry.last_resumed_at})"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.session_id)
            self._continue_learning_list.addItem(item)
        if not self._continue_learning_entries:
            empty = QListWidgetItem("No active sessions.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._continue_learning_list.addItem(empty)

        self._needs_attention_entries = history_svc.list_needs_attention(conn)
        self._needs_attention_list.clear()
        for entry in self._needs_attention_entries:
            reason_text = "; ".join(r.detail for r in entry.reasons)
            item = QListWidgetItem(f"{entry.material_title}: {reason_text}")
            item.setData(Qt.ItemDataRole.UserRole, entry.material_id)
            self._needs_attention_list.addItem(item)
        if not self._needs_attention_entries:
            empty = QListWidgetItem("No materials currently need attention.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._needs_attention_list.addItem(empty)

    def _selected_continue_learning_entry(self) -> SessionHistoryEntry | None:
        item = self._continue_learning_list.currentItem()
        if item is None:
            return None
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return None
        return next((e for e in self._continue_learning_entries if e.session_id == session_id), None)

    def _on_continue_learning_selection_changed(self, *_args) -> None:
        entry = self._selected_continue_learning_entry()
        enabled = entry is not None
        self._resume_button.setEnabled(enabled)
        self._open_material_from_continue_button.setEnabled(enabled)
        self._abandon_button.setEnabled(enabled)

    def _on_resume_clicked(self) -> None:
        entry = self._selected_continue_learning_entry()
        if entry is not None:
            self._open_guided_session(entry.material_id, entry.session_id)

    def _on_open_material_from_continue_clicked(self) -> None:
        entry = self._selected_continue_learning_entry()
        if entry is not None:
            self._open_material(entry.material_id)

    def _on_abandon_clicked(self) -> None:
        entry = self._selected_continue_learning_entry()
        if entry is None:
            return
        answer = QMessageBox.question(
            self,
            "Abandon Session",
            "Abandon this active session? It is preserved as historical evidence, but cannot resume "
            "as the same session again — restarting practice on this material creates a new session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            practice_session_service.abandon_session(self._connection, entry.session_id)
            self._reload()

    def _on_needs_attention_double_clicked(self, item: QListWidgetItem) -> None:
        material_id = item.data(Qt.ItemDataRole.UserRole)
        if material_id is None:
            return
        index = self._material_combo.findData(material_id)
        if index >= 0:
            self._material_combo.setCurrentIndex(index)

    # ---- Activity tab ----

    def _build_activity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        filter_row = QHBoxLayout()
        self._activity_checkboxes: dict[str, QCheckBox] = {}
        for activity_type in _ACTIVITY_TYPES:
            checkbox = QCheckBox(activity_type.capitalize())
            apply_role(checkbox, "ui_label")
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._on_activity_filter_changed)
            self._activity_checkboxes[activity_type] = checkbox
            filter_row.addWidget(checkbox)
        layout.addLayout(filter_row)

        activity_card, activity_column = theme.make_card()
        self._activity_list = QListWidget()
        theme.apply_role(self._activity_list, "ruled_list")
        theme.configure_long_text_list(self._activity_list)
        self._activity_list.itemDoubleClicked.connect(self._on_activity_item_double_clicked)
        activity_column.addWidget(self._activity_list, 1)
        layout.addWidget(activity_card, 1)

        return widget

    def _on_activity_filter_changed(self, *_args) -> None:
        self._render_activity_list()

    def _populate_activity(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._activity_entries = history_svc.list_activity(conn, material_id, resolved_range)
        self._render_activity_list()

    def _render_activity_list(self) -> None:
        selected_types = {t for t, box in self._activity_checkboxes.items() if box.isChecked()}
        self._activity_list.clear()
        shown = [e for e in self._activity_entries if e.activity_type in selected_types]
        for entry in shown:
            item = QListWidgetItem(f"[{entry.occurred_at}] {entry.material_title} — {entry.summary}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._activity_list.addItem(item)
        if not shown:
            empty = QListWidgetItem("No activity for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._activity_list.addItem(empty)

    def _on_activity_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry: ActivityItem | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        if entry.activity_type == "session":
            self._open_guided_session(entry.material_id, entry.ref_id)
        elif entry.activity_type == "shadowing":
            self._open_guided_session(entry.material_id, entry.session_id)
        elif entry.activity_type == "quiz":
            if entry.status == "completed":
                self._open_quiz_review(entry.ref_id)
            else:
                self._open_quiz_resume(entry.material_id, entry.ref_id)
        elif entry.activity_type == "diagnosis":
            self._open_material(entry.material_id, entry.subtitle_cue_id)
        elif entry.activity_type == "recording":
            if entry.session_id is not None:
                self._open_guided_session(entry.material_id, entry.session_id)
            else:
                self._open_shadowing(entry.material_id, entry.subtitle_cue_id)
        elif entry.activity_type == "quick_practice":
            # Quick Practice has no exact-step resume (see ROADMAP.md) — a
            # read-only history entry safely opens the material itself
            # rather than attempting to resume the run.
            self._open_material(entry.material_id)

    # ---- Sessions tab ----

    def _build_sessions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        list_card, list_column = theme.make_card()
        self._sessions_list = QListWidget()
        theme.configure_long_text_list(self._sessions_list)
        self._sessions_list.itemDoubleClicked.connect(self._on_session_item_double_clicked)
        list_column.addWidget(self._sessions_list, 1)
        layout.addWidget(list_card, 1)

        chart_card, chart_column = theme.make_card("Completed sessions by day")
        self._sessions_chart = SimpleBarChart()
        chart_column.addWidget(self._sessions_chart)
        self._sessions_chart_table = QListWidget()
        theme.configure_long_text_list(self._sessions_chart_table)
        self._sessions_chart_table.setMaximumHeight(100)
        chart_column.addWidget(self._sessions_chart_table)
        layout.addWidget(chart_card)
        return widget

    def _populate_sessions(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._session_entries = history_svc.list_sessions(conn, material_id, resolved_range)
        self._sessions_list.clear()
        for entry in self._session_entries:
            outcome = f"completed {entry.completed_stage_count}, skipped {entry.skipped_stage_count}, incomplete {entry.incomplete_stage_count}"
            notes = [f"{s.stage_key}: {s.skip_note}" for s in entry.stages if s.skip_note]
            text = (
                f"[{entry.status}] {entry.material_title} — started {format_local_timestamp(entry.started_at)} "
                f"— stages: {outcome}"
            )
            if notes:
                text += " — " + "; ".join(notes)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._sessions_list.addItem(item)
        if not self._session_entries:
            empty = QListWidgetItem("No sessions for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._sessions_list.addItem(empty)

        chart_data = history_svc.chart_completed_sessions_by_period(conn, material_id, resolved_range)
        self._sessions_chart.set_data(chart_data)
        self._sessions_chart_table.clear()
        for point in chart_data.points:
            self._sessions_chart_table.addItem(f"{point.label}: {int(point.value)}")

    def _on_session_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry: SessionHistoryEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self._open_guided_session(entry.material_id, entry.session_id)

    # ---- Diagnoses tab ----

    def _build_diagnoses_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        history_card, history_column = theme.make_card("Session Diagnosis History (session-scoped evidence)")
        self._diagnosis_history_list = QListWidget()
        theme.configure_long_text_list(self._diagnosis_history_list)
        history_column.addWidget(self._diagnosis_history_list, 1)
        layout.addWidget(history_card, 1)

        chart_card, chart_column = theme.make_card("Diagnosis category frequency")
        self._diagnosis_chart = SimpleBarChart()
        chart_column.addWidget(self._diagnosis_chart)
        layout.addWidget(chart_card)

        annotation_card, annotation_column = theme.make_card(
            "Current Material Annotations (present, editable state — never combined with the "
            "session history above)"
        )
        self._current_annotation_list = QListWidget()
        theme.configure_long_text_list(self._current_annotation_list)
        annotation_column.addWidget(self._current_annotation_list)
        layout.addWidget(annotation_card)
        return widget

    def _populate_diagnoses(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        summaries = history_svc.list_diagnosis_insights(conn, material_id, resolved_range)
        self._diagnosis_history_list.clear()
        for summary in summaries:
            self._diagnosis_history_list.addItem(
                f"{summary.label_key}: {summary.occurrence_count} occurrence(s) across "
                f"{summary.session_count} session(s), {summary.material_count} material(s) "
                f"— most recent {summary.most_recent_at}"
            )
        if not summaries:
            empty = QListWidgetItem("No session diagnosis evidence for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._diagnosis_history_list.addItem(empty)

        chart_data = history_svc.chart_diagnosis_category_frequency(conn, material_id, resolved_range)
        self._diagnosis_chart.set_data(chart_data)

        current_counts = history_svc.list_current_annotation_label_counts(conn, material_id)
        self._current_annotation_list.clear()
        for label_key, count in sorted(current_counts.items()):
            self._current_annotation_list.addItem(f"{label_key}: {count}")
        if not current_counts:
            empty = QListWidgetItem("No current annotations.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._current_annotation_list.addItem(empty)

    # ---- Quizzes tab ----

    def _build_quizzes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        history_card, history_column = theme.make_card(
            "Quiz History — completed attempts (double-click to open its review)"
        )
        self._quiz_history_list = QListWidget()
        theme.configure_long_text_list(self._quiz_history_list)
        self._quiz_history_list.itemDoubleClicked.connect(self._on_quiz_history_double_clicked)
        history_column.addWidget(self._quiz_history_list, 1)
        layout.addWidget(history_card, 1)

        trend_card, trend_column = theme.make_card()
        trend_row = QHBoxLayout()
        trend_row.addWidget(QLabel("Attempt Performance trend — one material/mode group at a time:"))
        self._quiz_trend_group_combo = QComboBox()
        self._quiz_trend_group_combo.currentIndexChanged.connect(self._on_quiz_trend_group_changed)
        trend_row.addWidget(self._quiz_trend_group_combo, 1)
        trend_column.addLayout(trend_row)

        self._quiz_chart = SimpleBarChart()
        trend_column.addWidget(self._quiz_chart)
        self._quiz_chart_table = QListWidget()
        theme.configure_long_text_list(self._quiz_chart_table)
        self._quiz_chart_table.setMaximumHeight(100)
        trend_column.addWidget(self._quiz_chart_table)
        layout.addWidget(trend_card)

        comparison_card, comparison_column = theme.make_card(
            "Quiz Comparison — grouped by material and mode (never combined across either)"
        )
        self._quiz_comparison_tree = QTreeWidget()
        self._quiz_comparison_tree.setHeaderLabels(["Material / Mode / Attempt", "Score", "Accuracy"])
        # Milestone 11: let the long first column claim the leftover width
        # instead of truncating with a horizontal scrollbar while Score/
        # Accuracy sit at their natural (short) width.
        self._quiz_comparison_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        comparison_column.addWidget(self._quiz_comparison_tree, 1)
        layout.addWidget(comparison_card, 1)
        return widget

    def _populate_quizzes(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._quiz_history_entries = history_svc.list_quiz_history(conn, material_id, resolved_range)
        self._quiz_history_list.clear()
        for entry in self._quiz_history_entries:
            breakdown = ", ".join(
                f"{b.question_type}: {b.correct_count}/{b.question_count}" for b in entry.breakdown
            )
            text = (
                f"{entry.material_title} — {entry.quiz_mode} quiz — {format_local_timestamp(entry.completed_at)} — "
                f"{entry.correct_count}/{entry.actual_count} ({_format_accuracy(entry.accuracy)})"
            )
            if breakdown:
                text += f" — {breakdown}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.attempt_id)
            self._quiz_history_list.addItem(item)
        if not self._quiz_history_entries:
            empty = QListWidgetItem("No completed quiz attempts for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._quiz_history_list.addItem(empty)

        # Quiz Comparison and the trend chart below both derive from this one
        # grouped-by-(material, mode) query — never two separately-fetched
        # groupings that could drift apart.
        self._quiz_comparison_groups = history_svc.list_quiz_comparisons(conn, material_id, resolved_range)

        self._quiz_comparison_tree.clear()
        for group in self._quiz_comparison_groups:
            group_item = QTreeWidgetItem([f"{group.material_title} — {group.quiz_mode}", "", ""])
            for entry in group.entries:
                child = QTreeWidgetItem(
                    [
                        f"{format_local_timestamp(entry.completed_at or entry.started_at)} (n={entry.actual_count})",
                        f"{entry.correct_count}/{entry.actual_count}",
                        _format_accuracy(entry.accuracy),
                    ]
                )
                group_item.addChild(child)
            self._quiz_comparison_tree.addTopLevelItem(group_item)
        self._quiz_comparison_tree.expandAll()

        previous_key = self._quiz_trend_group_combo.currentData()
        self._quiz_trend_group_combo.blockSignals(True)
        self._quiz_trend_group_combo.clear()
        select_index = 0
        for index, group in enumerate(self._quiz_comparison_groups):
            key = (group.material_id, group.quiz_mode)
            self._quiz_trend_group_combo.addItem(f"{group.material_title} — {group.quiz_mode}", key)
            if key == previous_key:
                select_index = index
        if self._quiz_comparison_groups:
            self._quiz_trend_group_combo.setCurrentIndex(select_index)
        self._quiz_trend_group_combo.blockSignals(False)

        self._render_quiz_trend_chart(conn, material_id, resolved_range)

    def _render_quiz_trend_chart(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        key = self._quiz_trend_group_combo.currentData()
        group_material_id, quiz_mode = key if key is not None else (None, None)
        chart_data = history_svc.chart_quiz_accuracy_over_time(
            conn, material_id, resolved_range, group_material_id=group_material_id, quiz_mode=quiz_mode
        )
        self._quiz_chart.set_data(chart_data)
        self._quiz_chart_table.clear()
        for point in chart_data.points:
            self._quiz_chart_table.addItem(f"{point.label}: {point.value}%")
        if not chart_data.points:
            empty = QListWidgetItem("No completed attempts in this material/mode group for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._quiz_chart_table.addItem(empty)

    def _on_quiz_trend_group_changed(self, *_args) -> None:
        resolved_range = self._resolve_current_range()
        if resolved_range is None:
            return
        self._render_quiz_trend_chart(self._connection, self._selected_material_id(), resolved_range)

    def _on_quiz_history_double_clicked(self, item: QListWidgetItem) -> None:
        attempt_id = item.data(Qt.ItemDataRole.UserRole)
        if attempt_id is not None:
            self._open_quiz_review(attempt_id)

    # ---- Shadowing & Recordings tab ----

    def _build_shadowing_recordings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        shadowing_card, shadowing_column = theme.make_card(
            "Shadowing Evidence — cumulative explicit practice counts only"
        )
        self._shadowing_list = QListWidget()
        theme.configure_long_text_list(self._shadowing_list)
        self._shadowing_list.itemDoubleClicked.connect(self._on_shadowing_item_double_clicked)
        shadowing_column.addWidget(self._shadowing_list, 1)
        layout.addWidget(shadowing_card, 1)

        high_frequency_card, high_frequency_column = theme.make_card("High-frequency practiced cues")
        self._high_frequency_list = QListWidget()
        theme.configure_long_text_list(self._high_frequency_list)
        self._high_frequency_list.itemDoubleClicked.connect(self._on_shadowing_item_double_clicked)
        high_frequency_column.addWidget(self._high_frequency_list)
        layout.addWidget(high_frequency_card)

        recording_card, recording_column = theme.make_card("Retained Recordings (ready takes only)")
        self._recording_list = QListWidget()
        theme.configure_long_text_list(self._recording_list)
        self._recording_list.itemDoubleClicked.connect(self._on_recording_item_double_clicked)
        recording_column.addWidget(self._recording_list, 1)
        self._recording_total_label = QLabel("")
        theme.apply_role(self._recording_total_label, "caption")
        recording_column.addWidget(self._recording_total_label)
        layout.addWidget(recording_card, 1)
        return widget

    def _shadowing_item_text(self, entry: ShadowingEvidenceEntry) -> str:
        text = f"{entry.material_title} — \"{entry.cue_text}\" — practiced {entry.practice_count}x"
        if entry.last_practiced_at:
            text += f" — last {entry.last_practiced_at}"
        if entry.note:
            text += f" — note: {entry.note}"
        return text

    def _populate_shadowing_recordings(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._shadowing_entries = history_svc.list_shadowing_evidence(conn, material_id, resolved_range)
        self._shadowing_list.clear()
        for entry in self._shadowing_entries:
            item = QListWidgetItem(self._shadowing_item_text(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._shadowing_list.addItem(item)
        if not self._shadowing_entries:
            empty = QListWidgetItem("No shadowing practice for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._shadowing_list.addItem(empty)

        self._high_frequency_entries = history_svc.list_high_frequency_shadowing_cues(
            conn, material_id, resolved_range
        )
        self._high_frequency_list.clear()
        for entry in self._high_frequency_entries:
            item = QListWidgetItem(self._shadowing_item_text(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._high_frequency_list.addItem(item)

        recording_summary = history_svc.list_recording_evidence(conn, material_id, resolved_range)
        self._recording_entries = recording_summary.entries
        self._recording_list.clear()
        for entry in self._recording_entries:
            item = QListWidgetItem(
                f"{entry.material_title} — \"{entry.cue_text}\" — {_format_duration_ms(entry.duration_ms)} "
                f"— recorded {format_local_timestamp(entry.created_at)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._recording_list.addItem(item)
        if not self._recording_entries:
            empty = QListWidgetItem("No retained recordings for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recording_list.addItem(empty)
        self._recording_total_label.setText(
            f"Total retained duration: {_format_duration_ms(recording_summary.total_duration_ms)}"
        )

    def _on_shadowing_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry: ShadowingEvidenceEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self._open_guided_session(entry.material_id, entry.session_id)

    def _on_recording_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry: RecordingEvidenceEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        if entry.practice_session_id is not None:
            self._open_guided_session(entry.material_id, entry.practice_session_id)
        else:
            self._open_shadowing(entry.material_id, entry.subtitle_cue_id)

    # ---- Quick Practice tab ----

    def _build_quick_practice_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        card, column = theme.make_card(
            "Quick Practice runs — Active/Completed/Abandoned kept visibly distinct, "
            "never counted as Intensive Sessions or Quiz Attempts (double-click opens the material)"
        )
        self._quick_practice_list = QListWidget()
        theme.configure_long_text_list(self._quick_practice_list)
        self._quick_practice_list.itemDoubleClicked.connect(self._on_quick_practice_item_double_clicked)
        self._quick_practice_list.currentItemChanged.connect(self._on_quick_practice_selection_changed)
        column.addWidget(self._quick_practice_list, 1)
        self._delete_quick_practice_button = QPushButton("Delete")
        self._delete_quick_practice_button.clicked.connect(self._on_delete_quick_practice_clicked)
        self._delete_quick_practice_button.setEnabled(False)
        theme.apply_role(self._delete_quick_practice_button, "danger")
        theme.set_button_icon(self._delete_quick_practice_button, "delete", color_token="danger")
        column.addWidget(self._delete_quick_practice_button)
        layout.addWidget(card, 1)
        return widget

    def _quick_practice_entry_text(self, entry: QuickPracticeHistoryEntry) -> str:
        anchor = format_local_timestamp(entry.completed_at or entry.abandoned_at or entry.started_at)
        results = ", ".join(
            f"{item.cue_text[:24]}: {item.recall_result or 'in progress'}" for item in entry.items
        )
        text = (
            f"[{entry.status}] {entry.material_title} — {entry.source_type} — {anchor} — "
            f"{entry.actual_count} cue(s)"
        )
        if results:
            text += f" — {results}"
        return text

    def _populate_quick_practice(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._quick_practice_entries = history_svc.list_quick_practice_history(conn, material_id, resolved_range)
        self._quick_practice_list.clear()
        for entry in self._quick_practice_entries:
            item = QListWidgetItem(self._quick_practice_entry_text(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._quick_practice_list.addItem(item)
        if not self._quick_practice_entries:
            empty = QListWidgetItem("No Quick Practice runs for the selected filters.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._quick_practice_list.addItem(empty)

    def _on_quick_practice_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry: QuickPracticeHistoryEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self._open_material(entry.material_id)

    def _on_quick_practice_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        entry: QuickPracticeHistoryEntry | None = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        # M12 Round 3 History Ownership Contract: only a completed/abandoned
        # run is a historical record; an active run must be closed first
        # (see quick_practice_service.delete_history).
        self._delete_quick_practice_button.setEnabled(
            entry is not None and entry.status != QuickPracticeStatus.ACTIVE.value
        )

    def _on_delete_quick_practice_clicked(self) -> None:
        item = self._quick_practice_list.currentItem()
        if item is None:
            return
        entry: QuickPracticeHistoryEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Quick Practice Run",
            "Delete this Quick Practice run record?\n\n"
            "This removes:\n"
            "• the run record and its per-cue results\n"
            "• diagnosis evidence recorded during this run\n\n"
            "This does not delete:\n"
            "• annotations, saved language items, or keyword captures "
            "(kept as independent assets)\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            quick_practice_service.delete_history(self._connection, entry.session_id)
        except QuickPracticeValidationError as exc:
            QMessageBox.warning(self, "Cannot Delete Run", str(exc))
            return
        self._reload()

    # ---- shared navigation ----

    def _open_material(self, material_id: int, initial_cue_id: int | None = None) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Material", str(exc))
            return
        initial_index = None
        if initial_cue_id is not None:
            for index, cue in enumerate(load_result.cues):
                if cue.id == initial_cue_id:
                    initial_index = index
                    break
        self._child_window = PlayerWindow(load_result, self._connection, self, initial_cue_index=initial_index)
        self._child_window.show()

    def _open_guided_session(self, material_id: int, session_id: int) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Session", str(exc))
            return
        self._child_window = GuidedSessionWindow(
            self._connection, load_result, session_id, self._recordings_dir, self
        )
        self._child_window.show()

    def _open_shadowing(self, material_id: int, initial_cue_id: int | None = None) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Shadowing Practice", str(exc))
            return
        self._child_window = ShadowingPracticeWindow(
            self._connection, load_result, self._recordings_dir, self, initial_cue_id=initial_cue_id
        )
        self._child_window.show()

    def _open_quiz_resume(self, material_id: int, attempt_id: int) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Quiz", str(exc))
            return
        self._child_window = QuizWindow(self._connection, load_result, attempt_id, self)
        self._child_window.show()

    def _open_quiz_review(self, attempt_id: int) -> None:
        dialog = QuizReviewDialog(self._connection, attempt_id, self)
        dialog.exec()

    def _on_export_clicked(self) -> None:
        dialog = ExportDialog(self._connection, self, initial_material_id=self._selected_material_id())
        dialog.exec()

    def _on_quick_practice_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            QMessageBox.information(
                self, "Select a Material", "Select one material from the filter above to start Quick Practice."
            )
            return
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Start Quick Practice", str(exc))
            return
        if not load_result.cues:
            QMessageBox.warning(
                self, "Cannot Start Quick Practice", "This material has no timed cues available for Quick Practice."
            )
            return
        start_dialog = QuickPracticeStartDialog(
            self._connection, material_id, load_result.material.title, load_result.cues, self
        )
        if start_dialog.exec() != QDialog.DialogCode.Accepted or start_dialog.started_session_id is None:
            return
        self._child_window = QuickPracticeWindow(
            self._connection, load_result, start_dialog.started_session_id, self._recordings_dir, self
        )
        self._child_window.show()

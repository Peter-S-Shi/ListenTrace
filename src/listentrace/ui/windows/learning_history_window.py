from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.learning_history import (
    ActivityItem,
    RecordingEvidenceEntry,
    SessionHistoryEntry,
    ShadowingEvidenceEntry,
)
from listentrace.application.errors import PlayerOpenError
from listentrace.application.services import learning_history_service as history_svc
from listentrace.application.services import practice_session_service
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.domain.services import date_range as date_range_rules
from listentrace.ui.widgets.simple_bar_chart import SimpleBarChart
from listentrace.ui.windows.export_dialog import ExportDialog
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow
from listentrace.ui.windows.player_window import PlayerWindow, _format_time
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

_ACTIVITY_TYPES = ("session", "quiz", "diagnosis", "shadowing", "recording")


def _format_duration_ms(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "unknown duration"
    return _format_time(duration_ms)


def _format_accuracy(accuracy: float | None) -> str:
    return "no completed attempts yet" if accuracy is None else f"{accuracy:.0%}"


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

        central = QWidget(self)
        outer_layout = QVBoxLayout(central)

        title_label = QLabel("Learning History & Insights")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer_layout.addWidget(title_label)

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
        filter_row.addWidget(self._apply_button)
        self._export_button = QPushButton("Export Learning Evidence...")
        self._export_button.clicked.connect(self._on_export_clicked)
        filter_row.addWidget(self._export_button)
        outer_layout.addLayout(filter_row)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.setWordWrap(True)
        outer_layout.addWidget(self._error_label)

        self._tabs = QTabWidget()
        outer_layout.addWidget(self._tabs, 1)

        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_activity_tab(), "Activity")
        self._tabs.addTab(self._build_sessions_tab(), "Sessions")
        self._tabs.addTab(self._build_diagnoses_tab(), "Diagnoses")
        self._tabs.addTab(self._build_quizzes_tab(), "Quizzes")
        self._tabs.addTab(self._build_shadowing_recordings_tab(), "Shadowing & Recordings")

        self.setCentralWidget(central)

        self._refresh_material_combo(initial_material_id)
        self._update_custom_range_visibility()
        self._reload()

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

    # ---- Overview tab ----

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._overview_label = QLabel("")
        self._overview_label.setWordWrap(True)
        layout.addWidget(self._overview_label)

        layout.addWidget(QLabel("Continue Learning — active sessions (always shown, regardless of filters):"))
        self._continue_learning_list = QListWidget()
        self._continue_learning_list.currentItemChanged.connect(self._on_continue_learning_selection_changed)
        layout.addWidget(self._continue_learning_list, 1)

        continue_buttons_row = QHBoxLayout()
        self._resume_button = QPushButton("Resume")
        self._resume_button.clicked.connect(self._on_resume_clicked)
        self._resume_button.setEnabled(False)
        self._open_material_from_continue_button = QPushButton("Open Material")
        self._open_material_from_continue_button.clicked.connect(self._on_open_material_from_continue_clicked)
        self._open_material_from_continue_button.setEnabled(False)
        self._abandon_button = QPushButton("Abandon Session")
        self._abandon_button.clicked.connect(self._on_abandon_clicked)
        self._abandon_button.setEnabled(False)
        continue_buttons_row.addWidget(self._resume_button)
        continue_buttons_row.addWidget(self._open_material_from_continue_button)
        continue_buttons_row.addWidget(self._abandon_button)
        layout.addLayout(continue_buttons_row)

        layout.addWidget(QLabel("Needs Attention — transparent reasons, not a ranking (always shown, all materials):"))
        self._needs_attention_list = QListWidget()
        self._needs_attention_list.itemDoubleClicked.connect(self._on_needs_attention_double_clicked)
        layout.addWidget(self._needs_attention_list, 1)

        return widget

    def _populate_overview(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        overview = history_svc.get_overview(conn, material_id, resolved_range)
        lines = [
            f"Materials Practiced: {overview.materials_practiced}",
            f"Completed Sessions: {overview.completed_sessions}",
            f"Active Sessions: {overview.active_sessions}",
            f"Abandoned Sessions: {overview.abandoned_sessions}",
            f"Completed Quizzes: {overview.completed_quizzes}",
            f"Average Quiz Accuracy (across completed attempts): {_format_accuracy(overview.average_quiz_accuracy)}",
            f"Session Diagnosis Evidence: {overview.session_diagnosis_evidence_count}",
            f"Shadowing Practice Actions (cumulative; approximate under a date filter — see docs): "
            f"{overview.shadowing_practice_count}",
            f"Retained Recordings: {overview.retained_recording_count} "
            f"({_format_duration_ms(overview.retained_recording_total_duration_ms)} total)",
        ]
        self._overview_label.setText("\n".join(lines))

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
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._on_activity_filter_changed)
            self._activity_checkboxes[activity_type] = checkbox
            filter_row.addWidget(checkbox)
        layout.addLayout(filter_row)

        self._activity_list = QListWidget()
        self._activity_list.itemDoubleClicked.connect(self._on_activity_item_double_clicked)
        layout.addWidget(self._activity_list, 1)

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

    # ---- Sessions tab ----

    def _build_sessions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._sessions_list = QListWidget()
        self._sessions_list.itemDoubleClicked.connect(self._on_session_item_double_clicked)
        layout.addWidget(self._sessions_list, 1)

        layout.addWidget(QLabel("Completed sessions by day:"))
        self._sessions_chart = SimpleBarChart()
        layout.addWidget(self._sessions_chart)
        self._sessions_chart_table = QListWidget()
        self._sessions_chart_table.setMaximumHeight(100)
        layout.addWidget(self._sessions_chart_table)
        return widget

    def _populate_sessions(
        self, conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
    ) -> None:
        self._session_entries = history_svc.list_sessions(conn, material_id, resolved_range)
        self._sessions_list.clear()
        for entry in self._session_entries:
            outcome = f"completed {entry.completed_stage_count}, skipped {entry.skipped_stage_count}, incomplete {entry.incomplete_stage_count}"
            notes = [f"{s.stage_key}: {s.skip_note}" for s in entry.stages if s.skip_note]
            text = f"[{entry.status}] {entry.material_title} — started {entry.started_at} — stages: {outcome}"
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

        layout.addWidget(QLabel("Session Diagnosis History (session-scoped evidence):"))
        self._diagnosis_history_list = QListWidget()
        layout.addWidget(self._diagnosis_history_list, 1)

        layout.addWidget(QLabel("Diagnosis category frequency:"))
        self._diagnosis_chart = SimpleBarChart()
        layout.addWidget(self._diagnosis_chart)

        layout.addWidget(
            QLabel(
                "Current Material Annotations (present, editable state — never combined with the "
                "session history above):"
            )
        )
        self._current_annotation_list = QListWidget()
        layout.addWidget(self._current_annotation_list)
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

        layout.addWidget(QLabel("Quiz History — completed attempts (double-click to open its review):"))
        self._quiz_history_list = QListWidget()
        self._quiz_history_list.itemDoubleClicked.connect(self._on_quiz_history_double_clicked)
        layout.addWidget(self._quiz_history_list, 1)

        trend_row = QHBoxLayout()
        trend_row.addWidget(QLabel("Attempt Performance trend — one material/mode group at a time:"))
        self._quiz_trend_group_combo = QComboBox()
        self._quiz_trend_group_combo.currentIndexChanged.connect(self._on_quiz_trend_group_changed)
        trend_row.addWidget(self._quiz_trend_group_combo, 1)
        layout.addLayout(trend_row)

        self._quiz_chart = SimpleBarChart()
        layout.addWidget(self._quiz_chart)
        self._quiz_chart_table = QListWidget()
        self._quiz_chart_table.setMaximumHeight(100)
        layout.addWidget(self._quiz_chart_table)

        layout.addWidget(QLabel("Quiz Comparison — grouped by material and mode (never combined across either):"))
        self._quiz_comparison_tree = QTreeWidget()
        self._quiz_comparison_tree.setHeaderLabels(["Material / Mode / Attempt", "Score", "Accuracy"])
        layout.addWidget(self._quiz_comparison_tree, 1)
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
                f"{entry.material_title} — {entry.quiz_mode} quiz — {entry.completed_at} — "
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
                        f"{entry.completed_at or entry.started_at} (n={entry.actual_count})",
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

        layout.addWidget(QLabel("Shadowing Evidence — cumulative explicit practice counts only:"))
        self._shadowing_list = QListWidget()
        self._shadowing_list.itemDoubleClicked.connect(self._on_shadowing_item_double_clicked)
        layout.addWidget(self._shadowing_list, 1)

        layout.addWidget(QLabel("High-frequency practiced cues:"))
        self._high_frequency_list = QListWidget()
        self._high_frequency_list.itemDoubleClicked.connect(self._on_shadowing_item_double_clicked)
        layout.addWidget(self._high_frequency_list)

        layout.addWidget(QLabel("Retained Recordings (ready takes only):"))
        self._recording_list = QListWidget()
        self._recording_list.itemDoubleClicked.connect(self._on_recording_item_double_clicked)
        layout.addWidget(self._recording_list, 1)
        self._recording_total_label = QLabel("")
        layout.addWidget(self._recording_total_label)
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
                f"— recorded {entry.created_at}"
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

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.errors import (
    ActiveSessionExistsError,
    MaterialNotFoundError,
    PlayerOpenError,
    QuizValidationError,
    RecordingValidationError,
)
from listentrace.application.services import material_library_service as library
from listentrace.application.services import practice_session_service
from listentrace.application.services import quiz_service
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.infrastructure.db.migrations import current_version
from listentrace.ui.theme import apply_role, make_card
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow
from listentrace.ui.windows.import_dialog import ImportDialog
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.player_window import PlayerWindow
from listentrace.ui.windows.quick_practice_start_dialog import QuickPracticeStartDialog
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow
from listentrace.ui.windows.quiz_history_dialog import QuizHistoryDialog
from listentrace.ui.windows.quiz_window import QuizWindow
from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

_DEFAULT_QUIZ_QUESTION_COUNT = 10
_MIN_QUIZ_QUESTION_COUNT = 1
_MAX_QUIZ_QUESTION_COUNT = 50


class MainWindow(QMainWindow):
    def __init__(self, db_connection: sqlite3.Connection, db_path: Path, recordings_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("ListenTrace")
        self.resize(720, 480)

        self._connection = db_connection
        self._db_path = db_path
        self._recordings_dir = recordings_dir
        self._showing_archived = False
        self._player_window: PlayerWindow | None = None
        self._guided_session_window: GuidedSessionWindow | None = None
        self._quiz_window: QuizWindow | None = None
        self._shadowing_practice_window: ShadowingPracticeWindow | None = None
        self._learning_history_window: LearningHistoryWindow | None = None
        self._quick_practice_window: QuickPracticeWindow | None = None

        central = QWidget(self)
        outer_layout = QVBoxLayout(central)

        title_label = QLabel("ListenTrace — Material Library")
        apply_role(title_label, "title")
        outer_layout.addWidget(title_label)

        self._status_label = QLabel(f"Database ready — Schema version: {current_version(db_connection)}")
        self._status_label.setToolTip(f"Database path: {db_path}")
        outer_layout.addWidget(self._status_label)

        # --- Action cards: Library / Practice / History, grouped by
        # purpose rather than one long undifferentiated button row. ---
        cards_row = QHBoxLayout()

        library_card, library_layout = make_card("Library")
        self._import_button = QPushButton("Import Material")
        self._import_button.clicked.connect(self._on_import_clicked)
        self._open_player_button = QPushButton("Open Player")
        self._open_player_button.clicked.connect(self._on_open_player_clicked)
        self._toggle_archived_button = QPushButton("Show Archived")
        self._toggle_archived_button.clicked.connect(self._on_toggle_archived)
        library_row = QHBoxLayout()
        library_row.addWidget(self._import_button)
        library_row.addWidget(self._open_player_button)
        library_row.addWidget(self._toggle_archived_button)
        library_layout.addLayout(library_row)
        library_layout.addStretch(1)
        cards_row.addWidget(library_card, 2)

        practice_card, practice_layout = make_card("Practice")
        self._start_intensive_button = QPushButton("Start Intensive Practice")
        self._start_intensive_button.clicked.connect(self._on_start_intensive_clicked)
        self._resume_intensive_button = QPushButton("Resume Intensive Practice")
        self._resume_intensive_button.clicked.connect(self._on_resume_intensive_clicked)
        self._shadowing_practice_button = QPushButton("Shadowing Practice")
        self._shadowing_practice_button.clicked.connect(self._on_shadowing_practice_clicked)
        self._quick_practice_button = QPushButton("Quick Practice")
        self._quick_practice_button.clicked.connect(self._on_quick_practice_clicked)
        practice_row_1 = QHBoxLayout()
        practice_row_1.addWidget(self._start_intensive_button)
        practice_row_1.addWidget(self._resume_intensive_button)
        practice_row_1.addWidget(self._shadowing_practice_button)
        practice_row_1.addWidget(self._quick_practice_button)
        practice_layout.addLayout(practice_row_1)
        self._start_material_quiz_button = QPushButton("Start Material Quiz")
        self._start_material_quiz_button.clicked.connect(self._on_start_material_quiz_clicked)
        self._start_review_quiz_button = QPushButton("Start Review Quiz")
        self._start_review_quiz_button.clicked.connect(self._on_start_review_quiz_clicked)
        self._resume_quiz_button = QPushButton("Resume Quiz")
        self._resume_quiz_button.clicked.connect(self._on_resume_quiz_clicked)
        practice_row_2 = QHBoxLayout()
        practice_row_2.addWidget(self._start_material_quiz_button)
        practice_row_2.addWidget(self._start_review_quiz_button)
        practice_row_2.addWidget(self._resume_quiz_button)
        practice_layout.addLayout(practice_row_2)
        practice_layout.addStretch(1)
        cards_row.addWidget(practice_card, 3)

        history_card, history_layout = make_card("History")
        self._session_history_button = QPushButton("Session History")
        self._session_history_button.clicked.connect(self._on_session_history_clicked)
        self._learning_history_button = QPushButton("Learning History")
        self._learning_history_button.clicked.connect(self._on_learning_history_clicked)
        self._quiz_history_button = QPushButton("Quiz History")
        self._quiz_history_button.clicked.connect(self._on_quiz_history_clicked)
        for button in (self._session_history_button, self._learning_history_button, self._quiz_history_button):
            history_layout.addWidget(button)
        history_layout.addStretch(1)
        cards_row.addWidget(history_card, 1)

        outer_layout.addLayout(cards_row)

        content_layout = QHBoxLayout()

        list_card, list_layout = make_card(None)
        self._material_list = QListWidget()
        self._material_list.currentItemChanged.connect(self._on_selection_changed)
        self._material_list.itemDoubleClicked.connect(self._on_material_double_clicked)
        list_layout.addWidget(self._material_list)
        content_layout.addWidget(list_card, 1)

        detail_card, detail_layout = make_card(None)
        self._detail_label = QLabel("Select a material to see details.")
        self._detail_label.setWordWrap(True)
        detail_layout.addWidget(self._detail_label)
        detail_layout.addStretch(1)

        action_row = QHBoxLayout()
        self._rename_button = QPushButton("Rename")
        self._rename_button.clicked.connect(self._on_rename_clicked)
        self._archive_restore_button = QPushButton("Archive")
        self._archive_restore_button.clicked.connect(self._on_archive_restore_clicked)
        self._remove_button = QPushButton("Remove")
        self._remove_button.clicked.connect(self._on_remove_clicked)
        action_row.addWidget(self._rename_button)
        action_row.addWidget(self._archive_restore_button)
        action_row.addWidget(self._remove_button)
        detail_layout.addLayout(action_row)

        content_layout.addWidget(detail_card, 1)

        outer_layout.addLayout(content_layout)

        self._error_label = QLabel("")
        apply_role(self._error_label, "error")
        self._error_label.setWordWrap(True)
        outer_layout.addWidget(self._error_label)

        self.setCentralWidget(central)

        self._apply_presentation()
        self._set_action_buttons_enabled(False)
        self.refresh_library()

    def _apply_presentation(self) -> None:
        """Milestone 11 button-role assignment for this window: `Open Player`
        is this view's single primary action (the most common next step once
        a material is selected); the rest of the per-material actions and
        the quiz row are secondary; the History card's actions are quiet and
        visually consistent with each other; `Remove` is the only
        destructive action here."""
        apply_role(self._status_label, "caption")
        apply_role(self._import_button, "secondary")
        apply_role(self._open_player_button, "primary")
        apply_role(self._toggle_archived_button, "secondary")
        apply_role(self._start_intensive_button, "secondary")
        apply_role(self._resume_intensive_button, "secondary")
        apply_role(self._session_history_button, "quiet")
        apply_role(self._shadowing_practice_button, "secondary")
        apply_role(self._learning_history_button, "quiet")
        apply_role(self._quick_practice_button, "secondary")
        apply_role(self._start_material_quiz_button, "secondary")
        apply_role(self._start_review_quiz_button, "secondary")
        apply_role(self._resume_quiz_button, "secondary")
        apply_role(self._quiz_history_button, "quiet")
        apply_role(self._rename_button, "secondary")
        apply_role(self._archive_restore_button, "secondary")
        apply_role(self._remove_button, "danger")

    def refresh_library(self) -> None:
        self._material_list.clear()

        materials = (
            library.list_archived_materials(self._connection)
            if self._showing_archived
            else library.list_active_materials(self._connection)
        )

        if not materials:
            empty_item = QListWidgetItem(
                "No archived materials."
                if self._showing_archived
                else "Library is empty — import a material to get started."
            )
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._material_list.addItem(empty_item)
            self._set_action_buttons_enabled(False)
            self._detail_label.setText("Select a material to see details.")
            self._detail_label.setToolTip("")
            return

        for material in materials:
            label = material.title
            if not material.media_available:
                label += "  [media missing]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, material.id)
            self._material_list.addItem(item)

    def _selected_material_id(self) -> int | None:
        item = self._material_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        material_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if material_id is None:
            self._set_action_buttons_enabled(False)
            self._detail_label.setText("Select a material to see details.")
            self._detail_label.setToolTip("")
            return

        self._set_action_buttons_enabled(True)
        try:
            detail = library.get_material_detail(self._connection, material_id)
        except MaterialNotFoundError:
            self._detail_label.setText("This material no longer exists.")
            self._detail_label.setToolTip("")
            self.refresh_library()
            return

        self._archive_restore_button.setText(
            "Restore" if detail.status == MaterialStatus.ARCHIVED.value else "Archive"
        )

        # Milestone 11: show a compact filename rather than the full absolute
        # path (which can run to a long, wrapped, privacy-sensitive paragraph
        # for a deeply nested folder) -- the full path remains available via
        # this label's tooltip on hover, never dropped, just not rendered.
        subtitle_display = Path(detail.subtitle_source_path).name if detail.subtitle_source_path else "(none)"
        subtitle_line = f"Subtitle path: {subtitle_display}"
        if detail.subtitle_source_path is not None and not detail.subtitle_available:
            subtitle_line += "  [MISSING]"

        media_line = f"Media path: {Path(detail.media_path).name}"
        if not detail.media_available:
            media_line += "  [MISSING]"

        lines = [
            f"Title: {detail.title}",
            f"Status: {detail.status}",
            f"Language: {detail.language or '(not set)'}",
            media_line,
            f"Subtitle format: {detail.subtitle_format or '(none)'}",
            subtitle_line,
            f"Cue count: {detail.cue_count}",
        ]
        self._detail_label.setText("\n".join(lines))
        tooltip_lines = [
            f"Media path: {detail.media_path}",
            f"Subtitle path: {detail.subtitle_source_path or '(none)'}",
        ]
        self._detail_label.setToolTip("\n".join(tooltip_lines))

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        self._rename_button.setEnabled(enabled)
        self._archive_restore_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)
        self._open_player_button.setEnabled(enabled and not self._showing_archived)
        self._start_intensive_button.setEnabled(enabled and not self._showing_archived)
        self._session_history_button.setEnabled(enabled and not self._showing_archived)
        self._shadowing_practice_button.setEnabled(enabled and not self._showing_archived)
        self._quick_practice_button.setEnabled(enabled and not self._showing_archived)
        self._start_material_quiz_button.setEnabled(enabled and not self._showing_archived)
        self._start_review_quiz_button.setEnabled(enabled and not self._showing_archived)
        self._quiz_history_button.setEnabled(enabled and not self._showing_archived)
        self._update_resume_button_state()

    def _update_resume_button_state(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            self._resume_intensive_button.setEnabled(False)
            self._resume_quiz_button.setEnabled(False)
            return
        active = practice_session_service.find_active_session(self._connection, material_id)
        self._resume_intensive_button.setEnabled(active is not None)
        active_quizzes = quiz_service.find_active_quizzes_for_material(self._connection, material_id)
        self._resume_quiz_button.setEnabled(len(active_quizzes) > 0)

    def _on_import_clicked(self) -> None:
        dialog = ImportDialog(self._connection, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_library()

    def _on_material_double_clicked(self, item: QListWidgetItem) -> None:
        if self._showing_archived:
            return
        material_id = item.data(Qt.ItemDataRole.UserRole)
        if material_id is not None:
            self._open_player(material_id)

    def _on_open_player_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is not None and not self._showing_archived:
            self._open_player(material_id)

    def _open_player(self, material_id: int) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Player", str(exc))
            return

        self._player_window = PlayerWindow(load_result, self._connection, self)
        self._player_window.show()

    def _on_start_intensive_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return

        active = practice_session_service.find_active_session(self._connection, material_id)
        if active is not None:
            answer = QMessageBox.question(
                self,
                "Active Session Exists",
                "This material already has an active intensive practice session.\n\n"
                "Yes = Resume it\nNo = Abandon it and start a new one\nCancel = do nothing",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_guided_session(material_id, active.id)
            elif answer == QMessageBox.StandardButton.No:
                practice_session_service.abandon_session(self._connection, active.id)
                new_session = practice_session_service.start_session(self._connection, material_id)
                self._open_guided_session(material_id, new_session.id)
            self._update_resume_button_state()
            return

        try:
            session = practice_session_service.start_session(self._connection, material_id)
        except ActiveSessionExistsError:
            # A session was created concurrently between the check above and here;
            # fall back to whatever is now active rather than erroring out.
            active = practice_session_service.find_active_session(self._connection, material_id)
            if active is not None:
                self._open_guided_session(material_id, active.id)
            self._update_resume_button_state()
            return
        self._open_guided_session(material_id, session.id)
        self._update_resume_button_state()

    def _on_resume_intensive_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        active = practice_session_service.find_active_session(self._connection, material_id)
        if active is None:
            self.show_error("No active intensive session to resume.")
            return
        self._open_guided_session(material_id, active.id)

    def _on_session_history_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            return
        detail = library.get_material_detail(self._connection, material_id)
        dialog = SessionHistoryDialog(self._connection, material_id, detail.title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_session_id is not None:
            self._open_guided_session(material_id, dialog.selected_session_id)
        self._update_resume_button_state()

    def _open_guided_session(self, material_id: int, session_id: int) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Guided Session", str(exc))
            return
        self._guided_session_window = GuidedSessionWindow(
            self._connection, load_result, session_id, self._recordings_dir, self
        )
        self._guided_session_window.show()

    def _on_shadowing_practice_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Shadowing Practice", str(exc))
            return
        self._shadowing_practice_window = ShadowingPracticeWindow(
            self._connection, load_result, self._recordings_dir, self
        )
        self._shadowing_practice_window.show()

    def _prompt_quiz_question_count(self, title: str) -> int | None:
        count, ok = QInputDialog.getInt(
            self,
            title,
            "Number of questions (a target, not a promise — the material may only support fewer):",
            _DEFAULT_QUIZ_QUESTION_COUNT,
            _MIN_QUIZ_QUESTION_COUNT,
            _MAX_QUIZ_QUESTION_COUNT,
        )
        return count if ok else None

    def _on_start_material_quiz_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        requested_count = self._prompt_quiz_question_count("Start Material Quiz")
        if requested_count is None:
            return
        try:
            attempt = quiz_service.create_material_quiz(self._connection, material_id, requested_count)
        except QuizValidationError as exc:
            QMessageBox.warning(self, "Cannot Start Quiz", str(exc))
            return
        if attempt.actual_count < requested_count:
            QMessageBox.information(
                self,
                "Smaller Quiz Created",
                f"This material only supports {attempt.actual_count} meaningful question(s) "
                f"out of the {requested_count} requested — the smaller quiz was created.",
            )
        self._open_quiz(material_id, attempt.id)
        self._update_resume_button_state()

    def _on_start_review_quiz_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        requested_count = self._prompt_quiz_question_count("Start Review Quiz")
        if requested_count is None:
            return
        try:
            attempt = quiz_service.create_review_quiz(self._connection, material_id, requested_count)
        except QuizValidationError as exc:
            QMessageBox.warning(self, "Cannot Start Review Quiz", str(exc))
            return
        if attempt.actual_count < requested_count:
            QMessageBox.information(
                self,
                "Smaller Quiz Created",
                f"This material only has {attempt.actual_count} usable piece(s) of saved diagnosis "
                f"evidence out of the {requested_count} requested — the smaller quiz was created.",
            )
        self._open_quiz(material_id, attempt.id)
        self._update_resume_button_state()

    def _on_resume_quiz_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        active_quizzes = quiz_service.find_active_quizzes_for_material(self._connection, material_id)
        if not active_quizzes:
            self.show_error("No active quiz to resume.")
            return
        if len(active_quizzes) == 1:
            self._open_quiz(material_id, active_quizzes[0].id)
            return
        self._on_quiz_history_clicked()

    def _on_quiz_history_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            return
        detail = library.get_material_detail(self._connection, material_id)
        dialog = QuizHistoryDialog(self._connection, material_id, detail.title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_attempt_id is not None:
            self._open_quiz(material_id, dialog.selected_attempt_id)
        self._update_resume_button_state()

    def _open_quiz(self, material_id: int, attempt_id: int) -> None:
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Open Quiz", str(exc))
            return
        self._quiz_window = QuizWindow(self._connection, load_result, attempt_id, self)
        self._quiz_window.show()

    def _on_quick_practice_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None or self._showing_archived:
            return
        try:
            load_result = load_material_for_player(self._connection, material_id)
        except PlayerOpenError as exc:
            QMessageBox.warning(self, "Cannot Start Quick Practice", str(exc))
            return
        if not load_result.cues:
            self.show_error("This material has no timed cues available for Quick Practice.")
            return
        start_dialog = QuickPracticeStartDialog(
            self._connection, material_id, load_result.material.title, load_result.cues, self
        )
        if start_dialog.exec() != QDialog.DialogCode.Accepted or start_dialog.started_session_id is None:
            return
        self._quick_practice_window = QuickPracticeWindow(
            self._connection, load_result, start_dialog.started_session_id, self._recordings_dir, self
        )
        self._quick_practice_window.show()

    def _on_learning_history_clicked(self) -> None:
        """Opens globally (works with no material selected); preselects the
        currently selected material in the library list, if any, as a
        convenience — the material-level Session History/Quiz History entry
        points above are unchanged and still open their own dialogs directly."""
        self._learning_history_window = LearningHistoryWindow(
            self._connection, self._recordings_dir, self, initial_material_id=self._selected_material_id()
        )
        self._learning_history_window.show()

    def _on_toggle_archived(self) -> None:
        self._showing_archived = not self._showing_archived
        self._toggle_archived_button.setText(
            "Show Active" if self._showing_archived else "Show Archived"
        )
        self.refresh_library()

    def _on_rename_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            return
        detail = library.get_material_detail(self._connection, material_id)
        new_title, ok = QInputDialog.getText(
            self, "Rename Material", "New title:", text=detail.title
        )
        if ok and new_title.strip():
            library.rename_material(self._connection, material_id, new_title.strip())
            self.refresh_library()

    def _on_archive_restore_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            return
        detail = library.get_material_detail(self._connection, material_id)
        if detail.status == MaterialStatus.ARCHIVED.value:
            library.restore_material(self._connection, material_id)
        else:
            library.archive_material(self._connection, material_id)
        self.refresh_library()

    def _on_remove_clicked(self) -> None:
        material_id = self._selected_material_id()
        if material_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove Material",
            "This removes ListenTrace's record for this material (its subtitle and cue data) "
            "and permanently deletes all of its managed learner recordings.\n"
            "The original media file and subtitle file on disk will NOT be modified or deleted.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                library.remove_material(self._connection, self._recordings_dir, material_id)
            except RecordingValidationError as exc:
                QMessageBox.warning(self, "Cannot Remove Material", str(exc))
                return
            self.refresh_library()

    def show_error(self, message: str) -> None:
        self._error_label.setText(message)

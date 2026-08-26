from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
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
from listentrace.ui import theme
from listentrace.ui.theme import (
    SPACE_COMPACT,
    SPACE_NORMAL,
    SPACE_PAGE,
    SPACE_SECTION,
    apply_role,
    apply_surface,
    configure_long_text_list,
    get_icon,
    make_card,
    make_notebook_surface,
    make_surface_header,
    set_button_icon,
)
from listentrace.ui.widgets.material_metadata_bus import material_metadata_bus
from listentrace.ui.widgets.recording_panel import recording_change_bus
from listentrace.ui.windows.guided_session_window import GuidedSessionWindow
from listentrace.ui.windows.import_dialog import ImportDialog
from listentrace.ui.windows.learning_history_window import LearningHistoryWindow
from listentrace.ui.windows.playback_settings_dialog import PlaybackSettingsDialog
from listentrace.ui.windows.player_window import PlayerWindow
from listentrace.ui.windows.quick_practice_start_dialog import QuickPracticeStartDialog
from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow
from listentrace.ui.windows.quiz_history_dialog import QuizHistoryDialog
from listentrace.ui.windows.quiz_window import QuizWindow
from listentrace.ui.windows.session_history_dialog import SessionHistoryDialog
from listentrace.ui.windows.settings_dialog import SettingsDialog
from listentrace.ui.windows.shadowing_practice_window import ShadowingPracticeWindow

_SETTINGS_ORG = "ListenTrace"
_SETTINGS_APP = "ListenTrace"
_SETTING_SIDEBAR_COLLAPSED = "ui/sidebar_collapsed"
_SETTING_SIDEBAR_WIDTH = "ui/sidebar_width"
_DEFAULT_SIDEBAR_WIDTH = 190

_DEFAULT_QUIZ_QUESTION_COUNT = 10
_MIN_QUIZ_QUESTION_COUNT = 1
_MAX_QUIZ_QUESTION_COUNT = 50


class _DossierRow(QFrame):
    """A ruled metadata row inside the Material Study Dossier matching the approved wireframe."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        apply_role(self, "dossier_meta_row")
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(SPACE_NORMAL)

        self._label = QLabel(label)
        apply_role(self._label, "dossier_meta_label")
        self._label.setFixedWidth(120)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(self._label)

        self._value = QLabel("")
        apply_role(self._value, "dossier_meta_value")
        self._value.setWordWrap(True)
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row_layout.addWidget(self._value, 1)

    def set_value(self, text: str, is_missing: bool = False) -> None:
        self._value.setText(text)
        apply_role(self._value, "dossier_meta_value_missing" if is_missing else "dossier_meta_value")


class MainWindow(QMainWindow):
    """M13 Reconstructed Main Workspace & Material Library Window.

    HG-1 Refined Visual Architecture:
    - Hybrid Shell with a streamlined, left-aligned bookmark directory sidebar (Adobe Acrobat style)
    - Ruled notebook / study archive list for Materials browsing
    - Spiral Notebook Study Dossier for Selected Material Context (ruled paper metadata)
    - Visually dominant Primary Action (Open Player / Continue)
    - Distinct secondary practice suites, quiet utilities, and isolated danger actions
    """

    def __init__(self, db_connection: sqlite3.Connection, db_path: Path, recordings_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("ListenTrace")
        self.resize(980, 640)
        self.setMinimumSize(780, 500)

        self._connection = db_connection
        self._db_path = db_path
        self._recordings_dir = recordings_dir
        self._showing_archived = False

        # Restore sidebar state from persisted preferences
        _settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._sidebar_collapsed: bool = _settings.value(_SETTING_SIDEBAR_COLLAPSED, False, type=bool)
        self._last_sidebar_width: int = _settings.value(_SETTING_SIDEBAR_WIDTH, _DEFAULT_SIDEBAR_WIDTH, type=int)

        self._player_window: PlayerWindow | None = None
        self._guided_session_window: GuidedSessionWindow | None = None
        self._quiz_window: QuizWindow | None = None
        self._shadowing_practice_window: ShadowingPracticeWindow | None = None
        self._learning_history_window: LearningHistoryWindow | None = None
        self._quick_practice_window: QuickPracticeWindow | None = None
        self._settings_dialog: SettingsDialog | None = None
        self._playback_settings_dialog: PlaybackSettingsDialog | None = None

        self._init_ui()
        self._apply_presentation()
        self._set_action_buttons_enabled(False)
        self.refresh_library()

        # Apply persisted sidebar collapsed state after UI is ready
        if self._sidebar_collapsed:
            self._sidebar_widget.setVisible(False)
            self._toggle_sidebar_button.setText("Show Sidebar")
            set_button_icon(self._toggle_sidebar_button, "show", color_token="secondary")


    def _init_ui(self) -> None:
        apply_surface(self, "workspace")
        central = QWidget(self)
        apply_surface(central, "workspace")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Main Splitter (Hybrid Shell: Left Bookmark Sidebar + Right Study Workspace)
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self._main_splitter.setChildrenCollapsible(False)

        # -------------------------------------------------------------------
        # 1. Left Sidebar (Acrobat-Style Bookmark / Navigation Directory)
        # -------------------------------------------------------------------
        self._sidebar_widget = QWidget(self._main_splitter)
        apply_surface(self._sidebar_widget, "sidebar")
        sidebar_layout = QVBoxLayout(self._sidebar_widget)
        sidebar_layout.setContentsMargins(SPACE_NORMAL, SPACE_SECTION, SPACE_NORMAL, SPACE_SECTION)
        sidebar_layout.setSpacing(SPACE_COMPACT)

        # Compact brand header
        brand_row = QHBoxLayout()
        self._brand_logo = QLabel("LT")
        apply_role(self._brand_logo, "badge_primary")
        self._brand_title = QLabel("ListenTrace")
        apply_role(self._brand_title, "title")
        brand_row.addWidget(self._brand_logo)
        brand_row.addWidget(self._brand_title)
        brand_row.addStretch(1)
        sidebar_layout.addLayout(brand_row)

        sidebar_layout.addSpacing(SPACE_NORMAL)

        dir_caption = QLabel("DIRECTORY")
        apply_role(dir_caption, "caption")
        sidebar_layout.addWidget(dir_caption)

        # Left-aligned directory navigation items
        self._nav_library_button = QPushButton("Material Library")
        apply_role(self._nav_library_button, "nav_item")
        self._nav_library_button.setProperty("active", "true")
        # M13 Axis 5: due-frame evidence (Main Library board's DIRECTORY
        # sidebar) shows one icon per nav item -- book/clock/gear. `active`
        # is set once here and never toggled elsewhere in this window, so a
        # static "accent" tint (matching the active-state text color) is
        # correct with no re-tinting needed on click.
        set_button_icon(self._nav_library_button, "material", color_token="accent")
        self._nav_library_button.clicked.connect(self._on_nav_library_clicked)
        sidebar_layout.addWidget(self._nav_library_button)

        self._learning_history_button = QPushButton("Learning History")
        apply_role(self._learning_history_button, "nav_item")
        set_button_icon(self._learning_history_button, "clock", color_token="secondary")
        self._learning_history_button.clicked.connect(self._on_learning_history_clicked)
        sidebar_layout.addWidget(self._learning_history_button)

        self._settings_button = QPushButton("Settings...")
        apply_role(self._settings_button, "nav_item")
        set_button_icon(self._settings_button, "settings", color_token="secondary")
        self._settings_button.clicked.connect(self._on_open_settings)
        self._playback_settings_button = self._settings_button
        sidebar_layout.addWidget(self._settings_button)

        sidebar_layout.addStretch(1)

        # Sidebar footer status
        self._status_label = QLabel(f"Database ready — Schema version: {current_version(self._connection)}")
        apply_role(self._status_label, "caption")
        self._status_label.setToolTip(f"Database path: {self._db_path}")
        sidebar_layout.addWidget(self._status_label)

        self._main_splitter.addWidget(self._sidebar_widget)

        # -------------------------------------------------------------------
        # 2. Right Workspace (Toolbar + Ruled Archive List + Notebook Dossier)
        # -------------------------------------------------------------------
        self._workspace_widget = QWidget(self._main_splitter)
        workspace_layout = QVBoxLayout(self._workspace_widget)
        workspace_layout.setContentsMargins(SPACE_PAGE, SPACE_PAGE, SPACE_PAGE, SPACE_PAGE)
        workspace_layout.setSpacing(SPACE_SECTION)

        # Top Bar: View Title & Primary Actions
        header = make_surface_header(
            "Material Library",
            subtitle="Study archive and lined diagnosis workspace",
            title_role="page_title",
        )
        top_bar = header.top_bar
        self._view_title_label = header.title_label
        self._view_subtitle_label = header.subtitle_label
        header.title_row.addStretch(1)

        self._toggle_sidebar_button = QPushButton("Hide Sidebar")
        apply_role(self._toggle_sidebar_button, "quiet")
        set_button_icon(self._toggle_sidebar_button, "hide", color_token="secondary")
        self._toggle_sidebar_button.clicked.connect(self._on_toggle_sidebar)
        top_bar.addWidget(self._toggle_sidebar_button)

        self._toggle_archived_button = QPushButton("Show Archived")
        apply_role(self._toggle_archived_button, "secondary")
        set_button_icon(self._toggle_archived_button, "show", color_token="secondary")
        self._toggle_archived_button.clicked.connect(self._on_toggle_archived)
        top_bar.addWidget(self._toggle_archived_button)

        self._import_button = QPushButton("+ Import Material")
        apply_role(self._import_button, "secondary")
        self._import_button.clicked.connect(self._on_import_clicked)
        top_bar.addWidget(self._import_button)

        workspace_layout.addLayout(top_bar)

        # Workspace Content Splitter: Ruled Material Archive vs Lined Notebook Dossier
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.setChildrenCollapsible(False)

        # --- Ruled Material Archive Panel (Left) ---
        list_card, list_layout = make_card(None)
        list_header_row = QHBoxLayout()
        list_title = QLabel("STUDY ARCHIVE")
        apply_role(list_title, "caption")
        list_header_row.addWidget(list_title)
        list_header_row.addStretch(1)
        list_layout.addLayout(list_header_row)

        self._material_list = QListWidget()
        apply_role(self._material_list, "ruled_list")
        configure_long_text_list(self._material_list)
        self._material_list.currentItemChanged.connect(self._on_selection_changed)
        self._material_list.itemDoubleClicked.connect(self._on_material_double_clicked)
        list_layout.addWidget(self._material_list)
        self._content_splitter.addWidget(list_card)

        # --- Spiral Notebook Study Dossier Panel (Right) ---
        dossier_card, dossier_inner_layout = make_notebook_surface("Material Study Dossier", context_label="Study Dossier")

        # Ruled Metadata Rows Block (matching Frozen Module Wireframe)
        self._dossier_meta_widget = QWidget()
        dossier_meta_layout = QVBoxLayout(self._dossier_meta_widget)
        dossier_meta_layout.setContentsMargins(0, 0, 0, 0)
        dossier_meta_layout.setSpacing(0)

        self._dossier_empty_label = QLabel("Select a material in the archive to load its study dossier.")
        apply_role(self._dossier_empty_label, "ruled_row")
        self._dossier_empty_label.setWordWrap(True)
        dossier_meta_layout.addWidget(self._dossier_empty_label)

        self._row_title = _DossierRow("Title")
        self._row_status = _DossierRow("Status")
        self._row_language = _DossierRow("Language")
        self._row_media = _DossierRow("Media")
        self._row_sub_format = _DossierRow("Subtitle format")
        self._row_subtitle = _DossierRow("Subtitle")
        self._row_cue_count = _DossierRow("Cue count")

        self._dossier_rows = [
            self._row_title,
            self._row_status,
            self._row_language,
            self._row_media,
            self._row_sub_format,
            self._row_subtitle,
            self._row_cue_count,
        ]
        for row in self._dossier_rows:
            row.setVisible(False)
            dossier_meta_layout.addWidget(row)

        # Detail label preserved for backward compatibility in automated tests
        self._detail_label = QLabel("Select a material to see details.")
        self._detail_label.setWordWrap(True)
        self._detail_label.setVisible(False)
        dossier_meta_layout.addWidget(self._detail_label)

        # Direct layout ownership for scan-at-a-glance dossier metadata
        dossier_inner_layout.addWidget(self._dossier_meta_widget)

        # Visual Separator between Dossier Metadata and Action Launchpad
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setStyleSheet(f"background-color: {theme.css('notebook_rule_blue')}; max-height: 1px; margin: {SPACE_COMPACT}px 0px;")
        dossier_inner_layout.addWidget(divider)

        # Action Suite with Strict Hierarchy
        action_suite_box = QVBoxLayout()
        action_suite_box.setSpacing(SPACE_NORMAL)

        # Dominant Hero Action: Open Player
        self._open_player_button = QPushButton("Open Player (Listening Focus)")
        self._open_player_button.setProperty("hero", "true")
        apply_role(self._open_player_button, "primary")
        set_button_icon(self._open_player_button, "play", color_token="ink_on_accent")
        self._open_player_button.clicked.connect(self._on_open_player_clicked)
        action_suite_box.addWidget(self._open_player_button)

        # Secondary Actions: Guided Session & Practice
        practice_row = QHBoxLayout()
        self._start_intensive_button = QPushButton("Start Intensive")
        self._start_intensive_button.clicked.connect(self._on_start_intensive_clicked)
        self._resume_intensive_button = QPushButton("Resume Intensive")
        self._resume_intensive_button.clicked.connect(self._on_resume_intensive_clicked)
        self._quick_practice_button = QPushButton("Quick Practice")
        self._quick_practice_button.clicked.connect(self._on_quick_practice_clicked)
        self._shadowing_practice_button = QPushButton("Shadowing")
        self._shadowing_practice_button.clicked.connect(self._on_shadowing_practice_clicked)

        practice_row.addWidget(self._start_intensive_button)
        practice_row.addWidget(self._resume_intensive_button)
        practice_row.addWidget(self._quick_practice_button)
        practice_row.addWidget(self._shadowing_practice_button)
        action_suite_box.addLayout(practice_row)

        # Quiz Row
        quiz_row = QHBoxLayout()
        self._start_material_quiz_button = QPushButton("Material Quiz")
        self._start_material_quiz_button.clicked.connect(self._on_start_material_quiz_clicked)
        self._start_review_quiz_button = QPushButton("Review Quiz")
        self._start_review_quiz_button.clicked.connect(self._on_start_review_quiz_clicked)
        self._resume_quiz_button = QPushButton("Resume Quiz")
        self._resume_quiz_button.clicked.connect(self._on_resume_quiz_clicked)

        quiz_row.addWidget(self._start_material_quiz_button)
        quiz_row.addWidget(self._start_review_quiz_button)
        quiz_row.addWidget(self._resume_quiz_button)
        action_suite_box.addLayout(quiz_row)

        # Utilities Row
        util_row = QHBoxLayout()
        self._session_history_button = QPushButton("Session History")
        self._session_history_button.clicked.connect(self._on_session_history_clicked)
        self._quiz_history_button = QPushButton("Quiz History")
        self._quiz_history_button.clicked.connect(self._on_quiz_history_clicked)
        self._rename_button = QPushButton("Rename")
        self._rename_button.clicked.connect(self._on_rename_clicked)
        set_button_icon(self._rename_button, "rename", color_token="secondary")
        self._archive_restore_button = QPushButton("Archive")
        self._archive_restore_button.clicked.connect(self._on_archive_restore_clicked)
        set_button_icon(self._archive_restore_button, "archive", color_token="secondary")

        util_row.addWidget(self._session_history_button)
        util_row.addWidget(self._quiz_history_button)
        util_row.addWidget(self._rename_button)
        util_row.addWidget(self._archive_restore_button)
        action_suite_box.addLayout(util_row)

        # Destructive Action: Isolated at Bottom
        danger_row = QHBoxLayout()
        self._remove_button = QPushButton("Remove Material")
        apply_role(self._remove_button, "danger")
        set_button_icon(self._remove_button, "delete", color_token="danger")
        self._remove_button.clicked.connect(self._on_remove_clicked)
        danger_row.addStretch(1)
        danger_row.addWidget(self._remove_button)
        action_suite_box.addLayout(danger_row)

        dossier_inner_layout.addLayout(action_suite_box)
        dossier_inner_layout.addStretch(1)

        dossier_scroll = QScrollArea()
        dossier_scroll.setWidgetResizable(True)
        dossier_scroll.setFrameShape(QFrame.Shape.NoFrame)
        dossier_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dossier_scroll.setWidget(dossier_card)
        self._content_splitter.addWidget(dossier_scroll)

        # Configure Splitter Ratios (List 10 : Inspector 12)
        self._content_splitter.setStretchFactor(0, 10)
        self._content_splitter.setStretchFactor(1, 12)
        workspace_layout.addWidget(self._content_splitter, 1)

        # Error Banner
        self._error_label = QLabel("")
        apply_role(self._error_label, "error")
        self._error_label.setWordWrap(True)
        workspace_layout.addWidget(self._error_label)

        self._main_splitter.addWidget(self._workspace_widget)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([190, 770])

        root_layout.addWidget(self._main_splitter)
        self.setCentralWidget(central)

    def _apply_presentation(self) -> None:
        """Assign button roles for MainWindow."""
        apply_role(self._status_label, "caption")
        apply_role(self._open_player_button, "primary")
        apply_role(self._import_button, "secondary")
        apply_role(self._toggle_archived_button, "secondary")
        apply_role(self._toggle_sidebar_button, "quiet")
        apply_role(self._start_intensive_button, "secondary")
        apply_role(self._resume_intensive_button, "secondary")
        apply_role(self._shadowing_practice_button, "secondary")
        apply_role(self._quick_practice_button, "secondary")
        apply_role(self._start_material_quiz_button, "secondary")
        apply_role(self._start_review_quiz_button, "secondary")
        apply_role(self._resume_quiz_button, "secondary")
        apply_role(self._session_history_button, "quiet")
        apply_role(self._quiz_history_button, "quiet")
        apply_role(self._rename_button, "quiet")
        apply_role(self._archive_restore_button, "quiet")
        apply_role(self._remove_button, "danger")

    def _on_nav_library_clicked(self) -> None:
        if self._showing_archived:
            self._showing_archived = False
            self._toggle_archived_button.setText("Show Archived")
            self._view_title_label.setText("Material Library")
            self.refresh_library()

    def _on_toggle_sidebar(self) -> None:
        """Collapse or expand the navigation sidebar, persisting the preference."""
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        if self._sidebar_widget.isVisible():
            sizes = self._main_splitter.sizes()
            if sizes and sizes[0] > 0:
                self._last_sidebar_width = sizes[0]
                settings.setValue(_SETTING_SIDEBAR_WIDTH, self._last_sidebar_width)
            self._sidebar_widget.setVisible(False)
            self._sidebar_collapsed = True
            settings.setValue(_SETTING_SIDEBAR_COLLAPSED, True)
            self._toggle_sidebar_button.setText("Show Sidebar")
            set_button_icon(self._toggle_sidebar_button, "show", color_token="secondary")
        else:
            self._sidebar_widget.setVisible(True)
            restore_w = self._last_sidebar_width if self._last_sidebar_width > 50 else _DEFAULT_SIDEBAR_WIDTH
            self._main_splitter.setSizes([restore_w, 770])
            self._sidebar_collapsed = False
            settings.setValue(_SETTING_SIDEBAR_COLLAPSED, False)
            self._toggle_sidebar_button.setText("Hide Sidebar")
            set_button_icon(self._toggle_sidebar_button, "hide", color_token="secondary")

    def refresh_library(self) -> None:
        # M14 Corrective Batch A (A1): preserve selection by stable material
        # identity, not by row index/title -- a rebuilt list has neither. If
        # the previously selected material isn't in the rebuilt list (e.g. it
        # was archived/restored/removed, so it correctly left this view), no
        # item below matches and selection is simply left empty, which is the
        # correct "expected disappearance" behavior for those actions.
        previously_selected_id = self._selected_material_id()
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
            self._dossier_empty_label.setText("Select a material in the archive to load its study dossier.")
            self._dossier_empty_label.setVisible(True)
            for row in self._dossier_rows:
                row.setVisible(False)
            self._detail_label.setText("Select a material to see details.")
            self._detail_label.setToolTip("")
            return

        for material in materials:
            label = material.title
            if not material.media_available:
                label += "  [media missing]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, material.id)
            # M13 Due-Frame-First Visual Polish, Axis 5: the approved
            # due-frame board gives every Study Archive row its own small
            # status marker rather than plain text alone -- never the only
            # signal (the "[media missing]" text above still carries that
            # state on its own).
            if not material.media_available:
                item.setIcon(get_icon("warning", color_token="danger"))
            elif self._showing_archived:
                item.setIcon(get_icon("archive", color_token="secondary"))
            else:
                item.setIcon(get_icon("material", color_token="accent"))
            self._material_list.addItem(item)
            if previously_selected_id is not None and material.id == previously_selected_id:
                self._material_list.setCurrentItem(item)

    def _selected_material_id(self) -> int | None:
        item = self._material_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        material_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if material_id is None:
            self._set_action_buttons_enabled(False)
            self._dossier_empty_label.setText("Select a material in the archive to load its study dossier.")
            self._dossier_empty_label.setVisible(True)
            for row in self._dossier_rows:
                row.setVisible(False)
            self._detail_label.setText("Select a material to see details.")
            self._detail_label.setToolTip("")
            return

        self._set_action_buttons_enabled(True)
        try:
            detail = library.get_material_detail(self._connection, material_id)
        except MaterialNotFoundError:
            self._dossier_empty_label.setText("This material no longer exists.")
            self._dossier_empty_label.setVisible(True)
            for row in self._dossier_rows:
                row.setVisible(False)
            self._detail_label.setText("This material no longer exists.")
            self._detail_label.setToolTip("")
            self.refresh_library()
            return

        self._archive_restore_button.setText(
            "Restore" if detail.status == MaterialStatus.ARCHIVED.value else "Archive"
        )

        subtitle_display = Path(detail.subtitle_source_path).name if detail.subtitle_source_path else "(none)"
        sub_missing = detail.subtitle_source_path is not None and not detail.subtitle_available
        if sub_missing:
            subtitle_display += "  [MISSING]"

        media_display = Path(detail.media_path).name
        media_missing = not detail.media_available
        if media_missing:
            media_display += "  [MISSING]"

        # Populate structured 7-row ruled dossier metadata
        self._dossier_empty_label.setVisible(False)
        self._row_title.set_value(detail.title)
        self._row_status.set_value(detail.status)
        self._row_language.set_value(detail.language or "(not set)")
        self._row_media.set_value(media_display, is_missing=media_missing)
        self._row_sub_format.set_value(detail.subtitle_format or "(none)")
        self._row_subtitle.set_value(subtitle_display, is_missing=sub_missing)
        self._row_cue_count.set_value(str(detail.cue_count))
        for row in self._dossier_rows:
            row.setVisible(True)

        lines = [
            f"Title: {detail.title}",
            f"Status: {detail.status}",
            f"Language: {detail.language or '(not set)'}",
            media_line := (f"Media: {media_display}"),
            f"Subtitle format: {detail.subtitle_format or '(none)'}",
            subtitle_line := (f"Subtitle: {subtitle_display}"),
            f"Cue count: {detail.cue_count}",
        ]
        self._detail_label.setText("\n".join(lines))
        tooltip_lines = [
            f"Media path: {detail.media_path}",
            f"Subtitle path: {detail.subtitle_source_path or '(none)'}",
        ]
        self._detail_label.setToolTip("\n".join(tooltip_lines))
        self._dossier_meta_widget.setToolTip("\n".join(tooltip_lines))

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
            self._resume_intensive_button.setToolTip("Select a material to check for an active session.")
            self._resume_quiz_button.setToolTip("Select a material to check for an active quiz.")
            return
        active = practice_session_service.find_active_session(self._connection, material_id)
        self._resume_intensive_button.setEnabled(active is not None)
        self._resume_intensive_button.setToolTip(
            "" if active is not None else "No active Intensive Practice session for this material."
        )
        active_quizzes = quiz_service.find_active_quizzes_for_material(self._connection, material_id)
        self._resume_quiz_button.setEnabled(len(active_quizzes) > 0)
        self._resume_quiz_button.setToolTip(
            "" if active_quizzes else "No active quiz for this material."
        )

    def _on_import_clicked(self) -> None:
        dialog = ImportDialog(self._connection, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_library()

    def _on_open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self._connection, self)
            self._playback_settings_dialog = self._settings_dialog
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_open_playback_settings(self) -> None:
        self._on_open_settings()

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
        self._learning_history_window = LearningHistoryWindow(
            self._connection, self._recordings_dir, self, initial_material_id=self._selected_material_id()
        )
        self._learning_history_window.show()

    def _on_toggle_archived(self) -> None:
        self._showing_archived = not self._showing_archived
        self._toggle_archived_button.setText(
            "Show Active" if self._showing_archived else "Show Archived"
        )
        self._view_title_label.setText(
            "Archived Materials" if self._showing_archived else "Material Library"
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
            stripped_title = new_title.strip()
            library.rename_material(self._connection, material_id, stripped_title)
            # M14 Corrective Batch A (A2): notify already-open dependent
            # windows (Player/Guided Session/Quiz/Quick Practice/Shadowing)
            # so their stale window title/header presentation refreshes
            # without requiring them to be closed and reopened.
            material_metadata_bus.material_renamed.emit(material_id, stripped_title)
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
            recording_change_bus.material_changed.emit(material_id)
            self.refresh_library()

    def show_error(self, message: str) -> None:
        self._error_label.setText(message)

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPixmap, QTextCursor
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import LoopMode, PlayerTick
from listentrace.application.dto.saved_item_results import SavedItemNeedsConfirmation
from listentrace.application.errors import (
    AnnotationNotFoundError,
    AnnotationValidationError,
    CueNotFoundError,
    QuickPracticeValidationError,
    SavedItemNotFoundError,
    SavedItemValidationError,
)
from listentrace.application.services import annotation_service, cue_note_service
from listentrace.application.services import cue_workspace_service as workspace_service
from listentrace.application.services import label_preference_service
from listentrace.application.services import loop_grace_service
from listentrace.application.services import quick_practice_service
from listentrace.application.services import saved_language_item_service as item_service
from listentrace.application.services.player_session import PlayerSession
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.saved_item_type import SavedItemType
from listentrace.domain.services.text_range import whole_cue_range
from listentrace.infrastructure.appdata import get_recordings_dir
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.ui import theme
from listentrace.ui.annotation_highlighting import UNKNOWN_LABEL_COLOR, apply_range_highlighting
from listentrace.ui.text_offset_conversion import (
    SurrogatePairOffsetError,
    codepoint_index_to_qt_offset,
    qt_offset_to_codepoint_index,
)
from listentrace.ui.theme import SPACE_COMPACT, SPACE_NORMAL, SPACE_PAGE, SPACE_SECTION, apply_role, apply_surface
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.widgets.notebook_paper import GrainedDeskWidget, RuledPaperFrame, RuledTextEdit
from listentrace.ui.windows.label_color_dialog import LabelColorDialog
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog

_SEEK_STEP_MS = 5000
# Milestone 11: sourced from theme.py's dedicated product-semantic tokens
# (never a generic accent color) rather than a locally hardcoded literal --
# these two names are re-exported unchanged, since guided_session_window.py
# and quick_practice_window.py import _OVERLAP_HIGHLIGHT/_color_badge_icon
# directly from this module (see _open_quick_practice's docstring below).
_ACTIVE_CUE_HIGHLIGHT = theme.qcolor("cue_active")
_OVERLAP_HIGHLIGHT = theme.qcolor("text_overlap")
_BADGE_SIZE = 12
# M13 Axis 7: the Transcript & Cues list's two visible columns (Timetable /
# Cue Text) -- fixed so every row's timestamp column lines up under the
# header regardless of that row's own timestamp/text length, per the
# Product Owner's explicit "real two-column table, not concatenated list
# rows" requirement.
_CUE_MARKER_COLUMN_WIDTH_PX = 14
_CUE_TIME_COLUMN_WIDTH_PX = 92
# Must mirror the vertical chrome `QListWidget[role="ruled_list_notebook"]
# ::item` paints around every row in theme.py: padding-top + padding-bottom
# (SPACE_NORMAL each) + border-bottom (2px) + margin-bottom (2px). Distinct
# from `theme.RULED_LIST_ITEM_VERTICAL_CHROME_PX`, which is the *different*
# `role="ruled_list"` role's own chrome -- the two roles' QSS numbers are
# not the same, so this list needs its own constant rather than reusing
# that helper's.
_CUE_ROW_VERTICAL_CHROME_PX = (SPACE_NORMAL * 2) + 2 + 2


class _CueTranscriptRow(QWidget):
    """One `Timetable | Cue Text` row of the Player's Transcript & Cues
    table (M13 Axis 7). A real `QListWidgetItem.setItemWidget()` row --
    not a single concatenated string -- so the timestamp and cue text
    render as two genuinely separate, aligned columns under the
    `Timetable`/`Cue Text` header built alongside `_build_workspace_panel`.

    `set_active()` renders the currently-playing-cue marker (a leading ▶,
    the same non-color indicator the old single-string row used) directly
    on this row, since a widget-hosted `QListWidgetItem` no longer paints
    its own `item.setText()` content.
    """

    def __init__(self, time_text: str, cue_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SPACE_NORMAL)

        self._marker_label = QLabel("")
        self._marker_label.setFixedWidth(_CUE_MARKER_COLUMN_WIDTH_PX)
        row_layout.addWidget(self._marker_label)

        self._time_label = QLabel(time_text)
        apply_role(self._time_label, "monospace")
        self._time_label.setFixedWidth(_CUE_TIME_COLUMN_WIDTH_PX)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(self._time_label)

        self._text_label = QLabel(cue_text)
        self._text_label.setWordWrap(True)
        apply_role(self._text_label, "transcript_cue")
        row_layout.addWidget(self._text_label, 1)

    def set_active(self, active: bool) -> None:
        self._marker_label.setText("▶" if active else "")


def _is_text_entry_widget(widget: object) -> bool:
    return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))


def _format_time(ms: int) -> str:
    total_seconds = max(ms, 0) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _color_badge_icon(color_hex: str) -> QIcon:
    pixmap = QPixmap(_BADGE_SIZE, _BADGE_SIZE)
    pixmap.fill(QColor(color_hex))
    return QIcon(pixmap)


class PlayerWindow(QMainWindow):
    """M13 Notebook Study Desk Window -- an open two-page learning journal.

    Target Architecture:
    - Top Level: a fixed (non-scrolling) top bar and horizontal QSplitter with
      three panes: the media study page, a fixed-width spiral binding strip,
      and the transcript/annotation notebook page. The media/playback context
      is always visible -- there is no outer QScrollArea around it.
    - Left page: media viewport in a warm paper frame, a quiet status strip,
      the seek timeline, and playback/loop/quick-practice controls grouped into
      compact spiral mini-notebook cards.
    - Right page: Transcript & Cues as a ruled study sheet, and an Annotation
      Notebook (Annotate / Cue Note / Save Item) below it, wrapped in its own
      local QScrollArea so working in it never scrolls the media page away.
    - Warm cream/paper surfaces throughout with pale-blue ruled lines; the
      media viewport itself may remain dark, but the surrounding chrome does not.
    """

    def __init__(
        self,
        load_result: PlayerLoadResult,
        connection: sqlite3.Connection,
        parent: QWidget | None = None,
        initial_cue_index: int | None = None,
    ) -> None:
        super().__init__(parent)
        material = load_result.material
        self.setWindowTitle(f"ListenTrace — {material.title}")
        self.resize(1060, 720)
        # M13 Notebook Study Desk: the three side-by-side mini-notebook control
        # cards genuinely need more horizontal room than the old single stacked
        # control card did. 880px caused real clipping/overflow under the new
        # architecture (measured), so the practical floor moves up with it.
        # The height floor is set later, once the layout below is fully
        # built -- see the `setMinimumSize` call near the end of this method.
        self.setMinimumWidth(1040)

        self._material = material
        self._connection = connection
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(connection, material.id)
        self._session = PlayerSession(load_result.cues, loop_end_grace_ms=grace_ms)
        self._playback = PlaybackController(self)
        self._seeking_via_slider = False
        self._playback_usable = True
        self._editing_cue_index: int | None = None
        self._editing_annotation_id: int | None = None
        self._editing_item_id: int | None = None
        self._quick_practice_window: QWidget | None = None
        self._loop_settings_dialog: MaterialLoopSettingsDialog | None = None
        loop_grace_change_bus.global_default_changed.connect(self._on_loop_grace_global_default_changed)
        loop_grace_change_bus.material_override_changed.connect(self._on_loop_grace_material_override_changed)

        central = GrainedDeskWidget()
        apply_surface(central, "paper")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(SPACE_PAGE, SPACE_PAGE, SPACE_PAGE, SPACE_PAGE)
        root_layout.setSpacing(SPACE_SECTION)

        # -------------------------------------------------------------------
        # 1. Top Bar (Context Header & Return Action)
        # -------------------------------------------------------------------
        header = theme.make_surface_header(
            material.title,
            subtitle="Study Desk — Synchronized playback & cue journal",
            chips=[
                ("VIDEO" if material.media_kind == "video" else "AUDIO", "badge_primary"),
                (f"{len(self._session.cues)} CUES", "badge_secondary"),
            ],
        )
        top_bar = header.top_bar
        header.title_row.addStretch(1)

        return_button = QPushButton("Return to Library")
        apply_role(return_button, "quiet")
        return_button.clicked.connect(self.close)
        top_bar.addWidget(return_button)
        root_layout.addLayout(top_bar)

        # -------------------------------------------------------------------
        # 2. Main Horizontal Splitter (Media Study Page | Binding | Notebook Page)
        # -------------------------------------------------------------------
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)
        # The app-wide splitter handle is a deliberately thin 1px seam; that's
        # too narrow a drag target here where the visual binding strip (not
        # the handle) carries the seam's visual weight. Widen just this
        # splitter's hit target via a scoped role/QSS rule rather than
        # touching the global QSplitter::handle rule used everywhere else.
        apply_role(self._main_splitter, "player_split")

        # === LEFT PANEL: Media Study Page ===
        self._cinema_stage_widget = QWidget(self._main_splitter)
        apply_surface(self._cinema_stage_widget, "paper")
        cinema_layout = QVBoxLayout(self._cinema_stage_widget)
        cinema_layout.setContentsMargins(0, 0, 0, 0)
        cinema_layout.setSpacing(SPACE_NORMAL)

        # Media Frame (viewport placed on the study desk)
        stage_card, stage_layout = theme.make_media_frame()
        if material.media_kind == "video":
            self._video_widget: QVideoWidget | None = QVideoWidget()
            self._video_widget.setMinimumHeight(240)
            self._playback.set_video_output(self._video_widget)
            stage_layout.addWidget(self._video_widget)
            self._audio_placeholder: QLabel | None = None
        else:
            self._video_widget = None
            self._audio_placeholder = QLabel(f"{material.title}\n00:00 / 00:00")
            self._audio_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._audio_placeholder.setMinimumHeight(120)
            apply_role(self._audio_placeholder, "media_placeholder")
            stage_layout.addWidget(self._audio_placeholder)
        # M13 Axis 7: give the media viewport the stretch instead of leaving
        # it to a trailing addStretch() below -- the right (Transcript/
        # Annotation) column's own natural content height was setting the
        # whole window's height, so any leftover vertical space used to sit
        # as dead blank space beneath the mini-notebook button row instead
        # of growing the one region actually meant to use it.
        cinema_layout.addWidget(stage_card, 1)

        # Quiet Active Subtitle / Status Strip below the media frame
        self._active_subtitle_hud = QLabel("[Ready to play]")
        self._active_subtitle_hud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._active_subtitle_hud.setWordWrap(True)
        apply_role(self._active_subtitle_hud, "study_status_strip")
        cinema_layout.addWidget(self._active_subtitle_hud)

        # Timeline Scrubber Strip
        scrubber_card, scrubber_layout = theme.make_card()
        seek_row = QHBoxLayout()
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)
        self._time_label = QLabel("00:00 / 00:00")
        apply_role(self._time_label, "monospace")
        seek_row.addWidget(self._seek_slider, 1)
        seek_row.addWidget(self._time_label)
        scrubber_layout.addLayout(seek_row)
        cinema_layout.addWidget(scrubber_card)

        # Mini Spiral Notebook Control Cards: Playback | Loop & Practice | Utility
        notebooks_row = QHBoxLayout()
        notebooks_row.setSpacing(SPACE_COMPACT)

        self._playback_notebook, playback_layout = theme.make_mini_notebook("Playback")
        playback_card = self._playback_notebook
        self._play_pause_button = QPushButton("Play")
        self._play_pause_button.setMinimumHeight(36)
        self._play_pause_button.clicked.connect(self._on_play_pause_clicked)
        apply_role(self._play_pause_button, "primary")
        playback_layout.addWidget(self._play_pause_button)

        self._replay_button = QPushButton("Replay Cue")
        self._replay_button.clicked.connect(self._on_replay_cue)
        apply_role(self._replay_button, "secondary")
        playback_layout.addWidget(self._replay_button)

        self._previous_button = QPushButton("Previous Cue")
        self._previous_button.clicked.connect(self._on_previous_cue)
        apply_role(self._previous_button, "secondary")
        playback_layout.addWidget(self._previous_button)

        self._next_button = QPushButton("Next Cue")
        self._next_button.clicked.connect(self._on_next_cue)
        apply_role(self._next_button, "secondary")
        playback_layout.addWidget(self._next_button)

        volume_row = QHBoxLayout()
        vol_label = QLabel("Volume:")
        apply_role(vol_label, "ui_label")
        volume_row.addWidget(vol_label)
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_row.addWidget(self._volume_slider, 1)
        playback_layout.addLayout(volume_row)

        self._mute_button = QPushButton("Mute")
        self._mute_button.clicked.connect(self._on_toggle_mute)
        apply_role(self._mute_button, "quiet")
        playback_layout.addWidget(self._mute_button)
        playback_layout.addStretch(1)
        notebooks_row.addWidget(playback_card, 1)

        self._loop_practice_notebook, loop_layout = theme.make_mini_notebook("Loop & Practice")
        loop_card = self._loop_practice_notebook
        self._loop_cue_button = QPushButton("Loop Cue")
        self._loop_cue_button.clicked.connect(self._on_loop_cue_clicked)
        apply_role(self._loop_cue_button, "secondary")
        loop_layout.addWidget(self._loop_cue_button)

        self._loop_range_button = QPushButton("Loop Selection")
        self._loop_range_button.clicked.connect(self._on_loop_range_clicked)
        apply_role(self._loop_range_button, "secondary")
        loop_layout.addWidget(self._loop_range_button)

        # Two-line button text (same words, wrapped) keeps these cards
        # hand-sized instead of the single un-wrapped line forcing the whole
        # mini-notebook card wider than its neighbors at practical window widths.
        self._quick_practice_this_cue_button = QPushButton("Quick Practice\nThis Cue")
        self._quick_practice_this_cue_button.clicked.connect(self._on_quick_practice_this_cue_clicked)
        apply_role(self._quick_practice_this_cue_button, "secondary")
        loop_layout.addWidget(self._quick_practice_this_cue_button)

        self._quick_practice_selected_button = QPushButton("Quick Practice\nSelected Cues")
        self._quick_practice_selected_button.clicked.connect(self._on_quick_practice_selected_clicked)
        apply_role(self._quick_practice_selected_button, "secondary")
        loop_layout.addWidget(self._quick_practice_selected_button)
        loop_layout.addStretch(1)
        notebooks_row.addWidget(loop_card, 1)

        self._utility_notebook, utility_layout = theme.make_mini_notebook("Utility")
        utility_card = self._utility_notebook
        self._loop_settings_button = QPushButton("Loop Settings...")
        self._loop_settings_button.clicked.connect(self._on_open_loop_settings)
        apply_role(self._loop_settings_button, "quiet")
        utility_layout.addWidget(self._loop_settings_button)

        self._label_colors_button = QPushButton("Label Colors...")
        self._label_colors_button.clicked.connect(self._on_open_label_colors)
        apply_role(self._label_colors_button, "quiet")
        utility_layout.addWidget(self._label_colors_button)

        self._transcript_button = QPushButton("Hide Transcript")
        self._transcript_button.clicked.connect(self._on_toggle_transcript)
        apply_role(self._transcript_button, "secondary")
        theme.set_button_icon(self._transcript_button, "hide", color_token="secondary")
        utility_layout.addWidget(self._transcript_button)
        utility_layout.addStretch(1)
        notebooks_row.addWidget(utility_card, 1)

        cinema_layout.addLayout(notebooks_row)

        self._main_splitter.addWidget(self._cinema_stage_widget)

        # === CENTER: Spiral Binding (open-book seam) ===
        self._spiral_binding_strip = theme.make_spiral_binding_strip()
        self._main_splitter.addWidget(self._spiral_binding_strip)
        self._main_splitter.setCollapsible(1, False)

        # === RIGHT PANEL: Transcript & Annotation Notebook ===
        self._right_workspace_widget = QWidget(self._main_splitter)
        apply_surface(self._right_workspace_widget, "paper")
        right_layout = QVBoxLayout(self._right_workspace_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACE_NORMAL)

        # Transcript & Cues study sheet
        transcript_notebook, transcript_content = theme.make_notebook_surface(
            context_label="Transcript & Cues"
        )

        transcript_header_row = QHBoxLayout()
        self._return_to_playing_button = QPushButton("Return to Playing Cue")
        apply_role(self._return_to_playing_button, "quiet")
        self._return_to_playing_button.clicked.connect(self._on_return_to_playing_clicked)
        self._return_to_playing_button.setVisible(False)
        transcript_header_row.addStretch(1)
        transcript_header_row.addWidget(self._return_to_playing_button)
        transcript_content.addLayout(transcript_header_row)

        # M13 Axis 7: a real `Timetable | Cue Text` column header, aligned
        # with each row's own fixed-width timestamp column below.
        table_header_row = QHBoxLayout()
        table_header_row.setContentsMargins(0, 0, 0, 0)
        table_header_row.setSpacing(SPACE_NORMAL)
        marker_header_spacer = QLabel("")
        marker_header_spacer.setFixedWidth(_CUE_MARKER_COLUMN_WIDTH_PX)
        table_header_row.addWidget(marker_header_spacer)
        timetable_header = QLabel("Timetable")
        apply_role(timetable_header, "section_header")
        timetable_header.setFixedWidth(_CUE_TIME_COLUMN_WIDTH_PX)
        table_header_row.addWidget(timetable_header)
        cue_text_header = QLabel("Cue Text")
        apply_role(cue_text_header, "section_header")
        table_header_row.addWidget(cue_text_header, 1)
        transcript_content.addLayout(table_header_row)

        # Cue Card Stream List -- a real two-column table row per cue
        # (`_CueTranscriptRow`), not a single concatenated "[time] text"
        # string, so Timetable and Cue Text render as genuinely separate
        # columns beneath the header above.
        self._cue_list = QListWidget()
        apply_role(self._cue_list, "ruled_list_notebook")
        self._cue_list.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self._cue_list.setMinimumHeight(160)
        self._cue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cue_rows: list[_CueTranscriptRow] = []
        for cue in self._session.cues:
            time_text = f"{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}"
            row = _CueTranscriptRow(time_text, cue.text)
            item = QListWidgetItem()
            hint = row.sizeHint()
            item.setSizeHint(QSize(hint.width(), hint.height() + _CUE_ROW_VERTICAL_CHROME_PX))
            self._cue_list.addItem(item)
            self._cue_list.setItemWidget(item, row)
            self._cue_rows.append(row)
        self._cue_list.currentItemChanged.connect(self._on_editing_cue_changed)
        transcript_content.addWidget(self._cue_list, 1)
        right_layout.addWidget(transcript_notebook, 1)

        self._follow_playback = True
        self._programmatic_scroll = False
        self._cue_list.verticalScrollBar().valueChanged.connect(self._on_transcript_scrollbar_changed)

        # Annotation Notebook (Annotate / Cue Note / Save Item). Wrapped in its
        # own local QScrollArea rather than the whole Player: this is the
        # piece whose fields/buttons historically compressed to unreadable
        # slivers in a short window (M12 Round 2 fix), and it's also the only
        # piece that actually needs to scroll -- keeping that scroll local
        # means working in it never carries the media/playback context (the
        # left page) off-screen with it.
        annotation_notebook, annotation_content = theme.make_notebook_surface(
            context_label="Annotation Notebook"
        )
        self._workspace_panel = self._build_workspace_panel()
        annotation_content.addWidget(self._workspace_panel)

        self._annotation_scroll_area = QScrollArea()
        self._annotation_scroll_area.setWidgetResizable(True)
        self._annotation_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._annotation_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._annotation_scroll_area.setWidget(annotation_notebook)
        right_layout.addWidget(self._annotation_scroll_area)

        self._main_splitter.addWidget(self._right_workspace_widget)

        # Configure Splitter Ratio (Left Page 11 : Binding 0 : Right Page 9)
        self._main_splitter.setStretchFactor(0, 11)
        self._main_splitter.setStretchFactor(1, 0)
        self._main_splitter.setStretchFactor(2, 9)
        self._main_splitter.setSizes([580, 28, 440])
        root_layout.addWidget(self._main_splitter, 1)

        # -------------------------------------------------------------------
        # 3. Status Banners (Error & Feedback)
        # -------------------------------------------------------------------
        self._status_label = QLabel("")
        apply_role(self._status_label, "error")
        self._status_label.setWordWrap(True)
        root_layout.addWidget(self._status_label)

        self._workspace_status_label = QLabel("")
        apply_role(self._workspace_status_label, "error")
        self._workspace_status_label.setWordWrap(True)
        root_layout.addWidget(self._workspace_status_label)

        # No outer QScrollArea: the top bar and the two-page notebook
        # workspace stay fixed/always-visible (the media/playback context
        # must never scroll off-screen while the learner works in the
        # Annotation Notebook -- see the local QScrollArea around it above).
        self.setCentralWidget(central)
        apply_surface(self, "paper")

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.duration_changed.connect(self._on_duration_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)

        self._playback.set_volume(self._volume_slider.value() / 100)
        self._playback.load(material.media_path)

        self._apply_presentation()
        self._set_workspace_form_enabled(False)

        # Lock in the real minimum height Qt's own layout just computed for
        # everything built above (video/audio viewport, status strip,
        # timeline, mini-notebooks, transcript, annotation notebook) as a
        # hard floor, alongside the fixed 1040px width reservation. A guessed
        # height constant here previously under-stated the media study
        # page's real requirement for a video-kind Player specifically (an
        # audio-kind Player's shorter placeholder made the shortfall easy to
        # miss) -- letting Qt supply the number keeps this self-healing
        # instead of a magic constant that can silently drift out of sync
        # with the content again.
        self.setMinimumSize(1040, self.minimumSizeHint().height())

        if initial_cue_index is not None and 0 <= initial_cue_index < self._cue_list.count():
            self._cue_list.setCurrentRow(initial_cue_index)

    def _apply_presentation(self) -> None:
        """Button role assignments for reconstructed Player."""
        apply_role(self._play_pause_button, "primary")
        for button in (
            self._previous_button,
            self._next_button,
            self._replay_button,
            self._loop_cue_button,
            self._loop_range_button,
            self._transcript_button,
            self._quick_practice_this_cue_button,
            self._quick_practice_selected_button,
        ):
            apply_role(button, "secondary")
        for button in (
            self._mute_button,
            self._label_colors_button,
            self._loop_settings_button,
            self._return_to_playing_button,
        ):
            apply_role(button, "quiet")
        for button in (
            self._save_annotation_button,
            self._save_note_button,
            self._save_item_button,
        ):
            apply_role(button, "notebook_primary_action")
            theme.set_button_icon(button, "save", color_token="accent")
        for button in (
            self._update_annotation_button,
            self._update_item_button,
        ):
            apply_role(button, "notebook_action")
        for button in (
            self._delete_annotation_button,
            self._delete_note_button,
            self._delete_item_button,
        ):
            apply_role(button, "notebook_destructive_action")
            theme.set_button_icon(button, "delete", color_token="danger")

    # ---- workspace panel construction ----

    def _build_workspace_panel(self) -> QWidget:
        """Build the compact tabbed cue-tools panel below the cue stream.

        Three modes — Annotate, Cue Note, Save Item — are each a tab in a
        QTabWidget.  This eliminates the inner horizontal QSplitter that caused
        annotation/item controls to clip at ~1080 px whole-window width.
        """
        self._cue_tools_tabs = QTabWidget()
        apply_role(self._cue_tools_tabs, "notebook_tabs")

        # ---- Tab 1: Annotate ------------------------------------------------
        annotation_widget = RuledPaperFrame()
        apply_role(annotation_widget, "notebook_tab_page")
        annotation_column = QVBoxLayout(annotation_widget)
        annotation_column.setContentsMargins(4, 8, 4, 8)
        annotation_column.setSpacing(4)

        annot_header = QLabel("Editing cue transcript (select text to annotate):")
        annot_header.setWordWrap(True)
        apply_role(annot_header, "ui_label")
        annotation_column.addWidget(annot_header)

        self._editing_transcript_view = RuledTextEdit()
        self._editing_transcript_view.setReadOnly(True)
        self._editing_transcript_view.setMaximumHeight(90)
        self._editing_transcript_view.cursorPositionChanged.connect(
            self._on_transcript_cursor_moved
        )
        annotation_column.addWidget(self._editing_transcript_view)

        # A single horizontal row of all 5 category checkboxes doesn't fit
        # the Annotate tab's intrinsic width at ~1060-1080px whole-window
        # width (the right workspace pane is only ~250px wide, narrower than
        # a full-width surface) -- the last category(ies) clipped off the
        # right edge. A 2-column grid still clipped the longest label
        # ("connected reduced speech") at this pane width, so each category
        # gets its own row instead -- guaranteed to fit at any window width
        # since it never needs more than one label's worth of horizontal space.
        label_grid = QGridLayout()
        label_grid.setHorizontalSpacing(8)
        label_grid.setVerticalSpacing(2)
        self._label_checkboxes: dict[str, QCheckBox] = {}
        for index, label in enumerate(AnnotationLabel):
            checkbox = QCheckBox(label.value.replace("_", " "))
            apply_role(checkbox, "ui_label")
            checkbox.stateChanged.connect(self._on_label_checkbox_changed)
            self._label_checkboxes[label.value] = checkbox
            label_grid.addWidget(checkbox, index, 0)
        annotation_column.addLayout(label_grid)

        heard_as_row = QHBoxLayout()
        heard_as_lbl = QLabel("Heard as:")
        apply_role(heard_as_lbl, "ui_label")
        heard_as_row.addWidget(heard_as_lbl)
        self._heard_as_edit = QLineEdit()
        self._heard_as_edit.setEnabled(False)
        apply_role(self._heard_as_edit, "notebook_writing_field")
        heard_as_row.addWidget(self._heard_as_edit)
        annotation_column.addLayout(heard_as_row)

        note_row = QHBoxLayout()
        note_lbl = QLabel("Annotation note:")
        apply_role(note_lbl, "ui_label")
        note_row.addWidget(note_lbl)
        self._annotation_note_edit = QLineEdit()
        apply_role(self._annotation_note_edit, "notebook_writing_field")
        note_row.addWidget(self._annotation_note_edit)
        annotation_column.addLayout(note_row)

        self._save_annotation_button = QPushButton("Save Annotation")
        self._save_annotation_button.clicked.connect(self._on_save_annotation_clicked)
        annotation_column.addWidget(self._save_annotation_button)

        annotation_update_delete_row = QHBoxLayout()
        self._update_annotation_button = QPushButton("Update")
        self._update_annotation_button.clicked.connect(self._on_update_annotation_clicked)
        self._update_annotation_button.setEnabled(False)
        self._delete_annotation_button = QPushButton("Delete")
        self._delete_annotation_button.clicked.connect(self._on_delete_annotation_clicked)
        self._delete_annotation_button.setEnabled(False)
        annotation_update_delete_row.addWidget(self._update_annotation_button)
        annotation_update_delete_row.addWidget(self._delete_annotation_button)
        annotation_column.addLayout(annotation_update_delete_row)

        annots_on_cue_lbl = QLabel("Annotations on this cue:")
        annots_on_cue_lbl.setWordWrap(True)
        apply_role(annots_on_cue_lbl, "ui_label")
        annotation_column.addWidget(annots_on_cue_lbl)
        self._annotation_list = QListWidget()
        self._annotation_list.setMaximumHeight(80)
        self._annotation_list.currentItemChanged.connect(self._on_annotation_selected)
        annotation_column.addWidget(self._annotation_list)

        self._cue_tools_tabs.addTab(annotation_widget, "Annotate")

        # ---- Tab 2: Cue Note ------------------------------------------------
        note_widget = RuledPaperFrame()
        apply_role(note_widget, "notebook_tab_page")
        note_column = QVBoxLayout(note_widget)
        note_column.setContentsMargins(4, 8, 4, 8)
        note_column.setSpacing(4)

        cue_note_lbl = QLabel("Cue Note:")
        apply_role(cue_note_lbl, "ui_label")
        note_column.addWidget(cue_note_lbl)
        self._cue_note_edit = RuledTextEdit()
        self._cue_note_edit.setMaximumHeight(80)
        note_column.addWidget(self._cue_note_edit)
        note_buttons_row = QHBoxLayout()
        self._save_note_button = QPushButton("Save Note")
        self._save_note_button.clicked.connect(self._on_save_note_clicked)
        self._delete_note_button = QPushButton("Delete Note")
        self._delete_note_button.clicked.connect(self._on_delete_note_clicked)
        note_buttons_row.addWidget(self._save_note_button)
        note_buttons_row.addWidget(self._delete_note_button)
        note_column.addLayout(note_buttons_row)
        note_column.addStretch(1)

        self._cue_tools_tabs.addTab(note_widget, "Cue Note")

        # ---- Tab 3: Save Item -----------------------------------------------
        item_widget = RuledPaperFrame()
        apply_role(item_widget, "notebook_tab_page")
        item_column = QVBoxLayout(item_widget)
        item_column.setContentsMargins(4, 8, 4, 8)
        item_column.setSpacing(4)

        item_hdr = QLabel("Save Language Item")
        apply_role(item_hdr, "ui_label")
        item_column.addWidget(item_hdr)
        source_lock_note = QLabel(
            "Type, meaning, note, and context can be edited later. Source text/range is fixed once saved."
        )
        source_lock_note.setWordWrap(True)
        apply_role(source_lock_note, "caption")
        item_column.addWidget(source_lock_note)

        item_type_row = QHBoxLayout()
        type_lbl = QLabel("Type:")
        apply_role(type_lbl, "ui_label")
        item_type_row.addWidget(type_lbl)
        self._item_type_combo = QComboBox()
        for item_type in SavedItemType:
            self._item_type_combo.addItem(item_type.value.replace("_", " "), item_type.value)
        item_type_row.addWidget(self._item_type_combo)
        item_column.addLayout(item_type_row)

        meaning_row = QHBoxLayout()
        mean_lbl = QLabel("Meaning:")
        apply_role(mean_lbl, "ui_label")
        meaning_row.addWidget(mean_lbl)
        self._item_meaning_edit = QLineEdit()
        apply_role(self._item_meaning_edit, "notebook_writing_field")
        meaning_row.addWidget(self._item_meaning_edit)
        item_column.addLayout(meaning_row)

        item_note_row = QHBoxLayout()
        inote_lbl = QLabel("Note:")
        apply_role(inote_lbl, "ui_label")
        item_note_row.addWidget(inote_lbl)
        self._item_note_edit = QLineEdit()
        apply_role(self._item_note_edit, "notebook_writing_field")
        item_note_row.addWidget(self._item_note_edit)
        item_column.addLayout(item_note_row)

        context_lbl = QLabel("Context (editable):")
        apply_role(context_lbl, "ui_label")
        item_column.addWidget(context_lbl)
        self._item_context_edit = RuledTextEdit()
        self._item_context_edit.setMaximumHeight(52)
        item_column.addWidget(self._item_context_edit)

        self._save_item_button = QPushButton("Save Item")
        self._save_item_button.clicked.connect(self._on_save_item_clicked)
        item_column.addWidget(self._save_item_button)

        item_update_delete_row = QHBoxLayout()
        self._update_item_button = QPushButton("Update")
        self._update_item_button.clicked.connect(self._on_update_item_clicked)
        self._update_item_button.setEnabled(False)
        self._delete_item_button = QPushButton("Delete")
        self._delete_item_button.clicked.connect(self._on_delete_item_clicked)
        self._delete_item_button.setEnabled(False)
        item_update_delete_row.addWidget(self._update_item_button)
        item_update_delete_row.addWidget(self._delete_item_button)
        item_column.addLayout(item_update_delete_row)

        saved_on_cue_lbl = QLabel("Saved items on this cue:")
        saved_on_cue_lbl.setWordWrap(True)
        apply_role(saved_on_cue_lbl, "ui_label")
        item_column.addWidget(saved_on_cue_lbl)
        self._saved_items_list = QListWidget()
        self._saved_items_list.setMaximumHeight(80)
        self._saved_items_list.currentItemChanged.connect(self._on_saved_item_selected)
        item_column.addWidget(self._saved_items_list)

        self._cue_tools_tabs.addTab(item_widget, "Save Item")

        return self._cue_tools_tabs


    # ---- transport handlers ----

    def _on_play_pause_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
            self._play_pause_button.setText("Play")
        else:
            self._playback.play()
            self._play_pause_button.setText("Pause")

    def _apply_player_tick(self, tick: PlayerTick) -> None:
        if tick.restart_at_ms is not None:
            self._playback.restart_span(tick.restart_at_ms)
        elif tick.pause:
            self._playback.pause()
            self._play_pause_button.setText("Play")

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._session.on_position_changed(position_ms)
        self._apply_player_tick(tick)

        if not self._seeking_via_slider:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(position_ms)
            self._seek_slider.blockSignals(False)

        self._update_time_label(position_ms)
        self._update_active_cue_highlight()
        self._update_subtitle_hud(position_ms)

    def _update_subtitle_hud(self, position_ms: int) -> None:
        active_idx = self._session.active_cue_index
        if active_idx is not None and 0 <= active_idx < len(self._session.cues):
            cue = self._session.cues[active_idx]
            self._active_subtitle_hud.setText(cue.text)
        elif self._editing_cue_index is not None and 0 <= self._editing_cue_index < len(self._session.cues):
            cue = self._session.cues[self._editing_cue_index]
            self._active_subtitle_hud.setText(f"[Selected Cue] {cue.text}")
        else:
            self._active_subtitle_hud.setText("[Ready to play]")

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._seek_slider.setRange(0, max(duration_ms, 0))
        self._update_time_label(self._playback.position_ms)

    def _update_time_label(self, position_ms: int) -> None:
        text = f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}"
        self._time_label.setText(text)
        if self._audio_placeholder is not None:
            self._audio_placeholder.setText(f"{self._material.title}\n{text}")

    def _update_active_cue_highlight(self) -> None:
        """Highlight the currently-playing cue with background color AND a non-color prefix marker."""
        active_index = self._session.active_cue_index
        for i in range(self._cue_list.count()):
            item = self._cue_list.item(i)
            if item is None:
                continue
            is_active = i == active_index
            item.setBackground(_ACTIVE_CUE_HIGHLIGHT if is_active else QColor(0, 0, 0, 0))
            # Non-color indicator: the row widget renders its own leading ▶
            # marker (item.setText() has no visual effect once a widget is
            # attached via setItemWidget()).
            if 0 <= i < len(self._cue_rows):
                self._cue_rows[i].set_active(is_active)

        if self._follow_playback and active_index is not None:
            self._scroll_to_cue_if_needed(active_index)

    def _scroll_to_cue_if_needed(self, index: int) -> None:
        item = self._cue_list.item(index)
        if item is None:
            return
        item_rect = self._cue_list.visualItemRect(item)
        if self._cue_list.viewport().rect().contains(item_rect):
            return
        self._programmatic_scroll = True
        self._cue_list.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
        self._programmatic_scroll = False

    def _on_transcript_scrollbar_changed(self, _value: int) -> None:
        if self._programmatic_scroll or not self._follow_playback:
            return
        self._follow_playback = False
        self._return_to_playing_button.setVisible(True)

    def _on_return_to_playing_clicked(self) -> None:
        self._follow_playback = True
        self._return_to_playing_button.setVisible(False)
        if self._session.active_cue_index is not None:
            self._scroll_to_cue_if_needed(self._session.active_cue_index)

    def _on_slider_pressed(self) -> None:
        self._seeking_via_slider = True

    def _on_slider_released(self) -> None:
        self._playback.seek(self._seek_slider.value())
        self._seeking_via_slider = False

    def _navigation_anchor_index(self) -> int | None:
        if self._editing_cue_index is not None:
            return self._editing_cue_index
        return self._session.active_cue_index

    def _navigate_to_cue(self, new_index: int) -> None:
        self._programmatic_scroll = True
        self._cue_list.setCurrentRow(new_index)
        self._programmatic_scroll = False
        cue = self._session.cues[new_index]
        self._playback.seek(cue.start_ms)

    def _on_previous_cue(self) -> None:
        anchor = self._navigation_anchor_index()
        target = self._session.previous_cue_index(anchor)
        if target is not None:
            self._navigate_to_cue(target)

    def _on_next_cue(self) -> None:
        anchor = self._navigation_anchor_index()
        target = self._session.next_cue_index(anchor)
        if target is not None:
            self._navigate_to_cue(target)

    def _on_replay_cue(self) -> None:
        anchor = self._navigation_anchor_index()
        if anchor is None:
            anchor = 0
        seek_to = self._session.replay_cue(anchor)
        self._sync_loop_button_text()
        self._playback.seek(seek_to)
        self._playback.play()
        self._play_pause_button.setText("Pause")

    def _on_loop_cue_clicked(self) -> None:
        if self._session.loop_mode == LoopMode.CUE:
            self._session.cancel_loop()
            self._playback.cancel_pending_restart()
            self._sync_loop_button_text()
            return

        anchor = self._navigation_anchor_index()
        if anchor is None:
            anchor = 0
        seek_to = self._session.loop_cue(anchor)
        self._sync_loop_button_text()
        self._playback.seek(seek_to)
        self._playback.play()
        self._play_pause_button.setText("Pause")

    def _on_loop_range_clicked(self) -> None:
        if self._session.loop_mode == LoopMode.RANGE:
            self._session.cancel_loop()
            self._playback.cancel_pending_restart()
            self._sync_loop_button_text()
            return

        selected_items = self._cue_list.selectedItems()
        if not selected_items:
            return
        rows = [self._cue_list.row(it) for it in selected_items]
        start_index, end_index = min(rows), max(rows)
        seek_to = self._session.loop_range(start_index, end_index)
        self._sync_loop_button_text()
        self._playback.seek(seek_to)
        self._playback.play()
        self._play_pause_button.setText("Pause")

    def _on_loop_toggle_shortcut(self) -> None:
        if self._session.loop_mode != LoopMode.NONE:
            self._session.cancel_loop()
            self._playback.cancel_pending_restart()
            self._sync_loop_button_text()
        else:
            self._on_loop_cue_clicked()

    def _sync_loop_button_text(self) -> None:
        if self._session.loop_mode == LoopMode.CUE:
            self._loop_cue_button.setText("Stop Loop")
            self._loop_range_button.setText("Loop Selection")
        elif self._session.loop_mode == LoopMode.RANGE:
            self._loop_cue_button.setText("Loop Cue")
            self._loop_range_button.setText("Stop Range Loop")
        else:
            self._loop_cue_button.setText("Loop Cue")
            self._loop_range_button.setText("Loop Selection")

    def _on_toggle_transcript(self) -> None:
        self._session.transcript_visible = not self._session.transcript_visible
        visible = self._session.transcript_visible
        self._cue_list.setVisible(visible)
        self._transcript_button.setText("Hide Transcript" if visible else "Show Transcript")
        theme.set_button_icon(self._transcript_button, "hide" if visible else "show", color_token="secondary")
        self._refresh_editing_cue_panels()

    def _on_toggle_mute(self) -> None:
        is_muted = not self._playback.is_muted
        self._playback.set_muted(is_muted)
        self._mute_button.setText("Unmute" if is_muted else "Mute")

    def _on_volume_changed(self, value: int) -> None:
        self._playback.set_volume(value / 100)

    def _on_playback_error(self, message: str) -> None:
        self._status_label.setText(f"Playback error: {message}")
        self._playback_usable = False
        for widget in (
            self._play_pause_button,
            self._seek_slider,
            self._previous_button,
            self._next_button,
            self._replay_button,
            self._loop_cue_button,
            self._loop_range_button,
            self._volume_slider,
            self._mute_button,
        ):
            widget.setEnabled(False)

    def _on_end_of_media(self) -> None:
        tick = self._session.on_media_ended()
        self._apply_player_tick(tick)
        if tick.restart_at_ms is None:
            self._play_pause_button.setText("Play")

    def _on_open_label_colors(self) -> None:
        dialog = LabelColorDialog(self._connection, self)
        dialog.exec()
        self._refresh_annotation_presentation()

    def _on_open_loop_settings(self) -> None:
        if self._loop_settings_dialog is None:
            self._loop_settings_dialog = MaterialLoopSettingsDialog(
                self._connection, self._material.id, self._material.title, self
            )
        self._loop_settings_dialog.show()
        self._loop_settings_dialog.raise_()
        self._loop_settings_dialog.activateWindow()

    def _on_loop_grace_global_default_changed(self) -> None:
        self._refresh_loop_end_grace()

    def _on_loop_grace_material_override_changed(self, material_id: int) -> None:
        if material_id == self._material.id:
            self._refresh_loop_end_grace()

    def _refresh_loop_end_grace(self) -> None:
        grace_ms = loop_grace_service.effective_loop_end_grace_ms(self._connection, self._material.id)
        self._session.set_loop_end_grace_ms(grace_ms)

    def _selected_cue_indices(self) -> list[int]:
        return [self._cue_list.row(item) for item in self._cue_list.selectedItems()]

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _open_quick_practice(self, subtitle_cue_ids: list[int]) -> None:
        from listentrace.ui.windows.quick_practice_window import QuickPracticeWindow

        if self._quick_practice_window is not None:
            self._quick_practice_window.close()

        try:
            session = quick_practice_service.start_selected_session(
                self._connection, self._material.id, subtitle_cue_ids
            )
        except QuickPracticeValidationError as exc:
            self._show_status(str(exc))
            return
        assert session.id is not None
        self._quick_practice_window = QuickPracticeWindow(
            self._connection,
            PlayerLoadResult(material=self._material, cues=self._session.cues),
            session.id,
            get_recordings_dir(),
            self,
        )
        self._quick_practice_window.show()

    def _on_quick_practice_this_cue_clicked(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            self._show_status("Select a cue to Quick Practice first.")
            return
        self._open_quick_practice([cue.id])

    def _on_quick_practice_selected_clicked(self) -> None:
        indices = self._selected_cue_indices()
        if not indices:
            cue = self._current_editing_cue()
            indices = [self._editing_cue_index] if cue is not None else []
        if not indices:
            self._show_status("Select one or more cues to Quick Practice.")
            return
        cue_ids = [self._session.cues[i].id for i in indices if self._session.cues[i].id is not None]
        self._open_quick_practice(cue_ids)

    # ---- keyboard navigation ----

    def keyPressEvent(self, event: QKeyEvent) -> None:
        focus = QApplication.focusWidget()
        if focus is not None and _is_text_entry_widget(focus):
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()
        letter_shortcuts_active = not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier))

        if key == Qt.Key.Key_T and letter_shortcuts_active:
            self._on_toggle_transcript()
        elif key == Qt.Key.Key_Escape:
            self._session.cancel_loop()
            self._playback.cancel_pending_restart()
            self._sync_loop_button_text()
        elif not self._playback_usable:
            super().keyPressEvent(event)
        elif key == Qt.Key.Key_Space:
            self._on_play_pause_clicked()
        elif key == Qt.Key.Key_Left and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._on_previous_cue()
        elif key == Qt.Key.Key_Right and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._on_next_cue()
        elif key == Qt.Key.Key_Left:
            self._playback.seek(max(self._playback.position_ms - _SEEK_STEP_MS, 0))
        elif key == Qt.Key.Key_Right:
            self._playback.seek(self._playback.position_ms + _SEEK_STEP_MS)
        elif key == Qt.Key.Key_R and letter_shortcuts_active:
            self._on_replay_cue()
        elif key == Qt.Key.Key_L and letter_shortcuts_active:
            self._on_loop_toggle_shortcut()
        elif key == Qt.Key.Key_M and letter_shortcuts_active:
            self._on_toggle_mute()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._session.cancel_loop()
        self._playback.stop()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._resync_video_widget_geometry()

    def changeEvent(self, event) -> None:  # type: ignore[override]
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._resync_video_widget_geometry()

    def _resync_video_widget_geometry(self) -> None:
        """Force the media frame's layout to push a fresh, synchronous
        geometry to the video widget right away.

        `QVideoWidget` renders through a native window-container surface on
        Windows; Qt documents that such surfaces "stack on top of the widget
        hierarchy as an opaque box" and are not clipped by normal Qt sibling
        z-order/layout the way ordinary widgets are. Qt's own layout
        recalculation is normally *deferred* to the next event-loop
        iteration, which leaves a window during a maximize/restore
        transition (a compound, fast sequence of geometry changes) where the
        native surface can retain a stale, larger rect than the freshly
        computed layout cell -- observed as the video visually bleeding over
        the study-status strip immediately below it. `QLayout.activate()`
        forces that recalculation (and the resulting `setGeometry()` calls)
        to happen immediately instead of waiting for the deferred pass,
        closing that race. This is a Qt-layout-level containment fix, not a
        spacer/margin hack; real native-window compositing on Windows still
        needs human verification (see the M13 Player Notebook Primitive
        Hardening corrective's P1 report)."""
        if self._video_widget is None:
            return
        layout = self._cinema_stage_widget.layout()
        if layout is not None:
            layout.activate()
        self._video_widget.updateGeometry()

    # ---- editing cue / transcript workspace ----

    def _current_editing_cue(self):
        if self._editing_cue_index is None:
            return None
        return self._session.cues[self._editing_cue_index]

    def _show_workspace_status(self, message: str) -> None:
        self._workspace_status_label.setText(message)

    def _on_editing_cue_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._editing_cue_index = None
            self._set_workspace_form_enabled(False)
            return
        self._editing_cue_index = self._cue_list.row(current)
        self._set_workspace_form_enabled(True)
        self._refresh_editing_cue_panels()
        self._update_subtitle_hud(self._playback.position_ms)

    def _set_workspace_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self._save_annotation_button,
            self._save_note_button,
            self._delete_note_button,
            self._save_item_button,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self._update_annotation_button.setEnabled(False)
            self._delete_annotation_button.setEnabled(False)
            self._update_item_button.setEnabled(False)
            self._delete_item_button.setEnabled(False)

    def _refresh_editing_cue_panels(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            return

        self._show_workspace_status("")

        if self._session.transcript_visible:
            self._editing_transcript_view.setPlainText(cue.text)
        else:
            self._editing_transcript_view.setPlainText("")

        try:
            workspace = workspace_service.load_cue_workspace(self._connection, cue.id)
        except CueNotFoundError:
            return

        self._current_annotations = workspace.annotations
        self._apply_annotation_highlighting(cue.text, workspace.annotations)

        label_colors = label_preference_service.get_label_preferences(self._connection)

        self._annotation_list.blockSignals(True)
        self._annotation_list.clear()
        for annotation in workspace.annotations:
            heard_as_suffix = f" (heard as: {annotation.heard_as})" if annotation.heard_as else ""
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, annotation.id)
            self._annotation_list.addItem(item)
            row = theme.DiagnosisNoteRow(
                f"[{annotation.label_key}] {annotation.selected_text}{heard_as_suffix}",
                label_colors.get(annotation.label_key, UNKNOWN_LABEL_COLOR),
            )
            item.setSizeHint(theme.ruled_list_row_size_hint(row))
            self._annotation_list.setItemWidget(item, row)
        self._annotation_list.blockSignals(False)

        self._cue_note_edit.blockSignals(True)
        self._cue_note_edit.setPlainText(workspace.cue_note.note_text if workspace.cue_note else "")
        self._cue_note_edit.blockSignals(False)

        self._item_context_edit.setPlainText(cue.text)

        self._saved_items_list.blockSignals(True)
        self._saved_items_list.clear()
        for item_row in workspace.saved_items:
            list_item = QListWidgetItem(f"[{item_row.item_type}] {item_row.text}")
            list_item.setData(Qt.ItemDataRole.UserRole, item_row.id)
            self._saved_items_list.addItem(list_item)
        self._saved_items_list.blockSignals(False)

        self._clear_annotation_form()

    def _apply_annotation_highlighting(self, cue_text: str, annotations) -> None:
        effective = annotations if self._session.transcript_visible else []
        colors = label_preference_service.get_label_preferences(self._connection) if effective else {}
        apply_range_highlighting(self._editing_transcript_view, cue_text, effective, colors, _OVERLAP_HIGHLIGHT)

    def _clear_annotation_form(self) -> None:
        for checkbox in self._label_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self._heard_as_edit.clear()
        self._heard_as_edit.setEnabled(False)
        self._annotation_note_edit.clear()
        self._editing_annotation_id = None
        self._update_annotation_button.setEnabled(False)
        self._delete_annotation_button.setEnabled(False)

    def _on_label_checkbox_changed(self, _state: int = 0) -> None:
        misheard_checked = self._label_checkboxes[AnnotationLabel.MISHEARD.value].isChecked()
        self._heard_as_edit.setEnabled(misheard_checked)

    def _current_selection_range(self, cue_text: str | None = None) -> tuple[int, int]:
        if cue_text is None:
            cue = self._current_editing_cue()
            cue_text = cue.text if cue else ""
        cursor = self._editing_transcript_view.textCursor()
        qt_start, qt_end = cursor.selectionStart(), cursor.selectionEnd()
        if qt_start == qt_end:
            return whole_cue_range(cue_text)
        try:
            start = qt_offset_to_codepoint_index(cue_text, qt_start)
            end = qt_offset_to_codepoint_index(cue_text, qt_end)
        except SurrogatePairOffsetError:
            return whole_cue_range(cue_text)
        return start, end

    def _on_transcript_cursor_moved(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or not getattr(self, "_current_annotations", None):
            return
        qt_position = self._editing_transcript_view.textCursor().position()
        try:
            position = qt_offset_to_codepoint_index(cue.text, qt_position)
        except SurrogatePairOffsetError:
            return
        for annotation in self._current_annotations:
            if annotation.selection_start <= position < annotation.selection_end:
                for i in range(self._annotation_list.count()):
                    item = self._annotation_list.item(i)
                    if item is not None and item.data(Qt.ItemDataRole.UserRole) == annotation.id:
                        self._annotation_list.setCurrentItem(item)
                        return
                break

    def _on_save_annotation_clicked(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            self._show_workspace_status("Select an editing cue first.")
            return

        start, end = self._current_selection_range(cue.text)
        label_keys = [key for key, checkbox in self._label_checkboxes.items() if checkbox.isChecked()]
        heard_as = self._heard_as_edit.text()
        note = self._annotation_note_edit.text()

        try:
            annotation_service.create_annotations(
                self._connection, cue.id, start, end, label_keys, heard_as=heard_as, note=note
            )
        except (CueNotFoundError, AnnotationValidationError) as exc:
            self._show_workspace_status(str(exc))
            return

        self._refresh_editing_cue_panels()

    def _on_annotation_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._editing_annotation_id = None
            self._update_annotation_button.setEnabled(False)
            self._delete_annotation_button.setEnabled(False)
            return

        annotation_id = current.data(Qt.ItemDataRole.UserRole)
        self._editing_annotation_id = annotation_id
        self._update_annotation_button.setEnabled(True)
        self._delete_annotation_button.setEnabled(True)

        annotation = next(
            (a for a in getattr(self, "_current_annotations", []) if a.id == annotation_id), None
        )
        cue = self._current_editing_cue()
        if annotation is None or cue is None:
            return

        for key, checkbox in self._label_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(key == annotation.label_key)
            checkbox.blockSignals(False)
        self._heard_as_edit.setEnabled(annotation.label_key == AnnotationLabel.MISHEARD.value)
        self._heard_as_edit.setText(annotation.heard_as or "")
        self._annotation_note_edit.setText(annotation.note or "")

        qt_start = codepoint_index_to_qt_offset(cue.text, annotation.selection_start)
        qt_end = codepoint_index_to_qt_offset(cue.text, annotation.selection_end)
        cursor = self._editing_transcript_view.textCursor()
        cursor.setPosition(qt_start)
        cursor.setPosition(qt_end, QTextCursor.MoveMode.KeepAnchor)
        self._editing_transcript_view.setTextCursor(cursor)

    def _on_update_annotation_clicked(self) -> None:
        if self._editing_annotation_id is None:
            return
        cue = self._current_editing_cue()
        if cue is None:
            return

        checked_labels = [key for key, checkbox in self._label_checkboxes.items() if checkbox.isChecked()]
        if len(checked_labels) != 1:
            self._show_workspace_status(
                "Select exactly one label to update this annotation "
                "(delete and save again to change how many labels apply)."
            )
            return

        start, end = self._current_selection_range(cue.text)
        heard_as = self._heard_as_edit.text()
        note = self._annotation_note_edit.text()

        try:
            annotation_service.update_annotation(
                self._connection,
                self._editing_annotation_id,
                checked_labels[0],
                start,
                end,
                heard_as=heard_as,
                note=note,
            )
        except (AnnotationNotFoundError, AnnotationValidationError, CueNotFoundError) as exc:
            self._show_workspace_status(str(exc))
            return
        self._refresh_editing_cue_panels()

    def _on_delete_annotation_clicked(self) -> None:
        if self._editing_annotation_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Annotation",
            "Delete this annotation? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            annotation_service.delete_annotation(self._connection, self._editing_annotation_id)
        except AnnotationNotFoundError as exc:
            self._show_workspace_status(str(exc))
        self._refresh_editing_cue_panels()

    def _on_save_note_clicked(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            return
        try:
            cue_note_service.save_cue_note(self._connection, cue.id, self._cue_note_edit.toPlainText())
        except CueNotFoundError as exc:
            self._show_workspace_status(str(exc))
            return
        self._refresh_editing_cue_panels()

    def _on_delete_note_clicked(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Cue Note",
            "Delete the note for this cue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        cue_note_service.delete_cue_note(self._connection, cue.id)
        self._refresh_editing_cue_panels()

    def _on_save_item_clicked(self) -> None:
        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            self._show_workspace_status("Select an editing cue first.")
            return

        start, end = self._current_selection_range(cue.text)
        item_type = self._item_type_combo.currentData()
        meaning = self._item_meaning_edit.text()
        note = self._item_note_edit.text()
        context_text = self._item_context_edit.toPlainText()

        try:
            result = item_service.save_language_item(
                self._connection,
                cue.id,
                item_type,
                start,
                end,
                meaning=meaning,
                note=note,
                context_text=context_text,
            )
        except (CueNotFoundError, SavedItemValidationError) as exc:
            self._show_workspace_status(str(exc))
            return

        if isinstance(result, SavedItemNeedsConfirmation):
            answer = QMessageBox.question(
                self,
                "Possible Duplicate",
                f"'{result.normalized_text}' was already saved elsewhere "
                f"(context: {result.existing_context_text}).\n\nSave this as a separate item anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                result = item_service.save_language_item(
                    self._connection,
                    cue.id,
                    item_type,
                    start,
                    end,
                    meaning=meaning,
                    note=note,
                    context_text=context_text,
                    confirm_duplicate_text_elsewhere=True,
                )
            except SavedItemValidationError as exc:
                self._show_workspace_status(str(exc))
                return

        self._refresh_editing_cue_panels()

    def _on_saved_item_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._editing_item_id = None
            self._update_item_button.setEnabled(False)
            self._delete_item_button.setEnabled(False)
            return

        item_id = current.data(Qt.ItemDataRole.UserRole)
        self._editing_item_id = item_id
        self._update_item_button.setEnabled(True)
        self._delete_item_button.setEnabled(True)

        cue = self._current_editing_cue()
        if cue is None or cue.id is None:
            return
        for saved_item in item_service.list_saved_items_for_cue(self._connection, cue.id):
            if saved_item.id == item_id:
                self._item_meaning_edit.setText(saved_item.meaning or "")
                self._item_note_edit.setText(saved_item.note or "")
                self._item_context_edit.setPlainText(saved_item.context_text)
                index = self._item_type_combo.findData(saved_item.item_type)
                if index >= 0:
                    self._item_type_combo.setCurrentIndex(index)
                break

    def _on_update_item_clicked(self) -> None:
        if self._editing_item_id is None:
            return
        try:
            item_service.update_saved_language_item(
                self._connection,
                self._editing_item_id,
                self._item_type_combo.currentData(),
                meaning=self._item_meaning_edit.text(),
                note=self._item_note_edit.text(),
                context_text=self._item_context_edit.toPlainText(),
            )
        except (SavedItemNotFoundError, SavedItemValidationError) as exc:
            self._show_workspace_status(str(exc))
            return
        self._refresh_editing_cue_panels()

    def _on_delete_item_clicked(self) -> None:
        if self._editing_item_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Saved Item",
            "Delete this saved language item?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            item_service.delete_saved_language_item(self._connection, self._editing_item_id)
        except SavedItemNotFoundError as exc:
            self._show_workspace_status(str(exc))
        self._refresh_editing_cue_panels()

    def _refresh_annotation_presentation(self) -> None:
        cue = self._current_editing_cue()
        if cue is None:
            return

        annotations = getattr(self, "_current_annotations", [])
        self._apply_annotation_highlighting(cue.text, annotations)

        colors = label_preference_service.get_label_preferences(self._connection)
        for i in range(self._annotation_list.count()):
            item = self._annotation_list.item(i)
            if item is None:
                continue
            annotation_id = item.data(Qt.ItemDataRole.UserRole)
            annotation = next((a for a in annotations if a.id == annotation_id), None)
            row = self._annotation_list.itemWidget(item)
            if annotation is not None and isinstance(row, theme.DiagnosisNoteRow):
                row.set_color(colors.get(annotation.label_key, UNKNOWN_LABEL_COLOR))

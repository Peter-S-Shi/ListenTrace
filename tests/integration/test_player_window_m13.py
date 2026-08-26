from __future__ import annotations

from pathlib import Path
import struct
import wave
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.player_window import PlayerWindow


@pytest.fixture()
def db_conn(tmp_path):
    connection = open_connection(tmp_path / "test_player_m13.db")
    migrate(connection)
    yield connection
    connection.close()


def _sample_player_load(tmp_path, media_kind="audio"):
    media_path = tmp_path / f"sample_{media_kind}.wav"
    with wave.open(str(media_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(struct.pack("<h", 0) * 8000 * 2)
    material = Material(id=1, title=f"M13 {media_kind.title()} Lesson", media_path=str(media_path), media_kind=media_kind)
    cues = [
        SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="First line of dialogue"),
        SubtitleCue(cue_index=2, start_ms=1000, end_ms=2500, text="Second line of dialogue"),
    ]
    return PlayerLoadResult(material=material, cues=cues)


def test_player_window_m13_notebook_study_desk_architecture(qapp, db_conn, tmp_path):
    load_res = _sample_player_load(tmp_path)
    window = PlayerWindow(load_res, db_conn)
    window.show()

    # 1. Verify Splitter Topology: Media Page | Spiral Binding | Notebook Page
    assert isinstance(window._main_splitter, QSplitter)
    assert window._main_splitter.orientation() == Qt.Orientation.Horizontal
    assert window._main_splitter.count() == 3
    assert window._main_splitter.widget(0) is window._cinema_scroll_area
    assert isinstance(window._cinema_scroll_area, QScrollArea)
    assert window._cinema_scroll_area.widget() is window._cinema_stage_widget
    assert window._cinema_scroll_area.widgetResizable() is True
    assert window._cinema_scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert window._main_splitter.widget(1) is window._spiral_binding_strip
    assert window._main_splitter.widget(2) is window._right_workspace_widget

    # 2. Verify the binding strip anchors the "open book" seam and cannot be
    #    collapsed/resized away, while the two real pages remain resizable.
    assert window._spiral_binding_strip.property("role") == "spiral_binding_strip"
    assert window._main_splitter.isCollapsible(1) is False
    assert window._spiral_binding_strip.minimumWidth() == window._spiral_binding_strip.maximumWidth()

    # 3. Verify warm paper identity replaced the dark cinema shell.
    assert window._cinema_stage_widget.property("surface") == "paper"
    assert window._right_workspace_widget.property("surface") == "paper"
    assert window.property("surface") == "paper"

    # 4. Verify Active Subtitle / Status Strip
    assert hasattr(window, "_active_subtitle_hud")
    assert window._active_subtitle_hud.property("role") == "study_status_strip"

    # 5. Verify Task-Oriented Control Roles
    assert window._play_pause_button.property("role") == "primary"
    assert window._replay_button.property("role") == "secondary"
    assert window._previous_button.property("role") == "secondary"
    assert window._next_button.property("role") == "secondary"
    assert window._loop_cue_button.property("role") == "secondary"
    assert window._loop_settings_button.property("role") == "quiet"
    assert window._mute_button.property("role") == "quiet"
    assert window._transcript_button.property("role") == "secondary"

    # 6. Verify the transport/loop/utility controls live inside compact mini
    #    spiral-notebook cards rather than one dense button slab.
    for notebook in (window._playback_notebook, window._loop_practice_notebook, window._utility_notebook):
        assert notebook.property("role") == "mini_notebook_card"
    assert window._playback_notebook.isAncestorOf(window._play_pause_button)
    assert window._loop_practice_notebook.isAncestorOf(window._loop_cue_button)
    assert window._utility_notebook.isAncestorOf(window._loop_settings_button)

    # 7. Verify Cue-as-Ruled-Study-Sheet Stream
    assert window._cue_list.property("role") == "ruled_list_notebook"
    assert window._cue_list.count() == 2

    window.close()


def test_player_window_m13_splitter_pages_remain_independently_resizable(qapp, db_conn, tmp_path):
    """Notebook Primitive Hardening corrective #9: the Player's own splitter
    gets a wider drag hit target (scoped role, not a global QSplitter change),
    and the left/right pages must still actually resize when dragged."""
    load_res = _sample_player_load(tmp_path)
    window = PlayerWindow(load_res, db_conn)
    window.resize(1400, 800)
    window.show()

    assert window._main_splitter.property("role") == "player_split"

    before_left, before_binding, before_right = window._main_splitter.sizes()
    window._main_splitter.moveSplitter(before_left - 100, 1)

    after_left, after_binding, after_right = window._main_splitter.sizes()
    assert after_left != before_left
    assert after_binding == before_binding  # the fixed-width binding strip never moves
    assert after_left + after_right == before_left + before_right

    window.close()


def test_player_window_m13_annotation_notebook_scrolls_independently_of_media_page(qapp, db_conn, tmp_path):
    """Notebook Primitive Hardening corrective #8: scrolling the Annotation
    Notebook to reach its lower controls must never carry the media/playback
    context off-screen -- that's the immersion bug this pass fixes. Proven by
    scrolling the local annotation QScrollArea to its maximum and confirming
    the media study page's geometry/visibility is completely unaffected."""
    load_res = _sample_player_load(tmp_path)
    window = PlayerWindow(load_res, db_conn)
    window.resize(1040, 620)
    window.show()

    assert not isinstance(window.centralWidget(), QScrollArea)
    assert isinstance(window._annotation_scroll_area, QScrollArea)

    before_geometry = window._cinema_stage_widget.geometry()
    before_visible = window._cinema_stage_widget.isVisible()

    scrollbar = window._annotation_scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())

    assert window._cinema_stage_widget.geometry() == before_geometry
    assert window._cinema_stage_widget.isVisible() == before_visible
    assert window._video_widget is None or window._video_widget.isVisible()

    window.close()


def test_player_window_m13_cinema_page_is_vertically_scrollable_on_short_windows(qapp, db_conn, tmp_path):
    """M13 Final Player Accessibility: on shorter screens, the left cinema page
    scrolls locally so all controls (Playback, Loop, Utility, Mute) remain
    accessible without forcing an excessive window minimum height or clipping."""
    load_res = _sample_player_load(tmp_path, media_kind="video")
    window = PlayerWindow(load_res, db_conn)
    window.resize(1040, 620)
    window.show()
    qapp.processEvents()

    assert not isinstance(window.centralWidget(), QScrollArea)
    assert isinstance(window._cinema_scroll_area, QScrollArea)
    assert window._cinema_scroll_area.widgetResizable() is True
    assert window._cinema_scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    # At short window height, video content is taller than viewport so vertical scrollbar is active
    vbar = window._cinema_scroll_area.verticalScrollBar()
    assert vbar.maximum() > 0

    # Video and HUD do not overlap
    video_top_left = window._video_widget.mapTo(window._cinema_stage_widget, window._video_widget.rect().topLeft())
    video_bottom = video_top_left.y() + window._video_widget.height()
    hud_top_left = window._active_subtitle_hud.mapTo(window._cinema_stage_widget, window._active_subtitle_hud.rect().topLeft())
    assert video_bottom <= hud_top_left.y()

    # Scrolling to maximum brings the bottom of the playback card and mute button into the viewport
    vbar.setValue(vbar.maximum())
    qapp.processEvents()

    mute_pt = window._mute_button.mapTo(window._cinema_scroll_area.viewport(), window._mute_button.rect().topLeft())
    mute_bottom = mute_pt.y() + window._mute_button.height()
    viewport_h = window._cinema_scroll_area.viewport().height()

    assert 0 <= mute_pt.y() < viewport_h
    assert mute_bottom <= viewport_h

    pb_pt = window._playback_notebook.mapTo(window._cinema_scroll_area.viewport(), window._playback_notebook.rect().topLeft())
    pb_bottom = pb_pt.y() + window._playback_notebook.height()
    assert pb_bottom <= viewport_h

    window.close()


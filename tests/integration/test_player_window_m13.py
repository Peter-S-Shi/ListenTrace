from __future__ import annotations

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter

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


def _sample_player_load(tmp_path):
    media_path = tmp_path / "sample.wav"
    media_path.write_bytes(b"\x00" * 1000)
    material = Material(id=1, title="M13 Architecture Lesson", media_path=str(media_path), media_kind="audio")
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
    assert window._main_splitter.widget(0) is window._cinema_stage_widget
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

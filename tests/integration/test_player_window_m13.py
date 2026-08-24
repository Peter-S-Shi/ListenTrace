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


def test_player_window_m13_horizontal_splitter_architecture(qapp, db_conn, tmp_path):
    load_res = _sample_player_load(tmp_path)
    window = PlayerWindow(load_res, db_conn)
    window.show()

    # 1. Verify Horizontal Splitter Topology
    assert isinstance(window._main_splitter, QSplitter)
    assert window._main_splitter.orientation() == Qt.Orientation.Horizontal
    assert window._main_splitter.count() == 2

    # 2. Verify Left Cinema Stage and Right Transcript Workspace
    assert window._cinema_stage_widget.property("surface") == "cinema"
    assert window._right_workspace_widget.property("surface") == "cinema"
    assert window.property("surface") == "cinema"

    # 3. Verify Active Subtitle HUD
    assert hasattr(window, "_active_subtitle_hud")
    assert window._active_subtitle_hud is not None

    # 4. Verify Task-Oriented Control Roles
    assert window._play_pause_button.property("role") == "primary"
    assert window._replay_button.property("role") == "secondary"
    assert window._previous_button.property("role") == "secondary"
    assert window._next_button.property("role") == "secondary"
    assert window._loop_cue_button.property("role") == "secondary"
    assert window._loop_settings_button.property("role") == "quiet"
    assert window._mute_button.property("role") == "quiet"
    assert window._transcript_button.property("role") == "secondary"

    # 5. Verify Cue-as-Card Stream
    assert window._cue_list.property("role") == "cinema_cue_list"
    assert window._cue_list.count() == 2

    window.close()

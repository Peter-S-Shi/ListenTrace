from __future__ import annotations

import struct
import wave

import pytest

from listentrace.application.services import quick_practice_service as svc
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db import learning_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.quick_practice_start_dialog import QuickPracticeStartDialog


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "start_dialog.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_wav(path, seconds=2, framerate=8000):
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(struct.pack("<h", 0) * framerate * seconds)


def _import_material(conn, tmp_path):
    media_path = tmp_path / "lesson.wav"
    _make_wav(media_path)
    srt = tmp_path / "lesson.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nBonjour tout le monde\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nComment ca va\n\n"
        "3\n00:00:02,000 --> 00:00:03,000\nAu revoir\n",
        encoding="utf-8",
    )
    result = import_material(conn, media_path, srt, "Start Dialog Lesson")
    return load_material_for_player(conn, result.material_id)


def test_recommended_is_selected_by_default_with_5_as_the_default_count(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    assert dialog._recommended_radio.isChecked()
    assert dialog._count_combo.currentData() == 5


def test_selected_cue_order_is_preserved_regardless_of_click_order(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    dialog._selected_radio.setChecked(True)
    # Select out of visual order (row 2 first, then row 0).
    dialog._cue_list.item(2).setSelected(True)
    dialog._cue_list.item(0).setSelected(True)
    dialog._on_start_clicked()

    assert dialog.started_session_id is not None
    state = svc.load_session_state(conn, dialog.started_session_id)
    assert [i.item.subtitle_cue_id for i in state.items] == [load_result.cues[0].id, load_result.cues[2].id]


def test_selected_with_no_cues_shows_an_error_and_does_not_start(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    dialog._selected_radio.setChecked(True)
    dialog._on_start_clicked()
    assert dialog.started_session_id is None
    assert dialog._status_label.text() != ""


def test_recommended_preview_shows_reasons_for_qualifying_cues(qapp, conn, tmp_path):
    from PySide6.QtWidgets import QLabel

    load_result = _import_material(conn, tmp_path)
    learning_repository.insert_annotations(
        conn, load_result.cues[1].id, [("misheard", "wrong")], load_result.cues[1].text[:7], 0, 7, None
    )
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    assert dialog._recommended_preview.count() > 0
    texts: list[str] = []
    for i in range(dialog._recommended_preview.count()):
        row = dialog._recommended_preview.itemWidget(dialog._recommended_preview.item(i))
        texts.extend(label.text() for label in row.findChildren(QLabel))
    assert any("misheard" in t for t in texts)


def test_recommended_preview_renders_each_reason_as_its_own_paper_tag(qapp, conn, tmp_path):
    """M13 Axis 4 corrective: each recommendation reason is its own
    `make_paper_tag()` label, not one plain comma-joined string."""
    from PySide6.QtWidgets import QLabel

    load_result = _import_material(conn, tmp_path)
    learning_repository.insert_annotations(
        conn, load_result.cues[1].id, [("misheard", "wrong")], load_result.cues[1].text[:7], 0, 7, None
    )
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    assert dialog._recommended_preview.count() > 0
    found_multi_reason_row = False
    for i in range(dialog._recommended_preview.count()):
        row = dialog._recommended_preview.itemWidget(dialog._recommended_preview.item(i))
        tags = [w for w in row.findChildren(QLabel) if w.property("role") == "paper_tag"]
        if len(tags) >= 2:
            found_multi_reason_row = True
        for tag in tags:
            assert "," not in tag.text(), "each reason must be its own tag, not comma-joined"
    assert found_multi_reason_row, "expected at least one recommended cue with multiple reason tags"


def test_recommended_start_creates_a_session_with_the_chosen_count(qapp, conn, tmp_path):
    load_result = _import_material(conn, tmp_path)
    dialog = QuickPracticeStartDialog(conn, load_result.material.id, load_result.material.title, load_result.cues)
    dialog._recommended_radio.setChecked(True)
    dialog._count_combo.setCurrentIndex(0)  # 3
    dialog._on_start_clicked()

    assert dialog.started_session_id is not None
    session = svc.get_session(conn, dialog.started_session_id)
    assert session.source_type == "recommended"
    assert session.requested_count == 3

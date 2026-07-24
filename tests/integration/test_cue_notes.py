from __future__ import annotations

import pytest

from listentrace.application.errors import CueNotFoundError
from listentrace.application.services import cue_note_service
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import get_cues_for_track, insert_material, insert_subtitle_track


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def cue(conn):
    material_id = insert_material(conn, Material(title="Lesson", media_path="m.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(conn, track)
    return get_cues_for_track(conn, track_id)[0]


def test_save_and_get_cue_note(conn, cue):
    cue_note_service.save_cue_note(conn, cue.id, "remember this")
    note = cue_note_service.get_cue_note(conn, cue.id)
    assert note.note_text == "remember this"


def test_save_cue_note_upserts_a_single_row(conn, cue):
    cue_note_service.save_cue_note(conn, cue.id, "first")
    cue_note_service.save_cue_note(conn, cue.id, "second")
    note = cue_note_service.get_cue_note(conn, cue.id)
    assert note.note_text == "second"
    count = conn.execute(
        "SELECT COUNT(*) FROM cue_note WHERE subtitle_cue_id = ?", (cue.id,)
    ).fetchone()[0]
    assert count == 1


def test_saving_empty_note_deletes_it(conn, cue):
    cue_note_service.save_cue_note(conn, cue.id, "something")
    cue_note_service.save_cue_note(conn, cue.id, "   ")
    assert cue_note_service.get_cue_note(conn, cue.id) is None


def test_explicit_delete(conn, cue):
    cue_note_service.save_cue_note(conn, cue.id, "something")
    cue_note_service.delete_cue_note(conn, cue.id)
    assert cue_note_service.get_cue_note(conn, cue.id) is None


def test_save_note_for_nonexistent_cue_raises(conn):
    with pytest.raises(CueNotFoundError):
        cue_note_service.save_cue_note(conn, 999, "note")


def test_cue_note_cascades_when_material_removed(conn, cue):
    cue_note_service.save_cue_note(conn, cue.id, "something")
    conn.execute("DELETE FROM material")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM cue_note").fetchone()[0] == 0

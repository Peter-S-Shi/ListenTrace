from __future__ import annotations

import sqlite3

import pytest

from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import current_version, migrate
from listentrace.infrastructure.db.repository import (
    get_cue_count,
    get_material,
    insert_material,
    insert_subtitle_track,
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def test_migrate_creates_expected_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"material", "subtitle_track", "subtitle_cue"} <= tables


def test_migrate_is_idempotent(conn):
    version_before = current_version(conn)
    migrate(conn)  # second call must not raise or duplicate schema
    version_after = current_version(conn)
    assert version_before == version_after == 1


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO subtitle_track (material_id, format, source_path) "
            "VALUES (999, 'srt', 'missing.srt')"
        )
        conn.commit()


def test_material_and_subtitle_persistence_round_trip(conn):
    material_id = insert_material(
        conn,
        Material(title="Sample Lesson", media_path="C:/media/sample.mp4", language="fr"),
    )
    stored = get_material(conn, material_id)
    assert stored is not None
    assert stored.title == "Sample Lesson"
    assert stored.language == "fr"

    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/sample.srt",
        cues=[
            SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour"),
            SubtitleCue(cue_index=2, start_ms=1000, end_ms=2500, text="Comment ça va ?"),
        ],
    )
    track_id = insert_subtitle_track(conn, track)
    assert get_cue_count(conn, track_id) == 2


def test_cue_end_before_start_is_rejected():
    with pytest.raises(ValueError):
        SubtitleCue(cue_index=1, start_ms=1000, end_ms=500, text="broken")

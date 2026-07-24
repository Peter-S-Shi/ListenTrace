from __future__ import annotations

import sqlite3

import pytest

from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import MIGRATIONS, current_version, migrate
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
    assert version_before == version_after == 2


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


def test_migration_upgrades_a_milestone1_v1_database(tmp_path):
    connection = open_connection(tmp_path / "v1.db")
    version_1_sql = dict(MIGRATIONS)[1]
    connection.executescript(version_1_sql)
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    assert current_version(connection) == 1

    # Insert using only the columns that existed under schema version 1 (before
    # `insert_material` knew about `normalized_path`), to simulate a pre-existing row.
    cursor = connection.execute(
        "INSERT INTO material (title, media_path) VALUES (?, ?)",
        ("Pre-existing", "C:/media/old.mp4"),
    )
    material_id = int(cursor.lastrowid)
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 2
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(material)")}
    assert "normalized_path" in columns

    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "Pre-existing"
    assert stored.normalized_path is None

    connection.close()

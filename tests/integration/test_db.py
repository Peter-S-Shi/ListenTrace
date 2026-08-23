from __future__ import annotations

import sqlite3

import pytest

from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import MIGRATIONS, current_version, migrate
from listentrace.infrastructure.db.repository import (
    get_cue_count,
    get_cues_for_track,
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
    assert version_before == version_after == 11


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

    assert final_version == 11
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(material)")}
    assert "normalized_path" in columns
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"annotation", "cue_note", "saved_language_item", "annotation_label_preference"} <= tables
    assert {"practice_session", "session_stage_progress", "stage_response"} <= tables
    assert {"keyword_capture", "session_diagnosis_evidence", "shadowing_cue_progress"} <= tables
    assert {"quiz_attempt", "quiz_question", "quiz_answer"} <= tables
    assert {"recording", "microphone_preference"} <= tables
    quiz_question_columns = {row["name"] for row in connection.execute("PRAGMA table_info(quiz_question)")}
    assert "source_cue_text" in quiz_question_columns

    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "Pre-existing"
    assert stored.normalized_path is None

    connection.close()


def test_migration_upgrades_a_milestone2_v2_database(tmp_path):
    connection = open_connection(tmp_path / "v2.db")
    connection.executescript(dict(MIGRATIONS)[1])
    connection.executescript(dict(MIGRATIONS)[2])
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    assert current_version(connection) == 2

    # Populate a v2-shaped material + subtitle track + cues, to prove the v3
    # migration doesn't disturb pre-existing Milestone 1/2 data.
    material_id = insert_material(
        connection, Material(title="Existing Lesson", media_path="C:/media/existing.mp4")
    )
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/existing.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(connection, track)

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"annotation", "cue_note", "saved_language_item", "annotation_label_preference"} <= tables
    assert {"practice_session", "session_stage_progress", "stage_response"} <= tables
    assert {"keyword_capture", "session_diagnosis_evidence", "shadowing_cue_progress"} <= tables
    assert {"quiz_attempt", "quiz_question", "quiz_answer"} <= tables
    assert {"recording", "microphone_preference"} <= tables

    # Existing material/track/cue data must remain intact after the upgrade.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "Existing Lesson"
    cues = get_cues_for_track(connection, track_id)
    assert len(cues) == 1
    assert cues[0].text == "Bonjour"

    prefs = {
        row["label_key"]: row["color"]
        for row in connection.execute("SELECT label_key, color FROM annotation_label_preference")
    }
    assert len(prefs) == 5

    connection.close()


def test_migration_upgrades_a_milestone4_v3_database_with_existing_data_intact(tmp_path):
    connection = open_connection(tmp_path / "v3.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 3:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 3")
    connection.commit()
    assert current_version(connection) == 3

    material_id = insert_material(
        connection, Material(title="M4 Lesson", media_path="C:/media/m4.mp4")
    )
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m4.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(connection, track)
    cue_id = get_cues_for_track(connection, track_id)[0].id

    connection.execute(
        "INSERT INTO annotation (subtitle_cue_id, label_key, selected_text, selection_start, selection_end) "
        "VALUES (?, 'keyword', 'Bonjour', 0, 7)",
        (cue_id,),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"practice_session", "session_stage_progress", "stage_response"} <= tables
    assert {"keyword_capture", "session_diagnosis_evidence", "shadowing_cue_progress"} <= tables
    assert {"quiz_attempt", "quiz_question", "quiz_answer"} <= tables
    assert {"recording", "microphone_preference"} <= tables

    # Existing Milestone 1-4 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M4 Lesson"
    cues = get_cues_for_track(connection, track_id)
    assert len(cues) == 1
    assert cues[0].text == "Bonjour"
    annotation_row = connection.execute(
        "SELECT label_key, selected_text FROM annotation WHERE subtitle_cue_id = ?", (cue_id,)
    ).fetchone()
    assert annotation_row["label_key"] == "keyword"
    assert annotation_row["selected_text"] == "Bonjour"

    connection.close()


def test_migration_upgrades_a_milestone5_v4_database_with_existing_data_intact(tmp_path):
    connection = open_connection(tmp_path / "v4.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 4:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 4")
    connection.commit()
    assert current_version(connection) == 4

    material_id = insert_material(
        connection, Material(title="M5 Lesson", media_path="C:/media/m5.mp4")
    )
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m5.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(connection, track)

    cursor = connection.execute(
        "INSERT INTO practice_session (material_id) VALUES (?)", (material_id,)
    )
    session_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO session_stage_progress (practice_session_id, stage_key) VALUES (?, 'global_comprehension')",
        (session_id,),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"quiz_attempt", "quiz_question", "quiz_answer"} <= tables
    assert {"recording", "microphone_preference"} <= tables

    # Existing Milestone 1-5 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M5 Lesson"
    cues = get_cues_for_track(connection, track_id)
    assert len(cues) == 1
    session_row = connection.execute(
        "SELECT material_id, status FROM practice_session WHERE id = ?", (session_id,)
    ).fetchone()
    assert session_row["material_id"] == material_id
    assert session_row["status"] == "active"

    connection.close()


def test_migration_upgrades_a_milestone6_v6_database_with_existing_data_intact(tmp_path):
    connection = open_connection(tmp_path / "v6.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 6:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 6")
    connection.commit()
    assert current_version(connection) == 6

    material_id = insert_material(connection, Material(title="M6 Lesson", media_path="C:/media/m6.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m6.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(connection, track)
    cue_id = get_cues_for_track(connection, track_id)[0].id

    cursor = connection.execute(
        "INSERT INTO quiz_attempt (material_id, seed, requested_count, actual_count) VALUES (?, 1, 1, 1)",
        (material_id,),
    )
    attempt_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO quiz_question (
            quiz_attempt_id, position, question_type, subtitle_cue_id, source_cue_text,
            prompt_payload, correct_answer_payload, scoring_config
        ) VALUES (?, 0, 'dictation', ?, 'Bonjour', '{}', '{}', '{}')
        """,
        (attempt_id, cue_id),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"recording", "microphone_preference"} <= tables

    # Existing Milestone 1-6 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M6 Lesson"
    quiz_question_row = connection.execute(
        "SELECT source_cue_text FROM quiz_question WHERE quiz_attempt_id = ?", (attempt_id,)
    ).fetchone()
    assert quiz_question_row["source_cue_text"] == "Bonjour"

    connection.close()


def test_migration_upgrades_a_milestone6_v5_database_backfills_source_cue_text(tmp_path):
    """A quiz_question row created under schema v5 (before source_cue_text
    existed) must be backfilled from the live subtitle_cue text it was
    generated from, not left null or empty."""
    connection = open_connection(tmp_path / "v5.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 5:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 5")
    connection.commit()
    assert current_version(connection) == 5

    material_id = insert_material(connection, Material(title="M6 Lesson", media_path="C:/media/m6.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m6.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour tout le monde")],
    )
    track_id = insert_subtitle_track(connection, track)
    cue_id = get_cues_for_track(connection, track_id)[0].id

    cursor = connection.execute(
        "INSERT INTO quiz_attempt (material_id, seed, requested_count, actual_count) VALUES (?, 1, 1, 1)",
        (material_id,),
    )
    attempt_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO quiz_question (
            quiz_attempt_id, position, question_type, subtitle_cue_id,
            prompt_payload, correct_answer_payload, scoring_config
        ) VALUES (?, 0, 'dictation', ?, '{}', '{}', '{}')
        """,
        (attempt_id, cue_id),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    backfilled = connection.execute(
        "SELECT source_cue_text FROM quiz_question WHERE quiz_attempt_id = ?", (attempt_id,)
    ).fetchone()
    assert backfilled["source_cue_text"] == "Bonjour tout le monde"

    connection.close()


def test_migration_upgrades_a_milestone9_v8_database_with_existing_data_intact(tmp_path):
    """Milestone 10 (Quick Practice Mode, schema version 9) is purely
    additive: an existing v8 database (post-Milestone-9) with real
    material/recording data must upgrade cleanly and keep that data intact."""
    connection = open_connection(tmp_path / "v8.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 8:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 8")
    connection.commit()
    assert current_version(connection) == 8

    material_id = insert_material(connection, Material(title="M9 Lesson", media_path="C:/media/m9.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m9.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(connection, track)
    cue_id = get_cues_for_track(connection, track_id)[0].id
    connection.execute(
        "INSERT INTO recording (material_id, subtitle_cue_id, relative_file_path, status) "
        "VALUES (?, ?, 'rec.wav', 'ready')",
        (material_id, cue_id),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"quick_practice_session", "quick_practice_item", "quick_practice_diagnosis_evidence"} <= tables

    # Existing Milestone 1-9 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M9 Lesson"
    recording_row = connection.execute(
        "SELECT status FROM recording WHERE material_id = ?", (material_id,)
    ).fetchone()
    assert recording_row["status"] == "ready"

    connection.close()


def test_migration_upgrades_a_milestone10_v9_database_with_existing_data_intact(tmp_path):
    """Post-M10 Phase B (Release Hardening) schema version 10 only adds
    indexes on pre-existing foreign-key columns for large-history query
    performance -- no table, column, or data change. An existing v9 database
    (post-Milestone-10) with real Quick Practice data must upgrade cleanly,
    gain the new indexes, and keep that data intact."""
    connection = open_connection(tmp_path / "v9.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 9:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 9")
    connection.commit()
    assert current_version(connection) == 9

    material_id = insert_material(connection, Material(title="M10 Lesson", media_path="C:/media/m10.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/m10.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    insert_subtitle_track(connection, track)
    connection.execute(
        "INSERT INTO quick_practice_session (material_id, source_type, requested_count, actual_count, status) "
        "VALUES (?, 'selected', 1, 1, 'completed')",
        (material_id,),
    )
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    indexes = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    }
    assert {
        "idx_subtitle_track_material_id",
        "idx_practice_session_material_id",
        "idx_keyword_capture_practice_session_id",
        "idx_session_diagnosis_evidence_subtitle_cue_id",
        "idx_quiz_attempt_material_id",
        "idx_recording_material_id",
        "idx_recording_subtitle_cue_id",
        "idx_quick_practice_session_material_id",
        "idx_saved_language_item_subtitle_cue_id",
    } <= indexes

    # Existing Milestone 1-10 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M10 Lesson"
    qp_row = connection.execute(
        "SELECT status FROM quick_practice_session WHERE material_id = ?", (material_id,)
    ).fetchone()
    assert qp_row["status"] == "completed"

    connection.close()


def test_migration_upgrades_a_milestone12_v10_database_with_existing_data_intact(tmp_path):
    """M12 Loop End Grace (schema version 11) is purely additive: an existing
    v10 database (post-Phase-B) with real material data must upgrade cleanly,
    gain the two new tables with the global default seeded, and keep existing
    data intact."""
    connection = open_connection(tmp_path / "v10.db")
    for target_version, sql in MIGRATIONS:
        if target_version > 10:
            break
        connection.executescript(sql)
    connection.execute("PRAGMA user_version = 10")
    connection.commit()
    assert current_version(connection) == 10

    material_id = insert_material(connection, Material(title="M12 Lesson", media_path="C:/media/m12.mp4"))
    connection.commit()

    final_version = migrate(connection)

    assert final_version == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"loop_grace_preference", "material_loop_grace_override"} <= tables

    global_row = connection.execute("SELECT grace_ms FROM loop_grace_preference WHERE id = 1").fetchone()
    assert global_row["grace_ms"] == 180

    override_rows = connection.execute("SELECT * FROM material_loop_grace_override").fetchall()
    assert override_rows == [], "no material has an override immediately after migration"

    # Existing Milestone 1-10 data must survive the upgrade untouched.
    stored = get_material(connection, material_id)
    assert stored is not None
    assert stored.title == "M12 Lesson"

    connection.close()


def test_migrate_rolls_back_completely_when_a_migration_fails(tmp_path, monkeypatch):
    """Regression test for a real bug caught during Post-M10 Phase B: `migrate`
    used to run each migration's SQL via `executescript`, which implicitly
    commits before running and executes statements outside normal
    transactional control -- a script failing partway through left every
    earlier statement in it already applied even after `conn.rollback()`.
    That meant a migration interrupted by any failure left the schema
    half-created while `PRAGMA user_version` stayed unbumped, so every
    subsequent app startup retried the exact same migration and failed again
    with "table already exists" -- a permanently stuck database with no
    recovery path. `migrate` now runs each migration inside one explicit
    transaction, split into individual statements, so a failure rolls back
    completely and a fixed-and-retried migration can still succeed."""
    connection = open_connection(tmp_path / "broken.db")
    baseline_version = migrate(connection)
    assert baseline_version == 11

    broken_migrations = list(MIGRATIONS) + [
        (
            12,
            """
            CREATE TABLE never_should_exist (id INTEGER PRIMARY KEY);
            CREATE TABLE THIS IS NOT VALID SQL;
            """,
        )
    ]
    monkeypatch.setattr("listentrace.infrastructure.db.migrations.MIGRATIONS", broken_migrations)

    with pytest.raises(sqlite3.OperationalError):
        migrate(connection)

    # The failure must be a true no-op: version unchanged, and the table from
    # the first (valid) statement in the broken script must not have leaked
    # through despite the later statement's failure.
    assert current_version(connection) == 11
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "never_should_exist" not in tables

    # Retrying the same broken migration again must fail the same clean way
    # -- never "table already exists" -- proving no partial state leaked
    # through on the first attempt.
    with pytest.raises(sqlite3.OperationalError) as excinfo:
        migrate(connection)
    assert "already exists" not in str(excinfo.value)
    assert current_version(connection) == 11

    # Fixing the migration and retrying must succeed normally -- the earlier
    # failure left nothing behind to conflict with a corrected retry.
    fixed_migrations = list(MIGRATIONS) + [
        (12, "CREATE TABLE never_should_exist (id INTEGER PRIMARY KEY);")
    ]
    monkeypatch.setattr("listentrace.infrastructure.db.migrations.MIGRATIONS", fixed_migrations)
    assert migrate(connection) == 12
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "never_should_exist" in tables

    connection.close()

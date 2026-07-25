from __future__ import annotations

import sqlite3

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE material (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            language TEXT,
            media_path TEXT NOT NULL,
            media_kind TEXT,
            duration_ms INTEGER,
            file_size_bytes INTEGER,
            file_fingerprint TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_opened_at TEXT
        );

        CREATE TABLE subtitle_track (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            format TEXT NOT NULL,
            language TEXT,
            source_path TEXT NOT NULL,
            is_timed INTEGER NOT NULL DEFAULT 1,
            encoding TEXT NOT NULL DEFAULT 'utf-8',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE subtitle_cue (
            id INTEGER PRIMARY KEY,
            subtitle_track_id INTEGER NOT NULL REFERENCES subtitle_track(id) ON DELETE CASCADE,
            cue_index INTEGER NOT NULL,
            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT,
            UNIQUE (subtitle_track_id, cue_index),
            CHECK (end_ms >= start_ms)
        );
        """,
    ),
    (
        2,
        """
        ALTER TABLE material ADD COLUMN normalized_path TEXT;
        CREATE UNIQUE INDEX idx_material_normalized_path ON material(normalized_path);
        """,
    ),
    (
        3,
        """
        CREATE TABLE annotation (
            id INTEGER PRIMARY KEY,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            label_key TEXT NOT NULL,
            selected_text TEXT NOT NULL,
            selection_start INTEGER NOT NULL,
            selection_end INTEGER NOT NULL,
            heard_as TEXT,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (subtitle_cue_id, label_key, selection_start, selection_end),
            CHECK (selection_end >= selection_start)
        );

        CREATE TABLE cue_note (
            subtitle_cue_id INTEGER PRIMARY KEY REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE saved_language_item (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            item_type TEXT NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            selection_start INTEGER NOT NULL,
            selection_end INTEGER NOT NULL,
            meaning TEXT,
            note TEXT,
            context_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized_text),
            CHECK (selection_end >= selection_start)
        );

        CREATE TABLE annotation_label_preference (
            label_key TEXT PRIMARY KEY,
            color TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        INSERT INTO annotation_label_preference (label_key, color) VALUES
            ('keyword', '#2563EB'),
            ('known_not_heard', '#D97706'),
            ('connected_reduced_speech', '#7C3AED'),
            ('misheard', '#DC2626'),
            ('unknown_word_or_chunk', '#059669');
        """,
    ),
    (
        4,
        """
        CREATE TABLE practice_session (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            mode TEXT NOT NULL DEFAULT 'intensive',
            status TEXT NOT NULL DEFAULT 'active',
            current_stage TEXT NOT NULL DEFAULT 'global_comprehension',
            transcript_revealed_at TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_resumed_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            abandoned_at TEXT
        );

        -- Enforces "at most one active intensive session per material" at the
        -- database level, not just in application code.
        CREATE UNIQUE INDEX idx_practice_session_one_active_per_material
            ON practice_session(material_id)
            WHERE status = 'active' AND mode = 'intensive';

        CREATE TABLE session_stage_progress (
            practice_session_id INTEGER NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
            stage_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started',
            outcome_key TEXT,
            skip_note TEXT,
            started_at TEXT,
            completed_at TEXT,
            skipped_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (practice_session_id, stage_key)
        );

        CREATE TABLE stage_response (
            id INTEGER PRIMARY KEY,
            practice_session_id INTEGER NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
            stage_key TEXT NOT NULL,
            prompt_key TEXT NOT NULL,
            response_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (practice_session_id, stage_key, prompt_key)
        );

        CREATE TABLE keyword_capture (
            id INTEGER PRIMARY KEY,
            practice_session_id INTEGER NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
            capture_type TEXT NOT NULL,
            text TEXT NOT NULL,
            position INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE session_diagnosis_evidence (
            id INTEGER PRIMARY KEY,
            practice_session_id INTEGER NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            annotation_id INTEGER REFERENCES annotation(id) ON DELETE SET NULL,
            label_key TEXT NOT NULL,
            selected_text TEXT NOT NULL,
            selection_start INTEGER NOT NULL,
            selection_end INTEGER NOT NULL,
            heard_as TEXT,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (practice_session_id, subtitle_cue_id, label_key, selection_start, selection_end),
            CHECK (selection_end >= selection_start)
        );

        CREATE TABLE shadowing_cue_progress (
            practice_session_id INTEGER NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'not_started',
            practice_count INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            last_practiced_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (practice_session_id, subtitle_cue_id)
        );
        """,
    ),
    (
        5,
        """
        CREATE TABLE quiz_attempt (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            quiz_mode TEXT NOT NULL DEFAULT 'material',
            status TEXT NOT NULL DEFAULT 'active',
            seed INTEGER NOT NULL,
            requested_count INTEGER NOT NULL,
            actual_count INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_resumed_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            abandoned_at TEXT
        );

        CREATE TABLE quiz_question (
            id INTEGER PRIMARY KEY,
            quiz_attempt_id INTEGER NOT NULL REFERENCES quiz_attempt(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            question_type TEXT NOT NULL,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            source_annotation_id INTEGER REFERENCES annotation(id) ON DELETE SET NULL,
            source_saved_item_id INTEGER REFERENCES saved_language_item(id) ON DELETE SET NULL,
            source_keyword_capture_id INTEGER REFERENCES keyword_capture(id) ON DELETE SET NULL,
            prompt_payload TEXT NOT NULL,
            correct_answer_payload TEXT NOT NULL,
            scoring_config TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (quiz_attempt_id, position)
        );

        CREATE TABLE quiz_answer (
            id INTEGER PRIMARY KEY,
            quiz_question_id INTEGER NOT NULL REFERENCES quiz_question(id) ON DELETE CASCADE,
            raw_answer_text TEXT,
            normalized_answer_text TEXT,
            selected_choice_index INTEGER,
            is_correct INTEGER,
            answered_state TEXT NOT NULL DEFAULT 'unanswered',
            answered_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (quiz_question_id)
        );
        """,
    ),
    (
        6,
        """
        ALTER TABLE quiz_question ADD COLUMN source_cue_text TEXT NOT NULL DEFAULT '';

        UPDATE quiz_question
        SET source_cue_text = COALESCE(
            (SELECT text FROM subtitle_cue WHERE subtitle_cue.id = quiz_question.subtitle_cue_id),
            ''
        );
        """,
    ),
    (
        7,
        """
        CREATE TABLE recording (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            practice_session_id INTEGER REFERENCES practice_session(id) ON DELETE SET NULL,
            relative_file_path TEXT NOT NULL UNIQUE,
            format TEXT NOT NULL DEFAULT 'wav',
            duration_ms INTEGER,
            device_descriptor TEXT,
            status TEXT NOT NULL DEFAULT 'recording',
            failure_detail TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE microphone_preference (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            device_id TEXT NOT NULL,
            device_description TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        8,
        """
        -- Defensive cleanup before the index below: the application already
        -- prevents more than one 'recording'-status row, but a migration must
        -- not fail outright if a pre-existing database somehow has more than
        -- one (only the most recently created is kept in progress).
        UPDATE recording
        SET status = 'failed',
            failure_detail = 'Recovered during migration: duplicate in-progress recording detected.',
            updated_at = datetime('now')
        WHERE status = 'recording'
          AND id NOT IN (SELECT id FROM recording WHERE status = 'recording' ORDER BY id DESC LIMIT 1);

        -- Enforces "at most one recording in progress" at the database level,
        -- not just in application code (mirrors idx_practice_session_one_active_per_material).
        CREATE UNIQUE INDEX idx_recording_one_in_progress
            ON recording(status)
            WHERE status = 'recording';
        """,
    ),
    (
        9,
        """
        -- Milestone 10 (Quick Practice Mode): an additive model of its own,
        -- deliberately not forced into the five-stage practice_session/
        -- session_stage_progress schema (see ARCHITECTURE.md). Quick Practice
        -- has no exact-step resume, so unlike practice_session there is no
        -- last_resumed_at column here.
        CREATE TABLE quick_practice_session (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL DEFAULT 'selected',
            requested_count INTEGER NOT NULL,
            actual_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            abandoned_at TEXT
        );

        CREATE TABLE quick_practice_item (
            id INTEGER PRIMARY KEY,
            quick_practice_session_id INTEGER NOT NULL REFERENCES quick_practice_session(id) ON DELETE CASCADE,
            subtitle_cue_id INTEGER NOT NULL REFERENCES subtitle_cue(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            recall_result TEXT,
            heard_fragment TEXT,
            transcript_revealed INTEGER NOT NULL DEFAULT 0,
            shadowed_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (quick_practice_session_id, position),
            UNIQUE (quick_practice_session_id, subtitle_cue_id)
        );

        -- Mirrors session_diagnosis_evidence's design (Milestone 5): a full
        -- snapshot plus an optional link to the shared material-level
        -- Annotation, scoped to a quick_practice_item instead of a
        -- (practice_session_id, subtitle_cue_id) pair. This is what gives
        -- diagnosis recorded through Quick Practice its own explicit
        -- provenance, distinct from Intensive Practice's session_diagnosis_
        -- evidence, without creating a second copy of annotation truth.
        CREATE TABLE quick_practice_diagnosis_evidence (
            id INTEGER PRIMARY KEY,
            quick_practice_item_id INTEGER NOT NULL REFERENCES quick_practice_item(id) ON DELETE CASCADE,
            annotation_id INTEGER REFERENCES annotation(id) ON DELETE SET NULL,
            label_key TEXT NOT NULL,
            selected_text TEXT NOT NULL,
            selection_start INTEGER NOT NULL,
            selection_end INTEGER NOT NULL,
            heard_as TEXT,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (quick_practice_item_id, label_key, selection_start, selection_end),
            CHECK (selection_end >= selection_start)
        );
        """,
    ),
]


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations in order. Safe to call repeatedly (idempotent)."""
    version = current_version(conn)
    for target_version, sql in MIGRATIONS:
        if target_version <= version:
            continue
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {target_version}")
        conn.commit()
        version = target_version
    return version

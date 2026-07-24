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

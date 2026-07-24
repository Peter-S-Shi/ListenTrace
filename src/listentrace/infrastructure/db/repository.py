from __future__ import annotations

import sqlite3

from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleTrack


def insert_material(conn: sqlite3.Connection, material: Material) -> int:
    cursor = conn.execute(
        """
        INSERT INTO material (
            title, language, media_path, media_kind,
            duration_ms, file_size_bytes, file_fingerprint, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            material.title,
            material.language,
            material.media_path,
            material.media_kind,
            material.duration_ms,
            material.file_size_bytes,
            material.file_fingerprint,
            material.status,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_material(conn: sqlite3.Connection, material_id: int) -> Material | None:
    row = conn.execute("SELECT * FROM material WHERE id = ?", (material_id,)).fetchone()
    if row is None:
        return None
    return Material(
        id=row["id"],
        title=row["title"],
        language=row["language"],
        media_path=row["media_path"],
        media_kind=row["media_kind"],
        duration_ms=row["duration_ms"],
        file_size_bytes=row["file_size_bytes"],
        file_fingerprint=row["file_fingerprint"],
        status=row["status"],
    )


def insert_subtitle_track(conn: sqlite3.Connection, track: SubtitleTrack) -> int:
    cursor = conn.execute(
        """
        INSERT INTO subtitle_track (
            material_id, format, language, source_path, is_timed, encoding
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            track.material_id,
            track.format,
            track.language,
            track.source_path,
            int(track.is_timed),
            track.encoding,
        ),
    )
    track_id = int(cursor.lastrowid)

    conn.executemany(
        """
        INSERT INTO subtitle_cue (
            subtitle_track_id, cue_index, start_ms, end_ms, text, normalized_text
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (track_id, cue.cue_index, cue.start_ms, cue.end_ms, cue.text, cue.normalized_text)
            for cue in track.cues
        ],
    )
    conn.commit()
    return track_id


def get_cue_count(conn: sqlite3.Connection, subtitle_track_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM subtitle_cue WHERE subtitle_track_id = ?",
        (subtitle_track_id,),
    ).fetchone()
    return int(row[0])

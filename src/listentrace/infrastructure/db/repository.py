from __future__ import annotations

import sqlite3

from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack


def _row_to_material(row: sqlite3.Row) -> Material:
    return Material(
        id=row["id"],
        title=row["title"],
        language=row["language"],
        media_path=row["media_path"],
        normalized_path=row["normalized_path"],
        media_kind=row["media_kind"],
        duration_ms=row["duration_ms"],
        file_size_bytes=row["file_size_bytes"],
        file_fingerprint=row["file_fingerprint"],
        status=row["status"],
    )


def insert_material(conn: sqlite3.Connection, material: Material) -> int:
    cursor = conn.execute(
        """
        INSERT INTO material (
            title, language, media_path, normalized_path, media_kind,
            duration_ms, file_size_bytes, file_fingerprint, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            material.title,
            material.language,
            material.media_path,
            material.normalized_path,
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
    return _row_to_material(row)


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


def _row_to_cue(row: sqlite3.Row) -> SubtitleCue:
    return SubtitleCue(
        id=row["id"],
        cue_index=row["cue_index"],
        start_ms=row["start_ms"],
        end_ms=row["end_ms"],
        text=row["text"],
        normalized_text=row["normalized_text"],
    )


def get_cues_for_track(conn: sqlite3.Connection, subtitle_track_id: int) -> list[SubtitleCue]:
    rows = conn.execute(
        "SELECT * FROM subtitle_cue WHERE subtitle_track_id = ? ORDER BY cue_index",
        (subtitle_track_id,),
    ).fetchall()
    return [_row_to_cue(row) for row in rows]


def get_cue_by_id(conn: sqlite3.Connection, subtitle_cue_id: int) -> SubtitleCue | None:
    row = conn.execute(
        "SELECT * FROM subtitle_cue WHERE id = ?", (subtitle_cue_id,)
    ).fetchone()
    return _row_to_cue(row) if row is not None else None


def create_material_package(
    conn: sqlite3.Connection, material: Material, track: SubtitleTrack
) -> tuple[int, int]:
    """Insert a material, its subtitle track, and cues as a single all-or-nothing transaction."""
    try:
        cursor = conn.execute(
            """
            INSERT INTO material (
                title, language, media_path, normalized_path, media_kind,
                duration_ms, file_size_bytes, file_fingerprint, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                material.title,
                material.language,
                material.media_path,
                material.normalized_path,
                material.media_kind,
                material.duration_ms,
                material.file_size_bytes,
                material.file_fingerprint,
                material.status,
            ),
        )
        material_id = int(cursor.lastrowid)

        track_cursor = conn.execute(
            """
            INSERT INTO subtitle_track (
                material_id, format, language, source_path, is_timed, encoding
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                material_id,
                track.format,
                track.language,
                track.source_path,
                int(track.is_timed),
                track.encoding,
            ),
        )
        track_id = int(track_cursor.lastrowid)

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
    except Exception:
        conn.rollback()
        raise

    conn.commit()
    return material_id, track_id


def find_material_by_normalized_path(
    conn: sqlite3.Connection, normalized_path: str
) -> Material | None:
    row = conn.execute(
        "SELECT * FROM material WHERE normalized_path = ?", (normalized_path,)
    ).fetchone()
    return _row_to_material(row) if row is not None else None


def find_material_by_fingerprint(
    conn: sqlite3.Connection, file_fingerprint: str
) -> Material | None:
    row = conn.execute(
        "SELECT * FROM material WHERE file_fingerprint = ? LIMIT 1", (file_fingerprint,)
    ).fetchone()
    return _row_to_material(row) if row is not None else None


def list_materials_by_status(conn: sqlite3.Connection, status: MaterialStatus) -> list[Material]:
    rows = conn.execute(
        "SELECT * FROM material WHERE status = ? ORDER BY title COLLATE NOCASE",
        (status.value,),
    ).fetchall()
    return [_row_to_material(row) for row in rows]


def rename_material(conn: sqlite3.Connection, material_id: int, new_title: str) -> None:
    conn.execute(
        "UPDATE material SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (new_title, material_id),
    )
    conn.commit()


def set_material_status(
    conn: sqlite3.Connection, material_id: int, status: MaterialStatus
) -> None:
    conn.execute(
        "UPDATE material SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status.value, material_id),
    )
    conn.commit()


def delete_material(conn: sqlite3.Connection, material_id: int) -> None:
    conn.execute("DELETE FROM material WHERE id = ?", (material_id,))
    conn.commit()


def get_subtitle_track_for_material(
    conn: sqlite3.Connection, material_id: int
) -> SubtitleTrack | None:
    row = conn.execute(
        "SELECT * FROM subtitle_track WHERE material_id = ? ORDER BY id DESC LIMIT 1",
        (material_id,),
    ).fetchone()
    if row is None:
        return None
    return SubtitleTrack(
        id=row["id"],
        material_id=row["material_id"],
        format=row["format"],
        language=row["language"],
        source_path=row["source_path"],
        is_timed=bool(row["is_timed"]),
        encoding=row["encoding"],
        cues=[],
    )

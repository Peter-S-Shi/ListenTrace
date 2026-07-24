from __future__ import annotations

import sqlite3

from listentrace.domain.models.microphone_preference import MicrophonePreference
from listentrace.domain.models.recording import Recording

# ---- row conversion ----


def _row_to_recording(row: sqlite3.Row) -> Recording:
    return Recording(
        id=row["id"],
        material_id=row["material_id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        practice_session_id=row["practice_session_id"],
        relative_file_path=row["relative_file_path"],
        format=row["format"],
        duration_ms=row["duration_ms"],
        device_descriptor=row["device_descriptor"],
        status=row["status"],
        failure_detail=row["failure_detail"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_microphone_preference(row: sqlite3.Row) -> MicrophonePreference:
    return MicrophonePreference(
        device_id=row["device_id"],
        device_description=row["device_description"],
        updated_at=row["updated_at"],
    )


# ---- recording ----


def insert_recording(conn: sqlite3.Connection, recording: Recording) -> int:
    cursor = conn.execute(
        """
        INSERT INTO recording (
            material_id, subtitle_cue_id, practice_session_id, relative_file_path,
            format, device_descriptor, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            recording.material_id,
            recording.subtitle_cue_id,
            recording.practice_session_id,
            recording.relative_file_path,
            recording.format,
            recording.device_descriptor,
            recording.status,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_recording(conn: sqlite3.Connection, recording_id: int) -> Recording | None:
    row = conn.execute("SELECT * FROM recording WHERE id = ?", (recording_id,)).fetchone()
    return _row_to_recording(row) if row is not None else None


def list_recordings_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[Recording]:
    rows = conn.execute(
        "SELECT * FROM recording WHERE subtitle_cue_id = ? ORDER BY id", (subtitle_cue_id,)
    ).fetchall()
    return [_row_to_recording(row) for row in rows]


def list_recordings_for_material(conn: sqlite3.Connection, material_id: int) -> list[Recording]:
    rows = conn.execute(
        "SELECT * FROM recording WHERE material_id = ? ORDER BY id", (material_id,)
    ).fetchall()
    return [_row_to_recording(row) for row in rows]


def list_recordings_with_status(conn: sqlite3.Connection, status: str) -> list[Recording]:
    rows = conn.execute("SELECT * FROM recording WHERE status = ? ORDER BY id", (status,)).fetchall()
    return [_row_to_recording(row) for row in rows]


def set_recording_ready(conn: sqlite3.Connection, recording_id: int, duration_ms: int) -> None:
    conn.execute(
        "UPDATE recording SET status = 'ready', duration_ms = ?, updated_at = datetime('now') WHERE id = ?",
        (duration_ms, recording_id),
    )
    conn.commit()


def set_recording_failed(conn: sqlite3.Connection, recording_id: int, failure_detail: str) -> None:
    conn.execute(
        "UPDATE recording SET status = 'failed', failure_detail = ?, updated_at = datetime('now') WHERE id = ?",
        (failure_detail, recording_id),
    )
    conn.commit()


def delete_recording(conn: sqlite3.Connection, recording_id: int) -> None:
    conn.execute("DELETE FROM recording WHERE id = ?", (recording_id,))
    conn.commit()


# ---- microphone_preference (singleton row, id = 1) ----


def get_microphone_preference(conn: sqlite3.Connection) -> MicrophonePreference | None:
    row = conn.execute("SELECT * FROM microphone_preference WHERE id = 1").fetchone()
    return _row_to_microphone_preference(row) if row is not None else None


def set_microphone_preference(conn: sqlite3.Connection, device_id: str, device_description: str) -> None:
    conn.execute(
        """
        INSERT INTO microphone_preference (id, device_id, device_description)
        VALUES (1, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            device_id = excluded.device_id,
            device_description = excluded.device_description,
            updated_at = datetime('now')
        """,
        (device_id, device_description),
    )
    conn.commit()

from __future__ import annotations

import sqlite3

"""Narrow, Milestone-9-specific read queries not already covered by an
existing repository. Everything else the exporter needs (sessions, stage
responses, keyword captures, session diagnosis, quiz attempts/questions/
answers, current annotations, shadowing evidence, retained recordings, saved
language items) is read directly from the existing `session_repository`,
`quiz_repository`, `learning_repository`, and `history_repository` modules —
see `application/services/export_service.py`, which is the only caller of
both this module and those.
"""


def list_materials_for_export(
    conn: sqlite3.Connection, material_ids: list[int] | None = None
) -> list[sqlite3.Row]:
    """Material rows carrying the fields Milestone 9 needs that the shared
    `Material` domain model does not expose (`created_at`) — a materials-only
    query so callers don't need to touch subtitle/session/quiz tables here.
    `material_ids=None` returns every material (active and archived), else
    exactly the requested ids, in the given id order."""
    if material_ids is not None:
        if not material_ids:
            return []
        placeholders = ", ".join("?" for _ in material_ids)
        rows = conn.execute(
            f"""
            SELECT id, title, language, media_kind, media_path, duration_ms, status, created_at
            FROM material WHERE id IN ({placeholders})
            """,
            material_ids,
        ).fetchall()
        by_id = {row["id"]: row for row in rows}
        return [by_id[i] for i in material_ids if i in by_id]
    return conn.execute(
        """
        SELECT id, title, language, media_kind, media_path, duration_ms, status, created_at
        FROM material ORDER BY title COLLATE NOCASE
        """
    ).fetchall()


def list_cue_notes_for_material(conn: sqlite3.Connection, material_id: int) -> list[sqlite3.Row]:
    """Every free-form Cue Note (Milestone 4) for one material, joined with
    its cue text — a genuinely separate evidence source from guided-session
    stage responses (see `domain/services/export_privacy.py`'s
    `CATEGORY_LEARNER_NOTES` docstring)."""
    return conn.execute(
        """
        SELECT cue_note.subtitle_cue_id AS subtitle_cue_id, subtitle_cue.text AS cue_text,
               cue_note.note_text AS note_text, cue_note.updated_at AS updated_at
        FROM cue_note
        JOIN subtitle_cue ON subtitle_cue.id = cue_note.subtitle_cue_id
        JOIN subtitle_track ON subtitle_track.id = subtitle_cue.subtitle_track_id
        WHERE subtitle_track.material_id = ?
        ORDER BY subtitle_cue.cue_index
        """,
        (material_id,),
    ).fetchall()


def get_subtitle_capability_for_material(conn: sqlite3.Connection, material_id: int) -> str:
    """`"timed"` / `"plain_text"` / `"none"` — never the subtitle file's
    path, only whether Milestone 3's timed-navigation capability is
    available. Mirrors `repository.get_subtitle_track_for_material`'s own
    "most recent track wins" convention."""
    row = conn.execute(
        "SELECT is_timed FROM subtitle_track WHERE material_id = ? ORDER BY id DESC LIMIT 1",
        (material_id,),
    ).fetchone()
    if row is None:
        return "none"
    return "timed" if row["is_timed"] else "plain_text"

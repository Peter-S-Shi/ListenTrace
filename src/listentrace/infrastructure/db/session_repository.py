from __future__ import annotations

import sqlite3

from listentrace.domain.enums.stage_key import STAGE_ORDER
from listentrace.domain.models.keyword_capture import KeywordCapture
from listentrace.domain.models.practice_session import PracticeSession
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.models.session_stage_progress import SessionStageProgress
from listentrace.domain.models.shadowing_cue_progress import ShadowingCueProgress
from listentrace.domain.models.stage_response import StageResponse

# ---- row conversion ----


def _row_to_session(row: sqlite3.Row) -> PracticeSession:
    return PracticeSession(
        id=row["id"],
        material_id=row["material_id"],
        mode=row["mode"],
        status=row["status"],
        current_stage=row["current_stage"],
        transcript_revealed_at=row["transcript_revealed_at"],
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        last_resumed_at=row["last_resumed_at"],
        completed_at=row["completed_at"],
        abandoned_at=row["abandoned_at"],
    )


def _row_to_stage_progress(row: sqlite3.Row) -> SessionStageProgress:
    return SessionStageProgress(
        practice_session_id=row["practice_session_id"],
        stage_key=row["stage_key"],
        status=row["status"],
        outcome_key=row["outcome_key"],
        skip_note=row["skip_note"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        skipped_at=row["skipped_at"],
        updated_at=row["updated_at"],
    )


def _row_to_stage_response(row: sqlite3.Row) -> StageResponse:
    return StageResponse(
        id=row["id"],
        practice_session_id=row["practice_session_id"],
        stage_key=row["stage_key"],
        prompt_key=row["prompt_key"],
        response_text=row["response_text"],
    )


def _row_to_keyword_capture(row: sqlite3.Row) -> KeywordCapture:
    return KeywordCapture(
        id=row["id"],
        practice_session_id=row["practice_session_id"],
        capture_type=row["capture_type"],
        text=row["text"],
        position=row["position"],
    )


def _row_to_diagnosis(row: sqlite3.Row) -> SessionDiagnosisEvidence:
    return SessionDiagnosisEvidence(
        id=row["id"],
        practice_session_id=row["practice_session_id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        annotation_id=row["annotation_id"],
        label_key=row["label_key"],
        selected_text=row["selected_text"],
        selection_start=row["selection_start"],
        selection_end=row["selection_end"],
        heard_as=row["heard_as"],
        note=row["note"],
    )


def _row_to_shadowing_progress(row: sqlite3.Row) -> ShadowingCueProgress:
    return ShadowingCueProgress(
        practice_session_id=row["practice_session_id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        status=row["status"],
        practice_count=row["practice_count"],
        note=row["note"],
        last_practiced_at=row["last_practiced_at"],
    )


# ---- practice_session ----


def create_practice_session(conn: sqlite3.Connection, material_id: int, mode: str = "intensive") -> int:
    """Create a session plus its five stage-progress rows as a single all-or-nothing
    transaction, so a session can never exist with a missing or partial stage set."""
    try:
        cursor = conn.execute(
            "INSERT INTO practice_session (material_id, mode) VALUES (?, ?)",
            (material_id, mode),
        )
        session_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO session_stage_progress (practice_session_id, stage_key) VALUES (?, ?)",
            [(session_id, stage_key) for stage_key in STAGE_ORDER],
        )
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return session_id


def get_practice_session(conn: sqlite3.Connection, session_id: int) -> PracticeSession | None:
    row = conn.execute("SELECT * FROM practice_session WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row) if row is not None else None


def find_active_session_for_material(
    conn: sqlite3.Connection, material_id: int, mode: str = "intensive"
) -> PracticeSession | None:
    row = conn.execute(
        "SELECT * FROM practice_session WHERE material_id = ? AND mode = ? AND status = 'active'",
        (material_id, mode),
    ).fetchone()
    return _row_to_session(row) if row is not None else None


def list_sessions_for_material(conn: sqlite3.Connection, material_id: int) -> list[PracticeSession]:
    rows = conn.execute(
        "SELECT * FROM practice_session WHERE material_id = ? ORDER BY id DESC",
        (material_id,),
    ).fetchall()
    return [_row_to_session(row) for row in rows]


def set_session_status(conn: sqlite3.Connection, session_id: int, status: str) -> None:
    column = {"completed": "completed_at", "abandoned": "abandoned_at"}.get(status)
    if column is not None:
        conn.execute(
            f"UPDATE practice_session SET status = ?, {column} = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    else:
        conn.execute(
            "UPDATE practice_session SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    conn.commit()


def touch_session_resumed(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        "UPDATE practice_session SET last_resumed_at = datetime('now'), "
        "updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()


def set_current_stage(conn: sqlite3.Connection, session_id: int, stage_key: str) -> None:
    conn.execute(
        "UPDATE practice_session SET current_stage = ?, updated_at = datetime('now') WHERE id = ?",
        (stage_key, session_id),
    )
    conn.commit()


def set_transcript_revealed(conn: sqlite3.Connection, session_id: int) -> None:
    """Idempotent: only the first call actually sets the timestamp."""
    conn.execute(
        "UPDATE practice_session SET "
        "transcript_revealed_at = COALESCE(transcript_revealed_at, datetime('now')), "
        "updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()


# ---- session_stage_progress ----


def get_stage_progress(
    conn: sqlite3.Connection, session_id: int, stage_key: str
) -> SessionStageProgress | None:
    row = conn.execute(
        "SELECT * FROM session_stage_progress WHERE practice_session_id = ? AND stage_key = ?",
        (session_id, stage_key),
    ).fetchone()
    return _row_to_stage_progress(row) if row is not None else None


def list_stage_progress(conn: sqlite3.Connection, session_id: int) -> list[SessionStageProgress]:
    rows = conn.execute(
        "SELECT * FROM session_stage_progress WHERE practice_session_id = ?",
        (session_id,),
    ).fetchall()
    by_key = {row["stage_key"]: _row_to_stage_progress(row) for row in rows}
    return [by_key[key] for key in STAGE_ORDER if key in by_key]


def set_stage_status(
    conn: sqlite3.Connection,
    session_id: int,
    stage_key: str,
    status: str,
    skip_note: str | None = None,
) -> None:
    timestamp_column = {"in_progress": "started_at", "completed": "completed_at", "skipped": "skipped_at"}.get(
        status
    )
    if timestamp_column == "started_at":
        # Only the first entry into a stage sets started_at.
        conn.execute(
            f"UPDATE session_stage_progress SET status = ?, "
            f"{timestamp_column} = COALESCE({timestamp_column}, datetime('now')), "
            "updated_at = datetime('now') WHERE practice_session_id = ? AND stage_key = ?",
            (status, session_id, stage_key),
        )
    elif timestamp_column is not None:
        conn.execute(
            f"UPDATE session_stage_progress SET status = ?, {timestamp_column} = datetime('now'), "
            "skip_note = ?, updated_at = datetime('now') "
            "WHERE practice_session_id = ? AND stage_key = ?",
            (status, skip_note, session_id, stage_key),
        )
    else:
        conn.execute(
            "UPDATE session_stage_progress SET status = ?, updated_at = datetime('now') "
            "WHERE practice_session_id = ? AND stage_key = ?",
            (status, session_id, stage_key),
        )
    conn.commit()


def set_stage_outcome(
    conn: sqlite3.Connection, session_id: int, stage_key: str, outcome_key: str | None
) -> None:
    conn.execute(
        "UPDATE session_stage_progress SET outcome_key = ?, updated_at = datetime('now') "
        "WHERE practice_session_id = ? AND stage_key = ?",
        (outcome_key, session_id, stage_key),
    )
    conn.commit()


# ---- stage_response ----


def upsert_stage_response(
    conn: sqlite3.Connection, session_id: int, stage_key: str, prompt_key: str, response_text: str
) -> None:
    conn.execute(
        """
        INSERT INTO stage_response (practice_session_id, stage_key, prompt_key, response_text)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (practice_session_id, stage_key, prompt_key) DO UPDATE SET
            response_text = excluded.response_text,
            updated_at = datetime('now')
        """,
        (session_id, stage_key, prompt_key, response_text),
    )
    conn.commit()


def list_stage_responses(
    conn: sqlite3.Connection, session_id: int, stage_key: str | None = None
) -> list[StageResponse]:
    if stage_key is None:
        rows = conn.execute(
            "SELECT * FROM stage_response WHERE practice_session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM stage_response WHERE practice_session_id = ? AND stage_key = ? ORDER BY id",
            (session_id, stage_key),
        ).fetchall()
    return [_row_to_stage_response(row) for row in rows]


# ---- keyword_capture ----


def next_keyword_capture_position(conn: sqlite3.Connection, session_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM keyword_capture "
        "WHERE practice_session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row["next_position"])


def insert_keyword_capture(
    conn: sqlite3.Connection, session_id: int, capture_type: str, text: str, position: int
) -> int:
    cursor = conn.execute(
        "INSERT INTO keyword_capture (practice_session_id, capture_type, text, position) "
        "VALUES (?, ?, ?, ?)",
        (session_id, capture_type, text, position),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_keyword_capture(conn: sqlite3.Connection, capture_id: int) -> KeywordCapture | None:
    row = conn.execute("SELECT * FROM keyword_capture WHERE id = ?", (capture_id,)).fetchone()
    return _row_to_keyword_capture(row) if row is not None else None


def update_keyword_capture(conn: sqlite3.Connection, capture_id: int, capture_type: str, text: str) -> None:
    conn.execute(
        "UPDATE keyword_capture SET capture_type = ?, text = ?, updated_at = datetime('now') WHERE id = ?",
        (capture_type, text, capture_id),
    )
    conn.commit()


def delete_keyword_capture(conn: sqlite3.Connection, capture_id: int) -> None:
    conn.execute("DELETE FROM keyword_capture WHERE id = ?", (capture_id,))
    conn.commit()


def list_keyword_captures(conn: sqlite3.Connection, session_id: int) -> list[KeywordCapture]:
    rows = conn.execute(
        "SELECT * FROM keyword_capture WHERE practice_session_id = ? ORDER BY position, id",
        (session_id,),
    ).fetchall()
    return [_row_to_keyword_capture(row) for row in rows]


def reorder_keyword_captures(conn: sqlite3.Connection, session_id: int, ordered_ids: list[int]) -> None:
    """Rewrite `position` for every capture id in `ordered_ids`, atomically."""
    try:
        conn.executemany(
            "UPDATE keyword_capture SET position = ?, updated_at = datetime('now') "
            "WHERE id = ? AND practice_session_id = ?",
            [(index, capture_id, session_id) for index, capture_id in enumerate(ordered_ids)],
        )
    except Exception:
        conn.rollback()
        raise
    conn.commit()


# ---- session_diagnosis_evidence ----


def find_session_diagnosis_exact(
    conn: sqlite3.Connection,
    session_id: int,
    subtitle_cue_id: int,
    label_key: str,
    selection_start: int,
    selection_end: int,
) -> SessionDiagnosisEvidence | None:
    row = conn.execute(
        "SELECT * FROM session_diagnosis_evidence WHERE practice_session_id = ? AND subtitle_cue_id = ? "
        "AND label_key = ? AND selection_start = ? AND selection_end = ?",
        (session_id, subtitle_cue_id, label_key, selection_start, selection_end),
    ).fetchone()
    return _row_to_diagnosis(row) if row is not None else None


def insert_session_diagnosis(conn: sqlite3.Connection, evidence: SessionDiagnosisEvidence) -> int:
    cursor = conn.execute(
        """
        INSERT INTO session_diagnosis_evidence (
            practice_session_id, subtitle_cue_id, annotation_id, label_key,
            selected_text, selection_start, selection_end, heard_as, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence.practice_session_id,
            evidence.subtitle_cue_id,
            evidence.annotation_id,
            evidence.label_key,
            evidence.selected_text,
            evidence.selection_start,
            evidence.selection_end,
            evidence.heard_as,
            evidence.note,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_session_diagnosis(conn: sqlite3.Connection, evidence_id: int) -> SessionDiagnosisEvidence | None:
    row = conn.execute(
        "SELECT * FROM session_diagnosis_evidence WHERE id = ?", (evidence_id,)
    ).fetchone()
    return _row_to_diagnosis(row) if row is not None else None


def list_session_diagnosis(conn: sqlite3.Connection, session_id: int) -> list[SessionDiagnosisEvidence]:
    rows = conn.execute(
        "SELECT * FROM session_diagnosis_evidence WHERE practice_session_id = ? ORDER BY selection_start, id",
        (session_id,),
    ).fetchall()
    return [_row_to_diagnosis(row) for row in rows]


def list_session_diagnosis_for_cue(
    conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int
) -> list[SessionDiagnosisEvidence]:
    rows = conn.execute(
        "SELECT * FROM session_diagnosis_evidence WHERE practice_session_id = ? AND subtitle_cue_id = ? "
        "ORDER BY selection_start, id",
        (session_id, subtitle_cue_id),
    ).fetchall()
    return [_row_to_diagnosis(row) for row in rows]


def update_session_diagnosis(
    conn: sqlite3.Connection,
    evidence_id: int,
    annotation_id: int | None,
    label_key: str,
    selected_text: str,
    selection_start: int,
    selection_end: int,
    heard_as: str | None,
    note: str | None,
) -> None:
    """Updates the session snapshot row, including which `annotation` row (if any)
    it links to — the caller is responsible for re-deriving `annotation_id` to
    match the new label/range. Never mutates the `annotation` row itself, only
    which row this snapshot points at."""
    conn.execute(
        """
        UPDATE session_diagnosis_evidence
        SET annotation_id = ?, label_key = ?, selected_text = ?, selection_start = ?, selection_end = ?,
            heard_as = ?, note = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (annotation_id, label_key, selected_text, selection_start, selection_end, heard_as, note, evidence_id),
    )
    conn.commit()


def delete_session_diagnosis(conn: sqlite3.Connection, evidence_id: int) -> None:
    """Deletes only the session snapshot row; never cascades to `annotation`."""
    conn.execute("DELETE FROM session_diagnosis_evidence WHERE id = ?", (evidence_id,))
    conn.commit()


def count_session_diagnosis(conn: sqlite3.Connection, session_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM session_diagnosis_evidence WHERE practice_session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row["n"])


# ---- shadowing_cue_progress ----


def ensure_shadowing_rows(conn: sqlite3.Connection, session_id: int, subtitle_cue_ids: list[int]) -> None:
    """Eagerly create one `not_started` row per cue. Safe to call repeatedly:
    an existing row for a cue is left untouched (`INSERT OR IGNORE`)."""
    conn.executemany(
        "INSERT OR IGNORE INTO shadowing_cue_progress (practice_session_id, subtitle_cue_id) VALUES (?, ?)",
        [(session_id, cue_id) for cue_id in subtitle_cue_ids],
    )
    conn.commit()


def get_shadowing_progress(
    conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int
) -> ShadowingCueProgress | None:
    row = conn.execute(
        "SELECT * FROM shadowing_cue_progress WHERE practice_session_id = ? AND subtitle_cue_id = ?",
        (session_id, subtitle_cue_id),
    ).fetchone()
    return _row_to_shadowing_progress(row) if row is not None else None


def list_shadowing_progress(conn: sqlite3.Connection, session_id: int) -> list[ShadowingCueProgress]:
    rows = conn.execute(
        "SELECT * FROM shadowing_cue_progress WHERE practice_session_id = ? ORDER BY subtitle_cue_id",
        (session_id,),
    ).fetchall()
    return [_row_to_shadowing_progress(row) for row in rows]


def mark_shadowing_practiced(conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int) -> None:
    conn.execute(
        "UPDATE shadowing_cue_progress SET status = 'practiced', practice_count = practice_count + 1, "
        "last_practiced_at = datetime('now'), updated_at = datetime('now') "
        "WHERE practice_session_id = ? AND subtitle_cue_id = ?",
        (session_id, subtitle_cue_id),
    )
    conn.commit()


def set_shadowing_note(
    conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int, note: str | None
) -> None:
    conn.execute(
        "UPDATE shadowing_cue_progress SET note = ?, updated_at = datetime('now') "
        "WHERE practice_session_id = ? AND subtitle_cue_id = ?",
        (note, session_id, subtitle_cue_id),
    )
    conn.commit()


def mark_shadowing_skipped(conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int) -> None:
    conn.execute(
        "UPDATE shadowing_cue_progress SET status = 'skipped', updated_at = datetime('now') "
        "WHERE practice_session_id = ? AND subtitle_cue_id = ?",
        (session_id, subtitle_cue_id),
    )
    conn.commit()


def skip_remaining_shadowing(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        "UPDATE shadowing_cue_progress SET status = 'skipped', updated_at = datetime('now') "
        "WHERE practice_session_id = ? AND status = 'not_started'",
        (session_id,),
    )
    conn.commit()


def count_unresolved_shadowing(conn: sqlite3.Connection, session_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM shadowing_cue_progress "
        "WHERE practice_session_id = ? AND status = 'not_started'",
        (session_id,),
    ).fetchone()
    return int(row["n"])

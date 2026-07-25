from __future__ import annotations

import sqlite3

from listentrace.domain.models.quick_practice_diagnosis_evidence import QuickPracticeDiagnosisEvidence
from listentrace.domain.models.quick_practice_item import QuickPracticeItem
from listentrace.domain.models.quick_practice_session import QuickPracticeSession

"""Live-workflow persistence for Milestone 10 (Quick Practice Mode) —
mirrors `session_repository.py`'s role for `practice_session`. Cross-
material reporting (Learning History, Needs Attention, export) reads these
same tables independently through `history_repository.py`'s own SQL, the
same split already used for `practice_session`/`quiz_attempt`."""


# ---- row conversion ----


def _row_to_session(row: sqlite3.Row) -> QuickPracticeSession:
    return QuickPracticeSession(
        id=row["id"],
        material_id=row["material_id"],
        source_type=row["source_type"],
        requested_count=row["requested_count"],
        actual_count=row["actual_count"],
        status=row["status"],
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        abandoned_at=row["abandoned_at"],
    )


def _row_to_item(row: sqlite3.Row) -> QuickPracticeItem:
    return QuickPracticeItem(
        id=row["id"],
        quick_practice_session_id=row["quick_practice_session_id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        position=row["position"],
        recall_result=row["recall_result"],
        heard_fragment=row["heard_fragment"],
        transcript_revealed=bool(row["transcript_revealed"]),
        shadowed_at=row["shadowed_at"],
        completed_at=row["completed_at"],
    )


def _row_to_diagnosis(row: sqlite3.Row) -> QuickPracticeDiagnosisEvidence:
    return QuickPracticeDiagnosisEvidence(
        id=row["id"],
        quick_practice_item_id=row["quick_practice_item_id"],
        annotation_id=row["annotation_id"],
        label_key=row["label_key"],
        selected_text=row["selected_text"],
        selection_start=row["selection_start"],
        selection_end=row["selection_end"],
        heard_as=row["heard_as"],
        note=row["note"],
    )


# ---- quick_practice_session ----


def create_quick_practice_session(
    conn: sqlite3.Connection,
    material_id: int,
    source_type: str,
    requested_count: int,
    ordered_subtitle_cue_ids: list[int],
) -> int:
    """Creates the session plus one item per cue (in the given order) as a
    single all-or-nothing transaction, so a session can never exist with a
    missing or partial item set — mirrors `session_repository.
    create_practice_session`."""
    try:
        cursor = conn.execute(
            "INSERT INTO quick_practice_session (material_id, source_type, requested_count, actual_count) "
            "VALUES (?, ?, ?, ?)",
            (material_id, source_type, requested_count, len(ordered_subtitle_cue_ids)),
        )
        session_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO quick_practice_item (quick_practice_session_id, subtitle_cue_id, position) "
            "VALUES (?, ?, ?)",
            [(session_id, cue_id, position) for position, cue_id in enumerate(ordered_subtitle_cue_ids)],
        )
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return session_id


def get_quick_practice_session(conn: sqlite3.Connection, session_id: int) -> QuickPracticeSession | None:
    row = conn.execute("SELECT * FROM quick_practice_session WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row) if row is not None else None


def list_active_quick_practice_sessions(conn: sqlite3.Connection) -> list[QuickPracticeSession]:
    """Every session still `active` — used only for startup crash recovery
    (a fresh process can never own an in-progress Quick Practice run)."""
    rows = conn.execute("SELECT * FROM quick_practice_session WHERE status = 'active'").fetchall()
    return [_row_to_session(row) for row in rows]


def set_quick_practice_session_status(conn: sqlite3.Connection, session_id: int, status: str) -> None:
    column = {"completed": "completed_at", "abandoned": "abandoned_at"}.get(status)
    if column is not None:
        conn.execute(
            f"UPDATE quick_practice_session SET status = ?, {column} = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    else:
        conn.execute(
            "UPDATE quick_practice_session SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    conn.commit()


def delete_quick_practice_session(conn: sqlite3.Connection, session_id: int) -> None:
    """A hard delete — used only when a session is discarded with zero
    completed cues, so it never appears anywhere as misleading history."""
    conn.execute("DELETE FROM quick_practice_session WHERE id = ?", (session_id,))
    conn.commit()


# ---- quick_practice_item ----


def list_items(conn: sqlite3.Connection, session_id: int) -> list[QuickPracticeItem]:
    rows = conn.execute(
        "SELECT * FROM quick_practice_item WHERE quick_practice_session_id = ? ORDER BY position",
        (session_id,),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def get_item(conn: sqlite3.Connection, item_id: int) -> QuickPracticeItem | None:
    row = conn.execute("SELECT * FROM quick_practice_item WHERE id = ?", (item_id,)).fetchone()
    return _row_to_item(row) if row is not None else None


def set_item_recall(
    conn: sqlite3.Connection, item_id: int, recall_result: str, heard_fragment: str | None
) -> None:
    conn.execute(
        "UPDATE quick_practice_item SET recall_result = ?, heard_fragment = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (recall_result, heard_fragment, item_id),
    )
    conn.commit()


def set_item_transcript_revealed(conn: sqlite3.Connection, item_id: int) -> None:
    """Idempotent: only the first call has any effect."""
    conn.execute(
        "UPDATE quick_practice_item SET transcript_revealed = 1, updated_at = datetime('now') WHERE id = ?",
        (item_id,),
    )
    conn.commit()


def set_item_shadowed(conn: sqlite3.Connection, item_id: int) -> None:
    """Idempotent: only the first call actually sets the timestamp."""
    conn.execute(
        "UPDATE quick_practice_item SET shadowed_at = COALESCE(shadowed_at, datetime('now')), "
        "updated_at = datetime('now') WHERE id = ?",
        (item_id,),
    )
    conn.commit()


def set_item_completed(conn: sqlite3.Connection, item_id: int) -> None:
    """Idempotent: only the first call actually sets the timestamp."""
    conn.execute(
        "UPDATE quick_practice_item SET completed_at = COALESCE(completed_at, datetime('now')), "
        "updated_at = datetime('now') WHERE id = ?",
        (item_id,),
    )
    conn.commit()


def count_completed_items(conn: sqlite3.Connection, session_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM quick_practice_item "
        "WHERE quick_practice_session_id = ? AND completed_at IS NOT NULL",
        (session_id,),
    ).fetchone()
    return int(row["n"])


# ---- quick_practice_diagnosis_evidence ----


def find_item_diagnosis_exact(
    conn: sqlite3.Connection, item_id: int, label_key: str, selection_start: int, selection_end: int
) -> QuickPracticeDiagnosisEvidence | None:
    row = conn.execute(
        "SELECT * FROM quick_practice_diagnosis_evidence WHERE quick_practice_item_id = ? AND label_key = ? "
        "AND selection_start = ? AND selection_end = ?",
        (item_id, label_key, selection_start, selection_end),
    ).fetchone()
    return _row_to_diagnosis(row) if row is not None else None


def insert_item_diagnosis(conn: sqlite3.Connection, evidence: QuickPracticeDiagnosisEvidence) -> int:
    cursor = conn.execute(
        """
        INSERT INTO quick_practice_diagnosis_evidence (
            quick_practice_item_id, annotation_id, label_key,
            selected_text, selection_start, selection_end, heard_as, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence.quick_practice_item_id,
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


def get_item_diagnosis(conn: sqlite3.Connection, evidence_id: int) -> QuickPracticeDiagnosisEvidence | None:
    row = conn.execute(
        "SELECT * FROM quick_practice_diagnosis_evidence WHERE id = ?", (evidence_id,)
    ).fetchone()
    return _row_to_diagnosis(row) if row is not None else None


def list_item_diagnosis(conn: sqlite3.Connection, item_id: int) -> list[QuickPracticeDiagnosisEvidence]:
    rows = conn.execute(
        "SELECT * FROM quick_practice_diagnosis_evidence WHERE quick_practice_item_id = ? "
        "ORDER BY selection_start, id",
        (item_id,),
    ).fetchall()
    return [_row_to_diagnosis(row) for row in rows]


def list_diagnosis_for_session(conn: sqlite3.Connection, session_id: int) -> list[QuickPracticeDiagnosisEvidence]:
    rows = conn.execute(
        """
        SELECT quick_practice_diagnosis_evidence.* FROM quick_practice_diagnosis_evidence
        JOIN quick_practice_item ON quick_practice_item.id = quick_practice_diagnosis_evidence.quick_practice_item_id
        WHERE quick_practice_item.quick_practice_session_id = ?
        ORDER BY quick_practice_item.position, quick_practice_diagnosis_evidence.id
        """,
        (session_id,),
    ).fetchall()
    return [_row_to_diagnosis(row) for row in rows]


def delete_item_diagnosis(conn: sqlite3.Connection, evidence_id: int) -> None:
    conn.execute("DELETE FROM quick_practice_diagnosis_evidence WHERE id = ?", (evidence_id,))
    conn.commit()


def count_item_diagnosis(conn: sqlite3.Connection, item_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM quick_practice_diagnosis_evidence WHERE quick_practice_item_id = ?",
        (item_id,),
    ).fetchone()
    return int(row["n"])


# ---- recommendation evidence (read-only) ----
#
# "Recommended Practice" (see `domain/services/quick_practice_recommendation.py`)
# reads pre-existing Milestone 4-7 evidence plus one deliberate exception:
# explicit Quick Practice shadowing (`shadowed_at`) is real shadowing
# evidence and is folded into the same shadowing-practice count Intensive
# Practice contributes to. It still never reads Quick Practice's own recall
# outcomes, diagnosis evidence, or session history — only that one signal —
# so recommendations do not feed on their own outcomes.


def list_annotation_labels_by_cue(conn: sqlite3.Connection, material_id: int) -> dict[int, frozenset[str]]:
    rows = conn.execute(
        """
        SELECT annotation.subtitle_cue_id AS subtitle_cue_id, annotation.label_key AS label_key
        FROM annotation
        JOIN subtitle_cue ON subtitle_cue.id = annotation.subtitle_cue_id
        JOIN subtitle_track ON subtitle_track.id = subtitle_cue.subtitle_track_id
        WHERE subtitle_track.material_id = ?
        """,
        (material_id,),
    ).fetchall()
    result: dict[int, set[str]] = {}
    for row in rows:
        result.setdefault(row["subtitle_cue_id"], set()).add(row["label_key"])
    return {cue_id: frozenset(labels) for cue_id, labels in result.items()}


def list_annotation_recency_by_cue(conn: sqlite3.Connection, material_id: int) -> dict[int, str]:
    """Per cue: the most recent `created_at` among this cue's material
    annotations — a real timestamp, used only for tie-break ordering
    (annotation *presence*, not recency, is what qualifies a `marked_*`
    reason; see `quick_practice_recommendation.py`)."""
    rows = conn.execute(
        """
        SELECT annotation.subtitle_cue_id AS subtitle_cue_id, MAX(annotation.created_at) AS most_recent_at
        FROM annotation
        JOIN subtitle_cue ON subtitle_cue.id = annotation.subtitle_cue_id
        JOIN subtitle_track ON subtitle_track.id = subtitle_cue.subtitle_track_id
        WHERE subtitle_track.material_id = ?
        GROUP BY annotation.subtitle_cue_id
        """,
        (material_id,),
    ).fetchall()
    return {row["subtitle_cue_id"]: row["most_recent_at"] for row in rows}


def list_diagnosis_counts_by_cue(conn: sqlite3.Connection, material_id: int) -> dict[int, tuple[int, str | None]]:
    """Session-scoped diagnosis evidence (Milestone 5), per cue across every
    session on this material: (count, most recent `created_at`) —
    deliberately not combined with Quick Practice's own diagnosis evidence
    (see module docstring)."""
    rows = conn.execute(
        """
        SELECT session_diagnosis_evidence.subtitle_cue_id AS subtitle_cue_id, COUNT(*) AS n,
               MAX(session_diagnosis_evidence.created_at) AS most_recent_at
        FROM session_diagnosis_evidence
        JOIN practice_session ON practice_session.id = session_diagnosis_evidence.practice_session_id
        WHERE practice_session.material_id = ?
        GROUP BY session_diagnosis_evidence.subtitle_cue_id
        """,
        (material_id,),
    ).fetchall()
    return {row["subtitle_cue_id"]: (row["n"], row["most_recent_at"]) for row in rows}


def list_incorrect_quiz_evidence_by_cue(conn: sqlite3.Connection, material_id: int) -> dict[int, str]:
    """Per cue: the most recent `answered_at` among incorrect answers on
    completed quiz attempts — presence in this dict means the cue has at
    least one incorrect quiz evidence."""
    rows = conn.execute(
        """
        SELECT quiz_question.subtitle_cue_id AS subtitle_cue_id, MAX(quiz_answer.answered_at) AS most_recent_at
        FROM quiz_answer
        JOIN quiz_question ON quiz_question.id = quiz_answer.quiz_question_id
        JOIN quiz_attempt ON quiz_attempt.id = quiz_question.quiz_attempt_id
        WHERE quiz_attempt.material_id = ? AND quiz_attempt.status = 'completed' AND quiz_answer.is_correct = 0
        GROUP BY quiz_question.subtitle_cue_id
        """,
        (material_id,),
    ).fetchall()
    return {row["subtitle_cue_id"]: row["most_recent_at"] for row in rows}


def list_shadowing_stats_by_cue(conn: sqlite3.Connection, material_id: int) -> dict[int, tuple[int, str | None]]:
    """Per cue: (total practice_count summed across sessions, most recent
    last_practiced_at) — a cue absent from this dict has never been
    shadowed."""
    rows = conn.execute(
        """
        SELECT shadowing_cue_progress.subtitle_cue_id AS subtitle_cue_id,
               SUM(shadowing_cue_progress.practice_count) AS total_count,
               MAX(shadowing_cue_progress.last_practiced_at) AS most_recent_at
        FROM shadowing_cue_progress
        JOIN practice_session ON practice_session.id = shadowing_cue_progress.practice_session_id
        WHERE practice_session.material_id = ? AND shadowing_cue_progress.practice_count > 0
        GROUP BY shadowing_cue_progress.subtitle_cue_id
        """,
        (material_id,),
    ).fetchall()
    return {row["subtitle_cue_id"]: (row["total_count"], row["most_recent_at"]) for row in rows}


def list_quick_practice_shadowing_counts_by_cue(
    conn: sqlite3.Connection, material_id: int
) -> dict[int, tuple[int, str | None]]:
    """Per cue: (count of completed Quick Practice items with explicit
    shadowing, most recent `shadowed_at`) — the one piece of Quick
    Practice's own history "Recommended Practice" is allowed to read (see
    module docstring): an explicit `shadowed_at` is real shadowing
    evidence, on the same footing as Intensive Practice's. Quick Practice
    recall outcomes are still never read here. Source replay or recording
    alone is never counted — only the explicit "Mark Shadowed" action."""
    rows = conn.execute(
        """
        SELECT quick_practice_item.subtitle_cue_id AS subtitle_cue_id,
               COUNT(*) AS total_count,
               MAX(quick_practice_item.shadowed_at) AS most_recent_at
        FROM quick_practice_item
        JOIN quick_practice_session ON quick_practice_session.id = quick_practice_item.quick_practice_session_id
        WHERE quick_practice_session.material_id = ?
          AND quick_practice_item.completed_at IS NOT NULL
          AND quick_practice_item.shadowed_at IS NOT NULL
        GROUP BY quick_practice_item.subtitle_cue_id
        """,
        (material_id,),
    ).fetchall()
    return {row["subtitle_cue_id"]: (row["total_count"], row["most_recent_at"]) for row in rows}

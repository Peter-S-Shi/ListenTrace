from __future__ import annotations

import sqlite3

"""Cross-material, bounded read queries for Milestone 8 (Learning History and
Analytics). Every function here is read-only and returns raw `sqlite3.Row`
results (or scalars) rather than converted domain models — these are
aggregate/report shapes, not entities, so `application/services/
learning_history_service.py` is responsible for turning them into the
public DTOs in `application/dto/learning_history.py`.

Two evidence sources must never be blurred together (see `ARCHITECTURE.md` /
`DATA_MODEL.md`): `session_diagnosis_evidence` is session-scoped *history*
(one immutable snapshot per session/cue/label/range, from Milestone 5);
`annotation` is the *current*, editable, material-level diagnosis state (from
Milestone 4). Functions here are named to keep that distinction obvious —
`list_session_diagnosis_evidence` for the former, `list_current_annotation_
label_counts` for the latter.

All date-range filtering takes an already-resolved `[start_utc, end_utc)`
half-open window (see `domain/services/date_range.py`) — this module never
converts timezones or reads the system clock itself.
"""


def _append_range(conditions: list[str], params: list, column: str, start_utc: str | None, end_utc: str | None) -> None:
    if start_utc is not None:
        conditions.append(f"{column} >= ?")
        params.append(start_utc)
    if end_utc is not None:
        conditions.append(f"{column} < ?")
        params.append(end_utc)


# ---- materials ----


def list_all_materials(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every material (active and archived), for filter dropdowns and title
    lookups — ordered by title for a stable, readable list."""
    return conn.execute(
        "SELECT id, title, status FROM material ORDER BY title COLLATE NOCASE"
    ).fetchall()


def count_materials_with_any_activity(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
) -> int:
    """"Materials practiced": distinct materials with at least one intensive
    practice session, quiz attempt, or ready recording whose own anchor
    timestamp (`started_at`/`started_at`/`created_at` respectively) falls in
    [start_utc, end_utc). Passing `material_id` narrows this to a 0/1 check
    for that one material (used by the drilldown view for consistency)."""
    conditions: list[str] = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "ts", start_utc, end_utc)
    sql = f"""
        SELECT COUNT(DISTINCT material_id) AS n FROM (
            SELECT material_id, started_at AS ts FROM practice_session
            UNION ALL
            SELECT material_id, started_at AS ts FROM quiz_attempt
            UNION ALL
            SELECT material_id, created_at AS ts FROM recording WHERE status = 'ready'
        )
        WHERE {" AND ".join(conditions)}
    """
    row = conn.execute(sql, params).fetchone()
    return int(row["n"])


# ---- sessions ----


def list_sessions(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
    statuses: list[str] | None = None,
) -> list[sqlite3.Row]:
    """Every practice_session, newest-started first, joined with its
    material's title. Date filtering is anchored on the same "most recent
    meaningful state change" used by the combined Activity feed: `completed_at`
    if completed, else `abandoned_at` if abandoned, else `last_resumed_at`."""
    conditions: list[str] = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(
        conditions,
        params,
        "COALESCE(practice_session.completed_at, practice_session.abandoned_at, practice_session.last_resumed_at)",
        start_utc,
        end_utc,
    )
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        conditions.append(f"practice_session.status IN ({placeholders})")
        params.extend(statuses)
    sql = f"""
        SELECT practice_session.*, material.title AS material_title
        FROM practice_session
        JOIN material ON material.id = practice_session.material_id
        WHERE {" AND ".join(conditions)}
        ORDER BY practice_session.started_at DESC, practice_session.id DESC
    """
    return conn.execute(sql, params).fetchall()


def list_stage_progress_for_sessions(
    conn: sqlite3.Connection, session_ids: list[int]
) -> dict[int, list[sqlite3.Row]]:
    """Stage-progress rows for a batch of sessions in one bounded query
    (never one query per session)."""
    if not session_ids:
        return {}
    placeholders = ", ".join("?" for _ in session_ids)
    rows = conn.execute(
        f"SELECT * FROM session_stage_progress WHERE practice_session_id IN ({placeholders})",
        session_ids,
    ).fetchall()
    result: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        result.setdefault(row["practice_session_id"], []).append(row)
    return result


# ---- quizzes ----


def list_quiz_attempts(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
    statuses: list[str] | None = None,
) -> list[sqlite3.Row]:
    """Every quiz_attempt, newest-started first, joined with its material's
    title. Date filtering uses the same "most recent meaningful state change"
    anchor as the combined Activity feed: `completed_at` if completed, else
    `abandoned_at` if abandoned, else `last_resumed_at`."""
    conditions: list[str] = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("quiz_attempt.material_id = ?")
        params.append(material_id)
    _append_range(
        conditions,
        params,
        "COALESCE(quiz_attempt.completed_at, quiz_attempt.abandoned_at, quiz_attempt.last_resumed_at)",
        start_utc,
        end_utc,
    )
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        conditions.append(f"quiz_attempt.status IN ({placeholders})")
        params.extend(statuses)
    sql = f"""
        SELECT quiz_attempt.*, material.title AS material_title
        FROM quiz_attempt
        JOIN material ON material.id = quiz_attempt.material_id
        WHERE {" AND ".join(conditions)}
        ORDER BY quiz_attempt.started_at DESC, quiz_attempt.id DESC
    """
    return conn.execute(sql, params).fetchall()


def list_question_type_breakdown_for_attempts(
    conn: sqlite3.Connection, attempt_ids: list[int]
) -> dict[int, list[sqlite3.Row]]:
    """Per attempt, per question_type: question count and correct count, in
    one bounded batch query."""
    if not attempt_ids:
        return {}
    placeholders = ", ".join("?" for _ in attempt_ids)
    rows = conn.execute(
        f"""
        SELECT quiz_question.quiz_attempt_id AS attempt_id,
               quiz_question.question_type AS question_type,
               COUNT(*) AS question_count,
               SUM(CASE WHEN quiz_answer.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM quiz_question
        JOIN quiz_answer ON quiz_answer.quiz_question_id = quiz_question.id
        WHERE quiz_question.quiz_attempt_id IN ({placeholders})
        GROUP BY quiz_question.quiz_attempt_id, quiz_question.question_type
        ORDER BY quiz_question.quiz_attempt_id, quiz_question.question_type
        """,
        attempt_ids,
    ).fetchall()
    result: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        result.setdefault(row["attempt_id"], []).append(row)
    return result


def average_completed_quiz_accuracy(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> float | None:
    """Macro-average accuracy across completed attempts in scope: the mean of
    each attempt's own `correct_count / actual_count`, each attempt weighted
    equally regardless of its question count. Returns `None` (never `0.0`)
    when there are zero completed attempts in scope, so "no data" can never
    be displayed as "0% accuracy"."""
    conditions = ["status = 'completed'", "actual_count > 0"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "completed_at", start_utc, end_utc)
    sql = f"SELECT correct_count, actual_count FROM quiz_attempt WHERE {' AND '.join(conditions)}"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return None
    return sum(row["correct_count"] / row["actual_count"] for row in rows) / len(rows)


# ---- diagnosis: session-scoped history vs. current annotation state ----


def list_session_diagnosis_evidence(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> list[sqlite3.Row]:
    """Session-scoped historical diagnosis evidence (Milestone 5), never the
    current editable `annotation` table. Date filtering is anchored on
    `session_diagnosis_evidence.created_at`."""
    conditions = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "session_diagnosis_evidence.created_at", start_utc, end_utc)
    sql = f"""
        SELECT session_diagnosis_evidence.*,
               practice_session.material_id AS material_id,
               material.title AS material_title,
               subtitle_cue.text AS cue_text
        FROM session_diagnosis_evidence
        JOIN practice_session ON practice_session.id = session_diagnosis_evidence.practice_session_id
        JOIN material ON material.id = practice_session.material_id
        JOIN subtitle_cue ON subtitle_cue.id = session_diagnosis_evidence.subtitle_cue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY session_diagnosis_evidence.created_at DESC, session_diagnosis_evidence.id DESC
    """
    return conn.execute(sql, params).fetchall()


def diagnosis_label_frequency(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> list[sqlite3.Row]:
    """label_key -> occurrence count, sessions-containing count, materials-
    containing count, and most recent occurrence — from session-scoped
    evidence only."""
    conditions = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "session_diagnosis_evidence.created_at", start_utc, end_utc)
    sql = f"""
        SELECT session_diagnosis_evidence.label_key AS label_key,
               COUNT(*) AS occurrence_count,
               COUNT(DISTINCT session_diagnosis_evidence.practice_session_id) AS session_count,
               COUNT(DISTINCT practice_session.material_id) AS material_count,
               MAX(session_diagnosis_evidence.created_at) AS most_recent_at
        FROM session_diagnosis_evidence
        JOIN practice_session ON practice_session.id = session_diagnosis_evidence.practice_session_id
        WHERE {" AND ".join(conditions)}
        GROUP BY session_diagnosis_evidence.label_key
        ORDER BY occurrence_count DESC, label_key
    """
    return conn.execute(sql, params).fetchall()


def list_current_annotation_label_counts(
    conn: sqlite3.Connection, material_id: int | None = None
) -> list[sqlite3.Row]:
    """Current, editable `annotation` counts by label — present material
    state (Milestone 4), never date-filtered and never combined with
    session_diagnosis_evidence history counts."""
    conditions = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("subtitle_track.material_id = ?")
        params.append(material_id)
    sql = f"""
        SELECT annotation.label_key AS label_key, COUNT(*) AS n
        FROM annotation
        JOIN subtitle_cue ON subtitle_cue.id = annotation.subtitle_cue_id
        JOIN subtitle_track ON subtitle_track.id = subtitle_cue.subtitle_track_id
        WHERE {" AND ".join(conditions)}
        GROUP BY annotation.label_key
        ORDER BY annotation.label_key
    """
    return conn.execute(sql, params).fetchall()


# ---- shadowing ----


def list_shadowing_evidence(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> list[sqlite3.Row]:
    """Every shadowing_cue_progress row with at least one explicit practice
    action (`practice_count > 0`), joined with material/cue text. Date
    filtering is anchored on `last_practiced_at` — NOTE: `practice_count` is a
    lifetime cumulative counter per session/cue row, not a per-day event log,
    so a date-filtered result reports the *full* cumulative count of any row
    last practiced in range, not the number of practice actions that
    specifically happened inside it (see `ARCHITECTURE.md`)."""
    conditions = ["shadowing_cue_progress.practice_count > 0"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "shadowing_cue_progress.last_practiced_at", start_utc, end_utc)
    sql = f"""
        SELECT shadowing_cue_progress.*,
               practice_session.material_id AS material_id,
               material.title AS material_title,
               subtitle_cue.text AS cue_text
        FROM shadowing_cue_progress
        JOIN practice_session ON practice_session.id = shadowing_cue_progress.practice_session_id
        JOIN material ON material.id = practice_session.material_id
        JOIN subtitle_cue ON subtitle_cue.id = shadowing_cue_progress.subtitle_cue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY shadowing_cue_progress.practice_count DESC, shadowing_cue_progress.last_practiced_at DESC
    """
    return conn.execute(sql, params).fetchall()


def sum_shadowing_practice_count(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> int:
    conditions = ["shadowing_cue_progress.practice_count > 0"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "shadowing_cue_progress.last_practiced_at", start_utc, end_utc)
    sql = f"""
        SELECT COALESCE(SUM(shadowing_cue_progress.practice_count), 0) AS n
        FROM shadowing_cue_progress
        JOIN practice_session ON practice_session.id = shadowing_cue_progress.practice_session_id
        WHERE {" AND ".join(conditions)}
    """
    return int(conn.execute(sql, params).fetchone()["n"])


# ---- recordings ----


def list_ready_recordings(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> list[sqlite3.Row]:
    """Retained (`status = 'ready'`) recordings only — a deleted take no
    longer has a row at all, so "retained" is simply every row presently
    stored with this status. Date filtering is anchored on `created_at`."""
    conditions = ["recording.status = 'ready'"]
    params: list = []
    if material_id is not None:
        conditions.append("recording.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "recording.created_at", start_utc, end_utc)
    sql = f"""
        SELECT recording.*, material.title AS material_title, subtitle_cue.text AS cue_text
        FROM recording
        JOIN material ON material.id = recording.material_id
        JOIN subtitle_cue ON subtitle_cue.id = recording.subtitle_cue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY recording.created_at DESC, recording.id DESC
    """
    return conn.execute(sql, params).fetchall()


def count_ready_recordings(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> int:
    conditions = ["status = 'ready'"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "created_at", start_utc, end_utc)
    sql = f"SELECT COUNT(*) AS n FROM recording WHERE {' AND '.join(conditions)}"
    return int(conn.execute(sql, params).fetchone()["n"])


def sum_ready_recording_duration_ms(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> int:
    conditions = ["status = 'ready'"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "created_at", start_utc, end_utc)
    sql = f"SELECT COALESCE(SUM(duration_ms), 0) AS n FROM recording WHERE {' AND '.join(conditions)}"
    return int(conn.execute(sql, params).fetchone()["n"])


# ---- session status counts (overview + needs-attention) ----


def count_practice_sessions(
    conn: sqlite3.Connection,
    status: str,
    anchor_column: str,
    material_id: int | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
) -> int:
    """`anchor_column` must be one of `started_at`/`completed_at`/
    `abandoned_at` — always a fixed literal supplied by our own calling code,
    never external input."""
    if anchor_column not in {"started_at", "completed_at", "abandoned_at", "last_resumed_at"}:
        raise ValueError(f"Unsupported anchor column: {anchor_column!r}")
    conditions = ["status = ?"]
    params: list = [status]
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, anchor_column, start_utc, end_utc)
    sql = f"SELECT COUNT(*) AS n FROM practice_session WHERE {' AND '.join(conditions)}"
    return int(conn.execute(sql, params).fetchone()["n"])


def count_active_sessions(conn: sqlite3.Connection, material_id: int | None = None) -> int:
    """Unfiltered by date on purpose: an active session is current state
    (used by Continue Learning), not a historical event to bucket by range."""
    conditions = ["status = 'active'"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    sql = f"SELECT COUNT(*) AS n FROM practice_session WHERE {' AND '.join(conditions)}"
    return int(conn.execute(sql, params).fetchone()["n"])


def list_active_sessions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every active session, across every material — the "Continue Learning"
    surface, always unfiltered by date range (see `count_active_sessions`)."""
    return conn.execute(
        """
        SELECT practice_session.*, material.title AS material_title
        FROM practice_session
        JOIN material ON material.id = practice_session.material_id
        WHERE practice_session.status = 'active'
        ORDER BY practice_session.last_resumed_at DESC, practice_session.id DESC
        """
    ).fetchall()


def count_completed_quiz_attempts(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> int:
    conditions = ["status = 'completed'"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "completed_at", start_utc, end_utc)
    sql = f"SELECT COUNT(*) AS n FROM quiz_attempt WHERE {' AND '.join(conditions)}"
    return int(conn.execute(sql, params).fetchone()["n"])


def count_session_diagnosis_evidence(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> int:
    conditions = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("practice_session.material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "session_diagnosis_evidence.created_at", start_utc, end_utc)
    sql = f"""
        SELECT COUNT(*) AS n FROM session_diagnosis_evidence
        JOIN practice_session ON practice_session.id = session_diagnosis_evidence.practice_session_id
        WHERE {" AND ".join(conditions)}
    """
    return int(conn.execute(sql, params).fetchone()["n"])


# ---- combined activity feed ----

_ACTIVITY_UNION_SQL = """
    SELECT 'session' AS activity_type,
           COALESCE(ps.completed_at, ps.abandoned_at, ps.last_resumed_at) AS occurred_at,
           ps.material_id AS material_id, m.title AS material_title,
           ps.id AS ref_id, NULL AS subtitle_cue_id, NULL AS label_key,
           ps.status AS status, NULL AS quiz_mode, NULL AS session_id
    FROM practice_session ps JOIN material m ON m.id = ps.material_id

    UNION ALL

    SELECT 'quiz', COALESCE(qa.completed_at, qa.abandoned_at, qa.last_resumed_at),
           qa.material_id, m.title, qa.id, NULL, NULL, qa.status, qa.quiz_mode, NULL
    FROM quiz_attempt qa JOIN material m ON m.id = qa.material_id

    UNION ALL

    SELECT 'diagnosis', sde.created_at, ps.material_id, m.title,
           sde.id, sde.subtitle_cue_id, sde.label_key, NULL, NULL, ps.id
    FROM session_diagnosis_evidence sde
    JOIN practice_session ps ON ps.id = sde.practice_session_id
    JOIN material m ON m.id = ps.material_id

    UNION ALL

    SELECT 'shadowing', scp.last_practiced_at, ps.material_id, m.title,
           ps.id, scp.subtitle_cue_id, NULL, scp.status, NULL, ps.id
    FROM shadowing_cue_progress scp
    JOIN practice_session ps ON ps.id = scp.practice_session_id
    JOIN material m ON m.id = ps.material_id
    WHERE scp.practice_count > 0

    UNION ALL

    SELECT 'recording', r.created_at, r.material_id, m.title,
           r.id, r.subtitle_cue_id, NULL, r.status, NULL, r.practice_session_id
    FROM recording r JOIN material m ON m.id = r.material_id
    WHERE r.status = 'ready'
"""


def list_activity(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
    activity_types: list[str] | None = None,
) -> list[sqlite3.Row]:
    """Combined chronological activity across Session/Quiz/Diagnosis/
    Shadowing/Recording — every row keeps its own `activity_type`, never
    merged into one ambiguous kind. `occurred_at` is a single clear per-type
    anchor: Session/Quiz -> completed_at, else abandoned_at, else
    last_resumed_at (its most recent meaningful state change); Diagnosis ->
    created_at; Shadowing -> last_practiced_at (practiced rows only);
    Recording -> created_at (retained/`ready` rows only, matching Recording
    Evidence's own scope)."""
    conditions = ["1 = 1"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "occurred_at", start_utc, end_utc)
    if activity_types:
        placeholders = ", ".join("?" for _ in activity_types)
        conditions.append(f"activity_type IN ({placeholders})")
        params.extend(activity_types)
    sql = f"""
        SELECT * FROM ({_ACTIVITY_UNION_SQL}) AS activity
        WHERE {" AND ".join(conditions)}
        ORDER BY occurred_at DESC, activity_type, ref_id DESC
    """
    return conn.execute(sql, params).fetchall()


# ---- needs-attention source data (unfiltered by date: a current snapshot) ----


def list_recent_completed_quiz_accuracies_by_material(conn: sqlite3.Connection) -> dict[int, list[float]]:
    """Per material: completed-quiz accuracies, newest-completed-attempt
    first. `needs_attention_rules` decides how many of these count as
    "recent"."""
    rows = conn.execute(
        """
        SELECT material_id, correct_count, actual_count
        FROM quiz_attempt
        WHERE status = 'completed' AND actual_count > 0
        ORDER BY material_id, completed_at DESC, id DESC
        """
    ).fetchall()
    result: dict[int, list[float]] = {}
    for row in rows:
        result.setdefault(row["material_id"], []).append(row["correct_count"] / row["actual_count"])
    return result


def list_diagnosis_label_counts_by_material(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    rows = conn.execute(
        """
        SELECT ps.material_id AS material_id, sde.label_key AS label_key, COUNT(*) AS n
        FROM session_diagnosis_evidence sde
        JOIN practice_session ps ON ps.id = sde.practice_session_id
        GROUP BY ps.material_id, sde.label_key
        """
    ).fetchall()
    result: dict[int, dict[str, int]] = {}
    for row in rows:
        result.setdefault(row["material_id"], {})[row["label_key"]] = row["n"]
    return result


def list_session_status_counts_by_material(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    rows = conn.execute(
        "SELECT material_id, status, COUNT(*) AS n FROM practice_session GROUP BY material_id, status"
    ).fetchall()
    result: dict[int, dict[str, int]] = {}
    for row in rows:
        result.setdefault(row["material_id"], {})[row["status"]] = row["n"]
    return result


def list_skipped_stage_counts_by_material(conn: sqlite3.Connection) -> dict[int, list[int]]:
    """Per material: one entry per completed/abandoned session, counting how
    many of its 5 stages ended up `skipped`. Active sessions are excluded —
    this is a completed-story metric, not a mid-session state."""
    rows = conn.execute(
        """
        SELECT ps.material_id AS material_id, ps.id AS session_id,
               SUM(CASE WHEN ssp.status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
        FROM practice_session ps
        JOIN session_stage_progress ssp ON ssp.practice_session_id = ps.id
        WHERE ps.status IN ('completed', 'abandoned')
        GROUP BY ps.id
        """
    ).fetchall()
    result: dict[int, list[int]] = {}
    for row in rows:
        result.setdefault(row["material_id"], []).append(row["skipped_count"])
    return result


# ---- charts ----


def list_completed_sessions_for_chart(
    conn: sqlite3.Connection, material_id: int | None = None, start_utc: str | None = None, end_utc: str | None = None
) -> list[sqlite3.Row]:
    """Raw `completed_at` values for completed sessions in scope — the
    service buckets these by local calendar day (a UTC-string GROUP BY would
    bucket by the wrong day near local midnight)."""
    conditions = ["status = 'completed'"]
    params: list = []
    if material_id is not None:
        conditions.append("material_id = ?")
        params.append(material_id)
    _append_range(conditions, params, "completed_at", start_utc, end_utc)
    sql = f"SELECT completed_at FROM practice_session WHERE {' AND '.join(conditions)} ORDER BY completed_at"
    return conn.execute(sql, params).fetchall()

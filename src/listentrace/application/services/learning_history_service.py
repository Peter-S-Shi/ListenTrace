from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from listentrace.application.dto.learning_history import (
    ActivityItem,
    ChartData,
    ChartPoint,
    DiagnosisCategorySummary,
    NeedsAttentionEntry,
    OverviewMetrics,
    QuestionTypeBreakdown,
    QuizComparisonGroup,
    QuizHistoryEntry,
    RecordingEvidenceEntry,
    RecordingEvidenceSummary,
    SessionHistoryEntry,
    ShadowingEvidenceEntry,
    StageOutcomeSummary,
)
from listentrace.domain.enums.stage_key import STAGE_ORDER
from listentrace.domain.services import date_range as date_range_rules
from listentrace.domain.services import needs_attention_rules
from listentrace.infrastructure.db import history_repository as repo

"""Application service for Milestone 8 (Learning History and Analytics).

This module is the single place that turns `history_repository`'s raw,
bounded SQL results into the public read-model DTOs
(`application/dto/learning_history.py`), and the single place that applies
this milestone's business rules: which sessions/quizzes count as
"completed" for aggregate purposes, how the Diagnosis history/current-state
distinction is kept visibly separate, how "Needs Attention" reasons are
assembled from raw per-material evidence, and how chart data is bucketed by
*local* calendar day. It never touches Qt and never writes SQL directly —
all queries live in `history_repository.py`.
"""

_HIGH_FREQUENCY_SHADOWING_TOP_N = 10


def resolve_date_range(
    preset: str,
    today_local: date,
    *,
    custom_start_date: date | None = None,
    custom_end_date: date | None = None,
) -> date_range_rules.ResolvedDateRange:
    return date_range_rules.resolve_date_range(
        preset, today_local, custom_start_date=custom_start_date, custom_end_date=custom_end_date
    )


def _utc_str_to_local_date(utc_str: str) -> date:
    dt_utc = datetime.strptime(utc_str, date_range_rules.SQLITE_UTC_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone().date()


def list_all_materials(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return repo.list_all_materials(conn)


# ---- overview ----


def get_overview(
    conn: sqlite3.Connection,
    material_id: int | None,
    resolved_range: date_range_rules.ResolvedDateRange,
) -> OverviewMetrics:
    start_utc, end_utc = resolved_range.start_utc, resolved_range.end_utc
    return OverviewMetrics(
        materials_practiced=repo.count_materials_with_any_activity(conn, material_id, start_utc, end_utc),
        completed_sessions=repo.count_practice_sessions(
            conn, "completed", "completed_at", material_id, start_utc, end_utc
        ),
        active_sessions=repo.count_practice_sessions(
            conn, "active", "last_resumed_at", material_id, start_utc, end_utc
        ),
        abandoned_sessions=repo.count_practice_sessions(
            conn, "abandoned", "abandoned_at", material_id, start_utc, end_utc
        ),
        completed_quizzes=repo.count_completed_quiz_attempts(conn, material_id, start_utc, end_utc),
        average_quiz_accuracy=repo.average_completed_quiz_accuracy(conn, material_id, start_utc, end_utc),
        session_diagnosis_evidence_count=repo.count_session_diagnosis_evidence(
            conn, material_id, start_utc, end_utc
        ),
        shadowing_practice_count=repo.sum_shadowing_practice_count(conn, material_id, start_utc, end_utc),
        retained_recording_count=repo.count_ready_recordings(conn, material_id, start_utc, end_utc),
        retained_recording_total_duration_ms=repo.sum_ready_recording_duration_ms(
            conn, material_id, start_utc, end_utc
        ),
    )


# ---- activity ----


def _activity_summary(row: sqlite3.Row) -> str:
    activity_type = row["activity_type"]
    if activity_type == "session":
        return f"Intensive practice session — {row['status']}"
    if activity_type == "quiz":
        return f"{row['quiz_mode']} quiz — {row['status']}"
    if activity_type == "diagnosis":
        return f"Diagnosis recorded — {row['label_key']}"
    if activity_type == "shadowing":
        return f"Shadowing practiced — {row['status']}"
    if activity_type == "recording":
        return "Recording retained"
    return activity_type


def list_activity(
    conn: sqlite3.Connection,
    material_id: int | None,
    resolved_range: date_range_rules.ResolvedDateRange,
    activity_types: list[str] | None = None,
) -> list[ActivityItem]:
    rows = repo.list_activity(
        conn, material_id, resolved_range.start_utc, resolved_range.end_utc, activity_types
    )
    return [
        ActivityItem(
            activity_type=row["activity_type"],
            occurred_at=row["occurred_at"],
            material_id=row["material_id"],
            material_title=row["material_title"],
            ref_id=row["ref_id"],
            subtitle_cue_id=row["subtitle_cue_id"],
            label_key=row["label_key"],
            status=row["status"],
            quiz_mode=row["quiz_mode"],
            session_id=row["session_id"],
            summary=_activity_summary(row),
        )
        for row in rows
    ]


# ---- sessions ----


def _stage_summaries(stage_rows: list[sqlite3.Row]) -> list[StageOutcomeSummary]:
    by_key = {row["stage_key"]: row for row in stage_rows}
    return [
        StageOutcomeSummary(stage_key=key, status=by_key[key]["status"], skip_note=by_key[key]["skip_note"])
        for key in STAGE_ORDER
        if key in by_key
    ]


def list_sessions(
    conn: sqlite3.Connection,
    material_id: int | None,
    resolved_range: date_range_rules.ResolvedDateRange,
    statuses: list[str] | None = None,
) -> list[SessionHistoryEntry]:
    rows = repo.list_sessions(conn, material_id, resolved_range.start_utc, resolved_range.end_utc, statuses)
    stage_rows_by_session = repo.list_stage_progress_for_sessions(conn, [row["id"] for row in rows])
    return [
        SessionHistoryEntry(
            session_id=row["id"],
            material_id=row["material_id"],
            material_title=row["material_title"],
            status=row["status"],
            current_stage=row["current_stage"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            abandoned_at=row["abandoned_at"],
            last_resumed_at=row["last_resumed_at"],
            stages=_stage_summaries(stage_rows_by_session.get(row["id"], [])),
        )
        for row in rows
    ]


def list_continue_learning_sessions(conn: sqlite3.Connection) -> list[SessionHistoryEntry]:
    """Every active session, across every material, always unfiltered by
    date range — "Continue Learning" is current actionable state, not a
    historical report (see ARCHITECTURE.md)."""
    rows = repo.list_active_sessions(conn)
    stage_rows_by_session = repo.list_stage_progress_for_sessions(conn, [row["id"] for row in rows])
    return [
        SessionHistoryEntry(
            session_id=row["id"],
            material_id=row["material_id"],
            material_title=row["material_title"],
            status=row["status"],
            current_stage=row["current_stage"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            abandoned_at=row["abandoned_at"],
            last_resumed_at=row["last_resumed_at"],
            stages=_stage_summaries(stage_rows_by_session.get(row["id"], [])),
        )
        for row in rows
    ]


# ---- diagnosis ----


def list_diagnosis_insights(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> list[DiagnosisCategorySummary]:
    """Session-scoped historical evidence only — see `list_current_annotation_
    label_counts` for the separately-presented current material state."""
    rows = repo.diagnosis_label_frequency(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    return [
        DiagnosisCategorySummary(
            label_key=row["label_key"],
            occurrence_count=row["occurrence_count"],
            session_count=row["session_count"],
            material_count=row["material_count"],
            most_recent_at=row["most_recent_at"],
        )
        for row in rows
    ]


def list_current_annotation_label_counts(conn: sqlite3.Connection, material_id: int | None) -> dict[str, int]:
    """Current, editable material-level diagnosis state (Milestone 4) — never
    date-filtered, and never combined with `list_diagnosis_insights`'
    session-history counts. Presented under its own label in the UI."""
    rows = repo.list_current_annotation_label_counts(conn, material_id)
    return {row["label_key"]: row["n"] for row in rows}


# ---- quizzes ----


def list_quiz_history(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> list[QuizHistoryEntry]:
    """Completed attempts only — an active or abandoned attempt never enters
    a completed-attempt average or history list (see `get_overview`)."""
    rows = repo.list_quiz_attempts(
        conn, material_id, resolved_range.start_utc, resolved_range.end_utc, statuses=["completed"]
    )
    breakdowns = repo.list_question_type_breakdown_for_attempts(conn, [row["id"] for row in rows])
    return [_to_quiz_history_entry(row, breakdowns.get(row["id"], [])) for row in rows]


def _to_quiz_history_entry(row: sqlite3.Row, breakdown_rows: list[sqlite3.Row]) -> QuizHistoryEntry:
    accuracy = row["correct_count"] / row["actual_count"] if row["actual_count"] else None
    return QuizHistoryEntry(
        attempt_id=row["id"],
        material_id=row["material_id"],
        material_title=row["material_title"],
        quiz_mode=row["quiz_mode"],
        status=row["status"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        correct_count=row["correct_count"],
        actual_count=row["actual_count"],
        accuracy=accuracy,
        breakdown=[
            QuestionTypeBreakdown(
                question_type=b["question_type"],
                question_count=b["question_count"],
                correct_count=b["correct_count"],
            )
            for b in breakdown_rows
        ],
    )


def list_quiz_comparisons(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> list[QuizComparisonGroup]:
    """Grouped by (material, quiz_mode); within a group, entries are ordered
    oldest-first (chronological trend), and different materials/modes are
    never combined into one series."""
    entries = list_quiz_history(conn, material_id, resolved_range)
    entries_oldest_first = list(reversed(entries))
    groups: dict[tuple[int, str], QuizComparisonGroup] = {}
    for entry in entries_oldest_first:
        key = (entry.material_id, entry.quiz_mode)
        group = groups.get(key)
        if group is None:
            group = QuizComparisonGroup(material_id=entry.material_id, material_title=entry.material_title, quiz_mode=entry.quiz_mode)
            groups[key] = group
        group.entries.append(entry)
    return list(groups.values())


# ---- needs attention ----


def list_needs_attention(conn: sqlite3.Connection) -> list[NeedsAttentionEntry]:
    """A current snapshot, unfiltered by date range — this is a call-to-action
    surface, not a historical report."""
    accuracies = repo.list_recent_completed_quiz_accuracies_by_material(conn)
    diagnosis_counts = repo.list_diagnosis_label_counts_by_material(conn)
    session_status_counts = repo.list_session_status_counts_by_material(conn)
    skipped_counts = repo.list_skipped_stage_counts_by_material(conn)

    material_ids = set(accuracies) | set(diagnosis_counts) | set(session_status_counts) | set(skipped_counts)
    if not material_ids:
        return []
    titles = {row["id"]: row["title"] for row in repo.list_all_materials(conn) if row["id"] in material_ids}

    entries: list[NeedsAttentionEntry] = []
    for material_id in sorted(material_ids):
        status_counts = session_status_counts.get(material_id, {})
        stats = needs_attention_rules.MaterialActivityStats(
            material_id=material_id,
            recent_quiz_accuracies=tuple(accuracies.get(material_id, [])),
            diagnosis_label_counts=diagnosis_counts.get(material_id, {}),
            abandoned_session_count=status_counts.get("abandoned", 0),
            total_session_count=sum(status_counts.values()),
            active_session_count=status_counts.get("active", 0),
            skipped_stage_counts_by_session=tuple(skipped_counts.get(material_id, [])),
        )
        reasons = needs_attention_rules.evaluate_material(stats)
        if reasons:
            entries.append(
                NeedsAttentionEntry(
                    material_id=material_id,
                    material_title=titles.get(material_id, f"Material {material_id}"),
                    reasons=reasons,
                )
            )
    return entries


# ---- shadowing ----


def list_shadowing_evidence(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> list[ShadowingEvidenceEntry]:
    rows = repo.list_shadowing_evidence(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    return [_to_shadowing_entry(row) for row in rows]


def _to_shadowing_entry(row: sqlite3.Row) -> ShadowingEvidenceEntry:
    return ShadowingEvidenceEntry(
        material_id=row["material_id"],
        material_title=row["material_title"],
        subtitle_cue_id=row["subtitle_cue_id"],
        cue_text=row["cue_text"],
        session_id=row["practice_session_id"],
        practice_count=row["practice_count"],
        last_practiced_at=row["last_practiced_at"],
        note=row["note"],
    )


def list_high_frequency_shadowing_cues(
    conn: sqlite3.Connection,
    material_id: int | None,
    resolved_range: date_range_rules.ResolvedDateRange,
    top_n: int = _HIGH_FREQUENCY_SHADOWING_TOP_N,
) -> list[ShadowingEvidenceEntry]:
    """`history_repository.list_shadowing_evidence` is already ordered by
    practice_count descending, so this is simply its first `top_n` rows —
    never a reconstructed daily/weekly count."""
    return list_shadowing_evidence(conn, material_id, resolved_range)[:top_n]


# ---- recordings ----


def list_recording_evidence(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> RecordingEvidenceSummary:
    rows = repo.list_ready_recordings(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    entries = [
        RecordingEvidenceEntry(
            recording_id=row["id"],
            material_id=row["material_id"],
            material_title=row["material_title"],
            subtitle_cue_id=row["subtitle_cue_id"],
            cue_text=row["cue_text"],
            practice_session_id=row["practice_session_id"],
            duration_ms=row["duration_ms"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    total_duration_ms = repo.sum_ready_recording_duration_ms(
        conn, material_id, resolved_range.start_utc, resolved_range.end_utc
    )
    return RecordingEvidenceSummary(entries=entries, total_duration_ms=total_duration_ms)


# ---- charts (each backed by the same data as its tabular equivalent) ----


def chart_quiz_accuracy_over_time(
    conn: sqlite3.Connection,
    material_id: int | None,
    resolved_range: date_range_rules.ResolvedDateRange,
    group_material_id: int | None = None,
    quiz_mode: str | None = None,
) -> ChartData:
    """One (material, quiz mode) trend at a time — attempts from different
    materials or different quiz modes are never combined into a single
    series (mirroring `list_quiz_comparisons`'s own grouping, which is the
    exact data this reads: no separate query, so the chart and the Quiz
    Comparison tree can never show different groupings of the same data).

    `group_material_id`/`quiz_mode` select which group to chart; if neither
    is given (or the requested group doesn't exist in scope), this falls
    back to the first available group deterministically rather than ever
    mixing groups together. Each point's label includes the attempt's
    question count (`actual_count`) alongside its date, since different
    attempts may have different sizes."""
    groups = list_quiz_comparisons(conn, material_id, resolved_range)
    if not groups:
        return ChartData(title="Quiz attempt accuracy over time (%)", points=[])

    selected_group = None
    if group_material_id is not None or quiz_mode is not None:
        selected_group = next(
            (
                g
                for g in groups
                if (group_material_id is None or g.material_id == group_material_id)
                and (quiz_mode is None or g.quiz_mode == quiz_mode)
            ),
            None,
        )
    group = selected_group or groups[0]

    points = [
        ChartPoint(
            label=f"{e.completed_at or e.started_at} (n={e.actual_count})",
            value=round((e.accuracy or 0.0) * 100, 1),
        )
        for e in group.entries
    ]
    title = f"Quiz attempt accuracy over time (%) — {group.material_title} / {group.quiz_mode}"
    return ChartData(title=title, points=points)


def chart_diagnosis_category_frequency(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> ChartData:
    summaries = list_diagnosis_insights(conn, material_id, resolved_range)
    points = [ChartPoint(label=s.label_key, value=float(s.occurrence_count)) for s in summaries]
    return ChartData(title="Diagnosis category frequency", points=points)


def chart_completed_sessions_by_period(
    conn: sqlite3.Connection, material_id: int | None, resolved_range: date_range_rules.ResolvedDateRange
) -> ChartData:
    """Buckets completed sessions by *local* calendar day (converted per-row
    from the stored UTC `completed_at`), not by a UTC-string truncation —
    otherwise a session completed shortly after local midnight could be
    bucketed into the wrong day near a timezone boundary."""
    rows = repo.list_completed_sessions_for_chart(
        conn, material_id, resolved_range.start_utc, resolved_range.end_utc
    )
    counts: dict[date, int] = {}
    for row in rows:
        local_day = _utc_str_to_local_date(row["completed_at"])
        counts[local_day] = counts.get(local_day, 0) + 1
    points = [ChartPoint(label=day.isoformat(), value=float(count)) for day, count in sorted(counts.items())]
    return ChartData(title="Completed sessions by day", points=points)

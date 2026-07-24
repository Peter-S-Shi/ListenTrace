from __future__ import annotations

import uuid
from datetime import date

import pytest

from listentrace.application.services import learning_history_service as svc
from listentrace.domain.models.material import Material
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion
from listentrace.domain.models.recording import Recording
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.domain.services.date_range import PRESET_ALL_TIME, PRESET_LAST_7_DAYS, resolve_date_range
from listentrace.infrastructure.db import quiz_repository, recording_repository, session_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import insert_material, insert_subtitle_track, get_subtitle_track_for_material, get_cues_for_track

_OLD_TIMESTAMP = "2000-01-01 00:00:00"
_TODAY_LOCAL = date(2026, 7, 24)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def recent_range(conn):
    return resolve_date_range(PRESET_LAST_7_DAYS, _TODAY_LOCAL)


@pytest.fixture()
def all_time_range():
    return resolve_date_range(PRESET_ALL_TIME, _TODAY_LOCAL)


def _make_material_with_cues(conn, title="Lesson", cue_texts=("Bonjour", "Comment ca va")):
    material_id = insert_material(conn, Material(title=title, media_path=f"C:/media/{title}.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path=f"C:/media/{title}.srt",
        cues=[
            SubtitleCue(cue_index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=text)
            for i, text in enumerate(cue_texts)
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def _make_session(conn, material_id, status="active", started_at=None):
    session_id = session_repository.create_practice_session(conn, material_id)
    if status != "active":
        session_repository.set_session_status(conn, session_id, status)
    if started_at is not None:
        conn.execute("UPDATE practice_session SET started_at = ? WHERE id = ?", (started_at, session_id))
        conn.commit()
    return session_id


def _touch_session_timestamp(conn, session_id, column, value):
    conn.execute(f"UPDATE practice_session SET {column} = ? WHERE id = ?", (value, session_id))
    conn.commit()


def _make_quiz_attempt(
    conn, material_id, status="completed", correct=3, actual=4, started_at=None, completed_at=None, quiz_mode="material"
):
    attempt = QuizAttempt(material_id=material_id, quiz_mode=quiz_mode, requested_count=actual)
    question = QuizQuestion(
        question_type="dictation",
        subtitle_cue_id=1,
        source_cue_text="text",
        prompt_payload="{}",
        correct_answer_payload="{}",
        scoring_config='{"rule": "normalized_text_exact", "version": 1}',
    )
    attempt_id, _ = quiz_repository.create_quiz_attempt_with_questions(conn, attempt, [question] * actual)
    if status == "completed":
        quiz_repository.finalize_quiz_score(conn, attempt_id, correct)
        conn.commit()
    elif status == "abandoned":
        quiz_repository.set_quiz_status(conn, attempt_id, "abandoned")
    if started_at is not None:
        conn.execute("UPDATE quiz_attempt SET started_at = ? WHERE id = ?", (started_at, attempt_id))
    if completed_at is not None:
        conn.execute("UPDATE quiz_attempt SET completed_at = ? WHERE id = ?", (completed_at, attempt_id))
    conn.commit()
    return attempt_id


def _make_diagnosis(conn, session_id, cue_id, label_key="misheard", created_at=None):
    evidence = SessionDiagnosisEvidence(
        practice_session_id=session_id,
        subtitle_cue_id=cue_id,
        label_key=label_key,
        selected_text="text",
        selection_start=0,
        selection_end=4,
        heard_as="x" if label_key == "misheard" else None,
    )
    evidence_id = session_repository.insert_session_diagnosis(conn, evidence)
    if created_at is not None:
        conn.execute("UPDATE session_diagnosis_evidence SET created_at = ? WHERE id = ?", (created_at, evidence_id))
        conn.commit()
    return evidence_id


def _make_recording(conn, material_id, cue_id, status="ready", duration_ms=1000, created_at=None, practice_session_id=None):
    recording = Recording(
        material_id=material_id,
        subtitle_cue_id=cue_id,
        practice_session_id=practice_session_id,
        relative_file_path=f"{material_id}/{cue_id}-{uuid.uuid4().hex}.wav",
    )
    recording_id = recording_repository.insert_recording(conn, recording)
    if status == "ready":
        recording_repository.set_recording_ready(conn, recording_id, duration_ms)
    elif status == "failed":
        recording_repository.set_recording_failed(conn, recording_id, "bad")
    if created_at is not None:
        conn.execute("UPDATE recording SET created_at = ? WHERE id = ?", (created_at, recording_id))
        conn.commit()
    return recording_id


# ---- overview ----


def test_overview_is_all_zero_when_nothing_exists(conn, all_time_range):
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.materials_practiced == 0
    assert overview.completed_sessions == 0
    assert overview.active_sessions == 0
    assert overview.abandoned_sessions == 0
    assert overview.completed_quizzes == 0
    assert overview.average_quiz_accuracy is None
    assert overview.session_diagnosis_evidence_count == 0
    assert overview.shadowing_practice_count == 0
    assert overview.retained_recording_count == 0
    assert overview.retained_recording_total_duration_ms == 0


def test_overview_counts_sessions_by_status_distinctly(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_session(conn, material_id, status="completed")
    _make_session(conn, material_id, status="abandoned")
    _make_session(conn, material_id, status="active")
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.completed_sessions == 1
    assert overview.abandoned_sessions == 1
    assert overview.active_sessions == 1


def test_active_and_abandoned_sessions_never_count_as_completed(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_session(conn, material_id, status="abandoned")
    _make_session(conn, material_id, status="active")
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.completed_sessions == 0


def test_average_quiz_accuracy_excludes_incomplete_attempts(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, status="completed", correct=2, actual=4)  # 50%
    _make_quiz_attempt(conn, material_id, status="completed", correct=4, actual=4)  # 100%
    _make_quiz_attempt(conn, material_id, status="active", correct=0, actual=4)
    _make_quiz_attempt(conn, material_id, status="abandoned", correct=0, actual=4)
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.completed_quizzes == 2
    assert overview.average_quiz_accuracy == pytest.approx(0.75)


def test_retained_recording_stats_exclude_failed_and_use_ready_only(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    _make_recording(conn, material_id, cues[0].id, status="ready", duration_ms=2000)
    _make_recording(conn, material_id, cues[0].id, status="ready", duration_ms=3000)
    _make_recording(conn, material_id, cues[0].id, status="failed")
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.retained_recording_count == 2
    assert overview.retained_recording_total_duration_ms == 5000


def test_deleted_recordings_are_not_retained_evidence(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    recording_id = _make_recording(conn, material_id, cues[0].id, status="ready", duration_ms=1000)
    recording_repository.delete_recording(conn, recording_id)
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.retained_recording_count == 0


# ---- date filtering ----


def test_date_range_excludes_sessions_outside_the_window(conn, recent_range):
    material_id, _ = _make_material_with_cues(conn)
    old_session = _make_session(conn, material_id, status="completed")
    _touch_session_timestamp(conn, old_session, "completed_at", _OLD_TIMESTAMP)
    recent_session = _make_session(conn, material_id, status="completed")
    _touch_session_timestamp(conn, recent_session, "completed_at", recent_range.start_utc)

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.completed_sessions == 1

    entries = svc.list_sessions(conn, None, recent_range)
    assert [e.session_id for e in entries] == [recent_session]


def test_all_time_includes_everything_regardless_of_timestamp(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    old_session = _make_session(conn, material_id, status="completed")
    _touch_session_timestamp(conn, old_session, "completed_at", _OLD_TIMESTAMP)
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.completed_sessions == 1


# ---- materials practiced: date-anchor consistency with Activity ----


def test_materials_practiced_counts_a_session_completed_inside_the_range_even_if_started_outside(
    conn, recent_range
):
    material_id, _ = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="completed", started_at=_OLD_TIMESTAMP)
    _touch_session_timestamp(conn, session_id, "completed_at", recent_range.start_utc)

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.materials_practiced == 1


def test_materials_practiced_counts_a_quiz_completed_inside_the_range_even_if_started_outside(conn, recent_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(
        conn,
        material_id,
        status="completed",
        correct=1,
        actual=4,
        started_at=_OLD_TIMESTAMP,
        completed_at=recent_range.start_utc,
    )

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.materials_practiced == 1


def test_materials_practiced_counts_diagnosis_only_qualifying_activity(conn, recent_range):
    material_id, cues = _make_material_with_cues(conn)
    # The owning session itself is old/unqualifying on its own — only the
    # diagnosis event's own created_at falls inside the range.
    session_id = _make_session(conn, material_id, status="active", started_at=_OLD_TIMESTAMP)
    _touch_session_timestamp(conn, session_id, "last_resumed_at", _OLD_TIMESTAMP)
    _make_diagnosis(conn, session_id, cues[0].id, created_at=recent_range.start_utc)

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.materials_practiced == 1


def test_materials_practiced_counts_shadowing_only_qualifying_activity(conn, recent_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="active", started_at=_OLD_TIMESTAMP)
    _touch_session_timestamp(conn, session_id, "last_resumed_at", _OLD_TIMESTAMP)
    session_repository.ensure_shadowing_rows(conn, session_id, [c.id for c in cues])
    session_repository.mark_shadowing_practiced(conn, session_id, cues[0].id)
    conn.execute(
        "UPDATE shadowing_cue_progress SET last_practiced_at = ? "
        "WHERE practice_session_id = ? AND subtitle_cue_id = ?",
        (recent_range.start_utc, session_id, cues[0].id),
    )
    conn.commit()

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.materials_practiced == 1


def test_materials_practiced_excludes_a_material_with_only_out_of_range_evidence(conn, recent_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="active", started_at=_OLD_TIMESTAMP)
    _touch_session_timestamp(conn, session_id, "last_resumed_at", _OLD_TIMESTAMP)
    _make_diagnosis(conn, session_id, cues[0].id, created_at=_OLD_TIMESTAMP)

    overview = svc.get_overview(conn, None, recent_range)
    assert overview.materials_practiced == 0


# ---- material filtering ----


def test_material_filter_scopes_every_metric_to_one_material(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_session(conn, material_a, status="completed")
    _make_session(conn, material_b, status="completed")
    _make_session(conn, material_b, status="completed")

    overview_a = svc.get_overview(conn, material_a, all_time_range)
    overview_b = svc.get_overview(conn, material_b, all_time_range)
    assert overview_a.completed_sessions == 1
    assert overview_b.completed_sessions == 2
    assert overview_a.materials_practiced == 1


def test_global_view_opens_without_a_selected_material(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_session(conn, material_id, status="completed")
    overview = svc.get_overview(conn, None, all_time_range)
    assert overview.completed_sessions == 1


# ---- sessions: stage outcomes ----


def test_session_history_reports_completed_skipped_and_incomplete_stages(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="active")
    session_repository.set_stage_status(conn, session_id, "global_comprehension", "completed")
    session_repository.set_stage_status(conn, session_id, "keyword_capture", "skipped", skip_note="skipped it")

    entries = svc.list_sessions(conn, material_id, all_time_range)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.completed_stage_count == 1
    assert entry.skipped_stage_count == 1
    assert entry.incomplete_stage_count == 3
    skip_notes = {s.stage_key: s.skip_note for s in entry.stages}
    assert skip_notes["keyword_capture"] == "skipped it"


def test_continue_learning_lists_only_active_sessions_and_ignores_date_range(conn):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    old_active = _make_session(conn, material_a, status="active")
    _touch_session_timestamp(conn, old_active, "last_resumed_at", _OLD_TIMESTAMP)
    conn.execute("UPDATE practice_session SET started_at = ? WHERE id = ?", (_OLD_TIMESTAMP, old_active))
    conn.commit()
    _make_session(conn, material_b, status="completed")

    entries = svc.list_continue_learning_sessions(conn)
    assert [e.session_id for e in entries] == [old_active]


def test_abandoned_session_never_appears_in_continue_learning(conn):
    material_id, _ = _make_material_with_cues(conn)
    _make_session(conn, material_id, status="abandoned")
    entries = svc.list_continue_learning_sessions(conn)
    assert entries == []


# ---- diagnosis: history vs current state ----


def test_diagnosis_insights_use_session_scoped_evidence_only(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id, label_key="misheard")
    _make_diagnosis(conn, session_id, cues[1].id, label_key="misheard")
    _make_diagnosis(conn, session_id, cues[1].id, label_key="keyword")

    summaries = svc.list_diagnosis_insights(conn, material_id, all_time_range)
    by_label = {s.label_key: s for s in summaries}
    assert by_label["misheard"].occurrence_count == 2
    assert by_label["misheard"].session_count == 1
    assert by_label["keyword"].occurrence_count == 1


def test_current_annotation_counts_are_never_mixed_with_session_history(conn):
    from listentrace.application.services import annotation_service

    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id, label_key="misheard")

    annotation_service.create_annotations(
        conn, cues[0].id, 0, len("Bonjour"), ["keyword"]
    )

    current_counts = svc.list_current_annotation_label_counts(conn, material_id)
    assert current_counts == {"keyword": 1}

    history = svc.list_diagnosis_insights(conn, material_id, resolve_date_range(PRESET_ALL_TIME, _TODAY_LOCAL))
    history_labels = {s.label_key for s in history}
    assert history_labels == {"misheard"}


# ---- quizzes: history and comparisons ----


def test_quiz_history_reports_accuracy_and_excludes_active_or_abandoned(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, status="completed", correct=3, actual=4)
    _make_quiz_attempt(conn, material_id, status="active")
    _make_quiz_attempt(conn, material_id, status="abandoned")

    history = svc.list_quiz_history(conn, material_id, all_time_range)
    assert len(history) == 1
    assert history[0].accuracy == pytest.approx(0.75)
    assert history[0].status == "completed"


def test_quiz_comparisons_group_by_material_and_mode_only(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_quiz_attempt(conn, material_a, status="completed", correct=1, actual=4)
    _make_quiz_attempt(conn, material_a, status="completed", correct=2, actual=4)
    _make_quiz_attempt(conn, material_b, status="completed", correct=3, actual=4)

    groups = svc.list_quiz_comparisons(conn, None, all_time_range)
    keyed = {(g.material_id, g.quiz_mode): g for g in groups}
    assert len(keyed[(material_a, "material")].entries) == 2
    assert len(keyed[(material_b, "material")].entries) == 1
    # oldest-first within a group
    accuracies = [e.accuracy for e in keyed[(material_a, "material")].entries]
    assert accuracies == pytest.approx([0.25, 0.5])


# ---- quiz trend chart: grouped by material and mode, never mixed ----


def test_quiz_trend_chart_separates_different_materials_into_different_groups(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_quiz_attempt(conn, material_a, status="completed", correct=1, actual=4)
    _make_quiz_attempt(conn, material_b, status="completed", correct=3, actual=4)

    chart_a = svc.chart_quiz_accuracy_over_time(conn, None, all_time_range, group_material_id=material_a, quiz_mode="material")
    chart_b = svc.chart_quiz_accuracy_over_time(conn, None, all_time_range, group_material_id=material_b, quiz_mode="material")

    assert len(chart_a.points) == 1
    assert len(chart_b.points) == 1
    assert chart_a.points[0].value == pytest.approx(25.0)
    assert chart_b.points[0].value == pytest.approx(75.0)
    assert chart_a.title != chart_b.title


def test_quiz_trend_chart_separates_different_quiz_modes_into_different_groups(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = session_repository.create_practice_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id)
    _make_quiz_attempt(conn, material_id, status="completed", correct=1, actual=4, quiz_mode="material")
    _make_quiz_attempt(conn, material_id, status="completed", correct=3, actual=4, quiz_mode="review")

    material_chart = svc.chart_quiz_accuracy_over_time(
        conn, None, all_time_range, group_material_id=material_id, quiz_mode="material"
    )
    review_chart = svc.chart_quiz_accuracy_over_time(
        conn, None, all_time_range, group_material_id=material_id, quiz_mode="review"
    )

    assert len(material_chart.points) == 1
    assert len(review_chart.points) == 1
    assert material_chart.points[0].value == pytest.approx(25.0)
    assert review_chart.points[0].value == pytest.approx(75.0)


def test_quiz_trend_chart_preserves_chronological_order_within_a_group(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, status="completed", correct=1, actual=4, completed_at="2026-01-01 00:00:00")
    _make_quiz_attempt(conn, material_id, status="completed", correct=2, actual=4, completed_at="2026-02-01 00:00:00")
    _make_quiz_attempt(conn, material_id, status="completed", correct=3, actual=4, completed_at="2026-03-01 00:00:00")

    chart = svc.chart_quiz_accuracy_over_time(
        conn, None, all_time_range, group_material_id=material_id, quiz_mode="material"
    )
    values = [p.value for p in chart.points]
    assert values == pytest.approx([25.0, 50.0, 75.0])


def test_quiz_trend_chart_never_mixes_materials_or_modes_into_one_series(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_quiz_attempt(conn, material_a, status="completed", correct=1, actual=4, quiz_mode="material")
    _make_quiz_attempt(conn, material_a, status="completed", correct=1, actual=4, quiz_mode="review")
    _make_quiz_attempt(conn, material_b, status="completed", correct=1, actual=4, quiz_mode="material")

    # No selector at all still yields exactly one group's worth of points,
    # never every attempt across every material/mode combined together.
    chart = svc.chart_quiz_accuracy_over_time(conn, None, all_time_range)
    assert len(chart.points) == 1

    # Every point in every possible group individually also never exceeds
    # that group's own attempt count.
    for group in svc.list_quiz_comparisons(conn, None, all_time_range):
        group_chart = svc.chart_quiz_accuracy_over_time(
            conn, None, all_time_range, group_material_id=group.material_id, quiz_mode=group.quiz_mode
        )
        assert len(group_chart.points) == len(group.entries)


def test_quiz_trend_chart_shows_question_count_alongside_each_attempt(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, status="completed", correct=1, actual=4)
    _make_quiz_attempt(conn, material_id, status="completed", correct=3, actual=10)

    chart = svc.chart_quiz_accuracy_over_time(
        conn, None, all_time_range, group_material_id=material_id, quiz_mode="material"
    )
    assert any("n=4" in p.label for p in chart.points)
    assert any("n=10" in p.label for p in chart.points)


def test_quiz_trend_chart_is_empty_when_no_completed_quizzes_exist(conn, all_time_range):
    chart = svc.chart_quiz_accuracy_over_time(conn, None, all_time_range)
    assert chart.points == []


# ---- shadowing ----


def test_shadowing_evidence_only_includes_rows_with_explicit_practice(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    session_repository.ensure_shadowing_rows(conn, session_id, [c.id for c in cues])
    session_repository.mark_shadowing_practiced(conn, session_id, cues[0].id)
    session_repository.mark_shadowing_practiced(conn, session_id, cues[0].id)

    evidence = svc.list_shadowing_evidence(conn, material_id, all_time_range)
    assert len(evidence) == 1
    assert evidence[0].practice_count == 2

    overview = svc.get_overview(conn, material_id, all_time_range)
    assert overview.shadowing_practice_count == 2


def test_high_frequency_shadowing_cues_are_ordered_by_practice_count(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn, cue_texts=("A", "B", "C"))
    session_id = _make_session(conn, material_id)
    session_repository.ensure_shadowing_rows(conn, session_id, [c.id for c in cues])
    for _ in range(3):
        session_repository.mark_shadowing_practiced(conn, session_id, cues[0].id)
    session_repository.mark_shadowing_practiced(conn, session_id, cues[1].id)

    top = svc.list_high_frequency_shadowing_cues(conn, material_id, all_time_range, top_n=1)
    assert len(top) == 1
    assert top[0].subtitle_cue_id == cues[0].id


# ---- needs attention ----


def test_needs_attention_flags_low_accuracy_material(conn):
    material_id, _ = _make_material_with_cues(conn)
    for _ in range(3):
        _make_quiz_attempt(conn, material_id, status="completed", correct=1, actual=4)  # 25% each

    entries = svc.list_needs_attention(conn)
    assert len(entries) == 1
    assert entries[0].material_id == material_id
    keys = [r.reason_key for r in entries[0].reasons]
    assert "low_recent_quiz_accuracy" in keys


def test_needs_attention_is_empty_for_a_healthy_material(conn):
    material_id, _ = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, status="completed", correct=4, actual=4)
    _make_session(conn, material_id, status="completed")

    entries = svc.list_needs_attention(conn)
    assert entries == []


def test_needs_attention_flags_active_unfinished_session(conn):
    material_id, _ = _make_material_with_cues(conn)
    _make_session(conn, material_id, status="active")
    entries = svc.list_needs_attention(conn)
    assert len(entries) == 1
    assert "active_unfinished_session" in [r.reason_key for r in entries[0].reasons]


# ---- activity feed ----


def test_activity_feed_keeps_each_evidence_kind_distinct(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="completed")
    _make_diagnosis(conn, session_id, cues[0].id)
    _make_quiz_attempt(conn, material_id, status="completed", correct=1, actual=4)
    _make_recording(conn, material_id, cues[0].id, status="ready")

    activity = svc.list_activity(conn, None, all_time_range)
    types = {item.activity_type for item in activity}
    assert types == {"session", "diagnosis", "quiz", "recording"}


def test_activity_feed_can_filter_by_type(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="completed")
    _make_diagnosis(conn, session_id, cues[0].id)

    activity = svc.list_activity(conn, None, all_time_range, activity_types=["diagnosis"])
    assert len(activity) == 1
    assert activity[0].activity_type == "diagnosis"


# ---- empty / partial states ----


def test_empty_material_has_empty_lists_not_errors(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    assert svc.list_sessions(conn, material_id, all_time_range) == []
    assert svc.list_quiz_history(conn, material_id, all_time_range) == []
    assert svc.list_diagnosis_insights(conn, material_id, all_time_range) == []
    assert svc.list_shadowing_evidence(conn, material_id, all_time_range) == []
    summary = svc.list_recording_evidence(conn, material_id, all_time_range)
    assert summary.entries == []
    assert summary.total_duration_ms == 0


def test_resolve_date_range_is_exposed_through_the_service(conn):
    resolved = svc.resolve_date_range(PRESET_LAST_7_DAYS, _TODAY_LOCAL)
    assert resolved.is_bounded

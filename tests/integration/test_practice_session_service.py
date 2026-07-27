from __future__ import annotations

import pytest

from listentrace.application.errors import (
    ActiveSessionExistsError,
    CueNotFoundError,
    DiagnosisNotFoundError,
    KeywordCaptureNotFoundError,
    SessionNotFoundError,
    SessionValidationError,
)
from listentrace.application.services import annotation_service
from listentrace.application.services import practice_session_service as svc
from listentrace.domain.enums.shadowing_status import ShadowingStatus
from listentrace.domain.enums.stage_status import StageStatus
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db import session_repository as repo
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.learning_repository import get_annotation, list_annotations_for_cue
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_material_with_cues(conn, cue_texts=("Bonjour tout le monde", "Comment ca va")):
    material_id = insert_material(conn, Material(title="Lesson", media_path="C:/media/lesson.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/lesson.srt",
        cues=[
            SubtitleCue(cue_index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=text)
            for i, text in enumerate(cue_texts)
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


# ---- lifecycle ----


def test_start_session_creates_five_not_started_stages(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    state = svc.load_session_state(conn, session.id)
    assert len(state.stage_progress) == 5
    assert all(p.status == "not_started" for p in state.stage_progress.values())
    assert session.current_stage == "global_comprehension"


def test_only_one_active_intensive_session_per_material(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    with pytest.raises(ActiveSessionExistsError):
        svc.start_session(conn, material_id)
    assert svc.find_active_session(conn, material_id).id == session.id


def test_new_attempt_allowed_after_completion_or_abandonment(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.abandon_session(conn, session.id)
    second = svc.start_session(conn, material_id)
    assert second.id != session.id
    svc.abandon_session(conn, second.id)

    third = svc.start_session(conn, material_id)
    assert svc.find_active_session(conn, material_id).id == third.id


def test_resume_updates_last_resumed_at_and_returns_full_state(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.save_stage_response(conn, session.id, "global_comprehension", "who_is_speaking", "A man")

    state = svc.resume_session(conn, session.id)
    assert state.stage_responses["global_comprehension"]["who_is_speaking"] == "A man"
    assert state.session.status == "active"


def test_resume_rejects_completed_or_abandoned_session(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.abandon_session(conn, session.id)
    with pytest.raises(SessionValidationError) as excinfo:
        svc.resume_session(conn, session.id)
    assert excinfo.value.category == "session_not_active"


def test_close_without_abandonment_leaves_session_active(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    # "Closing the window" has no dedicated verb in the service — it is simply not
    # calling abandon/complete. Confirm the session is still active and untouched.
    assert svc.get_session(conn, session.id).status == "active"


def test_abandon_then_double_abandon_is_rejected(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.abandon_session(conn, session.id)
    assert svc.get_session(conn, session.id).status == "abandoned"
    with pytest.raises(SessionValidationError) as excinfo:
        svc.abandon_session(conn, session.id)
    assert excinfo.value.category == "invalid_transition"


def test_complete_session_requires_every_stage_resolved(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    with pytest.raises(SessionValidationError) as excinfo:
        svc.complete_session(conn, session.id)
    assert excinfo.value.category == "session_not_ready"

    for stage_key in ("global_comprehension", "keyword_capture", "transcript_diagnosis", "shadowing", "final_summary"):
        svc.enter_stage(conn, session.id, stage_key)
        svc.skip_stage(conn, session.id, stage_key)
    svc.complete_session(conn, session.id)
    assert svc.get_session(conn, session.id).status == "completed"


def test_completed_and_abandoned_sessions_are_read_only(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.abandon_session(conn, session.id)
    with pytest.raises(SessionValidationError) as excinfo:
        svc.save_stage_response(conn, session.id, "global_comprehension", "who_is_speaking", "x")
    assert excinfo.value.category == "session_not_active"


def test_unknown_session_id_raises_not_found(conn):
    with pytest.raises(SessionNotFoundError):
        svc.load_session_state(conn, 999)


# ---- stage progression ----


def test_current_stage_persists_across_navigation(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.enter_stage(conn, session.id, "keyword_capture")
    assert svc.get_session(conn, session.id).current_stage == "keyword_capture"


def test_stage1_completes_with_partial_answers_but_not_when_empty(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    with pytest.raises(SessionValidationError) as excinfo:
        svc.complete_stage(conn, session.id, "global_comprehension")
    assert excinfo.value.category == "cannot_complete_stage"

    svc.save_stage_response(conn, session.id, "global_comprehension", "where", "A cafe")
    svc.complete_stage(conn, session.id, "global_comprehension")
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["global_comprehension"].status == "completed"


def test_stage1_empty_requires_explicit_skip(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.skip_stage(conn, session.id, "global_comprehension", skip_note="Could not make anything out.")
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["global_comprehension"].status == "skipped"
    assert state.stage_progress["global_comprehension"].skip_note == "Could not make anything out."


def test_stage2_requires_capture_or_explicit_skip(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")
    with pytest.raises(SessionValidationError):
        svc.complete_stage(conn, session.id, "keyword_capture")
    svc.add_keyword_capture(conn, session.id, "keyword", "bonjour")
    svc.complete_stage(conn, session.id, "keyword_capture")
    assert svc.load_session_state(conn, session.id).stage_progress["keyword_capture"].status == "completed"


def test_transcript_reveal_sets_timestamp_once(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    first = svc.get_session(conn, session.id).transcript_revealed_at
    assert first is not None
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    second = svc.get_session(conn, session.id).transcript_revealed_at
    assert first == second


def test_stage1_and_2_become_read_only_after_transcript_reveal(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.save_stage_response(conn, session.id, "global_comprehension", "where", "A cafe")
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    state = svc.load_session_state(conn, session.id)
    # Stage 1 had evidence -> auto-completed; Stage 2 had none -> auto-skipped.
    assert state.stage_progress["global_comprehension"].status == "completed"
    assert state.stage_progress["keyword_capture"].status == "skipped"

    with pytest.raises(SessionValidationError) as excinfo:
        svc.save_stage_response(conn, session.id, "global_comprehension", "where", "edited after lock")
    assert excinfo.value.category == "stage_locked"
    with pytest.raises(SessionValidationError):
        svc.add_keyword_capture(conn, session.id, "keyword", "too late")


def test_stage3_requires_evidence_or_no_difficulty_outcome_or_skip(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    with pytest.raises(SessionValidationError):
        svc.complete_stage(conn, session.id, "transcript_diagnosis")

    svc.mark_stage3_no_difficulty(conn, session.id)
    svc.complete_stage(conn, session.id, "transcript_diagnosis")
    assert svc.load_session_state(conn, session.id).stage_progress["transcript_diagnosis"].status == "completed"


def test_stage4_requires_all_cues_resolved_and_skip_remaining_resolves_it(conn):
    material_id, cues = _make_material_with_cues(conn, cue_texts=("One", "Two", "Three"))
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "shadowing")
    with pytest.raises(SessionValidationError):
        svc.complete_stage(conn, session.id, "shadowing")

    svc.mark_shadowing_practiced(conn, session.id, cues[0].id)
    with pytest.raises(SessionValidationError):
        svc.complete_stage(conn, session.id, "shadowing")

    svc.skip_remaining_shadowing(conn, session.id)
    svc.complete_stage(conn, session.id, "shadowing")
    progress = svc.list_shadowing_progress(conn, session.id)
    assert all(p.status != ShadowingStatus.NOT_STARTED.value for p in progress)


def test_stage5_requires_non_empty_summary_or_skip(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "final_summary")
    with pytest.raises(SessionValidationError):
        svc.complete_stage(conn, session.id, "final_summary")
    svc.save_stage_response(conn, session.id, "final_summary", "summary", "Un resume court.")
    svc.complete_stage(conn, session.id, "final_summary")
    assert svc.load_session_state(conn, session.id).stage_progress["final_summary"].status == "completed"


def test_back_navigation_does_not_roll_back_stage_status(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.save_stage_response(conn, session.id, "global_comprehension", "where", "A cafe")
    svc.complete_stage(conn, session.id, "global_comprehension")
    svc.enter_stage(conn, session.id, "keyword_capture")

    svc.enter_stage(conn, session.id, "global_comprehension")  # "Back"
    assert svc.load_session_state(conn, session.id).stage_progress["global_comprehension"].status == "completed"


# ---- keyword captures ----


def test_keyword_capture_add_edit_delete_round_trip(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")

    capture_id = svc.add_keyword_capture(conn, session.id, "keyword", "bonjour")
    svc.update_keyword_capture(conn, session.id, capture_id, "phrase", "bonjour tout le monde")
    captures = svc.list_keyword_captures(conn, session.id)
    assert captures[0].capture_type == "phrase"
    assert captures[0].text == "bonjour tout le monde"

    svc.delete_keyword_capture(conn, session.id, capture_id)
    assert svc.list_keyword_captures(conn, session.id) == []


def test_keyword_capture_rejects_invalid_type_and_whitespace_text(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")

    with pytest.raises(SessionValidationError) as excinfo:
        svc.add_keyword_capture(conn, session.id, "not_a_real_type", "text")
    assert excinfo.value.category == "invalid_capture_type"

    with pytest.raises(SessionValidationError) as excinfo:
        svc.add_keyword_capture(conn, session.id, "keyword", "   ")
    assert excinfo.value.category == "empty_capture_text"


def test_keyword_capture_reorder_is_stable_and_survives_resume(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")

    id_a = svc.add_keyword_capture(conn, session.id, "keyword", "a")
    id_b = svc.add_keyword_capture(conn, session.id, "keyword", "b")
    id_c = svc.add_keyword_capture(conn, session.id, "keyword", "c")
    svc.reorder_keyword_captures(conn, session.id, [id_c, id_a, id_b])

    ordered = [c.id for c in svc.list_keyword_captures(conn, session.id)]
    assert ordered == [id_c, id_a, id_b]

    state = svc.resume_session(conn, session.id)
    assert [c.id for c in state.keyword_captures] == [id_c, id_a, id_b]


def test_keyword_capture_is_read_only_after_transcript_reveal(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")
    capture_id = svc.add_keyword_capture(conn, session.id, "keyword", "bonjour")
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    with pytest.raises(SessionValidationError):
        svc.update_keyword_capture(conn, session.id, capture_id, "phrase", "edited")
    with pytest.raises(SessionValidationError):
        svc.delete_keyword_capture(conn, session.id, capture_id)
    with pytest.raises(SessionValidationError):
        svc.reorder_keyword_captures(conn, session.id, [capture_id])


def test_update_or_delete_unknown_capture_raises_not_found(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    with pytest.raises(KeywordCaptureNotFoundError):
        svc.update_keyword_capture(conn, session.id, 999, "keyword", "x")
    with pytest.raises(KeywordCaptureNotFoundError):
        svc.delete_keyword_capture(conn, session.id, 999)


# ---- session diagnosis ----


def test_session_diagnosis_whole_cue_and_partial_range(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    whole_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, len(cues[0].text), "keyword")
    partial_id = svc.record_session_diagnosis(conn, session.id, cues[1].id, 0, 7, "unknown_word_or_chunk")
    evidence = svc.list_session_diagnosis(conn, session.id)
    assert {e.id for e in evidence} == {whole_id, partial_id}


def test_misheard_diagnosis_requires_heard_as(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    with pytest.raises(SessionValidationError) as excinfo:
        svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "misheard")
    assert excinfo.value.category == "misheard_requires_heard_as"

    evidence_id = svc.record_session_diagnosis(
        conn, session.id, cues[0].id, 0, 7, "misheard", heard_as="Bonjour-ish"
    )
    evidence = svc.list_session_diagnosis(conn, session.id)
    assert next(e for e in evidence if e.id == evidence_id).heard_as == "Bonjour-ish"


def test_exact_duplicate_diagnosis_blocked_within_session_but_allowed_across_sessions(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    with pytest.raises(SessionValidationError) as excinfo:
        svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    assert excinfo.value.category == "duplicate_diagnosis_in_session"

    svc.complete_stage(conn, session.id, "transcript_diagnosis")
    svc.enter_stage(conn, session.id, "shadowing")
    svc.skip_remaining_shadowing(conn, session.id)
    svc.complete_stage(conn, session.id, "shadowing")
    svc.enter_stage(conn, session.id, "final_summary")
    svc.save_stage_response(conn, session.id, "final_summary", "summary", "x")
    svc.complete_stage(conn, session.id, "final_summary")
    svc.complete_session(conn, session.id)

    second_session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, second_session.id, "transcript_diagnosis")
    second_id = svc.record_session_diagnosis(conn, second_session.id, cues[0].id, 0, 7, "keyword")
    assert second_id is not None


def test_diagnosis_finds_or_creates_material_annotation_without_overwrite(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    first_evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword", note="first")
    first_evidence = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == first_evidence_id)
    assert first_evidence.annotation_id is not None
    annotation_before = get_annotation(conn, first_evidence.annotation_id)
    assert annotation_before.note == "first"

    svc.abandon_session(conn, session.id)
    second_session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, second_session.id, "transcript_diagnosis")
    second_evidence_id = svc.record_session_diagnosis(
        conn, second_session.id, cues[0].id, 0, 7, "keyword", note="second, should not overwrite"
    )
    second_evidence = next(
        e for e in svc.list_session_diagnosis(conn, second_session.id) if e.id == second_evidence_id
    )
    assert second_evidence.annotation_id == first_evidence.annotation_id
    annotation_after = get_annotation(conn, first_evidence.annotation_id)
    assert annotation_after.note == "first"  # reused, not overwritten


def test_session_diagnosis_snapshot_survives_material_annotation_deletion(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    evidence = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)

    from listentrace.infrastructure.db.learning_repository import delete_annotation

    delete_annotation(conn, evidence.annotation_id)

    surviving = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    assert surviving.selected_text == "Bonjour"
    assert surviving.annotation_id is None  # ON DELETE SET NULL


def test_editing_session_diagnosis_does_not_mutate_material_annotation(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword", note="original")
    evidence = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    annotation_id = evidence.annotation_id

    svc.update_session_diagnosis(conn, session.id, evidence_id, "keyword", 0, 7, note="edited snapshot")

    updated = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    assert updated.note == "edited snapshot"
    assert get_annotation(conn, annotation_id).note == "original"


def test_deleting_session_diagnosis_does_not_delete_material_annotation(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    evidence = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)

    svc.delete_session_diagnosis(conn, session.id, evidence_id)

    assert svc.list_session_diagnosis(conn, session.id) == []
    assert get_annotation(conn, evidence.annotation_id) is not None


def test_diagnosis_for_unknown_cue_or_evidence_raises_not_found(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    with pytest.raises(CueNotFoundError):
        svc.record_session_diagnosis(conn, session.id, 999, 0, 5, "keyword")
    with pytest.raises(DiagnosisNotFoundError):
        svc.update_session_diagnosis(conn, session.id, 999, "keyword", 0, 5)
    with pytest.raises(DiagnosisNotFoundError):
        svc.delete_session_diagnosis(conn, session.id, 999)


def test_record_session_diagnosis_is_atomic_across_annotation_and_evidence(conn, monkeypatch):
    """M12.2 regression: a failure between creating the material-level Annotation and
    inserting its session-scoped evidence snapshot must not leave an orphaned
    Annotation with no linked evidence row."""
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash between annotation insert and evidence insert")

    monkeypatch.setattr(repo, "insert_session_diagnosis", _boom)
    with pytest.raises(RuntimeError):
        svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")

    assert list_annotations_for_cue(conn, cues[0].id) == []
    assert svc.list_session_diagnosis(conn, session.id) == []

    monkeypatch.undo()
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    assert svc.list_session_diagnosis(conn, session.id)[0].id == evidence_id
    assert len(list_annotations_for_cue(conn, cues[0].id)) == 1


# ---- shadowing ----


def test_shadowing_progress_initializes_on_stage_entry(conn):
    material_id, cues = _make_material_with_cues(conn, cue_texts=("One", "Two"))
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "shadowing")
    progress = svc.list_shadowing_progress(conn, session.id)
    assert len(progress) == 2
    assert all(p.status == ShadowingStatus.NOT_STARTED.value for p in progress)
    assert all(p.practice_count == 0 for p in progress)


def test_practice_count_increments_only_on_explicit_mark_practiced(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "shadowing")
    svc.mark_shadowing_practiced(conn, session.id, cues[0].id)
    svc.mark_shadowing_practiced(conn, session.id, cues[0].id)
    progress = next(p for p in svc.list_shadowing_progress(conn, session.id) if p.subtitle_cue_id == cues[0].id)
    assert progress.status == ShadowingStatus.PRACTICED.value
    assert progress.practice_count == 2


def test_shadowing_skip_and_skip_remaining(conn):
    material_id, cues = _make_material_with_cues(conn, cue_texts=("One", "Two", "Three"))
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "shadowing")
    svc.mark_shadowing_skipped(conn, session.id, cues[0].id)
    svc.skip_remaining_shadowing(conn, session.id)
    progress = svc.list_shadowing_progress(conn, session.id)
    assert all(p.status == ShadowingStatus.SKIPPED.value for p in progress)


def test_shadowing_progress_survives_resume(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "shadowing")
    svc.mark_shadowing_practiced(conn, session.id, cues[0].id)
    svc.set_shadowing_note(conn, session.id, cues[0].id, "tricky liaison")

    state = svc.resume_session(conn, session.id)
    progress = next(p for p in state.shadowing_progress if p.subtitle_cue_id == cues[0].id)
    assert progress.status == ShadowingStatus.PRACTICED.value
    assert progress.note == "tricky liaison"


# ==== Acceptance-correction regression tests ====

# ---- 1. stage-completion invariants ----


def test_editing_stage1_response_to_empty_reverts_completed_stage(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "global_comprehension")
    svc.save_stage_response(conn, session.id, "global_comprehension", "where", "A cafe")
    svc.complete_stage(conn, session.id, "global_comprehension")
    assert svc.load_session_state(conn, session.id).stage_progress["global_comprehension"].status == "completed"

    svc.save_stage_response(conn, session.id, "global_comprehension", "where", "   ")
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["global_comprehension"].status == "in_progress"


def test_deleting_last_keyword_capture_reverts_completed_stage2(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "keyword_capture")
    capture_id = svc.add_keyword_capture(conn, session.id, "keyword", "bonjour")
    svc.complete_stage(conn, session.id, "keyword_capture")
    assert svc.load_session_state(conn, session.id).stage_progress["keyword_capture"].status == "completed"

    svc.delete_keyword_capture(conn, session.id, capture_id)
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["keyword_capture"].status == "in_progress"


def test_deleting_last_diagnosis_reverts_completed_stage3(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    svc.complete_stage(conn, session.id, "transcript_diagnosis")
    assert svc.load_session_state(conn, session.id).stage_progress["transcript_diagnosis"].status == "completed"

    svc.delete_session_diagnosis(conn, session.id, evidence_id)
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["transcript_diagnosis"].status == "in_progress"


def test_editing_stage5_summary_to_empty_reverts_completed_stage(conn):
    material_id, _ = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "final_summary")
    svc.save_stage_response(conn, session.id, "final_summary", "summary", "A short summary.")
    svc.complete_stage(conn, session.id, "final_summary")
    assert svc.load_session_state(conn, session.id).stage_progress["final_summary"].status == "completed"

    svc.save_stage_response(conn, session.id, "final_summary", "summary", "")
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["final_summary"].status == "in_progress"


def test_complete_session_revalidates_evidence_behind_a_stale_completed_stage(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)

    for stage_key in ("global_comprehension", "keyword_capture", "shadowing", "final_summary"):
        svc.enter_stage(conn, session.id, stage_key)
        svc.skip_stage(conn, session.id, stage_key)

    # Simulate a stale `completed` status with no backing evidence at all — a
    # state the public API should never itself produce, but `complete_session`
    # must defend against trusting stored status alone.
    repo.set_stage_status(conn, session.id, "transcript_diagnosis", StageStatus.IN_PROGRESS.value)
    repo.set_stage_status(conn, session.id, "transcript_diagnosis", StageStatus.COMPLETED.value)

    with pytest.raises(SessionValidationError) as excinfo:
        svc.complete_session(conn, session.id)
    assert excinfo.value.category == "session_not_ready"

    assert svc.get_session(conn, session.id).status == "active"
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["transcript_diagnosis"].status == "in_progress"


# ---- 2. Stage 3 application-layer enforcement ----


def test_diagnosis_requires_transcript_revealed(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    with pytest.raises(SessionValidationError) as excinfo:
        svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    assert excinfo.value.category == "transcript_not_revealed"

    with pytest.raises(SessionValidationError) as excinfo:
        svc.mark_stage3_no_difficulty(conn, session.id)
    assert excinfo.value.category == "transcript_not_revealed"


def test_diagnosis_requires_stage3_to_be_current_stage(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    svc.enter_stage(conn, session.id, "shadowing")  # transcript stays revealed, but stage3 no longer current

    with pytest.raises(SessionValidationError) as excinfo:
        svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    assert excinfo.value.category == "wrong_stage"

    with pytest.raises(SessionValidationError) as excinfo:
        svc.mark_stage3_no_difficulty(conn, session.id)
    assert excinfo.value.category == "wrong_stage"

    with pytest.raises(SessionValidationError) as excinfo:
        svc.delete_session_diagnosis(conn, session.id, 999)
    assert excinfo.value.category == "wrong_stage"


def test_no_notable_difficulty_rejected_while_diagnosis_evidence_exists(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")

    with pytest.raises(SessionValidationError) as excinfo:
        svc.mark_stage3_no_difficulty(conn, session.id)
    assert excinfo.value.category == "diagnosis_evidence_exists"


def test_recording_diagnosis_clears_a_prior_no_notable_difficulty_outcome(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    svc.mark_stage3_no_difficulty(conn, session.id)
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["transcript_diagnosis"].outcome_key == "no_notable_difficulty"

    svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    state = svc.load_session_state(conn, session.id)
    assert state.stage_progress["transcript_diagnosis"].outcome_key is None


# ---- 3. cue ownership ----


def test_record_session_diagnosis_rejects_a_cue_from_a_different_material(conn):
    material_a, cues_a = _make_material_with_cues(conn, cue_texts=("Material A cue",))
    material_b, cues_b = _make_material_with_cues(conn, cue_texts=("Material B cue",))
    session = svc.start_session(conn, material_a)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")

    with pytest.raises(SessionValidationError) as excinfo:
        svc.record_session_diagnosis(conn, session.id, cues_b[0].id, 0, 6, "keyword")
    assert excinfo.value.category == "cue_material_mismatch"

    # The matching-material cue must still work normally.
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues_a[0].id, 0, 6, "keyword")
    assert evidence_id is not None


# ---- 4. truthful annotation links after diagnosis edits ----


def test_update_session_diagnosis_clears_stale_annotation_link_when_no_match_exists(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    original = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    original_annotation_id = original.annotation_id
    assert original_annotation_id is not None

    # No `unknown_word_or_chunk` annotation exists for this cue/range, so the
    # link must be cleared, not left pointing at the old `keyword` annotation.
    svc.update_session_diagnosis(conn, session.id, evidence_id, "unknown_word_or_chunk", 0, 7)

    updated = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    assert updated.annotation_id is None
    # The original annotation itself must be untouched.
    assert get_annotation(conn, original_annotation_id).label_key == "keyword"


def test_update_session_diagnosis_relinks_to_a_different_existing_annotation(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_session(conn, material_id)
    svc.enter_stage(conn, session.id, "transcript_diagnosis")
    evidence_id = svc.record_session_diagnosis(conn, session.id, cues[0].id, 0, 7, "keyword")
    original = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    original_annotation_id = original.annotation_id

    # A material-level annotation for the new label/range already exists
    # (e.g. created independently via the Milestone 4 standalone workspace).
    other_ids = annotation_service.create_annotations(
        conn, cues[0].id, 0, 7, ["unknown_word_or_chunk"]
    )
    other_annotation_id = other_ids[0]

    svc.update_session_diagnosis(conn, session.id, evidence_id, "unknown_word_or_chunk", 0, 7)

    updated = next(e for e in svc.list_session_diagnosis(conn, session.id) if e.id == evidence_id)
    assert updated.annotation_id == other_annotation_id
    assert updated.annotation_id != original_annotation_id
    # Neither annotation row was mutated by the relink.
    assert get_annotation(conn, original_annotation_id).label_key == "keyword"
    assert get_annotation(conn, other_annotation_id).label_key == "unknown_word_or_chunk"

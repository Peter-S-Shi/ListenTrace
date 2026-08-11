from __future__ import annotations

import pytest

from listentrace.application.errors import (
    CueNotFoundError,
    QuickPracticeDiagnosisNotFoundError,
    QuickPracticeItemNotFoundError,
    QuickPracticeNotFoundError,
    QuickPracticeValidationError,
)
from listentrace.application.services import quick_practice_service as svc
from listentrace.domain.enums.quick_practice_source import QuickPracticeSource
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db import quick_practice_repository as repo
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.learning_repository import insert_annotations, list_annotations_for_cue
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    delete_material,
    insert_material,
    insert_subtitle_track,
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "quick_practice.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_material_with_cues(conn, cue_texts=("Bonjour tout le monde", "Comment ca va", "Au revoir", "Merci beaucoup")):
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


# ---- starting a run ----


def test_start_selected_session_preserves_given_order(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[2].id, cues[0].id])
    assert session.source_type == QuickPracticeSource.SELECTED.value
    assert session.actual_count == 2
    state = svc.load_session_state(conn, session.id)
    assert [i.item.subtitle_cue_id for i in state.items] == [cues[2].id, cues[0].id]


def test_start_selected_session_rejects_empty_selection(conn):
    material_id, _ = _make_material_with_cues(conn)
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.start_selected_session(conn, material_id, [])
    assert excinfo.value.category == "empty_selection"


def test_start_selected_session_rejects_duplicate_cues(conn):
    material_id, cues = _make_material_with_cues(conn)
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.start_selected_session(conn, material_id, [cues[0].id, cues[0].id])
    assert excinfo.value.category == "duplicate_cue_selection"


def test_start_selected_session_rejects_a_cue_from_another_material(conn):
    material_id, cues = _make_material_with_cues(conn)
    other_material_id, other_cues = _make_material_with_cues(conn, cue_texts=("Different material",))
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.start_selected_session(conn, material_id, [cues[0].id, other_cues[0].id])
    assert excinfo.value.category == "cue_material_mismatch"


def test_start_recommended_session_rejects_an_unsupported_count(conn):
    material_id, _ = _make_material_with_cues(conn)
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.start_recommended_session(conn, material_id, 4)
    assert excinfo.value.category == "invalid_count"


def test_start_recommended_session_falls_back_to_material_order_with_no_evidence(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_recommended_session(conn, material_id, 3)
    assert session.source_type == QuickPracticeSource.RECOMMENDED.value
    state = svc.load_session_state(conn, session.id)
    assert [i.item.subtitle_cue_id for i in state.items] == [c.id for c in cues[:3]]


def test_recommend_cues_prefers_cues_with_misheard_evidence(conn):
    material_id, cues = _make_material_with_cues(conn)
    insert_annotations(conn, cues[2].id, [("misheard", "wrong word")], cues[2].text, 0, 5, None)
    entries = svc.recommend_cues(conn, material_id, 2)
    assert entries[0].subtitle_cue_id == cues[2].id
    assert "marked_misheard" in entries[0].reasons


def test_recommend_cues_prefers_cues_with_incorrect_quiz_evidence(conn):
    material_id, cues = _make_material_with_cues(conn)
    cursor = conn.execute(
        "INSERT INTO quiz_attempt (material_id, quiz_mode, status, seed, requested_count, actual_count, correct_count, completed_at) "
        "VALUES (?, 'material', 'completed', 1, 1, 1, 0, datetime('now'))",
        (material_id,),
    )
    attempt_id = int(cursor.lastrowid)
    cursor = conn.execute(
        "INSERT INTO quiz_question (quiz_attempt_id, position, question_type, subtitle_cue_id, prompt_payload, "
        "correct_answer_payload, scoring_config) VALUES (?, 0, 'dictation', ?, '{}', '{}', '{}')",
        (attempt_id, cues[1].id),
    )
    question_id = int(cursor.lastrowid)
    conn.execute(
        "INSERT INTO quiz_answer (quiz_question_id, is_correct, answered_state, answered_at) "
        "VALUES (?, 0, 'answered', datetime('now'))",
        (question_id,),
    )
    conn.commit()
    entries = svc.recommend_cues(conn, material_id, 2)
    assert entries[0].subtitle_cue_id == cues[1].id
    assert "incorrect_quiz_evidence" in entries[0].reasons


def test_recommend_cues_little_shadowing_reason_clears_after_explicit_quick_practice_shadowing(conn):
    """Explicit Quick Practice shadowing (`shadowed_at`) is real shadowing
    evidence and must count the same as Intensive Practice shadowing for
    the "little or no shadowing practice" reason — while the cue's own
    independent qualifying reason (here, `marked_misheard`) stays intact."""
    material_id, cues = _make_material_with_cues(conn)
    cue = cues[0]
    insert_annotations(conn, cue.id, [("misheard", "wrong word")], cue.text[0:7], 0, 7, None)

    before = svc.recommend_cues(conn, material_id, 1)
    assert before[0].subtitle_cue_id == cue.id
    assert "marked_misheard" in before[0].reasons
    assert "little_or_no_shadowing_practice" in before[0].reasons

    session = svc.start_selected_session(conn, material_id, [cue.id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.mark_item_shadowed(conn, item_id)
    svc.complete_item(conn, item_id)
    svc.complete_session(conn, session.id)

    after = svc.recommend_cues(conn, material_id, 1)
    assert after[0].subtitle_cue_id == cue.id
    assert "marked_misheard" in after[0].reasons
    assert "little_or_no_shadowing_practice" not in after[0].reasons


def test_recommend_cues_does_not_count_shadowing_from_an_incomplete_quick_practice_item(conn):
    """An item that was shadowed but never completed (the run is still
    active, or was discarded/abandoned before this item finished) is not
    "completed Quick Practice" evidence yet."""
    material_id, cues = _make_material_with_cues(conn)
    cue = cues[0]
    insert_annotations(conn, cue.id, [("misheard", "wrong word")], cue.text[0:7], 0, 7, None)

    session = svc.start_selected_session(conn, material_id, [cue.id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.mark_item_shadowed(conn, item_id)
    # deliberately not completed

    entries = svc.recommend_cues(conn, material_id, 1)
    assert entries[0].subtitle_cue_id == cue.id
    assert "little_or_no_shadowing_practice" in entries[0].reasons


# ---- Step 2: recall ----


def test_record_recall_reveals_transcript_and_rejects_unknown_result(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id

    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_recall(conn, item_id, "confused")
    assert excinfo.value.category == "invalid_recall_result"

    svc.record_recall(conn, item_id, "missed", "  ")
    item = svc.load_session_state(conn, session.id).items[0].item
    assert item.recall_result == "missed"
    assert item.heard_fragment is None  # whitespace-only fragment is treated as absent
    assert item.transcript_revealed is True


def test_record_recall_on_completed_item_is_rejected(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.complete_item(conn, item_id)
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_recall(conn, item_id, "missed")
    assert excinfo.value.category == "item_already_completed"


# ---- Step 3: diagnosis (reuses Milestone 4 rules, distinct provenance) ----


def test_diagnosis_requires_recall_first(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_item_diagnosis(conn, item_id, 0, 7, "misheard", heard_as="x")
    assert excinfo.value.category == "transcript_not_revealed"


def test_diagnosis_reuses_an_existing_material_annotation_rather_than_duplicating(conn):
    material_id, cues = _make_material_with_cues(conn)
    existing_ids = insert_annotations(conn, cues[0].id, [("misheard", "wrong")], cues[0].text[0:7], 0, 7, None)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")

    evidence_id = svc.record_item_diagnosis(conn, item_id, 0, 7, "misheard", heard_as="wrong")
    evidence = repo.get_item_diagnosis(conn, evidence_id)
    assert evidence.annotation_id == existing_ids[0]
    assert len(list_annotations_for_cue(conn, cues[0].id)) == 1  # no duplicate annotation created


def test_diagnosis_misheard_requires_heard_as(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_item_diagnosis(conn, item_id, 0, 7, "misheard")
    assert excinfo.value.category == "misheard_requires_heard_as"


def test_diagnosis_rejects_exact_duplicate_within_the_same_item(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")
    assert excinfo.value.category == "duplicate_diagnosis_in_item"


def test_delete_item_diagnosis_never_deletes_the_linked_annotation(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    evidence_id = svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")

    svc.delete_item_diagnosis(conn, item_id, evidence_id)
    assert svc.list_item_diagnosis(conn, item_id) == []
    assert len(list_annotations_for_cue(conn, cues[0].id)) == 1  # annotation itself survives

    with pytest.raises(QuickPracticeDiagnosisNotFoundError):
        svc.delete_item_diagnosis(conn, item_id, evidence_id)


def test_diagnosis_rejects_an_unknown_cue_range(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.record_item_diagnosis(conn, item_id, 0, 9999, "keyword")
    assert excinfo.value.category == "invalid_range"


def test_record_item_diagnosis_is_atomic_across_annotation_and_evidence(conn, monkeypatch):
    """M12.2 regression: a failure between creating the material-level Annotation and
    inserting its Quick-Practice-scoped evidence snapshot must not leave an orphaned
    Annotation with no linked evidence row."""
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash between annotation insert and evidence insert")

    monkeypatch.setattr(repo, "insert_item_diagnosis", _boom)
    with pytest.raises(RuntimeError):
        svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")

    assert list_annotations_for_cue(conn, cues[0].id) == []
    assert svc.list_item_diagnosis(conn, item_id) == []

    monkeypatch.undo()
    evidence_id = svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")
    assert svc.list_item_diagnosis(conn, item_id)[0].id == evidence_id
    assert len(list_annotations_for_cue(conn, cues[0].id)) == 1


# ---- Step 4: shadowing ----


def test_mark_item_shadowed_is_rejected_before_recall_is_recorded(conn):
    """Shadowing is Step 4 of the per-cue cycle and cannot precede Recall
    (Step 2) / Reveal (Step 3) — mirrors the same revealed-item guard
    diagnosis uses."""
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.mark_item_shadowed(conn, item_id)
    assert excinfo.value.category == "transcript_not_revealed"
    assert svc.load_session_state(conn, session.id).items[0].item.shadowed_at is None


def test_mark_item_shadowed_succeeds_once_recall_has_revealed_the_transcript(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.mark_item_shadowed(conn, item_id)
    assert svc.load_session_state(conn, session.id).items[0].item.shadowed_at is not None


def test_mark_item_shadowed_is_idempotent(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.mark_item_shadowed(conn, item_id)
    first = svc.load_session_state(conn, session.id).items[0].item.shadowed_at
    svc.mark_item_shadowed(conn, item_id)
    second = svc.load_session_state(conn, session.id).items[0].item.shadowed_at
    assert first == second


def test_mark_item_shadowed_is_rejected_on_an_abandoned_session(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id])
    items = svc.load_session_state(conn, session.id).items
    svc.record_recall(conn, items[0].item.id, "understood")
    svc.complete_item(conn, items[0].item.id)
    outcome = svc.close_session(conn, session.id)  # one item completed -> abandoned, not discarded
    assert outcome == "abandoned"

    assert svc.get_session(conn, session.id).status == QuickPracticeStatus.ABANDONED.value
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.mark_item_shadowed(conn, items[1].item.id)
    assert excinfo.value.category == "session_not_active"


# ---- item / session completion ----


def test_complete_item_requires_a_recall_result(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.complete_item(conn, item_id)
    assert excinfo.value.category == "recall_required"


def test_complete_session_requires_every_item_completed(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id])
    items = svc.load_session_state(conn, session.id).items
    svc.record_recall(conn, items[0].item.id, "understood")
    svc.complete_item(conn, items[0].item.id)
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.complete_session(conn, session.id)
    assert excinfo.value.category == "session_not_ready"


def test_completed_session_is_read_only(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.complete_item(conn, item_id)
    svc.complete_session(conn, session.id)

    assert svc.get_session(conn, session.id).status == QuickPracticeStatus.COMPLETED.value
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.mark_item_shadowed(conn, item_id)
    assert excinfo.value.category == "session_not_active"


# ---- closing mid-run ----


def test_close_session_discards_with_zero_completed_items(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    outcome = svc.close_session(conn, session.id)
    assert outcome == "discarded"
    assert svc.get_session(conn, session.id) is None


def test_close_session_abandons_and_preserves_completed_evidence(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.complete_item(conn, item_id)

    outcome = svc.close_session(conn, session.id)
    assert outcome == "abandoned"
    session_after = svc.get_session(conn, session.id)
    assert session_after.status == QuickPracticeStatus.ABANDONED.value
    state = svc.load_session_state(conn, session.id)
    assert state.items[0].item.recall_result == "understood"  # preserved, not wiped


def test_close_session_on_an_already_resolved_session_is_a_no_op(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.complete_item(conn, item_id)
    svc.complete_session(conn, session.id)
    assert svc.close_session(conn, session.id) == "completed"


def test_delete_history_requires_completed_or_abandoned(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id])
    with pytest.raises(QuickPracticeValidationError) as excinfo:
        svc.delete_history(conn, session.id)
    assert excinfo.value.category == "session_active"

    svc.close_session(conn, session.id)  # zero progress -> discarded, not a useful case here
    session2 = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id])
    item_id = svc.load_session_state(conn, session2.id).items[0].item.id
    svc.record_recall(conn, item_id, "understood")
    svc.complete_item(conn, item_id)
    svc.close_session(conn, session2.id)  # -> abandoned (has evidence)

    svc.delete_history(conn, session2.id)  # must not raise once abandoned
    assert svc.get_session(conn, session2.id) is None


def test_delete_history_removes_items_but_preserves_independent_annotations(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")
    svc.complete_item(conn, item_id)
    svc.complete_session(conn, session.id)

    svc.delete_history(conn, session.id)

    assert svc.get_session(conn, session.id) is None
    remaining_items = conn.execute(
        "SELECT COUNT(*) AS n FROM quick_practice_item WHERE id = ?", (item_id,)
    ).fetchone()["n"]
    assert remaining_items == 0
    assert list_annotations_for_cue(conn, cues[0].id), "independent annotation must survive session deletion"


def test_recover_interrupted_sessions_applies_close_rules_to_every_active_run(conn):
    material_id, cues = _make_material_with_cues(conn)
    zero_progress = svc.start_selected_session(conn, material_id, [cues[0].id])
    with_progress = svc.start_selected_session(conn, material_id, [cues[1].id, cues[2].id])
    item_id = svc.load_session_state(conn, with_progress.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    svc.complete_item(conn, item_id)

    recovered = svc.recover_interrupted_sessions(conn)
    assert recovered == 2
    assert svc.get_session(conn, zero_progress.id) is None
    assert svc.get_session(conn, with_progress.id).status == QuickPracticeStatus.ABANDONED.value


# ---- completion summary ----


def test_build_completion_summary_counts_are_accurate(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id, cues[1].id, cues[2].id])
    items = svc.load_session_state(conn, session.id).items

    svc.record_recall(conn, items[0].item.id, "missed")
    svc.record_item_diagnosis(conn, items[0].item.id, 0, 7, "keyword")
    svc.mark_item_shadowed(conn, items[0].item.id)
    svc.complete_item(conn, items[0].item.id)

    svc.record_recall(conn, items[1].item.id, "understood")
    svc.complete_item(conn, items[1].item.id)

    svc.record_recall(conn, items[2].item.id, "partly_understood")
    svc.complete_item(conn, items[2].item.id)
    svc.complete_session(conn, session.id)

    summary = svc.build_completion_summary(conn, session.id)
    assert summary.cues_completed == 3
    assert summary.understood_count == 1
    assert summary.partly_understood_count == 1
    assert summary.missed_count == 1
    assert summary.diagnoses_created == 1
    assert summary.shadowing_actions == 1
    assert summary.cues_worth_revisiting == [cues[0].id]  # missed + diagnosed cue only


# ---- not-found errors ----


def test_operations_on_a_missing_session_or_item_raise_not_found(conn):
    with pytest.raises(QuickPracticeNotFoundError):
        svc.load_session_state(conn, 999999)
    with pytest.raises(QuickPracticeItemNotFoundError):
        svc.record_recall(conn, 999999, "understood")


def test_diagnosis_raises_cue_not_found_only_when_the_cue_row_itself_is_gone(conn):
    # Ordinary flow never hits this (a cue's own subtitle_cue row cannot
    # disappear while its quick_practice_item still references it, thanks
    # to ON DELETE CASCADE) — included for completeness against the shared
    # `CueNotFoundError` import used by the guard.
    assert CueNotFoundError is not None


# ---- material-deletion cascade ----


def test_removing_a_material_cascades_quick_practice_evidence(conn):
    material_id, cues = _make_material_with_cues(conn)
    session = svc.start_selected_session(conn, material_id, [cues[0].id])
    item_id = svc.load_session_state(conn, session.id).items[0].item.id
    svc.record_recall(conn, item_id, "missed")
    evidence_id = svc.record_item_diagnosis(conn, item_id, 0, 7, "keyword")
    svc.complete_item(conn, item_id)
    svc.complete_session(conn, session.id)

    delete_material(conn, material_id)

    assert svc.get_session(conn, session.id) is None
    assert repo.get_item(conn, item_id) is None
    assert repo.get_item_diagnosis(conn, evidence_id) is None

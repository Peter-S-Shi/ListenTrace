from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from listentrace.application.dto.export import (
    SCOPE_ALL,
    SCOPE_ONE_MATERIAL,
    SCOPE_SELECTED_MATERIALS,
    ExportScope,
)
from listentrace.application.services import export_service as svc
from listentrace.domain.models.material import Material
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion
from listentrace.domain.models.recording import Recording
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.domain.services import export_privacy
from listentrace.domain.services.date_range import PRESET_ALL_TIME, PRESET_LAST_7_DAYS, resolve_date_range
from listentrace.infrastructure.db import learning_repository, quiz_repository, recording_repository, session_repository
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)

_OLD_TIMESTAMP = "2000-01-01 00:00:00"
_TODAY_LOCAL = date(2026, 7, 24)
_ALL_CATEGORIES = frozenset(export_privacy.EVIDENCE_CATEGORIES)
_ALL_PRIVACY_FIELDS = frozenset(export_privacy.PRIVACY_FIELDS)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def all_time_range():
    return resolve_date_range(PRESET_ALL_TIME, _TODAY_LOCAL)


@pytest.fixture()
def recent_range():
    return resolve_date_range(PRESET_LAST_7_DAYS, _TODAY_LOCAL)


def _make_material_with_cues(conn, title="Lesson", media_path=None):
    material_id = insert_material(
        conn, Material(title=title, media_path=media_path or f"C:/Users/name/Videos/{title}.mp4", language="fr")
    )
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path=f"C:/Users/name/Videos/{title}.srt",
        cues=[
            SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour"),
            SubtitleCue(cue_index=2, start_ms=1000, end_ms=2000, text="Au revoir"),
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def _make_session(conn, material_id, status="completed"):
    session_id = session_repository.create_practice_session(conn, material_id)
    if status != "active":
        session_repository.set_session_status(conn, session_id, status)
    return session_id


def _make_diagnosis(conn, session_id, cue_id, label_key="misheard"):
    evidence = SessionDiagnosisEvidence(
        practice_session_id=session_id,
        subtitle_cue_id=cue_id,
        label_key=label_key,
        selected_text="Bonjour",
        selection_start=0,
        selection_end=7,
        heard_as="Bonjoir" if label_key == "misheard" else None,
    )
    return session_repository.insert_session_diagnosis(conn, evidence)


def _make_quiz_attempt(conn, material_id, cue_id, status="completed", correct=1, actual=1):
    attempt = QuizAttempt(material_id=material_id, requested_count=actual)
    question = QuizQuestion(
        question_type="dictation",
        subtitle_cue_id=cue_id,
        source_cue_text="Bonjour",
        prompt_payload="{}",
        correct_answer_payload='{"correct_text": "Bonjour"}',
        scoring_config='{"rule": "normalized_text_exact", "version": 1}',
    )
    attempt_id, question_ids = quiz_repository.create_quiz_attempt_with_questions(conn, attempt, [question] * actual)
    if status == "completed":
        quiz_repository.save_quiz_answer(conn, question_ids[0], "Bonjour", "bonjour", None)
        quiz_repository.set_quiz_answer_correctness(conn, question_ids[0], True)
        quiz_repository.finalize_quiz_score(conn, attempt_id, correct)
        conn.commit()
    elif status == "abandoned":
        quiz_repository.set_quiz_status(conn, attempt_id, "abandoned")
    return attempt_id


def _make_recording(conn, material_id, cue_id, status="ready", session_id=None):
    recording = Recording(
        material_id=material_id,
        subtitle_cue_id=cue_id,
        practice_session_id=session_id,
        relative_file_path=f"{material_id}/{uuid.uuid4().hex}.wav",
    )
    recording_id = recording_repository.insert_recording(conn, recording)
    if status == "ready":
        recording_repository.set_recording_ready(conn, recording_id, 1500)
    elif status == "failed":
        recording_repository.set_recording_failed(conn, recording_id, "bad")
    return recording_id


# ---- scope ----


def test_global_scope_exports_every_material(conn, all_time_range):
    _make_material_with_cues(conn, title="A")
    _make_material_with_cues(conn, title="B")
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS)
    assert len(bundle.materials) == 2


def test_one_material_scope_exports_only_that_material(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    _make_material_with_cues(conn, title="B")
    bundle = svc.build_export(
        conn, ExportScope(kind=SCOPE_ONE_MATERIAL, material_ids=(material_a,)), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS
    )
    assert len(bundle.materials) == 1
    assert bundle.materials[0]["material_id"] == material_a


def test_selected_materials_scope_exports_only_those_materials(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_material_with_cues(conn, title="C")
    bundle = svc.build_export(
        conn,
        ExportScope(kind=SCOPE_SELECTED_MATERIALS, material_ids=(material_a, material_b)),
        all_time_range,
        _ALL_CATEGORIES,
        _ALL_PRIVACY_FIELDS,
    )
    ids = {m["material_id"] for m in bundle.materials}
    assert ids == {material_a, material_b}


def test_global_export_works_without_a_selected_material(conn, all_time_range):
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS)
    assert bundle.materials == []
    assert bundle.scope_description == "All Materials"


# ---- date filtering ----


def test_date_filtering_matches_learning_historys_session_anchor(conn, recent_range):
    material_id, _ = _make_material_with_cues(conn)
    old_session = _make_session(conn, material_id, status="completed")
    conn.execute("UPDATE practice_session SET completed_at = ? WHERE id = ?", (_OLD_TIMESTAMP, old_session))
    recent_session = _make_session(conn, material_id, status="completed")
    conn.execute("UPDATE practice_session SET completed_at = ? WHERE id = ?", (recent_range.start_utc, recent_session))
    conn.commit()

    categories = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), recent_range, categories, _ALL_PRIVACY_FIELDS)
    session_ids = [s["session_id"] for s in bundle.materials[0]["sessions"]]
    assert session_ids == [recent_session]


def test_all_time_includes_everything(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="completed")
    conn.execute("UPDATE practice_session SET completed_at = ? WHERE id = ?", (_OLD_TIMESTAMP, session_id))
    conn.commit()
    categories = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    assert len(bundle.materials[0]["sessions"]) == 1


# ---- privacy filtering ----


def test_privacy_field_off_redacts_the_value_but_keeps_the_record(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id)

    categories = frozenset({export_privacy.CATEGORY_SESSION_DIAGNOSIS_HISTORY})
    no_mishearing = frozenset(export_privacy.PRIVACY_FIELDS) - {export_privacy.PRIVACY_MISHEARING_TEXT}
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, no_mishearing)

    history = bundle.materials[0]["session_diagnosis_history"]
    assert len(history) == 1  # the record is still present
    assert history[0]["heard_as"] == export_privacy.REDACTED_PLACEHOLDER
    assert history[0]["transcript_excerpt"] == "Bonjour"  # unaffected field stays


def test_all_privacy_fields_off_redacts_every_sensitive_field(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id)

    categories = frozenset({export_privacy.CATEGORY_SESSION_DIAGNOSIS_HISTORY})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, frozenset())

    history = bundle.materials[0]["session_diagnosis_history"]
    assert history[0]["heard_as"] == export_privacy.REDACTED_PLACEHOLDER
    assert history[0]["transcript_excerpt"] == export_privacy.REDACTED_PLACEHOLDER


# ---- path exclusion ----


def test_no_absolute_or_relative_paths_appear_anywhere_in_the_export(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn, media_path="C:/Users/name/Videos/secret_lesson.mp4")
    session_id = _make_session(conn, material_id)
    _make_recording(conn, material_id, cues[0].id, status="ready", session_id=session_id)

    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS)
    serialized = json.dumps(bundle.materials)
    assert "C:/Users" not in serialized
    assert "C:\\\\Users" not in serialized
    assert ".wav" not in serialized
    assert "relative_file_path" not in serialized


def test_local_file_names_privacy_field_shows_only_the_bare_filename(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn, media_path="C:/Users/name/Videos/secret_lesson.mp4")
    categories = frozenset({export_privacy.CATEGORY_MATERIAL_METADATA})
    privacy_fields = frozenset({export_privacy.PRIVACY_SOURCE_LABELS, export_privacy.PRIVACY_LOCAL_FILE_NAMES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, privacy_fields)
    label = bundle.materials[0]["material_metadata"]["source_label"]
    assert label == "secret_lesson.mp4"
    assert "C:" not in label
    assert "/" not in label


def test_source_label_is_generic_when_local_file_names_is_excluded(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn, media_path="C:/Users/name/Videos/secret_lesson.mp4")
    categories = frozenset({export_privacy.CATEGORY_MATERIAL_METADATA})
    privacy_fields = frozenset({export_privacy.PRIVACY_SOURCE_LABELS})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, privacy_fields)
    label = bundle.materials[0]["material_metadata"]["source_label"]
    assert "secret_lesson" not in label
    assert label == "media file"


# ---- diagnosis-source separation ----


def test_diagnosis_history_and_current_annotations_are_separate_keys(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id)
    _make_diagnosis(conn, session_id, cues[0].id)
    learning_repository.insert_annotations(conn, cues[0].id, [("keyword", None)], "Bonjour", 0, 7, None)

    categories = frozenset(
        {export_privacy.CATEGORY_SESSION_DIAGNOSIS_HISTORY, export_privacy.CATEGORY_CURRENT_ANNOTATIONS}
    )
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    material = bundle.materials[0]
    assert material["session_diagnosis_history"][0]["label_key"] == "misheard"
    assert material["current_material_annotations"][0]["label_key"] == "keyword"
    # never merged into one list or one count
    assert "session_diagnosis_history" in material and "current_material_annotations" in material


# ---- quiz snapshot preservation ----


def test_quiz_question_snapshot_is_not_regenerated_after_a_live_cue_edit(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, cues[0].id, status="completed")

    conn.execute("UPDATE subtitle_cue SET text = ? WHERE id = ?", ("A completely different sentence", cues[0].id))
    conn.commit()

    categories = frozenset({export_privacy.CATEGORY_QUIZ_ATTEMPTS, export_privacy.CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    question = bundle.materials[0]["quiz_attempts"][0]["questions"][0]
    assert question["source_cue_text"] == "Bonjour"


def test_incomplete_quiz_attempts_are_excluded_from_export(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, cues[0].id, status="completed")
    _make_quiz_attempt(conn, material_id, cues[0].id, status="abandoned")

    categories = frozenset({export_privacy.CATEGORY_QUIZ_ATTEMPTS})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    assert len(bundle.materials[0]["quiz_attempts"]) == 1


def test_quiz_questions_and_answers_only_appear_when_that_category_is_selected(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    _make_quiz_attempt(conn, material_id, cues[0].id, status="completed")

    categories = frozenset({export_privacy.CATEGORY_QUIZ_ATTEMPTS})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    assert "questions" not in bundle.materials[0]["quiz_attempts"][0]


# ---- retained recording metadata ----


def test_retained_recording_metadata_excludes_failed_recordings(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    _make_recording(conn, material_id, cues[0].id, status="ready")
    _make_recording(conn, material_id, cues[0].id, status="failed")

    categories = frozenset({export_privacy.CATEGORY_RETAINED_RECORDING_METADATA})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    recordings = bundle.materials[0]["retained_recordings"]
    assert len(recordings) == 1
    assert recordings[0]["status"] == "ready"


def test_deleted_recordings_do_not_appear_in_export(conn, all_time_range):
    material_id, cues = _make_material_with_cues(conn)
    recording_id = _make_recording(conn, material_id, cues[0].id, status="ready")
    recording_repository.delete_recording(conn, recording_id)

    categories = frozenset({export_privacy.CATEGORY_RETAINED_RECORDING_METADATA})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    assert bundle.materials[0]["retained_recordings"] == []


# ---- stage responses / session-state serialization ----


def test_session_status_states_remain_distinct_in_export(conn, all_time_range):
    material_a, _ = _make_material_with_cues(conn, title="A")
    _make_session(conn, material_a, status="completed")
    material_b, _ = _make_material_with_cues(conn, title="B")
    _make_session(conn, material_b, status="abandoned")
    material_c, _ = _make_material_with_cues(conn, title="C")
    _make_session(conn, material_c, status="active")

    categories = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    statuses = {m["title"]: m["sessions"][0]["status"] for m in bundle.materials}
    assert statuses == {"A": "completed", "B": "abandoned", "C": "active"}


def test_stage_responses_category_controls_raw_text_presence(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="active")
    session_repository.upsert_stage_response(conn, session_id, "global_comprehension", "who_is_speaking", "A teacher\nwith detail")

    without_responses = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, without_responses, _ALL_PRIVACY_FIELDS)
    assert "stage_responses" not in bundle.materials[0]["sessions"][0]

    with_responses = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES, export_privacy.CATEGORY_STAGE_RESPONSES})
    bundle2 = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, with_responses, _ALL_PRIVACY_FIELDS)
    responses = bundle2.materials[0]["sessions"][0]["stage_responses"]
    assert responses[0]["response_text"] == "A teacher\nwith detail"


def test_stage_ordering_is_preserved(conn, all_time_range):
    material_id, _ = _make_material_with_cues(conn)
    session_id = _make_session(conn, material_id, status="active")
    session_repository.set_stage_status(conn, session_id, "shadowing", "skipped")
    session_repository.set_stage_status(conn, session_id, "global_comprehension", "completed")

    categories = frozenset({export_privacy.CATEGORY_SESSION_SUMMARIES})
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, categories, _ALL_PRIVACY_FIELDS)
    stage_keys = [s["stage_key"] for s in bundle.materials[0]["sessions"][0]["stages"]]
    assert stage_keys == ["global_comprehension", "keyword_capture", "transcript_diagnosis", "shadowing", "final_summary"]


# ---- export version / empty state ----


def test_export_version_is_stamped(conn, all_time_range):
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS)
    assert bundle.export_version == 1


def test_material_with_no_evidence_still_exports_cleanly(conn, all_time_range):
    _make_material_with_cues(conn)
    bundle = svc.build_export(conn, ExportScope(kind=SCOPE_ALL), all_time_range, _ALL_CATEGORIES, _ALL_PRIVACY_FIELDS)
    material = bundle.materials[0]
    assert material["sessions"] == []
    assert material["quiz_attempts"] == []
    assert material["session_diagnosis_history"] == []
    assert material["retained_recordings"] == []

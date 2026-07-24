from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from listentrace.application.dto.export import (
    SCOPE_ALL,
    SCOPE_ONE_MATERIAL,
    ExportBundle,
    ExportScope,
)
from listentrace.domain.services import export_privacy as privacy
from listentrace.domain.services.date_range import SQLITE_UTC_TIMESTAMP_FORMAT, ResolvedDateRange
from listentrace.infrastructure.db import export_repository as export_repo
from listentrace.infrastructure.db import history_repository as history_repo
from listentrace.infrastructure.db import learning_repository, quiz_repository, session_repository

"""Application service for Milestone 9 (Structured Export and External
Evaluation).

`build_export` is the single place that turns existing, authoritative
evidence (read through `export_repository.py` plus the same repositories
Learning History already uses — never raw SQL in this module) into one
`ExportBundle` — a plain, JSON-serializable evidence tree. `export_
formatters.py` renders that one bundle to Markdown and to JSON; neither
formatter re-queries the database, so preview and saved output can never
show different data for the same export (see `ARCHITECTURE.md`).

No schema migration, no new authoritative table, no durable persistence of
generated exports — this module only reads.
"""

EXPORT_VERSION = 1

TIMESTAMP_CONVENTION = (
    "All timestamps in this export are exactly as recorded by ListenTrace, in "
    "UTC, formatted as 'YYYY-MM-DD HH:MM:SS'. They are not converted to any "
    "particular local timezone, and they are not a measure of study duration."
)


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime(SQLITE_UTC_TIMESTAMP_FORMAT)


def _describe_scope(scope: ExportScope, material_rows: list[sqlite3.Row]) -> str:
    if scope.kind == SCOPE_ALL:
        return "All Materials"
    if scope.kind == SCOPE_ONE_MATERIAL:
        title = material_rows[0]["title"] if material_rows else f"Material {scope.material_ids[0]}"
        return f"One Material — {title}"
    titles = ", ".join(row["title"] for row in material_rows)
    return f"Selected Materials ({len(material_rows)}) — {titles}"


def _describe_date_range(resolved_range: ResolvedDateRange) -> str:
    if not resolved_range.is_bounded:
        return "All Time"
    return f"{resolved_range.preset} ({resolved_range.local_start_date} to {resolved_range.local_end_date})"


def build_export(
    conn: sqlite3.Connection,
    scope: ExportScope,
    resolved_range: ResolvedDateRange,
    categories: frozenset[str] | None = None,
    privacy_fields: frozenset[str] | None = None,
) -> ExportBundle:
    categories = categories if categories is not None else privacy.DEFAULT_CATEGORIES
    privacy_fields = privacy_fields if privacy_fields is not None else privacy.DEFAULT_PRIVACY_FIELDS

    if scope.kind == SCOPE_ALL:
        material_rows = export_repo.list_materials_for_export(conn)
    else:
        material_rows = export_repo.list_materials_for_export(conn, list(scope.material_ids))

    materials = [
        _build_material_export(conn, row, resolved_range, categories, privacy_fields) for row in material_rows
    ]

    return ExportBundle(
        export_version=EXPORT_VERSION,
        generated_at=_now_utc_str(),
        timestamp_convention=TIMESTAMP_CONVENTION,
        scope_description=_describe_scope(scope, material_rows),
        date_range_description=_describe_date_range(resolved_range),
        categories=[c for c in privacy.EVIDENCE_CATEGORIES if c in categories],
        privacy_fields=[f for f in privacy.PRIVACY_FIELDS if f in privacy_fields],
        materials=materials,
    )


def _build_material_export(
    conn: sqlite3.Connection,
    material_row: sqlite3.Row,
    resolved_range: ResolvedDateRange,
    categories: frozenset[str],
    privacy_fields: frozenset[str],
) -> dict:
    material_id = material_row["id"]
    block: dict = {"material_id": material_id, "title": material_row["title"]}

    if privacy.CATEGORY_MATERIAL_METADATA in categories:
        block["material_metadata"] = _build_material_metadata(conn, material_row, privacy_fields)

    if privacy.CATEGORY_SESSION_SUMMARIES in categories or privacy.CATEGORY_STAGE_RESPONSES in categories:
        block["sessions"] = _build_sessions(conn, material_id, resolved_range, categories)

    if privacy.CATEGORY_SESSION_DIAGNOSIS_HISTORY in categories:
        block["session_diagnosis_history"] = _build_diagnosis_history(conn, material_id, resolved_range, privacy_fields)

    if privacy.CATEGORY_CURRENT_ANNOTATIONS in categories:
        block["current_material_annotations"] = _build_current_annotations(conn, material_id, privacy_fields)

    if privacy.CATEGORY_QUIZ_ATTEMPTS in categories or privacy.CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS in categories:
        # `quiz_questions_and_answers` has no meaning without its parent
        # attempt — selecting it alone still builds the attempt container
        # (summary fields included), matching the `sessions` block's own
        # `SESSION_SUMMARIES or STAGE_RESPONSES` precedent above. Selecting
        # only `quiz_attempts` still yields summary-only output (no
        # `questions` key), since `include_qa` below is independent of this.
        block["quiz_attempts"] = _build_quiz_attempts(conn, material_id, resolved_range, categories, privacy_fields)

    if privacy.CATEGORY_SHADOWING_EVIDENCE in categories:
        block["shadowing_evidence"] = _build_shadowing(conn, material_id, resolved_range, privacy_fields)

    if privacy.CATEGORY_RETAINED_RECORDING_METADATA in categories:
        block["retained_recordings"] = _build_recordings(conn, material_id, resolved_range)

    if privacy.CATEGORY_LEARNER_NOTES in categories:
        block["cue_notes"] = _build_cue_notes(conn, material_id, privacy_fields)

    if privacy.CATEGORY_VOCABULARY in categories:
        block["vocabulary_and_saved_chunks"] = _build_saved_items(conn, material_id, privacy_fields)

    return block


def _build_material_metadata(conn: sqlite3.Connection, material_row: sqlite3.Row, privacy_fields: frozenset[str]) -> dict:
    result: dict = {
        "language": material_row["language"],
        "media_kind": material_row["media_kind"],
        "duration_ms": material_row["duration_ms"],
        "created_at": material_row["created_at"],
        "status": material_row["status"],
        "subtitle_capability": export_repo.get_subtitle_capability_for_material(conn, material_row["id"]),
    }
    # `source_label` is always present when material metadata is included —
    # redacted in place when the field is excluded, never omitted, per the
    # same "redact, don't drop" contract every other privacy field follows.
    if privacy.PRIVACY_SOURCE_LABELS not in privacy_fields:
        result["source_label"] = privacy.REDACTED_PLACEHOLDER
    elif privacy.PRIVACY_LOCAL_FILE_NAMES in privacy_fields:
        result["source_label"] = privacy.sanitize_filename_for_label(material_row["media_path"])
    else:
        result["source_label"] = f"{material_row['media_kind'] or 'media'} file"
    return result


def _build_sessions(
    conn: sqlite3.Connection, material_id: int, resolved_range: ResolvedDateRange, categories: frozenset[str]
) -> list[dict]:
    rows = history_repo.list_sessions(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    include_summaries = privacy.CATEGORY_SESSION_SUMMARIES in categories
    include_responses = privacy.CATEGORY_STAGE_RESPONSES in categories

    result: list[dict] = []
    for row in rows:
        session_id = row["id"]
        entry: dict = {"session_id": session_id, "status": row["status"], "mode": row["mode"]}
        if include_summaries:
            entry["current_stage"] = row["current_stage"]
            entry["started_at"] = row["started_at"]
            entry["completed_at"] = row["completed_at"]
            entry["abandoned_at"] = row["abandoned_at"]
            entry["last_resumed_at"] = row["last_resumed_at"]
            entry["transcript_revealed_at"] = row["transcript_revealed_at"]
            entry["stages"] = [
                {"stage_key": p.stage_key, "status": p.status, "skip_note": p.skip_note}
                for p in session_repository.list_stage_progress(conn, session_id)
            ]
        if include_responses:
            entry["stage_responses"] = [
                {"stage_key": r.stage_key, "prompt_key": r.prompt_key, "response_text": r.response_text}
                for r in session_repository.list_stage_responses(conn, session_id)
            ]
            entry["keyword_captures"] = [
                {"capture_type": c.capture_type, "text": c.text, "position": c.position}
                for c in session_repository.list_keyword_captures(conn, session_id)
            ]
        result.append(entry)
    return result


def _build_diagnosis_history(
    conn: sqlite3.Connection, material_id: int, resolved_range: ResolvedDateRange, privacy_fields: frozenset[str]
) -> list[dict]:
    rows = history_repo.list_session_diagnosis_evidence(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    return [
        {
            "session_id": row["practice_session_id"],
            "subtitle_cue_id": row["subtitle_cue_id"],
            "label_key": row["label_key"],
            "transcript_excerpt": privacy.redact_unless_included(
                row["selected_text"], privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
            ),
            "heard_as": privacy.redact_unless_included(row["heard_as"], privacy.PRIVACY_MISHEARING_TEXT, privacy_fields),
            "note": privacy.redact_unless_included(row["note"], privacy.PRIVACY_LEARNER_NOTES, privacy_fields),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _build_current_annotations(conn: sqlite3.Connection, material_id: int, privacy_fields: frozenset[str]) -> list[dict]:
    annotations = learning_repository.list_annotations_for_material(conn, material_id)
    return [
        {
            "subtitle_cue_id": a.subtitle_cue_id,
            "label_key": a.label_key,
            "transcript_excerpt": privacy.redact_unless_included(
                a.selected_text, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
            ),
            "heard_as": privacy.redact_unless_included(a.heard_as, privacy.PRIVACY_MISHEARING_TEXT, privacy_fields),
            "note": privacy.redact_unless_included(a.note, privacy.PRIVACY_LEARNER_NOTES, privacy_fields),
        }
        for a in annotations
    ]


def _build_quiz_attempts(
    conn: sqlite3.Connection,
    material_id: int,
    resolved_range: ResolvedDateRange,
    categories: frozenset[str],
    privacy_fields: frozenset[str],
) -> list[dict]:
    rows = history_repo.list_quiz_attempts(
        conn, material_id, resolved_range.start_utc, resolved_range.end_utc, statuses=["completed"]
    )
    breakdowns = history_repo.list_question_type_breakdown_for_attempts(conn, [row["id"] for row in rows])
    include_qa = privacy.CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS in categories

    result: list[dict] = []
    for row in rows:
        accuracy = row["correct_count"] / row["actual_count"] if row["actual_count"] else None
        entry = {
            "attempt_id": row["id"],
            "quiz_mode": row["quiz_mode"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "correct_count": row["correct_count"],
            "actual_count": row["actual_count"],
            "accuracy": accuracy,
            "question_type_breakdown": [
                {
                    "question_type": b["question_type"],
                    "question_count": b["question_count"],
                    "correct_count": b["correct_count"],
                }
                for b in breakdowns.get(row["id"], [])
            ],
        }
        if include_qa:
            entry["questions"] = _build_quiz_questions(conn, row["id"], privacy_fields)
        result.append(entry)
    return result


# Which prompt/correct_answer JSON keys hold transcript-derived text, per
# question type — audited against every builder in `quiz_service.py`
# (`_try_build_dictation`, `_try_build_keyword_recognition`,
# `_try_build_audio_transcript_choice`, `_try_build_review_question`).
# Structural/scoring fields not listed here (mode, blank_start/blank_end,
# label_key, correct_choice_index, choices=["No","Yes"], expected) are never
# redacted — only the actual transcript-quoting text values are.
_TRANSCRIPT_TEXT_KEYS_BY_QUESTION_TYPE: dict[str, dict[str, tuple[str, ...]]] = {
    "dictation": {"prompt": ("masked_text",), "correct_answer": ("answer_text", "normalized_answer_text")},
    "keyword_recognition": {"prompt": ("target_text",), "correct_answer": ("target_text",)},
    "audio_transcript_choice": {"prompt": ("choices",), "correct_answer": ("correct_text",)},
    "review_missed": {"prompt": ("masked_text",), "correct_answer": ("answer_text", "normalized_answer_text")},
}

# The one payload key, on exactly one question type, that carries historical
# mishearing text (Milestone 4/5's `heard_as`) rather than plain transcript
# text — gated by `PRIVACY_MISHEARING_TEXT`, independently of
# `PRIVACY_TRANSCRIPT_EXCERPTS`.
_MISHEARING_TEXT_KEYS_BY_QUESTION_TYPE: dict[str, tuple[str, ...]] = {
    "review_missed": ("heard_as",),
}


def _redact_payload_field(payload: dict, key: str, field: str, privacy_fields: frozenset[str]) -> None:
    """Redacts `payload[key]` in place, unless it's a list (the one payload
    shape that holds transcript text as a list of choices — `audio_
    transcript_choice`'s `choices`), in which case every element is redacted
    individually so the list itself (and its length) is preserved."""
    if key not in payload or payload[key] is None:
        return
    value = payload[key]
    if isinstance(value, list):
        payload[key] = [privacy.redact_unless_included(v, field, privacy_fields) for v in value]
    else:
        payload[key] = privacy.redact_unless_included(value, field, privacy_fields)


def _redact_quiz_question_payloads(
    question_type: str, prompt: dict, correct_answer: dict, privacy_fields: frozenset[str]
) -> tuple[dict, dict]:
    """Applies `transcript_excerpts`/`mishearing_text` privacy control to
    every transcript-derived or mishearing-text value in a question's
    prompt/correct-answer payloads, for every supported question type —
    never just `source_cue_text`. Position, question type, scoring-relevant
    structure (mode, blank offsets, choice index, label key) and anything
    not listed as transcript-derived/mishearing text is left untouched."""
    prompt = dict(prompt)
    correct_answer = dict(correct_answer)

    transcript_keys = _TRANSCRIPT_TEXT_KEYS_BY_QUESTION_TYPE.get(question_type, {"prompt": (), "correct_answer": ()})
    for key in transcript_keys["prompt"]:
        _redact_payload_field(prompt, key, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields)
    for key in transcript_keys["correct_answer"]:
        _redact_payload_field(correct_answer, key, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields)

    for key in _MISHEARING_TEXT_KEYS_BY_QUESTION_TYPE.get(question_type, ()):
        _redact_payload_field(prompt, key, privacy.PRIVACY_MISHEARING_TEXT, privacy_fields)

    return prompt, correct_answer


def _build_quiz_questions(conn: sqlite3.Connection, attempt_id: int, privacy_fields: frozenset[str]) -> list[dict]:
    """Reads the immutable per-attempt snapshot only (`quiz_question`/
    `quiz_answer`) — never regenerates questions from live cue/annotation
    data, so a later edit to the material cannot change what an exported
    historical attempt shows (mirrors Milestone 6's own snapshot guarantee).
    The record itself is always retained; only its sensitive text values are
    ever redacted (see `_redact_quiz_question_payloads`)."""
    questions = quiz_repository.list_quiz_questions(conn, attempt_id)
    answers = quiz_repository.list_quiz_answers_for_attempt(conn, attempt_id)
    result = []
    for question in questions:
        answer = answers.get(question.id)
        prompt, correct_answer = _redact_quiz_question_payloads(
            question.question_type, json.loads(question.prompt_payload), json.loads(question.correct_answer_payload), privacy_fields
        )
        result.append(
            {
                "position": question.position,
                "question_type": question.question_type,
                "source_cue_text": privacy.redact_unless_included(
                    question.source_cue_text, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
                ),
                "prompt": prompt,
                "correct_answer": correct_answer,
                "learner_answer": {
                    "raw_answer_text": privacy.redact_unless_included(
                        answer.raw_answer_text, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
                    )
                    if answer
                    else None,
                    "selected_choice_index": answer.selected_choice_index if answer else None,
                    "is_correct": answer.is_correct if answer else None,
                },
            }
        )
    return result


def _build_shadowing(
    conn: sqlite3.Connection, material_id: int, resolved_range: ResolvedDateRange, privacy_fields: frozenset[str]
) -> list[dict]:
    rows = history_repo.list_shadowing_evidence(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    return [
        {
            "subtitle_cue_id": row["subtitle_cue_id"],
            "transcript_excerpt": privacy.redact_unless_included(
                row["cue_text"], privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
            ),
            "practice_count": row["practice_count"],
            "last_practiced_at": row["last_practiced_at"],
            "note": privacy.redact_unless_included(row["note"], privacy.PRIVACY_LEARNER_NOTES, privacy_fields),
        }
        for row in rows
    ]


def _build_recordings(conn: sqlite3.Connection, material_id: int, resolved_range: ResolvedDateRange) -> list[dict]:
    """Retained (`status = 'ready'`) recordings only, metadata fields only —
    never `relative_file_path` (or any path), never the audio itself."""
    rows = history_repo.list_ready_recordings(conn, material_id, resolved_range.start_utc, resolved_range.end_utc)
    return [
        {
            "recording_id": row["id"],
            "subtitle_cue_id": row["subtitle_cue_id"],
            "practice_session_id": row["practice_session_id"],
            "duration_ms": row["duration_ms"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _build_cue_notes(conn: sqlite3.Connection, material_id: int, privacy_fields: frozenset[str]) -> list[dict]:
    rows = export_repo.list_cue_notes_for_material(conn, material_id)
    return [
        {
            "subtitle_cue_id": row["subtitle_cue_id"],
            "transcript_excerpt": privacy.redact_unless_included(
                row["cue_text"], privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
            ),
            "note": privacy.redact_unless_included(row["note_text"], privacy.PRIVACY_LEARNER_NOTES, privacy_fields),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def _build_saved_items(conn: sqlite3.Connection, material_id: int, privacy_fields: frozenset[str]) -> list[dict]:
    items = learning_repository.list_saved_items_for_material(conn, material_id)
    return [
        {
            "subtitle_cue_id": item.subtitle_cue_id,
            "item_type": item.item_type,
            "text": item.text,
            "meaning": privacy.redact_unless_included(item.meaning, privacy.PRIVACY_VOCABULARY_MEANINGS, privacy_fields),
            "note": privacy.redact_unless_included(item.note, privacy.PRIVACY_LEARNER_NOTES, privacy_fields),
            "context_excerpt": privacy.redact_unless_included(
                item.context_text, privacy.PRIVACY_TRANSCRIPT_EXCERPTS, privacy_fields
            ),
        }
        for item in items
    ]

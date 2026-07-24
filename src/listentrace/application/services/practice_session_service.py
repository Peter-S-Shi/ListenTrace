from __future__ import annotations

import sqlite3

from listentrace.application.dto.practice_session_state import PracticeSessionState
from listentrace.application.errors import (
    ActiveSessionExistsError,
    CueNotFoundError,
    DiagnosisNotFoundError,
    KeywordCaptureNotFoundError,
    SessionNotFoundError,
    SessionValidationError,
)
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.keyword_capture_type import KeywordCaptureType
from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.stage_key import STAGE_ORDER, TRANSCRIPT_LOCKED_STAGES, StageKey
from listentrace.domain.enums.stage_outcome import StageOutcome
from listentrace.domain.enums.stage_status import StageStatus
from listentrace.domain.models.practice_session import PracticeSession
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.services import session_rules as rules
from listentrace.domain.services.text_range import TextRangeError, validate_selection
from listentrace.infrastructure.db import session_repository as repo
from listentrace.infrastructure.db.learning_repository import find_annotation, insert_annotations
from listentrace.infrastructure.db.repository import (
    get_cue_by_id,
    get_cues_for_track,
    get_subtitle_track_for_material,
)

_VALID_LABELS = {label.value for label in AnnotationLabel}
_VALID_CAPTURE_TYPES = {capture_type.value for capture_type in KeywordCaptureType}


# ---- internal guards ----


def _require_session(conn: sqlite3.Connection, session_id: int) -> PracticeSession:
    session = repo.get_practice_session(conn, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def _require_active_session(conn: sqlite3.Connection, session_id: int) -> PracticeSession:
    session = _require_session(conn, session_id)
    if session.status != SessionStatus.ACTIVE.value:
        raise SessionValidationError(
            "session_not_active", "This session is read-only (completed or abandoned)."
        )
    return session


def _require_stage_key(stage_key: str) -> None:
    if stage_key not in STAGE_ORDER:
        raise SessionValidationError("invalid_stage", f"Unknown stage: {stage_key!r}")


def _require_stage_unlocked(session: PracticeSession, stage_key: str) -> None:
    if stage_key in TRANSCRIPT_LOCKED_STAGES and session.transcript_revealed_at is not None:
        raise SessionValidationError(
            "stage_locked", "This stage became read-only after the transcript was revealed."
        )


def _responses_dict(conn: sqlite3.Connection, session_id: int, stage_key: str) -> dict[str, str]:
    return {r.prompt_key: r.response_text for r in repo.list_stage_responses(conn, session_id, stage_key)}


# ---- lifecycle ----


def find_active_session(conn: sqlite3.Connection, material_id: int) -> PracticeSession | None:
    return repo.find_active_session_for_material(conn, material_id)


def list_sessions_for_material(conn: sqlite3.Connection, material_id: int) -> list[PracticeSession]:
    return repo.list_sessions_for_material(conn, material_id)


def get_session(conn: sqlite3.Connection, session_id: int) -> PracticeSession | None:
    return repo.get_practice_session(conn, session_id)


def start_session(conn: sqlite3.Connection, material_id: int) -> PracticeSession:
    existing = repo.find_active_session_for_material(conn, material_id)
    if existing is not None and existing.id is not None:
        raise ActiveSessionExistsError(material_id, existing.id)
    session_id = repo.create_practice_session(conn, material_id)
    session = repo.get_practice_session(conn, session_id)
    assert session is not None
    return session


def resume_session(conn: sqlite3.Connection, session_id: int) -> PracticeSessionState:
    session = _require_session(conn, session_id)
    if session.status != SessionStatus.ACTIVE.value:
        raise SessionValidationError("session_not_active", "Only an active session can be resumed.")
    repo.touch_session_resumed(conn, session_id)
    return load_session_state(conn, session_id)


def abandon_session(conn: sqlite3.Connection, session_id: int) -> None:
    session = _require_session(conn, session_id)
    if not rules.is_valid_session_transition(session.status, SessionStatus.ABANDONED.value):
        raise SessionValidationError(
            "invalid_transition", f"Cannot abandon a session with status {session.status!r}."
        )
    repo.set_session_status(conn, session_id, SessionStatus.ABANDONED.value)


def complete_session(conn: sqlite3.Connection, session_id: int) -> None:
    session = _require_active_session(conn, session_id)
    if not rules.is_valid_session_transition(session.status, SessionStatus.COMPLETED.value):
        raise SessionValidationError(
            "invalid_transition", f"Cannot complete a session with status {session.status!r}."
        )
    statuses = {p.stage_key: p.status for p in repo.list_stage_progress(conn, session_id)}
    if not rules.session_can_complete(statuses):
        raise SessionValidationError(
            "session_not_ready", "Every stage must be completed or skipped before finishing the session."
        )
    repo.set_session_status(conn, session_id, SessionStatus.COMPLETED.value)


def load_session_state(conn: sqlite3.Connection, session_id: int) -> PracticeSessionState:
    session = _require_session(conn, session_id)
    stage_progress = {p.stage_key: p for p in repo.list_stage_progress(conn, session_id)}

    stage_responses: dict[str, dict[str, str]] = {key: {} for key in STAGE_ORDER}
    for response in repo.list_stage_responses(conn, session_id):
        stage_responses.setdefault(response.stage_key, {})[response.prompt_key] = response.response_text

    return PracticeSessionState(
        session=session,
        stage_progress=stage_progress,
        stage_responses=stage_responses,
        keyword_captures=repo.list_keyword_captures(conn, session_id),
        session_diagnosis=repo.list_session_diagnosis(conn, session_id),
        shadowing_progress=repo.list_shadowing_progress(conn, session_id),
    )


# ---- stage navigation ----


def _ensure_shadowing_initialized(conn: sqlite3.Connection, session_id: int, material_id: int) -> None:
    track = get_subtitle_track_for_material(conn, material_id)
    if track is None or track.id is None:
        return
    cue_ids = [cue.id for cue in get_cues_for_track(conn, track.id) if cue.id is not None]
    repo.ensure_shadowing_rows(conn, session_id, cue_ids)


def _reveal_transcript_and_lock_prior_stages(
    conn: sqlite3.Connection, session: PracticeSession, session_id: int
) -> None:
    if session.transcript_revealed_at is not None:
        return

    for stage_key in (StageKey.GLOBAL_COMPREHENSION.value, StageKey.KEYWORD_CAPTURE.value):
        progress = repo.get_stage_progress(conn, session_id, stage_key)
        if progress is None or progress.status in (StageStatus.COMPLETED.value, StageStatus.SKIPPED.value):
            continue

        if stage_key == StageKey.GLOBAL_COMPREHENSION.value:
            can_complete = rules.stage1_can_complete(_responses_dict(conn, session_id, stage_key))
        else:
            can_complete = rules.stage2_can_complete(len(repo.list_keyword_captures(conn, session_id)))

        if can_complete:
            repo.set_stage_status(conn, session_id, stage_key, StageStatus.COMPLETED.value)
        else:
            repo.set_stage_status(
                conn,
                session_id,
                stage_key,
                StageStatus.SKIPPED.value,
                skip_note="Auto-skipped: no evidence entered before transcript reveal.",
            )

    repo.set_transcript_revealed(conn, session_id)


def enter_stage(conn: sqlite3.Connection, session_id: int, stage_key: str) -> None:
    """Navigate to `stage_key`, persisting `current_stage` regardless of whether this
    is forward progress or Back navigation. Only transitions stage status from
    `not_started` to `in_progress` (never on Back into an already-resolved stage —
    "Back navigation is not the same as state rollback")."""
    session = _require_active_session(conn, session_id)
    _require_stage_key(stage_key)

    repo.set_current_stage(conn, session_id, stage_key)

    progress = repo.get_stage_progress(conn, session_id, stage_key)
    if progress is not None and progress.status == StageStatus.NOT_STARTED.value:
        repo.set_stage_status(conn, session_id, stage_key, StageStatus.IN_PROGRESS.value)

    if stage_key == StageKey.TRANSCRIPT_DIAGNOSIS.value:
        _reveal_transcript_and_lock_prior_stages(conn, session, session_id)
    elif stage_key == StageKey.SHADOWING.value:
        _ensure_shadowing_initialized(conn, session_id, session.material_id)


def skip_stage(conn: sqlite3.Connection, session_id: int, stage_key: str, skip_note: str | None = None) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_key(stage_key)
    _require_stage_unlocked(session, stage_key)

    progress = repo.get_stage_progress(conn, session_id, stage_key)
    if progress is None:
        raise SessionValidationError("invalid_stage", f"Unknown stage: {stage_key!r}")
    if not rules.is_valid_stage_transition(progress.status, StageStatus.SKIPPED.value):
        raise SessionValidationError(
            "invalid_stage_transition", f"Cannot skip a stage with status {progress.status!r}."
        )

    note_value = skip_note.strip() if skip_note and skip_note.strip() else None
    repo.set_stage_status(conn, session_id, stage_key, StageStatus.SKIPPED.value, skip_note=note_value)


def complete_stage(conn: sqlite3.Connection, session_id: int, stage_key: str) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_key(stage_key)
    _require_stage_unlocked(session, stage_key)

    progress = repo.get_stage_progress(conn, session_id, stage_key)
    if progress is None:
        raise SessionValidationError("invalid_stage", f"Unknown stage: {stage_key!r}")
    if not rules.is_valid_stage_transition(progress.status, StageStatus.COMPLETED.value):
        raise SessionValidationError(
            "invalid_stage_transition", f"Cannot complete a stage with status {progress.status!r}."
        )

    if stage_key == StageKey.GLOBAL_COMPREHENSION.value:
        eligible = rules.stage1_can_complete(_responses_dict(conn, session_id, stage_key))
    elif stage_key == StageKey.KEYWORD_CAPTURE.value:
        eligible = rules.stage2_can_complete(len(repo.list_keyword_captures(conn, session_id)))
    elif stage_key == StageKey.TRANSCRIPT_DIAGNOSIS.value:
        eligible = rules.stage3_can_complete(repo.count_session_diagnosis(conn, session_id), progress.outcome_key)
    elif stage_key == StageKey.SHADOWING.value:
        eligible = rules.stage4_can_complete(repo.count_unresolved_shadowing(conn, session_id))
    else:
        eligible = rules.stage5_can_complete(_responses_dict(conn, session_id, stage_key).get("summary", ""))

    if not eligible:
        raise SessionValidationError(
            "cannot_complete_stage",
            "This stage has no evidence yet. Add evidence first, or use Skip Stage.",
        )
    repo.set_stage_status(conn, session_id, stage_key, StageStatus.COMPLETED.value)


def save_stage_response(
    conn: sqlite3.Connection, session_id: int, stage_key: str, prompt_key: str, response_text: str
) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_key(stage_key)
    _require_stage_unlocked(session, stage_key)
    repo.upsert_stage_response(conn, session_id, stage_key, prompt_key, response_text or "")


def mark_stage3_no_difficulty(conn: sqlite3.Connection, session_id: int) -> None:
    _require_active_session(conn, session_id)
    repo.set_stage_outcome(
        conn, session_id, StageKey.TRANSCRIPT_DIAGNOSIS.value, StageOutcome.NO_NOTABLE_DIFFICULTY.value
    )


# ---- keyword captures (Stage 2) ----


def add_keyword_capture(conn: sqlite3.Connection, session_id: int, capture_type: str, text: str) -> int:
    session = _require_active_session(conn, session_id)
    _require_stage_unlocked(session, StageKey.KEYWORD_CAPTURE.value)
    if capture_type not in _VALID_CAPTURE_TYPES:
        raise SessionValidationError("invalid_capture_type", f"Unknown capture type: {capture_type!r}")
    text_value = text.strip() if text else ""
    if not text_value:
        raise SessionValidationError("empty_capture_text", "Capture text cannot be empty.")
    position = repo.next_keyword_capture_position(conn, session_id)
    return repo.insert_keyword_capture(conn, session_id, capture_type, text_value, position)


def update_keyword_capture(
    conn: sqlite3.Connection, session_id: int, capture_id: int, capture_type: str, text: str
) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_unlocked(session, StageKey.KEYWORD_CAPTURE.value)
    existing = repo.get_keyword_capture(conn, capture_id)
    if existing is None or existing.practice_session_id != session_id:
        raise KeywordCaptureNotFoundError(capture_id)
    if capture_type not in _VALID_CAPTURE_TYPES:
        raise SessionValidationError("invalid_capture_type", f"Unknown capture type: {capture_type!r}")
    text_value = text.strip() if text else ""
    if not text_value:
        raise SessionValidationError("empty_capture_text", "Capture text cannot be empty.")
    repo.update_keyword_capture(conn, capture_id, capture_type, text_value)


def delete_keyword_capture(conn: sqlite3.Connection, session_id: int, capture_id: int) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_unlocked(session, StageKey.KEYWORD_CAPTURE.value)
    existing = repo.get_keyword_capture(conn, capture_id)
    if existing is None or existing.practice_session_id != session_id:
        raise KeywordCaptureNotFoundError(capture_id)
    repo.delete_keyword_capture(conn, capture_id)


def reorder_keyword_captures(conn: sqlite3.Connection, session_id: int, ordered_ids: list[int]) -> None:
    session = _require_active_session(conn, session_id)
    _require_stage_unlocked(session, StageKey.KEYWORD_CAPTURE.value)
    repo.reorder_keyword_captures(conn, session_id, ordered_ids)


def list_keyword_captures(conn: sqlite3.Connection, session_id: int):
    return repo.list_keyword_captures(conn, session_id)


# ---- session diagnosis (Stage 3) ----


def record_session_diagnosis(
    conn: sqlite3.Connection,
    session_id: int,
    subtitle_cue_id: int,
    selection_start: int,
    selection_end: int,
    label_key: str,
    heard_as: str | None = None,
    note: str | None = None,
) -> int:
    """Validates using the shared Milestone 4 domain/application rules, then finds or
    creates a material-level `Annotation` for this exact cue/label/range (reusing an
    existing one rather than overwriting it), and always creates an independent
    session-scoped snapshot row."""
    _require_active_session(conn, session_id)

    cue = get_cue_by_id(conn, subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(subtitle_cue_id)

    if label_key not in _VALID_LABELS:
        raise SessionValidationError("invalid_label", f"Unknown label: {label_key!r}")

    try:
        selected_text = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise SessionValidationError("invalid_range", str(exc)) from exc

    heard_as_value = heard_as.strip() if heard_as and heard_as.strip() else None
    if label_key == AnnotationLabel.MISHEARD.value and not heard_as_value:
        raise SessionValidationError(
            "misheard_requires_heard_as", "Misheard diagnosis requires heard_as text."
        )
    if label_key != AnnotationLabel.MISHEARD.value:
        heard_as_value = None

    if (
        repo.find_session_diagnosis_exact(conn, session_id, subtitle_cue_id, label_key, selection_start, selection_end)
        is not None
    ):
        raise SessionValidationError(
            "duplicate_diagnosis_in_session", "This diagnosis already exists in this session."
        )

    note_value = note.strip() if note and note.strip() else None

    existing_annotation = find_annotation(conn, subtitle_cue_id, label_key, selection_start, selection_end)
    if existing_annotation is not None and existing_annotation.id is not None:
        annotation_id: int | None = existing_annotation.id
    else:
        ids = insert_annotations(
            conn, subtitle_cue_id, [(label_key, heard_as_value)], selected_text, selection_start, selection_end, note_value
        )
        annotation_id = ids[0]

    evidence = SessionDiagnosisEvidence(
        practice_session_id=session_id,
        subtitle_cue_id=subtitle_cue_id,
        annotation_id=annotation_id,
        label_key=label_key,
        selected_text=selected_text,
        selection_start=selection_start,
        selection_end=selection_end,
        heard_as=heard_as_value,
        note=note_value,
    )
    return repo.insert_session_diagnosis(conn, evidence)


def update_session_diagnosis(
    conn: sqlite3.Connection,
    session_id: int,
    evidence_id: int,
    label_key: str,
    selection_start: int,
    selection_end: int,
    heard_as: str | None = None,
    note: str | None = None,
) -> None:
    """Updates only the session snapshot. Never mutates the linked material-level
    `Annotation`, even if one is linked via `annotation_id`."""
    _require_active_session(conn, session_id)

    existing = repo.get_session_diagnosis(conn, evidence_id)
    if existing is None or existing.practice_session_id != session_id:
        raise DiagnosisNotFoundError(evidence_id)

    cue = get_cue_by_id(conn, existing.subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(existing.subtitle_cue_id)

    if label_key not in _VALID_LABELS:
        raise SessionValidationError("invalid_label", f"Unknown label: {label_key!r}")

    try:
        selected_text = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise SessionValidationError("invalid_range", str(exc)) from exc

    heard_as_value = heard_as.strip() if heard_as and heard_as.strip() else None
    if label_key == AnnotationLabel.MISHEARD.value and not heard_as_value:
        raise SessionValidationError(
            "misheard_requires_heard_as", "Misheard diagnosis requires heard_as text."
        )
    if label_key != AnnotationLabel.MISHEARD.value:
        heard_as_value = None

    duplicate = repo.find_session_diagnosis_exact(
        conn, session_id, existing.subtitle_cue_id, label_key, selection_start, selection_end
    )
    if duplicate is not None and duplicate.id != evidence_id:
        raise SessionValidationError(
            "duplicate_diagnosis_in_session", "This diagnosis already exists in this session."
        )

    note_value = note.strip() if note and note.strip() else None
    repo.update_session_diagnosis(
        conn, evidence_id, label_key, selected_text, selection_start, selection_end, heard_as_value, note_value
    )


def delete_session_diagnosis(conn: sqlite3.Connection, session_id: int, evidence_id: int) -> None:
    """Deletes only the session snapshot; never cascades to the linked `Annotation`."""
    _require_active_session(conn, session_id)
    existing = repo.get_session_diagnosis(conn, evidence_id)
    if existing is None or existing.practice_session_id != session_id:
        raise DiagnosisNotFoundError(evidence_id)
    repo.delete_session_diagnosis(conn, evidence_id)


def list_session_diagnosis(conn: sqlite3.Connection, session_id: int):
    return repo.list_session_diagnosis(conn, session_id)


def list_session_diagnosis_for_cue(conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int):
    return repo.list_session_diagnosis_for_cue(conn, session_id, subtitle_cue_id)


# ---- shadowing (Stage 4) ----


def mark_shadowing_practiced(conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int) -> None:
    _require_active_session(conn, session_id)
    if repo.get_shadowing_progress(conn, session_id, subtitle_cue_id) is None:
        raise CueNotFoundError(subtitle_cue_id)
    repo.mark_shadowing_practiced(conn, session_id, subtitle_cue_id)


def set_shadowing_note(
    conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int, note: str | None
) -> None:
    _require_active_session(conn, session_id)
    if repo.get_shadowing_progress(conn, session_id, subtitle_cue_id) is None:
        raise CueNotFoundError(subtitle_cue_id)
    note_value = note.strip() if note and note.strip() else None
    repo.set_shadowing_note(conn, session_id, subtitle_cue_id, note_value)


def mark_shadowing_skipped(conn: sqlite3.Connection, session_id: int, subtitle_cue_id: int) -> None:
    _require_active_session(conn, session_id)
    if repo.get_shadowing_progress(conn, session_id, subtitle_cue_id) is None:
        raise CueNotFoundError(subtitle_cue_id)
    repo.mark_shadowing_skipped(conn, session_id, subtitle_cue_id)


def skip_remaining_shadowing(conn: sqlite3.Connection, session_id: int) -> None:
    _require_active_session(conn, session_id)
    repo.skip_remaining_shadowing(conn, session_id)


def list_shadowing_progress(conn: sqlite3.Connection, session_id: int):
    return repo.list_shadowing_progress(conn, session_id)

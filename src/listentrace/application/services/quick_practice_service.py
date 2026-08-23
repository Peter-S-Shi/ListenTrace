from __future__ import annotations

import sqlite3

from listentrace.application.dto.quick_practice import (
    QuickPracticeCompletionSummary,
    QuickPracticeItemState,
    QuickPracticeSessionState,
    RecommendedCueEntry,
)
from listentrace.application.errors import (
    CueNotFoundError,
    QuickPracticeDiagnosisNotFoundError,
    QuickPracticeItemNotFoundError,
    QuickPracticeNotFoundError,
    QuickPracticeValidationError,
)
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.quick_practice_source import QuickPracticeSource
from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.enums.recall_result import RecallResult
from listentrace.domain.models.quick_practice_diagnosis_evidence import QuickPracticeDiagnosisEvidence
from listentrace.domain.models.quick_practice_item import QuickPracticeItem
from listentrace.domain.models.quick_practice_session import QuickPracticeSession
from listentrace.domain.services import quick_practice_recommendation as recommendation
from listentrace.domain.services import quick_practice_rules as rules
from listentrace.domain.services.text_range import TextRangeError, validate_selection
from listentrace.infrastructure.db import quick_practice_repository as repo
from listentrace.infrastructure.db.learning_repository import (
    find_annotation,
    get_material_id_for_subtitle_cue,
    insert_annotations,
)
from listentrace.infrastructure.db.repository import get_cue_by_id, get_cues_for_track, get_subtitle_track_for_material

"""Application service for Milestone 10 (Quick Practice Mode).

Mirrors `practice_session_service.py`'s structure for the pieces Quick
Practice genuinely shares with Intensive Practice (diagnosis validation
reusing the same domain/annotation rules, a lifecycle guarded by pure
domain rules), while staying deliberately lighter: no stage machine, no
exact-step resume, and progressive per-item persistence instead of a
five-stage state.
"""

_VALID_LABELS = {label.value for label in AnnotationLabel}


# ---- internal guards ----


def _require_session(conn: sqlite3.Connection, session_id: int) -> QuickPracticeSession:
    session = repo.get_quick_practice_session(conn, session_id)
    if session is None:
        raise QuickPracticeNotFoundError(session_id)
    return session


def _require_active_session(conn: sqlite3.Connection, session_id: int) -> QuickPracticeSession:
    session = _require_session(conn, session_id)
    if session.status != QuickPracticeStatus.ACTIVE.value:
        raise QuickPracticeValidationError(
            "session_not_active", "This Quick Practice run is read-only (completed or abandoned)."
        )
    return session


def _require_item(conn: sqlite3.Connection, item_id: int) -> QuickPracticeItem:
    item = repo.get_item(conn, item_id)
    if item is None:
        raise QuickPracticeItemNotFoundError(item_id)
    return item


def _require_active_item(conn: sqlite3.Connection, item_id: int) -> tuple[QuickPracticeSession, QuickPracticeItem]:
    item = _require_item(conn, item_id)
    session = _require_active_session(conn, item.quick_practice_session_id)
    if item.completed_at is not None:
        raise QuickPracticeValidationError(
            "item_already_completed", "This cue has already been completed in this run."
        )
    return session, item


def _require_active_revealed_item(
    conn: sqlite3.Connection, item_id: int
) -> tuple[QuickPracticeSession, QuickPracticeItem]:
    session, item = _require_active_item(conn, item_id)
    if not item.transcript_revealed:
        raise QuickPracticeValidationError(
            "transcript_not_revealed", "Record a recall result before adding diagnosis evidence."
        )
    return session, item


# ---- recommendation ----


def recommend_cues(conn: sqlite3.Connection, material_id: int, count: int) -> list[RecommendedCueEntry]:
    """Deterministic, transparent cue recommendation — read-only, callable
    before a session is created (used by the start dialog's preview) and
    reused internally by `start_recommended_session`. Reads existing
    Milestone 4/5/6/7 evidence, plus one deliberate exception: explicit
    Quick Practice shadowing (`shadowed_at`), which is real shadowing
    evidence and is folded into the same shadowing-practice count. Quick
    Practice's own recall outcomes and diagnosis evidence are still never
    read here (see `quick_practice_repository.py`)."""
    track = get_subtitle_track_for_material(conn, material_id)
    if track is None or track.id is None:
        return []
    cues = get_cues_for_track(conn, track.id)
    if not cues:
        return []

    labels_by_cue = repo.list_annotation_labels_by_cue(conn, material_id)
    annotation_recency = repo.list_annotation_recency_by_cue(conn, material_id)
    diagnosis_counts = repo.list_diagnosis_counts_by_cue(conn, material_id)
    incorrect_quiz = repo.list_incorrect_quiz_evidence_by_cue(conn, material_id)
    shadowing_stats = repo.list_shadowing_stats_by_cue(conn, material_id)
    quick_practice_shadowing_stats = repo.list_quick_practice_shadowing_counts_by_cue(conn, material_id)

    stats: list[recommendation.CueEvidenceStats] = []
    for position, cue in enumerate(cues):
        if cue.id is None:
            continue
        diagnosis_count, diagnosis_recent = diagnosis_counts.get(cue.id, (0, None))
        shadow_count, shadow_recent = shadowing_stats.get(cue.id, (0, None))
        qp_shadow_count, qp_shadow_recent = quick_practice_shadowing_stats.get(cue.id, (0, None))
        recency_candidates = [
            v
            for v in (
                annotation_recency.get(cue.id),
                diagnosis_recent,
                incorrect_quiz.get(cue.id),
                shadow_recent,
                qp_shadow_recent,
            )
            if v
        ]
        stats.append(
            recommendation.CueEvidenceStats(
                subtitle_cue_id=cue.id,
                position=position,
                annotation_labels=labels_by_cue.get(cue.id, frozenset()),
                diagnosis_evidence_count=diagnosis_count,
                has_incorrect_quiz_evidence=cue.id in incorrect_quiz,
                shadowing_practice_count=shadow_count + qp_shadow_count,
                most_recent_evidence_at=max(recency_candidates) if recency_candidates else None,
            )
        )

    recommended = recommendation.recommend_cues(stats, count)
    return [RecommendedCueEntry(subtitle_cue_id=r.subtitle_cue_id, reasons=r.reasons) for r in recommended]


# ---- lifecycle: starting a run ----


def start_recommended_session(conn: sqlite3.Connection, material_id: int, count: int) -> QuickPracticeSession:
    if not rules.is_valid_recommended_count(count):
        raise QuickPracticeValidationError(
            "invalid_count", f"Recommended count must be one of {rules.ALLOWED_RECOMMENDED_COUNTS}."
        )
    entries = recommend_cues(conn, material_id, count)
    if not entries:
        raise QuickPracticeValidationError(
            "no_usable_cues", "This material has no timed cues available for Quick Practice."
        )
    ordered_cue_ids = [e.subtitle_cue_id for e in entries]
    session_id = repo.create_quick_practice_session(
        conn, material_id, QuickPracticeSource.RECOMMENDED.value, count, ordered_cue_ids
    )
    session = repo.get_quick_practice_session(conn, session_id)
    assert session is not None
    return session


def start_selected_session(
    conn: sqlite3.Connection, material_id: int, subtitle_cue_ids: list[int]
) -> QuickPracticeSession:
    """`subtitle_cue_ids` order is preserved exactly as given — covers a
    single cue, a continuous range, or an explicit material-level
    selection alike."""
    if not subtitle_cue_ids:
        raise QuickPracticeValidationError("empty_selection", "Select at least one cue to start Quick Practice.")
    if len(set(subtitle_cue_ids)) != len(subtitle_cue_ids):
        raise QuickPracticeValidationError("duplicate_cue_selection", "The same cue was selected more than once.")
    for cue_id in subtitle_cue_ids:
        if get_material_id_for_subtitle_cue(conn, cue_id) != material_id:
            raise QuickPracticeValidationError(
                "cue_material_mismatch", "One or more selected cues do not belong to this material."
            )
    session_id = repo.create_quick_practice_session(
        conn, material_id, QuickPracticeSource.SELECTED.value, len(subtitle_cue_ids), subtitle_cue_ids
    )
    session = repo.get_quick_practice_session(conn, session_id)
    assert session is not None
    return session


# ---- state ----


def get_session(conn: sqlite3.Connection, session_id: int) -> QuickPracticeSession | None:
    return repo.get_quick_practice_session(conn, session_id)


def load_session_state(conn: sqlite3.Connection, session_id: int) -> QuickPracticeSessionState:
    session = _require_session(conn, session_id)
    items = repo.list_items(conn, session_id)
    item_states = [
        QuickPracticeItemState(item=item, diagnosis=repo.list_item_diagnosis(conn, item.id))
        for item in items
        if item.id is not None
    ]
    return QuickPracticeSessionState(session=session, items=item_states)


# ---- Step 2: recall ----


def record_recall(
    conn: sqlite3.Connection, item_id: int, recall_result: str, heard_fragment: str | None = None
) -> None:
    """Records the required recall result and reveals the transcript for
    this item (idempotent) — the natural, explicit transition into Step 3.
    Revealing never creates diagnosis evidence by itself; only
    `record_item_diagnosis` does that."""
    _require_active_item(conn, item_id)
    if not rules.is_valid_recall_result(recall_result):
        raise QuickPracticeValidationError("invalid_recall_result", f"Unknown recall result: {recall_result!r}")
    fragment_value = heard_fragment.strip() if heard_fragment and heard_fragment.strip() else None
    repo.set_item_recall(conn, item_id, recall_result, fragment_value)
    repo.set_item_transcript_revealed(conn, item_id)


# ---- Step 3: diagnosis ----


def record_item_diagnosis(
    conn: sqlite3.Connection,
    item_id: int,
    selection_start: int,
    selection_end: int,
    label_key: str,
    heard_as: str | None = None,
    note: str | None = None,
) -> int:
    """Validates using the same shared Milestone 4 domain/application rules
    `practice_session_service.record_session_diagnosis` uses, then finds or
    creates a material-level `Annotation` for this exact cue/label/range
    (reusing an existing one rather than duplicating it — "do not create
    duplicate diagnosis truth"), and always creates an independent,
    explicitly Quick-Practice-scoped snapshot row."""
    session, item = _require_active_revealed_item(conn, item_id)

    cue = get_cue_by_id(conn, item.subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(item.subtitle_cue_id)

    if label_key not in _VALID_LABELS:
        raise QuickPracticeValidationError("invalid_label", f"Unknown label: {label_key!r}")

    try:
        selected_text = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise QuickPracticeValidationError("invalid_range", str(exc)) from exc

    heard_as_value = heard_as.strip() if heard_as and heard_as.strip() else None
    if label_key == AnnotationLabel.MISHEARD.value and not heard_as_value:
        raise QuickPracticeValidationError(
            "misheard_requires_heard_as", "Misheard diagnosis requires heard_as text."
        )
    if label_key != AnnotationLabel.MISHEARD.value:
        heard_as_value = None

    if repo.find_item_diagnosis_exact(conn, item_id, label_key, selection_start, selection_end) is not None:
        raise QuickPracticeValidationError(
            "duplicate_diagnosis_in_item", "This diagnosis already exists for this cue in this run."
        )

    note_value = note.strip() if note and note.strip() else None

    existing_annotation = find_annotation(conn, item.subtitle_cue_id, label_key, selection_start, selection_end)

    # The annotation (if newly created) and its Quick-Practice-scoped evidence snapshot
    # must land together: a crash between them would otherwise leave an orphaned
    # Annotation with no linked evidence row (see practice_session_service's identical
    # guarantee for the Intensive Practice equivalent).
    try:
        if existing_annotation is not None and existing_annotation.id is not None:
            annotation_id: int | None = existing_annotation.id
        else:
            ids = insert_annotations(
                conn,
                item.subtitle_cue_id,
                [(label_key, heard_as_value)],
                selected_text,
                selection_start,
                selection_end,
                note_value,
                commit=False,
            )
            annotation_id = ids[0]

        evidence = QuickPracticeDiagnosisEvidence(
            quick_practice_item_id=item_id,
            annotation_id=annotation_id,
            label_key=label_key,
            selected_text=selected_text,
            selection_start=selection_start,
            selection_end=selection_end,
            heard_as=heard_as_value,
            note=note_value,
        )
        evidence_id = repo.insert_item_diagnosis(conn, evidence, commit=False)
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return evidence_id


def delete_item_diagnosis(conn: sqlite3.Connection, item_id: int, evidence_id: int) -> None:
    """Deletes only the Quick Practice snapshot; never cascades to the
    linked `Annotation`, mirroring `practice_session_service.
    delete_session_diagnosis`."""
    _require_active_revealed_item(conn, item_id)
    existing = repo.get_item_diagnosis(conn, evidence_id)
    if existing is None or existing.quick_practice_item_id != item_id:
        raise QuickPracticeDiagnosisNotFoundError(evidence_id)
    repo.delete_item_diagnosis(conn, evidence_id)


def list_item_diagnosis(conn: sqlite3.Connection, item_id: int) -> list[QuickPracticeDiagnosisEvidence]:
    return repo.list_item_diagnosis(conn, item_id)


# ---- Step 4: replay / shadow ----


def mark_item_shadowed(conn: sqlite3.Connection, item_id: int) -> None:
    """Explicit-action-only, idempotent — mirrors Milestone 5's "Mark
    Practiced" (never inferred from playback alone). Requires Recall to
    have been recorded and the transcript revealed first: shadowing is
    Step 4 of the per-cue cycle and cannot precede Steps 2-3 (reuses the
    same revealed-item guard `record_item_diagnosis` uses)."""
    _require_active_revealed_item(conn, item_id)
    repo.set_item_shadowed(conn, item_id)


# ---- item / session completion ----


def complete_item(conn: sqlite3.Connection, item_id: int) -> None:
    session, item = _require_active_item(conn, item_id)
    if not rules.item_can_complete(item.recall_result):
        raise QuickPracticeValidationError("recall_required", "Record a recall result before completing this cue.")
    repo.set_item_completed(conn, item_id)


def complete_session(conn: sqlite3.Connection, session_id: int) -> None:
    session = _require_active_session(conn, session_id)
    items = repo.list_items(conn, session_id)
    if not rules.session_can_complete([item.completed_at is not None for item in items]):
        raise QuickPracticeValidationError(
            "session_not_ready", "Every cue must be completed before finishing this run."
        )
    if not rules.is_valid_transition(session.status, QuickPracticeStatus.COMPLETED.value):
        raise QuickPracticeValidationError(
            "invalid_transition", f"Cannot complete a run with status {session.status!r}."
        )
    repo.set_quick_practice_session_status(conn, session_id, QuickPracticeStatus.COMPLETED.value)


def close_session(conn: sqlite3.Connection, session_id: int) -> str:
    """Called when the window closes mid-run (any path other than the
    normal Finish action reaching `complete_session`). Returns the outcome:
    "completed" (nothing to do, already finished), "abandoned" (at least
    one cue was completed — evidence preserved as read-only history), or
    "discarded" (zero cues completed — the session is hard-deleted so it
    never appears as misleading history). Idempotent: calling this on an
    already-resolved session just reports its existing status."""
    session = _require_session(conn, session_id)
    if session.status != QuickPracticeStatus.ACTIVE.value:
        return session.status
    completed_count = repo.count_completed_items(conn, session_id)
    if rules.session_should_discard_on_close(completed_count):
        assert session.id is not None
        repo.delete_quick_practice_session(conn, session.id)
        return "discarded"
    repo.set_quick_practice_session_status(conn, session_id, QuickPracticeStatus.ABANDONED.value)
    return "abandoned"


def delete_history(conn: sqlite3.Connection, session_id: int) -> None:
    """M12 Round 3/4 History Ownership Contract: only a completed or
    abandoned run -- a genuine historical record -- may be deleted this way;
    an active run must be closed first. Distinct from `close_session`'s
    zero-evidence auto-discard: this is the user explicitly deleting a
    *resolved* run they no longer want in their history. Cascades (see
    migrations.py) to quick_practice_item and quick_practice_diagnosis_
    evidence -- both run-owned; independent `annotation` links are
    `ON DELETE SET NULL`. No `recording` table reference exists for Quick
    Practice at all, so retained recordings are entirely unaffected."""
    session = _require_session(conn, session_id)
    if session.status == QuickPracticeStatus.ACTIVE.value:
        raise QuickPracticeValidationError(
            "session_active", "An active Quick Practice run cannot be deleted. Close it first."
        )
    assert session.id is not None
    repo.delete_quick_practice_session(conn, session.id)


def recover_interrupted_sessions(conn: sqlite3.Connection) -> int:
    """Run once at application startup (mirrors `recording_service.
    recover_interrupted_recordings`): a session left `active` was left that
    way by a prior process that never cleanly closed (crash or forced
    close) — a fresh process cannot own an in-progress run. Applies the
    same close-time rule to each one found."""
    stale = repo.list_active_quick_practice_sessions(conn)
    for session in stale:
        assert session.id is not None
        close_session(conn, session.id)
    return len(stale)


# ---- completion summary ----


def build_completion_summary(conn: sqlite3.Connection, session_id: int) -> QuickPracticeCompletionSummary:
    _require_session(conn, session_id)
    items = repo.list_items(conn, session_id)
    completed_items = [item for item in items if item.completed_at is not None]

    understood = sum(1 for i in completed_items if i.recall_result == RecallResult.UNDERSTOOD.value)
    partly = sum(1 for i in completed_items if i.recall_result == RecallResult.PARTLY_UNDERSTOOD.value)
    missed = sum(1 for i in completed_items if i.recall_result == RecallResult.MISSED.value)
    shadowing_actions = sum(1 for i in completed_items if i.shadowed_at is not None)

    diagnosis_rows = repo.list_diagnosis_for_session(conn, session_id)
    item_by_id = {item.id: item for item in items}
    diagnosis_cue_ids = {
        item_by_id[d.quick_practice_item_id].subtitle_cue_id
        for d in diagnosis_rows
        if d.quick_practice_item_id in item_by_id
    }
    missed_cue_ids = {i.subtitle_cue_id for i in completed_items if i.recall_result == RecallResult.MISSED.value}
    revisit_ids = missed_cue_ids | diagnosis_cue_ids
    cues_worth_revisiting = [item.subtitle_cue_id for item in items if item.subtitle_cue_id in revisit_ids]

    return QuickPracticeCompletionSummary(
        cues_completed=len(completed_items),
        understood_count=understood,
        partly_understood_count=partly,
        missed_count=missed,
        diagnoses_created=len(diagnosis_rows),
        shadowing_actions=shadowing_actions,
        cues_worth_revisiting=cues_worth_revisiting,
    )

from __future__ import annotations

import sqlite3

from listentrace.application.errors import (
    AnnotationNotFoundError,
    AnnotationValidationError,
    CueNotFoundError,
)
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.models.annotation import Annotation
from listentrace.domain.services.text_range import TextRangeError, validate_selection
from listentrace.infrastructure.db.learning_repository import (
    delete_annotation as _repo_delete_annotation,
)
from listentrace.infrastructure.db.learning_repository import find_annotation
from listentrace.infrastructure.db.learning_repository import (
    get_annotation as _repo_get_annotation,
)
from listentrace.infrastructure.db.learning_repository import insert_annotations
from listentrace.infrastructure.db.learning_repository import (
    list_annotations_for_cue as _repo_list_annotations_for_cue,
)
from listentrace.infrastructure.db.learning_repository import (
    update_annotation as _repo_update_annotation,
)
from listentrace.infrastructure.db.repository import get_cue_by_id

_VALID_LABELS = {label.value for label in AnnotationLabel}


def create_annotations(
    conn: sqlite3.Connection,
    subtitle_cue_id: int,
    selection_start: int,
    selection_end: int,
    label_keys: list[str],
    heard_as: str | None = None,
    note: str | None = None,
) -> list[int]:
    cue = get_cue_by_id(conn, subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(subtitle_cue_id)

    if not label_keys:
        raise AnnotationValidationError("no_label_selected", "Select at least one label.")

    for label_key in label_keys:
        if label_key not in _VALID_LABELS:
            raise AnnotationValidationError("invalid_label", f"Unknown label: {label_key!r}")

    try:
        selected_text = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise AnnotationValidationError("invalid_range", str(exc)) from exc

    heard_as_value = heard_as.strip() if heard_as and heard_as.strip() else None
    if AnnotationLabel.MISHEARD.value in label_keys and not heard_as_value:
        raise AnnotationValidationError(
            "misheard_requires_heard_as", "Misheard annotations require heard_as text."
        )

    for label_key in label_keys:
        if find_annotation(conn, subtitle_cue_id, label_key, selection_start, selection_end) is not None:
            raise AnnotationValidationError(
                "duplicate_annotation",
                f"An annotation with label {label_key!r} already exists for this range.",
            )

    labels_with_heard_as = [
        (label_key, heard_as_value if label_key == AnnotationLabel.MISHEARD.value else None)
        for label_key in label_keys
    ]

    note_value = note.strip() if note and note.strip() else None

    return insert_annotations(
        conn, subtitle_cue_id, labels_with_heard_as, selected_text, selection_start, selection_end, note_value
    )


def update_annotation(
    conn: sqlite3.Connection,
    annotation_id: int,
    label_key: str,
    selection_start: int,
    selection_end: int,
    heard_as: str | None = None,
    note: str | None = None,
) -> None:
    """Fully update an annotation: label, canonical range, selected text, heard_as,
    and note. Re-runs the same validation as creation (label validity, range bounds,
    duplicate-on-same-range excluding this row, Misheard-requires-heard_as). Scoped
    to a single row by id, so it never touches a sibling label on the same range."""
    existing = _repo_get_annotation(conn, annotation_id)
    if existing is None:
        raise AnnotationNotFoundError(annotation_id)

    if label_key not in _VALID_LABELS:
        raise AnnotationValidationError("invalid_label", f"Unknown label: {label_key!r}")

    cue = get_cue_by_id(conn, existing.subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(existing.subtitle_cue_id)

    try:
        selected_text = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise AnnotationValidationError("invalid_range", str(exc)) from exc

    heard_as_value = heard_as.strip() if heard_as and heard_as.strip() else None
    if label_key == AnnotationLabel.MISHEARD.value and not heard_as_value:
        raise AnnotationValidationError(
            "misheard_requires_heard_as", "Misheard annotations require heard_as text."
        )
    if label_key != AnnotationLabel.MISHEARD.value:
        heard_as_value = None

    duplicate = find_annotation(conn, existing.subtitle_cue_id, label_key, selection_start, selection_end)
    if duplicate is not None and duplicate.id != annotation_id:
        raise AnnotationValidationError(
            "duplicate_annotation",
            f"An annotation with label {label_key!r} already exists for this range.",
        )

    note_value = note.strip() if note and note.strip() else None
    _repo_update_annotation(
        conn, annotation_id, label_key, selected_text, selection_start, selection_end, heard_as_value, note_value
    )


def delete_annotation(conn: sqlite3.Connection, annotation_id: int) -> None:
    if _repo_get_annotation(conn, annotation_id) is None:
        raise AnnotationNotFoundError(annotation_id)
    _repo_delete_annotation(conn, annotation_id)


def list_annotations_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[Annotation]:
    return _repo_list_annotations_for_cue(conn, subtitle_cue_id)

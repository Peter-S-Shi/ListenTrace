from __future__ import annotations

import sqlite3

from listentrace.application.dto.saved_item_results import (
    SavedItemNeedsConfirmation,
    SavedItemSuccess,
)
from listentrace.application.errors import (
    CueNotFoundError,
    SavedItemNotFoundError,
    SavedItemValidationError,
)
from listentrace.domain.enums.saved_item_type import SavedItemType
from listentrace.domain.models.saved_language_item import SavedLanguageItem
from listentrace.domain.services.text_range import TextRangeError, validate_selection
from listentrace.infrastructure.db.learning_repository import (
    delete_saved_language_item as _repo_delete,
)
from listentrace.infrastructure.db.learning_repository import find_saved_item_by_normalized_text_elsewhere
from listentrace.infrastructure.db.learning_repository import find_saved_item_exact
from listentrace.infrastructure.db.learning_repository import (
    get_saved_language_item as _repo_get,
)
from listentrace.infrastructure.db.learning_repository import insert_saved_language_item
from listentrace.infrastructure.db.learning_repository import (
    list_saved_items_for_cue as _repo_list_for_cue,
)
from listentrace.infrastructure.db.learning_repository import (
    list_saved_items_for_material as _repo_list_for_material,
)
from listentrace.infrastructure.db.learning_repository import (
    update_saved_language_item as _repo_update,
)
from listentrace.infrastructure.db.repository import get_cue_by_id
from listentrace.infrastructure.subtitles.text_normalize import normalize_cue_text

_VALID_ITEM_TYPES = {item.value for item in SavedItemType}


def save_language_item(
    conn: sqlite3.Connection,
    material_id: int,
    subtitle_cue_id: int,
    item_type: str,
    selection_start: int,
    selection_end: int,
    meaning: str | None = None,
    note: str | None = None,
    context_text: str | None = None,
    *,
    confirm_duplicate_text_elsewhere: bool = False,
) -> SavedItemSuccess | SavedItemNeedsConfirmation:
    cue = get_cue_by_id(conn, subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(subtitle_cue_id)

    if item_type not in _VALID_ITEM_TYPES:
        raise SavedItemValidationError("invalid_item_type", f"Unknown item type: {item_type!r}")

    try:
        text_value = validate_selection(cue.text, selection_start, selection_end)
    except TextRangeError as exc:
        raise SavedItemValidationError("invalid_range", str(exc)) from exc

    if not text_value.strip():
        raise SavedItemValidationError(
            "empty_text", "Select some text to save as a language item."
        )

    normalized = normalize_cue_text(text_value)

    if find_saved_item_exact(
        conn, material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized
    ) is not None:
        raise SavedItemValidationError(
            "duplicate_saved_item", "This exact language item has already been saved."
        )

    if not confirm_duplicate_text_elsewhere:
        elsewhere = find_saved_item_by_normalized_text_elsewhere(
            conn, normalized, material_id, subtitle_cue_id
        )
        if elsewhere is not None and elsewhere.id is not None:
            return SavedItemNeedsConfirmation(
                existing_item_id=elsewhere.id,
                existing_context_text=elsewhere.context_text,
                normalized_text=normalized,
            )

    context_value = context_text.strip() if context_text and context_text.strip() else cue.text
    meaning_value = meaning.strip() if meaning and meaning.strip() else None
    note_value = note.strip() if note and note.strip() else None

    item = SavedLanguageItem(
        material_id=material_id,
        subtitle_cue_id=subtitle_cue_id,
        item_type=item_type,
        text=text_value,
        normalized_text=normalized,
        selection_start=selection_start,
        selection_end=selection_end,
        context_text=context_value,
        meaning=meaning_value,
        note=note_value,
    )
    item_id = insert_saved_language_item(conn, item)
    return SavedItemSuccess(item_id=item_id)


def update_saved_language_item(
    conn: sqlite3.Connection,
    item_id: int,
    meaning: str | None = None,
    note: str | None = None,
    context_text: str | None = None,
) -> None:
    existing = _repo_get(conn, item_id)
    if existing is None:
        raise SavedItemNotFoundError(item_id)

    meaning_value = meaning.strip() if meaning and meaning.strip() else None
    note_value = note.strip() if note and note.strip() else None
    context_value = context_text.strip() if context_text and context_text.strip() else existing.context_text
    _repo_update(conn, item_id, meaning_value, note_value, context_value)


def delete_saved_language_item(conn: sqlite3.Connection, item_id: int) -> None:
    if _repo_get(conn, item_id) is None:
        raise SavedItemNotFoundError(item_id)
    _repo_delete(conn, item_id)


def list_saved_items_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[SavedLanguageItem]:
    return _repo_list_for_cue(conn, subtitle_cue_id)


def list_saved_items_for_material(conn: sqlite3.Connection, material_id: int) -> list[SavedLanguageItem]:
    return _repo_list_for_material(conn, material_id)

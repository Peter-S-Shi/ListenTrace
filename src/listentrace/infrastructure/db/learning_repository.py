from __future__ import annotations

import sqlite3

from listentrace.domain.models.annotation import Annotation
from listentrace.domain.models.cue_note import CueNote
from listentrace.domain.models.saved_language_item import SavedLanguageItem


def get_material_id_for_subtitle_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> int | None:
    """Derive the owning material via subtitle_cue -> subtitle_track -> material.

    Used so callers (application services, UI) never supply a material_id for a
    Saved Language Item directly — it is always derived from the cue's real
    ownership chain, preventing an inconsistent cue/material association.
    """
    row = conn.execute(
        """
        SELECT subtitle_track.material_id AS material_id
        FROM subtitle_cue
        JOIN subtitle_track ON subtitle_cue.subtitle_track_id = subtitle_track.id
        WHERE subtitle_cue.id = ?
        """,
        (subtitle_cue_id,),
    ).fetchone()
    return int(row["material_id"]) if row is not None else None


def _row_to_annotation(row: sqlite3.Row) -> Annotation:
    return Annotation(
        id=row["id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        label_key=row["label_key"],
        selected_text=row["selected_text"],
        selection_start=row["selection_start"],
        selection_end=row["selection_end"],
        heard_as=row["heard_as"],
        note=row["note"],
    )


def find_annotation(
    conn: sqlite3.Connection,
    subtitle_cue_id: int,
    label_key: str,
    selection_start: int,
    selection_end: int,
) -> Annotation | None:
    row = conn.execute(
        """
        SELECT * FROM annotation
        WHERE subtitle_cue_id = ? AND label_key = ? AND selection_start = ? AND selection_end = ?
        """,
        (subtitle_cue_id, label_key, selection_start, selection_end),
    ).fetchone()
    return _row_to_annotation(row) if row is not None else None


def insert_annotations(
    conn: sqlite3.Connection,
    subtitle_cue_id: int,
    labels_with_heard_as: list[tuple[str, str | None]],
    selected_text: str,
    selection_start: int,
    selection_end: int,
    note: str | None,
) -> list[int]:
    """Insert one Annotation row per (label, heard_as) pair, sharing the same range and
    note, as a single all-or-nothing transaction."""
    try:
        ids: list[int] = []
        for label_key, heard_as in labels_with_heard_as:
            cursor = conn.execute(
                """
                INSERT INTO annotation (
                    subtitle_cue_id, label_key, selected_text,
                    selection_start, selection_end, heard_as, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (subtitle_cue_id, label_key, selected_text, selection_start, selection_end, heard_as, note),
            )
            ids.append(int(cursor.lastrowid))
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return ids


def get_annotation(conn: sqlite3.Connection, annotation_id: int) -> Annotation | None:
    row = conn.execute("SELECT * FROM annotation WHERE id = ?", (annotation_id,)).fetchone()
    return _row_to_annotation(row) if row is not None else None


def list_annotations_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[Annotation]:
    rows = conn.execute(
        "SELECT * FROM annotation WHERE subtitle_cue_id = ? ORDER BY selection_start, id",
        (subtitle_cue_id,),
    ).fetchall()
    return [_row_to_annotation(row) for row in rows]


def update_annotation(
    conn: sqlite3.Connection,
    annotation_id: int,
    label_key: str,
    selected_text: str,
    selection_start: int,
    selection_end: int,
    heard_as: str | None,
    note: str | None,
) -> None:
    """Update a single annotation row by id. Scoped to `WHERE id = ?` only, so this
    never touches a sibling row that happens to share the same cue/range/label."""
    conn.execute(
        """
        UPDATE annotation
        SET label_key = ?, selected_text = ?, selection_start = ?, selection_end = ?,
            heard_as = ?, note = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (label_key, selected_text, selection_start, selection_end, heard_as, note, annotation_id),
    )
    conn.commit()


def delete_annotation(conn: sqlite3.Connection, annotation_id: int) -> None:
    conn.execute("DELETE FROM annotation WHERE id = ?", (annotation_id,))
    conn.commit()


def _row_to_cue_note(row: sqlite3.Row) -> CueNote:
    return CueNote(subtitle_cue_id=row["subtitle_cue_id"], note_text=row["note_text"])


def get_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int) -> CueNote | None:
    row = conn.execute(
        "SELECT * FROM cue_note WHERE subtitle_cue_id = ?", (subtitle_cue_id,)
    ).fetchone()
    return _row_to_cue_note(row) if row is not None else None


def upsert_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int, note_text: str) -> None:
    conn.execute(
        """
        INSERT INTO cue_note (subtitle_cue_id, note_text)
        VALUES (?, ?)
        ON CONFLICT (subtitle_cue_id) DO UPDATE SET
            note_text = excluded.note_text,
            updated_at = datetime('now')
        """,
        (subtitle_cue_id, note_text),
    )
    conn.commit()


def delete_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int) -> None:
    conn.execute("DELETE FROM cue_note WHERE subtitle_cue_id = ?", (subtitle_cue_id,))
    conn.commit()


def _row_to_saved_item(row: sqlite3.Row) -> SavedLanguageItem:
    return SavedLanguageItem(
        id=row["id"],
        material_id=row["material_id"],
        subtitle_cue_id=row["subtitle_cue_id"],
        item_type=row["item_type"],
        text=row["text"],
        normalized_text=row["normalized_text"],
        selection_start=row["selection_start"],
        selection_end=row["selection_end"],
        meaning=row["meaning"],
        note=row["note"],
        context_text=row["context_text"],
    )


def insert_saved_language_item(conn: sqlite3.Connection, item: SavedLanguageItem) -> int:
    cursor = conn.execute(
        """
        INSERT INTO saved_language_item (
            material_id, subtitle_cue_id, item_type, text, normalized_text,
            selection_start, selection_end, meaning, note, context_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.material_id,
            item.subtitle_cue_id,
            item.item_type,
            item.text,
            item.normalized_text,
            item.selection_start,
            item.selection_end,
            item.meaning,
            item.note,
            item.context_text,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_saved_language_item(conn: sqlite3.Connection, item_id: int) -> SavedLanguageItem | None:
    row = conn.execute(
        "SELECT * FROM saved_language_item WHERE id = ?", (item_id,)
    ).fetchone()
    return _row_to_saved_item(row) if row is not None else None


def list_saved_items_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[SavedLanguageItem]:
    rows = conn.execute(
        "SELECT * FROM saved_language_item WHERE subtitle_cue_id = ? ORDER BY id",
        (subtitle_cue_id,),
    ).fetchall()
    return [_row_to_saved_item(row) for row in rows]


def list_saved_items_for_material(conn: sqlite3.Connection, material_id: int) -> list[SavedLanguageItem]:
    rows = conn.execute(
        "SELECT * FROM saved_language_item WHERE material_id = ? ORDER BY id",
        (material_id,),
    ).fetchall()
    return [_row_to_saved_item(row) for row in rows]


def find_saved_item_exact(
    conn: sqlite3.Connection,
    material_id: int,
    subtitle_cue_id: int,
    item_type: str,
    selection_start: int,
    selection_end: int,
    normalized_text: str,
) -> SavedLanguageItem | None:
    row = conn.execute(
        """
        SELECT * FROM saved_language_item
        WHERE material_id = ? AND subtitle_cue_id = ? AND item_type = ?
          AND selection_start = ? AND selection_end = ? AND normalized_text = ?
        """,
        (material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized_text),
    ).fetchone()
    return _row_to_saved_item(row) if row is not None else None


def find_saved_item_by_normalized_text_elsewhere(
    conn: sqlite3.Connection,
    normalized_text: str,
    exclude_material_id: int,
    exclude_subtitle_cue_id: int,
) -> SavedLanguageItem | None:
    row = conn.execute(
        """
        SELECT * FROM saved_language_item
        WHERE normalized_text = ?
          AND NOT (material_id = ? AND subtitle_cue_id = ?)
        LIMIT 1
        """,
        (normalized_text, exclude_material_id, exclude_subtitle_cue_id),
    ).fetchone()
    return _row_to_saved_item(row) if row is not None else None


def update_saved_language_item(
    conn: sqlite3.Connection,
    item_id: int,
    item_type: str,
    meaning: str | None,
    note: str | None,
    context_text: str,
) -> None:
    """Update type/meaning/note/context only. Source text/range/normalized_text are
    intentionally not parameters here: identity fields are locked once saved (see
    `saved_language_item_service.update_saved_language_item`)."""
    conn.execute(
        """
        UPDATE saved_language_item
        SET item_type = ?, meaning = ?, note = ?, context_text = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (item_type, meaning, note, context_text, item_id),
    )
    conn.commit()


def delete_saved_language_item(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute("DELETE FROM saved_language_item WHERE id = ?", (item_id,))
    conn.commit()


def get_label_preferences(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT label_key, color FROM annotation_label_preference ORDER BY label_key"
    ).fetchall()
    return {row["label_key"]: row["color"] for row in rows}


def update_label_color(conn: sqlite3.Connection, label_key: str, color: str) -> None:
    conn.execute(
        """
        UPDATE annotation_label_preference
        SET color = ?, updated_at = datetime('now')
        WHERE label_key = ?
        """,
        (color, label_key),
    )
    conn.commit()

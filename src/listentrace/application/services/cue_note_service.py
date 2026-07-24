from __future__ import annotations

import sqlite3

from listentrace.application.errors import CueNotFoundError
from listentrace.domain.models.cue_note import CueNote
from listentrace.infrastructure.db.learning_repository import delete_cue_note as _repo_delete
from listentrace.infrastructure.db.learning_repository import get_cue_note as _repo_get
from listentrace.infrastructure.db.learning_repository import upsert_cue_note as _repo_upsert
from listentrace.infrastructure.db.repository import get_cue_by_id


def save_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int, note_text: str) -> None:
    """Save the cue's note. An empty/whitespace-only save is treated as delete-intent."""
    if get_cue_by_id(conn, subtitle_cue_id) is None:
        raise CueNotFoundError(subtitle_cue_id)

    stripped = note_text.strip() if note_text else ""
    if not stripped:
        _repo_delete(conn, subtitle_cue_id)
    else:
        _repo_upsert(conn, subtitle_cue_id, stripped)


def get_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int) -> CueNote | None:
    return _repo_get(conn, subtitle_cue_id)


def delete_cue_note(conn: sqlite3.Connection, subtitle_cue_id: int) -> None:
    _repo_delete(conn, subtitle_cue_id)

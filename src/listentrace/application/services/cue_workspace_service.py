from __future__ import annotations

import sqlite3

from listentrace.application.dto.cue_workspace import CueWorkspace
from listentrace.application.errors import CueNotFoundError
from listentrace.infrastructure.db.learning_repository import get_cue_note, list_annotations_for_cue
from listentrace.infrastructure.db.learning_repository import (
    list_saved_items_for_cue,
)
from listentrace.infrastructure.db.repository import get_cue_by_id


def load_cue_workspace(conn: sqlite3.Connection, subtitle_cue_id: int) -> CueWorkspace:
    cue = get_cue_by_id(conn, subtitle_cue_id)
    if cue is None:
        raise CueNotFoundError(subtitle_cue_id)

    return CueWorkspace(
        cue=cue,
        annotations=list_annotations_for_cue(conn, subtitle_cue_id),
        cue_note=get_cue_note(conn, subtitle_cue_id),
        saved_items=list_saved_items_for_cue(conn, subtitle_cue_id),
    )

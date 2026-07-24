from __future__ import annotations

import sqlite3
from pathlib import Path

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.errors import PlayerOpenError
from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_material,
    get_subtitle_track_for_material,
)


def load_material_for_player(conn: sqlite3.Connection, material_id: int) -> PlayerLoadResult:
    material = get_material(conn, material_id)
    if material is None:
        raise PlayerOpenError("not_found", "This material no longer exists.")

    if material.status == MaterialStatus.ARCHIVED.value:
        raise PlayerOpenError(
            "archived", "Archived materials cannot be opened. Restore it first."
        )

    if not Path(material.media_path).exists():
        raise PlayerOpenError(
            "media_missing", f"The media file is missing: {material.media_path}"
        )

    track = get_subtitle_track_for_material(conn, material.id)
    if track is None or track.id is None:
        raise PlayerOpenError("subtitle_missing", "This material has no subtitle track.")

    if not Path(track.source_path).exists():
        raise PlayerOpenError(
            "subtitle_missing", f"The subtitle file is missing: {track.source_path}"
        )

    cues = get_cues_for_track(conn, track.id)
    return PlayerLoadResult(material=material, cues=cues)

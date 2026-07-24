from __future__ import annotations

import sqlite3
from pathlib import Path

from listentrace.application.dto.material_views import MaterialDetail, MaterialSummary
from listentrace.application.dto.recording_views import DeletionSummary
from listentrace.application.errors import MaterialNotFoundError
from listentrace.application.services import recording_service
from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.domain.models.material import Material
from listentrace.infrastructure.db.repository import (
    delete_material,
    get_cue_count,
    get_material,
    get_subtitle_track_for_material,
    list_materials_by_status,
)
from listentrace.infrastructure.db.repository import rename_material as _repo_rename_material
from listentrace.infrastructure.db.repository import set_material_status as _repo_set_status


def _to_summary(material: Material) -> MaterialSummary:
    return MaterialSummary(
        id=material.id,
        title=material.title,
        status=material.status,
        media_path=material.media_path,
        language=material.language,
        media_available=Path(material.media_path).exists(),
    )


def list_active_materials(conn: sqlite3.Connection) -> list[MaterialSummary]:
    return [_to_summary(m) for m in list_materials_by_status(conn, MaterialStatus.ACTIVE)]


def list_archived_materials(conn: sqlite3.Connection) -> list[MaterialSummary]:
    return [_to_summary(m) for m in list_materials_by_status(conn, MaterialStatus.ARCHIVED)]


def get_material_detail(conn: sqlite3.Connection, material_id: int) -> MaterialDetail:
    material = get_material(conn, material_id)
    if material is None:
        raise MaterialNotFoundError(material_id)

    track = get_subtitle_track_for_material(conn, material_id)
    cue_count = get_cue_count(conn, track.id) if track is not None and track.id is not None else 0

    return MaterialDetail(
        id=material.id,
        title=material.title,
        status=material.status,
        media_path=material.media_path,
        language=material.language,
        media_available=Path(material.media_path).exists(),
        subtitle_format=track.format if track is not None else None,
        subtitle_source_path=track.source_path if track is not None else None,
        subtitle_available=Path(track.source_path).exists() if track is not None else False,
        cue_count=cue_count,
    )


def rename_material(conn: sqlite3.Connection, material_id: int, new_title: str) -> None:
    if get_material(conn, material_id) is None:
        raise MaterialNotFoundError(material_id)
    _repo_rename_material(conn, material_id, new_title)


def archive_material(conn: sqlite3.Connection, material_id: int) -> None:
    if get_material(conn, material_id) is None:
        raise MaterialNotFoundError(material_id)
    _repo_set_status(conn, material_id, MaterialStatus.ARCHIVED)


def restore_material(conn: sqlite3.Connection, material_id: int) -> None:
    if get_material(conn, material_id) is None:
        raise MaterialNotFoundError(material_id)
    _repo_set_status(conn, material_id, MaterialStatus.ACTIVE)


def remove_material(conn: sqlite3.Connection, recordings_dir: Path, material_id: int) -> DeletionSummary:
    """Removes ListenTrace's own records for a material. Recording files are
    ListenTrace-managed local data (unlike the source media/subtitle files,
    which are never touched) — deleted explicitly here, before the DB cascade
    would otherwise remove their rows without cleaning up the files themselves.
    A recording whose file could not be deleted is reported back rather than
    silently left as an orphaned file; the material is removed regardless, since
    blocking the whole removal on one locked recording file would be worse."""
    if get_material(conn, material_id) is None:
        raise MaterialNotFoundError(material_id)
    summary = recording_service.delete_takes_for_material(conn, recordings_dir, material_id)
    delete_material(conn, material_id)
    return summary

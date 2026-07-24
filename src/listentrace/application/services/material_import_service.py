from __future__ import annotations

import sqlite3
from pathlib import Path

from listentrace.application.dto.import_results import ImportNeedsConfirmation, ImportSuccess
from listentrace.application.errors import MaterialValidationError
from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleTrack
from listentrace.infrastructure.db.repository import (
    create_material_package,
    find_material_by_fingerprint,
    find_material_by_normalized_path,
)
from listentrace.infrastructure.media.validation import (
    MediaValidationError,
    compute_file_fingerprint,
    normalize_media_path,
    validate_media_file,
)
from listentrace.infrastructure.subtitles.errors import SubtitleParseError
from listentrace.infrastructure.subtitles.loader import parse_subtitle_file

_SUPPORTED_SUBTITLE_SUFFIXES = (".srt", ".vtt")


def import_material(
    conn: sqlite3.Connection,
    media_path: Path | str,
    subtitle_path: Path | str,
    title: str,
    language: str | None = None,
    *,
    confirm_duplicate_fingerprint: bool = False,
) -> ImportSuccess | ImportNeedsConfirmation:
    media_file_path = Path(media_path)
    subtitle_file_path = Path(subtitle_path)

    try:
        media_info = validate_media_file(media_file_path)
    except MediaValidationError as exc:
        raise MaterialValidationError(exc.category, str(exc)) from exc

    if not subtitle_file_path.exists():
        raise MaterialValidationError(
            "subtitle_not_found", f"Subtitle file not found: {subtitle_file_path}"
        )

    if subtitle_file_path.suffix.lower() not in _SUPPORTED_SUBTITLE_SUFFIXES:
        raise MaterialValidationError(
            "subtitle_unsupported_format",
            f"Unsupported subtitle file type: {subtitle_file_path.suffix!r}",
        )

    try:
        cues = parse_subtitle_file(subtitle_file_path)
    except OSError as exc:
        raise MaterialValidationError(
            "subtitle_unreadable", f"Subtitle file could not be read: {exc}"
        ) from exc
    except SubtitleParseError as exc:
        raise MaterialValidationError("subtitle_malformed", str(exc)) from exc

    if not cues:
        raise MaterialValidationError("subtitle_empty", "Subtitle file contains no cues")

    normalized_path = normalize_media_path(media_file_path)
    existing_by_path = find_material_by_normalized_path(conn, normalized_path)
    if existing_by_path is not None:
        raise MaterialValidationError(
            "duplicate_path",
            f"This media file has already been imported as '{existing_by_path.title}'.",
        )

    fingerprint = compute_file_fingerprint(media_file_path)

    if not confirm_duplicate_fingerprint:
        existing_by_fingerprint = find_material_by_fingerprint(conn, fingerprint)
        if existing_by_fingerprint is not None and existing_by_fingerprint.id is not None:
            return ImportNeedsConfirmation(
                existing_material_id=existing_by_fingerprint.id,
                existing_media_path=existing_by_fingerprint.media_path,
                fingerprint=fingerprint,
            )

    material = Material(
        title=title,
        media_path=str(media_file_path),
        normalized_path=normalized_path,
        language=language,
        media_kind=media_info.media_kind,
        file_size_bytes=media_info.size_bytes,
        file_fingerprint=fingerprint,
        status=MaterialStatus.ACTIVE.value,
    )

    track = SubtitleTrack(
        material_id=0,
        format=subtitle_file_path.suffix.lower().lstrip("."),
        source_path=str(subtitle_file_path),
        cues=cues,
    )

    material_id, track_id = create_material_package(conn, material, track)
    return ImportSuccess(material_id=material_id, subtitle_track_id=track_id, cue_count=len(cues))

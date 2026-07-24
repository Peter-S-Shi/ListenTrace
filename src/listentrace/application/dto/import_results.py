from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ImportSuccess:
    material_id: int
    subtitle_track_id: int
    cue_count: int


@dataclass(slots=True)
class ImportNeedsConfirmation:
    existing_material_id: int
    existing_media_path: str
    fingerprint: str

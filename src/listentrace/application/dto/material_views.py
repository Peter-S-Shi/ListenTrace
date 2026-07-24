from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MaterialSummary:
    id: int
    title: str
    status: str
    media_path: str
    language: str | None
    media_available: bool


@dataclass(slots=True)
class MaterialDetail:
    id: int
    title: str
    status: str
    media_path: str
    language: str | None
    media_available: bool
    subtitle_format: str | None
    subtitle_source_path: str | None
    subtitle_available: bool
    cue_count: int

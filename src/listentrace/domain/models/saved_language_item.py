from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SavedLanguageItem:
    material_id: int
    subtitle_cue_id: int
    item_type: str
    text: str
    normalized_text: str
    selection_start: int
    selection_end: int
    context_text: str
    meaning: str | None = None
    note: str | None = None
    id: int | None = None

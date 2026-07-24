from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Annotation:
    subtitle_cue_id: int
    label_key: str
    selected_text: str
    selection_start: int
    selection_end: int
    heard_as: str | None = None
    note: str | None = None
    id: int | None = None

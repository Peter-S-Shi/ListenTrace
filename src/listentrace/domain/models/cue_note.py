from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CueNote:
    subtitle_cue_id: int
    note_text: str

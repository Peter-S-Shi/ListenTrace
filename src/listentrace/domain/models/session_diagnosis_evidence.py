from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionDiagnosisEvidence:
    practice_session_id: int
    subtitle_cue_id: int
    label_key: str
    selected_text: str
    selection_start: int
    selection_end: int
    annotation_id: int | None = None
    heard_as: str | None = None
    note: str | None = None
    id: int | None = None

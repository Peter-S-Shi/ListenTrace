from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuickPracticeDiagnosisEvidence:
    quick_practice_item_id: int
    label_key: str
    selected_text: str
    selection_start: int
    selection_end: int
    annotation_id: int | None = None
    heard_as: str | None = None
    note: str | None = None
    id: int | None = None

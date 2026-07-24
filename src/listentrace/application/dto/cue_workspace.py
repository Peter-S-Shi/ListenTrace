from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.models.annotation import Annotation
from listentrace.domain.models.cue_note import CueNote
from listentrace.domain.models.saved_language_item import SavedLanguageItem
from listentrace.domain.models.subtitle import SubtitleCue


@dataclass(slots=True)
class CueWorkspace:
    cue: SubtitleCue
    annotations: list[Annotation]
    cue_note: CueNote | None
    saved_items: list[SavedLanguageItem]

from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue


@dataclass(slots=True)
class PlayerLoadResult:
    material: Material
    cues: list[SubtitleCue]

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SubtitleCue:
    cue_index: int
    start_ms: int
    end_ms: int
    text: str
    normalized_text: str | None = None

    def __post_init__(self) -> None:
        if self.end_ms < self.start_ms:
            raise ValueError(
                f"cue {self.cue_index}: end_ms ({self.end_ms}) is before start_ms ({self.start_ms})"
            )


@dataclass(slots=True)
class SubtitleTrack:
    material_id: int
    format: str
    source_path: str
    cues: list[SubtitleCue]
    language: str | None = None
    is_timed: bool = True
    encoding: str = "utf-8"
    id: int | None = None

from __future__ import annotations

import bisect

from listentrace.domain.models.subtitle import SubtitleCue


class CueIndex:
    """Deterministic active-cue lookup and original-order navigation over a cue list."""

    def __init__(self, cues: list[SubtitleCue]):
        self._cues = list(cues)
        self._order_by_start = sorted(
            range(len(self._cues)), key=lambda i: self._cues[i].start_ms
        )
        self._starts_sorted = [self._cues[i].start_ms for i in self._order_by_start]

    @property
    def cues(self) -> list[SubtitleCue]:
        return self._cues

    def active_cue_index(self, position_ms: int) -> int | None:
        """Index (in original order) of the active cue at `position_ms`, or None during a gap.

        Rule: cue.start_ms <= position_ms < cue.end_ms. When cues overlap, the cue with the
        latest start time among those actually covering `position_ms` wins.
        """
        pos = bisect.bisect_right(self._starts_sorted, position_ms) - 1
        while pos >= 0:
            original_index = self._order_by_start[pos]
            cue = self._cues[original_index]
            if cue.start_ms <= position_ms < cue.end_ms:
                return original_index
            pos -= 1
        return None

    def previous_index(self, current_index: int | None) -> int | None:
        if not self._cues:
            return None
        if current_index is None:
            return 0
        return max(current_index - 1, 0)

    def next_index(self, current_index: int | None) -> int | None:
        if not self._cues:
            return None
        if current_index is None:
            return 0
        return min(current_index + 1, len(self._cues) - 1)

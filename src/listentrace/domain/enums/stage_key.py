from __future__ import annotations

from enum import Enum


class StageKey(str, Enum):
    GLOBAL_COMPREHENSION = "global_comprehension"
    KEYWORD_CAPTURE = "keyword_capture"
    TRANSCRIPT_DIAGNOSIS = "transcript_diagnosis"
    SHADOWING = "shadowing"
    FINAL_SUMMARY = "final_summary"


# Fixed guided-session stage order. Session creation initializes one
# SessionStageProgress row per key in this order; UI navigation follows it.
STAGE_ORDER: tuple[str, ...] = (
    StageKey.GLOBAL_COMPREHENSION.value,
    StageKey.KEYWORD_CAPTURE.value,
    StageKey.TRANSCRIPT_DIAGNOSIS.value,
    StageKey.SHADOWING.value,
    StageKey.FINAL_SUMMARY.value,
)

# Stages 1 and 2 are transcript-hidden and become read-only once the
# transcript is revealed for Stage 3.
TRANSCRIPT_LOCKED_STAGES: frozenset[str] = frozenset(
    {StageKey.GLOBAL_COMPREHENSION.value, StageKey.KEYWORD_CAPTURE.value}
)

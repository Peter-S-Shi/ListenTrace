from __future__ import annotations

from enum import Enum


class StageOutcome(str, Enum):
    """Stage outcomes distinct from ordinary evidence-based completion or skipping.

    Currently only Stage 3's explicit "no notable difficulty found" action, stored
    as `SessionStageProgress.outcome_key` — a completion path that is neither
    evidence-backed nor a skip.
    """

    NO_NOTABLE_DIFFICULTY = "no_notable_difficulty"

from __future__ import annotations

from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.stage_outcome import StageOutcome
from listentrace.domain.enums.stage_status import StageStatus

# Pure, framework-free session/stage lifecycle rules. No sqlite, no Qt: the
# application layer is responsible for loading the data these functions need
# and acting on their answers.

_SESSION_TRANSITIONS: dict[str, frozenset[str]] = {
    SessionStatus.ACTIVE.value: frozenset({SessionStatus.COMPLETED.value, SessionStatus.ABANDONED.value}),
}

_STAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    StageStatus.NOT_STARTED.value: frozenset({StageStatus.IN_PROGRESS.value, StageStatus.SKIPPED.value}),
    StageStatus.IN_PROGRESS.value: frozenset({StageStatus.COMPLETED.value, StageStatus.SKIPPED.value}),
}


def is_valid_session_transition(current_status: str, new_status: str) -> bool:
    return new_status in _SESSION_TRANSITIONS.get(current_status, frozenset())


def is_valid_stage_transition(current_status: str, new_status: str) -> bool:
    return new_status in _STAGE_TRANSITIONS.get(current_status, frozenset())


def stage1_can_complete(responses: dict[str, str]) -> bool:
    """At least one comprehension prompt has a non-whitespace answer."""
    return any(text.strip() for text in responses.values())


def stage2_can_complete(capture_count: int) -> bool:
    """At least one keyword/fragment capture exists."""
    return capture_count > 0


def stage3_can_complete(evidence_count: int, outcome_key: str | None) -> bool:
    """At least one diagnosis record, or the explicit no-difficulty outcome."""
    return evidence_count > 0 or outcome_key == StageOutcome.NO_NOTABLE_DIFFICULTY.value


def stage4_can_complete(unresolved_cue_count: int) -> bool:
    """Every timed cue has been marked practiced or skipped."""
    return unresolved_cue_count == 0


def stage5_can_complete(summary_text: str) -> bool:
    """A non-empty final summary."""
    return bool(summary_text.strip())


def session_can_complete(stage_statuses: dict[str, str]) -> bool:
    """Every stage is completed or skipped."""
    terminal = {StageStatus.COMPLETED.value, StageStatus.SKIPPED.value}
    return bool(stage_statuses) and all(status in terminal for status in stage_statuses.values())

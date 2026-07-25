from __future__ import annotations

from listentrace.domain.enums.quick_practice_status import QuickPracticeStatus
from listentrace.domain.enums.recall_result import RecallResult

# Pure, framework-free Quick Practice (Milestone 10) rules. No sqlite, no Qt:
# the application layer loads whatever data these functions need and acts on
# their answers, matching the existing `session_rules.py`/`quiz_rules.py`
# pattern.

ALLOWED_RECOMMENDED_COUNTS: tuple[int, ...] = (3, 5, 10)
DEFAULT_RECOMMENDED_COUNT = 5

VALID_RECALL_RESULTS: frozenset[str] = frozenset(result.value for result in RecallResult)

_TRANSITIONS: dict[str, frozenset[str]] = {
    QuickPracticeStatus.ACTIVE.value: frozenset(
        {QuickPracticeStatus.COMPLETED.value, QuickPracticeStatus.ABANDONED.value}
    ),
}


def is_valid_recommended_count(count: int) -> bool:
    return count in ALLOWED_RECOMMENDED_COUNTS


def is_valid_recall_result(value: str) -> bool:
    return value in VALID_RECALL_RESULTS


def is_valid_transition(current_status: str, new_status: str) -> bool:
    return new_status in _TRANSITIONS.get(current_status, frozenset())


def item_can_complete(recall_result: str | None) -> bool:
    """An item can only be marked complete once a recall result has been
    recorded (Step 2) — diagnosis (Step 3) and replay/shadow/recording
    (Step 4) are always optional and never gate completion."""
    return recall_result is not None


def session_can_complete(item_completed_flags: list[bool]) -> bool:
    """Every item in the session has been completed. An empty list can never
    complete (a session with zero items should not exist)."""
    return bool(item_completed_flags) and all(item_completed_flags)


def session_can_preserve_on_close(completed_item_count: int) -> bool:
    """Whether closing mid-session should preserve evidence (abandon) rather
    than discard it entirely — true once at least one cue has been
    completed (see `session_should_discard_on_close`, its exact complement)."""
    return completed_item_count > 0


def session_should_discard_on_close(completed_item_count: int) -> bool:
    """Zero completed cues means nothing meaningful was recorded — closing
    here must not leave a misleading historical session behind at all."""
    return completed_item_count == 0

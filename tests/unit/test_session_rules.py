from __future__ import annotations

from listentrace.domain.enums.session_status import SessionStatus
from listentrace.domain.enums.stage_outcome import StageOutcome
from listentrace.domain.enums.stage_status import StageStatus
from listentrace.domain.services import session_rules as rules


def test_active_session_can_complete_or_abandon():
    assert rules.is_valid_session_transition(SessionStatus.ACTIVE.value, SessionStatus.COMPLETED.value)
    assert rules.is_valid_session_transition(SessionStatus.ACTIVE.value, SessionStatus.ABANDONED.value)


def test_completed_and_abandoned_sessions_cannot_transition_further():
    assert not rules.is_valid_session_transition(SessionStatus.COMPLETED.value, SessionStatus.ACTIVE.value)
    assert not rules.is_valid_session_transition(SessionStatus.COMPLETED.value, SessionStatus.ABANDONED.value)
    assert not rules.is_valid_session_transition(SessionStatus.ABANDONED.value, SessionStatus.ACTIVE.value)
    assert not rules.is_valid_session_transition(SessionStatus.ABANDONED.value, SessionStatus.COMPLETED.value)


def test_stage_transitions_follow_not_started_in_progress_terminal():
    assert rules.is_valid_stage_transition(StageStatus.NOT_STARTED.value, StageStatus.IN_PROGRESS.value)
    assert rules.is_valid_stage_transition(StageStatus.NOT_STARTED.value, StageStatus.SKIPPED.value)
    assert rules.is_valid_stage_transition(StageStatus.IN_PROGRESS.value, StageStatus.COMPLETED.value)
    assert rules.is_valid_stage_transition(StageStatus.IN_PROGRESS.value, StageStatus.SKIPPED.value)


def test_terminal_stage_statuses_cannot_transition_further():
    assert not rules.is_valid_stage_transition(StageStatus.COMPLETED.value, StageStatus.SKIPPED.value)
    assert not rules.is_valid_stage_transition(StageStatus.SKIPPED.value, StageStatus.COMPLETED.value)
    assert not rules.is_valid_stage_transition(StageStatus.NOT_STARTED.value, StageStatus.COMPLETED.value)


def test_stage1_requires_at_least_one_non_whitespace_response():
    assert not rules.stage1_can_complete({})
    assert not rules.stage1_can_complete({"who_is_speaking": "", "where": "   "})
    assert rules.stage1_can_complete({"who_is_speaking": "", "where": "A park"})


def test_stage2_requires_at_least_one_capture():
    assert not rules.stage2_can_complete(0)
    assert rules.stage2_can_complete(1)


def test_stage3_requires_evidence_or_no_difficulty_outcome():
    assert not rules.stage3_can_complete(0, None)
    assert rules.stage3_can_complete(1, None)
    assert rules.stage3_can_complete(0, StageOutcome.NO_NOTABLE_DIFFICULTY.value)


def test_stage4_requires_zero_unresolved_cues():
    assert not rules.stage4_can_complete(1)
    assert rules.stage4_can_complete(0)


def test_stage5_requires_non_empty_summary():
    assert not rules.stage5_can_complete("")
    assert not rules.stage5_can_complete("   ")
    assert rules.stage5_can_complete("A short summary.")


def test_session_can_complete_only_when_every_stage_is_terminal():
    assert not rules.session_can_complete(
        {
            "global_comprehension": StageStatus.COMPLETED.value,
            "keyword_capture": StageStatus.IN_PROGRESS.value,
        }
    )
    assert rules.session_can_complete(
        {
            "global_comprehension": StageStatus.COMPLETED.value,
            "keyword_capture": StageStatus.SKIPPED.value,
            "transcript_diagnosis": StageStatus.COMPLETED.value,
            "shadowing": StageStatus.SKIPPED.value,
            "final_summary": StageStatus.COMPLETED.value,
        }
    )


def test_session_can_complete_is_false_for_empty_stage_map():
    assert not rules.session_can_complete({})

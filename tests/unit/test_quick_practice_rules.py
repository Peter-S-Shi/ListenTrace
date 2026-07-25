from __future__ import annotations

from listentrace.domain.services import quick_practice_rules as rules


def test_allowed_recommended_counts_are_3_5_10_default_5():
    assert rules.ALLOWED_RECOMMENDED_COUNTS == (3, 5, 10)
    assert rules.DEFAULT_RECOMMENDED_COUNT == 5


def test_is_valid_recommended_count():
    assert rules.is_valid_recommended_count(3)
    assert rules.is_valid_recommended_count(5)
    assert rules.is_valid_recommended_count(10)
    assert not rules.is_valid_recommended_count(4)
    assert not rules.is_valid_recommended_count(0)


def test_is_valid_recall_result():
    assert rules.is_valid_recall_result("understood")
    assert rules.is_valid_recall_result("partly_understood")
    assert rules.is_valid_recall_result("missed")
    assert not rules.is_valid_recall_result("confused")


def test_active_transitions_to_completed_or_abandoned_only():
    assert rules.is_valid_transition("active", "completed")
    assert rules.is_valid_transition("active", "abandoned")
    assert not rules.is_valid_transition("active", "active")
    assert not rules.is_valid_transition("completed", "abandoned")
    assert not rules.is_valid_transition("abandoned", "completed")


def test_item_can_complete_requires_a_recall_result():
    assert not rules.item_can_complete(None)
    assert rules.item_can_complete("understood")
    assert rules.item_can_complete("missed")


def test_session_can_complete_requires_every_item_completed():
    assert not rules.session_can_complete([])
    assert not rules.session_can_complete([True, False])
    assert rules.session_can_complete([True, True])


def test_close_behavior_discards_on_zero_progress_and_preserves_otherwise():
    assert rules.session_should_discard_on_close(0)
    assert not rules.session_should_discard_on_close(1)
    assert not rules.session_can_preserve_on_close(0)
    assert rules.session_can_preserve_on_close(1)
    assert rules.session_can_preserve_on_close(3)

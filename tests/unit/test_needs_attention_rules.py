from __future__ import annotations

from listentrace.domain.services import needs_attention_rules as rules


def _stats(**overrides):
    defaults = dict(
        material_id=1,
        recent_quiz_accuracies=(),
        diagnosis_label_counts={},
        abandoned_session_count=0,
        total_session_count=0,
        active_session_count=0,
        skipped_stage_counts_by_session=(),
        quick_practice_missed_count=0,
    )
    defaults.update(overrides)
    return rules.MaterialActivityStats(**defaults)


def test_no_evidence_yields_no_reasons():
    assert rules.evaluate_material(_stats()) == []


def test_low_recent_quiz_accuracy_is_flagged():
    stats = _stats(recent_quiz_accuracies=(0.4, 0.5, 0.3))
    reasons = rules.evaluate_material(stats)
    keys = [r.reason_key for r in reasons]
    assert "low_recent_quiz_accuracy" in keys


def test_high_recent_quiz_accuracy_is_not_flagged():
    stats = _stats(recent_quiz_accuracies=(0.9, 1.0, 0.8))
    reasons = rules.evaluate_material(stats)
    assert "low_recent_quiz_accuracy" not in [r.reason_key for r in reasons]


def test_only_the_most_recent_window_of_attempts_is_averaged():
    # 3 recent good scores followed by old bad ones the window should ignore.
    stats = _stats(recent_quiz_accuracies=(0.9, 0.9, 0.9, 0.1, 0.1, 0.1))
    reasons = rules.evaluate_material(stats)
    assert "low_recent_quiz_accuracy" not in [r.reason_key for r in reasons]


def test_repeated_diagnosis_evidence_is_flagged_per_label():
    stats = _stats(diagnosis_label_counts={"misheard": 3, "keyword": 1})
    reasons = rules.evaluate_material(stats)
    matching = [r for r in reasons if r.reason_key == "repeated_diagnosis_evidence"]
    assert len(matching) == 1
    assert "misheard" in matching[0].detail
    assert "keyword" not in matching[0].detail


def test_multiple_abandoned_sessions_is_flagged_at_threshold():
    below = _stats(abandoned_session_count=rules.ABANDONED_SESSION_THRESHOLD - 1)
    at = _stats(abandoned_session_count=rules.ABANDONED_SESSION_THRESHOLD)
    assert "multiple_abandoned_sessions" not in [r.reason_key for r in rules.evaluate_material(below)]
    assert "multiple_abandoned_sessions" in [r.reason_key for r in rules.evaluate_material(at)]


def test_frequently_revisited_material_is_flagged_at_threshold():
    stats = _stats(total_session_count=rules.FREQUENTLY_REVISITED_SESSION_THRESHOLD)
    assert "frequently_revisited_material" in [r.reason_key for r in rules.evaluate_material(stats)]


def test_many_skipped_stages_counts_sessions_at_or_above_threshold():
    stats = _stats(skipped_stage_counts_by_session=(0, 1, rules.MANY_SKIPPED_STAGES_THRESHOLD, 5))
    reasons = rules.evaluate_material(stats)
    matching = [r for r in reasons if r.reason_key == "many_skipped_stages"]
    assert len(matching) == 1
    assert "2 session(s)" in matching[0].detail


def test_active_unfinished_session_is_flagged():
    stats = _stats(active_session_count=1)
    assert "active_unfinished_session" in [r.reason_key for r in rules.evaluate_material(stats)]


def test_one_isolated_missed_quick_practice_result_is_not_flagged():
    stats = _stats(quick_practice_missed_count=1)
    assert "repeated_missed_in_quick_practice" not in [r.reason_key for r in rules.evaluate_material(stats)]


def test_repeated_missed_quick_practice_results_are_flagged():
    stats = _stats(quick_practice_missed_count=rules.REPEATED_QUICK_PRACTICE_MISSED_THRESHOLD)
    assert "repeated_missed_in_quick_practice" in [r.reason_key for r in rules.evaluate_material(stats)]


def test_reasons_never_produce_a_combined_score():
    stats = _stats(
        recent_quiz_accuracies=(0.1,),
        diagnosis_label_counts={"misheard": 5},
        abandoned_session_count=5,
        total_session_count=10,
        active_session_count=2,
        skipped_stage_counts_by_session=(4, 4),
    )
    reasons = rules.evaluate_material(stats)
    # Every reason is independently named and explainable; there is no
    # aggregate numeric field anywhere on NeedsAttentionReason.
    assert len(reasons) == 6
    for reason in reasons:
        assert not hasattr(reason, "score")

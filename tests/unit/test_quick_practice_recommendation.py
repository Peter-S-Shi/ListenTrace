from __future__ import annotations

from listentrace.domain.services import quick_practice_recommendation as recommendation


def _stats(cue_id, position, **kwargs):
    return recommendation.CueEvidenceStats(subtitle_cue_id=cue_id, position=position, **kwargs)


def test_cue_with_no_evidence_has_no_reasons():
    stats = _stats(1, 0)
    assert recommendation.evaluate_cue(stats) == ()


def test_little_shadowing_practice_never_qualifies_alone():
    """Every fresh cue trivially has zero shadowing practice — this must
    never be enough by itself to "qualify" a cue, or the safe-fallback
    behavior below would never trigger."""
    stats = _stats(1, 0, shadowing_practice_count=0)
    assert recommendation.evaluate_cue(stats) == ()


def test_little_shadowing_practice_amplifies_a_genuine_reason():
    stats = _stats(1, 0, annotation_labels=frozenset({"misheard"}), shadowing_practice_count=0)
    reasons = recommendation.evaluate_cue(stats)
    assert recommendation.REASON_MARKED_MISHEARD in reasons
    assert recommendation.REASON_LITTLE_SHADOWING_PRACTICE in reasons


def test_each_annotation_label_maps_to_its_own_reason():
    stats = _stats(
        1, 0, annotation_labels=frozenset({"misheard", "known_not_heard", "connected_reduced_speech"})
    )
    reasons = recommendation.evaluate_cue(stats)
    assert recommendation.REASON_MARKED_MISHEARD in reasons
    assert recommendation.REASON_MARKED_KNOWN_NOT_HEARD in reasons
    assert recommendation.REASON_MARKED_CONNECTED_REDUCED_SPEECH in reasons


def test_incorrect_quiz_evidence_reason():
    # shadowing_practice_count=1 isolates the reason under test — a default
    # of 0 would also trigger the amplifying "little shadowing" reason.
    stats = _stats(1, 0, has_incorrect_quiz_evidence=True, shadowing_practice_count=1)
    assert recommendation.evaluate_cue(stats) == (recommendation.REASON_INCORRECT_QUIZ_EVIDENCE,)


def test_recurring_diagnosis_threshold():
    below = _stats(1, 0, diagnosis_evidence_count=recommendation.RECURRING_DIAGNOSIS_THRESHOLD - 1, shadowing_practice_count=1)
    at = _stats(1, 0, diagnosis_evidence_count=recommendation.RECURRING_DIAGNOSIS_THRESHOLD, shadowing_practice_count=1)
    assert recommendation.evaluate_cue(below) == ()
    assert recommendation.evaluate_cue(at) == (recommendation.REASON_RECURRING_DIAGNOSIS,)


def test_recommend_cues_prioritizes_more_reasons_first():
    one_reason = _stats(1, 0, has_incorrect_quiz_evidence=True)
    two_reasons = _stats(2, 1, has_incorrect_quiz_evidence=True, annotation_labels=frozenset({"misheard"}))
    result = recommendation.recommend_cues([one_reason, two_reasons], 2)
    assert [r.subtitle_cue_id for r in result] == [2, 1]


def test_recommend_cues_breaks_ties_by_most_recent_evidence_then_position():
    older = _stats(1, 0, has_incorrect_quiz_evidence=True, most_recent_evidence_at="2026-01-01 00:00:00")
    newer = _stats(2, 1, has_incorrect_quiz_evidence=True, most_recent_evidence_at="2026-06-01 00:00:00")
    result = recommendation.recommend_cues([older, newer], 2)
    assert [r.subtitle_cue_id for r in result] == [2, 1]


def test_recommend_cues_falls_back_safely_when_insufficient_evidence():
    """With no qualifying evidence anywhere, the fallback fills the
    requested count from material order and every entry has no reasons —
    a visible, honest fallback rather than a lowered threshold."""
    stats = [_stats(cue_id, position) for position, cue_id in enumerate([10, 20, 30, 40])]
    result = recommendation.recommend_cues(stats, 3)
    assert [r.subtitle_cue_id for r in result] == [10, 20, 30]
    assert all(r.reasons == () for r in result)


def test_recommend_cues_fills_remaining_slots_after_partial_qualification():
    qualifying = _stats(5, 4, has_incorrect_quiz_evidence=True)
    fallback_candidates = [_stats(cue_id, position) for position, cue_id in enumerate([1, 2, 3])]
    result = recommendation.recommend_cues([qualifying, *fallback_candidates], 3)
    assert result[0].subtitle_cue_id == 5
    assert result[0].reasons != ()
    assert [r.subtitle_cue_id for r in result[1:]] == [1, 2]
    assert all(r.reasons == () for r in result[1:])


def test_recommend_cues_never_exceeds_available_cues():
    stats = [_stats(1, 0)]
    result = recommendation.recommend_cues(stats, 5)
    assert len(result) == 1


def test_recommend_cues_zero_count_returns_empty():
    stats = [_stats(1, 0)]
    assert recommendation.recommend_cues(stats, 0) == []

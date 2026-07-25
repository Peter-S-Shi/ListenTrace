from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.annotation_label import AnnotationLabel

# Pure, framework-free "Recommended Practice" cue selection for Milestone 10.
# Deliberately reason-based, not score-based: every recommended cue carries
# the visible, independently-named reason(s) it qualified for (mirroring
# `needs_attention_rules.py`'s "transparent reasons, never one composite
# score" pattern) — there is no hidden ability/difficulty/priority number
# anywhere in this module.

REASON_RECENT_MISHEARD = "recent_misheard"
REASON_RECENT_KNOWN_NOT_HEARD = "recent_known_not_heard"
REASON_RECENT_CONNECTED_REDUCED_SPEECH = "recent_connected_reduced_speech"
REASON_INCORRECT_QUIZ_EVIDENCE = "incorrect_quiz_evidence"
REASON_RECURRING_DIAGNOSIS = "recurring_diagnosis_history"
REASON_LITTLE_SHADOWING_PRACTICE = "little_or_no_shadowing_practice"

RECURRING_DIAGNOSIS_THRESHOLD = 2
"""A cue with at least this many session-diagnosis-evidence occurrences
(across any number of sessions) counts as having "recurring diagnosis
history"."""

_LABEL_REASON_BY_KEY: dict[str, str] = {
    AnnotationLabel.MISHEARD.value: REASON_RECENT_MISHEARD,
    AnnotationLabel.KNOWN_NOT_HEARD.value: REASON_RECENT_KNOWN_NOT_HEARD,
    AnnotationLabel.CONNECTED_REDUCED_SPEECH.value: REASON_RECENT_CONNECTED_REDUCED_SPEECH,
}


@dataclass(slots=True, frozen=True)
class CueEvidenceStats:
    """Pre-aggregated, already-queried evidence for one cue. This module
    never touches a database — it only judges these numbers, the same
    separation `needs_attention_rules.evaluate_material` uses."""

    subtitle_cue_id: int
    position: int
    """The cue's stable order within the material (e.g. `cue_index`) — used
    for deterministic tie-breaking and fallback ordering."""
    annotation_labels: frozenset[str] = frozenset()
    diagnosis_evidence_count: int = 0
    has_incorrect_quiz_evidence: bool = False
    shadowing_practice_count: int = 0
    most_recent_evidence_at: str | None = None
    """The latest timestamp among this cue's qualifying evidence (any of the
    signals above), used only to order otherwise-tied recommendations —
    never surfaced as a score."""


@dataclass(slots=True, frozen=True)
class RecommendedCue:
    subtitle_cue_id: int
    reasons: tuple[str, ...]
    """Empty when this cue was included only as a safe fallback (not enough
    qualifying evidence existed to fill the requested count)."""


def evaluate_cue(stats: CueEvidenceStats) -> tuple[str, ...]:
    """The transparent list of reasons (possibly empty) this cue qualifies
    for recommendation. Never combined into one score.

    "Little or no shadowing practice" is deliberately never a *qualifying*
    reason on its own — every cue in a freshly imported material trivially
    has zero shadowing practice, which would otherwise make every cue
    "qualify" and defeat the safe-fallback behavior below. It only ever
    appears as an amplifying reason alongside at least one genuine
    struggle signal (a diagnosis label, incorrect quiz evidence, or
    recurring diagnosis history)."""
    reasons: list[str] = []
    for label_key, reason in _LABEL_REASON_BY_KEY.items():
        if label_key in stats.annotation_labels:
            reasons.append(reason)
    if stats.has_incorrect_quiz_evidence:
        reasons.append(REASON_INCORRECT_QUIZ_EVIDENCE)
    if stats.diagnosis_evidence_count >= RECURRING_DIAGNOSIS_THRESHOLD:
        reasons.append(REASON_RECURRING_DIAGNOSIS)
    if reasons and stats.shadowing_practice_count == 0:
        reasons.append(REASON_LITTLE_SHADOWING_PRACTICE)
    return tuple(reasons)


def recommend_cues(stats: list[CueEvidenceStats], count: int) -> list[RecommendedCue]:
    """Deterministic, transparent recommendation of up to `count` cues.

    Cues with at least one qualifying reason are ranked (most reasons first,
    then most recent qualifying evidence, then material order) and taken
    first. If fewer than `count` cues qualify, the remaining slots are
    safely filled with the next cues in material order that were not
    already selected, carrying no reasons — a documented, visible fallback
    rather than a lowered or hidden threshold."""
    if count <= 0:
        return []

    evaluated = [(s, evaluate_cue(s)) for s in stats]
    qualifying = [(s, reasons) for s, reasons in evaluated if reasons]

    # Stable, ascending sorts applied lowest-priority-first so the final
    # order is: most reasons, then most recent evidence, then material
    # position — without needing a composite sort key.
    qualifying.sort(key=lambda pair: pair[0].position)
    qualifying.sort(key=lambda pair: pair[0].most_recent_evidence_at or "", reverse=True)
    qualifying.sort(key=lambda pair: len(pair[1]), reverse=True)

    selected = qualifying[:count]
    if len(selected) < count:
        selected_ids = {s.subtitle_cue_id for s, _ in selected}
        fallback = sorted(
            (s for s in stats if s.subtitle_cue_id not in selected_ids),
            key=lambda s: s.position,
        )
        for s in fallback:
            if len(selected) >= count:
                break
            selected.append((s, ()))

    return [RecommendedCue(subtitle_cue_id=s.subtitle_cue_id, reasons=reasons) for s, reasons in selected]

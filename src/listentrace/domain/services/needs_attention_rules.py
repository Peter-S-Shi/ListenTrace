from __future__ import annotations

from dataclasses import dataclass, field

# Named, centralized thresholds — deliberately simple and explainable rather
# than blended into one composite score. Each is independently documented so
# a "Needs Attention" reason can always point to the exact rule that fired.

LOW_ACCURACY_THRESHOLD = 0.6
"""A material's recent-quiz-accuracy average below this fraction (60%) counts
as "low recent quiz accuracy"."""

RECENT_QUIZ_ATTEMPT_WINDOW = 3
""""Recent" quiz accuracy = the average of at most this many of the most
recently completed attempts, newest first."""

REPEATED_DIAGNOSIS_THRESHOLD = 3
"""A single diagnosis category recurring at least this many times across a
material's session-diagnosis-evidence history counts as "repeated"."""

ABANDONED_SESSION_THRESHOLD = 2
"""At least this many abandoned intensive-practice sessions counts as
"multiple abandoned sessions"."""

FREQUENTLY_REVISITED_SESSION_THRESHOLD = 3
"""At least this many total intensive-practice sessions (any status) counts
as "frequently revisited material"."""

MANY_SKIPPED_STAGES_THRESHOLD = 2
"""A single session with at least this many skipped stages counts as "many
skipped stages"."""


@dataclass(slots=True, frozen=True)
class MaterialActivityStats:
    """Pre-aggregated, already-queried evidence for one material. This module
    never touches a database or a UI widget — it only judges these numbers."""

    material_id: int
    recent_quiz_accuracies: tuple[float, ...] = ()
    """Fractions in [0, 1], newest-completed-attempt first."""
    diagnosis_label_counts: dict[str, int] = field(default_factory=dict)
    """label_key -> total session_diagnosis_evidence occurrences for this material."""
    abandoned_session_count: int = 0
    total_session_count: int = 0
    active_session_count: int = 0
    skipped_stage_counts_by_session: tuple[int, ...] = ()
    """One entry per completed/abandoned session: how many of its stages were skipped."""


@dataclass(slots=True, frozen=True)
class NeedsAttentionReason:
    reason_key: str
    detail: str


def evaluate_material(stats: MaterialActivityStats) -> list[NeedsAttentionReason]:
    """Return the transparent list of reasons (possibly empty) this material
    appears in "Needs Attention". Never combines these into a single score —
    the caller decides whether "any reason" is enough to list the material."""
    reasons: list[NeedsAttentionReason] = []

    recent = stats.recent_quiz_accuracies[:RECENT_QUIZ_ATTEMPT_WINDOW]
    if recent:
        average = sum(recent) / len(recent)
        if average < LOW_ACCURACY_THRESHOLD:
            reasons.append(
                NeedsAttentionReason(
                    "low_recent_quiz_accuracy",
                    f"Average accuracy over the last {len(recent)} completed quiz "
                    f"attempt(s): {average:.0%} (below {LOW_ACCURACY_THRESHOLD:.0%}).",
                )
            )

    repeated_labels = [
        (label, count)
        for label, count in sorted(stats.diagnosis_label_counts.items())
        if count >= REPEATED_DIAGNOSIS_THRESHOLD
    ]
    if repeated_labels:
        detail = ", ".join(f"{label} ({count}x)" for label, count in repeated_labels)
        reasons.append(NeedsAttentionReason("repeated_diagnosis_evidence", f"Repeated diagnosis evidence: {detail}."))

    if stats.abandoned_session_count >= ABANDONED_SESSION_THRESHOLD:
        reasons.append(
            NeedsAttentionReason(
                "multiple_abandoned_sessions",
                f"{stats.abandoned_session_count} abandoned intensive-practice session(s).",
            )
        )

    if stats.total_session_count >= FREQUENTLY_REVISITED_SESSION_THRESHOLD:
        reasons.append(
            NeedsAttentionReason(
                "frequently_revisited_material",
                f"{stats.total_session_count} total intensive-practice session(s) on this material.",
            )
        )

    many_skipped = [n for n in stats.skipped_stage_counts_by_session if n >= MANY_SKIPPED_STAGES_THRESHOLD]
    if many_skipped:
        reasons.append(
            NeedsAttentionReason(
                "many_skipped_stages",
                f"{len(many_skipped)} session(s) skipped {MANY_SKIPPED_STAGES_THRESHOLD}+ stages.",
            )
        )

    if stats.active_session_count > 0:
        reasons.append(
            NeedsAttentionReason(
                "active_unfinished_session",
                f"{stats.active_session_count} active session(s) not yet completed.",
            )
        )

    return reasons

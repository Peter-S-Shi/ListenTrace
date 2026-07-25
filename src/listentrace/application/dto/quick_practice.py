from __future__ import annotations

from dataclasses import dataclass, field

from listentrace.domain.models.quick_practice_diagnosis_evidence import QuickPracticeDiagnosisEvidence
from listentrace.domain.models.quick_practice_item import QuickPracticeItem
from listentrace.domain.models.quick_practice_session import QuickPracticeSession


@dataclass(slots=True, frozen=True)
class QuickPracticeItemState:
    item: QuickPracticeItem
    diagnosis: list[QuickPracticeDiagnosisEvidence] = field(default_factory=list)


@dataclass(slots=True)
class QuickPracticeSessionState:
    """Full in-memory state for one Quick Practice run. There is
    deliberately no "current item index" persisted anywhere (see
    `ROADMAP.md`/`ARCHITECTURE.md`: Quick Practice has no exact-step
    resume) — the UI tracks its own position within `items` for the
    lifetime of the window only."""

    session: QuickPracticeSession
    items: list[QuickPracticeItemState] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class RecommendedCueEntry:
    subtitle_cue_id: int
    reasons: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class QuickPracticeCompletionSummary:
    """A concise, read-only run summary — deliberately has no effective-
    time, pronunciation, ability, difficulty, or improvement score field
    anywhere on this type (see ROADMAP.md)."""

    cues_completed: int
    understood_count: int
    partly_understood_count: int
    missed_count: int
    diagnoses_created: int
    shadowing_actions: int
    recordings_created: int
    cues_worth_revisiting: list[int] = field(default_factory=list)
    """subtitle_cue_ids with a Missed recall result or at least one
    diagnosis recorded during this run — evidence for the learner to
    revisit, never a difficulty score."""

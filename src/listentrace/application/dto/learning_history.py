from __future__ import annotations

from dataclasses import dataclass, field

from listentrace.domain.services.needs_attention_rules import NeedsAttentionReason


@dataclass(slots=True, frozen=True)
class OverviewMetrics:
    """Every field here has a single, fixed calculation rule (see
    `learning_history_service.get_overview`) — there is deliberately no
    combined learning/difficulty/improvement score anywhere on this type."""

    materials_practiced: int
    completed_sessions: int
    active_sessions: int
    abandoned_sessions: int
    completed_quizzes: int
    average_quiz_accuracy: float | None
    """Macro-average across completed quiz attempts in scope; `None` means
    zero completed attempts, never displayed as 0%."""
    session_diagnosis_evidence_count: int
    shadowing_practice_count: int
    """Sum of cumulative practice_count over shadowed cues in scope — an
    approximation under a date filter (see ARCHITECTURE.md); exact for
    All Time."""
    retained_recording_count: int
    retained_recording_total_duration_ms: int


@dataclass(slots=True, frozen=True)
class ActivityItem:
    activity_type: str  # "session" | "quiz" | "diagnosis" | "shadowing" | "recording"
    occurred_at: str
    material_id: int
    material_title: str
    ref_id: int
    subtitle_cue_id: int | None
    label_key: str | None
    status: str | None
    quiz_mode: str | None
    session_id: int | None
    summary: str


@dataclass(slots=True, frozen=True)
class StageOutcomeSummary:
    stage_key: str
    status: str
    skip_note: str | None


@dataclass(slots=True, frozen=True)
class SessionHistoryEntry:
    session_id: int
    material_id: int
    material_title: str
    status: str
    current_stage: str
    started_at: str
    completed_at: str | None
    abandoned_at: str | None
    last_resumed_at: str
    stages: list[StageOutcomeSummary] = field(default_factory=list)

    @property
    def completed_stage_count(self) -> int:
        return sum(1 for s in self.stages if s.status == "completed")

    @property
    def skipped_stage_count(self) -> int:
        return sum(1 for s in self.stages if s.status == "skipped")

    @property
    def incomplete_stage_count(self) -> int:
        return sum(1 for s in self.stages if s.status in ("not_started", "in_progress"))


@dataclass(slots=True, frozen=True)
class DiagnosisCategorySummary:
    """Evidence, not a verdict: presented for the learner to interpret — never
    labeled as "improving" or "regressing" (see ARCHITECTURE.md)."""

    label_key: str
    occurrence_count: int
    session_count: int
    material_count: int
    most_recent_at: str


@dataclass(slots=True, frozen=True)
class QuestionTypeBreakdown:
    question_type: str
    question_count: int
    correct_count: int


@dataclass(slots=True, frozen=True)
class QuizHistoryEntry:
    attempt_id: int
    material_id: int
    material_title: str
    quiz_mode: str
    status: str
    started_at: str
    completed_at: str | None
    correct_count: int | None
    actual_count: int
    accuracy: float | None
    breakdown: list[QuestionTypeBreakdown] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class QuizComparisonGroup:
    """Grouped by (material, quiz_mode) only — different materials and
    different modes are never combined into one comparable series."""

    material_id: int
    material_title: str
    quiz_mode: str
    entries: list[QuizHistoryEntry] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class NeedsAttentionEntry:
    material_id: int
    material_title: str
    reasons: list[NeedsAttentionReason] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ShadowingEvidenceEntry:
    material_id: int
    material_title: str
    subtitle_cue_id: int
    cue_text: str
    session_id: int
    practice_count: int
    last_practiced_at: str | None
    note: str | None


@dataclass(slots=True, frozen=True)
class RecordingEvidenceEntry:
    recording_id: int
    material_id: int
    material_title: str
    subtitle_cue_id: int
    cue_text: str
    practice_session_id: int | None
    duration_ms: int | None
    created_at: str


@dataclass(slots=True, frozen=True)
class RecordingEvidenceSummary:
    entries: list[RecordingEvidenceEntry]
    total_duration_ms: int


@dataclass(slots=True, frozen=True)
class ChartPoint:
    label: str
    value: float


@dataclass(slots=True, frozen=True)
class ChartData:
    """Every chart has a plain tabular equivalent: `points` IS the table —
    the chart widget only paints it, never computes anything extra."""

    title: str
    points: list[ChartPoint] = field(default_factory=list)

from __future__ import annotations

from dataclasses import dataclass, field

from listentrace.domain.models.keyword_capture import KeywordCapture
from listentrace.domain.models.practice_session import PracticeSession
from listentrace.domain.models.session_diagnosis_evidence import SessionDiagnosisEvidence
from listentrace.domain.models.session_stage_progress import SessionStageProgress
from listentrace.domain.models.shadowing_cue_progress import ShadowingCueProgress


@dataclass(slots=True)
class PracticeSessionState:
    """Full resumable state for a guided intensive-listening session."""

    session: PracticeSession
    stage_progress: dict[str, SessionStageProgress] = field(default_factory=dict)
    stage_responses: dict[str, dict[str, str]] = field(default_factory=dict)
    keyword_captures: list[KeywordCapture] = field(default_factory=list)
    session_diagnosis: list[SessionDiagnosisEvidence] = field(default_factory=list)
    shadowing_progress: list[ShadowingCueProgress] = field(default_factory=list)

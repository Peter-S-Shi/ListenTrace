from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from listentrace.domain.models.quiz_attempt import QuizAttempt


@dataclass(slots=True)
class QuizReviewItem:
    """One consolidated-review row: the learner's answer, the correct answer, and
    enough context to render it, all read from stored snapshots — never re-derived
    from live cue/annotation text."""

    question_id: int
    position: int
    question_type: str
    subtitle_cue_id: int
    prompt: dict[str, Any]
    correct_answer: dict[str, Any]
    raw_answer_text: str | None
    normalized_answer_text: str | None
    selected_choice_index: int | None
    is_correct: bool
    explanation: str


@dataclass(slots=True)
class QuizReviewResult:
    attempt: QuizAttempt
    items: list[QuizReviewItem]

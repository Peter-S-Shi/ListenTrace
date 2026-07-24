from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.answered_state import AnsweredState


@dataclass(slots=True)
class QuizAnswer:
    quiz_question_id: int
    raw_answer_text: str | None = None
    normalized_answer_text: str | None = None
    selected_choice_index: int | None = None
    is_correct: bool | None = None
    answered_state: str = AnsweredState.UNANSWERED.value
    answered_at: str | None = None
    id: int | None = None

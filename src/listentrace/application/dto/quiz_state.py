from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.models.quiz_answer import QuizAnswer
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion


@dataclass(slots=True)
class QuizState:
    attempt: QuizAttempt
    questions: list[QuizQuestion]
    answers: dict[int, QuizAnswer]  # keyed by quiz_question_id

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuizQuestion:
    question_type: str
    subtitle_cue_id: int
    prompt_payload: str
    correct_answer_payload: str
    scoring_config: str
    # `quiz_attempt_id`/`position` are unknown while a question is still being
    # generated in memory (before `quiz_repository.create_quiz_attempt_with_questions`
    # assigns the real attempt id and position) — placeholders here, real values
    # once round-tripped through the database.
    quiz_attempt_id: int = 0
    position: int = 0
    source_annotation_id: int | None = None
    source_saved_item_id: int | None = None
    source_keyword_capture_id: int | None = None
    id: int | None = None

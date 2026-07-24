from __future__ import annotations

from enum import Enum


class QuestionType(str, Enum):
    DICTATION = "dictation"
    KEYWORD_RECOGNITION = "keyword_recognition"
    AUDIO_TRANSCRIPT_CHOICE = "audio_transcript_choice"
    REVIEW_MISSED = "review_missed"


# Question types eligible for a Material Quiz (built only from usable cues).
MATERIAL_QUESTION_TYPES: tuple[str, ...] = (
    QuestionType.DICTATION.value,
    QuestionType.KEYWORD_RECOGNITION.value,
    QuestionType.AUDIO_TRANSCRIPT_CHOICE.value,
)

# The only question type a Review Quiz produces: it always targets a specific
# piece of saved diagnosis evidence.
REVIEW_QUESTION_TYPE: str = QuestionType.REVIEW_MISSED.value

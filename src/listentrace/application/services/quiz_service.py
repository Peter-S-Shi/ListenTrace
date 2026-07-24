from __future__ import annotations

import json
import random
import sqlite3

from listentrace.application.dto.quiz_review import QuizReviewItem, QuizReviewResult
from listentrace.application.dto.quiz_state import QuizState
from listentrace.application.errors import (
    QuizNotFoundError,
    QuizQuestionNotFoundError,
    QuizValidationError,
)
from listentrace.domain.enums.question_type import (
    MATERIAL_QUESTION_TYPES,
    REVIEW_QUESTION_TYPE,
    QuestionType,
)
from listentrace.domain.enums.quiz_mode import QuizMode
from listentrace.domain.enums.quiz_status import QuizStatus
from listentrace.domain.models.annotation import Annotation
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion
from listentrace.domain.models.saved_language_item import SavedLanguageItem
from listentrace.domain.models.subtitle import SubtitleCue
from listentrace.domain.services import quiz_rules as rules
from listentrace.infrastructure.db import quiz_repository as repo
from listentrace.infrastructure.db.learning_repository import (
    list_annotations_for_material,
    list_saved_items_for_material,
)
from listentrace.infrastructure.db.repository import get_cues_for_track, get_subtitle_track_for_material
from listentrace.infrastructure.db.session_repository import list_keyword_captures_for_material

_TEXT_SCORING_TYPES = frozenset({QuestionType.DICTATION.value, QuestionType.REVIEW_MISSED.value})
_TARGET_TEXT_SCORING_RULE = "normalized_text_exact"
_TARGET_CHOICE_SCORING_RULE = "exact_choice_index"

_SEED_UPPER_BOUND = 2**31 - 1


# ---- internal guards ----


def _require_attempt(conn: sqlite3.Connection, attempt_id: int) -> QuizAttempt:
    attempt = repo.get_quiz_attempt(conn, attempt_id)
    if attempt is None:
        raise QuizNotFoundError(attempt_id)
    return attempt


def _require_active_attempt(conn: sqlite3.Connection, attempt_id: int) -> QuizAttempt:
    attempt = _require_attempt(conn, attempt_id)
    if attempt.status != QuizStatus.ACTIVE.value:
        raise QuizValidationError("quiz_not_active", "This quiz is read-only (completed or abandoned).")
    return attempt


def _new_seed() -> int:
    return random.SystemRandom().randrange(1, _SEED_UPPER_BOUND)


# ---- lifecycle ----


def list_quiz_attempts_for_material(conn: sqlite3.Connection, material_id: int) -> list[QuizAttempt]:
    return repo.list_quiz_attempts_for_material(conn, material_id)


def find_active_quizzes_for_material(conn: sqlite3.Connection, material_id: int) -> list[QuizAttempt]:
    return repo.list_active_quiz_attempts_for_material(conn, material_id)


def get_quiz_attempt(conn: sqlite3.Connection, attempt_id: int) -> QuizAttempt | None:
    return repo.get_quiz_attempt(conn, attempt_id)


def resume_quiz(conn: sqlite3.Connection, attempt_id: int) -> QuizState:
    attempt = _require_attempt(conn, attempt_id)
    if attempt.status != QuizStatus.ACTIVE.value:
        raise QuizValidationError("quiz_not_active", "Only an active quiz can be resumed.")
    repo.touch_quiz_resumed(conn, attempt_id)
    return load_quiz_state(conn, attempt_id)


def load_quiz_state(conn: sqlite3.Connection, attempt_id: int) -> QuizState:
    attempt = _require_attempt(conn, attempt_id)
    questions = repo.list_quiz_questions(conn, attempt_id)
    answers = repo.list_quiz_answers_for_attempt(conn, attempt_id)
    return QuizState(attempt=attempt, questions=questions, answers=answers)


def abandon_quiz(conn: sqlite3.Connection, attempt_id: int) -> None:
    attempt = _require_attempt(conn, attempt_id)
    if not rules.is_valid_quiz_transition(attempt.status, QuizStatus.ABANDONED.value):
        raise QuizValidationError("invalid_transition", f"Cannot abandon a quiz with status {attempt.status!r}.")
    repo.set_quiz_status(conn, attempt_id, QuizStatus.ABANDONED.value)


def save_quiz_answer(
    conn: sqlite3.Connection,
    attempt_id: int,
    question_id: int,
    raw_answer_text: str | None = None,
    selected_choice_index: int | None = None,
) -> None:
    """Persists the learner's in-progress answer. Never computes or reveals
    correctness — that only ever happens atomically in `submit_quiz`."""
    _require_active_attempt(conn, attempt_id)
    question = repo.get_quiz_question(conn, question_id)
    if question is None or question.quiz_attempt_id != attempt_id:
        raise QuizQuestionNotFoundError(question_id)
    normalized = rules.normalize_answer_text(raw_answer_text) if raw_answer_text is not None else None
    repo.save_quiz_answer(conn, question_id, raw_answer_text, normalized, selected_choice_index)


def submit_quiz(conn: sqlite3.Connection, attempt_id: int) -> None:
    """Scores every question atomically and marks the attempt `completed`. This is
    the only place correctness is ever computed — answers stay hidden until this
    runs, and it runs as a single all-or-nothing transaction."""
    attempt = _require_active_attempt(conn, attempt_id)
    if not rules.is_valid_quiz_transition(attempt.status, QuizStatus.COMPLETED.value):
        raise QuizValidationError("invalid_transition", f"Cannot submit a quiz with status {attempt.status!r}.")
    questions = repo.list_quiz_questions(conn, attempt_id)
    if not questions:
        raise QuizValidationError("quiz_empty", "This quiz has no questions to score.")

    try:
        correct_count = 0
        for question in questions:
            answer = repo.get_quiz_answer(conn, question.id)
            correct_payload = json.loads(question.correct_answer_payload)
            if question.question_type in _TEXT_SCORING_TYPES:
                raw = answer.raw_answer_text if answer is not None else None
                is_correct = raw is not None and rules.is_text_answer_correct(
                    raw, correct_payload["normalized_answer_text"]
                )
            else:
                selected = answer.selected_choice_index if answer is not None else None
                is_correct = selected is not None and selected == correct_payload["correct_choice_index"]
            repo.set_quiz_answer_correctness(conn, question.id, is_correct)
            if is_correct:
                correct_count += 1
        repo.finalize_quiz_score(conn, attempt_id, correct_count)
    except Exception:
        conn.rollback()
        raise
    conn.commit()


def build_quiz_review(conn: sqlite3.Connection, attempt_id: int) -> QuizReviewResult:
    attempt = _require_attempt(conn, attempt_id)
    if attempt.status != QuizStatus.COMPLETED.value:
        raise QuizValidationError(
            "quiz_not_completed", "The consolidated review is available only after a quiz is submitted."
        )
    questions = repo.list_quiz_questions(conn, attempt_id)
    answers = repo.list_quiz_answers_for_attempt(conn, attempt_id)

    items: list[QuizReviewItem] = []
    for question in questions:
        answer = answers.get(question.id)
        scoring = json.loads(question.scoring_config)
        items.append(
            QuizReviewItem(
                question_id=question.id,
                position=question.position,
                question_type=question.question_type,
                subtitle_cue_id=question.subtitle_cue_id,
                prompt=json.loads(question.prompt_payload),
                correct_answer=json.loads(question.correct_answer_payload),
                raw_answer_text=answer.raw_answer_text if answer is not None else None,
                normalized_answer_text=answer.normalized_answer_text if answer is not None else None,
                selected_choice_index=answer.selected_choice_index if answer is not None else None,
                is_correct=bool(answer.is_correct) if answer is not None and answer.is_correct is not None else False,
                explanation=_explanation_for_scoring_rule(scoring.get("rule")),
            )
        )
    return QuizReviewResult(attempt=attempt, items=items)


def _explanation_for_scoring_rule(rule: str | None) -> str:
    if rule == _TARGET_TEXT_SCORING_RULE:
        return (
            "Scored by matching text: case, punctuation, and extra whitespace are "
            "ignored, but spelling must otherwise match exactly."
        )
    if rule == _TARGET_CHOICE_SCORING_RULE:
        return "Scored by matching the selected choice to the one correct choice."
    return ""


# ---- quiz creation: Material Quiz ----


def create_material_quiz(
    conn: sqlite3.Connection, material_id: int, requested_count: int, seed: int | None = None
) -> QuizAttempt:
    if requested_count <= 0:
        raise QuizValidationError("invalid_requested_count", "Requested question count must be positive.")

    cues = _material_cues(conn, material_id)
    usable_cues = [cue for cue in cues if cue.id is not None and rules.is_cue_usable_for_quiz(cue.text)]
    if not usable_cues:
        raise QuizValidationError("no_usable_cues", "This material has no cues with usable text to quiz from.")

    actual_seed = seed if seed is not None else _new_seed()
    rng = random.Random(actual_seed)

    shuffled_cues = list(usable_cues)
    rng.shuffle(shuffled_cues)

    saved_items = list_saved_items_for_material(conn, material_id)
    annotations = list_annotations_for_material(conn, material_id)
    keyword_captures = list_keyword_captures_for_material(conn, material_id)

    questions: list[QuizQuestion] = []
    for cue in shuffled_cues:
        if len(questions) >= requested_count:
            break
        question = _generate_material_question_for_cue(
            cue, usable_cues, saved_items, annotations, keyword_captures, rng
        )
        if question is not None:
            questions.append(question)

    if not questions:
        raise QuizValidationError(
            "no_meaningful_questions", "No meaningful questions could be generated for this material."
        )

    attempt = QuizAttempt(
        material_id=material_id, quiz_mode=QuizMode.MATERIAL.value, seed=actual_seed, requested_count=requested_count
    )
    attempt_id, _ = repo.create_quiz_attempt_with_questions(conn, attempt, questions)
    created = repo.get_quiz_attempt(conn, attempt_id)
    assert created is not None
    return created


def _material_cues(conn: sqlite3.Connection, material_id: int) -> list[SubtitleCue]:
    track = get_subtitle_track_for_material(conn, material_id)
    if track is None or track.id is None:
        return []
    return get_cues_for_track(conn, track.id)


def _generate_material_question_for_cue(
    cue: SubtitleCue,
    all_cues: list[SubtitleCue],
    saved_items: list[SavedLanguageItem],
    annotations: list[Annotation],
    keyword_captures,
    rng: random.Random,
) -> QuizQuestion | None:
    type_order = list(MATERIAL_QUESTION_TYPES)
    rng.shuffle(type_order)
    for question_type in type_order:
        if question_type == QuestionType.DICTATION.value:
            question = _try_build_dictation(cue, rng)
        elif question_type == QuestionType.KEYWORD_RECOGNITION.value:
            question = _try_build_keyword_recognition(cue, all_cues, saved_items, annotations, keyword_captures, rng)
        else:
            question = _try_build_audio_transcript_choice(cue, all_cues, rng)
        if question is not None:
            return question
    return None


def _try_build_dictation(cue: SubtitleCue, rng: random.Random) -> QuizQuestion | None:
    assert cue.id is not None
    want_blank = rng.random() < 0.6
    span = rules.select_blank_span(cue.text, rng) if want_blank else None

    if span is not None:
        token, start, end = span
        masked = rules.build_masked_text(cue.text, start, end)
        answer_text = token
        prompt = {"mode": "blank", "masked_text": masked, "blank_start": start, "blank_end": end}
    else:
        answer_text = cue.text
        prompt = {"mode": "full"}

    normalized = rules.normalize_answer_text(answer_text)
    if not normalized:
        return None

    correct = {"answer_text": answer_text, "normalized_answer_text": normalized}
    scoring = {"rule": _TARGET_TEXT_SCORING_RULE, "version": 1}
    return QuizQuestion(
        question_type=QuestionType.DICTATION.value,
        subtitle_cue_id=cue.id,
        prompt_payload=json.dumps(prompt),
        correct_answer_payload=json.dumps(correct),
        scoring_config=json.dumps(scoring),
    )


def _try_build_keyword_recognition(
    cue: SubtitleCue,
    all_cues: list[SubtitleCue],
    saved_items: list[SavedLanguageItem],
    annotations: list[Annotation],
    keyword_captures,
    rng: random.Random,
) -> QuizQuestion | None:
    assert cue.id is not None
    want_positive = rng.random() < 0.5

    if want_positive:
        candidates: list[tuple[str, int | None, int | None, int | None]] = [
            (a.selected_text, a.id, None, None) for a in annotations if a.subtitle_cue_id == cue.id
        ]
        candidates += [(i.text, None, i.id, None) for i in saved_items if i.subtitle_cue_id == cue.id]
        candidates += [(tok, None, None, None) for tok, _, _ in rules.meaningful_tokens(cue.text)]
        if not candidates:
            return None
        text, annotation_id, saved_item_id, capture_id = rng.choice(candidates)
        expected = True
    else:
        candidates = [
            (tok, None, None, None)
            for other_cue in all_cues
            if other_cue.id != cue.id
            for tok, _, _ in rules.meaningful_tokens(other_cue.text)
        ]
        candidates += [(a.selected_text, a.id, None, None) for a in annotations if a.subtitle_cue_id != cue.id]
        candidates += [(i.text, None, i.id, None) for i in saved_items if i.subtitle_cue_id != cue.id]
        candidates += [(c.text, None, None, c.id) for c in keyword_captures]
        rng.shuffle(candidates)
        chosen = next((c for c in candidates if not rules.cue_contains_target(cue.text, c[0])), None)
        if chosen is None:
            return None
        text, annotation_id, saved_item_id, capture_id = chosen
        expected = False

    prompt = {"target_text": text, "choices": ["No", "Yes"]}
    correct = {"correct_choice_index": 1 if expected else 0, "target_text": text, "expected": expected}
    scoring = {"rule": _TARGET_CHOICE_SCORING_RULE, "version": 1}
    return QuizQuestion(
        question_type=QuestionType.KEYWORD_RECOGNITION.value,
        subtitle_cue_id=cue.id,
        source_annotation_id=annotation_id,
        source_saved_item_id=saved_item_id,
        source_keyword_capture_id=capture_id,
        prompt_payload=json.dumps(prompt),
        correct_answer_payload=json.dumps(correct),
        scoring_config=json.dumps(scoring),
    )


def _try_build_audio_transcript_choice(
    cue: SubtitleCue, all_cues: list[SubtitleCue], rng: random.Random
) -> QuizQuestion | None:
    assert cue.id is not None
    correct_text = cue.text
    other_texts = [other.text for other in all_cues if other.id != cue.id]
    rng.shuffle(other_texts)
    distractors = rules.build_distinct_distractors(
        correct_text, other_texts, rules.MAX_TRANSCRIPT_CHOICE_DISTRACTORS
    )
    if len(distractors) < rules.MIN_TRANSCRIPT_CHOICE_DISTRACTORS:
        return None

    choices = distractors + [correct_text]
    rng.shuffle(choices)
    correct_index = choices.index(correct_text)

    prompt = {"choices": choices}
    correct = {"correct_choice_index": correct_index, "correct_text": correct_text}
    scoring = {"rule": _TARGET_CHOICE_SCORING_RULE, "version": 1}
    return QuizQuestion(
        question_type=QuestionType.AUDIO_TRANSCRIPT_CHOICE.value,
        subtitle_cue_id=cue.id,
        prompt_payload=json.dumps(prompt),
        correct_answer_payload=json.dumps(correct),
        scoring_config=json.dumps(scoring),
    )


# ---- quiz creation: Review Quiz ----


def create_review_quiz(
    conn: sqlite3.Connection, material_id: int, requested_count: int, seed: int | None = None
) -> QuizAttempt:
    if requested_count <= 0:
        raise QuizValidationError("invalid_requested_count", "Requested question count must be positive.")

    cues_by_id = {cue.id: cue for cue in _material_cues(conn, material_id) if cue.id is not None}
    annotations = list_annotations_for_material(conn, material_id)
    priority_index = {label: i for i, label in enumerate(rules.REVIEW_LABEL_PRIORITY)}
    eligible = [
        annotation
        for annotation in annotations
        if annotation.label_key in priority_index
        and annotation.subtitle_cue_id in cues_by_id
        and rules.normalize_answer_text(annotation.selected_text)
    ]
    if not eligible:
        raise QuizValidationError(
            "no_meaningful_questions", "This material has no saved diagnosis evidence to build a review quiz from."
        )

    actual_seed = seed if seed is not None else _new_seed()
    rng = random.Random(actual_seed)

    groups: dict[int, list[Annotation]] = {}
    for annotation in eligible:
        groups.setdefault(priority_index[annotation.label_key], []).append(annotation)
    ordered: list[Annotation] = []
    for group_index in sorted(groups):
        group = groups[group_index]
        rng.shuffle(group)
        ordered.extend(group)

    questions: list[QuizQuestion] = []
    for annotation in ordered:
        if len(questions) >= requested_count:
            break
        question = _try_build_review_question(annotation, cues_by_id[annotation.subtitle_cue_id])
        if question is not None:
            questions.append(question)

    if not questions:
        raise QuizValidationError(
            "no_meaningful_questions", "No meaningful review questions could be generated for this material."
        )

    attempt = QuizAttempt(
        material_id=material_id, quiz_mode=QuizMode.REVIEW.value, seed=actual_seed, requested_count=requested_count
    )
    attempt_id, _ = repo.create_quiz_attempt_with_questions(conn, attempt, questions)
    created = repo.get_quiz_attempt(conn, attempt_id)
    assert created is not None
    return created


def _try_build_review_question(annotation: Annotation, cue: SubtitleCue) -> QuizQuestion | None:
    assert cue.id is not None and annotation.id is not None
    if annotation.selection_start < 0 or annotation.selection_end > len(cue.text):
        return None
    answer_text = cue.text[annotation.selection_start : annotation.selection_end]
    normalized = rules.normalize_answer_text(answer_text)
    if not normalized:
        return None

    masked = rules.build_masked_text(cue.text, annotation.selection_start, annotation.selection_end)
    prompt = {
        "mode": "blank",
        "masked_text": masked,
        "blank_start": annotation.selection_start,
        "blank_end": annotation.selection_end,
        "label_key": annotation.label_key,
        "heard_as": annotation.heard_as,
    }
    correct = {"answer_text": answer_text, "normalized_answer_text": normalized}
    scoring = {"rule": _TARGET_TEXT_SCORING_RULE, "version": 1}
    return QuizQuestion(
        question_type=REVIEW_QUESTION_TYPE,
        subtitle_cue_id=cue.id,
        source_annotation_id=annotation.id,
        prompt_payload=json.dumps(prompt),
        correct_answer_payload=json.dumps(correct),
        scoring_config=json.dumps(scoring),
    )

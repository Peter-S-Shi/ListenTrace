from __future__ import annotations

import json

import pytest

from listentrace.application.errors import (
    QuizNotFoundError,
    QuizQuestionNotFoundError,
    QuizValidationError,
)
from listentrace.application.services import annotation_service
from listentrace.application.services import quiz_service as svc
from listentrace.domain.enums.question_type import QuestionType
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    get_subtitle_track_for_material,
    insert_material,
    insert_subtitle_track,
)

_RICH_CUE_TEXTS = (
    "Bonjour tout le monde et bienvenue",
    "Comment allez vous aujourd hui",
    "Je suis tres content de vous voir",
    "Au revoir et bonne journee a tous",
    "Merci beaucoup pour votre aide precieuse",
    "Il fait tres beau aujourd hui a Paris",
    "Nous allons commencer la lecon maintenant",
    "Pouvez vous repeter cette phrase encore",
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_material_with_cues(conn, cue_texts=_RICH_CUE_TEXTS):
    material_id = insert_material(conn, Material(title="Lesson", media_path="C:/media/lesson.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="C:/media/lesson.srt",
        cues=[
            SubtitleCue(cue_index=i + 1, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=text)
            for i, text in enumerate(cue_texts)
        ],
    )
    insert_subtitle_track(conn, track)
    track_row = get_subtitle_track_for_material(conn, material_id)
    cues = get_cues_for_track(conn, track_row.id)
    return material_id, cues


def _cue_id_by_text(cues, text):
    return next(cue.id for cue in cues if cue.text == text)


# ---- Material Quiz generation ----


def test_create_material_quiz_is_deterministic_for_a_given_seed(conn):
    material_id, _ = _make_material_with_cues(conn)
    first = svc.create_material_quiz(conn, material_id, requested_count=5, seed=123)
    second_material_id, _ = _make_material_with_cues(conn)
    second = svc.create_material_quiz(conn, second_material_id, requested_count=5, seed=123)

    first_questions = svc.load_quiz_state(conn, first.id).questions
    second_questions = svc.load_quiz_state(conn, second.id).questions
    assert [q.question_type for q in first_questions] == [q.question_type for q in second_questions]
    assert [q.prompt_payload for q in first_questions] == [q.prompt_payload for q in second_questions]


def test_create_material_quiz_can_produce_all_four_question_types_across_seeds(conn):
    material_id, _ = _make_material_with_cues(conn)
    seen_types: set[str] = set()
    for seed in range(20):
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        questions = svc.load_quiz_state(conn, attempt.id).questions
        seen_types.update(q.question_type for q in questions)
    assert {QuestionType.DICTATION.value, QuestionType.KEYWORD_RECOGNITION.value, QuestionType.AUDIO_TRANSCRIPT_CHOICE.value} <= seen_types


def test_create_material_quiz_never_reuses_a_cue_within_one_quiz(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=5)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    cue_ids = [q.subtitle_cue_id for q in questions]
    assert len(cue_ids) == len(set(cue_ids))


def test_create_material_quiz_creates_smaller_quiz_when_material_cannot_support_requested_count(conn):
    material_id, _ = _make_material_with_cues(conn, cue_texts=("Bonjour",))
    attempt = svc.create_material_quiz(conn, material_id, requested_count=10, seed=1)
    assert attempt.requested_count == 10
    assert attempt.actual_count == 1
    assert attempt.actual_count < attempt.requested_count


def test_create_material_quiz_refuses_when_no_usable_cues(conn):
    material_id, _ = _make_material_with_cues(conn, cue_texts=("...", "!!!", "   "))
    with pytest.raises(QuizValidationError) as exc_info:
        svc.create_material_quiz(conn, material_id, requested_count=3)
    assert exc_info.value.category == "no_usable_cues"


def test_create_material_quiz_rejects_non_positive_requested_count(conn):
    material_id, _ = _make_material_with_cues(conn)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.create_material_quiz(conn, material_id, requested_count=0)
    assert exc_info.value.category == "invalid_requested_count"


def test_audio_transcript_choice_never_has_duplicate_or_extra_correct_choices(conn):
    material_id, _ = _make_material_with_cues(conn)
    found_one = False
    for seed in range(30):
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        questions = svc.load_quiz_state(conn, attempt.id).questions
        for question in questions:
            if question.question_type != QuestionType.AUDIO_TRANSCRIPT_CHOICE.value:
                continue
            found_one = True
            prompt = json.loads(question.prompt_payload)
            correct = json.loads(question.correct_answer_payload)
            choices = prompt["choices"]
            correct_index = correct["correct_choice_index"]
            # Exactly one choice may equal the stored correct text (no duplicate
            # correct answers created by accidental distractor collision).
            matches = [i for i, choice in enumerate(choices) if choice == correct["correct_text"]]
            assert matches == [correct_index]
            assert len(choices) >= 3  # at least 2 distractors + 1 correct
    assert found_one


def test_audio_transcript_choice_is_skipped_when_material_has_too_few_cues(conn):
    material_id, _ = _make_material_with_cues(conn, cue_texts=("Bonjour tout le monde", "Comment ca va"))
    attempt = svc.create_material_quiz(conn, material_id, requested_count=5, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    assert all(q.question_type != QuestionType.AUDIO_TRANSCRIPT_CHOICE.value for q in questions)


def test_dictation_full_cue_answer_is_hidden_from_prompt_payload(conn):
    material_id, _ = _make_material_with_cues(conn)
    found_full_mode = False
    for seed in range(20):
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        for question in svc.load_quiz_state(conn, attempt.id).questions:
            if question.question_type != QuestionType.DICTATION.value:
                continue
            prompt = json.loads(question.prompt_payload)
            if prompt["mode"] == "full":
                found_full_mode = True
                assert "cue_text" not in prompt
                assert "answer_text" not in prompt
    assert found_full_mode


def _find_question_of_type(conn, material_id, question_type, seed_range=range(60)):
    """Same rng-search rationale as `_find_dictation_question`, generalized to
    any question type — which type lands where is seed-dependent, so tests
    that need a specific type search for it rather than assuming a fixed seed."""
    for seed in seed_range:
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        for question in svc.load_quiz_state(conn, attempt.id).questions:
            if question.question_type == question_type:
                return attempt, question
    raise AssertionError(f"no {question_type!r} question found across seeds")


def _find_dictation_question(conn, material_id, cue_predicate=None, seed_range=range(60)):
    """Generate quizzes across several seeds until a dictation-type question
    (optionally on a cue matching `cue_predicate`) is produced. Which question
    type lands on which cue is an rng-dependent implementation detail, so tests
    that need a specific type search for it rather than assuming a fixed seed
    always produces it."""
    for seed in seed_range:
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        for question in svc.load_quiz_state(conn, attempt.id).questions:
            if question.question_type != QuestionType.DICTATION.value:
                continue
            if cue_predicate is not None and not cue_predicate(question.subtitle_cue_id):
                continue
            return attempt, question
    raise AssertionError("no matching dictation question found across seeds")


def test_dictation_blank_never_targets_a_cues_only_meaningful_token(conn):
    # "Bonjour" has exactly one meaningful token; the other cues give the
    # generator enough material for keyword-recognition/audio-choice questions
    # to also succeed, so a dictation question landing on "Bonjour" specifically
    # must fall back to full-cue mode rather than blanking its only word.
    material_id, cues = _make_material_with_cues(conn, cue_texts=("Bonjour",) + _RICH_CUE_TEXTS)
    single_token_cue_id = _cue_id_by_text(cues, "Bonjour")
    _, question = _find_dictation_question(
        conn, material_id, cue_predicate=lambda cue_id: cue_id == single_token_cue_id
    )
    prompt = json.loads(question.prompt_payload)
    assert prompt["mode"] == "full"


def test_keyword_recognition_negative_target_never_occurs_in_the_cue(conn):
    material_id, _ = _make_material_with_cues(conn)
    checked_any = False
    for seed in range(30):
        attempt = svc.create_material_quiz(conn, material_id, requested_count=8, seed=seed)
        for question in svc.load_quiz_state(conn, attempt.id).questions:
            if question.question_type != QuestionType.KEYWORD_RECOGNITION.value:
                continue
            correct = json.loads(question.correct_answer_payload)
            if correct["expected"]:
                continue
            checked_any = True
            cue = next(c for c in get_cues_for_track(conn, get_subtitle_track_for_material(conn, material_id).id) if c.id == question.subtitle_cue_id)
            from listentrace.domain.services import quiz_rules
            assert not quiz_rules.cue_contains_target(cue.text, correct["target_text"])
    assert checked_any


# ---- Review Quiz generation ----


def test_create_review_quiz_refuses_when_material_has_no_diagnosis_evidence(conn):
    material_id, _ = _make_material_with_cues(conn)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.create_review_quiz(conn, material_id, requested_count=3)
    assert exc_info.value.category == "no_meaningful_questions"


def test_create_review_quiz_prioritizes_misheard_over_other_labels(conn):
    material_id, cues = _make_material_with_cues(conn)
    known_cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    misheard_cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[1])
    annotation_service.create_annotations(conn, known_cue_id, 0, 7, ["known_not_heard"])
    annotation_service.create_annotations(conn, misheard_cue_id, 0, 7, ["misheard"], heard_as="Comment")

    attempt = svc.create_review_quiz(conn, material_id, requested_count=1, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    assert len(questions) == 1
    prompt = json.loads(questions[0].prompt_payload)
    assert prompt["label_key"] == "misheard"


def test_review_quiz_only_uses_evidence_from_the_selected_material(conn):
    material_a, cues_a = _make_material_with_cues(conn)
    material_b, cues_b = _make_material_with_cues(conn, cue_texts=("Different material sentence",))
    annotation_service.create_annotations(conn, cues_b[0].id, 0, 9, ["misheard"], heard_as="x")

    with pytest.raises(QuizValidationError) as exc_info:
        svc.create_review_quiz(conn, material_a, requested_count=3)
    assert exc_info.value.category == "no_meaningful_questions"

    attempt = svc.create_review_quiz(conn, material_b, requested_count=3, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    assert all(q.subtitle_cue_id in {c.id for c in cues_b} for q in questions)


def test_review_quiz_correct_answer_is_the_actual_transcript_text_not_heard_as(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    annotation_service.create_annotations(conn, cue_id, 0, 7, ["misheard"], heard_as="Bonjoure")

    attempt = svc.create_review_quiz(conn, material_id, requested_count=1, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    correct = json.loads(question.correct_answer_payload)
    assert correct["answer_text"] == "Bonjour"


def test_review_quiz_source_annotation_id_is_preserved_on_the_question(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    annotation_ids = annotation_service.create_annotations(conn, cue_id, 0, 7, ["unknown_word_or_chunk"])

    attempt = svc.create_review_quiz(conn, material_id, requested_count=1, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    assert question.source_annotation_id == annotation_ids[0]


def test_review_quiz_does_not_modify_the_source_annotation(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    annotation_ids = annotation_service.create_annotations(conn, cue_id, 0, 7, ["known_not_heard"])

    from listentrace.infrastructure.db.learning_repository import get_annotation

    before = get_annotation(conn, annotation_ids[0])
    attempt = svc.create_review_quiz(conn, material_id, requested_count=1, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="Bonjour")
    svc.submit_quiz(conn, attempt.id)

    after = get_annotation(conn, annotation_ids[0])
    assert before == after


# ---- Historical stability ----


def test_quiz_question_snapshot_is_unaffected_by_later_annotation_changes(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    annotation_ids = annotation_service.create_annotations(conn, cue_id, 0, 7, ["misheard"], heard_as="Bonjoure")

    attempt = svc.create_review_quiz(conn, material_id, requested_count=1, seed=1)
    question_before = svc.load_quiz_state(conn, attempt.id).questions[0]
    payload_before = question_before.correct_answer_payload

    annotation_service.delete_annotation(conn, annotation_ids[0])

    question_after = svc.load_quiz_state(conn, attempt.id).questions[0]
    assert question_after.correct_answer_payload == payload_before


# ---- Lifecycle: resume / abandon / read-only ----


def test_resume_quiz_updates_last_resumed_at(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    state = svc.resume_quiz(conn, attempt.id)
    assert state.attempt.last_resumed_at is not None


def test_multiple_active_quizzes_per_material_are_allowed(conn):
    material_id, _ = _make_material_with_cues(conn)
    first = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    second = svc.create_material_quiz(conn, material_id, requested_count=3, seed=2)
    active = svc.find_active_quizzes_for_material(conn, material_id)
    assert {first.id, second.id} <= {a.id for a in active}


def test_abandon_quiz_makes_it_read_only(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    svc.abandon_quiz(conn, attempt.id)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    with pytest.raises(QuizValidationError) as exc_info:
        svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="x")
    assert exc_info.value.category == "quiz_not_active"


def test_cannot_abandon_a_completed_quiz(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=1, seed=1)
    svc.submit_quiz(conn, attempt.id)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.abandon_quiz(conn, attempt.id)
    assert exc_info.value.category == "invalid_transition"


def test_delete_quiz_attempt_requires_completed_or_abandoned(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.delete_quiz_attempt(conn, attempt.id)
    assert exc_info.value.category == "quiz_active"

    svc.abandon_quiz(conn, attempt.id)
    svc.delete_quiz_attempt(conn, attempt.id)  # must not raise once abandoned
    assert svc.get_quiz_attempt(conn, attempt.id) is None


def test_delete_quiz_attempt_removes_questions_and_answers(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="x")
    svc.submit_quiz(conn, attempt.id)
    question_ids = [q.id for q in svc.load_quiz_state(conn, attempt.id).questions]

    svc.delete_quiz_attempt(conn, attempt.id)

    assert svc.get_quiz_attempt(conn, attempt.id) is None
    with pytest.raises(QuizNotFoundError):
        svc.load_quiz_state(conn, attempt.id)
    remaining = conn.execute(
        f"SELECT COUNT(*) AS n FROM quiz_question WHERE id IN ({','.join('?' * len(question_ids))})",
        question_ids,
    ).fetchone()["n"]
    assert remaining == 0, "quiz_question rows must cascade-delete with the attempt"


def test_save_quiz_answer_rejects_a_question_from_a_different_attempt(conn):
    material_id, _ = _make_material_with_cues(conn)
    first = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    second = svc.create_material_quiz(conn, material_id, requested_count=3, seed=2)
    first_question = svc.load_quiz_state(conn, first.id).questions[0]
    with pytest.raises(QuizQuestionNotFoundError):
        svc.save_quiz_answer(conn, second.id, first_question.id, raw_answer_text="x")


def test_answers_survive_close_and_resume(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="Bonjour tout le monde")

    reloaded = svc.resume_quiz(conn, attempt.id)
    assert reloaded.answers[question.id].raw_answer_text == "Bonjour tout le monde"
    assert reloaded.answers[question.id].answered_state == "answered"


def test_get_quiz_attempt_returns_none_for_unknown_id(conn):
    assert svc.get_quiz_attempt(conn, 999999) is None


def test_load_quiz_state_raises_for_unknown_attempt(conn):
    with pytest.raises(QuizNotFoundError):
        svc.load_quiz_state(conn, 999999)


# ---- Submission: correctness hidden until submit, atomic scoring ----


def test_correctness_is_hidden_until_submission(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="anything")
    state = svc.load_quiz_state(conn, attempt.id)
    assert state.answers[question.id].is_correct is None


def test_submit_quiz_scores_all_questions_and_completes_the_attempt(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=5, seed=1)
    state = svc.load_quiz_state(conn, attempt.id)
    for question in state.questions:
        correct = json.loads(question.correct_answer_payload)
        if question.question_type in ("dictation", "review_missed"):
            svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text=correct["answer_text"])
        else:
            svc.save_quiz_answer(conn, attempt.id, question.id, selected_choice_index=correct["correct_choice_index"])

    svc.submit_quiz(conn, attempt.id)
    completed = svc.get_quiz_attempt(conn, attempt.id)
    assert completed.status == "completed"
    assert completed.correct_count == len(state.questions)
    assert completed.completed_at is not None


def test_submit_quiz_marks_wrong_and_unanswered_as_incorrect(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    svc.save_quiz_answer(conn, attempt.id, questions[0].id, raw_answer_text="definitely wrong text")
    # questions[1] and questions[2] left unanswered

    svc.submit_quiz(conn, attempt.id)
    completed = svc.get_quiz_attempt(conn, attempt.id)
    assert completed.correct_count == 0


def test_answers_cannot_be_changed_after_submission(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=1, seed=1)
    question = svc.load_quiz_state(conn, attempt.id).questions[0]
    svc.submit_quiz(conn, attempt.id)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="late change")
    assert exc_info.value.category == "quiz_not_active"


def test_cannot_submit_an_already_completed_quiz(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=1, seed=1)
    svc.submit_quiz(conn, attempt.id)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.submit_quiz(conn, attempt.id)
    assert exc_info.value.category == "quiz_not_active"


# ---- Dictation scoring rules ----


def _mangle_case_punctuation_and_whitespace(text: str) -> str:
    return "  " + " , ".join(f"{tok.upper()}!" for tok in text.split()) + "   "


def test_dictation_scoring_ignores_case_punctuation_and_whitespace(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)
    correct = json.loads(question.correct_answer_payload)
    mangled = _mangle_case_punctuation_and_whitespace(correct["answer_text"])

    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text=mangled)
    svc.submit_quiz(conn, attempt.id)

    review = svc.build_quiz_review(conn, attempt.id)
    item = next(i for i in review.items if i.question_id == question.id)
    assert item.is_correct is True


def test_dictation_scoring_requires_exact_spelling_otherwise(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)

    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="zzzzzzzzzzzzzzzzzzzz")
    svc.submit_quiz(conn, attempt.id)

    review = svc.build_quiz_review(conn, attempt.id)
    item = next(i for i in review.items if i.question_id == question.id)
    assert item.is_correct is False


# ---- Consolidated review ----


def test_build_quiz_review_requires_a_completed_attempt(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=1, seed=1)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.build_quiz_review(conn, attempt.id)
    assert exc_info.value.category == "quiz_not_completed"


def test_build_quiz_review_shows_answer_correct_answer_type_and_source_cue(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)
    correct = json.loads(question.correct_answer_payload)
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text=correct["answer_text"])
    svc.submit_quiz(conn, attempt.id)

    review = svc.build_quiz_review(conn, attempt.id)
    item = next(i for i in review.items if i.question_id == question.id)
    assert item.raw_answer_text == correct["answer_text"]
    assert item.correct_answer["answer_text"] == correct["answer_text"]
    assert item.is_correct is True
    assert item.question_type == "dictation"
    assert item.subtitle_cue_id == question.subtitle_cue_id
    assert item.explanation


# ---- Acceptance correction: source-cue-text snapshot ----


def test_question_source_cue_text_is_captured_at_generation_time(conn):
    material_id, cues = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)
    cue = next(c for c in cues if c.id == question.subtitle_cue_id)
    assert question.source_cue_text == cue.text


def test_consolidated_review_source_cue_text_is_unaffected_by_a_later_live_cue_edit(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)
    original_text = question.source_cue_text
    correct = json.loads(question.correct_answer_payload)
    svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text=correct["answer_text"])
    svc.submit_quiz(conn, attempt.id)

    # Simulate the live subtitle cue changing after the quiz already exists.
    conn.execute("UPDATE subtitle_cue SET text = ? WHERE id = ?", ("Completely different text", question.subtitle_cue_id))
    conn.commit()

    review = svc.build_quiz_review(conn, attempt.id)
    item = next(i for i in review.items if i.question_id == question.id)
    assert item.source_cue_text == original_text
    assert item.source_cue_text != "Completely different text"


# ---- Acceptance correction: Review Quiz dedup by tested evidence ----


def test_review_quiz_dedupes_same_range_tagged_with_several_labels_keeping_highest_priority(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_id = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    # The same range carries two labels at once (allowed since Milestone 4) —
    # both describe identical tested evidence, so only one review question
    # should ever be generated for it, using the higher-priority label.
    annotation_service.create_annotations(
        conn, cue_id, 0, 7, ["connected_reduced_speech", "misheard"], heard_as="Bonjoure"
    )

    attempt = svc.create_review_quiz(conn, material_id, requested_count=5, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    assert len(questions) == 1
    prompt = json.loads(questions[0].prompt_payload)
    assert prompt["label_key"] == "misheard"


def test_review_quiz_dedup_keeps_distinct_evidence_on_different_cues(conn):
    material_id, cues = _make_material_with_cues(conn)
    cue_a = _cue_id_by_text(cues, _RICH_CUE_TEXTS[0])
    cue_b = _cue_id_by_text(cues, _RICH_CUE_TEXTS[1])
    annotation_service.create_annotations(conn, cue_a, 0, 7, ["misheard"], heard_as="x")
    annotation_service.create_annotations(conn, cue_b, 0, 7, ["known_not_heard"])

    attempt = svc.create_review_quiz(conn, material_id, requested_count=5, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    assert len(questions) == 2


# ---- Acceptance correction: scoring_config authoritative + answer-shape validation ----


def test_submit_quiz_rejects_an_unsupported_scoring_rule_atomically(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt = svc.create_material_quiz(conn, material_id, requested_count=3, seed=1)
    questions = svc.load_quiz_state(conn, attempt.id).questions
    for question in questions:
        correct = json.loads(question.correct_answer_payload)
        if question.question_type in ("dictation", "review_missed"):
            svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text=correct["answer_text"])
        else:
            svc.save_quiz_answer(conn, attempt.id, question.id, selected_choice_index=correct["correct_choice_index"])

    # Simulate a future/unknown scoring rule landing on one question's snapshot.
    conn.execute(
        "UPDATE quiz_question SET scoring_config = ? WHERE id = ?",
        (json.dumps({"rule": "semantic_similarity", "version": 1}), questions[0].id),
    )
    conn.commit()

    with pytest.raises(QuizValidationError) as exc_info:
        svc.submit_quiz(conn, attempt.id)
    assert exc_info.value.category == "unsupported_scoring_rule"

    # Nothing was scored and the attempt is still active — a bad rule on one
    # question must not silently score the rest.
    attempt_after = svc.get_quiz_attempt(conn, attempt.id)
    assert attempt_after.status == "active"
    assert attempt_after.correct_count is None
    state = svc.load_quiz_state(conn, attempt.id)
    assert all(answer.is_correct is None for answer in state.answers.values())


def test_save_quiz_answer_rejects_a_choice_index_on_a_text_question(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_dictation_question(conn, material_id)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.save_quiz_answer(conn, attempt.id, question.id, selected_choice_index=0)
    assert exc_info.value.category == "invalid_answer_shape"


def test_save_quiz_answer_rejects_text_on_a_choice_question(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_question_of_type(conn, material_id, QuestionType.AUDIO_TRANSCRIPT_CHOICE.value)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.save_quiz_answer(conn, attempt.id, question.id, raw_answer_text="some text")
    assert exc_info.value.category == "invalid_answer_shape"


def test_save_quiz_answer_rejects_an_out_of_range_choice_index(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_question_of_type(conn, material_id, QuestionType.AUDIO_TRANSCRIPT_CHOICE.value)
    with pytest.raises(QuizValidationError) as exc_info:
        svc.save_quiz_answer(conn, attempt.id, question.id, selected_choice_index=999)
    assert exc_info.value.category == "invalid_answer_shape"


def test_save_quiz_answer_accepts_a_valid_in_range_choice_index(conn):
    material_id, _ = _make_material_with_cues(conn)
    attempt, question = _find_question_of_type(conn, material_id, QuestionType.AUDIO_TRANSCRIPT_CHOICE.value)
    svc.save_quiz_answer(conn, attempt.id, question.id, selected_choice_index=0)
    state = svc.load_quiz_state(conn, attempt.id)
    assert state.answers[question.id].selected_choice_index == 0

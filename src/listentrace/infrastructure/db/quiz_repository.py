from __future__ import annotations

import sqlite3

from listentrace.domain.models.quiz_answer import QuizAnswer
from listentrace.domain.models.quiz_attempt import QuizAttempt
from listentrace.domain.models.quiz_question import QuizQuestion

# ---- row conversion ----


def _row_to_quiz_attempt(row: sqlite3.Row) -> QuizAttempt:
    return QuizAttempt(
        id=row["id"],
        material_id=row["material_id"],
        quiz_mode=row["quiz_mode"],
        status=row["status"],
        seed=row["seed"],
        requested_count=row["requested_count"],
        actual_count=row["actual_count"],
        correct_count=row["correct_count"],
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        last_resumed_at=row["last_resumed_at"],
        completed_at=row["completed_at"],
        abandoned_at=row["abandoned_at"],
    )


def _row_to_quiz_question(row: sqlite3.Row) -> QuizQuestion:
    return QuizQuestion(
        id=row["id"],
        quiz_attempt_id=row["quiz_attempt_id"],
        position=row["position"],
        question_type=row["question_type"],
        subtitle_cue_id=row["subtitle_cue_id"],
        source_annotation_id=row["source_annotation_id"],
        source_saved_item_id=row["source_saved_item_id"],
        source_keyword_capture_id=row["source_keyword_capture_id"],
        prompt_payload=row["prompt_payload"],
        correct_answer_payload=row["correct_answer_payload"],
        scoring_config=row["scoring_config"],
    )


def _row_to_quiz_answer(row: sqlite3.Row) -> QuizAnswer:
    return QuizAnswer(
        id=row["id"],
        quiz_question_id=row["quiz_question_id"],
        raw_answer_text=row["raw_answer_text"],
        normalized_answer_text=row["normalized_answer_text"],
        selected_choice_index=row["selected_choice_index"],
        is_correct=None if row["is_correct"] is None else bool(row["is_correct"]),
        answered_state=row["answered_state"],
        answered_at=row["answered_at"],
    )


# ---- quiz_attempt ----


def create_quiz_attempt_with_questions(
    conn: sqlite3.Connection, attempt: QuizAttempt, questions: list[QuizQuestion]
) -> tuple[int, list[int]]:
    """Insert the attempt, every question (in `questions` order, positions 0..n-1),
    and one eagerly-created `unanswered` `quiz_answer` row per question — all as a
    single all-or-nothing transaction, mirroring `create_practice_session`'s
    atomic multi-row pattern. A quiz is never left half-created."""
    try:
        cursor = conn.execute(
            """
            INSERT INTO quiz_attempt (material_id, quiz_mode, seed, requested_count, actual_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (attempt.material_id, attempt.quiz_mode, attempt.seed, attempt.requested_count, len(questions)),
        )
        attempt_id = int(cursor.lastrowid)

        question_ids: list[int] = []
        for position, question in enumerate(questions):
            q_cursor = conn.execute(
                """
                INSERT INTO quiz_question (
                    quiz_attempt_id, position, question_type, subtitle_cue_id,
                    source_annotation_id, source_saved_item_id, source_keyword_capture_id,
                    prompt_payload, correct_answer_payload, scoring_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    position,
                    question.question_type,
                    question.subtitle_cue_id,
                    question.source_annotation_id,
                    question.source_saved_item_id,
                    question.source_keyword_capture_id,
                    question.prompt_payload,
                    question.correct_answer_payload,
                    question.scoring_config,
                ),
            )
            question_ids.append(int(q_cursor.lastrowid))

        conn.executemany(
            "INSERT INTO quiz_answer (quiz_question_id) VALUES (?)",
            [(question_id,) for question_id in question_ids],
        )
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return attempt_id, question_ids


def get_quiz_attempt(conn: sqlite3.Connection, attempt_id: int) -> QuizAttempt | None:
    row = conn.execute("SELECT * FROM quiz_attempt WHERE id = ?", (attempt_id,)).fetchone()
    return _row_to_quiz_attempt(row) if row is not None else None


def list_quiz_attempts_for_material(conn: sqlite3.Connection, material_id: int) -> list[QuizAttempt]:
    rows = conn.execute(
        "SELECT * FROM quiz_attempt WHERE material_id = ? ORDER BY id DESC", (material_id,)
    ).fetchall()
    return [_row_to_quiz_attempt(row) for row in rows]


def list_active_quiz_attempts_for_material(conn: sqlite3.Connection, material_id: int) -> list[QuizAttempt]:
    rows = conn.execute(
        "SELECT * FROM quiz_attempt WHERE material_id = ? AND status = 'active' ORDER BY id DESC",
        (material_id,),
    ).fetchall()
    return [_row_to_quiz_attempt(row) for row in rows]


def set_quiz_status(conn: sqlite3.Connection, attempt_id: int, status: str) -> None:
    column = {"abandoned": "abandoned_at"}.get(status)
    if column is not None:
        conn.execute(
            f"UPDATE quiz_attempt SET status = ?, {column} = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (status, attempt_id),
        )
    else:
        conn.execute(
            "UPDATE quiz_attempt SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, attempt_id),
        )
    conn.commit()


def touch_quiz_resumed(conn: sqlite3.Connection, attempt_id: int) -> None:
    conn.execute(
        "UPDATE quiz_attempt SET last_resumed_at = datetime('now'), "
        "updated_at = datetime('now') WHERE id = ?",
        (attempt_id,),
    )
    conn.commit()


def finalize_quiz_score(conn: sqlite3.Connection, attempt_id: int, correct_count: int) -> None:
    """Atomically marks the attempt `completed` and records its final score.
    Callers are responsible for scoring every `quiz_answer` row first, in the
    same transaction (see `quiz_service.submit_quiz`)."""
    conn.execute(
        "UPDATE quiz_attempt SET status = 'completed', correct_count = ?, "
        "completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (correct_count, attempt_id),
    )


# ---- quiz_question ----


def get_quiz_question(conn: sqlite3.Connection, question_id: int) -> QuizQuestion | None:
    row = conn.execute("SELECT * FROM quiz_question WHERE id = ?", (question_id,)).fetchone()
    return _row_to_quiz_question(row) if row is not None else None


def list_quiz_questions(conn: sqlite3.Connection, attempt_id: int) -> list[QuizQuestion]:
    rows = conn.execute(
        "SELECT * FROM quiz_question WHERE quiz_attempt_id = ? ORDER BY position", (attempt_id,)
    ).fetchall()
    return [_row_to_quiz_question(row) for row in rows]


# ---- quiz_answer ----


def get_quiz_answer(conn: sqlite3.Connection, question_id: int) -> QuizAnswer | None:
    row = conn.execute(
        "SELECT * FROM quiz_answer WHERE quiz_question_id = ?", (question_id,)
    ).fetchone()
    return _row_to_quiz_answer(row) if row is not None else None


def list_quiz_answers_for_attempt(conn: sqlite3.Connection, attempt_id: int) -> dict[int, QuizAnswer]:
    rows = conn.execute(
        """
        SELECT quiz_answer.* FROM quiz_answer
        JOIN quiz_question ON quiz_question.id = quiz_answer.quiz_question_id
        WHERE quiz_question.quiz_attempt_id = ?
        ORDER BY quiz_question.position
        """,
        (attempt_id,),
    ).fetchall()
    return {row["quiz_question_id"]: _row_to_quiz_answer(row) for row in rows}


def save_quiz_answer(
    conn: sqlite3.Connection,
    question_id: int,
    raw_answer_text: str | None,
    normalized_answer_text: str | None,
    selected_choice_index: int | None,
) -> None:
    """Saves the learner's in-progress answer without revealing or computing
    correctness — `is_correct` is left untouched here and only ever set by
    `set_quiz_answer_correctness` during atomic submission scoring."""
    answered = raw_answer_text is not None or selected_choice_index is not None
    conn.execute(
        """
        UPDATE quiz_answer
        SET raw_answer_text = ?, normalized_answer_text = ?, selected_choice_index = ?,
            answered_state = ?, answered_at = datetime('now'), updated_at = datetime('now')
        WHERE quiz_question_id = ?
        """,
        (
            raw_answer_text,
            normalized_answer_text,
            selected_choice_index,
            "answered" if answered else "unanswered",
            question_id,
        ),
    )
    conn.commit()


def set_quiz_answer_correctness(conn: sqlite3.Connection, question_id: int, is_correct: bool) -> None:
    conn.execute(
        "UPDATE quiz_answer SET is_correct = ?, updated_at = datetime('now') WHERE quiz_question_id = ?",
        (int(is_correct), question_id),
    )

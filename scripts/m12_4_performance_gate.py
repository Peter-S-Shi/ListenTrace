"""M12.4 Performance Decision Gate.

Empirically measures Learning History's "All Materials" default view and the
related Export "All Materials" query path against privacy-safe synthetic data
at realistic personal-use scale, to decide whether HARDENING_BACKLOG.md
finding #17 (a full-table scan across 6 activity-source tables, confirmed
via EXPLAIN QUERY PLAN) actually needs a schema migration now, or can be
safely deferred to v1.0.x.

This does not, by itself, decide anything — it produces measured numbers.
The actual decision and its rationale are recorded in HARDENING_BACKLOG.md.

All data generated here is synthetic (Lorem-Ipsum-style placeholder text,
sequential IDs, randomly distributed timestamps from a seeded RNG) and lives
only in a temporary on-disk SQLite file deleted at the end of the run. No
real user data, no network access, no product code is modified.

Usage:
    .venv/Scripts/python.exe scripts/m12_4_performance_gate.py
"""

from __future__ import annotations

import random
import sqlite3
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from listentrace.application.dto.export import SCOPE_ALL, ExportScope  # noqa: E402
from listentrace.application.services import learning_history_service as history_svc  # noqa: E402
from listentrace.application.services import export_service  # noqa: E402
from listentrace.domain.services import date_range as date_range_rules  # noqa: E402
from listentrace.infrastructure.db.connection import open_connection  # noqa: E402
from listentrace.infrastructure.db.migrations import migrate  # noqa: E402

TIMESTAMP_FORMAT = date_range_rules.SQLITE_UTC_TIMESTAMP_FORMAT
RNG_SEED = 20260727

# Two tiers, both defensible as "personal, local-first, single-user" scale —
# not a multi-tenant server workload:
#   REALISTIC: a very dedicated daily learner over roughly 2 years (materials
#     imported a few per week; 1-2 Intensive Practice sessions and a quiz
#     most days; several diagnosis/shadowing events per session).
#   STRESS: 5x REALISTIC, to see whether cost grows linearly (safe to defer)
#     or worse (would argue for fixing regardless of the realistic number).
SCALES = {
    "REALISTIC (~2yr dedicated daily use)": {
        "materials": 100,
        "sessions": 1000,
        "quizzes": 800,
        "diagnosis_per_session": 8,
        "shadowing_per_session": 8,
        "recordings": 3000,
        "quick_practice_sessions": 1500,
        "quiz_questions_per_attempt": 5,
    },
    "STRESS (5x realistic)": {
        "materials": 300,
        "sessions": 5000,
        "quizzes": 4000,
        "diagnosis_per_session": 8,
        "shadowing_per_session": 8,
        "recordings": 15000,
        "quick_practice_sessions": 7500,
        "quiz_questions_per_attempt": 5,
    },
}

HISTORY_WINDOW_DAYS = 730  # ~2 years of simulated activity


def _ts(rng: random.Random, days_back_max: int) -> str:
    dt = datetime.now() - timedelta(
        days=rng.uniform(0, days_back_max), seconds=rng.uniform(0, 86400)
    )
    return dt.strftime(TIMESTAMP_FORMAT)


def compute_ground_truth(conn: sqlite3.Connection) -> dict:
    """Independently recomputes the same 7 Overview metrics directly from
    whatever actually landed in the tables, using simple, obviously-correct
    SQL deliberately written in a different shape than the production
    queries under test (no COALESCE/UNION tricks) — this is what the
    production result is checked against, not the generator's pre-insertion
    intent (which can differ from what was actually persisted, e.g. when a
    UNIQUE constraint silently drops a collided row)."""
    def scalar(sql: str, params: tuple = ()) -> int:
        return conn.execute(sql, params).fetchone()[0]

    materials_with_activity = set()
    for sql in (
        "SELECT DISTINCT material_id FROM practice_session",
        "SELECT DISTINCT material_id FROM quiz_attempt",
        "SELECT DISTINCT material_id FROM recording WHERE status = 'ready'",
        "SELECT DISTINCT material_id FROM quick_practice_session",
    ):
        materials_with_activity.update(row[0] for row in conn.execute(sql).fetchall())

    return {
        "materials_with_activity": len(materials_with_activity),
        "completed_sessions": scalar("SELECT COUNT(*) FROM practice_session WHERE status = 'completed'"),
        "completed_quizzes": scalar("SELECT COUNT(*) FROM quiz_attempt WHERE status = 'completed'"),
        "ready_recordings": scalar("SELECT COUNT(*) FROM recording WHERE status = 'ready'"),
        "completed_quick_practice": scalar(
            "SELECT COUNT(*) FROM quick_practice_session WHERE status = 'completed'"
        ),
        "shadowing_practice_sum": scalar(
            "SELECT COALESCE(SUM(practice_count), 0) FROM shadowing_cue_progress WHERE practice_count > 0"
        ),
        "diagnosis_count": scalar("SELECT COUNT(*) FROM session_diagnosis_evidence"),
    }


def build_synthetic_db(path: Path, scale: dict, rng: random.Random) -> None:
    """Bulk-generates synthetic data directly via SQL (not the application
    service layer) purely for generation speed at these row counts."""
    conn = open_connection(path)
    migrate(conn)

    material_ids: list[int] = []
    cue_ids_by_material: dict[int, list[int]] = {}
    for i in range(scale["materials"]):
        cur = conn.execute(
            "INSERT INTO material (title, media_path, status) VALUES (?, ?, 'active')",
            (f"Synthetic Lesson {i:05d}", f"synthetic/media/lesson_{i:05d}.wav"),
        )
        material_id = cur.lastrowid
        material_ids.append(material_id)
        track_cur = conn.execute(
            "INSERT INTO subtitle_track (material_id, format, source_path) VALUES (?, 'srt', ?)",
            (material_id, f"synthetic/media/lesson_{i:05d}.srt"),
        )
        track_id = track_cur.lastrowid
        cue_rows = [
            (track_id, j + 1, j * 2000, j * 2000 + 1800, f"Synthetic cue text number {j}.")
            for j in range(10)
        ]
        conn.executemany(
            "INSERT INTO subtitle_cue (subtitle_track_id, cue_index, start_ms, end_ms, text) "
            "VALUES (?, ?, ?, ?, ?)",
            cue_rows,
        )
        cue_ids_by_material[material_id] = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM subtitle_cue WHERE subtitle_track_id = ?", (track_id,)
            ).fetchall()
        ]
    conn.commit()

    session_rows = []
    for _ in range(scale["sessions"]):
        material_id = rng.choice(material_ids)
        status = rng.choices(["completed", "abandoned"], weights=[0.8, 0.2])[0]
        anchor_ts = _ts(rng, HISTORY_WINDOW_DAYS)
        completed_at = anchor_ts if status == "completed" else None
        abandoned_at = anchor_ts if status == "abandoned" else None
        session_rows.append((material_id, status, anchor_ts, completed_at, abandoned_at))
    conn.executemany(
        "INSERT INTO practice_session (material_id, status, last_resumed_at, completed_at, abandoned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        session_rows,
    )
    conn.commit()
    session_ids_and_materials = conn.execute(
        "SELECT id, material_id FROM practice_session"
    ).fetchall()

    diagnosis_rows = []
    shadowing_rows = []
    for session_id, material_id in session_ids_and_materials:
        cues = cue_ids_by_material[material_id]
        for _ in range(scale["diagnosis_per_session"]):
            cue_id = rng.choice(cues)
            diagnosis_rows.append(
                (session_id, cue_id, "keyword", "synthetic text", 0, 5, _ts(rng, HISTORY_WINDOW_DAYS))
            )
        for _ in range(scale["shadowing_per_session"]):
            cue_id = rng.choice(cues)
            practice_count = rng.randint(1, 3)
            shadowing_rows.append(
                (session_id, cue_id, "practiced", practice_count, _ts(rng, HISTORY_WINDOW_DAYS))
            )
    conn.executemany(
        "INSERT OR IGNORE INTO session_diagnosis_evidence "
        "(practice_session_id, subtitle_cue_id, label_key, selected_text, selection_start, selection_end, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        diagnosis_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO shadowing_cue_progress "
        "(practice_session_id, subtitle_cue_id, status, practice_count, last_practiced_at) "
        "VALUES (?, ?, ?, ?, ?)",
        shadowing_rows,
    )
    conn.commit()

    quiz_rows = []
    for _ in range(scale["quizzes"]):
        material_id = rng.choice(material_ids)
        status = rng.choices(["completed", "abandoned"], weights=[0.85, 0.15])[0]
        anchor_ts = _ts(rng, HISTORY_WINDOW_DAYS)
        actual_count = scale["quiz_questions_per_attempt"]
        correct_count = rng.randint(0, actual_count) if status == "completed" else None
        quiz_rows.append(
            (
                material_id, status, rng.randint(1, 10_000_000), actual_count, actual_count,
                correct_count, anchor_ts, anchor_ts if status == "completed" else None,
                anchor_ts if status == "abandoned" else None,
            )
        )
    conn.executemany(
        "INSERT INTO quiz_attempt (material_id, status, seed, requested_count, actual_count, "
        "correct_count, last_resumed_at, completed_at, abandoned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        quiz_rows,
    )
    conn.commit()
    quiz_attempt_ids_and_materials = conn.execute(
        "SELECT id, material_id FROM quiz_attempt"
    ).fetchall()

    question_rows = []
    answer_rows = []
    for attempt_id, material_id in quiz_attempt_ids_and_materials:
        cues = cue_ids_by_material[material_id]
        for position in range(scale["quiz_questions_per_attempt"]):
            cue_id = rng.choice(cues)
            question_rows.append(
                (
                    attempt_id, position, "cue_dictation", cue_id,
                    '{"cue_text": "synthetic"}', '{"normalized_answer_text": "synthetic"}',
                    '{"rule": "target_text", "version": 1}', "synthetic cue text",
                )
            )
    conn.executemany(
        "INSERT INTO quiz_question (quiz_attempt_id, position, question_type, subtitle_cue_id, "
        "prompt_payload, correct_answer_payload, scoring_config, source_cue_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        question_rows,
    )
    conn.commit()
    for (question_id,) in conn.execute("SELECT id FROM quiz_question").fetchall():
        answer_rows.append((question_id, "synthetic answer", "synthetic answer", 1, "answered"))
    conn.executemany(
        "INSERT INTO quiz_answer (quiz_question_id, raw_answer_text, normalized_answer_text, "
        "is_correct, answered_state) VALUES (?, ?, ?, ?, ?)",
        answer_rows,
    )
    conn.commit()

    recording_rows = []
    for i in range(scale["recordings"]):
        material_id = rng.choice(material_ids)
        cue_id = rng.choice(cue_ids_by_material[material_id])
        status = rng.choices(["ready", "failed"], weights=[0.95, 0.05])[0]
        recording_rows.append(
            (material_id, cue_id, f"recordings/synthetic_{i:06d}.wav", status, rng.randint(1000, 8000), _ts(rng, HISTORY_WINDOW_DAYS))
        )
    conn.executemany(
        "INSERT INTO recording (material_id, subtitle_cue_id, relative_file_path, status, duration_ms, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        recording_rows,
    )
    conn.commit()

    qp_session_rows = []
    for _ in range(scale["quick_practice_sessions"]):
        material_id = rng.choice(material_ids)
        status = rng.choices(["completed", "abandoned"], weights=[0.9, 0.1])[0]
        anchor_ts = _ts(rng, HISTORY_WINDOW_DAYS)
        qp_session_rows.append(
            (
                material_id, "selected", 3, 3, status, anchor_ts,
                anchor_ts if status == "completed" else None,
                anchor_ts if status == "abandoned" else None,
            )
        )
    conn.executemany(
        "INSERT INTO quick_practice_session (material_id, source_type, requested_count, actual_count, "
        "status, started_at, completed_at, abandoned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        qp_session_rows,
    )
    conn.commit()
    qp_session_ids_and_materials = conn.execute(
        "SELECT id, material_id FROM quick_practice_session"
    ).fetchall()
    qp_item_rows = []
    for qp_id, material_id in qp_session_ids_and_materials:
        cues = cue_ids_by_material[material_id][:3]
        for position, cue_id in enumerate(cues):
            qp_item_rows.append((qp_id, cue_id, position, "understood", 1, None))
    conn.executemany(
        "INSERT INTO quick_practice_item (quick_practice_session_id, subtitle_cue_id, position, "
        "recall_result, transcript_revealed, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
        qp_item_rows,
    )
    conn.commit()
    conn.close()


def _time_call(fn, *args, repeats: int = 3) -> tuple[float, float, object]:
    timings = []
    result = None
    for i in range(repeats):
        start = time.perf_counter()
        result = fn(*args)
        timings.append(time.perf_counter() - start)
    cold = timings[0]
    warm_avg = sum(timings[1:]) / max(1, len(timings) - 1)
    return cold, warm_avg, result


def run_tier(tier_name: str, scale: dict) -> None:
    rng = random.Random(RNG_SEED)
    with tempfile.TemporaryDirectory(prefix="ltperf_") as tmpdir:
        db_path = Path(tmpdir) / "perf.db"
        print(f"\n=== {tier_name} ===")
        print(f"Generating synthetic data (nominal target): {scale}")
        gen_start = time.perf_counter()
        build_synthetic_db(db_path, scale, rng)
        print(f"Generation took {time.perf_counter() - gen_start:.2f}s")

        conn = open_connection(db_path)
        try:
            row_counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "material", "practice_session", "session_diagnosis_evidence",
                    "shadowing_cue_progress", "quiz_attempt", "quiz_question", "quiz_answer",
                    "recording", "quick_practice_session", "quick_practice_item",
                )
            }
            print(f"Actual row counts (some diagnosis/shadowing rows are deduplicated by a UNIQUE "
                  f"constraint when the RNG draws the same cue twice for one session): {row_counts}")

            ground_truth = compute_ground_truth(conn)

            today = date.today()
            all_time = date_range_rules.resolve_date_range(date_range_rules.PRESET_ALL_TIME, today)
            last_90 = date_range_rules.resolve_date_range(date_range_rules.PRESET_LAST_90_DAYS, today)

            results = {}
            for range_name, resolved_range in (("All Time", all_time), ("Last 90 Days", last_90)):
                cold, warm, overview = _time_call(history_svc.get_overview, conn, None, resolved_range)
                print(
                    f"  get_overview(material=None, {range_name}): cold={cold*1000:.1f}ms warm_avg={warm*1000:.1f}ms"
                )
                cold_a, warm_a, activity = _time_call(history_svc.list_activity, conn, None, resolved_range)
                print(
                    f"  list_activity(material=None, {range_name}): cold={cold_a*1000:.1f}ms "
                    f"warm_avg={warm_a*1000:.1f}ms rows={len(activity)}"
                )
                results[range_name] = overview

            cold_e, warm_e, bundle = _time_call(
                export_service.build_export, conn, ExportScope(kind=SCOPE_ALL), all_time
            )
            total_sessions = sum(len(m.get("sessions", [])) for m in bundle.materials)
            print(
                f"  build_export(All Materials, All Time): cold={cold_e*1000:.1f}ms warm_avg={warm_e*1000:.1f}ms "
                f"materials={len(bundle.materials)} total_session_entries_in_export={total_sessions}"
            )

            overview_all_time = results["All Time"]
            checks = [
                ("materials_practiced", overview_all_time.materials_practiced, ground_truth["materials_with_activity"]),
                ("completed_sessions", overview_all_time.completed_sessions, ground_truth["completed_sessions"]),
                ("completed_quizzes", overview_all_time.completed_quizzes, ground_truth["completed_quizzes"]),
                ("retained_recording_count", overview_all_time.retained_recording_count, ground_truth["ready_recordings"]),
                ("quick_practices_completed", overview_all_time.quick_practices_completed, ground_truth["completed_quick_practice"]),
                ("shadowing_practice_count", overview_all_time.shadowing_practice_count, ground_truth["shadowing_practice_sum"]),
                ("session_diagnosis_evidence_count", overview_all_time.session_diagnosis_evidence_count, ground_truth["diagnosis_count"]),
            ]
            for name, actual, expected in checks:
                assert actual == expected, f"{name} mismatch: got {actual}, expected {expected}"
            print(f"  Correctness: all {len(checks)} checked Overview metrics match independently-computed ground truth.")
        finally:
            conn.close()


def main() -> None:
    print("M12.4 Performance Decision Gate — Learning History 'All Materials' + Export")
    print("(HARDENING_BACKLOG.md #17 — see that file for the recorded decision)")
    for tier_name, scale in SCALES.items():
        run_tier(tier_name, scale)
    print("\nDone. See HARDENING_BACKLOG.md's Performance Decision Gate section for the interpretation and decision.")


if __name__ == "__main__":
    main()

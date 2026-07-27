# Milestone 12 Hardening Backlog

Tracks findings from the M12.1-B agent-led audit and their disposition. Created
once the first audit pass produced enough findings (7, from one focus area
alone) to warrant structured tracking, per `ROADMAP.md`'s M12.1 policy.

Status legend: **Fixed** (repaired + regression test added this milestone),
**Accepted** (confirmed real, deliberately not fixed tonight — narrow/low
severity, rationale given), **Deferred** (out of M12 scope), **Open**
(confirmed, not yet addressed).

## Batch 1 — Diagnosis-evidence write atomicity

Audit method: read `src/listentrace/infrastructure/db/connection.py` (plain
`sqlite3.connect`, no shared transaction helper) and traced every
application-service function that performs more than one DB write to
represent one logical operation, looking for crash-window data-integrity
risk (each repository function commits independently by convention; nothing
enforces grouping).

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 1 | `record_session_diagnosis`: annotation-insert and its session-scoped evidence-snapshot insert (+ conditional stage-outcome clear) were three independently-committed writes. A crash between them left an orphaned `Annotation` row with no linked `session_diagnosis_evidence`, contradicting the function's own documented guarantee. | `application/services/practice_session_service.py` | High (data-integrity, documented-invariant violation) | **Fixed** — wrapped in one explicit transaction (`commit=False` on the interior repository calls, single `conn.commit()`/`conn.rollback()` at the end). Regression tests added and verified to fail against the pre-fix code (`tests/integration/test_practice_session_service.py::test_record_session_diagnosis_is_atomic_across_annotation_and_evidence`). |
| 2 | Same pattern for Quick Practice's `record_item_diagnosis`. | `application/services/quick_practice_service.py` | High (data-integrity) | **Fixed** — same treatment; regression test `tests/integration/test_quick_practice_service.py::test_record_item_diagnosis_is_atomic_across_annotation_and_evidence`, also verified to fail pre-fix. |
| 3 | `recording_service.delete_take` unlinks the on-disk `.wav` file, then commits the DB delete as a separate step. A crash in that narrow window leaves a `recording` row referencing a file that no longer exists, with no automatic recovery path (unlike interrupted-`status='recording'` rows, which `recover_interrupted_recordings` already cleans up at startup). | `application/services/recording_service.py` | Low (crash-only window between two adjacent statements; no realistic exploit path in normal use) | **Accepted** — reordering (DB-first, then unlink) would invert the risk and break an existing, deliberate M7 promise ("a file that fails to delete leaves its database row intact rather than falsely reporting success"). A real fix needs a startup reconciliation pass (check every `recording` row's file still exists), which is new infrastructure, not a targeted fix — deferred rather than built tonight under M12's "no scope expansion disguised as a fix" boundary. |
| 4 | `_reevaluate_stage`-paired writes (`save_stage_response`, `update_session_diagnosis`, `delete_session_diagnosis`, `update_keyword_capture`, `delete_keyword_capture`) each pair one evidence write with a separate stage-status-recompute commit. A crash between them can leave a stage `completed` one write-cycle longer than its evidence currently justifies. | `application/services/practice_session_service.py` | Low (self-correcting: the next evidence change re-runs `_reevaluate_stage` from current, correct state; never produces an orphaned row, only transient staleness) | **Accepted** — same class of issue as #1/#2 but self-healing rather than permanent; lower priority than the orphaned-row cases. |
| 5 | `_reveal_transcript_and_lock_prior_stages` (entering Stage 3) performs up to 4 independent commits (`set_current_stage`, up to two `set_stage_status` calls, `set_transcript_revealed`). A crash mid-sequence could in principle advance `current_stage` before `transcript_revealed_at` is set, or vice versa. | `application/services/practice_session_service.py` | Medium (narrow crash window; if it did land badly, a user could see a session that looks like Stage 3 but rejects diagnosis entry until re-entering the stage) | **Accepted for now, flagged for a follow-up batch** — same fix shape as #1/#2 (thread `commit=False` through the four calls, single outer commit) is straightforward but was not done in this batch to keep the first repair batch small and reviewable. Tracked as **Open** for M12.2's next batch. |

## Repair rules applied

- Existing external call sites of the four touched repository functions
  (`insert_annotations`, `insert_session_diagnosis`, `set_stage_outcome`,
  `insert_item_diagnosis`) were enumerated before changing signatures; the new
  `commit: bool = True` parameter defaults to the prior behavior everywhere
  except the two composite call sites that now pass `commit=False`.
- Both fixes were verified to actually change test outcomes: each new
  regression test fails against the pre-fix source (confirmed via
  `git stash` of just the fix files) and passes after.
- Full automated suite: 630 passed (628 prior + 2 new), no regressions.

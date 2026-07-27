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
| 5 | `enter_stage`'s Stage 3 entry (`set_current_stage`, up to two `set_stage_status` calls, `set_transcript_revealed`) performed up to 4 independent commits. A crash mid-sequence could advance `current_stage` before `transcript_revealed_at` was set, or vice versa. | `application/services/practice_session_service.py` | Medium (narrow crash window; if it landed badly, a user could see a session that looks like Stage 3 but rejects diagnosis entry until re-entering the stage) | **Fixed** (Batch 3) — the whole `enter_stage` body (current_stage, the not_started->in_progress transition, and the Stage 3 reveal/lock sequence) now runs as one explicit transaction. Regression test `tests/integration/test_practice_session_service.py::test_enter_stage3_is_atomic_across_current_stage_and_transcript_reveal`, verified to fail pre-fix (current_stage advanced to `transcript_diagnosis` with `transcript_revealed_at` still `None`). |

## Batch 2 — Verification sweep (export, material/recording deletion, migration, Quick Practice crash recovery)

No code changes this batch — every area checked was verified correct against the
actual source (not assumed from docstrings), with one architecture-debt note
recorded for the future.

| # | Area | Verdict | Evidence |
|---|---|---|---|
| 6 | Export preview invalidation / atomic save / overwrite-confirm ordering | **Pass** | `ui/windows/export_dialog.py`: every scope/date/category/privacy control is wired to `_invalidate_preview`, which clears the stored preview text and disables Save/Copy until regenerated; Save/Copy only ever read the stored (possibly-`None`) text, so a stale preview cannot be saved. `infrastructure/export_io.py`'s `atomic_write_text` always writes to a sibling temp file and `os.replace()`s it into place; overwrite confirmation happens before that call, not after. |
| 7 | Material removal vs. partially-failed recording-file deletion | **Pass** | `material_library_service.remove_material` checks `DeletionSummary.all_succeeded` and raises before calling `delete_material` if any recording file failed to delete — the material row is never removed while an undeletable recording still exists; already-succeeded per-row deletions (file unlink then DB row delete) leave no file/DB divergence. |
| 8 | Migration safety re-check (Post-M10 Phase B fix still holds) | **Pass** | `migrations.py`'s `migrate()` still runs each migration as one explicit transaction, bumps `PRAGMA user_version` as the last statement inside that same transaction, and rolls back + re-raises without advancing on failure — confirmed a failure at migration N leaves the DB cleanly at migration N-1's version. |
| 9 | Migration statement splitting — latent fragility, not an active defect | **Architecture debt (low, latent)** | `migrate()` splits each migration's SQL on `;` with a naive string split, with no awareness of `;` inside a string literal or comment. None of the 10 current migrations trip this. Not fixed tonight (nothing is broken today); noted so a future migration author writing a migration containing a literal semicolon in string data doesn't get silently mis-split. |
| 10 | Quick Practice: crash after ≥1 completed cue, before explicit close | **Pass** | `recover_interrupted_sessions` runs unconditionally on every startup (`ui/app.py`, right after `recover_interrupted_recordings`) and applies the same discard/abandon rule as an explicit close to every session left `status='active'` — zero completed items is hard-deleted, ≥1 completed item becomes `abandoned`. No orphaned "active" session or misleading permanent history entry survives past the next launch. |

## Batch 4 — M12.3 workflow/UX consistency

Audit method: read-only trace of terminology, confirmation dialogs, disabled-
control explanations, and status-label wording across all 14 windows. Per
M12.3's boundary, only targeted corrective changes were made — no visual
redesign.

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 11 | `QuickPracticeWindow._on_delete_diagnosis_clicked` deleted a diagnosis with **no confirmation dialog**, while the identical action in `GuidedSessionWindow._on_delete_diagnosis_clicked` does confirm. | `ui/windows/quick_practice_window.py` | Medium (destructive action, no confirmation — inconsistent with every other delete in the app) | **Fixed** — added a matching confirmation dialog. Regression test verified to fail pre-fix (no prompt appeared). |
| 12 | Quick Practice's close-with-progress confirmation dialog was titled "Close Quick Practice" while it actually marks the run `abandoned` — GuidedSessionWindow/QuizWindow use "Abandon Session"/"Abandon Quiz" for the same semantic action, so a user trained on those two windows could be surprised that "Close" here is actually an abandon. | `ui/windows/quick_practice_window.py` | Low (wording only, body text already explained the abandon) | **Fixed** — retitled to "Abandon Quick Practice Run"; dialog body text (already accurate) unchanged. |
| 13 | Stage 4 shadowing status was shown as the raw enum value (`Status: not_started`) instead of a human-readable label, inconsistent with the title-cased/uppercase convention used a few lines away for session status (`[ABANDONED — read-only]`). | `ui/windows/guided_session_window.py` | Low (cosmetic, within-window inconsistency) | **Fixed** — now renders as `NOT STARTED` / `PRACTICED` / `SKIPPED`, matching the existing convention. No test asserted the old raw string. |
| 14 | Stage 1/2 controls go grey with no on-screen explanation when the transcript-reveal lock kicks in — a user has no cue why beyond recalling a one-time dialog shown earlier. | `ui/windows/guided_session_window.py` | Low (a real UX gap, not a redesign) | **Fixed** — added a small hint label to each stage's panel, shown only while locked ("Read-only: the transcript has been revealed for this session."). Regression test verified to fail pre-fix (`AttributeError`, label didn't exist). |
| 15 | MainWindow's Resume Intensive Practice / Resume Quiz buttons disable with no tooltip explaining why (no material selected vs. no active session/quiz for the selected material). | `ui/windows/main_window.py` | Low | **Fixed** — added context-appropriate tooltips for both disabled cases. No dedicated test added (trivial `setToolTip` call, already exercised indirectly by existing button-state tests; screenshotting tooltip text is not practical in offscreen tests). |

Verified but not changed: quiz submission's confirmation + service-level status-
transition guard already safely handles double-submission; no fix needed
(see Batch 2's Quiz scoring-atomicity verification, same audit pass).

## Repair rules applied

- Existing external call sites of the four touched repository functions
  (`insert_annotations`, `insert_session_diagnosis`, `set_stage_outcome`,
  `insert_item_diagnosis`) were enumerated before changing signatures; the new
  `commit: bool = True` parameter defaults to the prior behavior everywhere
  except the two composite call sites that now pass `commit=False`.
- Both fixes were verified to actually change test outcomes: each new
  regression test fails against the pre-fix source (confirmed via
  `git stash` of just the fix files) and passes after.
- Full automated suite: 632 passed (628 through Milestone 11, + 2 from Batch 1, + 1 from Batch 3, + 1 from Batch 4), no regressions.

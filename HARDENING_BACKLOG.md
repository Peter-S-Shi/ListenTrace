# Milestone 12 Hardening Backlog

Tracks findings from the M12.1-B agent-led audit and their disposition. Created
once the first audit pass produced enough findings (7, from one focus area
alone) to warrant structured tracking, per `ROADMAP.md`'s M12.1 policy.

Status legend: **Fixed** (repaired + regression test added this milestone),
**Accepted** (confirmed real, deliberately not fixed tonight — narrow/low
severity, rationale given), **Deferred** (out of M12 scope), **Open**
(confirmed, not yet addressed).

## Session summary (autonomous overnight pass, Batches 1-5, plus the M12.4 Performance Decision Gate)

18 findings total across M12.1-B/M12.2/M12.3/M12.4: **8 Fixed**, **4 Pass/
verified-clean** (#6-#8, #10 — no action needed), **4 Accepted** (#3, #4, #9,
#16 — confirmed real, low severity, rationale given), **2 Deferred to
v1.0.x** (#17, #18 — both decided by measurement, not just a query-plan
shape; see the Performance Decision Gate section below; neither blocks
merging `milestone/12-product-hardening` into `main`). No release-blocking
or high-risk unresolved defect is known.

Of the 8 Fixed, the regression-coverage picture is deliberately not uniform
— data/behavior fixes are held to a stricter bar than text/tooltip fixes:
- **5 have a dedicated regression test independently verified to fail
  against the pre-fix code via `git stash`** (#1, #2, #5, #11, #14 — every
  fix that changes stored data, write atomicity, or a confirmation
  behavior).
- **3 are low-risk text/tooltip corrections** (#12 dialog title, #13 status
  text, #15 tooltip strings) **verified only via the existing test suite
  staying green (no regression) plus direct code review** — no new
  dedicated pre-fix-verified test was written for these, since a wrong
  string is not a data-integrity or workflow-correctness risk.

Zero destructive actions taken; `main` untouched throughout — all work on
`milestone/12-product-hardening`.

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

## Batch 5 — M12.4 robustness, privacy, and performance (verification, no code changes)

Audit method: grepped every logging call site in `src/`, read the crash-logging
hook and custom exception classes for content leakage, verified query plans
for the Learning History/Export query layer with `EXPLAIN QUERY PLAN` against
the live migrated schema, and spot-checked rapid-click safety on the three
highest-risk buttons (Start Recording, Start Material Quiz, Start Intensive
Practice) — all three already guarded (button self-disable, a blocking modal
dialog, or a caught `ActiveSessionExistsError` fallback). No code changed
this batch; two findings are documented rather than fixed, with rationale.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 16 | The only 4 logging call sites in the app (all in `ui/app.py`) log static text or numeric counts only — no transcript/note/vocabulary content is ever logged directly. However, `sys.excepthook`'s crash-logging hook (`app.py`) logs a caught exception's full `exc_info`, and several exception messages elsewhere embed absolute file paths (e.g. `material_import_service.py`'s "Subtitle file not found: {path}", `media/validation.py`'s "Media file not found: {file_path}") — typically containing the Windows username. Today every such exception is already caught locally and shown in a dialog, never logged; the path would only reach the log file if some *unanticipated* exception type escaped every existing handler and fell through to the crash hook. | Low (latent, not currently exploitable) | **Accepted** — `ROADMAP.md`'s own privacy rule permits paths in logs "unless necessary for troubleshooting," and a crash traceback naming which file failed to open is genuinely necessary for diagnosing that class of bug. Building a message-redaction layer for a not-yet-observed leak path was judged disproportionate to the (currently zero) confirmed exposure. |
| 17 | Learning History's "All Materials" default view (`history_repository.py`'s `_ACTIVITY_UNION_SQL`, backing `list_activity` and `count_materials_with_any_activity`) filters on `occurred_at`, a `COALESCE(...)` **expression** computed in the outer query, not a real column. Confirmed via `EXPLAIN QUERY PLAN` against the live schema: every one of the 6 UNIONed branches (session/quiz/diagnosis/shadowing/recording/quick_practice) does a full `SCAN`, not an indexed `SEARCH`, when no `material_id` narrows it. | Originally logged Moderate from the query plan alone; **downgraded after measurement** — see the Performance Decision Gate below. | **Deferred to v1.0.x — does not block merging `milestone/12-product-hardening` into `main`.** A dedicated benchmark (`scripts/m12_4_performance_gate.py`) measured actual wall-clock time at realistic and 5x-stress personal-use data volumes, not just the query plan shape. See "M12.4 Performance Decision Gate" below for the full method, numbers, and reasoning — a schema migration is not currently justified by measured user impact. |

Verified Pass, no action needed: rapid-click safety on Start Recording (button self-disables while active), Start Material Quiz (blocked behind a modal `QInputDialog`), and Start Intensive Practice (no button-disable, but race-safe via a caught `ActiveSessionExistsError` fallback — worst case is a duplicate window, never a duplicate session).

## M12.4 Performance Decision Gate (finding #17)

`EXPLAIN QUERY PLAN` showing a full table scan is a shape observation, not a
measurement of user-visible impact — it says nothing about how large the
tables actually get in real personal use, or how many milliseconds a scan
of that size costs. Per instruction, a schema migration is **not** to be
introduced on the strength of the query plan alone. This gate instead
measures actual wall-clock time against privacy-safe synthetic data at a
reasoned, defensible personal-use scale, before deciding.

### Method

`scripts/m12_4_performance_gate.py` (new, committed — a reusable, repeatable
verification procedure, not a one-off). For each of two tiers, it:

1. Bulk-generates synthetic data directly via SQL (fully synthetic titles/
   text, no real user data, temporary on-disk SQLite file deleted after the
   run) at a defensible personal-use scale, then
2. Times `learning_history_service.get_overview`, `.list_activity`, and
   `export_service.build_export` (All Materials scope) for both "All Time"
   and "Last 90 Days", each averaged over 3 runs (first run reported
   separately as "cold", remaining runs averaged as "warm"), then
3. Independently recomputes 7 of `OverviewMetrics`' fields directly from
   the persisted rows (deliberately different, simpler SQL than the
   production queries — no `COALESCE`/`UNION`) and asserts they match the
   production result exactly, so the benchmark also re-verifies current
   result correctness/statistical accuracy, not just speed.

**Scale tiers** (both defensible as single-user, local-first, not a
multi-tenant workload):
- **REALISTIC** (~2 years of very dedicated daily use): 100 materials,
  1,000 Intensive Practice sessions, 800 quiz attempts (5 questions each),
  ~5,700 session-diagnosis rows, ~5,700 shadowing-progress rows, 3,000
  recordings, 1,500 Quick Practice sessions — roughly 87,000 total activity
  rows across the 6 source tables.
- **STRESS** (5x REALISTIC): 300 materials, 5,000 sessions, 4,000 quizzes,
  ~28,500 diagnosis rows, ~28,400 shadowing rows, 15,000 recordings, 7,500
  Quick Practice sessions — to see whether cost grows roughly linearly
  (safe to defer) or worse (would argue for fixing regardless of the
  realistic number), not because 5x is itself claimed as realistic.

### Results

| Tier | Operation | Cold | Warm avg | Rows / materials |
|---|---|---|---|---|
| REALISTIC | `get_overview`, All Time | 5.0ms | 4.2ms | — |
| REALISTIC | `list_activity`, All Time | 69.6ms | 70.9ms | 17,505 rows |
| REALISTIC | `get_overview`, Last 90 Days | 4.5ms | 3.7ms | — |
| REALISTIC | `list_activity`, Last 90 Days | 10.0ms | 10.6ms | 2,098 rows |
| REALISTIC | `build_export`, All Materials/All Time | 250.0ms | 246.8ms | 100 materials |
| STRESS | `get_overview`, All Time | 29.9ms | 29.5ms | — |
| STRESS | `list_activity`, All Time | 413.7ms | 677.3ms | 87,717 rows |
| STRESS | `get_overview`, Last 90 Days | 52.4ms | 51.4ms | — |
| STRESS | `list_activity`, Last 90 Days | 101.9ms | 103.5ms | 10,701 rows |
| STRESS | `build_export`, All Materials/All Time | 3,309.6ms | 3,405.0ms | 300 materials |

Correctness: at both tiers, all 7 independently-recomputed Overview metrics
(`materials_practiced`, `completed_sessions`, `completed_quizzes`,
`retained_recording_count`, `quick_practices_completed`,
`shadowing_practice_count`, `session_diagnosis_evidence_count`) matched the
production result exactly — confirms today's calculations remain accurate
at this scale, independent of the performance question.

### Decision on #17

**Deferred to v1.0.x. Does not block merging `milestone/12-product-hardening`
into `main`.** At REALISTIC scale, `list_activity`/`get_overview` (the
functions #17 is actually about) complete in 4-71ms — imperceptible for a
dashboard a learner opens occasionally, not a hot path hit on every
keystroke. Even at 5x-stress they stay under ~680ms, still within a
reasonable "brief pause for a full-history refresh" budget. A schema
migration (expression indexes on each branch's `COALESCE(...)` timestamp,
version 11) is not currently justified by any measured evidence of user
impact. Re-run `scripts/m12_4_performance_gate.py` if a real user ever
reports Learning History feeling slow, or periodically as history
naturally accumulates well beyond the STRESS tier's assumptions.

### New finding discovered during this gate (#18)

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 18 | `export_service.build_export`'s "All Materials" scope loops per-material (not a combined query), so its cost scales with `materials x average-evidence-per-material` rather than staying flat. Measured: 250ms at REALISTIC (100 materials), but 3.3-3.4 **seconds** at STRESS (300 materials, 5x the per-material evidence) — a ~13x time increase for a 5x data increase, i.e. worse than linear, and structurally unrelated to #17 (this path never touches `_ACTIVITY_UNION_SQL`, so #17's proposed fix would not help it). | Low at realistic personal-use scale (250ms is a normal, expected wait for an explicit "generate my full export" action, not a hot path); worth monitoring, not release-blocking. | **Deferred to v1.0.x, same rationale as #17** — real personal-use scale (100 materials) measures fine; only the 5x-stress tier crosses into clearly-noticeable territory. Documented rather than silently fixed or silently dropped, per the same "measure before deciding" discipline applied to #17. If a future user's material count grows well past ~100-150 with heavy per-material history, re-run the benchmark before assuming it's still fine. |

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

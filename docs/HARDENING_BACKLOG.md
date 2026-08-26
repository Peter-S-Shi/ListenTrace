# Milestone 12 Hardening Backlog

Tracks findings from the M12.1-B agent-led audit and their disposition. Created
once the first audit pass produced enough findings (7, from one focus area
alone) to warrant structured tracking, per `ROADMAP.md`'s M12.1 policy.

Status legend: **Fixed** (repaired + regression test added this milestone),
**Accepted** (confirmed real, deliberately not fixed tonight — narrow/low
severity, rationale given), **Deferred** (out of M12 scope), **Open**
(confirmed, not yet addressed).

## Session summary

**Autonomous overnight pass (Batches 1-5 + M12.4 Performance Decision Gate):**
18 findings across M12.1-B/M12.2/M12.3/M12.4 — 8 Fixed, 4 Pass/verified-clean
(#6-#8, #10), 4 Accepted (#3, #4, #9, #16), 2 Deferred to v1.0.x (#17, #18,
decided by measurement, not query-plan shape alone; see the Performance
Decision Gate section). Of the 8 Fixed, 5 have a dedicated pre-fix-verified
regression test (#1, #2, #5, #11, #14 — every data/atomicity/confirmation
fix); 3 are low-risk text/tooltip corrections (#12, #13, #15) verified via
the existing suite staying green plus code review, no dedicated test.

**Human QA Round 1 corrective work (Batches A/B/C + History Deletion + QA
cleanup, this round):** 12 further findings — 10 Fixed (#19-28, release
blockers, Playback Contract, Layout Contract, and the new History Deletion
feature) and 2 QA Specification Defects corrected at the fixture/wording
level with no product-code change (#29-30). Every one of the 10 Fixed
findings this round has a dedicated pre-fix-verified regression test — no
exceptions taken.

**Combined total: 30 findings — 18 Fixed, 4 Pass, 4 Accepted, 2 Deferred to
v1.0.x, 2 QA-spec corrected.** No release-blocking or high-risk unresolved
defect is known. Zero destructive actions taken; `main` untouched throughout
— all work on `milestone/12-product-hardening`.

**Addendum — Loop Cue audible-endpoint defect, closed (2026-08-23):** the
Loop Cue toggle-label fix above (#24 area / Batch B) did not resolve the
underlying audible clipping at a Loop's boundary. This was not one further
"finding" fixable in this backlog's usual shape — it took three further
corrective rounds (each human-retested and found insufficient) before a full
redesign into a calibratable **Loop End Grace** feature (its own persistence
schema and Settings UI, not a bounded bug fix — see `PROJECT_STATUS.md`'s
Completed section for the full round-by-round record). Closed with a
3-material human calibration retest: the
180ms built-in default failed all three materially different samples, 200ms
passed all three (complete tail, no next-cue leakage, continuous multi-cue
playback). **Loop audible-end blocker: HUMAN ACCEPTED / CLOSED.** This is
the last piece of Milestone 12 Phase 12-A (Pre-UI Product Hardening), now
complete — see `PROJECT_STATUS.md` and `ROADMAP.md`. 93 further tests added
across this addendum (666 -> 759).

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

## M12 Round 1 Human QA Corrective Work (Batches A/B/C, History Deletion, QA cleanup)

Source: the user's first full manual-acceptance pass against
`manual-qa/listentrace-manual-qa-tester-2026-08-11.json`, reconciled against
product intent through four structured feedback documents
(`M12.QA feedback-round 1-4`, product-requirements/architecture-analysis
inputs, not implementation orders — never committed, per the repo's local-
prompt-draft convention). Phase 0 was a read-only audit producing
`M12_CORRECTIVE_DIVERGENCE_MAP.md` (committed, human-reviewed before any
code changed), mapping each human finding to the applicable contract, actual
current implementation, root-cause evidence, and a Batch assignment. What
follows is the disposition after implementing that plan; the Divergence Map
itself retains the full audit reasoning and is not duplicated here.

Every fix below has a dedicated regression test independently verified via
`git stash` to fail against the pre-fix source, per this branch's estab-
lished discipline — no exceptions taken for this batch of work.

### Batch A — Release blockers / correctness

| # | Finding | File | Status |
|---|---|---|---|
| 19 | Guided Session `Complete Session` stayed disabled after Stage 5 was filled in (human QA: m08-04/m10-01/m10-03). Domain logic (`session_rules.py`) was independently verified already correct via a new end-to-end UI test walking Stage1→5 through the real "Save and Continue" action — the actual defect was explainability: the shared button gave no indication anything still needed to happen on the terminal stage, and a disabled Complete Session gave no reason. | `ui/windows/guided_session_window.py` | **Fixed** — the action relabels to "Save Summary" on Stage 5; a new status line shows which stages remain unresolved, derived from the same `rules.session_can_complete` predicate driving the button (single source of truth). `tests/integration/test_guided_session_window.py::test_stage5_summary_save_and_continue_enables_complete_button`, `::test_complete_button_disabled_reason_is_visible_and_accurate`. |
| 20 | Ghost recording Take (m06-08): after a take was deleted in one window, a second open window on the same cue kept showing the stale row; clicking it reported "Not Found", and re-deleting it silently did nothing. Two-part root cause: no cross-window invalidation existed, and the delete handler caught `RecordingValidationError` but not its sibling `RecordingNotFoundError`. | `ui/widgets/recording_panel.py`, `ui/windows/shadowing_practice_window.py`, `ui/windows/main_window.py` | **Fixed** — a new process-wide Qt signal bus (`recording_change_bus`) notifies every open `RecordingPanel` to refresh on a deletion elsewhere (per-cue or per-material); the delete handler now also catches `RecordingNotFoundError` and clears the stale row instead of raising uncaught. `tests/integration/test_recording_panel.py` (2 tests). |
| 21 | History/session timestamps displayed the raw stored UTC string with no local-time conversion (m08-02) — confirmed a genuine ~4-hour discrepancy in this environment (EDT). Local-calendar date-range *filtering* (`resolve_date_range`, callers using `date.today()`) was verified already correct — only display was wrong. | `ui/time_display.py` (new), `ui/windows/session_history_dialog.py`, `ui/windows/quiz_history_dialog.py`, `ui/windows/learning_history_window.py` | **Fixed** — one shared `format_local_timestamp` helper applied at every identified display call site (systemic, not a per-window patch, per explicit instruction). `tests/unit/test_time_display.py`, `tests/integration/test_session_history_dialog.py`. |

### Batch B — Playback Convergence (Round 1 Playback Contract)

| # | Finding | File | Status |
|---|---|---|---|
| 22 | Quiz/Quick Practice/Shadowing's "Play" button called only the raw transport `play()`, so it could run straight through every remaining cue instead of stopping at the current one (m05-01/m10-05/m12-05). | `application/services/player_session.py`, `ui/windows/quiz_window.py`, `ui/windows/quick_practice_window.py`, `ui/windows/shadowing_practice_window.py` | **Fixed** — new `PlayerSession.play_cue()`: cue-scoped like the existing `replay_cue()`, but resumes in place if paused mid-cue rather than always restarting (disambiguated from "this cue already finished" via explicit state, not position alone). 4 unit tests + 3 real-event-loop UI tests (one per window). |
| 23 | Main Player: repeated Previous Cue could jump straight back to the start (m02-03/m13-02, intermittent). Root cause: navigation read `active_cue_index`, transiently `None` right after a seek before the next position tick lands; `CueIndex.previous_index(None)` falls back to cue 0. | `ui/windows/player_window.py` | **Fixed** — navigation now anchors on `_editing_cue_index` (the stable, explicitly-tracked Selected Cue), mirroring the pattern `ShadowingPracticeWindow` already used correctly. Previous/Next also now drive the cue-list selection, so Selected Cue/list selection/workspace panel move atomically with Media Position. 2 tests. |
| 24 | Loop Cue button always read "Loop Cue" even while active, with no visible cancel affordance beyond undocumented keyboard shortcuts (m02-05). | `ui/windows/player_window.py` | **Fixed** — toggles to "Stop Loop" while active; resets on Escape, the `L` shortcut, and Replay Cue (which cancels any active loop as a side effect). 3 tests. |
| 25 | Transcript viewport never scrolled to keep the playing cue visible during continuous playback (m02-01/m12-05) — a clean gap, not a partial bug; only highlighting existed. | `ui/windows/player_window.py` | **Fixed** — Follow Playback: on by default, scrolls only when the active cue isn't already comfortably visible (no forced re-centering every tick); a manual scroll suspends it and reveals a "Return to Playing Cue" action; a programmatic-scroll guard distinguishes Previous/Next's own scroll-into-view from a genuine manual free-scroll. 3 tests. |

### Batch C — Desktop Layout Convergence (Round 2 Layout Contract)

| # | Finding | File | Status |
|---|---|---|---|
| 26 | PlayerWindow's Transcript Workspace panel (QLineEdits, Save/Update/Delete buttons) compressed to unreadable slivers when the window was shorter than the stacked content's combined height (m03-01/m03-04/m03-05, screenshot-confirmed). No scroll container existed anywhere in the window; none of the affected fields had a minimum height. | `ui/windows/player_window.py` | **Fixed** — content wrapped in a resizable `QScrollArea` (the window scrolls instead of squeezing anything); the cue list and the previously-unbounded fields/buttons also get an explicit minimum height as an independent second safety floor. 1 test. |
| 27 | Long Quiz answer options were hard-truncated with an ellipsis regardless of window size (m05-01, screenshot-confirmed) — `QRadioButton` has no word-wrap support in Qt Widgets at all; a wrong-widget-choice problem, not a missed property. | `ui/windows/quiz_window.py` | **Fixed** — each radio now carries no text; a paired `QLabel(wordWrap=True)` is the actual reading/selection target (clicking it selects the radio too). `QButtonGroup`/`checkedId()`-based answer logic untouched. 1 test. |

### History Deletion (Round 4 Feasibility Gate — approved)

| # | Finding | File | Status |
|---|---|---|---|
| 28 | No history view let the user delete a completed/abandoned record (m05-02) — a Major Product Semantics Decision per Round 3, gated on the Round 4 Feasibility checklist. All 8 preauthorized conditions verified against the real schema (session-owned children cascade; independent annotation/saved-item/keyword-capture/recording references are `ON DELETE SET NULL`, never cascaded; stats are computed live, no stored counters) — gate passed, no schema migration needed. | `session_repository.py`, `practice_session_service.py`, `quiz_repository.py`, `quiz_service.py`, `quick_practice_service.py`, `session_history_dialog.py`, `quiz_history_dialog.py`, `learning_history_window.py` | **Fixed** — single-record delete for completed/abandoned Guided Sessions, Quiz attempts, and Quick Practice runs; an active record must be abandoned/closed first. Confirmation dialogs state actual cascade impact (a Guided Session's recordings are explicitly retained, not deleted — the schema is `SET NULL`, correcting Round 3's own illustrative example text, which assumed `CASCADE`). Verified directly, not just asserted, that an annotation and a completed recording both survive session deletion. 9 tests across service and UI layers. |

### QA fixture/wording corrections (no product code)

| # | Finding | Status |
|---|---|---|
| 29 | m01-02's fixture imported `normal_lesson.wav` twice to test SRT/VTT parsing equivalence, unintentionally colliding with the product's separate, intentional "same file path can only be imported once" invariant. Confirmed via code (`material_import_service.py`) that this is a **QA Specification Defect**, not a product bug — the same-path case has no confirm override by design; only content-fingerprint duplicates under a different path are confirmable. | **QA fixture fixed, product unchanged** — added `normal_lesson2.wav` (byte-identical, distinct filename); reworded the step/expectation to describe the real "Possible Duplicate" confirmation flow. |
| 30 | m10-02's expectation could be read as requiring an interrupted recording to vanish entirely on relaunch. Implementation already matches Round 3's own accepted terminal model: marked `failed`, not playable, not counted as evidence — confirmed via `recover_interrupted_recordings` and `RecordingPanel._refresh_takes`/`_update_take_buttons`. | **QA wording fixed, product unchanged** — reworded to state a labeled "failed" row persisting in the list is expected, not a residual bug, while preserving the actual regression-relevant check (nothing stuck in "recording" status). |

Also added: `m08-09`, new manual QA coverage for the History Deletion capability (a genuinely new user-facing feature, not a correction).

### Repair rules applied (Human QA Round 1 corrective work)

- Root-cause domain grouping, not questionnaire-item-by-item patching (Round 4 §2) — e.g. the three cue-scoped-Play fixes share one new `PlayerSession.play_cue()` method rather than three independent per-window hacks.
- Repository-grounded evidence took precedence over the feedback documents' illustrative assumptions where they conflicted with the real schema — see `M12_CORRECTIVE_DIVERGENCE_MAP.md` §0 for the two corrections found (no Mistake Book/Starred/Proficient Pool/Collection semantics exist in this codebase; `recording.practice_session_id` is `SET NULL`, not `CASCADE`).
- No Level-3 stop condition was triggered: no schema migration, no data-model redesign, no technology-stack change, no product-contract conflict.
- `main` untouched throughout; all work on `milestone/12-product-hardening`.

## Repair rules applied (Batches 1-5, overnight autonomous pass)

- Existing external call sites of the four touched repository functions
  (`insert_annotations`, `insert_session_diagnosis`, `set_stage_outcome`,
  `insert_item_diagnosis`) were enumerated before changing signatures; the new
  `commit: bool = True` parameter defaults to the prior behavior everywhere
  except the two composite call sites that now pass `commit=False`.
- Both fixes were verified to actually change test outcomes: each new
  regression test fails against the pre-fix source (confirmed via
  `git stash` of just the fix files) and passes after.
- Full automated suite at the end of Batches 1-5: 632 passed (628 through
  Milestone 11, + 2 from Batch 1, + 1 from Batch 3, + 1 from Batch 4), no
  regressions.

## Current automated suite total

666 tests passing as of the end of the Human QA Round 1 corrective work
(632 at the end of the overnight pass + 34 new regression tests across
Batches A/B/C, History Deletion, and this document's own coverage — see
each batch's table above for the per-fix test names). No regressions.

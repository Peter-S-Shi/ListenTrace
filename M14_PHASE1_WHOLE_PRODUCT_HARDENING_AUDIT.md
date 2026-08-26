# ListenTrace — Milestone 14 Phase 1: Whole-Product Hardening Audit

**Date**: 2026-08-26 (revised after Product Owner corrective review)
**Branch**: `milestone/14-final-product-hardening`
**HEAD at audit time**: `6fea91750fe6d246dbf4d250746b38eb275a78e0`
**Baseline automated test result**: `900 passed in 128.92s` (0 failures, re-run fresh for this audit)
**Audit mode**: Read-only against production code (no production code modified). Risk-based sampling across five parallel review passes covering all in-scope product areas from the Phase 1 kickoff prompt, plus one non-destructive, disposable diagnostic reproduction used only to settle a classification question (Section B, P2-4b) — no production code or committed test file was touched by it.

### Baseline provenance

`6fea917` is a remote-pushed commit whose direct parent is `2e5a038876fa21a6375af37f6f966001b155cbbd` — the branch HEAD the Phase 1 kickoff prompt itself names as "the accepted Phase 0 baseline." `6fea917`'s own diff (`fix(learning-history): wrap section workspace tabs in scroll area and prevent metric/list squishing`, `theme.py` + `learning_history_window.py`, 77 insertions / 49 deletions) is the Learning History scroll/metric correction referenced throughout this audit — it was already present on the branch, already reviewed by its own commit, and predates this read-only audit entirely. This audit did not author, and does not take credit for, that change; it is cited here only as prior context for the Learning History findings below.

**Revision note**: this is a corrected version of the Phase 1 audit. Product Owner review identified three classification errors in the first draft (a UI-unreachable dead-code path misclassified as a confirmed P1 defect; four semantically distinct list actions incorrectly grouped as one defect; a not-yet-reproduced scenario placed in the confirmed-defect inventory instead of verification-required). All three are corrected below with new evidence gathered specifically to resolve them.

**Batch A status update (post-acceptance)**: the Phase 1 audit below was Product Owner **ACCEPTED**. Corrective Batch A — Cross-Window State Consistency — has since been implemented and closes **P2-1, P2-2, P2-3, and P2-4** (all four are marked `[RESOLVED — Batch A]` in Section B below, with their implementation/regression-test evidence). This document is left otherwise unchanged from its accepted form, per instruction — findings, corrections, and reasoning below still reflect the state of the product *before* Batch A, except where a `[RESOLVED — Batch A]` marker says otherwise. P2-5, P3-1, G-1, and G-2 remain open. See the end of Section F for what remains.

**PH-3 acceptance-gap update**: Product Owner remote review gave the initial Batch A implementation a **CONDITIONAL PASS** — A1 and A3 (P2-3, P2-1) were accepted outright; A2 and A4 (P2-4, P2-2) each had one bounded gap. Both gaps are now closed (see P2-2's and P2-4's `[RESOLVED — Batch A / A4]`/`[RESOLVED — Batch A / A2]` entries in Section B for the acceptance-gap fix detail) — **all four Batch A findings are now fully resolved with no open conditions.**

**Batch B status update**: M14 Corrective Batch B — Semantic & Time-Display Correctness — closes the two remaining confirmed defects, **P2-5 and P3-1** (both marked `[RESOLVED — Batch B]` in Section B below), and adds a permanent regression test locking in the remove-while-open-window safety property Correction 3c verified by disposable diagnostic (see Section E, former test gap 8, now closed). **All 6 confirmed defects from the accepted Phase 1 map are now resolved.** Only G-1 and G-2 (governance/documentation drift, Section G) remain open, plus the Correction-1 `LabelColorDialog` dead-code cleanup explicitly deferred to a later "Batch C."

---

## A. Executive Verdict

- **Branch/HEAD**: `milestone/14-final-product-hardening` @ `6fea917`, in sync with `origin`, working tree clean.
- **Baseline test result**: 900 passed, 0 failures — matches the Phase 0 handoff claim exactly.
- **Overall release-risk assessment**: **No P0 (release-stop) and no P1 (must-fix) defects found.** The product is structurally sound — migrations, session/quiz lifecycle transactions, missing-media handling, export privacy boundaries, and (newly verified this revision) the remove-material-while-a-dependent-window-is-open path all independently hold up under inspection or direct reproduction. The real risk concentration is a **recurring pattern of incomplete rollout of shared mechanisms**: two systems (the label-color live-refresh bus, and the pre-existing local-time display convention) were correctly wired into the *primary* evidenced surface but not swept to every analogous consumer, leaving a few already-open windows silently stale. A second, smaller pattern is **UI controls that stay enabled based on only local/per-window state**, so an action appears available and then fails post-click once a cross-window or cross-evidence precondition is actually checked server-side.
- **Finding counts (revised)**:
  - CONFIRMED DEFECT: 6 (P0: 0, P1: 0, P2: 5, P3: 1)
  - CONFIRMED GOVERNANCE/DOCUMENTATION DRIFT: 2
  - TEST COVERAGE GAP: 10
  - HUMAN-ONLY VERIFICATION REQUIRED: 4
  - ACCEPTED LIMITATION / NON-DEFECT (positively verified, no action needed): 20 (corrected from an earlier draft's miscount of 17 against Section H's actual 20-item list; Section H is the source of truth)
  - **Post-acceptance**: all 6 confirmed defects are now resolved — P2-1, P2-2, P2-3, P2-4 via `[RESOLVED — Batch A]`, P2-5 and P3-1 via `[RESOLVED — Batch B]`.

---

## B. Confirmed Defect Inventory (P0 → P3)

### P0 — none found.

### P1 — none found (see Correction 1 below for the finding removed from this tier).

### P2

**P2-1. `[RESOLVED — Batch A / A3]` Guided Session Stage 3 and Quick Practice diagnosis panels never subscribe to `label_color_change_bus`**
- **Resolution**: both windows now import `label_color_change_bus`, connect it in `__init__`, and implement a narrow `_refresh_diagnosis_presentation_colors()` that reapplies transcript highlighting and walks the existing `DiagnosisNoteRow` list items calling `.set_color(...)` in place — deliberately *not* the full `_refresh_diagnosis_cue_panels()`/`_populate_diagnose()` reload path, since those also clear the in-progress diagnosis edit form (checkboxes, heard-as, note draft) as a side effect, which the corrective prompt explicitly required preserving. Regression tests: `test_label_color_live_refresh_preserves_diagnosis_editing_state` in both `tests/integration/test_guided_session_window.py` and `tests/integration/test_quick_practice_window.py` — each saves one diagnosis, leaves an unsaved draft note, triggers the bus, and asserts both the color updated and the draft note text is untouched.
- Files: `guided_session_window.py`, `quick_practice_window.py` (zero references to `label_color_change_bus` in either file, confirmed by repo-wide grep — vs. `player_window.py:236`, which connects, and `settings_dialog.py:238`, which emits after a real edit).
- Trigger: user has a Guided Session Stage 3 panel or a Quick Practice diagnosis panel open, opens the (real, reachable) Settings dialog in parallel — both are independent, non-modal top-level windows, nothing prevents this — and changes a label color there.
- Observed vs expected: per the bus's own docstring ("every already-open study desk surface"), diagnosis-evidence colors should update live in these panels too; in practice they only refresh the next time the window/stage is opened.
- Existing tests: none reference `label_color_change_bus` from either window's test file.
- Human retest: yes, for the fix (a live two-window check that Guided Session/Quick Practice repaint mid-session).

**P2-2. `[RESOLVED — Batch A / A4]` Start Recording stays clickable in a second `RecordingPanel` while another panel is actively recording — click fails only after the fact**
- **Resolution (initial Batch A pass)**: `_RecordingChangeBus` gained two payload-free `recording_started`/`recording_stopped` signals (payload-free because the underlying domain/database invariant is global, not per-material/cue — migration 8's partial unique index allows at most one `status = 'recording'` row app-wide). `RecordingPanel` tracked a separate `_external_recording_active` flag alongside its own `_active_recording`, and `_update_recording_buttons()` disabled Start Recording on a sibling panel while blocked. Regression test: `test_sibling_panel_start_button_becomes_truthful_while_another_panel_is_recording` in `tests/integration/test_recording_panel.py`.
- **Product Owner remote review (PH-3): CONDITIONAL PASS.** The event-only `_external_recording_active` cache correctly handled panels that already existed when `recording_started` fired, but a `RecordingPanel` **constructed after** a recording had already started would initialize `_external_recording_active = False` and had simply missed the historical event — permanently wrong (stuck enabled) until the next unrelated `recording_stopped` broadcast.
- **Acceptance-gap fix**: replaced the cached flag with a live query against authoritative current state. New `recording_service.has_active_recording(conn) -> bool` (thin wrapper over the same `repo.list_recordings_with_status(conn, RecordingStatus.RECORDING.value)` check `begin_recording` itself already performs). `_update_recording_buttons()` now computes `blocked_by_other_panel` by calling this fresh on every invocation (when the panel's own `_active_recording is None`), instead of reading a cache. `_on_external_recording_started`/`_on_external_recording_stopped` are now pure "go re-check now" invalidation notifications with no state of their own — they just call `_update_recording_buttons()`. This means a late-joining panel is correct from its very first `_update_recording_buttons()` call (fired at the end of both `__init__` and `set_context()`), regardless of whether it existed to hear any historical signal, and an immediate startup error cannot leave any panel permanently stale since there is no cache to go stale — every check re-derives truth from the database. Regression tests (`tests/integration/test_recording_panel.py`): `test_late_joining_panel_starts_disabled_when_a_recording_is_already_in_progress`, `test_immediate_startup_error_does_not_leave_sibling_panel_permanently_blocked`.
- Files: `recording_panel.py:393-406` (`_update_recording_buttons`, panel-local only); `_RecordingChangeBus` (`recording_panel.py:29-43`) carries `cue_changed`/`material_changed` but no "recording started/stopped" event.
- Observed vs expected: clicking calls `recording_service.begin_recording`, which raises `RecordingValidationError("recording_in_progress", ...)` — no data loss (the DB unique index and service pre-check fully protect the invariant), but the button visibly offers an action guaranteed to fail.
- Human retest: not required for the fix; UI-only, deterministic from signal wiring.

**P2-3. `[RESOLVED — Batch A / A1]` Renaming a material loses its Library-list selection (narrowed from the original draft — see Correction 2)**
- **Resolution**: `refresh_library()` now captures `_selected_material_id()` before clearing the list, and re-selects the matching item by `material_id` (not row index/title) once the list is rebuilt — a no-op when the id genuinely isn't in the rebuilt list, which correctly preserves Correction 2's finding that Archive/Restore/Remove should *not* keep a selection. Regression tests: `test_rename_preserves_library_selection_by_material_id` (selection survives a rename that also changes alphabetical position) and `test_archiving_correctly_leaves_selection_empty_not_a_regression` (archive still correctly clears selection) in `tests/integration/test_main_window_m13.py`.
- Files: `main_window.py:883-893` (`_on_rename_clicked`) → `refresh_library()` (`:488-531`) does `self._material_list.clear()` and rebuilds with no `setCurrentItem`/`setCurrentRow` call anywhere in the file.
- Scope check performed: `list_materials_by_status` (`repository.py:203-208`) orders by `title COLLATE NOCASE`, and a rename never changes a material's `status`, so the renamed item **always remains in the currently-displayed list** (it may move to a new alphabetical position, but it does not leave the view). This is what makes selection loss here a genuine defect rather than expected disappearance — see Correction 2 for why archive/restore/remove are different and are *not* included in this finding.
- Observed vs expected: after renaming, the dossier blanks and all action buttons disable; the user must re-click the (still-visible, just-renamed) item to continue a natural follow-up action.
- Human retest: not required; deterministic from code.

**P2-4. `[RESOLVED — Batch A / A2]` Renaming a material does not notify already-open dependent windows on that material (narrowed from the original draft — see Correction 3)**
- **Resolution (initial Batch A pass)**: a new, narrowly-scoped `material_metadata_bus` (`src/listentrace/ui/widgets/material_metadata_bus.py`, one `material_renamed(material_id, new_title)` signal — deliberately not a repurposed `recording_change_bus`, per the corrective prompt's explicit instruction against misleading ownership, and deliberately not a generic material-changed event, since rename is the only signal currently needed). `MainWindow._on_rename_clicked` emits it after a successful rename. `PlayerWindow`, `GuidedSessionWindow`, `QuizWindow`, `QuickPracticeWindow`, and `ShadowingPracticeWindow` — the five material-bound long-lived host windows identified by auditing every `setWindowTitle` call site that bakes in a material title — each connect it and refresh only their window title and in-body header label (`theme.make_surface_header`'s `title_label`) plus `self._material.title` itself. Regression tests: one per host window (`test_material_renamed_updates_window_title_and_header` in each of `test_guided_session_window.py`, `test_quick_practice_window.py`, `test_shadowing_practice_window.py`, plus a Quiz variant in `test_ui_smoke.py`), and one end-to-end test (`test_rename_propagates_to_open_player_window_title_and_header` in `test_main_window_m13.py`) driving the real `MainWindow → PlayerWindow` path.
- **Product Owner remote review (PH-3): CONDITIONAL PASS.** The five *host* windows were correctly covered, but `MaterialLoopSettingsDialog` — a modeless child dialog reachable from all five hosts, whose window title also bakes in the material title at construction (`Loop Settings — {material_title}`) — was missed and stayed stale after a rename while open.
- **Acceptance-gap fix**: `MaterialLoopSettingsDialog` now connects directly to `material_metadata_bus.material_renamed` itself (rather than adding a sixth host-specific relay path) and updates its own window title when the id matches. Regression test: `test_material_renamed_updates_dialog_title_for_matching_id_only` in `tests/integration/test_material_loop_settings_dialog.py`, asserting both the matching-id update and that an unrelated id is ignored.
- Files: no signal of any kind is emitted from `_on_rename_clicked` (`main_window.py:883-893`); contrast with `_on_remove_clicked`, which does emit `recording_change_bus.material_changed` (`:925`).
- Observed vs expected: a `PlayerWindow`/`GuidedSessionWindow`/`QuizWindow` already open on material X keeps showing the stale title indefinitely after a rename from the Library — the only one of the four mutating actions with a live-window consistency gap and *zero* signal of any kind (see Correction 3: archive/restore and remove were independently re-investigated this revision and are **not** included here).
- Human retest: not required for the fix; the effect (a stale title on an open window) is deterministic and observable.

**P2-5. `[RESOLVED — Batch B / B1]` Local-time display contract (`format_local_timestamp`) is inconsistently applied across Learning History**
- Files (state at time of finding — re-audited fresh against current-branch line numbers before the fix, per instruction, rather than treating this audit's own line numbers as permanent): `learning_history_window.py:432` (Continue Learning), `:543` (Activity list), `:667-670` (Diagnoses "most recent"), `:852-854` (Shadowing/High-Frequency lists, sharing `_shadowing_item_text`) all interpolated the raw stored-UTC timestamp instead of calling `format_local_timestamp` (self-documented as the mandatory M12 Round 3 Time Contract); `learning_history_service.py:489-491` (`chart_quiz_accuracy_over_time`) likewise built a chart-point label from the raw value.
- Observed vs expected: within the *same* window, the Sessions list, Quiz History list, Quiz Comparison tree, Recording list, and Quick Practice list correctly showed local wall-clock time, while the five surfaces above showed the raw UTC string unconverted — most visibly wrong where the Quiz Comparison tree and the quiz trend chart render the *same underlying entries* with different conventions side by side.
- **Resolution**: swept all five consumers to call `format_local_timestamp`. The four UI-layer call sites in `learning_history_window.py` were wrapped directly. The chart point label is built in the *application*-service layer (`chart_quiz_accuracy_over_time`), where it is presentational text only — never re-parsed for chronological logic (chronological order comes from the SQL query's own ordering of `group.entries`, not from this label string) — so converting it there does not blur UTC-storage-vs-presentation responsibility; no database storage semantics were touched anywhere. `format_local_timestamp` itself was relocated from `ui/time_display.py` to `domain/services/time_display.py` (it was already framework-free, zero PySide6 imports — this is an architectural cleanup that legitimizes the application-service layer importing it directly, consistent with `domain/services/date_range.py`'s existing pattern for the same class of UTC-conversion concern, rather than importing a `ui/`-layer module from `application/services/`). Gained an optional `tz: tzinfo | None = None` injection seam (default preserves the exact original system-local behavior for every real call site) purely so a DST-offset-sensitive case can be tested deterministically without depending on the host machine's timezone or installing `tzdata`.
- Regression tests: `tests/unit/test_time_display.py` gained `test_offset_conversion_is_correct_across_a_dst_style_transition` (fixed `timezone(timedelta(hours=-4))`/`(hours=-5)` fixtures proving the conversion applies whatever offset is in effect, not one memoized delta — the exact bug class a real DST transition would expose) and `test_tz_argument_does_not_change_default_system_local_behavior`. `tests/integration/test_learning_history_window.py` gained `test_persisted_timestamps_render_as_local_time_not_raw_utc` (one test, fixed known UTC timestamp, covering all four UI consumers including Shadowing's shared render path) and `test_quiz_accuracy_chart_point_label_renders_local_time`.
- Human retest: no longer required for correctness (now code-verifiable via the DST-offset test); a live spot-check remains reasonable but is not blocking.

### P3

**P3-1. `[RESOLVED — Batch B / B2]` "No Notable Difficulty" button (Guided Session Stage 3) stays enabled even when the session already has diagnosis evidence, and the click is guaranteed to fail**
- Files: `guided_session_window.py:1057-1064`/`1131` (`_no_difficulty_button` enabled purely from `revealed and not read_only`) vs. `practice_session_service.mark_stage3_no_difficulty` (`:349-358`), which raises `SessionValidationError("diagnosis_evidence_exists", ...)` whenever any diagnosis evidence already exists. The opposite direction (`record_session_diagnosis`) self-heals silently instead of erroring — the two directions are asymmetric.
- **Resolution**: `_populate_stage3` now also gates the button on `not (len(state.session_diagnosis) > 0)` — the exact same session-wide evidence-count condition `mark_stage3_no_difficulty` itself checks (`repo.count_session_diagnosis(...) > 0`), so the UI can never present an action the service is guaranteed to reject. The service-level guard is untouched and remains the ultimate invariant; this is proactive UI truthfulness only. Because `_refresh_state()` already re-runs `_populate_stage3` after every diagnosis save/delete, availability correctly flips back to enabled the moment the only evidence is removed — no additional wiring was needed for that case.
- Regression tests: `test_no_notable_difficulty_available_only_when_stage3_revealed_with_no_evidence` (covers: available with no evidence → disabled once evidence exists → re-enabled after deleting that evidence → the click itself still succeeds and records the outcome exactly as before) and `test_no_notable_difficulty_stays_disabled_on_a_read_only_completed_session` (a read-only/abandoned session keeps the action disabled regardless of evidence state, unchanged from before).
- Human retest: not required; code-verifiable.

---

## Corrections Applied This Revision

### Correction 1 — the Label Colors "P1" finding was a misclassification of unreachable dead code, not a live defect

Re-inspected the actual current Player UI construction (`player_window.py:380-629`), not merely the existence of `_on_open_label_colors`/`LabelColorDialog`/`_label_colors_button`:

- `self._label_colors_button` is constructed (`:408`), wired to `_on_open_label_colors` (`:409`), and later has a role applied to it in `_apply_presentation`'s loop (`:605`) — but it is **never added to any layout anywhere in the file** (verified: every sibling button built in the same method, e.g. `self._transcript_button`, has a matching `utility_layout.addWidget(...)` call right next to its construction; `_label_colors_button` has no such call, confirmed by a full-file grep for the attribute name — it appears only at lines 408, 409, and 605).
- The in-code comment directly above its construction is explicit and accurate: *"Global label colors preference lives in Library Settings; kept as attribute for programmatic/test backward compatibility without UI duplication."*
- No menu bar exists in `PlayerWindow` (the file's only `QMenu` is the cue-list's right-click "Clear Cue Selection" context menu) that could reach it another way.
- The one test that exercises this path, `test_open_label_colors_refreshes_highlight_and_badge_without_full_reload` (`test_player_window_workspace.py:465-509`), calls `window._on_open_label_colors()` **directly** — it does not click a button or otherwise prove UI reachability, and could not, since there is none.

**Conclusion, matching the Product Owner's premise exactly**: `_label_colors_button`/`_on_open_label_colors`/the `LabelColorDialog` import are orphaned compatibility code, not a user-reachable second settings path. There is exactly one real, visible, global Label Colors entry point today: **Library sidebar → Settings... → Label Colors tab** (`settings_dialog.py:189-238`), which does correctly emit `label_color_change_bus` after an edit (`:238`).

**Disposition**:
- The former P1-1 ("`LabelColorDialog` bypasses the bus") is **removed from the confirmed-defect inventory**. It cannot cause the described user-facing staleness because a user cannot reach it.
- The former P2-6/G-3 ("duplicate divergent UI reachable from different entry points") is **removed** for the same reason — there is only one reachable UI, not two.
- Reclassified as **ACCEPTED LIMITATION-NON-DEFECT with a recommended low-priority cleanup**: `LabelColorDialog`, `_label_colors_button`, and `_on_open_label_colors` should either be deleted outright (if truly dead) or the one test exercising them should be rewritten to assert non-reachability explicitly, so a future accidental re-wiring (or accidental deletion of intentionally-kept compatibility code) is caught either way. Filed as a **TEST COVERAGE GAP**, not a product defect: today's test proves the handler's internal logic works but proves nothing about the UI surface, in either direction.
- The **narrower, independent question the Product Owner explicitly asked to keep investigating** — whether already-open Guided Session Stage 3 and Quick Practice diagnosis surfaces should live-refresh when the one real Settings-dialog path changes a label color — was re-confirmed still valid by the same grep (`guided_session_window.py`/`quick_practice_window.py` have zero `label_color_change_bus` references). This survives as **P2-1** above, unchanged in substance, now correctly scoped to the one real entry point.
- **Human QA wording corrected**: the questionnaire item about Label Colors should name the actual, single visible path — "Library sidebar → Settings... → Label Colors tab" — not describe or imply two parallel visible settings paths. See Section D.

### Correction 2 — P2-3 was four semantically distinct actions incorrectly grouped as one defect

Re-evaluated `_on_rename_clicked`, `_on_archive_restore_clicked`, and `_on_remove_clicked` (`main_window.py:883-926`) individually against `refresh_library()`'s actual list-membership behavior (`:488-531`, which calls `library.list_active_materials`/`list_archived_materials` depending on `self._showing_archived`):

- **Rename**: the material's `status` is untouched by `rename_material` (`material_library_service.py:64-67` → `repository.py:211-216`, a pure `UPDATE ... SET title`), so the item always stays in whichever list (Active or Archived) is currently displayed. Selection loss here is losing a still-visible item — a genuine UX regression. **Retained as a defect (P2-3 above).**
- **Archive**: `archive_material` sets `status = ARCHIVED` (`material_library_service.py:70-73`). If the currently-displayed view is Active (the normal case for archiving), the item **correctly and expectedly leaves that view** the moment `refresh_library()` re-queries `list_active_materials`. This is the list doing exactly what "archiving hides a material from the default library view" (`ARCHITECTURE.md:40`) says it should do. Calling this "selection lost" mischaracterizes intended behavior as a defect. **Not a defect.**
- **Restore**: the mirror image of Archive — an item viewed in the Archived list correctly leaves that view once restored to Active. **Not a defect**, same reasoning.
- **Remove**: the material record no longer exists at all after `remove_material` succeeds. There is no list membership for a deleted row to remain in. **Not a defect** — this is the only outcome consistent with what "remove" means.

**Disposition**: the original P2-3 (all four actions) is retired. Only the **rename** case is retained as a confirmed defect, now standing alone as **P2-3** in Section B. Archive/Restore/Remove selection changes are reclassified as **ACCEPTED LIMITATION-NON-DEFECT** — expected list-membership behavior, not a UI bug.

### Correction 3 — P2-4 was three distinct scenarios; two are now resolved by direct evidence rather than deferred to a human

Split the original "open secondary windows are not notified" finding into its three named scenarios and investigated each on its own terms:

**3a. Rename → cross-window stale presentation.** No signal is emitted on rename at all (confirmed by grep — `_on_rename_clicked` calls only `library.rename_material` then `self.refresh_library()`; no bus, no event). An already-open dependent window's title genuinely goes stale with no path to correct itself short of being closed and reopened. **Retained as a confirmed defect — this is P2-4 above, narrowed to rename only.**

**3b. Archive/Restore → behavior of already-open dependent windows.** Checked the normative product contract before judging this (`ARCHITECTURE.md:40,150`): *"Archiving hides a material from the default library view without deleting any records; archived materials can be viewed and restored,"* and *"Archived materials cannot be opened"* (i.e., the contract's actual restriction is on **starting new** access, not on continuing existing access). `archive_material`/`restore_material` (`material_library_service.py:70-79`) are pure, non-cascading status-flag flips with no effect on any session/annotation/recording row. An already-open window continuing to function normally against a now-archived material is consistent with "archiving is reversible and non-destructive" — the contract never says an in-progress window must be forcibly closed or blocked mid-use, only that *new* opens are refused. **Reclassified as ACCEPTED LIMITATION-NON-DEFECT** (a deliberate, contract-consistent design choice, not an oversight) — flagged as worth a one-line explicit confirmation from the Product Owner if they want the stricter behavior, but not filed as a defect absent that instruction.

**3c. Remove-while-dependent-window-open.** Per the corrective instruction, this was **not** deferred to human reproduction; a deterministic, non-destructive, disposable integration test was written and run instead (not committed — created under the session scratchpad, copied into `tests/integration/` only long enough to execute under the project's real `qapp`/`conn` fixtures, then deleted; the repository's working tree is unchanged by this step, confirmed via `git status` before and after). Reproduction: opened a real `PlayerWindow` on a freshly imported material, called the real `library.remove_material(...)` service path against that same material (which succeeded, cascading the DB deletes as designed), then invoked the still-open window's real `_on_save_annotation_clicked()` handler — a representative write.
  - **Observed result**: no exception propagated (no crash); no orphan `annotation` row was created (`SELECT COUNT(*) FROM annotation` → `0`); the material and its cues were confirmed actually gone (`0` rows each); the window's own `_workspace_status_label` displayed a clean, user-visible message — `"Subtitle cue 1 not found"` — because `annotation_service` validates the target cue's existence before writing and raises a handled domain error rather than letting a raw `sqlite3.IntegrityError`/foreign-key violation surface.
  - **Conclusion from this evidence**: the write path is safe. No data loss, no crash, no orphaned row, no partial write. The only residual imperfection is a UX-clarity one — the message names a missing cue rather than explaining that the material itself was removed from another window — which is a minor polish item, not a data-integrity or stability defect.
  - **Reclassified as ACCEPTED LIMITATION-NON-DEFECT**, now backed by direct reproduction rather than a hypothesis. The message-clarity nuance is recorded as a **TEST COVERAGE GAP** (worth a permanent regression test locking in today's safe behavior) rather than a defect.

**Disposition**: the original P2-4 (three scenarios bundled, one HUMAN-ONLY) is retired. Only 3a survives as a confirmed defect (now P2-4 in Section B, rename-only). 3b and 3c are both resolved to ACCEPTED LIMITATION-NON-DEFECT by direct evidence gathered this revision — neither remains in Human-Only Verification Required.

---

## C. Cross-Cutting Patterns

Two patterns remain supported by repeated, independent evidence across otherwise-unrelated subsystems after this revision's corrections:

1. **New shared "live refresh" mechanisms are wired to the one evidenced surface, not swept to every analogous consumer.** Seen twice, both confirmed independently: `label_color_change_bus` (P2-1) reaches `PlayerWindow` and `SettingsDialog` but not `GuidedSessionWindow`/`QuickPracticeWindow`; the pre-existing `format_local_timestamp` local-time convention (P2-5) reaches 5 of 10 comparable Learning History list surfaces but not the other 5. Both are the same shape: a good mechanism was introduced against the milestone's named acceptance surface, and the "does every widget that shows this same kind of data now use it" sweep was not done.

2. **A control's enabled/disabled state reflects only local/per-widget state, while the real precondition is checked elsewhere (a service call, or another window's state) — so an action looks available and only fails after the click.** Seen twice: cross-window Start Recording (P2-2) and the Stage 3 "No Notable Difficulty" button (P3-1).

One narrower, single-instance observation, downgraded from "pattern" status this revision now that its broader framing (all four Library mutating actions) turned out to be wrong: **rename is the only one of the four Library mutating actions with zero cross-window/selection consistency handling at all** (P2-3, P2-4) — archive, restore, and remove were each independently checked this revision and found to already behave correctly (expected list departure, or a verified-safe write path). This is worth fixing on its own merits, but it is not evidence of a repo-wide "mutating actions don't notify" pattern — the other three actions do not have this problem.

---

## D. Human QA Round 2 Readiness

`manual-qa/manual_review_questionnaire.html` carries `questionnaireVersion: "2026-07-27.2"` — **it predates both Milestone 13's whole-product UI reconstruction and Milestone 14 Phase 0.** Its 15 modules (m00–m14) are still structurally sound (they test product *behavior*, not literal widget names), but the following gaps were confirmed by direct inspection:

**Stale / needs correction (revised this pass):**
- m03-06 ("Open Label Colors, change a color") does not name an entry point. **Corrected recommendation**: name the one real, visible path explicitly — *"Library sidebar → Settings... → Label Colors tab"* — rather than the previous draft's incorrect implication that two parallel visible settings paths exist. There is only one.

**Missing coverage — no item exists at all:**
- The M14 Phase 0 consolidated Settings surface itself (Library sidebar "Settings..." with Playback + Label Colors tabs) has no dedicated item confirming the redundant Player-level settings button is actually gone (it is — see Correction 1) and the one remaining entry point covers both categories.
- The M14 Phase 0 "Clear Selection" right-click context-menu feature in the Player transcript view has zero questionnaire coverage.
- Learning History's M14 Phase 0 scroll-wrap of all 7 workspace tabs (nested-scroll interaction — see HQ-3 below) has no item exercising a constrained window height against a tab with many rows.
- Material Study Dossier's "7 rows simultaneously visible + whole-card scroll fallback only at extreme heights" claim (M14 Phase 0) has no item testing a very small window height or a very long CJK title/path together.
- Renaming a material's selection-preservation (P2-3) and cross-window title staleness after rename (P2-4) have no item — worth adding regardless of whether the underlying defects are fixed first.

**Genuinely human-only, correctly left as such:** 125%/150% Windows display-scale rendering; real-microphone audio quality and native Windows multimedia surfaces; nested QScrollArea wheel-capture feel at real window sizes; `FlowLayout` wrapping under extreme width or long localized button text.

**Could move from repeated human spot-check to automation now that root causes are understood:** local-time display correctness (P2-5, once fixed); label-color live-refresh propagation to Guided Session/Quick Practice (P2-1, once fixed); remove-while-open-window safety (already proven safe by direct reproduction this revision — worth locking in as a permanent automated regression test rather than a recurring manual check at all).

**Recommendation**: preserve the questionnaire's existing structure per the kickoff prompt's own instruction. Add the items above as part of whichever corrective batch closes the corresponding defect, so the questionnaire and the fix land together.

---

## E. Test-Gap Inventory

Only gaps judged meaningful (i.e., an area a defect could hide in, or already hid in, without any test noticing) are listed; each is cross-referenced to its defect/finding above where one exists.

1. No test exercises `LabelColorDialog`'s real reachability (or intentional non-reachability) — `test_player_window_workspace.py:465-509` calls the private handler directly, proving nothing about the UI surface. Companion to Correction 1's cleanup recommendation.
2. No test asserts Guided Session/Quick Practice diagnosis panels react to `label_color_change_bus` — companion to P2-1.
3. No test covers two open `RecordingPanel`s where one is actively recording — companion to P2-2.
4. No test asserts post-rename selection state in `MainWindow` — companion to P2-3. (Archive/Restore/Remove do **not** need an equivalent test added for "selection preservation," since disappearing from the view is their correct behavior; a test confirming *that* — the list no longer contains the item, and the empty-selection state renders cleanly — would still be a reasonable addition, but is not closing a defect.)
5. No test covers open-secondary-window title staleness when the underlying material is renamed — companion to P2-4.
6. No test asserts displayed timestamp text/format for Continue Learning, Activity, Diagnoses, Shadowing/High-Frequency lists, or the quiz trend chart — companion to P2-5.
7. No test asserts the "No Notable Difficulty" button's enabled state vs. existing diagnosis evidence — companion to P3-1.
8. `[CLOSED — Batch B / B3]` No permanent regression test locked in the now-directly-verified-safe remove-while-open-window write path (Correction 3c) — this revision's disposable diagnostic proved the behavior but was deleted per its own non-destructive/temporary mandate. **Closed**: `test_removing_material_while_player_open_then_saving_leaves_no_orphan_write` in `tests/integration/test_player_window_workspace.py` promotes the smallest representative version into the permanent suite (open Player on material X → remove X via the real Library service path → attempt a representative annotation write from the still-open window → assert no exception, no orphan `annotation` row, the cascade-deleted rows are actually gone, and a handled status message is shown). Test-only change; the reproduction confirmed current behavior is unchanged from Correction 3c's original finding, so no production code was touched for this item.
9. `QuizWindow._on_submit_clicked` (the real submit UI handler — confirmation dialog, unanswered-count warning, review-then-close sequencing) is never exercised end-to-end; existing tests call `quiz_service.submit_quiz` directly instead.
10. No regression test exists for the M14 Phase 0 `_wrap_scrollable` change across Learning History's 7 tabs; no test exists for `import_dialog.py` or `migrations.py`'s rollback path; no unit test was located exercising non-BMP (surrogate-pair) text through `apply_range_highlighting` end-to-end.

---

## F. Proposed Corrective Batches

Grouped by shared root cause/surface. Re-derived this revision now that no P1 exists — ordering below reflects everyday workflow frequency and evidenced risk, not a mechanical "highest label wins" rule.

### Batch 1 — `[DONE — implemented as M14 Corrective Batch A1/A2]` Rename consistency (Library selection + cross-window staleness)
- **Goal**: preserve Library-list selection after a rename; notify already-open dependent windows so their title stops going stale.
- **Findings included**: P2-3, P2-4.
- **Why first**: rename is exercised by essentially every user in ordinary Library management, and both findings are narrowly scoped, code-verifiable, and now precisely bounded to one action (not four) after Correction 2/3 — the cheapest batch to close correctly.
- **Likely files**: `main_window.py` (`_on_rename_clicked`, `refresh_library`), a rename-notification signal (new, or reuse/extend `recording_change_bus` — needs a naming decision since that bus's name is recording-specific).
- **Regression strategy**: automated tests for selection-preservation (test gap 4) and open-window title-refresh-on-rename (test gap 5).
- **Human retest**: not required.
- **Dependencies**: none.

### Batch 2 — `[DONE — implemented as M14 Corrective Batch B1]` Local-time display sweep
- **Goal**: apply `format_local_timestamp` to the 5 remaining Learning History surfaces and the quiz trend chart's point labels.
- **Findings included**: P2-5.
- **Likely files**: `learning_history_window.py`, `learning_history_service.py`.
- **Regression strategy**: string-format assertions per surface, plus one DST-boundary case (test gap 6).
- **Human retest**: not required; fully code-verifiable.
- **Dependencies**: none. Can run fully in parallel with Batch 1.
- **Status**: see P2-5's `[RESOLVED — Batch B / B1]` entry in Section B for full implementation detail, including the `ui/time_display.py` → `domain/services/time_display.py` relocation this batch made along the way.

### Batch 3 — `[DONE — implemented as M14 Corrective Batch A3]` Live-refresh bus completeness for diagnosis panels
- **Goal**: extend `label_color_change_bus` subscription to Guided Session Stage 3 and Quick Practice diagnosis panels; resolve the `LabelColorDialog`/`_label_colors_button` dead-code cleanup decision (delete, or add an explicit non-reachability test) from Correction 1.
- **Findings included**: P2-1, plus the Correction-1 cleanup item.
- **Likely files**: `guided_session_window.py`, `quick_practice_window.py`, `label_color_dialog.py`/`player_window.py` (cleanup).
- **Regression strategy**: bus-subscription tests for both windows (test gap 2); a deliberate reachability test either way for the cleanup item (test gap 1).
- **Human retest**: recommended smoke check for the live-refresh half.
- **Dependencies**: none.
- **Status**: P2-1 done (see P2-1's `[RESOLVED]` entry in Section B). The Correction-1 dead-code cleanup item (`LabelColorDialog`/`_label_colors_button`) was explicitly **deferred to Batch C** by the Batch A kickoff instruction ("Cleanup may be deferred to Batch C unless removing it is trivially safe and all affected tests are updated") and remains untouched — still filed as a TEST COVERAGE GAP, not a defect.

### Batch 4 — `[DONE — implemented as M14 Corrective Batch A4]` Cross-panel recording-button awareness
- **Goal**: give `_RecordingChangeBus` a "recording started/stopped" event so a sibling `RecordingPanel` disables Start Recording proactively instead of failing post-click.
- **Findings included**: P2-2.
- **Likely files**: `recording_panel.py`.
- **Regression strategy**: automated cross-panel test (test gap 3).
- **Human retest**: not required.
- **Dependencies**: none. Narrowest-frequency scenario (requires two panels open simultaneously) — lowest priority of the four P2 batches, safe to defer if the Product Owner wants a smaller M14 close-out slice.

### Batch 5 — `[PARTIALLY DONE — P3-1 and test gap 8 implemented as M14 Corrective Batch B2/B3; G-1/G-2 still open]` Small UX correctness + governance cleanup + durable safety regression test
- **Goal**: gate the "No Notable Difficulty" button on absence of existing diagnosis evidence; reconcile the `899`→`900` test-count wording drift in `ROADMAP.md` (G-1); align `MainWindow`'s dossier-tooltip/status-bar path display with the elision convention `import_dialog.py`/`ExportDialog` already follow (G-2); promote this revision's disposable remove-while-open-window reproduction into a permanent regression test (test gap 8).
- **Findings included**: P3-1, G-1, G-2, test gap 8.
- **Likely files**: `guided_session_window.py`, `ROADMAP.md`, `main_window.py`, a new test in `tests/integration/`.
- **Regression strategy**: one test for the button-gating fix (test gap 7); one new permanent test for the remove-while-open safety property; doc fixes need no test.
- **Human retest**: not required.
- **Dependencies**: none. Lowest risk — safe to bundle into whichever other batch lands first, or ship standalone.
- **Status**: Batch B's B2 and B3 closed the P3-1 button-gating fix and the test-gap-8 permanent regression test (see Section B and Section E). Batch B's own kickoff scope was explicitly B1/B2/B3 only — **G-1 and G-2's documentation fixes were not part of Batch B and remain open**, still the smallest possible remaining scope (two one-line doc/tooltip edits, no test needed).

---

## G. Governance / Documentation Drift Inventory

Exactly two items meet the classification contract's definition ("repository current-truth documentation contradicts the actual product/lifecycle") after this revision's corrections removed the one item that didn't actually belong here (the former G-3, resolved by Correction 1 — the in-code comment about `LabelColorDialog` turned out to be *accurate*, not drifted, so it was never documentation drift in the first place).

**G-1. Test-count wording drift (`899` vs. `900`) in `ROADMAP.md`**
- Exact finding: `ROADMAP.md:464` states *"automated test suite expanded to **899** passing tests,"* while `PROJECT_STATUS.md:3,24,51,84` and this audit's own re-run all confirm **900**.
- Affected document/surface: `ROADMAP.md`'s Milestone 14 Phase 0 closeout entry.
- Why governance drift, not UX/test debt: this is a factual claim in a lifecycle-tracking document that no longer matches the current, verified engineering state — exactly the contract's definition, not a code or test quality issue.
- Corrective destination: fold into **Batch 5** (Section F) — a one-line documentation edit, no test needed.
- Already named as a known low-priority item in the Phase 1 kickoff prompt itself (Section 13); this audit independently re-confirms it rather than discovering it fresh.

**G-2. `MainWindow`'s dossier tooltip/status bar does not follow the repo's own stated path-elision convention**
- Exact finding: `main_window.py:223` (`self._status_label.setToolTip(f"Database path: {self._db_path}")`) and the dossier's file-path tooltips show the full absolute local path on hover, while `import_dialog.py:122-125` carries an explicit in-code comment describing itself as following "the same elision pattern as MainWindow's/ExportDialog's Batch 0/3 fixes" — a claim that `MainWindow`'s own dossier/status-bar code does not actually honor.
- Affected document/surface: in-code comment in `import_dialog.py` vs. actual behavior in `main_window.py`.
- Why governance drift, not UX/test debt: the drift is specifically between a documented convention (asserted in-code, attributed to specific prior fixes) and the current code's actual behavior — a truth-vs-reality mismatch, not a missing test or a stylistic inconsistency without a documented baseline to diverge from. Not classified as a privacy/security defect: this is a local single-user desktop app and paths never leave the machine.
- Corrective destination: fold into **Batch 5** (Section F).

---

## H. Deferred / Accepted Limitations

Positively verified during this audit (including this revision's corrections) as **not** defects — listed so they are not re-investigated in a future pass without new evidence:

- `_label_colors_button`/`LabelColorDialog`/`_on_open_label_colors` are intentionally unreachable compatibility code, not a live second settings path (Correction 1) — cleanup recommended but this is not a product defect.
- Archiving/restoring a material correctly and expectedly removes it from the currently-displayed list; this is the list behaving as designed, not a selection-loss bug (Correction 2).
- Removing a material correctly removes all list membership since the record no longer exists; not a selection-loss bug (Correction 2).
- Already-open dependent windows continuing to function normally after their material is archived/restored is consistent with "archiving is reversible and non-destructive, only new opens on archived materials are blocked" (Correction 3b) — a deliberate design choice, not an oversight, though worth an explicit Product Owner confirmation if stricter behavior is ever wanted.
- Removing a material while a dependent window is open, followed by a representative write from that window, was **directly reproduced** this revision: no crash, no orphan row, and a cleanly handled (if not maximally clear) user-facing error message (Correction 3c) — verified safe, not merely assumed safe.
- Player's `RuledTextEdit` "Clear Selection" (M14 Phase 0) correctly leaves editing-cue and playing-cue state untouched.
- `MaterialLoopSettingsDialog`'s cache-plus-`showEvent`-refresh-plus-cross-window-bus pattern is a correctly implemented reference example — cited as the pattern Batch 3 should replicate for label colors.
- `SettingsDialog`'s dirty-state discard on window-close (vs. Apply/Cancel) is ordinary, non-corrupting dialog UX, consistent with conventions elsewhere in the app.
- Axis 7→8's previously-documented Quick Practice Step-3 horizontal-overflow debt is verified genuinely resolved via the `FlowLayout` conversion — not merely relocated. One narrow caveat (a single button wider than the available line width won't wrap) is flagged HUMAN-ONLY for extreme-width/long-localized-text cases, not a confirmed defect.
- Session-linked recording gating (must be active session + Shadowing stage) intentionally does not apply to Quick Practice/standalone Shadowing Practice — consistent by design, not a regression.
- Missing-recording-file handling (playback, comparison, single/bulk deletion) is consistent across all three hosting surfaces.
- No recording file paths, device descriptors, or other privacy-sensitive values were found in any log/print statement across the Recording/Quick Practice/Shadowing surfaces.
- Migration atomicity (`migrations.py`) and startup crash handling (`app.py`) are both solid.
- Missing-media/missing-subtitle handling is genuinely consistent across every entry point via one shared `load_material_for_player` chokepoint.
- Export privacy boundary (`export_service.py`, `export_privacy.py`) is sound — no absolute path, device descriptor, or app-data value can reach an export.
- Double-click navigation from Learning History's various lists into the corresponding source windows was spot-checked and found correctly wired.
- Stage-completion downgrade deliberately never re-checks a `skipped` stage (documented, intentional invariant).
- `record_session_diagnosis`/`enter_stage`/`submit_quiz` all correctly wrap multi-write sequences in commit/rollback transactions.
- Guided Session Stage 3's `DiagnosisNoteRow`/`FlowLayout` list-row rework was actively re-tested against click-to-select behavior via a live PySide6 harness and found not to be a regression.
- Needs Attention actually implements 7 independently-thresholded reasons (not 6 as the kickoff prompt's own bookkeeping note assumed) — all 7 are correctly wired end-to-end; this corrects the audit brief's premise, not a product finding.

---

## I. Recommended Next Action

~~Start corrective implementation with **Batch 1 (rename consistency)**...~~ — **superseded by the Batch A implementation below.**

**Post-acceptance update**: Batches 1, 3, and 4 (findings P2-3, P2-4, P2-1, P2-2 — everything in Section C's Pattern 1 "incomplete bus rollout" and Pattern 2 "truthful-before-click" instances that Batch A's scope covered) are implemented, tested, and merged to this branch as **M14 Corrective Batch A — Cross-Window State Consistency**. See each finding's `[RESOLVED — Batch A]` marker in Section B for implementation/test detail.

**Batch B update**: M14 Corrective Batch B — Semantic & Time-Display Correctness — closed **P2-5** (B1: local-time display sweep, plus a `time_display.py` relocation to `domain/services/`) and **P3-1** (B2: "No Notable Difficulty" truthful-availability fix), and permanently locked in the remove-while-open-window safety property with a real regression test (B3, closing the former test gap 8). See each finding's `[RESOLVED — Batch B]` marker in Section B, and Section E's item 8, for implementation/test detail. **All 6 confirmed defects from the accepted Phase 1 map are now resolved — none remain open.**

**What remains**:
- **G-1 and G-2** (governance/documentation drift, Section G): not started. Two one-line doc/tooltip edits, no test needed, no dependency on anything else.
- The Correction-1 dead-code cleanup (`LabelColorDialog`/`_label_colors_button`) remains explicitly deferred, per the Batch A kickoff's own instruction, to a later "Batch C."
- Human QA questionnaire reconciliation (Section D) is deliberately deferred until the remaining corrective batches stabilize, per instruction, to avoid repeated document churn. With all confirmed defects now closed, this reconciliation pass is the natural next major step.

Do not begin Phase C2/Phase D until Human QA Round 2 runs against the corrected product, per the Phase 1 kickoff's own scope boundary (unchanged from the original recommendation). G-1/G-2 and the deferred cleanup are low enough risk that they need not block that pass, but should be closed out before M14 itself is declared complete.

Do not begin Phase C2 (clean-machine acceptance) or Phase D (release candidate) until this batch sequence is closed and Human QA Round 2 has run against the corrected product, per the Phase 1 kickoff's own scope boundary.

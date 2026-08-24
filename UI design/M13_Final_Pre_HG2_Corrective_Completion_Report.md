# M13 Final Pre-HG2 Corrective Completion Report

## 1. Remote state

- Branch: `milestone/13-advanced-ui-ux`
- New remote HEAD SHA: `bc9abd6444722a525a6c5ef1cab9dacc1a505309`
- Previous HEAD (start of this pass): `ee027a4`
- Working tree: clean of engineering changes after commit; only pre-existing local-only artifacts remain untracked (`handoff/`, `UI design/new evidence*`, `UI design/task.md`, `UI design/implementation_plan.md` — the user's screenshot evidence and a stale duplicate plan from a prior pass, deliberately not committed)
- No merge to `main`. No PR opened or merged. `main` was independently verified already merged with Phase 12-A (`PR #1`, `main` at `6ef3997`) — this was discovered during the governance audit (see §8), not caused by this pass.

## 2. P0 progression regression

**Root cause**: `GuidedSessionWindow._on_save_and_continue_clicked()` (`src/listentrace/ui/windows/guided_session_window.py`) called `svc.complete_stage(...)` inside a `try/except SessionValidationError: pass` and then **unconditionally advanced to the next stage regardless of whether completion succeeded**. This matches the user's screenshot evidence exactly: a session reached Stage 5 with "2 STAGES REMAINING: Transcript Comparison & Error Diagnosis, Sentence-Level Shadowing" still shown, and the disabled `Complete Session` button circled — Stages 3 and 4 were never legally resolved.

**Exact code change**:
```python
except SessionValidationError as exc:
    self._show_status(str(exc))
    self._refresh_state()
    return
```
replacing the previous `except SessionValidationError: pass` that fell through to the advance logic unconditionally.

**Tests proving Stages 1–4 cannot advance illegally** (`tests/integration/test_guided_session_window.py`):
- `test_save_and_continue_does_not_advance_when_stage1_completion_fails`
- `test_save_and_continue_does_not_advance_when_stage2_completion_fails` (also asserts the transcript is not revealed as a side effect)
- `test_save_and_continue_does_not_advance_when_stage3_completion_fails`
- `test_save_and_continue_does_not_advance_when_stage4_has_unresolved_cues`

**Proof a valid Stage 1→5 flow still enables Complete Session**:
- `test_save_and_continue_valid_flow_reaches_complete_session` — walks a fully legal path through all 5 stages, asserts every stage ends `completed`/`skipped`, `Complete Session` becomes enabled, and clicking it actually transitions the session to `completed`.

**Two pre-existing tests corrected** — both had unknowingly relied on the bug to advance past an empty Stage 1/2 without filling it in (`test_reveal_confirmation_declined_stays_on_stage2`, `test_stage_stepper_and_stage2_scope_fidelity` in `test_batch_5a_m13.py`); both now fill valid stage data first, matching their actual documented intent.

## 3. Player clipping

**Layout change**: the Annotate tab's 5 annotation-category `QCheckBox` widgets were laid out in a single `QHBoxLayout` row (`src/listentrace/ui/windows/player_window.py`). At the right workspace pane's real width (~250px at a 1080px whole-window width), even a 3-column grid still clipped the longest label ("connected reduced speech"). Switched to one checkbox per row (`QGridLayout`, 1 column, 5 rows) — guaranteed to fit at any window width since it never needs more than one label's worth of horizontal space.

**Narrow-width verification**: re-captured a 1080×720 screenshot after the fix and cropped the right pane — all 5 category rows render fully within the pane with margin to spare, none clipped or bleeding past the window edge (previously the pane's checkbox row extended past the window's right edge). See `manual-qa/screenshots/m13_pre_hg2/02_player_window.png`.

## 4. StageStepper clipping

**Size/layout correction**: `StageStepper`'s step `QPushButton` items had no explicit minimum height — a `QPushButton` with a directly-assigned internal layout does not reliably size-hint tall enough to contain a 22px badge plus its margins/border/focus-ring, which is what clipped badges/labels/borders on every stage in the user's screenshots. Added `btn.setMinimumHeight(_STEP_BUTTON_MIN_HEIGHT_PX)` (44px) — makes the row's height deterministic instead of depending on the QPushButton size-hint quirk.

**Keyboard/accessibility preserved**: no change to focus policy, enabled/disabled logic, or click wiring — only the height constraint was added. All existing StageStepper accessibility tests (illegal-jump prevention, keyboard activation, read-only lockout) still pass unmodified.

## 5. Learning History

- **Directory width/wrapping**: `_section_list` truncated "Shadowing & Recordings" and forced an unwanted horizontal scrollbar at 168px with no wrapping. Fixed with `theme.configure_long_text_list()` (word-wrap, no horizontal scrollbar) plus a modest width bump (168→190px max, 120→150px min). No return to horizontal tabs.
- **Overview metrics presentation**: replaced the raw multi-line `QLabel` (read like a debug/status dump) with a scan-oriented 2-column `QGridLayout` of the same 10 metrics — no new metrics invented, no ranking/score added. Long clarifying detail that doesn't fit a short label (accuracy caveat, shadowing-count caveat) moved into a tooltip instead of inline text.

## 6. Guided Stage 2

**Empty-state correction**: the empty-capture `QListWidget` previously stayed at full stretch height even with zero captures, so the empty-state hint sat underneath a large meaningless blank region rather than owning the space. The list is now hidden and its maximum height collapsed to 0 while empty; the hint gets the stretch factor and centers itself in the freed space. Reverses cleanly when a capture exists (list reappears, hint hides).

## 7. Quiz

**Width/height ownership correction**: canvas max-width increased 680→760px for a more comfortable reading width. More importantly, the canvas card's vertical size policy changed from `Expanding` to `Preferred` (natural content height) with an explicit top-alignment in its row and a trailing `addStretch(1)` in the outer layout — previously a 2-3-option question was force-stretched to the window's full height, putting the dead space *inside* the card's own border; it now lives *outside* the card. Verified visually: `manual-qa/screenshots/m13_pre_hg2/08_quiz_multiple_choice.png` shows the card at its natural height with the excess space below it, outside the border.

## 8. Governance

**Stale statements removed**: audited `PROJECT_STATUS.md` beyond the top summary line, per the instruction. Found and corrected — in the Current Lifecycle Phase, Open Release Blockers, Hardening Progress, Next Engineering Objective, and Repository State sections — every remaining reference to `milestone/12-product-hardening`'s PR as "in preparation" and every citation of `main`'s pre-merge HEAD (`1285fcf`). **Verified fact** (not assumed): `git fetch origin` + `git merge-base --is-ancestor` confirmed Phase 12-A (`milestone/12-product-hardening`) is now actually merged into `main` via PR #1, with `main` at `6ef3997` — this had happened independently of this pass (not something this session did) and the docs were stale relative to it. Historical `## Completed` log entries describing that same PR as "prepared for a PR merge" at the time they were written were left untouched, per "preserve historical narrative that is clearly historical."

**Current lifecycle wording** (top-of-file and Current Milestone section) now reads: implementation + two Pre-HG2 corrective passes complete on `milestone/13-advanced-ui-ux`; HG-2 pending user review; M13 not yet accepted/complete; M12 Phase 12-B not started; `milestone/13-advanced-ui-ux` not merged into `main`.

README.md was also audited per the instruction; its existing M13 status line was already accurate (says Phase 12-A "complete," doesn't claim non-merged or in-preparation) — left unchanged, nothing stale found there.

## 9. Tests

**Targeted results**: every new/modified test file passed in isolation during development (`test_guided_session_window.py`, `test_guided_session_window_m13.py`, `test_batch_5a_m13.py`, `test_learning_history_window.py`, `test_player_window_workspace.py`, `test_player_window.py`).

**Final full-suite result**: **787 passed, 0 failed** (confirmed via a completed run, not partial/truncated output — `115.21s`). This is the actual final count; it is reported honestly rather than reused from the prior pass's 781, per the instruction. Net change from 781: +5 new P0 regression tests, +1 new `RuledTextEdit` phase test, +1 new Learning History section-navigation-adjacent assertion strengthening in `test_overview_reflects_seeded_evidence`, −0 removed (2 pre-existing tests were *corrected*, not deleted, so they still count).

## 10. Visual evidence

The user's own local screenshots (`UI design/new evidence/`) are the trusted evidence and were used to confirm every finding's root cause before fixing (Player clipping, StageStepper clipping, Learning History directory/Overview, Quiz dead space, and the Stage-5-reached-with-2-stages-remaining smoking gun for the P0 bug).

**This session's own screenshot environment remains broken for typography**: `manual-qa/screenshots/m13_pre_hg2/*.png` were regenerated after every fix (`QT_QPA_PLATFORM=offscreen` has no working font backend in this sandbox — all text renders as hollow/tofu box glyphs, exactly as flagged in the prompt's §16). These screenshots were used only for **geometry/layout verification** — widget positions, row counts, clipping boundaries, card borders vs. surrounding space — cross-checked against pixel crops where the finding was subtle (Player's Annotate tab specifically, since the first grid attempt at 3 columns still clipped and needed a second iteration to 1 column, caught only by cropping and visually counting rows). **Explicitly not claimed**: typography quality, text wrapping correctness, or literal copy — those were verified only through the user's real screenshots and code-level reading, never through this session's own captures.

## 11. Remaining debt

**Blocker**: none identified.

**Non-blocking polish**:
- Learning History's filter header row still won't let the window shrink below roughly 1900px wide in this sandbox environment (noted previously, unrelated to this pass's fixes, not one of the registered findings).
- Quiz's canvas still has some vertical space below very short answer sets (3-4 options) even after the natural-height fix — the *forced-fill* problem is solved (space now lives outside the card), but no attempt was made to make the card itself taller/denser for that case, since the prompt's exit gate only required removing the *unnecessarily large internal* blank region, which is done.

**Deferred later-phase work** (unchanged from before this pass, not in scope): Phase 12-B full manual regression, Phase C2 clean-machine validation, Phase D release candidate — all correctly still gated behind HG-2 acceptance and a `main` merge in the updated docs.

**Documented, not fixed** (explicitly low-priority per the prompt, left as-is to avoid destabilizing the Material list): MainWindow's long-CJK-title wrapping quirk (`main_window.py`'s `_material_list` uses `configure_long_text_list()` already; the residual truncation-looking artifact in the user's screenshot is a `QListWidget` item size-hint interaction with unbroken CJK runs, not something this pass's scope covers).

## 12. Final verdict

**`PRE_HG2_EXTERNAL_REVIEW_READY`**

All 12 exit-gate conditions from §21 are met: the progression bug is fixed and proven both ways (illegal-advance blocked, legal-advance still works); Player/StageStepper/Learning-History/Stage-2/Quiz layout findings are fixed and visually re-verified at geometry level; governance docs are internally truthful (verified against real `git` state, not assumed); targeted and full regression both pass (787/787); no new product semantics were introduced anywhere in this pass.

Not merged to `main`. HG-2 has not been declared passed — that remains the user's own review to make.

# M12 Corrective Divergence Map — Phase 0 (Read-Only Audit)

**Status: DRAFT, pending human review. Not committed. No product code or existing
tracked documentation (`HARDENING_BACKLOG.md`, `PROJECT_STATUS.md`, the manual QA
artifact) was modified while producing this file.**

Scope: maps the first Human QA pass's findings to `M12.QA feedback-round 1–4`
(Playback Contract / Desktop Layout Contract / Workflow-Data Semantics Contract /
Repair Architecture & Autonomy Contract), against the actual current implementation,
per Round 4 §3's required format. Every root-cause claim below is grounded in an
actual code read this session, not inference from the questionnaire text alone —
file:line references are given so each claim can be independently re-checked.

This document does not authorize implementation. Per your instruction, execution
begins only after you review this map and explicitly say so.

---

## 0. Corrections to Round 1–3's own assumptions

Round 4 §1 requires checking the contract documents against the real repository
before trusting their illustrative examples. Two corrections surfaced:

1. **Round 3 §21's "Mistake Book / Starred / Proficient Pool / Collections"
   examples do not exist in this codebase.** Grepped the full `src/` tree — no
   `mistake_book`, `starred`, `proficient_pool`, or `collection` concept exists
   anywhere. These were illustrative examples in the contract document, not real
   ListenTrace features. The actual History Deletion Cascade Contract (§4 below)
   is simpler than Round 3's hypothetical examples suggest — there is no
   Mistake-Book-style cross-attempt aggregation to protect.
2. **Round 3 §23's illustrative confirmation text ("this will remove... associated
   retained recordings") does not match the actual schema.** `recording.practice_session_id`
   is `REFERENCES practice_session(id) ON DELETE SET NULL`
   (`src/listentrace/infrastructure/db/migrations.py:268`), not `ON DELETE CASCADE`.
   Deleting a Guided Session today would **not** delete its recordings — they would
   survive, unlinked. Any future Guided-Session-deletion confirmation text must say
   the opposite of Round 3's example (recordings are retained, not removed).

---

## 1. Playback Contract (Round 1) — Divergence Map

| # | Human Finding | Contract | Current Implementation (file:line) | Root-Cause Evidence | Affected Surfaces | Classification | Decision |
|---|---|---|---|---|---|---|---|
| P1 | Quiz/Quick Practice/Shadowing "Play" starts whole-media playback, not the cue (m05-01, m10-05, m12-05) | §3.2 Cue Playback should default in cue-oriented contexts | `quiz_window.py:433`, `quick_practice_window.py:275`, `shadowing_practice_window.py:212` — all three `_on_play_clicked` call only `self._playback.play()`/`.pause()` | **Confirmed.** All three windows share the identical pattern; none scope to the cue. By contrast `_on_replay_clicked`/`_on_loop_clicked` in the same three files correctly call `PlayerSession.replay_cue()`/`.loop_cue()` (already cue-scoped) | Quiz, Quick Practice, Shadowing | Correctness Bug | **Batch B.** `PlayerSession.replay_cue()` (`application/services/player_session.py:63`) already implements exactly the cue-start→cue-end-then-stop semantics Round 1 wants as "Play Cue" default — this is a call-site fix (route the generic Play button through the existing `replay_cue`-style one-shot-stop-at-end path in these 3 windows), not a new playback engine |
| P2 | Repeated Previous Cue can jump to the very start (m02-03, m13-02, intermittent) | §6 Navigation Contract, §6.2 Boundary Behavior | `player_window.py:465-473` `_on_previous_cue`/`_on_next_cue` derive the nav target from `self._session.active_cue_index` — a value recomputed asynchronously from playback position on every `positionChanged` tick (`player_window.py:419-420`) | **Confirmed, high-confidence root cause.** `CueIndex.previous_index(None)` (`domain/services/cue_index.py:37-42`) intentionally returns `0` when given `None`. `active_cue_index` becomes `None` whenever the play position is momentarily in a gap between cues (e.g. right after a seek, before the next position tick lands). Main Player has no separate "Selected Cue" state — Previous/Next silently fall back to cue 0 exactly when `active_cue_index` is transiently `None`, which explains the *intermittent* nature exactly. **`ShadowingPracticeWindow` does NOT have this bug** — it tracks its own stable `self._cue_index` (`shadowing_practice_window.py:53,166-174`), independent of playback position, which is the correct pattern | Main synchronized Player only (Quiz/Quick Practice/Shadowing use their own stable index and are unaffected) | Correctness Bug (State/Explainability root cause: Selected Cue vs Playing Cue conflation, exactly Round 1 §2's core distinction) | **Batch B.** Give `PlayerWindow` its own stable selected/navigation index (mirroring `ShadowingPracticeWindow`'s already-correct pattern) instead of deriving Previous/Next from the async `active_cue_index` |
| P3 | No visible way to cancel Loop Cue except pause+click-away (m02-05) | §7.1 Toggle Semantics — button must show "Stop Loop" while active | `player_window.py:149-150,490-497` — `_loop_cue_button` text is set once at construction (`"Loop Cue"`) and never updated in `_on_loop_cue_clicked`/`_start_loop`/`cancel_loop` | **Confirmed.** No `setText` call anywhere flips the button label on activation/deactivation. The only cancel paths are the `Escape` key and the `L` toggle shortcut (`player_window.py:644-645,660-661`) — both undiscoverable from the UI alone | Main Player (Quick Practice/Quiz/Shadowing don't expose a persistent Loop button in the same way — scope should be verified per-window before implementing) | State/Explainability Defect | **Batch B.** Toggle button text (and ideally a compact non-color loop indicator per §9.4) on loop start/stop |
| P4 | Transcript viewport does not follow playback; user must scroll manually (m02-01, m12-05) | §8 Transcript Playback Follow | `player_window.py:445-456` `_update_active_cue_highlight` only recolors the `QListWidgetItem` background; no `scrollToItem`/`ensureVisible` call exists anywhere in the file | **Confirmed — this is a clean gap, not a partial bug.** The feature (viewport-follow) was never implemented; only highlighting was | Main Player (only surface with a visible transcript list) | Correctness Bug / Missing Behavior | **Batch B.** Implement §8's Follow/Suspend/Return-to-Playing-Cue model on the existing `_cue_list` |
| P5 | Shadowing "Compare" already sequences source→take correctly | §3.6 Compare | `shadowing_practice_window.py:235-260` — `_on_recording_panel_request_play_source` correctly uses `replay_cue` (cue-scoped, not whole-media) and notifies `RecordingPanel` on finish/fail | Confirmed working as intended; no divergence | Shadowing | N/A — already conforms | **No action.** Cite as a positive baseline, not a finding |
| P6 | Main Player's "Play"/"Pause" is whole-media | — | `player_window.py:411-417` | This is **correct per §3.1** — Main Player is supposed to default to Continuous | Main Player | N/A | **No action** |

---

## 2. Desktop Layout Contract (Round 2) — Divergence Map

| # | Human Finding | Contract | Current Implementation | Root-Cause Evidence | Affected Surfaces | Classification | Decision |
|---|---|---|---|---|---|---|---|
| L1 | Small window hides the bottom; maximized window still squeezes the Transcript Workspace's input fields/buttons to unreadable thinness (m03-01, m03-04, m03-05, screenshots confirm) | §4 Persistent Header + Scrollable Content + Persistent Action Bar; §6 Multiline Input Contract | `player_window.py:109-221` — the entire central widget (title, media area, seek bar, transport row, Quick Practice row, volume row, `_cue_list`, `_workspace_panel` splitter, status labels, Return button) is one non-scrollable `QVBoxLayout`. No `QScrollArea` exists anywhere in the file. `_cue_list` gets stretch factor 1 (`layout.addWidget(self._cue_list, 1)`, line 202); every workspace-panel `QLineEdit`/`QPushButton` has **no minimum height set** | **Confirmed via 2 screenshots** (`manual-qa/results/03-1...png`, `03-2...png`): "Save Item / Update / Delete" button row and every `QLineEdit` in both columns render as unreadable slivers. Root cause: when total content height exceeds the window, Qt compresses every zero-minimum-height widget rather than scrolling, because there is no scroll container at all | `PlayerWindow` (all other windows checked did not exhibit this specific pattern, but were not screenshot-verified individually — see Batch C note) | Release-Blocking Layout Defect (blocked m03-01/04/05 outright) | **Batch C.** Wrap the workspace panel (at minimum) or the whole central widget in a `QScrollArea`; give the annotation/item-column `QLineEdit`s explicit minimum heights, per §4/§6 |
| L2 | Long Quiz answer options get hard-truncated with an ellipsis, never wrap, regardless of window size (m05-01, screenshot confirms) | §12 Quiz Text Is Primary Reading Content | `quiz_window.py:182-193,365-367` — answer choices are rendered as `QRadioButton("")` with `radio.setText(choices[index])` | **Confirmed, and it is a widget-choice problem, not a missed property.** `QRadioButton`/`QAbstractButton` has no word-wrap capability in Qt Widgets at all — there is no `setWordWrap` on this class, so this cannot be fixed by flipping a flag | Quiz | Release-Blocking Layout Defect | **Batch C.** Per §12, pair each `QRadioButton` (selection control only) with a separate `QLabel(wordWrap=True)` for the option text, or build the "clickable multiline answer card" §12 describes |
| L3 | General "display scaling is bad, no wrap/scroll awareness" (m12-02) | §21, §26 | Not separately re-verified beyond L1/L2 — the questionnaire item is broad and likely restates L1/L2 from a different module | Overlaps L1/L2 | Same as L1/L2 | Superseded by L1/L2's concrete root causes — do not treat as a third independent defect | **Fold into Batch C**, re-verify after L1/L2 land whether any distinct instance remains |
| L4 | Other complex windows (Guided Session, History windows) were not screenshot-verified for the same squish pattern | §13, §18 | Not inspected yet — Phase 0 did not exhaustively check every window's layout code | Unverified | Guided Session, History/List windows | Unverified — do not assume Pass or Fail | **Batch C** should include a representative smoke pass (per §25's Layout Smoke Matrix) across Guided Session and List/History windows before declaring Batch C done, since L1 shows the same missing-scroll-container pattern could plausibly recur wherever a window lacks a `QScrollArea` |

---

## 3. Workflow / Data Semantics Contract (Round 3) — Divergence Map

| # | Human Finding | Contract | Current Implementation | Root-Cause Evidence | Affected Surfaces | Classification | Decision |
|---|---|---|---|---|---|---|---|
| W1 | Guided Session: Stage 5 filled in, "Complete Session" stays disabled (m08-04, m10-01, m10-03) | §5–§11 Completion Contract | `domain/services/session_rules.py:29-57` implements stage1–5 predicates and `session_can_complete` **exactly matching Round 3's own target model already** (verified against `tests/integration/test_practice_session_service.py:261-269`, a passing service-level test that saves a Stage-5 summary then calls `complete_stage` and asserts it succeeds). `guided_session_window.py:273` correctly reads the single authoritative `rules.session_can_complete(statuses)` — no duplicated local readiness logic found | **The domain/service layer is verified correct — this is very likely a UI State/Explainability gap, not a logic bug.** Stage 5 only becomes `completed` when the user clicks the shared "Save and Continue" button (`guided_session_window.py:146-147,337-348`) — the same label is reused for every stage, including the last one, where "Continue" has nowhere to go. A user who types the summary and does not realize they still need to click that specific button (because it says "Continue", not "Save" or "Finish") would see exactly the reported symptom. **No UI-level automated test exercises this exact end-to-end path** (`tests/integration/test_guided_session_window.py` has no Stage-5→Complete-button test), so a genuine UI-wiring bug on top of the discoverability gap cannot be fully ruled out without a new targeted test | Guided Session | State/Explainability Defect (high confidence) with residual small chance of a real UI-wiring bug not yet isolated | **Batch A** (release-blocking per Round 4 §6). First step of the fix batch: write the missing UI-level regression test for exactly this path to settle which it is, then (a) relabel the final stage's action distinctly from "Continue", and (b) add the §9 "why is Complete disabled" explanation near the button |
| W2 | Ghost recording Take after deletion: file gone, DB row/UI entry remains, clicking shows "Not Found", and re-deleting it also silently fails (m06-08) | §34 Ghost Take is a must-fix Data/Live-State Consistency Bug | Deletion path itself is clean: `remove_material` (`material_library_service.py:82-104`) deletes recording files+rows via `delete_takes_for_material` *before* deleting the material row, and only one call site exists (`main_window.py:607`) — no bypass path found. `RecordingPanel._on_delete_take_clicked` (`ui/widgets/recording_panel.py:404-422`) correctly calls `_refresh_takes()` after a successful delete within the *same* window | **Two-part confirmed root cause.** (a) No cross-window refresh signal exists anywhere in the codebase — if a second window (e.g. a separately-open Shadowing/Quick Practice/Guided Session window) is showing the same cue's takes when a deletion happens elsewhere, its `RecordingPanel` list is never invalidated, producing exactly the stale "Not Found" row on click (`recording_panel.py:398-400`, the file-missing warning). (b) Retrying Delete on that ghost row then silently does nothing: `recording_service.delete_take` raises `RecordingNotFoundError` (`recording_service.py:29`) when the row is already gone, but `_on_delete_take_clicked`'s `except RecordingValidationError` (`recording_panel.py:420`) does **not** catch it — `RecordingNotFoundError` and `RecordingValidationError` are sibling classes, not parent/child (`application/errors.py:103,109`) — so the exception escapes uncaught and the stale row is never removed from the list | Any window using `RecordingPanel` while another window/action deletes the same underlying recording | Data / Live-State Consistency Bug (must-fix per Round 3 §34) | **Batch A.** Two bounded fixes: (1) catch `RecordingNotFoundError` alongside `RecordingValidationError` in `_on_delete_take_clicked` and refresh/clear the stale row regardless; (2) add a refresh mechanism so open `RecordingPanel` instances pick up deletions made elsewhere (exact mechanism — Qt signal, or refresh-on-window-activate — is an implementation choice, not a decision-gate item) |
| W3 | Interrupted recording leaves a residual record (m10-02) | §35 Product Semantics Decision — must not masquerade as a valid Take | `recording_service.recover_interrupted_recordings` (`recording_service.py:216-226`), run once at app startup (`ui/app.py:59-61`): deletes the partial file and marks the row `failed` with a reason. `RecordingPanel._refresh_takes` (`recording_panel.py:357-375`) shows failed takes labeled `"Take #N — failed (<reason>)"`, and `_update_take_buttons` (`recording_panel.py:384-391`) disables Play/Compare for anything not `READY` | **Already matches Round 3 §35's own "Potentially acceptable" model almost exactly**: `status = failed`, not playable, clearly labeled, does not count as a retained Take (`_refresh_takes` only excludes live `RECORDING`-status rows from the *in-progress* filter, but failed rows are correctly never treated as usable evidence anywhere else in the code checked) | Shadowing / Quick Practice / Guided Session Stage 4 (shared `RecordingPanel`) | Product Semantics Decision — **already resolved by existing implementation** | **No code change recommended.** If you want the failed row to eventually disappear from the list entirely rather than stay as a labeled "failed" entry, that is a small opportunistic UX preference to confirm with you, not a defect |
| W4 | Same `.wav` rejected on second import paired with a different subtitle format (m01-02) | §3 QA Specification Defect (already Round 3's working hypothesis) | `material_import_service.py:68-85` — two-tier duplicate policy: identical **file path** is a hard, unconditional block (`duplicate_path`, no override); identical **file content under a different path** (fingerprint match) goes through an explicit `ImportNeedsConfirmation` confirm-to-proceed flow | **Confirmed exactly as Round 3 hypothesized, with more precision than the hypothesis had.** The tester reused the literal same file path for both import attempts, which hits the unconditional, intentional `duplicate_path` invariant (no confirm override exists for this case by design — only the fingerprint case is confirmable) | Manual QA fixture only; import behavior is working as designed | QA Specification Defect | **Fix the QA fixture, not the product** (Round 3 §3's own conclusion, now code-confirmed): add a second audio file with equivalent content under a distinct filename for the SRT/VTT-equivalence test, per Round 3's own suggested approach |
| W5 | No delete option in various History views (m05-02) | §16-§32 History Ownership Contract | See §4 below (Feasibility Gate) | — | Learning History, Quiz History, Session History | Major Product Semantics Decision, subject to the Round 4 Feasibility Gate | **See §4** |
| W6 | Recording deletion is one-at-a-time or all, no arbitrary multi-select (m06-06) | §36 Workflow Enhancement | `recording_panel.py` exposes only `_on_delete_take_clicked` (single) and `_on_delete_all_takes_for_cue_clicked` (all) — confirmed, no partial-selection code path exists | Confirmed absent, as expected — this was never claimed to exist | Recording | Workflow Enhancement | **Deferred to v1.1**, per Round 3 §36 / Round 4 §14 — opportunistic inclusion only if Batch C's layout work on this panel happens to introduce a selection model for free, not on its own |
| W7 | Timestamps shown ~4 hours off from local time (m08-02) — **root cause already confirmed in a prior turn this session**, restated here for completeness | §37-§41 Time Contract | `session_history_dialog.py:64-66`, `quiz_history_dialog.py:66`, `learning_history_window.py:477,608,632,754,797` all interpolate `started_at`/`completed_at`/`created_at` directly into display strings with no `.astimezone()` or equivalent conversion anywhere. Storage is confirmed canonical UTC (`domain/services/date_range.py:68`, `export_service.py:48`) | Confirmed (verified last turn, re-confirmed present) | Session History, Quiz History, Learning History window (all history/timestamp displays) | Correctness Bug / Time Contract | **Batch A.** Centralize a single local-time display conversion helper and apply it at every listed call site; also audit local-calendar filter boundaries (`date_range.py`) per §39 before considering this closed, not just the visible label text |
| W8 | Export privacy redaction "na" in the questionnaire (m11-04) — verified last turn, restated for completeness | §40 Timezone Awareness in Export (unrelated) / general privacy | Read `manual-qa/results/One Material — normal_lesson_2026-08-11-隐私未勾选.json` directly: `transcript_excerpt`, `meaning`, `context_excerpt`, `source_label` are all `"[redacted]"` with privacy fields unchecked | Confirmed working as specified | Export | **Not a defect — the questionnaire's own answer should be corrected from "na" to "pass"** | **No product action.** Flag as a QA-record correction only (the manual QA *result*, not the questionnaire itself, so no artifact file needs editing — just noted here for your awareness) |

---

## 4. History Deletion Feasibility Gate (Round 4 §10-§12)

Per Round 4's explicit preauthorized-conditions checklist:

| Condition (Round 4 §11) | Finding |
|---|---|
| 1. No new schema version/migration required | **Met.** All FK relationships needed already exist and are already correctly shaped (see §0 above) |
| 2. No major data-model redesign required | **Met** |
| 3. Ownership/cascade relationships sufficiently clear from current schema | **Met.** Verified directly in `migrations.py`: `practice_session` deletion would cleanly cascade to `session_stage_progress`, `stage_response`, `keyword_capture`, `session_diagnosis_evidence`, `shadowing_cue_progress` (all genuinely session-owned) while `annotation`/`saved_language_item`/`recording` are protected via `ON DELETE SET NULL`, never cascaded. Same pattern holds for `quiz_attempt` → `quiz_question` → `quiz_answer` (cascade) vs. `annotation`/`saved_language_item`/`keyword_capture` source references (`SET NULL`). `quick_practice_session` already has a repository-level `delete_quick_practice_session` function (`quick_practice_repository.py:123-126`) — currently unused by any service or UI code, i.e. partially-built infrastructure from an earlier milestone |
| 4. Transaction safety can be guaranteed | **Met**, using the same `commit: bool = True`-threading pattern already established elsewhere in this branch's earlier hardening batches |
| 5. Derived statistics/counters can remain correct | **Met.** `learning_history_service.py`/`history_repository.py` compute every Overview/Activity statistic live via SQL aggregation each time — confirmed during the M12.4 Performance Decision Gate work — there are no stored/denormalized counters to keep in sync |
| 6. Independent user assets protected from accidental deletion | **Met** — by schema design, not by service-layer discipline that could drift |
| 7. Export and open UI state can stay consistent | **Conditionally met** — requires the same "no open view may show stale/ghost data" refresh work already scoped for W2 (ghost Take); reasonable to build once and reuse for both |
| 8. Bounded and reviewable | **Met** — single-record delete for `completed`/`abandoned` sessions across 3 history types is a small, well-scoped feature given the above |

**Conclusion: the Feasibility Gate passes. Round 4 §11 authorizes single-record
History deletion (completed/abandoned Guided Sessions, Quiz attempts, Quick
Practice sessions) as part of the autonomous corrective batches, once you grant
execution authorization** — not as a Level-3 stop condition. One correction to
flag per §0: any confirmation dialog text for Guided Session deletion must say
recordings are **retained** (schema is `SET NULL`), the reverse of Round 3 §23's
illustrative example text.

Recommended scope for v1.0 given Round 3 §29: single-record delete of
completed/abandoned sessions only, standard confirmation dialog stating actual
cascade impact, no bulk/multi-select, no archive/soft-delete.

---

## 5. Batch Assignment Summary

| Batch | Items |
|---|---|
| **Batch A — Release Blockers / Correctness** | W1 (Guided Session Complete stuck), W2 (ghost Take + swallowed exception), W7 (UTC/local time display) |
| **Batch B — Playback Convergence** | P1 (Play button whole-media in Quiz/QP/Shadowing), P2 (Previous Cue jump-to-start), P3 (Loop button never shows Stop Loop), P4 (transcript auto-follow missing) |
| **Batch C — Layout Convergence** | L1 (PlayerWindow workspace panel squish — missing QScrollArea + min-heights), L2 (Quiz QRadioButton can't wrap), L3 (fold into L1/L2), L4 (representative smoke pass on other windows, currently Unverified) |
| **History Deletion Gate** | W5 — **Gate passed**, authorized pending your execution sign-off (see §4) |
| **QA-Spec Correction (not product code)** | W4 (duplicate-path fixture), W8 (m11-04 answer should read "pass") |
| **No Action / Already Correct** | P5, P6, W3 |
| **Deferred to v1.1** | W6 (recording multi-select) |

No Level-3 stop condition was triggered anywhere in this audit: no schema
migration, no data-model redesign, no technology-stack change, and no
product-contract conflict was found. Everything above fits within Round 4's
Level 1/Level 2 autonomy once you authorize execution.

---

## 6. What Phase 0 Did Not Cover

- L4's "other windows" layout smoke pass was scoped but not executed (Batch C work item, not a Phase 0 gap).
- No DPI/scaling environment testing was attempted (correctly out of scope for a read-only code audit; remains Round 4 §9's "mark Unverified" territory for whichever human/environment pass eventually covers it).
- `import_dialog.py`'s actual UI-level error presentation for `duplicate_path` was not screenshotted — the service-layer rejection message was confirmed, but not how it renders to the user. Low priority given W4 is a QA-fixture fix, not a product fix.

---

**End of Phase 0. Awaiting your review and explicit execution authorization before
any Batch A/B/C work, per the agreed lifecycle:**
`Phase 0 read-only audit → human review (you are here) → explicit execution authorization → autonomous corrective batches under Round 4 → Ready for Human QA Round 2`

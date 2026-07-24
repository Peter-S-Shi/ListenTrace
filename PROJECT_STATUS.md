# ListenTrace Project Status

Last updated: 2026-07-24

## Project Purpose

ListenTrace is a local-first desktop application for transcript-guided foreign-language listening practice and listening-error diagnosis.

## Repository Verification

The remote repository exists, is private, and uses `main` as its default branch. It contains the initial documentation commit, the Milestone 1 application-foundation commit, the Milestone 2 material-library commit, the Milestone 3 synchronized-player commit (plus its acceptance-correction follow-up), the Milestone 4 transcript-workspace commit (plus its acceptance-correction follow-up and a small post-milestone presentation-refresh follow-up), and the Milestone 5 guided-session commit; no pull requests; no continuous-integration configuration.

## Current Engineering State

| Area | Status |
|---|---|
| Product concept | Defined |
| Product workflow | Defined at roadmap level |
| Public engineering documentation | Committed and pushed to `main` |
| Application code | Implemented (foundation + material library + synchronized player + transcript workspace + guided intensive-listening session) |
| Desktop shell | Material library + player window (with integrated transcript workspace) + guided session window (five stages) + session history dialog, manually verified end-to-end |
| Database schema | Schema version 4: adds `practice_session`, `session_stage_progress`, `stage_response`, `keyword_capture`, `session_diagnosis_evidence`, `shadowing_cue_progress` (additive; Milestone 1/2/4 tables unchanged) |
| Media/subtitle import | Implemented and tested (Milestone 2, unchanged) |
| Material library | Implemented and tested (Milestone 2), opens the player (Milestone 3) and the guided session (Milestone 5) |
| Synchronized player | Implemented and tested (Milestone 3 + acceptance-correction pass, unchanged this milestone) |
| Transcript workspace | Implemented and tested (Milestone 4, unchanged this milestone except the shared highlighting extraction described below): multi-label annotations on whole-cue or partial text ranges, Misheard/`heard_as` validation, per-cue Cue Notes (empty-save = delete), Saved Language Items (word/phrase/chunk/sentence_pattern) with exact-duplicate rejection and same-text-elsewhere confirmation, global per-label colors, editing cue kept independent of the active playback cue |
| Guided intensive-listening session | Implemented and tested: five-stage resumable session (global comprehension, keyword capture, transcript diagnosis, shadowing, final summary), one active session per material, explicit skip on every stage, transcript-reveal lock on Stages 1/2, session-scoped diagnosis evidence reusing Milestone 4's annotation tools, shadowing practiced/skipped tracking, completed/abandoned read-only history |
| Subtitle parsing | Implemented and tested (Milestone 1, unchanged) |
| Automated tests | 226 tests passing (8 database/migrations, 8 import, 8 library, 3 media playback, 7 subtitle parsing, 8 cue index, 9 player session, 5 player loading, 13 player window, 11 UI smoke, 7 text range, 7 text-offset conversion, 25 annotations, 6 cue notes, 19 saved language items, 5 label preferences, 20 player-workspace UI integration, 11 session rules, 37 practice-session service, 9 guided-session window) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 5 — Guided Intensive Listening**

Status: **Completed**

## Completed

- Milestones 1–3 (see history; unchanged except where the Milestone 3 acceptance-correction pass is noted)
- Milestone 4 — Transcript Workspace and Listening Diagnosis:
  - Schema version 3 (additive migration, no data loss): `annotation` (with a unique `(subtitle_cue_id, label_key, selection_start, selection_end)` constraint), `cue_note` (one row per cue via `subtitle_cue_id` as primary key), `saved_language_item` (with a unique `(material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized_text)` constraint), and `annotation_label_preference` (seeded with default colors for all 5 labels). Verified to upgrade cleanly from both a Milestone-1 (v1) and a Milestone-2 (v2) database with existing data intact.
  - `domain/services/text_range.py`: pure, framework-free canonical selection-offset validation (`validate_selection`, `whole_cue_range`) — zero-based, end-exclusive, Python Unicode code-point offsets
  - `application/services/annotation_service.py`: atomic multi-label annotation creation (one Save action can create several `Annotation` rows sharing one cue+range, all-or-nothing), validates label keys, enforces "Misheard requires `heard_as`", rejects duplicate label+range, allows different labels to share a range; `update_annotation`/`delete_annotation`/`list_annotations_for_cue`
  - `application/services/cue_note_service.py`: single Cue Note per cue via upsert; saving an empty/whitespace-only note is treated as delete-intent, not a stored empty string
  - `application/services/saved_language_item_service.py`: validates item type and selection range, derives canonical text from the cue substring (not a separately-trusted string), rejects exact duplicates, and returns a typed `SavedItemNeedsConfirmation` when the same normalized text already exists elsewhere (a different cue/material) — the caller must explicitly confirm before it is created
  - `application/services/label_preference_service.py`: validates label key and a 6-digit hex color before persisting; editing a color never touches any stored `Annotation.label_key`
  - `application/services/cue_workspace_service.py`: loads a cue's text, annotations, Cue Note, and saved items together for the UI
  - `ui/windows/player_window.py` extended with an integrated transcript workspace (not a separate window): the cue list's `currentItem` now represents an independently-controlled **editing cue**, decoupled from the **active playback cue** (which is shown only via a background-color highlight, never by moving selection) — playback progress can no longer steal focus from the cue being edited. Adds a selectable read-only transcript view for the editing cue, 5 label checkboxes + conditional `heard_as` + annotation note + Save/Update/Delete, an annotation list with a colored badge icon per row plus per-character highlight in the transcript (single-label color, neutral gray for overlaps), a Cue Note editor, a Saved Language Item form (type/meaning/note/context, context prefilled from the full cue and editable) with its own list, and a "Label Colors..." button opening `ui/windows/label_color_dialog.py`. Hiding the transcript hides the whole workspace panel *and* clears the transcript view's text (defense in depth, not just visual hiding).
  - **Acceptance-correction pass** (post-review), four fixes:
    1. **Unicode offset conversion** — `ui/text_offset_conversion.py` (new): Qt's `QTextCursor` reports UTF-16 code-unit offsets, which are *not* the same number line as the canonical Python code-point offsets the domain/application layers use. Every read from or write to a Qt text widget now goes through explicit conversion (`qt_offset_to_codepoint_index` / `codepoint_index_to_qt_offset`), applied at all 4 points where `player_window.py` touches cursor positions (reading a selection, cursor-position annotation lookup, restoring a selection, highlighting). A `SurrogatePairOffsetError` guards against a Qt offset landing mid-surrogate-pair. Verified end-to-end with a real emoji character through the actual `QTextEdit` widget, not just unit-level string math.
    2. **Truthful annotation/saved-item editing** — `annotation_service.update_annotation` now accepts and re-validates label, range, and text together with heard_as/note (previously Update silently only changed heard_as/note while looking like a full edit); duplicate-check now excludes the row being updated so a no-op re-save doesn't falsely collide, and the update is scoped to a single row by id so it never touches a sibling label sharing the same range. `saved_language_item_service.update_saved_language_item` now allows changing `item_type` (with a re-run duplicate check), but source text/range/normalized_text are an intentionally locked identity — documented in the docstring and in a visible UI note — changing what text an item refers to requires delete-and-recreate.
    3. **Material/cue relationship integrity** — `save_language_item` no longer accepts a `material_id` parameter at all; a new `learning_repository.get_material_id_for_subtitle_cue` derives it from `subtitle_cue -> subtitle_track -> material`, so no caller (UI or otherwise) can create a Saved Language Item associated with the wrong material.
    4. **Color badges** — the annotation list now shows a small colored-square icon per row (from the label's configured color) alongside the still-visible `[label_key]` text; overlapping annotations remain individually selectable with their own badge; a color change refreshes both the badge and the transcript highlight without touching any `label_key` data.
  - 26 new automated tests for this pass (7 text-offset conversion, 6 annotation edit/duplicate-exclusion/label-integrity, 6 saved-item material-derivation/type-edit, 7 player-workspace UI: 2 non-BMP round-trip, 2 annotation full-edit, 1 saved-item locked-source edit, 2 badge/overlap) on top of the prior 136 — 162 total, all passing, including in a clean virtual environment outside the working tree
  - Manual smoke test covering non-BMP selection round-trip, full annotation edit (label+range+heard_as together), saved-item type edit with source locked, badge color refresh, persistence after app restart, and Milestone 3 playback regression — all passed
  - Confirmed zero PySide6 imports remain in `domain/` or `application/` — all Milestone 4 validation/duplicate/canonical-offset logic is framework-free; only `ui/` and `infrastructure/media/` reference Qt
- Post-Milestone-4 follow-up: a targeted annotation-presentation refresh (`player_window.py`) now runs after the Label Colors dialog closes — it reloads label-color preferences, reapplies transcript highlighting, and updates every existing annotation-list badge in place, without the disruptive full workspace reload that previously cleared the editing cue, the selected annotation, and any unsaved form contents on a color change.
- Milestone 5 — Guided Intensive Listening:
  - Schema version 4 (additive migration, no data loss): `practice_session` (with a partial unique index enforcing at most one active intensive session per material), `session_stage_progress` (one row per session/stage, created atomically with the session), `stage_response` (upsert, unique per session/stage/prompt — shared by Stage 1's four prompts and Stage 5's summary), `keyword_capture` (typed, learner-ordered), `session_diagnosis_evidence` (session-scoped diagnosis snapshot with an optional `ON DELETE SET NULL` link to a Milestone 4 `Annotation`), and `shadowing_cue_progress` (one row per session/cue, eagerly created on first Stage 4 entry). Verified to upgrade cleanly from a Milestone 4 (v3) database with existing material/annotation data intact.
  - `domain/services/session_rules.py`: pure, framework-free session/stage transition tables and per-stage completion-eligibility predicates (`stage1_can_complete` .. `stage5_can_complete`, `session_can_complete`)
  - `application/services/practice_session_service.py`: session lifecycle (`start_session`/`resume_session`/`abandon_session`/`complete_session`, each re-validated against `session_rules`), stage navigation (`enter_stage`/`skip_stage`/`complete_stage`, the latter two dispatching per-stage eligibility checks rather than five separate functions), the transcript-reveal lock (auto-resolves Stages 1/2 the first time Stage 3 is entered, so a session can never get permanently stuck on a locked, unresolved stage), keyword-capture CRUD and reordering, session-diagnosis CRUD with material-annotation find-or-create linkage, and shadowing progress
  - `ui/annotation_highlighting.py` (new, extracted from `player_window.py`): the Unicode-offset-aware transcript-highlight painting logic used by both the standalone transcript workspace and the new guided-session Stage 3 panel — not duplicated between them; `PlayerWindow` was refactored to call it with zero behavior change (verified against the full existing Milestone 3/4 test suite)
  - `ui/windows/guided_session_window.py` (new): the five-stage guided session, reusing `PlayerSession`/`PlaybackController` for Stage 3/4 playback and `annotation_service`'s validation rules (via `practice_session_service`) for Stage 3 diagnosis — no forked cue-timing, loop, playback-error, offset-conversion, or label/color logic
  - `ui/windows/main_window.py`: new **Start Intensive Practice** (offers Resume / Abandon and Start New / Cancel when a session is already active), **Resume Intensive Practice**, and **Session History** entry points, alongside the unchanged standalone **Open Player**
  - `ui/windows/session_history_dialog.py` (new): lists every session (active/completed/abandoned) for a material, newest first; opening one resumes it (if active) or opens it read-only (otherwise)
  - 87 new automated tests (11 domain session-rules, 37 practice-session-service lifecycle/stage/diagnosis/shadowing, 9 guided-session-window UI, 5 new MainWindow/SessionHistoryDialog UI smoke, plus the migration test and the 2 schema-version assertions updated for version 4) on top of the prior 163 (net +63 after 2 pre-existing assertions were updated rather than added) — 226 total, all passing, including in a clean virtual environment outside the working tree
  - Manual smoke test covering the full 19-step scenario from the milestone prompt (import → start → close/resume with Stage 1 answer preserved → Stage 2 capture add/edit/reorder/delete → Stage 3 reveal confirmation → Stage 1/2 read-only lock → non-BMP diagnosis → Misheard-requires-`heard_as` → material-annotation reuse without overwrite → Stage 4 practice/skip counts → close/reopen shadowing-progress persistence → Skip Remaining Cues → transcript-free Stage 5 summary → session completion → read-only reopen → repeated diagnosis evidence in a second session → unaffected standalone player/workspace → untouched source files) plus abandonment and new-attempt-after-abandonment — all passed
  - Two real bugs caught and fixed during this milestone's own manual/automated verification (not present in any prior milestone): (1) `GuidedSessionWindow`'s save-before-close logic used a possibly-stale cached session state, so closing the window immediately after completing or abandoning a session crashed with a false "session is read-only" error — fixed by checking live session status; (2) the very first `_show_stage` call during window construction ran the same outgoing-stage save logic as normal navigation, which — for a session resumed on any stage after Stage 1 — silently overwrote real, already-saved Stage 1 answers with the empty text of the just-built (not yet populated) widgets; fixed with an `_initialized` guard that skips the flush exactly once, on that first call
  - Confirmed zero PySide6 imports remain in `domain/` or `application/` — all Milestone 5 lifecycle/stage/diagnosis logic is framework-free; only `ui/` and `infrastructure/media/` reference Qt

### Manual smoke steps verified

Launch and open a valid material; confirm Milestone 3 playback still works; select an editing cue while a different cue becomes active through playback and confirm the editing cue does not move; select part of a cue and save one label; select a range and save multiple labels atomically; attempt a Misheard annotation without `heard_as` (rejected) then with it (succeeds); edit and delete an annotation; create/edit/delete a Cue Note (empty save deletes it); save all four Saved Language Item types with prefilled editable context; trigger exact-duplicate rejection and the same-text-elsewhere confirmation flow; change a global label color and confirm annotation label/text are unaffected; hide/show the transcript and confirm hidden cue text is not exposed; close and reopen the app and confirm annotations/notes/saved items persisted; remove a material and confirm all four learning-evidence tables cascade to zero rows while the original media and subtitle files remain on disk; start/close/resume a guided session and confirm the same stage and answers return; add/edit/reorder/delete Stage 2 captures; confirm the transcript-reveal warning and the resulting Stage 1/2 read-only lock; record a non-BMP-character diagnosis and a Misheard diagnosis (heard_as required); confirm a repeated diagnosis reuses rather than duplicates the material annotation; practice/skip Stage 4 cues and confirm counts/progress persist across close and reopen; write a transcript-free Stage 5 summary; complete a session and confirm it reopens read-only; start a second session on the same material and confirm repeated diagnosis evidence is allowed; abandon a session and confirm a new attempt can start; confirm the standalone player and Milestone 4 workspace are unaffected; confirm original media/subtitle files are untouched throughout.

## Planned Next Work

- Milestone 6 — Quizzes and Recall Practice (see `ROADMAP.md`)

## Known Risks

- Multimedia behavior can vary across operating systems and codec availability; only Windows has been verified.
- Subtitle timing quality varies by source.
- Large media files should not be copied or committed accidentally.
- Plain-text transcripts do not support reliable synchronized navigation without timing data.
- Recording support introduces permissions, device-selection, and local-storage concerns (relevant starting Milestone 7 — no microphone access exists yet).
- The duplicate-detection fingerprint (material import) samples only the start/end of large files, not a full-file hash — a deliberate performance tradeoff.
- Loop/replay boundary detection depends on a fixed 50ms tolerance tuned against QtMultimedia's observed position-update cadence in this environment.
- After any annotation/note/saved-item/keyword-capture/session-diagnosis Save, Update, or Delete action, the corresponding list widget loses its selection (the form clears); the user must reselect a row to continue editing it. A minor UX rough edge, not a correctness issue.
- Saved Language Item source text/range is a locked identity once saved (by design — see Architecture); changing what text an item refers to requires delete-and-recreate rather than in-place edit.
- The transcript-reveal auto-resolution of Stages 1/2 (see Architecture) is a documented design decision to avoid a permanently-stuck stage, but it does mean a learner who reveals the transcript without deliberately finishing Stage 1/2 first gets an automatic skip rather than a prompt to go back.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows has been available so far)
- Playback across the broader range of real-world codecs/containers beyond the one verified H.264/MP4 configuration and uncompressed WAV audio
- Packaging method
- Continuous-integration configuration
- Behavior with very large media libraries, very large subtitle tracks, or a very large number of annotations/saved items/session records on one cue or material
- Behavior with a very large number of prior sessions in Session History for one material (no pagination implemented)

## Next Engineering Objective

Begin Milestone 6 — Quizzes and Recall Practice: material-derived listening/transcript-recall exercises (cue-level dictation or fill-in-the-blank, keyword recognition, audio-to-transcript choice, review of previously misheard/missed cues), built on the verified Milestone 3 player, Milestone 4 transcript workspace, and Milestone 5 guided-session evidence, per `ROADMAP.md`.

# ListenTrace Project Status

Last updated: 2026-07-23

## Project Purpose

ListenTrace is a local-first desktop application for transcript-guided foreign-language listening practice and listening-error diagnosis.

## Repository Verification

The remote repository exists, is private, and uses `main` as its default branch. It contains the initial documentation commit, the Milestone 1 application-foundation commit, the Milestone 2 material-library commit, the Milestone 3 synchronized-player commit (plus its acceptance-correction follow-up), and the Milestone 4 transcript-workspace commit; no pull requests; no continuous-integration configuration.

## Current Engineering State

| Area | Status |
|---|---|
| Product concept | Defined |
| Product workflow | Defined at roadmap level |
| Public engineering documentation | Committed and pushed to `main` |
| Application code | Implemented (foundation + material library + synchronized player + transcript workspace) |
| Desktop shell | Material library + player window (with integrated transcript workspace), manually verified end-to-end |
| Database schema | Schema version 3: adds `annotation`, `cue_note`, `saved_language_item`, `annotation_label_preference` (additive; Milestone 1/2 tables unchanged) |
| Media/subtitle import | Implemented and tested (Milestone 2, unchanged) |
| Material library | Implemented and tested (Milestone 2), opens the player (Milestone 3) |
| Synchronized player | Implemented and tested (Milestone 3 + acceptance-correction pass, unchanged this milestone) |
| Transcript workspace | Implemented and tested: multi-label annotations on whole-cue or partial text ranges, Misheard/`heard_as` validation, per-cue Cue Notes (empty-save = delete), Saved Language Items (word/phrase/chunk/sentence_pattern) with exact-duplicate rejection and same-text-elsewhere confirmation, global per-label colors, editing cue kept independent of the active playback cue |
| Subtitle parsing | Implemented and tested (Milestone 1, unchanged) |
| Automated tests | 162 tests passing (7 database/migrations, 8 import, 8 library, 3 media playback, 7 subtitle parsing, 8 cue index, 9 player session, 5 player loading, 13 player window, 6 UI smoke, 7 text range, 7 text-offset conversion, 25 annotations, 6 cue notes, 19 saved language items, 5 label preferences, 19 player-workspace UI integration) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 4 — Transcript Workspace and Listening Diagnosis**

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

### Manual smoke steps verified

Launch and open a valid material; confirm Milestone 3 playback still works; select an editing cue while a different cue becomes active through playback and confirm the editing cue does not move; select part of a cue and save one label; select a range and save multiple labels atomically; attempt a Misheard annotation without `heard_as` (rejected) then with it (succeeds); edit and delete an annotation; create/edit/delete a Cue Note (empty save deletes it); save all four Saved Language Item types with prefilled editable context; trigger exact-duplicate rejection and the same-text-elsewhere confirmation flow; change a global label color and confirm annotation label/text are unaffected; hide/show the transcript and confirm hidden cue text is not exposed; close and reopen the app and confirm annotations/notes/saved items persisted; remove a material and confirm all four learning-evidence tables cascade to zero rows while the original media and subtitle files remain on disk.

## Planned Next Work

- Milestone 5 — Guided Intensive Listening (see `ROADMAP.md`)

## Known Risks

- Multimedia behavior can vary across operating systems and codec availability; only Windows has been verified.
- Subtitle timing quality varies by source.
- Large media files should not be copied or committed accidentally.
- Plain-text transcripts do not support reliable synchronized navigation without timing data.
- Recording support introduces permissions, device-selection, and local-storage concerns.
- The duplicate-detection fingerprint (material import) samples only the start/end of large files, not a full-file hash — a deliberate performance tradeoff.
- Loop/replay boundary detection depends on a fixed 50ms tolerance tuned against QtMultimedia's observed position-update cadence in this environment.
- After any annotation/note/saved-item Save, Update, or Delete action, the corresponding list widget loses its selection (the form clears); the user must reselect a row to continue editing it. A minor UX rough edge, not a correctness issue.
- Saved Language Item source text/range is a locked identity once saved (by design — see Architecture); changing what text an item refers to requires delete-and-recreate rather than in-place edit.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows has been available so far)
- Playback across the broader range of real-world codecs/containers beyond the one verified H.264/MP4 configuration and uncompressed WAV audio
- Packaging method
- Continuous-integration configuration
- Behavior with very large media libraries, very large subtitle tracks, or a very large number of annotations/saved items on one cue

## Next Engineering Objective

Begin Milestone 5 — Guided Intensive Listening: the five-stage guided practice session (global comprehension, blind-listening keyword capture, transcript diagnosis reusing Milestone 4's annotation tools, shadowing, final summary), built on the verified Milestone 3 player and Milestone 4 transcript workspace, per `ROADMAP.md`.

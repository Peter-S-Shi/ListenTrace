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
| Automated tests | 136 tests passing (7 database/migrations, 8 import, 8 library, 3 media playback, 7 subtitle parsing, 8 cue index, 9 player session, 5 player loading, 13 player window, 6 UI smoke, 7 text range, 19 annotations, 6 cue notes, 13 saved language items, 5 label preferences, 12 player-workspace UI integration) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 4 — Transcript Workspace and Listening Diagnosis**

Status: **Completed**

## Completed

- Milestones 1–3 (see history; unchanged except where the Milestone 3 acceptance-correction pass is noted)
- Milestone 4 — Transcript Workspace and Listening Diagnosis:
  - Schema version 3 (additive migration, no data loss): `annotation` (with a unique `(subtitle_cue_id, label_key, selection_start, selection_end)` constraint), `cue_note` (one row per cue via `subtitle_cue_id` as primary key), `saved_language_item` (with a unique `(material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized_text)` constraint), and `annotation_label_preference` (seeded with default colors for all 5 labels). Verified to upgrade cleanly from both a Milestone-1 (v1) and a Milestone-2 (v2) database with existing data intact.
  - `domain/services/text_range.py`: pure, framework-free canonical selection-offset validation (`validate_selection`, `whole_cue_range`) — zero-based, end-exclusive, Python code-point offsets (matches Qt's `QTextCursor` offsets for all Basic-Multilingual-Plane text; documented as untested for UTF-16-surrogate-pair characters)
  - `application/services/annotation_service.py`: atomic multi-label annotation creation (one Save action can create several `Annotation` rows sharing one cue+range, all-or-nothing), validates label keys, enforces "Misheard requires `heard_as`", rejects duplicate label+range, allows different labels to share a range; `update_annotation`/`delete_annotation`/`list_annotations_for_cue`
  - `application/services/cue_note_service.py`: single Cue Note per cue via upsert; saving an empty/whitespace-only note is treated as delete-intent, not a stored empty string
  - `application/services/saved_language_item_service.py`: validates item type and selection range, derives canonical text from the cue substring (not a separately-trusted string), rejects exact duplicates, and returns a typed `SavedItemNeedsConfirmation` when the same normalized text already exists elsewhere (a different cue/material) — the caller must explicitly confirm before it is created
  - `application/services/label_preference_service.py`: validates label key and a 6-digit hex color before persisting; editing a color never touches any stored `Annotation.label_key`
  - `application/services/cue_workspace_service.py`: loads a cue's text, annotations, Cue Note, and saved items together for the UI
  - `ui/windows/player_window.py` extended with an integrated transcript workspace (not a separate window): the cue list's `currentItem` now represents an independently-controlled **editing cue**, decoupled from the **active playback cue** (which is shown only via a background-color highlight, never by moving selection) — playback progress can no longer steal focus from the cue being edited. Adds a selectable read-only transcript view for the editing cue, 5 label checkboxes + conditional `heard_as` + annotation note + Save/Update/Delete, an annotation list with per-character highlight in the transcript (single-label color, neutral gray for overlaps), a Cue Note editor, a Saved Language Item form (type/meaning/note/context, context prefilled from the full cue and editable) with its own list, and a "Label Colors..." button opening `ui/windows/label_color_dialog.py`. Hiding the transcript hides the whole workspace panel *and* clears the transcript view's text (defense in depth, not just visual hiding).
  - 63 new automated tests (19 annotations, 6 cue notes, 13 saved language items, 5 label preferences, 7 text-range, 12 player-workspace UI integration, 1 additional v2→v3 migration test) on top of the prior 73 — 136 total, all passing, including in a clean virtual environment outside the working tree
  - Manual 15-step Windows smoke workflow run end-to-end (see below); all steps passed, and closing/reopening the app confirmed annotations, saved items, and the Cue Note all persisted correctly
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
- Canonical text-selection offsets are Python code-point based; characters requiring UTF-16 surrogate pairs (some emoji) are not verified to round-trip correctly against Qt's `QTextCursor` offsets.
- After any annotation/note/saved-item Save, Update, or Delete action, the corresponding list widget loses its selection (the form clears); the user must reselect a row to continue editing it. A minor UX rough edge, not a correctness issue.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows has been available so far)
- Playback across the broader range of real-world codecs/containers beyond the one verified H.264/MP4 configuration and uncompressed WAV audio
- Packaging method
- Continuous-integration configuration
- Behavior with very large media libraries, very large subtitle tracks, or a very large number of annotations/saved items on one cue
- Selection-offset correctness for text containing UTF-16 surrogate-pair characters

## Next Engineering Objective

Begin Milestone 5 — Guided Intensive Listening: the five-stage guided practice session (global comprehension, blind-listening keyword capture, transcript diagnosis reusing Milestone 4's annotation tools, shadowing, final summary), built on the verified Milestone 3 player and Milestone 4 transcript workspace, per `ROADMAP.md`.

# ListenTrace Project Status

Last updated: 2026-07-23

## Project Purpose

ListenTrace is a local-first desktop application for transcript-guided foreign-language listening practice and listening-error diagnosis.

## Repository Verification

The remote repository exists, is private, and uses `main` as its default branch. It contains the initial documentation commit, the Milestone 1 application-foundation commit, and the Milestone 2 material-library commit; no pull requests; no continuous-integration configuration.

## Current Engineering State

| Area | Status |
|---|---|
| Product concept | Defined |
| Product workflow | Defined at roadmap level |
| Public engineering documentation | Committed and pushed to `main` |
| Application code | Implemented (foundation + material library scope) |
| Desktop shell | Implemented and manually verified: library list, import, details, rename, archive/restore, remove |
| Database schema | Schema version 2: `material` (with `normalized_path`), `subtitle_track`, `subtitle_cue`, via additive migrations |
| Media playback | Verified in Milestone 1: PySide6 `QtMultimedia` load/duration/play/pause/seek/end-of-media. Not re-exercised in Milestone 2 (no player UI yet). |
| Media/subtitle import | Implemented and tested: atomic import, validation (missing/unreadable/unsupported media, missing/unreadable/unsupported/malformed/empty subtitle), duplicate-path rejection, duplicate-fingerprint confirmation flow |
| Material library | Implemented and tested: active/archived listing, detail view with missing-source detection, rename, archive/restore, remove (cascades DB records, never touches source files) |
| Subtitle parsing | Implemented and tested: SRT and WebVTT parsers producing normalized cues, with structured validation errors for malformed input |
| Automated tests | 35 tests passing (6 database/migrations, 8 import, 8 library, 3 media playback, 3 UI smoke, 7 subtitle parsing) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 2 — Material Library and Import Validation**

Status: **Completed**

## Completed

- Milestone 1 — Application Foundation (see prior status; unchanged)
- Milestone 2 — Material Library and Import Validation:
  - `normalized_path` column + unique index added via an additive migration (schema version 2), verified to upgrade cleanly from a Milestone 1 (version 1) database
  - File validation (`infrastructure/media/validation.py`): existence, readability, supported audio/video extensions, and a cheap content+size fingerprint (partial-read hash, not a full-file hash) for duplicate detection without re-reading large media in full
  - Atomic import service (`application/services/material_import_service.py`): validates media and subtitle fully before any database write; a single all-or-nothing transaction creates the material, subtitle track, and cues together
  - Duplicate handling: importing an already-registered normalized media path is rejected outright; a different path with the same content fingerprint returns a structured "needs confirmation" result that the UI must resolve before writing
  - Material library service (`application/services/material_library_service.py`): list active/archived, detail retrieval with live availability checks against the filesystem, rename, archive/restore, and remove (DB-only, cascades via existing foreign keys, never touches source files)
  - Material library UI replacing the Milestone 1 foundation shell: list with missing-file indicators, import dialog (with duplicate-fingerprint confirmation prompt and inline validation errors), detail panel, rename/archive-restore/remove actions with explicit source-file-safety wording, empty-library and no-archived states
  - 35 automated tests total (19 new for Milestone 2), all passing, including in a clean virtual environment outside the working tree
  - Manual 8-step Windows smoke workflow verified: launch, import, library listing, details, rename, archive/restore, remove-with-source-files-intact, invalid-subtitle produces a controlled error with no partial record

## Planned Next Work

- Milestone 3 — Synchronized Player (see `ROADMAP.md`)

## Known Risks

- Multimedia behavior can vary across operating systems and codec availability; only Windows has been verified.
- Subtitle timing quality varies by source.
- Large media files should not be copied or committed accidentally.
- Plain-text transcripts do not support reliable synchronized navigation without timing data.
- Recording support introduces permissions, device-selection, and local-storage concerns.
- The fingerprint used for duplicate detection samples only the start/end of large files (not a full-file hash), which is a deliberate performance tradeoff and should be revisited if stronger collision resistance is needed.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows has been available so far)
- Real-file playback across representative codecs/containers (still only exercised with a synthesized WAV in Milestone 1)
- Packaging method
- Continuous-integration configuration
- Behavior with very large media libraries (list/detail queries are not yet paginated or indexed beyond the primary key and the normalized-path unique index)

## Next Engineering Objective

Begin Milestone 3 — Synchronized Player: play/pause/seek/position, active-cue display, previous/next-cue navigation, cue replay, cue/range looping, transcript show/hide, and keyboard shortcuts, built on the verified Milestone 1 playback adapter and the Milestone 2 material library, per `ROADMAP.md`.

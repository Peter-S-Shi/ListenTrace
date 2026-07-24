# ListenTrace Project Status

Last updated: 2026-07-23

## Project Purpose

ListenTrace is a local-first desktop application for transcript-guided foreign-language listening practice and listening-error diagnosis.

## Repository Verification

The remote repository exists, is private, and uses `main` as its default branch. It contains the initial documentation commit, the Milestone 1 application-foundation commit, the Milestone 2 material-library commit, and the Milestone 3 synchronized-player commit; no pull requests; no continuous-integration configuration.

## Current Engineering State

| Area | Status |
|---|---|
| Product concept | Defined |
| Product workflow | Defined at roadmap level |
| Public engineering documentation | Committed and pushed to `main` |
| Application code | Implemented (foundation + material library + synchronized player) |
| Desktop shell | Material library + player window, both manually verified end-to-end |
| Database schema | Schema version 2 (unchanged in Milestone 3 — no new migration was needed) |
| Media/subtitle import | Implemented and tested (Milestone 2, unchanged) |
| Material library | Implemented and tested (Milestone 2), now also opens the player |
| Synchronized player | Implemented and tested: play/pause/seek, active-cue sync (gaps/overlaps handled), previous/next-cue navigation, replay-once, single-cue loop, continuous-range loop with cancellation, transcript show/hide, volume/mute, audio placeholder and video surface, keyboard shortcuts, controlled errors for missing/invalid media |
| Subtitle parsing | Implemented and tested (Milestone 1, unchanged) |
| Automated tests | 73 tests passing (6 database/migrations, 8 import, 8 library, 3 media playback, 7 subtitle parsing, 8 cue index, 9 player session, 5 player loading, 13 player window, 6 UI smoke) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 3 — Synchronized Player**

Status: **Completed**

## Completed

- Milestone 1 — Application Foundation (see history; unchanged)
- Milestone 2 — Material Library and Import Validation (see history; unchanged)
- Milestone 3 — Synchronized Player:
  - `domain/services/cue_index.py`: pure, framework-free active-cue lookup (bisect-based) implementing the confirmed rule `start_ms <= position_ms < end_ms`, with deterministic tie-breaking toward the latest-started cue on overlaps, and original-order previous/next navigation
  - `application/services/player_session.py`: pure state machine (no Qt dependency) for replay-once, single-cue loop, continuous-range loop, and cancellation, returning side-effect instructions (`PlayerTick`) rather than driving playback directly — fully unit-testable without a Qt event loop; documented 50ms loop-boundary tolerance appropriate for QtMultimedia's position-update cadence, with a seek-pending guard to prevent repeated boundary seeks
  - `application/services/player_loading_service.py`: loads a material's ordered cues for the player, blocking archived materials and missing media/subtitle files with typed `PlayerOpenError` categories
  - `infrastructure/media/playback.py` extended: video-output attachment, mute, and `InvalidMedia` status surfaced through the existing `playback_error` signal (closes the Milestone 2 gap where a valid extension was treated as proof of playability)
  - `ui/windows/player_window.py`: full player UI — seek bar, transport controls, previous/next/replay/loop-cue/loop-range buttons, audio placeholder or video surface depending on `media_kind`, cue list with contiguous-only (`ContiguousSelection`) range selection, transcript show/hide, volume/mute, keyboard shortcuts (Space, Left/Right, Ctrl+Left/Right, R, L, T, M, Escape) with letter-shortcut suppression while a text-entry control has focus, and a controlled error/status area
  - Library integration: double-click or "Open Player" opens an active material; both are disabled while viewing the archived list; opening the player never mutates material metadata
  - **Acceptance-correction pass** (post-review): (1) added `PlayerWindow._set_playback_controls_enabled`, a single helper disabling every playback-dependent control (play/pause, seek slider, previous/next cue, replay cue, loop cue, loop selection, volume, mute) on a playback error, while transcript toggle and Return to Library stay usable; keyboard shortcuts for those same actions are now gated behind the same `_playback_usable` flag (T and Escape remain exempt); (2) switched the cue list from `ExtendedSelection` to `ContiguousSelection` so Loop Selection can only ever target a genuinely contiguous cue range — no silent expansion of a non-contiguous selection; (3) ran a manual real-video smoke test with a locally generated, non-copyrighted H.264/MP4 test-pattern clip (not committed) confirming actual decode, visible video output, play/pause/seek, and correct subtitle sync — see "Completed" below
  - 38 new automated tests total for this milestone (8 cue index, 9 player session, 5 player loading, 13 player window, 3 additional UI smoke) on top of Milestone 2's 35, all passing — 73 total, including in a clean virtual environment outside the working tree
  - Manual 14-step Windows smoke workflow (original, synthesized-audio pass) run end-to-end: launch, open audio material, confirm no autoplay, play/pause/seek, active-cue sync, previous/next navigation, replay-cue pause at end, single-cue loop, continuous-range loop, transcript hide/show during playback, all keyboard shortcuts, video-surface creation (fake video bytes), damaged-media controlled failure, and a clean return to the library with the database and all four source files (audio, subtitle, video, broken media) intact
  - Additional manual real-video smoke test (acceptance-correction pass): imported a real, locally generated 3-second H.264/MP4 test-pattern clip (ffmpeg `testsrc`, not committed to Git) plus a matching SRT. Verified: `MediaStatus.LoadedMedia` with correct 3000ms duration, a visible `QVideoWidget`, play advancing position and pause holding it, seek landing exactly on the requested position, active-cue resolution correct at two different positions, and a clean close with the video/subtitle files and database row count unaffected
  - Confirmed zero PySide6 imports remain in `domain/` or `application/` — the player-session/cue-index coordination logic is fully framework-free; only `ui/` and `infrastructure/media/` reference Qt

## Planned Next Work

- Milestone 4 — Transcript Workspace and Listening Diagnosis (see `ROADMAP.md`)

## Known Risks

- Multimedia behavior can vary across operating systems and codec availability; only Windows has been verified.
- Subtitle timing quality varies by source.
- Large media files should not be copied or committed accidentally.
- Plain-text transcripts do not support reliable synchronized navigation without timing data.
- Recording support introduces permissions, device-selection, and local-storage concerns.
- The duplicate-detection fingerprint samples only the start/end of large files, not a full-file hash — a deliberate performance tradeoff.
- Loop/replay boundary detection depends on a fixed 50ms tolerance tuned against QtMultimedia's observed position-update cadence in this environment; a much slower or faster-updating backend could need retuning.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows has been available so far)
- Playback across the broader range of real-world codecs/containers: only one real codec configuration has been manually verified (H.264 video in an MP4 container, generated locally via ffmpeg's `testsrc`) and uncompressed WAV for audio; compressed audio formats (MP3/AAC/etc.) and other video codecs/containers remain unverified
- Packaging method
- Continuous-integration configuration
- Behavior with very large media libraries or very large subtitle tracks (thousands of cues)

## Next Engineering Objective

Begin Milestone 4 — Transcript Workspace and Listening Diagnosis: semantic annotation labels, mishearing records, cue notes, and keyword/chunk capture, built on the verified Milestone 3 player and cue synchronization, per `ROADMAP.md`.

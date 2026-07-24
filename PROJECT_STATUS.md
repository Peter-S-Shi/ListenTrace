# ListenTrace Project Status

Last updated: 2026-07-23

## Project Purpose

ListenTrace is a local-first desktop application for transcript-guided foreign-language listening practice and listening-error diagnosis.

## Repository Verification

The remote repository exists, is private, and uses `main` as its default branch. It contains the initial documentation commit and the Milestone 1 application-foundation commit, no pull requests, and no continuous-integration configuration.

## Current Engineering State

| Area | Status |
|---|---|
| Product concept | Defined |
| Product workflow | Defined at roadmap level |
| Public engineering documentation | Committed and pushed to `main` |
| Application code | Implemented (foundation scope) |
| Desktop shell | Implemented and manually verified (starts, shows status, runs the media spike) |
| Database schema | Implemented: `material`, `subtitle_track`, `subtitle_cue` tables via an explicit migration (schema version 1) |
| Media playback | Verified: PySide6 `QtMultimedia` (`QMediaPlayer` + `QAudioOutput`) loads media, reports duration, and supports play/pause/seek/end-of-media detection. No system FFmpeg install was required. |
| Subtitle parsing | Implemented and tested: SRT and WebVTT parsers producing normalized cues, with structured validation errors for malformed input |
| Automated tests | 16 tests passing (5 database, 3 media playback, 1 UI smoke, 7 subtitle parsing) |
| Build and packaging | Not started |
| Continuous integration | Not configured |

## Current Milestone

**Milestone 1 — Application Foundation**

Status: **Completed**

## Completed

- Product name and concise positioning
- Core intensive-listening workflow
- Initial error-classification semantics
- Milestone sequence
- Initial architecture and data-model direction
- Privacy and copyright boundaries
- Python `src`-layout project (`pyproject.toml`, editable install verified in a clean virtual environment)
- Cross-platform application-data directory resolution and rotating file logging
- SQLite connection boundary with an explicit, idempotent migration mechanism (foreign keys enabled, `PRAGMA user_version` schema tracking)
- Minimum tables to prove material metadata, subtitle-track metadata, and normalized subtitle-cue persistence
- SRT and WebVTT parsers producing a normalized cue model, with fixtures covering valid input and malformed timing/index/header cases
- Media playback feasibility spike: verified load, duration reporting, play, pause, seek, and end-of-media detection using a locally synthesized silent WAV (no user media committed)
- Minimal PySide6 desktop shell: main window, database status display, and an interactive media-spike check with error display
- 16 automated tests (unit + integration), all passing, including in a clean virtual environment outside the working tree

## Planned Next Work

- Milestone 2 — Material Library and Import Validation (see `ROADMAP.md`)

## Known Risks

- Multimedia behavior can vary across operating systems and codec availability; the spike was verified on Windows only.
- Subtitle timing quality varies by source.
- Large media files should not be copied or committed accidentally.
- Plain-text transcripts do not support reliable synchronized navigation without timing data.
- Recording support introduces permissions, device-selection, and local-storage concerns.

## Unknown or Unverified

- Behavior on macOS and Linux (only Windows was available for this milestone)
- Real-file playback across representative codecs/containers (the spike used a synthesized WAV, not representative media samples)
- Packaging method
- Continuous-integration configuration

## Next Engineering Objective

Begin Milestone 2 — Material Library and Import Validation: local audio/video import, SRT/WebVTT attachment, validation of missing/incompatible files, and material record management, per `ROADMAP.md`.

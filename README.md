# ListenTrace

ListenTrace is a local-first desktop application for foreign-language listening practice. It helps learners move beyond simply replaying media by recording what they understood, comparing it with a transcript, classifying listening failures, practicing difficult segments, and tracking improvement over time.

## Problem

Language learners often know a word on paper but fail to recognize it in natural speech. A normal media player does not explain whether the difficulty came from an unknown word, connected speech, reduction, segmentation, or a mishearing.

ListenTrace is designed to make those failures visible and trainable.

## Core Workflow

A learning material combines:

- one local audio or video file;
- one matching subtitle or transcript;
- one or more guided practice sessions.

The intended intensive-listening flow is:

1. Listen without subtitles and record the overall meaning.
2. Listen again and capture keywords or fragments.
3. Compare against the transcript and classify missed or misheard content.
4. Practice sentence-by-sentence shadowing or repetition.
5. Hide the transcript and summarize the material in the target language.

## Planned Capabilities

- Local media and subtitle import
- Subtitle synchronization and sentence-level playback
- Transcript annotation with listening-error categories
- Keyword and chunk capture
- Guided multi-pass intensive listening
- Shadowing and optional local recording
- Material-based quizzes
- Learning history and progress summaries
- Structured export for external evaluation

## Initial Technical Direction

The implementation target verified in Milestone 1:

- Python (3.10+, verified on 3.14)
- PySide6 desktop interface
- SQLite local storage
- PySide6's built-in `QtMultimedia` backend for media inspection and playback (bundles its own decoding backend; no separate system FFmpeg install is required)
- SRT and WebVTT subtitle parsing

## Setup, Run, and Test

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows; use .venv/bin/pip on macOS/Linux
```

Run the application:

```bash
.venv/Scripts/python -m listentrace.ui.app
```

Run the automated tests:

```bash
.venv/Scripts/python -m pytest
```

## Development Status

Milestones 1–3 are implemented and verified. Users can import a local media file plus an SRT/WebVTT subtitle into a library, view details, rename, archive/restore, and remove records, then open a synchronized player: play/pause/seek, active-cue tracking, previous/next-cue navigation, replay-once, single-cue and continuous-range looping, transcript show/hide, volume/mute, and keyboard shortcuts — with atomic import, duplicate handling, and no modification of source files.

See:

- `ROADMAP.md` for milestone sequencing
- `PROJECT_STATUS.md` for the current engineering state
- `ARCHITECTURE.md` for system boundaries
- `DATA_MODEL.md` for the initial domain model
- `docs/PRODUCT_SPEC.md` for product behavior

## Repository Structure

```text
src/listentrace/
  application/
    dto/              # ImportSuccess/ImportNeedsConfirmation, MaterialSummary/MaterialDetail,
                       # PlayerLoadResult, LoopMode/PlayerTick
    services/         # material_import_service, material_library_service,
                       # player_loading_service, player_session (pure, no Qt)
  domain/
    enums/            # MaterialStatus
    models/           # Material, SubtitleTrack, SubtitleCue
    services/         # CueIndex (active-cue/navigation rules, pure, no Qt)
  infrastructure/
    db/               # SQLite connection, migrations, repository functions
    subtitles/        # SRT/WebVTT parsers, timecode and text normalization
    media/            # PlaybackController adapter around QtMultimedia; file validation/fingerprinting
    appdata.py         # cross-platform app-data directory resolution
    logging_setup.py   # rotating file + console logging
  ui/
    app.py            # application entry point
    windows/          # MainWindow (material library), ImportDialog, PlayerWindow
tests/
  unit/               # subtitle parsing, CueIndex, PlayerSession
  integration/        # database, migrations, media playback, import, library, player, UI smoke tests
  fixtures/
docs/
```

## Current Limitations

- No transcript-annotation workspace, quizzes, shadowing, or recording yet (planned for later milestones).
- Only one primary subtitle track per material is managed through the UI, though the schema supports more.
- Plain-text (non-timed) transcript import is not supported.
- Player loop/replay timing uses a small internal tolerance (50ms) appropriate for QtMultimedia's position-update cadence; it is not frame-exact.
- Real-file, multi-codec playback and audio/video-device behavior are only verified with synthesized WAV test fixtures and on Windows so far.
- Text-only transcripts cannot provide reliable sentence seeking unless timing data is added.
- Speech recognition, pronunciation scoring, automatic translation, subtitle generation, and cloud synchronization are outside the first release.
- Users are responsible for using media and transcript material they are legally permitted to use.

## Privacy

ListenTrace is local-first. User media, transcripts, annotations, recordings, and learning records should remain on the user's device unless the user explicitly exports them.

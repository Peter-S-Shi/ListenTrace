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

The initial implementation target is:

- Python
- PySide6 desktop interface
- SQLite local storage
- FFmpeg/ffprobe for media inspection and playback support
- SRT and WebVTT subtitle parsing

This direction may be refined during the foundation milestone after a minimal technical spike.

## Development Status

The product plan and project architecture are documented. Product code, installation commands, build steps, automated tests, and continuous integration have not yet been verified.

See:

- `ROADMAP.md` for milestone sequencing
- `PROJECT_STATUS.md` for the current engineering state
- `ARCHITECTURE.md` for system boundaries
- `DATA_MODEL.md` for the initial domain model
- `docs/PRODUCT_SPEC.md` for product behavior

## Repository Structure

The planned structure is:

```text
src/listentrace/
  application/
  domain/
  infrastructure/
  ui/
tests/
docs/
```

The exact package structure will be established during Milestone 1.

## Current Limitations

- No working application has been verified.
- Media formats and playback backend remain subject to a technical spike.
- Text-only transcripts cannot provide reliable sentence seeking unless timing data is added.
- Speech recognition, pronunciation scoring, automatic translation, subtitle generation, and cloud synchronization are outside the first release.
- Users are responsible for using media and transcript material they are legally permitted to use.

## Privacy

ListenTrace is local-first. User media, transcripts, annotations, recordings, and learning records should remain on the user's device unless the user explicitly exports them.

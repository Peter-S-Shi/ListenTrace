# ListenTrace Architecture

## Architectural Goals

ListenTrace should remain:

- local-first;
- desktop-oriented;
- testable outside the graphical interface;
- resilient to changing multimedia libraries;
- explicit about data ownership and privacy;
- maintainable through milestone-based evolution.

## Layered Structure

### Domain

Contains product concepts and rules without desktop-framework, database, or multimedia dependencies.

Examples:

- MaterialPackage
- SubtitleTrack
- SubtitleCue
- PracticeSession
- Annotation
- VocabularyItem
- QuizSession
- RecordingReference

### Application

Coordinates use cases.

Examples:

- import and validate material;
- start or resume a practice session;
- save a stage response;
- apply an annotation label;
- create a quiz from valid cues;
- export a learning report.

Application services depend on domain interfaces rather than concrete UI or storage classes.

### Infrastructure

Provides concrete adapters:

- SQLite repositories and migrations;
- filesystem and application-data paths;
- subtitle parsers;
- media inspection;
- playback backend;
- recording backend;
- export writers.

Multimedia and filesystem behavior should be hidden behind narrow interfaces because platform behavior may change.

### UI

Contains PySide6 windows, views, widgets, and presentation state.

The UI may call application services but must not own SQL, migrations, parsing logic, or learning rules.

## Proposed Package Layout

```text
src/listentrace/
  __init__.py
  application/
    services/
    dto/
  domain/
    models/
    enums/
    repositories/
  infrastructure/
    db/
    media/
    subtitles/
    recording/
    export/
  ui/
    windows/
    widgets/
    viewmodels/
tests/
  unit/
  integration/
  fixtures/
docs/
```

This structure may be simplified during Milestone 1, but separation of concerns must remain.

## Main Data Flow

```text
Local media + subtitle
        |
        v
Material validation
        |
        v
Material metadata + cue records
        |
        v
Synchronized player
        |
        v
Practice-session stages
        |
        +--> annotations / keyword captures
        +--> quiz results
        +--> recording references
        +--> summary
        |
        v
Progress queries and structured export
```

## Media Boundary

Original media should normally remain in its existing filesystem location. The database stores a reference and metadata.

Requirements:

- Detect missing or moved files.
- Do not commit or bundle user media.
- Do not delete the original file when deleting a material record.
- Consider optional managed copies only after explicit product design.

## Subtitle Boundary

Timed subtitles are the canonical source for sentence-level navigation.

Initial formats:

- SRT
- WebVTT

Plain text may be supported with reduced capabilities. Parsing must produce a normalized cue model:

- sequence/index;
- start time;
- end time;
- source text;
- optional normalized text.

Malformed input should produce controlled validation errors.

## Persistence

SQLite is the initial local store.

Requirements:

- explicit migrations;
- foreign keys enabled;
- transaction-safe writes;
- repository interfaces outside UI;
- timestamps stored consistently;
- user data excluded from source control;
- schema version visible for diagnostics.

## Playback

The playback backend is a high-risk implementation choice and should be verified early.

The selected adapter must support, at minimum:

- play and pause;
- seek;
- current-time updates;
- end-of-media detection;
- audio and common video formats;
- cue looping with acceptable precision.

The domain must not depend directly on backend-specific objects.

## Practice Session State

A guided intensive-listening session should be persisted as an explicit state rather than inferred from open screens.

Initial stages:

1. global comprehension;
2. keyword capture;
3. transcript diagnosis;
4. shadowing;
5. final summary.

The user should be able to resume safely after closing the application.

## Error Labels

The stored value is a stable semantic key, not a display color.

Initial keys:

- `keyword`
- `known_not_heard`
- `connected_reduced_speech`
- `misheard`
- `unknown_word_or_chunk`

Display labels and colors are presentation settings.

## Observability

Logs should help diagnose technical failures without exposing learning content unnecessarily.

Avoid logging:

- full transcript text;
- user summaries;
- recordings;
- personal absolute paths when a shortened or redacted path is sufficient.

## Security and Privacy

- No silent network upload.
- External integrations are optional and isolated.
- Credentials use local configuration or an operating-system credential store.
- Export is explicit and previewable.
- Local recordings and exports have visible deletion controls.

## Testing Strategy

### Unit Tests

- subtitle parsing;
- time conversion;
- annotation validation;
- session-stage transitions;
- quiz item construction;
- export serialization.

### Integration Tests

- SQLite migrations and repositories;
- material validation with temporary files;
- persistence and resume of practice sessions.

### Manual Tests

- playback across representative formats;
- seeking and cue loops;
- audio-device and microphone behavior;
- desktop packaging.

## Architecture Decisions Still Open

- exact playback backend;
- whether UI uses view models or a lighter presenter pattern;
- application-data path library;
- migration library versus a minimal internal migration runner;
- supported operating systems;
- packaging tool.

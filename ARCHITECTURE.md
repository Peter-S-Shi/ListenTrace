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

- whether UI uses view models or a lighter presenter pattern (the player window currently talks to the application layer directly);
- supported operating systems (only Windows verified so far);
- packaging tool.

## Architecture Decisions Resolved in Milestone 1

- Playback backend: PySide6's `QtMultimedia` (`QMediaPlayer` + `QAudioOutput`), wrapped in `infrastructure/media/playback.py`. It bundles its own decoding backend, so no separate system FFmpeg install is required. Verified: load, duration, play, pause, seek, end-of-media detection.
- Application-data path: a small internal `infrastructure/appdata.py` module (no external dependency), resolving `%APPDATA%`/`~/Library/Application Support`/`XDG_DATA_HOME` per platform.
- Migrations: a minimal internal migration runner (`infrastructure/db/migrations.py`) using `PRAGMA user_version` for schema-version tracking, rather than an external migration library.

## Architecture Decisions Resolved in Milestone 2

- Duplicate detection: a `normalized_path` column (resolved absolute path, case-folded) with a unique index rejects re-importing the same file; a separate content fingerprint (`infrastructure/media/validation.py::compute_file_fingerprint`) catches the same content at a different path and requires explicit user confirmation rather than blocking or silently merging. The fingerprint hashes file size plus the first and last 1 MiB, not the full file, to stay fast on large media.
- Media/subtitle validation lives in `infrastructure/media/validation.py` (existence, readability, supported extensions) and reuses the Milestone 1 subtitle parsers/errors — it does not re-verify actual playback; that remains the player's job in Milestone 3.
- Atomicity: `infrastructure/db/repository.py::create_material_package` performs the material + subtitle-track + cue inserts as one transaction (commit only on full success, rollback on any exception). All validation (media, subtitle, duplicates) runs before this function is ever called, so a rejected import never touches the database.
- Application services (`material_import_service`, `material_library_service`) return typed results/raise typed errors (`ImportSuccess`, `ImportNeedsConfirmation`, `MaterialValidationError` with a `category`, `MaterialNotFoundError`) rather than exposing SQL/exception details directly to the UI.

## Architecture Decisions Resolved in Milestone 3

- Active-cue resolution and cue navigation live in `domain/services/cue_index.py` — a plain, framework-free class (bisect over cue start times, then a bounded backward scan to honor "latest-started cue wins" on overlaps). It has no Qt or database dependency and is directly unit-tested.
- Player presentation state (replay-once, single-cue loop, continuous-range loop, cancellation, transcript visibility) lives in `application/services/player_session.py`, also framework-free. It does not hold a playback-backend reference; instead `on_position_changed(position_ms)` returns a small `PlayerTick` (active cue index, whether to pause, whether to seek) that the UI applies to the real `PlaybackController`. This keeps loop/replay semantics fully unit-testable without a running Qt event loop, and keeps the UI from owning any of those rules (only executing the returned instructions).
- Loop/replay boundary detection uses a fixed 50ms tolerance (`player_session.LOOP_END_TOLERANCE_MS`), because QtMultimedia position updates are not frame-exact. A "seek pending" guard suppresses repeated boundary-triggered seeks until a position update confirms the seek actually landed, preventing rapid re-triggering right at the loop edge.
- The Milestone 2 gap ("a valid extension does not prove media is playable") is closed here: `PlaybackController` now surfaces `QMediaPlayer.MediaStatus.InvalidMedia` through its existing `playback_error` signal, and the player UI disables playback controls and shows a controlled message instead of failing silently or crashing.
- Video vs. audio presentation is chosen from the already-stored `Material.media_kind` (set at import time in Milestone 2): video materials get a `QVideoWidget` attached via `PlaybackController.set_video_output`; audio materials get a simple title+time placeholder. Both share the same transport/cue/loop controls.
- Opening the player performs no writes: `player_loading_service.load_material_for_player` only reads (material, subtitle track, cues) and raises a typed `PlayerOpenError` (`not_found` / `archived` / `media_missing` / `subtitle_missing`) rather than mutating any material metadata.

## Architecture Decisions Resolved in Milestone 4

- Canonical text-selection representation: `domain/services/text_range.py` defines offsets as zero-based, end-exclusive Python string (Unicode code-point) positions into the immutable cue `text`. This is a different number line from Qt's `QTextCursor.selectionStart()/selectionEnd()`, which count UTF-16 code units — the two coincide only for text within the Basic Multilingual Plane. `ui/text_offset_conversion.py` is the single place that bridges them (see the acceptance-correction entry below); nothing outside `ui/` ever sees a Qt offset.
- Annotation storage: one row per (cue, label, range) rather than a label array or comma-separated column, so "one Save action creates several labels" is just several inserts in one transaction (`learning_repository.insert_annotations`) and "different labels may share a range" falls out naturally. A `UNIQUE(subtitle_cue_id, label_key, selection_start, selection_end)` constraint blocks the exact-duplicate case at the database level as well as in `annotation_service`.
- `heard_as` is attached per-row, not per-save-action: when a save creates multiple labels together (e.g. `keyword` + `misheard`), only the `misheard` row receives the typed `heard_as` value; other rows store `NULL`. `update_annotation` fully re-validates and replaces label/range/text/heard_as/note for one row (see the acceptance-correction entry below) — it is scoped to a single row by id, so it can never touch a sibling label that happens to share the same range.
- Cue Note uses `subtitle_cue_id` as its own primary key (one row per cue, enforced by the schema itself, not just application logic) and an `INSERT ... ON CONFLICT DO UPDATE` upsert. Saving an empty/whitespace-only note is treated as delete-intent by `cue_note_service`, not stored as an empty row — this was a deliberate scope decision ("CC may choose the safer implementation") favoring one unambiguous state (note exists with content, or doesn't exist) over a nullable-vs-empty distinction.
- Saved Language Item duplicate handling mirrors Milestone 2's material-import pattern: an exact match (`material_id` + `subtitle_cue_id` + `item_type` + range + `normalized_text`, enforced by a `UNIQUE` constraint too) is a hard rejection; the same `normalized_text` appearing elsewhere (different cue/material) returns a typed `SavedItemNeedsConfirmation` rather than blocking, requiring the caller to explicitly re-call with `confirm_duplicate_text_elsewhere=True`.
- Editing cue vs. active playback cue: the player's `QListWidget` `currentItem`/selection now represents the **editing cue** exclusively; the **active playback cue** is indicated only via per-row background-color highlighting (`PlayerWindow._update_active_cue_highlight`), never by moving the list's current row. This is the direct fix for "playback progress must not steal focus from the cue being edited" — before Milestone 4, `setCurrentRow` was used for both purposes and would have conflated them.
- Label colors are a presentation-only preference table (`annotation_label_preference`, keyed by the stable `label_key`) validated by `label_preference_service` (label must be one of the 5 keys, color must be a 6-digit hex string). Changing a color never touches any `Annotation.label_key` value — verified directly in tests by reading annotation rows before/after a color change.

## Architecture Decisions Resolved in the Milestone 4 Acceptance-Correction Pass

- **Qt/Python offset boundary is now explicit.** `ui/text_offset_conversion.py` converts between Qt's UTF-16 code-unit offsets and the canonical Python code-point offsets, with a `SurrogatePairOffsetError` guard for a Qt offset that lands mid-surrogate-pair. `player_window.py` routes every read from or write to `QTextCursor` positions through this module — reading a transcript selection, cursor-position-driven annotation lookup, restoring an annotation's selection, and per-character highlighting. Verified against a real non-BMP (emoji) character through the actual `QTextEdit` widget, not only via isolated string-offset math.
- **Saved Language Item identity is locked by design, not by oversight.** `saved_language_item_service.update_saved_language_item` accepts `item_type`/`meaning`/`note`/`context_text` but not source text or range — changing what text an item refers to is delete-and-recreate. This is documented in the function's docstring and surfaced to the user as a visible, permanent note in the UI (not a control that silently ignores input). `item_type` changes still re-run the exact-duplicate check, since `item_type` is part of the uniqueness key.
- **A cue's material is derived, never trusted from the caller.** `learning_repository.get_material_id_for_subtitle_cue` looks up `subtitle_cue -> subtitle_track -> material` directly; `saved_language_item_service.save_language_item` no longer accepts a `material_id` parameter at all. This closes off an entire class of bug (a UI passing a stale or mismatched `material_id`) at the function-signature level rather than by validating and rejecting after the fact.
- **Annotation-list badges reuse the same color lookup as transcript highlighting** (`label_preference_service.get_label_preferences`), rendered as a small solid-color `QIcon` per row alongside the still-visible `[label_key]` text — color is a secondary cue, never the only one. Both the badge and the transcript highlight are recomputed together on every `_refresh_editing_cue_panels()` call, so a color-preference change can never leave one stale while the other updates.
- Transcript-hidden defense in depth: hiding the transcript hides the whole workspace panel (`PlayerWindow._workspace_panel`) *and* clears the editing transcript view's text content, rather than relying on `.setVisible(False)` alone to keep hidden cue text from lingering in a widget.

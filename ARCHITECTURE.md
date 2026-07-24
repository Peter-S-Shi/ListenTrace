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

## Architecture Decisions Resolved in Milestone 5

- **Session lifecycle/stage rules live in a framework-free domain service**, `domain/services/session_rules.py` (transition tables for session/stage status, and per-stage completion-eligibility predicates: `stage1_can_complete` .. `stage5_can_complete`, `session_can_complete`). It has no sqlite or Qt dependency and is unit-tested directly (`tests/unit/test_session_rules.py`), matching the existing `text_range.py`/`cue_index.py` pattern.
- **One active intensive session per material is enforced at the database level**, not only in application code: a partial unique index, `CREATE UNIQUE INDEX ... ON practice_session(material_id) WHERE status = 'active' AND mode = 'intensive'`. `practice_session_service.start_session` still checks first and raises a typed `ActiveSessionExistsError` for a clean UI message, but the index is the actual guarantee against a race or a bypassed check.
- **`complete_stage`/`skip_stage` are single dispatching functions**, not five stage-specific functions each. Each internally loads exactly the evidence its stage needs (stage-1/2/5 responses or captures, stage-3 diagnosis count/outcome, stage-4 unresolved-cue count) and delegates the actual yes/no decision to `session_rules`. This keeps the public service surface small and keeps "what counts as evidence for this stage" defined in exactly one place per stage.
- **Transcript-reveal auto-resolves Stages 1 and 2** rather than leaving them permanently stuck `in_progress` if the learner reveals the transcript without explicitly completing or skipping them first. `practice_session_service._reveal_transcript_and_lock_prior_stages` completes a stage if it already has qualifying evidence, otherwise skips it with an automatic `skip_note`. This was a genuine ambiguity in the milestone spec (revealing locks Stages 1/2 forever, but nothing required they be resolved *before* reveal) — auto-resolving avoids a dead-end where a session could never reach `session_can_complete` because a locked stage was permanently stuck `not_started`/`in_progress`.
- **Session diagnosis is a two-table design**: `session_diagnosis_evidence` (a full snapshot: label, range, selected text, heard_as, note, one row per session/cue/label/range) plus an optional `annotation_id` link (`ON DELETE SET NULL`) to the Milestone 4 `annotation` table. `practice_session_service.record_session_diagnosis` finds an existing material-level annotation for the exact cue/label/range and reuses its id without overwriting its fields; only when none exists does it create one. This lets the same diagnosis repeat across multiple sessions (each gets its own snapshot row, so the Milestone 4 `UNIQUE(subtitle_cue_id, label_key, selection_start, selection_end)` constraint is never hit across sessions) while a session's own evidence stays exact-duplicate-blocked (a second `session_diagnosis_evidence` unique constraint scoped by `practice_session_id`). Editing or deleting a session diagnosis touches only its own row — the linked `Annotation`, if any, is never mutated or cascaded.
- **The Milestone 4 transcript-highlight painting logic was extracted, not duplicated.** `ui/annotation_highlighting.py::apply_range_highlighting` is the one place that turns a list of label-keyed codepoint ranges into `QTextCharFormat` backgrounds on a `QTextEdit` (via `ui/text_offset_conversion.py` for every position). `PlayerWindow._apply_annotation_highlighting` was refactored into a thin wrapper around it (verified against the full existing Milestone 3/4 test suite with zero behavior change), and the new Stage 3 diagnosis panel calls the same function directly — there are not two copies of this Unicode-offset-sensitive math anywhere in the codebase.
- **The guided session window reuses `PlayerSession`/`PlaybackController` directly** for Stage 3/4 playback (one shared instance per `GuidedSessionWindow`, covering both stages) rather than reimplementing cue timing, loop, replay, or playback-error handling. A playback error disables only the playback-dependent buttons (mirroring `PlayerWindow._set_playback_controls_enabled`'s established pattern) and leaves every text-based stage action (responses, captures, diagnosis text-entry, shadowing notes, session navigation) fully usable.
- **The guided window's save-on-navigate flow must not run before the first real display.** `GuidedSessionWindow.__init__` calls `_show_stage(session.current_stage)` to show the resumed stage, and `_show_stage` always flushes the *outgoing* stage's widgets before navigating — but on the very first call there is no real outgoing stage yet, only freshly constructed empty widgets. An `_initialized` flag (set `True` only after that first call returns) skips the flush exactly once, preventing a resumed session's real Stage 1 answers from being overwritten with the empty text of a just-built widget. Caught by `tests/integration/test_guided_session_window.py::test_close_and_resume_restores_stage_and_responses`.

## Architecture Decisions Resolved in Milestone 6

- **Quiz generation is deterministic and framework-free at its core.** `domain/services/quiz_rules.py` holds every piece of pure selection/validation math (case-/punctuation-/whitespace-insensitive text normalization, tokenization, meaningful-token filtering, blank-span selection, whole-token-boundary containment checks for keyword targets, distractor de-duplication) with no sqlite or Qt dependency, unit-tested directly (`tests/unit/test_quiz_rules.py`) — the same pattern as `session_rules.py`/`text_range.py`/`cue_index.py`. `application/services/quiz_service.py` is the only layer that touches the database, feeding real cue/annotation/saved-item/keyword-capture data through one seeded `random.Random(seed)` instance so every generation decision, and therefore the whole question set, is reproducible from the stored `QuizAttempt.seed`.
- **Three tables, not two.** The original design sketch (`DATA_MODEL.md`) proposed a `QuizSession`/`QuizItemResult` pair; the actual implementation is `QuizAttempt` (lifecycle) / `QuizQuestion` (immutable generation snapshot) / `QuizAnswer` (mutable in-progress answer, one row eagerly created per question). Splitting the question snapshot from the answer means a question's `prompt_payload`/`correct_answer_payload` are written exactly once at generation time and never touched again — later subtitle or annotation edits cannot rewrite a historical attempt — while the answer row can be freely upserted as the learner progresses through the quiz.
- **Correctness is absent from the data, not merely hidden by the UI, until submission.** `QuizAnswer.is_correct` stays `NULL` for every answer through the entire active phase; `quiz_service.submit_quiz` is the *only* place that ever computes it, scoring every question and marking the attempt `completed` as one all-or-nothing transaction (mirroring `practice_session_service.complete_session`'s atomicity, but here the transaction also does real scoring work, not just a status check). There is no code path — UI or service — that can reveal a per-question result before that transaction commits.
- **Material Quiz and Review Quiz are the same lifecycle with different generators, not two features.** Both produce ordinary `QuizAttempt`/`QuizQuestion` rows and share every lifecycle/scoring/review function; only quiz creation branches (`create_material_quiz` vs. `create_review_quiz`). This was a genuine design choice: the milestone prompt describes four *question types* and two *quiz modes* somewhat orthogonally, and this implementation resolves that by making Review Quiz always generate the `review_missed` question type exclusively (sourced from the material's own `Annotation` diagnosis history, in `misheard > known_not_heard > unknown_word_or_chunk > connected_reduced_speech` priority order) while Material Quiz freely mixes `dictation`/`keyword_recognition`/`audio_transcript_choice` across its usable cues — documented here because nothing in the prompt strictly required this particular type-to-mode mapping.
- **Safe generation is enforced by never padding, not by a post-hoc filter.** Each per-cue (or per-annotation) question-building attempt either returns a fully valid `QuizQuestion` or `None`; a `None` means that cue/annotation is skipped entirely rather than downgraded into a weaker question. `create_material_quiz`/`create_review_quiz` cap the result at `requested_count` but accept fewer, and refuse creation outright (`QuizValidationError`) only when zero valid questions could be built at all — the caller can distinguish "smaller quiz created" from "refused" by comparing `QuizAttempt.actual_count` to `requested_count`, both of which are always populated.
- **Quiz playback reuses `PlayerSession`/`PlaybackController` exactly as the guided session does** — `QuizWindow` builds one `PlayerSession` over the material's full cue list and looks up each question's `subtitle_cue_id` to call the same `replay_cue`/`loop_cue` methods, so cue-timing/loop/replay/playback-error behavior is identical across the standalone player, the guided session, and quizzes; none of it is reimplemented here.
- **The consolidated review is a separate, explicitly-opened surface, not an inline reveal.** `QuizWindow` never shows correctness for any question at any status — a completed attempt only exposes a "View Consolidated Review" button that opens `QuizReviewDialog`, which reads `quiz_service.build_quiz_review`'s DTOs (already-parsed prompt/correct-answer JSON, per-item `is_correct`, and a scoring-rule explanation string derived from `scoring_config` at display time, never persisted redundantly). This keeps "answer now" and "review results" as two distinct window contexts, matching the guided session's own pattern of a live window plus a separate read-only history surface.

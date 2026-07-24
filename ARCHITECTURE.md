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

### Milestone 6 acceptance correction

- **The snapshot was incomplete: the source cue's text itself was still being read live.** `QuizReviewDialog` originally called `get_cue_by_id` against the live `subtitle_cue` table to show "Source cue:" text, which meant a later edit to that cue would change what an already-completed quiz's review displayed — contradicting the "never re-derived from live cue/annotation text" claim made elsewhere for `prompt_payload`/`correct_answer_payload`. Fixed by adding `quiz_question.source_cue_text` (migration 6, backfilled from live cue text for pre-existing rows) captured at generation time and threaded through `QuizReviewItem`; `QuizReviewDialog` no longer queries `subtitle_cue` at all.
- **Review Quiz could ask the same tested evidence twice.** Milestone 4 allows one cue range to carry several labels at once (e.g. both `misheard` and `unknown_word_or_chunk`), and `create_review_quiz` originally turned every qualifying `Annotation` into its own question — so the same span could appear as two separate, redundant questions. Fixed by deduplicating candidates by `(subtitle_cue_id, normalized tested-range text)` before priority-grouping, keeping only the highest-priority label's annotation per distinct span (`create_review_quiz` in `quiz_service.py`).
- **`submit_quiz` scored by `question_type`, not by the persisted `scoring_config`.** Since every current `question_type` maps to exactly one scoring rule this happened to be equivalent today, but it meant `scoring_config` — the field documented as the scoring source of truth — was decorative, and a future rule/version mismatch would have been silently scored under the wrong branch instead of refused. Fixed by making `scoring_config`'s `rule`/`version` authoritative in both `submit_quiz` and `save_quiz_answer` (`_load_supported_scoring_config`), which also now validates answer *shape* at save time (a text-scored question rejects a choice index, a choice-scored question rejects text and any out-of-range index) and rejects an unsupported rule/version by aborting the entire submission transaction (`conn.rollback()`) rather than scoring the rest of the attempt around it.

## Architecture Decisions Resolved in Milestone 7

- **Recording lifecycle and file-management logic is entirely application/domain-owned, never UI-owned.** `application/services/recording_service.py` is the only place that creates, validates, transitions, or deletes a `Recording` row or its managed WAV file; `infrastructure/media/recording.py` (`RecordingController`, wrapping `QMediaCaptureSession`/`QAudioInput`/`QMediaRecorder`) is a narrow Qt adapter with no lifecycle logic of its own, mirroring `PlaybackController`'s role for `QMediaPlayer`. The one UI widget that drives recording, `ui/widgets/recording_panel.py::RecordingPanel`, only wires Qt signals to `recording_service` calls and renders the result — it never writes a file path or a database row directly.
- **One recording system, two entry points, enforced by sharing one widget.** The milestone explicitly required Guided Session Stage 4 and standalone Shadowing Practice to reuse the same recording/playback/comparison/persistence/deletion logic rather than becoming two implementations that could quietly drift apart. This is enforced structurally: both `GuidedSessionWindow` (Stage 4) and the new `ShadowingPracticeWindow` embed the exact same `RecordingPanel` instance type, parameterized only by `(material_id, subtitle_cue_id, practice_session_id)` via `RecordingPanel.set_context` — Stage 4 passes its session id, standalone practice always passes `None`. There is no second recording widget or second copy of the start/stop/list/play/delete/compare code paths anywhere in `ui/`.
- **`deleted` is a real row-and-file removal, not a fourth stored status.** The product lifecycle names four stages (`recording`/`ready`/`failed`/`deleted`), but "deleting a take removes both its database record and managed audio file" is a hard delete, not a soft flag — so only `recording`/`ready`/`failed` are ever stored (`domain/enums/recording_status.py`), and `recording_service.delete_take` genuinely removes the row. Documented as a deliberate resolution of a literal-vs-intent reading, the same category of judgment call as Milestone 5's transcript-reveal auto-resolution and Milestone 6's Material-Quiz/Review-Quiz type-to-mode mapping.
- **Comparison sequencing (source, then a short pause, then the take) is a pure, framework-free state machine**, `domain/services/comparison_sequence.py::ComparisonSequencer` — mirroring `PlayerSession`'s existing pattern of "the pure object decides what happens next; the Qt-aware caller executes it." `RecordingPanel` owns one `ComparisonSequencer` and emits `request_play_source` for the *host* window to run one one-shot source-cue replay (via the host's own existing `PlayerSession.replay_cue`, exactly like the ordinary Replay Cue button) — the panel never touches the host's `PlaybackController` or `PlayerSession` directly. The host calls `RecordingPanel.notify_source_finished()` once that replay's `PlayerTick.pause` fires, driving the panel to its own short `QTimer` pause and then to playing the take on the panel's own second `PlaybackController`. Two independent `QMediaPlayer`s (source, take) are used specifically so the two streams are never mixed, matching the explicit "do not mix both audio streams simultaneously" boundary.
- **`practice_session_id` is `ON DELETE SET NULL`, not `CASCADE`.** A recording is app-managed local data with its own retention story; nothing about a `PracticeSession` disappearing (today, only ever a soft `abandoned` status — there is no "delete a session" operation) should be able to take a learner's recording down with it. This mirrors `SessionDiagnosisEvidence.annotation_id`'s Milestone 5 `SET NULL` pattern and directly satisfies "deleting a Practice Session must not silently delete standalone recordings" — after the (currently hypothetical) case of a session row actually being deleted, the recording simply becomes indistinguishable from one created in standalone mode.
- **The single-active-recording rule is enforced by a real database query, not just a disabled button.** `recording_service.begin_recording` checks for any existing `recording`-status row across the whole database before creating a new one, so the guarantee holds even across two windows sharing one connection (e.g. Guided Session Stage 4 open at the same time as standalone Shadowing Practice). A row stuck in `recording` status from a crash or forced close is swept up once at the next application startup (`recording_service.recover_interrupted_recordings`, called from `ui/app.py` right after `migrate()`) — marked `failed` and its partial file removed — so the rule can never become permanently unsatisfiable.
- **A stopped `QMediaPlayer` still locks its source file on Windows — caught by the required real-microphone manual smoke test, not by any automated (offscreen, synthetic-file) test.** Every automated test for `recording_service` uses synthetic WAV files written directly to disk, deliberately avoiding a dependency on real audio hardware; this is correct and sufficient for lifecycle/ownership/deletion logic, but it could not have caught a real Qt/OS resource-lifecycle behavior. Running the actual `RecordingPanel` against a real microphone surfaced it: playing a take with `RecordingPanel`'s own `PlaybackController` and then immediately deleting that same take failed with `file_deletion_failed`, because `PlaybackController.stop()` does not release the underlying file handle. Fixed with a new `PlaybackController.unload()` (stops and clears the source, actually releasing the OS-level lock), called by `RecordingPanel` before every delete action, after a take finishes or errors, on cue-context switches, and from both host windows' `closeEvent`. A synthetic-file regression test (`test_recording_panel_can_delete_a_take_immediately_after_playing_it`) was added afterward to lock in the fix at the automated-suite level, once the real cause was understood — the real-hardware pass is what actually found it.

### Milestone 7 acceptance correction

- **Session-linked recording was not actually gated on the session being in the shadowing stage.** `begin_recording` checked that a given `practice_session_id` belonged to the right material, but nothing stopped it from succeeding against a session sitting on Stage 1, or a completed/abandoned one — the UI only ever *showed* the recording panel on Stage 4, so this was reachable only via a bug or a second window on the same connection, but the service itself did not actually enforce it. Fixed by adding two checks in `begin_recording`: the session must be `active`, and its `current_stage` must be `shadowing`; a standalone recording (`practice_session_id=None`) is untouched by either check, per the explicit correction scope. Existing/new tests had to construct sessions with `enter_stage(..., "shadowing")` before linking a recording to them, which is itself evidence the previous behavior was under-constrained.
- **A saved-but-missing microphone still resulted in an implicitly selected device.** `RecordingPanel.refresh_devices` correctly computed `DeviceResolution(device=None, fallback_reason=...)` when the saved device was gone, but never told the combo box to reflect "nothing selected" — Qt auto-selects the first item added to an empty `QComboBox`, so the *first enumerated device* silently became the active selection, and the `_start_recording_button.setEnabled(...)` check only tested `self._device_combo.count() > 0`, not that anything was actually chosen. Recording could start against a device the learner never picked. Fixed by explicitly calling `setCurrentIndex(-1)` on fallback and changing the enable check to `self._selected_device() is not None`.
- **A stuck comparison could make take playback and deletion permanently unusable if the source could not play.** `ComparisonSequencer` only had forward transitions (`on_source_finished`/`on_pause_elapsed`/`on_recording_finished`); nothing told it "the source failed" or "the source ended without ever reaching the point that would normally advance the sequence." A playback error, or a cue whose end time exceeds the actual media duration, left the sequencer stuck in `PLAY_SOURCE`, and `_update_take_buttons` correctly-but-unhelpfully keeps Play/Delete disabled while `is_active`. Fixed with `RecordingPanel.notify_source_failed()` (cancels the sequencer and refreshes take-button state; a no-op if no comparison is running), wired identically into both hosts' `_on_playback_error` (explicit failure) and `_on_end_of_media` (media ended while a replay was still pending — the "cannot finish" case) — the same two hook points already used for `notify_source_finished`, so the fix is symmetric between `GuidedSessionWindow` and `ShadowingPracticeWindow` rather than living in only one.
- **Material removal could orphan a recording file.** The original M7 design deliberately let `remove_material` proceed even when a recording file failed to delete, reasoning that blocking removal on one locked file was worse — but that meant the DB cascade still removed the row, leaving a file on disk with nothing left pointing at it. The correction reverses this tradeoff: `remove_material` now raises `RecordingValidationError("recording_deletion_failed", ...)` and does **not** call `delete_material` at all if `delete_takes_for_material` reports any failure — the material and every still-undeleted recording row are left exactly as they were, so the learner can resolve the lock and retry the same removal. `MainWindow`'s confirmation dialog was also reworded to state plainly that recordings will be permanently deleted, not just implied by the removal itself.
- **The single-active-recording rule gained a real database constraint, not just the existing pre-check.** Migration 8 adds `idx_recording_one_in_progress`, a partial unique index on `recording(status) WHERE status = 'recording'` — the same pattern as Milestone 5's `idx_practice_session_one_active_per_material` — with a defensive `UPDATE` immediately before it that would resolve any pre-existing duplicate `recording`-status row (extremely unlikely given the pre-check already existed, but a migration must not fail against real data on the off chance one exists). `begin_recording` now wraps its insert in a `try`/`except sqlite3.IntegrityError`, translating a constraint violation into the identical `RecordingValidationError("recording_in_progress", ...)` the ordinary pre-check path raises — the two paths are indistinguishable to callers, and the index exists purely as a race-condition backstop, not a new user-facing behavior.

## Architecture Decisions Resolved in Milestone 8

- **Learning History is a read model layer, not a new source of truth.** `infrastructure/db/history_repository.py` holds every cross-material, bounded SQL query (joined with `material`/`subtitle_cue` titles where useful), returning raw `sqlite3.Row` results rather than converted domain models — these are report/aggregate shapes, not entities. `application/services/learning_history_service.py` is the only place that turns those rows into the public DTOs in `application/dto/learning_history.py` and applies this milestone's business rules (which counts as "completed" for aggregates, how session vs. quiz date-anchoring stays consistent, how chart data is bucketed by local calendar day, how Needs Attention reasons are assembled). No new authoritative table was added, and schema stayed at version 8 — every metric is derived from Milestones 3-7's existing `practice_session`/`session_stage_progress`/`session_diagnosis_evidence`/`quiz_attempt`/`quiz_question`/`quiz_answer`/`shadowing_cue_progress`/`recording`/`annotation` data, read through bounded, foreign-key-scoped queries rather than loading everything and filtering in Python.
- **Date-range resolution is a pure domain service**, `domain/services/date_range.py::resolve_date_range` — given a preset (`last_7_days`/`last_30_days`/`last_90_days`/`custom`/`all_time`) and the caller's current local calendar date, it returns a half-open `[start_utc, end_utc)` window already converted to the exact `datetime('now')` string format every table's timestamp columns use (SQLite's `datetime('now')` returns UTC, confirmed directly against this project's own database). Conversion happens per-boundary via `time.mktime` (not one fixed "now" offset applied to both ends), so a range spanning a DST transition still lands on the correct real-world instants. This function never reads the system clock itself, keeping it directly unit-testable (`tests/unit/test_date_range.py`) the same way `text_range.py`/`session_rules.py`/`quiz_rules.py` are.
- **"Needs Attention" reasons are simple, named, independently-evaluated rules**, `domain/services/needs_attention_rules.py::evaluate_material` — low recent-quiz-accuracy average, repeated diagnosis-label counts, multiple abandoned sessions, a frequently revisited material, sessions with many skipped stages, and an active unfinished session are each a separate, documented threshold constant and a separate `NeedsAttentionReason`. There is deliberately no combining formula anywhere — a material's entry is just the list of reasons that happened to fire, and the milestone prompt's "transparent evidence labels instead of one composite rank" requirement is enforced by this type simply never having a numeric score field at all.
- **Two evidence sources are kept structurally separate, never summed.** `session_diagnosis_evidence` (Milestone 5's per-session historical snapshot) and `annotation` (Milestone 4's current, editable, material-level diagnosis state) are read by two different functions (`list_diagnosis_insights` vs. `list_current_annotation_label_counts`) returning two different DTOs, rendered in two visibly separate sections of the Diagnoses tab. Nothing in `learning_history_service.py` ever adds a count from one to a count from the other.
- **One date anchor per record kind is used consistently everywhere that record appears**, not just in one view. A `PracticeSession`/`QuizAttempt`'s date-filter and Activity-feed anchor is the same expression in every query that touches it: `COALESCE(completed_at, abandoned_at, last_resumed_at)` — its own most recent meaningful state change. Overview's per-status counts use the literal matching column for that status (`completed_at` for completed, `abandoned_at` for abandoned, `last_resumed_at` for active), which is the value the COALESCE expression would already pick for a record in that status. `Continue Learning` (the list of currently-active sessions) and `Needs Attention` (a current snapshot) are the two deliberate, documented exceptions that ignore the date filter entirely, because both represent current actionable state rather than a historical window.
- **Shadowing's cumulative practice count is presented as an honest approximation under a date filter, not silently exact.** `shadowing_cue_progress.practice_count` is a lifetime counter per session/cue row with only a `last_practiced_at` timestamp, not a per-event log — there is no way to know how many of a row's practice clicks happened specifically inside an arbitrary date window. Filtering by date selects rows whose *most recent* practice falls in range and reports their *full* cumulative count; this is documented directly in `history_repository.list_shadowing_evidence`'s docstring, in `OverviewMetrics.shadowing_practice_count`'s docstring, and in the Overview tab's own on-screen label text — never fabricated as a true in-range event count, per the milestone's explicit "do not reconstruct daily shadowing counts" boundary.
- **Chart data and its tabular equivalent are computed from the exact same call, never two separate paths.** Each of the three charts (`chart_quiz_accuracy_over_time`, `chart_diagnosis_category_frequency`, `chart_completed_sessions_by_period`) returns one `ChartData` whose `points` list is rendered both by `ui/widgets/simple_bar_chart.py::SimpleBarChart` (a small dependency-free `QPainter` bar chart) and by an adjacent plain list/table in `LearningHistoryWindow` — the table is never a separate query, so it cannot drift from what the chart shows. Completed-sessions-by-period buckets by *local* calendar day, computed per-row from the stored UTC timestamp via `datetime.astimezone()` (not a UTC-string `GROUP BY`, which would misbucket a session completed shortly after local midnight).
- **Navigation from history never duplicates a workflow window.** `LearningHistoryWindow` holds no independent playback, recording, or quiz-taking logic of its own — every navigation action (Open Material, Resume/View Session Detail, Open Quiz Review, Jump to Cue, Open Shadowing Practice) constructs the same `PlayerWindow`/`GuidedSessionWindow`/`QuizWindow`/`QuizReviewDialog`/`ShadowingPracticeWindow` classes `MainWindow` already uses, via the same `load_material_for_player` loading path. Two small, additive, backward-compatible constructor parameters support "Jump to Cue" deep-linking without introducing a second navigation mechanism: `PlayerWindow(..., initial_cue_index: int | None = None)` selects that row in the existing cue list once, at construction, and `ShadowingPracticeWindow(..., initial_cue_id: int | None = None)` resolves it to the matching cue index the same way. Neither changes any existing call site's behavior when the new parameter is omitted.
- **No effective-study-time, pronunciation, or composite-score field exists anywhere in the new code** — not merely hidden by the UI. `OverviewMetrics` has no duration-since-start field and no combined-score field; there is no code path anywhere in `history_repository.py`/`learning_history_service.py` that computes wall-clock elapsed time between a session's `started_at` and `completed_at`, or that averages a diagnosis-frequency trend into an "improving/regressing" verdict. This mirrors the same category of hard architectural boundary as Milestone 6's "`is_correct` is genuinely absent from the data until submission" — here, "elapsed practice time" and "ability score" are genuinely absent from the data model at every layer, not just unsurfaced.

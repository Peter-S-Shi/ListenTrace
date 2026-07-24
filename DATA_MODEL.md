# ListenTrace Initial Data Model

This document defines the first domain direction. It is not a frozen database schema.

**Status (through Milestone 5)**: `Material`, `SubtitleTrack`, `SubtitleCue`, `Annotation`, `CueNote`, `SavedLanguageItem`, `AnnotationLabelPreference`, `PracticeSession`, `SessionStageProgress`, `StageResponse`, `KeywordCapture`, `SessionDiagnosisEvidence`, and `ShadowingCueProgress` are implemented as actual SQLite tables (schema version 4). Migration 2 added `Material.normalized_path`; migration 3 (Milestone 4) added the four learning-evidence tables; migration 4 (Milestone 5, additive, no data loss) added the six guided-session tables — see their sections below for the field lists actually implemented, which differ from this document's original design sketch in one deliberate way: `Annotation` did **not** gain a `practice_session_id` column. Instead, a session's diagnosis evidence is its own table (`SessionDiagnosisEvidence`) that optionally *links to* an `Annotation` row rather than living inside it — see that section for why. `QuizSession`, `QuizItemResult`, and `RecordingReference` remain design direction only and will be added as migrations in the milestones that need them.

## Entity Overview

```text
Material
  1 --- many SubtitleTracks
  1 --- many PracticeSessions        (implemented, Milestone 5)
  1 --- many SavedLanguageItems       (implemented, Milestone 4)

SubtitleTrack
  1 --- many SubtitleCues

SubtitleCue
  1 --- many Annotations              (implemented, Milestone 4 — independent of PracticeSession)
  1 --- 0..1 CueNote                  (implemented, Milestone 4)
  1 --- many SavedLanguageItems       (implemented, Milestone 4)
  1 --- many SessionDiagnosisEvidence (implemented, Milestone 5)
  1 --- many ShadowingCueProgress     (implemented, Milestone 5, one row per session/cue)

PracticeSession                       (implemented, Milestone 5)
  1 --- 5   SessionStageProgress      (exactly one row per stage key, created with the session)
  1 --- many StageResponses
  1 --- many KeywordCaptures
  1 --- many SessionDiagnosisEvidence
  1 --- many ShadowingCueProgress
  1 --- many QuizSessions             (design direction only, not yet implemented)
  1 --- many RecordingReferences      (design direction only, not yet implemented)

Annotation
  0..1 --- many SessionDiagnosisEvidence  (optional link, `ON DELETE SET NULL` — see below)
```

## Material

Represents one learning media item.

Suggested fields:

- `id`
- `title`
- `language`
- `media_path`
- `normalized_path` (added in migration 2: resolved absolute path, case-folded; unique — enforces duplicate-path rejection)
- `media_kind`
- `duration_ms`
- `file_size_bytes`
- `file_fingerprint` (partial-content hash: file size + first/last 1 MiB, not a full-file hash)
- `status` (`active` or `archived`; removal deletes the row rather than using a third status value)
- `created_at`
- `updated_at`
- `last_opened_at`

Notes:

- Store a filesystem reference, not media bytes.
- `normalized_path` catches re-importing the identical file path; `file_fingerprint` separately catches the same content at a different path (soft warning, not a hard rejection).
- Removing a record must not delete the source file by default — verified: `DELETE FROM material` cascades to `subtitle_track`/`subtitle_cue` via existing foreign keys but never touches the filesystem.

## SubtitleTrack

Represents one transcript associated with a material.

Suggested fields:

- `id`
- `material_id`
- `format`
- `language`
- `source_path`
- `is_timed`
- `encoding`
- `created_at`
- `updated_at`

## SubtitleCue

Normalized timed segment.

Suggested fields:

- `id`
- `subtitle_track_id`
- `cue_index`
- `start_ms`
- `end_ms`
- `text`
- `normalized_text`

Constraints:

- cue order is stable within a track;
- end time must not be earlier than start time;
- malformed or overlapping cues may be accepted only with explicit validation behavior.

## PracticeSession

One guided intensive-listening attempt. **Implemented (migration 4).**

Implemented fields:

- `id`
- `material_id` (FK → `material.id`, `ON DELETE CASCADE`)
- `mode` (only `intensive` so far; `speed` is future/Milestone 10 direction, not implemented)
- `status`
- `current_stage`
- `transcript_revealed_at` (`NULL` until Stage 3 is first entered; set at most once — see Constraints)
- `started_at`
- `updated_at`
- `last_resumed_at`
- `completed_at`
- `abandoned_at`

Status values (`domain/enums/session_status.py`):

- `active`
- `completed`
- `abandoned`

Allowed transitions (`domain/services/session_rules.py`): `active -> completed` and `active -> abandoned` only — a completed or abandoned session can never return to `active`, and `completed`/`abandoned` never transition to each other.

Constraints actually enforced:

- A partial unique index, `idx_practice_session_one_active_per_material` on `(material_id) WHERE status = 'active' AND mode = 'intensive'`, blocks a second concurrently-active intensive session for the same material at the database level (reinforcing the `practice_session_service.start_session` application-level check, which raises a typed `ActiveSessionExistsError`).
- `transcript_revealed_at` is set via `SET transcript_revealed_at = COALESCE(transcript_revealed_at, datetime('now'))` — idempotent, so re-entering Stage 3 in the same session never resets it.

## SessionStageProgress

Per-stage status within one `PracticeSession`. **Implemented (migration 4), not present in the original design sketch.** Exactly five rows (one per stage key) are created atomically with the session itself.

Implemented fields:

- `practice_session_id` (FK → `practice_session.id`, `ON DELETE CASCADE`; composite primary key with `stage_key`)
- `stage_key`
- `status`
- `outcome_key` (currently only ever `no_notable_difficulty`, Stage 3's explicit "nothing to report" action — distinct from both evidence-based completion and skipping)
- `skip_note` (optional, never required)
- `started_at` / `completed_at` / `skipped_at`
- `updated_at`

Stage keys (`domain/enums/stage_key.py`, in fixed order):

- `global_comprehension`
- `keyword_capture`
- `transcript_diagnosis`
- `shadowing`
- `final_summary`

Stage status values and allowed transitions (`domain/services/session_rules.py`): `not_started -> in_progress -> {completed, skipped}`, and `not_started -> skipped` directly. A terminal (`completed`/`skipped`) stage never transitions further within the same session.

Per-stage completion eligibility (evidence-based, checked before allowing a `completed` transition — see `application/services/practice_session_service.py::complete_stage`):

- Stage 1 (global comprehension): at least one prompt response is non-whitespace.
- Stage 2 (keyword capture): at least one capture exists.
- Stage 3 (transcript diagnosis): at least one `SessionDiagnosisEvidence` row exists, or `outcome_key = 'no_notable_difficulty'`.
- Stage 4 (shadowing): every `ShadowingCueProgress` row for the session has a status other than `not_started`.
- Stage 5 (final summary): the `summary` response is non-whitespace.

If none of the above holds, the stage must be explicitly skipped rather than completed.

**Transcript-reveal auto-resolution**: entering Stage 3 for the first time (`transcript_revealed_at` still `NULL`) both reveals the transcript and, for Stages 1 and 2 specifically, resolves whichever of them is not already `completed`/`skipped` — completing it if it already has qualifying evidence, otherwise skipping it with an automatic `skip_note`. This prevents a session from getting permanently stuck unable to reach `session_can_complete` because a transcript-locked stage was left `not_started`/`in_progress` forever.

## StageResponse

Stores learner input for a session stage. **Implemented (migration 4).** Used for both the Stage 1 comprehension prompts and the Stage 5 final summary (a single generic table, not a Stage-1-specific one).

Implemented fields:

- `id`
- `practice_session_id` (FK → `practice_session.id`, `ON DELETE CASCADE`)
- `stage_key`
- `prompt_key`
- `response_text`
- `created_at`
- `updated_at`

Constraint actually enforced: `UNIQUE (practice_session_id, stage_key, prompt_key)` — one response per session/stage/prompt, written via `INSERT ... ON CONFLICT DO UPDATE` upsert.

Stage 1 prompt keys: `who_is_speaking`, `where`, `intent`, `result`. Stage 5 prompt key: `summary`.

## KeywordCapture

A learner-entered word or fragment captured before transcript comparison. **Implemented (migration 4).**

Implemented fields:

- `id`
- `practice_session_id` (FK → `practice_session.id`, `ON DELETE CASCADE`)
- `capture_type`
- `text`
- `position` (learner-controlled display order, reassigned on every reorder via `session_repository.reorder_keyword_captures`)
- `created_at`
- `updated_at`

Capture types (`domain/enums/keyword_capture_type.py`): `keyword`, `name_or_place`, `number`, `phrase`, `uncertain_fragment`.

Rule: read-only once the transcript is revealed for the same session as any other Stage 1/2 evidence (enforced centrally in `practice_session_service`, not in the UI).

## Annotation

Semantic diagnosis attached to a cue or selected text range. **Implemented (migration 3).** `Annotation` still has no `practice_session_id` column and never will: Milestone 5 deliberately did *not* add a session association here (see `SessionDiagnosisEvidence` below for why) — `Annotation` remains an independent, material-level record regardless of which sessions have referenced it.

Implemented fields:

- `id`
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE`)
- `label_key`
- `selected_text`
- `selection_start` (zero-based, end-exclusive offset into the cue's `text`, in Python/Unicode-code-point units — see `domain/services/text_range.py`)
- `selection_end`
- `heard_as` (only ever populated when `label_key = 'misheard'`; `NULL` for every other label, even when several labels are saved together in one action)
- `note`
- `created_at`
- `updated_at`

Constraints actually enforced: `UNIQUE (subtitle_cue_id, label_key, selection_start, selection_end)` (blocks the exact-duplicate case at the database level, reinforcing the application-layer check); `CHECK (selection_end >= selection_start)`.

Editing: `annotation_service.update_annotation` can change every field on a row — `label_key`, `selection_start`/`selection_end` (and the `selected_text` re-derived from them), `heard_as`, and `note` — with the same validation as creation re-run (label validity, range bounds, Misheard-requires-`heard_as`, duplicate-on-same-range excluding the row being updated). The update is scoped to `WHERE id = ?`, so it can never affect a sibling row that shares the same cue/range under a different label.

Initial label keys:

- `keyword`
- `known_not_heard`
- `connected_reduced_speech`
- `misheard`
- `unknown_word_or_chunk`

## SessionDiagnosisEvidence

A guided-session snapshot of one Stage 3 diagnosis action. **Implemented (migration 4), not present in the original design sketch.**

Why a separate table instead of a `practice_session_id` column on `Annotation`: the Milestone 4 `Annotation` uniqueness constraint is `UNIQUE (subtitle_cue_id, label_key, selection_start, selection_end)` — one row per exact cue/label/range, full stop. If a second guided-session attempt on the same material diagnosed the exact same word again, adding a session column to `Annotation` would force a choice between violating that constraint or silently reusing/overwriting the first session's row (losing session-specific history). A dedicated table sidesteps this entirely: `SessionDiagnosisEvidence` has its own `UNIQUE (practice_session_id, subtitle_cue_id, label_key, selection_start, selection_end)`, so the same diagnosis can recur once per session indefinitely, while an *optional* link back to a shared `Annotation` row still lets material-level diagnosis tools (the Milestone 4 workspace) see it.

Implemented fields:

- `id`
- `practice_session_id` (FK → `practice_session.id`, `ON DELETE CASCADE`)
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE`)
- `annotation_id` (FK → `annotation.id`, `ON DELETE SET NULL` — nullable; a snapshot survives its linked annotation being deleted)
- `label_key`
- `selected_text`
- `selection_start` / `selection_end` (same canonical offset semantics as `Annotation`)
- `heard_as`
- `note`
- `created_at`
- `updated_at`

Constraints actually enforced: `UNIQUE (practice_session_id, subtitle_cue_id, label_key, selection_start, selection_end)`; `CHECK (selection_end >= selection_start)`.

Find-or-create linkage (`practice_session_service.record_session_diagnosis`): validates using the same domain rules as `annotation_service` (label validity, range bounds, Misheard-requires-`heard_as`), then looks for an existing `Annotation` with the exact same cue/label/range — reusing its id without overwriting any of its fields if found, or creating one if not — and always creates a new, independent `SessionDiagnosisEvidence` row. Editing (`update_session_diagnosis`) or deleting (`delete_session_diagnosis`) a snapshot touches only that row; the linked `Annotation`, if any, is never mutated or cascaded.

## ShadowingCueProgress

Per-cue Stage 4 practice state within one `PracticeSession`. **Implemented (migration 4), not present in the original design sketch.**

Implemented fields:

- `practice_session_id` (FK → `practice_session.id`, `ON DELETE CASCADE`; composite primary key with `subtitle_cue_id`)
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE`)
- `status`
- `practice_count` (incremented only by an explicit "Mark Practiced" action — playback alone is never treated as proof of practice)
- `note` (optional, per-cue)
- `last_practiced_at`
- `updated_at`

Status values (`domain/enums/shadowing_status.py`): `not_started`, `practiced`, `skipped`.

Rows are created eagerly, one per cue, the first time Stage 4 is entered (`session_repository.ensure_shadowing_rows`, `INSERT OR IGNORE` — safe to call again on every re-entry). Stage 4 is eligible to complete only once every row for the session has a status other than `not_started`; "Skip Remaining Cues" bulk-resolves every still-`not_started` row.

## CueNote

One free-form note per subtitle cue, distinct from an Annotation's per-annotation `note`. **Implemented (migration 3), not present in earlier drafts of this document.**

Implemented fields:

- `subtitle_cue_id` (primary key and FK → `subtitle_cue.id`, `ON DELETE CASCADE` — the primary-key choice itself enforces "at most one note per cue")
- `note_text` (never stored empty — see below)
- `created_at`
- `updated_at`

Rule: saving an empty/whitespace-only note is treated as delete-intent by `cue_note_service.save_cue_note` — the row is removed rather than persisted with empty text, so "cue has no note" and "cue has an empty-string note" are never both possible states.

## SavedLanguageItem

User-managed vocabulary item or chunk. **Implemented (migration 3).**

Implemented fields:

- `id`
- `material_id` (FK → `material.id`, `ON DELETE CASCADE` — **never accepted as caller input**; always derived server-side via `subtitle_cue -> subtitle_track -> material`, see below)
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE`)
- `item_type` (`word` / `phrase` / `chunk` / `sentence_pattern`)
- `text` (derived from the cue substring at the stored range, not a separately-trusted string)
- `normalized_text` (same normalization as subtitle cues — strips simple tags, collapses whitespace; used for duplicate/"same text elsewhere" lookups)
- `selection_start` / `selection_end` (same canonical offset semantics as Annotation)
- `meaning`
- `note`
- `context_text` (prefilled from the full cue text at save time, then freely user-editable and stored as typed)
- `created_at`
- `updated_at`

Constraint actually enforced: `UNIQUE (material_id, subtitle_cue_id, item_type, selection_start, selection_end, normalized_text)` — the exact-duplicate rule reinforced at the database level. A different cue/material with the same `normalized_text` is not blocked by this constraint; the application layer (`saved_language_item_service`) detects it and requires explicit confirmation before creating a second record.

`material_id` integrity: `saved_language_item_service.save_language_item` does not take `material_id` as a parameter — `infrastructure/db/learning_repository.get_material_id_for_subtitle_cue` derives it from the cue's actual ownership chain, so a cue from one material can never be recorded as belonging to another.

Editing: `saved_language_item_service.update_saved_language_item` can change `item_type` (re-running the duplicate check, since `item_type` is part of the uniqueness key), `meaning`, `note`, and `context_text`. `text`, `selection_start`/`selection_end`, and `normalized_text` are a locked identity once saved — changing what text an item refers to is delete-and-recreate, not update, and this is stated directly in the UI (not a control that silently ignores changes).

The application does not claim dictionary authority. The user edits and owns these fields.

## AnnotationLabelPreference

Global, material-independent presentation preference — not a per-annotation field. **Implemented (migration 3), seeded with defaults for all 5 labels at migration time.**

Implemented fields:

- `label_key` (primary key; one of the 5 stable label keys)
- `color` (6-digit hex string, validated by `label_preference_service`)
- `updated_at`

Rule: this table stores *only* the color preference. Label semantics/meaning are defined by the domain layer (`AnnotationLabel` enum), never by this table — changing a color must never be able to change what a stored `Annotation.label_key` means.

## QuizSession

Suggested fields:

- `id`
- `practice_session_id`
- `quiz_type`
- `status`
- `started_at`
- `completed_at`
- `total_items`
- `correct_count`

## QuizItemResult

Suggested fields:

- `id`
- `quiz_session_id`
- `subtitle_cue_id`
- `prompt_payload`
- `expected_payload`
- `response_payload`
- `is_correct`
- `answered_at`

Structured payloads should use a documented versioned format rather than arbitrary serialization.

## RecordingReference

References an optional local learner recording.

Suggested fields:

- `id`
- `practice_session_id`
- `subtitle_cue_id`
- `file_path`
- `format`
- `duration_ms`
- `created_at`

Recording bytes should remain outside SQLite.

## Future Progress Events

Analytics should be derived from reliable session, annotation, quiz, and review evidence. A generic event table may be introduced later only when concrete reporting needs justify it.

## Data Rules

- All destructive actions require explicit user intent.
- Foreign keys and cascading behavior must be reviewed carefully.
- Source media, subtitle files, recordings, databases, and exports are local user data.
- Database migrations must be additive and tested.
- Display colors never replace semantic label keys.
- Migrations 1→2→3→4 have each been additive only (no table rewritten or dropped) and are each covered by an automated upgrade test starting from the prior version's schema with real data present.

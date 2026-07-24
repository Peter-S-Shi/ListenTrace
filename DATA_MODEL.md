# ListenTrace Initial Data Model

This document defines the first domain direction. It is not a frozen database schema.

**Status (through Milestone 4)**: `Material`, `SubtitleTrack`, `SubtitleCue`, `Annotation`, `CueNote`, `SavedLanguageItem`, and `AnnotationLabelPreference` are implemented as actual SQLite tables (schema version 3). Migration 2 added `Material.normalized_path`; migration 3 (Milestone 4, additive, no data loss) added the four learning-evidence tables — see their sections below for the field lists actually implemented, which differ slightly from this document's original design sketch (in particular: `Annotation` and `SavedLanguageItem` are independent of any practice session in Milestone 4; `CueNote` was not in the original sketch at all). `PracticeSession`, `StageResponse`, `KeywordCapture`, `QuizSession`, `QuizItemResult`, and `RecordingReference` remain design direction only and will be added as migrations in the milestones that need them — Milestone 5 is expected to add an optional `practice_session_id` to `Annotation` via a further additive migration rather than redesigning the table.

## Entity Overview

```text
Material
  1 --- many SubtitleTracks
  1 --- many PracticeSessions        (design direction only, not yet implemented)
  1 --- many SavedLanguageItems       (implemented, Milestone 4)

SubtitleTrack
  1 --- many SubtitleCues

SubtitleCue
  1 --- many Annotations              (implemented, Milestone 4 — independent of PracticeSession)
  1 --- 0..1 CueNote                  (implemented, Milestone 4)
  1 --- many SavedLanguageItems       (implemented, Milestone 4)

PracticeSession                       (design direction only, not yet implemented)
  1 --- many StageResponses
  1 --- many QuizSessions
  1 --- many RecordingReferences
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

One guided or shorter practice attempt.

Suggested fields:

- `id`
- `material_id`
- `mode`
- `status`
- `current_stage`
- `started_at`
- `completed_at`
- `last_resumed_at`

Initial status values:

- `active`
- `completed`
- `abandoned`

Initial mode values:

- `intensive`
- future `speed`

## StageResponse

Stores learner input for a session stage.

Suggested fields:

- `id`
- `practice_session_id`
- `stage_key`
- `prompt_key`
- `response_text`
- `created_at`
- `updated_at`

Example prompt keys:

- `who_is_speaking`
- `where`
- `intent`
- `result`
- `final_summary`

## KeywordCapture

A learner-entered word or fragment captured before transcript comparison.

Suggested fields:

- `id`
- `practice_session_id`
- `text`
- `position`
- `created_at`

## Annotation

Semantic diagnosis attached to a cue or selected text range. **Implemented (migration 3).** Milestone 4 annotations have no `practice_session_id` — they are independent material/cue records by design, so Milestone 5 can add an optional association via a further additive migration rather than a redesign.

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

Initial label keys:

- `keyword`
- `known_not_heard`
- `connected_reduced_speech`
- `misheard`
- `unknown_word_or_chunk`

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
- `material_id` (FK → `material.id`, `ON DELETE CASCADE`)
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
- Migrations 1→2→3 have each been additive only (no table rewritten or dropped) and are each covered by an automated upgrade test starting from the prior version's schema with real data present.

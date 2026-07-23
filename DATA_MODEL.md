# ListenTrace Initial Data Model

This document defines the first domain direction. It is not a frozen database schema. Milestone 1 should convert it into migrations only after the application foundation and playback spike confirm the implementation approach.

## Entity Overview

```text
Material
  1 --- many SubtitleTracks
  1 --- many PracticeSessions
  1 --- many SavedLanguageItems

SubtitleTrack
  1 --- many SubtitleCues

PracticeSession
  1 --- many StageResponses
  1 --- many Annotations
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
- `media_kind`
- `duration_ms`
- `file_size_bytes`
- `file_fingerprint`
- `status`
- `created_at`
- `updated_at`
- `last_opened_at`

Notes:

- Store a filesystem reference, not media bytes.
- Fingerprinting should help detect replacement or movement without exposing file content.
- Removing a record must not delete the source file by default.

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

Semantic diagnosis attached to a cue or selected text range.

Suggested fields:

- `id`
- `practice_session_id`
- `subtitle_cue_id`
- `label_key`
- `selected_text`
- `selection_start`
- `selection_end`
- `heard_as`
- `note`
- `created_at`
- `updated_at`

Initial label keys:

- `keyword`
- `known_not_heard`
- `connected_reduced_speech`
- `misheard`
- `unknown_word_or_chunk`

## SavedLanguageItem

User-managed vocabulary item or chunk.

Suggested fields:

- `id`
- `material_id`
- `subtitle_cue_id`
- `item_type`
- `text`
- `meaning`
- `note`
- `context_text`
- `created_at`
- `updated_at`

The application does not claim dictionary authority. The user edits and owns these fields.

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

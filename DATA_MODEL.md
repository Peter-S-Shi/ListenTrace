# ListenTrace Initial Data Model

This document defines the first domain direction. It is not a frozen database schema.

**Status (through the Milestone 7 acceptance correction)**: `Material`, `SubtitleTrack`, `SubtitleCue`, `Annotation`, `CueNote`, `SavedLanguageItem`, `AnnotationLabelPreference`, `PracticeSession`, `SessionStageProgress`, `StageResponse`, `KeywordCapture`, `SessionDiagnosisEvidence`, `ShadowingCueProgress`, `QuizAttempt`, `QuizQuestion`, `QuizAnswer`, `Recording`, and `MicrophonePreference` are implemented as actual SQLite tables (schema version 8). Migration 2 added `Material.normalized_path`; migration 3 (Milestone 4) added the four learning-evidence tables; migration 4 (Milestone 5, additive, no data loss) added the six guided-session tables; migration 5 (Milestone 6, additive, no data loss) added the three quiz tables; migration 6 (Milestone 6 acceptance correction, additive) added `QuizQuestion.source_cue_text`; migration 7 (Milestone 7, additive, no data loss) added `Recording` and `MicrophonePreference`; migration 8 (Milestone 7 acceptance correction, additive) added the `idx_recording_one_in_progress` partial unique index — see their sections below for the field lists actually implemented, which differ from this document's original design sketch in three deliberate ways: `Annotation` did **not** gain a `practice_session_id` column (see `SessionDiagnosisEvidence` below for why), the quiz design replaced the sketched `QuizSession`/`QuizItemResult` pair with `QuizAttempt`/`QuizQuestion`/`QuizAnswer`, and `RecordingReference` was renamed `Recording` with a `practice_session_id` that is optional and `ON DELETE SET NULL` rather than required — see the `Recording` section below for why.

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
  1 --- many Recordings               (implemented, Milestone 7 — independent of PracticeSession)

PracticeSession                       (implemented, Milestone 5)
  1 --- 5   SessionStageProgress      (exactly one row per stage key, created with the session)
  1 --- many StageResponses
  1 --- many KeywordCaptures
  1 --- many SessionDiagnosisEvidence
  1 --- many ShadowingCueProgress
  0..1 --- many Recordings            (implemented, Milestone 7 — optional link, `ON DELETE SET NULL`)

Material
  1 --- many QuizAttempts             (implemented, Milestone 6 — independent of PracticeSession)
  1 --- many Recordings               (implemented, Milestone 7 — independent of PracticeSession)

QuizAttempt                           (implemented, Milestone 6)
  1 --- many QuizQuestions            (generation snapshot, stable position order)
QuizQuestion
  1 --- 0..1 QuizAnswer               (eagerly created with the question; unanswered until saved)
  0..1 --- 1 Annotation               (optional source-evidence link, `ON DELETE SET NULL`)
  0..1 --- 1 SavedLanguageItem        (optional source-evidence link, `ON DELETE SET NULL`)
  0..1 --- 1 KeywordCapture           (optional source-evidence link, `ON DELETE SET NULL`)

Annotation
  0..1 --- many SessionDiagnosisEvidence  (optional link, `ON DELETE SET NULL` — see below)
  0..1 --- many QuizQuestions              (optional source-evidence link, `ON DELETE SET NULL`)
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

## QuizAttempt

One quiz attempt (Material Quiz or Review Quiz) on one material. **Implemented (migration 5).** Independent of `PracticeSession` — a quiz does not require or belong to a guided intensive-listening session.

Implemented fields:

- `id`
- `material_id` (FK → `material.id`, `ON DELETE CASCADE`)
- `quiz_mode` (`material` or `review`)
- `status`
- `seed` (the deterministic RNG seed generation was run with — stored so an attempt's question set is reproducible/debuggable; auto-generated if the caller does not supply one)
- `requested_count` (what the learner asked for)
- `actual_count` (what could actually be generated — see Safe Generation below; may be less than `requested_count`, never more)
- `correct_count` (`NULL` until `submit_quiz` scores the attempt)
- `started_at` / `updated_at` / `last_resumed_at` / `completed_at` / `abandoned_at`

Status values (`domain/enums/quiz_status.py`): `active`, `completed`, `abandoned`. Allowed transitions (`domain/services/quiz_rules.py::is_valid_quiz_transition`): `active -> completed` and `active -> abandoned` only, mirroring `PracticeSession`'s lifecycle.

Constraint deliberately **not** enforced: unlike `PracticeSession`, there is no "one active quiz per material" unique index — the Milestone 6 prompt explicitly allows multiple concurrently-active quiz attempts per material, listed and resumed distinctly via Quiz History.

## QuizQuestion

One generated question within a `QuizAttempt` — an immutable snapshot, never rewritten after generation. **Implemented (migration 5; `source_cue_text` added in migration 6).**

Implemented fields:

- `id`
- `quiz_attempt_id` (FK → `quiz_attempt.id`, `ON DELETE CASCADE`)
- `position` (0-based stable order; `UNIQUE (quiz_attempt_id, position)`)
- `question_type` (`dictation`, `keyword_recognition`, `audio_transcript_choice`, or `review_missed`)
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE` — the cue played for this question)
- `source_cue_text` (migration 6 — the source cue's text captured at generation time, as part of the immutable snapshot; the consolidated review reads this, never the live `subtitle_cue.text`, so a later edit to the cue cannot change what an existing question or its review displays)
- `source_annotation_id` / `source_saved_item_id` / `source_keyword_capture_id` (all optional, `ON DELETE SET NULL` — whichever one, if any, this question's target/evidence was drawn from; a question snapshot survives its source being edited or deleted afterward)
- `prompt_payload` (JSON: what the learner is shown — never includes the answer itself, e.g. a dictation cue's full text is never present in `prompt_payload`, only in `correct_answer_payload`)
- `correct_answer_payload` (JSON: the answer snapshot used for scoring and for the consolidated review — never re-derived from live cue/annotation text after generation)
- `scoring_config` (JSON: `{"rule": ..., "version": 1}` — either `normalized_text_exact` for dictation/review-missed questions or `exact_choice_index` for keyword-recognition/audio-transcript-choice questions; this is the **authoritative** description of how the question is scored — `submit_quiz` reads it, not `question_type`, to decide text-vs-choice scoring, and refuses to score (aborting the whole submission) a rule/version it doesn't recognize rather than guessing; the consolidated review's scoring-rule explanation is also derived from this at display time)
- `created_at`

## QuizAnswer

The learner's answer to one `QuizQuestion` — mutable while the attempt is `active`, frozen once `completed`/`abandoned`. **Implemented (migration 5).** One row is eagerly created (`unanswered`, all value fields `NULL`) for every question at quiz-creation time, mirroring `ShadowingCueProgress`'s eager-row pattern — saving an answer is always an update, never an insert.

Implemented fields:

- `id`
- `quiz_question_id` (FK → `quiz_question.id`, `ON DELETE CASCADE`; `UNIQUE` — exactly one answer row per question)
- `raw_answer_text` (the learner's typed text, unmodified, for `dictation`/`review_missed` questions)
- `normalized_answer_text` (the same scoring normalization applied to `raw_answer_text` — case-folded, punctuation-stripped, whitespace-collapsed — computed and stored when the answer is saved, not only at scoring time)
- `selected_choice_index` (for `keyword_recognition`/`audio_transcript_choice` questions)
- `is_correct` (`NULL` until `submit_quiz` scores the attempt — correctness is genuinely absent from the row, not merely hidden by the UI, until the whole attempt is submitted)
- `answered_state` (`unanswered` or `answered`)
- `answered_at`

Constraint actually enforced: `UNIQUE (quiz_question_id)`.

`quiz_service.save_quiz_answer` validates answer shape against the question's authoritative `scoring_config` rule before persisting: a text-scored question (`normalized_text_exact`) accepts `raw_answer_text` only, a choice-scored question (`exact_choice_index`) accepts `selected_choice_index` only and rejects an out-of-range index — a malformed answer is refused (`QuizValidationError("invalid_answer_shape", ...)`) rather than silently stored.

## Quiz Generation and Scoring (`domain/services/quiz_rules.py`, `application/services/quiz_service.py`)

Generation is deterministic and reproducible: every random choice (which cue gets which question type, which meaningful token is blanked, which distractors are picked, review-evidence tie-break ordering within the same priority label) is made through one seeded `random.Random(seed)` instance, and the seed itself is persisted on `QuizAttempt`. The pure selection/validation math (text normalization, tokenization, blank-span selection, whole-token-boundary containment checks, distractor de-duplication) lives in `domain/services/quiz_rules.py` with no sqlite or Qt dependency; `application/services/quiz_service.py` orchestrates it against real material/cue/annotation/saved-item/keyword-capture data and persists the result.

- **Material Quiz**: built only from "usable" cues (cues with at least one non-punctuation, non-whitespace token). Each cue is used for at most one question; if fewer usable cues exist than `requested_count`, the smaller quiz is created rather than reusing a cue or padding with a weak question — if *no* usable cues exist, creation is refused (`QuizValidationError("no_usable_cues", ...)`).
- **Review Quiz**: built only from the material's own `Annotation` rows (never another material's, and never a session-scoped `SessionDiagnosisEvidence` row directly — `Annotation` is the material-level, cross-session evidence table), filtered to the four diagnosis labels and ordered by the priority `misheard > known_not_heard > unknown_word_or_chunk > connected_reduced_speech`. Because Milestone 4 allows one cue range to carry several labels at once, candidates are first deduplicated by `(subtitle_cue_id, normalized tested-range text)` — when several labels describe the exact same tested evidence, only the single highest-priority label's annotation becomes a question, so the same span is never asked about twice. If no qualifying annotation exists, creation is refused (`QuizValidationError("no_meaningful_questions", ...)`). Every Review Quiz question is `review_missed`, always blanking exactly the annotation's own stored range — no additional token selection.
- **Dictation** questions choose between full-cue dictation and single-meaningful-token fill-in-the-blank; blanking is skipped in favor of full-cue mode whenever a cue has fewer than two meaningful tokens (blanking a cue's only real content would leave nothing to answer from).
- **Keyword Recognition** questions prefer a target tied to real evidence on that cue (an `Annotation` or `SavedLanguageItem` already attached to it) before falling back to a deterministically chosen token from the cue itself; a negative ("did NOT occur") question's target is verified via whole-token-boundary containment (`quiz_rules.cue_contains_target`) to genuinely not occur in that cue before being used.
- **Audio-to-Transcript-Choice** questions require at least 2 valid distractors (other cues in the same material, deduplicated by normalized text against both the correct answer and each other) before being created at all; a cue without enough distinct distractors is skipped rather than shipped as a weak 2-choice or duplicate-choice question.
- **Scoring**: `dictation`/`review_missed` compare `normalize_answer_text(raw_answer)` against the stored `normalized_answer_text` in `correct_answer_payload` (case-insensitive, punctuation-insensitive, whitespace-collapsed, otherwise exact); `keyword_recognition`/`audio_transcript_choice` compare `selected_choice_index` against the stored `correct_choice_index`. Scoring happens exactly once, inside `quiz_service.submit_quiz`, as a single all-or-nothing transaction that also marks the attempt `completed` — an answer's `is_correct` is `NULL` at every point before that call.

## Recording

One learner shadowing take. **Implemented (migration 7).** A cue may have any number of recordings — new takes never overwrite or replace older ones; the learner deletes what they no longer want. Renamed from the original design sketch's `RecordingReference` (same purpose) once the actual ownership/lifecycle requirements were worked out.

Implemented fields:

- `id`
- `material_id` (FK → `material.id`, `ON DELETE CASCADE` — always present; every recording belongs to exactly one material)
- `subtitle_cue_id` (FK → `subtitle_cue.id`, `ON DELETE CASCADE` — the cue this take is shadowing; validated against `material_id` by `recording_service.begin_recording`, never trusted from caller input)
- `practice_session_id` (optional, FK → `practice_session.id`, `ON DELETE SET NULL`) — set when the take was created from Guided Session Stage 4, `NULL` when created from standalone Shadowing Practice. **Deliberately `SET NULL`, not `CASCADE`**: a take is app-managed local data in its own right (a `PracticeSession`'s deletion — currently only ever a soft `abandoned` status, never a real row delete — must not silently take a learner's recording down with it); losing the session link just makes an already-standalone-looking take fully standalone. When set, `recording_service.begin_recording` (acceptance correction) requires that session to be `active` and its `current_stage` to be `shadowing` — recording is a Stage 4 action, enforced at the service layer, not only by the UI only showing the recording panel there. A standalone recording (`practice_session_id = NULL`) is never subject to this check.
- `relative_file_path` (`UNIQUE` — app-managed path, relative to the recordings root under the app-data directory, e.g. `"<material_id>/<uuid4>.wav"`; a collision-resistant filename, never a material title, transcript text, username, machine name, or absolute source path)
- `format` (always `"wav"` for Milestone 7 — no user-selectable formats, transcoding, or external codec dependencies)
- `duration_ms` (`NULL` until the take is scored `ready`)
- `device_descriptor` (the human-readable device description at capture time, e.g. `"Microphone Array (Realtek(R) Audio)"` — diagnostic/display only, not used for playback)
- `status` (`recording`, `ready`, or `failed` — see below)
- `failure_detail` (set only when `status = 'failed'`; a short diagnostic message, never raw exception internals)
- `created_at` / `updated_at`

**Lifecycle.** Three statuses are actually stored: `recording` (capture in progress, not yet usable), `ready` (validated, playable), `failed` (invalid/zero-length capture, or an aborted/interrupted one — the file is removed, but the row is kept so the learner sees that *something* happened rather than a silent no-op). The product's stated four-stage lifecycle (`recording`/`ready`/`failed`/`deleted`) treats `deleted` as a real, hard removal of both the row and the managed file (`recording_service.delete_take`) rather than a fourth stored status — a `deleted` row with no backing file would be a broken reference, not history worth keeping. Allowed status transitions (`domain/services/recording_rules.py::is_valid_recording_transition`): `recording -> ready` and `recording -> failed` only; both are terminal. Only one row may be in `recording` status across the whole database at a time — enforced both by an application-level pre-check in `recording_service.begin_recording` and, as of the acceptance correction, by a partial unique index at the database level (**migration 8**: `CREATE UNIQUE INDEX idx_recording_one_in_progress ON recording(status) WHERE status = 'recording'`, mirroring `idx_practice_session_one_active_per_material`); a `sqlite3.IntegrityError` from that index is translated back into the same typed `RecordingValidationError("recording_in_progress", ...)` the pre-check raises. A row still `recording` after an app crash/forced close is recovered at the next startup (`recording_service.recover_interrupted_recordings`, called once from `ui/app.py`), which marks it `failed` and cleans up its partial file so the single-active-recording rule never gets permanently stuck.

**Not stored in SQLite:** raw audio bytes. `relative_file_path` is the only pointer to the actual WAV file, stored under `appdata.get_recordings_dir()`.

## MicrophonePreference

The learner's remembered microphone choice. **Implemented (migration 7).** A single row (`id = 1`, enforced by `CHECK (id = 1)`), app-wide rather than per-material — recording is a device-level choice, not a per-lesson one.

Implemented fields:

- `id` (always `1`)
- `device_id` (a stable, hex-encoded device identity from Qt's `QAudioDevice.id()` — not the human-readable description, which can collide or change)
- `device_description` (human-readable, shown in the device dropdown and remembered for display even if the device later disappears)
- `updated_at`

`recording_service.resolve_preferred_device` never silently substitutes a different device for one that was saved but is no longer connected — it returns no device plus a clear `fallback_reason`, and the UI requires the learner to explicitly choose again.

## Future Progress Events

Analytics should be derived from reliable session, annotation, quiz, and review evidence. A generic event table may be introduced later only when concrete reporting needs justify it.

## Data Rules

- All destructive actions require explicit user intent.
- Foreign keys and cascading behavior must be reviewed carefully.
- Source media, subtitle files, recordings, databases, and exports are local user data.
- Database migrations must be additive and tested.
- Display colors never replace semantic label keys.
- Migrations 1→2→3→4→5→6→7→8 have each been additive only (no table rewritten or dropped) and are each covered by an automated upgrade test starting from the prior version's schema with real data present. Migration 6 adds `quiz_question.source_cue_text` and backfills it from the live `subtitle_cue.text` for any pre-existing rows. Migration 7 adds `recording` and `microphone_preference`. Migration 8 adds `idx_recording_one_in_progress` (a partial unique index enforcing at most one `recording`-status row), defensively recovering any pre-existing duplicate first so the index creation itself cannot fail against real data.

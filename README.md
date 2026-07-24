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

Milestones 1–6 are implemented and verified. Users can import a local media file plus an SRT/WebVTT subtitle into a library, view details, rename, archive/restore, and remove records, then open a synchronized player: play/pause/seek, active-cue tracking, previous/next-cue navigation, replay-once, single-cue and continuous-range looping, transcript show/hide, volume/mute, and keyboard shortcuts. The player includes an integrated transcript workspace: select an editing cue (independent of whatever cue is currently playing), select a text range, and save one or more semantic labels (keyword, known-but-not-heard, connected/reduced speech, misheard, unknown word/chunk) as annotations; keep a free-form note per cue; and save reusable word/phrase/chunk/sentence-pattern language items with source context.

The library also offers a guided, resumable intensive-listening session (Start/Resume Intensive Practice, plus a Session History view) alongside the standalone player: five sequential stages — global comprehension, keyword/fragment capture, transcript comparison and error diagnosis, sentence-level shadowing, and a transcript-free final summary — each with its own persisted status (not started/in progress/completed/skipped) and explicit Skip Stage support so the workflow never becomes a rigid exam. At most one intensive session is active per material at a time; completed or abandoned sessions remain as read-only history. Revealing the transcript for Stage 3 locks Stages 1 and 2 as read-only evidence for that session. Stage 3 diagnosis reuses the exact same semantic-label/highlighting/Unicode-offset logic as the standalone workspace, recording a repeatable per-session snapshot that optionally links to (without ever overwriting) a shared material-level annotation. Duplicate handling, atomic writes, and no modification of source files apply throughout.

The library also offers deterministic, locally-generated quizzes (Start Material Quiz / Start Review Quiz / Resume Quiz / Quiz History): cue dictation or fill-in-the-blank, keyword recognition (does a word/chunk occur in this cue?), audio-to-transcript multiple choice, and — for a Review Quiz built from a material's own saved diagnosis history — targeted recall of previously misheard or missed spots, prioritized `misheard > known but not heard > unknown word/chunk > connected/reduced speech`. A requested question count is a target, not a promise: a material with too little usable content produces a smaller quiz or is refused outright rather than padded with weak or duplicate questions. Correctness is never revealed question-by-question — the learner answers the whole quiz, submits it once (an atomic, all-or-nothing scoring transaction), and only then sees one consolidated review showing their answer, the correct answer, correct/incorrect, the source cue, the question type, and a short explanation of the scoring rule. Quiz attempts can be closed and resumed without losing answers; completed and abandoned attempts are permanently read-only, and multiple quiz attempts may be active on the same material at once. Text scoring ignores case, punctuation, and extra whitespace but otherwise requires exact spelling — no fuzzy or AI-assisted matching.

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
                       # PlayerLoadResult, LoopMode/PlayerTick, SavedItemSuccess/NeedsConfirmation,
                       # CueWorkspace, PracticeSessionState, QuizState, QuizReviewItem/QuizReviewResult
    services/         # material_import_service, material_library_service,
                       # player_loading_service, player_session (pure, no Qt),
                       # annotation_service, cue_note_service, saved_language_item_service,
                       # label_preference_service, cue_workspace_service, practice_session_service,
                       # quiz_service
  domain/
    enums/            # MaterialStatus, AnnotationLabel, SavedItemType, SessionStatus, StageStatus,
                       # StageKey, KeywordCaptureType, StageOutcome, ShadowingStatus, QuizMode,
                       # QuizStatus, QuestionType, AnsweredState
    models/           # Material, SubtitleTrack, SubtitleCue, Annotation, CueNote, SavedLanguageItem,
                       # PracticeSession, SessionStageProgress, StageResponse, KeywordCapture,
                       # SessionDiagnosisEvidence, ShadowingCueProgress, QuizAttempt, QuizQuestion,
                       # QuizAnswer
    services/         # CueIndex (active-cue/navigation rules), text_range (canonical selection
                       # offsets), session_rules (session/stage lifecycle + completion eligibility),
                       # quiz_rules (deterministic generation/scoring math) — all pure, no Qt
  infrastructure/
    db/               # SQLite connection, migrations, repository + learning_repository +
                       # session_repository + quiz_repository functions
    subtitles/        # SRT/WebVTT parsers, timecode and text normalization
    media/            # PlaybackController adapter around QtMultimedia; file validation/fingerprinting
    appdata.py         # cross-platform app-data directory resolution
    logging_setup.py   # rotating file + console logging
  ui/
    annotation_highlighting.py  # shared transcript-highlight painting (used by PlayerWindow and
                                 # GuidedSessionWindow — not duplicated)
    text_offset_conversion.py   # shared Qt UTF-16 <-> Python code-point offset conversion
    app.py            # application entry point
    windows/          # MainWindow (material library), ImportDialog, PlayerWindow
                       # (with integrated transcript workspace), LabelColorDialog,
                       # GuidedSessionWindow (five-stage guided session), SessionHistoryDialog,
                       # QuizWindow, QuizHistoryDialog, QuizReviewDialog
tests/
  unit/               # subtitle parsing, CueIndex, PlayerSession, text_range, session_rules,
                       # quiz_rules
  integration/        # database/migrations, import, library, player, player workspace,
                       # annotations, cue notes, saved language items, label preferences,
                       # practice_session_service, guided session window, quiz_service, UI smoke
  fixtures/
docs/
```

## Current Limitations

- No shadowing audio recording or progress analytics yet (planned for Milestone 7+); Milestone 5's shadowing stage tracks practiced/skipped status and count but never records or plays back the learner's own voice.
- Quizzes are deterministic and locally generated only — no AI-generated questions, fuzzy/semantic answer grading, speech recognition, or adaptive difficulty (see `docs/PRODUCT_SPEC.md`).
- Only one primary subtitle track per material is managed through the UI, though the schema supports more.
- Plain-text (non-timed) transcript import is not supported.
- Player loop/replay timing uses a small internal tolerance (50ms) appropriate for QtMultimedia's position-update cadence; it is not frame-exact.
- Canonical text-selection offsets are Python code-point based; text requiring UTF-16 surrogate pairs (some emoji) is verified to round-trip correctly in both the standalone workspace and the guided session's Stage 3 diagnosis panel.
- Real-file, multi-codec playback and audio/video-device behavior are only verified with a synthesized WAV and one locally generated H.264/MP4 clip, on Windows so far.
- After saving/updating/deleting an annotation, saved item, keyword capture, or session diagnosis, the corresponding list loses its selection (the form clears) — the user reselects a row to continue editing it.
- Text-only transcripts cannot provide reliable sentence seeking unless timing data is added.
- Speech recognition, pronunciation scoring, automatic translation, subtitle generation, dictionary lookups, and cloud synchronization are outside the first release.
- Users are responsible for using media and transcript material they are legally permitted to use.

## Privacy

ListenTrace is local-first. User media, transcripts, annotations, recordings, and learning records should remain on the user's device unless the user explicitly exports them.

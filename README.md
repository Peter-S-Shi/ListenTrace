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

On Windows, once `.venv` is set up, `run_listentrace.bat` (repo root) is a
double-click launcher that starts the app without a console window. It is a
developer convenience for anyone who already has the repo cloned and `.venv`
installed — not an end-user installer; see `packaging/README.md` for the
PyInstaller/Inno Setup build that produces a real Start Menu shortcut for
people without a Python environment. To pin `run_listentrace.bat` to your
desktop or taskbar, right-click it and choose "Send to > Desktop (create
shortcut)"; the resulting shortcut can optionally be given the app's icon via
its Properties > Change Icon, pointing at `packaging/assets/listentrace.ico`.

Run the automated tests:

```bash
.venv/Scripts/python -m pytest
```

## Development Status

Milestones 1–10 are implemented and verified. Users can import a local media file plus an SRT/WebVTT subtitle into a library, view details, rename, archive/restore, and remove records, then open a synchronized player: play/pause/seek, active-cue tracking, previous/next-cue navigation, replay-once, single-cue and continuous-range looping, transcript show/hide, volume/mute, and keyboard shortcuts. The player includes an integrated transcript workspace: select an editing cue (independent of whatever cue is currently playing), select a text range, and save one or more semantic labels (keyword, known-but-not-heard, connected/reduced speech, misheard, unknown word/chunk) as annotations; keep a free-form note per cue; and save reusable word/phrase/chunk/sentence-pattern language items with source context.

The library also offers a guided, resumable intensive-listening session (Start/Resume Intensive Practice, plus a Session History view) alongside the standalone player: five sequential stages — global comprehension, keyword/fragment capture, transcript comparison and error diagnosis, sentence-level shadowing, and a transcript-free final summary — each with its own persisted status (not started/in progress/completed/skipped) and explicit Skip Stage support so the workflow never becomes a rigid exam. At most one intensive session is active per material at a time; completed or abandoned sessions remain as read-only history. Revealing the transcript for Stage 3 locks Stages 1 and 2 as read-only evidence for that session. Stage 3 diagnosis reuses the exact same semantic-label/highlighting/Unicode-offset logic as the standalone workspace, recording a repeatable per-session snapshot that optionally links to (without ever overwriting) a shared material-level annotation. Duplicate handling, atomic writes, and no modification of source files apply throughout.

The library also offers deterministic, locally-generated quizzes (Start Material Quiz / Start Review Quiz / Resume Quiz / Quiz History): cue dictation or fill-in-the-blank, keyword recognition (does a word/chunk occur in this cue?), audio-to-transcript multiple choice, and — for a Review Quiz built from a material's own saved diagnosis history — targeted recall of previously misheard or missed spots, prioritized `misheard > known but not heard > unknown word/chunk > connected/reduced speech`. A requested question count is a target, not a promise: a material with too little usable content produces a smaller quiz or is refused outright rather than padded with weak or duplicate questions. Correctness is never revealed question-by-question — the learner answers the whole quiz, submits it once (an atomic, all-or-nothing scoring transaction), and only then sees one consolidated review showing their answer, the correct answer, correct/incorrect, the source cue, the question type, and a short explanation of the scoring rule. Quiz attempts can be closed and resumed without losing answers; completed and abandoned attempts are permanently read-only, and multiple quiz attempts may be active on the same material at once. Text scoring ignores case, punctuation, and extra whitespace but otherwise requires exact spelling — no fuzzy or AI-assisted matching.

The library also offers shadowing recording, from Guided Session Stage 4 or a standalone Shadowing Practice window (both reuse the exact same recording widget — there is only one recording system, not two): pick a microphone (remembered for next time, never silently swapped if it disappears), record a take as local WAV, and keep as many takes per cue as wanted until explicitly deleted (one take, every take for a cue, or every take for a material). Play any take, or run a source-then-take comparison that plays the original cue, pauses briefly, then plays the take — never mixed together. A take is only ever listed once it is confirmed valid; a failed or aborted capture never appears as a normal playable take. Only one recording can be in progress at a time, and a capture interrupted by a crash or forced close is automatically cleaned up the next time the app starts. Recording is entirely optional in Guided Session Stage 4 and never changes any stage's completion status.

A global **Learning History** view (opens with no material selected, or preselected from the library) is a read-only learning-evidence center across six areas — Overview, Activity, Sessions, Diagnoses, Quizzes, and Shadowing & Recordings — filterable by material and by date range (Last 7/30/90 Days, Custom Range, All Time, applied consistently across every list and chart in the local timezone). Active/Completed/Abandoned sessions stay visibly distinct (only Completed counts as completed practice); a dedicated Continue Learning area always shows active sessions regardless of the date filter; session-scoped diagnosis history is shown separately from the material's current, editable annotations; quiz trends are grouped strictly by material and mode; a Needs Attention list gives each flagged material transparent, independently-named reasons rather than one score; and every list can navigate back into the live workflow (open the material, resume or view a session, open a quiz's review, jump to a cue, open Shadowing Practice). No effective study time, pronunciation score, or combined ability/difficulty score is ever computed or shown — only real stored evidence.

From Learning History, **Export Learning Evidence** builds a local, user-controlled Markdown or JSON export of the same stored evidence: choose a scope (All Materials / One Material / Selected Materials), a date range (the same presets and local-time rules as Learning History), which evidence categories to include, and which privacy-sensitive fields (transcript excerpts, learner notes, mishearing text, vocabulary meanings, source labels, local file names) to include or redact — an unchecked field is redacted in place, never silently dropped along with its whole record. Absolute paths, original media/subtitle/recording paths, and raw audio are never included, regardless of any selection. A preview (Markdown, JSON, and a separate reusable external-evaluation instruction template) is generated before anything is saved or copied, and the exact same generated text is what gets written to disk (atomically, with overwrite confirmation) or copied to the clipboard — nothing is ever regenerated between preview and save. The JSON export carries a stable `export_version` (currently `1`), independent of the database schema version. No network request is made anywhere in the export flow.

The library also offers **Quick Practice** — a short, low-friction, cue-based practice mode, a companion to Guided Intensive Listening rather than a replacement for it. Start it from the Material Library / Learning History (**Quick Practice**, choosing Recommended Practice — 3, 5, or 10 cues, default 5, from a deterministic, reason-based recommendation list built from existing diagnosis/quiz/shadowing evidence, with a safe fallback when too little evidence exists — or Selected Cues, in whatever order picked) or from the Player (**Quick Practice This Cue** / **Quick Practice Selected Cues**, starting immediately from the current cue or range). Each cue runs one compact, forward-only cycle: Listen (transcript hidden) -> Recall (Understood/Partly Understood/Missed, required, plus an optional guessed fragment) -> Reveal & Diagnose (the same semantic labels and validation as the standalone workspace, always optional) -> Replay & Shadow (optional explicit shadowing mark, optional recording through the same shared recording widget). There is no exact-step resume: closing after at least one completed cue preserves that evidence as a read-only abandoned run; closing before any cue is completed discards the run entirely rather than leaving misleading history. A concise completion summary (cues completed, recall-result counts, diagnoses created, shadowing actions, recordings created, cues worth revisiting) never computes an effective-time, pronunciation, ability, difficulty, or improvement score. Quick Practice evidence is always counted separately from Intensive Practice and Quiz evidence in Learning History (a `Quick Practices Completed` overview count, its own Activity entries, and a dedicated history tab), can trigger its own transparent Needs Attention reason (`Missed repeatedly in Quick Practice`, requiring at least two Missed results), and has its own independent, privacy-controlled export category.

Milestone 10 reached the **Functional Feature Complete Gate**: it was the final planned *functional*-feature milestone for the first release, and the project is now in Functional Feature Freeze (which constrains learning workflow/domain/analytics/AI-cloud scope, not UI redesign). Feature Complete is explicitly not the same as Release Ready — release engineering, presentation convergence, and product-wide hardening remain. The optional assisted features once numbered "Milestone 11" (speech recognition, pronunciation feedback, translation, and similar) are deferred beyond v1.0 and no longer carry a milestone number — see `ROADMAP.md`'s "Deferred Beyond v1.0" section. **Milestone 11 — UI/UX Presentation Refresh is complete and accepted**: a presentation-only pass over the existing Qt Widgets UI (centralized theme, all 14 windows migrated); the Presentation Complete Gate has passed. v1.0 Release Engineering's Phase A — Packaging Spike, Phase B — targeted technical Release Hardening, and Phase C1 — development-machine Release Preflight are all complete: a Windows PyInstaller build, an Inno Setup installer, and a portable zip have all been built and validated end-to-end (see `packaging/README.md`), a corrective-work pass fixed a migration-atomicity bug, a startup-crash-before-`QApplication` gap, added crash logging and large-history database indexes, and added a partial Windows long-path mitigation (see `ARCHITECTURE.md`), and a development-machine preflight covered install/upgrade/uninstall, a legacy database upgrade, real audio/microphone checks, and a full feature-area walkthrough. **Milestone 12 — Pre-UI Product Hardening is complete and merged** (a system-wide audit and defect-repair pass, not a new-feature milestone — see `PROJECT_STATUS.md` and `docs/HARDENING_BACKLOG.md`), including the Loop Cue audible-endpoint defect chain, closed with a human-calibrated fix (**HUMAN ACCEPTED / CLOSED**). **Milestone 13 — Advanced UI/UX Reconstruction is complete, accepted, and merged into `main`** (a whole-product Notebook Study Desk reconstruction across all 16 production surfaces, Axes 1–8 closed, Product Owner Human Visual Gate **PASS**, short-screen accessibility and aspect-ratio-aware video geometry verified). It is followed by **Milestone 14 — Final Product Hardening & Full Manual Regression** (Phase 0 immediate correctives, a Whole-Product Hardening Audit and its corrective batches, and the user's full Human QA Round 2 pass against the final UI — all complete/PASS; a bounded pre-merge repository-hygiene/privacy/Windows-app-identity corrective remains before the branch is merge-ready), then **Milestone 15 — Release Candidate & Delivery** (Candidate Build/Packaging Refresh, Clean-Machine Acceptance, and Release Candidate Closure & Delivery) — see `ROADMAP.md`.

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
                       # CueWorkspace, PracticeSessionState, QuizState, QuizReviewItem/QuizReviewResult,
                       # DeviceResolution, DeletionSummary, learning_history (OverviewMetrics,
                       # ActivityItem, SessionHistoryEntry, DiagnosisCategorySummary, QuizHistoryEntry,
                       # QuizComparisonGroup, NeedsAttentionEntry, ShadowingEvidenceEntry,
                       # RecordingEvidenceEntry/Summary, QuickPracticeHistoryEntry/ItemResult,
                       # ChartData/ChartPoint, export (ExportScope/ExportBundle), quick_practice
                       # (QuickPracticeSessionState/ItemState, RecommendedCueEntry,
                       # QuickPracticeCompletionSummary)
    services/         # material_import_service, material_library_service,
                       # player_loading_service, player_session (pure, no Qt),
                       # annotation_service, cue_note_service, saved_language_item_service,
                       # label_preference_service, cue_workspace_service, practice_session_service,
                       # quiz_service, recording_service, learning_history_service,
                       # export_service (build_export), export_formatters (Markdown/JSON/
                       # evaluation-template rendering), quick_practice_service (recommend_cues,
                       # start_recommended_session/start_selected_session, recall/diagnosis/
                       # shadowed/completion lifecycle, close_session, completion summary)
  domain/
    enums/            # MaterialStatus, AnnotationLabel, SavedItemType, SessionStatus, StageStatus,
                       # StageKey, KeywordCaptureType, StageOutcome, ShadowingStatus, QuizMode,
                       # QuizStatus, QuestionType, AnsweredState, RecordingStatus, RecallResult,
                       # QuickPracticeStatus, QuickPracticeSource
    models/           # Material, SubtitleTrack, SubtitleCue, Annotation, CueNote, SavedLanguageItem,
                       # PracticeSession, SessionStageProgress, StageResponse, KeywordCapture,
                       # SessionDiagnosisEvidence, ShadowingCueProgress, QuizAttempt, QuizQuestion,
                       # QuizAnswer, Recording, MicrophonePreference, QuickPracticeSession,
                       # QuickPracticeItem, QuickPracticeDiagnosisEvidence
    services/         # CueIndex (active-cue/navigation rules), text_range (canonical selection
                       # offsets), session_rules (session/stage lifecycle + completion eligibility),
                       # quiz_rules (deterministic generation/scoring math), recording_rules
                       # (status transitions + managed-path construction), comparison_sequence
                       # (source-vs-take comparison state machine), date_range (timezone-safe
                       # date-range-preset resolution), needs_attention_rules (transparent,
                       # independently-named material-attention reasons), export_privacy (evidence-
                       # category/privacy-field defaults and redaction rules), quick_practice_rules
                       # (lifecycle/completion rules), quick_practice_recommendation (deterministic,
                       # reason-based cue recommendation) — all pure, no Qt
  infrastructure/
    db/               # SQLite connection, migrations, repository + learning_repository +
                       # session_repository + quiz_repository + recording_repository +
                       # history_repository + export_repository (narrow export-only queries) +
                       # quick_practice_repository (live-workflow CRUD + recommendation evidence
                       # queries) functions
    subtitles/        # SRT/WebVTT parsers, timecode and text normalization
    media/            # PlaybackController adapter around QtMultimedia playback; RecordingController
                       # adapter around QtMultimedia audio capture; file validation/fingerprinting
    appdata.py         # cross-platform app-data directory resolution (database, logs, recordings)
    export_io.py       # atomic file writes and filename sanitization for exports
    logging_setup.py   # rotating file + console logging
  ui/
    annotation_highlighting.py  # shared transcript-highlight painting (used by PlayerWindow and
                                 # GuidedSessionWindow — not duplicated)
    text_offset_conversion.py   # shared Qt UTF-16 <-> Python code-point offset conversion
    app.py            # application entry point
    widgets/          # RecordingPanel — the one recording UI, shared by GuidedSessionWindow
                       # Stage 4, ShadowingPracticeWindow, and QuickPracticeWindow (not duplicated);
                       # SimpleBarChart — a small dependency-free QPainter bar chart used by
                       # Learning History
    windows/          # MainWindow (material library), ImportDialog, PlayerWindow
                       # (with integrated transcript workspace), LabelColorDialog,
                       # GuidedSessionWindow (five-stage guided session), SessionHistoryDialog,
                       # QuizWindow, QuizHistoryDialog, QuizReviewDialog, ShadowingPracticeWindow,
                       # LearningHistoryWindow (global learning-evidence center), ExportDialog
                       # (scope/date/category/privacy selection, preview, save, copy),
                       # QuickPracticeStartDialog (Recommended/Selected Cues), QuickPracticeWindow
                       # (per-cue Listen&Recall/Diagnose/Replay&Shadow cycle + completion summary)
tests/
  unit/               # subtitle parsing, CueIndex, PlayerSession, text_range, session_rules,
                       # quiz_rules, recording_rules, comparison_sequence, date_range,
                       # needs_attention_rules, export_privacy, export_formatters, export_io,
                       # quick_practice_rules, quick_practice_recommendation
  integration/        # database/migrations, app startup (Post-M10 Phase B), import, library,
                       # player, player workspace, annotations, cue notes, saved language items,
                       # label preferences, practice_session_service, guided session window,
                       # quiz_service, recording_service, learning_history_service, learning
                       # history window, export_service, export dialog, quick_practice_service,
                       # quick practice window, quick practice start dialog, quick practice
                       # entry points, UI smoke
  fixtures/
docs/
packaging/            # Post-M10 Phase A packaging spike, plus a Phase B addition:
                       # listentrace.spec (PyInstaller), version_info.txt (Windows version
                       # resource), installer.iss (Inno Setup), app.manifest (longPathAware
                       # opt-in, Phase B), assets/ (placeholder icon + its generator script),
                       # README.md (decisions and build steps). Build output (packaging/build,
                       # packaging/dist) is gitignored.
```

## Current Limitations

- Learning History shows no effective study time, practice-minute totals, pronunciation score, waveform analysis, or combined ability/difficulty score — by design (see `docs/PRODUCT_SPEC.md`/`ARCHITECTURE.md`), not an oversight.
- Cumulative shadowing-practice-count totals shown under a date filter are an honest approximation (they include a row's full lifetime count whenever its *most recent* practice falls in range, since only a last-practiced timestamp is stored, not a per-event log) — exact only under All Time.
- Learning History itself has no deletion or editing of sessions/quiz attempts/session diagnosis evidence — it is a read-only navigation surface; the separate Export Learning Evidence flow is read-only in the same way (no history editing/deletion from export either).
- Export supports Markdown and JSON only — no PDF/HTML export, no database backup, no re-import of an edited export, and no bundled media/recordings (see `docs/PRODUCT_SPEC.md`).
- Export never performs a network request, automatic AI submission, or embedded evaluation — the external-evaluation instruction template is meant to be pasted into a tool of the user's own choosing.
- Recordings are fixed-format WAV only — no user-selectable formats, transcoding, trimming, editing, noise reduction, waveform display, automatic take ranking, or pronunciation/speech-recognition scoring (see `docs/PRODUCT_SPEC.md`).
- Quizzes are deterministic and locally generated only — no AI-generated questions, fuzzy/semantic answer grading, speech recognition, or adaptive difficulty (see `docs/PRODUCT_SPEC.md`).
- Only one primary subtitle track per material is managed through the UI, though the schema supports more.
- Plain-text (non-timed) transcript import is not supported.
- Player loop/replay timing uses a small internal tolerance (50ms) appropriate for QtMultimedia's position-update cadence; it is not frame-exact.
- Canonical text-selection offsets are Python code-point based; text requiring UTF-16 surrogate pairs (some emoji) is verified to round-trip correctly in both the standalone workspace and the guided session's Stage 3 diagnosis panel.
- Real-file, multi-codec playback, audio/video-device behavior, and microphone recording are only verified with a synthesized WAV, one locally generated H.264/MP4 clip, and (for recording) three real physical microphones, on Windows so far.
- After saving/updating/deleting an annotation, saved item, keyword capture, or session diagnosis, the corresponding list loses its selection (the form clears) — the user reselects a row to continue editing it.
- Text-only transcripts cannot provide reliable sentence seeking unless timing data is added.
- If a recording file cannot be deleted while removing its material (e.g. locked by another process at that exact moment), the material is not removed at all — it and the still-undeleted recording stay in place until the learner resolves the issue and retries.
- Speech recognition, pronunciation scoring, automatic translation, subtitle generation, dictionary lookups, and cloud synchronization are outside the first release.
- Quick Practice has no back navigation and no exact-step resume by design — closing mid-run either preserves completed-cue evidence as read-only "abandoned" history or, if nothing was completed yet, discards the run entirely; a completed or abandoned run can never resume as itself. Its completion summary intentionally does not report a "recordings created" count — Quick Practice recordings are ordinary standalone recordings with no schema link back to the run, so any such count could not be authoritative; recordings remain available through the Replay & Shadow step and through Learning History.
- Users are responsible for using media and transcript material they are legally permitted to use.
- The packaged Windows build (installer and portable zip, see `packaging/README.md`) is unsigned — Windows SmartScreen is expected to warn on first run — and has only been built/installed/uninstalled on the development machine so far, not on a genuinely clean machine with no preinstalled Python. Code signing, auto-update, and macOS/Linux packaging are not addressed.
- Windows long-path support (paths over roughly 260 characters) is only partially addressed: the packaged exe opts into `longPathAware`, but Windows also requires an admin-only, off-by-default machine-wide setting this app cannot enable itself — see `ARCHITECTURE.md`.

## Privacy

ListenTrace is local-first. User media, transcripts, annotations, recordings, and learning records should remain on the user's device unless the user explicitly exports them.

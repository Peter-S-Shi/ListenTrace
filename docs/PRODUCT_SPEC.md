# ListenTrace Product Specification

## Product Statement

ListenTrace is a desktop listening-practice workspace for learners who want to understand why natural foreign-language speech was not recognized.

It combines local media, a matching transcript, repeated listening, semantic error tagging, shadowing, quizzes, quick practice, and learning history.

## Primary User

A self-directed language learner who:

- has audio or video and a matching transcript;
- wants deliberate listening practice rather than passive consumption;
- may use English, French, or another target language;
- wants local ownership of media and learning data;
- is willing to edit personal notes and vocabulary records.

## Material Package

A full-capability material requires:

- a readable local audio or video file;
- a matching timed subtitle file.

SRT and WebVTT are initial targets.

A plain-text transcript may be accepted later with reduced functionality:

- full-text reading and notes;
- manual segmentation;
- no reliable automatic sentence seeking until timing is provided.

The interface must clearly explain any reduced mode.

## Material Library Management

- The application references the original media and subtitle files in place; it never copies, modifies, or deletes them.
- Importing the same media file twice (by path) is rejected. Importing different files with identical content prompts the user to confirm before continuing, rather than silently merging them.
- Archiving hides a material from the default library view without deleting any records; archived materials can be viewed and restored.
- Removing a material deletes only ListenTrace's own records (material, subtitle track, cues) for it, including permanently deleting every managed learner recording for that material. The confirmation dialog states explicitly that the original media and subtitle files are left untouched and that recordings will be permanently deleted. If any recording file cannot actually be deleted, the material is not removed at all — it stays, along with the still-undeleted recording, so the learner can resolve the issue and try again, rather than the record disappearing while an untracked file is left behind.
- If a previously imported media or subtitle file is later moved or deleted, the library marks it as missing rather than failing silently.

## Guided Intensive Listening

### Stage 1 — Global Comprehension

Play without transcript display. Ask short questions such as:

- Who is speaking?
- Where are they?
- What do they want to do?
- What is the result?

Responses are learning evidence, not formal grading.

### Stage 2 — Keyword Capture

Play again without revealing the transcript. Let the learner record:

- keywords;
- names and places;
- numbers;
- phrases;
- uncertain fragments.

Captured items remain visible while the session continues.

### Stage 3 — Transcript Comparison

Reveal the transcript and allow semantic annotation.

Initial categories:

| Key | Meaning |
|---|---|
| Keyword | Important to understanding the material |
| Known but Not Heard | Known in writing but not recognized in speech |
| Connected or Reduced Speech | Altered by linking, reduction, elision, or natural speech flow |
| Misheard | Perceived as a different word or sound |
| Unknown Word or Chunk | Unknown vocabulary or an unparsed expression |

For a mishearing, support:

- transcript text;
- what the learner thought they heard;
- an optional reason or note.

Colors are configurable presentation. Category meaning is stored independently.

### Stage 4 — Shadowing

Use cue-level playback:

1. play one cue;
2. pause;
3. let the learner repeat;
4. optionally record;
5. replay source or learner audio;
6. continue.

Automatic evaluation is not required. Milestone 5 tracks practiced/skipped status and a practice count per cue, driven only by explicit learner action (never inferred from playback alone). Recording and learner-audio playback are implemented in Milestone 7 — see "Confirmed Shadowing and Recording Behavior" below — and remain entirely optional: creating, comparing, or deleting a recording never changes a cue's practiced/skipped status.

### Stage 5 — Final Recall

Hide the transcript. Ask the learner to summarize the material in two or three target-language sentences.

### Confirmed Guided Session Behavior (Milestone 5)

The five-stage flow above is now a real, resumable guided session — built on the Milestone 3 player and Milestone 4 transcript-workspace tools rather than duplicating them.

- **One active intensive session per material.** Starting a new one while another is active offers Resume, Abandon and Start New, or Cancel — never a silent second session or a silent overwrite. Completed and abandoned sessions remain as permanent, read-only history, browsable per material.
- **Not a rigid exam.** Every stage can be explicitly skipped, with an optional (never required) reason. Back navigation revisits earlier stages without undoing their recorded status — reviewing a completed Stage 1 does not reopen it for editing.
- **The transcript-reveal boundary is a one-way door, confirmed up front.** Entering Stage 3 for the first time shows a clear warning that Stages 1 and 2 are about to become permanent, read-only evidence for this session, before it happens. After that point, their answers/captures remain visible for reference but cannot be edited in that session.
- **Stage 3 reuses the Milestone 4 diagnosis tools exactly** — same five semantic labels, same Misheard-requires-an-explanation rule, same Unicode-safe text selection. A diagnosis recorded during a session is repeatable: doing the same diagnosis again in a *later* session on the same material is allowed (each session keeps its own evidence), while an identical diagnosis cannot be recorded twice within the *same* session.
- **Shadowing tracks explicit action, not playback time.** A cue only becomes "practiced" when the learner presses Mark Practiced, and the count only increases on repeated explicit presses. Skip Remaining Cues resolves everything left over in one confirmed action.
- **A playback problem never blocks the session.** If the underlying media fails to play, only the playback-dependent buttons (play/pause, replay, loop) are disabled — every stage's text-based evidence, navigation, and session-completion path stay fully usable.
- **Nothing here modifies the source subtitle or media files** — session records are ListenTrace's own, deleted independently of (and never deleting) the imported files.

### Confirmed Shadowing and Recording Behavior (Milestone 7)

Shadowing recording works identically from two entry points — Guided Session Stage 4 and a standalone Shadowing Practice window opened directly from the material library — sharing one recording implementation rather than two.

- **Multiple takes, never overwritten.** A cue may keep any number of recordings. New takes never replace older ones; the learner reviews, plays, or deletes any take individually, deletes every take for one cue, or deletes every take for a whole material — each a separate, explicitly confirmed action.
- **Recording never touches Stage 4 completion.** Creating, comparing, or deleting a recording does not mark a cue practiced or skipped, and does not affect stage or session completion in any way — Mark Practiced/Skip Cue remain entirely independent actions the learner takes separately, exactly as in Milestone 5.
- **Session-linked vs. standalone recordings are distinguished, not merged.** A recording made during Guided Session Stage 4 links to that practice session; a recording made in standalone Shadowing Practice does not. Nothing about a practice session's status can silently delete a standalone-looking recording. A session-linked recording can only be started while that session is active and its current stage is actually Shadowing — recording is a Stage 4 action, not something that can happen against a completed, abandoned, or differently-staged session.
- **The microphone is never swapped silently.** Available input devices are listed for the learner to choose from; the last valid choice is remembered for next time. If that saved device is no longer connected, ListenTrace does not silently substitute a different one — the device choice is left blank, Start Recording stays unavailable, and the learner must explicitly pick a device before recording can begin.
- **Source and take audio are never mixed.** The learner can play the source cue and a take separately at any time, or run one combined action that plays the source cue, pauses briefly, then plays the take — the two streams never overlap. If the source cannot play, or playback ends before the comparison could finish, the comparison is cancelled automatically rather than leaving take playback or deletion stuck waiting on it.
- **A take is not usable until it is confirmed valid.** An empty, corrupted, or interrupted capture (a closed window, a lost device, an app crash) is never listed as a normal playable take; it is either cleaned up automatically or shown as failed, and the learner is told clearly rather than seeing a silent gap.
- **Only one recording can be in progress at a time**, across the whole application — starting a second one while the first is still capturing is refused, not silently allowed to collide.
- **Recordings are WAV, local-only, and retained until deleted.** Before the first recording attempt, the learner is told plainly that the microphone will be accessed, that audio stays on the device, that nothing is uploaded, and that recordings remain until they choose to delete them.
- **Nothing here modifies the source subtitle or media files**, and recording files are never placed beside them — they live under ListenTrace's own managed local storage, named with non-personal, collision-resistant filenames (no material title, transcript text, username, machine name, or source file path).

## Player Requirements

High-frequency controls should include:

- play and pause;
- seek;
- previous and next cue;
- replay cue;
- loop cue or selected range;
- transcript show/hide;
- keyboard shortcuts.

Timing failures must not silently attach notes to the wrong cue.

### Confirmed Player Behavior

- Opening the player (double-click or "Open Player") never autoplays; playback stays paused at 00:00 until the user presses play. Archived materials cannot be opened; missing media or subtitle files block entry with a clear message instead of a crash.
- The active cue is the one where `cue.start_ms <= current_time < cue.end_ms`. During a timing gap, no cue is active. If cues overlap, the cue with the latest start time among those covering the current instant is shown as active.
- Replay Cue is one-shot: seek to the selected/active cue's start, play, and pause automatically at that cue's end. Loop Cue and Loop Selection are continuous: they repeat until the user cancels (toggle, Escape, changing material, or closing the player). Only one loop can be active at a time.
- Hiding the transcript only hides the cue text; active-cue tracking, navigation, replay, and looping keep working underneath.
- A valid file extension is not treated as proof that the media is actually playable — an unplayable or corrupted file produces a controlled error and disables playback controls rather than crashing.

### Confirmed Transcript Workspace Behavior (Milestone 4)

The five semantic labels described in Stage 3 above, plus Cue Notes and Saved Language Items, are usable now as standalone learning-evidence tools inside the player — independent of any material/session. The guided five-stage flow that sequences them (Stages 1–5) is Milestone 5's job; Milestone 4 only builds the tools themselves.

- **Editing cue vs. active cue**: the cue you are annotating ("editing cue") is a separate, learner-controlled selection from whichever cue is currently playing ("active cue"). Playback moving into a new cue never changes what you're editing.
- **One Save, several labels**: selecting a whole cue or a text range within it and checking multiple labels creates all of them together in one action, sharing the same range. The same range may carry as many of the five labels as apply; different labels never merge into one record.
- **Misheard requires an explanation**: choosing "Misheard" requires filling in what the learner thought they heard before it can be saved. Other labels don't require this field.
- **Cue Note vs. Annotation Note**: a Cue Note is one free-form note for the whole cue. An Annotation Note is optional and belongs to one specific semantic annotation. They are never the same field.
- **Saved Language Items** (word / phrase / chunk / sentence pattern) capture the selected text plus its source material, source cue, and full cue context automatically; the context is editable afterward. Saving the identical item twice (same material, cue, range, type) is blocked. Saving the same text found elsewhere (a different cue or material) asks for confirmation rather than silently creating a duplicate or merging records.
- **Label colors are global and presentation-only**: changing a label's color affects every material and every existing annotation with that label, but never changes what the label means or which annotations exist.
- **Nothing here modifies the source subtitle or media files** — annotations, notes, and saved items are ListenTrace's own records, deleted independently of (and never deleting) the imported files.

## Vocabulary and Chunk Capture

Users may save selected text as:

- word;
- phrase;
- chunk;
- sentence pattern.

Each item may include:

- user-written meaning;
- note;
- source material;
- source cue;
- context.

This feature is not a built-in dictionary and does not claim authoritative definitions.

## Quizzes

Early quizzes are derived from the imported material.

Possible exercises:

- listen and fill a transcript blank;
- identify whether a keyword occurred;
- select the matching transcript for a cue;
- review previously missed or misheard cues;
- complete cue-level dictation.

Quiz behavior must be safe when there are too few cues or duplicate answer candidates.

### Confirmed Quiz Behavior (Milestone 6)

- A quiz belongs to one material and is either a **Material Quiz** (built from usable cues) or a **Review Quiz** (built from that material's own saved diagnosis history — `Annotation` rows labeled `misheard`/`known_not_heard`/`unknown_word_or_chunk`/`connected_reduced_speech`, prioritized in that order). A Review Quiz only ever produces Review-Missed-Cue questions; a Material Quiz freely mixes Cue Dictation/Fill-in-the-Blank, Keyword Recognition, and Audio-to-Transcript-Choice questions. When the same cue span was tagged with more than one diagnosis label, a Review Quiz asks about it only once, using the highest-priority label — the same tested spot is never repeated as two separate questions.
- Correctness is never revealed per-question. The learner answers every question, then submits the whole quiz once — an atomic, all-or-nothing scoring transaction — and only then sees one consolidated review: their answer, the correct answer, correct/incorrect, the source cue, the question type, and a short explanation of the deterministic scoring rule used.
- Dictation/fill-in/review-missed scoring ignores leading/trailing whitespace, collapses internal whitespace, ignores case, and ignores punctuation, but otherwise requires exact spelling — no fuzzy matching, semantic matching, or AI judgment of any kind.
- A requested question count is a target, not a promise: if a material cannot support that many meaningful questions, a smaller quiz is created and the learner is told why; if no meaningful question can be produced at all, quiz creation is refused outright. A cue or piece of diagnosis evidence is never reused within one quiz, and a weak or ambiguous question (too few valid transcript-choice distractors, a blank that would leave no context) is skipped rather than forced.
- Every question is generated deterministically from a stored seed, and its prompt/correct-answer/scoring snapshot is written once at generation time and never rewritten — a later edit or deletion of the live subtitle, annotation, or saved item it was drawn from has no effect on a quiz that already exists.
- A quiz attempt has three states — `active`, `completed`, `abandoned` — the same shape as a guided intensive-listening session. Closing an active quiz preserves it for resume without losing any saved answers. Completed and abandoned attempts are permanently read-only; answers can never be changed after submission. Unlike guided sessions, more than one quiz attempt may be active on the same material at once — Quiz History lists and reopens all of them, distinctly.
- The standalone player and the guided intensive session are unaffected by quizzes: a quiz is a separate entry point (Start Material Quiz / Start Review Quiz / Resume Quiz / Quiz History) reusing the same playback timing behavior, not a mode of either existing window.

## Learning History

Record only meaningful and reliable evidence:

- session completion;
- stage responses;
- annotation categories;
- quiz attempts and accuracy;
- repeated attempts;
- recording references.

Progress views should help answer:

- Which error types recur?
- Which materials remain difficult?
- How consistently is the learner practicing?

Progress views must not claim to answer whether recognition is "improving" —
recurring or receding diagnosis frequency is shown as evidence for the
learner to interpret, never converted into an improvement/regression verdict
or an ability score (see the Milestone 8 subsection below).

### Confirmed Learning History Behavior (Milestone 8)

- A global **Learning History** entry point opens without any material
  selected, covering every material by default; it can also be filtered or
  drilled down to one material, and existing material-level Session
  History/Quiz History shortcuts are unchanged.
- Six areas: **Overview** (fixed-calculation-rule metrics — materials
  practiced, completed/active/abandoned sessions, completed quizzes and their
  average accuracy, session-diagnosis-evidence count, cumulative shadowing
  practice actions, retained-recording count and total duration — no
  combined learning or difficulty score), **Activity** (a combined,
  type-filterable, material-filterable, date-filterable chronological feed
  across Session/Quiz/Diagnosis/Shadowing/Recording, each kept in its own
  distinct type), **Sessions** (Active/Completed/Abandoned kept visibly
  distinct; only Completed counts as completed practice; per-session
  stage-completion/skip/incomplete outcomes and skip notes are shown), a
  **Continue Learning** area (always shows every active session regardless of
  the current date filter, with Resume/Open Material/Abandon — an abandoned
  session is preserved as history but can never resume as itself; restarting
  practice creates a new session), **Diagnoses** (session-scoped historical
  `session_diagnosis_evidence` frequency/recurrence, kept in a visibly
  separate section from the material's *current*, editable `Annotation`
  state — the two counts are never added together), **Quizzes** (completed-
  attempt history with per-question-type breakdown when available, an
  accuracy-over-time trend chart for one selectable material-and-mode group
  at a time with its question count shown per attempt, plus a comparison
  view grouped strictly by material and quiz mode — the trend chart and the
  comparison view read the same grouped data, so attempts from different
  materials or modes are never combined into one series in either), and
  **Shadowing & Recordings** (cumulative explicit practice
  counts and high-frequency cues; retained — `ready` status only — recording
  totals and durations; deleted recordings are excluded from every total).
- A **Needs Attention** list gives each flagged material transparent,
  independently-named reasons (low recent quiz accuracy, repeated diagnosis
  evidence, multiple abandoned sessions, a frequently revisited material,
  sessions with many skipped stages, an active unfinished session) — never a
  single rank or difficulty index.
- Five date-range presets (Last 7/30/90 Days, Custom Range, All Time) filter
  consistently across the Overview, every list, and all charts, using the
  computer's local timezone to interpret and display boundaries; Continue
  Learning and Needs Attention are deliberately exceptions — they always
  reflect current state, not a historical window.
- No effective study time, practice-minute totals, or elapsed-wall-clock
  duration is ever shown or computed — only real, stored event timestamps.
  No pronunciation score, waveform analysis, or composite ability/difficulty
  score exists anywhere in Learning History.
- History is read-only: no deletion of sessions, quiz attempts, or session
  diagnosis evidence, and no bulk-delete or export from this surface
  (existing Milestone 7 recording deletion is unchanged). Every list
  supports navigating back into the live workflow (Open Material, Resume,
  View Session Detail, Open Quiz Review, Jump to Cue, Open Shadowing
  Practice) without ever auto-starting a new session.

## Export

Early external evaluation should use a structured local export rather than a mandatory embedded service.

Possible export content:

- material metadata;
- global-comprehension responses;
- captured keywords;
- transcript annotations;
- quiz results;
- final summary;
- practice statistics.

Requirements:

- preview before saving;
- exclude media by default;
- allow sensitive sections to be omitted;
- support Markdown and JSON;
- provide a reusable evaluation instruction template.

### Confirmed Export Behavior (Milestone 9)

- **Export Learning Evidence** opens from the global Learning History window (also preselecting whichever material is currently selected, when opened that way). Scope is **All Materials**, **One Material**, or **Selected Materials**; date range uses the same five presets and local-time boundary rules as Learning History (Last 7/30/90 Days, Custom Range, All Time), applied consistently to the preview, the Markdown, and the JSON.
- Eleven independently-selectable evidence categories (material metadata, session summaries, stage responses, session diagnosis history, current material annotations, quiz attempts, quiz questions and answers, shadowing evidence, retained recording metadata, learner notes and summaries, vocabulary and saved chunks) and six independently-selectable privacy fields (transcript excerpts, learner notes, mishearing text, vocabulary meanings, source labels, local file names). Turning a category off omits that whole section; turning a privacy field off redacts that one value in place (`[redacted]`) without removing the record it belongs to. Defaults favor summaries over the two most verbose raw-text categories (stage responses, quiz questions and answers) and include every privacy field except local file names.
- Absolute local paths, original media/subtitle/recording paths, and raw audio are never included in any export, under any selection — the exporter never reads a path field into the export tree in the first place, rather than filtering one out afterward.
- A preview (Markdown, JSON, and a separate reusable evaluation-instruction template) is generated on demand and shown before anything is saved or copied; the exact same generated text is what gets saved (atomically, with an explicit overwrite confirmation) or copied to the clipboard — never regenerated in between, so preview and saved output can never disagree. Changing scope, material selection, date range, evidence categories, or privacy fields after a preview exists immediately invalidates it (a visible stale notice replaces the old text, and every Save/Copy action is disabled) until Generate Preview is clicked again — the saved or copied output always corresponds to the selections currently shown.
- Quiz questions-and-answers export applies the same privacy redaction as every other category, across all four supported question types (dictation, keyword recognition, audio-to-transcript choice, review of missed/misheard cues): transcript-derived text is redacted under Transcript Excerpts, and a review question's historical mishearing text is redacted independently under Mishearing Text — position, question type, scoring structure, and choice indices are always preserved, and a question or attempt is never omitted for having a redacted field. Selecting quiz questions-and-answers without quiz attempts still produces the attempt (summary fields plus full question detail); selecting quiz attempts alone still produces summary-only output.
- The JSON export carries a stable `export_version` (currently `1`), tracked independently of the database schema version (unchanged at 8 — this milestone required no migration).
- Quiz question/answer exports read only each attempt's immutable generation-time snapshot, never live cue or annotation text, so an export remains accurate even after the source material is later edited. Incomplete (active or abandoned) quiz attempts are excluded from export the same way they are excluded from Learning History's own averages. Session diagnosis history and current material annotations are exported under separate keys and are never merged or added together.
- No network request occurs anywhere in the export flow; no account, API key, cloud upload, scheduled export, or embedded AI submission exists.

## Quick Practice

A short, low-friction, cue-based practice mode — a companion to Guided Intensive Listening, never a replacement for it. Typically 5-10 minutes; the application never displays or calculates effective study time.

- **Two ways to start**: **Recommended Practice** (3, 5, or 10 cues, default 5 — a deterministic list built from existing local evidence: recent Misheard/Known but Not Heard/Connected or Reduced Speech diagnosis, incorrect quiz evidence, recurring diagnosis history, and little-or-no shadowing practice as an amplifying signal only, never a qualifying one on its own; every recommended cue shows its own transparent reason(s), never a hidden score; when too little evidence exists, the list safely falls back to material order with no invented reasons) or **Selected Cues** (one cue, a continuous range, or an explicit multi-cue selection — order preserved exactly as picked).
- **Entry points**: Material Library / Learning History (**Quick Practice**, opens the start dialog), the Player (**Quick Practice This Cue** for the current editing cue, **Quick Practice Selected Cues** for a selected range — both start immediately, no dialog needed since the cue selection is already unambiguous).
- **Per-cue micro-cycle**, forward-only (no back navigation, no exact-step resume):
  1. **Listen** — transcript hidden, replay freely.
  2. **Recall** — choose Understood / Partly Understood / Missed (required to continue); an optional short typed guess at what was heard.
  3. **Reveal & Diagnose** — the transcript is revealed as the natural next step after Recall (never automatically during Listen); add one or more of the same five semantic diagnosis labels used everywhere else in the app, or add none and continue — diagnosis is always optional and reuses the exact same validation, annotation reuse, and Misheard-requires-an-explanation rule as the standalone workspace and Guided Session Stage 3.
  4. **Replay & Shadow** — replay the source, optionally mark the cue explicitly shadowed, optionally record a take through the same shared recording widget used everywhere else — recording is always optional and never blocks moving on.
- **Progressive, forward-only persistence.** Each cue's result is saved as it happens; there is no "current step" to resume into after closing the app. Closing mid-run preserves every already-completed cue's evidence and marks the run **abandoned** (with a confirmation, since real evidence would otherwise be lost); closing before any cue is completed **discards the run entirely** so it never appears as misleading history — no confirmation is needed, since nothing was recorded yet. A completed or abandoned run is permanently read-only and can never resume as itself; a later Quick Practice always starts a new run.
- **A concise, read-only completion summary**: cues completed, Understood/Partly Understood/Missed counts, diagnoses created, explicit shadowing actions, recordings created during the run, and which cues are worth revisiting (a Missed result or at least one diagnosis) — never an effective-time, pronunciation, ability, difficulty, or improvement score.
- **Evidence stays distinct from Intensive Practice, Quiz Attempts, and plain player activity.** A Quick Practice run is never counted as a completed Intensive Session or a completed quiz, and diagnosis recorded through it carries its own explicit provenance even though it reuses the same underlying `Annotation` records everyone else edits.
- **Learning History** shows a `Quick Practices Completed` overview count, `quick_practice` Activity feed entries, and a dedicated Quick Practice tab with each run's status (Active/Completed/Abandoned kept visibly distinct) and its own per-cue results.
- **Needs Attention** may flag a material with `Missed repeatedly in Quick Practice` once at least two completed items have a Missed recall result, across any number of runs — a single isolated Missed result never raises this on its own.
- **Export** offers an independent `quick_practice_evidence` category (on by default, alongside the other summary-level categories — Quick Practice evidence is closer in verbosity to a summary than to raw transcript text) covering scope, source type, cue order, recall result, heard fragment, related diagnosis evidence, explicit shadowing evidence, and timestamps, with the same privacy controls as everywhere else (transcript excerpts, mishearing text, learner notes) — never recording metadata or any path.
- No AI recommendation, pronunciation scoring, adaptive difficulty, countdown, streaks, points, or other game mechanics exist anywhere in Quick Practice.

## Release Scope

- Quick Practice (Milestone 10) is implemented; the project is now in feature freeze for the first release. No further user-feature milestones are planned before v1.0.
- Milestone 11's optional assisted features (speech recognition, pronunciation feedback, translation assistance, subtitle generation, question generation) are outside first-release scope and remain deferred until after a packaged, tested, successfully used v1.0.
- Windows-first packaging and release validation (packaging spike, release hardening, clean-machine testing, release-candidate validation) follow feature completion — see `ROADMAP.md`'s Post-M10 sequence, which is the project's next engineering objective.

## Copyright and Source Policy

ListenTrace does not download protected streaming content or circumvent access controls.

Testing and distributed examples should use:

- public-domain material;
- permissively licensed material;
- original project-created material;
- content explicitly authorized for reuse.

Users are responsible for media and transcript rights.

## Accessibility

The design should eventually support:

- keyboard operation;
- readable focus states;
- category labels that do not depend on color alone;
- adjustable transcript size;
- captions and text equivalents for interface sounds.

## Explicit Non-Goals for Early Development

- streaming-site downloading;
- automatic translation;
- automatic subtitle generation;
- automatic question generation;
- pronunciation scoring;
- word-level forced alignment;
- cloud accounts;
- full dictionary replacement;
- multi-user collaboration.

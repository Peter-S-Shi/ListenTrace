# ListenTrace Product Specification

## Product Statement

ListenTrace is a desktop listening-practice workspace for learners who want to understand why natural foreign-language speech was not recognized.

It combines local media, a matching transcript, repeated listening, semantic error tagging, shadowing, quizzes, and learning history.

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
- optional practice duration;
- recording references.

Progress views should help answer:

- Which error types recur?
- Which materials remain difficult?
- Is recognition improving on repeated practice?
- How consistently is the learner practicing?

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

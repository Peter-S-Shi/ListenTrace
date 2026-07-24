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
- Removing a material deletes only ListenTrace's own records (material, subtitle track, cues) for it. The confirmation dialog states explicitly that the original media and subtitle files are left untouched.
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

Automatic evaluation is not required initially. Recording and learner-audio playback are Milestone 7's job — Milestone 5 tracks practiced/skipped status and a practice count per cue, driven only by explicit learner action (never inferred from playback alone), with no microphone access at all.

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

# ListenTrace Roadmap

## Product Goal

ListenTrace is a local-first desktop learning tool that helps users diagnose and improve foreign-language listening. Its central value is not media playback alone, but a repeatable workflow that turns “I did not understand this” into structured evidence:

- what the learner understood globally;
- which words or chunks were captured;
- which transcript segments were missed;
- why they were missed;
- whether the same difficulty improves after practice.

## Core User Workflow

1. Import a local audio or video file.
2. Attach a matching subtitle or transcript.
3. Validate that the material package is usable.
4. Complete a guided listening session:
   - global comprehension;
   - keyword capture;
   - transcript comparison and diagnosis;
   - sentence-level shadowing;
   - transcript-free summary.
5. Save annotations, vocabulary items, quiz results, and session progress.
6. Revisit difficult material and compare performance over time.
7. Export structured learning evidence when external evaluation is desired.

## Architectural Progression

The system should evolve in layers:

1. **Foundation:** desktop shell, domain boundaries, local persistence, test harness, media/subtitle technical spike.
2. **Material handling:** reliable import and validation.
3. **Synchronized playback:** media time, subtitle cues, sentence navigation, looping.
4. **Learning evidence:** annotations, notes, error categories, vocabulary/chunk capture.
5. **Guided training:** an explicit multi-stage session state.
6. **Practice extensions:** quizzes, shadowing, recording, summaries.
7. **Analytics and portability:** progress views and structured exports.
8. **Optional intelligence:** external services only after the local workflow is stable.

The domain and persistence layers must remain independent from the desktop widget layer so the interface can evolve without rewriting learning logic.

---

# Milestone 1 — Application Foundation

## Goal

Create a runnable, testable desktop project foundation and prove the highest-risk technical assumptions before building product workflows.

## Main Scope

- Establish the Python project and package layout.
- Create a minimal PySide6 desktop window.
- Establish configuration, logging, and local application-data paths.
- Create SQLite initialization and migration foundations.
- Define initial domain entities for material packages and subtitle cues.
- Add a small SRT/WebVTT parser boundary.
- Add a media inspection and playback feasibility spike.
- Establish automated tests for non-UI logic.
- Document verified setup, run, and test commands.

## Boundary

This milestone does not implement the complete library, learning workflow, annotations, quiz system, recording workflow, or polished interface.

## Exit Condition

A clean clone can be set up using documented commands; the minimal application starts; the database initializes; a sample subtitle can be parsed; the selected media approach is either verified or its blocker is documented; tests pass.

---

# Milestone 2 — Material Library and Import Validation

## Goal

Let users create and manage valid listening-material packages.

## Main Scope

- Import local audio or video.
- Attach SRT or WebVTT subtitles.
- Optionally accept plain-text transcripts with reduced capabilities.
- Validate missing, unreadable, or incompatible files.
- Store metadata without copying large media by default.
- List, open, rename, archive, and remove material records.
- Clearly distinguish removing a record from deleting a source file.

## Boundary

No complete guided practice flow and no automatic subtitle generation.

## Dependencies

Requires the application shell, persistence, media inspection, and subtitle boundaries from Milestone 1.

---

# Milestone 3 — Synchronized Player

## Goal

Provide reliable playback synchronized with timed subtitle cues.

## Main Scope

- Play, pause, seek, and change position.
- Display the active subtitle cue.
- Navigate to previous and next cues.
- Replay a cue.
- Loop one cue or a selected cue range.
- Toggle transcript visibility.
- Support keyboard shortcuts for high-frequency controls.
- Handle timing gaps and malformed cues safely.

## Boundary

No pronunciation scoring and no automatic word-level alignment.

## Dependencies

Requires validated material packages from Milestone 2.

---

# Milestone 4 — Transcript Workspace and Listening Diagnosis

## Goal

Turn transcript comparison into structured learning evidence.

## Main Scope

- Select text or cues and assign semantic labels.
- Initial labels:
  - Keyword
  - Known but Not Heard
  - Connected or Reduced Speech
  - Misheard
  - Unknown Word or Chunk
- Allow editable display colors without storing meaning as color alone.
- Provide a mishearing record with:
  - transcript text;
  - what the learner thought they heard;
  - optional explanation.
- Save cue notes and session keyword captures.
- Save vocabulary and chunks with source-material context.

## Boundary

This is not a full dictionary. Users own and edit saved meanings and notes.

## Dependencies

Requires stable cues and navigation from Milestone 3.

---

# Milestone 5 — Guided Intensive Listening

## Goal

Join playback, notes, annotations, and recall into one coherent learning session.

## Main Scope

Implement a resumable session with these stages:

1. Global comprehension questions
2. Keyword and fragment capture
3. Transcript comparison and error tagging
4. Sentence-level shadowing
5. Transcript-free target-language summary

Also include:

- clear stage progress;
- save and resume;
- completion status;
- validation of required responses where appropriate;
- preservation of earlier-stage answers for later reflection.

## Boundary

Do not let the workflow become a rigid exam. Users should be able to skip optional actions while the session still records what occurred.

## Dependencies

Requires the player and transcript workspace.

---

# Milestone 6 — Quizzes and Recall Practice

## Goal

Create material-based listening and transcript-recall exercises using existing local content.

## Main Scope

- Cue-level dictation or fill-in-the-blank practice.
- Keyword recognition.
- Audio-to-transcript choice questions.
- Review of previously misheard or missed cues.
- Quiz sessions, item results, and summary.
- Safe handling when a material lacks enough usable cues.

## Boundary

No generative question service is required. Early quizzes should be deterministic and derived from local material.

## Dependencies

Requires structured cues, annotations, and session evidence.

---

# Milestone 7 — Shadowing and Local Recording

## Goal

Support deliberate comparison between the source audio and the learner's own speech.

## Main Scope

- Cue-by-cue shadowing mode.
- Optional microphone recording.
- Local playback of learner recordings.
- Compare source and learner audio manually.
- Recording retention and deletion controls.
- Clear microphone permission and privacy messages.

## Boundary

No automatic pronunciation score or speech-to-text requirement.

## Dependencies

Requires sentence navigation and stable local storage boundaries.

---

# Milestone 8 — Progress and Learning History

## Goal

Show whether the learner is practicing consistently and whether recurring listening problems are changing.

## Main Scope

- Material and session completion history.
- Practice time where reliably measurable.
- Annotation-category trends.
- Quiz performance trends.
- Repeat-attempt comparisons.
- Difficult materials and frequently recurring error categories.
- Filters by language, date range, and material.

## Boundary

Avoid false precision. Only report metrics supported by stored evidence.

## Dependencies

Requires stable event and session data from earlier milestones.

---

# Milestone 9 — Structured Export and External Evaluation

## Goal

Allow users to export their learning evidence without requiring an embedded online service.

## Main Scope

- Markdown and JSON export.
- Include material metadata, stage responses, annotations, quiz results, and summaries.
- Generate a reusable evaluation instruction template.
- Exclude source media by default.
- Preview export content before saving.
- Make sensitive fields selectable.

## Boundary

No account, cloud upload, or mandatory external integration.

## Dependencies

Requires stable data contracts and learning records.

---

# Milestone 10 — Quick Practice Mode

## Goal

Provide a short, low-friction, cue-based practice mode as a companion to the full five-stage Intensive Practice session, and the final planned user-feature milestone for the first release.

## Locked Definition

- Short, low-friction, cue-based practice.
- Normally about 5–10 minutes, with no time scoring.
- 3, 5, or 10 cues per session, defaulting to 5.
- Two entry points: Recommended Practice and Selected Cues.
- Per-cue flow: Listen → Recall → Reveal/Diagnose → Replay/Shadow.
- Progressive evidence saving as the session proceeds.
- No exact-step resume if a session is interrupted.
- Produces its own distinct Quick Practice history and export evidence, kept separate from Intensive Practice and Quiz evidence.
- Out of scope: AI assistance, pronunciation scoring, adaptive difficulty, a countdown timer, or game mechanics.

## Boundary

Quick Practice is a companion workflow, not a replacement for Milestone 5's five-stage Intensive Practice session; it is not required to reproduce every stage or produce identical evidence.

## Dependencies

Requires stable cues, annotations, quiz, and shadowing/recording behavior from earlier milestones.

After Milestone 10 is accepted, the project enters feature freeze for the first release (see "Post-M10 — Release Engineering and v1.0 Delivery" below).

---

# Milestone 11 — Optional Assisted Features (Deferred Beyond v1.0)

## Status

Deferred beyond v1.0. There is no current implementation plan, and it is not part of the first release. It may be reconsidered only after the local-first desktop product is packaged, tested, and used successfully — it is not the next active engineering objective.

## Possible Scope

- Speech recognition
- Pronunciation feedback
- Translation assistance
- Subtitle generation
- Question generation
- Pluggable external-service providers

## Boundary

- Every future assisted feature must remain optional.
- Any data leaving the device must be disclosed.
- The core practice workflow must never depend on it.
- Credentials must not be stored in source control.

---

# Post-M10 — Release Engineering and v1.0 Delivery

Once Milestone 10 is accepted, remaining work before v1.0 is release engineering rather than new user features, organized into four phases. Phase A's packaging decisions are locked (see below); a v1.0 release date is still not chosen.

## Phase A — Packaging Spike (Completed)

Decided and validated:

- Windows-first release target;
- packaging technology: PyInstaller, one onedir build;
- that same onedir build serves both distribution forms — an Inno Setup installer and a portable ZIP, not two separate pipelines;
- per-user install only (no admin rights required to install) — machine-wide install is out of scope for v1.0, a release-scope decision, not just a default;
- application icon and version metadata: a placeholder icon (regenerable, not a final design) and version/publisher metadata that names only "ListenTrace" — no separate individual or company name;
- application-data and recording locations: unchanged — the existing `%APPDATA%\ListenTrace` location (database, recordings, logs) is preserved exactly as before packaging;
- preservation of SQLite data during upgrades: the install/upgrade path never touches `%APPDATA%\ListenTrace`;
- uninstall behavior: uninstalling removes only the installed program files — the learner's local data (database, recordings, logs) is never deleted by install, upgrade, or uninstall.

See `packaging/README.md` for the full build recipe and `ARCHITECTURE.md`'s "Resolved in Post-M10 Phase A" section for the validation evidence (a real install → launch → uninstall cycle, and a portable-build launch from a different path). Code signing, auto-update, macOS/Linux packaging, and CI-driven builds remain unaddressed.

## Phase B — Release Hardening

Corrective work for:

- startup and shutdown failures;
- missing or moved media;
- Unicode and non-English paths;
- long Windows paths;
- missing microphone;
- codec and playback failures;
- interrupted recording;
- migration failure;
- export failure;
- large-history behavior;
- operation without a developer Python environment.

## Phase C — Clean-Machine Testing

Testing on a clean Windows environment covering:

- no preinstalled Python;
- fresh user account;
- non-English user and path names;
- install, launch, upgrade, and uninstall;
- data preservation;
- legacy database upgrade;
- playback and microphone;
- Intensive Practice;
- Quiz;
- Learning History;
- Export;
- Quick Practice.

## Phase D — v1.0 Release Candidate

Completion of:

- versioning;
- About page;
- privacy and local-data explanation;
- installation and usage documentation;
- known limitations;
- release notes;
- final privacy audit;
- complete regression run;
- installable release candidate;
- small real-user acceptance test;
- v1.0 release decision.

---

# Cross-Cutting Requirements

## Testing

- Domain and persistence behavior should be covered by automated tests.
- Subtitle parsing and timing edge cases require fixtures.
- Database changes require migrations and migration tests.
- High-risk playback behavior needs a documented manual test matrix.
- Each milestone must add or update relevant tests.

## Data and Privacy

- Media, transcripts, annotations, recordings, and study records are local user data.
- The application should not silently upload them.
- Deleting an application record must not delete original source media unless explicitly requested and confirmed.
- Exports must be previewable and user-controlled.
- Logs must avoid transcript content and personal file paths unless necessary for troubleshooting.

## Maintainability

- UI code must not own database queries or core learning rules.
- External tools and libraries should be accessed through narrow adapters.
- Important product decisions should be documented.
- Public project status must match implemented behavior.
- Each milestone should leave setup, tests, and next engineering work understandable from the repository.

## Desktop Delivery

- Early development prioritizes a reliable local development run.
- Packaging should be investigated after core playback and persistence are stable.
- Later milestones should add platform-specific build and release checks.

# Non-Goals for the First Release

- Streaming-site downloading
- Circumventing access controls or copyright protections
- Built-in commercial media catalog
- Full dictionary replacement
- Mandatory account or cloud synchronization
- Automatic pronunciation scoring
- Automatic translation or subtitle generation
- Word-level forced alignment
- Mobile application
- Multi-user collaboration

# Confirmed Decisions

- Product name: ListenTrace
- Local-first desktop product
- User supplies media and matching transcript or subtitles
- Timed subtitles provide the full experience
- Listening failure categories are semantic labels, not colors
- User owns saved word and chunk content
- Structured export precedes embedded online evaluation
- Original user media should remain outside the application database

# Decisions Still Open

- Final media playback backend
- Minimum supported desktop operating systems
- Whether plain-text transcripts are included in the first usable release
- Whether imported media is referenced in place or optionally copied
- Audio recording format and retention defaults
- Initial accessibility and localization targets
- Update strategy (auto-update) — packaging itself was decided and validated in Post-M10 Phase A; see `packaging/README.md`

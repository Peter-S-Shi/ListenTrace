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

After Milestone 10 is accepted, the project enters Functional Feature Freeze for the first release.

## Functional Feature Freeze

Functional Feature Freeze means:

- no new learning workflow;
- no new domain capability;
- no new analytics concept;
- no new user-data semantics;
- no AI/cloud feature;
- no expansion of first-release product scope.

It does **not** mean the UI can no longer be redesigned — presentation work continues in Milestone 11, below.

---

# Milestone 11 — UI/UX Presentation Refresh

## Goal

Transform the functionally complete ListenTrace into a visually coherent, low-cognitive-load desktop product without changing its learning logic, evidence semantics, or data model.

M11 is a first-release milestone, but it is **not** a new functional-feature milestone and does not reopen Functional Feature Freeze: Milestone 10 ended functional feature development; Milestone 11 is presentation-only release work that happens after it.

## Main Scope

M11 may redesign presentation-level concerns: overall visual language, layout hierarchy, application navigation, spacing and density, typography hierarchy, color system, button hierarchy and states, forms and controls, cards/panels, dialogs, empty states, icons, status presentation, player presentation, transcript workspace presentation, Intensive Practice presentation, Quiz presentation, Learning History presentation, Export presentation, Quick Practice presentation, and visual consistency across windows.

The existing Daily Canvas project may be used as a visual/product-design reference where useful (hierarchy, restrained color usage, whitespace, card grouping, visual rhythm, a friendly but focused learning/productivity aesthetic) — its web technology stack is not relevant and must not be copied merely for visual similarity. ListenTrace remains Python, PySide6, a Qt desktop application. The preferred v1.0 direction is to improve the existing Qt Widgets UI through reusable presentation components, centralized QSS/theme rules, consistent design tokens, icons/assets, and layout refinement, rather than a React or full-QML rewrite. A full UI-framework rewrite is outside M11 scope unless a separately approved architectural decision is made later. M11's detailed implementation plan will be defined separately; this roadmap entry only fixes its scope and boundaries.

## Boundary

M11 must preserve Functional Feature Freeze. It must not introduce new learning modes, quiz types, diagnosis semantics, analytics, recommendation logic, export semantics, or recording behavior; it must not introduce speech recognition, pronunciation scoring, translation, subtitle generation, question generation, AI services, cloud accounts, or synchronization; it must not introduce new domain entities created merely for presentation, or unnecessary schema migrations. M11 should normally require no database schema change. Existing behavior from Milestones 1-10 remains authoritative — presentation refactoring must not silently alter session lifecycle, quiz scoring, recording safety, recommendation logic, privacy rules, Learning History calculations, export contracts, Quick Practice evidence, or data ownership/deletion behavior.

## Dependencies

Requires the functionally complete, feature-frozen application from Milestones 1-10. Phase C2 — Clean-Machine Acceptance (see "v1.0 Release Engineering" below) is scheduled after M11 so the actual release UI is what gets validated, not the presentation layer it replaces.

---

# Deferred Beyond v1.0 — Optional Assisted Features

Not a numbered milestone. There is no current implementation plan, and it is not part of the first release and not the next milestone after M11. It may be reconsidered only after the local-first v1.0 product is released and evaluated.

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

# v1.0 Release Engineering

Release engineering began once Milestone 10 was accepted and functional feature development entered freeze, organized into phases: A (packaging spike), B (release hardening), C1 (release preflight), C2 (clean-machine acceptance), D (release candidate). This section was previously named "Post-M10 — Release Engineering and v1.0 Delivery"; it is renamed here only because Milestone 11 now exists after M10, which made a "Post-M10" heading historically awkward — the Phase A/B/C history and decisions below are preserved, not rewritten. Phase A's packaging decisions are locked and Phase B's hardening pass is complete (see below). The former single Phase C is now represented as two distinct stages: Phase C1 — Release Preflight (completed on the development machine) and Phase C2 — Clean-Machine Acceptance (pending, scheduled after Milestone 11 so the actual release UI is validated rather than the presentation layer it replaces). A v1.0 release date is still not chosen.

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

## Phase B — Release Hardening (Completed)

Corrective work for:

- startup and shutdown failures: startup fixed — `QApplication` is now constructed before anything else that could fail, so a startup failure can always show a friendly dialog instead of the process silently terminating; unhandled exceptions during normal use are now logged via a global crash-logging hook. Shutdown audited directly (closeout pass) and found already correct: no explicit database-connection close exists anywhere, which is safe because every write already commits synchronously in SQLite's default (non-WAL) journal mode; a normal window close really aborts an in-progress recording through the real service path, not just in a mocked test; re-opening the database afterward reads back exactly what was left, with nothing dangling for startup crash-recovery to find;
- missing or moved media: verified already solid — every material-opening entry point already pre-flight-checks the media and subtitle paths with a friendly error;
- Unicode and non-English paths: verified already solid — a real end-to-end import/load test with CJK characters, spaces, and an emoji in file/folder names succeeded with no code change needed;
- long Windows paths: partially addressed — `packaging/app.manifest` opts the exe into `longPathAware`, but this alone is not sufficient (Windows also requires an admin-only, off-by-default machine-wide registry policy this app cannot enable itself); documented as a known, accepted limitation, not claimed as fully solved;
- missing microphone: verified already solid (Milestone 7's `resolve_preferred_device`);
- codec and playback failures: verified already solid — every window owning a `PlaybackController` already handles `playback_error` consistently;
- interrupted recording: verified already solid (Milestone 7's crash recovery);
- migration failure: fixed — a real bug was found and reproduced (`migrate()`'s use of `executescript` could leave a failed migration half-applied while `PRAGMA user_version` stayed unbumped, permanently stuck); migrations now run as one explicit transaction per migration, rolling back completely on any failure;
- export failure: verified already solid (`export_dialog.py`'s existing atomic-write error handling);
- large-history behavior: fixed — schema version 10 adds nine indexes on foreign-key columns that were previously unindexed full-table-scan targets in the Learning History/Quick-Practice-recommendation/export query layer;
- operation without a developer Python environment: structurally addressed by construction (the PyInstaller build embeds the Python runtime and every dependency, with no intended dependency on a separately installed interpreter), but **not yet empirically verified on a machine without Python installed** — every Phase A/B validation so far ran on the development machine, which already has Python installed; that empirical verification belongs to Phase C's "no preinstalled Python" clean-machine criterion.

An acceptance closeout pass corrected the wording above (the no-developer-Python-environment item had originally, and incorrectly, been described as already verified) and completed the shutdown half of the startup/shutdown audit that the original pass had left unaudited.

See `ARCHITECTURE.md`'s "Resolved in Post-M10 Phase B" section and `packaging/README.md` for full detail and validation evidence.

## Phase C1 — Release Preflight (Completed)

Represents all validation already performed on the development machine, formerly recorded as the single Phase C. Covers:

- install, launch, upgrade, and uninstall: a fresh silent install, a reinstall over the same install (upgrade-in-place via the same AppId), a silent uninstall, each launch in between, all completed cleanly;
- data preservation: a real material row survived install → data creation → reinstall → uninstall intact;
- legacy database upgrade: a real pre-Milestone-10 (schema version 8) database with real material/session/recording rows, opened directly by the compiled exe, upgraded cleanly to version 10 with all data intact;
- WAV playback through the packaged Qt Multimedia (FFmpeg) plugin: loads correctly, correct duration, no errors;
- a real physical microphone recording, producing a valid WAV file with no errors;
- Unicode executable/path verification: the packaged exe launched successfully from a Chinese-character install path;
- core application-service walkthroughs (Intensive Practice, Quiz, a standalone recording, Quick Practice), Learning History aggregation, and Markdown export generation, all through the real application services, feeding one database;
- the latest packaged application opening the resulting database without error.

**C1 does not prove**: clean Windows behavior, no-Python target-machine behavior, fresh Windows-user behavior, a genuinely non-development environment, broad real-world MP4/H.264 compatibility, or native GUI interaction coverage on another machine — every check above ran on this project's own development machine, which already has Python, Git, an IDE, FFmpeg, and other developer tooling installed. C1 is release preflight, not Clean-Machine Testing; that is Phase C2's job, below.

## Phase C2 — Clean-Machine Acceptance (Pending)

The remaining final environment-validation gate, occurring **after Milestone 11 — UI/UX Presentation Refresh** so the actual release UI is tested rather than the presentation layer it replaces.

Target baseline: Windows 11 x64, Home or Pro, standard non-N edition, normal Windows system updates, no Python installation, no Git, no IDE, no PyInstaller, no Inno Setup, no project source tree, no developer virtual environment, and no manually installed FFmpeg or codec pack required for ListenTrace.

C2 validates the actual packaged release candidate. At minimum:

- **Runtime foundation**: install, launch, application-data creation, restart, uninstall, data preservation.
- **Multimedia**: real WAV playback, real MP4/H.264 playback, audio output, microphone detection, real recording, playback of a retained recording.
- **Data**: fresh schema creation, legacy database upgrade, persistence after restart, upgrade-install preservation, uninstall preservation.
- **Core workflows**: Material import, Player, Transcript Workspace, Intensive Practice, Quiz, Shadowing/Recording, Learning History, Export, Quick Practice.

Phase C2 is a release gate: it must not be marked completed until a genuinely appropriate clean environment has actually been used.

## Phase D — v1.0 Release Candidate (Pending)

Completion of:

- versioning;
- About surface;
- privacy and local-data explanation;
- installation and usage documentation;
- known limitations;
- release notes;
- final icon and release metadata;
- final privacy audit;
- complete regression suite;
- RC installer and RC zip;
- release checklist;
- small real-user acceptance test where practical;
- v1.0 release decision.

Some Phase D planning/preparation may occur earlier if useful, but Phase D must not be marked completed, v1.0 must not be tagged or released, and final release readiness must not be claimed until Phase C2 passes.

## Canonical v1.0 Sequence

```
Milestones 1-10 — Core Functional Development
  -> Functional Feature Freeze
  -> Phase A — Packaging Spike (Completed)
  -> Phase B — Release Hardening (Completed)
  -> Phase C1 — Release Preflight (Completed)
  -> Milestone 11 — UI/UX Presentation Refresh (Next Product Milestone)
  -> Phase C2 — Clean-Machine Acceptance (Pending)
  -> Phase D — v1.0 Release Candidate (Pending)
  -> v1.0 Release
```

The deferred assisted-feature ideas ("Deferred Beyond v1.0 — Optional Assisted Features", above) sit outside this primary sequence and carry no milestone number.

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

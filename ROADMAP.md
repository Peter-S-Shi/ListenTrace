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

---

# Functional Feature Complete Gate

ListenTrace became functionally feature-complete for v1.0 when the planned local-first learning workflows from Milestones 1-10 were implemented and accepted. This gate marks the end of general feature expansion, not the end of engineering work: the project is now in the convergence portion of the v1.0 lifecycle (presentation refresh, product-wide hardening, environment acceptance, release candidate). **Feature Complete is not Release Ready** — the two are deliberately distinct milestones on this roadmap, not synonyms.

## Functional Feature Freeze

Functional Feature Freeze is active. During freeze:

- critical defects may be fixed;
- data-integrity, privacy, security, and core-workflow defects **must** be fixed;
- severe UX defects that prevent reliable use **must** be fixed;
- presentation redesign is allowed, through Milestone 11;
- nonessential new capabilities move to Deferred Features or a later version, not into the frozen v1.0 scope;
- scope expansion requires an explicit decision and a roadmap update — it is never a silent side effect of other work.

It does **not** mean the UI can no longer be redesigned — presentation work continues in Milestone 11, below.

---

# Milestone 11 — UI/UX Presentation Refresh (Completed)

## Goal

Transform the functionally complete ListenTrace into a visually coherent, low-cognitive-load desktop product without changing its learning logic, evidence semantics, or data model.

M11 is a first-release milestone, but it is **not** a new functional-feature milestone and does not reopen Functional Feature Freeze: Milestone 10 ended functional feature development; Milestone 11 is presentation-only release work that happens after it.

## Main Scope

M11 may redesign presentation-level concerns: overall visual language, layout hierarchy, application navigation, spacing and density, typography hierarchy, color system, button hierarchy and states, forms and controls, cards/panels, dialogs, empty states, icons, status presentation, player presentation, transcript workspace presentation, Intensive Practice presentation, Quiz presentation, Learning History presentation, Export presentation, Quick Practice presentation, and visual consistency across windows.

The existing Daily Canvas project may be used as a visual/product-design reference where useful (hierarchy, restrained color usage, whitespace, card grouping, visual rhythm, a friendly but focused learning/productivity aesthetic) — its web technology stack is not relevant and must not be copied merely for visual similarity. ListenTrace remains Python, PySide6, a Qt desktop application. The preferred v1.0 direction is to improve the existing Qt Widgets UI through reusable presentation components, centralized QSS/theme rules, consistent design tokens, icons/assets, and layout refinement, rather than a React or full-QML rewrite. A full UI-framework rewrite is outside M11 scope unless a separately approved architectural decision is made later. M11's detailed implementation plan will be defined separately; this roadmap entry only fixes its scope and boundaries.

## Boundary

M11 must preserve Functional Feature Freeze. It must not introduce new learning modes, quiz types, diagnosis semantics, analytics, recommendation logic, export semantics, or recording behavior; it must not introduce speech recognition, pronunciation scoring, translation, subtitle generation, question generation, AI services, cloud accounts, or synchronization; it must not introduce new domain entities created merely for presentation, or unnecessary schema migrations. M11 should normally require no database schema change. Existing behavior from Milestones 1-10 remains authoritative — presentation refactoring must not silently alter session lifecycle, quiz scoring, recording safety, recommendation logic, privacy rules, Learning History calculations, export contracts, Quick Practice evidence, or data ownership/deletion behavior.

## Dependencies

Requires the functionally complete, feature-frozen application from Milestones 1-10. Milestone 12 (Pre-UI Product Hardening), Milestone 13 (Advanced UI/UX Reconstruction), and Milestone 14 (Final Product Hardening & Full Manual Regression) follow M11's Presentation Complete Gate; Milestone 15 — Release Candidate & Delivery, including its clean-machine acceptance stage (see "v1.0 Release Engineering" below), occurs only after Milestone 14, so the actual hardened, final-UI release is what gets clean-machine-validated, not an earlier presentation layer or unaudited build.

## Closeout Summary

Delivered on branch `m11-ui-ux-refresh`, merged to `main`, in five batches plus targeted corrections, each gated on the user's visual approval before the next began:

- **Batch 0** — theme foundation (`src/listentrace/ui/theme.py`: brand/semantic/product-semantic color tokens, spacing/shape scale, safe system font stack, a two-layer QSS model, a `primary`/`secondary`/`quiet`/`danger`/`success` button-role system, a shared `make_card()` card helper), runtime window-icon resolution across all four execution contexts, and the first two migrated windows (`MainWindow`, `PlayerWindow`).
- **Batch 1** — `GuidedSessionWindow` (all 5 stages) and `SessionHistoryDialog`.
- **Batch 2** — `QuizWindow`, `QuizReviewDialog`, `QuizHistoryDialog` — correctness-hiding-before-submission and non-color-only correctness signaling preserved and verified.
- **Batch 3** — `LearningHistoryWindow` (all 7 tabs), `SimpleBarChart`, `ExportDialog` — plus a centralized `QTabBar` state-contrast fix and a `chart_bar` color correction (teal, replacing a legacy saturated blue).
- **Batch 4** — `QuickPracticeStartDialog`, `QuickPracticeWindow`, `ShadowingPracticeWindow`, `RecordingPanel`, `LabelColorDialog` (chrome only — the learner's own annotation-label colors were never touched), `ImportDialog` — plus a centralized `QRadioButton` checked-state visibility fix.
- **Closeout** — a cross-window consistency and control-inventory audit (no unthemed buttons or stray inline styles found outside the one documented `LabelColorDialog` exception), an added `QPushButton:focus` ring for keyboard navigation, a rebuilt-and-relaunched packaged onedir build with the runtime icon and full theme confirmed visually, and icon-resolution confirmed programmatically from a portable-ZIP-style relocated path.

Two genuine, pre-existing functional defects were found during visual review and fixed as separate, explicitly-flagged, regression-tested corrective commits (not folded into presentation commits): `PlayerWindow`'s crash when constructed with a non-`None` `initial_cue_index` (Learning History's "Jump to Cue"), and `RecordingPanel.set_context()` never refreshing recording-button enabled state (most visible in `ShadowingPracticeWindow`, which has no `set_read_only()` call to mask it).

**Known limitations, reported rather than silently accepted:** this development machine only ever exercises 100% Windows display scaling (`devicePixelRatio` 1.0, 96 logical DPI) — a 125%/150% scaled-DPI pass was never available and remains unverified. The installed-application icon context (post-Inno-Setup-install, launched from Program Files) was not freshly rebuilt or re-verified against the final M11 code in this session, because Inno Setup is not installed in this environment and installing new software was not authorized; the onedir and portable-ZIP contexts were verified instead, and both share the identical runtime icon-resolution code path Inno Setup's installer would also use (a straight copy of the same onedir tree), so this is a code-level equivalence argument, not a direct re-observation. Native OS-level title-bar screenshots beyond the one clean onedir capture were not repeated for the portable-ZIP context after two attempts intermittently captured an unrelated foreground application instead of the launched window — repeating them further was judged a needless privacy risk given a working code-level check already existed.

---

# Presentation Complete Gate (Passed)

The presentation layer becomes complete when:

- the final v1.0 visual system is applied consistently;
- the major windows use coherent navigation, hierarchy, typography, spacing, colors, controls, dialogs, empty states, and status presentation;
- existing functionality remains behaviorally unchanged except for approved defect fixes;
- the application is ready for product-wide hardening and manual acceptance.

Do not claim presentation completion before M11 is implemented and accepted.

**Passed.** All 14 windows and shared widgets use the centralized theme system consistently; the user visually approved every batch (and every requested correction) before the next began; existing functionality is behaviorally unchanged except the two explicitly-flagged, regression-tested corrective fixes described in Milestone 11's Closeout Summary above. Milestone 12 may begin.

---

# Milestone 12 — Pre-UI Product Hardening (Completed)

## Goal

Audit and harden the pre-reconstruction v1.0 product, repair release-relevant defects, and complete initial system audits and automated regression baselines without expanding the frozen product scope.

## Status

**Completed, Accepted, and Merged to `main`.**

- **M12.1-B autonomous overnight audit** (Batches 1-5 + the M12.4 Performance Decision Gate): 18 findings, 8 fixed (5 with pre-fix-verified regression tests), 4 verified already correct, 4 accepted with rationale, 2 deferred to v1.0.x by measurement — see `docs/HARDENING_BACKLOG.md`.
- **Human QA Round 1** (the user's first full manual-acceptance pass) surfaced systemic playback/layout/workflow findings, handled through a read-only Phase 0 audit (`docs/M12_CORRECTIVE_DIVERGENCE_MAP.md`, human-reviewed before any fix) then Batches A (release blockers: Guided Session completion-explainability, ghost-recording-Take, UTC-to-local-time display), B (Round 1 Playback Contract: cue-scoped Play, Previous/Next-Cue fix, Loop Cue toggle label, transcript auto-follow), C (Round 2 Layout Contract: Player workspace scroll/min-height fix, Quiz answer word-wrap), a new History Deletion capability (Round 4 Feasibility Gate), and 2 QA fixture/wording corrections — 10 further fixes, every one with a pre-fix-verified regression test.
- **The Loop Cue audible-endpoint defect** (surfaced by Human QA Round 1): resolved through the calibratable **Loop End Grace** mechanism (per-Material override, global default, a `PlayerSession` snapshot mechanism guaranteeing a live change never retroactively edits an in-flight Loop iteration) plus settings dialogs. **Human-calibrated and closed**: a 3-material retest verified 200ms default sufficient on all three samples — **HUMAN ACCEPTED / CLOSED**.
- **Human QA Round 2**: frozen as a pre-UI baseline/partial acceptance (Loop End Grace calibration only). Full-questionnaire manual regression pass against the finalized UI was cleanly transitioned to Milestone 14.
- **Automated Tests**: reached 759 passing tests upon M12 completion.

---

# Milestone 13 — Advanced UI/UX Reconstruction (Completed)

## Goal

A whole-product visual/interaction reconstruction across all 16 production surfaces, replacing the legacy UI with the modern ListenTrace Notebook Study Desk design system.

## Status

**Completed, Accepted, and Merged to `main`.** Product Owner Human Visual Gate: **PASS**. All 16 production surfaces reconstructed into the modern ListenTrace Notebook Study Desk design system; Axes 1–8 closed; corrective passes resolved StageStepper navigation safety, Learning History information architecture, Player short-screen local-scroll accessibility and aspect-ratio-aware video geometry, Quiz canvas sizing, and all P0/P1/P2 visual/accessibility findings. Automated test suite: 894 passing tests (100% green).

## Closeout Summary

- **Notebook Study Desk Design System**: unified tokens, surface/role styling (`apply_surface`, `apply_role`), warm study paper surfaces, ruled paper list widgets, margin lines, spiral binding strips, and clear action grammar across all 16 production surfaces.
- **Deep Surface Interaction Reconstruction**:
  - **Synchronized Player**: open-book layout with horizontal splitter, persistent quiet active-subtitle HUD, unified playback timeline scrubber, three mini-notebook control cards (Playback, Loop & Practice, Utility), independent right workspace with tabbed Transcript & Cues and ruled Annotation Notebook, local vertical scroll container (`_cinema_scroll_area`) for the left cinema column guaranteeing full control reachability on short screens with horizontal scrolling disabled, and aspect-ratio-aware video viewport (`_PlayerVideoWidget`) preventing raw 1080p/4K frame dimensions from inflating the scroll area.
  - **Guided Intensive Listening**: persistent 5-stage study book shell with a 5-step horizontal non-clickable StageStepper, stage-specific writing/capture forms, and atomic stage-progression validation (`Save and Continue` properly enforces completion eligibility).
  - **Quizzes & Recall Practice**: clean question cards with natural content-height ownership, radio answer cards with proper word-wrap, and structured post-submission review dossier (`QuizReviewDialog`).
  - **Quick Practice**: stable left-two/right-one runtime workspace layout (left column: persistent cue context + step-specific processing workspace; right column: shared RecordingPanel support workspace) and a 4-stage non-clickable progress stepper derived from real session state.
  - **Standalone Shadowing Practice**: dedicated single-focus study desk studio with cue navigation, reference cue card, and embedded recording panel.
  - **Learning History**: structured Study Dossier layout with a multi-tab sidebar directory, scan-oriented Overview metric grid, and dedicated tabs for Activity, Sessions, Diagnoses, Quizzes, Shadowing & Recordings, and Needs Attention.
  - **Material Library & Dialogs**: Study Dossier sidebar and detail panel, themed Session History, Quiz History, Import, Export, Label Colors, and Material Loop Settings sheets.
- **Axes 1–8 Closure & Corrective Passes**:
  - Axes 1–5: surface architecture, paper primitives, and card layouts accepted.
  - Axis 6: residual typography unification into role-based display and readable long-form/CJK-safe content families.
  - Axis 7: geometry, density, and clipping corrections across all surfaces.
  - Axis 8: Quick Practice structural redesign into a stable runtime layout.
  - Final Human-Gate corrective passes: resolved StageStepper accessibility/clipping, Learning History IA/wrapping, Player right-workspace clipping, and P0/P1/P2 findings.
  - Final Player accessibility/geometry corrective passes: added local left cinema vertical scrolling and aspect-ratio-aware video viewport, eliminating video/HUD overlap and black letterbox inflation.
- **Database Schema**: zero schema changes; database schema remains stable at version 12.
- **Automated Tests**: 894 passed (100% green regression and integration test suite).
- **Human Visual Gate**: formally accepted on native Windows.

---

# Milestone 14 — Final Product Hardening & Full Manual Regression (Completed, Accepted, Merged)

## Goal

Final product hardening and full manual acceptance against the reconstructed Notebook Study Desk interface, resolving remaining edge-case defects, and preparing the codebase for clean-machine packaging and v1.0 release.

## Status

**Completed, Accepted, and Merged to `main`.** Human QA Round 2 PASS; the pre-merge repository-hygiene/privacy/Windows-app-identity corrective is Product Owner ACCEPTED (Windows taskbar-identity spot-check PASS). Accepted M14 product baseline: the final commit on `milestone/14-final-product-hardening` merged into `main` via the M14 pull request.

- **Phase 0 — Baseline Reconciliation & Immediate Correctives (Complete)**:
  - Macro documentation reconciled to the then-canonical lifecycle: `M12 (Completed) -> M13 (Completed) -> M14 (Current) -> Phase C2 -> Phase D` (superseded by the M14 pre-merge hygiene/privacy/app-identity corrective's `M15 — Release Candidate & Delivery` lifecycle — see "Canonical v1.0 Sequence", below; the former Phase C2/Phase D content was not discarded, only renamed and consolidated into Milestone 15).
  - Interface-sound system explicitly excluded from product/design specs (decorative audio removed; learning audio fully intact).
  - Material Study Dossier in `MainWindow` aligned to approved wireframe (structured 7-row ruled metadata panel with blue ink labels, spiral dots, and action suite).
  - Global Settings consolidated under Library sidebar `Settings...` with categorized `Playback` and `Label Colors` tabs; redundant Player entry point removed.
  - Cue selection clearing via right-click context menu implemented; selection box border clipping normalized; automated test suite expanded to 900 passing tests.
- **Phase 1 — Whole-Product Hardening Audit (Complete, Product Owner Accepted)**: a read-only, risk-based audit across all in-scope product areas (`docs/M14_PHASE1_WHOLE_PRODUCT_HARDENING_AUDIT.md`) — 6 confirmed defects, 2 governance/documentation drift items, and a proposed corrective batch plan.
- **Corrective Batches A, B, C (All Complete)**: every confirmed defect from the accepted Phase 1 audit resolved (0 open) — cross-window state consistency (rename/selection/label-color/recording-availability), local-time display correctness, "No Notable Difficulty" availability truthfulness, a permanent remove-while-open-window safety regression test, the two governance drift items closed, and the orphaned Player-local Label Colors compatibility path removed. Automated test suite: 924 passing.
- **Human QA Round 2 (PASS)**: full manual regression pass against the finalized, corrective-batch-complete product using `manual-qa/manual_review_questionnaire.html` (`2026-08-26.2` — stale M13-era wording corrected, new M14 behavior covered, and items strongly protected by the new automated regression consolidated so the Product Owner isn't asked to repeatedly re-verify what automation already proves). One finding (`m09-04`, structured-export Markdown/JSON evidence parity) was corrected across two focused correctives before Product Owner retest passed; 0 known open Human QA defects.
- **Pre-Merge Repository Hygiene, Privacy & Windows Product Identity Corrective (Complete, Product Owner Accepted)**: lifecycle/governance naming cleanup (this document), repository-root hygiene and historical-artifact archival, manual-QA/live-database source-control privacy hardening, and a Windows AppUserModelID fix so ListenTrace no longer shares taskbar grouping with unrelated local applications — Product Owner Windows taskbar spot-check **PASS**.
- **Final `/code-review` exit pass (Complete)**: reviewed the full M14 branch diff against `main` (Standards and Spec axes). Two bounded, real gaps found and fixed with regression coverage — a missing test for `PlayerWindow`'s cross-window rename-propagation handler, and a stale `LabelColorDialog` reference in `README.md`'s architecture tree. No release blocker found otherwise. Final automated suite: 948 passing.
- **Pre-Release Non-Visual Hardening**: Final sweep of error boundaries, missing file handlers, and edge cases — folded into the above; no additional open items.

**M14 exit summary**: confirmed open defects — 0; M14-internal release blockers — 0. Milestone 14 does not itself perform clean-machine acceptance or release-candidate delivery; those are Milestone 15's job, below.

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

Release engineering began once Milestone 10 was accepted and functional feature development entered freeze, organized into phases: A (packaging spike), B (targeted technical release hardening), C1 (release preflight) — interleaved with Milestones 11, 12, 13, and 14 in the Canonical v1.0 Sequence, below. This section was previously named "Post-M10 — Release Engineering and v1.0 Delivery"; it is renamed here only because Milestone 11 now exists after M10, which made a "Post-M10" heading historically awkward — the Phase A/B/C history and decisions below are preserved, not rewritten. Phase A's packaging decisions are locked, Phase B's hardening pass is complete, and Phase C1's development-machine preflight is complete (see below).

The forward-facing release-candidate work — formerly tracked as the separate "Phase C2" and "Phase D" release-engineering labels sitting awkwardly beside numbered product milestones — is consolidated as **Milestone 15 — Release Candidate & Delivery** (see below), the next numbered milestone after Milestone 14, occurring after it in the sequence. A v1.0 release date is still not chosen.

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

## Phase B — Targeted Technical Release Hardening (Completed)

Phase B was a targeted technical release-hardening pass completed before the final UI and product-wide acceptance stages. It addressed confirmed technical risks, but it does not replace the subsequent hardening passes in Milestone 12 and Milestone 14 — Phase B is not reopened merely because later hardening milestones exist. Corrective work for:

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
- operation without a developer Python environment: structurally addressed by construction (the PyInstaller build embeds the Python runtime and every dependency, with no intended dependency on a separately installed interpreter), but **not yet empirically verified on a machine without Python installed** — every Phase A/B validation so far ran on the development machine, which already has Python installed; that empirical verification belongs specifically to Milestone 15.2's "no preinstalled Python" clean-machine criterion (not Phase C1, which is development-machine preflight only).

An acceptance closeout pass corrected the wording above (the no-developer-Python-environment item had originally, and incorrectly, been described as already verified) and completed the shutdown half of the startup/shutdown audit that the original pass had left unaudited.

See `ARCHITECTURE.md`'s "Resolved in Post-M10 Phase B" section and `packaging/README.md` for full detail and validation evidence.

## Phase C1 — Development-Machine Release Preflight (Completed)

Represents all validation already performed on the development machine, formerly recorded as the single Phase C. Not to be confused with product-wide hardening and full manual regression (Milestones 12 and 14) — C1 is packaged-build preflight evidence, not a product-wide audit. Covers:

- install, launch, upgrade, and uninstall: a fresh silent install, a reinstall over the same install (upgrade-in-place via the same AppId), a silent uninstall, each launch in between, all completed cleanly;
- data preservation: a real material row survived install → data creation → reinstall → uninstall intact;
- legacy database upgrade: a real pre-Milestone-10 (schema version 8) database with real material/session/recording rows, opened directly by the compiled exe, upgraded cleanly to version 10 with all data intact;
- WAV playback through the packaged Qt Multimedia (FFmpeg) plugin: loads correctly, correct duration, no errors;
- a real physical microphone recording, producing a valid WAV file with no errors;
- Unicode executable/path verification: the packaged exe launched successfully from a Chinese-character install path;
- core application-service walkthroughs (Intensive Practice, Quiz, a standalone recording, Quick Practice), Learning History aggregation, and Markdown export generation, all through the real application services, feeding one database;
- the latest packaged application opening the resulting database without error.

**C1 does not prove**: clean Windows behavior, no-Python target-machine behavior, fresh Windows-user behavior, a genuinely non-development environment, broad real-world MP4/H.264 compatibility, or native GUI interaction coverage on another machine — every check above ran on this project's own development machine, which already has Python, Git, an IDE, FFmpeg, and other developer tooling installed. C1 is release preflight, not Clean-Machine Testing; that is Milestone 15.2's job, below.

---

# Milestone 15 — Release Candidate & Delivery (Complete, Accepted, Merged)

## Goal

Take the Milestone 14-hardened, Human-QA-accepted product through a refreshed candidate build, genuine clean-machine acceptance, and final release-candidate closure — the last milestone before `v1.0 — Current Version Complete`.

## Status

**Complete. 15.1 Product Owner ACCEPTED. 15.2 PASS / Product Owner Accepted. 15.3 complete.** Accepted M15 product baseline: the final commit on `milestone/15-release-candidate-delivery` merged into `main` via PR #4. Consolidates the former separate "Phase C2" and "Phase D" release-engineering labels (historical names, preserved above under Phase A/B/C1) into three sub-stages of one numbered milestone, so the active lifecycle no longer mixes numbered product milestones with unnumbered release-engineering phases:

- **Milestone 15.1 — Candidate Build / Packaging Refresh (Product Owner ACCEPTED)**: rebuilds the PyInstaller onedir build and Inno Setup installer against the final, merged Milestone 14 code (including the Windows AppUserModelID/taskbar-identity fix); confirms packaging identity metadata (icon, AppUserModelID, shortcut/AppId) is internally consistent; promotes the product version to `1.0.0` via a new single-source-of-truth mechanism (`scripts/release_version.py`); adds a GitHub Actions Windows release-candidate pipeline (`.github/workflows/release-candidate.yml`) that builds and smoke-tests the portable ZIP and installer from the same onedir output and uploads checksummed/provenance-tracked canonical artifacts. CI green end-to-end.
- **Milestone 15.2 — Clean-Machine Acceptance (PASS / Product Owner Accepted)**: the environment-validation gate, occurring after Milestone 14 so the final hardened, final-UI release candidate is what gets tested, not an earlier presentation layer or an unaudited product.

  Environment used: a clean Windows 11 VMware VM, VMware Tools installed, a clean baseline snapshot, no Python/Git/IDE/developer environment installed — meeting the target baseline below.

  Target baseline: Windows 11 x64, Home or Pro, standard non-N edition, normal Windows system updates, no Python installation, no Git, no IDE, no PyInstaller, no Inno Setup, no project source tree, no developer virtual environment, and no manually installed FFmpeg or codec pack required for ListenTrace.

  **Canonical validated release payload (locked — see "Validated Release Payload Policy" below)**: version `1.0.0`, source SHA `661bca47ce93f1a12a6a17c66f1ed6065d816e43`, artifact bundle `ListenTrace-1.0.0-candidate-661bca47ce93f1a12a6a17c66f1ed6065d816e43` (`ListenTrace-Setup-1.0.0.exe`, `ListenTrace-1.0.0-win64-portable.zip`, `SHA256SUMS.txt`, `provenance.json`) — confirmed via `gh run view`/`gh api` to be the exact CI-built canonical bundle at that commit, and checksums independently re-verified with `sha256sum`. This is the payload that must ship as v1.0.0, regardless of how much further the branch/`main` HEAD has since advanced for documentation/governance purposes.

  Human clean-machine evidence, all **PASS**: normal per-user installation; first launch; real MP4/H.264 import and playback; real audio output; SRT/material import; a representative Intensive Practice completion; full app close/reopen with session persistence; Windows taskbar/app identity (own icon, own taskbar group, no shared grouping with an unrelated locally installed application). No release-blocking abnormal behavior observed. Microphone passthrough and display-scaling checks were exercised informally but, by Product Owner decision, were not expanded into additional hard acceptance gates — M15.2 validates the packaged artifact and clean environment, it does not repeat Milestone 14's broad manual regression.

  This is a release gate: it must not be marked completed until a genuinely appropriate clean environment has actually been used. If it discovers a release-blocking defect: `M15.2 failure -> return to an M14 corrective batch -> regression -> repeat M15.2`. M15.2 is an environment and packaged-artifact acceptance gate — it does not replace Milestone 14's product-wide hardening and full manual regression.
- **Milestone 15.3 — Release Candidate Closure & Delivery (Complete)**: final versioning; privacy and local-data explanation; installation and usage documentation; known limitations; release notes (`RELEASE_NOTES.md`); final privacy audit (re-verified, no regression since M14 closure); complete regression status; RC installer and RC zip (produced by the M15.1 pipeline, provenance-reconciled against the M15.2-tested candidate — see the validated release-payload policy below); release checklist; a small real-user acceptance test (satisfied by M15.2's clean-machine session); unsigned-v1.0 and Update-Awareness-deferral decisions documented. **Update Awareness is explicitly out of scope, deferred to the first v1.0.x maintenance update.**

  **Milestone 14 and Milestone 15.2 have both passed, so Milestone 15 is complete** and, via PR #4, merged into `main`. The `v1.0.0` tag and GitHub Release are deliberately **not** created by this milestone's engineering work — those, and the final `v1.0 — Current Version Complete` declaration, are the Product Owner's own subsequent actions (see below). If a blocking problem is discovered before that publication step, return to an M14 corrective batch, rerun affected regression, and repeat any invalidated M15.2/M15.3 checks.

## Validated Release Payload Policy (locked, Product Owner approved)

The canonical v1.0.0 release payload is, and remains, the exact Milestone 15.2 human-validated candidate — source SHA `661bca47ce93f1a12a6a17c66f1ed6065d816e43`, artifact bundle `ListenTrace-1.0.0-candidate-661bca47ce93f1a12a6a17c66f1ed6065d816e43`. **Test what we ship; ship what we tested.** Later docs-only commits on `milestone/15-release-candidate-delivery` (governance/documentation reconciliation, this closure included) intentionally advance the branch and `main` HEAD past that commit; each such commit's own CI run produces its own workflow artifact under a different commit SHA, but no product/application code changed after `661bca47...`, so those later artifacts are automatically-generated verification evidence for the branch state — **not** a substitute release payload. When the Product Owner tags and publishes `v1.0.0`, the artifact bundle attached to that Release must be the `661bca47...` bundle specifically, not whatever the final merge commit's own CI run produces.

---

# v1.0 — Current Version Complete

This state means: the approved v1.0 scope is implemented; Functional Feature Freeze was respected; M11 presentation refresh and M13 UI reconstruction are complete; M14 product hardening and manual regression passed; Milestone 15.2 clean-machine acceptance passed; Milestone 15.3 release-candidate checks passed; the release artifact, documentation, known limitations, and repository state are finalized. This does **not** describe the project as permanently complete — see Maintenance and Next-Version Planning, below.

**Status: declared.** Every engineering/acceptance gate above (M11–M14, Milestone 15.1/15.2/15.3) is complete, PR #4 is merged into `main` at `4e50b6b195c9c214b3875a9ae33d0ca0ac35f8bb`, the `v1.0.0` tag exists at that commit, and GitHub Release `ListenTrace v1.0.0` is published carrying the validated `661bca47...` payload (installer, portable ZIP, `SHA256SUMS.txt`, `provenance.json`). The project is now in **Maintenance / v1.0.x**. **Portfolio Packaging is complete**, and the immediate next project step is the **Public Readiness Gate** before any repository-visibility change.

# Maintenance / v1.0.x

Possible scope: release-blocking or user-impacting defect fixes; compatibility fixes; narrowly scoped UX corrections; dependency/security maintenance; documentation corrections; patch releases that do not expand the product into a new feature cycle.

# Next-Version Planning / v1.1+

Possible new capabilities may be evaluated only after v1.0 is stabilized and used. Optional Assisted Features (above) remain in the deferred section unless explicitly promoted through a future product decision.

## Candidate: Milestone 16 — Library Organization & Collections

Recorded during real high-frequency post-Human-QA use: the Product Owner identified that ListenTrace will be used across multiple languages (including English and French), and that long-term use will build a large material library where materials serve different learning purposes and skill areas. The current flat Library remains functionally correct for v1.0 but will become increasingly costly to navigate at scale — a product-growth / information-architecture requirement, not an M14 defect or v1.0 release blocker.

Possible future exploration (not designed, not locked): language-aware organization; Collections; optional tags / learning-purpose organization; scalable Library filtering/navigation; relationships between organization metadata and existing Archive / History / Export behavior.

**Explicitly**: not part of Milestone 14; not part of Milestone 15 (Release Candidate & Delivery); no current schema migration; no current UI change; a v1.1 / Milestone 16 candidate only, to be scoped after v1.0 is closed. This is intentional scope control, not a missing v1.0 feature.

---

# Canonical v1.0 Sequence

```
Milestones 1-10 — Core Functional Development
  -> Functional Feature Complete Gate
  -> Functional Feature Freeze
  -> Phase A — Packaging Spike (Completed)
  -> Phase B — Targeted Technical Release Hardening (Completed)
  -> Phase C1 — Development-Machine Release Preflight (Completed)
  -> Milestone 11 — UI/UX Presentation Refresh (Completed)
  -> Presentation Complete Gate (Passed)
  -> Milestone 12 — Pre-UI Product Hardening (Completed)
  -> Milestone 13 — Advanced UI/UX Reconstruction (Completed / Human Visual Gate Passed / Merged)
  -> Milestone 14 — Final Product Hardening & Full Manual Regression (Completed, Accepted, Merged — Human QA Round 2 PASS; pre-merge hygiene/privacy/app-identity corrective Product Owner ACCEPTED)
  -> Milestone 15 — Release Candidate & Delivery (Completed, Accepted, Merged)
       -> Milestone 15.1 — Candidate Build / Packaging Refresh (Product Owner ACCEPTED)
       -> Milestone 15.2 — Clean-Machine Acceptance (PASS / Product Owner Accepted)
       -> Milestone 15.3 — Release Candidate Closure & Delivery (Completed)
  -> v1.0 — Current Version Complete (Declared — tag `v1.0.0` and GitHub Release published at `4e50b6b195c9c214b3875a9ae33d0ca0ac35f8bb`)
  -> Maintenance / v1.0.x
  -> Next-Version Planning / v1.1+
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
- User supplies media and matching transcript or timed subtitles
- Timed subtitles (.srt, .vtt) provide the primary structured learning experience
- Listening failure categories are semantic labels, not colors
- User owns saved word and chunk content
- Structured export precedes embedded online evaluation
- Original user media remains outside the application database, referenced in place, never modified or deleted
- Desktop media playback backend: PySide6 Qt Multimedia with bundled FFmpeg backend
- Audio recording format: 16-bit PCM WAV captured locally to `%APPDATA%\ListenTrace\recordings`
- Target desktop OS: Windows 10/11 x64 (per-user installation via Inno Setup and portable zip)
- Interface sound policy: decorative UI audio explicitly excluded; authentic learning audio fully preserved

# Decisions Still Open

- Future platform packaging (macOS, Linux) — deferred beyond v1.0
- Long-term auto-update service integration — deferred beyond v1.0
- Multi-language interface localization — English UI baseline established for v1.0; additional locales deferred beyond v1.0

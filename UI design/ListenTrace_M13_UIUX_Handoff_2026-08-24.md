# ListenTrace-5 — UI/UX M13 Handoff

## 0. Purpose

This handoff is for continuing the **ListenTrace Milestone 13 UI/UX reconstruction** in a new chat without reloading the full prior conversation.

Primary focus of the new chat:

> finish the final Pre-HG2 corrective pass, externally re-audit the corrected remote branch, then perform the user's formal HG-2 whole-product UI acceptance.

Do not restart design discovery.  
Do not reopen M13 architecture broadly.  
Do not enter M12 Phase 12-B until HG-2 is passed.

---

# 1. Collaboration / Operating Rules

The assistant should act as:

1. senior AI-coding prompt engineer;
2. rigorous software/product advisor;
3. senior educational psychologist familiar with cognition, learning workflows, and AI-assisted education.

AI-coding operating rules:

- milestone-driven development;
- prompts should be clear contracts, not giant construction manuals;
- only one manually selected skill per agent run;
- when producing agent prompts, always state the recommended Manual Skill;
- if a Markdown prompt exceeds ~200 lines, provide it as a downloadable `.md`;
- keep Human Gates sparse;
- Batch Exit is not automatically a Human Gate;
- final merge-ready prompts must force macro/governance docs into truthful post-merge state;
- never let current-state documentation drift across lifecycle transitions.

Current implementation skill preference:

> `/tdd` only

---

# 2. Repository / Branch State

Repository:

`Peter-S-Shi/ListenTrace`

M12 Phase 12-A was already merged into `main`.

Known M12 merge commit:

`6ef399771fe94a18551fca50328e989759e84cb8`

Current M13 remote branch:

`milestone/13-advanced-ui-ux`

Last externally verified corrective remote HEAD before the newest final corrective run:

`ee027a4fd57da5a7cb0f4b7dabbdec1dcda7aa9d`

Important:

- M13 has **not** been merged into `main`;
- HG-2 has **not** passed;
- M13 is **not** complete;
- M12 Phase 12-B has **not** started.

---

# 3. Lifecycle State

Current truthful state:

```text
M13.0 — UI/UX Audit & Design Discovery — COMPLETE
M13.1 — Whole-Product UI Architecture — COMPLETE
M13.2 — Prototype & Human Design Validation — COMPLETE
M13.3 — Design System Contract & Implementation Mapping — COMPLETE

M13.4 — Production Reconstruction
  Batch 0 — COMPLETE / KEEP
  Batch 1 — COMPLETE / KEEP
  HG-1 — PASS

  Original Batch 2–5
  — REJECTED AS INSUFFICIENT RECONSTRUCTION

  Corrective 2A — COMPLETE
  Corrective 3A — COMPLETE
  Corrective 4A — COMPLETE
  Corrective 5A — COMPLETE

Pre-HG2 external code + screenshot audit
— CORRECTIONS REQUIRED

HG-2 — NOT STARTED
M13 — NOT COMPLETE
M12 Phase 12-B — NOT STARTED
```

---

# 4. Frozen M13 Design Direction

Long-lived design authority:

`/DESIGN.md`

Do not create a competing design-contract document.

The accepted M13 design DNA is:

> **Professional workspace outside, focused media when listening, calm paper-like surface when learning.**

Frozen product-family direction:

- Warm Professional Learning Desk
- Professional Blue
- Spacious Learning
- Hybrid Shell
- selective lined-notebook / ruled-paper language
- full-workspace Dark Listening Focus for Player
- session-local Stage 1–5 Guided navigation
- Cue-as-Card
- restrained card depth
- contextual state language

Contextual state language:

- Library / History = Rich Scan
- Player = Quiet Focus
- Guided Learning = Balanced Guidance

Notebook language is selective, not a global skin.

Use ruled-paper / notebook language for:

- archive/record surfaces;
- material dossier/context;
- history;
- Final Recall;
- suitable note-like study surfaces.

Do not turn media, settings, every dialog, or every card into stationery.

---

# 5. HG-1 Result

HG-1 was passed after correcting the representative MainWindow slice.

Accepted MainWindow direction includes:

- Acrobat-style narrow left directory/sidebar;
- left-aligned navigation;
- Materials archive/list;
- Material Study Dossier;
- Professional Blue;
- Spacious Learning;
- notebook/ruled-paper visual language;
- action hierarchy.

MainWindow should not be broadly redesigned again.

---

# 6. Why Original Batch 2–5 Was Rejected

A read-only corrective audit found that the original Batch 2–5 implementation mostly added:

- QSS roles;
- surface styling;
- theme calls;
- minor layout adjustments.

It did not materially reconstruct the major PySide6 interaction architecture.

Audit verdict:

`BATCH_2_5_REJECTED_AS_INSUFFICIENT_RECONSTRUCTION`

This triggered separate corrective batches:

- 2A Player
- 3A Guided Session
- 4A Quiz / Practice / History
- 5A Whole-product integration

---

# 7. Corrective Reconstruction That Should Be Preserved

## Player

Now has a real left/right architecture:

```text
Dark Listening Focus
├─ Cinema / Listening Stage
└─ Transcript & Cue Workspace
```

Includes:

- dedicated Cinema Stage;
- grouped transport controls;
- Cue-as-Card direction;
- playing cue marker;
- selected cue distinction;
- cue tools moved into tabs:
  - Annotate
  - Cue Note
  - Save Item

Do not redesign the Player from scratch.

## Guided Session

Now has:

- session-local StageStepper;
- Stage 1–5 shell;
- Stage 3 two-region diagnosis workspace;
- Stage 4 recording/shadowing workflow;
- Stage 5 ruled Final Recall notebook.

Do not remove the StageStepper concept.

## Quiz

Now has:

- focused question canvas;
- `QuizOptionCard`-style answers;
- improved Next / Submit hierarchy.

## Quick Practice

Now has a more compact micro-cycle architecture.

## Standalone Shadowing

Now reuses the Stage 4 workflow language more coherently.

## Learning History

The old seven horizontal tabs were replaced by:

```text
left section directory
+
right QStackedWidget workspace
```

This is a real architecture improvement and should be preserved.

---

# 8. CC Transition Context

AG2.0 ran out of quota during a Pre-HG2 corrective run.

The user switched to Claude Code (CC), which continued the work and pushed the branch.

Two AG artifacts were reviewed:

- implementation plan;
- task checklist.

Those documents describe handoff/planned work at the moment AG stopped; they are not the authoritative final implementation state.

CC subsequently implemented most of the planned fixes and pushed them to the M13 branch.

CC reported a final local test baseline of:

`781 passed`

No independent remote CI evidence was available at that point, so treat 781 as a local verification report, not GitHub CI proof.

---

# 9. Important Visual Evidence Rule

CC-generated screenshots are **invalid visual evidence** because text rendered as hollow square boxes.

Do not use those screenshots to judge:

- typography;
- wrapping;
- clipping;
- information hierarchy;
- final UI acceptance.

The user's own local screenshots are the trusted visual evidence.

The user uploaded a ZIP:

`new evidence.zip`

It contained 16 unnamed screenshots.

The screenshots were manually identified by window/state before audit.

---

# 10. Screenshot Identification Map

The 16 screenshots were identified as:

- Guided Stage 4 — Sentence-Level Shadowing, empty Take state
- PlayerWindow — Dark Listening Focus, normal wide desktop
- Guided Stage 3 — Transcript Comparison & Error Diagnosis
- Session History Dialog
- Guided Stage 1 — Global Comprehension
- Guided Stage 5 — Final Recall, empty summary
- Standalone Shadowing Practice — one Take
- Learning History — Overview
- PlayerWindow — another transcript/scroll state
- Guided Stage 5 — summary saved, Complete Session still disabled
- Standalone Shadowing — recording in progress
- PlayerWindow around ~1060px width, layered over MainWindow
- MainWindow — Material Library / Study Dossier
- Guided Stage 2 — Keyword & Fragment Capture
- QuizWindow — multiple-choice question
- QuizWindow — text-answer / Review Quiz question

Missing valid visual evidence:

- Quick Practice
- Quiz Review
- Learning History non-Overview section

These should get a short visual check later, but do not redesign them merely because screenshots are missing.

---

# 11. Highest-Priority Bug Found During Screenshot + Code Cross-Audit

## P0 — Guided Save-and-Continue progression regression

User observed:

> after Stage 5 is completed, Complete Session is disabled again.

Root cause was identified from screenshots + remote code.

Current problematic UI flow:

```python
try:
    svc.complete_stage(...)
except SessionValidationError:
    pass

# then advance anyway
```

Meaning:

> a Stage can fail its completion rule, but the UI silently swallows the error and still navigates to the next Stage.

This explains the apparent Complete Session regression.

Example reproduced state:

- Stage 3 unresolved;
- Stage 4 shows unresolved cues;
- user is still allowed to reach Stage 5;
- Stage 5 summary can be saved;
- Complete Session correctly remains disabled because prior stages are not terminal.

The final disabled Complete Session button is therefore not the root bug.

The real bug is:

> **invalid Stage completion can still advance workflow.**

Domain rules themselves are correct:

- Stage 1 needs qualifying comprehension evidence;
- Stage 2 needs at least one capture;
- Stage 3 needs diagnosis evidence or explicit no-notable-difficulty;
- Stage 4 needs all timed cues resolved;
- Stage 5 needs non-empty summary;
- Session complete requires all stages completed/skipped.

Required UI behavior:

```text
complete_stage success
→ advance

complete_stage failure
→ show reason
→ remain on current Stage
→ do not advance
```

This is the top blocker before HG-2.

---

# 12. Other Confirmed Pre-HG2 Issues

## P0 — Player clipping around 1060–1080px

Player's top-level reconstruction is good.

Remaining problem is inside the Annotate tab:

- five annotation category checkboxes remain in one horizontal row;
- final category clips at narrower desktop width;
- action buttons can also extend beyond the pane.

Fix only the inner form.

Recommended:

- multi-row/grid/wrapping category layout;
- compact action row if needed.

Do not redesign Player again.

## P1 — StageStepper vertical clipping

User screenshots show the StageStepper content clipped vertically on all stages.

Likely cause:

- a `QPushButton` contains a nested child widget/layout;
- button minimum/size hint does not fully contain badge + label + margins.

Preserve:

- QPushButton semantics;
- keyboard accessibility;
- disabled future stages.

Fix geometry / minimum height / sizeHint behavior.

## P1 — Learning History directory

The new left-directory architecture is accepted.

Remaining issues:

- `Shadowing & Recordings` truncates;
- horizontal scrollbar appears.

Fix through:

- slightly wider directory and/or wrapping;
- no horizontal scrollbar.

Do not return to horizontal tabs.

## P1 — Learning History Overview

Overview still looks like a raw multi-line metrics dump.

Recommended:

- simple 2-column scan-oriented metrics grid;
- preserve existing metrics;
- no BI-dashboard expansion.

Keep Continue Learning and Needs Attention.

## P1 — Guided Stage 2 empty state

CC added an empty-state label, but the empty capture list still occupies a huge blank region.

Correct behavior:

- no captures → deliberate centered/contained empty state, list minimized/hidden;
- captures exist → list expands, hint hides.

## P1 — Quiz canvas ownership

Quiz architecture is much better.

Remaining problem:

- card appears narrower than ideal;
- options occupy the top;
- large empty region remains inside the card.

Recommended:

- deliberate comfortable width;
- choice questions use mostly natural content height;
- empty space stays outside the card;
- text-answer/dictation may legitimately need more height.

Preserve Next/Submit behavior.

## P1 — Governance drift

`PROJECT_STATUS.md` was improved at the top but later sections still contained stale current-state claims, including old main/M12 branch sequencing.

Must be cleaned before HG-2 readiness.

Truthful state before HG-2:

```text
M12 Phase 12-A already merged to main.
M13 exists on milestone/13-advanced-ui-ux.
Pre-HG2 corrective work is on the branch.
HG-2 has not passed.
M13 is not complete.
M12 Phase 12-B has not started.
M13 is not merged to main.
```

---

# 13. Items Already Judged Good / Do Not Rework

## Guided Stage 4 layout

CC's shared `RecordingPanel` empty-state correction was successful.

Do not perform another architecture redesign.

## Guided Stage 5 notebook

The user's screenshots confirm real horizontal ruled lines now exist.

This direction is accepted.

There is a low-priority technical risk around ruled-line scroll phase for very long scrolled text, but it is not currently a blocker.

## Session History Dialog

Visual result is acceptable.

Keep it restrained.

Do not add excessive spiral decoration.

## MainWindow

Overall architecture is mature enough to preserve.

Do not reopen the shell.

## Player top-level architecture

Accepted.

Only fix the narrow-width inner Annotate form.

---

# 14. Latest Prompt Prepared for CC

A final narrow corrective prompt has been created:

`ListenTrace_M13_Final_Pre_HG2_Corrective_Prompt.md`

Manual Skill:

`/tdd` only

The prompt requires CC to fix:

1. Guided invalid Save-and-Continue progression;
2. Player ~1060–1080px annotation clipping;
3. StageStepper vertical clipping;
4. Learning History directory truncation/horizontal scroll;
5. Learning History Overview raw metrics;
6. Guided Stage 2 empty-state dead space;
7. Quiz internal dead space / width ownership;
8. stale `PROJECT_STATUS.md` current-state wording.

It explicitly tells CC:

- do not redesign successful M13 surfaces;
- do not merge;
- do not start HG-2;
- do not enter M12 Phase 12-B;
- push corrections to the same remote M13 branch.

---

# 15. Mandatory Tests in the Final Corrective Run

The final corrective run must add/retain tests proving:

## Guided progression

- empty Stage 1 cannot advance;
- empty Stage 2 cannot advance and cannot reveal transcript;
- unresolved Stage 3 cannot advance;
- unresolved Stage 4 cannot advance;
- valid Stage 1→5 flow enables Complete Session.

## StageStepper

- future jump remains blocked;
- keyboard activation remains;
- geometry/minimum-height check if deterministic.

## Player

- annotation controls remain reachable/contained at a representative narrow desktop width where deterministic.

## Learning History

- left directory + right stack architecture remains;
- no regression to seven horizontal tabs.

## Quiz

- retain option-card accessibility/selection tests;
- add layout assertions only where meaningful.

Do not rely on tests that merely check:

- a class exists;
- the outer window resized;
- a surface property is set.

---

# 16. What Happens Next

After CC completes `ListenTrace_M13_Final_Pre_HG2_Corrective_Prompt.md`:

1. user provides CC completion report + new remote HEAD SHA;
2. assistant directly re-audits the remote branch;
3. confirm the P0 progression bug is actually fixed;
4. inspect code changes for the remaining layout fixes;
5. user performs only a **short visual check** for remaining uncertain surfaces:
   - Quick Practice
   - Quiz Review
   - Learning History non-Overview
   - plus any corrected view where the assistant still needs visual confirmation;
6. if external pre-HG2 review passes → formally start HG-2;
7. HG-2 remains the same five-journey whole-product human acceptance;
8. only after HG-2 PASS:
   - mark M13 complete;
   - prepare PR / merge-ready governance closure;
   - merge to main;
   - then return to M12 Phase 12-B.

---

# 17. HG-2 Contract — Do Not Expand It

HG-2 should remain a compact five-journey review:

1. Whole-product visual coherence
2. Player / Dark Focus
3. Guided Session representative stages
4. Quiz + History
5. Basic resize + overall trust

HG-2 is **not** a repeat of full M12 manual QA.

The user should not manually retest every:

- Loop edge case;
- recording ownership rule;
- database operation;
- deletion cascade;
- quiz scoring edge case;
- export path.

Those belong to automated regression and M12 Phase 12-B.

---

# 18. HG-2 Outcomes

Use only:

## PASS

Then:

- M13 accepted and complete;
- finalize governance truthfully;
- proceed toward merge;
- next lifecycle phase = M12 Phase 12-B.

## PASS WITH CORRECTIONS

Do one narrow M13 closeout correction.

Do not reopen design discovery.

## FAIL

Reopen only the failed design/interaction axis.

Do not discard the whole M13 system automatically.

---

# 19. Important Governance Rule for Final Merge-Ready Prompt

When M13 eventually reaches PR merge-ready state:

> macro/current-state documentation must be written one step ahead into the truthful post-merge state.

Use this semantic test:

> If Merge is clicked now, will every current-state sentence still be true one second later?

If not, the PR is not merge-ready.

Do not allow another migration/state-drift incident.

---

# 20. Immediate Next Action for the New Chat

The next chat should **not** start by discussing new UI ideas.

Immediate action:

> wait for / review the completion of `ListenTrace_M13_Final_Pre_HG2_Corrective_Prompt.md`.

When the user provides the CC completion report and new SHA:

- inspect GitHub first;
- verify the progression regression and final corrections;
- do not accept self-reported test success without checking code;
- then request only the minimum missing user screenshots;
- only after external review passes, begin HG-2.

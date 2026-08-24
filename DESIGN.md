# ListenTrace — DESIGN.md

> Status: M13 Design Authority Draft v0.1  
> Scope: Milestone 13 — Advanced UI/UX Reconstruction  
> Product: ListenTrace  
> UI stack: PySide6 / Qt Widgets  
> Design evidence: Human QA screenshots, M13 Prototype A, UI Design Grill Round 1, Round 2 Comparison Prototype, Round 2 human decision  
> Authority model: This file is the long-lived product design authority. The section **M13 Frozen UI/UX Design Contract** records decisions that M13 implementation must not casually reinterpret.

---

## 1. Purpose

ListenTrace is a local-first desktop learning product for intensive listening practice, transcript-centered diagnosis, cue-level replay, guided practice, shadowing, recall, quiz, and learning-history workflows.

The product already has mature functional behavior. M13 is not a feature-expansion milestone. Its purpose is to reconstruct the visual and interaction architecture so that the existing product behaves and feels like one coherent desktop learning system.

The design goal is not “make Qt prettier.”

The goal is:

> Make the current learning workflows easier to understand, easier to operate, easier to resize, calmer to study in, and more internally consistent without reopening settled domain behavior.

---

## 2. Product Design Philosophy

ListenTrace should feel like a **Warm Professional Learning Desk**:

- professional enough for long, repeated desktop use;
- calm enough for cognitively demanding listening work;
- spacious enough to reduce unnecessary visual pressure;
- structured enough that the next action and current state are immediately legible;
- focused enough that media, transcript, diagnosis, recall, and recording never compete equally for attention.

A useful shorthand is:

> **Professional workspace outside.  
> Full focus when listening.  
> Calm study surface when learning.**

The software chrome should become quieter as the learning task becomes more cognitively demanding.

---

# 3. M13 Frozen UI/UX Design Contract

The following decisions are frozen for M13 unless a genuine Product / Scope Gate proves that one of them makes the real application unusable.

## 3.1 Product Personality

**Frozen:** Warm Professional Learning Desk.

ListenTrace is not:

- a generic enterprise dashboard;
- a playful gamified language app;
- a marketing-style SaaS interface;
- an extreme minimalist showcase;
- a dense engineering IDE.

It should combine professional desktop clarity with an intentionally calm learning atmosphere.

---

## 3.2 Product-Family Relationship with Quiz Studio

ListenTrace and Quiz Studio should visibly belong to the same personal learning-product family.

Shared family traits should include:

- Professional Blue as the primary accent family;
- spacious learning-oriented composition;
- restrained card depth;
- strong typography and action hierarchy;
- clear semantic states;
- strong Light / Dark support;
- learning surfaces that visually recede behind the task;
- accessibility as a baseline, not an optional mode.

This is **family resemblance, not pixel-level cloning**.

ListenTrace retains product-specific visual modes that Quiz Studio does not need:

- full-workspace dark listening Focus Mode;
- cue-centered interaction language;
- transcript-follow and cue-selection states;
- context-sensitive paper study surfaces;
- recording / take workflows.

---

## 3.3 Accent Color

**Frozen:** Professional Blue.

The accent should communicate:

- stability;
- trust;
- mature productivity software;
- clear interaction focus;
- compatibility with long-duration use;
- visual continuity with Quiz Studio.

The exact production HEX values are implementation tokens, not immutable product semantics.

Recommended starting family for visual validation:

```text
Primary Blue:        #2563EB / #3B82F6 family
Primary Hover:       darker blue
Primary Subtle:      very light blue tint
Focus Ring:          translucent blue ring
Dark-mode Accent:    slightly brighter blue
```

Final token values may be tuned during implementation visual validation, but the design must remain recognizably **Professional Blue**, not drift into teal, orange, purple, or multi-accent branding.

---

## 3.4 Information Density

**Frozen:** Spacious Learning.

Prototype A was judged slightly too compact.

M13 should therefore prefer:

- more breathing room around primary learning content;
- fewer simultaneous controls in the immediate visual field;
- larger separation between unrelated action groups;
- readable transcript and recall spacing;
- desktop space used deliberately rather than left as accidental blank area.

“Spacious” does not mean oversized marketing whitespace.

Management-heavy screens may remain denser than active learning screens.

---

## 3.5 Global Shell

**Frozen:** Hybrid Shell.

Management-oriented views may use a persistent global shell.

Immersive learning views should visually weaken global navigation so that the learning task becomes dominant.

### Sidebar contract

The global sidebar should:

- exist where persistent global navigation has real value;
- be resizable;
- support collapse;
- permit the user to keep it collapsed when they choose that preference;
- avoid taking permanent visual priority during focused learning;
- not become the navigation container for every Guided Session stage.

Preferred implementation direction:

- use a resizable desktop layout primitive such as `QSplitter`;
- reuse existing UI-preference infrastructure where available;
- do not create a second unrelated settings mechanism solely for M13.

Exact default / min / max widths are implementation decisions to validate in the real app.

---

## 3.6 Guided Session Navigation

**Frozen:** Stage 1–5 are session-local workflow navigation.

They are not permanent first-level global navigation.

Conceptually:

```text
Global Navigation
├─ Material Library
├─ Player / Practice entry points
├─ Quiz
├─ Learning History
└─ Settings / Data / other global destinations

Guided Session
└─ Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5
```

The current stage, completed stages, available stages, and progression state should be visible inside the Guided Session experience.

Global information architecture and session workflow state must not be conflated.

---

## 3.7 Paper-Like Study Surfaces

**Frozen:** Contextual intensity by page.

Paper is a learning-surface language, not the global product theme.

### Low paper intensity

Suitable for:

- Transcript Diagnosis;
- comparison;
- evidence inspection;
- structured analysis.

Use:

- calm off-white / matte surface;
- readable line spacing;
- reduced chrome;
- modern sans-serif typography.

### Medium paper intensity

Suitable for:

- Quiz;
- guided written responses;
- structured reflection.

Use:

- calm study surface;
- stronger reading hierarchy;
- modestly increased whitespace;
- limited card depth.

### High paper intensity

Suitable for:

- Final Recall;
- extended learner writing;
- synthesis / reconstruction.

High paper intensity may use more editorial typography if visual validation shows that it improves reading and writing rather than becoming decorative.

Paper styling must never reduce accessibility, text contrast, or control discoverability.

### 3.7.1 Lined Spiral Notebook & Ruled Paper Refinement (HG-1 Closeout)

Certain text-heavy, record-like, and context-like surfaces adopt a **lined spiral notebook / ruled paper** visual language:

- **Sidebar Directory**: Narrower Acrobat-style bookmark directory with left-aligned navigation items and clean vertical rhythm.
- **Study Archive / Material List**: Ruled list presentation with horizontal row dividing lines and study-record spacing.
- **Selected Material Context / Dossier**: Spiral notebook page appearance with top wire-binding visual cues, horizontal ruled metadata rows, and subtle, low-opacity corner study stamps.
- **History & Attempt Dialogs**: Ruled-record list styling for historical sessions and quiz attempts.

This language remains disciplined, line-based, and functional—enhancing study readability and archival order without turning into a cluttered scrapbook.

---

## 3.8 Player Focus Mode

**Frozen:** Full-workspace Dark Focus Mode.

When the user enters the primary listening workspace, the experience should feel intentionally different from management screens.

The dark listening mode should cover the **whole listening workspace**, not only the video rectangle.

The purpose is attentional:

- media becomes the visual stage;
- current cue remains unmistakable;
- transcript remains highly readable;
- transport and loop controls remain accessible;
- irrelevant global chrome becomes quieter;
- nonessential badges disappear.

Focus Mode is not a separate brand.

It must remain visibly part of ListenTrace.

---

## 3.9 Cue-as-Card

**Frozen:** Cue-as-Card is an approved core interaction pattern.

A cue is one of ListenTrace’s primary learning objects.

Where appropriate, an individual cue may be represented as a reusable visual unit containing:

- timestamp / cue identity;
- transcript text;
- playing state;
- selected state;
- bounded cue-level actions;
- limited status/evidence information.

Cue cards should not become oversized dashboard cards.

The pattern should support rapid scanning and preserve transcript continuity.

---

## 3.10 Contextual State Language

**Frozen:** State communication intensity changes by scene.

### Library / History — Rich Scan

Purpose: fast global scanning.

May show relatively rich state information:

- current / resumable session;
- progress;
- completed;
- needs attention;
- archived / inactive;
- relevant evidence counts.

Badges / chips are appropriate when they improve scanning.

### Player / Focus — Quiet Focus

Purpose: protect listening attention.

Keep only states required to understand the active listening interaction:

- playing cue;
- selected cue / cue selection;
- loop state;
- transcript-follow state where relevant;
- essential playback state.

Avoid badge clouds.

Prefer:

- spatial emphasis;
- selected surface;
- clear edge / indicator;
- icon + concise text;
- restrained color.

### Guided Learning — Balanced Guidance

Purpose: guide learning without overwhelming content.

Clearly expose:

- current stage;
- completed stages;
- ready / not-ready progression;
- read-only evidence;
- needs-attention state where relevant.

State presentation must support the learning task, not become the primary content.

### Accessibility rule

No important state may rely on color alone.

Use an appropriate combination of:

- text;
- icon;
- shape / border;
- position;
- weight;
- color.

---

## 3.11 Action Hierarchy

**Frozen default:** one visually dominant Primary action per major work area.

Action roles:

### Primary
The most important next-step action.

Examples:

- Continue Session
- Save Diagnosis and Continue
- Complete Session
- Submit Quiz

### Secondary
Valid alternate actions that should not compete with the current next step.

### Quiet / Utility
Playback, filtering, refresh, settings, minor navigation, reveal, and other supporting operations.

### Danger
Destructive or abandoning actions.

Danger actions must be visually separated from normal progression.

### Disabled
Disabled controls must be understandable.

Where practical, explain why the action is unavailable rather than presenting unexplained gray controls.

### Exception rule

A genuinely complex workspace may contain two visually strong actions when they represent two equally legitimate product paths.

This is an exception requiring a clear interaction rationale, not the default composition strategy.

---

## 3.12 Card / Panel Depth

**Frozen:** Prototype A depth level is accepted.

Use:

- subtle borders;
- restrained shadow;
- moderate rounding;
- tonal surface differences;
- whitespace as the primary grouping tool.

Do not recreate the old “box inside box inside box” Qt appearance.

Do not turn the application into a SaaS card wall.

A useful hierarchy is:

```text
Spacing first
→ tonal surface second
→ border third
→ elevation only when useful
```

---

# 4. Core Design Principles

## 4.1 One Primary Task Per Screen

Within seconds, the user should understand:

1. Where am I?
2. What am I doing?
3. What is the most important next action?

Every major screen should make those answers visually clear.

---

## 4.2 Learning Content Is Louder Than Software Chrome

The product should reduce interface competition during cognitively demanding tasks.

General rule:

> software chrome quiet; learning content loud.

The denser the learning task, the less decorative or administrative UI should compete with it.

---

## 4.3 Task Flow Before Widget Placement

A screen is not a collection of controls.

Each workflow screen should be designed around:

```text
Context
→ Primary Task
→ Working Surface
→ Supporting Tools
→ Evidence / State
→ Next Action
```

Controls exist inside that hierarchy.

---

## 4.4 Resize Is Part of the Design

Desktop layout must remain useful across realistic window sizes.

Resizing should improve or reorganize content, not merely create:

- giant blank regions;
- compressed button rows;
- clipped text;
- unreachable primary actions.

Each major workspace needs explicit resize behavior.

---

## 4.5 Stable Object Language

The same domain object should feel like the same object everywhere.

Important reusable visual objects include:

- Material
- Cue
- Playing Cue
- Selected Cue / Cue Selection
- Guided Stage
- Evidence
- Recording Take
- Session

Do not invent a different visual grammar for the same object in every window.

---

# 5. Surface Modes

ListenTrace uses three related surface modes.

## 5.1 Professional Workspace

Primary use:

- Material Library;
- Learning History;
- settings / data;
- export;
- management-heavy views.

Visual behavior:

- light professional shell;
- Professional Blue accent;
- clear tables/lists;
- restrained card depth;
- higher state-information density;
- efficient desktop navigation.

---

## 5.2 Dark Listening Focus

Primary use:

- Player;
- continuous listening;
- cue replay / looping;
- playback-centered Quick Practice surfaces.

Visual behavior:

- full-workspace dark background;
- high-readability transcript;
- minimal state noise;
- blue interaction focus;
- clear cue selection / playing distinction;
- transport controls grouped close to playback context.

Dark Focus Mode must not turn into decorative “cinematic” styling that reduces usability.

---

## 5.3 Paper Study Surface

Primary use:

- diagnosis;
- recall;
- written learning work;
- selected guided-practice stages.

Visual behavior:

- calm matte surface;
- lower chrome;
- increased reading comfort;
- limited visual interruption;
- contextual paper intensity.

---

# 6. Color System

## 6.1 Accent vs Semantic Color

Professional Blue is the **interaction accent**.

Semantic colors remain semantically independent.

Do not turn every state into a blue state.

Recommended semantic roles:

- Success / completed
- Warning / needs attention
- Danger / destructive / error
- Info
- Correct
- Wrong
- Neutral / read-only

Semantic colors should not change meaning between Light and Dark themes.

---

## 6.2 Color Restraint

Avoid:

- rainbow status systems;
- a different color for every diagnosis category unless meaning truly requires it;
- decorative gradients in ordinary learning views;
- multiple competing brand accents.

Color should primarily communicate:

- interaction;
- selection;
- state;
- attention;
- semantic meaning.

---

## 6.3 Light / Dark Relationship

Light and Dark themes should remain the same product.

Do not redesign component hierarchy between themes.

Dark theme may adjust:

- contrast;
- surface luminance;
- focus-ring brightness;
- shadow behavior;
- text emphasis.

It must preserve object and state semantics.

---

# 7. Typography

Typography should prioritize long-duration readability.

Default direction:

- modern system / UI sans-serif for shell, navigation, controls, labels;
- readable sans-serif for transcript and most study content;
- optional editorial / serif treatment only where high-intensity Paper mode genuinely improves extended recall writing.

Typography hierarchy should communicate role before color does.

Expected roles:

- Window / View title
- Section heading
- Primary learning text
- Standard body
- Control label
- State label
- Metadata / timestamp
- Caption / helper text

Avoid extremely small metadata text.

Avoid using bold everywhere as a substitute for hierarchy.

---

# 8. Spacing, Alignment, and Geometry

Use a consistent spacing scale.

A practical starting scale:

```text
4 / 8 / 12 / 16 / 24 / 32 px
```

Use larger gaps between unrelated groups and smaller gaps inside a functional group.

Rounded corners should remain moderate.

Do not make every button pill-shaped.

Cards, fields, dialogs, and panels should feel related but not identical.

Alignment should make scanning easier:

- timestamps align predictably;
- action groups align consistently;
- stage progression retains a stable location;
- primary next action remains easy to reach.

---

# 9. Navigation Architecture

## 9.1 Global Navigation

Global navigation is for product destinations, not every transient workflow state.

Candidate global destinations include:

- Material Library
- Player / Practice entry point
- Quiz
- Learning History
- Settings / Data
- Export / evidence tools where appropriate

Final exact global navigation entries must reflect the existing product, not prototype-invented scope.

---

## 9.2 Session Navigation

Guided Session owns Stage navigation.

Preferred pattern:

- clear stage stepper / session navigator;
- current stage emphasized;
- completed stages identifiable;
- unavailable stages understandable;
- navigation does not crowd out the current learning task.

---

## 9.3 Contextual Navigation

Use contextual controls close to the object they affect.

Examples:

- cue actions near the cue;
- material actions in selected-material context;
- take actions beside the recording take;
- quiz progression inside the quiz workspace.

Avoid forcing every action into global navigation.

---

# 10. Object Patterns

## 10.1 Material

A Material should expose:

- identity;
- type / useful metadata;
- current learning status;
- current resumable action where relevant;
- access to material-level actions.

The primary material action should be obvious.

Avoid presenting every possible practice action with identical emphasis.

---

## 10.2 Cue

Cue visual treatment must support:

- rapid reading;
- timestamp scanning;
- playing state;
- selection state;
- actionable context;
- transcript continuity.

### Playing Cue

Playing cue and selected cue are not automatically the same concept.

Their visual states must remain distinguishable.

### Selected Cue

Selection may represent the user’s editing / practice target even when another cue is currently playing.

Do not collapse these two states into one color treatment.

---

## 10.3 Stage

A Stage is workflow state, not a global application destination.

The visual language should answer:

- current?
- completed?
- available?
- blocked / not ready?
- read-only?

---

## 10.4 Evidence

Evidence should generally be quieter than the current task.

Read-only evidence must look different from editable learner input.

Evidence may be surfaced in:

- secondary panel;
- drawer;
- supporting card;
- contextual history area.

Avoid presenting evidence as another equally dominant editor.

---

## 10.5 Recording Take

Recording Takes should feel like repeatable versions of the same practice object.

A Take presentation may contain:

- take number / identity;
- duration;
- timestamp where useful;
- selected / preferred state if the existing product supports it;
- bounded playback / deletion actions.

Do not add recording semantics merely because a prototype displayed them.

---

## 10.6 Session

Active, resumable, completed, and read-only Session states should be visibly distinct.

Session state belongs primarily in:

- Material context;
- Guided Session shell;
- History.

---

# 11. Screen Pattern Guidance

These are design patterns, not new feature specifications.

## 11.1 Material Library

Design goals:

- professional management workspace;
- high scanability;
- Rich Scan state language;
- selected material context;
- one obvious next action.

Recommended structure:

```text
Global Shell
├─ Material List / Table
└─ Selected Material Inspector / Context Area
```

Avoid:

- equal-weight action stacks;
- excessive nested boxes;
- tiny metadata;
- inactive space that does not help scanning.

---

## 11.2 Player

Design goals:

- full-workspace Dark Focus Mode;
- strong media / transcript relationship;
- playing cue immediately visible;
- selected cue separately visible;
- playback controls close to playback context;
- Quiet Focus state language.

The transcript should remain usable while media is playing.

Manual transcript navigation and auto-follow must remain understandable.

Do not visually imply changed playback semantics.

---

## 11.3 Guided Session

Design goals:

- task-first structure;
- persistent session-local stage context;
- resize resilience;
- clear completion requirements;
- low ambiguity around Save / Skip / Complete / Resume actions.

Recommended conceptual hierarchy:

```text
Session Context
Stage Progress
Current Stage Goal
Primary Working Surface
Supporting Tools / Evidence
Progression Actions
```

Avoid unused blank regions and undifferentiated button rows.

---

## 11.4 Transcript Comparison / Diagnosis

Design goals:

- calm analytical study surface;
- readable comparison;
- current cue context;
- evidence secondary to active diagnosis;
- Balanced Guidance state language.

Use paper styling at low-to-medium intensity.

---

## 11.5 Shadowing / Recording

Design goals:

- current cue remains dominant;
- source playback and recording actions are grouped clearly;
- recording state unmistakable;
- Takes scan easily;
- destructive Take actions visually isolated.

Do not let microphone controls, playback controls, Take history, and notes all compete as equal primary regions.

---

## 11.6 Final Recall

Design goals:

- strongest Paper Study mode;
- writing surface visually dominant;
- supporting evidence available without dominating;
- completion action clear;
- minimal chrome.

This should feel like a learning synthesis activity, not a generic multiline form.

---

## 11.7 Quiz

Design goals:

- focused single-question interaction;
- long text wraps naturally;
- answer choices have generous hit targets;
- progress visible but quiet;
- Submit / Next hierarchy obvious;
- playback controls demoted to supporting tools.

---

## 11.8 Learning History

Design goals:

- evidence density may be higher than learning screens;
- Rich Scan state system;
- filters / history controls remain utilities;
- detail drill-down should not overwhelm the list.

---

## 11.9 Dialogs and Settings

Design goals:

- consistent title / body / footer structure;
- Primary action visually obvious;
- Cancel / Close secondary;
- destructive actions semantic red and separated;
- disabled settings explain why when needed;
- global vs material-specific settings clearly distinguished.

Existing Loop End Grace behavior is frozen product behavior and may be re-presented, but M13 must not silently alter its semantics.

---

# 12. Resize and Desktop Responsiveness

Each major screen should define behavior across:

- comfortable desktop width;
- narrower but still supported desktop width;
- user-resized panels.

Principles:

- the primary task must remain reachable;
- text should wrap rather than truncate wherever learning meaning would be lost;
- side panels should shrink, collapse, or move before the main learning content becomes unusable;
- accidental empty space should be redistributed;
- action rows should wrap or reorganize instead of clipping.

Avoid relying only on hard minimum window sizes to solve layout problems.

---

# 13. Accessibility

Accessibility is a baseline design requirement.

M13 should preserve or improve:

- readable font sizes;
- strong text contrast;
- visible keyboard focus;
- keyboard navigation for major interactive surfaces;
- understandable disabled states;
- sufficient click targets;
- non-color-only state communication;
- reduced dependence on hover-only disclosure;
- long-text wrapping;
- predictable tab order.

Where Qt-native controls create unacceptable text truncation or interaction problems, a composite custom control may be appropriate.

---

# 14. PySide6 / Qt Widgets Implementation Mapping

M13 remains a PySide6 / Qt Widgets redesign.

A framework rewrite is out of scope.

Recommended implementation direction:

## 14.1 Theme tokens

Continue centralizing design tokens in the existing theme infrastructure where practical:

- colors;
- semantic colors;
- spacing;
- typography roles;
- radii;
- component roles;
- focus / selected / disabled states.

## 14.2 Widget roles

Prefer semantic widget properties over one-off per-window styling.

Conceptual examples:

```text
role=primary
role=secondary
role=quiet
role=danger

surface=workspace
surface=paper
surface=focus

state=playing
state=selected
state=read-only
```

Exact property names remain an implementation choice.

## 14.3 Shared components

Where M13 naturally reveals stable reusable components, prefer shared implementation.

High-value candidates may include:

- Cue Card;
- Stage Stepper;
- action footer;
- Paper Study Surface;
- state badge / status label;
- resizable / collapsible navigation shell;
- long-text quiz option card.

Do not turn M13 into a broad architecture-cleanup campaign.

---

# 15. Behavioral Fidelity / Feature-Freeze Boundary

M13 may redesign presentation and interaction architecture.

M13 must not silently change settled product semantics involving:

- playback behavior;
- loop behavior;
- Loop End Grace contract;
- transcript-follow behavior;
- persisted learning evidence;
- session lifecycle;
- quiz scoring;
- recording semantics;
- deletion ownership;
- export semantics;
- database semantics.

A prototype is visual evidence, not a source of new domain behavior.

If an attractive prototype invents product semantics that were never approved, those semantics are not inherited by implementation.

---

# 16. M13 UI Acceptance Criteria

M13 should not be considered visually complete merely because the application has consistent colors.

The reconstructed product should satisfy:

## Cognitive clarity
The current task and next action are obvious.

## Interaction economy
Primary workflows do not require unnecessary searching or repeated navigation.

## Hierarchy
Primary, secondary, utility, destructive, state, evidence, and learning content are visually distinct.

## Resize resilience
Core screens remain usable through realistic desktop resizing.

## Readability
Transcript, quiz, recall, history, and diagnostic content remain readable without truncation or unnecessary visual noise.

## Cross-window consistency
The same object and state behave visually like the same object and state across the product.

## Behavioral fidelity
Frozen product behavior remains unchanged unless explicitly approved through a Product / Scope Gate.

## Human acceptance
Representative real user journeys must be reviewed after reconstruction.

M13 visual acceptance is not the same as final release acceptance; full final hardening remains in M12 Phase 12-B after M13.

---

# 17. Change-Control Rule

The Frozen UI/UX Design Contract is not a suggestion list.

During M13 implementation:

- ordinary component-level choices may be made autonomously inside the contract;
- exact spacing / dimensions / token values may be tuned through implementation evidence;
- a design choice that contradicts a frozen item must be surfaced as a Product Design Gate;
- visual polish must not become feature expansion.

Use prototypes only where seeing alternatives would materially improve a still-unresolved decision.

Do not reopen already-resolved design axes for aesthetic experimentation alone.

---

# 18. Evidence and Provenance

This design authority was derived from:

- real ListenTrace UI screenshots and human-use observations;
- M12 Human QA findings;
- M13 UI DNA Prototype A;
- ListenTrace M13 UI Design Grill · Round 1;
- ListenTrace M13 Round 2 Prototype Comparison;
- explicit final human selection of Professional Blue;
- prior Quiz Studio UI design work used as a product-family reference.

The prototype artifacts are evidence and references.

`DESIGN.md` is the long-lived design authority.

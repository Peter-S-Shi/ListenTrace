# ListenTrace — DESIGN.md

> **Status:** Normative Rendering Authority v1.0 — Implemented and Accepted in Milestone 13  
> **Scope:** Final visual rendering, interaction styling, typography, color, paper/notebook treatment, decorative grammar, and visual acceptance.  
> **Product:** ListenTrace  
> **UI stack:** PySide6 / Qt Widgets  
> **Primary visual system:** **Notebook Study Desk**  
> **North Star:** the approved warm spiral-notebook Learning Session / Player composition and the approved final design boards for Quick Practice, Shadowing, Guided Session, Quiz/Review, Learning History, Main Library/Dossier, History dialogs, Settings, Import, and Export.  
> **Architecture relationship:** Surface architecture, workflow, persistence, domain semantics, and module composition are defined elsewhere. This document defines the normative rendering system and visual contract implemented across all 16 production surfaces in Milestone 13.

---

## 0. Authority and implementation rule

This document is the normative rendering authority for the ListenTrace Notebook Study Desk visual system, implemented and accepted across all 16 production surfaces in Milestone 13.

It supersedes older visual directions where they conflict with the approved final design boards, including:

- generic “professional dashboard” styling;
- app-wide dark listening-shell concepts;
- ordinary white SaaS cards placed on a warm background;
- inconsistent per-window button styling;
- decorative paper texture used only as wallpaper;
- ad-hoc colors, fonts, radii, and spacing chosen inside individual windows.

The **media viewport remains black/dark** because it is a media surface. The surrounding Player is a warm Notebook Study Desk, not an app-wide dark control panel.

The codebase implements this contract through `src/listentrace/ui/theme.py`, `src/listentrace/ui/widgets/notebook_paper.py`, and shared role/surface helpers (`apply_surface`, `apply_role`, `make_notebook_surface`, `make_card`). All production surfaces conform to this contract.

When maintaining or extending UI components:

1. preserve behavior and domain semantics;
2. update or reuse the central theme/shared primitives;
3. update consumers through the shared tokens/roles;
4. do not patch individual windows with local magic values unless a documented platform exception requires it.

---

# 1. Design identity — Notebook Study Desk

ListenTrace should feel like a **personal language-learning desk that has been digitized without losing the clarity of modern desktop software**.

The visual metaphor is not “a paper texture theme.” It is a coherent family of study objects:

```text
Desk
├─ Notebook
├─ Ruled Study Sheet
├─ Cue / Transcript Sheet
├─ Practice Page
├─ Material Dossier
├─ Archive / History Record
├─ Settings Form
└─ Evidence Export Worksheet
```

The product should feel:

- warm;
- intimate;
- studious;
- tactile;
- calm;
- focused;
- archival where evidence is being reviewed;
- non-corporate;
- non-gamified;
- clearly interactive.

A concise identity string for agents:

> **Warm analog study desk + personal learning journal + archival dossier + modern desktop controls.**

---

## 1.1 Paper is structure, not decoration

**Paper is Structure, not Decoration.**

A surface should use a paper/notebook form because that form helps explain the information architecture.

Examples:

- Transcript & Cues → ruled reference sheet;
- Diagnosis → diagnosis notebook;
- Recording → recording notebook;
- Final Recall → large ruled writing journal;
- Main material detail → study dossier;
- Learning History → evidence dossier/archive;
- Settings → orderly preference sheet;
- Import → compact intake sheet;
- Export → evidence-packaging worksheet.

Do **not** place a paper texture behind an otherwise generic collection of SaaS cards and call the work complete.

---

## 1.2 Modern interaction remains explicit

The physical metaphor must never reduce interaction clarity.

A checkbox still looks and behaves like a checkbox.  
A radio still behaves like a radio.  
A button still has clear normal, hover, pressed, focus, disabled, and selected states.  
A destructive action remains visibly destructive.  
Keyboard focus remains visible.  
Read-only state remains distinguishable.

The governing rule is:

> **Simulate a study object, not a historical physical object.**

---

# 2. Visual intensity by surface type

Not every window receives the same amount of notebook decoration.

| Surface class | Notebook intensity | Rendering direction |
|---|---:|---|
| Player / primary Learning Session | 5 / 5 | Full Notebook Study Desk; open-book composition; strongest physical-paper identity |
| Guided Session | 5 / 5 | Persistent study-book shell; stage pages; strong notebook chapter language |
| Quick Practice / Shadowing / Quiz | 4 / 5 | Focused practice sheets/notebooks; less decoration; one dominant task |
| Quiz Review / Main Library / Learning History | 3 / 5 | Dossier/archive language; scan-friendly structure; restrained scrapbook accents |
| Session History / Quiz History / Settings | 2 / 5 | Paper-form family; clean ruled lists/forms; little decoration |
| Import | 2 / 5 | Compact intake sheet; almost no decorative noise |
| Export | 3 / 5 | Large structured evidence worksheet; complexity handled by hierarchy, not decoration |

Rules:

- Dense information surfaces are **not** made more decorative to compensate for density.
- Small dialogs should not inherit the full open-book composition.
- Spiral binding is reserved for surfaces that genuinely read as notebook pages/modules.
- Flowers, stars, tape, paperclips, and sticky notes are accents, not mandatory badges.

---

# 3. Canonical color system

## 3.1 Color token policy

Every production color must come from a central token.

**Forbidden:**

```python
widget.setStyleSheet("color: #some-new-value")
```

inside a window merely because the local result “looks close.”

When a new semantic color is genuinely required, add a named central token and document its purpose.

All values below are the canonical **light/warm Notebook Study Desk palette**.

---

## 3.2 Macro surfaces

| Token | Hex | Use |
|---|---|---|
| `desk_bg` | `#F6F1E7` | Root workspace / warm desk background |
| `paper_primary` | `#FFFDF8` | Primary paper sheets, main notebook pages |
| `paper_secondary` | `#FAF6ED` | Secondary panels, mini notebooks, light inset areas |
| `paper_deep` | `#F3EBDD` | Deeper paper layer, directory backing, paper edge contrast |
| `sidebar_bg` | `#F0E8DC` | App directory / archive sidebar |
| `surface_plain` | `#FFFEFB` | Plain clean form/table surface when ruled paper is unnecessary |
| `media_black` | `#0F1115` | Media/video viewport only |
| `paper_edge` | `#CFC3B2` | Visible paper/card edge |
| `warm_border` | `#D8CFC1` | Ordinary panel/control border |
| `warm_divider` | `#E6DED2` | Quiet section separator |

The application should never drift back to a cold `#FFFFFF + #E5E7EB` enterprise palette.

---

## 3.3 Ink and text

| Token | Hex | Use |
|---|---|---|
| `ink_primary` | `#1F1D1A` | Main readable text |
| `ink_secondary` | `#5A5147` | Secondary text, noncritical labels |
| `ink_muted` | `#6F665C` | Helper text and low-emphasis metadata |
| `ink_caption` | `#7B7165` | Captions at 12px+ |
| `ink_placeholder` | `#948A7D` | Placeholder text only |
| `ink_disabled` | `#9B9388` | Disabled controls; never used for important active information |
| `ink_on_accent` | `#FFFDF8` | Text/icons on primary blue |
| `ink_on_dark` | `#F7F4EE` | Text over media/dark-only surfaces |

Small active text must use `ink_primary`, `ink_secondary`, or `ink_muted`.  
Do not use very low-contrast warm gray for required instructions.

---

## 3.4 Academic blue interaction family

| Token | Hex | Use |
|---|---|---|
| `accent` | `#2563EB` | Primary academic blue |
| `accent_hover` | `#1D4ED8` | Hover |
| `accent_pressed` | `#1E40AF` | Pressed |
| `accent_soft` | `#EFF6FF` | Very light selected/active background |
| `accent_selected` | `#DBEAFE` | Stronger selected row/state |
| `accent_border_soft` | `#93C5FD` | Secondary hover/focus border |
| `focus_ring` | `#60A5FA` | Keyboard focus ring |
| `rule_blue` | `#BFDBFE` | Ruled notebook line base color |
| `handwritten_blue` | `#2458B8` | Decorative handwritten labels, tape labels, pen-like headings |

Blue means **current learning action, selection, focus, or notebook ink**.  
It is not a license to make every button blue.

---

## 3.5 Notebook and paper detail colors

| Token | Hex | Use |
|---|---|---|
| `rule_blue` | `#BFDBFE` | Ruled lines; render at 52% opacity by default |
| `margin_line` | `#E6A7AD` | Vertical notebook margin line; render at 46% opacity |
| `spiral_metal` | `#7D8794` | Spiral ring base |
| `spiral_shadow` | `#4D5660` | Spiral underside/shadow at 25% opacity |
| `paper_hole` | `#E9E1D5` | Punched paper holes |
| `tape_cream` | `#E8D6A8` | Cream masking tape |
| `tape_blue` | `#91B4E4` | Blue decorative tape |
| `sticky_note` | `#F2E2B4` | Helper sticky note |
| `paperclip_metal` | `#7C858D` | Paperclip / metal detail |
| `leaf_green` | `#4F7A58` | Sparse botanical doodle |
| `flower_pink` | `#D78EA2` | Sparse flower accent |
| `star_gold` | `#D2A43A` | Decorative star outline/fill accent |

Decorative colors are never used to encode correctness, error, or workflow state.

---

## 3.6 Semantic colors

| Token | Hex | Subtle background | Use |
|---|---|---|---|
| `success` | `#168247` | `#EDF8F1` | completed, correct, success |
| `warning` | `#C87508` | `#FFF4D6` | skipped, abandoned, caution |
| `danger` | `#D9383A` | `#FDF2F2` | destructive actions, errors |
| `danger_hover` | `#BF2628` | `#FBE8E8` | destructive hover |
| `incorrect` | `#DC2626` | `#FEF2F2` | quiz incorrect result |
| `info` | `#2563EB` | `#EFF6FF` | informational active state |
| `neutral_state` | `#776E64` | `#F2EEE7` | inactive/read-only status |

Semantic colors retain meaning everywhere.

No important state may rely on color alone. Add text, icon, border, shape, or position.

---

## 3.7 Learning evidence label colors

Diagnosis label colors should be visibly distinct but not fluorescent.

| Diagnosis label | Hex |
|---|---|
| `keyword` | `#D3A83E` |
| `known_not_heard` | `#E08A3E` |
| `connected_reduced_speech` | `#5F9A69` |
| `misheard` | `#D96A76` |
| `unknown_word_or_chunk` | `#4F86D9` |

If the domain currently exposes additional labels, map them into the same muted-study palette and verify contrast.

User-customized label colors remain supported; previews must show the actual chosen color.

---

# 4. Typography contract

## 4.1 Font families

### Functional UI and learning text

Canonical stack:

```text
"Segoe UI Variable Text",
"Segoe UI Variable",
"Segoe UI",
"Microsoft YaHei UI",
"Microsoft YaHei",
"PingFang SC",
sans-serif
```

Use this for:

- transcript;
- cue text;
- questions;
- forms;
- lists;
- history;
- settings;
- buttons;
- metadata;
- diagnosis evidence;
- tables;
- errors;
- instructions.

### Handwritten personality font

For **short Latin-script decorative text only**:

```text
"Segoe Print",
"Segoe Script",
"Segoe UI"
```

Allowed for:

- tape labels;
- tiny notebook chapter tags;
- short decorative helper notes;
- optional hand-drawn title accent;
- noncritical margin annotations.

Do **not** force CJK text into a Latin handwriting font.  
Chinese/Japanese/Korean decorative labels fall back to `Microsoft YaHei UI` / the functional stack and gain personality through color, weight, tape/paper treatment, and spacing instead.

### Monospace

```text
"Cascadia Mono",
"Consolas",
"Courier New",
monospace
```

Use only for:

- playback time;
- exact timestamps where alignment matters;
- file/schema technical values where monospacing improves scanning.

---

## 4.2 Type scale

All sizes are logical pixels at 100% scale.

| Role | Family | Size | Weight | Target line height | Letter spacing | Color |
|---|---|---:|---:|---:|---:|---|
| Product / material hero title | Functional | 22px | 650 | 30px | 0 | `#1F1D1A` |
| Page title | Functional | 20px | 700 | 28px | 0 | `#1F1D1A` |
| Major notebook/page title | Functional | 16px | 700 | 23px | 0.1px | `#1F1D1A` |
| Decorative notebook tag | Handwriting | 15px | 600 | 22px | 0.2px | `#2458B8` |
| Section header | Functional | 13px | 700 | 20px | 0.6px | `#2458B8` |
| Subsection title | Functional | 14px | 650 | 21px | 0 | `#1F1D1A` |
| Standard body | Functional | 14px | 400 | 21px | 0 | `#1F1D1A` |
| Reading body / study instruction | Functional | 15px | 400 | 23px | 0 | `#1F1D1A` |
| Transcript / cue text | Functional | 16px | 500 | 26px | 0 | `#1F1D1A` |
| Dominant transcript / current cue | Functional | 17px | 600 | 27px | 0 | `#1F1D1A` |
| Final Recall writing | Functional | 17px | 400 | 28px | 0 | `#1F1D1A` |
| Quiz question stem | Functional | 16px | 650 | 24px | 0 | `#1F1D1A` |
| Form label | Functional | 13px | 600 | 19px | 0 | `#5A5147` |
| Input text | Functional | 14px | 400 | 20px | 0 | `#1F1D1A` |
| Regular button | Functional | 13px | 600 | 18px | 0 | role-specific |
| Hero button | Functional | 14px | 650 | 20px | 0.1px | role-specific |
| Caption | Functional | 12px | 600 | 18px | 0.4px | `#7B7165` |
| Helper text | Functional | 12px | 400 | 18px | 0 | `#6F665C` |
| Metadata | Functional | 12px | 400 | 18px | 0 | `#6F665C` |
| Timecode | Monospace | 11px | 500 | 17px | 0 | `#6F665C` |
| Error / warning | Functional | 12px | 600 | 18px | 0 | semantic |
| Sticky-note annotation | Handwriting | 12px | 500 | 18px | 0.1px | `#5A5147` |

---

## 4.3 Typography emphasis rules

### Bold

Use 600–700 weight for:

- active page title;
- current cue;
- question stem;
- stage title;
- selected major section;
- score/result headline;
- primary metric value.

Do not use bold for every label.

### Italic

Use sparingly for:

- quoted learner reflection;
- helper/example text;
- a very short handwritten-like note when it improves voice.

Do not italicize transcript, question stems, form labels, or history rows.

### Underline

Do not use underline as ordinary emphasis. Reserve it for:

- true link-like actions where applicable;
- rare notebook annotation effect that is noninteractive and clearly decorative.

### Highlight

Use background highlight rather than text color alone.

Canonical learning highlights:

```text
Current/selected:      #EFF6FF
Stronger selection:    #DBEAFE
Active cue:            #FFF3CD
Correct:               #EDF8F1
Incorrect:             #FEF2F2
Warning/skipped:       #FFF4D6
```

### All caps

Allowed only for short functional section stamps such as:

```text
TRANSCRIPT & CUES
STUDY ARCHIVE
RECORDING NOTEBOOK
```

Use actual uppercase strings rather than relying on unsupported QSS text transforms.

Max recommended length: **28 characters**.

---

## 4.4 Typography spacing

Default vertical distances:

| Relationship | Gap |
|---|---:|
| Page title → subtitle | 4px |
| Page title block → first major region | 16px |
| Section header → section content | 8px |
| Form label → field | 4px |
| Paragraph → related helper text | 4px |
| Paragraph → unrelated next group | 12px |
| Notebook title → first content row | 8px |
| Error text → recovery action | 8px |
| Transcript row vertical padding | 8px top + 8px bottom |

For multi-line reading text, never fake line-height by inserting blank lines. Prefer widget/document margin/paragraph spacing.

---

# 5. Spacing, density, and geometry

## 5.1 Canonical spacing scale

```text
SPACE_XXS = 4px
SPACE_XS  = 6px
SPACE_S   = 8px
SPACE_M   = 12px
SPACE_L   = 16px
SPACE_XL  = 24px
SPACE_XXL = 32px
```

The codebase may keep existing symbolic names, but values should converge on this scale.

---

## 5.2 Layout geometry

| Element | Required value |
|---|---:|
| Main workspace outer margin | 24px |
| Compact dialog outer margin | 16px |
| Major section gap | 16px |
| Related control gap | 8px |
| Tight inline gap | 6px |
| Card/notebook internal padding | 16px |
| Dense history/export internal padding | 12px |
| Mini notebook internal padding | 12px |
| Splitter visual gutter | 8px |
| Open-book spiral binding strip | 28px |
| Sidebar default width | 190px |
| Sidebar practical minimum | 150px |
| Section directory practical maximum | 210px |

Responsive layouts may reduce a 16px gap to **12px**, but never below 8px without a documented compact-mode reason.

---

## 5.3 Control sizes

| Control | Minimum height |
|---|---:|
| Hero primary button | 40px |
| Standard button | 34px |
| Compact utility button | 30px |
| Line edit / combo box | 34px |
| Checkbox / radio interactive row | 30px |
| Tab / chapter selector | 34px |
| Standard list row | 36px |
| Dense evidence/history row | 32px |
| Transcript/cue row | 44px |
| Stage stepper item | 44px |
| Error/warning banner | 38px plus wrapping |

Recommended horizontal button padding:

```text
Hero:      16px
Standard:  12px
Compact:   10px
```

Icon-text gap: **6px**.

---

## 5.4 Radii and borders

```text
Control radius:       6px
Paper/card radius:   10px
Small tag radius:     4px
Pill radius:         only for true badge/chip semantics
Standard border:      1px
Strong focus border:  2px
```

Do not use 16–24px rounded SaaS cards.

Do not make navigation, primary buttons, or ordinary form controls into pills.

---

# 6. Paper, notebook, and physical-layer rendering

## 6.1 Ruled paper

Canonical ruled paper:

```text
Paper:          #FFFDF8
Rule color:     #BFDBFE at 52% opacity
Rule spacing:   28px
Rule thickness: 1px
Margin line:    #E6A7AD at 46% opacity
Margin width:   1px
```

Ruled lines should remain anchored to document coordinates when text areas scroll.

They belong **under** text, never over it.

---

## 6.2 Spiral binding

Canonical open-book / notebook binding:

```text
Binding strip width:     28px
Ring visual pitch:       32px target
Ring pitch tolerance:    28–36px when height adapts
Metal:                   #7D8794
Metal shadow:            #4D5660 at 25%
Paper hole:              #E9E1D5
```

The binding is a structural separator.

Do not place a spiral strip between two regions merely to decorate them.

---

## 6.3 Paper shadows

Qt Style Sheets do not provide a reliable cross-platform box-shadow. Use `QGraphicsDropShadowEffect` only where the physical-paper layer benefits from it.

Canonical paper shadow:

```text
Color:   #5B4935
Opacity: 14%
X:       0px
Y:       3px
Blur:    10px
```

Mini-paper shadow:

```text
Color:   #5B4935
Opacity: 10%
X:       0px
Y:       2px
Blur:    6px
```

Do not shadow every container.

Hierarchy:

```text
spacing
→ paper tone
→ border
→ physical shadow when it clarifies layering
```

---

## 6.4 Paper edges and layering

Use `paper_edge #CFC3B2` only where the eye should perceive a separate sheet.

A ruled list inside a larger dossier does **not** need a second heavy card edge.

Avoid:

```text
card
  └ card
      └ card
          └ card
```

---

# 7. Button and interaction language

## 7.1 Core rule

> **One region, one visual hero.**

The primary progression/action button must be instantly identifiable.

Supporting playback, utility, and exit actions must not compete with it.

---

## 7.2 Primary / Hero

Use for the current major next action:

- Open Player;
- Start Practice;
- Reveal & Continue;
- Save & Continue;
- Submit Quiz;
- Import;
- other equivalent major progression actions.

Canonical rendering:

```text
Background normal:   #2563EB
Background hover:    #1D4ED8
Background pressed:  #1E40AF
Text/icon:           #FFFDF8
Border:              #2563EB
Focus ring:          #60A5FA, 2px
Height:              40px hero / 34px ordinary primary
Radius:              6px
Font:                14px / 650 hero; 13px / 600 ordinary
```

Disabled:

```text
Background: #DDD7CE
Border:     #D1CAC0
Text:       #91897E
```

Never use a primary-blue fill merely because an action is clickable.

---

## 7.3 Secondary

Use for valid alternate actions:

- Replay;
- Loop;
- Quick Practice;
- Save Diagnosis;
- Apply;
- history/open alternatives.

```text
Background normal:   #FFFDF8
Background hover:    #EFF6FF
Background pressed:  #DBEAFE
Text:                #2A2723
Border normal:       #CFC3B2
Border hover:        #93C5FD
Focus ring:          #60A5FA, 2px
Height:              34px
Radius:              6px
Font:                13px / 600
```

---

## 7.4 Quiet / Utility

Use for:

- Close;
- Refresh;
- settings links;
- Hide Transcript;
- minor navigation;
- low-frequency helpers.

```text
Background normal:   transparent
Background hover:    #F3EEE6
Background pressed:  #EAE3D8
Text normal:         #5A5147
Text hover:          #1F1D1A
Border:              transparent
Optional border:     #D8CFC1 when spatial affordance is needed
Height:              30–34px
```

Quiet does not mean invisible.

---

## 7.5 Danger

Use for:

- Delete;
- Remove Material;
- Abandon Session;
- destructive history removal.

```text
Background normal:   #FFFDF8
Background hover:    #FDF2F2
Background pressed:  #FBE8E8
Text:                #D9383A
Border:              #D9383A
Focus ring:          #EF9A9B
Height:              34px
Radius:              6px
Font:                13px / 600
```

Danger actions must be spatially separated from normal progression whenever practical.

Do not use a filled red button unless the destructive action is itself a confirmation dialog’s unambiguous final destructive commit.

---

## 7.6 Selected / Active controls

Selected rows, modes, stages, and active choices:

```text
Background:  #EFF6FF
Strong bg:   #DBEAFE
Border:      #2563EB
Text:        #1F1D1A
Indicator:   #2563EB
```

The selected state must remain visible without relying only on blue.

Use at least one:

- filled indicator;
- border;
- check;
- active marker;
- bold label.

---

## 7.7 Tabs vs executable buttons

A tab/chapter selector should look like a **paper index tab**:

- flatter;
- connected to its page;
- no hero-button fill;
- selected state indicated by blue ink underline/border/background.

An executable action should retain a button shape and press state.

The user should be able to distinguish “switch surface” from “perform action” before reading the label.

---

## 7.8 Playback-action restraint

Playback controls are tools, not progression.

`Play`, `Replay Cue`, `Loop Cue`, `Previous Cue`, `Next Cue`, and `Loop Settings` should normally be Secondary or Quiet.

They must not visually outrank:

- Continue;
- Submit;
- Complete;
- Start Recording when recording is the current central task.

---

# 8. Native control rendering

## 8.1 Inputs

LineEdit / ComboBox:

```text
Background:      #FFFDF8
Border:          #CFC3B2
Text:            #1F1D1A
Placeholder:     #948A7D
Hover border:    #B7AA98
Focus border:    #2563EB
Focus ring:      #93C5FD
Height:          34px
Radius:          6px
Horizontal pad:  10px
Font:            14px / 400
```

Read-only:

```text
Background: #F4EFE7
Border:     #D8CFC1
Text:       #5A5147
```

Invalid:

```text
Border:     #D9383A
Background: #FDF2F2
```

---

## 8.2 Checkboxes and radios

- Interactive row minimum: 30px.
- Indicator target: 16px.
- Label gap: 8px.
- Selected check/fill: `#2563EB`.
- Focus ring: `#60A5FA`.
- Disabled text: `#9B9388`.
- Never replace a real checkbox/radio with a decorative doodle that loses keyboard semantics.

---

## 8.3 Lists

Standard ruled-list row:

```text
Background normal:    transparent
Divider:              #BFDBFE at 35%
Hover:                #F7F4ED
Selected background:  #EFF6FF
Selected border:      #2563EB
Text:                 #1F1D1A
Secondary text:       #6F665C
```

Rows should not look like isolated pill cards.

---

## 8.4 Scrollbars

Scrollbars should be quiet and desktop-readable.

```text
Track:       transparent / #F3EEE6 when needed
Thumb:       #B9B0A4
Thumb hover: #91877B
Width:       10px
Minimum thumb length: 28px
```

Do not use oversized web-style overlay scrollbars.

---

## 8.5 Sliders

```text
Groove:        #D8CFC1
Active groove: #2563EB
Handle:        #2563EB
Handle hover:  #1D4ED8
Handle size:   14px
Groove height: 4px
```

Media volume is controlled via the standard horizontal slider component.

---

## 8.6 Stepper states

Guided Stage Stepper:

### Current

```text
Background: #EFF6FF
Border:     #2563EB
Badge:      #2563EB
Badge text: #FFFDF8
Label:      #1F1D1A, 700
```

### Completed

```text
Background: #FFFDF8
Border:     #168247
Badge:      #168247 with ✓
Label:      #1F1D1A
```

### Skipped

```text
Background: #FFFDF8
Border:     #C87508
Badge:      #C87508 with –
Label:      #6F665C
```

### Future / unavailable

```text
Background: #FAF6ED
Border:     #D8CFC1
Badge:      #E3DDD4
Label:      #91897E
```

Minimum height: **44px**.

---

# 9. Information hierarchy and desktop composition

ListenTrace is a desktop workspace, not a vertically scrolling website.

Prefer:

```text
master → detail
directory → workspace
archive → dossier
reference → action surface
left page → right page
persistent shell → changing stage content
```

Avoid turning major screens into one long stacked web page when a stable desktop split communicates the workflow more clearly.

---

## 9.1 Scroll ownership

Scrolling should belong to the content region that owns the overflow.

Examples:

- Transcript sheet scrolls internally.
- Annotation/evidence list scrolls internally.
- Recording takes list scrolls internally.
- History workspace scrolls internally where necessary.
- Player should not acquire a giant whole-window scrollbar merely because Annotation grows.

A stable shell should remain stable while its intended evidence/content region scrolls.

---

# 10. Decorative motif grammar

Decorative motifs must feel **discovered, not repeated**.

## 10.1 Allowed motifs

### Star

Use for:

- optional hero/learning identity accent;
- completion flourish;
- notebook personality.

Canonical size: **18–22px**.  
Color: `#D2A43A` or handwritten blue outline.

### Botanical doodle / flower

Use to soften a genuinely empty paper corner.

Canonical size: **16–24px**.

Colors:

```text
Leaf:   #4F7A58
Flower: #D78EA2
```

Do not place decorative botanicals next to errors, dangerous actions, or dense data.

### Paperclip

Use as an attachment/material/paper-layer accent.

Canonical size: **18–22px**.  
Color: `#7C858D`.

### Tape

Use for:

- notebook title tag;
- chapter label;
- small attached-note illusion.

Canonical dimensions:

```text
Height: 14–20px
Width:  44–90px depending on label
```

Cream: `#E8D6A8`  
Blue: `#91B4E4`

### Sticky note

Use only for short helper/caution/context text.

```text
Background: #F2E2B4
Text:       #5A5147
Padding:    10px
Radius:     2–4px
```

A sticky note is **not** a substitute for an error banner or required instruction.

---

## 10.2 Decoration budget

Default maximum visible decorative motifs in one major viewport:

- Player / Guided: **3** small motifs, excluding structural spiral/tape.
- Quick / Shadowing / Quiz: **2**.
- Main / History / Review: **2**.
- Settings: **1**.
- Import: **0–1**.
- Export: **1**.

Structural notebook features do not count as decorative motifs.

The explanatory sticky notes seen around design-board mockups are **not product UI**.

---

# 11. Interface sound policy — Decorative UI audio explicitly excluded

ListenTrace is a dedicated listening-training application. Decorative interface sound effects (paper rustles, pencil ticks, UI button clicks, completion stamps, and folder navigation sounds) are **explicitly excluded from the product design contract**.

Additional UI sounds create auditory competition and cognitive interference during intensive foreign-language listening practice.

All auditory capabilities in ListenTrace are reserved exclusively for authentic learning audio:

- media playback;
- cue replay and loop practice;
- volume and mute controls;
- microphone recording capture;
- learner take playback;
- source-versus-take comparison.

All interface actions communicate state changes through visual clarity, state tokens, and accessible visual feedback rather than decorative UI sounds.

---

# 12. Accessibility and cognitive clarity

## 12.1 Contrast

Targets:

- normal text: WCAG AA 4.5:1 minimum;
- large text: 3:1 minimum;
- focus indicator: clearly distinguishable from surrounding border;
- interactive state must never be color-only.

`ink_caption #7B7165` is the lightest canonical active text color intended for 12px+ captions on `paper_primary`.

Do not use `ink_placeholder` for active instructions.

---

## 12.2 Focus

Keyboard focus:

```text
Color: #60A5FA
Width: 2px
Offset: 1px where implementation permits
```

Do not remove native focus semantics solely for aesthetics.

---

## 12.3 Learning psychology

The visual system must protect the learning sequence.

Examples:

- Quick Practice Step 1 keeps transcript hidden.
- Transcript reveal becomes visually meaningful only after recall commitment.
- Diagnosis appears after listening/recall rather than competing with it.
- Recording becomes visually dominant when shadowing is the current task.
- Final Recall provides a large, quiet writing surface.
- Danger actions remain separated from progression.
- Dense evidence browsers prioritize scanning over decoration.

The interface should reduce extraneous cognitive load, not merely look handcrafted.

---

# 13. Surface-specific rendering notes

These notes do **not** redefine architecture.

They describe how the already-approved architecture should be rendered.

---

## 13.1 Player / Learning Session

Visual intensity: **5 / 5**.

- Warm open-book / Notebook Study Desk is the visual North Star.
- Media viewport remains black/dark inside the warm desk.
- Transcript & Cues is a ruled study sheet.
- Annotation is a lined notebook page.
- Playback / Loop & Practice / Utility are mini notebooks.
- Strong central spiral binding is allowed.
- Decorative motifs may be slightly richer here than elsewhere.
- The whole application must not become dark merely because the media rectangle is dark.

---

## 13.2 Quick Practice Setup

Visual intensity: **3 / 5**.

- Practice Setup / Selection Sheet.
- Recommended vs Selected is the major decision.
- Transparent recommendation reasons remain readable.
- No Playback/Diagnosis/Recording notebooks at setup.
- Start Practice is the single hero.

---

## 13.3 Quick Practice Run

Visual intensity: **4 / 5**.

- Persistent compact context shell.
- Step-specific notebook/sheet modules swap rather than accumulating.
- Step 1: Playback + Recall.
- Step 2: Diagnosis.
- Step 3: Playback + Recording.
- Step 4: Summary sheet.
- Progression action is visually dominant.

---

## 13.4 Shadowing

Visual intensity: **4 / 5**.

- Cue/Playback support above.
- Recording Notebook is the visual center.
- Takes remain a scan-friendly list.
- Recording Start/Stop receives the strongest interaction emphasis.
- Delete controls remain isolated.

---

## 13.5 Guided Session

Visual intensity: **5 / 5**.

- Persistent shell and 5-stage chapter stepper.
- The center page changes by stage.
- Stage 1–2 are quiet and low-stimulus.
- Stage 3 is the densest evidence workspace.
- Stage 4 centers Recording.
- Stage 5 is a large ruled Final Recall Journal.

---

## 13.6 Quiz

Visual intensity: **4 / 5**.

- Focused Question Canvas.
- Question/media region + answer region + Learning Flow Action Bar.
- Do not turn each answer into an oversized card.
- Submit remains hero when eligible.

---

## 13.7 Quiz Review

Visual intensity: **3 / 5**.

- Post-submission evidence surface.
- Question Directory + Answer Analysis/Feedback.
- Correct/incorrect semantics are clear but restrained.
- Learner answer, correct answer, and feedback must remain typographically distinct.

---

## 13.8 Learning History

Visual intensity: **3 / 5**.

- Dossier / evidence-browser language.
- Left directory remains stable.
- Right workspace is scan-oriented.
- Charts/lists stay modern and readable; do not spiral-notebook every table.
- “Needs Attention” remains transparent reasons, never a ranking.

---

## 13.9 Main Library / Dossier

Visual intensity: **3 / 5**.

- App Directory → Study Archive → Material Study Dossier.
- Open Player is the hero action.
- Practice, Quiz, Utility, and Danger action groups remain visibly hierarchical.
- Archive list is ruled and scan-friendly.
- Dossier gets more physical-paper identity than the archive list.

---

## 13.10 Session History / Quiz History

Visual intensity: **2 / 5**.

- Sibling dialog family.
- Header + ruled history list + bottom action bar.
- Active rows cannot be deleted.
- Open is primary; Delete is danger; Close is quiet.
- No extra charts or dashboard panels.

---

## 13.11 Settings family

Visual intensity: **2 / 5**.

- Global Settings (Playback and Label Colors) and Material Loop Settings share visual chrome.
- Global scope vs per-material override must be immediately legible.
- Inherit / Custom / Reset-to-Global semantics must not be visually collapsed.
- Label Colors is lighter and more visual; include a real preview.

---

## 13.12 Import

Visual intensity: **2 / 5**.

- Compact Material Intake Sheet.
- File sources → metadata → validation → actions.
- Inline validation.
- Duplicate confirmation is a second dialog state, not an expanded wizard.
- Keep the interface small and focused.

---

## 13.13 Export

Visual intensity: **3 / 5**.

- Large Learning Evidence Export Workspace.
- Scope and date define the export boundary.
- Evidence categories remain structured and selectable.
- Privacy Review is prominent.
- Preview is read-only.
- Save / Copy / Evaluation actions remain distinct.
- Complexity is handled through hierarchy, not decoration.

---

# 14. Implementation rules for CC / AG2.0

## 14.1 Centralize tokens

Prefer:

```text
theme.py
shared notebook primitives
shared button/control roles
```

Avoid:

```text
window-local magic hex
window-local arbitrary font sizes
window-local one-off radii
window-local duplicated notebook painters
```

---

## 14.2 Shared primitives before local styling

When an approved visual object exists in multiple surfaces, improve/reuse the shared primitive.

Examples:

- Playback Notebook;
- Diagnosis Notebook;
- RecordingPanel / Recording Notebook;
- Transcript & Cues Sheet;
- Learning Flow Action grammar;
- ruled paper;
- spiral binding;
- notebook page;
- history ruled list;
- settings section.

Do not create a universal mega-widget with dozens of configuration flags merely to claim reuse.

Reuse the proven semantic seam.

---

## 14.3 Qt implementation notes

Some visual requirements are not reliable QSS properties.

Use the correct Qt mechanism:

- letter spacing → `QFont.setLetterSpacing`;
- drop shadow → `QGraphicsDropShadowEffect`;
- ruled paper / spiral rings → `QPainter`;
- uppercase labels → uppercase source string;
- text document paragraph spacing → `QTextDocument` / block formatting;
- real focus / keyboard semantics → native QWidget/QAbstractButton behavior.

Do not fake unsupported QSS behavior and assume it works because the stylesheet parses.

---

## 14.4 No visual feature may reopen domain behavior

Rendering work must preserve:

- persistence;
- workflow state machines;
- history ownership;
- quiz scoring;
- diagnosis range semantics;
- recording ownership;
- loop-grace inherit/custom policy;
- active/completed/abandoned semantics;
- accessibility and keyboard behavior.

If a rendering requirement appears to require a domain change, stop and surface it as a Product/Scope Gate.

---

## 14.5 Reference-image usage

Approved design boards are **final appearance references**, not literal pixel maps.

Use them for:

- hierarchy;
- palette;
- paper/notebook language;
- action emphasis;
- density;
- decoration restraint;
- typography personality;
- spatial composition.

Do not copy explanatory annotations, arrows, board titles, or external design notes into the actual application.

---

# 15. Rendering acceptance checklist

A surface is not visually complete until all applicable checks pass.

## 15.1 Color

- [ ] No arbitrary local hex values without a documented token.
- [ ] Root background is warm desk, not cold gray/white.
- [ ] Paper surfaces use the canonical paper family.
- [ ] Academic Blue is reserved for interaction/focus/ink emphasis.
- [ ] Danger, warning, success, incorrect colors keep stable semantics.
- [ ] Disabled/read-only states are recognizable.
- [ ] Small active text meets contrast requirements.

## 15.2 Typography

- [ ] Functional text uses the canonical UI/CJK stack.
- [ ] Handwritten font appears only in short decorative Latin labels.
- [ ] Transcript/cue text is 16–17px and comfortable for long study.
- [ ] Final Recall writing is 17px with generous line spacing.
- [ ] Buttons use 13–14px semibold text.
- [ ] Captions are not microscopically small.
- [ ] Bold is used for hierarchy, not everywhere.
- [ ] CJK fallback has been visually checked.

## 15.3 Geometry

- [ ] Outer margins and group spacing follow the canonical scale.
- [ ] Hero buttons are visually stronger without being oversized.
- [ ] Standard controls meet minimum heights.
- [ ] Cards use 10px radius; controls use 6px.
- [ ] Ordinary controls are not pills.
- [ ] Dense surfaces remain scan-friendly.

## 15.4 Paper/notebook language

- [ ] Paper is structural, not wallpaper.
- [ ] Ruled lines use 28px spacing and pale blue.
- [ ] Spiral binding appears only where semantically justified.
- [ ] Paper shadows are restrained.
- [ ] No box-inside-box-inside-box card wall.

## 15.5 Buttons and states

- [ ] One visual hero per region.
- [ ] Secondary/Quiet actions do not compete with progression.
- [ ] Danger actions are isolated.
- [ ] Tabs look different from executable buttons.
- [ ] Hover, pressed, focus, selected, disabled, read-only states all exist.
- [ ] Focus remains keyboard-visible.

## 15.6 Decoration

- [ ] Decoration budget is respected.
- [ ] Design-board explanatory sticky notes are not present in production.
- [ ] Flowers/stars/tape/paperclips are sparse and purposeful.
- [ ] Dense data and error zones remain decoration-free.

## 15.7 Learning audio integrity

- [ ] Media playback starts cleanly without UI audio contamination.
- [ ] Replay, cue navigation, and loop endpoints operate without synthetic clicks.
- [ ] Microphone recording and take review preserve authentic audio signals.
- [ ] All action feedback is provided visually with accessible state indications.

## 15.8 Platform verification

Human-check on Windows:

- [ ] 100% scale.
- [ ] 125% scale.
- [ ] 150% scale.
- [ ] Chinese/CJK material title.
- [ ] Long English title.
- [ ] Long button labels.
- [ ] Keyboard-only navigation.
- [ ] Hover/focus/disabled/read-only states.
- [ ] Real video / QVideoWidget composition.
- [ ] Recording device list.
- [ ] Long transcript and long history evidence.
- [ ] Smallest supported practical window.
- [ ] Maximized window.

---

# 16. Final visual test

Before accepting a rendered surface, ask:

1. Does it look like part of the same **Notebook Study Desk** as the approved Player/Learning Session?
2. Is the learning content louder than the software chrome?
3. Is the most important next action immediately obvious?
4. Does paper explain structure, or is it merely decoration?
5. Are colors and fonts exact tokens rather than “close enough” approximations?
6. Is the surface appropriately restrained for its visual-intensity class?
7. Does it still behave like a precise modern desktop application?
8. Would removing the decorative motifs leave a coherent, usable information architecture?
9. Does the interface communicate state changes purely visually without competing audio?
10. Does the result feel like **ListenTrace**, not a generic SaaS dashboard wearing a notebook skin?

The intended final impression is:

> **A warm, personal, tactile study desk where listening, diagnosis, shadowing, quizzes, and learning evidence live in one coherent journal system — with modern desktop clarity underneath every paper and notebook surface.**

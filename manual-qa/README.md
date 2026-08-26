# ListenTrace Manual QA

Originated as a retroactive full-product manual QA baseline (Milestone
12.1-A). This is a living artifact: it established the pre-M12 baseline and
was exercised in Human QA Round 1 (Milestone 12). **Its current active run
is Milestone 14 Human QA Round 2 / Full Manual Regression**, executed
against the final Notebook Study Desk UI (Milestone 13) with M14 Corrective
Batches A/B/C all complete (see `PROJECT_STATUS.md`/`ROADMAP.md`). The
questionnaire itself carries this identity in its own on-page Purpose text
and via `META.questionnaireVersion`.

## Purpose

`manual_review_questionnaire.html` is a single-file, offline, bilingual
(Chinese/English) checklist covering every user-visible ListenTrace workflow:
material import, the synchronized player, the transcript workspace/diagnosis,
Guided Intensive Listening, Quizzes, Shadowing/Recording, Quick Practice,
Learning History, Export, cross-module/restart recovery, privacy/local-data
boundaries, accessibility/responsiveness, and performance/stability, plus an
overall subjective/release-blocker module. It exists to catch real functional
defects, cross-module inconsistencies, data risks, and UX problems that
automated tests and an AI agent are unlikely to notice on their own —
originally feeding Milestone 12 (Product Hardening & Full Manual Acceptance),
and now feeding Milestone 14 Human QA Round 2 and later regression/
release-candidate acceptance.

## How to launch the product

Dev environment (see the repo root `README.md`):

```bash
.venv/Scripts/python -m listentrace.ui.app
```

Or launch a build already produced under `packaging/` (the Inno Setup
installer or the portable zip), if you are specifically validating a packaged
build rather than a dev run.

## How to open the questionnaire

Double-click `manual_review_questionnaire.html`, or open it with
`File > Open` in any desktop browser. No build step, no server, no network
access — it works fully offline.

## Sample usage order

Samples live under `samples/` (see `samples/README.md` for what each file is
for). Each module in the questionnaire names the exact files it needs in its
"Samples used" field. Recommended order:

1. Module 01 (Material Import) first — this is where every sample subtitle
   and the sample audio actually get imported into the library.
2. Modules 02-09 then reuse the materials created in Module 01.
3. Module 13 (Performance) may reuse `boundary_stress.srt` again for a larger
   cue-list stress check.

You do not need your own real media/subtitle files to complete the baseline —
everything is synthetic. Using your own real material afterward as an
additional, informal pass is welcome but out of scope for this baseline.

## How results are saved

- Every field autosaves to this browser's `localStorage`, under a key
  specific to the exact `questionnaireVersion` currently open
  (`listentrace_manual_qa_v1__<questionnaireVersion>`, e.g.
  `listentrace_manual_qa_v1__2026-08-26.2`). This is per-browser, per-machine
  — it is not a hand-off mechanism by itself.
- **Version isolation (M14 Human QA Round 2 readiness corrective)**: this
  per-version key means a browser that still has saved state from an older
  questionnaire version (e.g. the original M12.1-A baseline, or any earlier
  M14 draft) can never silently populate a fresh run of the current version
  — opening a version for the first time always starts blank. `loadState()`
  also independently checks the stored `questionnaireVersion` matches before
  loading, as a second guard. Old versions' saved data is never deleted or
  auto-migrated; it simply sits under its own key until you deliberately
  revisit that version or explicitly import it (see below).
- Before closing the browser, or when you want to hand off progress, click
  **Export JSON**. This produces a single JSON file containing every item's
  status/evidence/suggestions, the questionnaire's own item definitions
  (so it stays interpretable even if the checklist evolves later), your
  tester code, environment, and app version/commit.
- **Export Markdown report** produces a human-readable report of the same
  data, grouped by module, for quick reading or pasting into an issue.
- **Print / Save PDF** uses the browser's print dialog; the print stylesheet
  expands every module so nothing is cut off by the on-screen single-module
  view.
- **Reset questionnaire** requires a second, explicit confirmation click and
  only clears the *current version's* saved answers — it never touches the
  sample files, the questionnaire HTML itself, or another version's saved
  state under its own key.
- **Import JSON**: importing a file whose `questionnaireVersion` matches the
  currently open one merges normally. Importing a file from a **different**
  `questionnaireVersion` (e.g. an old M12.1-A export, or an earlier M14
  draft) shows an explicit confirmation naming both versions before
  proceeding — this is deliberately not silent, since merging a mismatched
  version's answers into what's supposed to be a fresh Round 2 result would
  make that result ambiguous. Use this only when you genuinely want to bring
  in a historical result as reference; cancel it for anything else.

## Handing a result back to an Agent

Save the exported JSON under `results/` (a local, non-committed folder — see
below) and point the Agent at that file, or paste/attach it directly. The
JSON's `schemaVersion`/`questionnaireVersion` fields let the Agent judge
whether it matches the current questionnaire before treating it as
authoritative. The JSON re-imports cleanly back into the same HTML (via
**Import JSON**) if you want to keep filling it in rather than have an Agent
read it directly.

## What's safe to commit vs. what stays local

- Safe to commit after a privacy pass: `manual_review_questionnaire.html`,
  this `README.md`, `samples/README.md`, and the sample files themselves
  (all synthetic, see `samples/README.md`).
- Stays local by default: anything under `results/` (filled-in JSON/Markdown
  exports). These are excluded via `.git/info/exclude` rather than the
  shared `.gitignore`, per this repo's privacy policy in the root
  `CLAUDE.md`/`AGENTS.md`. Do not add real, filled-in results to Git without
  explicit approval, and re-check their content for anything sensitive first
  (see the questionnaire's own privacy reminder at the top of the page).
- Nothing here is auto-committed or auto-pushed by design.

## Using this for Hardening and regression
 
- Milestone 12: Human QA Round 1 used this questionnaire to surface
  systemic findings, resolved in Batches A-C, History Deletion, and Loop End Grace.
- Milestone 14: run the full questionnaire as the full manual regression
  pass against the finalized post-M13 UI; failed/blocked items become the Milestone 14
  defect inventory.
 - After a repair batch: only re-run the affected modules/items, not the
   whole questionnaire, unless the change is broad.
 - Before a release candidate: run the full questionnaire again as the final
   regression pass; keep the internal, detailed version for that. A simplified
  external-tester version may be derived from it later (see the source
  prompt's "future maintenance" section) but is not part of this baseline.
- When product behavior changes: update only the affected module(s) in the
  HTML, add any new samples needed, and bump `questionnaireVersion` at the
  top of the script — do not regenerate the whole file unless the product's
  architecture changes substantially. Keep old result JSONs importable, or
  document the compatibility break explicitly if a field has to change shape.

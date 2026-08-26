# ListenTrace v1.0.0 — Release Notes (Draft, Milestone 15.3)

**Status: draft, prepared during Milestone 15.3 (Release Candidate Closure & Delivery), which is now
complete.** No `v1.0.0` tag or GitHub Release has been created yet — that remains a Product Owner
publication decision after Milestone 15 closure. This document is written for the Product Owner
and, eventually, real users; it is not itself a release announcement.

## Validated release payload (locked)

**The canonical v1.0.0 release payload is the exact Milestone 15.2 human-validated candidate, and only
that candidate** — version `1.0.0`, source commit `661bca47ce93f1a12a6a17c66f1ed6065d816e43`, artifact
bundle `ListenTrace-1.0.0-candidate-661bca47ce93f1a12a6a17c66f1ed6065d816e43` (`ListenTrace-Setup-1.0.0.exe`,
`ListenTrace-1.0.0-win64-portable.zip`, `SHA256SUMS.txt`, `provenance.json`), produced by the Milestone
15.1 GitHub Actions release-candidate pipeline and installed/exercised end-to-end on a genuinely clean
Windows 11 VM during Milestone 15.2.

**Test what we ship; ship what we tested.** Later docs-only commits on this branch (including this M15.3
closure work) intentionally advance the branch HEAD past `661bca47...` for governance/documentation
purposes, and each such commit's own CI run produces its own workflow artifact bundle under a different
commit SHA. Those later, automatically generated bundles are **not** a substitute release payload — no
product/application code changed after `661bca47...`, so rebuilding merely to match SHAs would trade a
human-validated binary for an unvalidated one for no real benefit. When the Product Owner is ready to
tag and publish `v1.0.0`, the release payload attached to that tag/Release must be the `661bca47...`
artifact bundle specifically, not whatever the merge commit's own CI run happens to produce.

Checksums (downloaded and independently re-verified with `sha256sum` against the GitHub Actions
artifact for workflow run `33005303492`, which built commit `661bca47...`):

```
71cdf8c8b1d6167042153ae5861123bf51abf29bea8584e6e88363a998513200  ListenTrace-1.0.0-win64-portable.zip
d174cf0304675979d908c4f9abeff951b393a4525928882cf4fd83a8480135d7  ListenTrace-Setup-1.0.0.exe
```

`provenance.json` for this build records `product: ListenTrace`, `version: 1.0.0`,
`commit: 661bca47ce93f1a12a6a17c66f1ed6065d816e43`, `workflow_run_id: 33005303492`, and
`automated_tests: {passed: 972, result: pass}` — consistent with the Milestone 15.2 candidate under
test and with this closure's own final full-suite result (see "Final Verification", below).

## What ListenTrace v1.0.0 is

A local-first desktop application (Windows) for transcript-guided foreign-language listening practice
and listening-error diagnosis: import audio/video with a subtitle track, then practice against
individual cues through a synchronized player, a five-stage Guided Intensive Listening workflow, quizzes
generated from your own material and diagnosis history, Shadowing/Recording, a low-friction Quick
Practice mode, a Learning History evidence center, and structured Markdown/JSON export of your own
practice evidence. All data — the database, recordings, and logs — stays on your machine under
`%APPDATA%\ListenTrace`; nothing is uploaded anywhere, and there is no account or network dependency of
any kind.

## Highlights since the last internally-tracked milestones

- **Milestone 13** replaced the whole interface with the "Notebook Study Desk" design system across all
  16 production surfaces.
- **Milestone 14** completed a whole-product hardening audit, three corrective batches, and a full
  Product Owner manual-regression pass (Human QA Round 2) against the finished UI — 0 open defects.
- **Milestone 15** produced the actual v1.0.0 release candidate: a single-source-of-truth version
  mechanism, an automated Windows build/package/checksum pipeline, and clean-machine acceptance on a
  genuinely clean Windows 11 VM (no developer tooling of any kind) — installation, first launch, real
  MP4/H.264 playback, real audio, material import, an Intensive Practice session, session persistence
  across a full close/reopen, and Windows taskbar/application identity all verified directly by a human
  on that clean machine.

## Known limitations

These are documented, deliberate scope boundaries or measured gaps — not release-blocking defects
unless stated otherwise. See `PROJECT_STATUS.md`'s "Open Release Blockers / Remaining Release
Decisions", "Known Limitations", and "Unknown or Unverified" sections for the complete, continuously
maintained list; the summary below is what's most relevant to someone deciding whether to install this
release.

- **The installer and executable are unsigned** (Product Owner decision: unsigned v1.0 is approved;
  code signing is not a v1.0 blocker and no signing infrastructure has been built). Windows SmartScreen
  **may** show an "unrecognized app" warning on first run for some users, depending on download source,
  file reputation, and Mark-of-the-Web context — the Milestone 15.2 clean-machine acceptance install
  did not itself encounter a SmartScreen block, so this is a possible, not certain, first-run
  experience. Known limitation, not a release blocker.
- **No automatic update checking.** ListenTrace does not check for or notify about newer versions in
  this release; this is a deliberately deferred feature for the first v1.0.x maintenance update, not an
  oversight.
- **Windows only.** macOS and Linux are unsupported; behavior there is untested.
- **125%/150% Windows display scaling** was exercised informally during clean-machine acceptance but
  was not promoted to a hard-gated verification; only 100% scaling has been formally verified.
- **No pagination** in Session History, Quiz History, take lists, or Learning History — behavior with a
  very large number of historical records is unverified.
- **Export** supports Markdown and JSON only (no PDF/HTML, no database backup, no bundled media), by
  design — see `README.md`'s Current Limitations for the full export-scope boundary.
- **Windows long-path support** is only partially addressed: the app opts into `longPathAware`, but the
  machine-wide registry policy that fully enables long paths on Windows is admin-only and off by
  default; ListenTrace cannot enable it itself.
- **Large-library performance** (many thousands of sessions/quizzes/recordings) has structural
  indexing in place but has not been benchmarked at that scale.

## What v1.0.0 explicitly does not include

- Any of the "Deferred Beyond v1.0 — Optional Assisted Features" (speech recognition, pronunciation
  feedback, translation, subtitle/question generation, pluggable external AI-service providers).
- The Milestone 16 (Library Organization & Collections) candidate — recorded as a possible v1.1
  requirement, not designed or implemented.
- Update Awareness — deferred to the first v1.0.x maintenance update.

## Privacy

No account, no network dependency, no telemetry. All application data (database, recordings, logs)
lives under `%APPDATA%\ListenTrace`. ListenTrace necessarily reads its own local application data to
function (to display your library, history, and practice evidence) — what it does not do is upload,
copy elsewhere, or transmit that data anywhere; nothing leaves your machine.
Uninstalling removes only the installed program files — your data is never deleted by install, upgrade,
or uninstall.

## Installation

Two forms are produced from the same build: an Inno Setup installer (`ListenTrace-Setup-1.0.0.exe`,
per-user install, no admin rights required) and a portable ZIP (extract and run, no install step). See
`packaging/README.md` for the full build/distribution mechanism.

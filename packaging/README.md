# Packaging (Post-M10 Phase A/B, plus Milestone 15.1 CI refresh)

This directory holds the build recipe validated during Phase A of
`ROADMAP.md`'s "v1.0 Release Engineering" sequence (previously named
"Post-M10 — Release Engineering and v1.0 Delivery"; renamed once Milestone
11 — UI/UX Presentation Refresh was introduced after M10). Phase A's job
was to **decide and validate** a Windows packaging approach, not to
finalize release engineering — Phase B (targeted technical hardening) has
since added one packaging-level fix of its own (the manifest addition
below), and Phase C1 (development-machine release preflight) is also
complete. Milestone 11 (UI/UX Presentation Refresh), Milestone 12
(Pre-UI Product Hardening), and Milestone 13 (Advanced UI/UX Reconstruction)
are all complete and merged. Milestone 14 (Final Product Hardening &
Full Manual Regression) is likewise **complete, accepted, and merged**
(Human QA Round 2 PASS; the pre-merge repository-hygiene/privacy/
Windows-app-identity corrective is Product Owner ACCEPTED). **Milestone
15.1 — Candidate Build/Packaging Refresh** builds on this directory's Phase
A/B recipe: it promotes the product version to `1.0.0`, adds a
single-source-of-truth version-sync mechanism, and adds the GitHub Actions
release-candidate pipeline described below, against this same final merged
M14 code. **Milestone 15.1 is Product Owner ACCEPTED. Milestone 15.2
(Clean-Machine Acceptance) is PASS / Product Owner Accepted, and Milestone
15.3 (Release Candidate Closure & Delivery) is complete** — Milestone 15 as
a whole is complete, accepted, and merged into `main` via PR #4. The
canonical validated v1.0.0 release payload remains the exact candidate from
source SHA `661bca47ce93f1a12a6a17c66f1ed6065d816e43` — see `ROADMAP.md`'s
"Validated Release Payload Policy" and "Canonical v1.0 Sequence".

## Version consistency (Milestone 15.1)

`pyproject.toml`'s `[project].version` is the single authoritative product
version. `packaging/version_info.txt` and `packaging/installer.iss`'s
`MyAppVersion` define are both *generated* from it by
`scripts/release_version.py` — nobody hand-edits three version literals in
sync:

```bash
python scripts/release_version.py --write   # after bumping pyproject.toml's version
python scripts/release_version.py --check   # CI gate: fails if any derived file drifted
```

## GitHub Actions release-candidate pipeline (Milestone 15.1)

`.github/workflows/release-candidate.yml` runs on a GitHub-hosted Windows
runner (`workflow_dispatch`, and on push to a `milestone/15-*` branch) and
performs, against an exact commit:

```text
checkout exact SHA
→ install project (dev + packaging extras)
→ run the full automated test suite
→ validate release/version consistency (release_version.py --check)
→ build the PyInstaller onedir candidate
→ validate the packaged payload (validate_build_payload.py)
→ smoke-test the portable build (packaging_smoke.py portable)
→ build the portable ZIP from that same onedir output
→ build the Inno Setup installer from that same onedir output
→ smoke-test silent install / launch / silent uninstall (packaging_smoke.py installed)
→ generate SHA-256 checksums + provenance.json (generate_provenance.py)
→ upload the four canonical artifacts as one workflow-run artifact bundle
```

The uploaded bundle is: the portable ZIP, the Inno Setup installer,
`SHA256SUMS.txt`, and `provenance.json` (product version, exact commit SHA,
workflow run id/URL, automated-test pass count, and each artifact's SHA-256
— everything needed to answer "what is this candidate and did it pass its
gates" without re-deriving it by hand). This is what Milestone 15.2's
clean-machine acceptance is expected to consume.

The two smoke checks are deliberately narrow given a headless Windows
runner and this app having no CLI flags: they launch the real frozen
build/installed exe with `%APPDATA%` redirected to a throwaway directory
and `QT_QPA_PLATFORM=offscreen`, and confirm it reaches the same
observable milestone a real first run reaches — creating
`listentrace.db` — plus (installed-build only) that a silent uninstall
removes the program files while a canary file placed in the redirected
app-data directory survives untouched. They do not attempt real
audio/video playback, real microphone capture, or real Windows shell/
taskbar verification — those remain Milestone 15.2's genuinely
human/clean-environment-dependent checks (see `ROADMAP.md`).

## Decisions made in Phase A

- **Packaging technology: PyInstaller** (onedir build). Chosen over Nuitka —
  mature, first-class PySide6 support via `pyinstaller-hooks-contrib`, no C
  compiler required to build, and a fast build turnaround suited to a spike.
- **Distribution form: both an installer and a portable build, from the same
  onedir output.** `packaging/dist/ListenTrace/` (built once) is either
  zipped as-is for the portable form, or wrapped by the Inno Setup script
  below for the installer form — there is only one build artifact, not two
  separate pipelines.
- **Installer tool: Inno Setup**, installed locally via
  `winget install JRSoftware.InnoSetup` (per-user, no admin rights consumed
  by the install itself). `packaging/installer.iss` installs **per-user
  only** (`PrivilegesRequired=lowest`, `DefaultDirName={autopf}\ListenTrace`,
  which resolves to `%LOCALAPPDATA%\Programs\ListenTrace` without admin
  rights). This is a **v1.0 release-scope decision, not just a default**:
  machine-wide install is out of scope for v1.0, so
  `PrivilegesRequiredOverridesAllowed` is deliberately left unset, which
  disables Inno Setup's per-user/machine-wide choice entirely rather than
  merely defaulting it.
- **Icon: a generated placeholder**, not a final design. See
  `assets/generate_icon.py` — a simple flat rounded-square-and-waveform
  glyph, regenerable at any time; swapping in a real icon later requires no
  changes anywhere else in the packaging pipeline.
- **Version metadata**: `ProductName`/`CompanyName`/`FileDescription` are all
  just `"ListenTrace"` — no separate publisher/company name is embedded
  anywhere in the exe version resource or the installer, by explicit choice.
- **Application-data and recording locations**: unchanged from
  `infrastructure/appdata.py` (`%APPDATA%\ListenTrace` on Windows) — already
  correct for a frozen build, since it resolves via `%APPDATA%` and
  `Path.home()`, never via `__file__`-relative paths. Validated directly (see
  below), not just assumed.
- **Preservation of SQLite data during upgrades / uninstall behavior**: the
  installer never touches `%APPDATA%\ListenTrace` — install, upgrade, and
  uninstall only ever add or remove the program-files copy. There is
  deliberately no "also delete my data" uninstall option yet. This follows
  directly from the database already living outside the install directory;
  Phase A validated this holds in practice for a real install → launch →
  uninstall cycle (see below), not just architecturally.
- **Windows-first**: this spike targets Windows only; macOS/Linux packaging
  is not addressed here (consistent with `ROADMAP.md`/`PROJECT_STATUS.md`,
  which have only ever verified this project on Windows).

## What was actually validated (not just planned)

All of the following were run for real during Phase A, not just reasoned
about:

1. **PyInstaller onedir build succeeds** with no unexpected missing-module
   warnings (only POSIX/macOS-only stdlib modules and unused optional
   `pywin32` logging handlers were reported missing — all expected and
   harmless on Windows).
2. **The frozen exe launches successfully** and, with `%APPDATA%` redirected
   to a throwaway directory, correctly creates `ListenTrace/listentrace.db`
   (schema version 9 at the time of this validation, all 21 tables present,
   including `quick_practice_*`), `ListenTrace/recordings/`, and
   `ListenTrace/logs/listentrace.log` — the exact same layout `appdata.py`
   produces when run from source.
3. **The portable form works from an arbitrary path**: the onedir build was
   zipped, extracted to a completely different directory, and launched from
   there — it started correctly and resolved app-data the same way.
4. **The installer form was compiled and run end-to-end**: silent install
   (no admin prompt, installed under `%LOCALAPPDATA%\Programs\ListenTrace`),
   a correct "Programs and Features" entry (`ListenTrace version 0.1.0`,
   Publisher `ListenTrace`), Start Menu shortcuts created, the installed exe
   launched correctly (again with `%APPDATA%` redirected for the test), then
   silent uninstall removed the install directory, the registry uninstall
   entry, and the Start Menu shortcuts completely — while a pre-existing
   real `%APPDATA%\Roaming\ListenTrace\recordings` directory on this machine
   was left completely untouched throughout the entire install → launch →
   uninstall cycle.

## Phase B addition: long-path manifest opt-in

`packaging/app.manifest` (embedded into the exe via `listentrace.spec`'s
`manifest=` argument) declares `longPathAware`, opting the built exe into
Windows support for paths longer than the legacy 260-character `MAX_PATH`
limit. This is a **partial mitigation, not a full fix** — confirmed directly
that creating a deeply nested path over ~260 characters fails with
`WinError 206` on this development machine even with the manifest in place,
because Windows' legacy Win32 file APIs also require the machine-wide
`LongPathsEnabled` registry policy to be turned on (admin-only, off by
default). This app cannot enable that policy itself without contradicting
Phase A's own per-user-only, no-admin-required install decision, so this
manifest entry only helps on a machine where an administrator has already
turned that policy on elsewhere. See `ARCHITECTURE.md`'s "Resolved in
Post-M10 Phase B" section for the full investigation.

## Building it yourself

The GitHub Actions pipeline above is now the canonical way to produce a
candidate build; the manual recipe below is the same steps by hand (e.g.
for local iteration on the packaging recipe itself):

```bash
pip install -e ".[packaging]"
python packaging/assets/generate_icon.py   # only if the icon needs regenerating
python scripts/release_version.py --write  # after bumping pyproject.toml's version
pyinstaller packaging/listentrace.spec --distpath packaging/dist --workpath packaging/build
python scripts/validate_build_payload.py
```

This produces `packaging/dist/ListenTrace/` (the onedir build). From there:

- **Portable form**: zip `packaging/dist/ListenTrace/` as-is.
- **Installer form**: compile `packaging/installer.iss` with Inno Setup 6
  (`ISCC.exe packaging/installer.iss`), which produces
  `packaging/dist/ListenTrace-Setup-<version>.exe`.

`packaging/build/` and `packaging/dist/` are both gitignored (matching the
repository's existing `build/`/`dist/` rules) — only the recipe files
(`listentrace.spec`, `version_info.txt`, `installer.iss`, `app.manifest`,
`assets/`) are committed. `version_info.txt` is committed but generated —
see "Version consistency" above, don't hand-edit its version fields.

## Explicitly out of scope for this directory

Phase A and Phase B are both complete (`ROADMAP.md`); Milestone 15.1 has
added version-sync tooling and the CI pipeline described above. The items
below remain out of scope for this directory, either because they belong to
a later milestone or because the fix lives in application code rather than
here:

- Code signing (unsigned v1.0 is Product Owner approved, not a release
  blocker; the exe and installer are unsigned, and Windows SmartScreen
  **may** warn on first run depending on download source/reputation/
  Mark-of-the-Web context — the Milestone 15.2 clean-machine install did
  not itself encounter a SmartScreen block).
- Auto-update.
- macOS/Linux packaging.
- A final, designed application icon (the current one is a placeholder).
- Full Windows long-path support (see the Phase B addition above — the
  manifest opt-in is necessary but not sufficient on its own; this is a
  documented, accepted limitation, not an open task).
- Clean-machine verification of anything in this file — every validation
  here (build, launch, install, uninstall, the long-path reproduction) ran
  on this development machine, which already has Python and other developer
  tooling installed (Phase C1 — Development-Machine Release Preflight,
  completed). Genuinely clean-machine testing (no preinstalled Python,
  fresh user account, non-English paths) is Milestone 15.2's job, follows
  the now-completed Milestone 14 merge, and remains pending/not started so
  it tests the final hardened, final-UI release candidate rather than an
  earlier presentation layer or unaudited product.
- Everything else Phase B fixed lives in application code, not this
  directory (migration atomicity, startup-crash ordering, crash logging,
  large-history indexes) — see `ARCHITECTURE.md`'s "Resolved in Post-M10
  Phase B" section for that work.

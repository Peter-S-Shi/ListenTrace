# Packaging (Post-M10 Phase A — Packaging Spike)

This directory holds the build recipe validated during Phase A of
`ROADMAP.md`'s "Post-M10 — Release Engineering and v1.0 Delivery" sequence.
Phase A's job was to **decide and validate** a Windows packaging approach,
not to finalize release engineering — Phase B (hardening), Phase C
(clean-machine testing), and Phase D (release candidate) still remain.

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
   (schema version 9, all 21 tables present, including `quick_practice_*`),
   `ListenTrace/recordings/`, and `ListenTrace/logs/listentrace.log` — the
   exact same layout `appdata.py` produces when run from source.
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

## Building it yourself

```bash
pip install -e ".[packaging]"
python packaging/assets/generate_icon.py   # only if the icon needs regenerating
pyinstaller packaging/listentrace.spec --distpath packaging/dist --workpath packaging/build
```

This produces `packaging/dist/ListenTrace/` (the onedir build). From there:

- **Portable form**: zip `packaging/dist/ListenTrace/` as-is.
- **Installer form**: compile `packaging/installer.iss` with Inno Setup 6
  (`ISCC.exe packaging/installer.iss`), which produces
  `packaging/dist/ListenTrace-Setup-<version>.exe`.

`packaging/build/` and `packaging/dist/` are both gitignored (matching the
repository's existing `build/`/`dist/` rules) — only the recipe files
(`listentrace.spec`, `version_info.txt`, `installer.iss`, `assets/`) are
committed.

## Explicitly not addressed by Phase A

- Code signing (the exe and installer are unsigned; Windows SmartScreen will
  warn on first run — a Phase B/D concern, not resolved here).
- Auto-update.
- macOS/Linux packaging.
- CI-driven builds (there is still no continuous-integration configuration
  anywhere in this project).
- A final, designed application icon (the current one is a placeholder).
- Everything listed under `ROADMAP.md`'s Phase B (hardening), Phase C
  (clean-machine testing on a genuinely clean environment — this spike's
  validation all ran on the existing development machine), and Phase D
  (release candidate).

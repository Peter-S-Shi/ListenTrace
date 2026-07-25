; Inno Setup script for ListenTrace (Post-M10 Phase A packaging spike).
;
; Build the PyInstaller onedir output first (from the repository root, with
; the `packaging` extra installed):
;     pyinstaller packaging/listentrace.spec --distpath packaging/dist --workpath packaging/build
; Then compile this script (paths below are relative to this file):
;     "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
; The compiled installer is written to packaging\dist\ListenTrace-Setup-<version>.exe
; (gitignored, same as the PyInstaller build output).
;
; AppId is a fixed, generated GUID -- do not change it. Inno Setup uses it to
; recognize "this is the same product" across versions so that running a
; newer installer upgrades in place rather than installing side-by-side.

#define MyAppName "ListenTrace"
#define MyAppVersion "0.1.0"
#define MyAppExeName "ListenTrace.exe"

[Setup]
AppId={{AED15111-65FC-44FB-80D2-1F6D28039E61}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Per-user install only for v1.0 -- no UAC prompt, and no machine-wide
; install option offered. This is a deliberate v1.0 release-scope decision
; (not merely a default): PrivilegesRequiredOverridesAllowed is intentionally
; left unset, which means Inno Setup does not offer a per-user/machine-wide
; choice at all -- omitting it, rather than setting it to a value, is what
; disables the choice (its default is "no overrides allowed"). Revisit only
; as an explicit future release-scope decision, not as a packaging default.
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=ListenTrace-Setup-{#MyAppVersion}
SetupIconFile=assets\listentrace.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\ListenTrace\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Deliberately no [UninstallDelete] entries for the app-data directory
; (%APPDATA%\ListenTrace -- database, recordings, logs). Uninstalling removes
; only the installed program files; the learner's local data is never
; touched by install, upgrade, or uninstall. This matches the project's
; local-first, user-owns-their-data philosophy (see ARCHITECTURE.md /
; infrastructure/appdata.py) and is a deliberate Phase A decision, not an
; oversight -- there is currently no "also delete my data" uninstall option.

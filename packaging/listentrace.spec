# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for ListenTrace (Post-M10 Phase A packaging spike).

Build from the repository root, with the project's `packaging` extra
installed (`pip install -e ".[packaging]"`):

    pyinstaller packaging/listentrace.spec --distpath packaging/dist --workpath packaging/build

Produces a one-dir build at `packaging/dist/ListenTrace/`, containing
`ListenTrace.exe` and its bundled Python/Qt runtime. This same folder is
both the Inno Setup installer's payload (`packaging/installer.iss`) and,
zipped as-is, the portable distribution -- there is only one build output
for both distribution forms, per Phase A's decision.

`build/`, `dist/`, and this spec's own `packaging/build`/`packaging/dist`
output directories are all gitignored; only this recipe, the version
resource, and the icon are committed.
"""

from pathlib import Path

REPO_ROOT = Path(SPECPATH).parent  # noqa: F821 -- SPECPATH is the directory containing this spec (packaging/)
PACKAGING_DIR = REPO_ROOT / "packaging"
SRC_DIR = REPO_ROOT / "src"

a = Analysis(
    [str(SRC_DIR / "listentrace" / "ui" / "app.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ListenTrace",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(PACKAGING_DIR / "assets" / "listentrace.ico"),
    version=str(PACKAGING_DIR / "version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ListenTrace",
)

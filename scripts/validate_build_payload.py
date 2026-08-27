"""Validate that a PyInstaller onedir build produced the expected payload.

Run after `pyinstaller packaging/listentrace.spec --distpath packaging/dist
--workpath packaging/build` to catch a build that "succeeded" (exit code 0)
but silently produced an incomplete or empty payload -- e.g. a missing exe,
a missing bundled icon/icons directory, or a suspiciously tiny executable
that suggests the Qt/PySide6 runtime was not actually bundled.

Usage:
    python scripts/validate_build_payload.py [--dist-dir packaging/dist/ListenTrace]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIST_DIR = REPO_ROOT / "packaging" / "dist" / "ListenTrace"

# A onedir PySide6 build bundling Qt WebEngine-free widgets is realistically
# tens of MB; anything under this is almost certainly a broken/partial build
# rather than a legitimately small one.
MIN_EXE_SIZE_BYTES = 1_000_000


def validate(dist_dir: Path) -> list[str]:
    problems = []

    exe_path = dist_dir / "ListenTrace.exe"
    if not exe_path.is_file():
        problems.append(f"missing executable: {exe_path}")
    elif exe_path.stat().st_size < MIN_EXE_SIZE_BYTES:
        problems.append(
            f"{exe_path} is only {exe_path.stat().st_size} bytes "
            f"(expected at least {MIN_EXE_SIZE_BYTES}) -- looks like an incomplete build"
        )

    # PyInstaller 6.x's onedir layout collects non-exe payload (datas,
    # binaries, the Python/Qt runtime) under an `_internal/` subdirectory
    # rather than beside the exe -- checked via glob so this keeps working
    # if a future PyInstaller version changes that layout again.
    if not list(dist_dir.glob("**/listentrace.ico")):
        problems.append(f"missing bundled app icon under {dist_dir}")

    icons_dirs = [p for p in dist_dir.glob("**/icons") if p.is_dir()]
    if not icons_dirs or not any(any(d.glob("*.svg")) for d in icons_dirs):
        problems.append(f"missing or empty bundled icons directory under {dist_dir}")

    # PySide6's Qt runtime is the bulk of a onedir build; its absence means
    # PyInstaller's dependency analysis silently failed to bundle Qt itself.
    if not list(dist_dir.glob("**/Qt6Core.dll")):
        problems.append(f"could not find a bundled Qt6Core.dll under {dist_dir} -- Qt runtime may be missing")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR)
    args = parser.parse_args(argv)

    if not args.dist_dir.is_dir():
        print(f"error: dist directory does not exist: {args.dist_dir}", file=sys.stderr)
        return 2

    problems = validate(args.dist_dir)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    print(f"Build payload at {args.dist_dir} looks complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

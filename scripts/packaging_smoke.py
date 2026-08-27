"""Deterministic, clean-environment-safe smoke checks for the packaged build.

ListenTrace is a windowed GUI application with no CLI flags -- there is no
`--version`/`--check` switch to shell out to. These smoke checks instead
launch the real frozen build (offscreen, with `%APPDATA%` redirected to a
throwaway directory) and confirm it reaches the same observable milestone a
successful first run always reaches: creating `listentrace.db` under its
app-data directory. This mirrors the Post-M10 Phase A manual validation
(see `packaging/README.md`), just automated and pointed at a disposable
directory instead of a real user profile.

Two checks:

    portable   -- launch packaging/dist/ListenTrace/ListenTrace.exe directly
    installed  -- silently install the Inno Setup output, launch the
                  installed exe, then silently uninstall and confirm the
                  program files are gone while app-data survives

Usage:
    python scripts/packaging_smoke.py portable --exe path/to/ListenTrace.exe
    python scripts/packaging_smoke.py installed --installer path/to/Setup.exe

Windows-only (uses `%APPDATA%`, Inno Setup silent-install switches, and
`taskkill`). Not meant to run on developer machines with real ListenTrace
data in `%APPDATA%` -- always redirects to a fresh temporary directory.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LAUNCH_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.5


def _wait_for_db(appdata_root: Path, timeout: float) -> bool:
    db_path = appdata_root / "ListenTrace" / "listentrace.db"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if db_path.is_file() and db_path.stat().st_size > 0:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return False


def _launch_and_verify(exe_path: Path, appdata_root: Path) -> None:
    appdata_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["APPDATA"] = str(appdata_root)
    env["QT_QPA_PLATFORM"] = "offscreen"

    process = subprocess.Popen([str(exe_path)], env=env)
    try:
        reached_db = _wait_for_db(appdata_root, LAUNCH_TIMEOUT_SECONDS)
        if not reached_db:
            raise SystemExit(
                f"error: {exe_path} did not create listentrace.db under {appdata_root} "
                f"within {LAUNCH_TIMEOUT_SECONDS}s"
            )
        print(f"OK: {exe_path} launched and created its app-data database under {appdata_root}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def portable_smoke(exe_path: Path) -> None:
    if not exe_path.is_file():
        raise SystemExit(f"error: executable not found: {exe_path}")
    with tempfile.TemporaryDirectory(prefix="lt_portable_appdata_") as appdata_dir:
        _launch_and_verify(exe_path, Path(appdata_dir))


def installed_smoke(installer_path: Path) -> None:
    if not installer_path.is_file():
        raise SystemExit(f"error: installer not found: {installer_path}")

    with tempfile.TemporaryDirectory(prefix="lt_install_") as install_root, tempfile.TemporaryDirectory(
        prefix="lt_installed_appdata_"
    ) as appdata_dir:
        install_dir = Path(install_root) / "ListenTrace"

        install_result = subprocess.run(
            [
                str(installer_path),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/DIR={install_dir}",
            ],
            timeout=180,
        )
        if install_result.returncode != 0:
            raise SystemExit(f"error: silent install failed with exit code {install_result.returncode}")

        exe_path = install_dir / "ListenTrace.exe"
        if not exe_path.is_file():
            raise SystemExit(f"error: silent install reported success but {exe_path} does not exist")
        print(f"OK: silent install produced {exe_path}")

        _launch_and_verify(exe_path, Path(appdata_dir))

        # Leave a canary file in app-data so uninstall-preserves-user-data is
        # an assertion, not an assumption -- the launch above only proves the
        # directory exists, not that uninstall leaves it alone afterward.
        canary_dir = Path(appdata_dir) / "ListenTrace"
        canary_path = canary_dir / "smoke_canary.txt"
        canary_path.write_text("packaging smoke canary", encoding="utf-8")

        uninstaller_path = install_dir / "unins000.exe"
        if not uninstaller_path.is_file():
            raise SystemExit(f"error: expected uninstaller not found: {uninstaller_path}")

        uninstall_result = subprocess.run(
            [str(uninstaller_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            timeout=180,
        )
        if uninstall_result.returncode != 0:
            raise SystemExit(f"error: silent uninstall failed with exit code {uninstall_result.returncode}")

        # The uninstaller spawns itself as a copy and exits the parent
        # process before file removal finishes; give it a moment to settle.
        deadline = time.monotonic() + 30
        while exe_path.exists() and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)

        if exe_path.exists():
            raise SystemExit(f"error: {exe_path} still exists after silent uninstall")
        print(f"OK: silent uninstall removed {exe_path}")

        if not canary_path.is_file():
            raise SystemExit(
                f"error: uninstall removed {canary_path} -- app-data must never be touched by install/uninstall"
            )
        print(f"OK: app-data canary at {canary_path} survived uninstall untouched")


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "win32":
        print("error: packaging_smoke.py is Windows-only", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    portable_parser = subparsers.add_parser("portable")
    portable_parser.add_argument("--exe", type=Path, required=True)

    installed_parser = subparsers.add_parser("installed")
    installed_parser.add_argument("--installer", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.mode == "portable":
        portable_smoke(args.exe)
    else:
        installed_smoke(args.installer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

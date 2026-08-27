"""Unit tests for scripts/validate_build_payload.py's pure directory-shape
validation, exercised against a synthetic onedir tree rather than a real
PyInstaller build."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import validate_build_payload  # noqa: E402


def _make_complete_dist(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "ListenTrace"
    internal = dist_dir / "_internal"
    (internal / "PySide6").mkdir(parents=True)
    (internal / "icons").mkdir(parents=True)
    dist_dir.mkdir(exist_ok=True)

    (dist_dir / "ListenTrace.exe").write_bytes(b"0" * (validate_build_payload.MIN_EXE_SIZE_BYTES + 1))
    (internal / "listentrace.ico").write_bytes(b"icon")
    (internal / "icons" / "check.svg").write_text("<svg/>", encoding="utf-8")
    (internal / "PySide6" / "Qt6Core.dll").write_bytes(b"dll")
    return dist_dir


def test_validate_reports_no_problems_for_a_complete_payload(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    assert validate_build_payload.validate(dist_dir) == []


def test_validate_reports_missing_exe(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    (dist_dir / "ListenTrace.exe").unlink()

    problems = validate_build_payload.validate(dist_dir)
    assert any("missing executable" in problem for problem in problems)


def test_validate_reports_suspiciously_small_exe(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    (dist_dir / "ListenTrace.exe").write_bytes(b"tiny")

    problems = validate_build_payload.validate(dist_dir)
    assert any("looks like an incomplete build" in problem for problem in problems)


def test_validate_reports_missing_icon(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    (dist_dir / "_internal" / "listentrace.ico").unlink()

    problems = validate_build_payload.validate(dist_dir)
    assert any("missing bundled app icon" in problem for problem in problems)


def test_validate_reports_missing_icons_directory_contents(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    (dist_dir / "_internal" / "icons" / "check.svg").unlink()

    problems = validate_build_payload.validate(dist_dir)
    assert any("icons directory" in problem for problem in problems)


def test_validate_reports_missing_qt_runtime(tmp_path):
    dist_dir = _make_complete_dist(tmp_path)
    (dist_dir / "_internal" / "PySide6" / "Qt6Core.dll").unlink()

    problems = validate_build_payload.validate(dist_dir)
    assert any("Qt6Core.dll" in problem for problem in problems)


def test_validate_reports_all_problems_together_for_an_empty_directory(tmp_path):
    dist_dir = tmp_path / "ListenTrace"
    dist_dir.mkdir()

    problems = validate_build_payload.validate(dist_dir)
    assert len(problems) == 4

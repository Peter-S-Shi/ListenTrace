"""Unit tests for scripts/release_version.py -- the version single-source-of-
truth mechanism M15.1 introduces. Pure string/regex logic, no OS/CI
dependency, so it is tested directly rather than only exercised by CI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import release_version  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """Every test points the module's module-level path constants at
    throwaway files instead of the real repository's, so nothing here can
    ever read or write the actual pyproject.toml/packaging files."""
    pyproject = tmp_path / "pyproject.toml"
    version_info = tmp_path / "version_info.txt"
    installer_iss = tmp_path / "installer.iss"
    monkeypatch.setattr(release_version, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(release_version, "VERSION_INFO_PATH", version_info)
    monkeypatch.setattr(release_version, "INSTALLER_ISS_PATH", installer_iss)
    return {"pyproject": pyproject, "version_info": version_info, "installer_iss": installer_iss}


def _write_pyproject(path: Path, version: str) -> None:
    path.write_text(
        f'[project]\nname = "listentrace"\nversion = "{version}"\ndescription = "x"\n',
        encoding="utf-8",
    )


def _write_installer_iss(path: Path, version: str) -> None:
    path.write_text(
        f'#define MyAppName "ListenTrace"\n#define MyAppVersion "{version}"\n#define MyAppExeName "ListenTrace.exe"\n',
        encoding="utf-8",
    )


def test_read_product_version_extracts_the_project_version(_isolate_paths):
    _write_pyproject(_isolate_paths["pyproject"], "1.2.3")
    assert release_version.read_product_version() == "1.2.3"


def test_read_product_version_raises_when_field_is_absent(_isolate_paths):
    _isolate_paths["pyproject"].write_text('[project]\nname = "x"\n', encoding="utf-8")
    with pytest.raises(release_version.VersionSyncError):
        release_version.read_product_version()


@pytest.mark.parametrize(
    "version,expected",
    [
        ("1.0.0", (1, 0, 0, 0)),
        ("0.1.0", (0, 1, 0, 0)),
        ("12.34.56", (12, 34, 56, 0)),
    ],
)
def test_four_part_converts_semver_to_windows_version_tuple(version, expected):
    assert release_version._four_part(version) == expected


@pytest.mark.parametrize("bad_version", ["1.0", "1.0.0.0", "1.0.rc1", "abc"])
def test_four_part_rejects_non_three_part_numeric_versions(bad_version):
    with pytest.raises(release_version.VersionSyncError):
        release_version._four_part(bad_version)


def test_render_version_info_txt_embeds_the_dotted_and_tuple_forms():
    rendered = release_version.render_version_info_txt("1.0.0")
    assert "filevers=(1, 0, 0, 0)" in rendered
    assert "prodvers=(1, 0, 0, 0)" in rendered
    assert "u'FileVersion', u'1.0.0.0'" in rendered
    assert "u'ProductVersion', u'1.0.0.0'" in rendered


def test_render_installer_iss_replaces_only_the_version_define():
    current = '#define MyAppName "ListenTrace"\n#define MyAppVersion "0.1.0"\n#define MyAppExeName "ListenTrace.exe"\n'
    rendered = release_version.render_installer_iss("1.0.0", current)
    assert '#define MyAppVersion "1.0.0"' in rendered
    assert '#define MyAppName "ListenTrace"' in rendered
    assert '#define MyAppExeName "ListenTrace.exe"' in rendered


def test_render_installer_iss_raises_if_the_define_is_missing():
    with pytest.raises(release_version.VersionSyncError):
        release_version.render_installer_iss("1.0.0", "; no version define here\n")


def test_check_reports_no_problems_once_files_are_in_sync(_isolate_paths):
    _write_pyproject(_isolate_paths["pyproject"], "1.0.0")
    _write_installer_iss(_isolate_paths["installer_iss"], "1.0.0")
    _isolate_paths["version_info"].write_text(release_version.render_version_info_txt("1.0.0"), encoding="utf-8")

    assert release_version.check("1.0.0") == []


def test_check_reports_a_problem_per_drifted_file(_isolate_paths):
    _write_pyproject(_isolate_paths["pyproject"], "1.0.0")
    _write_installer_iss(_isolate_paths["installer_iss"], "0.1.0")
    _isolate_paths["version_info"].write_text(release_version.render_version_info_txt("0.1.0"), encoding="utf-8")

    problems = release_version.check("1.0.0")
    assert len(problems) == 2
    assert any("version_info.txt" in problem for problem in problems)
    assert any("installer.iss" in problem for problem in problems)


def test_write_then_check_round_trips_to_zero_problems(_isolate_paths):
    _write_pyproject(_isolate_paths["pyproject"], "2.5.1")
    _write_installer_iss(_isolate_paths["installer_iss"], "0.1.0")
    _isolate_paths["version_info"].write_text("placeholder", encoding="utf-8")

    release_version.write("2.5.1")

    assert release_version.check("2.5.1") == []


def test_main_check_mode_returns_nonzero_on_drift(_isolate_paths, capsys):
    _write_pyproject(_isolate_paths["pyproject"], "1.0.0")
    _write_installer_iss(_isolate_paths["installer_iss"], "0.1.0")
    _isolate_paths["version_info"].write_text("placeholder", encoding="utf-8")

    exit_code = release_version.main(["--check"])

    assert exit_code == 1
    assert "out of sync" in capsys.readouterr().err


def test_main_write_mode_syncs_and_returns_zero(_isolate_paths):
    _write_pyproject(_isolate_paths["pyproject"], "1.0.0")
    _write_installer_iss(_isolate_paths["installer_iss"], "0.1.0")
    _isolate_paths["version_info"].write_text("placeholder", encoding="utf-8")

    assert release_version.main(["--write"]) == 0
    assert release_version.main(["--check"]) == 0

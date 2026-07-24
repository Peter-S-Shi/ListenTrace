from __future__ import annotations

import pytest

from listentrace.infrastructure import export_io


def test_sanitize_export_filename_strips_unsafe_characters():
    result = export_io.sanitize_export_filename('Lesson: "Intro" / Part 1?')
    for unsafe in (":", '"', "/", "?"):
        assert unsafe not in result
    assert result.startswith("Lesson")


def test_sanitize_export_filename_collapses_repeated_underscores():
    result = export_io.sanitize_export_filename("a///b")
    assert "___" not in result


def test_sanitize_export_filename_never_empty():
    assert export_io.sanitize_export_filename("") == "listentrace_export"


def test_atomic_write_text_creates_the_file_with_full_content(tmp_path):
    path = tmp_path / "out.md"
    export_io.atomic_write_text(path, "hello world")
    assert path.read_text(encoding="utf-8") == "hello world"


def test_atomic_write_text_leaves_no_temp_file_behind_on_success(tmp_path):
    path = tmp_path / "out.md"
    export_io.atomic_write_text(path, "content")
    leftovers = list(tmp_path.glob("*.tmp-*"))
    assert leftovers == []


def test_atomic_write_text_overwrites_an_existing_file_completely(tmp_path):
    path = tmp_path / "out.md"
    path.write_text("old content that is much longer than the new one", encoding="utf-8")
    export_io.atomic_write_text(path, "new")
    assert path.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_leaves_the_original_file_untouched_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "out.md"
    path.write_text("original", encoding="utf-8")

    from pathlib import Path

    original_write_text = Path.write_text

    def _boom(self, *args, **kwargs):
        if self.name.startswith("out.md.tmp-"):
            raise OSError("simulated disk-full failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(OSError):
        export_io.atomic_write_text(path, "new content that should never land")

    assert path.read_text(encoding="utf-8") == "original"
    leftovers = list(tmp_path.glob("*.tmp-*"))
    assert leftovers == []

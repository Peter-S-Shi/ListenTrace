from __future__ import annotations

import pytest

from listentrace.application.dto.import_results import ImportNeedsConfirmation, ImportSuccess
from listentrace.application.errors import MaterialValidationError
from listentrace.application.services.material_import_service import import_material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _make_media(tmp_path, name="lesson.mp3", content=b"fake audio bytes" * 50):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def _make_srt(tmp_path, name="lesson.srt"):
    path = tmp_path / name
    path.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nBonjour\n\n2\n00:00:02,000 --> 00:00:04,000\nComment ça va ?\n",
        encoding="utf-8",
    )
    return path


def _make_vtt(tmp_path, name="lesson.vtt"):
    path = tmp_path / name
    path.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nBonjour\n",
        encoding="utf-8",
    )
    return path


def _row_count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_import_success_with_srt(conn, tmp_path):
    media = _make_media(tmp_path)
    subtitle = _make_srt(tmp_path)

    result = import_material(conn, media, subtitle, "Lesson 1", language="fr")

    assert isinstance(result, ImportSuccess)
    assert result.cue_count == 2
    assert _row_count(conn, "material") == 1
    assert _row_count(conn, "subtitle_track") == 1
    assert _row_count(conn, "subtitle_cue") == 2


def test_import_success_with_vtt(conn, tmp_path):
    media = _make_media(tmp_path)
    subtitle = _make_vtt(tmp_path)

    result = import_material(conn, media, subtitle, "Lesson VTT")

    assert isinstance(result, ImportSuccess)
    assert result.cue_count == 1


def test_import_missing_media_writes_no_records(conn, tmp_path):
    missing_media = tmp_path / "missing.mp3"
    subtitle = _make_srt(tmp_path)

    with pytest.raises(MaterialValidationError) as exc_info:
        import_material(conn, missing_media, subtitle, "Should Not Persist")

    assert exc_info.value.category == "media_not_found"
    assert _row_count(conn, "material") == 0


def test_import_malformed_subtitle_writes_no_records(conn, tmp_path):
    media = _make_media(tmp_path)
    malformed = tmp_path / "broken.srt"
    malformed.write_text("1\n00:00:05,000 --> 00:00:02,000\nBad timing\n", encoding="utf-8")

    with pytest.raises(MaterialValidationError) as exc_info:
        import_material(conn, media, malformed, "Should Not Persist")

    assert exc_info.value.category == "subtitle_malformed"
    assert _row_count(conn, "material") == 0
    assert _row_count(conn, "subtitle_track") == 0


def test_import_empty_subtitle_is_rejected(conn, tmp_path):
    media = _make_media(tmp_path)
    empty_vtt = tmp_path / "empty.vtt"
    empty_vtt.write_text("WEBVTT\n", encoding="utf-8")

    with pytest.raises(MaterialValidationError) as exc_info:
        import_material(conn, media, empty_vtt, "Empty Track")

    assert exc_info.value.category == "subtitle_empty"
    assert _row_count(conn, "material") == 0


def test_import_unsupported_media_type_is_rejected(conn, tmp_path):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("not a media file", encoding="utf-8")
    subtitle = _make_srt(tmp_path)

    with pytest.raises(MaterialValidationError) as exc_info:
        import_material(conn, unsupported, subtitle, "Bad Type")

    assert exc_info.value.category == "media_unsupported"


def test_import_duplicate_normalized_path_is_rejected(conn, tmp_path):
    media = _make_media(tmp_path)
    subtitle = _make_srt(tmp_path)

    import_material(conn, media, subtitle, "First Import")

    with pytest.raises(MaterialValidationError) as exc_info:
        import_material(conn, media, subtitle, "Second Import Same File")

    assert exc_info.value.category == "duplicate_path"
    assert _row_count(conn, "material") == 1


def test_import_duplicate_fingerprint_needs_confirmation_then_succeeds(conn, tmp_path):
    media_a = _make_media(tmp_path, name="a.mp3")
    media_b = _make_media(tmp_path, name="b.mp3", content=media_a.read_bytes())
    subtitle = _make_srt(tmp_path)

    import_material(conn, media_a, subtitle, "Original")

    result = import_material(conn, media_b, subtitle, "Copy")
    assert isinstance(result, ImportNeedsConfirmation)
    assert _row_count(conn, "material") == 1  # nothing written yet

    confirmed = import_material(
        conn, media_b, subtitle, "Copy", confirm_duplicate_fingerprint=True
    )
    assert isinstance(confirmed, ImportSuccess)
    assert _row_count(conn, "material") == 2

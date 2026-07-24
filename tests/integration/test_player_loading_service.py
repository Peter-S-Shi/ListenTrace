from __future__ import annotations

import pytest

from listentrace.application.errors import PlayerOpenError
from listentrace.application.services import material_library_service as library
from listentrace.application.services.material_import_service import import_material
from listentrace.application.services.player_loading_service import load_material_for_player
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _import_sample(conn, tmp_path, name="lesson"):
    media = tmp_path / f"{name}.mp3"
    media.write_bytes(b"fake audio bytes" * 50)
    subtitle = tmp_path / f"{name}.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nBonjour\n\n2\n00:00:02,000 --> 00:00:04,000\nSalut\n",
        encoding="utf-8",
    )
    result = import_material(conn, media, subtitle, "Lesson")
    return result.material_id, media, subtitle


def test_load_material_for_player_returns_material_and_ordered_cues(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)
    result = load_material_for_player(conn, material_id)

    assert result.material.id == material_id
    assert [cue.text for cue in result.cues] == ["Bonjour", "Salut"]


def test_load_material_for_player_blocks_archived(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)
    library.archive_material(conn, material_id)

    with pytest.raises(PlayerOpenError) as exc_info:
        load_material_for_player(conn, material_id)
    assert exc_info.value.category == "archived"


def test_load_material_for_player_blocks_missing_media(conn, tmp_path):
    material_id, media, _ = _import_sample(conn, tmp_path)
    media.unlink()

    with pytest.raises(PlayerOpenError) as exc_info:
        load_material_for_player(conn, material_id)
    assert exc_info.value.category == "media_missing"


def test_load_material_for_player_blocks_missing_subtitle(conn, tmp_path):
    material_id, _, subtitle = _import_sample(conn, tmp_path)
    subtitle.unlink()

    with pytest.raises(PlayerOpenError) as exc_info:
        load_material_for_player(conn, material_id)
    assert exc_info.value.category == "subtitle_missing"


def test_load_material_for_player_not_found(conn):
    with pytest.raises(PlayerOpenError) as exc_info:
        load_material_for_player(conn, 999)
    assert exc_info.value.category == "not_found"

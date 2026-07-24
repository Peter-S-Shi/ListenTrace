from __future__ import annotations

import pytest

from listentrace.application.errors import MaterialNotFoundError
from listentrace.application.services import material_library_service as library
from listentrace.application.services.material_import_service import import_material
from listentrace.domain.enums.material_status import MaterialStatus
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def _import_sample(conn, tmp_path, name="lesson", title="Lesson"):
    media = tmp_path / f"{name}.mp3"
    media.write_bytes(b"fake audio bytes" * 50)
    subtitle = tmp_path / f"{name}.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nBonjour\n", encoding="utf-8")
    result = import_material(conn, media, subtitle, title)
    return result.material_id, media, subtitle


def test_list_active_materials(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)
    active = library.list_active_materials(conn)
    assert [m.id for m in active] == [material_id]
    assert library.list_archived_materials(conn) == []


def test_get_material_detail(conn, tmp_path):
    material_id, media, subtitle = _import_sample(conn, tmp_path)
    detail = library.get_material_detail(conn, material_id)

    assert detail.title == "Lesson"
    assert detail.status == MaterialStatus.ACTIVE.value
    assert detail.media_available is True
    assert detail.subtitle_available is True
    assert detail.cue_count == 1


def test_get_material_detail_missing_raises(conn):
    with pytest.raises(MaterialNotFoundError):
        library.get_material_detail(conn, 999)


def test_rename_material(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)
    library.rename_material(conn, material_id, "Renamed Lesson")
    detail = library.get_material_detail(conn, material_id)
    assert detail.title == "Renamed Lesson"


def test_archive_and_restore(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)

    library.archive_material(conn, material_id)
    assert [m.id for m in library.list_active_materials(conn)] == []
    assert [m.id for m in library.list_archived_materials(conn)] == [material_id]

    library.restore_material(conn, material_id)
    assert [m.id for m in library.list_active_materials(conn)] == [material_id]
    assert library.list_archived_materials(conn) == []


def test_remove_material_cascades_and_preserves_source_files(conn, tmp_path):
    material_id, media, subtitle = _import_sample(conn, tmp_path)

    library.remove_material(conn, material_id)

    assert conn.execute("SELECT COUNT(*) FROM material").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM subtitle_track").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM subtitle_cue").fetchone()[0] == 0

    assert media.exists()
    assert subtitle.exists()


def test_missing_source_file_is_detected(conn, tmp_path):
    material_id, media, _ = _import_sample(conn, tmp_path)
    media.unlink()

    active = library.list_active_materials(conn)
    assert active[0].media_available is False

    detail = library.get_material_detail(conn, material_id)
    assert detail.media_available is False


def test_operations_on_removed_material_raise_not_found(conn, tmp_path):
    material_id, _, _ = _import_sample(conn, tmp_path)
    library.remove_material(conn, material_id)

    with pytest.raises(MaterialNotFoundError):
        library.rename_material(conn, material_id, "Ghost")
    with pytest.raises(MaterialNotFoundError):
        library.archive_material(conn, material_id)
    with pytest.raises(MaterialNotFoundError):
        library.remove_material(conn, material_id)

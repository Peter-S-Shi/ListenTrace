from __future__ import annotations

import pytest

from listentrace.application.dto.saved_item_results import (
    SavedItemNeedsConfirmation,
    SavedItemSuccess,
)
from listentrace.application.errors import (
    CueNotFoundError,
    SavedItemNotFoundError,
    SavedItemValidationError,
)
from listentrace.application.services import saved_language_item_service as item_service
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import (
    get_cues_for_track,
    insert_material,
    insert_subtitle_track,
)


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def setup(conn):
    material_id = insert_material(conn, Material(title="Lesson", media_path="m.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour tout le monde")],
    )
    track_id = insert_subtitle_track(conn, track)
    cue = get_cues_for_track(conn, track_id)[0]
    return material_id, cue


def test_save_language_item_success(conn, setup):
    material_id, cue = setup
    result = item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    assert isinstance(result, SavedItemSuccess)
    items = item_service.list_saved_items_for_cue(conn, cue.id)
    assert items[0].text == "Bonjour"
    assert items[0].normalized_text == "Bonjour"
    assert items[0].context_text == cue.text


def test_context_text_defaults_to_full_cue_and_is_editable(conn, setup):
    material_id, cue = setup
    result = item_service.save_language_item(
        conn, material_id, cue.id, "phrase", 0, 7, context_text="custom context"
    )
    item = item_service.list_saved_items_for_cue(conn, cue.id)[0]
    assert item.context_text == "custom context"


def test_invalid_item_type_is_rejected(conn, setup):
    material_id, cue = setup
    with pytest.raises(SavedItemValidationError) as exc_info:
        item_service.save_language_item(conn, material_id, cue.id, "not_a_type", 0, 7)
    assert exc_info.value.category == "invalid_item_type"


def test_out_of_bounds_range_is_rejected(conn, setup):
    material_id, cue = setup
    with pytest.raises(SavedItemValidationError) as exc_info:
        item_service.save_language_item(conn, material_id, cue.id, "word", 0, 999)
    assert exc_info.value.category == "invalid_range"


def test_empty_selection_is_rejected(conn, setup):
    material_id, cue = setup
    with pytest.raises(SavedItemValidationError) as exc_info:
        item_service.save_language_item(conn, material_id, cue.id, "word", 3, 3)
    assert exc_info.value.category == "empty_text"


def test_exact_duplicate_is_rejected(conn, setup):
    material_id, cue = setup
    item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    with pytest.raises(SavedItemValidationError) as exc_info:
        item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    assert exc_info.value.category == "duplicate_saved_item"
    assert len(item_service.list_saved_items_for_cue(conn, cue.id)) == 1


def test_same_text_elsewhere_returns_confirmation_then_succeeds(conn, setup):
    material_id, cue = setup
    item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)

    # Different range within the same cue with the same normalized text ("Bonjour" doesn't
    # repeat here, so use a second cue instead to model "elsewhere").
    track2 = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s2.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=2000, end_ms=3000, text="Bonjour a tous")],
    )
    from listentrace.infrastructure.db.repository import insert_subtitle_track as insert_track

    track2_id = insert_track(conn, track2)
    cue2 = get_cues_for_track(conn, track2_id)[0]

    result = item_service.save_language_item(conn, material_id, cue2.id, "word", 0, 7)
    assert isinstance(result, SavedItemNeedsConfirmation)
    assert len(item_service.list_saved_items_for_cue(conn, cue2.id)) == 0

    confirmed = item_service.save_language_item(
        conn, material_id, cue2.id, "word", 0, 7, confirm_duplicate_text_elsewhere=True
    )
    assert isinstance(confirmed, SavedItemSuccess)
    assert len(item_service.list_saved_items_for_cue(conn, cue2.id)) == 1


def test_cue_not_found_raises(conn):
    with pytest.raises(CueNotFoundError):
        item_service.save_language_item(conn, 1, 999, "word", 0, 5)


def test_update_saved_item(conn, setup):
    material_id, cue = setup
    result = item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    item_service.update_saved_language_item(conn, result.item_id, meaning="hello", note="greeting")
    item = item_service.list_saved_items_for_cue(conn, cue.id)[0]
    assert item.meaning == "hello"
    assert item.note == "greeting"


def test_update_nonexistent_item_raises(conn):
    with pytest.raises(SavedItemNotFoundError):
        item_service.update_saved_language_item(conn, 999, meaning="x")


def test_delete_saved_item(conn, setup):
    material_id, cue = setup
    result = item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    item_service.delete_saved_language_item(conn, result.item_id)
    assert item_service.list_saved_items_for_cue(conn, cue.id) == []


def test_delete_nonexistent_item_raises(conn):
    with pytest.raises(SavedItemNotFoundError):
        item_service.delete_saved_language_item(conn, 999)


def test_saved_items_cascade_when_material_removed(conn, setup):
    material_id, cue = setup
    item_service.save_language_item(conn, material_id, cue.id, "word", 0, 7)
    conn.execute("DELETE FROM material")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM saved_language_item").fetchone()[0] == 0

from __future__ import annotations

import pytest

from listentrace.application.errors import AnnotationValidationError
from listentrace.application.services import annotation_service, label_preference_service
from listentrace.domain.models.material import Material
from listentrace.domain.models.subtitle import SubtitleCue, SubtitleTrack
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import get_cues_for_track, insert_material, insert_subtitle_track


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def test_defaults_seeded_for_all_five_labels(conn):
    prefs = label_preference_service.get_label_preferences(conn)
    assert set(prefs.keys()) == {
        "keyword",
        "known_not_heard",
        "connected_reduced_speech",
        "misheard",
        "unknown_word_or_chunk",
    }
    assert all(color.startswith("#") for color in prefs.values())


def test_update_label_color(conn):
    label_preference_service.update_label_color(conn, "keyword", "#112233")
    prefs = label_preference_service.get_label_preferences(conn)
    assert prefs["keyword"] == "#112233"


def test_invalid_label_is_rejected(conn):
    with pytest.raises(AnnotationValidationError) as exc_info:
        label_preference_service.update_label_color(conn, "not_a_label", "#112233")
    assert exc_info.value.category == "invalid_label"


def test_invalid_color_is_rejected(conn):
    with pytest.raises(AnnotationValidationError) as exc_info:
        label_preference_service.update_label_color(conn, "keyword", "blue")
    assert exc_info.value.category == "invalid_color"


def test_color_change_does_not_alter_stored_annotation_label_key(conn):
    material_id = insert_material(conn, Material(title="Lesson", media_path="m.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour")],
    )
    track_id = insert_subtitle_track(conn, track)
    cue = get_cues_for_track(conn, track_id)[0]

    annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    before = annotation_service.list_annotations_for_cue(conn, cue.id)[0]

    label_preference_service.update_label_color(conn, "keyword", "#ABCDEF")

    after = annotation_service.list_annotations_for_cue(conn, cue.id)[0]
    assert after.label_key == before.label_key == "keyword"
    assert after.selected_text == before.selected_text

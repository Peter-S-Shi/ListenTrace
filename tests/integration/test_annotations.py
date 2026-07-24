from __future__ import annotations

import pytest

from listentrace.application.errors import (
    AnnotationNotFoundError,
    AnnotationValidationError,
    CueNotFoundError,
)
from listentrace.application.services import annotation_service
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
def cue(conn):
    material_id = insert_material(conn, Material(title="Lesson", media_path="m.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Bonjour tout le monde")],
    )
    track_id = insert_subtitle_track(conn, track)
    return get_cues_for_track(conn, track_id)[0]


def test_create_whole_cue_annotation(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, len(cue.text), ["keyword"])
    assert len(ids) == 1
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert annotations[0].selected_text == cue.text


def test_create_partial_range_annotation(conn, cue):
    annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert annotations[0].selected_text == "Bonjour"


def test_multiple_labels_created_atomically_from_one_save(conn, cue):
    ids = annotation_service.create_annotations(
        conn, cue.id, 0, 7, ["keyword", "unknown_word_or_chunk"]
    )
    assert len(ids) == 2
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert {a.label_key for a in annotations} == {"keyword", "unknown_word_or_chunk"}
    assert all(a.selection_start == 0 and a.selection_end == 7 for a in annotations)


def test_duplicate_label_on_same_range_is_rejected(conn, cue):
    annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    assert exc_info.value.category == "duplicate_annotation"
    # only the first annotation should exist
    assert len(annotation_service.list_annotations_for_cue(conn, cue.id)) == 1


def test_different_labels_may_share_the_same_range(conn, cue):
    annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    annotation_service.create_annotations(conn, cue.id, 0, 7, ["unknown_word_or_chunk"])
    assert len(annotation_service.list_annotations_for_cue(conn, cue.id)) == 2


def test_out_of_bounds_range_is_rejected(conn, cue):
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.create_annotations(conn, cue.id, 0, 999, ["keyword"])
    assert exc_info.value.category == "invalid_range"
    assert annotation_service.list_annotations_for_cue(conn, cue.id) == []


def test_no_label_selected_is_rejected(conn, cue):
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.create_annotations(conn, cue.id, 0, 7, [])
    assert exc_info.value.category == "no_label_selected"


def test_invalid_label_key_is_rejected(conn, cue):
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.create_annotations(conn, cue.id, 0, 7, ["not_a_real_label"])
    assert exc_info.value.category == "invalid_label"


def test_misheard_requires_heard_as(conn, cue):
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.create_annotations(conn, cue.id, 0, 7, ["misheard"])
    assert exc_info.value.category == "misheard_requires_heard_as"
    assert annotation_service.list_annotations_for_cue(conn, cue.id) == []


def test_misheard_with_heard_as_succeeds_and_stores_it(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["misheard"], heard_as="Bonsoir")
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert annotations[0].heard_as == "Bonsoir"


def test_non_misheard_label_does_not_store_heard_as(conn, cue):
    # Saving keyword + misheard together in one action: only the misheard row gets heard_as.
    annotation_service.create_annotations(
        conn, cue.id, 0, 7, ["keyword", "misheard"], heard_as="Bonsoir"
    )
    annotations = {a.label_key: a for a in annotation_service.list_annotations_for_cue(conn, cue.id)}
    assert annotations["misheard"].heard_as == "Bonsoir"
    assert annotations["keyword"].heard_as is None


def test_cue_not_found_raises(conn):
    with pytest.raises(CueNotFoundError):
        annotation_service.create_annotations(conn, 999, 0, 5, ["keyword"])


def test_unicode_selection_round_trips(conn):
    material_id = insert_material(conn, Material(title="Lesson", media_path="m.mp4"))
    track = SubtitleTrack(
        material_id=material_id,
        format="srt",
        source_path="s.srt",
        cues=[SubtitleCue(cue_index=1, start_ms=0, end_ms=1000, text="Comment ça va ? 你好世界")],
    )
    track_id = insert_subtitle_track(conn, track)
    unicode_cue = get_cues_for_track(conn, track_id)[0]

    ids = annotation_service.create_annotations(conn, unicode_cue.id, 16, 18, ["keyword"])
    annotations = annotation_service.list_annotations_for_cue(conn, unicode_cue.id)
    assert annotations[0].selected_text == "你好"


def test_update_annotation_note_and_heard_as(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["misheard"], heard_as="X")
    annotation_service.update_annotation(conn, ids[0], "misheard", 0, 7, heard_as="Y", note="clarified")
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert annotations[0].heard_as == "Y"
    assert annotations[0].note == "clarified"


def test_update_annotation_can_change_label_and_range(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    annotation_service.update_annotation(conn, ids[0], "unknown_word_or_chunk", 8, 12)
    annotations = annotation_service.list_annotations_for_cue(conn, cue.id)
    assert annotations[0].label_key == "unknown_word_or_chunk"
    assert (annotations[0].selection_start, annotations[0].selection_end) == (8, 12)
    assert annotations[0].selected_text == "tout"


def test_update_annotation_rejects_invalid_label(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.update_annotation(conn, ids[0], "not_a_label", 0, 7)
    assert exc_info.value.category == "invalid_label"


def test_update_annotation_rejects_out_of_bounds_range(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.update_annotation(conn, ids[0], "keyword", 0, 999)
    assert exc_info.value.category == "invalid_range"


def test_update_annotation_rejects_collision_with_another_row(conn, cue):
    ids_a = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    annotation_service.create_annotations(conn, cue.id, 8, 12, ["unknown_word_or_chunk"])
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.update_annotation(conn, ids_a[0], "unknown_word_or_chunk", 8, 12)
    assert exc_info.value.category == "duplicate_annotation"


def test_update_annotation_to_same_label_and_range_is_not_a_false_duplicate(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["misheard"], heard_as="X")
    # Updating a row to its own current label/range must not trip the duplicate check.
    annotation_service.update_annotation(conn, ids[0], "misheard", 0, 7, heard_as="Y")
    assert annotation_service.list_annotations_for_cue(conn, cue.id)[0].heard_as == "Y"


def test_updating_one_annotation_does_not_affect_a_sibling_on_the_same_range(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword", "unknown_word_or_chunk"])
    annotation_service.update_annotation(conn, ids[0], "keyword", 0, 7, note="only this one")
    annotations = {a.id: a for a in annotation_service.list_annotations_for_cue(conn, cue.id)}
    assert annotations[ids[0]].note == "only this one"
    assert annotations[ids[1]].note is None
    assert annotations[ids[1]].label_key == "unknown_word_or_chunk"


def test_update_misheard_annotation_requires_heard_as(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["misheard"], heard_as="X")
    with pytest.raises(AnnotationValidationError) as exc_info:
        annotation_service.update_annotation(conn, ids[0], "misheard", 0, 7, heard_as="", note="note")
    assert exc_info.value.category == "misheard_requires_heard_as"


def test_delete_annotation(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    annotation_service.delete_annotation(conn, ids[0])
    assert annotation_service.list_annotations_for_cue(conn, cue.id) == []


def test_delete_nonexistent_annotation_raises(conn):
    with pytest.raises(AnnotationNotFoundError):
        annotation_service.delete_annotation(conn, 999)


def test_update_nonexistent_annotation_raises(conn):
    with pytest.raises(AnnotationNotFoundError):
        annotation_service.update_annotation(conn, 999, "keyword", 0, 5, heard_as=None, note="x")


def test_annotations_cascade_when_material_removed(conn, cue):
    ids = annotation_service.create_annotations(conn, cue.id, 0, 7, ["keyword"])
    conn.execute("DELETE FROM material")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM annotation").fetchone()[0] == 0

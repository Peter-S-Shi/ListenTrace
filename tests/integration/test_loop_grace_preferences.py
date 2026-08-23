from __future__ import annotations

import pytest

from listentrace.application.errors import LoopGraceValidationError
from listentrace.application.services import loop_grace_service
from listentrace.domain.models.material import Material
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import insert_material


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def material_id(conn):
    return insert_material(conn, Material(title="Lesson", media_path="m.mp4"))


def test_global_default_is_200_immediately_after_migration(conn):
    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 200


def test_set_global_loop_end_grace_ms(conn):
    loop_grace_service.set_global_loop_end_grace_ms(conn, 240)
    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 240


def test_set_global_rejects_a_value_below_the_minimum(conn):
    with pytest.raises(LoopGraceValidationError) as exc_info:
        loop_grace_service.set_global_loop_end_grace_ms(conn, 59)
    assert exc_info.value.category == "invalid_loop_end_grace_ms"


def test_set_global_rejects_a_value_above_the_maximum(conn):
    with pytest.raises(LoopGraceValidationError):
        loop_grace_service.set_global_loop_end_grace_ms(conn, 301)


def test_material_with_no_override_has_none(conn, material_id):
    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) is None


def test_effective_grace_inherits_the_global_default_when_no_override(conn, material_id):
    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 200
    loop_grace_service.set_global_loop_end_grace_ms(conn, 220)
    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 220


def test_material_override_wins_over_the_global_default(conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) == 90
    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 90


def test_changing_the_global_default_does_not_touch_a_material_override(conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    loop_grace_service.set_global_loop_end_grace_ms(conn, 250)
    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 90


def test_set_material_override_rejects_out_of_range_values(conn, material_id):
    with pytest.raises(LoopGraceValidationError):
        loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 59)
    with pytest.raises(LoopGraceValidationError):
        loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 301)


def test_reset_to_global_removes_the_override_and_resumes_inheritance(conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    loop_grace_service.reset_material_loop_end_grace_override(conn, material_id)

    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) is None
    # inheritance resumes -- must follow the *current* global, not a copy of
    # whatever the global was at the moment of the override.
    loop_grace_service.set_global_loop_end_grace_ms(conn, 210)
    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 210


def test_reset_to_global_is_a_no_op_when_there_was_no_override(conn, material_id):
    loop_grace_service.reset_material_loop_end_grace_override(conn, material_id)
    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) is None


def test_effective_grace_clamps_an_already_persisted_out_of_range_global_value(conn):
    """Defensive backstop: write-time rejection is the primary defense, but a
    value that got into the row some other way (future migration issue,
    manual DB edit) must not silently become an uncontrolled runtime value."""
    conn.execute("UPDATE loop_grace_preference SET grace_ms = 5000 WHERE id = 1")
    conn.commit()
    assert loop_grace_service.effective_loop_end_grace_ms(conn, 1) == 300


def test_effective_grace_falls_back_to_the_domain_default_if_the_global_row_is_missing(conn):
    conn.execute("DELETE FROM loop_grace_preference")
    conn.commit()
    assert loop_grace_service.effective_loop_end_grace_ms(conn, 1) == 200


def test_material_deletion_cascades_the_override(conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    conn.execute("DELETE FROM material WHERE id = ?", (material_id,))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM material_loop_grace_override WHERE material_id = ?", (material_id,)
    ).fetchone()
    assert row is None

from __future__ import annotations

import pytest

from listentrace.application.services import loop_grace_service
from listentrace.domain.models.material import Material
from listentrace.domain.services.loop_grace_policy import LOOP_END_GRACE_STEP_MS
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.db.repository import insert_material
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.material_loop_settings_dialog import MaterialLoopSettingsDialog


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def material_id(conn):
    return insert_material(conn, Material(title="Lesson", media_path="m.mp4"))


def test_opens_showing_inherit_state_by_default(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    assert dialog._inherit_radio.isChecked() is True
    assert dialog._custom_radio.isChecked() is False
    assert "180" in dialog._effective_label.text()
    dialog.close()


def test_opens_showing_custom_state_when_an_override_already_exists(qapp, conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    assert dialog._custom_radio.isChecked() is True
    assert dialog._value_slider.value() == 90
    assert dialog._value_spinbox.value() == 90
    dialog.close()


def test_switching_to_custom_persists_immediately_starting_from_the_effective_value(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    dialog._custom_radio.setChecked(True)

    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) == 180
    dialog.close()


def test_adjusting_the_spinbox_persists_immediately_to_any_integer(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    dialog._custom_radio.setChecked(True)

    dialog._value_spinbox.setValue(183)

    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) == 183
    assert "183" in dialog._effective_label.text()
    dialog.close()


def test_dragging_the_slider_to_a_non_multiple_of_ten_snaps_the_persisted_value(qapp, conn, material_id):
    """Regression: QSlider.singleStep/pageStep only govern keyboard/wheel
    increments, not mouse-drag values -- a drag can land the slider on any
    integer in range. Only the slider must snap; the spinbox stays free."""
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    dialog._custom_radio.setChecked(True)

    dialog._value_slider.setValue(183)  # simulates a mouse-drag landing off-grid

    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) == 180
    assert dialog._value_slider.value() == 180
    assert dialog._value_spinbox.value() == 180
    dialog.close()


def test_spinbox_is_not_restricted_to_multiples_of_ten(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    assert dialog._value_spinbox.singleStep() == 1
    assert dialog._value_slider.singleStep() == 10
    dialog.close()


def test_reset_to_global_deletes_the_override_and_switches_back_to_inherit(qapp, conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")

    dialog._reset_button.click()

    assert loop_grace_service.get_material_loop_end_grace_override_ms(conn, material_id) is None
    assert dialog._inherit_radio.isChecked() is True
    dialog.close()


def test_reset_to_global_does_not_copy_the_current_global_value(qapp, conn, material_id):
    loop_grace_service.set_global_loop_end_grace_ms(conn, 300)
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")

    dialog._reset_button.click()
    loop_grace_service.set_global_loop_end_grace_ms(conn, 60)

    assert loop_grace_service.effective_loop_end_grace_ms(conn, material_id) == 60
    dialog.close()


def test_bounds_are_enforced_by_the_controls_not_just_the_backend(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    assert dialog._value_spinbox.minimum() == 60
    assert dialog._value_spinbox.maximum() == 300
    assert dialog._value_slider.minimum() == 60
    assert dialog._value_slider.maximum() == 300
    dialog.close()


def test_switching_to_custom_emits_material_override_changed(qapp, conn, material_id):
    received = []
    loop_grace_change_bus.material_override_changed.connect(lambda mid: received.append(mid))
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")

    dialog._custom_radio.setChecked(True)

    assert received == [material_id]
    dialog.close()


def test_adjusting_the_value_emits_material_override_changed(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    dialog._custom_radio.setChecked(True)

    received = []
    loop_grace_change_bus.material_override_changed.connect(lambda mid: received.append(mid))
    dialog._value_spinbox.setValue(220)

    assert received == [material_id]
    dialog.close()


def test_a_second_open_dialog_for_the_same_material_stays_in_sync(qapp, conn, material_id):
    """Regression: if the same Material is open (e.g. via two windows) with
    two Loop Settings dialogs, a change persisted in one must not leave the
    other showing a stale inherit/custom state and value."""
    first = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    second = MaterialLoopSettingsDialog(conn, material_id, "Lesson")

    first._custom_radio.setChecked(True)
    first._value_spinbox.setValue(220)

    assert second._custom_radio.isChecked() is True
    assert second._value_spinbox.value() == 220
    first.close()
    second.close()


def test_slider_step_matches_the_authoritative_domain_policy_constant(qapp, conn, material_id):
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")
    assert dialog._value_slider.singleStep() == LOOP_END_GRACE_STEP_MS
    dialog.close()


def test_reset_emits_material_override_changed(qapp, conn, material_id):
    loop_grace_service.set_material_loop_end_grace_override_ms(conn, material_id, 90)
    dialog = MaterialLoopSettingsDialog(conn, material_id, "Lesson")

    received = []
    loop_grace_change_bus.material_override_changed.connect(lambda mid: received.append(mid))
    dialog._reset_button.click()

    assert received == [material_id]
    dialog.close()

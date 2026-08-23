from __future__ import annotations

import pytest

from listentrace.application.services import loop_grace_service
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.playback_settings_dialog import PlaybackSettingsDialog


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test.db")
    migrate(connection)
    yield connection
    connection.close()


def test_opens_showing_the_currently_saved_global_default(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    assert dialog._value_spinbox.value() == 180
    assert dialog._value_slider.value() == 180
    dialog.close()


def test_adjusting_the_controls_does_not_persist_until_apply(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(260)

    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 180, "must still be the old value"
    dialog.close()


def test_apply_persists_the_draft_value(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(260)
    dialog._apply_button.click()

    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 260
    dialog.close()


def test_cancel_discards_the_draft_and_never_persists(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(260)
    dialog._cancel_button.click()

    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 180
    assert dialog._value_spinbox.value() == 180, "the dialog's own display must revert too"
    dialog.close()


def test_apply_emits_global_default_changed(qapp, conn):
    received = []
    loop_grace_change_bus.global_default_changed.connect(lambda: received.append(True))
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(150)
    dialog._apply_button.click()

    assert received == [True]
    dialog.close()


def test_cancel_does_not_emit_global_default_changed(qapp, conn):
    received = []
    loop_grace_change_bus.global_default_changed.connect(lambda: received.append(True))
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(150)
    dialog._cancel_button.click()

    assert received == []
    dialog.close()


def test_bounds_are_enforced_by_the_controls(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    assert dialog._value_spinbox.minimum() == 60
    assert dialog._value_spinbox.maximum() == 300
    assert dialog._value_spinbox.singleStep() == 1
    assert dialog._value_slider.singleStep() == 10
    dialog.close()


def test_slider_step_matches_the_authoritative_domain_policy_constant(qapp, conn):
    from listentrace.domain.services.loop_grace_policy import LOOP_END_GRACE_STEP_MS

    dialog = PlaybackSettingsDialog(conn)
    assert dialog._value_slider.singleStep() == LOOP_END_GRACE_STEP_MS
    dialog.close()


def test_reshowing_a_reused_instance_discards_a_dirty_unsaved_draft(qapp, conn):
    """Regression: MainWindow caches and reuses one dialog instance. If the
    learner drags the slider then clicks Close (not Cancel, not Apply), the
    dirty draft must not still be showing the next time this same cached
    instance is shown -- it must reflect the actual persisted value."""
    dialog = PlaybackSettingsDialog(conn)
    dialog._value_spinbox.setValue(260)
    dialog.close()  # Close, not Cancel -- leaves a dirty, unapplied draft

    dialog.show()

    assert dialog._value_spinbox.value() == 180
    assert dialog._apply_button.isEnabled() is False
    dialog.close()


def test_apply_and_cancel_buttons_are_disabled_until_the_value_changes(qapp, conn):
    dialog = PlaybackSettingsDialog(conn)
    assert dialog._apply_button.isEnabled() is False
    assert dialog._cancel_button.isEnabled() is False

    dialog._value_spinbox.setValue(200)
    assert dialog._apply_button.isEnabled() is True
    assert dialog._cancel_button.isEnabled() is True

    dialog._apply_button.click()
    assert dialog._apply_button.isEnabled() is False
    assert dialog._cancel_button.isEnabled() is False
    dialog.close()

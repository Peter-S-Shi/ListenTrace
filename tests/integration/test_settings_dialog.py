from __future__ import annotations

import pytest

from listentrace.application.services import label_preference_service, loop_grace_service
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus
from listentrace.ui.windows.settings_dialog import SettingsDialog


@pytest.fixture()
def conn(tmp_path):
    connection = open_connection(tmp_path / "test_settings.db")
    migrate(connection)
    yield connection
    connection.close()


def test_settings_dialog_initialization_and_tabs(qapp, conn):
    dialog = SettingsDialog(conn)
    assert dialog._tabs.count() == 2
    assert dialog._tabs.tabText(0) == "Playback"
    assert dialog._tabs.tabText(1) == "Label Colors"
    assert dialog._value_spinbox.value() == 200
    assert dialog._value_slider.value() == 200
    assert len(dialog._color_buttons) == 5
    dialog.close()


def test_settings_dialog_playback_apply_and_cancel(qapp, conn):
    received = []
    loop_grace_change_bus.global_default_changed.connect(lambda: received.append(True))

    dialog = SettingsDialog(conn)
    dialog._value_spinbox.setValue(250)
    assert dialog._apply_button.isEnabled() is True
    assert dialog._cancel_button.isEnabled() is True

    # Cancel reverts
    dialog._cancel_button.click()
    assert dialog._value_spinbox.value() == 200
    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 200
    assert received == []

    # Apply persists and emits bus signal
    dialog._value_spinbox.setValue(280)
    dialog._apply_button.click()
    assert loop_grace_service.get_global_loop_end_grace_ms(conn) == 280
    assert received == [True]
    dialog.close()


def test_settings_dialog_label_colors_category(qapp, conn):
    dialog = SettingsDialog(conn)
    # Check that each annotation category is represented
    assert "keyword" in dialog._color_buttons
    assert "known_not_heard" in dialog._color_buttons

    # Directly test updating a label color
    label_preference_service.update_label_color(conn, "keyword", "#123456")
    dialog.show()  # triggers showEvent refresh
    assert dialog._color_buttons["keyword"].text() == "#123456"
    dialog.close()

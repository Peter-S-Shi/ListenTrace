from __future__ import annotations

from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.ui.windows.main_window import MainWindow


def test_main_window_starts_with_initialized_database(qapp, tmp_path):
    db_path = tmp_path / "smoke.db"
    connection = open_connection(db_path)
    migrate(connection)

    window = MainWindow(connection, db_path)

    assert window.windowTitle() == "ListenTrace"
    assert "Schema version: 1" in window._status_label.text()

    window.close()

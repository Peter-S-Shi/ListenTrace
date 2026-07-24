from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from listentrace.application.services.recording_service import recover_interrupted_recordings
from listentrace.infrastructure.appdata import get_database_path, get_recordings_dir
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.logging_setup import configure_logging
from listentrace.ui.windows.main_window import MainWindow


def main() -> int:
    logger = configure_logging()
    app = QApplication(sys.argv)

    db_path = get_database_path()
    recordings_dir = get_recordings_dir()
    try:
        connection = open_connection(db_path)
        migrate(connection)
        recovered = recover_interrupted_recordings(connection, recordings_dir)
        if recovered:
            logger.warning("Recovered %d recording(s) left in-progress by a prior run", recovered)
    except Exception as exc:
        logger.exception("Failed to initialize the local database")
        QMessageBox.critical(None, "ListenTrace — Startup Error", f"Could not start ListenTrace:\n{exc}")
        return 1

    window = MainWindow(connection, db_path, recordings_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

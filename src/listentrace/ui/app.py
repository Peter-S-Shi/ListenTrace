from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from listentrace.application.services.quick_practice_service import recover_interrupted_sessions
from listentrace.application.services.recording_service import recover_interrupted_recordings
from listentrace.infrastructure.appdata import get_database_path, get_recordings_dir
from listentrace.infrastructure.db.connection import open_connection
from listentrace.infrastructure.db.migrations import migrate
from listentrace.infrastructure.logging_setup import configure_logging
from listentrace.ui.windows.main_window import MainWindow


def _install_crash_logging(logger: logging.Logger) -> None:
    """A windowed build (`console=False`, see `packaging/listentrace.spec`)
    has no visible console at all -- an unhandled exception during normal
    use would otherwise leave zero diagnostic trail anywhere on a real
    user's machine. Logs the full traceback to the rotating log file before
    still calling whatever hook was previously installed (Python's own
    default, ordinarily), so behavior is unaffected apart from this one
    added log line."""
    previous_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_traceback):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook


def main() -> int:
    """`QApplication` is constructed before anything else that could fail.
    Resolving the app-data directory, configuring logging, and opening or
    migrating the database can all raise on a machine this app has never run
    on before (permission denied, a locked/read-only profile, disk full) --
    without a `QApplication` instance already existing, `QMessageBox.critical`
    cannot show anything at all, and an unhandled exception this early in a
    windowed frozen build terminates the process with zero visible feedback:
    to a real user, the app would simply appear to do nothing when launched.
    Reuses an existing instance if one is already running rather than always
    constructing a new one -- this never happens for the real console-script
    entry point, but lets tests exercise this function directly."""
    app = QApplication.instance() or QApplication(sys.argv)

    try:
        logger = configure_logging()
        _install_crash_logging(logger)

        db_path = get_database_path()
        recordings_dir = get_recordings_dir()
        connection = open_connection(db_path)
        migrate(connection)
        recovered = recover_interrupted_recordings(connection, recordings_dir)
        if recovered:
            logger.warning("Recovered %d recording(s) left in-progress by a prior run", recovered)
        recovered_quick_practice = recover_interrupted_sessions(connection)
        if recovered_quick_practice:
            logger.warning(
                "Recovered %d Quick Practice run(s) left in-progress by a prior run", recovered_quick_practice
            )
    except Exception as exc:
        # `logging.getLogger` (rather than a possibly-unbound `logger` local)
        # is deliberate: `configure_logging()` itself is inside this same try
        # block and may be what failed, so `logger` might never have been
        # assigned. `getLogger` always returns a usable Logger regardless --
        # a harmless no-op if no handler was ever attached to it.
        logging.getLogger("listentrace").exception("Failed to start ListenTrace")
        QMessageBox.critical(None, "ListenTrace — Startup Error", f"Could not start ListenTrace:\n{exc}")
        return 1

    window = MainWindow(connection, db_path, recordings_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

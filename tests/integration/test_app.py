from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QMessageBox

from listentrace.ui import app as app_module
from listentrace.ui.theme import get_app_icon


def test_install_crash_logging_logs_and_still_calls_the_previous_hook(caplog):
    """`_install_crash_logging` must not silently replace error handling --
    it should log the traceback (the only diagnostic trail available on a
    windowed frozen build, which has no visible console) and then still
    delegate to whatever hook was previously installed."""
    logger = logging.getLogger("listentrace_test_crash_hook")
    logger.setLevel(logging.CRITICAL)
    delegated_calls = []
    original_hook = lambda exc_type, exc_value, exc_tb: delegated_calls.append((exc_type, exc_value))  # noqa: E731
    previous = sys.excepthook
    sys.excepthook = original_hook
    try:
        app_module._install_crash_logging(logger)
        installed_hook = sys.excepthook
        assert installed_hook is not original_hook

        try:
            raise ValueError("boom")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()

        with caplog.at_level(logging.CRITICAL, logger="listentrace_test_crash_hook"):
            installed_hook(exc_type, exc_value, exc_tb)

        assert delegated_calls == [(exc_type, exc_value)]
        assert "Unhandled exception" in caplog.text
    finally:
        sys.excepthook = previous


def test_main_reports_a_friendly_error_when_startup_fails_before_appdata_is_ready(qapp, monkeypatch):
    """Regression test for a real gap caught during Post-M10 Phase B:
    `configure_logging`/app-data resolution used to run before `QApplication`
    was constructed, so a failure there (permission denied creating
    `%APPDATA%\\ListenTrace`, a locked profile, disk full) had no
    `QApplication` instance available to show a `QMessageBox` with --
    an unhandled exception this early in a windowed (console=False) frozen
    build would terminate the process with zero visible feedback to the
    user. `QApplication` is now constructed first, so even a failure this
    early can still show a friendly dialog and return cleanly instead of
    crashing."""
    monkeypatch.setattr(
        app_module,
        "configure_logging",
        lambda: (_ for _ in ()).throw(OSError("permission denied creating the app-data directory")),
    )
    calls = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: calls.append(args))

    result = app_module.main()

    assert result == 1
    assert len(calls) == 1
    parent, title, message = calls[0]
    assert title == "ListenTrace — Startup Error"
    assert "Could not start ListenTrace" in message
    assert "permission denied" in message


def test_main_sets_windows_app_user_model_id_before_anything_qapplication_dependent(qapp, monkeypatch, tmp_path):
    """Regression test for the M14 pre-merge Windows taskbar-identity fix:
    `set_windows_app_user_model_id()` must run before the app-data/database
    setup that can fail and show a `QMessageBox` -- otherwise a startup
    failure could show that dialog under the wrong (generic `python.exe`)
    taskbar identity."""
    call_order = []
    monkeypatch.setattr(
        app_module,
        "set_windows_app_user_model_id",
        lambda: call_order.append("identity") or True,
    )
    monkeypatch.setattr(
        app_module, "get_database_path", lambda: call_order.append("db_path") or tmp_path / "listentrace.db"
    )
    monkeypatch.setattr(app_module, "get_recordings_dir", lambda: tmp_path / "recordings")
    # Stop before a real MainWindow/event loop would be reached -- this test
    # only needs to observe call order, not run the app.
    monkeypatch.setattr(
        app_module,
        "open_connection",
        lambda db_path: (_ for _ in ()).throw(OSError("stop before a real MainWindow is constructed")),
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    result = app_module.main()

    assert result == 1
    assert call_order[0] == "identity"


def test_main_sets_qt_application_identity_metadata(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "get_database_path", lambda: tmp_path / "listentrace.db")
    monkeypatch.setattr(app_module, "get_recordings_dir", lambda: tmp_path / "recordings")
    monkeypatch.setattr(
        app_module,
        "open_connection",
        lambda db_path: (_ for _ in ()).throw(OSError("stop before a real MainWindow is constructed")),
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    app_module.main()

    assert qapp.applicationName() == "ListenTrace"
    assert qapp.applicationDisplayName() == "ListenTrace"


def test_app_icon_still_resolves():
    icon = get_app_icon()
    assert not icon.isNull()


def test_main_reports_a_friendly_error_when_database_initialization_fails(qapp, monkeypatch, tmp_path):
    # Keep this test hermetic -- point app-data resolution at tmp_path rather
    # than letting `main()` touch the real machine's %APPDATA%\ListenTrace.
    monkeypatch.setattr(app_module, "get_database_path", lambda: tmp_path / "listentrace.db")
    monkeypatch.setattr(app_module, "get_recordings_dir", lambda: tmp_path / "recordings")
    monkeypatch.setattr(
        app_module,
        "open_connection",
        lambda db_path: (_ for _ in ()).throw(OSError("disk full")),
    )
    calls = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: calls.append(args))

    result = app_module.main()

    assert result == 1
    assert len(calls) == 1

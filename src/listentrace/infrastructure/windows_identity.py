from __future__ import annotations

import ctypes
import sys

APP_USER_MODEL_ID = "ListenTrace.Desktop"
"""Stable, product-only Windows Shell application identity — no personal
name, no version number (so it survives releases unchanged). Used only for
`SetCurrentProcessExplicitAppUserModelID`, never shown to the user directly."""


def set_windows_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """Tells the Windows shell this process is its own distinct application,
    so the taskbar groups it separately instead of inheriting the hosting
    interpreter's (`python.exe` in source-mode runs) generic identity, which
    is what makes two unrelated PySide6 apps appear grouped as one on the
    taskbar. Must be called before `QApplication`/any top-level window is
    created -- the shell reads this once, at first window creation. No-op on
    any non-Windows platform. Returns whether the call was made."""
    if sys.platform != "win32":
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)  # type: ignore[attr-defined]
        return True
    except (AttributeError, OSError):
        return False

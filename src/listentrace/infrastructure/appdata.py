from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ListenTrace"


def get_app_data_dir() -> Path:
    """Return the per-user application-data directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        root = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        root = Path(base) / APP_NAME

    root.mkdir(parents=True, exist_ok=True)
    return root


def get_database_path() -> Path:
    return get_app_data_dir() / "listentrace.db"


def get_log_dir() -> Path:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

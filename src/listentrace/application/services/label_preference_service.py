from __future__ import annotations

import re
import sqlite3

from listentrace.application.errors import AnnotationValidationError
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.infrastructure.db.learning_repository import get_label_preferences as _repo_get
from listentrace.infrastructure.db.learning_repository import update_label_color as _repo_update

_VALID_LABELS = {label.value for label in AnnotationLabel}
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def get_label_preferences(conn: sqlite3.Connection) -> dict[str, str]:
    return _repo_get(conn)


def update_label_color(conn: sqlite3.Connection, label_key: str, color: str) -> None:
    if label_key not in _VALID_LABELS:
        raise AnnotationValidationError("invalid_label", f"Unknown label: {label_key!r}")
    if not _HEX_COLOR_RE.match(color or ""):
        raise AnnotationValidationError(
            "invalid_color", f"Color must be a 6-digit hex value like #2563EB, got {color!r}"
        )
    _repo_update(conn, label_key, color)

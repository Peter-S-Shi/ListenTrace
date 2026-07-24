from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

"""Filesystem helpers for Milestone 9 (Structured Export). Kept out of both
`application/services/export_service.py` (which never touches a filesystem)
and the UI layer (which should not own write mechanics) — a narrow adapter,
mirroring how `infrastructure/media/*.py` wraps QtMultimedia."""

_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_export_filename(label: str) -> str:
    """A filesystem-safe stem (no extension) derived from a scope/material
    label and today's date — never the original material's real filename."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", label).strip().strip(".")
    cleaned = re.sub(r"_+", "_", cleaned) or "listentrace_export"
    return cleaned[:80]


def atomic_write_text(path: Path, content: str) -> None:
    """Writes `content` to `path` atomically: the full content is written to
    a sibling temp file first, then moved into place with `os.replace`
    (atomic on the same filesystem) — `path` either ends up with the
    complete new content or is left completely untouched; it is never
    observed half-written. On any failure, the temp file is cleaned up
    (best-effort) and the original exception is re-raised so the caller
    never reports success for a failed write."""
    tmp_path = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise

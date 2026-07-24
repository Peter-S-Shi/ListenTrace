from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Material:
    title: str
    media_path: str
    language: str | None = None
    media_kind: str | None = None
    duration_ms: int | None = None
    file_size_bytes: int | None = None
    file_fingerprint: str | None = None
    status: str = "active"
    id: int | None = None

from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.material_status import MaterialStatus


@dataclass(slots=True)
class Material:
    title: str
    media_path: str
    normalized_path: str | None = None
    language: str | None = None
    media_kind: str | None = None
    duration_ms: int | None = None
    file_size_bytes: int | None = None
    file_fingerprint: str | None = None
    status: str = MaterialStatus.ACTIVE.value
    id: int | None = None

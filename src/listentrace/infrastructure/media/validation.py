from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

_FINGERPRINT_SAMPLE_BYTES = 1024 * 1024  # 1 MiB from each end; avoids hashing large media in full


class MediaValidationError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(slots=True)
class MediaFileInfo:
    media_kind: str
    size_bytes: int


def normalize_media_path(path: Path | str) -> str:
    resolved = Path(path).expanduser().resolve()
    return str(resolved).casefold()


def validate_media_file(path: Path | str) -> MediaFileInfo:
    file_path = Path(path)

    if not file_path.exists():
        raise MediaValidationError("media_not_found", f"Media file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in _AUDIO_EXTENSIONS:
        media_kind = "audio"
    elif suffix in _VIDEO_EXTENSIONS:
        media_kind = "video"
    else:
        raise MediaValidationError(
            "media_unsupported", f"Unsupported media file type: {suffix!r}"
        )

    try:
        size_bytes = file_path.stat().st_size
        with file_path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise MediaValidationError(
            "media_unreadable", f"Media file could not be read: {exc}"
        ) from exc

    return MediaFileInfo(media_kind=media_kind, size_bytes=size_bytes)


def compute_file_fingerprint(path: Path | str) -> str:
    file_path = Path(path)
    size_bytes = file_path.stat().st_size

    digest = hashlib.sha256()
    digest.update(str(size_bytes).encode("utf-8"))

    with file_path.open("rb") as handle:
        digest.update(handle.read(_FINGERPRINT_SAMPLE_BYTES))
        if size_bytes > _FINGERPRINT_SAMPLE_BYTES:
            handle.seek(max(size_bytes - _FINGERPRINT_SAMPLE_BYTES, 0))
            digest.update(handle.read(_FINGERPRINT_SAMPLE_BYTES))

    return digest.hexdigest()

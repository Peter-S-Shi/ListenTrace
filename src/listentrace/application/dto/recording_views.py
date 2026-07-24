from __future__ import annotations

from dataclasses import dataclass, field

from listentrace.infrastructure.media.recording import AudioInputDevice


@dataclass(slots=True)
class DeviceResolution:
    """The result of resolving which microphone to use. `device` is `None` only
    when nothing usable is available — a saved-but-now-missing preference is
    never silently swapped for a different device; the caller must surface
    `fallback_reason` and let the learner choose explicitly."""

    device: AudioInputDevice | None
    fallback_reason: str | None = None


@dataclass(slots=True)
class DeletionSummary:
    """Result of a bulk (cue-wide or material-wide) recording deletion. A file
    that failed to delete is reported here rather than silently dropped or
    falsely counted as removed — its database row is left intact."""

    deleted_ids: list[int] = field(default_factory=list)
    failed: list[tuple[int, str]] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return not self.failed

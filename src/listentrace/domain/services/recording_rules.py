from __future__ import annotations

from listentrace.domain.enums.recording_status import RecordingStatus

# Pure, framework-free recording rules. No sqlite, no Qt, no filesystem access:
# the application layer performs the actual capture/file-validation work and
# calls these functions for the small amount of decision logic worth isolating
# and unit-testing directly.

_RECORDING_TRANSITIONS: dict[str, frozenset[str]] = {
    RecordingStatus.RECORDING.value: frozenset({RecordingStatus.READY.value, RecordingStatus.FAILED.value}),
}


def is_valid_recording_transition(current_status: str, new_status: str) -> bool:
    """A take can only leave `recording` for `ready` or `failed`, exactly once.
    `ready`/`failed` are terminal statuses — a take is never re-scored or
    reopened; deleting it removes the row entirely rather than transitioning it."""
    return new_status in _RECORDING_TRANSITIONS.get(current_status, frozenset())


def build_relative_recording_path(material_id: int, filename: str) -> str:
    """The managed, app-relative storage path for one take's audio file. Grouped
    by material so a material's recordings are easy to locate and bulk-delete;
    `filename` itself must already be a collision-resistant, non-personal name
    (the application layer generates it, e.g. via `uuid4()`) — no material title,
    transcript text, or other personal/content-derived text belongs in it."""
    return f"{material_id}/{filename}"

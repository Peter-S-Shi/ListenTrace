from __future__ import annotations

from enum import Enum


class RecordingStatus(str, Enum):
    """A take's lifecycle while its row exists. `deleted` (from the product
    lifecycle description) is deliberately not a stored value here: deleting a
    take is a hard removal of both the database row and the managed file (see
    `recording_service.delete_take`), not a soft status flag — a `deleted` row
    with no backing file would be a broken reference, not history worth keeping.
    """

    RECORDING = "recording"
    READY = "ready"
    FAILED = "failed"

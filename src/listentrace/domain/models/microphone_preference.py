from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MicrophonePreference:
    """The learner's remembered microphone choice, app-wide (one row)."""

    device_id: str
    device_description: str
    updated_at: str | None = None

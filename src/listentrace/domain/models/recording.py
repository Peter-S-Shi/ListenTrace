from __future__ import annotations

from dataclasses import dataclass

from listentrace.domain.enums.recording_status import RecordingStatus


@dataclass(slots=True)
class Recording:
    material_id: int
    subtitle_cue_id: int
    relative_file_path: str
    format: str = "wav"
    practice_session_id: int | None = None
    duration_ms: int | None = None
    device_descriptor: str | None = None
    status: str = RecordingStatus.RECORDING.value
    failure_detail: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    id: int | None = None

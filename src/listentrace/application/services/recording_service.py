from __future__ import annotations

import sqlite3
import uuid
import wave
from pathlib import Path

from listentrace.application.dto.recording_views import DeletionSummary, DeviceResolution
from listentrace.application.errors import RecordingNotFoundError, RecordingValidationError
from listentrace.domain.enums.recording_status import RecordingStatus
from listentrace.domain.models.recording import Recording
from listentrace.domain.services import recording_rules as rules
from listentrace.infrastructure.db import recording_repository as repo
from listentrace.infrastructure.db.learning_repository import get_material_id_for_subtitle_cue
from listentrace.infrastructure.db.session_repository import get_practice_session
from listentrace.infrastructure.media.recording import AudioInputDevice, list_audio_input_devices

_INTERRUPTED_DETAIL = "Interrupted: the application closed or crashed while this recording was in progress."


# ---- internal guards ----


def _require_recording(conn: sqlite3.Connection, recording_id: int) -> Recording:
    recording = repo.get_recording(conn, recording_id)
    if recording is None:
        raise RecordingNotFoundError(recording_id)
    return recording


def _require_in_progress(conn: sqlite3.Connection, recording_id: int) -> Recording:
    recording = _require_recording(conn, recording_id)
    if recording.status != RecordingStatus.RECORDING.value:
        raise RecordingValidationError(
            "invalid_transition", f"Recording {recording_id} is not in progress (status={recording.status!r})."
        )
    return recording


def _absolute_path(recordings_dir: Path, recording: Recording) -> Path:
    return recordings_dir / recording.relative_file_path


def _delete_file_best_effort(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _validate_wav_file(path: Path) -> tuple[bool, int]:
    """Returns (is_valid, duration_ms). A missing file, an unparseable file, or
    zero audio frames are all treated as an invalid capture — never as a normal
    playable take."""
    if not path.exists() or path.stat().st_size == 0:
        return False, 0
    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if frames <= 0 or rate <= 0:
                return False, 0
            duration_ms = int(frames * 1000 / rate)
            return duration_ms > 0, duration_ms
    except (wave.Error, EOFError, OSError):
        return False, 0


# ---- device selection ----


def list_input_devices() -> list[AudioInputDevice]:
    return list_audio_input_devices()


def resolve_preferred_device(conn: sqlite3.Connection) -> DeviceResolution:
    """Decide which device to preselect: the remembered choice if it is still
    connected, otherwise the system default if any device exists at all — but
    never a silent substitute for a saved device that has disappeared; that case
    is surfaced via `fallback_reason` so the UI can tell the learner and let
    them pick again."""
    devices = list_audio_input_devices()
    preference = repo.get_microphone_preference(conn)

    if preference is not None:
        match = next((d for d in devices if d.device_id == preference.device_id), None)
        if match is not None:
            return DeviceResolution(device=match, fallback_reason=None)
        if devices:
            return DeviceResolution(
                device=None,
                fallback_reason=(
                    f"Your saved microphone ({preference.device_description!r}) is no longer available. "
                    "Please choose another."
                ),
            )
        return DeviceResolution(
            device=None,
            fallback_reason=(
                f"Your saved microphone ({preference.device_description!r}) is no longer available, "
                "and no other microphone was found."
            ),
        )

    if devices:
        default_device = next((d for d in devices if d.is_default), devices[0])
        return DeviceResolution(device=default_device, fallback_reason=None)

    return DeviceResolution(device=None, fallback_reason="No microphone was found on this system.")


def remember_device_choice(conn: sqlite3.Connection, device_id: str, device_description: str) -> None:
    repo.set_microphone_preference(conn, device_id, device_description)


# ---- recording lifecycle ----


def begin_recording(
    conn: sqlite3.Connection,
    recordings_dir: Path,
    material_id: int,
    subtitle_cue_id: int,
    device_id: str,
    device_description: str,
    practice_session_id: int | None = None,
) -> tuple[Recording, Path]:
    """Validates ownership, enforces the single-active-recording rule, and
    creates the `recording` row (status `recording`) before any audio is
    captured. Returns the row and the absolute path the caller's
    `RecordingController` should write to."""
    if get_material_id_for_subtitle_cue(conn, subtitle_cue_id) != material_id:
        raise RecordingValidationError(
            "cue_material_mismatch", "This cue does not belong to the given material."
        )
    if practice_session_id is not None:
        session = get_practice_session(conn, practice_session_id)
        if session is None or session.material_id != material_id:
            raise RecordingValidationError(
                "session_material_mismatch", "This practice session does not belong to the given material."
            )
    if repo.list_recordings_with_status(conn, RecordingStatus.RECORDING.value):
        raise RecordingValidationError(
            "recording_in_progress", "Another recording is already in progress. Stop it before starting a new one."
        )

    filename = f"{uuid.uuid4().hex}.wav"
    relative_path = rules.build_relative_recording_path(material_id, filename)
    absolute_path = recordings_dir / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    recording = Recording(
        material_id=material_id,
        subtitle_cue_id=subtitle_cue_id,
        practice_session_id=practice_session_id,
        relative_file_path=relative_path,
        device_descriptor=device_description,
    )
    recording.id = repo.insert_recording(conn, recording)
    return recording, absolute_path


def finish_recording(conn: sqlite3.Connection, recordings_dir: Path, recording_id: int) -> Recording:
    """Validates the captured file and transitions the take to `ready` (usable)
    or `failed` (invalid/zero-length capture — the file is removed, the row is
    kept so the learner sees *something* happened rather than a silent no-op)."""
    recording = _require_in_progress(conn, recording_id)
    absolute_path = _absolute_path(recordings_dir, recording)

    is_valid, duration_ms = _validate_wav_file(absolute_path)
    if is_valid:
        repo.set_recording_ready(conn, recording_id, duration_ms)
    else:
        _delete_file_best_effort(absolute_path)
        repo.set_recording_failed(conn, recording_id, "The captured audio was empty or invalid.")
    updated = repo.get_recording(conn, recording_id)
    assert updated is not None
    return updated


def fail_recording(
    conn: sqlite3.Connection, recordings_dir: Path, recording_id: int, failure_detail: str
) -> Recording:
    """Marks an in-progress take failed directly — for device/permission/capture
    errors reported before a normal stop, or for a safe abort (navigation,
    window close, app shutdown) while capture was still active."""
    recording = _require_in_progress(conn, recording_id)
    _delete_file_best_effort(_absolute_path(recordings_dir, recording))
    repo.set_recording_failed(conn, recording_id, failure_detail)
    updated = repo.get_recording(conn, recording_id)
    assert updated is not None
    return updated


def recover_interrupted_recordings(conn: sqlite3.Connection, recordings_dir: Path) -> int:
    """Run once at application startup: any row still `recording` was left that
    way by a prior process that never cleanly stopped (crash or forced close),
    since a fresh process cannot own an in-progress capture. Cleans up the
    partial file and marks each one `failed` rather than leaving it stuck,
    which would otherwise permanently block the single-active-recording rule."""
    stale = repo.list_recordings_with_status(conn, RecordingStatus.RECORDING.value)
    for recording in stale:
        _delete_file_best_effort(_absolute_path(recordings_dir, recording))
        repo.set_recording_failed(conn, recording.id, _INTERRUPTED_DETAIL)
    return len(stale)


# ---- listing ----


def get_take(conn: sqlite3.Connection, recording_id: int) -> Recording | None:
    return repo.get_recording(conn, recording_id)


def list_takes_for_cue(conn: sqlite3.Connection, subtitle_cue_id: int) -> list[Recording]:
    return repo.list_recordings_for_cue(conn, subtitle_cue_id)


def list_takes_for_material(conn: sqlite3.Connection, material_id: int) -> list[Recording]:
    return repo.list_recordings_for_material(conn, material_id)


# ---- deletion ----


def delete_take(conn: sqlite3.Connection, recordings_dir: Path, recording_id: int) -> None:
    recording = _require_recording(conn, recording_id)
    if recording.status == RecordingStatus.RECORDING.value:
        raise RecordingValidationError(
            "recording_in_progress", "Stop the recording before deleting it."
        )
    absolute_path = _absolute_path(recordings_dir, recording)
    if absolute_path.exists():
        try:
            absolute_path.unlink()
        except OSError as exc:
            raise RecordingValidationError(
                "file_deletion_failed", f"Could not delete the recording file: {exc}"
            ) from exc
    repo.delete_recording(conn, recording_id)


def delete_takes_for_cue(conn: sqlite3.Connection, recordings_dir: Path, subtitle_cue_id: int) -> DeletionSummary:
    summary = DeletionSummary()
    for take in repo.list_recordings_for_cue(conn, subtitle_cue_id):
        try:
            delete_take(conn, recordings_dir, take.id)
            summary.deleted_ids.append(take.id)
        except RecordingValidationError as exc:
            summary.failed.append((take.id, str(exc)))
    return summary


def delete_takes_for_material(conn: sqlite3.Connection, recordings_dir: Path, material_id: int) -> DeletionSummary:
    summary = DeletionSummary()
    for take in repo.list_recordings_for_material(conn, material_id):
        try:
            delete_take(conn, recordings_dir, take.id)
            summary.deleted_ids.append(take.id)
        except RecordingValidationError as exc:
            summary.failed.append((take.id, str(exc)))
    return summary

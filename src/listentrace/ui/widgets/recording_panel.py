from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.errors import RecordingValidationError
from listentrace.application.services import recording_service
from listentrace.domain.enums.recording_status import RecordingStatus
from listentrace.domain.models.recording import Recording
from listentrace.domain.services.comparison_sequence import COMPARISON_PAUSE_MS, ComparisonSequencer, ComparisonStep
from listentrace.infrastructure.media.playback import PlaybackController
from listentrace.infrastructure.media.recording import AudioInputDevice, RecordingController
from listentrace.ui import theme


class RecordingPanel(QWidget):
    """Shadowing recording UI: device selection, start/stop capture, the take
    list for one cue, take playback, source-vs-take comparison, and deletion.

    The one implementation shared by `GuidedSessionWindow` Stage 4 and the
    standalone `ShadowingPracticeWindow` — per the Milestone 7 requirement that
    both entry points reuse the same recording/playback/comparison/persistence/
    deletion logic rather than two separate recording systems. Every actual
    lifecycle/ownership/deletion decision is delegated to
    `application.services.recording_service`; this widget only wires Qt signals
    to it and renders the result.

    The host window owns *source* cue playback (it already has its own
    `PlaybackController`/`PlayerSession` for that). To run a comparison, this
    panel emits `request_play_source` and waits for the host to call
    `notify_source_finished()` once that one-shot source replay ends — the
    panel then runs its own short pause and plays the take on its own
    `PlaybackController`, never touching the host's player.
    """

    request_play_source = Signal()

    def __init__(self, connection: sqlite3.Connection, recordings_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connection = connection
        self._recordings_dir = recordings_dir

        self._material_id: int | None = None
        self._subtitle_cue_id: int | None = None
        self._practice_session_id: int | None = None
        self._current_context: tuple[int | None, int | None, int | None] | None = None

        self._active_recording: Recording | None = None
        self._pending_action: str | None = None  # "finish" while awaiting RecordingController.recording_stopped
        self._takes: list[Recording] = []
        self._comparison_take: Recording | None = None
        self._privacy_notice_shown = False
        self._read_only = False

        self._recorder = RecordingController(self)
        self._recorder.recording_error.connect(self._on_recording_error)
        self._recorder.recording_stopped.connect(self._on_recorder_stopped)

        self._take_playback = PlaybackController(self)
        self._take_playback.end_of_media.connect(self._on_take_playback_end_of_media)
        self._take_playback.playback_error.connect(self._on_take_playback_error)

        self._sequencer = ComparisonSequencer()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Microphone:"))
        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(self._on_device_selected)
        device_row.addWidget(self._device_combo, 1)
        self._refresh_devices_button = QPushButton("Refresh")
        self._refresh_devices_button.clicked.connect(self.refresh_devices)
        theme.apply_role(self._refresh_devices_button, "quiet")
        device_row.addWidget(self._refresh_devices_button)
        layout.addLayout(device_row)

        self._device_status_label = QLabel("")
        theme.apply_role(self._device_status_label, "error")
        self._device_status_label.setWordWrap(True)
        layout.addWidget(self._device_status_label)

        record_row = QHBoxLayout()
        self._start_recording_button = QPushButton("Start Recording")
        self._start_recording_button.clicked.connect(self._on_start_recording_clicked)
        theme.apply_role(self._start_recording_button, "secondary")
        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.clicked.connect(self._on_stop_recording_clicked)
        theme.apply_role(self._stop_recording_button, "secondary")
        record_row.addWidget(self._start_recording_button)
        record_row.addWidget(self._stop_recording_button)
        layout.addLayout(record_row)

        # Milestone 11: an explicit text state (never color alone) for
        # whether a capture is currently in progress -- distinct from the
        # per-take "ready"/"failed" labels in the takes list below.
        self._recording_state_label = QLabel("")
        theme.apply_role(self._recording_state_label, "caption")
        layout.addWidget(self._recording_state_label)

        layout.addWidget(QLabel("Takes for this cue:"))
        self._takes_list = QListWidget()
        theme.configure_long_text_list(self._takes_list)
        self._takes_list.currentItemChanged.connect(lambda *_: self._update_take_buttons())
        layout.addWidget(self._takes_list)

        take_row = QHBoxLayout()
        self._play_take_button = QPushButton("Play Take")
        self._play_take_button.clicked.connect(self._on_play_take_clicked)
        theme.apply_role(self._play_take_button, "secondary")
        self._compare_button = QPushButton("Compare (Source, then Take)")
        self._compare_button.clicked.connect(self._on_compare_clicked)
        theme.apply_role(self._compare_button, "secondary")
        self._delete_take_button = QPushButton("Delete Take")
        self._delete_take_button.clicked.connect(self._on_delete_take_clicked)
        theme.apply_role(self._delete_take_button, "danger")
        self._delete_cue_takes_button = QPushButton("Delete All Takes for This Cue")
        self._delete_cue_takes_button.clicked.connect(self._on_delete_all_takes_for_cue_clicked)
        theme.apply_role(self._delete_cue_takes_button, "danger")
        for button in (
            self._play_take_button,
            self._compare_button,
            self._delete_take_button,
            self._delete_cue_takes_button,
        ):
            take_row.addWidget(button)
        layout.addLayout(take_row)

        self.refresh_devices()
        self._update_recording_buttons()
        self._update_take_buttons()

    # ---- context ----

    def set_context(
        self, material_id: int, subtitle_cue_id: int | None, practice_session_id: int | None = None
    ) -> None:
        """Call whenever the host refreshes its state. A no-op if the
        (material, cue, session) tuple is unchanged from last time — safe to
        call on every host refresh without disturbing an in-progress recording
        for an unrelated reason (e.g. clicking "Mark Practiced" while
        recording). When the cue genuinely changes, any in-progress recording
        for the previous cue is safely aborted first — never left dangling."""
        new_context = (material_id, subtitle_cue_id, practice_session_id)
        if new_context == self._current_context:
            return
        self.abort_active_recording()
        self.release_take_playback()
        self._material_id, self._subtitle_cue_id, self._practice_session_id = new_context
        self._current_context = new_context
        self._refresh_takes()

    def set_read_only(self, read_only: bool) -> None:
        """A completed/abandoned Guided Session makes Stage 4 read-only for
        every other action; recording follows the same rule — no new takes and
        no deletions, but existing takes remain playable and comparable."""
        self._read_only = read_only
        self._update_recording_buttons()
        self._update_take_buttons()

    def release_take_playback(self) -> None:
        """Stop and unload the take-playback source. `stop()` alone leaves the
        file locked on Windows, which would block deleting a take right after
        playing it — call this before any delete, and whenever the panel is no
        longer showing the take that was loaded (context switch, host close)."""
        self._take_playback.unload()
        if self._sequencer.is_active:
            self._sequencer.cancel()
            self._comparison_take = None
            self._update_take_buttons()

    # ---- devices ----

    def refresh_devices(self) -> None:
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        devices = recording_service.list_input_devices()
        for device in devices:
            self._device_combo.addItem(device.description, device)
        resolution = recording_service.resolve_preferred_device(self._connection)
        if resolution.device is not None:
            index = next(
                (i for i in range(self._device_combo.count()) if self._device_combo.itemData(i).device_id == resolution.device.device_id),
                -1,
            )
            self._device_combo.setCurrentIndex(index)
        else:
            # No device to preselect — including when a remembered device is no
            # longer connected. Leave the combo unselected rather than falling
            # back to whatever Qt would otherwise default to (the first item);
            # the learner must explicitly choose before recording is allowed.
            self._device_combo.setCurrentIndex(-1)
        self._device_combo.blockSignals(False)
        self._device_status_label.setText(resolution.fallback_reason or "")
        self._update_recording_buttons()

    def _selected_device(self) -> AudioInputDevice | None:
        index = self._device_combo.currentIndex()
        if index < 0:
            return None
        return self._device_combo.itemData(index)

    def _on_device_selected(self, index: int) -> None:
        device = self._selected_device()
        if device is not None:
            recording_service.remember_device_choice(self._connection, device.device_id, device.description)
            self._device_status_label.setText("")
        self._update_recording_buttons()

    # ---- recording lifecycle ----

    def _on_start_recording_clicked(self) -> None:
        if self._material_id is None or self._subtitle_cue_id is None:
            return
        if self._recorder.is_recording or self._active_recording is not None:
            return
        device = self._selected_device()
        if device is None:
            QMessageBox.warning(self, "No Microphone Selected", "Choose a microphone before recording.")
            return

        if not self._privacy_notice_shown:
            QMessageBox.information(
                self,
                "Microphone Access",
                "Starting a recording will access your microphone. Audio stays on this device — "
                "nothing is uploaded. Recordings remain until you delete them.",
            )
            self._privacy_notice_shown = True

        try:
            recording, absolute_path = recording_service.begin_recording(
                self._connection,
                self._recordings_dir,
                self._material_id,
                self._subtitle_cue_id,
                device.device_id,
                device.description,
                self._practice_session_id,
            )
        except RecordingValidationError as exc:
            QMessageBox.warning(self, "Cannot Start Recording", str(exc))
            return

        if not self._recorder.set_device(device.device_id):
            recording_service.fail_recording(
                self._connection, self._recordings_dir, recording.id, "The selected microphone is no longer available."
            )
            QMessageBox.warning(self, "Microphone Unavailable", "The selected microphone is no longer available.")
            self._refresh_takes()
            return

        self._active_recording = recording
        self._pending_action = None
        self._recorder.start(absolute_path)
        self._update_recording_buttons()

    def _on_stop_recording_clicked(self) -> None:
        if not self._recorder.is_recording or self._active_recording is None:
            return
        self._pending_action = "finish"
        self._recorder.stop()
        self._update_recording_buttons()

    def abort_active_recording(self) -> None:
        """Safely end an in-progress capture without keeping it as a normal
        take — for cue navigation, material switch, window close, or app
        shutdown while recording. The take is marked `failed`; its partial
        file is removed on a best-effort basis."""
        if self._active_recording is None:
            return
        recording_id = self._active_recording.id
        self._pending_action = None
        self._active_recording = None
        if self._recorder.is_recording:
            self._recorder.stop()
        try:
            recording_service.fail_recording(
                self._connection,
                self._recordings_dir,
                recording_id,
                "Recording was interrupted before it could finish.",
            )
        except RecordingValidationError:
            pass  # already resolved by another path (e.g. a device error)
        self._refresh_takes()
        self._update_recording_buttons()

    def _on_recording_error(self, message: str) -> None:
        if self._active_recording is None:
            return
        recording_id = self._active_recording.id
        self._pending_action = None
        self._active_recording = None
        try:
            recording_service.fail_recording(self._connection, self._recordings_dir, recording_id, message)
        except RecordingValidationError:
            pass
        QMessageBox.warning(self, "Recording Error", message)
        self._refresh_takes()
        self._update_recording_buttons()

    def _on_recorder_stopped(self) -> None:
        if self._pending_action != "finish" or self._active_recording is None:
            self._pending_action = None
            return
        self._pending_action = None
        recording_id = self._active_recording.id
        self._active_recording = None
        try:
            updated = recording_service.finish_recording(self._connection, self._recordings_dir, recording_id)
        except RecordingValidationError:
            updated = None
        if updated is not None and updated.status == RecordingStatus.FAILED.value:
            QMessageBox.warning(self, "Recording Failed", updated.failure_detail or "The recording could not be saved.")
        self._refresh_takes()
        self._update_recording_buttons()

    def _update_recording_buttons(self) -> None:
        has_cue = self._subtitle_cue_id is not None
        recording_in_progress = self._active_recording is not None
        self._start_recording_button.setEnabled(
            has_cue and not recording_in_progress and self._selected_device() is not None and not self._read_only
        )
        self._stop_recording_button.setEnabled(recording_in_progress and self._pending_action != "finish")
        self._device_combo.setEnabled(not recording_in_progress)
        if recording_in_progress and self._pending_action == "finish":
            self._recording_state_label.setText("Stopping…")
        elif recording_in_progress:
            self._recording_state_label.setText("Recording in progress…")
        else:
            self._recording_state_label.setText("")

    # ---- takes ----

    def _refresh_takes(self) -> None:
        self._takes_list.clear()
        self._takes = []
        if self._subtitle_cue_id is not None:
            self._takes = [
                take
                for take in recording_service.list_takes_for_cue(self._connection, self._subtitle_cue_id)
                if take.status != RecordingStatus.RECORDING.value
            ]
        for take in self._takes:
            if take.status == RecordingStatus.READY.value:
                seconds = (take.duration_ms or 0) / 1000
                label = f"Take #{take.id} — {seconds:.1f}s"
            else:
                label = f"Take #{take.id} — failed ({take.failure_detail or 'unknown error'})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, take.id)
            self._takes_list.addItem(item)
        self._update_take_buttons()

    def _selected_take(self) -> Recording | None:
        item = self._takes_list.currentItem()
        if item is None:
            return None
        take_id = item.data(Qt.ItemDataRole.UserRole)
        return next((t for t in self._takes if t.id == take_id), None)

    def _update_take_buttons(self) -> None:
        take = self._selected_take()
        playable = take is not None and take.status == RecordingStatus.READY.value
        idle = not self._sequencer.is_active
        self._play_take_button.setEnabled(playable and idle)
        self._compare_button.setEnabled(playable and idle)
        self._delete_take_button.setEnabled(take is not None and idle and not self._read_only)
        self._delete_cue_takes_button.setEnabled(bool(self._takes) and idle and not self._read_only)

    def _on_play_take_clicked(self) -> None:
        take = self._selected_take()
        if take is None or take.status != RecordingStatus.READY.value or self._sequencer.is_active:
            return
        absolute_path = self._recordings_dir / take.relative_file_path
        if not absolute_path.exists():
            QMessageBox.warning(self, "Recording Missing", "This recording's file could not be found.")
            return
        self._take_playback.load(absolute_path)
        self._take_playback.play()

    def _on_delete_take_clicked(self) -> None:
        take = self._selected_take()
        if take is None:
            return
        answer = QMessageBox.question(
            self, "Delete Take", "Delete this recording? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        # A stopped QMediaPlayer still holds its source file locked on Windows —
        # release it first so deleting a take right after playing/comparing it
        # doesn't spuriously fail.
        self.release_take_playback()
        try:
            recording_service.delete_take(self._connection, self._recordings_dir, take.id)
        except RecordingValidationError as exc:
            QMessageBox.warning(self, "Cannot Delete Recording", str(exc))
        self._refresh_takes()

    def _on_delete_all_takes_for_cue_clicked(self) -> None:
        if self._subtitle_cue_id is None or not self._takes:
            return
        answer = QMessageBox.question(
            self, "Delete All Takes", "Delete every recording for this cue? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.release_take_playback()
        summary = recording_service.delete_takes_for_cue(self._connection, self._recordings_dir, self._subtitle_cue_id)
        if not summary.all_succeeded:
            QMessageBox.warning(
                self, "Some Recordings Could Not Be Deleted",
                f"{len(summary.failed)} of {len(summary.failed) + len(summary.deleted_ids)} recording(s) "
                "could not be deleted and remain in the list.",
            )
        self._refresh_takes()

    # ---- comparison sequencing ----

    def _on_compare_clicked(self) -> None:
        take = self._selected_take()
        if take is None or take.status != RecordingStatus.READY.value or self._sequencer.is_active:
            return
        self._comparison_take = take
        self._sequencer.start()
        self._update_take_buttons()
        self.request_play_source.emit()

    def notify_source_finished(self) -> None:
        """The host calls this once the one-shot source replay it started (in
        response to `request_play_source`) reaches its end."""
        if self._sequencer.step is not ComparisonStep.PLAY_SOURCE:
            return
        self._sequencer.on_source_finished()
        QTimer.singleShot(COMPARISON_PAUSE_MS, self._play_comparison_take)

    def notify_source_failed(self) -> None:
        """The host calls this when source playback fails or cannot finish
        (a playback error, or the media ending before the one-shot replay it
        was asked to run for the comparison ever reached its natural end) —
        a no-op unless a comparison is actually waiting on the source. Cancels
        the stuck comparison so take playback and deletion become usable again
        even though the source itself is unavailable."""
        if not self._sequencer.is_active:
            return
        self._sequencer.cancel()
        self._comparison_take = None
        self._update_take_buttons()

    def _play_comparison_take(self) -> None:
        if self._sequencer.step is not ComparisonStep.WAIT:
            return
        self._sequencer.on_pause_elapsed()
        take = self._comparison_take
        if take is None:
            self._sequencer.cancel()
            self._update_take_buttons()
            return
        absolute_path = self._recordings_dir / take.relative_file_path
        if not absolute_path.exists():
            self._sequencer.cancel()
            self._comparison_take = None
            self._update_take_buttons()
            QMessageBox.warning(self, "Recording Missing", "This recording's file could not be found.")
            return
        self._take_playback.load(absolute_path)
        self._take_playback.play()

    def _on_take_playback_end_of_media(self) -> None:
        if self._sequencer.step is ComparisonStep.PLAY_RECORDING:
            self._sequencer.on_recording_finished()
            self._comparison_take = None
            self._update_take_buttons()
        # Release the file now rather than waiting for the next play/delete —
        # a stopped-but-still-loaded QMediaPlayer keeps the file locked on Windows.
        self._take_playback.unload()

    def _on_take_playback_error(self, message: str) -> None:
        if self._sequencer.is_active:
            self._sequencer.cancel()
            self._comparison_take = None
            self._update_take_buttons()
        self._take_playback.unload()
        QMessageBox.warning(self, "Playback Error", message)

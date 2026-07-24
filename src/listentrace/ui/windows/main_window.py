from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from listentrace.infrastructure.db.migrations import current_version
from listentrace.infrastructure.media.playback import PlaybackController


class MainWindow(QMainWindow):
    def __init__(self, db_connection, db_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("ListenTrace")
        self.resize(480, 320)

        self._db_connection = db_connection
        self._playback_controller: PlaybackController | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)

        title_label = QLabel("ListenTrace — Application Foundation")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        schema_version = current_version(db_connection)
        self._status_label = QLabel(
            f"Database ready\nPath: {db_path}\nSchema version: {schema_version}"
        )
        layout.addWidget(self._status_label)

        self._spike_label = QLabel("Media playback spike: not yet run")
        layout.addWidget(self._spike_label)

        spike_button = QPushButton("Run media playback spike")
        spike_button.clicked.connect(self._run_media_spike)
        layout.addWidget(spike_button)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        layout.addWidget(self._error_label)

        self.setCentralWidget(central)

    def show_error(self, message: str) -> None:
        self._error_label.setText(message)

    def _run_media_spike(self) -> None:
        try:
            tmp_dir = tempfile.mkdtemp()
            wav_path = Path(tmp_dir) / "spike.wav"
            with wave.open(str(wav_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(struct.pack("<h", 0) * 8000)

            controller = PlaybackController(self)
            controller.set_volume(0.0)
            self._playback_controller = controller

            def report_duration() -> None:
                self._spike_label.setText(
                    f"Media playback spike: loaded OK, duration={controller.duration_ms} ms"
                )

            controller.duration_changed.connect(lambda _d: report_duration())
            controller.playback_error.connect(
                lambda msg: self._spike_label.setText(f"Media playback spike failed: {msg}")
            )
            controller.load(wav_path)
            QTimer.singleShot(500, controller.play)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.show_error(f"Media spike error: {exc}")

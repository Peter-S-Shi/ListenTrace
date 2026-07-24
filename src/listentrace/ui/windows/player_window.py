from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.dto.player_load import PlayerLoadResult
from listentrace.application.dto.player_state import LoopMode
from listentrace.application.services.player_session import PlayerSession
from listentrace.infrastructure.media.playback import PlaybackController

_SEEK_STEP_MS = 5000


def _is_text_entry_widget(widget: object) -> bool:
    return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))


def _format_time(ms: int) -> str:
    total_seconds = max(ms, 0) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class PlayerWindow(QMainWindow):
    def __init__(self, load_result: PlayerLoadResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        material = load_result.material
        self.setWindowTitle(f"ListenTrace — {material.title}")
        self.resize(760, 600)

        self._material = material
        self._session = PlayerSession(load_result.cues)
        self._playback = PlaybackController(self)
        self._seeking_via_slider = False

        central = QWidget(self)
        layout = QVBoxLayout(central)

        title_label = QLabel(material.title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        if material.media_kind == "video":
            self._video_widget: QVideoWidget | None = QVideoWidget()
            self._video_widget.setMinimumHeight(240)
            self._playback.set_video_output(self._video_widget)
            layout.addWidget(self._video_widget)
            self._audio_placeholder: QLabel | None = None
        else:
            self._video_widget = None
            self._audio_placeholder = QLabel(f"{material.title}\n00:00 / 00:00")
            self._audio_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._audio_placeholder.setMinimumHeight(120)
            self._audio_placeholder.setStyleSheet(
                "background: #222; color: white; font-size: 14px;"
            )
            layout.addWidget(self._audio_placeholder)

        seek_row = QHBoxLayout()
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)
        self._time_label = QLabel("00:00 / 00:00")
        seek_row.addWidget(self._seek_slider, 1)
        seek_row.addWidget(self._time_label)
        layout.addLayout(seek_row)

        transport_row = QHBoxLayout()
        self._play_pause_button = QPushButton("Play")
        self._play_pause_button.clicked.connect(self._on_play_pause_clicked)
        self._previous_button = QPushButton("Previous Cue")
        self._previous_button.clicked.connect(self._on_previous_cue)
        self._next_button = QPushButton("Next Cue")
        self._next_button.clicked.connect(self._on_next_cue)
        self._replay_button = QPushButton("Replay Cue")
        self._replay_button.clicked.connect(self._on_replay_cue)
        self._loop_cue_button = QPushButton("Loop Cue")
        self._loop_cue_button.clicked.connect(self._on_loop_cue_clicked)
        self._loop_range_button = QPushButton("Loop Selection")
        self._loop_range_button.clicked.connect(self._on_loop_range_clicked)
        self._transcript_button = QPushButton("Hide Transcript")
        self._transcript_button.clicked.connect(self._on_toggle_transcript)
        self._mute_button = QPushButton("Mute")
        self._mute_button.clicked.connect(self._on_toggle_mute)
        for button in (
            self._play_pause_button,
            self._previous_button,
            self._next_button,
            self._replay_button,
            self._loop_cue_button,
            self._loop_range_button,
            self._transcript_button,
            self._mute_button,
        ):
            transport_row.addWidget(button)
        layout.addLayout(transport_row)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_row.addWidget(self._volume_slider)
        layout.addLayout(volume_row)

        self._cue_list = QListWidget()
        self._cue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for cue in self._session.cues:
            label = f"[{_format_time(cue.start_ms)}-{_format_time(cue.end_ms)}] {cue.text}"
            self._cue_list.addItem(QListWidgetItem(label))
        layout.addWidget(self._cue_list, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: red;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        return_button = QPushButton("Return to Library")
        return_button.clicked.connect(self.close)
        layout.addWidget(return_button)

        self.setCentralWidget(central)

        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.duration_changed.connect(self._on_duration_changed)
        self._playback.playback_error.connect(self._on_playback_error)
        self._playback.end_of_media.connect(self._on_end_of_media)

        self._playback.set_volume(self._volume_slider.value() / 100)
        self._playback.load(material.media_path)
        # No autoplay: playback stays paused at 0 until the user presses Play.

    def _on_play_pause_clicked(self) -> None:
        if self._playback.is_playing:
            self._playback.pause()
            self._play_pause_button.setText("Play")
        else:
            self._playback.play()
            self._play_pause_button.setText("Pause")

    def _on_position_changed(self, position_ms: int) -> None:
        tick = self._session.on_position_changed(position_ms)
        if tick.pause:
            self._playback.pause()
            self._play_pause_button.setText("Play")
        if tick.seek_to_ms is not None:
            self._playback.seek(tick.seek_to_ms)

        if not self._seeking_via_slider:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(position_ms)
            self._seek_slider.blockSignals(False)

        self._update_time_label(position_ms)
        self._update_active_cue_highlight()

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._seek_slider.setRange(0, max(duration_ms, 0))
        self._update_time_label(self._playback.position_ms)

    def _update_time_label(self, position_ms: int) -> None:
        text = f"{_format_time(position_ms)} / {_format_time(self._playback.duration_ms)}"
        self._time_label.setText(text)
        if self._audio_placeholder is not None:
            self._audio_placeholder.setText(f"{self._material.title}\n{text}")

    def _update_active_cue_highlight(self) -> None:
        active_index = self._session.active_cue_index
        if active_index is None:
            return
        if len(self._cue_list.selectedItems()) <= 1:
            self._cue_list.setCurrentRow(active_index)

    def _on_slider_pressed(self) -> None:
        self._seeking_via_slider = True

    def _on_slider_released(self) -> None:
        self._playback.seek(self._seek_slider.value())
        self._seeking_via_slider = False

    def _on_previous_cue(self) -> None:
        new_index = self._session.previous_cue_index(self._session.active_cue_index)
        if new_index is not None:
            self._playback.seek(self._session.cues[new_index].start_ms)

    def _on_next_cue(self) -> None:
        new_index = self._session.next_cue_index(self._session.active_cue_index)
        if new_index is not None:
            self._playback.seek(self._session.cues[new_index].start_ms)

    def _selected_cue_indices(self) -> list[int]:
        return sorted(self._cue_list.row(item) for item in self._cue_list.selectedItems())

    def _on_replay_cue(self) -> None:
        indices = self._selected_cue_indices()
        cue_index = indices[0] if indices else self._session.active_cue_index
        if cue_index is None:
            self._show_status("No cue selected to replay.")
            return
        seek_to = self._session.replay_cue(cue_index)
        self._playback.seek(seek_to)
        self._playback.play()
        self._play_pause_button.setText("Pause")
        self._show_status("")

    def _on_loop_cue_clicked(self) -> None:
        indices = self._selected_cue_indices()
        cue_index = indices[0] if indices else self._session.active_cue_index
        if cue_index is None:
            self._show_status("No cue selected to loop.")
            return
        self._start_loop(self._session.loop_cue(cue_index))

    def _on_loop_range_clicked(self) -> None:
        indices = self._selected_cue_indices()
        if not indices:
            self._show_status("Select one or more cues to loop.")
            return
        self._start_loop(self._session.loop_range(indices[0], indices[-1]))

    def _start_loop(self, seek_to_ms: int) -> None:
        self._playback.seek(seek_to_ms)
        self._playback.play()
        self._play_pause_button.setText("Pause")
        self._show_status("")

    def _on_toggle_transcript(self) -> None:
        self._session.transcript_visible = not self._session.transcript_visible
        self._cue_list.setVisible(self._session.transcript_visible)
        self._transcript_button.setText(
            "Show Transcript" if not self._session.transcript_visible else "Hide Transcript"
        )

    def _on_toggle_mute(self) -> None:
        muted = not self._playback.is_muted
        self._playback.set_muted(muted)
        self._mute_button.setText("Unmute" if muted else "Mute")

    def _on_volume_changed(self, value: int) -> None:
        self._playback.set_volume(value / 100)

    def _on_end_of_media(self) -> None:
        self._play_pause_button.setText("Play")

    def _on_playback_error(self, message: str) -> None:
        self._show_status(f"Playback error: {message}")
        self._play_pause_button.setEnabled(False)

    def _show_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _on_loop_toggle_shortcut(self) -> None:
        if self._session.loop_mode is not LoopMode.NONE:
            self._session.cancel_loop()
            return
        indices = self._selected_cue_indices()
        if len(indices) >= 2:
            self._start_loop(self._session.loop_range(indices[0], indices[-1]))
        elif len(indices) == 1:
            self._start_loop(self._session.loop_cue(indices[0]))
        elif self._session.active_cue_index is not None:
            self._start_loop(self._session.loop_cue(self._session.active_cue_index))
        else:
            self._show_status("No cue selected to loop.")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        focus_widget = QApplication.focusWidget()
        letter_shortcuts_active = not _is_text_entry_widget(focus_widget)

        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Space:
            self._on_play_pause_clicked()
        elif key == Qt.Key.Key_Left and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._on_previous_cue()
        elif key == Qt.Key.Key_Right and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._on_next_cue()
        elif key == Qt.Key.Key_Left:
            self._playback.seek(max(self._playback.position_ms - _SEEK_STEP_MS, 0))
        elif key == Qt.Key.Key_Right:
            self._playback.seek(self._playback.position_ms + _SEEK_STEP_MS)
        elif key == Qt.Key.Key_R and letter_shortcuts_active:
            self._on_replay_cue()
        elif key == Qt.Key.Key_L and letter_shortcuts_active:
            self._on_loop_toggle_shortcut()
        elif key == Qt.Key.Key_T and letter_shortcuts_active:
            self._on_toggle_transcript()
        elif key == Qt.Key.Key_M and letter_shortcuts_active:
            self._on_toggle_mute()
        elif key == Qt.Key.Key_Escape:
            self._session.cancel_loop()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._session.cancel_loop()
        self._playback.stop()
        super().closeEvent(event)

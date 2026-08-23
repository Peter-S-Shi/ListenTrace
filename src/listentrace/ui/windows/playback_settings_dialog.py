from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout

from listentrace.application.services import loop_grace_service
from listentrace.domain.services.loop_grace_policy import (
    LOOP_END_GRACE_MAX_MS,
    LOOP_END_GRACE_MIN_MS,
    LOOP_END_GRACE_STEP_MS,
)
from listentrace.ui import theme
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus

_EXPLANATION = (
    "This is the fallback used by every Material that has not been given "
    "its own custom Loop End Grace value. Materials with a custom override "
    "are never changed by this."
)


class PlaybackSettingsDialog(QDialog):
    """Global-scope settings surface. Unlike `MaterialLoopSettingsDialog`,
    this one requires an explicit Apply/Cancel: a change here reaches every
    inheriting Material, a wide enough blast radius to deserve one
    deliberate confirmation rather than persisting on every drag. See
    `.prompt-drafts/Handoffs/listentrace-loop-end-grace-ux-contract-freeze-2026-08-23.md`
    (local-only) for the full frozen interaction contract this implements."""

    def __init__(self, connection: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._connection = connection
        self.setWindowTitle("Playback Settings")

        layout = QVBoxLayout(self)

        title = QLabel("Default Loop End Grace")
        theme.apply_role(title, "title")
        layout.addWidget(title)

        explanation = QLabel(_EXPLANATION)
        explanation.setWordWrap(True)
        theme.apply_role(explanation, "caption")
        layout.addWidget(explanation)

        value_row = QHBoxLayout()
        self._value_slider = QSlider(Qt.Orientation.Horizontal)
        self._value_slider.setRange(LOOP_END_GRACE_MIN_MS, LOOP_END_GRACE_MAX_MS)
        self._value_slider.setSingleStep(LOOP_END_GRACE_STEP_MS)
        self._value_slider.setPageStep(LOOP_END_GRACE_STEP_MS)
        self._value_slider.valueChanged.connect(self._on_slider_changed)
        value_row.addWidget(self._value_slider, 1)

        self._value_spinbox = QSpinBox()
        self._value_spinbox.setRange(LOOP_END_GRACE_MIN_MS, LOOP_END_GRACE_MAX_MS)
        self._value_spinbox.setSingleStep(1)  # any integer in range is legal, not just multiples of 10
        self._value_spinbox.setSuffix(" ms")
        self._value_spinbox.valueChanged.connect(self._on_spinbox_changed)
        value_row.addWidget(self._value_spinbox)
        layout.addLayout(value_row)

        bounds_hint = QLabel(f"Allowed range {LOOP_END_GRACE_MIN_MS}–{LOOP_END_GRACE_MAX_MS} ms.")
        theme.apply_role(bounds_hint, "caption")
        layout.addWidget(bounds_hint)

        button_row = QHBoxLayout()
        self._apply_button = QPushButton("Apply")
        self._apply_button.clicked.connect(self._on_apply_clicked)
        theme.apply_role(self._apply_button, "primary")
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self._apply_button)
        button_row.addWidget(self._cancel_button)
        layout.addLayout(button_row)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        theme.apply_role(close_button, "secondary")
        layout.addWidget(close_button)

        self._saved_value = loop_grace_service.get_global_loop_end_grace_ms(connection)
        self._set_controls(self._saved_value)
        self._update_apply_cancel_enabled()

    def _set_controls(self, value: int) -> None:
        for control in (self._value_slider, self._value_spinbox):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)

    def _update_apply_cancel_enabled(self) -> None:
        dirty = self._value_spinbox.value() != self._saved_value
        self._apply_button.setEnabled(dirty)
        self._cancel_button.setEnabled(dirty)

    # ---- interaction ----

    def _on_slider_changed(self, value: int) -> None:
        self._set_controls(value)
        self._update_apply_cancel_enabled()

    def _on_spinbox_changed(self, value: int) -> None:
        self._set_controls(value)
        self._update_apply_cancel_enabled()

    def _on_apply_clicked(self) -> None:
        loop_grace_service.set_global_loop_end_grace_ms(self._connection, self._value_spinbox.value())
        self._saved_value = self._value_spinbox.value()
        self._update_apply_cancel_enabled()
        loop_grace_change_bus.global_default_changed.emit()

    def _on_cancel_clicked(self) -> None:
        self._set_controls(self._saved_value)
        self._update_apply_cancel_enabled()

    def showEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().showEvent(event)
        # The instance is cached and reused (see MainWindow._on_open_playback_
        # settings) -- closing with an unapplied dirty draft (Close, not
        # Cancel) must not leave that draft visible the next time this same
        # instance is shown; reload the actual persisted value instead.
        self._saved_value = loop_grace_service.get_global_loop_end_grace_ms(self._connection)
        self._set_controls(self._saved_value)
        self._update_apply_cancel_enabled()


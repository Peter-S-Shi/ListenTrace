from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from listentrace.application.errors import AnnotationValidationError
from listentrace.application.services import label_preference_service, loop_grace_service
from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.services import loop_grace_policy
from listentrace.domain.services.loop_grace_policy import (
    LOOP_END_GRACE_MAX_MS,
    LOOP_END_GRACE_MIN_MS,
    LOOP_END_GRACE_STEP_MS,
)
from listentrace.ui import theme
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus

_PLAYBACK_EXPLANATION = (
    "This is the fallback used by every Material that has not been given "
    "its own custom Loop End Grace value. Materials with a custom override "
    "are never changed by this."
)


class SettingsDialog(QDialog):
    """Consolidated Global Settings Surface for ListenTrace.

    Houses global application preferences organized into clear categories:
    1. Playback: Global default Loop End Grace and playback timing.
    2. Label Colors: Global annotation label color preferences.

    Extensible for future preference categories without separate competing
    settings surfaces.
    """

    def __init__(self, connection: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connection = connection
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        theme.apply_surface(self, "modal")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION, theme.SPACE_SECTION)
        root_layout.setSpacing(theme.SPACE_NORMAL)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Settings")
        theme.apply_role(title, "page_title")
        header_row.addWidget(title)
        header_row.addStretch(1)
        root_layout.addLayout(header_row)

        # Category Tabs
        self._tabs = QTabWidget()
        theme.apply_role(self._tabs, "notebook_tabs")

        # 1. Playback Tab
        playback_widget = self._build_playback_tab()
        self._tabs.addTab(playback_widget, "Playback")

        # 2. Label Colors Tab
        label_colors_widget = self._build_label_colors_tab()
        self._tabs.addTab(label_colors_widget, "Label Colors")

        root_layout.addWidget(self._tabs, 1)

        # Bottom Bar: Close button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.close)
        theme.apply_role(self._close_button, "secondary")
        bottom_row.addWidget(self._close_button)
        root_layout.addLayout(bottom_row)

        # Initial values
        self._saved_grace_value = loop_grace_service.get_global_loop_end_grace_ms(self._connection)
        self._set_playback_controls(self._saved_grace_value)
        self._update_apply_cancel_enabled()

    # -------------------------------------------------------------------
    # Playback Category Tab
    # -------------------------------------------------------------------

    def _build_playback_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(theme.SPACE_NORMAL, theme.SPACE_SECTION, theme.SPACE_NORMAL, theme.SPACE_SECTION)
        layout.setSpacing(theme.SPACE_NORMAL)

        section_title = QLabel("Default Loop End Grace")
        theme.apply_role(section_title, "title")
        layout.addWidget(section_title)

        explanation = QLabel(_PLAYBACK_EXPLANATION)
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
        self._value_spinbox.setSingleStep(1)
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
        theme.apply_role(self._cancel_button, "secondary")

        button_row.addWidget(self._apply_button)
        button_row.addWidget(self._cancel_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        layout.addStretch(1)
        return widget

    def _set_playback_controls(self, value: int) -> None:
        for control in (self._value_slider, self._value_spinbox):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)

    def _update_apply_cancel_enabled(self) -> None:
        dirty = self._value_spinbox.value() != self._saved_grace_value
        self._apply_button.setEnabled(dirty)
        self._cancel_button.setEnabled(dirty)

    def _on_slider_changed(self, value: int) -> None:
        self._set_playback_controls(loop_grace_policy.snap_to_slider_step_ms(value))
        self._update_apply_cancel_enabled()

    def _on_spinbox_changed(self, value: int) -> None:
        self._set_playback_controls(value)
        self._update_apply_cancel_enabled()

    def _on_apply_clicked(self) -> None:
        loop_grace_service.set_global_loop_end_grace_ms(self._connection, self._value_spinbox.value())
        self._saved_grace_value = self._value_spinbox.value()
        self._update_apply_cancel_enabled()
        loop_grace_change_bus.global_default_changed.emit()

    def _on_cancel_clicked(self) -> None:
        self._set_playback_controls(self._saved_grace_value)
        self._update_apply_cancel_enabled()

    # -------------------------------------------------------------------
    # Label Colors Category Tab
    # -------------------------------------------------------------------

    def _build_label_colors_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(theme.SPACE_NORMAL, theme.SPACE_SECTION, theme.SPACE_NORMAL, theme.SPACE_SECTION)
        layout.setSpacing(theme.SPACE_NORMAL)

        section_title = QLabel("Annotation Label Colors")
        theme.apply_role(section_title, "title")
        layout.addWidget(section_title)

        hint = QLabel("Select custom highlight colors for each annotation category.")
        theme.apply_role(hint, "caption")
        layout.addWidget(hint)

        self._color_buttons: dict[str, QPushButton] = {}
        preferences = label_preference_service.get_label_preferences(self._connection)

        for label in AnnotationLabel:
            row = QHBoxLayout()
            label_display = QLabel(label.value.replace("_", " ").title())
            theme.apply_role(label_display, "ui_label")
            row.addWidget(label_display, 1)

            color = preferences.get(label.value, "#FFFFFF")
            button = QPushButton(color)
            button.setFixedWidth(100)
            button.setStyleSheet(f"background-color: {color}; font-weight: bold;")
            button.clicked.connect(
                lambda _checked=False, key=label.value, btn=button: self._pick_label_color(key, btn)
            )
            self._color_buttons[label.value] = button
            row.addWidget(button)
            layout.addLayout(row)

        layout.addStretch(1)
        return widget

    def _pick_label_color(self, label_key: str, button: QPushButton) -> None:
        chosen = QColorDialog.getColor(QColor(button.text()), self, "Choose Color")
        if not chosen.isValid():
            return
        hex_color = chosen.name()
        try:
            label_preference_service.update_label_color(self._connection, label_key, hex_color)
        except AnnotationValidationError as exc:
            QMessageBox.warning(self, "Invalid Color", str(exc))
            return
        button.setText(hex_color)
        button.setStyleSheet(f"background-color: {hex_color}; font-weight: bold;")

    def showEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().showEvent(event)
        self._saved_grace_value = loop_grace_service.get_global_loop_end_grace_ms(self._connection)
        self._set_playback_controls(self._saved_grace_value)
        self._update_apply_cancel_enabled()
        # Refresh label buttons with latest persisted colors
        preferences = label_preference_service.get_label_preferences(self._connection)
        for label_key, button in self._color_buttons.items():
            color = preferences.get(label_key, "#FFFFFF")
            button.setText(color)
            button.setStyleSheet(f"background-color: {color}; font-weight: bold;")

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from listentrace.application.services import loop_grace_service
from listentrace.domain.services.loop_grace_policy import (
    LOOP_END_GRACE_MAX_MS,
    LOOP_END_GRACE_MIN_MS,
    LOOP_END_GRACE_STEP_MS,
)
from listentrace.ui import theme
from listentrace.ui.widgets.loop_grace_change_bus import loop_grace_change_bus

_EXPLANATION = (
    "Some subtitle timings cut off the end of spoken audio during Loop. "
    "Increase this value if the tail sounds clipped; reduce it if the next "
    "cue's audio leaks into the Loop."
)


class MaterialLoopSettingsDialog(QDialog):
    """Modeless, reusable across every Loop-capable training surface (Main
    Player, Guided Session, Quiz, Quick Practice, Shadowing Practice) --
    each window constructs its own instance rather than sharing one, but all
    five call this same class. Material edits persist immediately (no Save
    button); the Global Default dialog is the one that needs explicit
    Apply/Cancel, since it has a much wider blast radius. See
    `.prompt-drafts/Handoffs/listentrace-loop-end-grace-ux-contract-freeze-2026-08-23.md`
    (local-only) for the full frozen interaction contract this implements."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        material_id: int,
        material_title: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setModal(False)
        self._connection = connection
        self._material_id = material_id
        self.setWindowTitle(f"Loop Settings — {material_title}")
        # If the same Material is open in two windows and both have this
        # dialog open, a change made in one must not leave the other's
        # display stale -- it would otherwise keep showing an inherit/
        # custom state and value that no longer match what's persisted.
        loop_grace_change_bus.global_default_changed.connect(self._on_preference_changed_elsewhere)
        loop_grace_change_bus.material_override_changed.connect(self._on_material_override_changed_elsewhere)

        layout = QVBoxLayout(self)

        explanation = QLabel(_EXPLANATION)
        explanation.setWordWrap(True)
        apply_role = theme.apply_role
        apply_role(explanation, "caption")
        layout.addWidget(explanation)

        self._inherit_radio = QRadioButton()
        self._inherit_radio.toggled.connect(self._on_inherit_toggled)
        layout.addWidget(self._inherit_radio)

        self._custom_radio = QRadioButton("Custom for this Material")
        self._custom_radio.toggled.connect(self._on_custom_toggled)
        layout.addWidget(self._custom_radio)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._inherit_radio)
        self._mode_group.addButton(self._custom_radio)

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

        self._reset_button = QPushButton("Reset to Global")
        self._reset_button.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self._reset_button)

        self._effective_label = QLabel("")
        layout.addWidget(self._effective_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        apply_role(close_button, "secondary")
        layout.addWidget(close_button)

        self._refresh_from_persistence()

    # ---- rendering ----

    def _refresh_from_persistence(self) -> None:
        override = loop_grace_service.get_material_loop_end_grace_override_ms(
            self._connection, self._material_id
        )
        global_default = loop_grace_service.get_global_loop_end_grace_ms(self._connection)
        self._inherit_radio.setText(f"Use global default (currently {global_default} ms)")

        is_custom = override is not None
        for radio in (self._inherit_radio, self._custom_radio):
            radio.blockSignals(True)
        self._inherit_radio.setChecked(not is_custom)
        self._custom_radio.setChecked(is_custom)
        for radio in (self._inherit_radio, self._custom_radio):
            radio.blockSignals(False)

        self._value_slider.setVisible(is_custom)
        self._value_spinbox.setVisible(is_custom)
        self._reset_button.setVisible(is_custom)
        if is_custom:
            for control in (self._value_slider, self._value_spinbox):
                control.blockSignals(True)
                control.setValue(override)
                control.blockSignals(False)

        effective = loop_grace_service.effective_loop_end_grace_ms(self._connection, self._material_id)
        self._effective_label.setText(f"Effective value now: {effective} ms")

    # ---- interaction ----

    def _on_inherit_toggled(self, checked: bool) -> None:
        if not checked:
            return
        loop_grace_service.reset_material_loop_end_grace_override(self._connection, self._material_id)
        loop_grace_change_bus.material_override_changed.emit(self._material_id)
        self._refresh_from_persistence()

    def _on_custom_toggled(self, checked: bool) -> None:
        if not checked:
            return
        # Starts editing from the Material's current effective value -- not
        # from the global default, not from 180 -- so nothing audibly jumps
        # at the moment of the switch. Distinct from Reset, which never
        # copies a value.
        starting_value = loop_grace_service.effective_loop_end_grace_ms(self._connection, self._material_id)
        self._persist_custom_value(starting_value)

    def _persist_custom_value(self, value: int) -> None:
        loop_grace_service.set_material_loop_end_grace_override_ms(self._connection, self._material_id, value)
        loop_grace_change_bus.material_override_changed.emit(self._material_id)
        self._refresh_from_persistence()

    def _on_slider_changed(self, value: int) -> None:
        if not self._custom_radio.isChecked():
            # The radio's own toggle handler already persists the starting
            # value; the slider's value is set programmatically to match
            # during that same refresh, which must not double-persist.
            return
        self._persist_custom_value(value)

    def _on_spinbox_changed(self, value: int) -> None:
        if not self._custom_radio.isChecked():
            return
        self._persist_custom_value(value)

    def _on_reset_clicked(self) -> None:
        self._inherit_radio.setChecked(True)  # triggers _on_inherit_toggled

    def _on_preference_changed_elsewhere(self) -> None:
        self._refresh_from_persistence()

    def _on_material_override_changed_elsewhere(self, material_id: int) -> None:
        if material_id == self._material_id:
            self._refresh_from_persistence()

    def showEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().showEvent(event)
        self._refresh_from_persistence()

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _LabelColorChangeBus(QObject):
    """Process-wide notification so every already-open study desk surface (e.g.
    PlayerWindow) can refresh its live annotation presentation (transcript
    highlights and diagnosis note badges) when label colors are updated from
    the consolidated Settings dialog without requiring window reload or cue
    switching."""

    label_colors_changed = Signal()


label_color_change_bus = _LabelColorChangeBus()

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _MaterialMetadataChangeBus(QObject):
    """M14 Corrective Batch A: process-wide notification so every already-open
    material-bound surface (PlayerWindow, GuidedSessionWindow, QuizWindow,
    QuickPracticeWindow, ShadowingPracticeWindow) can refresh its title/header
    presentation when a material's metadata changes from the Library, without
    requiring the window to be closed and reopened. Deliberately narrow --
    just the one signal the Library currently needs (rename) -- rather than a
    generic material-changed event; extend with another typed signal if a
    future batch needs to propagate a different metadata field."""

    material_renamed = Signal(int, str)  # material_id, new_title


material_metadata_bus = _MaterialMetadataChangeBus()

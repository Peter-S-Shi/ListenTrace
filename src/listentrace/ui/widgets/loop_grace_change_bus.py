from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _LoopGraceChangeBus(QObject):
    """Process-wide notification so every already-open training surface
    (Player, Guided Session, Quiz, Quick Practice, Shadowing Practice) can
    re-resolve its `PlayerSession`'s live Loop End Grace when a preference
    changes elsewhere -- e.g. the same Material is open in two windows, or
    the global default is Applied while an inheriting Material is open.
    Deliberately just two signals, not a general event bus, mirroring
    `recording_change_bus`'s precedent. Listeners always re-call
    `loop_grace_service.effective_loop_end_grace_ms(...)` on receipt rather
    than being handed a raw value -- the resolver stays the single
    authority on override-vs-inherit, never duplicated per window."""

    global_default_changed = Signal()
    material_override_changed = Signal(int)  # material_id


loop_grace_change_bus = _LoopGraceChangeBus()

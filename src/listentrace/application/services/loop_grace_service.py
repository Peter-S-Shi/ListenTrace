from __future__ import annotations

import sqlite3

from listentrace.application.errors import LoopGraceValidationError
from listentrace.domain.services import loop_grace_policy as policy
from listentrace.infrastructure.db import loop_grace_repository as _repo


def _validate(value: int) -> None:
    if not policy.is_valid_loop_end_grace_ms(value):
        raise LoopGraceValidationError(
            "invalid_loop_end_grace_ms",
            f"Loop End Grace must be between {policy.LOOP_END_GRACE_MIN_MS} and "
            f"{policy.LOOP_END_GRACE_MAX_MS}ms, got {value!r}",
        )


def get_global_loop_end_grace_ms(conn: sqlite3.Connection) -> int:
    value = _repo.get_global_loop_end_grace_ms(conn)
    return policy.clamp_loop_end_grace_ms(value) if value is not None else policy.LOOP_END_GRACE_DEFAULT_MS


def set_global_loop_end_grace_ms(conn: sqlite3.Connection, value: int) -> None:
    _validate(value)
    _repo.set_global_loop_end_grace_ms(conn, value)


def get_material_loop_end_grace_override_ms(conn: sqlite3.Connection, material_id: int) -> int | None:
    return _repo.get_material_loop_end_grace_override_ms(conn, material_id)


def set_material_loop_end_grace_override_ms(conn: sqlite3.Connection, material_id: int, value: int) -> None:
    _validate(value)
    _repo.set_material_loop_end_grace_override_ms(conn, material_id, value)


def reset_material_loop_end_grace_override(conn: sqlite3.Connection, material_id: int) -> None:
    _repo.delete_material_loop_end_grace_override(conn, material_id)


def effective_loop_end_grace_ms(conn: sqlite3.Connection, material_id: int) -> int:
    """Override if present, else the global default -- clamped defensively
    regardless of source. Write-time rejection in `set_*` above is the
    primary defense against out-of-range values; this clamp is only the
    backstop against data that got into a row some other way (a future
    migration issue, a manual DB edit)."""
    override = get_material_loop_end_grace_override_ms(conn, material_id)
    if override is not None:
        return policy.clamp_loop_end_grace_ms(override)
    return get_global_loop_end_grace_ms(conn)

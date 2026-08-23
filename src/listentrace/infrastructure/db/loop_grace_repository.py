from __future__ import annotations

import sqlite3

# ---- loop_grace_preference (singleton row, id = 1) ----


def get_global_loop_end_grace_ms(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT grace_ms FROM loop_grace_preference WHERE id = 1").fetchone()
    return int(row["grace_ms"]) if row is not None else None


def set_global_loop_end_grace_ms(conn: sqlite3.Connection, value: int) -> None:
    conn.execute(
        """
        INSERT INTO loop_grace_preference (id, grace_ms) VALUES (1, ?)
        ON CONFLICT (id) DO UPDATE SET grace_ms = excluded.grace_ms, updated_at = datetime('now')
        """,
        (value,),
    )
    conn.commit()


# ---- material_loop_grace_override (row present = override, row absent = inherit) ----


def get_material_loop_end_grace_override_ms(conn: sqlite3.Connection, material_id: int) -> int | None:
    row = conn.execute(
        "SELECT grace_ms FROM material_loop_grace_override WHERE material_id = ?", (material_id,)
    ).fetchone()
    return int(row["grace_ms"]) if row is not None else None


def set_material_loop_end_grace_override_ms(conn: sqlite3.Connection, material_id: int, value: int) -> None:
    conn.execute(
        """
        INSERT INTO material_loop_grace_override (material_id, grace_ms) VALUES (?, ?)
        ON CONFLICT (material_id) DO UPDATE SET grace_ms = excluded.grace_ms, updated_at = datetime('now')
        """,
        (material_id, value),
    )
    conn.commit()


def delete_material_loop_end_grace_override(conn: sqlite3.Connection, material_id: int) -> None:
    conn.execute("DELETE FROM material_loop_grace_override WHERE material_id = ?", (material_id,))
    conn.commit()

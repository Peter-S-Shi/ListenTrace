from __future__ import annotations

from enum import Enum


class MaterialStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

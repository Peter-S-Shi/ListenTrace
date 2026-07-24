from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SavedItemSuccess:
    item_id: int


@dataclass(slots=True)
class SavedItemNeedsConfirmation:
    existing_item_id: int
    existing_context_text: str
    normalized_text: str

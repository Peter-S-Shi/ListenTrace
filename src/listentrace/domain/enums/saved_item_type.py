from __future__ import annotations

from enum import Enum


class SavedItemType(str, Enum):
    WORD = "word"
    PHRASE = "phrase"
    CHUNK = "chunk"
    SENTENCE_PATTERN = "sentence_pattern"

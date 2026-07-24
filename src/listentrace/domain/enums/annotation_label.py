from __future__ import annotations

from enum import Enum


class AnnotationLabel(str, Enum):
    KEYWORD = "keyword"
    KNOWN_NOT_HEARD = "known_not_heard"
    CONNECTED_REDUCED_SPEECH = "connected_reduced_speech"
    MISHEARD = "misheard"
    UNKNOWN_WORD_OR_CHUNK = "unknown_word_or_chunk"

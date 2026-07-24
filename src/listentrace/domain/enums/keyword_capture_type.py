from __future__ import annotations

from enum import Enum


class KeywordCaptureType(str, Enum):
    KEYWORD = "keyword"
    NAME_OR_PLACE = "name_or_place"
    NUMBER = "number"
    PHRASE = "phrase"
    UNCERTAIN_FRAGMENT = "uncertain_fragment"

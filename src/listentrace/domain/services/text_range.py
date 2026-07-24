from __future__ import annotations


class TextRangeError(ValueError):
    pass


def validate_selection(cue_text: str, start: int, end: int) -> str:
    """Validate a zero-based, end-exclusive selection range against `cue_text`.

    Offsets are counted in Python string (Unicode code point) units. This matches Qt's
    QTextEdit/QTextCursor selection offsets for all text within the Basic Multilingual
    Plane; text requiring UTF-16 surrogate pairs (e.g. some emoji) is out of scope and
    not verified.

    Returns the substring covered by the range.
    """
    if start < 0 or end < start or end > len(cue_text):
        raise TextRangeError(
            f"selection [{start}:{end}] is out of bounds for cue text of length {len(cue_text)}"
        )
    return cue_text[start:end]


def whole_cue_range(cue_text: str) -> tuple[int, int]:
    return 0, len(cue_text)

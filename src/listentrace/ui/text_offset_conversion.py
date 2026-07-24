from __future__ import annotations

"""Qt text-widget offsets (QTextCursor/QString: UTF-16 code units) are not the same
number line as the canonical selection representation used by the domain/application
layers (Python str: Unicode code-point indices). Every read from, or write to, a Qt
text widget must go through this module rather than passing positions through directly.
"""


class SurrogatePairOffsetError(ValueError):
    """Raised when a Qt offset falls inside a UTF-16 surrogate pair, i.e. does not
    correspond to the start of any whole Unicode code point."""


def _utf16_start_offsets(text: str) -> list[int]:
    """offsets[i] = the UTF-16 code-unit offset at which code-point index i starts,
    for i in 0..len(text); offsets[len(text)] is the total UTF-16 length."""
    offsets = [0]
    pos = 0
    for ch in text:
        pos += 2 if ord(ch) > 0xFFFF else 1
        offsets.append(pos)
    return offsets


def qt_offset_to_codepoint_index(text: str, qt_offset: int) -> int:
    """Convert a Qt (UTF-16 code-unit) offset into a Python (Unicode code-point) index."""
    offsets = _utf16_start_offsets(text)
    try:
        return offsets.index(qt_offset)
    except ValueError:
        raise SurrogatePairOffsetError(
            f"Qt offset {qt_offset} falls inside a surrogate pair (non-BMP character) "
            "and does not correspond to a whole code point."
        ) from None


def codepoint_index_to_qt_offset(text: str, codepoint_index: int) -> int:
    """Convert a Python (Unicode code-point) index into a Qt (UTF-16 code-unit) offset."""
    if codepoint_index < 0 or codepoint_index > len(text):
        raise ValueError(
            f"code-point index {codepoint_index} is out of bounds for text of length {len(text)}"
        )
    return _utf16_start_offsets(text)[codepoint_index]


def is_qt_offset_on_codepoint_boundary(text: str, qt_offset: int) -> bool:
    return qt_offset in _utf16_start_offsets(text)

from __future__ import annotations

import pytest

from listentrace.ui.text_offset_conversion import (
    SurrogatePairOffsetError,
    codepoint_index_to_qt_offset,
    is_qt_offset_on_codepoint_boundary,
    qt_offset_to_codepoint_index,
)


def test_ascii_offsets_are_identity():
    text = "hello world"
    for i in range(len(text) + 1):
        assert codepoint_index_to_qt_offset(text, i) == i
        assert qt_offset_to_codepoint_index(text, i) == i


def test_bmp_non_ascii_offsets_are_identity():
    # BMP non-ASCII characters (accented Latin, CJK) are 1 UTF-16 unit each, same as
    # 1 Python code point, so Qt and Python offsets coincide.
    text = "Comment ça va ? 你好世界"
    for i in range(len(text) + 1):
        assert codepoint_index_to_qt_offset(text, i) == i
        assert qt_offset_to_codepoint_index(text, i) == i


def test_non_bmp_character_before_selection_shifts_qt_offset():
    emoji = "\U0001F600"  # 😀, non-BMP, 2 UTF-16 code units, 1 Python code point
    text = emoji + "hello"
    # Python code-point index 1 ('h') is Qt UTF-16 offset 2 (emoji took 2 units).
    assert codepoint_index_to_qt_offset(text, 1) == 2
    assert qt_offset_to_codepoint_index(text, 2) == 1
    # end of string
    assert codepoint_index_to_qt_offset(text, len(text)) == 2 + 5
    assert qt_offset_to_codepoint_index(text, 2 + 5) == len(text)


def test_non_bmp_character_inside_selection_round_trips():
    emoji = "\U0001F600"
    text = "hi " + emoji + " there"
    # select from before 'hi' through just after the emoji
    start_cp = 0
    end_cp = text.index(" there")  # code-point index right after the emoji
    start_qt = codepoint_index_to_qt_offset(text, start_cp)
    end_qt = codepoint_index_to_qt_offset(text, end_cp)
    assert qt_offset_to_codepoint_index(text, start_qt) == start_cp
    assert qt_offset_to_codepoint_index(text, end_qt) == end_cp


def test_qt_offset_inside_surrogate_pair_is_rejected():
    emoji = "\U0001F600"
    text = emoji + "hello"
    # offset 1 lands between the two UTF-16 code units of the emoji.
    assert is_qt_offset_on_codepoint_boundary(text, 1) is False
    with pytest.raises(SurrogatePairOffsetError):
        qt_offset_to_codepoint_index(text, 1)


def test_qt_offset_on_boundary_is_accepted():
    emoji = "\U0001F600"
    text = emoji + "hello"
    assert is_qt_offset_on_codepoint_boundary(text, 0) is True
    assert is_qt_offset_on_codepoint_boundary(text, 2) is True


def test_codepoint_index_out_of_bounds_is_rejected():
    with pytest.raises(ValueError):
        codepoint_index_to_qt_offset("hello", -1)
    with pytest.raises(ValueError):
        codepoint_index_to_qt_offset("hello", 100)

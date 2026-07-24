from __future__ import annotations

import pytest

from listentrace.domain.services.text_range import (
    TextRangeError,
    validate_selection,
    whole_cue_range,
)


def test_whole_cue_range_spans_entire_text():
    text = "Bonjour tout le monde"
    start, end = whole_cue_range(text)
    assert validate_selection(text, start, end) == text


def test_partial_selection_returns_substring():
    text = "Bonjour tout le monde"
    assert validate_selection(text, 0, 7) == "Bonjour"
    assert validate_selection(text, 8, 12) == "tout"


def test_empty_selection_at_boundary_is_allowed():
    text = "hello"
    assert validate_selection(text, 5, 5) == ""
    assert validate_selection(text, 0, 0) == ""


def test_negative_start_is_rejected():
    with pytest.raises(TextRangeError):
        validate_selection("hello", -1, 3)


def test_end_before_start_is_rejected():
    with pytest.raises(TextRangeError):
        validate_selection("hello", 3, 1)


def test_end_beyond_text_length_is_rejected():
    with pytest.raises(TextRangeError):
        validate_selection("hello", 0, 10)


def test_unicode_non_ascii_round_trip():
    text = "Comment ça va ? 你好世界"
    # "ça" occupies indices 8-10; "你好" occupies indices 16-18
    assert validate_selection(text, 8, 10) == "ça"
    assert validate_selection(text, 16, 18) == "你好"
    assert validate_selection(text, 0, len(text)) == text

from __future__ import annotations

from typing import Iterable, Protocol

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from listentrace.ui import theme
from listentrace.ui.text_offset_conversion import codepoint_index_to_qt_offset

# M13 Stage B, G20: the transcript-highlight background is a 40% alpha tint
# (never full opacity) -- distinct from the 100%-opacity 12px list/badge
# swatch (`_color_badge_icon`), which is unaffected by this rule. Applies
# uniformly to canonical-default and user-chosen label colors alike.
_TRANSCRIPT_HIGHLIGHT_ALPHA = 0.4

# The color shown wherever a diagnosis label has no stored color (should be
# rare/never in practice), sourced from the `neutral_state` token rather
# than a bare "#CCCCCC" literal. This module is the single canonical source
# -- every window that needs the fallback (player_window.py,
# guided_session_window.py, quick_practice_window.py) imports it from here
# rather than each defining/re-exporting its own copy.
UNKNOWN_LABEL_COLOR = theme.css("neutral_state")


class _LabeledRange(Protocol):
    label_key: str
    selection_start: int
    selection_end: int


def apply_range_highlighting(
    text_edit: QTextEdit,
    cue_text: str,
    ranges: Iterable[_LabeledRange],
    colors: dict[str, str],
    overlap_color: QColor,
) -> None:
    """Clear then repaint background highlighting on `text_edit` for the given
    label-keyed codepoint ranges.

    `ranges` is any iterable of objects exposing `.selection_start`,
    `.selection_end`, `.label_key` — both `Annotation` and
    `SessionDiagnosisEvidence` satisfy this. Shared by the Milestone 4
    transcript workspace and the Milestone 5 guided-session Stage 3 diagnosis
    panel so this Unicode-offset/highlight math is never duplicated.
    """
    document = text_edit.document()
    clear_cursor = QTextCursor(document)
    clear_cursor.select(QTextCursor.SelectionType.Document)
    clear_cursor.setCharFormat(QTextCharFormat())

    range_list = list(ranges)
    if not range_list:
        return

    text_length = len(cue_text)
    coverage: list[list[str]] = [[] for _ in range(text_length)]
    for item in range_list:
        start = max(item.selection_start, 0)
        end = min(item.selection_end, text_length)
        for i in range(start, end):
            coverage[i].append(item.label_key)

    i = 0
    while i < text_length:
        labels_here = coverage[i]
        if not labels_here:
            i += 1
            continue
        j = i
        while j < text_length and coverage[j] == labels_here:
            j += 1

        fmt = QTextCharFormat()
        if len(labels_here) == 1:
            highlight_color = QColor(colors.get(labels_here[0], UNKNOWN_LABEL_COLOR))
            highlight_color.setAlphaF(_TRANSCRIPT_HIGHLIGHT_ALPHA)
            fmt.setBackground(highlight_color)
        else:
            fmt.setBackground(overlap_color)

        # i/j are codepoint indices; convert to Qt UTF-16 offsets before
        # positioning the highlight cursor.
        highlight_cursor = QTextCursor(document)
        highlight_cursor.setPosition(codepoint_index_to_qt_offset(cue_text, i))
        highlight_cursor.setPosition(
            codepoint_index_to_qt_offset(cue_text, j), QTextCursor.MoveMode.KeepAnchor
        )
        highlight_cursor.setCharFormat(fmt)
        i = j

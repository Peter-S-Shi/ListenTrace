from __future__ import annotations

from typing import Iterable, Protocol

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from listentrace.ui.text_offset_conversion import codepoint_index_to_qt_offset


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
            fmt.setBackground(QColor(colors.get(labels_here[0], "#CCCCCC")))
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

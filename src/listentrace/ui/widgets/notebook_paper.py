"""Reusable QPainter-based notebook paper/binding primitives.

These widgets paint the "ruled paper" and "spiral binding" grammar shared by
Player's Notebook Study Desk and Guided Session's writing surfaces, rather
than approximating either with raster assets or fragile CSS borders.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QTextEdit, QWidget

# Faint blue ink for ruled lines -- Professional Blue at ~11% alpha.
RULED_LINE_COLOR = QColor(37, 99, 235, 28)
RULED_LINE_SPACING_PX = 28  # matches comfortable line height at 10pt font


def _ruled_line_phase(spacing_px: int, scroll_offset_px: int) -> int:
    """Where the first ruled line should be painted (viewport-relative y) so
    the periodic line pattern stays anchored to the document instead of the
    viewport. Painting from a fixed viewport-relative offset drew lines that
    stayed still while the text scrolled underneath them -- correct only when
    the scroll offset happened to be an exact multiple of `spacing_px`, and
    visibly drifting out of alignment with text baselines otherwise (final
    Pre-HG2 corrective pass #12)."""
    return (spacing_px - 1 - scroll_offset_px) % spacing_px


def _paint_ruled_lines(painter: QPainter, width: int, height: int, start_y: int) -> None:
    """Shared ruled-line drawing used by both `RuledTextEdit` (scroll-phase
    aware) and `RuledPaperFrame` (static) so the two surfaces render the same
    grammar from one place."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    pen = QPen(RULED_LINE_COLOR)
    pen.setWidth(1)
    painter.setPen(pen)

    y = start_y
    while y < height:
        painter.drawLine(0, y, width, y)
        y += RULED_LINE_SPACING_PX


class RuledTextEdit(QTextEdit):
    """A QTextEdit with visible horizontal ruled lines underneath the text, like a lined notepad.

    Lines are painted via paintEvent so they scale correctly with any text size, require no
    raster images, and remain visible when the widget is scrolled.
    """

    _ruled_line_phase = staticmethod(_ruled_line_phase)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        start_y = self._ruled_line_phase(RULED_LINE_SPACING_PX, self.verticalScrollBar().value())
        _paint_ruled_lines(painter, self.viewport().width(), self.viewport().height(), start_y)
        painter.end()


class RuledPaperFrame(QFrame):
    """A static (non-scrolling) ruled-paper surface for a notebook page body.

    Unlike `RuledTextEdit`, this paints the ruled-line grammar as a plain
    background across the whole frame -- no scroll-phase handling needed,
    since the frame itself never scrolls. Intended to host a normal layout
    of controls (buttons, labels, fields) on top, with the rules showing
    through as the page's writing surface.
    """

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        _paint_ruled_lines(painter, self.width(), self.height(), RULED_LINE_SPACING_PX)
        painter.end()


_RING_HOLE_DIAMETER_PX = 6
_RING_LOOP_DIAMETER_PX = 13
_RING_SPACING_PX = 26
_RING_TOP_MARGIN_PX = 10


class SpiralBindingWidget(QWidget):
    """A vertical column of spiral-notebook rings, painted with QPainter.

    The ring count is derived from the widget's current height every paint,
    so it adapts naturally to resizing without any manual bookkeeping. Each
    ring is a small filled "paper hole" plus a surrounding open "metal loop"
    ellipse, in the `notebook_binding` token color -- no fonts or raster
    assets involved.
    """

    def __init__(self, hole_color: QColor, loop_color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hole_color = hole_color
        self._loop_color = loop_color

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # A narrow binding edge (e.g. a MiniNotebook's own spine) can't fit
        # the full-size loop used by the wide center binding strip -- scale
        # the ring down to whatever width is actually available.
        loop_diameter = max(6.0, min(_RING_LOOP_DIAMETER_PX, self.width() - 4))
        hole_diameter = max(3.0, loop_diameter * (_RING_HOLE_DIAMETER_PX / _RING_LOOP_DIAMETER_PX))

        center_x = self.width() / 2
        loop_pen = QPen(self._loop_color)
        loop_pen.setWidth(2)

        y = _RING_TOP_MARGIN_PX + loop_diameter / 2
        while y + loop_diameter / 2 <= self.height() - _RING_TOP_MARGIN_PX:
            painter.setPen(loop_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                center_x - loop_diameter / 2,
                y - loop_diameter / 2,
                loop_diameter,
                loop_diameter,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._hole_color)
            painter.drawEllipse(
                center_x - hole_diameter / 2,
                y - hole_diameter / 2,
                hole_diameter,
                hole_diameter,
            )
            y += _RING_SPACING_PX
        painter.end()

    def ring_count(self) -> int:
        """The number of rings the current height produces (used by tests)."""
        usable = self.height() - 2 * _RING_TOP_MARGIN_PX - _RING_LOOP_DIAMETER_PX
        if usable < 0:
            return 0
        return int(usable // _RING_SPACING_PX) + 1

"""Reusable QPainter-based notebook paper/binding primitives.

These widgets paint the "ruled paper" and "spiral binding" grammar shared by
Player's Notebook Study Desk and Guided Session's writing surfaces, rather
than approximating either with raster assets or fragile CSS borders.
"""

from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QTextEdit, QWidget

RULED_LINE_SPACING_PX = 28  # matches comfortable line height at 10pt font
MARGIN_LINE_WIDTH_PX = 1
MARGIN_INSET_PX = 32  # distance of the vertical margin rule from the left edge


def ruled_paper_colors() -> tuple[QColor, QColor]:
    """(rule_color, margin_color), sourced from `theme.py`'s `rule_blue`/
    `margin_line` tokens rather than a hardcoded literal (M13 Stage B, G17).

    Imported lazily to avoid a circular import: `theme.py` imports this
    module at load time to build `make_mini_notebook`/`make_spiral_binding_strip`.
    """
    from listentrace.ui import theme

    return theme.qcolor("rule_blue"), theme.qcolor("margin_line")


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
    rule_color, margin_color = ruled_paper_colors()

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    pen = QPen(rule_color)
    pen.setWidth(1)
    painter.setPen(pen)

    y = start_y
    while y < height:
        painter.drawLine(0, y, width, y)
        y += RULED_LINE_SPACING_PX

    _paint_margin_line(painter, height, margin_color)


def _paint_margin_line(painter: QPainter, height: int, margin_color: QColor) -> None:
    """The vertical margin rule near the left edge, like a school notebook's
    red margin line (M13 Stage B, G17) -- shared by both ruled-paper surfaces."""
    pen = QPen(margin_color)
    pen.setWidth(MARGIN_LINE_WIDTH_PX)
    painter.setPen(pen)
    painter.drawLine(MARGIN_INSET_PX, 0, MARGIN_INSET_PX, height)


_GRAIN_TILE_SIZE_PX = 64
_GRAIN_OPACITY = 0.025  # ~2.5%, within the frozen 2-3% contract band
_grain_tile_cache: QPixmap | None = None


def _build_grain_tile() -> QPixmap:
    """A small deterministic pseudo-random luminance-noise tile (fixed
    seed -- not per-frame flicker), tiled across large paper fills for a
    restrained, non-directional procedural grain (M13 Stage B; local/
    procedural only, no runtime-fetched texture asset)."""
    rng = random.Random(1337)
    image = QImage(_GRAIN_TILE_SIZE_PX, _GRAIN_TILE_SIZE_PX, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    alpha = round(255 * _GRAIN_OPACITY)
    for y in range(_GRAIN_TILE_SIZE_PX):
        for x in range(_GRAIN_TILE_SIZE_PX):
            luminance = rng.randint(0, 255)
            image.setPixelColor(x, y, QColor(luminance, luminance, luminance, alpha))
    return QPixmap.fromImage(image)


def _grain_tile() -> QPixmap:
    global _grain_tile_cache
    if _grain_tile_cache is None:
        _grain_tile_cache = _build_grain_tile()
    return _grain_tile_cache


def paint_paper_grain(painter: QPainter, width: int, height: int) -> None:
    """Paint restrained procedural grain over a `width` x `height` rect.
    Callers must paint this *before* ruled lines/text/shadows so grain
    stays subordinate to them per the frozen hierarchy -- never on media,
    controls, highlights, or dense-data regions."""
    painter.drawTiledPixmap(0, 0, width, height, _grain_tile())


class GrainedPaperFrame(QFrame):
    """A top-level page-level paper sheet with restrained procedural grain
    on its fill (M13 Stage B; large paper-sheet fills only -- NOT used for
    mini-notebooks' small fills, which stay plain per the frozen rule).
    Used by `theme.make_notebook_surface()`'s outer frame.
    """

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        paint_paper_grain(painter, self.width(), self.height())
        painter.end()


class GrainedDeskWidget(QWidget):
    """The root workspace/desk background surface with restrained
    procedural grain (M13 Stage B) -- the drop-in replacement for a bare
    `QWidget()` central widget on any workspace window carrying
    `apply_surface(widget, "paper")`/`"workspace"` at the window-root
    level. NOT used for media viewports, form controls, or nested
    surfaces -- only the one root desk-background widget per window.
    """

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        paint_paper_grain(painter, self.width(), self.height())
        painter.end()


class RuledTextEdit(QTextEdit):
    """A QTextEdit with visible horizontal ruled lines underneath the text, like a lined notepad.

    Lines are painted via paintEvent so they scale correctly with any text size, require no
    raster images, and remain visible when the widget is scrolled.
    """

    _ruled_line_phase = staticmethod(_ruled_line_phase)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # QAbstractScrollArea normally auto-erases the viewport with the
        # palette base color before every paint; with it on, whatever this
        # subclass paints in `paintEvent` before delegating to QTextEdit's
        # own text painting gets wiped, which is why the ruled/margin lines
        # previously ended up drawn *over* the text instead of under it
        # (corrective: rendering contract requires lines under text).
        self.viewport().setAutoFillBackground(False)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self.viewport())
        start_y = self._ruled_line_phase(RULED_LINE_SPACING_PX, self.verticalScrollBar().value())
        _paint_ruled_lines(painter, self.viewport().width(), self.viewport().height(), start_y)
        painter.end()
        super().paintEvent(event)


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
_RING_SPACING_PX = 32  # G22: corrected from 26px (below the 28px tolerance floor)
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

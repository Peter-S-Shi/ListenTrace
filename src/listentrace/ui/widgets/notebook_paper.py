"""Reusable QPainter-based notebook paper/binding primitives.

These widgets paint the "ruled paper" and "spiral binding" grammar shared by
Player's Notebook Study Desk and Guided Session's writing surfaces, rather
than approximating either with raster assets or fragile CSS borders.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
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
        _paint_dog_ear(self)


def _seeded_offset(seed_key: tuple, index: int, amplitude: float) -> float:
    """A fixed, deterministic offset in `[-amplitude, amplitude]`, stable for
    a given `(seed_key, index)` -- never per-frame/per-paint randomness."""
    rng = random.Random(str((*seed_key, index)))
    return (rng.random() * 2 - 1) * amplitude


def paint_ink_outline(painter: QPainter, width: float, height: float, color: QColor, radius: float = 9.0) -> None:
    """Paint a deterministic, gently irregular rounded-rect outline in a
    doubled sketchy stroke -- the ink/pencil line character the approved
    due-frame boards show on every button and card edge (a hand-drawn line
    is very slightly retraced, not a mathematically single, perfectly
    uniform machine stroke). M13 Due-Frame Polish, Axis 1 continuation.

    Deterministic from `(width, height)` only: one control at one size
    always renders identically, and a resize recomputes to a new but still
    fixed shape -- never flickering per-frame noise.
    """
    if width <= 3 or height <= 3:
        return
    inset = 1.4
    rect = QRectF(inset, inset, width - 2 * inset, height - 2 * inset)
    r = min(radius, rect.width() / 2, rect.height() / 2)
    base_path = QPainterPath()
    base_path.addRoundedRect(rect, r, r)

    seed = (round(width), round(height))
    # Two passes: a crisp main stroke, and a second, faint, very slightly
    # offset/rotated retrace -- the classic "hand went over the line twice"
    # sketch technique, cheap and reliable compared to perturbing the path
    # itself point-by-point.
    passes = (
        (0.0, 0.0, 0.0, 1.0, 1.15),
        (
            _seeded_offset(seed, 0, 0.9),
            _seeded_offset(seed, 1, 0.9),
            _seeded_offset(seed, 2, 0.6),
            0.5,
            1.05,
        ),
    )
    center = rect.center()
    for dx, dy, rotation_deg, alpha, width_px in passes:
        painter.save()
        painter.translate(center)
        painter.rotate(rotation_deg)
        painter.translate(-center)
        painter.translate(dx, dy)
        stroke_color = QColor(color)
        stroke_color.setAlphaF(stroke_color.alphaF() * alpha)
        pen = QPen(stroke_color)
        pen.setWidthF(width_px)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(base_path)
        painter.restore()


_DOG_EAR_SIZE_PX = 15
_DOG_EAR_INSET_PX = 9  # keeps the fold clear of a rounded card's own corner radius


def _paint_dog_ear(widget: QWidget) -> None:
    """Paint one small lifted-paper-corner fold at the bottom-right, so the
    surface reads as a physical sheet of paper rather than a flat machine
    rectangle (M13 Due-Frame-First Visual Polish, Axis 1 -- the approved
    due-frame boards consistently show layered/lifted paper edges, never a
    single flat-bordered rectangle). Fixed size/position, not per-instance
    randomness -- every consumer gets the identical controlled fold.
    """
    from listentrace.ui import theme

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    w, h = widget.width(), widget.height()
    x = w - _DOG_EAR_INSET_PX
    y = h - _DOG_EAR_INSET_PX
    fold = QPolygonF(
        [
            QPointF(x - _DOG_EAR_SIZE_PX, y),
            QPointF(x, y),
            QPointF(x, y - _DOG_EAR_SIZE_PX),
        ]
    )
    painter.setPen(QPen(theme.qcolor("paper_edge"), 1))
    painter.setBrush(theme.qcolor("paper_deep"))
    painter.drawPolygon(fold)
    painter.end()


class LayeredPaperFrame(QFrame):
    """A page/card frame with a painted ink-outline edge and one small
    lifted paper corner at its bottom-right, instead of a perfectly flat
    single machine-drawn rectangle (M13 Due-Frame Polish, Axis 1). Its own
    QSS supplies the fill/radius only (border is transparent -- the QSS
    role rule is responsible for that); this class paints the edge line
    itself, then overlays the fixed dog-ear fold.
    """

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        from listentrace.ui import theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_ink_outline(painter, self.width(), self.height(), theme.qcolor("paper_edge"), radius=9.0)
        painter.end()
        _paint_dog_ear(self)


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

"""Ruled-paper rendering contract tests (M13 Stage B, G17/G22).

Seams under test (confirmed against M13_RENDERING_IMPLEMENTATION_MAP.md
§3/§4.3 G17 and Gap Register G22): the module-level color/geometry constants
`notebook_paper` exposes to its own `paintEvent` overrides and to callers via
`ruled_paper_colors()`, plus the pure phase/ring-count calculations already
covered by `test_theme.py`'s `SpiralBindingWidget` test. No pixel-level paint
assertions -- consistent with the existing test style in this file's sibling,
which tests the same pure calculations rather than rendered output.
"""

from __future__ import annotations

from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QTextEdit

from listentrace.ui import theme
from listentrace.ui.widgets import notebook_paper


def test_ruled_paper_colors_are_sourced_from_theme_tokens_not_hardcoded():
    rule_color, margin_color = notebook_paper.ruled_paper_colors()

    assert rule_color.getRgb() == theme.qcolor("rule_blue").getRgb()
    assert margin_color.getRgb() == theme.qcolor("margin_line").getRgb()


def test_ruled_line_spacing_matches_the_canonical_28px_contract():
    assert notebook_paper.RULED_LINE_SPACING_PX == 28


def test_margin_line_geometry_matches_the_canonical_contract():
    assert notebook_paper.MARGIN_LINE_WIDTH_PX == 1
    assert notebook_paper.MARGIN_INSET_PX == 32


def test_spiral_ring_pitch_matches_the_corrected_32px_target():
    # G22: was 26px (below the 28px tolerance floor), corrected to 32px.
    assert notebook_paper._RING_SPACING_PX == 32


def test_grain_tile_opacity_is_within_the_frozen_2_to_3_percent_band(qapp):
    tile = notebook_paper._grain_tile()

    # Sample the alpha channel directly -- the tile is a fixed-seed
    # deterministic luminance-noise pattern, so every pixel shares the same
    # alpha regardless of its (random) luminance value.
    alpha_fraction = tile.toImage().pixelColor(0, 0).alphaF()
    assert 0.02 <= alpha_fraction <= 0.03


def test_grain_tile_is_deterministic_across_calls(qapp):
    """Fixed seed, not per-frame flicker -- repeated calls return the cached
    tile, and rebuilding it from scratch reproduces the same pixels."""
    first = notebook_paper._build_grain_tile()
    second = notebook_paper._build_grain_tile()

    assert first.toImage() == second.toImage()


def test_make_notebook_surface_uses_the_grained_paper_frame(qapp):
    from listentrace.ui import theme

    frame, _layout = theme.make_notebook_surface("Title")

    assert isinstance(frame, notebook_paper.GrainedPaperFrame)


def test_ruled_text_edit_viewport_does_not_autofill_over_the_custom_paint_layer(qapp):
    """The rendering contract requires ruled/margin lines to sit *under*
    readable text. QAbstractScrollArea's default viewport autofill erases
    whatever a subclass painted before delegating to QTextEdit's own text
    painting, which is exactly what previously made the lines draw over the
    text instead of under it (paint order alone isn't enough while autofill
    is on)."""
    widget = notebook_paper.RuledTextEdit()

    assert widget.viewport().autoFillBackground() is False


def test_ruled_text_edit_paints_ruled_lines_before_delegating_to_qtextedit_text_paint(qapp, monkeypatch):
    """Regression coverage for the corrective: ruled/margin lines must be
    painted before QTextEdit's own paintEvent draws the text, so the text
    layer composites on top. Spies on both painting steps and asserts call
    order through the real `paintEvent` public override -- not screenshot
    pixels, not private internals."""
    order: list[str] = []
    monkeypatch.setattr(
        notebook_paper, "_paint_ruled_lines", lambda *a, **k: order.append("rules")
    )
    original_text_paint = QTextEdit.paintEvent
    monkeypatch.setattr(
        QTextEdit,
        "paintEvent",
        lambda self, event: (order.append("text"), original_text_paint(self, event))[1],
    )

    widget = notebook_paper.RuledTextEdit()
    widget.resize(200, 200)
    widget.paintEvent(QPaintEvent(widget.rect()))

    assert order == ["rules", "text"]

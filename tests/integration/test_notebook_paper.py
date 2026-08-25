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

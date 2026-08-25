"""Central design tokens and QSS theme for ListenTrace's presentation layer.

Milestone 13 (Advanced UI/UX Reconstruction) Theme System:
- Professional Blue primary accent (#2563EB / #3B82F6 family)
- Notebook Study Desk personality (DESIGN.md §3 canonical palette, migrated
  in Stage B; token keys are stable across the migration, only values moved)
- Lined Spiral Notebook & Ruled Study Paper contextual surfaces
- Spacious Learning density (4 / 8 / 16 / 24 / 32 px scale)
- Contextual Surface Modes (Workspace, Paper Study, Ruled Notebook, Dark Focus)
- Light theme is the actual runtime mode: `app.py` calls `apply_theme(app)`
  with no mode argument, so the whole application always renders with
  `_TOKENS_LIGHT`. The Player's "Dark Focus" cinema surface is a fixed dark
  *surface* token (`surface_cinema` etc.) defined inside `_TOKENS_LIGHT`
  itself, not a runtime light/dark mode switch. `_TOKENS_DARK` and
  `build_stylesheet`/`css`/`qcolor`'s `theme_mode="dark"` parameter exist
  but nothing in the product calls them with `"dark"` — there is no
  app-wide runtime light/dark toggle wired in yet. Do not describe this as
  "full light and dark support" until one exists.
- Two-layer QSS model (Base Layer + Opt-in Component/Surface Layer)

Product-semantic tokens (cue_active, text_overlap, quiz_correct, quiz_incorrect,
chart palette) preserve semantic meaning and are distinct from brand tokens.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from listentrace.ui.widgets.notebook_paper import RuledPaperFrame, SpiralBindingWidget

# ---------------------------------------------------------------------------
# Tokens: Light & Dark Palettes
# ---------------------------------------------------------------------------

_TOKENS_LIGHT: dict[str, tuple[int, int, int, int]] = {
    # Brand: Notebook Study Desk + Professional Blue Accent (DESIGN.md §3
    # canonical values -- M13 Stage B whole-product migration, per
    # M13_RENDERING_IMPLEMENTATION_MAP.md §2). Keys are stable across the
    # migration; only values changed.
    "page": (246, 241, 231, 255),           # #F6F1E7 desk_bg
    "surface": (255, 254, 251, 255),        # #FFFEFB surface_plain
    "surface_soft": (250, 246, 237, 255),   # #FAF6ED paper_secondary
    "surface_sidebar": (240, 232, 220, 255), # #F0E8DC sidebar_bg
    "surface_paper": (255, 253, 248, 255),  # #FFFDF8 paper_primary
    "surface_cinema": (15, 17, 21, 255),    # #0F1115 media_black
    "ink": (31, 29, 26, 255),               # #1F1D1A ink_primary
    "muted": (111, 102, 92, 255),           # #6F665C ink_muted
    "line": (216, 207, 193, 255),           # #D8CFC1 warm_border
    "line_ruled": (230, 222, 210, 255),     # #E6DED2 warm_divider
    "accent": (37, 99, 235, 255),           # #2563EB Professional Blue
    "accent_hover": (29, 78, 216, 255),     # #1D4ED8
    "accent_pressed": (30, 64, 175, 255),   # #1E40AF
    "accent_subtle": (239, 246, 255, 255),  # #EFF6FF accent_soft
    "secondary": (90, 81, 71, 255),         # #5A5147 ink_secondary
    # Semantic
    "success": (22, 130, 71, 255),          # #168247
    "danger": (217, 56, 58, 255),           # #D9383A
    "danger_hover": (191, 38, 40, 255),     # #BF2628
    "danger_subtle": (253, 242, 242, 255),  # #FDF2F2
    "warning": (200, 117, 8, 255),          # #C87508
    "warning_subtle": (255, 244, 214, 255), # #FFF4D6
    "info": (37, 99, 235, 255),             # #2563EB
    "focus": (96, 165, 250, 255),           # #60A5FA focus_ring
    "disabled_text": (145, 137, 126, 255),  # #91897E universal disabled text
    "disabled_border": (209, 202, 192, 255), # #D1CAC0 universal disabled border
    "disabled_surface": (221, 215, 206, 255), # #DDD7CE universal disabled bg
    # Dedicated Product-Semantic Tokens (not part of the DESIGN.md palette;
    # unchanged by this migration)
    "cue_active": (255, 243, 205, 255),    # #FFF3CD active cue highlight
    "text_overlap": (208, 208, 208, 255),  # #D0D0D0
    "quiz_correct": (22, 130, 71, 255),    # aligned to `success` #168247
    "quiz_incorrect": (220, 38, 38, 255),  # aligned to `incorrect` #DC2626
    "chart_background": (255, 253, 248, 255), # paper_primary #FFFDF8
    "chart_bar": (37, 99, 235, 255),       # #2563EB aligned with Professional Blue
    "chart_axis": (230, 222, 210, 255),    # warm_divider #E6DED2
    "chart_text": (31, 29, 26, 255),       # ink_primary #1F1D1A
    # Notebook/paper detail palette (DESIGN.md §3/§6) -- additive, new keys.
    "paper_deep": (243, 235, 221, 255),        # #F3EBDD directory backing / paper-edge contrast
    "paper_edge": (207, 195, 178, 255),        # #CFC3B2 visible paper/card edge
    "rule_blue": (191, 219, 254, 133),         # #BFDBFE @ 52%
    "margin_line": (230, 167, 173, 117),       # #E6A7AD @ 46%
    "handwritten_blue": (36, 88, 184, 255),    # #2458B8
    "accent_selected": (219, 234, 254, 255),   # #DBEAFE
    "accent_border_soft": (147, 197, 253, 255), # #93C5FD
    "spiral_shadow": (77, 86, 96, 64),         # #4D5660 @ 25%
    "paper_hole": (233, 225, 213, 255),        # #E9E1D5
    "tape_cream": (232, 214, 168, 255),        # #E8D6A8
    "tape_blue": (145, 180, 228, 255),         # #91B4E4
    "sticky_note": (242, 226, 180, 255),       # #F2E2B4
    "paperclip_metal": (124, 133, 141, 255),   # #7C858D
    "leaf_green": (79, 122, 88, 255),          # #4F7A58
    "flower_pink": (215, 142, 162, 255),       # #D78EA2
    "star_gold": (210, 164, 58, 255),          # #D2A43A
    "incorrect": (220, 38, 38, 255),           # #DC2626
    "neutral_state": (119, 110, 100, 255),     # #776E64
    "ink_caption": (123, 113, 101, 255),       # #7B7165
    "ink_placeholder": (148, 138, 125, 255),   # #948A7D
    "ink_on_accent": (255, 253, 248, 255),     # #FFFDF8
    "ink_on_dark": (247, 244, 238, 255),       # #F7F4EE
    "shadow_full": (91, 73, 53, 36),           # #5B4935 @ 14%, page-level paper sheet shadow
    "shadow_mini": (91, 73, 53, 26),           # #5B4935 @ 10%, mini-notebook shadow
    # Player Notebook Study Desk (M13 Player Reconstruction) -- scoped, additive tokens.
    # `line_ruled` above is the shared quiet-divider color (MainWindow dossier, Guided
    # Session Stage 5); these two tokens exist so the Player's notebook surfaces can use
    # the canonical ruled-paper pale blue without altering that shared look.
    "notebook_rule_blue": (191, 219, 254, 133),  # #BFDBFE @ 52% pale-blue ruled line
    "notebook_binding": (125, 135, 148, 255),    # #7D8794 spiral_metal
}

_TOKENS_DARK: dict[str, tuple[int, int, int, int]] = {
    # Brand: Deep Slate + Bright Professional Blue Accent
    "page": (18, 20, 24, 255),             # #121418
    "surface": (30, 34, 42, 255),          # #1E222A
    "surface_soft": (25, 29, 36, 255),     # #191D24
    "surface_sidebar": (23, 26, 32, 255),  # #171A20
    "surface_paper": (27, 30, 37, 255),    # #1B1E25
    "surface_cinema": (10, 12, 14, 255),   # #0A0C0E
    "ink": (237, 237, 236, 255),           # #EDEDEC
    "muted": (115, 110, 101, 255),         # #736E65
    "line": (255, 255, 255, 33),           # subtle white border ~13% alpha
    "line_ruled": (255, 255, 255, 20),     # subtle ruled line ~8% alpha
    "accent": (59, 130, 246, 255),         # #3B82F6 Bright Blue
    "accent_hover": (96, 165, 250, 255),   # #60A5FA
    "accent_pressed": (37, 99, 235, 255),  # #2563EB
    "accent_subtle": (59, 130, 246, 45),
    "secondary": (173, 169, 159, 255),     # #ADA99F
    # Semantic
    "success": (52, 211, 153, 255),        # #34D399
    "danger": (239, 68, 68, 255),          # #EF4444
    "danger_hover": (248, 113, 113, 255),  # #F87171
    "danger_subtle": (239, 68, 68, 45),
    "warning": (245, 158, 11, 255),        # #F59E0B
    "warning_subtle": (245, 158, 11, 45),
    "info": (59, 130, 246, 255),
    "focus": (59, 130, 246, 255),
    "disabled_text": (115, 110, 101, 255),
    "disabled_surface": (30, 34, 42, 255),
    # Dedicated Product-Semantic Tokens
    "cue_active": (59, 130, 246, 45),
    "text_overlap": (100, 116, 139, 255),
    "quiz_correct": (52, 211, 153, 255),
    "quiz_incorrect": (248, 113, 113, 255),
    "chart_background": (30, 34, 42, 255),
    "chart_bar": (59, 130, 246, 255),
    "chart_axis": (100, 116, 139, 255),
    "chart_text": (203, 213, 225, 255),
}

# Default light tokens for backward compatibility
_TOKENS = _TOKENS_LIGHT

# ---------------------------------------------------------------------------
# Spacing & Shape Scale (Spacious Learning Density)
# ---------------------------------------------------------------------------

SPACE_COMPACT = 4
SPACE_NORMAL = 8
SPACE_SECTION = 16
SPACE_PAGE = 24
SPACE_LARGE = 32

RADIUS_CONTROL = 6
RADIUS_CARD = 10
RADIUS_PILL = 9999
BORDER_WIDTH = 1

FONT_FAMILY = (
    '"Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", '
    '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'
)
# Latin-only decorative face for short handwritten stamps/tags; CJK text must
# never be forced into this stack and should fall back to `FONT_FAMILY` at the
# call site instead (DESIGN.md §4.2).
HANDWRITING_FONT_FAMILY = '"Segoe Print", "Segoe Script", "Segoe UI"'
MONOSPACE_FONT_FAMILY = '"Cascadia Mono", "Consolas", "Courier New", monospace'


def qcolor(token: str, theme_mode: str = "light") -> QColor:
    """Return a real `QColor` for a token in the specified theme."""
    palette = _TOKENS_DARK if theme_mode == "dark" else _TOKENS_LIGHT
    r, g, b, a = palette.get(token, _TOKENS_LIGHT[token])
    return QColor(r, g, b, a)


def css(token: str, theme_mode: str = "light") -> str:
    """Return a QSS-compatible color string for a token."""
    palette = _TOKENS_DARK if theme_mode == "dark" else _TOKENS_LIGHT
    r, g, b, a = palette.get(token, _TOKENS_LIGHT[token])
    if a == 255:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"rgba({r}, {g}, {b}, {a / 255:.3f})"


def apply_role(widget: QWidget, role: str) -> None:
    """Tag `widget` with a presentation role consumed by the component-layer QSS."""
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def apply_surface(widget: QWidget, surface: str) -> None:
    """Tag `widget` with a surface family (workspace / paper / cinema / elevated)."""
    widget.setProperty("surface", surface)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def make_card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A light `QFrame[role="card"]` surface with spacious padding."""
    frame = QFrame()
    apply_role(frame, "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACE_SECTION, SPACE_SECTION, SPACE_SECTION, SPACE_SECTION)
    layout.setSpacing(SPACE_NORMAL)
    if title is not None:
        caption = QLabel(title)
        apply_role(caption, "caption")
        layout.addWidget(caption)
    return frame, layout


def make_paper_surface(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A calm matte `QFrame[surface="paper"]` surface for study / recall / diagnosis."""
    frame = QFrame()
    apply_surface(frame, "paper")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACE_SECTION, SPACE_SECTION, SPACE_SECTION, SPACE_SECTION)
    layout.setSpacing(SPACE_NORMAL)
    if title is not None:
        caption = QLabel(title)
        apply_role(caption, "title")
        layout.addWidget(caption)
    return frame, layout


def make_notebook_surface(
    title: str | None = None,
    context_label: str | None = "Study Dossier",
) -> tuple[QFrame, QVBoxLayout]:
    """A lined spiral notebook study surface with wire-binding cues and ruled paper styling.

    Args:
        title: Optional title rendered inside the content area.
        context_label: The label shown in the spiral bar header.  Pass ``None``
            to omit the stamp entirely (e.g. for Stage-5 Final Recall where
            "Study Dossier" would be semantically wrong).  Defaults to
            ``"Study Dossier"`` for backward compatibility with the MainWindow
            dossier panel.
    """
    frame = QFrame()
    apply_surface(frame, "paper")
    apply_role(frame, "notebook_page")
    root_layout = QVBoxLayout(frame)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    # Wire binding / spiral header bar
    spiral_bar = QFrame()
    apply_role(spiral_bar, "notebook_spiral_bar")
    spiral_layout = QHBoxLayout(spiral_bar)
    spiral_layout.setContentsMargins(SPACE_SECTION, SPACE_COMPACT, SPACE_SECTION, SPACE_COMPACT)

    spiral_cue = QLabel("◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎  ◎")
    apply_role(spiral_cue, "notebook_spiral_cues")
    # Purely decorative -- let the layout shrink it below its natural text
    # width instead of it forcing the whole notebook surface's minimum width
    # (a real bug: on a narrow host like the Player's split panes, this label's
    # un-wrapped sizeHint alone was inflating the surface to 700+px wide).
    spiral_cue.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    spiral_layout.addWidget(spiral_cue)
    spiral_layout.addStretch(1)

    if context_label is not None:
        doodle_stamp = QLabel(context_label)
        apply_role(doodle_stamp, "notebook_doodle_tag")
        spiral_layout.addWidget(doodle_stamp)
    root_layout.addWidget(spiral_bar)

    # Content container with ruled margins
    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)
    content_layout.setContentsMargins(SPACE_SECTION, SPACE_SECTION, SPACE_SECTION, SPACE_SECTION)
    content_layout.setSpacing(SPACE_NORMAL)

    if title is not None:
        header_row = QHBoxLayout()
        title_label = QLabel(title)
        apply_role(title_label, "title")
        header_row.addWidget(title_label)
        header_row.addStretch(1)
        content_layout.addLayout(header_row)

    root_layout.addWidget(content_widget, 1)
    return frame, content_layout


_SPIRAL_BINDING_STRIP_WIDTH_PX = 28


def _make_notebook_binding_widget(parent: QWidget | None = None) -> SpiralBindingWidget:
    """A `SpiralBindingWidget` using the standard notebook hole/loop token pairing."""
    return SpiralBindingWidget(qcolor("surface_paper"), qcolor("notebook_binding"), parent)


def make_spiral_binding_strip() -> QFrame:
    """A narrow vertical seam styled as an open-book center binding.

    Placed as the fixed-width middle widget of a 3-pane `QSplitter` so the two
    outer panes read as facing notebook pages while remaining independently
    resizable (the binding strip itself is never collapsible or draggable).
    The binding itself is a real `QPainter`-rendered `SpiralBindingWidget`
    (paper-hole + metal-loop rings, findable as `strip.findChild(SpiralBindingWidget)`)
    whose ring count adapts to the strip's height, not a font-glyph column.
    """
    strip = QFrame()
    apply_role(strip, "spiral_binding_strip")
    strip.setMinimumWidth(_SPIRAL_BINDING_STRIP_WIDTH_PX)
    strip.setMaximumWidth(_SPIRAL_BINDING_STRIP_WIDTH_PX)
    layout = QVBoxLayout(strip)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    binding = _make_notebook_binding_widget()
    layout.addWidget(binding, 1)
    return strip


def make_media_frame() -> tuple[QFrame, QVBoxLayout]:
    """A warm paper frame around a media viewport -- media placed on a study desk."""
    frame = QFrame()
    apply_role(frame, "media_frame")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL)
    layout.setSpacing(SPACE_NORMAL)
    return frame, layout


_MINI_NOTEBOOK_BINDING_WIDTH_PX = 10


def make_mini_notebook(title: str) -> tuple[QFrame, QVBoxLayout]:
    """A hand-sized spiral notebook page for one control group.

    A real `SpiralBindingWidget` binding edge runs down the left side, and
    the body is a `RuledPaperFrame` (pale-blue ruled lines painted as the
    page surface, not just list-row separators) -- so this reads as an
    actual notebook page rather than a titled card.
    """
    frame = QFrame()
    apply_role(frame, "mini_notebook_card")
    root_layout = QHBoxLayout(frame)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    binding_edge = QFrame()
    apply_role(binding_edge, "mini_notebook_binding_edge")
    binding_edge.setFixedWidth(_MINI_NOTEBOOK_BINDING_WIDTH_PX)
    binding_edge_layout = QVBoxLayout(binding_edge)
    binding_edge_layout.setContentsMargins(0, 0, 0, 0)
    binding_edge_layout.setSpacing(0)
    binding_edge_layout.addWidget(_make_notebook_binding_widget(), 1)
    root_layout.addWidget(binding_edge)

    page = QVBoxLayout()
    page.setContentsMargins(0, 0, 0, 0)
    page.setSpacing(0)

    header_bar = QFrame()
    apply_role(header_bar, "mini_notebook_spiral_bar")
    header_layout = QHBoxLayout(header_bar)
    header_layout.setContentsMargins(SPACE_NORMAL, SPACE_COMPACT, SPACE_NORMAL, SPACE_COMPACT)
    title_label = QLabel(title)
    apply_role(title_label, "mini_notebook_title")
    header_layout.addWidget(title_label)
    header_layout.addStretch(1)
    page.addWidget(header_bar)

    body = RuledPaperFrame()
    apply_role(body, "mini_notebook_body")
    content_layout = QVBoxLayout(body)
    content_layout.setContentsMargins(SPACE_COMPACT, SPACE_COMPACT, SPACE_COMPACT, SPACE_COMPACT)
    content_layout.setSpacing(SPACE_COMPACT)
    page.addWidget(body, 1)

    root_layout.addLayout(page, 1)
    return frame, content_layout


def configure_long_text_list(list_widget: QListWidget) -> None:
    """Wrap long row text instead of horizontal scrolling."""
    list_widget.setWordWrap(True)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


# ---------------------------------------------------------------------------
# QSS Stylesheet Builders
# ---------------------------------------------------------------------------

def _build_base_qss(m: str) -> str:
    return f"""
QWidget {{
    background-color: {css('page', m)};
    color: {css('ink', m)};
    font-family: {FONT_FAMILY};
    font-size: 10pt;
}}
QToolTip {{
    background-color: {css('surface', m)};
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {{
    selection-background-color: {css('accent', m)};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus {{
    border: {BORDER_WIDTH}px solid {css('focus', m)};
}}
*:disabled {{
    color: {css('disabled_text', m)};
}}
QLabel {{
    background-color: transparent;
}}
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QListWidget::item:selected, QListWidget::item:selected:active {{
    background-color: {css('accent', m)};
    color: #FFFFFF;
}}
QListWidget::item:selected:!active {{
    background-color: {css('accent_hover', m)};
    color: #FFFFFF;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {css('line', m)};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {css('accent', m)};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {css('accent', m)};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {css('accent_hover', m)};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
}}
QScrollBar::handle {{
    background: {css('line', m)};
    border-radius: 4px;
}}
QScrollBar::handle:hover {{
    background: {css('muted', m)};
}}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    width: 0px;
    height: 0px;
    background: none;
}}
QSplitter::handle {{
    background-color: {css('line', m)};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
"""


def _build_component_qss(m: str) -> str:
    return f"""
/* Typography & Labels */
QLabel[role="page_title"] {{ font-size: 20px; font-weight: bold; color: {css('ink', m)}; }}
QLabel[role="title"] {{ font-size: 15px; font-weight: bold; color: {css('ink', m)}; }}
QLabel[role="subtitle"] {{ font-size: 13px; color: {css('muted', m)}; }}
QLabel[role="caption"] {{ font-size: 11px; font-weight: bold; text-transform: uppercase; color: {css('muted', m)}; }}
QLabel[role="muted"] {{ color: {css('muted', m)}; }}
QLabel[role="error"] {{ color: {css('danger', m)}; }}
QLabel[role="warning"] {{ color: {css('warning', m)}; }}
QLabel[role="success"] {{ color: {css('success', m)}; }}
QLabel[role="monospace"] {{ font-family: {MONOSPACE_FONT_FAMILY}; color: {css('muted', m)}; }}

/* Notebook & Lined Paper Elements */
QFrame[role="notebook_page"] {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}

QFrame[role="notebook_spiral_bar"] {{
    background-color: {css('surface_soft', m)};
    border-bottom: 1px solid {css('line', m)};
    border-top-left-radius: {RADIUS_CARD}px;
    border-top-right-radius: {RADIUS_CARD}px;
}}

QLabel[role="notebook_spiral_cues"] {{
    color: {css('muted', m)};
    font-size: 10px;
    letter-spacing: 2px;
}}

QLabel[role="notebook_doodle_tag"] {{
    color: {css('muted', m)};
    font-size: 11px;
    font-weight: 600;
}}

/* Ruled List for Notebook Archive / Material Browsing */
QListWidget[role="ruled_list"] {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_COMPACT}px;
}}
QListWidget[role="ruled_list"]::item {{
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    border-bottom: 1px solid {css('line_ruled', m)};
    border-radius: {RADIUS_CONTROL}px;
    margin-bottom: 2px;
}}
QListWidget[role="ruled_list"]::item:hover {{
    background-color: {css('surface_soft', m)};
}}
QListWidget[role="ruled_list"]::item:selected, QListWidget[role="ruled_list"]::item:selected:active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}
QListWidget[role="ruled_list"]::item:selected:!active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent_hover', m)};
}}

/* Ruled Metadata Rows in Dossier */
QLabel[role="ruled_row"] {{
    border-bottom: 1px solid {css('line_ruled', m)};
    padding: {SPACE_COMPACT + 2}px 0px;
    font-size: 13px;
    color: {css('ink', m)};
}}

/* Navigation Directory / Bookmark Pane Items */
QPushButton[role="nav_item"] {{
    text-align: left;
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    font-size: 13px;
    font-weight: 500;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    background-color: transparent;
    color: {css('ink', m)};
}}
QPushButton[role="nav_item"]:hover {{
    background-color: {css('surface_soft', m)};
}}
QPushButton[role="nav_item"][active="true"] {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}

/* Badges & Chips */
QLabel[role="chip"] {{
    background-color: {css('surface_soft', m)};
    color: {css('secondary', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_PILL}px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="badge_primary"] {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    border-radius: {RADIUS_PILL}px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="badge_warning"] {{
    background-color: {css('warning_subtle', m)};
    color: {css('warning', m)};
    border: {BORDER_WIDTH}px solid {css('warning', m)};
    border-radius: {RADIUS_PILL}px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="badge_success"] {{
    background-color: {css('surface_soft', m)};
    color: {css('success', m)};
    border: {BORDER_WIDTH}px solid {css('success', m)};
    border-radius: {RADIUS_PILL}px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* Player Notebook Study Desk (M13 Player Reconstruction) */
QFrame[role="spiral_binding_strip"] {{
    background-color: {css('surface_soft', m)};
    border-left: {BORDER_WIDTH}px solid {css('line', m)};
    border-right: {BORDER_WIDTH}px solid {css('line', m)};
}}
/* Wider drag hit-target for the Player's own splitter only -- every other
   QSplitter in the app keeps the global 1px handle above. */
QSplitter[role="player_split"]::handle:horizontal {{
    width: 6px;
    background-color: transparent;
}}
QSplitter[role="player_split"]::handle:horizontal:hover {{
    background-color: {css('accent_subtle', m)};
}}
QFrame[role="media_frame"] {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}
QLabel[role="study_status_strip"] {{
    background-color: {css('surface_soft', m)};
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
    font-size: 13px;
    font-weight: 600;
}}
QFrame[role="mini_notebook_card"] {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}
/* Compact button footprint scoped to mini-notebook cards only -- keeps three
   hand-sized control notebooks side-by-side at practical Player widths
   without touching the "secondary"/"quiet" roles used elsewhere. */
QFrame[role="mini_notebook_card"] QPushButton[role="secondary"],
QFrame[role="mini_notebook_card"] QPushButton[role="quiet"] {{
    padding: {SPACE_COMPACT}px {SPACE_COMPACT + 2}px;
    font-size: 9pt;
}}
QFrame[role="mini_notebook_spiral_bar"] {{
    background-color: {css('surface_soft', m)};
    border-bottom: 1px solid {css('line', m)};
    border-top-right-radius: {RADIUS_CARD}px;
}}
QLabel[role="mini_notebook_title"] {{
    color: {css('muted', m)};
    font-size: 11px;
    font-weight: 700;
}}
QFrame[role="mini_notebook_binding_edge"] {{
    background-color: {css('surface_soft', m)};
    border-right: 1px solid {css('line', m)};
    border-top-left-radius: {RADIUS_CARD}px;
    border-bottom-left-radius: {RADIUS_CARD}px;
}}
QFrame[role="mini_notebook_body"] {{
    background-color: {css('surface_paper', m)};
    border: none;
    border-bottom-right-radius: {RADIUS_CARD}px;
}}
QListWidget[role="ruled_list_notebook"] {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_COMPACT}px;
}}
QListWidget[role="ruled_list_notebook"]::item {{
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    border-bottom: 2px solid {css('notebook_rule_blue', m)};
    border-radius: {RADIUS_CONTROL}px;
    margin-bottom: 2px;
}}
QListWidget[role="ruled_list_notebook"]::item:hover {{
    background-color: {css('surface_soft', m)};
}}
QListWidget[role="ruled_list_notebook"]::item:selected, QListWidget[role="ruled_list_notebook"]::item:selected:active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}
QListWidget[role="ruled_list_notebook"]::item:selected:!active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent_hover', m)};
}}
/* Compact tab bar so the Annotate/Cue Note/Save Item pages fit without
   Qt's scroll-arrow overflow indicator inside the narrower Annotation
   Notebook card -- scoped to this tab widget only. */
QTabWidget[role="notebook_tabs"] QTabBar::tab {{
    padding: {SPACE_COMPACT}px {SPACE_COMPACT + 2}px;
    margin-right: 1px;
}}

/* Annotation Notebook: writing-field / notebook-action grammar so Annotate /
   Cue Note / Save Item read as a study notebook page rather than a generic
   desktop CRUD form. */
QFrame[role="notebook_tab_page"] {{
    background-color: {css('surface_paper', m)};
    border: none;
}}
QLineEdit[role="notebook_writing_field"] {{
    background-color: transparent;
    border: none;
    border-bottom: {BORDER_WIDTH}px solid {css('notebook_rule_blue', m)};
    border-radius: 0px;
    padding: {SPACE_COMPACT}px {SPACE_COMPACT}px;
}}
QLineEdit[role="notebook_writing_field"]:focus {{
    border-bottom: 2px solid {css('accent', m)};
}}
QLineEdit[role="notebook_writing_field"]:disabled {{
    border-bottom: {BORDER_WIDTH}px solid {css('line', m)};
}}
QPushButton[role="notebook_primary_action"] {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    font-weight: 600;
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="notebook_primary_action"]:hover {{
    background-color: {css('accent', m)};
    color: #FFFFFF;
}}
QPushButton[role="notebook_primary_action"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
    border-color: {css('line', m)};
}}
QPushButton[role="notebook_action"] {{
    background-color: transparent;
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="notebook_action"]:hover {{
    background-color: {css('surface_soft', m)};
}}
QPushButton[role="notebook_action"]:disabled {{
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}
QPushButton[role="notebook_destructive_action"] {{
    background-color: transparent;
    color: {css('danger', m)};
    border: {BORDER_WIDTH}px solid {css('danger', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="notebook_destructive_action"]:hover {{
    background-color: {css('danger', m)};
    color: #FFFFFF;
}}
QPushButton[role="notebook_destructive_action"]:disabled {{
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}

/* Surfaces & Containers */
QFrame[role="card"] {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}

/* Paper Surface */
QMainWindow[surface="paper"],
QWidget[surface="paper"],
QScrollArea[surface="paper"],
QScrollArea[surface="paper"] > QWidget > QWidget {{
    background-color: {css('surface_paper', m)};
    color: {css('ink', m)};
}}
QFrame[surface="paper"] {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}

/* Cinema / Dark Focus Surface */
QMainWindow[surface="cinema"],
QWidget[surface="cinema"],
QScrollArea[surface="cinema"],
QScrollArea[surface="cinema"] > QWidget > QWidget {{
    background-color: {css('surface_cinema', m)};
    color: #EDEDEC;
}}
QFrame[surface="cinema"] {{
    background-color: #181B22;
    color: #EDEDEC;
    border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.12);
    border-radius: {RADIUS_CARD}px;
}}
QWidget[surface="cinema"] QLabel {{
    color: #EDEDEC;
}}
QWidget[surface="cinema"] QLabel[role="caption"] {{
    color: #9CA3AF;
}}
QWidget[surface="cinema"] QLabel[role="subtitle"] {{
    color: #9CA3AF;
}}
QWidget[surface="cinema"] QCheckBox {{
    color: #EDEDEC;
}}
QWidget[surface="cinema"] QLineEdit,
QWidget[surface="cinema"] QTextEdit,
QWidget[surface="cinema"] QPlainTextEdit {{
    background-color: #12151B;
    color: #EDEDEC;
    border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.18);
    border-radius: {RADIUS_CONTROL}px;
}}

QListWidget[role="cinema_cue_list"] {{
    background-color: #12151B;
    color: #EDEDEC;
    border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.12);
    border-radius: {RADIUS_CARD}px;
    padding: {SPACE_COMPACT}px;
}}
QListWidget[role="cinema_cue_list"]::item {{
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: {RADIUS_CONTROL}px;
    margin-bottom: 2px;
    color: #D1D5DB;
}}
QListWidget[role="cinema_cue_list"]::item:hover {{
    background-color: rgba(255, 255, 255, 0.05);
}}
QListWidget[role="cinema_cue_list"]::item:selected {{
    background-color: rgba(59, 130, 246, 0.25);
    color: #FFFFFF;
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}
QMainWindow[surface="workspace"],
QWidget[surface="workspace"],
QScrollArea[surface="workspace"],
QScrollArea[surface="workspace"] > QWidget > QWidget,
QFrame[surface="workspace"] {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
}}

/* Buttons: Primary / Secondary / Quiet / Danger / Success */
QPushButton[role="primary"] {{
    background-color: {css('accent', m)};
    color: #FFFFFF;
    font-weight: 600;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
}}
QPushButton[role="primary"]:hover {{ background-color: {css('accent_hover', m)}; }}
QPushButton[role="primary"]:pressed {{ background-color: {css('accent_pressed', m)}; }}
QPushButton[role="primary"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
}}

QPushButton[role="secondary"] {{
    background-color: {css('surface', m)};
    color: {css('ink', m)};
    font-weight: 500;
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL + 2}px;
}}
QPushButton[role="secondary"]:hover {{ background-color: {css('surface_soft', m)}; }}
QPushButton[role="secondary"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}

QPushButton[role="quiet"] {{
    background-color: transparent;
    color: {css('muted', m)};
    border: none;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="quiet"]:hover {{ color: {css('ink', m)}; }}
QPushButton[role="quiet"]:disabled {{ color: {css('disabled_text', m)}; }}

QPushButton[role="danger"] {{
    background-color: {css('surface', m)};
    color: {css('danger', m)};
    border: {BORDER_WIDTH}px solid {css('danger', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="danger"]:hover {{ background-color: {css('danger', m)}; color: #FFFFFF; }}
QPushButton[role="danger"]:pressed {{ background-color: {css('danger_hover', m)}; color: #FFFFFF; }}
QPushButton[role="danger"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}

QPushButton[role="success"] {{
    background-color: {css('success', m)};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="success"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
}}

QPushButton:focus {{
    border: {BORDER_WIDTH}px solid {css('focus', m)};
}}

/* RadioButton */
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 8px;
    border: {BORDER_WIDTH}px solid {css('line', m)};
    background-color: {css('surface', m)};
}}
QRadioButton::indicator:hover {{ border-color: {css('muted', m)}; }}
QRadioButton::indicator:checked {{
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    background-color: {css('accent', m)};
}}
QRadioButton::indicator:focus {{
    border: {BORDER_WIDTH}px solid {css('focus', m)};
}}

/* TabWidget */
QTabWidget::pane {{ border: {BORDER_WIDTH}px solid {css('line', m)}; }}
QTabBar::tab {{
    background: {css('surface_soft', m)};
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-bottom: none;
    border-top-left-radius: {RADIUS_CONTROL}px;
    border-top-right-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT + 2}px {SPACE_NORMAL + 2}px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {css('surface', m)};
    color: {css('accent', m)};
    font-weight: bold;
}}
QTabBar::tab:!selected:hover {{
    background: {css('surface', m)};
    color: {css('ink', m)};
}}
"""


def build_stylesheet(theme_mode: str = "light") -> str:
    """Assemble the app-wide QSS for the given theme mode."""
    return _build_base_qss(theme_mode) + _build_component_qss(theme_mode)


def apply_theme(app: QApplication, theme_mode: str = "light") -> None:
    """Apply ListenTrace's theme to the whole application."""
    app.setStyleSheet(build_stylesheet(theme_mode))


_ICON_FILENAME = "listentrace.ico"


def _icon_search_paths() -> list[Path]:
    """Candidate paths for the app icon, covering every runtime context."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / _ICON_FILENAME)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / _ICON_FILENAME)
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "packaging" / "assets" / _ICON_FILENAME)
    return candidates


def get_app_icon() -> QIcon:
    """Return ListenTrace's app icon, or a null `QIcon` if not found."""
    for path in _icon_search_paths():
        if path.is_file():
            return QIcon(str(path))
    return QIcon()

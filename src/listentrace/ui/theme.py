"""Central design tokens and QSS theme for ListenTrace's presentation layer.

Milestone 13 (Advanced UI/UX Reconstruction) Theme System:
- Professional Blue primary accent (#2563EB / #3B82F6 family)
- Warm Professional Learning Desk personality
- Lined Spiral Notebook & Ruled Study Paper contextual surfaces
- Spacious Learning density (4 / 8 / 16 / 24 / 32 px scale)
- Contextual Surface Modes (Workspace, Paper Study, Ruled Notebook, Dark Focus)
- Full Light and Dark theme support
- Two-layer QSS model (Base Layer + Opt-in Component/Surface Layer)

Product-semantic tokens (cue_active, text_overlap, quiz_correct, quiz_incorrect,
chart palette) preserve semantic meaning and are distinct from brand tokens.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# Tokens: Light & Dark Palettes
# ---------------------------------------------------------------------------

_TOKENS_LIGHT: dict[str, tuple[int, int, int, int]] = {
    # Brand: Warm Professional Learning Desk + Professional Blue Accent
    "page": (246, 244, 238, 255),          # #F6F4EE warm desk page
    "surface": (255, 255, 255, 255),       # #FFFFFF pure white card
    "surface_soft": (250, 247, 240, 255),  # #FAF7F0 soft panel
    "surface_sidebar": (240, 236, 227, 255), # #F0ECE3 directory sidebar
    "surface_paper": (253, 251, 247, 255), # #FDFBF7 matte ruled paper
    "surface_cinema": (15, 17, 21, 255),   # #0F1115 dark listening stage
    "ink": (31, 29, 26, 255),              # #1F1D1A dark ink
    "muted": (140, 132, 119, 255),         # #8C8477 muted text
    "line": (60, 50, 40, 36),              # subtle border ~14% alpha
    "line_ruled": (60, 50, 40, 25),        # subtle ruled horizontal line ~10% alpha
    "accent": (37, 99, 235, 255),          # #2563EB Professional Blue
    "accent_hover": (29, 78, 216, 255),    # #1D4ED8
    "accent_pressed": (30, 64, 175, 255),  # #1E40AF
    "accent_subtle": (239, 246, 255, 255), # #EFF6FF
    "secondary": (90, 84, 74, 255),        # #5A544A
    # Semantic
    "success": (22, 163, 74, 255),         # #16A34A
    "danger": (217, 56, 58, 255),          # #D9383A
    "danger_hover": (191, 38, 40, 255),    # #BF2628
    "danger_subtle": (253, 242, 242, 255), # #FDF2F2
    "warning": (217, 119, 6, 255),         # #D97706
    "warning_subtle": (254, 243, 199, 255),# #FEF3C7
    "info": (37, 99, 235, 255),            # #2563EB
    "focus": (37, 99, 235, 255),           # #2563EB
    "disabled_text": (140, 132, 122, 255),
    "disabled_surface": (232, 226, 216, 255),
    # Dedicated Product-Semantic Tokens
    "cue_active": (255, 243, 205, 255),    # #FFF3CD active cue highlight
    "text_overlap": (208, 208, 208, 255),  # #D0D0D0
    "quiz_correct": (22, 163, 74, 255),    # #16A34A
    "quiz_incorrect": (220, 38, 38, 255),  # #DC2626
    "chart_background": (255, 255, 255, 255),
    "chart_bar": (37, 99, 235, 255),       # #2563EB aligned with Professional Blue
    "chart_axis": (156, 163, 175, 255),    # #9CA3AF
    "chart_text": (55, 65, 81, 255),       # #374151
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

FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif'


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


def make_notebook_surface(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A lined spiral notebook study surface with wire-binding cues and ruled paper styling."""
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
    spiral_layout.addWidget(spiral_cue)
    spiral_layout.addStretch(1)

    doodle_stamp = QLabel("📝 Study Dossier")
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
QLabel[role="monospace"] {{ font-family: monospace; }}

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
    border-color: {css('line', m)};
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
    border-color: {css('line', m)};
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

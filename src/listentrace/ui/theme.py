"""Central design tokens and QSS theme for ListenTrace's presentation layer.

Milestone 11 (UI/UX Presentation Refresh), light mode only. Two-layer model:

- the global **base** layer (see `_BASE_QSS`) is safe to apply to every
  window immediately -- font, page background, tooltip, selection/focus
  baseline, conservative disabled-state styling -- and must not make an
  unmigrated window look broken or become unusable;
- the opt-in **component** layer (see `_COMPONENT_QSS`) is entirely
  attribute-selector based (``QPushButton[role="primary"]`` etc.) and only
  ever affects a widget that has been explicitly tagged via `apply_role` --
  a window is not "migrated" merely because it inherits the base layer.

Every color is defined once, in `_TOKENS`, and exposed both as a QSS string
(`css`) and as a real `QColor` (`qcolor`) so no hex literal is duplicated
between this stylesheet builder and custom-painted widgets such as
`SimpleBarChart`. Product-semantic tokens (`cue_active`, `text_overlap`,
`quiz_correct`, `quiz_incorrect`, the chart tokens) preserve the exact
values of the pre-Milestone-11 hardcoded literals they replace -- their
*meaning* (highlight, correctness, chart palette) is deliberately kept
separate from brand tokens, never collapsed into a generic accent color.

User-owned annotation-label colors (`label_color_dialog.py`) are learner
data, not app chrome, and are never read from or written through this
module.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QListWidget, QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_TOKENS: dict[str, tuple[int, int, int, int]] = {
    # Brand (adapted from the Daily Canvas light theme, per ROADMAP.md's
    # Milestone 11 reference)
    "page": (243, 239, 232, 255),
    "surface": (255, 253, 249, 255),
    "surface_soft": (248, 243, 235, 255),
    "ink": (41, 38, 34, 255),
    "muted": (119, 112, 102, 255),
    "line": (74, 64, 52, 70),
    "accent": (232, 121, 79, 255),
    "accent_hover": (219, 107, 65, 255),
    "accent_pressed": (201, 85, 51, 255),
    "secondary": (42, 157, 143, 255),
    # Semantic -- kept namespace-separate from brand identity even where a
    # value is initially shared with a brand token.
    "success": (42, 157, 143, 255),
    "danger": (215, 91, 86, 255),
    "danger_hover": (196, 74, 69, 255),
    "warning": (230, 162, 59, 255),
    "info": (69, 123, 157, 255),
    "focus": (232, 121, 79, 255),
    "disabled_text": (140, 132, 122, 255),
    "disabled_surface": (232, 226, 216, 255),
    # Dedicated product-semantic tokens -- never collapsed into a generic
    # accent token. Values preserved from the pre-M11 hardcoded literals
    # they replace.
    "cue_active": (255, 243, 205, 255),  # was player_window._ACTIVE_CUE_HIGHLIGHT
    "text_overlap": (208, 208, 208, 255),  # was player_window._OVERLAP_HIGHLIGHT
    "quiz_correct": (22, 163, 74, 255),  # was quiz_review_dialog._CORRECT_COLOR
    "quiz_incorrect": (220, 38, 38, 255),  # was quiz_review_dialog._INCORRECT_COLOR
    "chart_background": (255, 253, 249, 255),  # was Qt.GlobalColor.white
    "chart_bar": (42, 157, 143, 255),  # calmer teal (matches `secondary`) -- was simple_bar_chart._BAR_COLOR's royal blue (#2563EB)
    "chart_axis": (156, 163, 175, 255),  # was simple_bar_chart._AXIS_COLOR
    "chart_text": (55, 65, 81, 255),  # was simple_bar_chart._TEXT_COLOR
}

# Spacing scale (px): compact / normal / section / page.
SPACE_COMPACT = 4
SPACE_NORMAL = 8
SPACE_SECTION = 16
SPACE_PAGE = 24

# Shape scale (px).
RADIUS_CONTROL = 6
RADIUS_CARD = 12
BORDER_WIDTH = 1

# Safe system fonts only -- no new font dependency.
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif'


def qcolor(token: str) -> QColor:
    """Return a real `QColor` for a token, for QPainter code (e.g. `SimpleBarChart`)."""
    r, g, b, a = _TOKENS[token]
    return QColor(r, g, b, a)


def css(token: str) -> str:
    """Return a QSS-compatible color string for a token."""
    r, g, b, a = _TOKENS[token]
    if a == 255:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"rgba({r}, {g}, {b}, {a / 255:.3f})"


def make_card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A light `QFrame[role="card"]` surface with its own padded layout.

    Shared by any window that wants to group related content as a visually
    distinct surface (e.g. separating a list from a detail panel, or giving
    a workspace sub-panel its own bordered/rounded/padded frame) -- one
    definition, reused rather than re-implemented per window.
    """
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


def configure_long_text_list(list_widget: QListWidget) -> None:
    """Wrap long row text instead of growing an unnecessary horizontal
    scrollbar -- the fix established in PlayerWindow's cue list (Batch 0),
    GuidedSessionWindow's diagnosis cue list (Batch 1), and QuizReviewDialog's
    question list (Batch 2), promoted here to a shared helper since Batch 3
    applies it across many list widgets in one window.
    """
    list_widget.setWordWrap(True)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


def apply_role(widget: QWidget, role: str) -> None:
    """Tag `widget` with a presentation role consumed by the component-layer QSS.

    Sets a Qt dynamic property only -- does not change alignment, word-wrap,
    size policy, or interaction behavior, and never touches the widget's
    object name or any test-facing attribute.
    """
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


_BASE_QSS = f"""
QWidget {{
    background-color: {css('page')};
    color: {css('ink')};
    font-family: {FONT_FAMILY};
    font-size: 10pt;
}}
QToolTip {{
    background-color: {css('surface')};
    color: {css('ink')};
    border: {BORDER_WIDTH}px solid {css('line')};
    padding: {SPACE_COMPACT}px;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {{
    selection-background-color: {css('accent')};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus {{
    border: {BORDER_WIDTH}px solid {css('focus')};
}}
*:disabled {{
    color: {css('disabled_text')};
}}

/* A plain label should let its container's surface show through (a card,
   the page, etc.) rather than always painting its own page-colored patch
   -- role-specific label rules (below) are attribute-selectors and take
   precedence over this bare-type rule regardless of source order. */
QLabel {{
    background-color: transparent;
}}

/* Fields must look like fields, not disconnected horizontal lines --
   a real box with a visible border and a surface background. List/table
   widgets get the same surface treatment so they read as part of the same
   card rather than a mismatched page-colored patch inside a white card. */
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget {{
    background-color: {css('surface')};
    border: {BORDER_WIDTH}px solid {css('line')};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_COMPACT + 2}px;
}}

/* The current-but-unfocused selected row must stay clearly visible --
   Qt's native "inactive selection" palette otherwise barely shows. */
QListWidget::item:selected, QListWidget::item:selected:active {{
    background-color: {css('accent')};
    color: #FFFFFF;
}}
QListWidget::item:selected:!active {{
    background-color: {css('accent_hover')};
    color: #FFFFFF;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {css('line')};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {css('accent')};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {css('accent')};
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {css('accent_hover')}; }}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
}}
QScrollBar::handle {{
    background: {css('line')};
    border-radius: 4px;
}}
QScrollBar::handle:hover {{ background: {css('muted')}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    border: none;
    background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}
"""

_COMPONENT_QSS = f"""
QLabel[role="page_title"] {{ font-size: 20px; font-weight: bold; }}
QLabel[role="title"] {{ font-size: 16px; font-weight: bold; }}
QLabel[role="caption"] {{ font-size: 11px; color: {css('muted')}; }}
QLabel[role="muted"] {{ color: {css('muted')}; }}
QLabel[role="error"] {{ color: {css('danger')}; }}
QLabel[role="warning"] {{ color: {css('warning')}; }}
QLabel[role="success"] {{ color: {css('success')}; }}
QLabel[role="monospace"] {{ font-family: monospace; }}
QLabel[role="media_placeholder"] {{
    background-color: {css('ink')};
    color: #FFFFFF;
    font-size: 14px;
}}

QFrame[role="card"] {{
    background-color: {css('surface')};
    border: {BORDER_WIDTH}px solid {css('line')};
    border-radius: {RADIUS_CARD}px;
}}

/* Batch 4 correction: the native radio indicator rendered its checked dot
   almost invisibly against this warm palette, while the unchecked ring
   stayed visible -- which mode was selected could only be inferred from
   which panel/list was enabled, not from the control itself. Every state
   gets an explicit, centralized definition here. */
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 8px;
    border: {BORDER_WIDTH}px solid {css('line')};
    background-color: {css('surface')};
}}
QRadioButton::indicator:hover {{
    border-color: {css('muted')};
}}
QRadioButton::indicator:checked {{
    border: {BORDER_WIDTH}px solid {css('accent')};
    background-color: qradialgradient(
        cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {css('accent')}, stop:0.45 {css('accent')}, stop:0.5 {css('surface')}, stop:1 {css('surface')}
    );
}}
QRadioButton::indicator:checked:hover {{
    border-color: {css('accent_hover')};
}}
QRadioButton::indicator:unchecked:disabled {{
    border-color: {css('line')};
    background-color: {css('disabled_surface')};
}}
QRadioButton::indicator:checked:disabled {{
    border: {BORDER_WIDTH}px solid {css('disabled_text')};
    background-color: qradialgradient(
        cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {css('disabled_text')}, stop:0.45 {css('disabled_text')}, stop:0.5 {css('disabled_surface')}, stop:1 {css('disabled_surface')}
    );
}}
QRadioButton::indicator:focus {{
    border: {BORDER_WIDTH}px solid {css('focus')};
}}

QPushButton[role="primary"] {{
    background-color: {css('accent')};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="primary"]:hover {{ background-color: {css('accent_hover')}; }}
QPushButton[role="primary"]:pressed {{ background-color: {css('accent_pressed')}; }}
QPushButton[role="primary"]:disabled {{
    background-color: {css('disabled_surface')};
    color: {css('disabled_text')};
}}

QPushButton[role="secondary"] {{
    background-color: {css('surface')};
    color: {css('ink')};
    border: {BORDER_WIDTH}px solid {css('line')};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="secondary"]:hover {{ background-color: {css('surface_soft')}; }}
QPushButton[role="secondary"]:disabled {{
    background-color: {css('disabled_surface')};
    color: {css('disabled_text')};
    border-color: {css('line')};
}}

QPushButton[role="quiet"] {{
    background-color: transparent;
    color: {css('muted')};
    border: none;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="quiet"]:hover {{ color: {css('ink')}; }}
QPushButton[role="quiet"]:disabled {{ color: {css('disabled_text')}; }}

/* Destructive actions stay clearly legible (outlined, not a solid block)
   so they never visually overpower an adjacent Save/Update action -- the
   solid fill only appears on hover/press, right when actually interacting. */
QPushButton[role="danger"] {{
    background-color: {css('surface')};
    color: {css('danger')};
    border: {BORDER_WIDTH}px solid {css('danger')};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="danger"]:hover {{ background-color: {css('danger')}; color: #FFFFFF; }}
QPushButton[role="danger"]:pressed {{ background-color: {css('danger_hover')}; color: #FFFFFF; }}
QPushButton[role="danger"]:disabled {{
    background-color: {css('disabled_surface')};
    color: {css('disabled_text')};
    border-color: {css('line')};
}}

QPushButton[role="success"] {{
    background-color: {css('success')};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="success"]:disabled {{
    background-color: {css('disabled_surface')};
    color: {css('disabled_text')};
}}

/* Milestone 11 Closeout: a visible keyboard-focus ring for every themed
   button role -- source order lets this win the border color specifically
   for the focused state, while each role's own background/color/padding
   are untouched. */
QPushButton:focus {{
    border: {BORDER_WIDTH}px solid {css('focus')};
}}

QTabWidget::pane {{ border: {BORDER_WIDTH}px solid {css('line')}; }}

/* Milestone 11 (Batch 3 correction): the native tab-bar style painted
   enabled-but-unselected tabs almost white on this warm page background --
   nearly unreadable and hard to discover. Every state gets an explicit,
   centralized definition here rather than per-window styling. */
QTabBar::tab {{
    background: {css('surface_soft')};
    color: {css('ink')};
    border: {BORDER_WIDTH}px solid {css('line')};
    border-bottom: none;
    border-top-left-radius: {RADIUS_CONTROL}px;
    border-top-right-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
    margin-right: {SPACE_COMPACT}px;
}}
QTabBar::tab:selected {{
    background: {css('surface')};
    color: {css('accent_pressed')};
    font-weight: bold;
}}
QTabBar::tab:!selected:hover {{
    background: {css('surface')};
    color: {css('ink')};
}}
QTabBar::tab:disabled {{
    background: {css('disabled_surface')};
    color: {css('disabled_text')};
    border-color: {css('line')};
}}
QTabBar::tab:focus {{
    border: {BORDER_WIDTH}px solid {css('focus')};
}}
"""


def build_stylesheet() -> str:
    """Assemble the app-wide QSS: the global base layer plus the opt-in component layer."""
    return _BASE_QSS + _COMPONENT_QSS


def apply_theme(app: QApplication) -> None:
    """Apply ListenTrace's Milestone 11 light theme to the whole application."""
    app.setStyleSheet(build_stylesheet())


_ICON_FILENAME = "listentrace.ico"


def _icon_search_paths() -> list[Path]:
    """Candidate paths for the app icon, covering every runtime context.

    Order matters: frozen-build locations are checked first (cheap, exact),
    falling back to the dev-from-source repo path last.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        # PyInstaller onedir build: listentrace.spec's `datas` copies the
        # icon into the onedir root, alongside the executable.
        candidates.append(Path(sys.executable).resolve().parent / _ICON_FILENAME)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / _ICON_FILENAME)
    # Development from source: repo_root/packaging/assets/listentrace.ico
    # (theme.py is at src/listentrace/ui/theme.py -- parents[3] is the repo root).
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "packaging" / "assets" / _ICON_FILENAME)
    return candidates


def get_app_icon() -> QIcon:
    """Return ListenTrace's app icon, or a null `QIcon` if it cannot be found.

    Never raises -- a missing icon asset must not block startup.
    """
    for path in _icon_search_paths():
        if path.is_file():
            return QIcon(str(path))
    return QIcon()

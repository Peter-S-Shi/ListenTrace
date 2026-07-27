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

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QWidget

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
    "line": (74, 64, 52, 31),
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
    "disabled_text": (168, 160, 150, 255),
    "disabled_surface": (238, 233, 224, 255),
    # Dedicated product-semantic tokens -- never collapsed into a generic
    # accent token. Values preserved from the pre-M11 hardcoded literals
    # they replace.
    "cue_active": (255, 243, 205, 255),  # was player_window._ACTIVE_CUE_HIGHLIGHT
    "text_overlap": (208, 208, 208, 255),  # was player_window._OVERLAP_HIGHLIGHT
    "quiz_correct": (22, 163, 74, 255),  # was quiz_review_dialog._CORRECT_COLOR
    "quiz_incorrect": (220, 38, 38, 255),  # was quiz_review_dialog._INCORRECT_COLOR
    "chart_background": (255, 253, 249, 255),  # was Qt.GlobalColor.white
    "chart_bar": (37, 99, 235, 255),  # was simple_bar_chart._BAR_COLOR
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

QPushButton[role="danger"] {{
    background-color: {css('danger')};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}
QPushButton[role="danger"]:hover {{ background-color: {css('danger_hover')}; }}
QPushButton[role="danger"]:disabled {{
    background-color: {css('disabled_surface')};
    color: {css('disabled_text')};
}}

QPushButton[role="success"] {{
    background-color: {css('success')};
    color: #FFFFFF;
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px {SPACE_NORMAL}px;
}}

QTabWidget::pane {{ border: {BORDER_WIDTH}px solid {css('line')}; }}
QTabBar::tab:selected {{ color: {css('accent_pressed')}; font-weight: bold; }}
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

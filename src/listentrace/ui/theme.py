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
from typing import NamedTuple

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from listentrace.ui.widgets.notebook_paper import (
    GrainedPaperFrame,
    LayeredPaperFrame,
    RuledPaperFrame,
    SketchFlourishWidget,
    SpiralBindingWidget,
    paint_ink_outline,
)

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
    "cinema_ink": (237, 237, 236, 255),     # #EDEDEC -- fixed regardless of app light/dark mode
    "cinema_card_bg": (24, 27, 34, 255),    # #181B22
    "cinema_muted": (156, 163, 175, 255),   # #9CA3AF
    "cinema_input_bg": (18, 21, 22, 255),   # #12151B
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
    "stepper_future_badge": (227, 221, 212, 255),  # #E3DDD4 -- DESIGN.md §8.6 future-stage badge fill
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
    # M13 Stage B whole-product reconciliation (DESIGN.md §7/§8) -- exact
    # per-role button/input/list/scrollbar values not covered by the more
    # general palette above.
    "ink_button_secondary": (42, 39, 35, 255),   # #2A2723 -- secondary button text (DESIGN.md §7.3)
    "quiet_hover": (243, 238, 230, 255),         # #F3EEE6 -- quiet button hover bg (§7.4)
    "quiet_pressed": (234, 227, 216, 255),       # #EAE3D8 -- quiet button pressed bg (§7.4)
    "danger_pressed": (251, 232, 232, 255),      # #FBE8E8 -- danger button pressed bg (§7.5)
    "danger_focus_ring": (239, 154, 155, 255),   # #EF9A9B -- danger's own focus ring (§7.5)
    "input_hover_border": (183, 170, 152, 255),  # #B7AA98 -- LineEdit/ComboBox hover border (§8.1)
    "input_readonly_bg": (244, 239, 231, 255),   # #F4EFE7 -- read-only input bg (§8.1)
    "list_hover": (247, 244, 237, 255),          # #F7F4ED -- ruled-list row hover (§8.3)
    "list_divider": (191, 219, 254, 89),         # #BFDBFE @ 35% -- ruled-list row divider (§8.3)
    "scrollbar_thumb": (185, 176, 164, 255),     # #B9B0A4 (§8.4)
    "scrollbar_thumb_hover": (145, 135, 123, 255), # #91877B (§8.4)
    "scrollbar_track": (243, 238, 230, 255),     # #F3EEE6 (§8.4)
}

_TOKENS_DARK: dict[str, tuple[int, int, int, int]] = {
    # Brand: Deep Slate + Bright Professional Blue Accent
    "page": (18, 20, 24, 255),             # #121418
    "surface": (30, 34, 42, 255),          # #1E222A
    "surface_soft": (25, 29, 36, 255),     # #191D24
    "surface_sidebar": (23, 26, 32, 255),  # #171A20
    "surface_paper": (27, 30, 37, 255),    # #1B1E25
    "surface_cinema": (10, 12, 14, 255),   # #0A0C0E
    "cinema_ink": (237, 237, 236, 255),    # #EDEDEC -- fixed regardless of app light/dark mode
    "cinema_card_bg": (24, 27, 34, 255),   # #181B22
    "cinema_muted": (156, 163, 175, 255),  # #9CA3AF
    "cinema_input_bg": (18, 21, 22, 255),  # #12151B
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

SPACE_COMPACT = 4   # DESIGN.md §5.1 SPACE_XXS
SPACE_TIGHT = 6      # SPACE_XS
SPACE_NORMAL = 8     # SPACE_S
SPACE_MEDIUM = 12    # SPACE_M
SPACE_SECTION = 16   # SPACE_L
SPACE_PAGE = 24      # SPACE_XL
SPACE_LARGE = 32     # SPACE_XXL

RADIUS_CONTROL = 6
RADIUS_CARD = 10
RADIUS_PILL = 9999
RADIUS_STATE_CARD = 8  # shared by stepper_item/quiz_option (M13 Stage B, G15)

# M13 Due-Frame-First Visual Polish, Axis 1: a small, fixed per-corner
# variance on cards/media frames/ordinary buttons -- a "hand-set" rectangle
# instead of a mathematically uniform machine one, matching the due-frame
# boards' controlled irregularity. Deliberately NOT applied to pills, list
# rows, inputs, or state-card badges, whose symmetric shape is functional
# (a pill/pill-badge that isn't symmetric doesn't read as a pill).
RADIUS_CARD_TL = RADIUS_CARD
RADIUS_CARD_TR = RADIUS_CARD - 3
RADIUS_CARD_BR = RADIUS_CARD + 2
RADIUS_CARD_BL = RADIUS_CARD - 1
RADIUS_BUTTON_TL = RADIUS_CONTROL
RADIUS_BUTTON_TR = RADIUS_CONTROL - 2
RADIUS_BUTTON_BR = RADIUS_CONTROL + 3
RADIUS_BUTTON_BL = RADIUS_CONTROL - 1
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
# M13 Due-Frame Polish, Axis 2: the due-frame boards' titles, subtitles,
# section headers, and metric values consistently share one rounded
# geometric-sans letterform (single-story lowercase "a", circular "o"/"g"/
# "d") -- visibly not `FONT_FAMILY`'s corporate Segoe UI character. "Century
# Gothic" (bundled with Windows, confirmed present via QFontDatabase on this
# machine) is the closest safe local match. Latin-only, same CJK-fallback
# rule as `HANDWRITING_FONT_FAMILY` above -- never forced onto CJK glyphs,
# and never used for body/reading text (DESIGN.md's readability boundary is
# unchanged; only the *display* tier's face changed).
TITLE_FONT_FAMILY = (
    '"Century Gothic", "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", '
    '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'
)


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


# M13 Due-Frame Polish, Axis 1 continuation: the roles whose ordinary
# (non-hero) rendering gets a painted ink-outline edge instead of a flat
# QSS 1px border -- the due-frame boards' clearest remaining "still looks
# like Qt" signal was button/frame line character, not radius alone.
# "quiet" is deliberately excluded: it is a borderless/flat action by
# product design (DESIGN.md's action grammar), and an ink outline would
# contradict that semantic, not reinforce it.
_INK_OUTLINE_BUTTON_ROLES = {"primary", "secondary", "danger", "success"}
_INK_OUTLINE_BUTTON_TOKENS = {
    # "primary" is only ever painted for its non-hero (outline) variant --
    # see the hero skip below -- so this is the same accent-blue its own
    # QSS border already uses, not the old filled-button's darker
    # accent_pressed accent.
    "primary": "accent",
    "secondary": "handwritten_blue",
    "danger": "danger_hover",
    "success": "success",
}


def _install_ink_outline_button_paint(widget: QPushButton, role: str) -> None:
    """Monkeypatch one `QPushButton` instance's `paintEvent` to run Qt's own
    QSS-driven paint first (fill/text/hover/pressed/disabled all unchanged),
    then overlay a deterministic sketchy ink-outline edge -- one shared
    primitive installed from the single `apply_role()` chokepoint every
    button already goes through, not a per-window custom widget. Guarded so
    a widget already carrying the override is never double-patched (this
    function can run more than once on the same widget across a role
    change or a later `apply_role()` re-call)."""
    if widget.property("_ink_outline_installed"):
        return
    widget.setProperty("_ink_outline_installed", True)
    base_paint_event = QPushButton.paintEvent

    def _paint_event(self: QPushButton, event) -> None:  # noqa: ANN001
        base_paint_event(self, event)
        if not self.isEnabled():
            return
        current_role = self.property("role")
        if current_role not in _INK_OUTLINE_BUTTON_TOKENS:
            return
        # A `hero="true"` primary button is the one genuinely solid-filled
        # tier the due frame evidences (Open Player, Submit Quiz, Start
        # Recording, ...) -- those boards show it as a clean filled
        # rectangle with no separate sketchy outline layered on top, so
        # the ink outline is scoped to the non-filled roles only.
        if current_role == "primary" and self.property("hero") == "true":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_ink_outline(
            painter,
            self.width(),
            self.height(),
            qcolor(_INK_OUTLINE_BUTTON_TOKENS[current_role]),
            radius=float(RADIUS_CONTROL) + 1.0,
        )
        painter.end()

    import types

    widget.paintEvent = types.MethodType(_paint_event, widget)


def apply_role(widget: QWidget, role: str) -> None:
    """Tag `widget` with a presentation role consumed by the component-layer QSS."""
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    if isinstance(widget, QPushButton) and role in _INK_OUTLINE_BUTTON_ROLES:
        _install_ink_outline_button_paint(widget, role)


def apply_surface(widget: QWidget, surface: str) -> None:
    """Tag `widget` with a surface family (workspace / paper / cinema / elevated)."""
    widget.setProperty("surface", surface)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def apply_variant(widget: QWidget, **properties: str) -> None:
    """Set one or more state-variant properties (e.g. `state="completed"`,
    `selected="true"`) consumed by `role="..."[prop="value"]` QSS selectors,
    and re-polish so a later change to an already-visible widget actually
    re-renders (M13 Stage B, G15's shared stepper_item/quiz_option
    vocabulary; the same "tag a property, then unpolish/polish" mechanism
    `apply_role`/`apply_surface` use, generalized to arbitrary properties
    that change repeatedly on one widget rather than being set once)."""
    for name, value in properties.items():
        widget.setProperty(name, value)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


_STATUS_DOT_DIAMETER_PX = 10
_STATUS_DOT_TOKENS = {
    "active": "accent",
    "completed": "success",
    "abandoned": "warning",
}


def _status_dot_pixmap(status: str) -> QPixmap:
    """An exact `_STATUS_DOT_DIAMETER_PX`-square pixmap (no antialiasing
    margin) so the dot's rendered size and a caller's layout spacing are
    the only two numbers involved in placing it next to text -- no hidden
    padding baked into the image that would throw off an exact gap."""
    token = _STATUS_DOT_TOKENS.get(status, "neutral_state")
    pixmap = QPixmap(_STATUS_DOT_DIAMETER_PX, _STATUS_DOT_DIAMETER_PX)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(qcolor(token))
    painter.drawEllipse(0, 0, _STATUS_DOT_DIAMETER_PX, _STATUS_DOT_DIAMETER_PX)
    painter.end()
    return pixmap


def status_dot_icon(status: str) -> QIcon:
    """A 10px filled-circle `QIcon` in the frozen status-marker color for
    `status` ("active"/"completed"/"abandoned") -- DESIGN.md §3.6,
    M13_RENDERING_IMPLEMENTATION_MAP.md `status_dot`. Always set alongside
    the existing textual status label, never as a replacement for it --
    color alone must never carry the state.

    Prefer `make_status_row()` over `QListWidgetItem.setIcon()` with this
    icon directly: `setIcon()` leaves the icon-to-text gap to Qt's
    unspecified native list-item style metrics, which cannot guarantee the
    frozen 6px gap.
    """
    return QIcon(_status_dot_pixmap(status))


def make_status_row(text: str, status: str) -> QWidget:
    """A `status_dot` + status text row with the frozen 6px icon-to-text
    gap enforced via real layout spacing -- not `QListWidgetItem.setIcon()`,
    whose icon-to-text gap is an unspecified native list-item style metric
    that cannot guarantee an exact value.

    Usage: `item = QListWidgetItem(); row = make_status_row(text, status);
    item.setSizeHint(ruled_list_row_size_hint(row)); list_widget.addItem(item);
    list_widget.setItemWidget(item, row)`. Use `ruled_list_row_size_hint()`,
    not `row.sizeHint()` directly -- see that function for why.
    """
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(ICON_TEXT_GAP_PX)

    dot = QLabel()
    dot.setPixmap(_status_dot_pixmap(status))
    dot.setFixedSize(_STATUS_DOT_DIAMETER_PX, _STATUS_DOT_DIAMETER_PX)
    row_layout.addWidget(dot)

    label = QLabel(text)
    row_layout.addWidget(label, 1)
    return row


# Must mirror the vertical chrome the `QListWidget[role="ruled_list"]::item`
# QSS rule paints around every row: padding-top + padding-bottom
# (SPACE_NORMAL each) + border-bottom (1px) + margin-bottom (2px). Qt paints
# this chrome ON TOP OF an item's set size, not carved out of it -- the same
# box-model rule that governs widget min-height applies to
# QListWidgetItem.setSizeHint() too. Single source of truth for both sides
# so the QSS rule and this constant cannot silently drift apart.
RULED_LIST_ITEM_VERTICAL_CHROME_PX = (SPACE_NORMAL * 2) + BORDER_WIDTH + 2


def ruled_list_row_size_hint(row_widget: QWidget) -> QSize:
    """The `QSize` a `QListWidgetItem` hosting `row_widget` via
    `QListWidget.setItemWidget()` inside a `role="ruled_list"` list must be
    given via `item.setSizeHint(...)`.

    `row_widget.sizeHint()` alone is not enough: the `ruled_list` item QSS
    (padding/border/margin) is rendered on top of whatever height the item
    cell is given, so using the bare row height starves the row widget's own
    content of the space that QSS chrome needs, collapsing it toward zero
    height -- the row widget and its `status_dot` become invisible, and the
    QSS border/margin lines end up drawn through the item's own native text
    instead of below it.
    """
    hint = row_widget.sizeHint()
    return QSize(hint.width(), hint.height() + RULED_LIST_ITEM_VERTICAL_CHROME_PX)


def apply_paper_shadow(widget: QWidget, tier: str = "full") -> None:
    """Attach the frozen paper-shadow treatment (M13 Stage B; DESIGN.md §6,
    Gap Register G10) to `widget`. Three tiers:

    - "full": an independent page-level dossier/paper sheet layered against
      the desk -- #5B4935 @ 14%, offset (0, 3), blur 10.
    - "mini": a mini-notebook module -- #5B4935 @ 10%, offset (0, 2), blur 6.
    - "chip": a small paper-slip note object (M13 Axis 4, `DiagnosisNoteRow`)
      -- barely-lifted, #5B4935 @ 10%, offset (0, 1), blur 4.

    Per the frozen coverage rule, nested ruled lists/inset panels/rows/tabs/
    controls *inside* an already-shadowed sheet get no shadow of their own
    -- do not call this on anything but a top-level page sheet, a
    mini-notebook card, or a discrete "chip"-tier note object.
    """
    effect = QGraphicsDropShadowEffect(widget)
    if tier == "mini":
        effect.setColor(qcolor("shadow_mini"))
        effect.setXOffset(0)
        effect.setYOffset(2)
        effect.setBlurRadius(6)
    elif tier == "chip":
        effect.setColor(qcolor("shadow_mini"))
        effect.setXOffset(0)
        effect.setYOffset(1)
        effect.setBlurRadius(4)
    else:
        effect.setColor(qcolor("shadow_full"))
        effect.setXOffset(0)
        effect.setYOffset(3)
        effect.setBlurRadius(10)
    widget.setGraphicsEffect(effect)


# M13 Axis 4 -- the discrete cue/diagnosis/evidence note object (due-frame
# evidence: Quick Practice's recommendation-reason tags render as small pale
# paper-colored labels with a soft lift, never as saturated opaque GUI
# chips). Blend ratios, not the raw stored diagnosis color, produce the
# note's fill/edge -- muted paper tint that still carries the label's color
# identity, per the Product Owner's explicit "not paperized color" rejection
# criterion for the axis.
_NOTE_FILL_BLEND = 0.16
_NOTE_EDGE_BLEND = 0.40
RADIUS_NOTE = 6
RADIUS_NOTE_TL = RADIUS_NOTE
RADIUS_NOTE_TR = RADIUS_NOTE - 2
RADIUS_NOTE_BR = RADIUS_NOTE + 2
RADIUS_NOTE_BL = RADIUS_NOTE - 1


def _blend_color(base: QColor, tint: QColor, ratio: float) -> QColor:
    return QColor(
        round(base.red() * (1 - ratio) + tint.red() * ratio),
        round(base.green() * (1 - ratio) + tint.green() * ratio),
        round(base.blue() * (1 - ratio) + tint.blue() * ratio),
    )


class DiagnosisNoteRow(QFrame):
    """A single cue/diagnosis/evidence label rendered as a small colored
    paper slip -- the Axis 4 shared seam for the three real consumers
    (Player's annotation list, Guided Session Stage 3's diagnosis list,
    Quick Practice Diagnose's diagnosis list), replacing the plain
    `QListWidgetItem` text + tiny color-dot icon each previously used.

    Usage mirrors `make_status_row()`: `row = DiagnosisNoteRow(text, color);
    item.setSizeHint(ruled_list_row_size_hint(row));
    list_widget.setItemWidget(item, row)`. Call `row.set_color(new_hex)` /
    `row.set_text(new_text)` to refresh an existing row in place (e.g. when
    label-color preferences change) instead of replacing the item widget.
    """

    def __init__(self, text: str, color_hex: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(SPACE_TIGHT, SPACE_COMPACT, SPACE_TIGHT, SPACE_COMPACT)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"color: {css('ink')}; background: transparent; font-size: 13px;")
        row_layout.addWidget(self._label)
        apply_paper_shadow(self, "chip")
        self.set_color(color_hex)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def set_color(self, color_hex: str) -> None:
        self.color_hex = color_hex
        base = qcolor("surface_paper")
        tint = QColor(color_hex)
        fill = _blend_color(base, tint, _NOTE_FILL_BLEND)
        edge = _blend_color(base, tint, _NOTE_EDGE_BLEND)
        self.setStyleSheet(
            "DiagnosisNoteRow {"
            f"background-color: {fill.name()};"
            f"border: {BORDER_WIDTH}px solid {edge.name()};"
            f"border-top-left-radius: {RADIUS_NOTE_TL}px;"
            f"border-top-right-radius: {RADIUS_NOTE_TR}px;"
            f"border-bottom-right-radius: {RADIUS_NOTE_BR}px;"
            f"border-bottom-left-radius: {RADIUS_NOTE_BL}px;"
            "}"
        )


class FlowLayout(QLayout):
    """A left-to-right, top-to-bottom wrapping layout (Qt's own documented
    "Flow Layout" example, adapted). Used to lay out a variable number of
    `make_paper_tag()` widgets so they wrap onto additional lines instead of
    clipping or forcing horizontal scroll -- M13 Axis 4 corrective, Quick
    Practice's recommendation-reason tags."""

    def __init__(self, parent: QWidget | None = None, h_spacing: int = SPACE_TIGHT, v_spacing: int = SPACE_TIGHT) -> None:
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list = []

    def addItem(self, item) -> None:  # noqa: N802 -- Qt override
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 -- Qt override
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802 -- Qt override
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802 -- Qt override
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 -- Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 -- Qt override
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:  # noqa: N802 -- Qt override
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x, y = effective_rect.x(), effective_rect.y()
        line_height = 0

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._h_spacing
            if next_x - self._h_spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + self._v_spacing
                next_x = x + item_size.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y()


def make_paper_tag(text: str) -> QLabel:
    """A small neutral warm-paper tag (M13 Axis 4 corrective) -- the direct
    due-frame consumer: Quick Practice's recommendation-reason tags
    ("misheard", "quiz miss", "connected speech", ...), pixel-sampled at a
    near-paper RGB (249, 247, 241), not a saturated diagnosis color.

    Distinct from `DiagnosisNoteRow`, which is a shared-product *extension*
    of the same paper-slip idea to the real annotation/diagnosis list rows
    -- the due-frame boards themselves don't render those rows as paper
    slips, so this tag (not `DiagnosisNoteRow`) is the primary evidenced
    object. Deliberately colorless: recommendation reasons carry no
    per-label user color to derive a tint from.
    """
    label = QLabel(text)
    apply_role(label, "paper_tag")
    apply_paper_shadow(label, "chip")
    return label


def make_reason_tag_row(cue_label: str, reasons: list[str]) -> QWidget:
    """A recommendation-preview row: ordinary readable cue/time/text on its
    own line, followed by a `FlowLayout` of `make_paper_tag()` reason tags
    that wrap cleanly instead of clipping when a cue has several reasons.
    """
    row = QWidget()
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(SPACE_TIGHT, SPACE_COMPACT, SPACE_TIGHT, SPACE_COMPACT)
    row_layout.setSpacing(SPACE_COMPACT)

    cue_text_label = QLabel(cue_label)
    cue_text_label.setWordWrap(True)
    row_layout.addWidget(cue_text_label)

    tag_flow_widget = QWidget()
    tag_flow = FlowLayout(tag_flow_widget)
    for reason in reasons:
        tag_flow.addWidget(make_paper_tag(reason))
    row_layout.addWidget(tag_flow_widget)

    return row


def make_card(title: str | None = None, decorated: bool = True) -> tuple[QFrame, QVBoxLayout]:
    """A light card surface with spacious padding.

    `decorated=True` (default) is the M13 Due-Frame Polish, Axis 1 paper
    treatment -- a painted ink-outline edge and a small lifted paper corner
    instead of a perfectly flat machine rectangle -- scoped to the
    rendering map's 7 rich workspace surfaces (Player, Guided Session,
    Quick Practice Run, Shadowing, Quiz, Main Library, Learning History).
    Pass `decorated=False` for a plain flat card: the compact-dialog
    surfaces (Export/Import/Quick Practice Start/Quiz Review) keep today's
    plain rectangle convention, matching the due-frame boards' own
    restraint there (no paper/ink treatment shown on those boards) rather
    than decorating every card indiscriminately.
    """
    frame = LayeredPaperFrame() if decorated else QFrame()
    apply_role(frame, "card" if decorated else "card_plain")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SPACE_SECTION, SPACE_SECTION, SPACE_SECTION, SPACE_SECTION)
    layout.setSpacing(SPACE_NORMAL)
    if title is not None:
        caption = QLabel(title)
        # M13 Due-Frame Polish, Axis 3: the due-frame boards repeatedly
        # render a card's own title as a blue-ink section header (e.g.
        # Guided Session's "SESSION DIAGNOSIS (so far)") -- `role=
        # "section_header"` already existed in the shared QSS for exactly
        # this (handwritten_blue color) but had zero real consumers
        # anywhere in the app until now. Tied to the same `decorated` flag
        # as the paper/ink-outline treatment: compact dialogs keep the
        # plain caption, matching the due frame's own restraint there.
        apply_role(caption, "section_header" if decorated else "caption")
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
    frame = GrainedPaperFrame()
    apply_surface(frame, "paper")
    apply_role(frame, "notebook_page")
    apply_paper_shadow(frame, "full")
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

    # A single decorative motif in the spiral bar's own title/tape zone --
    # already purely decorative content (spiral cues + optional doodle
    # stamp), never over learning content or controls. One motif per
    # notebook surface, well within every consumer's per-surface budget
    # (Player 3, Guided Session 3, Main Library 2) -- DESIGN.md §10.1.
    spiral_layout.addWidget(make_decorative_motif("star", size_px=16))

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


def make_inset_panel(dense: bool = False) -> tuple[QFrame, QVBoxLayout]:
    """A quiet nested sub-region (`role="inset_panel"`), e.g. a transport/audio
    bar sitting inside an already-paper-surfaced card.

    Distinct from `make_paper_surface()` (M13 Stage B, G16/G18): that helper
    is currently unconsumed and remains a separate concern, not repurposed
    to back this role just because both are "generic flat paper" -- callers
    that need this specific quiet-nested-region look should use this helper.
    """
    frame = QFrame()
    apply_role(frame, "inset_panel")
    layout = QVBoxLayout(frame)
    # DESIGN.md contract: 8-12px internal padding, by density -- uniform on
    # all sides (not the old asymmetric SPACE_SECTION=16px horizontal /
    # SPACE_COMPACT=4px vertical split, which exceeded the 12px ceiling).
    pad = 8 if dense else 12
    layout.setContentsMargins(pad, pad, pad, pad)
    layout.setSpacing(SPACE_COMPACT)
    return frame, layout


class SurfaceHeader(NamedTuple):
    """Return value of `make_surface_header()`. `subtitle_label` is `None`
    when no `subtitle` was passed."""

    top_bar: QHBoxLayout
    title_row: QHBoxLayout
    title_label: QLabel
    subtitle_label: QLabel | None


def make_surface_header(
    title: str,
    subtitle: str | None = None,
    chips: list[tuple[str, str]] | None = None,
    title_role: str = "title",
) -> SurfaceHeader:
    """The shared workspace surface-header vocabulary (M13 Stage B, G6): a
    title (+ optional inline metadata chips) on one row, and an optional
    subtitle/mode caption below. `chips` is a list of `(text, role)` pairs,
    e.g. `[("VIDEO", "badge_primary"), ("12 CUES", "badge_secondary")]`.
    `title_role` lets a surface use a different title tier (e.g. Main
    Library's larger `page_title`) rather than forcing every surface onto
    the same visual weight.

    Returns a `SurfaceHeader(top_bar, title_row, title_label, subtitle_label)`.
    `top_bar` already owns the title block
    (in a column with the chip row + optional subtitle) at stretch factor
    1; the caller decides how to fill the rest of the row, since real
    surfaces vary here (a legitimate-variant seam, not one rigid shape):

    - Add a static trailing action directly: `title_row.addStretch(1)`,
      then `top_bar.addWidget(close_button)` (e.g. Player's "Return to
      Library").
    - Add a live, expanding status label mid-row instead of chips (e.g.
      Guided Session/Quick Practice/Shadowing/Quiz's stage-or-cue progress
      caption): `title_row.addWidget(progress_label, 1)`, then
      `top_bar.addWidget(close_button)`.
    - Add several trailing actions (e.g. Main Library's Hide Sidebar/Show
      Archived/Import): `top_bar.addStretch(1)` (skipping title_row's own
      stretch entirely), then `top_bar.addWidget(...)` per action.

    Scoped to the 7 rich workspace surfaces this rendering map names
    (Player, Guided Session, Quick Practice Run, Shadowing, Quiz, Main
    Library, Learning History). The lighter compact-dialog surfaces keep
    today's native-titlebar-carries-identity convention and must not
    receive this -- it is not a general-purpose header for every window.
    """
    top_bar = QHBoxLayout()
    title_col = QVBoxLayout()
    title_row = QHBoxLayout()
    title_row.setSpacing(SPACE_NORMAL)

    title_label = QLabel(title)
    apply_role(title_label, title_role)
    title_row.addWidget(title_label)

    for chip_text, chip_role in chips or ():
        chip = QLabel(chip_text)
        apply_role(chip, chip_role)
        title_row.addWidget(chip)

    title_col.addLayout(title_row)
    subtitle_label: QLabel | None = None
    if subtitle is not None:
        subtitle_label = QLabel(subtitle)
        apply_role(subtitle_label, "subtitle" if title_role == "page_title" else "caption")
        # M13 Due-Frame Polish, Axis 3: the due-frame boards consistently
        # end this exact subtitle/caption line with a small blue-pencil
        # flourish -- see SketchFlourishWidget's own docstring for the two
        # separate boards this was observed on.
        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(SPACE_COMPACT)
        subtitle_row.addWidget(subtitle_label)
        subtitle_row.addWidget(SketchFlourishWidget(qcolor("handwritten_blue")))
        subtitle_row.addStretch(1)
        title_col.addLayout(subtitle_row)

    top_bar.addLayout(title_col, 1)
    return SurfaceHeader(top_bar, title_row, title_label, subtitle_label)


_DECORATIVE_MOTIFS = {
    "star": ("motif_star", "star_gold"),
    "leaf": ("motif_leaf", "leaf_green"),
    "flower": ("motif_flower", "flower_pink"),
}


def make_decorative_motif(kind: str, size_px: int = 20) -> QLabel:
    """A single decorative motif (DESIGN.md §10.1), rendered from the
    bundled `icons/motif_{kind}.svg` family (deterministic local vector,
    not a font/Unicode glyph -- font rendering of decorative symbols isn't
    guaranteed consistent across platforms/font substitution) in its
    frozen token color. `kind` is one of "star"/"leaf"/"flower". Purely
    ornamental; carries no interaction and must only be placed in a
    genuinely empty paper corner or title/tape zone, never over learning
    content, controls, dense evidence, or beside danger/error regions, and
    never merely to fill empty space. Each surface's per-motif budget and
    eligible zones are in M13_RENDERING_IMPLEMENTATION_MAP.md §7.
    """
    icon_name, token = _DECORATIVE_MOTIFS[kind]
    label = QLabel()
    label.setPixmap(get_icon(icon_name, color_token=token, size=size_px).pixmap(size_px, size_px))
    label.setFixedSize(size_px, size_px)
    return label


def make_metric_tile(icon_name: str, label_text: str, tooltip: str | None = None) -> tuple[QFrame, QLabel]:
    """An icon + label/value tile for a scan-oriented metric sheet (M13
    Due-Frame-First Visual Polish, Axis 5 -- Learning History's Overview
    "METRIC SUMMARY SHEET"). Returns `(tile, value_label)`; the caller sets
    `value_label`'s text after construction. `label_text` is the static
    metric name shown above the value. Purely presentational -- carries no
    new metric semantics beyond what the caller already computed.
    """
    tile = QFrame()
    apply_role(tile, "metric_tile")
    layout = QHBoxLayout(tile)
    layout.setContentsMargins(SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL, SPACE_NORMAL)
    layout.setSpacing(SPACE_NORMAL)

    icon_label = QLabel()
    icon_pixmap = get_icon(icon_name, color_token="accent", size=ICON_SIZE_EMPHASIZED).pixmap(
        ICON_SIZE_EMPHASIZED, ICON_SIZE_EMPHASIZED
    )
    icon_label.setPixmap(icon_pixmap)
    icon_label.setFixedSize(ICON_SIZE_EMPHASIZED, ICON_SIZE_EMPHASIZED)
    if tooltip:
        icon_label.setToolTip(tooltip)
    layout.addWidget(icon_label)

    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    name_label = QLabel(label_text)
    apply_role(name_label, "caption")
    if tooltip:
        name_label.setToolTip(tooltip)
    value_label = QLabel("")
    apply_role(value_label, "metric_value")
    if tooltip:
        value_label.setToolTip(tooltip)
    text_col.addWidget(name_label)
    text_col.addWidget(value_label)
    layout.addLayout(text_col, 1)

    return tile, value_label


def make_media_frame() -> tuple[QFrame, QVBoxLayout]:
    """A warm paper frame around a media viewport -- media placed on a study
    desk, with a small lifted paper corner (M13 Due-Frame-First Visual
    Polish, Axis 1) instead of a perfectly flat machine rectangle."""
    frame = LayeredPaperFrame()
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
    apply_paper_shadow(frame, "mini")
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
    content_layout.setContentsMargins(SPACE_MEDIUM, SPACE_MEDIUM, SPACE_MEDIUM, SPACE_MEDIUM)
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
    selection-color: {css('ink_on_accent', m)};
}}
/* DESIGN.md §8.1: input focus border is `accent` itself (#2563EB), not the
   softer shared `focus` token used elsewhere -- `accent_border_soft`
   (#93C5FD) is the contract's paired "focus ring" value, approximated here
   via hover border since Qt QSS has no outer-glow/box-shadow primitive.
   2px width matches the contract's "visibly strong focus treatment" (same
   1px-border -> 2px-focus convention already used by every button role);
   the same documented, accepted Qt platform limitation applies -- no
   separate soft outer glow, and a 1px box-model shift on focus. */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus {{
    border: 2px solid {css('accent', m)};
}}
*:disabled {{
    color: {css('disabled_text', m)};
}}
QLabel {{
    background-color: transparent;
}}
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget {{
    background-color: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('paper_edge', m)};
    border-radius: {RADIUS_CONTROL}px;
    padding: {SPACE_COMPACT}px 10px;
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: {css('input_hover_border', m)};
}}
QLineEdit:read-only {{
    background-color: {css('input_readonly_bg', m)};
    border-color: {css('line', m)};
    color: {css('secondary', m)};
}}
QLineEdit[invalid="true"] {{
    border-color: {css('danger', m)};
    background-color: {css('danger_subtle', m)};
}}
/* DESIGN.md §5 control-size contract: single-line inputs have a 34px height
   floor. Scoped to QLineEdit/QComboBox only -- QTextEdit/QPlainTextEdit are
   multi-line surfaces and QListWidget/QTableWidget are multi-row containers,
   neither governed by this single-line floor. The shared base rule above
   gives both a 2*SPACE_COMPACT=8px vertical padding and a 2*1px border, so
   (per Qt's QSS box model, which adds padding/border on top of min-height)
   min-height is set to (34 - 8 - 2) to converge the *rendered* height on
   the contract. */
QLineEdit, QComboBox {{
    font-size: 14px;
    min-height: 24px;
}}
/* DESIGN.md §8.3: standard list selection is a light selected-paper tint
   with ink text and a blue border -- never a full-blue/white "enterprise"
   selection. This base rule covers every QListWidget by default (dialogs
   without a dedicated role="ruled_list"/etc.), not just the roled ones. */
QListWidget::item:selected, QListWidget::item:selected:active {{
    background-color: {css('accent_subtle', m)};
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    font-weight: 600;
}}
QListWidget::item:selected:!active {{
    background-color: {css('accent_subtle', m)};
    color: {css('ink', m)};
    border: {BORDER_WIDTH}px solid {css('accent_border_soft', m)};
}}
QListWidget::item:hover {{
    background-color: {css('list_hover', m)};
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
/* DESIGN.md §8.4: 10px width, quiet thumb, 28px minimum thumb length. */
QScrollBar:vertical {{
    background: transparent;
    border: none;
    width: 10px;
}}
QScrollBar:horizontal {{
    background: transparent;
    border: none;
    height: 10px;
}}
QScrollBar::handle {{
    background: {css('scrollbar_thumb', m)};
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{ min-height: 28px; }}
QScrollBar::handle:horizontal {{ min-width: 28px; }}
QScrollBar::handle:hover {{
    background: {css('scrollbar_thumb_hover', m)};
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
/* Typography & Labels (DESIGN.md §4.2 type scale) */
/* M13 Due-Frame Polish, Axis 2: page_title/title/subtitle/metric_value use
   `TITLE_FONT_FAMILY` (rounded geometric) instead of the body/engineering
   `FONT_FAMILY` -- see that constant's own comment for the due-frame
   evidence and CJK-fallback rule. Body, form, caption, helper, transcript,
   question, and diagnosis roles are deliberately untouched. */
QLabel[role="page_title"] {{ font-family: {TITLE_FONT_FAMILY}; font-size: 20px; font-weight: 700; color: {css('ink', m)}; }}
QLabel[role="title"] {{ font-family: {TITLE_FONT_FAMILY}; font-size: 16px; font-weight: 700; letter-spacing: 0.1px; color: {css('ink', m)}; }}
QLabel[role="subtitle"] {{ font-family: {TITLE_FONT_FAMILY}; font-size: 13px; color: {css('muted', m)}; }}
QLabel[role="section_header"] {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: {css('handwritten_blue', m)};
}}
QLabel[role="caption"] {{
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
    color: {css('ink_caption', m)};
}}
QLabel[role="helper"] {{ font-size: 12px; font-weight: 400; color: {css('muted', m)}; }}
QLabel[role="form_label"] {{ font-size: 13px; font-weight: 600; color: {css('secondary', m)}; }}
QLabel[role="muted"] {{ color: {css('muted', m)}; }}
QLabel[role="error"] {{ font-size: 12px; font-weight: 600; color: {css('danger', m)}; }}
QLabel[role="warning"] {{ font-size: 12px; font-weight: 600; color: {css('warning', m)}; }}
QLabel[role="success"] {{ font-size: 12px; font-weight: 600; color: {css('success', m)}; }}
QLabel[role="monospace"] {{ font-family: {MONOSPACE_FONT_FAMILY}; font-size: 11px; font-weight: 500; color: {css('muted', m)}; }}
QLabel[role="dominant_cue"] {{ font-size: 17px; font-weight: 600; color: {css('ink', m)}; padding: 4px 0; }}
QLabel[role="question_stem"] {{ font-size: 16px; font-weight: 650; color: {css('ink', m)}; padding: 4px 0; }}
QLabel[role="body"], QRadioButton[role="body"], QCheckBox[role="body"] {{ font-size: 14px; font-weight: 400; color: {css('ink', m)}; }}
QLabel[role="transcript_cue"] {{ font-size: 16px; font-weight: 500; color: {css('ink', m)}; }}
QLabel[role="metric_value"] {{ font-family: {TITLE_FONT_FAMILY}; font-size: 14px; font-weight: 700; color: {css('ink', m)}; }}
/* Central semantic result-status role (M13 Stage B corrective) -- Quiz
   Review's own "correct"/"incorrect" outcome label, replacing a local
   14px/700/color stylesheet at each call site with one shared role plus an
   `outcome` variant, per DESIGN.md §4.3's "score/result headline" bold rule
   and the existing quiz_correct/quiz_incorrect semantic tokens. */
QLabel[role="result_status"] {{ font-size: 14px; font-weight: 700; }}
QLabel[role="result_status"][outcome="correct"] {{ color: {css('quiz_correct', m)}; }}
QLabel[role="result_status"][outcome="incorrect"] {{ color: {css('quiz_incorrect', m)}; }}

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

/* Washi-tape section stamp (M13 Due-Frame-First Visual Polish, Axis 1/3/4):
   the due-frame boards render every notebook section label as a pinned
   tape/paper-slip with handwritten-blue ink, not plain colored text on the
   bare surface -- this closes that gap for every `make_notebook_surface()`
   context-label consumer (Player x2, Guided Session Stage 5, Main Library
   dossier) from one shared rule. Consumes the previously-orphaned
   `tape_cream` token. */
QLabel[role="notebook_doodle_tag"] {{
    font-family: {HANDWRITING_FONT_FAMILY};
    color: {css('handwritten_blue', m)};
    background-color: {css('tape_cream', m)};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.2px;
    padding: 3px 12px;
    border-radius: 3px;
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
    border-bottom: 1px solid {css('list_divider', m)};
    border-radius: {RADIUS_CONTROL}px;
    margin-bottom: 2px;
}}
QListWidget[role="ruled_list"]::item:hover {{
    background-color: {css('list_hover', m)};
}}
QListWidget[role="ruled_list"]::item:selected, QListWidget[role="ruled_list"]::item:selected:active {{
    background-color: {css('accent_subtle', m)};
    color: {css('ink', m)};
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}
QListWidget[role="ruled_list"]::item:selected:!active {{
    background-color: {css('accent_subtle', m)};
    color: {css('ink', m)};
    border-left: 3px solid {css('accent_border_soft', m)};
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

/* Directory / bookmark list (e.g. Learning History section nav) -- the
   QListWidget sibling of the QPushButton-based `nav_item` role above. */
QListWidget[role="nav_directory"] {{
    border: none;
    padding: {SPACE_COMPACT}px;
}}
QListWidget[role="nav_directory"]::item {{
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    border-radius: {RADIUS_CONTROL}px;
    color: {css('ink', m)};
    font-size: 13px;
    font-weight: 500;
}}
QListWidget[role="nav_directory"]::item:hover {{
    background-color: {css('surface', m)};
}}
QListWidget[role="nav_directory"]::item:selected, QListWidget[role="nav_directory"]::item:selected:active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent', m)};
    font-weight: 600;
}}
QListWidget[role="nav_directory"]::item:selected:!active {{
    background-color: {css('accent_subtle', m)};
    color: {css('accent', m)};
    border-left: 3px solid {css('accent_hover', m)};
}}

/* M13 Axis 4 -- the neutral warm-paper recommendation-reason tag
(`make_paper_tag()`), distinct from `role="chip"` below: a due-frame-
evidenced paper-slip object, not a generic saturated GUI chip. */
QLabel[role="paper_tag"] {{
    background-color: {css('paper_deep', m)};
    color: {css('ink_caption', m)};
    border: {BORDER_WIDTH}px solid {css('paper_edge', m)};
    border-top-left-radius: {RADIUS_NOTE_TL}px;
    border-top-right-radius: {RADIUS_NOTE_TR}px;
    border-bottom-right-radius: {RADIUS_NOTE_BR}px;
    border-bottom-left-radius: {RADIUS_NOTE_BL}px;
    padding: 2px 8px;
    font-size: 12px;
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
QLabel[role="badge_secondary"] {{
    background-color: {css('surface_soft', m)};
    color: {css('secondary', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
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
    border: {BORDER_WIDTH}px solid transparent;
    border-top-left-radius: {RADIUS_CARD_TL}px;
    border-top-right-radius: {RADIUS_CARD_TR}px;
    border-bottom-right-radius: {RADIUS_CARD_BR}px;
    border-bottom-left-radius: {RADIUS_CARD_BL}px;
}}
QFrame[role="inset_panel"] {{
    background-color: {css('surface_soft', m)};
    border: {BORDER_WIDTH}px solid {css('line_ruled', m)};
    border-radius: {RADIUS_CONTROL}px;
}}
QLabel[role="media_placeholder"] {{
    background-color: {css('surface_paper', m)};
    color: {css('muted', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
    font-size: 13px;
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
   without touching the "secondary"/"quiet" roles used elsewhere. Padding
   only -- a local `font-size: 9pt` override here used to silently diverge
   from the frozen "Regular button: 13px/600" contract (DESIGN.md §4.2);
   removed rather than kept, since compacting footprint doesn't require
   compacting the shared button type scale too. */
QFrame[role="mini_notebook_card"] QPushButton[role="secondary"],
QFrame[role="mini_notebook_card"] QPushButton[role="quiet"] {{
    padding: {SPACE_COMPACT}px {SPACE_COMPACT + 2}px;
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
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
}}
QPushButton[role="notebook_primary_action"]:hover {{
    background-color: {css('accent', m)};
    color: {css('ink_on_accent', m)};
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
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
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
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
}}
/* DESIGN.md §7.5: ordinary destructive hover stays a subtle paper-pink
   tint, matching role="danger" -- filled red with white text is reserved
   for an unambiguous final destructive commit inside a confirmation
   context, never an ordinary notebook action button's hover state. */
QPushButton[role="notebook_destructive_action"]:hover {{
    background-color: {css('danger_subtle', m)};
}}
QPushButton[role="notebook_destructive_action"]:pressed {{
    background-color: {css('danger_pressed', m)};
}}
QPushButton[role="notebook_destructive_action"]:disabled {{
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}

/* Surfaces & Containers */
/* M13 Due-Frame Polish, Axis 1 continuation: the edge line is now painted
   by LayeredPaperFrame.paintEvent() (a deterministic ink-outline stroke),
   not this QSS border -- kept as `solid transparent` (not `none`) so Qt's
   background-clip still respects the per-corner radius below. */
QFrame[role="card"] {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid transparent;
    border-top-left-radius: {RADIUS_CARD_TL}px;
    border-top-right-radius: {RADIUS_CARD_TR}px;
    border-bottom-right-radius: {RADIUS_CARD_BR}px;
    border-bottom-left-radius: {RADIUS_CARD_BL}px;
}}

/* Plain flat card (M13 Due-Frame Polish, Axis 1 scoping) -- the
   pre-Axis-1 rectangle, for compact dialogs the due-frame boards show
   with no paper/ink treatment. */
QFrame[role="card_plain"] {{
    background-color: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CARD}px;
}}

/* Metric tile (M13 Due-Frame-First Visual Polish, Axis 5): a small
   icon + label/value card for a scan-oriented metric sheet, e.g. Learning
   History's Overview "METRIC SUMMARY SHEET". */
QFrame[role="metric_tile"] {{
    background-color: {css('surface_soft', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
    border-radius: {RADIUS_CONTROL}px;
}}

/* Surface: Soft Panel (directory / sidebar backing) */
QMainWindow[surface="surface_soft"],
QWidget[surface="surface_soft"],
QScrollArea[surface="surface_soft"],
QScrollArea[surface="surface_soft"] > QWidget > QWidget,
QListWidget[surface="surface_soft"] {{
    background-color: {css('surface_soft', m)};
    color: {css('ink', m)};
}}

/* Surface: Sidebar (app directory / archive rail) -- the dedicated
   `surface_sidebar`/sidebar_bg token, distinct from the generic
   `workspace` surface. */
QMainWindow[surface="sidebar"],
QWidget[surface="sidebar"] {{
    background-color: {css('surface_sidebar', m)};
    color: {css('ink', m)};
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

/* Cinema / Dark Focus Surface -- M13 Rendering Map §Surfaces names this as a
   frozen surface family; no window currently calls apply_surface(widget,
   "cinema") (it's tied to video-mode playback, untestable in this pass --
   no video fixture exists under manual-qa/, only audio). Kept and
   token-sourced rather than deleted since the Map treats it as accepted
   infrastructure, not dead code -- see M13 Stage B native-visual corrective
   final report for this exact drift. */
QMainWindow[surface="cinema"],
QWidget[surface="cinema"],
QScrollArea[surface="cinema"],
QScrollArea[surface="cinema"] > QWidget > QWidget {{
    background-color: {css('surface_cinema', m)};
    color: {css('cinema_ink', m)};
}}
QFrame[surface="cinema"] {{
    background-color: {css('cinema_card_bg', m)};
    color: {css('cinema_ink', m)};
    border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.12);
    border-radius: {RADIUS_CARD}px;
}}
QWidget[surface="cinema"] QLabel {{
    color: {css('cinema_ink', m)};
}}
QWidget[surface="cinema"] QLabel[role="caption"] {{
    color: {css('cinema_muted', m)};
}}
QWidget[surface="cinema"] QLabel[role="subtitle"] {{
    color: {css('cinema_muted', m)};
}}
QWidget[surface="cinema"] QCheckBox {{
    color: {css('cinema_ink', m)};
}}
QWidget[surface="cinema"] QLineEdit,
QWidget[surface="cinema"] QTextEdit,
QWidget[surface="cinema"] QPlainTextEdit {{
    background-color: {css('cinema_input_bg', m)};
    color: {css('cinema_ink', m)};
    border: {BORDER_WIDTH}px solid rgba(255, 255, 255, 0.18);
    border-radius: {RADIUS_CONTROL}px;
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
/* DESIGN.md §4.2 "Regular button" row: 13px/600 for every ordinary
   (non-hero) button role, color role-specific -- applied once here so
   every role below inherits it without repeating the declaration.
   M13 Due-Frame Polish, Axis 2: the due-frame boards render every ordinary
   button's label in the casual handwriting face -- short,
   personality-bearing chrome text, exactly the category
   `HANDWRITING_FONT_FAMILY`'s own docstring sanctions it for. The
   `[hero="true"]` filled tier is a distinct evidenced exception (see its
   own rule below): those boards show it in the same bold rounded
   *display* face as titles, not handwriting. */
QPushButton[role="primary"], QPushButton[role="secondary"], QPushButton[role="quiet"],
QPushButton[role="danger"], QPushButton[role="success"], QPushButton[role="notebook_primary_action"],
QPushButton[role="notebook_action"], QPushButton[role="notebook_destructive_action"] {{
    font-family: {HANDWRITING_FONT_FAMILY};
    font-size: 13px;
    font-weight: 600;
}}

/* M13 Due-Frame Polish, Axis 1 continuation: the due-frame boards' own
   close-ups show a genuine two-tier button hierarchy, not "every primary
   action is filled" -- an ordinary (non-hero) `role="primary"` action
   (e.g. Player's Play, Quiz's Next Question) reads as paper/no-fill with
   a blue ink outline, exactly like secondary/danger/success. Only the
   `hero="true"` tier (a screen's single genuine launch/commit action --
   Main Library's Open Player, Quiz's final Submit, Quick Practice's
   Start/Reveal-and-Continue, Shadowing's Start Recording) is evidenced as
   solid-filled. Keeping the old "every primary is filled" grammar here
   would have painted the new ink outline on top of a contradiction
   instead of resolving it. */
QPushButton[role="primary"] {{
    background-color: {css('surface_paper', m)};
    color: {css('accent', m)};
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    border-top-left-radius: {RADIUS_BUTTON_TL}px;
    border-top-right-radius: {RADIUS_BUTTON_TR}px;
    border-bottom-right-radius: {RADIUS_BUTTON_BR}px;
    border-bottom-left-radius: {RADIUS_BUTTON_BL}px;
    padding: {SPACE_COMPACT}px {SPACE_MEDIUM}px;
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24,
       matching secondary's box model -- fill/border color changed, not
       the 34px ordinary-button height contract. */
    min-height: 24px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {css('accent_subtle', m)};
    border-color: {css('accent_hover', m)};
}}
QPushButton[role="primary"]:pressed {{ background-color: {css('accent_selected', m)}; }}
/* Hero tier (DESIGN.md §5.3/§7.2, 40px): the single most prominent
   progression action on a surface -- opted in via
   `widget.setProperty("hero", "true")`. This is the ONLY `role="primary"`
   variant that is solid-filled, per the due-frame evidence above. */
QPushButton[role="primary"][hero="true"] {{
    background-color: {css('accent', m)};
    color: {css('ink_on_accent', m)};
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    font-family: {TITLE_FONT_FAMILY};
    font-size: 14px;
    font-weight: 650;
    letter-spacing: 0.1px;
    padding: {SPACE_NORMAL}px {SPACE_SECTION}px;
    /* vertical padding 16px + border 2px -> 40-16-2=22. */
    min-height: 22px;
}}
QPushButton[role="primary"][hero="true"]:hover {{
    background-color: {css('accent_hover', m)};
    border-color: {css('accent_hover', m)};
}}
QPushButton[role="primary"][hero="true"]:pressed {{
    background-color: {css('accent_pressed', m)};
    border-color: {css('accent_pressed', m)};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {css('disabled_surface', m)};
    border-color: {css('disabled_border', m)};
    color: {css('disabled_text', m)};
}}

QPushButton[role="secondary"] {{
    background-color: {css('surface_paper', m)};
    color: {css('ink_button_secondary', m)};
    border: {BORDER_WIDTH}px solid {css('paper_edge', m)};
    border-top-left-radius: {RADIUS_BUTTON_TL}px;
    border-top-right-radius: {RADIUS_BUTTON_TR}px;
    border-bottom-right-radius: {RADIUS_BUTTON_BR}px;
    border-bottom-left-radius: {RADIUS_BUTTON_BL}px;
    padding: {SPACE_COMPACT}px {SPACE_MEDIUM}px;
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
}}
QPushButton[role="secondary"]:hover {{
    background-color: {css('accent_subtle', m)};
    border-color: {css('accent_border_soft', m)};
}}
QPushButton[role="secondary"]:pressed {{ background-color: {css('accent_selected', m)}; }}
QPushButton[role="secondary"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}

QPushButton[role="quiet"] {{
    background-color: transparent;
    color: {css('secondary', m)};
    border: {BORDER_WIDTH}px solid transparent;
    border-top-left-radius: {RADIUS_BUTTON_TL}px;
    border-top-right-radius: {RADIUS_BUTTON_TR}px;
    border-bottom-right-radius: {RADIUS_BUTTON_BR}px;
    border-bottom-left-radius: {RADIUS_BUTTON_BL}px;
    padding: {SPACE_COMPACT}px 10px;
    /* 2*SPACE_COMPACT=8px vertical padding, transparent border still
       reserves its 2*1px in the box model -> 30-8-2=20. */
    min-height: 20px;
}}
QPushButton[role="quiet"]:hover {{ background-color: {css('quiet_hover', m)}; color: {css('ink', m)}; }}
QPushButton[role="quiet"]:pressed {{ background-color: {css('quiet_pressed', m)}; }}
QPushButton[role="quiet"]:disabled {{ color: {css('disabled_text', m)}; }}

QPushButton[role="danger"] {{
    background-color: {css('surface_paper', m)};
    color: {css('danger', m)};
    border: {BORDER_WIDTH}px solid {css('danger', m)};
    border-top-left-radius: {RADIUS_BUTTON_TL}px;
    border-top-right-radius: {RADIUS_BUTTON_TR}px;
    border-bottom-right-radius: {RADIUS_BUTTON_BR}px;
    border-bottom-left-radius: {RADIUS_BUTTON_BL}px;
    padding: {SPACE_COMPACT}px {SPACE_MEDIUM}px;
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
}}
/* DESIGN.md §7.5: danger's ordinary hover is a subtle paper-pink tint, NOT
   a filled solid-red button -- filled red is reserved for a destructive
   confirmation dialog's unambiguous final commit, never ordinary hover. */
QPushButton[role="danger"]:hover {{ background-color: {css('danger_subtle', m)}; }}
QPushButton[role="danger"]:pressed {{ background-color: {css('danger_pressed', m)}; }}
QPushButton[role="danger"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
    border-color: {css('disabled_border', m)};
}}
/* Danger has its own focus-ring color (#EF9A9B), distinct from every other
   role's shared `focus` token -- declared after the generic QPushButton:focus
   rule below so equal-specificity QSS ordering lets it win. */
QPushButton[role="danger"]:focus {{
    border: 2px solid {css('danger_focus_ring', m)};
}}

/* M13 Due-Frame Polish, Axis 1 continuation: the due frame's only
   `success`-role consumer (Guided Session's "Complete Session") reads as
   paper/no-fill with a green ink outline, not a filled green button --
   no due-frame evidence anywhere supports a filled-success tier, so
   (unlike `primary`) this role has no hero-filled variant at all. */
QPushButton[role="success"] {{
    background-color: {css('surface_paper', m)};
    color: {css('success', m)};
    border: {BORDER_WIDTH}px solid {css('success', m)};
    border-top-left-radius: {RADIUS_BUTTON_TL}px;
    border-top-right-radius: {RADIUS_BUTTON_TR}px;
    border-bottom-right-radius: {RADIUS_BUTTON_BR}px;
    border-bottom-left-radius: {RADIUS_BUTTON_BL}px;
    padding: {SPACE_COMPACT}px {SPACE_MEDIUM}px;
    /* 2*SPACE_COMPACT=8px vertical padding + 2*1px border -> 34-8-2=24. */
    min-height: 24px;
}}
QPushButton[role="success"]:hover {{ background-color: {css('quiet_hover', m)}; }}
QPushButton[role="success"]:pressed {{ background-color: {css('quiet_pressed', m)}; }}
QPushButton[role="success"]:disabled {{
    background-color: {css('disabled_surface', m)};
    color: {css('disabled_text', m)};
}}

QPushButton:focus {{
    border: 2px solid {css('focus', m)};
}}

/* Shared state-card rendering vocabulary (M13 Stage B, G15): the visual
   mechanics genuinely common to Guided Session's StageStepper items and
   Quiz's QuizOptionCard answer cards -- border/radius, focus treatment,
   selected/active + success/warning/disabled tokens. They remain distinct
   semantic roles (`stepper_item` progress state vs `quiz_option` answer
   selection), each still its own widget -- this is shared vocabulary, not
   a shared widget. */
QPushButton[role="stepper_item"] {{
    border-radius: {RADIUS_STATE_CARD}px;
}}
QPushButton[role="stepper_item"]:focus {{
    border: 2px solid {css('accent', m)};
}}
QPushButton[role="stepper_item"][state="current"] {{
    background: {css('accent_subtle', m)};
    border: 1.5px solid {css('accent', m)};
}}
QPushButton[role="stepper_item"][state="completed"] {{
    background: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('success', m)};
}}
QPushButton[role="stepper_item"][state="completed"]:hover {{
    background: {css('accent_subtle', m)};
}}
QPushButton[role="stepper_item"][state="skipped"] {{
    background: {css('surface_paper', m)};
    border: {BORDER_WIDTH}px solid {css('warning', m)};
}}
QPushButton[role="stepper_item"][state="skipped"]:hover {{
    background: {css('accent_subtle', m)};
}}
QPushButton[role="stepper_item"][state="not_started"],
QPushButton[role="stepper_item"][state="not_started"]:disabled {{
    background: {css('surface_soft', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
}}

QLabel[role="stepper_item_badge"] {{
    border-radius: 11px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel[role="stepper_item_badge"][state="current"] {{
    background: {css('accent', m)};
    color: {css('ink_on_accent', m)};
}}
QLabel[role="stepper_item_badge"][state="completed"] {{
    background: {css('success', m)};
    color: {css('ink_on_accent', m)};
}}
QLabel[role="stepper_item_badge"][state="skipped"] {{
    background: {css('warning', m)};
    color: {css('ink_on_accent', m)};
}}
QLabel[role="stepper_item_badge"][state="not_started"] {{
    background: {css('stepper_future_badge', m)};
    color: {css('disabled_text', m)};
    font-weight: 600;
}}

QLabel[role="stepper_item_label"] {{
    font-size: 12px;
}}
QLabel[role="stepper_item_label"][state="current"] {{
    font-weight: 700;
    color: {css('ink', m)};
}}
QLabel[role="stepper_item_label"][state="completed"] {{
    font-weight: 600;
    color: {css('ink', m)};
}}
QLabel[role="stepper_item_label"][state="skipped"],
QLabel[role="stepper_item_label"][state="not_started"] {{
    font-weight: 500;
    color: {css('muted', m)};
}}

QFrame[role="quiz_option"] {{
    border-radius: {RADIUS_STATE_CARD}px;
}}
QFrame[role="quiz_option"]:focus {{
    border: 2px solid {css('accent', m)};
}}
QFrame[role="quiz_option"][selected="true"] {{
    background: {css('accent_subtle', m)};
    border: 1.5px solid {css('accent', m)};
}}
QFrame[role="quiz_option"][selected="false"] {{
    background: {css('surface', m)};
    border: {BORDER_WIDTH}px solid {css('line', m)};
}}
QFrame[role="quiz_option"][selected="false"]:hover {{
    border-color: {css('accent', m)};
}}

QLabel[role="quiz_option_badge"] {{
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel[role="quiz_option_badge"][selected="true"] {{
    background: {css('accent', m)};
    color: {css('ink_on_accent', m)};
}}
QLabel[role="quiz_option_badge"][selected="false"] {{
    background: {css('line', m)};
    color: {css('ink', m)};
}}

QLabel[role="quiz_option_marker"] {{
    font-size: 13px;
    font-weight: 700;
}}
QLabel[role="quiz_option_marker"][selected="true"] {{
    color: {css('accent', m)};
}}

/* RadioButton / CheckBox -- DESIGN.md §8.2: 16px indicator, 8px label gap;
   §5.3: 30px interactive-row minimum. No padding/border is declared on the
   button itself, so min-height sets the full row height directly -- no
   box-model subtraction needed (contrast with QPushButton, which does). */
QRadioButton, QCheckBox {{
    spacing: {SPACE_NORMAL}px;
    min-height: 30px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;
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
QRadioButton:disabled, QCheckBox:disabled {{
    color: {css('disabled_text', m)};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: {BORDER_WIDTH}px solid {css('line', m)};
    background-color: {css('surface', m)};
}}
QCheckBox::indicator:hover {{ border-color: {css('muted', m)}; }}
QCheckBox::indicator:checked {{
    border: {BORDER_WIDTH}px solid {css('accent', m)};
    background-color: {css('accent', m)};
}}
QCheckBox::indicator:focus {{
    border: {BORDER_WIDTH}px solid {css('focus', m)};
}}

/* TabWidget -- DESIGN.md §7.7/§5.3: a paper-index tab, 34px */
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
    /* 2*(SPACE_COMPACT+2)=12px vertical padding + 1px top border (bottom
       is none) -> 34-12-1=21. */
    min-height: 21px;
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
    # DESIGN.md §8.1 placeholder text color: Qt Style Sheets have no
    # `placeholder-text-color` property (unlike `color`/`background`), so the
    # `ink_placeholder` token can only reach QLineEdit/QComboBox through the
    # application palette's PlaceholderText role -- set once here rather than
    # per call site.
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.PlaceholderText, qcolor("ink_placeholder", theme_mode))
    app.setPalette(palette)


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


# ---------------------------------------------------------------------------
# Functional icon system (M13 Stage B, G7/G21)
#
# One bundled, repo-local, permissively-licensed monochrome-outline SVG
# family (this project's own hand-authored geometric glyphs -- no
# third-party icon library, no runtime web dependency). 24x24 source
# viewBox, ~2px stroke, round cap/join. `get_icon()` renders and tints an
# SVG to the requested token color, since the source files use a neutral
# stroke rather than baking in any one theme color. The sanctioned
# inventory is derived only from real production actions currently
# expressed as bare Unicode glyphs (see the migrated call sites in
# player_window.py, guided_session_window.py, quick_practice_window.py,
# quiz_window.py, shadowing_practice_window.py, main_window.py); the
# decorative "*" completion flourish is explicitly NOT part of this system.
# ---------------------------------------------------------------------------

ICON_SIZE_NORMAL = 16
ICON_SIZE_EMPHASIZED = 20
ICON_TEXT_GAP_PX = 6

# Documented Qt platform exception (frozen contract still 6px): unlike
# make_status_row()'s hand-built QHBoxLayout -- where ICON_TEXT_GAP_PX is a
# real, exact layout.setSpacing() value -- a QPushButton's native
# icon-to-text gap comes from QStyle::PM_ButtonMargin, which Qt Style
# Sheets have no supported property to override, and whose exact pixel
# value is a platform/style detail (Fusion/Windows/etc. each compute it
# differently). set_button_icon() cannot make this exact without replacing
# QPushButton's native icon+text layout with fully custom painting, which
# is out of proportion to a cosmetic icon-text gap. Bounded instead of
# exact: PM_ButtonMargin must stay within BUTTON_ICON_GAP_TOLERANCE_PX of
# the frozen 6px target (see test_button_icon_gap_is_within_the_documented_
# platform_tolerance).
BUTTON_ICON_GAP_TOLERANCE_PX = 4


def _icons_search_dirs() -> list[Path]:
    """Candidate directories for bundled icon SVGs, covering every runtime
    context -- mirrors `_icon_search_paths()`'s frozen/dev split above."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "icons")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "icons")
    candidates.append(Path(__file__).resolve().parent / "icons")
    return candidates


def _find_icon_path(name: str) -> Path | None:
    for directory in _icons_search_dirs():
        candidate = directory / f"{name}.svg"
        if candidate.is_file():
            return candidate
    return None


def set_button_icon(
    button: QWidget,
    name: str,
    color_token: str = "secondary",
    emphasized: bool = False,
) -> None:
    """Set a sanctioned functional icon on `button` at the frozen normal
    (16px) or emphasized (18-20px) size, alongside its existing text label
    -- never as a replacement for it. Thin convenience wrapper around
    `get_icon()` so call sites don't each re-derive `QSize(...)`."""
    size = ICON_SIZE_EMPHASIZED if emphasized else ICON_SIZE_NORMAL
    button.setIcon(get_icon(name, color_token=color_token, size=size))
    button.setIconSize(QSize(size, size))


def get_icon(name: str, color_token: str = "secondary", size: int = ICON_SIZE_NORMAL) -> QIcon:
    """A tinted `QIcon` rendered from the bundled `icons/{name}.svg`, or a
    null `QIcon` if the file can't be found (degrades to no icon, never a
    crash -- callers keep their existing text label either way).

    `color_token` is the icon's *enabled* state color per DESIGN.md §7.6:
    `secondary` (ink_secondary) normal, `ink_on_accent` primary/active,
    `danger` danger. The returned icon also carries a `QIcon.Mode.Disabled`
    pixmap tinted with `disabled_text` (ink_disabled) -- Qt selects it
    automatically from the button's own `isEnabled()` state, so a button
    that gets `setEnabled(False)` anywhere in the codebase always renders
    the correct disabled tint with no risk of a stale enabled-state color
    lingering (no per-call-site re-tinting required).
    """
    from PySide6.QtSvg import QSvgRenderer

    path = _find_icon_path(name)
    if path is None:
        return QIcon()

    renderer = QSvgRenderer(str(path))

    def _tinted_pixmap(token: str) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), qcolor(token))
        painter.end()
        return pixmap

    icon = QIcon()
    icon.addPixmap(_tinted_pixmap(color_token), QIcon.Mode.Normal)
    icon.addPixmap(_tinted_pixmap("disabled_text"), QIcon.Mode.Disabled)
    return icon

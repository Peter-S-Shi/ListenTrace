from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton

from listentrace.ui import theme


def _rendered_height(widget) -> int:
    """The widget's real, QSS-stylesheet-driven height (content + padding +
    border), not the raw min-height CSS property -- Qt's box model adds
    padding/border on top of min-height, so string-matching the QSS for
    "min-height: 34px" would not actually verify the rendered contract."""
    widget.setStyleSheet(theme.build_stylesheet("light"))
    widget.ensurePolished()
    return widget.sizeHint().height()


def _qss_rule(sheet: str, selector: str) -> str:
    """The literal `{ ... }` body Qt would parse for `selector` -- the
    actual public contract the style engine consumes."""
    import re

    match = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", sheet)
    assert match is not None, f"no QSS rule found for selector: {selector}"
    return match.group(1)


def test_build_stylesheet_is_non_empty_and_contains_m13_tokens():
    sheet = theme.build_stylesheet("light")

    assert sheet.strip() != ""
    assert theme.css("page") in sheet
    assert theme.css("accent") in sheet
    assert theme.css("danger") in sheet
    assert 'role="primary"' in sheet
    assert 'role="secondary"' in sheet
    assert 'role="quiet"' in sheet
    assert 'role="danger"' in sheet
    assert 'role="error"' in sheet
    assert 'role="nav_item"' in sheet
    assert 'role="ruled_list"' in sheet
    assert 'surface="paper"' in sheet
    assert 'surface="cinema"' in sheet


def test_build_stylesheet_supports_dark_mode():
    sheet_dark = theme.build_stylesheet("dark")
    assert sheet_dark.strip() != ""
    assert theme.css("page", theme_mode="dark") in sheet_dark
    assert theme.css("accent", theme_mode="dark") in sheet_dark


def test_apply_theme_sets_the_application_stylesheet(qapp):
    qapp.setStyleSheet("")

    theme.apply_theme(qapp, "light")

    assert qapp.styleSheet() == theme.build_stylesheet("light")


def test_apply_role_sets_the_role_property_without_changing_widget_identity(qapp):
    label = QLabel("Status")
    label.setWordWrap(True)

    theme.apply_role(label, "error")

    assert label.property("role") == "error"
    assert label.text() == "Status"
    assert label.wordWrap() is True


def test_apply_role_works_for_buttons_too(qapp):
    button = QPushButton("Save")

    theme.apply_role(button, "primary")

    assert button.property("role") == "primary"
    assert button.text() == "Save"


def test_apply_surface_sets_the_surface_property(qapp):
    frame = QFrame()
    theme.apply_surface(frame, "paper")
    assert frame.property("surface") == "paper"


def test_make_paper_surface_creates_styled_frame():
    frame, layout = theme.make_paper_surface("Study Notes")
    assert frame.property("surface") == "paper"
    assert layout.count() >= 1


def test_make_notebook_surface_creates_spiral_ruled_frame():
    frame, layout = theme.make_notebook_surface("Material Study Dossier")
    assert frame.property("surface") == "paper"
    assert frame.property("role") == "notebook_page"
    assert layout.count() >= 1


def test_make_spiral_binding_strip_uses_a_real_painted_widget_not_a_glyph_label():
    """Player Notebook Primitive Hardening corrective: the center binding must
    be a real QPainter-rendered component, not a QLabel of repeated glyphs."""
    from listentrace.ui.widgets.notebook_paper import SpiralBindingWidget

    strip = theme.make_spiral_binding_strip()

    assert strip.property("role") == "spiral_binding_strip"
    binding = strip.findChild(SpiralBindingWidget)
    assert binding is not None


def test_make_mini_notebook_has_a_real_binding_edge_and_ruled_paper_body():
    from listentrace.ui.widgets.notebook_paper import RuledPaperFrame, SpiralBindingWidget

    frame, content_layout = theme.make_mini_notebook("Playback")

    assert frame.property("role") == "mini_notebook_card"
    assert frame.findChild(SpiralBindingWidget) is not None
    body = frame.findChild(RuledPaperFrame)
    assert body is not None
    assert body.property("role") == "mini_notebook_body"

    # The returned content_layout is still a normal layout callers can add
    # real controls to, and those controls land inside the ruled-paper body.
    marker = QPushButton("Play")
    content_layout.addWidget(marker)
    assert body.isAncestorOf(marker)


def test_qcolor_and_css_agree_on_the_same_token():
    color = theme.qcolor("accent")

    assert isinstance(color, QColor)
    assert color.name().upper() == theme.css("accent").upper()


def test_qcolor_handles_a_token_with_alpha():
    color = theme.qcolor("rule_blue")

    r, g, b, a = theme._TOKENS["rule_blue"]
    assert color.red() == r
    assert color.green() == g
    assert color.blue() == b
    assert color.alpha() == a
    assert "rgba(" in theme.css("rule_blue")


def test_accent_is_professional_blue():
    # M13 Frozen Contract: Professional Blue
    color = theme.qcolor("accent")
    assert color.blue() > color.red()
    assert color.blue() > color.green()
    assert theme.css("accent").upper() in ["#2563EB", "#3B82F6"]


def test_product_semantic_tokens_preserve_their_values():
    # M13 Stage B migration: `quiz_correct`/`chart_axis`/`chart_text` moved to
    # DESIGN.md's canonical values (aligned to `success`/`warm_divider`/
    # `ink_primary` respectively); `cue_active`/`text_overlap`/`quiz_incorrect`
    # are not part of the DESIGN.md palette and are genuinely unchanged.
    assert theme.css("cue_active").upper() == "#FFF3CD"
    assert theme.css("text_overlap").upper() == "#D0D0D0"
    assert theme.css("quiz_correct").upper() == "#168247"
    assert theme.css("quiz_incorrect").upper() == "#DC2626"
    assert theme.css("chart_axis").upper() == "#E6DED2"
    assert theme.css("chart_text").upper() == "#1F1D1A"


def test_get_app_icon_returns_a_real_icon_when_the_packaging_asset_exists():
    icon = theme.get_app_icon()

    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_get_app_icon_degrades_gracefully_when_no_candidate_path_exists(monkeypatch):
    monkeypatch.setattr(theme, "_icon_search_paths", lambda: [])

    icon = theme.get_app_icon()

    assert isinstance(icon, QIcon)
    assert icon.isNull()


def test_spiral_binding_widget_ring_count_scales_with_available_height(qapp):
    """The binding must derive its ring count from real available geometry
    (dynamic), not a hardcoded count baked in at construction time."""
    from listentrace.ui.widgets.notebook_paper import SpiralBindingWidget

    binding = SpiralBindingWidget(theme.qcolor("surface_paper"), theme.qcolor("notebook_binding"))

    binding.resize(28, 120)
    short_count = binding.ring_count()

    binding.resize(28, 600)
    tall_count = binding.ring_count()

    assert tall_count > short_count
    assert short_count >= 0


@pytest.mark.parametrize(
    "role,expected_height",
    [
        ("primary", 34),
        ("secondary", 34),
        ("danger", 34),
        ("success", 34),
        ("quiet", 30),
        ("notebook_primary_action", 34),
        ("notebook_action", 34),
        ("notebook_destructive_action", 34),
    ],
)
def test_button_role_renders_at_the_contract_height(qapp, role, expected_height):
    """DESIGN.md §2.8/§5: 34px standard button, 30px quiet -- verified against
    the widget's real stylesheet-driven sizeHint (content + padding +
    border), so the QSS's min-height plus its own padding/border actually
    converges on the contract instead of merely declaring it."""
    button = QPushButton("Label")
    theme.apply_role(button, role)

    assert _rendered_height(button) == expected_height


def test_hero_primary_button_renders_40px_tall(qapp):
    """A `hero="true"` primary button (DESIGN.md's 40px Hero tier, e.g. a
    workspace's single most prominent progression action) is a distinct,
    additive QSS variant from the 34px ordinary primary button."""
    button = QPushButton("Start Practice")
    theme.apply_role(button, "primary")
    button.setProperty("hero", "true")

    assert _rendered_height(button) == 40


def test_single_line_inputs_render_at_the_34px_contract_height(qapp):
    """DESIGN.md §5: QLineEdit/QComboBox have a 34px height floor -- verified
    against real stylesheet-driven sizeHint, not the QSS source text."""
    line_edit = QLineEdit()

    assert _rendered_height(line_edit) == 34


@pytest.mark.parametrize(
    "status,token",
    [("active", "accent"), ("completed", "success"), ("abandoned", "warning")],
)
def test_status_dot_icon_uses_the_frozen_color_per_status(qapp, status, token):
    icon = theme.status_dot_icon(status)

    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    pixmap = icon.pixmap(icon.availableSizes()[0])
    center = pixmap.toImage().pixelColor(pixmap.width() // 2, pixmap.height() // 2)
    assert center.getRgb()[:3] == theme.qcolor(token).getRgb()[:3]


@pytest.mark.parametrize(
    "name",
    [
        "play",
        "forward",
        "back",
        "up",
        "down",
        "check",
        "close",
        "material",
        "clock",
        "x_circle",
        "quiz",
        "chart",
        "clipboard",
        "mic",
        "waveform",
        "warning",
    ],
)
def test_get_icon_finds_every_sanctioned_inventory_icon(qapp, name):
    icon = theme.get_icon(name)

    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_get_icon_tints_to_the_requested_color_token(qapp):
    icon = theme.get_icon("close", color_token="danger")

    pixmap = icon.pixmap(theme.ICON_SIZE_NORMAL, theme.ICON_SIZE_NORMAL)
    image = pixmap.toImage()
    # The X glyph's diagonal strokes cross through the center pixel.
    center = image.pixelColor(image.width() // 2, image.height() // 2)
    assert center.alpha() > 0
    assert center.getRgb()[:3] == theme.qcolor("danger").getRgb()[:3]


def test_get_icon_degrades_to_a_null_icon_for_an_unknown_name(qapp):
    icon = theme.get_icon("does_not_exist")

    assert isinstance(icon, QIcon)
    assert icon.isNull()


@pytest.mark.parametrize(
    "kind,token",
    [("star", "star_gold"), ("leaf", "leaf_green"), ("flower", "flower_pink")],
)
def test_make_decorative_motif_uses_the_frozen_token_color(qapp, kind, token):
    label = theme.make_decorative_motif(kind)

    pixmap = label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    image = pixmap.toImage()
    expected = theme.qcolor(token).getRgb()[:3]
    # Scan for the tinted color rather than assuming a specific pixel is
    # opaque -- the three motifs are different shapes (filled vs. stroked),
    # so no single coordinate is guaranteed covered by all of them.
    found = any(
        image.pixelColor(x, y).alpha() > 0 and image.pixelColor(x, y).getRgb()[:3] == expected
        for x in range(image.width())
        for y in range(image.height())
    )
    assert found


def test_make_metric_tile_returns_a_settable_value_label(qapp):
    tile, value_label = theme.make_metric_tile("material", "Materials Practiced")

    assert tile.property("role") == "metric_tile"
    value_label.setText("3")
    assert value_label.text() == "3"
    assert value_label.property("role") == "metric_value"


def test_make_metric_tile_renders_the_requested_icon(qapp):
    tile, _value_label = theme.make_metric_tile("clock", "Active Sessions")

    icon_labels = [child for child in tile.findChildren(QLabel) if child.pixmap() is not None and not child.pixmap().isNull()]
    assert len(icon_labels) == 1


def test_make_surface_header_default_title_role(qapp):
    header = theme.make_surface_header("Some Material")

    assert header.title_label.property("role") == "title"
    assert header.subtitle_label is None


def test_make_surface_header_supports_a_different_title_role_variant(qapp):
    header = theme.make_surface_header("Material Library", subtitle="Study archive", title_role="page_title")

    assert header.title_label.property("role") == "page_title"
    assert header.subtitle_label is not None
    assert header.subtitle_label.property("role") == "subtitle"


def test_make_card_title_uses_the_section_header_role_when_decorated(qapp):
    """M13 Due-Frame Polish, Axis 3: a decorated card's own title is a
    blue-ink section header (e.g. Guided Session's "SESSION DIAGNOSIS (so
    far)"), not a plain caption -- `section_header` existed in the shared
    QSS with zero real consumers before this."""
    frame, layout = theme.make_card("Session Diagnosis")

    title_label = layout.itemAt(0).widget()
    assert title_label.text() == "Session Diagnosis"
    assert title_label.property("role") == "section_header"


def test_make_card_title_stays_plain_caption_when_not_decorated(qapp):
    """Compact dialogs (decorated=False) keep the plain caption, matching
    the due frame's own restraint there."""
    frame, layout = theme.make_card("Scope", decorated=False)

    title_label = layout.itemAt(0).widget()
    assert title_label.property("role") == "caption"


def test_make_surface_header_subtitle_gets_a_sketch_flourish(qapp):
    """M13 Due-Frame Polish, Axis 3: the due-frame boards end this exact
    subtitle/caption line with a small blue-pencil flourish mark."""
    from listentrace.ui.widgets.notebook_paper import SketchFlourishWidget

    header = theme.make_surface_header("Material Library", subtitle="Study archive", title_role="page_title")

    title_col = header.top_bar.itemAt(0).layout()
    subtitle_row = title_col.itemAt(1).layout()
    widgets = [subtitle_row.itemAt(i).widget() for i in range(subtitle_row.count())]
    assert header.subtitle_label in widgets
    assert any(isinstance(w, SketchFlourishWidget) for w in widgets)


def test_make_surface_header_chips_get_their_own_roles(qapp):
    header = theme.make_surface_header("Title", chips=[("VIDEO", "badge_primary")])

    chip = header.title_row.itemAt(1).widget()
    assert chip.text() == "VIDEO"
    assert chip.property("role") == "badge_primary"


def test_button_icon_gap_is_within_the_documented_platform_tolerance(qapp):
    """QPushButton's native icon-to-text gap (QStyle::PM_ButtonMargin) has
    no supported QSS override -- documented as a bounded platform
    exception rather than claimed exact. Contrast with
    make_status_row(), where the same 6px contract IS enforced exactly via
    real layout spacing."""
    from PySide6.QtWidgets import QPushButton, QStyle

    button = QPushButton("Label")
    button.ensurePolished()
    margin = button.style().pixelMetric(QStyle.PixelMetric.PM_ButtonMargin, None, button)

    assert abs(margin - theme.ICON_TEXT_GAP_PX) <= theme.BUTTON_ICON_GAP_TOLERANCE_PX


def test_make_status_row_enforces_the_frozen_6px_icon_text_gap(qapp):
    row = theme.make_status_row("Active", "active")

    layout = row.layout()
    assert layout.spacing() == theme.ICON_TEXT_GAP_PX


def test_make_status_row_dot_is_the_frozen_10px_diameter(qapp):
    row = theme.make_status_row("Active", "active")

    dot_label = row.layout().itemAt(0).widget()
    assert dot_label.size().width() == 10
    assert dot_label.size().height() == 10


def test_ruled_list_row_size_hint_reserves_the_ruled_list_item_qss_chrome(qapp):
    """Regression for the SessionHistoryDialog/QuizHistoryDialog defect: a
    QListWidgetItem hosting a make_status_row() via setItemWidget() inside a
    role="ruled_list" list must reserve the ::item QSS's own vertical
    padding/border/margin on top of the row widget's natural height, or Qt
    squeezes the row widget (status dot + text) toward zero visible height
    and the QSS border-bottom/margin lines render through the item's own
    native text instead of below it."""
    row = theme.make_status_row("[active] started 2026-01-01 00:00", "active")

    hint = theme.ruled_list_row_size_hint(row)

    assert hint.width() == row.sizeHint().width()
    assert hint.height() == row.sizeHint().height() + theme.RULED_LIST_ITEM_VERTICAL_CHROME_PX
    assert hint.height() > row.sizeHint().height()


def test_apply_paper_shadow_full_tier_uses_the_frozen_parameters(qapp):
    frame = QFrame()

    theme.apply_paper_shadow(frame, "full")

    effect = frame.graphicsEffect()
    assert effect is not None
    assert effect.color().getRgb() == theme.qcolor("shadow_full").getRgb()
    assert (effect.xOffset(), effect.yOffset()) == (0, 3)
    assert effect.blurRadius() == 10


def test_apply_paper_shadow_mini_tier_uses_the_frozen_parameters(qapp):
    frame = QFrame()

    theme.apply_paper_shadow(frame, "mini")

    effect = frame.graphicsEffect()
    assert effect is not None
    assert effect.color().getRgb() == theme.qcolor("shadow_mini").getRgb()
    assert (effect.xOffset(), effect.yOffset()) == (0, 2)
    assert effect.blurRadius() == 6


def test_make_notebook_surface_gets_the_full_paper_shadow():
    frame, _layout = theme.make_notebook_surface("Title")

    assert frame.graphicsEffect() is not None


def test_make_mini_notebook_gets_the_mini_paper_shadow():
    frame, _layout = theme.make_mini_notebook("Playback")

    assert frame.graphicsEffect() is not None


def test_icon_search_paths_include_the_frozen_locations_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "ListenTrace.exe"
    fake_exe.touch()
    monkeypatch.setattr(theme.sys, "frozen", True, raising=False)
    monkeypatch.setattr(theme.sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(theme.sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)

    paths = theme._icon_search_paths()

    assert paths[0] == fake_exe.parent / "listentrace.ico"
    assert paths[1] == tmp_path / "meipass" / "listentrace.ico"


# ---------------------------------------------------------------------------
# M13 Stage B whole-product reconciliation contract tests
# ---------------------------------------------------------------------------


def test_title_role_matches_the_16px_major_title_contract():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QLabel[role="title"]')
    assert "font-size: 16px" in rule
    assert "font-weight: 700" in rule


def test_caption_role_matches_the_contract_and_does_not_rely_on_text_transform():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QLabel[role="caption"]')
    assert "font-size: 12px" in rule
    assert "font-weight: 600" in rule
    assert "letter-spacing: 0.4px" in rule
    assert theme.css("ink_caption") in rule
    assert "text-transform" not in rule


def test_notebook_doodle_tag_uses_the_handwriting_grammar():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QLabel[role="notebook_doodle_tag"]')
    assert theme.HANDWRITING_FONT_FAMILY in rule
    assert theme.css("handwritten_blue") in rule
    assert "font-size: 14px" in rule


def test_notebook_doodle_tag_renders_as_a_pinned_tape_stamp():
    """M13 Due-Frame-First Visual Polish, Axis 1/3/4: the approved due-frame
    boards render every notebook section label as a pinned tape/paper-slip,
    not plain colored text on the bare surface."""
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QLabel[role="notebook_doodle_tag"]')
    assert theme.css("tape_cream") in rule


def test_danger_button_ordinary_hover_is_not_filled_red():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QPushButton[role="danger"]:hover')
    assert theme.css("danger_subtle") in rule
    assert theme.css("danger") not in rule


def test_quiet_button_hover_has_a_real_background_not_text_color_only():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QPushButton[role="quiet"]:hover')
    assert theme.css("quiet_hover") in rule


def test_secondary_button_uses_the_canonical_paper_and_paper_edge():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QPushButton[role="secondary"] ')
    assert theme.css("surface_paper") in rule
    assert theme.css("paper_edge") in rule


def test_input_uses_paper_primary_and_paper_edge_not_generic_surface():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, "QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget")
    assert theme.css("surface_paper") in rule
    assert theme.css("paper_edge") in rule


def test_checkbox_and_radio_indicator_is_the_canonical_16px():
    sheet = theme.build_stylesheet("light")
    assert "width: 16px" in _qss_rule(sheet, "QCheckBox::indicator")
    assert "width: 16px" in _qss_rule(sheet, "QRadioButton::indicator")


def test_scrollbar_matches_the_10px_width_and_28px_minimum_thumb_contract():
    sheet = theme.build_stylesheet("light")
    assert "width: 10px" in _qss_rule(sheet, "QScrollBar:vertical")
    assert "min-height: 28px" in _qss_rule(sheet, "QScrollBar::handle:vertical")
    assert theme.css("scrollbar_thumb") in _qss_rule(sheet, "QScrollBar::handle ")


def test_base_list_selection_is_not_full_blue_white_enterprise_style():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, "QListWidget::item:selected, QListWidget::item:selected:active")
    assert "#FFFFFF" not in rule
    assert theme.css("accent_subtle") in rule
    assert theme.css("ink") in rule


def test_sidebar_surface_uses_the_dedicated_sidebar_token():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QWidget[surface="sidebar"]')
    assert theme.css("surface_sidebar") in rule


def test_workspace_surface_uses_surface_plain_not_desk_bg():
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QFrame[surface="workspace"]')
    assert theme.css("surface", "light") in rule
    assert theme.css("page", "light") not in rule


def test_hero_button_matches_the_40px_14px650_contract(qapp):
    button = QPushButton("Label")
    theme.apply_role(button, "primary")
    button.setProperty("hero", "true")

    assert _rendered_height(button) == 40
    sheet = theme.build_stylesheet("light")
    rule = _qss_rule(sheet, 'QPushButton[role="primary"][hero="true"]')
    assert "font-size: 14px" in rule


def test_spacing_scale_has_all_seven_canonical_tiers():
    assert (
        theme.SPACE_COMPACT,
        theme.SPACE_TIGHT,
        theme.SPACE_NORMAL,
        theme.SPACE_MEDIUM,
        theme.SPACE_SECTION,
        theme.SPACE_PAGE,
        theme.SPACE_LARGE,
    ) == (4, 6, 8, 12, 16, 24, 32)

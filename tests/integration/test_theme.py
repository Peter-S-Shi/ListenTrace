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


def test_icon_search_paths_include_the_frozen_locations_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "ListenTrace.exe"
    fake_exe.touch()
    monkeypatch.setattr(theme.sys, "frozen", True, raising=False)
    monkeypatch.setattr(theme.sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(theme.sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)

    paths = theme._icon_search_paths()

    assert paths[0] == fake_exe.parent / "listentrace.ico"
    assert paths[1] == tmp_path / "meipass" / "listentrace.ico"

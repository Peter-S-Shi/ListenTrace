from __future__ import annotations

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from listentrace.ui import theme


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


def test_qcolor_and_css_agree_on_the_same_token():
    color = theme.qcolor("accent")

    assert isinstance(color, QColor)
    assert color.name().upper() == theme.css("accent").upper()


def test_qcolor_handles_a_token_with_alpha():
    color = theme.qcolor("line")

    r, g, b, a = theme._TOKENS["line"]
    assert color.red() == r
    assert color.green() == g
    assert color.blue() == b
    assert color.alpha() == a
    assert "rgba(" in theme.css("line")


def test_accent_is_professional_blue():
    # M13 Frozen Contract: Professional Blue
    color = theme.qcolor("accent")
    assert color.blue() > color.red()
    assert color.blue() > color.green()
    assert theme.css("accent").upper() in ["#2563EB", "#3B82F6"]


def test_product_semantic_tokens_preserve_their_values():
    assert theme.css("cue_active").upper() == "#FFF3CD"
    assert theme.css("text_overlap").upper() == "#D0D0D0"
    assert theme.css("quiz_correct").upper() == "#16A34A"
    assert theme.css("quiz_incorrect").upper() == "#DC2626"
    assert theme.css("chart_axis").upper() == "#9CA3AF"
    assert theme.css("chart_text").upper() == "#374151"


def test_get_app_icon_returns_a_real_icon_when_the_packaging_asset_exists():
    icon = theme.get_app_icon()

    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_get_app_icon_degrades_gracefully_when_no_candidate_path_exists(monkeypatch):
    monkeypatch.setattr(theme, "_icon_search_paths", lambda: [])

    icon = theme.get_app_icon()

    assert isinstance(icon, QIcon)
    assert icon.isNull()


def test_icon_search_paths_include_the_frozen_locations_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "ListenTrace.exe"
    fake_exe.touch()
    monkeypatch.setattr(theme.sys, "frozen", True, raising=False)
    monkeypatch.setattr(theme.sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(theme.sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)

    paths = theme._icon_search_paths()

    assert paths[0] == fake_exe.parent / "listentrace.ico"
    assert paths[1] == tmp_path / "meipass" / "listentrace.ico"

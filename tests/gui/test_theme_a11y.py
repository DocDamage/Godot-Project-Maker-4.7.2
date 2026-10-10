from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QSlider,
    QTabBar,
    QTableWidget,
    QToolButton,
    QWidget,
)

from rpggen import dev
from rpggen.core import app_settings, config
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import theme, workers
from rpggen.gui.pages.archetype_page import ArchetypePage
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.pages.generate_page import GeneratePage
from rpggen.gui.pages.mapping_page import MappingPage
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.pages.welcome_page import WelcomePage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import asset_grid as ag

GUI = Path(ag.__file__).parents[1]
SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _luminance(hex_colour: str) -> float:
    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _selectors(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"([^{}]+)\{", text)]


def test_the_template_renders_for_both_themes_with_the_same_selectors() -> None:
    dark, light = theme.stylesheet("dark"), theme.stylesheet("light")
    assert _selectors(dark) == _selectors(light) and len(_selectors(dark)) > 100
    for rendered in (dark, light):
        outside_urls = re.sub(r"url\([^)]*\)", "", rendered)
        assert "@" not in outside_urls  # no placeholder is left
        assert "/*" not in rendered
        for path in re.findall(r"url\(([^)]*)\)", rendered):
            assert Path(path).is_file(), path  # every icon the stylesheet names was written
    assert theme.TOKENS["dark"]["accent"] in dark and theme.TOKENS["light"]["accent"] in light
    assert theme.stylesheet("nonsense") == dark  # unknown: the dark theme


def test_a_placeholder_that_is_not_a_token_stops_the_rendering() -> None:
    with pytest.raises(KeyError, match="acent"):
        theme.render("QLabel { color: @acent; }", "dark")
    with pytest.raises(KeyError, match="no icon"):
        theme.render("QLabel { image: url(@icon(no-such-icon, text)); }", "dark")
    with pytest.raises(KeyError, match="not a token"):
        theme.render("QLabel { image: url(@icon(check, no_such_colour)); }", "dark")
    assert theme.render("/* @nothing here */ QLabel { margin: @space_8; }", "light").strip() == (
        "QLabel { margin: 8px; }"
    )


def test_both_themes_have_the_same_tokens_and_every_token_is_used() -> None:
    assert set(theme.TOKENS["dark"]) == set(theme.TOKENS["light"])
    template = theme.template_text()
    python = "".join(path.read_text(encoding="utf-8") for path in GUI.rglob("*.py"))
    theme_py = (GUI / "theme.py").read_text(encoding="utf-8")
    used_in_theme = theme_py.split("def crisp_scale")[1]  # past the tables themselves
    for name in list(theme.TOKENS["dark"]) + list(theme.SIZES):
        in_template = re.search(rf"@{name}\b", template) or re.search(
            rf"@icon\([a-z0-9-]+,\s*{name}\)", template
        )
        in_python = f'"{name}"' in python.replace(theme_py, used_in_theme)
        assert in_template or in_python, f"the token {name} is read by nobody"


@pytest.mark.parametrize("name", ["dark", "light"])
def test_the_tokens_meet_the_contrast_rules(name: str) -> None:
    tokens = theme.TOKENS[name]
    for surface in ("bg", "base", "surface", "surface_hover"):
        assert _contrast(tokens["text"], tokens[surface]) >= 4.5, surface
        assert _contrast(tokens["text_muted"], tokens[surface]) >= 4.5, surface
    for surface in ("bg", "surface"):
        assert _contrast(tokens["border_strong"], tokens[surface]) >= 3.0, surface
        assert _contrast(tokens["focus"], tokens[surface]) >= 3.0, surface
        for state in ("danger", "warning", "success", "accent"):
            assert _contrast(tokens[state], tokens[surface]) >= 4.5, (state, surface)
    for fill in ("accent", "accent_hover", "accent_pressed"):
        assert _contrast(tokens["on_accent"], tokens[fill]) >= 4.5, fill
    for fill in ("danger", "warning", "success"):
        assert _contrast(tokens["on_status"], tokens[fill]) >= 4.5, fill


@pytest.mark.parametrize("name", ["dark", "light"])
def test_every_rule_with_a_colour_and_a_background_is_readable(name: str) -> None:
    """A small parser over the rendered stylesheet: a rule that sets both ``color`` and
    ``background`` to plain colours must reach 4.5:1 (3:1 for a disabled look, which only has
    to be told apart). Rules without both are judged by the token test above."""
    rendered = theme.stylesheet(name)
    checked = 0
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", rendered):
        props = dict(
            (key.strip(), value.strip())
            for key, _, value in (line.partition(":") for line in body.split(";"))
            if value
        )
        colour, background = props.get("color"), props.get("background")
        if not (colour and background):
            continue
        if not (
            re.fullmatch(r"#[0-9a-f]{6}", colour) and re.fullmatch(r"#[0-9a-f]{6}", background)
        ):
            continue
        need = 3.0 if ":disabled" in selector else 4.5
        assert _contrast(colour, background) >= need, (selector.strip(), colour, background)
        checked += 1
    assert checked >= 10


def test_the_palette_reads_the_same_tokens_as_the_stylesheet() -> None:
    for name in theme.THEMES:
        pal = theme.palette(name)
        tokens = theme.TOKENS[name]
        assert pal.color(QPalette.ColorRole.Window).name() == tokens["bg"]
        assert pal.color(QPalette.ColorRole.Base).name() == tokens["base"]
        assert pal.color(QPalette.ColorRole.Highlight).name() == tokens["accent"]
        assert pal.color(QPalette.ColorRole.PlaceholderText).name() == tokens["text_muted"]
        assert pal.color(QPalette.ColorRole.Link).name() == tokens["accent"]
    assert theme.px("radius_card") == 10 and theme.px("control_height") == 30
    assert theme.color("grid_line", "dark").alpha() == 150  # a colour with transparency


@pytest.mark.parametrize("name", ["dark", "light"])
def test_every_status_colour_stands_out_from_both_backgrounds(name: str) -> None:
    for status, colour in ag.STATUS_COLORS.items():
        for theme_name, background in theme.BACKGROUNDS.items():
            assert _contrast(colour, background) >= 3.0, (status, theme_name)
    base = theme.palette(name).color(QPalette.ColorRole.Base).name()
    assert base == theme.BACKGROUNDS[name]  # the palette really uses the background tested


def test_switching_the_theme_changes_the_palette_and_is_remembered(qtbot) -> None:
    app = QApplication.instance()
    theme.apply_theme("light")
    assert app.palette().color(QPalette.ColorRole.Base).name() == "#ffffff"
    assert theme.TOKENS["light"]["accent"] in app.styleSheet()
    assert app_settings.load().theme == "light"
    theme.apply_theme("dark")
    assert app.palette().color(QPalette.ColorRole.Base).name() == theme.BACKGROUNDS["dark"]
    assert theme.apply_theme("nonsense") == "dark"  # unknown: back to dark


def test_status_is_not_colour_only() -> None:
    assert set(ag.STATUS_GLYPHS) >= set(ag.STATUS_COLORS)
    assert ag.STATUS_GLYPHS["CONFIRMED"] == "✔" and ag.STATUS_GLYPHS["CONFLICT"] == "!"
    assert ag.STATUS_GLYPHS["NEEDS_REVIEW"] == "?" and ag.STATUS_GLYPHS["MISSING"] == "∅"


# ------------------------------------------------------------------------ tooltips and names


def _pages(qtbot):
    state = WizardState(pack_sources=[SYNTH / "basic16"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    ref = config.PackRef("basic16", str(SYNTH / "basic16"), "0" * 64, "folder")
    state.config = config.default_for("T", [ref])
    pages = [
        ProjectPage(),
        ArchetypePage(),
        AuditPage(),
        MappingPage(),
        OptionsPage(),
        GeneratePage(),
        ResultsPage(),
        WelcomePage(),
    ]
    for page in pages:
        qtbot.addWidget(page)
        page.resize(1100, 800)
        page.show()
        if hasattr(page, "enter"):
            page.enter(state)
    return pages


def _interactive(widget: QWidget) -> bool:
    if isinstance(widget, QToolButton) and isinstance(widget.parentWidget(), QTabBar | QLineEdit):
        return False  # tab scroll arrows and the clear button of a line edit
    return (
        isinstance(
            widget,
            QAbstractButton
            | QAbstractSpinBox
            | QComboBox
            | QLineEdit
            | QSlider
            | QListWidget
            | QTableWidget,
        )
        and not widget.objectName().startswith("qt_")
        and widget.parent() is not None
    )


def _labelled(widget: QWidget) -> bool:
    """A tooltip, an accessible name, the visible text of a button, or a label that points at it."""
    if widget.toolTip() or widget.accessibleName():
        return True
    if isinstance(widget, QAbstractButton) and widget.text().strip():
        return True
    if isinstance(widget, QLineEdit) and widget.placeholderText():
        return True
    parent = widget.parentWidget()
    while parent is not None:
        for label in parent.findChildren(QLabel):
            if label.buddy() is widget:
                return True
        parent = parent.parentWidget()
    # a spin box or combo inside a composite editor is named by the editor
    node = widget.parentWidget()
    while node is not None:
        if node.toolTip() or node.accessibleName():
            return True
        node = node.parentWidget()
    return False


def test_every_interactive_widget_has_a_tooltip_a_name_or_a_label(qtbot) -> None:
    missing: list[str] = []
    for page in _pages(qtbot):
        for widget in page.findChildren(QWidget):
            if _interactive(widget) and not _labelled(widget):
                missing.append(
                    f"{type(page).__name__}: {widget.objectName() or type(widget).__name__}"
                )
    assert not missing, missing


def test_the_main_buttons_have_mnemonic_shortcuts(qtbot) -> None:
    from rpggen.gui.wizard import MainWindow, default_pages

    win = MainWindow(pages=default_pages())
    qtbot.addWidget(win)
    assert win.next_button.shortcut().toString() == "Alt+N"
    assert win.back_button.shortcut().toString() == "Alt+B"
    assert win.next_button.toolTip() and win.back_button.toolTip() and win.quit_button.toolTip()


def test_tab_order_runs_through_the_project_page_fields(qtbot) -> None:
    page = ProjectPage()
    qtbot.addWidget(page)
    page.show()
    order: list[QWidget] = []
    widget = page.pack_list
    for _ in range(40):
        order.append(widget)
        widget = widget.nextInFocusChain()
        if widget is page.pack_list:
            break
    names = [w.objectName() for w in order]
    assert names.index("targetEdit") < names.index("godotCombo") < names.index("nameEdit")


def test_the_archetype_cards_show_a_check_when_chosen(qtbot) -> None:
    page = ArchetypePage()
    qtbot.addWidget(page)
    page.show()
    page.enter(WizardState())
    assert not page.turn_card.check_label.isHidden() and page.arpg_card.check_label.isHidden()
    page.arpg_card.click()
    assert not page.arpg_card.check_label.isHidden() and page.turn_card.check_label.isHidden()
    assert "Controls" in page.arpg_card.bullet_label.text() or page.arpg_card.bullet_label.text()
    assert "other kind later" in page.same_label.text()


# ------------------------------------------------------------------------ T12.42: system theme


def test_the_system_theme_follows_a_faked_scheme_change(qtbot, monkeypatch) -> None:
    app = QApplication.instance()
    scheme = {"now": "dark"}
    monkeypatch.setattr(theme, "system_scheme", lambda: scheme["now"])
    seen: list[str] = []
    theme.signals.changed.connect(seen.append)
    try:
        assert theme.apply_theme("system", remember=False) == "system"
        assert theme.current() == "dark"
        assert app.palette().color(QPalette.ColorRole.Base).name() == theme.BACKGROUNDS["dark"]
        scheme["now"] = "light"
        theme.on_system_scheme_changed()  # what the colorSchemeChanged signal calls
        assert theme.current() == "light" and seen[-1] == "light"
        assert app.palette().color(QPalette.ColorRole.Base).name() == theme.BACKGROUNDS["light"]
        theme.apply_theme("dark", remember=False)  # an explicit choice does not follow
        scheme["now"] = "dark"
        scheme["now"] = "light"
        theme.on_system_scheme_changed()
        assert theme.current() == "dark"
    finally:
        theme.signals.changed.disconnect(seen.append)
        theme.apply_theme("dark", remember=False)


def test_a_first_run_follows_the_system_and_a_saved_choice_is_kept(tmp_path) -> None:
    import json

    assert app_settings.AppSettings().theme == "system"
    assert "system" in app_settings.THEMES
    kept = tmp_path / "settings.json"
    kept.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    assert app_settings.from_json(json.loads(kept.read_text(encoding="utf-8"))).theme == "light"
    assert app_settings.from_json({}).theme == "system"
    assert app_settings.from_json({"theme": "nonsense"}).theme == "system"


def test_the_canvas_colour_differs_between_themes_and_views_follow(qtbot) -> None:
    from rpggen.gui.widgets.image_view import ImageView

    assert theme.token("canvas_bg", "dark") != theme.token("canvas_bg", "light")
    assert theme.token("canvas_bg_alt", "dark") != theme.token("canvas_bg_alt", "light")
    assert theme.token("grid_line", "dark") != theme.token("grid_line", "light")
    view = ImageView()
    qtbot.addWidget(view)
    try:
        theme.apply_theme("light", remember=False)
        assert view.backgroundBrush().color() == theme.token("canvas_bg", "light")
        theme.apply_theme("dark", remember=False)
        assert view.backgroundBrush().color() == theme.token("canvas_bg", "dark")
    finally:
        theme.apply_theme("dark", remember=False)


def test_the_light_canvases_are_light_enough_for_dark_text(qtbot) -> None:
    for name in ("canvas_bg", "canvas_bg_alt"):
        assert theme.token(name, "light").lightness() > 180
        assert theme.token(name, "dark").lightness() < 100


def test_the_menu_offers_the_system_theme(qtbot) -> None:
    from rpggen.gui.wizard import MainWindow, stub_pages

    win = MainWindow(None, stub_pages())
    qtbot.addWidget(win)
    assert set(win.theme_actions) == {"system", "dark", "light"}
    win.theme_actions["system"].trigger()
    assert app_settings.get().theme == "system"
    win.set_theme("dark")
    assert app_settings.get().theme == "dark"


# ------------------------------------------------------------------------ scaling, names, motion, taskbar (T13.10)


def _tile_png(tmp_path: Path, size: int = 16) -> Path:
    from PIL import Image

    path = tmp_path / "tile.png"
    image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    for i in range(size):
        image.putpixel((i, i), (255, 255, 255, 255))
    image.save(path)
    return path


def test_at_ratio_2_a_16_px_tile_is_a_32_px_device_image(qtbot, tmp_path, monkeypatch) -> None:
    from PySide6.QtGui import QPixmap

    from rpggen.gui import thumbnails

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    tile = _tile_png(tmp_path)
    facets = {"usage": "object"}
    one = thumbnails.request_for("ab" * 32, tile, facets, size=16)
    two = thumbnails.request_for("ab" * 32, tile, facets, size=16, ratio=2.0)
    assert one.size == 16 and two.size == 32 and one.key != two.key, "the key has the ratio"
    assert thumbnails.request_for("ab" * 32, tile, facets, size=16, ratio=1.0).key == one.key
    data = thumbnails.load_or_render(two)
    assert data is not None
    pixmap = thumbnails.pixmap_from_bytes(data, 2.0)
    assert (pixmap.width(), pixmap.height()) == (32, 32), "device pixels"
    assert pixmap.devicePixelRatio() == 2.0
    assert pixmap.deviceIndependentSize().toSize().width() == 16, "16 px in the window"
    # every image pixel is exactly 2 x 2 device pixels: nothing is blended
    image = pixmap.toImage()
    assert image.pixelColor(0, 0) == image.pixelColor(1, 1) == QColor(255, 255, 255)
    assert image.pixelColor(2, 0) == image.pixelColor(3, 1) == QColor(0, 0, 0)
    assert isinstance(pixmap, QPixmap)
    # 150 %: a 96 px box has 144 device pixels, and a 16 px tile fills them 9 times over
    request = thumbnails.request_for("cd" * 32, tile, facets, size=96, ratio=1.5)
    assert request.size == 144
    rendered = thumbnails.pixmap_from_bytes(thumbnails.load_or_render(request), 1.5)
    assert rendered.width() == 144 and rendered.width() % 16 == 0


def test_the_grid_asks_for_pictures_of_its_screen_and_draws_them_at_window_size(qtbot) -> None:
    from PySide6.QtCore import QSize

    from rpggen.gui.widgets import asset_grid as ag

    model = ag.AssetListModel()
    assert model.ratio == 1.0
    model.set_device_ratio(2.0)
    assert model.ratio == 2.0 and len(model.cache) == 0
    model.set_device_ratio(0)  # a nonsense ratio is 1
    assert model.ratio == 1.0
    # the card fits the picture by its size in the window, not by its device pixels
    pixmap = QPixmap(192, 192)
    pixmap.setDevicePixelRatio(2.0)
    logical = pixmap.deviceIndependentSize().toSize()
    assert logical == QSize(96, 96)
    assert ag.AssetCardDelegate.fit(logical, QSize(96, 96)).size() == QSize(96, 96)


def test_whole_device_pixels_at_every_scaling() -> None:
    assert theme.crisp_scale(3.0, 1.0) == 3.0
    assert theme.crisp_scale(3.0, 2.0) == 3.0
    for ratio in (1.25, 1.5, 1.75, 2.0, 2.5):
        for scale in (1.0, 2.0, 3.0, 5.0, 7.0):
            crisp = theme.crisp_scale(scale, ratio)
            device = crisp * ratio
            assert abs(device - round(device)) < 1e-6 and round(device) >= 1, (scale, ratio)
            assert crisp <= scale + 1e-9 and scale - crisp < 1 / ratio + 1e-9
    assert theme.crisp_scale(0.25, 1.5) == 0.25, "a picture shown smaller is left alone"
    assert theme.device_size(96, 1.5) == 144 and theme.device_size(0, 2.0) == 1


def test_the_overlay_lines_are_one_device_pixel(qtbot, tmp_path) -> None:
    from rpggen.gui.widgets.image_view import ImageView

    view = ImageView()
    qtbot.addWidget(view)
    view.resize(300, 300)
    view.show()
    view.set_image(
        _tile_png(tmp_path, 32), {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}
    )
    view.draw_marks([("footprint", 0, 16, 32, 16), ("origin", 16, 30, 0, 0)])
    lines = [item for item in view.grid_items + view.mark_items if hasattr(item, "pen")]
    assert lines
    for item in lines:
        pen = item.pen()
        if pen.style() != Qt.PenStyle.NoPen:
            assert pen.isCosmetic(), "a cosmetic pen keeps its width at any zoom and scaling"
    grid_lines = [i for i in view.grid_items if hasattr(i, "line")]
    assert grid_lines and all(i.pen().width() <= 1 for i in grid_lines)
    assert view.zoom == theme.crisp_scale(view.zoom, view.devicePixelRatioF())


def test_every_grid_cell_has_an_accessible_name(qtbot) -> None:
    from rpggen.core import archive, catalog, inventory
    from rpggen.gui.widgets import asset_grid as ag

    synth = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
    opened = archive.open_pack(synth / "basic16", set())
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    grid = ag.AssetGrid()
    qtbot.addWidget(grid)
    grid.set_catalog(cat, lambda asset: None)
    grid.chips["chipAll"].click()
    for row in range(grid.proxy.rowCount()):
        index = grid.proxy.index(row, 0)
        name = index.data(Qt.ItemDataRole.AccessibleTextRole)
        asset = cat.asset(index.data(ag.AssetIdRole))
        assert name.startswith(asset.path.rsplit("/", 1)[-1]), name
        assert name.endswith(asset.status.replace("_", " ").lower()), name
        assert index.data(Qt.ItemDataRole.AccessibleDescriptionRole) == asset.path
    hero = grid.model.index(grid.model.row_of("basic16.characters.hero"), 0)
    assert hero.data(Qt.ItemDataRole.AccessibleTextRole) == (
        "hero.png, Sprite or character, Player, needs review"
    )
    # a folder header says which folder it is
    grid.set_grouped(True)
    header = next(
        grid.proxy.index(r, 0)
        for r in range(grid.proxy.rowCount())
        if grid.proxy.index(r, 0).data(ag.HeaderRole) is not None
    )
    assert header.data(Qt.ItemDataRole.AccessibleTextRole).startswith("basic16 / ")


def _tab_stops(root: QWidget) -> list[QWidget]:
    """The controls of ``root`` a user would expect to reach with Tab."""
    from PySide6.QtWidgets import QAbstractItemView, QAbstractSlider

    kinds = (QAbstractButton, QComboBox, QLineEdit, QAbstractSpinBox, QAbstractItemView)
    out = []
    for widget in root.findChildren(QWidget):
        if not isinstance(widget, kinds + (QAbstractSlider,)) or not widget.isVisibleTo(root):
            continue
        if not widget.isEnabled() or widget.objectName().startswith("qt_"):
            continue
        parent = widget.parentWidget()
        if isinstance(parent, QComboBox | QAbstractSpinBox | QAbstractItemView | QLineEdit):
            continue  # the line edit of a combo, the buttons of a spin box, a combo's list,
            # the icon and the clear button inside a line edit
        if isinstance(widget, QAbstractSlider) and widget.objectName() == "":
            continue  # a scroll bar
        out.append(widget)
    return out


@pytest.mark.parametrize("archetype", dev.LAYOUT_ARCHETYPES)
def test_tab_reaches_every_control_on_every_page_and_the_welcome_view(
    qtbot, tmp_path, archetype: str
) -> None:
    from PySide6.QtWidgets import QApplication

    from rpggen.gui.wizard import MainWindow, default_pages

    window = MainWindow(dev.layout_state(archetype, tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(1100, 720)
    window.show()
    unreachable: list[str] = []

    def check(page_name: str, win: MainWindow) -> None:
        current = win.welcome if win.welcome_visible else win.current_page
        QApplication.processEvents()
        stops = _tab_stops(current)
        assert stops, page_name
        # the focus chain of the window, as Tab walks it
        chain: set[QWidget] = set()
        widget = current
        for _ in range(5000):
            widget = widget.nextInFocusChain()
            if widget is current or widget is None:
                break
            if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.isEnabled():
                chain.add(widget)
        for stop in stops:
            if stop not in chain:
                name = (
                    stop.objectName() or f"{type(stop).__name__}({getattr(stop, 'text', str)()!r})"
                )
                unreachable.append(f"{page_name}: {name}")

    dev.show_each_page(window, check)
    assert not unreachable, "\n".join(unreachable)


def test_reduce_motion_follows_the_system_until_it_is_set(qtbot, monkeypatch) -> None:
    from rpggen.gui.wizard import MainWindow, default_pages

    # what Qt is told: whether an effect really shows also depends on the platform, so the
    # test reads the calls and not Qt's answer
    effects: dict[Qt.UIEffect, bool] = {}
    monkeypatch.setattr(
        QApplication, "setEffectEnabled", lambda effect, on=True: effects.__setitem__(effect, on)
    )
    assert app_settings.get().reduce_motion == "system"
    monkeypatch.setattr(theme, "system_reduces_motion", lambda: True)
    assert theme.reduce_motion() and theme.apply_motion()
    assert effects[Qt.UIEffect.UI_AnimateMenu] is False
    assert effects[Qt.UIEffect.UI_FadeTooltip] is False and len(effects) == 6
    monkeypatch.setattr(theme, "system_reduces_motion", lambda: False)
    assert not theme.apply_motion()
    assert all(effects.values())
    win = MainWindow(pages=default_pages())
    qtbot.addWidget(win)
    assert win.motion_action.isCheckable() and not win.motion_action.isChecked()
    win.motion_action.trigger()
    assert app_settings.load().reduce_motion == "on" and win.motion_action.isChecked()
    assert not any(effects.values())
    monkeypatch.setattr(theme, "system_reduces_motion", lambda: True)
    win.motion_action.trigger()  # off, although the system asks for it: the choice is yours
    assert app_settings.load().reduce_motion == "off" and not theme.reduce_motion()
    assert all(effects.values())
    path = app_settings.settings_path()
    path.write_text('{"reduce_motion": "sometimes"}', encoding="utf-8")
    assert app_settings.load().reduce_motion == "system"


def test_the_taskbar_is_a_no_op_elsewhere_and_when_the_call_fails(monkeypatch) -> None:
    from rpggen.gui import taskbar

    class Window:
        def winId(self) -> int:  # noqa: N802
            return 1234

    # Linux: nothing to do, nothing raised
    monkeypatch.setattr(taskbar.sys, "platform", "linux")
    assert taskbar.set_progress(Window(), 3, 11) is False
    assert taskbar.clear(Window()) is False
    # Windows without a working COM object
    monkeypatch.setattr(taskbar.sys, "platform", "win32")
    monkeypatch.setattr(taskbar, "_taskbar", None)
    monkeypatch.setattr(taskbar, "_broken", False)

    def boom() -> None:
        raise OSError("no COM here")

    monkeypatch.setattr(taskbar, "_WindowsTaskbar", boom)
    assert taskbar.set_progress(Window(), 3, 11) is False
    assert taskbar._broken, "it is not tried again in this run"
    assert taskbar.clear(Window()) is False
    # a COM object whose calls fail
    calls: list[tuple] = []

    class Failing:
        def set_state(self, hwnd: int, state: int) -> None:
            calls.append(("state", hwnd, state))
            raise OSError("E_FAIL")

        def set_value(self, hwnd: int, done: int, total: int) -> None:
            calls.append(("value", hwnd, done, total))

    monkeypatch.setattr(taskbar, "_taskbar", Failing())
    monkeypatch.setattr(taskbar, "_broken", False)
    assert taskbar.set_progress(Window(), 3, 11) is False
    assert calls == [("state", 1234, taskbar.TBPF_NORMAL)]
    # ... and one that works gets the state and the clamped value
    calls.clear()

    class Working(Failing):
        def set_state(self, hwnd: int, state: int) -> None:
            calls.append(("state", hwnd, state))

    monkeypatch.setattr(taskbar, "_taskbar", Working())
    monkeypatch.setattr(taskbar, "_broken", False)
    assert taskbar.set_progress(Window(), 30, 11) is True
    assert calls == [("state", 1234, taskbar.TBPF_NORMAL), ("value", 1234, 11, 11)]
    assert taskbar.set_progress(Window(), 1, 0) is False, "no total: nothing to show"
    assert taskbar.set_progress(None, 1, 5) is False, "no window"
    calls.clear()
    assert taskbar.clear(Window(), failed=True) is True
    assert calls == [("state", 1234, taskbar.TBPF_ERROR)]
    # macOS: the dock badge, or nothing where Qt has none
    monkeypatch.setattr(taskbar.sys, "platform", "darwin")
    badges: list[int] = []
    monkeypatch.setattr(taskbar, "_badge", badges.append)
    assert taskbar.set_progress(Window(), 4, 11) and taskbar.clear(Window())
    assert badges == [7, 0]

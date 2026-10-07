from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtGui import QPalette
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


def test_the_two_stylesheets_have_the_same_selectors_and_status_colours() -> None:
    dark = (GUI / "style.qss").read_text(encoding="utf-8")
    light = (GUI / "style_light.qss").read_text(encoding="utf-8")

    def selectors(text: str) -> list[str]:
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return re.findall(r"([^{}]+)\{", body)

    assert [s.strip() for s in selectors(dark)] == [s.strip() for s in selectors(light)]
    block = re.compile(r"status-colors.*?\n(.*?)\*/", re.S)
    assert block.search(dark).group(1) == block.search(light).group(1)  # the same in both


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
    assert "e6e9ee" in app.styleSheet()
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
    return isinstance(
        widget,
        QAbstractButton | QAbstractSpinBox | QComboBox | QLineEdit | QSlider | QListWidget | QTableWidget,
    ) and not widget.objectName().startswith("qt_") and widget.parent() is not None


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
                missing.append(f"{type(page).__name__}: {widget.objectName() or type(widget).__name__}")
    assert not missing, missing


def test_the_main_buttons_have_mnemonic_shortcuts(qtbot) -> None:
    from rpggen.gui.wizard import MainWindow, default_pages

    win = MainWindow(pages=default_pages())
    qtbot.addWidget(win)
    assert win.next_button.shortcut().toString() == "Alt+N"
    assert win.back_button.shortcut().toString() == "Alt+B"
    assert win.next_button.toolTip() and win.back_button.toolTip() and win.cancel_button.toolTip()


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

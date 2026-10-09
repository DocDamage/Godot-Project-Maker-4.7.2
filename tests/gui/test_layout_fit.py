"""T12.16: no wizard page squeezes a widget below its minimum size or clips a button or combo.

The sample pack is analysed (no Godot is needed) and every page is shown inside the real window,
for both archetypes, both themes and two window sizes. A failure names the page and the widget.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionToolButton,
    QTabBar,
    QToolButton,
    QWidget,
)

from rpggen import dev
from rpggen.gui import app as gui_app
from rpggen.gui import theme
from rpggen.gui.wizard import MainWindow, default_pages

SIZES = dev.layout_sizes()


@pytest.fixture(autouse=True)
def _real_font(qapp):
    """Offscreen Qt on Windows draws every glyph as a box about twice as wide as a letter, so the
    layouts are measured with a real font and the application's own font comes back afterwards."""
    gui_app.create_app()
    original = QApplication.font()
    if dev.ensure_real_font() is None:
        pytest.skip("no real font on this machine")
    yield
    QApplication.setFont(original)
    theme.apply_theme("dark", remember=False)


def _inside_scroll_area(widget: QWidget) -> bool:
    """A widget in a scroll area's viewport may be larger than what is shown."""
    node = widget.parentWidget()
    while node is not None:
        if isinstance(node, QAbstractScrollArea):
            return True
        node = node.parentWidget()
    return False


def _effective_minimum(widget: QWidget) -> QSize:
    """What the layouts ask for: an explicit minimum size, else the widget's own hint."""
    hint = widget.minimumSizeHint()
    policy = widget.sizePolicy()
    width = widget.minimumWidth() or (
        0 if policy.horizontalPolicy() == QSizePolicy.Policy.Ignored else max(hint.width(), 0)
    )
    height = widget.minimumHeight() or (
        0 if policy.verticalPolicy() == QSizePolicy.Policy.Ignored else max(hint.height(), 0)
    )
    return QSize(width, height)


def _text_clipped(widget: QWidget) -> str | None:
    """A sentence when the shown text of a combo or a button needs more room than it has."""
    style = widget.style()
    if isinstance(widget, QComboBox):
        if widget.isEditable():
            return None  # its text scrolls, as in a line edit (a long path is fine)
        option = QStyleOptionComboBox()
        widget.initStyleOption(option)
        field = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            widget,
        )
        need = widget.fontMetrics().horizontalAdvance(widget.currentText())
        if need > field.width():
            return f"combo text {widget.currentText()!r} needs {need} px, has {field.width()}"
        return None
    text = widget.text().replace("&", "") if isinstance(widget, QPushButton | QToolButton) else ""
    if not text:
        return None
    need = widget.fontMetrics().horizontalAdvance(text)
    if isinstance(widget, QPushButton):
        button = QStyleOptionButton()
        widget.initStyleOption(button)
        room = style.subElementRect(QStyle.SubElement.SE_PushButtonContents, button, widget).width()
    else:
        tool = QStyleOptionToolButton()
        widget.initStyleOption(tool)
        room = style.subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            tool,
            QStyle.SubControl.SC_ToolButton,
            widget,
        ).width()
        if widget.menu() is not None:
            room -= 14  # the arrow of a menu button
    if need > room:
        return f"button text {text!r} needs {need} px, has {room}"
    return None


def layout_problems(root: QWidget) -> list[str]:
    """Every visible widget of ``root`` below its minimum size or with clipped text."""
    problems: list[str] = []
    for widget in root.findChildren(QWidget):
        name = widget.objectName()
        if not widget.isVisible() or name.startswith("qt_") or isinstance(widget, QScrollBar):
            continue
        if isinstance(widget.parentWidget(), QTabBar | QComboBox | QAbstractSpinBox):
            continue  # the scroll arrows of a tab bar, the editor of a combo: Qt places those
        if _inside_scroll_area(widget):
            continue
        need = _effective_minimum(widget)
        label = f"{type(widget).__name__} '{name}'"
        if isinstance(widget, QLabel) and not name:
            label += f" ({widget.text()[:30]!r})"
        if widget.width() < need.width() or widget.height() < need.height():
            problems.append(
                f"{label} is {widget.width()}x{widget.height()}, needs "
                f"{need.width()}x{need.height()}"
            )
        clipped = _text_clipped(widget)
        if clipped:
            problems.append(f"{label}: {clipped}")
    return problems


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
@pytest.mark.parametrize("archetype", dev.LAYOUT_ARCHETYPES)
def test_no_page_squeezes_or_clips_a_widget(
    qtbot, tmp_path: Path, archetype: str, theme_name: str, size: str
) -> None:
    theme.apply_theme(theme_name, remember=False)
    state = dev.layout_state(archetype, tmp_path)
    # a long Godot path, as CI's temporary folders give: it must not widen the window
    state.godot_exe = tmp_path / ("very_long_folder_name_" * 6) / "Godot_v4.7.2-stable_win64.exe"
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    width, height = SIZES[size]
    window.resize(width, height)
    window.show()
    QApplication.processEvents()
    found: list[str] = []

    def check(page_name: str, win: MainWindow) -> None:
        current = win.welcome if win.welcome_visible else win.current_page
        found.extend(f"{page_name}: {p}" for p in layout_problems(current))

    dev.show_each_page(window, check)
    assert not found, f"{archetype}/{theme_name}/{size}:\n" + "\n".join(found)


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_the_audit_page_fits_with_the_grid_grouped_by_folder(
    qtbot, tmp_path: Path, theme_name: str, size: str
) -> None:
    """T13.02: the Group by folder toggle on the filter bar, and the grid with header rows."""
    from rpggen.gui.pages.audit_page import AuditPage

    theme.apply_theme(theme_name, remember=False)
    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    audit = next(p for p in window.pages if isinstance(p, AuditPage))
    window.show_page(window.pages.index(audit))
    audit.grid.set_grouped(True)
    audit.grid.chips["chipAll"].click()
    for _ in range(3):
        QApplication.processEvents()
    assert audit.grid.header_keys()
    assert layout_problems(audit) == []


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
@pytest.mark.parametrize("archetype", ["turn_based", "arpg"])
def test_the_audit_page_fits_in_review_mode_with_folder_groups(
    qtbot, tmp_path: Path, archetype: str, theme_name: str, size: str
) -> None:
    """The 1.1 gate: T12.16 with review mode and folder groups on, both themes, both archetypes."""
    from rpggen.gui.pages.audit_page import AuditPage

    theme.apply_theme(theme_name, remember=False)
    window = MainWindow(dev.layout_state(archetype, tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    audit = next(p for p in window.pages if isinstance(p, AuditPage))
    window.show_page(window.pages.index(audit))
    audit.grid.set_grouped(True)
    audit.grid.chips["chipAll"].click()
    audit.set_review_mode(True)
    for _ in range(3):
        QApplication.processEvents()
    assert audit.in_review_mode
    assert layout_problems(audit) == []
    audit.set_review_mode(False)
    for _ in range(3):
        QApplication.processEvents()
    assert layout_problems(audit) == []


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_the_options_page_fits_with_a_world_of_areas(
    qtbot, tmp_path: Path, theme_name: str, size: str
) -> None:
    """T13.20: the Areas table, the world preview and the button under it."""
    from rpggen.gui.pages.options_page import OptionsPage

    theme.apply_theme(theme_name, remember=False)
    window = MainWindow(dev.layout_state("turn_based", tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    options = next(p for p in window.pages if isinstance(p, OptionsPage))
    window.show_page(window.pages.index(options))
    box = options.starter_box
    box.areas.enable_box.setChecked(True)
    for name, biome in (("Woods", "forest"), ("Old mine", "cave")):
        box.areas.set_value(box.areas.add_row(name), "biome", biome)
    for _ in range(3):
        QApplication.processEvents()
    assert not box.world.isHidden() and box.world.plan is not None
    assert layout_problems(options) == []

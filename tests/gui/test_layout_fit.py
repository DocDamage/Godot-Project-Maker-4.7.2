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
    QLineEdit,
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
        if isinstance(widget.parentWidget(), QTabBar | QComboBox | QAbstractSpinBox | QLineEdit):
            continue  # the scroll arrows of a tab bar, the editor of a combo, the icon in a
            # search field: Qt places those
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
    qtbot, tmp_path: Path, monkeypatch, archetype: str, theme_name: str, size: str
) -> None:
    """The 1.1 gate: T12.16 with review mode and folder groups on, both themes, both archetypes."""
    from rpggen.gui.pages.audit_page import AuditPage

    # With a fresh settings folder the Audit page starts its first-run tour 0.4 s after it is
    # shown, and a tour leaves review mode. On a slow machine that timer fired in the middle of
    # this test (the Windows CI job); the tour is not what is measured here.
    monkeypatch.setattr(AuditPage, "maybe_start_tour", lambda self: False)
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


def _two_rows_in_view(page) -> None:  # noqa: ANN001 - an ArchetypePage in rows of three
    """T17.16, T17.33: eight cards in rows of three. Two rows are whole in the page's room and fill
    it, wherever the page has scrolled to (the chosen card is brought into view), and the rest
    scrolls. Under two lines of hints the room is too low for two rows of cards: every row is
    then as high as its cards need, and the page scrolls a little more."""
    cards = list(page.cards.values())
    room = page.cards_scroll.viewport().height()
    gap = page.cards_grid.verticalSpacing()
    assert page.columns == 3 and page.cards_box.height() > room
    tops = sorted({card.geometry().top() for card in cards})
    assert len(tops) == 3, "three rows"
    needs = page._row_needs(3)
    if needs[0] + gap + needs[1] <= room:
        assert tops[2] - tops[0] == room + gap, "two rows fill the room"
        assert max(card.geometry().bottom() for card in cards[:6]) < tops[0] + room
    else:
        assert [tops[1] - tops[0], tops[2] - tops[1]] == [needs[0] + gap, needs[1] + gap]
    at = page.cards_scroll.verticalScrollBar().value()
    chosen = page.cards[page.selected()].geometry()
    assert at <= chosen.top() and chosen.bottom() <= at + max(room, chosen.height())


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("archetype", dev.LAYOUT_ARCADE)
def test_the_pages_of_an_arcade_kind_fit(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archetype: str, size: str
) -> None:
    """T16.16: six cards on the Archetype page, the kind's roles on the Mapping page and its
    box with a preview on the Options page, at the minimum window and at the default one."""
    from rpggen import features
    from rpggen.gui.pages.archetype_page import ArchetypePage
    from rpggen.gui.pages.mapping_page import MappingPage
    from rpggen.gui.pages.options_page import OptionsPage

    for flag in ("SHMUP_AVAILABLE", "RUN_AND_GUN_AVAILABLE", "RACING_AVAILABLE"):
        monkeypatch.setattr(features, flag, True)
    theme.apply_theme("dark", remember=False)
    window = MainWindow(dev.layout_state(archetype, tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    found: list[str] = []
    for kind in (ArchetypePage, MappingPage, OptionsPage):
        page = next(p for p in window.pages if isinstance(p, kind))
        window.show_page(window.pages.index(page))
        for _ in range(3):
            QApplication.processEvents()
        found.extend(f"{page.title}: {p}" for p in layout_problems(page))
        if isinstance(page, ArchetypePage):
            assert page.selected() == archetype
            assert page.in_grid == (size == "default"), "rows of three from 1000 px on"
            if page.in_grid:  # two rows are in view at 720 px; the third row scrolls
                _two_rows_in_view(page)
            for card in page.cards.values():
                assert card.height() >= card.minimumSizeHint().height(), card.key
        if isinstance(page, OptionsPage):
            box = page.arcade_box
            assert box is not None and not box.isHidden() and box.plan is not None
            assert not box.preview.pixmap().isNull()
    assert not found, f"{archetype}/{size}:\n" + "\n".join(found)


# (packs, the kind of game, how its maps are seen): a farm of each view, and the two other
# kinds of the wizard's isometric paths. The two sample packs of T17.17 are not what these
# pages are laid out with: the synthetic packs of the tests are.
M17_CASES = {
    "farm": (("ranch",), "farm", "top_down"),
    "farm_iso": (("iso_miniature",), "farm", "isometric"),
    "rpg_iso": (("iso_tiles",), "turn_based", "isometric"),
    "race_iso": (("racer", "iso_tiles"), "racing", "isometric"),
}


def _synthetic_state(packs: tuple[str, ...], archetype: str, projection: str, scratch: Path):  # noqa: ANN202
    """A wizard state analysed from synthetic packs, on the way to its first generation."""
    from rpggen.core import config
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers
    from rpggen.gui.state import WizardState

    sources = [dev.REPO_ROOT / "test_packs" / "synthetic" / pack for pack in packs]
    state = WizardState(project_name="Layout check", pack_sources=sources, archetype=archetype)
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    refs = [
        config.PackRef(opened.pack_id, str(source), "0" * 64, "folder")
        for opened, source in zip(state.opened_packs, sources, strict=True)
    ]
    state.config = config.default_for("Layout check", refs, archetype=archetype)
    state.config.projection = projection
    state.view_chosen = True
    state.target = scratch / "layout_project"
    state.godot_exe = scratch / "godot.exe"
    return state


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
@pytest.mark.parametrize("case", sorted(M17_CASES))
def test_the_pages_of_a_farm_and_of_an_isometric_project_fit(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, theme_name: str, size: str
) -> None:
    """T17.16: eight cards on the Archetype page with its two hints, the roles of the view on
    the Mapping page, and on the Options page the farm's box over its village's and the View
    choice in the box of the kind, at the minimum window and at the default one, in both
    themes. The two flags are set here; they are on in the wizard since the gate of 1.5."""
    from rpggen import features
    from rpggen.gui.pages.archetype_page import ArchetypePage
    from rpggen.gui.pages.mapping_page import MappingPage
    from rpggen.gui.pages.options_page import OptionsPage

    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", True)
    packs, archetype, projection = M17_CASES[case]
    theme.apply_theme(theme_name, remember=False)
    state = _synthetic_state(packs, archetype, projection, tmp_path)
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    found: list[str] = []
    for kind in (ArchetypePage, MappingPage, OptionsPage):
        page = next(p for p in window.pages if isinstance(p, kind))
        window.show_page(window.pages.index(page))
        for _ in range(3):
            QApplication.processEvents()
        found.extend(f"{page.title}: {p}" for p in layout_problems(page))
        if isinstance(page, ArchetypePage):
            assert page.selected() == archetype and len(page.cards) == 8
            assert page.farm_card.isEnabled()
            assert page.iso_hint.isHidden() == (projection != "isometric")
            # (the miniature pack has cars: detection says a racing game fits it too)
            assert page.view_hint.isHidden() == (case == "rpg_iso")
            assert page.in_grid == (size == "default"), "rows of three from 1000 px on"
            if page.in_grid:
                _two_rows_in_view(page)
            for card in page.cards.values():
                assert card.height() >= card.minimumSizeHint().height(), card.key
                assert card.width() <= page.cards_scroll.viewport().width(), card.key
        if isinstance(page, MappingPage):
            assert page.projection == projection
            flat = [r.row.role for r in page.rows.values() if not r.note_label.isHidden()]
            assert flat == (["VEHICLE"] if case == "race_iso" else [])
        if isinstance(page, OptionsPage):
            assert state.config.projection == projection, "the pages left it as it was"
            view = page.view_choice
            # the row is there when a pack has isometric pictures (the ranch has none), and
            # the Pad with the isometric view of a kind whose player walks (not a race's)
            assert view is not None and view.isHidden() == (case == "farm")
            assert view.projection() == projection
            pad = projection == "isometric" and archetype != "racing"
            assert view.pad_combo.isHidden() == (not pad)
            if archetype == "farm":
                box = page.farm_box
                assert not box.isHidden() and box.plan is not None
                assert not box.preview.pixmap().isNull()
                assert not page.starter_box.isHidden(), "the village under the farm"
                assert (box.footprint is None) == (projection != "isometric")
            elif archetype == "racing":
                assert page.arcade_box is not None and page.arcade_box.plan is not None
            else:
                assert page.farm_box.isHidden() and not page.starter_box.isHidden()
    assert not found, f"{case}/{theme_name}/{size}:\n" + "\n".join(found)


@pytest.mark.parametrize("size", [(1280, 720), (1400, 1000), (1600, 1000)])
def test_eight_cards_are_two_rows_of_four_in_a_window_1280_wide_and_more(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int]
) -> None:
    """T17.16, T17.33: from 1280 px on the eight cards are in view together, at every height:
    with their lists when two rows of whole cards fit, without them when they do not."""
    from rpggen import features
    from rpggen.gui.pages.archetype_page import ArchetypePage

    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    theme.apply_theme("dark", remember=False)
    state = _synthetic_state(("ranch",), "farm", "top_down", tmp_path)
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    page = next(p for p in window.pages if isinstance(p, ArchetypePage))
    window.show_page(window.pages.index(page))
    for _ in range(3):
        QApplication.processEvents()
    assert layout_problems(page) == []
    cards = list(page.cards.values())
    assert page.columns == 4 and page.selected() == "farm"
    assert page.cards_box.height() <= page.cards_scroll.viewport().height(), "nothing scrolls"
    assert not page.cards_scroll.verticalScrollBar().isVisible()
    assert len({card.geometry().top() for card in cards}) == 2
    assert len({card.width() for card in cards}) <= 2, "the cards are as wide as each other"
    for card in cards:
        assert card.width() >= card.minimumWidth(), card.key
        assert card.height() >= card.heightForWidth(card.width()), f"{card.key} is clipped"


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("layout", ["farm", dev.ISO_LAYOUT])
def test_the_pages_fit_with_the_two_samples_of_m17(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str, size: str
) -> None:
    """T17.17: ``dev.layout_state`` lays a farm out with *Green acre* and a turn-based game in
    the isometric view with *Stone isle*, the packs these games are tried with: every page
    fits at the minimum window and at the default one."""
    from rpggen import features, paths

    monkeypatch.setattr(features, "FARM_AVAILABLE", True)
    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", True)
    theme.apply_theme("dark", remember=False)
    state = dev.layout_state(layout, tmp_path)
    kind, _, view = layout.partition(":")
    assert state.pack_sources == [paths.sample_pack_dir(dev.KIND_SAMPLES[layout])]
    assert state.archetype == kind and state.config.archetype == kind
    assert state.config.projection == (view or "top_down")
    state.view_chosen = True  # the pages leave the view as it was laid out
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    QApplication.processEvents()
    found: list[str] = []

    def check(page_name: str, win: MainWindow) -> None:
        current = win.welcome if win.welcome_visible else win.current_page
        found.extend(f"{page_name}: {p}" for p in layout_problems(current))

    dev.show_each_page(window, check)
    assert not found, f"{layout}/{size}:\n" + "\n".join(found)
    assert state.config.projection == (view or "top_down"), "the pages left the view as it was"


@pytest.mark.parametrize("size", sorted(SIZES))
@pytest.mark.parametrize("theme_name", dev.LAYOUT_THEMES)
def test_the_pages_of_a_project_of_assets_only_fit(
    qtbot, tmp_path: Path, theme_name: str, size: str
) -> None:
    """T17.33: a project of assets only on the sample pack: its card is chosen, the Mapping
    page has its note instead of roles and sounds, the Options page its own box instead of a
    game's sections, and Results no Play button; every page fits at both sizes and themes."""
    from rpggen.gui.pages.archetype_page import ArchetypePage
    from rpggen.gui.pages.mapping_page import MappingPage
    from rpggen.gui.pages.options_page import OptionsPage
    from rpggen.gui.pages.results_page import ResultsPage

    theme.apply_theme(theme_name, remember=False)
    state = dev.layout_state("assets", tmp_path)
    assert state.archetype == "assets" and state.config.archetype == "assets"
    window = MainWindow(state, default_pages())
    qtbot.addWidget(window)
    window.resize(*SIZES[size])
    window.show()
    QApplication.processEvents()
    found: list[str] = []

    def check(page_name: str, win: MainWindow) -> None:
        current = win.welcome if win.welcome_visible else win.current_page
        found.extend(f"{page_name}: {p}" for p in layout_problems(current))
        if isinstance(current, ArchetypePage):
            assert current.selected() == "assets" and len(current.cards) == 8
            if current.in_grid:
                visible = current.cards_scroll.viewport().height()
                at = current.cards_scroll.verticalScrollBar().value()
                card = current.assets_card.geometry()
                assert at <= card.top() and card.bottom() <= at + max(visible, card.height())
        if isinstance(current, MappingPage):
            assert not current.assets_note.isHidden() and current.sound_section.isHidden()
            assert current.rows == {}
        if isinstance(current, OptionsPage):
            assert not current.assets_box.isHidden() and current.starter_box.isHidden()
            assert current.layers_box.isHidden() and current.export_targets.isHidden()
            assert current.presets.isHidden()
        if isinstance(current, ResultsPage):
            assert current.play_button.isHidden() and current.starter_button.isHidden()
            assert not current.godot_button.isHidden()

    dev.show_each_page(window, check)
    assert not found, f"assets/{theme_name}/{size}:\n" + "\n".join(found)

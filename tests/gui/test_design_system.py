"""M15, Parts A and B of the shell: the stylesheet really applies (T15.02), button kinds
(T15.03), no inline styles (T15.05), the page header (T15.06), the stepper (T15.07), cards and
the welcome view (T15.08, T15.10), page motion (T15.09) and the dialogs' buttons (T15.19)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import dev
from rpggen.core import app_settings
from rpggen.gui import app as gui_app
from rpggen.gui import state as state_mod
from rpggen.gui import theme, wizard, workers
from rpggen.gui.pages.welcome_page import WelcomePage
from rpggen.gui.widgets import buttons, card, stepper
from rpggen.gui.widgets.page_header import PageHeader
from rpggen.gui.wizard import PAGE_NAMES, MainWindow, default_pages, stub_pages

REPO = Path(__file__).resolve().parents[2]
GUI = REPO / "rpggen" / "gui"
THEMES = ("dark", "light")


@pytest.fixture(autouse=True)
def _dark_again():
    yield
    theme.apply_theme("dark", remember=False)


@pytest.fixture(autouse=True)
def _no_godot_scan(monkeypatch):
    monkeypatch.setattr(workers, "find_working_godot", lambda *, callbacks: None)


def _shown(qtbot, widget: QWidget) -> QWidget:
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()
    return widget


def _pixel(widget: QWidget, x: int, y: int) -> str:
    return widget.grab().toImage().pixelColor(x, y).name()


def _focus(widget: QWidget, reason: Qt.FocusReason) -> None:
    QApplication.sendEvent(
        widget, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason)
    )
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn, reason))
    QApplication.processEvents()


# ------------------------------------------------------------------ T15.02: stock widgets


@pytest.mark.parametrize("name", THEMES)
def test_the_stylesheet_really_draws_the_stock_widgets(qtbot, name: str) -> None:
    theme.apply_theme(name, remember=False)
    holder = QWidget()
    box = QVBoxLayout(holder)
    check = QCheckBox("Tilesets")
    check.setChecked(True)
    combo = QComboBox()
    combo.addItems(["one", "two"])
    button = QPushButton("Browse…")
    edit = QLineEdit()
    for widget in (check, combo, button, edit):
        box.addWidget(widget)
    _shown(qtbot, holder)
    option = QStyleOptionButton()
    check.initStyleOption(option)
    indicator = check.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, check)
    assert indicator.width() == indicator.height() == 18  # 16 px and the border
    # inside the checked box, beside the tick: the accent
    assert _pixel(check, indicator.left() + 2, indicator.top() + 4) == theme.hex_of("accent")
    # the button: a border that is not its background, and the control height of the design
    assert button.height() == combo.height() == edit.height() == theme.px("control_height")
    assert _pixel(button, 0, button.height() // 2) == theme.hex_of("border_strong")
    assert _pixel(button, 4, 4) == theme.hex_of("surface")
    assert _pixel(edit, 6, 6) == theme.hex_of("base")
    check.setChecked(False)
    QApplication.processEvents()
    assert _pixel(check, indicator.left() + 2, indicator.top() + 4) == theme.hex_of("base")


@pytest.mark.parametrize("name", THEMES)
def test_the_focus_ring_is_for_the_keyboard_only(qtbot, name: str) -> None:
    theme.apply_theme(name, remember=False)
    theme.install_focus_ring(QApplication.instance())  # type: ignore[arg-type]
    holder = QWidget()
    box = QVBoxLayout(holder)
    button, edit = QPushButton("Next"), QLineEdit()
    box.addWidget(button)
    box.addWidget(edit)
    _shown(qtbot, holder)
    middle = button.height() // 2
    for reason in (
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    ):
        _focus(button, reason)
        assert button.property("kbfocus") == "true", reason
        # two pixels of the focus colour at the edge
        assert _pixel(button, 0, middle) == theme.hex_of("focus")
        assert _pixel(button, 1, middle) == theme.hex_of("focus")
        assert button.height() == theme.px("control_height")  # the ring does not move anything
    _focus(button, Qt.FocusReason.MouseFocusReason)  # a click: focus, but no ring
    assert not button.property("kbfocus")
    assert _pixel(button, 0, middle) == theme.hex_of("border_strong")
    assert _pixel(button, 1, middle) == theme.hex_of("surface")
    _focus(edit, Qt.FocusReason.TabFocusReason)
    assert edit.property("kbfocus") == "true"
    QApplication.sendEvent(edit, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason))
    assert not edit.property("kbfocus")  # the ring goes with the focus


def test_the_stylesheet_has_no_focus_rule_for_buttons() -> None:
    """T15.09: the keyboard ring is the only focus indication of a button, so a mouse click
    shows none. (An input keeps its accent border while it has the focus: that is where the
    typing goes.)"""
    rendered = theme.stylesheet("dark")
    for selector in re.findall(r"([^{}]+)\{", rendered):
        if ":focus" in selector:
            assert "Button" not in selector and "CheckBox" not in selector, selector.strip()


# ------------------------------------------------------------------ T15.03: button kinds


def test_set_kind_restyles_and_names_the_main_action(qtbot) -> None:
    button = QPushButton("Generate")
    _shown(qtbot, button)
    assert buttons.kind_of(button) == buttons.SECONDARY
    before = _pixel(button, 4, 4)
    buttons.set_kind(button, buttons.PRIMARY)
    QApplication.processEvents()
    assert _pixel(button, 4, 4) == theme.hex_of("accent") != before  # restyled after the show
    assert "main action" in button.accessibleDescription()
    buttons.set_kind(button, buttons.QUIET)
    QApplication.processEvents()
    assert "main action" not in button.accessibleDescription()
    with pytest.raises(ValueError):
        buttons.set_kind(button, "loud")
    icon = QPushButton("words")
    _shown(qtbot, icon)
    buttons.icon_only(icon, "eye", "Show in audit")
    assert icon.text() == "" and icon.toolTip() == icon.accessibleName() == "Show in audit"


def _primaries(root: QWidget) -> list[QAbstractButton]:
    return [
        b
        for b in root.findChildren(QAbstractButton)
        if b.property("kind") == buttons.PRIMARY and b.isVisibleTo(root.window())
    ]


@pytest.mark.parametrize("archetype", ["turn_based", "metroidvania"])
def test_every_view_has_one_primary_button(qtbot, tmp_path, archetype: str) -> None:
    window = MainWindow(dev.layout_state(archetype, tmp_path), default_pages())
    qtbot.addWidget(window)
    window.resize(1100, 720)
    window.show()
    found: dict[str, list[str]] = {}

    def check(name: str, win: MainWindow) -> None:
        view = win.welcome if win.welcome_visible else win.current_page
        found[name] = [b.objectName() for b in _primaries(view)]
        if not win.welcome_visible and win.current_index < len(win.pages) - 1:
            # the wizard's Next is the main action of pages 1 to 6
            assert win.next_button.property("kind") == buttons.PRIMARY, name
            assert win.next_button.isVisibleTo(win), name

    dev.show_each_page(window, check)
    assert all(len(names) <= 1 for names in found.values()), found
    assert found["3_audit"] in ([], ["confirmButton"])  # Confirm, once an asset is selected
    # Download Godot is the welcome view's only primary, and only while no Godot is found
    assert found["0_welcome"] in ([], ["welcomeDownloadGodot"])
    # the bar: Quit quiet, Back secondary, both bar buttons at least 96 px wide
    assert window.quit_button.property("kind") == buttons.QUIET
    assert window.back_button.property("kind") == buttons.SECONDARY
    assert window.next_button.minimumWidth() == window.back_button.minimumWidth() == 96
    assert window.next_button.shortcut().toString() == "Alt+N"
    assert window.back_button.shortcut().toString() == "Alt+B"
    assert window.next_button.objectName() == "nextButton"


def test_the_welcome_views_primary_is_download_godot_only_while_godot_is_missing(qtbot) -> None:
    page = WelcomePage()
    _shown(qtbot, page)
    page.show_godot(None)
    assert [b.objectName() for b in _primaries(page)] == ["welcomeDownloadGodot"]
    assert page.godot_status.kind == card.WARNING and not page.choose_godot_button.isHidden()
    page.show_godot((Path("C:/Godot/godot.exe"), "4.7.2.stable"))
    assert _primaries(page) == [] and page.godot_status.kind == card.SUCCESS
    assert page.choose_godot_button.isHidden() and page.download_button.isHidden()
    page.check_godot()  # looking again
    assert page.godot_status.kind == card.INFO and "Looking" in page.godot_status.text()
    assert page.godot_status.objectName() == "welcomeGodotStatus"
    assert page.download_button.objectName() == "welcomeDownloadGodot"


# ------------------------------------------------------------------ T15.05: no inline styles


def test_no_inline_styles() -> None:
    """Colours and fonts live in the template. Two widgets set a **data** colour (the status
    of an asset, the marker of a map legend) and read it from a table."""
    allowed = {"theme.py": 1, "asset_detail.py": 1, "map_preview.py": 1}
    found: dict[str, int] = {}
    for path in GUI.rglob("*.py"):
        count = len(re.findall(r"\.setStyleSheet\(", path.read_text(encoding="utf-8")))
        if count:
            found[path.name] = count
    assert found == allowed
    detail = (GUI / "widgets" / "asset_detail.py").read_text(encoding="utf-8")
    legend = (GUI / "widgets" / "map_preview.py").read_text(encoding="utf-8")
    assert "STATUS_COLORS" in detail and "MARKER_COLORS" in legend
    for path in GUI.rglob("*.py"):  # and no colour is typed into a widget
        if path.name in ("theme.py", "asset_grid.py", "map_preview.py", "archetype_page.py"):
            continue  # the tokens, the status colours, the two painters of drawings
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"font-size:\s*\d+px|color:\s*#[0-9a-fA-F]{6}", text), path.name


# ------------------------------------------------------------------ T15.06: the page header


def test_every_page_starts_with_the_same_header(qtbot, monkeypatch) -> None:
    window = MainWindow(state_mod.WizardState(), default_pages())
    qtbot.addWidget(window)
    opened: list[str] = []
    monkeypatch.setattr(
        MainWindow, "show_user_guide", lambda self, anchor="": opened.append(anchor)
    )
    purposes = set()
    for index, page in enumerate(window.pages):
        header = page.page_header
        assert isinstance(header, PageHeader) and header.parentWidget() is page
        expected = "Kind of game" if page.title == "Archetype" else PAGE_NAMES[index]
        assert header.title() == expected
        assert header.purpose_label.text() and header.purpose_label.text() not in purposes
        purposes.add(header.purpose_label.text())
        margins = page.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            24,
            20,
            24,
            16,
        )
        assert page.layout().itemAt(0).widget() is header  # in the same place on every page
        # the help button does what F1 does: the guide at the page's section
        assert header.help_button.toolTip() and header.help_button.accessibleName()
        header.help_button.click()
        assert opened[-1] == page.help_anchor
    assert len(opened) == 7


def test_the_problem_line_is_a_danger_banner(qtbot) -> None:
    state = state_mod.WizardState()
    state.pack_sources = [Path("x")]  # the stub page 1 has nothing to say with a pack
    window = MainWindow(state, stub_pages())
    _shown(qtbot, window)
    assert (
        isinstance(window.problem_label, card.Banner) and window.problem_label.kind == card.DANGER
    )
    assert window.problem_label.isHidden()
    window.pages[0].validate = lambda state: [  # type: ignore[method-assign]
        wizard.form_error("Add at least one asset pack.")
    ]
    window.refresh()
    assert not window.problem_label.isHidden()
    assert window.problem_label.text() == "Add at least one asset pack."
    assert not window.problem_label.icon_label.pixmap().isNull()  # the icon, beside the words


# ------------------------------------------------------------------ T15.07: the stepper


@pytest.mark.parametrize("width", [1100, 880])
@pytest.mark.parametrize("name", THEMES)
def test_the_sidebar_paints_the_steps(qtbot, name: str, width: int) -> None:
    theme.apply_theme(name, remember=False)
    state = state_mod.WizardState()
    state.pack_sources = [Path("x")]
    pages = stub_pages()
    pages[0].status = lambda state: ("ok", 0)  # type: ignore[method-assign]
    pages[1].status = lambda state: ("attention", 12)  # type: ignore[method-assign]
    window = MainWindow(state, pages)
    qtbot.addWidget(window)
    window.resize(width, 600)
    window.show()
    window.show_page(1)
    window.show_page(2)
    QApplication.processEvents()
    sidebar = window.sidebar
    delegate = sidebar.itemDelegate()
    assert isinstance(delegate, stepper.StepDelegate)
    image = sidebar.viewport().grab().toImage()

    def circle(row: int) -> str:
        rect = delegate.circle_rect(sidebar.visualItemRect(sidebar.item(row)))
        return image.pixelColor(rect.center() + QPoint(-rect.width() // 2 + 4, 0)).name()

    assert circle(0) == theme.hex_of("success")  # done
    assert circle(1) == theme.hex_of("warning")  # needs attention
    assert circle(2) == theme.hex_of("accent")  # the current step
    assert [sidebar.item(i).data(stepper.StateRole) for i in range(4)] == [
        stepper.DONE,
        stepper.ATTENTION,
        stepper.CURRENT,
        stepper.PENDING,
    ]
    assert sidebar.item(1).data(stepper.NoteRole) == "12"
    # the accessible names and the texts are what they were (never icon-only)
    assert sidebar.item(1).data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Step 2, Archetype, needs attention (12)"
    )
    narrow = width < wizard.NARROW_BELOW
    assert sidebar.width() == (wizard.SIDEBAR_NARROW if narrow else wizard.SIDEBAR_WIDE)
    assert sidebar.item(1).text() == ("2 ⚠" if narrow else "2. Archetype · 12  ⚠")
    rect = delegate.circle_rect(sidebar.visualItemRect(sidebar.item(0)))
    assert rect.left() >= 0 and rect.right() <= sidebar.viewport().width()  # the circle fits


# ------------------------------------------------------------------ T15.08, T15.10: cards


def test_the_welcome_cards_are_buttons_for_the_keyboard(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(app_settings.get(), "recent_projects", [], raising=False)
    page = WelcomePage()
    _shown(qtbot, page)
    fired: list[str] = []
    page.trySampleRequested.connect(lambda: fired.append("sample"))
    page.ownPackRequested.connect(lambda: fired.append("own"))
    page.openProjectRequested.connect(lambda: fired.append("open"))
    cards = (page.sample_card, page.own_card, page.open_card)
    assert [c.objectName() for c in cards] == ["sampleCard", "ownPackCard", "openProjectCard"]
    for item in cards:
        assert isinstance(item, card.CardButton) and item.property("kind") == "card"
        assert item.focusPolicy() & Qt.FocusPolicy.TabFocus
        assert item.accessibleName() and item.toolTip()
        assert item.height() >= 160 and item.height() == page.sample_card.height()
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Return):
        for item in cards:
            item.setFocus()
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QApplication.sendEvent(item, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))
    assert fired.count("sample") >= 1 and fired.count("own") >= 1 and fired.count("open") >= 1
    # the sample's choices are a quiet button under the description, not a strip on the card
    assert page.sample_choose_button is not None
    assert page.sample_choose_button.property("kind") == buttons.QUIET
    assert page.sample_choose_button.menu() is page.sample_menu is page.sample_card.menu()
    before = len(fired)
    page.sample_card.click()
    assert fired[before:] == ["sample"]  # a click on the card is the top-down village


def test_a_first_start_shows_how_it_works_and_a_later_one_the_projects(qtbot, tmp_path) -> None:
    page = WelcomePage()
    _shown(qtbot, page)
    assert not page.how_box.isHidden() and page.recent_list.isHidden()
    assert page.locate_button.isHidden() and page.recent_label.isHidden()
    assert len(page.how_cards) == 3 and all(c.accessibleName() for c in page.how_cards)
    guide: list[bool] = []
    page.userGuideRequested.connect(lambda: guide.append(True))
    page.guide_button.click()
    assert guide == [True]
    project = tmp_path / "game"
    project.mkdir()
    app_settings.update(
        recent_projects=[app_settings.RecentProject(target=str(project), name="Game")]
    )
    page.refresh()
    assert page.how_box.isHidden() and not page.recent_list.isHidden()
    assert page.recent_list.count() == 1 and not page.recent_label.isHidden()
    assert page.locate_button.property("kind") == page.remove_button.property("kind") == "quiet"
    # two columns of project cards in a wide view, one in a narrow one
    page.setFixedWidth(1100)
    assert page.recent_columns() == 2
    page.setFixedWidth(880)
    assert page.recent_columns() == 1


def test_a_banner_says_its_kind_in_words_and_wraps(qtbot) -> None:
    banner = card.Banner(card.WARNING, "No Godot 4.7.2 found")
    _shown(qtbot, banner)
    banner.set_text("Something long " * 20, "a second line")
    assert banner.text_label.wordWrap() and not banner.detail_label.isHidden()
    assert banner.accessibleName().startswith("warning: ")
    assert banner.property("banner") == "warning"
    banner.set_kind(card.SUCCESS)
    assert banner.property("banner") == "success" and not banner.icon_label.pixmap().isNull()
    with pytest.raises(ValueError):
        banner.set_kind("loud")
    plain = card.Card(interactive=True)
    _shown(qtbot, plain)
    assert plain.property("card") is True and plain.property("interactive") is True
    assert plain.cursor().shape() == Qt.CursorShape.PointingHandCursor


# ------------------------------------------------------------------ T15.09: page motion


def test_a_page_change_fades_in_unless_motion_is_reduced(qtbot, monkeypatch) -> None:
    state = state_mod.WizardState()
    state.pack_sources = [Path("x")]
    window = MainWindow(state, stub_pages())
    _shown(qtbot, window)
    monkeypatch.setattr(theme, "reduce_motion", lambda: True)
    window.show_page(1)
    assert window.stack.currentIndex() == 1  # at once
    assert window.pages[1].graphicsEffect() is None and wizard.fade_opacity(window.pages[1]) == 1.0
    monkeypatch.setattr(theme, "reduce_motion", lambda: False)
    window.show_page(2)
    assert window.stack.currentIndex() == 2  # the index changes at once
    assert wizard.fade_opacity(window.pages[2]) < 1.0  # ... and the page fades in
    qtbot.waitUntil(lambda: wizard.fade_opacity(window.pages[2]) == 1.0, timeout=1000)
    qtbot.waitUntil(lambda: window.pages[2].graphicsEffect() is None, timeout=1000)
    window.show_page(2)  # the same page again: nothing fades
    assert window.pages[2].graphicsEffect() is None
    # the welcome view's change to the wizard does the same
    window.show_welcome_view()
    window.leave_welcome()
    assert wizard.fade_opacity(window.root_stack.currentWidget()) < 1.0
    qtbot.waitUntil(
        lambda: window.root_stack.currentWidget().graphicsEffect() is None, timeout=1000
    )


# ------------------------------------------------------------------ T15.19: dialogs


def _dialogs(window: MainWindow, tmp_path: Path) -> list[QDialog]:
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import make_doc_screenshots as shots
    finally:
        sys.path.pop(0)
    from rpggen.gui.dialogs.about_dialog import AboutDialog, NoticesDialog
    from rpggen.gui.dialogs.conflict_dialog import ConflictDialog
    from rpggen.gui.dialogs.error_lookup import ErrorLookupDialog
    from rpggen.gui.dialogs.promotion_dialog import PromotionDialog
    from rpggen.gui.dialogs.storage_dialog import StorageDialog

    return [
        AboutDialog(window),
        NoticesDialog(window),
        ErrorLookupDialog(window),
        StorageDialog(window),
        PromotionDialog(shots.promotion_summary(), window),
        ConflictDialog(shots.conflict_project(tmp_path / "conflict"), None, window),
        gui_app.CrashDialog("Traceback (most recent call last):\nValueError: example"),
    ]


@pytest.mark.parametrize("name", THEMES)
def test_every_dialog_opens_with_one_primary_button(qtbot, tmp_path, name: str) -> None:
    theme.apply_theme(name, remember=False)
    theme.install_focus_ring(QApplication.instance())  # type: ignore[arg-type]
    window = MainWindow(state_mod.WizardState(), stub_pages())
    qtbot.addWidget(window)
    for dialog in _dialogs(window, tmp_path):
        qtbot.addWidget(dialog)
        dialog.show()
        QApplication.processEvents()
        primaries = [
            b
            for b in dialog.findChildren(QAbstractButton)
            if b.property("kind") == buttons.PRIMARY and b.isVisibleTo(dialog)
        ]
        assert len(primaries) == 1, (type(dialog).__name__, [b.text() for b in primaries])
        dialog.close()


def test_the_dialogs_details(qtbot, tmp_path) -> None:
    window = MainWindow(state_mod.WizardState(), stub_pages())
    qtbot.addWidget(window)
    about, _notices, _lookup, storage, promotion, conflict, _crash = _dialogs(window, tmp_path)
    for dialog in (about, storage, promotion, conflict):
        qtbot.addWidget(dialog)
        dialog.show()
    QApplication.processEvents()
    # About shows the application's icon at 48 px
    assert about.icon_label.width() == 48 and not about.icon_label.pixmap().isNull()
    # the one destructive button of the wizard is marked
    from rpggen.core import cache_policy

    for item, button in storage.clear_buttons.items():
        expected = buttons.DANGER if item in cache_policy.DATA_ITEMS else None
        assert button.property("kind") == expected, item
    assert promotion.go_button.property("kind") == buttons.PRIMARY
    assert promotion.cancel_button.property("kind") == buttons.SECONDARY
    assert (
        isinstance(promotion.backup_banner, card.Banner) and promotion.backup_banner.kind == "info"
    )
    assert "saved first" in promotion.backup_label.text()
    assert not promotion.update_item.icon(0).isNull()
    # the resolver: three panes of 300 px at least, each with its header, the files in a card
    assert conflict.width() >= 1000
    for pane in (conflict.base_pane, conflict.mine_pane, conflict.new_pane):
        assert pane.minimumWidth() == 300 and pane.title.text()
    assert not conflict.mine_pane.count_chip.isHidden()
    assert "differ" in conflict.mine_pane.count_chip.text()
    assert isinstance(conflict.file_card, card.Card)
    assert conflict.close_button.property("kind") == buttons.PRIMARY

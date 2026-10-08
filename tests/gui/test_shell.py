from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QStackedWidget

from rpggen.gui import app as gui_app
from rpggen.gui import state as state_mod
from rpggen.gui.wizard import PAGE_NAMES, MainWindow, stub_pages


def _window(qtbot, state=None) -> MainWindow:
    win = MainWindow(state, stub_pages())
    qtbot.addWidget(win)
    win.show()
    return win


def test_window_opens_with_seven_pages(qtbot) -> None:
    win = _window(qtbot)
    sidebar = win.findChild(QListWidget, "sidebar")
    assert sidebar.count() == len(PAGE_NAMES) == 7
    assert win.findChild(QStackedWidget, "pageStack").count() == 7
    assert win.findChild(QPushButton, "quitButton") is not None


def test_next_is_disabled_on_an_empty_first_page(qtbot) -> None:
    win = _window(qtbot)
    assert not win.findChild(QPushButton, "nextButton").isEnabled()
    assert not win.findChild(QPushButton, "backButton").isEnabled()
    win.state.pack_sources.append(Path("x"))
    win.refresh()
    assert win.findChild(QPushButton, "nextButton").isEnabled()


def test_sidebar_follows_the_current_page(qtbot) -> None:
    state = state_mod.WizardState(pack_sources=[Path("x")])
    win = _window(qtbot, state)
    sidebar = win.findChild(QListWidget, "sidebar")
    assert sidebar.currentRow() == 0
    win.go_next()
    assert sidebar.currentRow() == 1
    # visited pages, and pages ahead up to Options once this one lets Next through (T12.35)
    assert sidebar.item(1).flags() & Qt.ItemFlag.ItemIsEnabled
    assert sidebar.item(2).flags() & Qt.ItemFlag.ItemIsEnabled
    assert not sidebar.item(5).flags() & Qt.ItemFlag.ItemIsEnabled  # Generate: not by a click
    win._on_sidebar_clicked(sidebar.item(0))
    assert win.current_index == 0
    win._on_sidebar_clicked(sidebar.item(5))  # not visited yet and past Options
    assert win.current_index == 0
    win._on_sidebar_clicked(sidebar.item(3))  # forward, through pages 1 and 2
    assert win.current_index == 3
    win.go_next()
    assert win.current_index == 4
    assert win.findChild(QPushButton, "nextButton").text() == "Generate"


def test_back_returns_to_the_previous_page(qtbot) -> None:
    win = _window(qtbot, state_mod.WizardState(pack_sources=[Path("x")]))
    win.go_next()
    win.go_back()
    assert win.current_index == 0


def test_leaving_a_page_saves_a_draft(qtbot, tmp_path) -> None:
    target = tmp_path / "proj"
    state = state_mod.WizardState(
        pack_sources=[Path("x")], target=target, project_name="Demo", archetype="turn_based"
    )
    win = _window(qtbot, state)
    win.go_next()
    data = state_mod.load_draft(target)
    assert data is not None and data["project_name"] == "Demo"


def test_draft_path_is_stable_and_case_insensitive(tmp_path) -> None:
    a = state_mod.draft_path(tmp_path / "Proj")
    assert a == state_mod.draft_path(tmp_path / "Proj")
    assert a.parent.name == "drafts" and len(a.stem) == 16
    assert state_mod.load_draft(tmp_path / "none") is None


def test_crash_dialog_shows_gui_001(qtbot) -> None:
    dlg = gui_app.CrashDialog("Traceback...\nValueError: boom")
    qtbot.addWidget(dlg)
    assert "GUI-001" in dlg.findChild(QLabel, "crashMessage").text()
    assert dlg.export_button.isEnabled()
    assert dlg.details.isHidden()
    dlg.show()
    dlg.details_toggle.setChecked(True)
    assert not dlg.details.isHidden()


def test_the_bottom_left_button_is_quit_with_ctrl_q(qtbot) -> None:
    win = _window(qtbot)
    assert win.quit_button.text() == "Quit"
    assert win.findChild(QPushButton, "cancelButton") is None
    assert win.exit_action.shortcut().toString() == "Ctrl+Q"
    assert "Quit" in win.exit_action.text().replace("&", "")


def test_quit_is_hidden_while_a_page_is_running(qtbot) -> None:
    win = _window(qtbot)
    assert win.quit_button.isVisibleTo(win)
    win.current_page.running = True
    win.refresh()
    assert not win.quit_button.isVisibleTo(win)
    win.current_page.running = False
    win.refresh()
    assert win.quit_button.isVisibleTo(win)


def test_minimum_size_and_narrow_sidebar(qtbot) -> None:
    win = _window(qtbot)
    assert (win.minimumWidth(), win.minimumHeight()) == (880, 540)
    win.resize(1100, 720)
    assert win.sidebar.item(0).text().startswith("1. ")
    win.resize(900, 560)
    assert win.sidebar.item(0).text() == "1"
    assert win.sidebar.item(0).toolTip() == PAGE_NAMES[0]
    assert win.sidebar.width() < 100


def _analysed_state(pack: str) -> state_mod.WizardState:
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers

    synth = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
    state = state_mod.WizardState(pack_sources=[synth / pack])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return state


def test_step_status_counts_for_audit_and_mapping(qtbot) -> None:
    from rpggen.core import catalog
    from rpggen.gui.pages.audit_page import AuditPage
    from rpggen.gui.pages.mapping_page import MappingPage
    from rpggen.gui.pages.project_page import ProjectPage

    state = _analysed_state("mixed")
    _done, attention, _total = catalog.review_progress(state.catalog)
    assert attention > 0
    assert AuditPage().status(state) == ("attention", attention)
    assert ProjectPage().status(state) == ("ok", 1)
    mapping_page = MappingPage()
    qtbot.addWidget(mapping_page)
    kind, missing = mapping_page.status(state)  # the mixed pack has no player
    assert kind == "error" and missing >= 1
    assert AuditPage().status(state_mod.WizardState()) == ("none", 0)
    state.placeholders = {"PLAYER", "GROUND"}
    assert mapping_page.status(state)[0] in ("ok", "error")


def test_sidebar_items_show_the_status_and_describe_it(qtbot) -> None:
    from rpggen.gui.pages.base import WizardPage

    pages = stub_pages()
    pages[1].status = lambda state: ("attention", 12)  # type: ignore[method-assign]
    pages[2].status = lambda state: ("error", 0)  # type: ignore[method-assign]
    pages[3].status = lambda state: ("ok", 0)  # type: ignore[method-assign]
    assert isinstance(pages[0], WizardPage)
    win = MainWindow(state_mod.WizardState(pack_sources=[Path("x")]), pages)
    qtbot.addWidget(win)
    win.resize(1100, 700)
    win.show()
    win.continue_to(3)
    sidebar = win.sidebar
    assert sidebar.item(1).text() == f"2. {PAGE_NAMES[1]} · 12  ⚠"
    assert sidebar.item(2).text().endswith("✖") and sidebar.item(3).text().endswith("✓")
    spoken = sidebar.item(1).data(Qt.ItemDataRole.AccessibleTextRole)
    assert "needs attention" in spoken and "12" in spoken
    assert sidebar.item(5).text() == f"6. {PAGE_NAMES[5]}"  # not visited: no status
    win.resize(900, 600)
    assert sidebar.item(1).text() == "2 ⚠"


def test_a_forward_click_enters_and_leaves_every_page_in_between(qtbot) -> None:
    calls: list[str] = []
    pages = stub_pages()
    for i, page in enumerate(pages):
        page.enter = lambda state, i=i: calls.append(f"enter{i}")  # type: ignore[method-assign]
        page.leave = lambda state, i=i: calls.append(f"leave{i}")  # type: ignore[method-assign]
    win = MainWindow(state_mod.WizardState(pack_sources=[Path("x")]), pages)
    qtbot.addWidget(win)
    win.show()
    calls.clear()
    win._on_sidebar_clicked(win.sidebar.item(4))  # Project -> Options
    assert win.current_index == 4
    assert calls == [
        "leave0", "enter1", "leave1", "enter2", "leave2", "enter3", "leave3", "enter4",
    ]  # fmt: skip


def test_a_forward_click_stops_at_the_first_page_that_blocks(qtbot) -> None:
    pages = stub_pages()
    from rpggen.gui.pages.base import form_error

    pages[2].validate = lambda state: [form_error("not yet")]  # type: ignore[method-assign]
    win = MainWindow(state_mod.WizardState(pack_sources=[Path("x")]), pages)
    qtbot.addWidget(win)
    win.show()
    win._on_sidebar_clicked(win.sidebar.item(4))
    assert win.current_index == 2  # entered, and Next is blocked there
    assert not win.sidebar.item(4).flags() & Qt.ItemFlag.ItemIsEnabled

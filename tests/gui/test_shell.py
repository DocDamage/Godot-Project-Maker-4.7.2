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
    assert win.findChild(QPushButton, "cancelButton") is not None


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
    # only visited pages can be clicked
    assert sidebar.item(1).flags() & Qt.ItemFlag.ItemIsEnabled
    assert not sidebar.item(2).flags() & Qt.ItemFlag.ItemIsEnabled
    win._on_sidebar_clicked(sidebar.item(0))
    assert win.current_index == 0
    win._on_sidebar_clicked(sidebar.item(3))  # not visited yet
    assert win.current_index == 0
    win.go_next()
    win.go_next()
    win.go_next()
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
    assert not dlg.export_button.isEnabled()
    assert dlg.details.isHidden()
    dlg.show()
    dlg.details_toggle.setChecked(True)
    assert not dlg.details.isHidden()

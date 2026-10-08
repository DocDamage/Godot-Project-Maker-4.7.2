from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

import rpggen
from rpggen import godot_target
from rpggen.core import app_settings, profile_registry, update_check
from rpggen.gui import state as state_mod
from rpggen.gui import workers
from rpggen.gui.dialogs import help_viewer
from rpggen.gui.dialogs.about_dialog import AboutDialog
from rpggen.gui.dialogs.error_lookup import ErrorLookupDialog, matching
from rpggen.gui.wizard import MainWindow, default_pages


@pytest.fixture(autouse=True)
def _no_godot_scan(monkeypatch):
    """The welcome view looks for Godot in a worker; keep it away from the real machine."""
    monkeypatch.setattr(workers, "find_working_godot", lambda *, callbacks: None)


def _window(qtbot, welcome: bool = False) -> MainWindow:
    win = MainWindow(state_mod.WizardState(), default_pages(), show_welcome=welcome)
    qtbot.addWidget(win)
    return win


def _names(win: MainWindow) -> set[str]:
    return {a.objectName() for a in win.findChildren(QAction) if a.objectName()}


def test_every_menu_action_exists(qtbot) -> None:
    win = _window(qtbot)
    expected = {
        "newProject", "openProject", "exitAction", "undoMenuAction", "redoMenuAction",
        "guideAction", "codesAction", "shortcutsAction", "reportAction", "updateAction",
        "aboutAction", "theme_dark", "theme_light", "thumb_64", "thumb_96", "thumb_128",
        "thumb_192", "storageAction",
    }  # fmt: skip
    assert expected <= _names(win)
    assert [
        m.title().replace("&", "")
        for m in win.menuBar().findChildren(type(win.recent_menu))
        if m.parent() is win.menuBar()
    ] == ["File", "Edit", "View", "Help"]


def test_about_shows_the_versions(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    text = dialog.findChild(type(dialog.details), "aboutTitle").text() + dialog.details.text()
    assert rpggen.__version__ in text
    assert godot_target.VERSION in text
    assert rpggen.REPO_URL in text
    assert dialog.notices_button.isEnabled()


def test_error_lookup_searches_code_message_and_fix(qtbot) -> None:
    assert "ENV-002" in matching("ENV-002")
    assert "ENV-011" in matching("download godot")
    assert matching("zzzzzz-not-there") == []
    dialog = ErrorLookupDialog(initial="ENV-011")
    qtbot.addWidget(dialog)
    assert dialog.codes.count() == 1
    assert "Could not download Godot" in dialog.detail.text()


def test_f1_resolves_to_a_real_guide_section_on_every_page(qtbot) -> None:
    win = _window(qtbot)
    for page in win.pages:
        assert help_viewer.anchor_exists(page.help_anchor), (page.title, page.help_anchor)


def test_user_guide_opens_at_the_section(qtbot) -> None:
    viewer = help_viewer.HelpViewer(anchor="4. In Godot")
    qtbot.addWidget(viewer)
    assert "rpggen user guide" in viewer.windowTitle()
    assert viewer.scroll_to("4. In Godot")
    assert not viewer.scroll_to("no such section")


def test_welcome_view_hides_the_wizard_and_cards_drive_it(qtbot, monkeypatch) -> None:
    win = _window(qtbot, welcome=True)
    assert win.welcome_visible
    assert win.windowTitle() == "rpggen"
    called: list[str] = []
    page = win._project_page()
    monkeypatch.setattr(page, "try_sample", lambda: called.append("sample") or True)
    win.welcome.sample_card.click()
    assert not win.welcome_visible and called == ["sample"]
    win.show_welcome_view()
    win.welcome.own_card.click()
    assert not win.welcome_visible and win.current_index == 0


def test_open_card_asks_for_a_project_folder(qtbot, tmp_path: Path, monkeypatch) -> None:
    win = _window(qtbot, welcome=True)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    win.choose_project_folder = lambda: tmp_path  # type: ignore[method-assign]
    win.welcome.open_card.click()
    assert win.welcome_visible  # not a project: stays on the welcome view
    project = tmp_path / "proj"
    (project / "rpggen").mkdir(parents=True)
    (project / "rpggen" / "generator_config.json").write_text("{}", encoding="utf-8")
    opened: list[Path] = []
    monkeypatch.setattr(win, "open_target", lambda t: opened.append(Path(t)))
    monkeypatch.setattr("rpggen.core.preflight.is_rpggen_project", lambda p: True)
    assert win.open_project(project)
    assert opened == [project] and not win.welcome_visible


def test_recent_projects_keep_unreachable_folders_greyed_with_locate_and_remove(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import time

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    keep, gone, slow = tmp_path / "keep", tmp_path / "gone", tmp_path / "slow"
    keep.mkdir()
    s = app_settings.AppSettings()
    for folder in (slow, gone, keep):
        app_settings.add_recent(s, folder, folder.name.title(), "arpg")
    app_settings.save(s)

    def is_dir(target: str) -> bool:
        if target == str(slow):
            time.sleep(1.5)  # a share that does not answer
        return target == str(keep)

    real = app_settings.available
    monkeypatch.setattr(
        app_settings, "available", lambda targets, timeout_s=2.0, **k: real(targets, 0.3, is_dir)
    )
    started = time.monotonic()
    win = _window(qtbot, welcome=True)
    assert time.monotonic() - started < 1.0  # the window did not wait for the folders
    assert win.welcome.recent_targets() == [str(keep), str(gone), str(slow)]  # all are listed
    qtbot.waitUntil(lambda: win.welcome.unavailable == {str(gone), str(slow)}, timeout=5000)
    gone_item = win.welcome.recent_list.item(1)
    assert gone_item.data(0x0100 + 1) is True and "cannot be reached" in gone_item.toolTip()
    assert win.welcome.recent_list.item(0).data(0x0100 + 1) is False
    chosen: list[str] = []
    win.welcome.recentChosen.connect(chosen.append)
    win.welcome.recent_list.itemActivated.emit(win.welcome.recent_list.item(0))
    win.welcome.recent_list.itemActivated.emit(gone_item)  # an unreachable one does not open
    assert chosen == [str(keep)]
    # Locate… on the unreachable one, Remove on another
    win.welcome.recent_list.setCurrentRow(1)
    assert win.welcome.locate_button.isEnabled() and win.welcome.remove_button.isEnabled()
    moved = tmp_path / "moved"
    win.welcome.ask_folder = lambda start: str(moved)  # type: ignore[method-assign]
    assert win.welcome.locate_selected()
    assert (
        str(moved) in win.welcome.recent_targets() and str(gone) not in win.welcome.recent_targets()
    )
    win.welcome.recent_list.setCurrentRow(0)
    assert not win.welcome.locate_button.isEnabled() or win.welcome.recent_list.item(0).data(
        0x0100 + 1
    )
    win.welcome.recent_list.setCurrentRow(win.welcome.recent_targets().index(str(slow)))
    assert win.welcome.remove_selected()
    assert str(slow) not in [r.target for r in app_settings.load().recent_projects]


def test_godot_status_line_and_download_button(qtbot) -> None:
    win = _window(qtbot, welcome=True)
    win.welcome.show_godot(None)
    assert "not found" in win.welcome.godot_status.text()
    assert not win.welcome.download_button.isHidden()
    win.welcome.show_godot((Path("C:/g/godot.exe"), "4.7.2.stable"))
    assert "4.7.2.stable" in win.welcome.godot_status.text()
    assert win.welcome.download_button.isHidden()


def test_new_project_goes_back_to_the_welcome_view(qtbot) -> None:
    win = _window(qtbot)
    win.state.project_name = "Old"
    win.new_project()
    assert win.welcome_visible and win.state.project_name == ""


def test_window_title_names_the_project_and_regeneration(qtbot) -> None:
    win = _window(qtbot)
    win.state.project_name = "My Game"
    win.refresh()
    assert win.windowTitle() == "rpggen — My Game"
    win.state.regenerating = True
    win.refresh()
    assert win.windowTitle().endswith("[regenerating]")


def test_theme_and_thumbnail_choices_are_remembered(qtbot) -> None:
    win = _window(qtbot)
    win.set_theme("light")
    win.set_thumb_size(128)
    app_settings.store().flush()
    saved = app_settings.load()
    assert (saved.theme, saved.thumb_size) == ("light", 128)
    assert win.theme_actions["light"].isChecked() and win.thumb_actions[128].isChecked()
    win.set_theme("dark")


def test_update_check_outcomes(qtbot) -> None:
    win = _window(qtbot)
    shown: list[tuple[str, str | None]] = []
    win.show_update_result = lambda message, url: shown.append((message, url))  # type: ignore[method-assign]

    def release(tag: str):
        body = f'{{"tag_name": "{tag}", "html_url": "https://github.com/x/y/releases/{tag}"}}'
        return lambda url, limit: body.encode()

    win.update_fetcher = lambda: release("v" + rpggen.__version__)  # type: ignore[method-assign]
    assert win.check_for_updates() == "latest"
    assert "latest version" in shown[-1][0] and shown[-1][1] is None
    win.update_fetcher = lambda: release("v99.0.0")  # type: ignore[method-assign]
    assert win.check_for_updates() == "newer"
    assert "99.0.0" in shown[-1][0] and shown[-1][1].endswith("v99.0.0")

    def offline(url: str, limit: int) -> bytes:
        raise profile_registry.RegistryOffline("no route")

    win.update_fetcher = lambda: offline  # type: ignore[method-assign]
    assert win.check_for_updates() == "failed"
    assert "Could not check for updates" in shown[-1][0]
    assert update_check.is_newer("v99.0.0", rpggen.__version__)


def test_report_a_problem_offers_the_bundle_then_opens_the_issues_page(qtbot, monkeypatch) -> None:
    win = _window(qtbot)
    opened: list[str] = []
    exported: list[bool] = []
    win.open_url = opened.append  # type: ignore[method-assign]
    monkeypatch.setattr(
        "rpggen.gui.window_menus.diagnostic_export.export_bundle",
        lambda *a, **k: exported.append(True),
    )
    win.ask_export_before_report = lambda: None  # type: ignore[method-assign]
    win.report_problem()
    assert opened == [] and exported == []
    win.ask_export_before_report = lambda: True  # type: ignore[method-assign]
    win.report_problem()
    assert exported == [True] and opened == [rpggen.ISSUES_URL]


# ------------------------------------------------------------------------ storage (T12.10)


def _blob(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_the_storage_dialog_reports_sizes_and_clears_a_cache(qtbot) -> None:
    from rpggen import paths
    from rpggen.gui.dialogs.storage_dialog import StorageDialog, format_size

    _blob(paths.cache_dir() / "thumbs" / "a.png", 3 * 1024 * 1024)
    _blob(paths.data_dir() / "drafts" / "d.json", 2048)
    dialog = StorageDialog()
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.size_labels["thumbs"].text() != "…", timeout=5000)
    assert dialog.size_labels["thumbs"].text() == "3 MB" == format_size(3 * 1024 * 1024)
    assert dialog.size_labels["drafts"].text() == "2 KB"
    assert dialog.size_labels["extracted"].text() == "0 B"
    assert not dialog.clear_buttons["extracted"].isEnabled()  # nothing to clear
    assert "Cache 3 MB" in dialog.total_label.text() and "data 2 KB" in dialog.total_label.text()
    assert dialog.clear("thumbs")
    qtbot.waitUntil(lambda: dialog.size_labels["thumbs"].text() == "0 B", timeout=5000)
    assert not (paths.cache_dir() / "thumbs").exists()


def test_your_data_is_cleared_only_after_a_confirmation_that_says_what_is_lost(qtbot) -> None:
    from rpggen import paths
    from rpggen.gui.dialogs.storage_dialog import StorageDialog

    _blob(paths.data_dir() / "drafts" / "d.json", 10)
    dialog = StorageDialog()
    qtbot.addWidget(dialog)
    asked: list[str] = []
    dialog.confirm_clear_data = lambda name: asked.append(name) or False  # type: ignore[method-assign]
    assert dialog.clear("drafts") is False
    assert asked == ["drafts"] and (paths.data_dir() / "drafts" / "d.json").is_file()
    dialog.confirm_clear_data = lambda name: True  # type: ignore[method-assign]
    assert dialog.clear("drafts") is True
    assert not (paths.data_dir() / "drafts").exists()
    from rpggen.core import cache_policy

    assert "unfinished audits" in cache_policy.DATA_LOSSES["drafts"]


def test_the_limit_is_saved_in_the_settings(qtbot) -> None:
    from rpggen.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog()
    qtbot.addWidget(dialog)
    assert dialog.limit_box.value() == 10  # the default
    dialog.limit_box.setValue(25)
    dialog.limit_box.editingFinished.emit()
    assert app_settings.load().cache_limit_gb == 25.0


def test_edit_storage_opens_the_dialog(qtbot, monkeypatch) -> None:
    from rpggen.gui.dialogs import storage_dialog

    opened: list[bool] = []
    monkeypatch.setattr(storage_dialog.StorageDialog, "exec", lambda self: opened.append(True) or 0)
    win = _window(qtbot)
    win.storage_action.trigger()
    assert opened == [True]


def test_the_storage_dialog_can_keep_the_whole_folder_of_failed_runs(qtbot) -> None:
    from rpggen.gui.dialogs.storage_dialog import StorageDialog

    dialog = StorageDialog()
    qtbot.addWidget(dialog)
    assert not dialog.keep_failed_box.isChecked()  # the default is a lean failed run
    dialog.keep_failed_box.setChecked(True)
    assert app_settings.load().keep_full_failed_runs is True

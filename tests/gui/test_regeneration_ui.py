"""The wizard's regeneration features: Update pack, "Changed in update", Restore previous,
the editor-open dialog and the git option."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import paths
from rpggen.core import archive, catalog, config, godot, inventory, orchestrator, promote, vcs
from rpggen.core.ledger import Ledger, LedgerEntry, file_hash
from rpggen.errors import Issue, Severity
from rpggen.gui.pages.generate_page import GeneratePage
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.results_page import ResultsPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.asset_grid import AssetGrid

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture
def fake_godot(tmp_path, monkeypatch):
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setattr(godot, "detect_version", lambda p: (4, 7, 2, "stable"))
    monkeypatch.setattr(godot, "auto_find_godot", lambda: [exe])
    return exe


def _catalog() -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / "basic16", set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


# ------------------------------------------------------------------------ Update pack


def _existing_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A generated-looking project for pack ``basic16`` plus a newer release of the pack."""
    old_pack = tmp_path / "pack_v1"
    shutil.copytree(SYNTH / "basic16", old_pack)
    new_pack = tmp_path / "pack_v2"
    shutil.copytree(old_pack, new_pack)
    target = tmp_path / "game"
    shutil.copytree(old_pack, target / "assets" / "packs" / "basic16")
    ref = config.pack_ref_from_source(old_pack, "basic16")
    config.save(config.default_for("Game", [ref]), target / paths.CONFIG)
    opened = archive.open_pack(old_pack, set(), pack_id="basic16")
    old_catalog = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    catalog.save(old_catalog, target / paths.CATALOG)
    first = sorted((new_pack).rglob("*.png"))[0]
    with Image.open(first) as img:
        img.resize((img.width * 2, img.height)).save(first)  # a resized sheet
    (new_pack / "extra.png").write_bytes((old_pack / first.relative_to(new_pack)).read_bytes())
    return target, old_pack, new_pack


def test_update_pack_button_shows_only_for_an_existing_project(qtbot, fake_godot, tmp_path) -> None:
    target, _old, _new = _existing_project(tmp_path)
    page = ProjectPage()
    qtbot.addWidget(page)
    page.enter(WizardState())
    page.target_edit.setText(str(tmp_path / "somewhere_new"))
    assert page.update_pack_button.isHidden()
    page.target_edit.setText(str(target))
    assert not page.update_pack_button.isHidden()


def test_update_pack_shows_a_summary_and_swaps_the_source(qtbot, fake_godot, tmp_path) -> None:
    target, old_pack, new_pack = _existing_project(tmp_path)
    state = WizardState()
    page = ProjectPage()
    qtbot.addWidget(page)
    page.enter(state)
    page.add_sources([old_pack])
    page.target_edit.setText(str(target))
    summaries: list[str] = []
    page.confirm_update = lambda text: summaries.append(text) or True  # type: ignore[method-assign]
    assert page.update_pack("basic16", new_pack) is True
    assert page.sources() == [new_pack]
    text = summaries[0]
    assert "1 added" in text and "1 resized" in text and "become CONFLICT" in text
    assert "0 removed" in text

    page._run_analysis = lambda s: True  # type: ignore[method-assign]
    assert page.leave(state) is True
    assert state.regenerating
    assert state.pack_updates == {str(new_pack): "basic16"}
    assert "assets/packs/basic16/extra.png" in state.changed_paths
    assert any(p.endswith(".png") and "basic16" in p for p in state.changed_paths)
    assert [(p.pack_id, p.source) for p in state.config.packs] == [
        ("basic16", str(new_pack.resolve()))
    ], "the updated pack keeps its pack id and the rest of the config stays"


def test_a_declined_update_changes_nothing(qtbot, fake_godot, tmp_path) -> None:
    target, old_pack, new_pack = _existing_project(tmp_path)
    page = ProjectPage()
    qtbot.addWidget(page)
    page.enter(WizardState())
    page.add_sources([old_pack])
    page.target_edit.setText(str(target))
    page.confirm_update = lambda text: False  # type: ignore[method-assign]
    assert page.update_pack("basic16", new_pack) is False
    assert page.sources() == [old_pack]


# ------------------------------------------------------------------------ audit filter


def test_changed_in_update_filter(qtbot) -> None:
    cat = _catalog()
    grid = AssetGrid()
    qtbot.addWidget(grid)
    grid.set_catalog(cat)
    chip = grid.chips["chipChanged"]
    assert chip.isHidden()
    wanted = {cat.assets[0].id}
    grid.set_changed(wanted)
    assert not chip.isHidden() and chip.isChecked()
    assert set(grid.visible_ids()) == wanted
    grid.chips["chipAll"].click()
    assert len(grid.visible_ids()) == len(cat.assets)
    grid.set_changed(set())
    assert chip.isHidden()


# ------------------------------------------------------------------------ restore


def _results_page(qtbot, target: Path) -> ResultsPage:
    state = WizardState(target=target)
    state.run_result = orchestrator.RunResult(True, target, [], None, None, catalog=_catalog())
    page = ResultsPage()
    qtbot.addWidget(page)
    page.enter(state)
    return page


def test_restore_button_needs_a_backup(qtbot, tmp_path) -> None:
    (tmp_path / "out").mkdir()
    page = _results_page(qtbot, tmp_path / "out")
    assert not page.restore_button.isEnabled()
    (tmp_path / "out" / ".rpggen_backups" / "20260101-000001").mkdir(parents=True)
    page.enter(page.state)
    assert page.restore_button.isEnabled()


def test_restore_previous_asks_then_restores(qtbot, tmp_path, monkeypatch) -> None:
    target = tmp_path / "out"
    (target / "generated").mkdir(parents=True)
    old = target / "generated" / "a.tres"
    old.write_text("v1", encoding="utf-8")
    backup = target / ".rpggen_backups" / "20260101-000001"
    (backup / "generated").mkdir(parents=True)
    (backup / "generated" / "a.tres").write_text("v0", encoding="utf-8")
    Ledger(
        {"generated/a.tres": LedgerEntry(file_hash(backup / "generated/a.tres"), "r", "generated")}
    ).save(backup / paths.LEDGER)
    page = _results_page(qtbot, target)
    messages: list[str] = []
    page.show_message = lambda title, text: messages.append(title)  # type: ignore[method-assign]
    page.confirm_restore = lambda: False  # type: ignore[method-assign]
    assert page.restore_previous() is False and old.read_text() == "v1"
    page.confirm_restore = lambda: True  # type: ignore[method-assign]
    assert page.restore_previous() is True
    assert old.read_text() == "v0" and messages == ["Restored"]


def test_restore_failure_is_reported(qtbot, tmp_path) -> None:
    (tmp_path / "out").mkdir()
    page = _results_page(qtbot, tmp_path / "out")
    messages: list[str] = []
    page.show_message = lambda title, text: messages.append(title)  # type: ignore[method-assign]
    page.confirm_restore = lambda: True  # type: ignore[method-assign]
    assert page.restore_previous() is False
    assert messages == ["Restore failed"]


# ------------------------------------------------------------------------ editor open


def _generate_page(qtbot, tmp_path: Path) -> tuple[GeneratePage, WizardState]:
    ref = config.PackRef("basic16", str(SYNTH / "basic16"), "0" * 64, "folder")
    state = WizardState(
        target=tmp_path / "out",
        godot_exe=tmp_path / "godot.exe",
        config=config.default_for("T", [ref]),
        catalog=_catalog(),
        regenerating=True,
    )
    page = GeneratePage()
    qtbot.addWidget(page)
    page.state = state
    return page, state


def _editor_result(tmp_path: Path) -> orchestrator.RunResult:
    issue = Issue("REGEN-005", Severity.ERROR, "The Godot editor appears to be open.", "Close it.")
    return orchestrator.RunResult(
        False, tmp_path / "out", [issue], None, None, failed_phase="preflight"
    )


def test_editor_open_dialog_retry_starts_again(qtbot, tmp_path) -> None:
    page, state = _generate_page(qtbot, tmp_path)
    started: list[bool] = []
    page.start = lambda: started.append(True)  # type: ignore[method-assign]
    page.ask_editor_open = lambda: True  # type: ignore[method-assign]
    page._on_finished(_editor_result(tmp_path))
    assert started == [True]
    assert state.run_result is None


def test_editor_open_dialog_cancel_shows_the_failure(qtbot, tmp_path) -> None:
    page, state = _generate_page(qtbot, tmp_path)
    started: list[bool] = []
    page.start = lambda: started.append(True)  # type: ignore[method-assign]
    page.ask_editor_open = lambda: False  # type: ignore[method-assign]
    page._on_finished(_editor_result(tmp_path))
    assert started == []
    assert state.run_result is not None and not state.run_result.ok


# ------------------------------------------------------------------------ git option


def test_git_message_follows_the_checkbox(qtbot, tmp_path, monkeypatch) -> None:
    page, state = _generate_page(qtbot, tmp_path)
    monkeypatch.setattr(vcs, "git_available", lambda: True)
    state.regenerating = False
    assert page.git_message() == "rpggen: generate project", "on by default for a new project"
    state.regenerating = True
    assert page.git_message() is None, "off by default when regenerating"
    state.git_commit = True
    assert page.git_message() == "rpggen: regenerate project"
    monkeypatch.setattr(vcs, "git_available", lambda: False)
    assert page.git_message() is None


def test_git_option_text_and_defaults(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(vcs, "git_available", lambda: True)
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    state = WizardState(config=config.default_for("T", [ref]))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.enter(state)
    assert page.git_box.text() == "Initialize git repository" and page.git_box.isChecked()
    page.git_box.setChecked(False)
    assert state.git_commit is False
    state.git_commit = None
    state.regenerating = True
    page.enter(state)
    assert page.git_box.text() == "Commit regeneration" and not page.git_box.isChecked()
    monkeypatch.setattr(vcs, "git_available", lambda: False)
    page.enter(state)
    assert not page.git_box.isEnabled() and not page.git_box.isChecked()


def test_promote_backups_are_what_the_restore_button_looks_at(tmp_path) -> None:
    assert promote.list_backups(tmp_path) == []


# ------------------------------------------------------------------------ the preview (T12.40)


def _summary():  # type: ignore[no-untyped-def]
    from rpggen.core import promote

    return promote.PromotionSummary(
        ["generated/a.tres", "game/maps/starter_map.tscn"],
        ["generated/mine.tres"],
        ["generated/old.tres"],
        ["generated/gone.tres"],
        ".rpggen_backups/20260101-000000",
    )


def test_the_promotion_dialog_lists_every_group(qtbot) -> None:
    from rpggen.gui.dialogs.promotion_dialog import PromotionDialog

    dialog = PromotionDialog(_summary())
    qtbot.addWidget(dialog)
    assert dialog.listed(dialog.update_item) == ["game/maps/starter_map.tscn", "generated/a.tres"]
    assert dialog.listed(dialog.conflict_item) == ["generated/mine.tres"]
    assert ".rpggen-new" in dialog.conflict_item.text(0)
    assert dialog.listed(dialog.respected_item) == ["generated/gone.tres"]
    assert dialog.listed(dialog.delete_item) == ["generated/old.tres"]
    assert ".rpggen_backups/20260101-000000" in dialog.backup_label.text()


def test_declining_the_dialog_cancels_the_run_and_accepting_goes_on(qtbot, tmp_path) -> None:
    from rpggen.gui import workers

    page, _state = _generate_page(qtbot, tmp_path)
    worker = workers.Worker(lambda callbacks: None)
    page.worker = worker
    cancelled: list[bool] = []
    page.cancel = lambda: cancelled.append(True)  # type: ignore[method-assign]
    page.ask_promotion = lambda summary: False  # type: ignore[method-assign]
    page._on_confirmation(_summary())
    assert worker._answered.is_set() and worker._answer is False and cancelled == [True]
    worker2 = workers.Worker(lambda callbacks: None)
    page.worker = worker2
    page.ask_promotion = lambda summary: True  # type: ignore[method-assign]
    page._on_confirmation(_summary())
    assert worker2._answer is True and cancelled == [True]


def test_the_worker_waits_for_the_answer_and_a_cancel_is_a_no() -> None:
    import threading

    from PySide6.QtCore import Qt

    from rpggen.gui import workers

    worker = workers.Worker(lambda callbacks: None)
    assert worker.callbacks().confirm_promotion(_summary()) is True  # not asked unless enabled
    worker.confirm_promotions = True
    asked: list[object] = []
    worker.signals.confirmation.connect(asked.append, Qt.ConnectionType.DirectConnection)
    result: list[bool] = []
    thread = threading.Thread(
        target=lambda: result.append(worker.callbacks().confirm_promotion(_summary()))
    )
    thread.start()
    thread.join(0.3)
    assert thread.is_alive() and len(asked) == 1  # waiting
    worker.answer(True)
    thread.join(2)
    assert result == [True]
    stopped = workers.Worker(lambda callbacks: None)
    stopped.confirm_promotions = True
    stopped.cancel()
    assert stopped.callbacks().confirm_promotion(_summary()) is False


def test_closing_the_window_while_the_dialog_is_open_cancels(qtbot, tmp_path) -> None:
    from rpggen.gui import workers

    page, _state = _generate_page(qtbot, tmp_path)
    page.worker = workers.Worker(lambda callbacks: None)
    page.running = True
    rejected: list[bool] = []

    class FakeDialog:
        def reject(self) -> None:
            rejected.append(True)

    page._promotion_dialog = FakeDialog()  # type: ignore[assignment]
    cancelled: list[bool] = []
    page.cancel = lambda: cancelled.append(True)  # type: ignore[method-assign]
    assert page.request_close(timeout_ms=50) is True
    assert rejected == [True] and cancelled and page.worker._answer is False


def test_the_setting_is_on_by_default_and_the_menu_changes_it(qtbot) -> None:
    from rpggen.core import app_settings
    from rpggen.gui.wizard import MainWindow, stub_pages

    assert app_settings.get().confirm_regeneration is True
    win = MainWindow(None, stub_pages())
    qtbot.addWidget(win)
    assert win.confirm_regen_action.isChecked()
    win.confirm_regen_action.trigger()
    assert app_settings.get().confirm_regeneration is False
    win.confirm_regen_action.trigger()
    assert app_settings.get().confirm_regeneration is True

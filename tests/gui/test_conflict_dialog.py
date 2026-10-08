"""T12.58: the conflict dialog and its entry points."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from rpggen.core import conflicts
from rpggen.gui.dialogs.conflict_dialog import ConflictDialog, changed_lines
from tests.gui.test_generate_results import _state
from tests.unit.test_conflicts import FILE, V1, _first_generation, _regenerate, _write


def _project(tmp_path: Path) -> Path:
    """A project ("out", as the results helpers expect) with a text and a binary conflict."""
    target = tmp_path / "out"
    _first_generation(target, {FILE: V1, "generated/art/tile.png": "PNG1"})
    _write(target, FILE, V1.replace("line a", "MY a"))
    _write(target, "generated/art/tile.png", "PNG-mine")
    _regenerate(target, {FILE: V1.replace("line c", "NEW c"), "generated/art/tile.png": "PNG2"})
    return target


def _dialog(qtbot, target: Path, select: str | None = None) -> ConflictDialog:  # type: ignore[no-untyped-def]
    dialog = ConflictDialog(target, select)
    qtbot.addWidget(dialog)
    return dialog


def test_the_dialog_lists_the_files_and_shows_two_versions_without_a_base(
    qtbot, tmp_path: Path
) -> None:
    dialog = _dialog(qtbot, _project(tmp_path), FILE)
    items = [dialog.file_list.item(i).text() for i in range(dialog.file_list.count())]
    assert items == ["generated/art/tile.png", FILE]
    assert dialog.current == FILE  # the file the issue named
    assert dialog.base_pane.isHidden()  # no backup or commit holds the base
    assert "MY a" in dialog.mine_pane.view.toPlainText()
    assert "NEW c" in dialog.new_pane.view.toPlainText()
    # without a base, each side is compared with the other: both differ at lines 1 and 3
    assert dialog.mine_pane.marked == [1, 3] and dialog.new_pane.marked == [1, 3]
    assert "not found" in dialog.note.text() and "Godot" in dialog.note.text()
    assert dialog.merge_button.isEnabled()


def test_binary_files_offer_no_merge(qtbot, tmp_path: Path) -> None:
    dialog = _dialog(qtbot, _project(tmp_path), "generated/art/tile.png")
    assert not dialog.merge_button.isEnabled() and dialog.take_button.isEnabled()
    assert "binary" in dialog.mine_pane.view.toPlainText()


def test_each_action_resolves_the_selected_file_and_the_list_shrinks(qtbot, tmp_path: Path) -> None:
    target = _project(tmp_path)
    dialog = _dialog(qtbot, target, FILE)
    done = dialog.apply(conflicts.Action.MERGE)
    assert done is not None and done.conflicts == 2  # no base: every difference is marked
    assert "<<<<<<< yours" in (target / FILE).read_text(encoding="utf-8")
    assert "merged" in dialog.status.text() and ".rpggen_backups/" in dialog.status.text()
    assert dialog.file_list.count() == 1 and dialog.current == "generated/art/tile.png"
    dialog.take_button.click()
    assert (target / "generated/art/tile.png").read_text(encoding="utf-8") == "PNG2"
    assert dialog.file_list.count() == 0 and not dialog.keep_button.isEnabled()
    assert "No conflicts" in dialog.note.text()
    assert [r.action for r in dialog.resolved] == ["merge", "take_new"]


def test_the_diff_marks_replaced_and_inserted_lines() -> None:
    assert changed_lines("a\nb\nc\n", "a\nB\nc\nd\n") == [1, 3]
    assert changed_lines("a\nb\n", "a\nb\n") == []


def test_the_results_page_offers_the_resolver_and_the_fix_opens_it_at_the_file(
    qtbot, tmp_path: Path
) -> None:
    from rpggen.errors import IssueList
    from rpggen.gui.pages.results_page import ResultsPage

    target = _project(tmp_path)
    issues = IssueList()
    issues.add("REGEN-001", file=FILE)
    state = _state(tmp_path)
    from rpggen.core import orchestrator

    result = orchestrator.RunResult(True, target, list(issues), None, None, cfg=None)
    state.run_result = result
    page = ResultsPage()
    qtbot.addWidget(page)
    shown: list[str | None] = []
    page.run_conflict_dialog = lambda d: shown.append(d.current)  # type: ignore[method-assign]
    page.show()
    page.enter(state)
    assert page.conflicts_button.isVisible()
    assert "(2)" in page.conflicts_button.text()
    page.conflicts_button.click()
    assert shown == ["generated/art/tile.png"]  # the first file
    from rpggen.gui import fixes

    (fix,) = fixes.fixes_for("REGEN-001")
    page.apply_fix(fix, list(issues)[0])
    assert shown[-1] == FILE  # the fix opens the resolver at the issue's file
    for rel in conflicts.list_conflicts(target):
        conflicts.resolve(target, rel, "keep_mine")
    page.resolve_conflicts()
    assert not page.conflicts_button.isVisible()  # nothing left: the button goes


def test_the_file_menu_says_when_there_is_nothing_to_resolve(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from rpggen.gui.wizard import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    said: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: said.append(a[2]))
    window.state.target = None
    window.conflicts_action.trigger()
    assert said and "Open a generated project" in said[-1]
    window.state.target = tmp_path
    window.conflicts_action.trigger()
    assert "no files" in said[-1]

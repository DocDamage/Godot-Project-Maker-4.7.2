from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from rpggen.core import catalog
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.bulk_panel import FolderRuleDialog, common_folder, default_glob

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _page(qtbot, pack: str = "mixed"):
    state = WizardState(pack_sources=[SYNTH / pack])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    return page, state


def _ids(state, n: int = 3) -> list[str]:
    return [a.id for a in state.catalog.assets if a.kind == "image"][:n]


def test_bulk_role_change_is_one_undo_step(qtbot) -> None:
    page, state = _page(qtbot)
    ids = _ids(state)
    page.grid.select_ids(ids)
    assert page.side.currentWidget() is page.bulk
    assert page.bulk.count_label.text() == "3 assets selected"
    before = page.session.catalog
    page.bulk.role_combo.setCurrentIndex(page.bulk.role_combo.findData("WALL"))
    page.bulk.apply_button.click()
    for asset_id in ids:
        assert page.session.catalog.asset(asset_id).overrides["role"] == "WALL"
    assert page.session.undo_stack.count() == 1
    page.session.undo_stack.undo()
    assert page.session.catalog is before


def test_bulk_unchanged_fields_are_left_alone(qtbot) -> None:
    page, state = _page(qtbot)
    ids = _ids(state)
    page.grid.select_ids(ids)
    page.bulk.apply_button.click()  # nothing chosen -> nothing happens
    assert page.session.undo_stack.count() == 0
    page.bulk.add_tags_edit.setText("pack1, shared")
    page.bulk.apply_button.click()
    tags = [catalog.effective(page.session.catalog.asset(i)).get("tags") for i in ids]
    assert all("shared" in t and "pack1" in t for t in tags)
    page.grid.select_ids(ids)
    page.bulk.remove_tags_edit.setText("shared")
    page.bulk.apply_button.click()
    tags = [catalog.effective(page.session.catalog.asset(i)).get("tags") for i in ids]
    assert all("shared" not in t and "pack1" in t for t in tags)


def test_confirm_all_and_exclude_all(qtbot) -> None:
    page, state = _page(qtbot)
    ids = [a.id for a in state.catalog.assets if a.status == "NEEDS_REVIEW"][:3]
    page.grid.select_ids(ids)
    page.bulk.confirm_button.click()
    assert {page.session.catalog.asset(i).status for i in ids} == {"CONFIRMED"}
    page.grid.select_ids(ids)
    page.bulk.exclude_button.click()
    assert {page.session.catalog.asset(i).status for i in ids} == {"UNUSED"}
    assert page.session.undo_stack.count() == 2


def test_keyboard_shortcuts(qtbot) -> None:
    page, state = _page(qtbot)
    ids = [a.id for a in state.catalog.assets if a.status == "NEEDS_REVIEW"][:2]
    view = page.grid.view
    view.setFocus()
    page.grid.select_ids(ids)
    QTest.keyClick(view, Qt.Key.Key_C)
    assert {page.session.catalog.asset(i).status for i in ids} == {"CONFIRMED"}
    page.grid.select_ids(ids)
    QTest.keyClick(view, Qt.Key.Key_2)  # second quick role: WALL
    assert {page.session.catalog.asset(i).overrides["role"] for i in ids} == {"WALL"}
    page.grid.select_ids(ids)
    QTest.keyClick(view, Qt.Key.Key_X)
    assert {page.session.catalog.asset(i).status for i in ids} == {"UNUSED"}


def test_folder_rule_applies_to_matching_assets_only(qtbot) -> None:
    page, state = _page(qtbot)
    cat = page.session.catalog
    folders = {a.id: common_folder(cat, [a.id])[1] for a in cat.assets if a.kind == "image"}
    target_folder = next(f for f in folders.values() if f)
    inside = [i for i, f in folders.items() if f == target_folder]
    outside = [i for i, f in folders.items() if f != target_folder]
    assert inside and outside
    page.grid.select_ids(inside[:1])
    page.run_rule_dialog = lambda dialog: (  # type: ignore[method-assign]
        dialog.role_combo.setCurrentIndex(dialog.role_combo.findData("DECORATION")) or True
    )
    assert page.make_rule()
    result = page.session.catalog
    assert [r.glob for r in result.folder_rules] == [default_glob(target_folder)]
    for asset_id in inside:
        assert result.asset(asset_id).rule == {"role": "DECORATION"}
        assert catalog.effective(result.asset(asset_id))["role"] == "DECORATION"
    for asset_id in outside:
        assert result.asset(asset_id).rule == {}
    # the rules tab lists it and deleting removes the effect
    assert page.rules_panel.list.count() == 1
    page.rules_panel.list.setCurrentRow(0)
    page.rules_panel.delete_button.click()
    assert page.session.catalog.folder_rules == []
    assert all(a.rule == {} for a in page.session.catalog.assets)
    page.session.undo_stack.undo()
    assert len(page.session.catalog.folder_rules) == 1


def test_rules_can_be_reordered(qtbot) -> None:
    page, state = _page(qtbot)
    session = page.session
    pack = session.catalog.packs[0].pack_id
    session.add_rule(catalog.FolderRule(pack, "**", {"role": "DECORATION"}))
    session.add_rule(catalog.FolderRule(pack, "**", {"role": "WALL"}))
    some = next(a for a in session.catalog.assets if a.kind == "image")
    assert catalog.effective(session.catalog.asset(some.id))["role"] == "WALL"  # later rule wins
    assert session.reorder_rules([1, 0])
    assert [r.set["role"] for r in session.catalog.folder_rules] == ["WALL", "DECORATION"]
    assert catalog.effective(session.catalog.asset(some.id))["role"] == "DECORATION"
    assert session.reorder_rules([1, 0]) and session.undo_stack.count() == 4
    assert not session.reorder_rules([0, 1])  # same order: no change


def test_rule_dialog_builds_the_rule(qtbot) -> None:
    dialog = FolderRuleDialog(["a", "b"], "b", "tiles/**", {"collision": {"profile": "FULL"}})
    qtbot.addWidget(dialog)
    dialog.role_combo.setCurrentIndex(dialog.role_combo.findData("WALL"))
    rule = dialog.rule()
    assert (rule.pack_id, rule.glob) == ("b", "tiles/**")
    assert rule.set == {"collision": {"profile": "FULL"}, "role": "WALL"}


def test_common_folder_helpers() -> None:
    assert default_glob("") == "**" and default_glob("a/b") == "a/b/**"

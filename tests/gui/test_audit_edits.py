from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import edits

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _build(pack: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


@pytest.fixture
def cat() -> catalog.Catalog:
    return _build("basic16")


def _tiles(cat: catalog.Catalog) -> list[catalog.Asset]:
    return [a for a in cat.assets if catalog.effective(a).get("usage") == "tiles"]


def test_set_role_creates_override_and_confirms(cat) -> None:
    asset = next(a for a in cat.assets if a.status == "NEEDS_REVIEW")
    new = edits.set_override(cat, asset.id, "role", "WALL")
    edited = new.asset(asset.id)
    assert edited.overrides == {"role": "WALL"} and edited.status == "CONFIRMED"
    assert catalog.effective(edited)["role"] == "WALL"
    # copy on write: the original catalog and asset are untouched
    assert cat.asset(asset.id).overrides == {} and cat.asset(asset.id).status == "NEEDS_REVIEW"
    assert new is not cat


def test_exclude_sets_unused_and_clear_restores(cat) -> None:
    asset = cat.assets[0]
    new = edits.set_override(cat, asset.id, "role", "NONE")
    assert new.asset(asset.id).status == "UNUSED"
    back = edits.clear_override(new, asset.id, "role")
    assert back.asset(asset.id).overrides == {}
    assert back.asset(asset.id).status == cat.asset(asset.id).status
    assert edits.clear_override(back, asset.id, "role") is back  # nothing to clear


def test_null_override_deletes_a_facet(cat) -> None:
    asset = next(a for a in cat.assets if catalog.effective(a).get("usage") == "tiles")
    new = edits.set_override(cat, asset.id, "grid", None)
    assert "grid" not in catalog.effective(new.asset(asset.id))


def test_confirm_changes_only_the_status(cat) -> None:
    ids = [a.id for a in cat.assets if a.status == "NEEDS_REVIEW"][:2]
    new = edits.confirm(cat, ids)
    for asset_id in ids:
        assert new.asset(asset_id).status == "CONFIRMED"
        assert new.asset(asset_id).overrides == {}
        assert new.asset(asset_id).detected == cat.asset(asset_id).detected
    assert edits.confirm(new, ids) is new  # already confirmed


def test_confirm_resolves_a_conflict_but_keeps_excluded_unused(cat) -> None:
    a, b = cat.assets[0], cat.assets[1]
    a.status = "CONFLICT"
    b.overrides = {"role": "NONE"}
    b.status = "UNUSED"
    new = edits.confirm(cat, [a.id, b.id])
    assert new.asset(a.id).status == "CONFIRMED"
    assert new.asset(b.id).status == "UNUSED"


def test_changing_the_grid_keeps_source_ids(cat) -> None:
    before = {s["asset"]: (t.name, s["source_id"]) for t in cat.tilesets for s in t.sources}
    assert before
    asset = _tiles(cat)[0]
    grid = dict(catalog.effective(asset)["grid"])
    new = edits.set_override(
        cat, asset.id, "grid", {**grid, "margin": [0, 0], "separation": [0, 0]}
    )
    after = {s["asset"]: (t.name, s["source_id"]) for t in new.tilesets for s in t.sources}
    assert after == before


def test_usage_change_retiles_and_never_reuses_ids(cat) -> None:
    tiles = _tiles(cat)
    assert len(tiles) >= 1
    asset = tiles[0]
    old = {s["asset"]: s["source_id"] for t in cat.tilesets for s in t.sources}
    gone = edits.set_override(cat, asset.id, "usage", "image")
    assert asset.id not in {s["asset"] for t in gone.tilesets for s in t.sources}
    back = edits.clear_override(gone, asset.id, "usage")
    again = {s["asset"]: s["source_id"] for t in back.tilesets for s in t.sources}
    assert asset.id in again
    # the others keep their ids even though the sheet left and returned
    for aid, source_id in old.items():
        if aid != asset.id:
            assert again[aid] == source_id


def test_undo_restores_the_previous_state(qtbot, cat) -> None:
    session = edits.EditSession(cat)
    seen: list[list[str]] = []
    session.changed.connect(seen.append)
    asset = cat.assets[0]
    assert session.set_override(asset.id, "role", "WALL")
    assert session.catalog.asset(asset.id).overrides == {"role": "WALL"}
    assert seen[-1] == [asset.id]
    session.undo_stack.undo()
    assert session.catalog is cat
    session.undo_stack.redo()
    assert session.catalog.asset(asset.id).overrides == {"role": "WALL"}


def test_each_edit_type_is_one_undo_step(qtbot, cat) -> None:
    session = edits.EditSession(cat)
    ids = [a.id for a in cat.assets if a.status == "NEEDS_REVIEW"]
    asset = cat.asset(ids[0])
    steps = [
        lambda: session.set_override(asset.id, "role", "WALL"),
        lambda: session.set_override(asset.id, "tags", ["x"]),
        lambda: session.confirm(ids[1:3]),
    ]
    for step in steps:
        before = session.catalog
        assert step()
        session.undo_stack.undo()
        assert session.catalog is before
        session.undo_stack.redo()
    assert session.undo_stack.count() == 3
    session.reset(cat)
    assert session.undo_stack.count() == 0


# ------------------------------------------------------------------------ the audit page


def _page(qtbot, pack: str = "basic16"):
    from rpggen.gui import workers
    from rpggen.gui.pages.audit_page import AuditPage
    from rpggen.gui.state import WizardState

    state = WizardState(pack_sources=[SYNTH / pack])
    result = workers.analyze_packs(state, callbacks=Callbacks())
    workers.apply_analysis(state, result)
    page = AuditPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    page.enter(state)
    page.grid.chips["chipAll"].click()
    return page, state


def _select(page, asset_id: str) -> None:
    page.grid.select_ids([asset_id])
    assert page.grid.selected_ids() == [asset_id]


def test_selecting_an_asset_fills_the_detail_panel(qtbot) -> None:
    from rpggen.gui.widgets.asset_detail import AssetDetail

    page, state = _page(qtbot)
    asset = next(a for a in state.catalog.assets if catalog.effective(a).get("usage") == "tiles")
    _select(page, asset.id)
    detail = page.findChild(AssetDetail)
    assert detail.isEnabled() and detail.asset_id == asset.id
    assert detail.path_label.text() == asset.path
    assert detail.usage_combo.currentData() == "tiles"
    assert detail.role_combo.currentData() == catalog.effective(asset)["role"]
    assert not detail.collision_combo.isHidden() and not detail.tileset_combo.isHidden()
    assert detail.grid_button.isEnabled() and not detail.anim_button.isEnabled()
    assert detail.preview.grid_items  # overlay for tile sheets


def test_changing_the_role_in_the_panel_overrides_and_confirms(qtbot) -> None:
    page, state = _page(qtbot)
    asset = next(a for a in state.catalog.assets if a.status == "NEEDS_REVIEW")
    _select(page, asset.id)
    detail = page.detail
    index = detail.role_combo.findData("WALL")
    detail.role_combo.setCurrentIndex(index)
    detail.role_combo.activated.emit(index)
    edited = page.session.catalog.asset(asset.id)
    assert edited.overrides == {"role": "WALL"} and edited.status == "CONFIRMED"
    assert detail.status_badge.text() == "CONFIRMED"
    page.undo_action.trigger()
    assert page.session.catalog.asset(asset.id).overrides == {}
    assert detail.status_badge.text() == asset.status
    page.redo_action.trigger()
    assert page.session.catalog.asset(asset.id).overrides == {"role": "WALL"}


def test_confirm_and_exclude_buttons(qtbot) -> None:
    page, state = _page(qtbot)
    first, second = [a for a in state.catalog.assets if a.status == "NEEDS_REVIEW"][:2]
    _select(page, first.id)
    page.detail.confirm_button.click()
    assert page.session.catalog.asset(first.id).status == "CONFIRMED"
    assert page.session.catalog.asset(first.id).overrides == {}
    _select(page, second.id)
    page.detail.exclude_button.click()
    assert page.session.catalog.asset(second.id).overrides == {"role": "NONE"}
    assert page.session.catalog.asset(second.id).status == "UNUSED"


def test_alternative_roles_are_quick_buttons(qtbot) -> None:
    page, state = _page(qtbot)
    asset = next(a for a in state.catalog.assets if len(a.detected.get("roles_alt", [])) > 1)
    _select(page, asset.id)
    visible = [b for b in page.detail.alt_buttons if not b.isHidden()]
    assert visible and "%" in visible[0].text()
    role = visible[0].property("role_value")
    visible[0].click()
    assert catalog.effective(page.session.catalog.asset(asset.id))["role"] == role


def test_tags_and_leave_writes_the_catalog_to_the_state(qtbot) -> None:
    page, state = _page(qtbot)
    asset = state.catalog.assets[0]
    _select(page, asset.id)
    page.detail.tags_edit.setText("forest, summer")
    page.detail.tags_edit.editingFinished.emit()
    assert catalog.effective(page.session.catalog.asset(asset.id))["tags"] == ["forest", "summer"]
    page.leave(state)
    assert state.catalog is page.session.catalog
    assert state.catalog.asset(asset.id).overrides["tags"] == ["forest", "summer"]


# ------------------------------------------------------------------------ T12.43: the Changes tab


def test_describe_changes_lists_overrides_rules_and_objects(cat) -> None:
    session = edits.EditSession(cat)
    assert edits.describe_changes(cat) == []
    asset = cat.assets[0]
    other = cat.assets[1]
    session.set_override(asset.id, "role", "WALL")
    session.set_override(other.id, "role", "NONE")
    session.set_override(other.id, "tags", ["x"])
    session.add_rule(catalog.FolderRule(asset.pack_id, "tiles/*", {"role": "GROUND"}))
    found = edits.describe_changes(session.catalog)
    kinds = sorted(c.kind for c in found)
    assert kinds == ["excluded", "other", "role", "rules"]
    role = next(c for c in found if c.kind == "role")
    assert (
        role.asset_id == asset.id and role.after == "WALL" and role.before == asset.detected["role"]
    )
    assert next(c for c in found if c.kind == "rules").label.endswith("tiles/*")


def test_an_override_equal_to_the_detection_is_not_a_change(cat) -> None:
    session = edits.EditSession(cat)
    asset = cat.assets[0]
    session.set_override(asset.id, "role", asset.detected["role"])
    assert edits.describe_changes(session.catalog) == []


def test_revert_restores_the_detected_value_and_can_be_undone(qtbot, cat) -> None:
    session = edits.EditSession(cat)
    asset = cat.assets[0]
    session.set_override(asset.id, "role", "WALL")
    (change,) = edits.describe_changes(session.catalog)
    assert session.revert(change)
    assert session.catalog.asset(asset.id).overrides == {}
    assert edits.describe_changes(session.catalog) == []
    session.undo_stack.undo()  # the revert is an undo step of its own
    assert session.catalog.asset(asset.id).overrides == {"role": "WALL"}
    assert len(edits.describe_changes(session.catalog)) == 1


def test_the_changes_tab_counts_and_follows_every_edit(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.tabs.tabText(page.changes_index) == "Changes (0)"
    assert page.changes_panel.count() == 0 and not page.changes_panel.empty_label.isHidden()
    ids = [a.id for a in page.session.catalog.assets]
    page.session.set_override(ids[0], "role", "WALL")
    assert page.tabs.tabText(page.changes_index) == "Changes (1)"
    page.session.set_override(ids[1], "role", "NONE")
    assert page.changes_panel.count() == 2
    rows = page.changes_panel.row_texts()
    assert {r[0] for r in rows} == {"Role", "Excluded"}
    assert any(r[3] == "Wall tiles" for r in rows)  # the friendly name, not WALL
    page.session.undo_stack.undo()
    assert page.tabs.tabText(page.changes_index) == "Changes (1)"
    page.session.undo_stack.redo()
    assert page.tabs.tabText(page.changes_index) == "Changes (2)"


def test_the_revert_button_and_the_kind_filter(qtbot) -> None:
    page, _state = _page(qtbot)
    panel = page.changes_panel
    ids = [a.id for a in page.session.catalog.assets]
    page.session.set_override(ids[0], "role", "WALL")
    page.session.set_override(ids[1], "role", "NONE")
    panel.kind_filter.setCurrentIndex(panel.kind_filter.findData("excluded"))
    assert [r[0] for r in panel.row_texts()] == ["Excluded"]
    assert panel.count() == 2  # the count ignores the filter
    panel.table.cellWidget(0, 4).click()
    assert panel.count() == 1 and page.session.catalog.asset(ids[1]).overrides == {}
    page.session.undo_stack.undo()
    assert panel.count() == 2


def test_double_clicking_a_change_selects_the_asset_in_the_grid(qtbot) -> None:
    page, _state = _page(qtbot, "mixed")
    target = page.session.catalog.assets[2].id
    page.session.set_override(target, "role", "WALL")
    page.grid.chips["chipAttention"].click()  # a filter that may hide it
    page.tabs.setCurrentWidget(page.changes_panel)
    page.changes_panel.table.cellDoubleClicked.emit(0, 1)
    assert page.tabs.currentWidget() is page.grid
    assert page.grid.selected_ids() == [target]


def test_folder_rules_have_a_revert_too(qtbot) -> None:
    page, _state = _page(qtbot)
    asset = page.session.catalog.assets[0]
    page.session.add_rule(catalog.FolderRule(asset.pack_id, "tiles/*", {"role": "GROUND"}))
    assert page.changes_panel.count() == 1
    page.changes_panel.table.cellWidget(0, 4).click()
    assert page.changes_panel.count() == 0 and page.session.catalog.folder_rules == []


# ------------------------------------------------------------------------ folder headers (T13.02)


def test_confirm_all_of_a_folder_is_one_undo_step_for_its_visible_assets(qtbot) -> None:
    from rpggen.gui.widgets import asset_grid as ag

    page, state = _page(qtbot, "mixed")
    page.grid.set_grouped(True)
    page.grid.chips["chipAttention"].click()  # only what needs attention passes the filter
    key = page.grid.header_keys()[0]
    folder = ag.split_folder_key(key)[1]
    visible = set(page.grid.folder_ids(key))
    in_folder = {
        a.id for a in state.catalog.assets if catalog.folder_of(state.catalog, a) == folder
    }
    assert visible and visible <= in_folder
    before = {a.id: a.status for a in page.session.catalog.assets}
    steps = page.session.undo_stack.count()
    page.grid.view.card_delegate.headerAction.emit(key, "confirm")
    after = {a.id: a.status for a in page.session.catalog.assets}
    changed = {i for i in after if after[i] != before[i]}
    assert changed == visible and all(after[i] == "CONFIRMED" for i in visible)
    assert page.session.undo_stack.count() == steps + 1
    page.session.undo_stack.undo()
    assert {a.id: a.status for a in page.session.catalog.assets} == before
    assert not page.confirm_folder(ag.folder_key("mixed", "no_such_folder"))


def test_make_rule_on_a_header_opens_with_the_folder_glob(qtbot) -> None:
    from rpggen.gui.widgets import asset_grid as ag

    page, _state = _page(qtbot, "mixed")
    page.grid.set_grouped(True)
    key = next(k for k in page.grid.header_keys() if ag.split_folder_key(k)[1] == "items")
    opened = []

    def run(dialog) -> bool:
        opened.append((dialog.pack_combo.currentText(), dialog.glob_edit.text()))
        return False  # cancelled: no rule

    page.run_rule_dialog = run  # type: ignore[method-assign]
    rules = len(page.session.catalog.folder_rules)
    page.grid.view.card_delegate.headerAction.emit(key, "rule")
    assert opened == [("mixed", "items/**")]
    assert len(page.session.catalog.folder_rules) == rules


def test_the_grouping_choice_is_remembered(qtbot) -> None:
    from rpggen.core import app_settings

    page, _state = _page(qtbot, "mixed")
    assert not page.grid.model.grouped
    page.grid.group_button.click()
    assert app_settings.get().group_by_folder is True
    again, _state = _page(qtbot, "mixed")
    assert again.grid.model.grouped and again.grid.header_keys()
    again.grid.group_button.click()
    assert app_settings.get().group_by_folder is False


# ------------------------------------------------------------------------ select similar (T13.04)


def test_select_similar_selects_the_lookalikes_and_the_bulk_panel_applies(qtbot) -> None:
    from PySide6.QtGui import QKeySequence

    from rpggen.core.analyzer import similarity

    page, state = _page(qtbot, "mixed")
    first = "mixed.items.item_01"
    expected = [i for i, _d in similarity.near(state.catalog, first)]
    assert "mixed.items.spare.item_01" in expected, "the repeated file is at distance 0"
    _select(page, first)
    assert page.can_select_similar()
    assert page.similar_shortcut.key() == QKeySequence("Ctrl+Shift+S")
    page.similar_shortcut.activated.emit()
    assert sorted(page.grid.selected_ids()) == sorted([first, *expected])
    assert page.selection_note.text() == f"{len(expected)} similar assets selected"
    # more than one asset selected: the bulk panel shows and applies to all of them
    assert page.side.currentWidget() is page.bulk_scroll
    steps = page.session.undo_stack.count()
    assert page.session.set_overrides(page.grid.selected_ids(), {"role": "DECORATION"})
    assert page.session.undo_stack.count() == steps + 1
    for asset_id in [first, *expected]:
        assert catalog.effective(page.session.catalog.asset(asset_id))["role"] == "DECORATION"
    # nothing looks like the background, and the command says so
    _select(page, "mixed.backgrounds.sky")
    assert page.select_similar() == []
    assert page.selection_note.text() == "No similar assets found"
    assert page.grid.selected_ids() == ["mixed.backgrounds.sky"]


def test_select_similar_is_off_for_a_sound(qtbot) -> None:
    page, state = _page(qtbot, "audio_basic")
    sound = next(a for a in state.catalog.assets if a.kind == "audio")
    _select(page, sound.id)
    assert not page.can_select_similar() and page.select_similar() == []
    page.grid.select_ids([])
    assert not page.can_select_similar()

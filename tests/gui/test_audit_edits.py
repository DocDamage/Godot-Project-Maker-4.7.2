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

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory, objects
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import edits, workers
from rpggen.gui.pages.audit_page import AuditPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.object_cutter import ObjectCutterDialog

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
GRID16 = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}


def _assemble(pack: str, previous: catalog.Catalog | None = None) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], previous, [])[0]


# ------------------------------------------------------------------------ pure helpers


def test_snap_rect_covers_whole_cells() -> None:
    rect = objects.snap_rect(5, 5, 20, 18, GRID16, (128, 128), snap=True)
    assert rect == (0, 0, 32, 32)
    assert objects.snap_rect(5, 5, 20, 18, GRID16, (128, 128), snap=False) == (5, 5, 16, 14)
    assert objects.snap_rect(20, 18, 5, 5, GRID16, (128, 128), snap=True) == (0, 0, 32, 32)
    assert objects.snap_rect(-10, -10, 500, 500, GRID16, (128, 96), snap=True) == (0, 0, 128, 96)
    gutter = {"cell": [16, 16], "margin": [1, 1], "separation": [2, 2]}
    assert objects.snap_rect(19, 19, 20, 20, gutter, (100, 100), snap=True) == (19, 19, 16, 16)


def test_make_object_defaults() -> None:
    obj = objects.make_object("pack.sheet", "Big House", (16, 32, 48, 40), set())
    assert obj.id == "pack.sheet#big_house" and obj.source == "user"
    assert obj.origin == [24, 39]  # bottom-center
    assert obj.footprint == [0, 28, 48, 12]  # bottom 30%
    assert obj.collision["profile"] == "CUSTOM"
    assert obj.collision["polygon"] == [[0, 28], [48, 28], [48, 40], [0, 40]]
    again = objects.make_object("pack.sheet", "Big House", (0, 0, 8, 8), {obj.id})
    assert again.id == "pack.sheet#big_house__2"


def test_with_footprint_clamps_and_updates_polygon() -> None:
    obj = objects.make_object("s", "o", (0, 0, 32, 32), set())
    new = objects.with_footprint(obj, [-5, 20, 100, 100])
    assert new.footprint == [0, 20, 32, 12]
    assert new.collision["polygon"][0] == [0, 20]
    full = objects.with_footprint(
        edits.update_object(
            catalog.Catalog(objects=[obj]), obj.id, collision={"profile": "FULL"}
        ).objects[0],
        [1, 1, 4, 4],
    )
    assert full.collision == {"profile": "FULL"}


# ------------------------------------------------------------------------ edits


def test_object_edits_are_pure_and_undoable(qtbot) -> None:
    cat = _assemble("basic16")
    sheet = next(a for a in cat.assets if catalog.effective(a).get("usage") == "tiles")
    session = edits.EditSession(cat)
    obj = objects.make_object(sheet.id, "tree", (0, 0, 16, 32), set())
    assert session.add_object(obj)
    assert [o.id for o in session.catalog.objects] == [obj.id]
    assert cat.objects == []  # copy on write
    assert session.update_object(obj.id, name="oak", tags=["tree"])
    assert session.catalog.objects[0].name == "oak" and session.catalog.objects[0].tags == ["tree"]
    assert session.remove_object(obj.id) and session.catalog.objects == []
    session.undo_stack.undo()
    assert session.catalog.objects[0].name == "oak"
    session.undo_stack.undo()
    session.undo_stack.undo()
    assert session.catalog.objects == []


# ------------------------------------------------------------------------ dialog


def _sheet_catalog() -> tuple[catalog.Catalog, catalog.Asset, Path]:
    cat = _assemble("objects_in_sheet")
    sheet = cat.asset(cat.objects[0].sheet)
    opened = archive.open_pack(SYNTH / "objects_in_sheet", set())
    return cat, sheet, opened.root / sheet.path.split("/", 3)[3]


def _dialog(qtbot, objs, grid=GRID16, path: Path | None = None) -> ObjectCutterDialog:
    if path is None:
        path = SYNTH / "basic16" / "tiles" / "terrain.png"
    dialog = ObjectCutterDialog(path, "pack.sheet", objs, grid, set())
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_rectangle_tool_creates_a_snapped_object(qtbot) -> None:
    dialog = _dialog(qtbot, [])
    dialog.set_tool("rect")
    dialog.tool_press(20, 20)
    dialog.tool_move(40, 30)
    assert dialog._rubber is not None
    dialog.tool_release(40, 30)
    assert len(dialog.objects) == 1
    obj = dialog.objects[0]
    assert obj.region == [16, 16, 32, 16] and obj.source == "user" and obj.status == "CONFIRMED"
    assert obj.origin == [16, 15] and obj.footprint == [0, 11, 32, 5]
    assert obj.id == "pack.sheet#object_1" and dialog.selected == obj.id
    assert dialog.list.count() == 1


def test_alt_gives_pixel_precision(qtbot) -> None:
    dialog = _dialog(qtbot, [])
    dialog.tool_press(3, 4, alt=True)
    dialog.tool_release(10, 9, alt=True)
    assert dialog.objects[0].region == [3, 4, 8, 6]


def test_footprint_door_and_origin_tools(qtbot) -> None:
    dialog = _dialog(qtbot, [])
    dialog.tool_press(16, 16)
    dialog.tool_release(47, 47)  # 32x32 object at (16,16)
    obj = dialog.objects[0]
    dialog.set_tool("footprint")
    dialog.tool_press(20, 40)
    dialog.tool_move(30, 46)
    dialog.tool_release(30, 46)
    obj = dialog.get(obj.id)
    assert obj.footprint == [4, 24, 11, 7]
    assert obj.collision["polygon"] == [[4, 24], [15, 24], [15, 31], [4, 31]]
    dialog.set_tool("door")
    dialog.tool_press(30, 45)
    dialog.tool_release(30, 45)
    assert dialog.get(obj.id).door == [14, 29]
    dialog.set_tool("origin")
    dialog.tool_press(20, 20)
    dialog.tool_release(20, 20)
    assert dialog.get(obj.id).origin == [4, 4]
    dialog.tool_press(100, 100)  # outside every object: nothing changes
    assert dialog.get(obj.id).origin == [4, 4]


def test_select_move_and_resize(qtbot) -> None:
    dialog = _dialog(qtbot, [])
    dialog.tool_press(0, 0)
    dialog.tool_release(15, 15)
    obj_id = dialog.objects[0].id
    dialog.set_tool("select")
    dialog.tool_press(8, 8)
    assert dialog.selected == obj_id
    dialog.tool_move(8 + 33, 8 + 17)  # moves by about 2 cells and 1 cell (snapped)
    dialog.tool_release(8 + 33, 8 + 17)
    assert dialog.get(obj_id).region[:2] == [32, 16]
    # resize from the bottom-right corner (inclusive snapping makes it 2x2 cells)
    obj = dialog.get(obj_id)
    cx, cy = obj.region[0] + obj.region[2], obj.region[1] + obj.region[3]
    dialog.tool_press(cx, cy)
    dialog.tool_move(cx + 16, cy + 16)
    dialog.tool_release(cx + 16, cy + 16)
    assert dialog.get(obj_id).region[2:] == [32, 32]
    dialog.tool_press(120, 100)  # empty space deselects
    assert dialog.selected is None


def test_side_panel_edits_the_selected_object(qtbot) -> None:
    dialog = _dialog(qtbot, [])
    dialog.tool_press(0, 0)
    dialog.tool_release(31, 31)
    obj_id = dialog.objects[0].id
    dialog.name_edit.setText("Hut")
    dialog.name_edit.editingFinished.emit()
    dialog.role_combo.setCurrentText("BUILDING")
    dialog.role_combo.activated.emit(dialog.role_combo.currentIndex())
    dialog.tags_edit.setText("a, b")
    dialog.tags_edit.editingFinished.emit()
    dialog.collision_combo.setCurrentText("FULL")
    dialog.collision_combo.activated.emit(dialog.collision_combo.currentIndex())
    obj = dialog.get(obj_id)
    assert (obj.name, obj.role, obj.tags, obj.collision) == (
        "Hut",
        "BUILDING",
        ["a", "b"],
        {"profile": "FULL"},
    )
    assert obj.id == obj_id  # ids do not follow renames
    dialog.delete_selected()
    assert dialog.objects == [] and dialog.list.count() == 0


def test_auto_objects_are_blue_user_objects_green_and_accept_all(qtbot) -> None:
    cat, sheet, path = _sheet_catalog()
    autos = [o for o in cat.objects if o.sheet == sheet.id]
    assert autos and all(o.source == "auto" and o.status == "AUTO_DETECTED" for o in autos)
    dialog = _dialog(qtbot, autos, catalog.effective(sheet).get("grid"), path)
    dialog.accept_all()
    assert all(o.status == "CONFIRMED" and o.source == "auto" for o in dialog.objects)
    assert dialog.list.count() == len(autos)


def test_reject_persists_across_reassembly(qtbot) -> None:
    cat, sheet, path = _sheet_catalog()
    autos = [o for o in cat.objects if o.sheet == sheet.id]
    dialog = _dialog(qtbot, autos, catalog.effective(sheet).get("grid"), path)
    victim = autos[0]
    dialog.select(victim.id)
    dialog.reject_selected()
    rejected = dialog.get(victim.id)
    assert rejected.role == "NONE" and rejected.status == "UNUSED"
    assert dialog.list.count() == len(autos) - 1  # hidden from the list
    session = edits.EditSession(cat)
    assert session.set_sheet_objects(sheet.id, dialog.result_objects())
    again = _assemble("objects_in_sheet", previous=session.catalog)
    kept = next(o for o in again.objects if o.id == victim.id)
    assert kept.role == "NONE"
    assert len([o for o in again.objects if o.sheet == sheet.id]) == len(autos)  # no duplicate


def test_user_objects_and_confirmations_survive_reassembly(qtbot) -> None:
    cat, sheet, path = _sheet_catalog()
    autos = [o for o in cat.objects if o.sheet == sheet.id]
    dialog = _dialog(qtbot, autos, catalog.effective(sheet).get("grid"), path)
    dialog.accept_all()
    mine = dialog.add_region((0, 0, 16, 16))
    session = edits.EditSession(cat)
    session.set_sheet_objects(sheet.id, dialog.result_objects())
    again = _assemble("objects_in_sheet", previous=session.catalog)
    assert mine.id in {o.id for o in again.objects}
    for o in again.objects:
        if o.source == "auto":
            assert o.status == "CONFIRMED"


def test_apply_through_the_audit_page_is_one_undo_step(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "objects_in_sheet"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page = AuditPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    sheet_id = state.catalog.objects[0].sheet

    def run(dialog) -> bool:
        dialog.accept_all()
        dialog.add_region((0, 0, 16, 16))
        return True

    page.run_dialog = run  # type: ignore[method-assign]
    before = page.session.catalog
    assert page.cut_objects(sheet_id)
    assert page.session.undo_stack.count() == 1
    assert any(o.source == "user" for o in page.session.catalog.objects)
    page.session.undo_stack.undo()
    assert page.session.catalog is before


@pytest.mark.parametrize("tool", ["rect", "select", "footprint", "door", "origin"])
def test_every_tool_has_a_button(qtbot, tool) -> None:
    dialog = _dialog(qtbot, [])
    dialog.tool_buttons[tool].click()
    assert dialog.tool == tool and dialog.tool_buttons[tool].isChecked()

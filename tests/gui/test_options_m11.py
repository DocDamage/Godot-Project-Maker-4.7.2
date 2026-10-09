from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from rpggen.core import app_settings, config, options
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.pages.options_page import DEFAULTS_ITEM, ManagePresetsDialog, OptionsPage
from rpggen.gui.state import WizardState

REF = config.PackRef("x", "C:/x", "0" * 64, "folder")
SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _page(qtbot) -> tuple[OptionsPage, WizardState]:
    state = WizardState(config=config.default_for("T", [REF]))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def test_every_feature_has_a_group_label_and_sentence() -> None:
    for key in config.FEATURE_KEYS:
        group, label, text = options.FEATURE_INFO[key]
        assert group in options.FEATURE_GROUPS and label and text.endswith(".")
    grouped = [k for g in options.FEATURE_GROUPS for k in options.features_in_group(g)]
    assert sorted(grouped) == sorted(config.FEATURE_KEYS)


def test_features_are_two_state_boxes_with_descriptions(qtbot) -> None:
    page, _state = _page(qtbot)
    for key, box in page.feature_boxes.items():
        assert not box.isTristate(), key
        assert box.toolTip()
    nav = page.findChild(type(page.hint_label), "featureText_navigation")
    assert "enemies" in nav.text() and "Off by default" in nav.text()


def test_the_page_uses_two_columns_only_when_wide(qtbot) -> None:
    page, _state = _page(qtbot)
    page.resize(1150, 800)
    qtbot.wait(20)
    assert page.two_columns
    page.resize(900, 800)
    qtbot.wait(20)
    assert not page.two_columns


def test_reset_buttons_restore_each_section(qtbot) -> None:
    page, state = _page(qtbot)
    page.feature_boxes["save"].setChecked(False)
    page.resolution.combo.setCurrentIndex(0)
    page.layer_name.setText("Fog")
    page.add_layer_button.click()
    page.starter_counts["npcs"].setValue(4)
    page.features_reset.click()
    assert (
        page.feature_boxes["save"].isChecked() and not page.feature_boxes["navigation"].isChecked()
    )
    page.screen_reset.click()
    assert page.resolution.value() == (640, 360)
    page.layers_reset.click()
    assert page.layers() == config.DEFAULT_MAP_LAYERS
    page.starter_reset.click()
    assert page.starter_counts["npcs"].value() == 1
    page.leave(state)
    assert "starter_map" not in state.config.to_json()  # the defaults are not written


def test_starter_map_options_are_stored_as_differences(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.starter_size.value() == (40, 24)
    page.starter_size.combo.setCurrentIndex(2)  # Large
    page.starter_counts["buildings"].setValue(3)
    page.starter_counts["enemies"].setValue(1)  # the default of turn-based: not stored
    page.leave(state)
    assert state.config.starter_map == {"size": [64, 40], "buildings": 3}
    assert state.config.to_json()["starter_map"]["npcs"] == 1
    assert page.validate(state) == []


def test_an_existing_starter_map_is_not_editable(qtbot, tmp_path) -> None:
    project = tmp_path / "game"
    (project / "game" / "maps").mkdir(parents=True)
    (project / "game" / "maps" / "starter_map.tscn").write_text("x")
    state = WizardState(config=config.default_for("T", [REF]), target=project, regenerating=True)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    assert not page.starter_size.isEnabled() and not page.starter_counts["npcs"].isEnabled()
    assert not page.starter_note.isHidden() and "apply to new projects" in page.starter_note.text()
    assert not page.preview.reroll_button.isEnabled()
    page.leave(state)
    assert state.config.starter_map == {}


def test_presets_round_trip_through_the_app_settings(qtbot) -> None:
    page, _state = _page(qtbot)
    page.feature_boxes["navigation"].setChecked(True)
    page.resolution.combo.setCurrentIndex(1)
    page.starter_counts["chests"].setValue(3)
    page.ask_preset_name = lambda: "My look"  # type: ignore[method-assign]
    assert page.save_preset() == "My look"
    saved = app_settings.load().option_presets["My look"]
    assert saved["resolution"] == [384, 216] and saved["features"]["navigation"] is True
    assert "seed" not in saved and "packs" not in saved and "project_name" not in saved
    assert page.preset_combo.findData("My look") >= 0
    page.apply_preset_named(DEFAULTS_ITEM)  # back to the defaults
    assert (
        page.resolution.value() == (640, 360) and not page.feature_boxes["navigation"].isChecked()
    )
    assert page.starter_counts["chests"].value() == 1
    page.seed_box.setValue(4242)
    assert page.apply_preset_named("My look")
    assert page.resolution.value() == (384, 216) and page.feature_boxes["navigation"].isChecked()
    assert page.starter_counts["chests"].value() == 3
    assert page.seed_box.value() == 4242  # a preset never changes the seed


def test_apply_preset_ignores_unknown_keys_and_the_other_archetype_input() -> None:
    cfg = config.default_for("T", [REF])
    preset = options.to_preset(config.default_for("A", [REF], archetype="arpg"))
    preset["mystery"] = 1
    preset["features"]["unknown_feature"] = True
    out = options.apply_preset(cfg, preset)
    assert set(out.input) == set(cfg.input)  # the action bindings stayed turn-based
    assert "unknown_feature" not in out.features
    with pytest.raises(ValueError):
        options.apply_preset(cfg, {"resolution": [10, 10]})


def test_managing_presets_renames_and_deletes(qtbot) -> None:
    page, _state = _page(qtbot)
    settings = app_settings.load()
    settings.option_presets = {"a": options.default_preset(), "b": options.default_preset()}
    app_settings.save(settings)

    def run(dialog: ManagePresetsDialog) -> bool:
        dialog.ask_name = lambda current: "renamed"  # type: ignore[method-assign]
        dialog.list.setCurrentRow(0)
        dialog.rename_current()
        dialog.list.setCurrentRow(1)
        dialog.delete_current()
        return True

    page.run_dialog = run  # type: ignore[method-assign]
    page.manage_presets()
    assert sorted(app_settings.load().option_presets) == ["renamed"]


def test_key_capture_fills_a_cell_and_escape_cancels(qtbot) -> None:
    page, state = _page(qtbot)
    page.advanced.set_open(True)
    table = page.input_table
    row = next(r for r in range(table.rowCount()) if table.item(r, 0).text() == "interact")
    table.start_capture(row, 1)
    assert table.item(row, 1).text() == "Press a key…" and table.is_capturing()
    QTest.keyClick(table, Qt.Key.Key_F)
    assert table.item(row, 1).text() == "E, Space, F"
    table.start_capture(row, 1)
    QTest.keyClick(table, Qt.Key.Key_Escape)
    assert table.item(row, 1).text() == "E, Space, F"  # cancelled: unchanged
    table.start_capture(row, 1)
    QTest.keyClick(table, Qt.Key.Key_Return)
    assert table.item(row, 1).text().endswith("Enter")
    assert page.validate(state) == []
    assert options.key_name("Return") == "Enter" and options.key_name("Ctrl") is None


def test_the_preview_renders_after_a_pause_and_the_reroll_changes_the_seed(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "basic16"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    state.config = config.default_for("T", [REF])
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    with qtbot.waitSignal(page.preview.rendered, timeout=20000):
        page.preview.flush()
    assert page.preview.last_png.startswith(b"\x89PNG")
    seed_before = page.seed_box.value()
    with qtbot.waitSignal(page.preview.rendered, timeout=20000):
        page.starter_counts["decorations"].setValue(20)  # debounced 200 ms, then rendered
    page.preview.reroll_button.click()
    assert page.seed_box.value() != seed_before
    assert "can differ" in page.preview.note_label.text()


def test_the_legend_is_five_translated_labels_and_the_image_is_just_the_map(qtbot) -> None:
    import io

    from PIL import Image
    from PySide6.QtCore import QCoreApplication, QTranslator

    from rpggen.gui.widgets.map_preview import MapPreviewWidget

    class Shout(QTranslator):
        def translate(self, context, source, disambiguation=None, n=-1):  # type: ignore[no-untyped-def]
            return source.upper() if context == "MapPreviewWidget" else ""

    plain = MapPreviewWidget()
    qtbot.addWidget(plain)
    assert [label.text() for label in plain.legend_labels.values()] == [
        "start",
        "villager",
        "enemy",
        "chest",
        "east exit",
    ]
    translator = Shout()
    QCoreApplication.installTranslator(translator)
    try:
        shouted = MapPreviewWidget()
        qtbot.addWidget(shouted)
        assert [label.text() for label in shouted.legend_labels.values()][0] == "START"
        assert len(shouted.legend_labels) == len(shouted.legend_dots) == 5
    finally:
        QCoreApplication.removeTranslator(translator)

    state = WizardState(pack_sources=[SYNTH / "basic16"])
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    state.config = config.default_for("T", [REF])
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    with qtbot.waitSignal(page.preview.rendered, timeout=20000):
        page.preview.flush()
    image = Image.open(io.BytesIO(page.preview.last_png))
    assert image.height * 40 == image.width * 24  # the 40 x 24 map and nothing underneath


# ------------------------------------------------------------------------ the areas of a world (T13.20)


def _starter_box(page: OptionsPage):
    return page.starter_box


def test_the_areas_table_is_off_until_asked_for_and_stores_the_rows(qtbot) -> None:
    page, state = _page(qtbot)
    box = _starter_box(page)
    table = box.areas
    assert not table.enabled() and table.areas() is None
    assert box.world.isHidden(), "no world: no world preview"
    page.leave(state)
    assert "areas" not in state.config.starter_map, "off: today's starter map and field"
    # switching it on starts with the village and a field
    table.enable_box.setChecked(True)
    assert [r["name"] for r in table.rows()] == ["Village", "Field"]
    assert table.table.rowCount() == 2
    assert not box.world.isHidden() and box.world.plan is not None
    row = table.add_row("Woods")
    table.set_value(row, "biome", "forest")
    table.set_value(row, "width", 28)
    table.set_value(row, "enemies", 3)
    page.leave(state)
    assert state.config.starter_map["areas"] == [
        {"name": "Village", "biome": "village", "size": [32, 20], "enemies": 2, "chests": 1},
        {"name": "Field", "biome": "field", "size": [32, 20], "enemies": 2, "chests": 1},
        {"name": "Woods", "biome": "forest", "size": [28, 20], "enemies": 3, "chests": 1},
    ]
    assert page.validate(state) == []
    from rpggen import schema

    schema.validate("config", state.config.to_json())
    # coming back shows the same table
    page.enter(state)
    assert _starter_box(page).areas.enabled()
    assert [r["name"] for r in _starter_box(page).areas.rows()] == ["Village", "Field", "Woods"]


def test_every_change_to_the_areas_table_is_undoable(qtbot) -> None:
    page, _state = _page(qtbot)
    table = _starter_box(page).areas
    assert not table.undo_button.isEnabled()
    table.enable_box.setChecked(True)
    row = table.add_row("Cave")
    table.set_value(row, "biome", "cave")
    table.set_value(row, "chests", 4)
    assert table.move_row(row, -1)
    assert [r["name"] for r in table.rows()] == ["Village", "Cave", "Field"]
    assert table.remove_row(2)
    assert [r["name"] for r in table.rows()] == ["Village", "Cave"]
    # the cell widgets write through the same path
    table.table.cellWidget(1, 5).setValue(7)
    assert table.rows()[1]["chests"] == 7
    table.table.item(1, 0).setText("Old mine")
    assert table.rows()[1]["name"] == "Old mine"
    # ... and every step comes back, one at a time
    expected = [
        (["Village", "Cave"], 7),
        (["Village", "Cave"], 4),
        (["Village", "Cave", "Field"], 4),
        (["Village", "Field", "Cave"], 4),
        (["Village", "Field", "Cave"], 1),
    ]
    for names, chests in expected:
        assert table.undo()
        rows = table.rows()
        assert [r["name"] for r in rows] == names
        assert next(r for r in rows if r["name"] == "Cave")["chests"] == chests
    assert table.undo() and table.rows()[2]["biome"] == "field"
    assert table.undo() and [r["name"] for r in table.rows()] == ["Village", "Field"]
    assert table.undo() and not table.enabled(), "the box itself is the first step"
    assert not table.undo() and not table.undo_button.isEnabled()


def test_a_table_with_a_problem_says_why_and_is_not_stored(qtbot) -> None:
    page, state = _page(qtbot)
    table = _starter_box(page).areas
    table.enable_box.setChecked(True)
    table.table.item(1, 0).setText("Village")
    assert "two areas are called" in table.error.text() and not table.error.isHidden()
    assert table.areas() is None
    assert _starter_box(page).world.isHidden(), "nothing to draw for a table that is not valid"
    page.leave(state)
    assert "areas" not in state.config.starter_map
    assert table.undo() and table.error.isHidden()
    for _ in range(20):
        table.add_row()
    assert len(table.rows()) == 12 or not table.add_button.isEnabled()


def test_the_world_preview_draws_one_tile_per_area(qtbot) -> None:
    page, _state = _page(qtbot)
    box = _starter_box(page)
    box.areas.enable_box.setChecked(True)
    box.areas.add_row("Woods")
    box.areas.add_row("Mine")
    world = box.world
    plan = world.plan
    assert plan is not None and [a["name"] for a in plan["areas"]] == [
        "Village",
        "Field",
        "Woods",
        "Mine",
    ]
    tiles = world.tiles()
    assert sorted(tiles) == ["field", "mine", "starter_map", "woods"], "one tile per area"
    rects = list(tiles.values())
    assert not any(a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1 :])
    # the field lies east of the village, and every door pair has its mark
    assert tiles["field"].left() > tiles["starter_map"].right()
    pairs = {tuple(sorted((a["id"], d["to"]))) for a in plan["areas"] for d in a["doors"]}
    assert len(world.door_marks()) == len(pairs)
    # a click chooses an area, which is then the one drawn cell by cell
    assert world.chosen == "field"
    chosen: list[str] = []
    world.areaChosen.connect(chosen.append)
    world.resize(520, 420)
    QTest.mouseClick(world, Qt.MouseButton.LeftButton, pos=tiles["woods"].center())
    assert world.chosen == "woods" and chosen == ["woods"]
    assert world.area_at(tiles["mine"].center()) == "mine"
    world.grab()  # painting it does not raise


def test_rearranging_one_area_leaves_the_others_as_they_are(qtbot) -> None:
    page, state = _page(qtbot)
    box = _starter_box(page)
    box.areas.enable_box.setChecked(True)
    box.areas.add_row("Woods")
    before = box.world.plan
    box.world.choose("starter_map")
    assert not box.reroll_area.isEnabled() and not box.reroll_chosen_area(), "not the village"
    box.world.choose("woods")
    assert box.reroll_area.isEnabled()
    box.reroll_area.click()
    after = box.world.plan
    from rpggen.core import world_plan

    assert world_plan.area_of(after, "field") == world_plan.area_of(before, "field")
    assert (
        world_plan.area_of(after, "woods")["decorations"]
        != (world_plan.area_of(before, "woods")["decorations"])
    )
    assert (
        world_plan.area_of(after, "woods")["doors"] == world_plan.area_of(before, "woods")["doors"]
    )
    page.leave(state)
    assert state.config.starter_map["areas"][2]["reroll"] == 1
    assert box.areas.undo() and "reroll" not in box.areas.rows()[2]


def test_a_project_with_its_world_shows_the_table_fixed_but_takes_a_new_area(
    qtbot, tmp_path
) -> None:
    from rpggen.core import world_plan

    areas = [
        {"name": "Village", "biome": "village"},
        {"name": "Meadow", "biome": "field"},
        {"name": "Woods", "biome": "forest"},
    ]
    project = tmp_path / "game"
    (project / "game" / "maps").mkdir(parents=True)
    for name in ("starter_map", "meadow", "woods"):
        (project / "game" / "maps" / f"{name}.tscn").write_text("x")
    stored = world_plan.plan(areas, 7)
    world_plan.save(project, stored)
    cfg = config.default_for("T", [REF])
    cfg.starter_map = {"areas": world_plan.normalized(areas)}
    state = WizardState(config=cfg, target=project, regenerating=True)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    box = _starter_box(page)
    table = box.areas
    assert not table.note.isHidden()
    assert "This project has its world already" in table.note.text()
    assert "game/maps/<area>.tscn" in table.note.text()
    # the rows of the world cannot be changed, removed or moved
    assert all(table.is_locked(r) for r in range(3))
    assert not table.set_value(1, "biome", "cave") and not table.remove_row(1)
    assert not table.move_row(2, -1)
    assert not table.table.cellWidget(1, 1).isEnabled()
    assert not box.reroll_area.isEnabled(), "rearranging is for before the first generation"
    # the preview is the stored world, whatever the seed is now
    assert box.world.plan["grid"] == stored["grid"]
    # a new row is allowed, joined to the area it names
    row = table.add_row("Old mine")
    assert not table.is_locked(row) and table.rows()[row]["join"] == "Village"
    assert table.table.cellWidget(row, 6).isEnabled()
    assert table.set_value(row, "biome", "cave") and table.set_value(row, "join", "Woods")
    plan = box.world.plan
    assert [a["id"] for a in plan["areas"]] == ["starter_map", "meadow", "woods", "old_mine"]
    assert [d["to"] for d in world_plan.area_of(plan, "old_mine")["doors"]] == ["woods"]
    for area in stored["areas"]:
        assert plan["grid"][area["id"]] == stored["grid"][area["id"]]
    page.leave(state)
    assert state.config.starter_map["areas"][3] == {
        "name": "Old mine",
        "biome": "cave",
        "size": [32, 20],
        "enemies": 2,
        "chests": 1,
        "join": "Woods",
    }
    assert "size" not in state.config.starter_map, "the starter map's own options stay as they were"


def test_advanced_has_the_repair_generated_maps_box(qtbot) -> None:
    """T13.24: on by default; off is stored as repair_world: false."""
    page, state = _page(qtbot)
    box = page.repair_box
    assert box.objectName() == "repairWorld" and box.isChecked()
    assert box.text() == "Repair generated maps after a build"
    page.leave(state)
    assert state.config.repair_world is True and "repair_world" not in state.config.to_json()
    box.setChecked(False)
    page.leave(state)
    assert state.config.repair_world is False
    assert state.config.to_json()["repair_world"] is False
    page.enter(state)
    assert not page.repair_box.isChecked()

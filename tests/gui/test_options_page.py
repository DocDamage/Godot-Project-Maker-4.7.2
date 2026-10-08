from __future__ import annotations

from rpggen.core import config, options
from rpggen.gui.pages.options_page import OptionsPage
from rpggen.gui.state import WizardState

REF = config.PackRef("x", "C:/x", "0" * 64, "folder")


# ------------------------------------------------------------------------ core


def test_demo_needs_dialogue_combat_and_save() -> None:
    feats = config.default_features()
    assert options.missing_deps(feats, "demo") == []
    feats["combat"] = False
    assert options.missing_deps(feats, "demo") == ["combat"]
    assert options.effective_features(feats)["demo"] is False
    assert options.missing_deps(feats, "debug_tools") == []


def test_tiles_hint_and_presets() -> None:
    assert options.tiles_hint((640, 360), 16) == "≈ 40 × 22.5 tiles on screen"
    assert options.preset_index(options.RESOLUTION_PRESETS, (640, 360)) == 3
    assert options.preset_index(options.RESOLUTION_PRESETS, (700, 400)) == 4


def test_layer_rules() -> None:
    layers = ["Ground", "Walls"]
    assert options.remove_layer(layers, "Ground") == layers
    assert options.remove_layer(layers, "Walls") == ["Ground"]
    assert options.add_layer(layers, " Fog ") == ["Ground", "Walls", "Fog"]
    assert options.add_layer(layers, "Walls") == layers
    assert options.layer_issues(["Walls"]) == [options.LAYER_GROUND_REQUIRED]
    assert options.layer_issues(["Ground", "Ground"]) == [options.LAYER_DUPLICATE]


def test_binding_text_keeps_untouched_fields() -> None:
    bindings = {"keys": ["W"], "joy_axes": [[1, -1.0]]}
    out = options.apply_binding_text(bindings, "keys", "W, Up")
    assert out == {"keys": ["W", "Up"], "joy_axes": [[1, -1.0]]}
    assert "keys" not in options.apply_binding_text(bindings, "keys", "")
    assert options.apply_binding_text(bindings, "joy_buttons", "11, 12")["joy_buttons"] == [11, 12]


# ------------------------------------------------------------------------ the page


def _page(qtbot) -> tuple[OptionsPage, WizardState]:
    state = WizardState(config=config.default_for("T", [REF]))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    return page, state


def test_defaults_are_shown_and_unchanged_by_leaving(qtbot) -> None:
    page, state = _page(qtbot)
    before = state.config.to_json()
    assert page.feature_boxes["demo"].isChecked()
    assert not page.feature_boxes["navigation"].isChecked()
    assert page.resolution.combo.currentData() == (640, 360)
    assert page.window_editor.combo.currentData() == (1280, 720)
    assert page.hint_label.text() == "≈ 40 × 22.5 tiles on screen"
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.to_json() == before


def test_unchecking_a_dependency_disables_demo_with_a_tooltip(qtbot) -> None:
    page, state = _page(qtbot)
    page.feature_boxes["combat"].setChecked(False)
    demo = page.feature_boxes["demo"]
    assert not demo.isChecked() and not demo.isEnabled()
    assert "Combat" in demo.toolTip()
    needs = page.feature_needs["demo"]
    assert not needs.isHidden() and needs.text() == "Needs: Combat"  # in plain sight
    page.leave(state)
    assert state.config.features["demo"] is False and state.config.features["combat"] is False
    page.feature_boxes["combat"].setChecked(True)
    assert demo.isEnabled() and demo.isChecked() and "Requires" not in demo.toolTip()
    assert needs.isHidden()


def test_resolution_presets_custom_and_hint(qtbot) -> None:
    page, state = _page(qtbot)
    page.resolution.combo.setCurrentIndex(0)
    assert page.resolution.value() == (320, 180)
    assert not page.resolution.width_box.isEnabled()
    assert page.hint_label.text() == "≈ 20 × 11.25 tiles on screen"
    page.resolution.combo.setCurrentIndex(4)  # Custom
    assert page.resolution.width_box.isEnabled()
    page.resolution.width_box.setValue(800)
    page.resolution.height_box.setValue(448)
    page.window_editor.combo.setCurrentIndex(3)
    page.leave(state)
    assert state.config.resolution == (800, 448)
    assert state.config.window_size == (1920, 1080)


def test_custom_resolution_is_restored_as_custom(qtbot) -> None:
    state = WizardState(config=config.default_for("T", [REF]))
    state.config.resolution = (700, 400)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.enter(state)
    assert page.resolution.combo.currentData() is None
    assert page.resolution.value() == (700, 400)


def test_layers_add_remove_reorder_and_ground_is_protected(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.layers() == config.DEFAULT_MAP_LAYERS
    page.layer_list.setCurrentRow(0)
    assert not page.remove_layer_button.isEnabled()
    page.layer_name.setText("Fog")
    page.add_layer_button.click()
    assert page.layers()[-1] == "Fog"
    page.layer_list.setCurrentRow(len(page.layers()) - 1)
    page.up_button.click()
    assert page.layers()[-2] == "Fog"
    page.remove_layer_button.click()
    page.layer_list.setCurrentRow(1)
    page.remove_layer_button.click()
    assert "GroundDetails" not in page.layers()
    page.layer_name.setText("Walls")  # duplicate is ignored
    page.add_layer_button.click()
    assert page.layers().count("Walls") == 1
    page.leave(state)
    assert state.config.map_layers == page.layers()
    assert state.config.map_layers[0] == "Ground"


def test_a_missing_ground_layer_is_an_error(qtbot) -> None:
    page, state = _page(qtbot)
    page.layer_list.item(0).setText("Floor")
    assert [i.severity.value for i in page.validate(state)] == ["error"]
    page.layer_list.item(0).setText("Ground")
    assert page.validate(state) == []


def test_advanced_seed_and_input_table(qtbot) -> None:
    page, state = _page(qtbot)
    assert page.advanced_body.isHidden()
    page.advanced.set_open(True)
    assert not page.advanced_body.isHidden()
    page.seed_box.setValue(777)
    row = next(
        r
        for r in range(page.input_table.rowCount())
        if page.input_table.item(r, 0).text() == "interact"
    )
    page.input_table.item(row, 1).setText("F, Space")
    page.input_table.item(row, 2).setText("1")
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.seed == 777
    assert state.config.input["interact"]["keys"] == ["F", "Space"]
    assert state.config.input["interact"]["mouse_buttons"] == [1]
    assert state.config.input["move_up"]["joy_axes"] == [[1, -1.0]]  # kept
    config.GeneratorConfig.from_json(state.config.to_json())


def test_a_bad_binding_number_blocks_next(qtbot) -> None:
    page, state = _page(qtbot)
    page.input_table.item(0, 3).setText("two")
    issues = page.validate(state)
    assert len(issues) == 1 and "whole numbers" in issues[0].message
    page.input_table.item(0, 3).setText("11")
    assert page.validate(state) == []


def test_changes_emit_changed_for_revalidation(qtbot) -> None:
    page, _state = _page(qtbot)
    with qtbot.waitSignal(page.changed, timeout=500):
        page.feature_boxes["save"].setChecked(False)


def test_the_hint_uses_the_tile_size_of_the_packs_and_a_resolution_is_suggested(qtbot) -> None:
    state = WizardState(config=config.default_for("T", [REF], base_tile_size=48))
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    page.resolution.combo.setCurrentIndex(3)  # 640 x 360
    assert page.hint_label.text() == "≈ 13.3 × 7.5 tiles on screen"
    texts = [page.resolution.combo.itemText(i) for i in range(4)]
    assert [t.endswith("(suggested)") for t in texts] == [False, False, False, True]
    state16 = WizardState(config=config.default_for("T", [REF]))
    page.enter(state16)
    page.resolution.combo.setCurrentIndex(0)
    assert page.resolution.combo.itemText(0).endswith("(suggested)")
    assert not page.resolution.combo.itemText(3).endswith("(suggested)")


def test_version_control_offers_three_ways_to_handle_the_pack_art(qtbot) -> None:
    page, state = _page(qtbot)
    assert set(page.pack_art_radios) == {"commit", "lfs", "ignore"}
    assert page.pack_art_radios["commit"].isChecked()  # the default
    assert "public" in page.findChild(type(page.hint_label), "packArtNote").text()
    page.pack_art_radios["ignore"].setChecked(True)
    page.leave(state)
    assert state.config.git == {"pack_art": "ignore"}
    assert state.config.to_json()["git"] == {"pack_art": "ignore"}
    page.enter(state)  # coming back shows the choice that was made
    assert page.pack_art_radios["ignore"].isChecked()
    page.pack_art_radios["commit"].setChecked(True)
    page.leave(state)
    assert state.config.git == {} and "git" not in state.config.to_json()  # the default is omitted


def test_export_targets_default_to_windows_and_keep_at_least_one(qtbot) -> None:
    page, state = _page(qtbot)
    boxes = page.export_target_boxes
    assert list(boxes) == ["windows", "web", "linux", "macos"]
    assert [k for k, b in boxes.items() if b.isChecked()] == ["windows"]
    boxes["macos"].setChecked(True)
    boxes["web"].setChecked(True)
    page.leave(state)
    assert state.config.export_targets == ["windows", "web", "macos"]
    assert state.config.to_json()["export_targets"] == ["windows", "web", "macos"]
    page.enter(state)  # coming back shows the choice that was made
    assert [k for k, b in boxes.items() if b.isChecked()] == ["windows", "web", "macos"]
    for key in ("windows", "web", "macos"):
        boxes[key].setChecked(False)
    assert boxes["macos"].isChecked()  # the last target cannot be turned off
    boxes["windows"].setChecked(True)
    boxes["macos"].setChecked(False)
    page.leave(state)
    assert state.config.export_targets == ["windows"]
    assert "export_targets" not in state.config.to_json()  # the default is omitted


# ------------------------------------------------------------------------ T12.37: the summary


def test_summary_core_follows_the_options() -> None:
    feats = config.default_features()
    sm = config.starter_map_defaults()
    summary = options.summarize("turn_based", feats, sm, 16, (640, 360))
    assert summary.maps == ["Starter map", "Second area", "1 interior"]
    assert "Demo scene" in summary.systems and "Navigation" not in summary.systems
    assert summary.tiles == "≈ 40 × 22.5 tiles on screen" and summary.tile_size == 16
    feats["demo"] = False
    bare = options.summarize("arpg", feats, {**sm, "buildings": 3}, 32, (640, 360))
    assert bare.maps == [] and "Demo scene" not in bare.systems
    more = options.summarize(
        "arpg", config.default_features(), {**sm, "buildings": 3}, 16, (640, 360)
    )
    assert more.maps[-1] == "3 interiors"


def test_estimates() -> None:
    timings = {"import": 10.0, "build": 20.0, "smoke": 10.0}
    assert options.estimate_generation_seconds(timings, 20, 40) == 80.0
    assert options.estimate_generation_seconds({}, 20, 40) is None
    assert options.estimate_generation_seconds(timings, 0, 40) is None
    assert options.estimate_generation_seconds(timings, 20, 0) is None
    assert options.estimate_project_bytes(1_000_000) == 1_800_000
    assert options.estimate_project_bytes(-5) == 0


def test_the_summary_follows_feature_toggles_and_the_screen(qtbot) -> None:
    page, _state = _page(qtbot)
    summary = page.summary
    assert "Turn-based RPG" in summary.archetype_label.text()
    assert "Starter map" in summary.maps_label.text() and "1 interior" in summary.maps_label.text()
    chips = [c.text() for c in summary.chips]
    assert "Demo scene" in chips and "Navigation" not in chips
    page.feature_boxes["navigation"].setChecked(True)
    assert "Navigation" in [c.text() for c in summary.chips]
    page.feature_boxes["combat"].setChecked(False)  # the demo needs combat: it goes with it
    chips = [c.text() for c in summary.chips]
    assert "Combat" not in chips and "Demo scene" not in chips
    assert "No starter maps" in summary.maps_label.text()
    page.resolution.set_value((320, 180))
    assert "20 × 11.25" in summary.tiles_label.text()
    page.starter_counts["buildings"].setValue(3)
    page.feature_boxes["combat"].setChecked(True)
    assert (
        "3 interiors" in summary.maps_label.text() or "No starter maps" in summary.maps_label.text()
    )


def test_the_time_estimate_is_hidden_without_saved_timings(qtbot, monkeypatch) -> None:
    from rpggen.core import app_settings

    app_settings.update(phase_timings={}, timing_assets=0)
    page, _state = _page(qtbot)
    assert page.summary.time_label.isHidden()
    app_settings.update(phase_timings={"build": 30.0}, timing_assets=10)
    page.refresh_summary()
    assert page.summary.time_label.isHidden()  # no catalog: no asset count to scale to
    from pathlib import Path

    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui import workers

    synth = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic" / "basic16"
    state = WizardState(pack_sources=[synth], config=config.default_for("T", [REF]))
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    page.enter(state)
    assert not page.summary.time_label.isHidden() and "about" in page.summary.time_label.text()
    assert not page.summary.size_label.isHidden()
    assert any(unit in page.summary.size_label.text() for unit in ("KB", "MB"))


def test_the_summary_moves_to_a_right_hand_column_when_very_wide(qtbot) -> None:
    page, _state = _page(qtbot)
    page.resize(1000, 700)
    assert not page.summary_on_side and page.side.isHidden()
    page.resize(1300, 700)
    assert page.summary_on_side and not page.side.isHidden()
    assert page.summary.parentWidget() is page.side
    page.resize(900, 700)
    assert not page.summary_on_side and page.summary.isVisible()

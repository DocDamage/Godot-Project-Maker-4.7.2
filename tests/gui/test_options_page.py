from __future__ import annotations

from pathlib import Path

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


# ------------------------------------------------------------------------ built-in presets and dependencies (T13.06)


def test_the_built_in_presets_head_the_combo_before_the_users(qtbot) -> None:
    from rpggen.gui.models import options_model as om

    page, state = _page(qtbot)
    page.ask_preset_name = lambda: "Mine"  # type: ignore[method-assign]
    assert page.save_preset() == "Mine"
    combo = page.preset_combo
    texts = [combo.itemText(i) for i in range(combo.count())]
    assert texts[:4] == ["Choose a preset…", "Everything", "Minimal", "Just the tilesets"]
    assert texts[-1] == "Mine" and combo.itemData(combo.count() - 1) == "Mine"
    assert combo.itemData(1) == om.DEFAULTS_ITEM
    # choosing a built-in applies it and the combo goes back to its prompt
    minimal = combo.findData(om.BUILTIN_PREFIX + "minimal")
    combo.setCurrentIndex(minimal)
    combo.activated.emit(minimal)
    assert combo.currentIndex() == 0
    assert not page.feature_boxes["combat"].isChecked()
    assert not page.feature_boxes["demo"].isChecked() and not page.feature_boxes["demo"].isEnabled()
    assert page.feature_boxes["dialogue"].isChecked()
    page.leave(state)
    assert state.config.features["combat"] is False and state.config.features["save"] is True
    # a built-in's name is not free for a preset of your own; the page says so
    said = []
    page.show_message = lambda title, text: said.append(text)  # type: ignore[method-assign]
    page.ask_preset_name = lambda: "Minimal"  # type: ignore[method-assign]
    assert page.save_preset() is None
    assert said and "built-in" in said[0]
    # Manage… lists only the user's presets, so a built-in cannot be renamed or deleted there
    seen = []

    def run(dialog) -> None:
        seen.append([dialog.list.item(i).text() for i in range(dialog.list.count())])
        dialog.list.setCurrentRow(0)
        dialog.delete_current()

    page.run_dialog = run  # type: ignore[method-assign]
    page.manage_presets()
    assert seen == [["Mine"]]
    texts = [combo.itemText(i) for i in range(combo.count())]
    assert texts == ["Choose a preset…", "Everything", "Minimal", "Just the tilesets"]


def test_turning_off_combat_disables_and_clears_navigation(qtbot) -> None:
    page, state = _page(qtbot)
    navigation = page.feature_boxes["navigation"]
    navigation.setChecked(True)
    assert navigation.isEnabled() and navigation.isChecked()
    page.feature_boxes["combat"].setChecked(False)
    assert not navigation.isChecked() and not navigation.isEnabled()
    needs = page.feature_needs["navigation"]
    assert not needs.isHidden() and needs.text() == "Needs: Combat"
    page.leave(state)
    assert state.config.features["navigation"] is False
    page.feature_boxes["combat"].setChecked(True)
    assert navigation.isEnabled() and navigation.isChecked(), "the wish comes back"
    assert needs.isHidden()


# ------------------------------------------------------------------------ the arcade kinds (T16.16)

ARCADE_BOXES = {"shmup": "shmupBox", "run_and_gun": "runAndGunBox", "racing": "racingBox"}


def _arcade_page(qtbot, kind: str, **starter) -> tuple[OptionsPage, WizardState]:
    cfg = config.default_for("T", [REF], archetype=kind)
    cfg.starter_map = dict(starter)
    state = WizardState(config=cfg, archetype=kind)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.resize(828, 900)
    page.show()
    page.enter(state)
    return page, state


def test_the_numbers_of_an_arcade_kind_in_words() -> None:
    assert options.arcade_numbers("shmup", {}) == ["vertical", "3 stages", "3 lives"]
    assert options.arcade_numbers("shmup", {"stages": 1, "lives": 1}) == [
        "vertical",
        "1 stage",
        "1 life",
    ]
    assert options.arcade_numbers("run_and_gun", {"grapple": True, "jump": False}) == [
        "3 stages",
        "3 lives",
        "grapple, no jump",
    ]
    assert options.arcade_numbers("racing", {"rivals": 1}) == ["4 tracks", "3 laps", "1 rival"]
    assert options.arcade_numbers("racing", {"laps": 99}) == [], "options that make no plan"
    assert options.arcade_numbers("turn_based", {}) == []
    summary = options.summarize("shmup", config.default_features("shmup"), {}, 16, (640, 360))
    assert summary.numbers == ("vertical", "3 stages", "3 lives")
    assert "Demo scene" not in summary.systems and "Navigation" not in summary.systems


def test_a_planned_run_in_words_and_the_estimate_of_a_kind() -> None:
    from rpggen.core import stage_plan, track_plan, wave_plan

    waves = wave_plan.plan({}, 5)
    count = sum(len(stage["waves"]) for stage in waves["list"])
    assert options.plan_text("shmup", waves, {}) == f"3 stages, {count} waves, 3 bosses"
    stages = stage_plan.plan({"stages": 1}, 5)
    text = options.plan_text("run_and_gun", stages, {"stages": 1})
    assert text.startswith("1 stage, ") and text.endswith(" waves, 1 boss")
    carried = sum(1 for wave in stages["list"][0]["waves"] if wave["enemy"] == "pickup")
    assert carried and f", {len(stages['list'][0]['waves']) - carried} waves" in text
    tracks = track_plan.plan({"rivals": 2}, 5)
    assert options.plan_text("racing", tracks, {"rivals": 2}) == "4 tracks of 3 laps, 2 rivals"
    # the estimate learns per kind, and says nothing of a kind that was never timed
    timed = {"racing": [100.0, 40.0]}
    assert options.estimate_kind_seconds(timed, "racing", 200) == 80.0
    assert options.estimate_kind_seconds(timed, "shmup", 200) is None
    assert options.estimate_kind_seconds({"racing": [0.0, 40.0]}, "racing", 200) is None


def test_the_pictures_of_a_wave_plan_and_of_a_stage_plan() -> None:
    from rpggen.core import map_preview, stage_plan, wave_plan

    waves = wave_plan.plan({"stages": 2}, 3)
    chart = map_preview.render_waves(waves, scale=2)
    rects = map_preview.wave_rects(waves, 2)
    assert list(rects) == ["stage_01", "stage_02"]
    last = rects["stage_02"]
    assert chart.size == (last[0] + last[2], map_preview.WAVE_HEIGHT * 2)
    colours = {colour for _n, colour in chart.getcolors(1 << 16)}
    assert map_preview.WAVE_BOSS in colours and map_preview.WAVE_COLORS["popcorn"] in colours
    assert map_preview.WAVE_COLORS["carrier"] in colours, "the power-up carrier of every stage"
    left, top, width, _height = rects["stage_01"]
    assert chart.getpixel((left + width // 2, top + 6)) == map_preview.WAVE_BOSS, "at the top"

    run = stage_plan.plan({"stages": 2}, 3)
    strip = map_preview.render_stage_strip(run, scale=2)
    places = map_preview.strip_rects(run, 2)
    first = run["list"][0]
    assert places["stage_01"][2:] == (len(first["tiles"][0]) * 2, len(first["tiles"]) * 2)
    assert strip.size[0] == places["stage_01"][2]
    assert places["stage_02"][1] == places["stage_01"][3] + map_preview.STRIP_GAP
    colours = {colour for _n, colour in strip.getcolors(1 << 16)}
    for mark in ("start", "enemy", "pickup", "boss"):
        assert map_preview.STRIP_MARKERS[mark] in colours, mark
    assert map_preview.STRIP_TILES["#"] in colours and map_preview.STRIP_ARENA in colours
    assert map_preview.STRIP_MARKERS["grapple"] not in colours, "a soldier that jumps has none"
    arm = stage_plan.plan({"grapple": True, "jump": False}, 3)
    points = map_preview.grapple_points(arm["list"][0]["tiles"])
    assert points, "something to swing from"
    armed = map_preview.render_stage_strip(arm, scale=2)
    assert (
        armed.getpixel((points[0][0] * 2, points[0][1] * 2))
        == (map_preview.STRIP_MARKERS["grapple"])
    )


def test_an_arcade_kind_has_its_box_in_place_of_the_starter_map(qtbot) -> None:
    summaries = {
        "shmup": ("<b>Shoot 'em up</b> · vertical · 3 stages · 3 lives", "Stages: 3 stages, "),
        "run_and_gun": ("<b>Run and gun</b> · 3 stages · 3 lives", "Stages: 3 stages, "),
        "racing": ("<b>Racing</b> · 4 tracks · 3 laps · 3 rivals", "Tracks: 4 tracks of 3 laps"),
    }
    for kind, name in ARCADE_BOXES.items():
        page, state = _arcade_page(qtbot, kind)
        before = state.config.to_json()
        box = page.arcade_box
        assert box is not None and box.objectName() == name and not box.isHidden()
        assert [b.isHidden() for b in page.arcade_boxes.values()].count(False) == 1
        assert page.starter_box.isHidden() and page.world_box.isHidden()
        assert page.imported_box.isHidden() and page.layers_box.isHidden()
        assert page.feature_boxes["demo"].isHidden() and page.feature_boxes["navigation"].isHidden()
        assert not page.feature_boxes["dialogue"].isHidden()
        assert box.values() == config.starter_map_defaults(kind)
        # the preview is drawn from the plan, with the plan in words under it
        assert box.plan is not None and len(box.plan["list"]) == (4 if kind == "racing" else 3)
        assert not box.preview.pixmap().isNull()
        assert box.preview.pixmap().height() <= box.PREVIEW_HEIGHT
        assert box.summary.text() == page.model.planner().summary(box.plan)
        assert len(box.legend_labels) == len(box.LEGEND) >= 5
        title, plan = summaries[kind]
        assert page.summary.archetype_label.text() == title
        assert page.summary.maps_label.text().startswith(plan)
        assert "Demo scene" not in [chip.text() for chip in page.summary.chips]
        assert page.validate(state) == []
        page.leave(state)
        assert state.config.to_json() == before, "the defaults are not written out"


def test_the_options_of_a_shoot_em_up_follow_its_box(qtbot) -> None:
    page, state = _arcade_page(qtbot, "shmup")
    box = page.arcade_box
    seen: list[int] = []
    page.changed.connect(lambda: seen.append(1))
    box.combos["orientation"].setCurrentIndex(box.combos["orientation"].findData("horizontal"))
    box.spins["stages"].setValue(5)
    box.checks["auto_fire"].setChecked(False)
    assert len(seen) == 3
    assert len(box.plan["list"]) == 5 and box.plan["orientation"] == "horizontal"
    assert box.summary.text() == "5 stages, 5 bosses, scrolling right"
    assert page.summary.archetype_label.text() == (
        "<b>Shoot 'em up</b> · horizontal · 5 stages · 3 lives"
    )
    assert box.spins["stages"].maximum() == 8 and box.spins["lives"].minimum() == 1
    # an added stage is a row of the options, named after the last
    assert box.add_row() and box.added_rows() == [{"name": "Stage 6"}]
    assert len(box.plan["list"]) == 6
    page.leave(state)
    assert state.config.starter_map == {
        "orientation": "horizontal",
        "stages": 5,
        "auto_fire": False,
        "added_stages": [{"name": "Stage 6"}],
    }
    box.reset.click()
    assert box.values() == config.starter_map_defaults("shmup")
    assert len(box.plan["list"]) == 3
    # the screen decides how long a stage is: the plan follows the resolution
    length = box.plan["list"][0]["length"]
    page.resolution.set_value((320, 180))
    assert box.plan["list"][0]["length"] != length and box.plan["view"] == [320, 180]


def test_a_soldier_without_the_arm_always_jumps_and_the_presets_of_the_kinds(qtbot) -> None:
    page, state = _arcade_page(qtbot, "run_and_gun")
    box = page.arcade_box
    grapple, jump = box.checks["grapple"], box.checks["jump"]
    assert jump.isChecked() and not jump.isEnabled(), "no arm: the box cannot be cleared"
    assert box.legend_items["grapple"].isHidden()
    labels = [page.preset_combo.itemText(i) for i in range(page.preset_combo.count())]
    assert labels[-2:] == ["Arcade classic", "Bionic"] and "Sunday drive" not in labels
    box.spins["stages"].setValue(2)
    assert page.apply_preset_named("__builtin__:bionic")
    assert grapple.isChecked() and not jump.isChecked() and jump.isEnabled()
    assert box.spins["stages"].value() == 2, "a preset of a kind keeps the other options"
    assert box.plan["jump"] is False and not box.legend_items["grapple"].isHidden()
    assert page.summary.archetype_label.text().endswith("2 stages · 3 lives · grapple, no jump")
    grapple.setChecked(False)
    assert jump.isChecked() and not jump.isEnabled(), "the arm goes: the jump comes back"
    assert page.validate(state) == []
    assert page.apply_preset_named("__builtin__:arcade_classic")
    assert box.combos["difficulty"].currentData() == "hard" and box.spins["lives"].value() == 3
    page.leave(state)
    assert state.config.starter_map == {"stages": 2, "difficulty": "hard"}

    race, race_state = _arcade_page(qtbot, "racing")
    labels = [race.preset_combo.itemText(i) for i in range(race.preset_combo.count())]
    assert labels[-1] == "Sunday drive" and "Bionic" not in labels
    assert race.apply_preset_named("__builtin__:sunday_drive")
    track = race.arcade_box
    assert track.combos["steering"].currentData() == "absolute"
    assert track.spins["rivals"].value() == 2 and track.checks["rubber_band"].isChecked()
    assert race.summary.archetype_label.text() == "<b>Racing</b> · 4 tracks · 3 laps · 2 rivals"
    assert track.add_row() and track.added_rows() == [{"name": "Track 5"}]
    assert len(track.plan["list"]) == 5
    assert track.remove_row() and track.added_rows() == []
    race.leave(race_state)
    assert race_state.config.starter_map == {"steering": "absolute", "rivals": 2}
    # the presets of the arcade kinds are no preset of the others, and their names are taken
    plain, _state = _page(qtbot)
    labels = [plain.preset_combo.itemText(i) for i in range(plain.preset_combo.count())]
    assert not {"Arcade classic", "Bionic", "Sunday drive"} & set(labels)
    assert not plain.apply_preset_named("__builtin__:bionic")
    assert not plain.model.save_preset("Bionic")
    assert options.kind_preset("bionic", "shmup", {}) is None
    assert options.kind_preset_keys("run_and_gun") == ["arcade_classic", "bionic"]


def test_the_stages_of_a_game_that_exists_are_kept_but_one_can_be_added(
    qtbot, tmp_path: Path
) -> None:
    from rpggen.core import wave_plan, world_plan

    target = tmp_path / "game"
    world, _notes = wave_plan.for_project(None, {"added_stages": [{"name": "Finale"}]}, 9)
    (target / "rpggen").mkdir(parents=True)
    (target / wave_plan.STAGES_FILE).parent.mkdir(parents=True)
    (target / wave_plan.STAGES_FILE).write_text("{}", encoding="utf-8")
    world_plan.save(target, world)
    assert wave_plan.exists(target)
    cfg = config.default_for("T", [REF], archetype="shmup")
    cfg.starter_map = {"added_stages": [{"name": "Finale"}]}
    state = WizardState(config=cfg, archetype="shmup", target=target, regenerating=True)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.show()
    page.enter(state)
    box = page.arcade_box
    assert page.model.starter_locked and not box.note.isHidden()
    assert "kept as they are" in box.note.text()
    assert not box.spins["stages"].isEnabled() and not box.reset.isEnabled()
    assert len(box.plan["list"]) == 4, "the stored plan, with the stage that was added"
    assert not box.remove_row(), "a stage that is built stays"
    assert box.add_row("Encore") and len(box.plan["list"]) == 5
    page.leave(state)
    assert state.config.starter_map == {"added_stages": [{"name": "Finale"}, {"name": "Encore"}]}

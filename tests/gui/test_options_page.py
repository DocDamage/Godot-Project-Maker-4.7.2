from __future__ import annotations

from pathlib import Path

from rpggen.core import config, options
from rpggen.gui.models.options_model import ViewState
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


# ------------------------------------------------------------------ T17.16: a farm, and the view

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _cat(pack: str):  # noqa: ANN202 - a catalog
    from rpggen.core import archive, catalog, inventory

    opened = archive.open_pack(SYNTH / pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


def _flags(monkeypatch, farm: bool = True, isometric: bool = True) -> None:
    from rpggen import features

    monkeypatch.setattr(features, "FARM_AVAILABLE", farm)
    monkeypatch.setattr(features, "ISOMETRIC_AVAILABLE", isometric)


def _kind_page(
    qtbot, kind: str, pack: str = "", projection: str = "top_down", **starter
) -> tuple[OptionsPage, WizardState]:
    cfg = config.default_for("T", [REF], archetype=kind)
    cfg.starter_map = dict(starter)
    cfg.projection = projection
    state = WizardState(config=cfg, archetype=kind, catalog=_cat(pack) if pack else None)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.resize(828, 900)
    page.show()
    page.enter(state)
    return page, state


def test_what_a_farm_needs_of_its_features_and_what_it_says_of_itself() -> None:
    """The demo of a farm does not need combat (T17.04 left the contradiction to this card),
    and since T17.24 the feature is shown: with it a farm has a cave to fight in."""
    farm = config.default_features("farm")
    assert farm["combat"] is False and farm["demo"] is True
    assert options.missing_deps(farm, "demo") == ["combat"], "the rule of the other kinds"
    assert options.missing_deps(farm, "demo", "farm") == []
    assert options.effective_features(farm, "farm") == farm
    assert options.effective_features(farm)["demo"] is False
    assert options.dependencies("farm")["demo"] == ("tilesets", "dialogue", "save")
    assert options.dependencies("farm")["navigation"] == ()
    assert options.dependencies("arpg") is options.DEPENDENCIES
    assert options.hidden_features("farm") == (), "combat is shown since T17.24: it gives a cave"
    assert options.hidden_features("racing") == options.ARCADE_HIDDEN
    assert options.hidden_features("metroidvania") == ("navigation",)
    assert options.hidden_features("turn_based") == ()
    assert "people of the village" in options.feature_text("navigation", "farm")
    assert options.feature_text("navigation", "arpg") == options.FEATURE_INFO["navigation"][2]
    # the numbers of the summary and the sentence of a dry run
    defaults = config.starter_map_defaults("farm")
    assert options.farm_numbers(defaults, 6) == ["28 days a season", "no animals", "6 crops"]
    chosen = {**defaults, "days_per_season": 7, "animals": "coop_and_barn"}
    assert options.farm_numbers(chosen) == ["7 days a season", "a coop and a barn"]
    assert options.farm_numbers({**defaults, "animals": "coop"}, 1)[1:] == ["a coop", "1 crop"]
    assert options.farm_numbers({"plot": "huge"}) == []
    summary = options.summarize("farm", farm, defaults, 16, (640, 360), None, 6)
    assert summary.numbers == ("28 days a season", "no animals", "6 crops")
    assert summary.world == "a medium farm with a medium plot"
    assert summary.maps == ["Starter map", "Second area", "1 interior"], "its village"
    assert "Combat" not in summary.systems and "Demo scene" in summary.systems
    cfg = config.default_for("T", [REF], archetype="farm")
    plans = options.plan_farm(cfg, None)
    text = options.farm_text(plans)
    assert text == (
        "a farm of 40 x 30 with a plot of 96 cells, a pond, 3 crops, 3 people, 4 festivals"
    )
    assert options.farm_text({**plans, "people": 1}).endswith("3 crops, 1 person, 4 festivals")
    assert options.farm_text({**plans, "festivals": 0}).endswith("3 crops, 3 people")


def test_a_farm_has_its_box_over_the_box_of_its_village(qtbot, monkeypatch) -> None:
    _flags(monkeypatch)
    page, state = _kind_page(qtbot, "farm")
    before = state.config.to_json()
    farm, village = page.farm_box, page.starter_box
    assert not farm.isHidden() and not village.isHidden()
    assert farm.title() == "Farm" and village.title() == "Village"
    body = farm.parentWidget().layout()
    assert body.indexOf(farm) < body.indexOf(village), "the farm first, its village under it"
    assert page.world_box.isHidden() and page.arcade_box is None
    assert not page.layers_box.isHidden(), "the village is a map of layers"
    # the village: the two counts its builder does not read are not shown
    for key in ("npcs", "enemies"):
        assert village.counts[key].isHidden() and village.count_labels[key].isHidden()
    for key in ("buildings", "chests", "decorations", "ground_patches"):
        assert not village.counts[key].isHidden()
    # the farm: every option of the config has its widget, with a name and a tooltip
    fields = {**farm.spins, **farm.combos, **farm.checks}
    own = set(config.starter_map_defaults("farm")) - set(config.starter_map_defaults())
    assert set(fields) | {"added_maps"} == own
    for key, widget in fields.items():
        assert widget.objectName() == f"farm_{key}" and widget.toolTip(), key
    assert farm.combos["farm_size"].currentText() == "Medium (40 x 30)"
    assert farm.combos["plot"].currentText() == "Medium (96 cells)"
    assert farm.combos["days_per_season"].currentData() == 28
    assert farm.combos["day_length"].currentText() == "Normal (14 minutes)"
    assert farm.spins["starting_money"].value() == 100
    # marriage (T17.26): how many can be courted, 2 unless changed, 0 to 6
    courtable = farm.spins["courtable"]
    assert courtable.value() == 2 and (courtable.minimum(), courtable.maximum()) == (0, 6)
    assert courtable.toolTip()
    assert farm.checks["fishing"].isChecked() and farm.checks["pass_out_loss"].isChecked()
    # combat is shown since T17.24 (it gives the farm a cave), off; the demo does not need it:
    # the page changes nothing by itself
    combat = page.feature_boxes["combat"]
    assert not combat.isHidden() and not combat.isChecked()
    assert "cave" in page.features.descriptions["combat"].text()
    demo = page.feature_boxes["demo"]
    assert not demo.isHidden() and demo.isEnabled() and demo.isChecked()
    assert page.feature_needs["demo"].isHidden()
    assert "keeps the shop" in page.features.descriptions["demo"].text()
    assert not page.feature_boxes["navigation"].isHidden()
    assert page.feature_boxes["navigation"].isEnabled()
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.to_json() == before, "a farm that is only looked at stays what it was"
    assert state.config.features["combat"] is False and state.config.features["demo"] is True
    # the summary names the kind with its numbers, the farm in words and the village's maps
    assert page.summary.archetype_label.text() == (
        "<b>Farm</b> · 28 days a season · no animals · 3 crops"
    )
    assert page.summary.farm_label.text() == "Farm: a medium farm with a medium plot"
    assert page.summary.maps_label.text() == "Village: Starter map, Second area, 1 interior"
    assert "Combat" not in [chip.text() for chip in page.summary.chips]
    # the features go back to a farm's own defaults, not to those of a game with battles
    page.feature_boxes["demo"].setChecked(False)
    page.features_reset.click()
    assert page.feature_boxes["demo"].isChecked()
    page.leave(state)
    assert state.config.features == config.default_features("farm")
    # another kind has the box of the starter map as it always was
    other, _state = _kind_page(qtbot, "turn_based")
    assert other.farm_box.isHidden() and other.starter_box.title() == "Starter map"
    assert not other.starter_box.counts["enemies"].isHidden()
    assert not other.feature_boxes["combat"].isHidden() and other.summary.farm_label.isHidden()


def test_the_options_of_a_farm_follow_its_box(qtbot, monkeypatch) -> None:
    from rpggen.core import farm_plan, map_preview

    _flags(monkeypatch)
    page, state = _kind_page(qtbot, "farm")
    box = page.farm_box
    plans = box.plans
    assert plans is not None and box.plan == plans["map"]
    assert plans["map"] == farm_plan.plan({}, state.config.seed), "the plan a run would make"
    assert not box.preview.pixmap().isNull()
    assert box.summary.text() == options.farm_text(plans)
    assert box.summary.text().startswith("a farm of 40 x 30 with a plot of 96 cells, a pond")
    # the legend names what the picture has, in the picture's colours
    assert list(box.legend_labels) == list(map_preview.FARM_ORDER)
    assert box.legend_labels["tillable"].text() == "plot"
    assert box.legend_labels["exit"].text() == "way to the village"
    assert not box.legend_items["water"].isHidden() and box.legend_items["fence"].isHidden()
    box.combos["animals"].setCurrentIndex(box.combos["animals"].findData("coop_and_barn"))
    assert [b["kind"] for b in box.plan["animal_houses"]] == ["coop", "barn"]
    assert not box.legend_items["fence"].isHidden() and not box.legend_items["gate"].isHidden()
    assert "a coop, a barn" in box.summary.text()
    assert page.summary.archetype_label.text().endswith("· a coop and a barn · 3 crops")
    box.combos["days_per_season"].setCurrentIndex(box.combos["days_per_season"].findData(14))
    box.combos["day_length"].setCurrentIndex(box.combos["day_length"].findData("short"))
    box.combos["farm_size"].setCurrentIndex(box.combos["farm_size"].findData("large"))
    box.spins["starting_money"].setValue(40)
    box.checks["fishing"].setChecked(False)
    assert box.plan["size"] == [48, 36]
    assert "14 days a season" in page.summary.archetype_label.text()
    assert page.summary.farm_label.text() == "Farm: a large farm with a medium plot, a coop, a barn"
    # the village beside it is still the starter map's
    page.starter_box.counts["buildings"].setValue(3)
    assert page.summary.maps_label.text().endswith("3 interiors")
    # added maps (T17.23): a row is a name and a kind, and each is a map of its own
    assert box.added_label.text() == "Added maps" and "a map of its own" in box.added_note.text()
    assert "not built" not in box.added_note.text()
    assert box.added.columnCount() == 2
    assert [box.added.horizontalHeaderItem(i).text() for i in range(2)] == ["Name", "Kind"]
    alone = box._pixmap.toImage().width()
    assert box.add_row() and box.add_row("Beach")
    first, second = box.kind_combo(0), box.kind_combo(1)
    assert [first.itemData(i) for i in range(first.count())] == ["forest", "beach", "cave"]
    assert [first.itemText(i) for i in range(first.count())] == ["Forest", "Beach", "Cave"]
    assert first.toolTip() and first.accessibleName()
    # the kind is the name's words until somebody chooses it
    assert (first.currentData(), second.currentData()) == ("forest", "beach")
    assert box.added_rows() == [
        {"name": "Map 1", "kind": "forest"},
        {"name": "Beach", "kind": "beach"},
    ]
    box.added.item(0, 0).setText("North shore")
    assert first.currentData() == "beach", "the kind follows the name"
    first.setCurrentIndex(first.findData("forest"))
    first.activated.emit(first.currentIndex())  # what choosing it by hand does
    box.added.item(0, 0).setText("Map 1")
    box.added.item(0, 0).setText("Sea view")
    assert first.currentData() == "forest", "a kind that was chosen stays"
    box.added.item(0, 0).setText("Map 1")
    assert box.plan["added_maps"] == ["Map 1", "Beach"]
    assert [(e["name"], e["kind"]) for e in box.plan["added"]] == [
        ("Map 1", "forest"),
        ("Beach", "beach"),
    ]
    # the picture has them beside the farm, and the words name them
    assert box._pixmap.toImage().width() > alone
    assert "a forest (Map 1), a beach (Beach)" in box.summary.text()
    assert page.summary.farm_label.text().endswith("a coop, a barn, a forest, a beach")
    assert page.validate(state) == []
    page.leave(state)
    assert state.config.starter_map == {
        "animals": "coop_and_barn",
        "days_per_season": 14,
        "day_length": "short",
        "farm_size": "large",
        "starting_money": 40,
        "fishing": False,
        "buildings": 3,
        "added_maps": [{"name": "Map 1", "kind": "forest"}, {"name": "Beach", "kind": "beach"}],
    }
    config.GeneratorConfig.from_json(state.config.to_json())
    # a row that says its kind comes back with it, whatever its name
    page.enter(state)
    assert page.farm_box.kind_combo(0).currentData() == "forest"
    state.config.starter_map["added_maps"][0] = {"name": "Map 1", "kind": "beach"}
    page.enter(state)
    assert page.farm_box.kind_combo(0).currentData() == "beach"
    assert page.farm_box.plan["added"][0]["kind"] == "beach"
    state.config.starter_map["added_maps"][0] = {"name": "Map 1", "kind": "forest"}
    # the farm's reset leaves the village alone, and the village's the farm
    page.enter(state)
    assert page.farm_box.combos["animals"].currentData() == "coop_and_barn"
    page.farm_box.reset.click()
    page.leave(state)
    assert state.config.starter_map == {"buildings": 3}
    page.enter(state)
    page.farm_box.combos["plot"].setCurrentIndex(0)
    page.starter_reset.click()
    page.leave(state)
    assert state.config.starter_map == {"plot": "small"}
    # two maps of one name are no farm: said on the page, and Next waits
    page.enter(state)
    page.farm_box.add_row("Beach")
    page.farm_box.add_row("beach")
    assert page.farm_box.plan is None and "two added maps" in page.farm_box.preview.text()
    assert [i.message for i in page.validate(state)] == ["Farm: two added maps are called beach."]


def test_the_presets_of_a_farm(qtbot, monkeypatch) -> None:
    _flags(monkeypatch)
    assert options.kind_preset_keys("farm") == ["cosy", "short_year"]
    assert options.kind_preset_keys("turn_based") == [] and "cosy" in options.KIND_PRESETS
    assert {"Cosy", "Short year"} <= set(options.builtin_labels())
    page, state = _kind_page(qtbot, "farm", animals="coop", buildings=2)
    items = [page.preset_combo.itemText(i) for i in range(page.preset_combo.count())]
    assert items[1:6] == ["Everything", "Minimal", "Just the tilesets", "Cosy", "Short year"]
    assert page.apply_preset_named("__builtin__:cosy")
    box = page.farm_box
    assert box.combos["day_length"].currentData() == "long"
    assert not box.checks["pass_out_loss"].isChecked()
    assert box.spins["starting_money"].value() == 500
    assert box.combos["animals"].currentData() == "coop", "the rest of the page stays"
    assert page.apply_preset_named("__builtin__:short_year")
    assert box.combos["days_per_season"].currentData() == 7
    assert "7 days a season" in page.summary.archetype_label.text()
    page.leave(state)
    assert state.config.starter_map == {
        "animals": "coop",
        "buildings": 2,
        "day_length": "long",
        "pass_out_loss": False,
        "starting_money": 500,
        "days_per_season": 7,
    }
    assert not page.apply_preset_named("__builtin__:bionic"), "a preset of another kind"
    other, _state = _kind_page(qtbot, "arpg")
    labels = [other.preset_combo.itemText(i) for i in range(other.preset_combo.count())]
    assert "Cosy" not in labels and not other.apply_preset_named("__builtin__:cosy")


def test_the_view_is_offered_only_with_the_flag_and_for_a_kind_that_has_it(
    qtbot, monkeypatch
) -> None:
    _flags(monkeypatch, isometric=False)
    page, state = _kind_page(qtbot, "turn_based", "iso_tiles")
    assert all(choice.isHidden() for choice in page.view_choices.values())
    before = state.config.to_json()
    page.leave(state)
    assert state.config.to_json() == before
    _flags(monkeypatch)
    for kind, holder in (
        ("turn_based", "starterMap"),
        ("arpg", "starterMap"),
        ("farm", "farmBox"),
        ("racing", "racingBox"),
    ):
        page, _state = _kind_page(qtbot, kind, "iso_tiles")
        mine = page.view_choice
        assert mine is not None and not mine.isHidden(), kind
        assert mine.parentWidget().objectName() == holder, "in the box of the kind"
        others = [c for c in set(page.view_choices.values()) if c is not mine]
        assert all(choice.isHidden() for choice in others)
        texts = [mine.view_combo.itemText(i) for i in range(mine.view_combo.count())]
        assert texts == ["From above", "Isometric"]
        assert mine.view_combo.accessibleName() == "View" and mine.view_combo.toolTip()
        assert mine.view_label.buddy() is mine.view_combo
    for kind in ("metroidvania", "shmup", "run_and_gun"):
        page, _state = _kind_page(qtbot, kind, "iso_tiles")
        assert page.view_choice is None
        assert all(choice.isHidden() for choice in page.view_choices.values()), kind


def test_packs_of_squares_have_no_view_row(qtbot, monkeypatch) -> None:
    """Most projects are made of packs that have nothing isometric: there is nothing to choose
    and nothing to explain, so the row is not there at all (it was shown disabled, with the
    command line's sentence under it)."""
    _flags(monkeypatch)
    assert not options.has_isometric_art(_cat("basic16"))
    assert not options.has_isometric_art(None)
    assert options.has_isometric_art(_cat("iso_tiles"))
    for kind in ("turn_based", "arpg", "farm", "racing"):
        page, state = _kind_page(qtbot, kind, "basic16")
        assert page.model.view_state() == ViewState(False), kind
        assert all(choice.isHidden() for choice in page.view_choices.values()), kind
        assert not page.model.set_view("isometric", "grid"), "and nothing can be set"
        before = state.config.to_json()
        page.leave(state)
        assert state.config.to_json() == before, kind
        assert "projection" not in before and "iso_controls" not in before
    # a project that exists and is seen from above, of such packs: no row either
    page, state = _kind_page(qtbot, "turn_based", "basic16")
    state.regenerating = True
    page.enter(state)
    assert all(choice.isHidden() for choice in page.view_choices.values())


def test_isometric_pictures_without_ground_say_why_in_the_wizards_words(qtbot, monkeypatch) -> None:
    from rpggen.core import catalog as catalog_mod
    from rpggen.core import iso_atlas
    from rpggen.gui import edits
    from rpggen.gui.models.options_model import VIEW_NO_GROUND_TEXT

    _flags(monkeypatch)
    cat = _cat("iso_tiles")
    grounds = [a.id for a in iso_atlas.ground_tiles(cat)]
    assert grounds
    cat = edits.set_overrides(cat, grounds, {"role": "DECORATION"})
    assert iso_atlas.ground_problem(cat) == iso_atlas.NO_GROUND_REASON, "what the run says"
    assert options.has_isometric_art(cat)
    cfg = config.default_for("T", [REF])
    state = WizardState(config=cfg, catalog=cat)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.resize(828, 900)
    page.show()
    page.enter(state)
    view = page.view_choice
    assert not view.isHidden() and view.projection() == "top_down"
    assert not view.view_combo.isEnabled()
    assert view.note.text() == view.view_combo.toolTip() == VIEW_NO_GROUND_TEXT
    assert not view.note.isHidden()
    # written for a person: no key of the config, no name of a role as the catalog spells it
    for word in ("GROUND", "top_down", "projection", "the audit"):
        assert word not in view.note.text(), word
    assert "role Ground on the Audit page" in view.note.text()
    assert not page.model.set_view("isometric", "screen"), "and it cannot be set"
    page.leave(state)
    assert state.config.projection == "top_down"
    # the command line and the run keep their sentence
    assert "GROUND" in iso_atlas.NO_GROUND_REASON and "top_down" in iso_atlas.NO_GROUND_REASON
    assert catalog_mod.effective(cat.asset(grounds[0]))["role"] == "DECORATION"


def test_a_race_has_no_pad_and_its_config_carries_none(qtbot, monkeypatch) -> None:
    """A race is steered, relative to the car or by the stick as a direction of the screen: it
    does not read ``iso_controls``. Its View has no Pad, and its config never carries the
    key, whoever set it."""
    _flags(monkeypatch)
    page, state = _kind_page(qtbot, "racing", "iso_tiles", projection="isometric")
    view = page.view_choice
    assert view is page.arcade_boxes["racing"].view and not view.isHidden()
    assert view.projection() == "isometric" and view.view_combo.isEnabled()
    assert view.pad_combo.isHidden() and view.pad_label.isHidden()
    assert page.model.view_state().pad is False
    assert page.arcade_boxes["racing"].combos["steering"].isVisibleTo(page), "it has Steering"
    assert not page.model.set_view("isometric", "grid"), "the Pad is not the model's to set"
    assert page.model.draft.iso_controls == "screen"
    view.view_combo.setCurrentIndex(0)
    view.view_combo.setCurrentIndex(1)
    assert view.pad_combo.isHidden(), "choosing the view again does not bring the Pad"
    page.leave(state)
    assert state.config.projection == "isometric"
    assert "iso_controls" not in state.config.to_json()
    # a config that carries the key for a race: accepted, not read, not written back
    data = state.config.to_json()
    data["iso_controls"] = "grid"
    loaded = config.GeneratorConfig.from_json(data)
    assert loaded.iso_controls == "screen" and "iso_controls" not in loaded.to_json()
    loaded.iso_controls = "grid"  # set by hand on the object
    assert "iso_controls" not in loaded.to_json()
    page, state = _kind_page(qtbot, "racing", "iso_tiles", projection="isometric")
    state.config.iso_controls = "grid"
    page.enter(state)
    assert page.view_choice.pad_combo.isHidden()
    page.leave(state)
    assert state.config.iso_controls == "screen"
    # the kinds whose player walks keep theirs
    for kind in ("turn_based", "arpg", "farm"):
        page, state = _kind_page(qtbot, kind, "iso_tiles", projection="isometric")
        assert not page.view_choice.pad_combo.isHidden(), kind
        assert page.model.set_view("isometric", "grid")
        page.leave(state)
        assert state.config.to_json()["iso_controls"] == "grid", kind


def test_the_view_sets_the_projection_and_the_pad(qtbot, monkeypatch) -> None:
    from rpggen.core import iso_atlas
    from rpggen.gui.pages.archetype_page import ArchetypePage

    _flags(monkeypatch)
    # chosen for the pack: the Archetype page leaves an isometric pack isometric
    cfg = config.default_for("T", [REF])
    state = WizardState(config=cfg, catalog=_cat("iso_tiles"))
    kinds = ArchetypePage()
    qtbot.addWidget(kinds)
    kinds.enter(state)
    kinds.leave(state)
    assert state.config.projection == "isometric" and not state.view_chosen
    page = OptionsPage()
    qtbot.addWidget(page)
    page.resize(828, 900)
    page.show()
    page.enter(state)
    view = page.view_choice
    assert view.projection() == "isometric" and view.view_combo.isEnabled()
    assert not view.pad_combo.isHidden() and view.controls() == "screen"
    pads = [view.pad_combo.itemText(i) for i in range(view.pad_combo.count())]
    assert pads == ["follows the screen", "follows the diamonds"]
    assert view.pad_combo.accessibleName() == "Pad" and view.pad_combo.toolTip()
    assert view.note.isHidden()
    view.pad_combo.setCurrentIndex(1)
    page.leave(state)
    assert state.config.projection == "isometric" and state.config.iso_controls == "grid"
    assert state.config.to_json()["iso_controls"] == "grid"
    assert not state.view_chosen, "the pad is no choice of the view"
    page.enter(state)
    view.view_combo.setCurrentIndex(0)  # From above: the pad has nothing to follow
    assert view.pad_combo.isHidden() and view.pad_label.isHidden()
    page.leave(state)
    assert state.config.projection == "top_down" and state.view_chosen
    assert "projection" not in state.config.to_json()
    kinds.enter(state)
    kinds.leave(state)
    assert state.config.projection == "top_down", "what was chosen by hand stays"
    page.enter(state)
    view.view_combo.setCurrentIndex(1)
    page.leave(state)
    assert state.config.projection == "isometric"
    # a pack of squares: the view stays From above, and there is no row to say so
    page, state = _kind_page(qtbot, "turn_based", "basic16")
    view = page.view_choice
    assert view.isHidden() and view.projection() == "top_down"
    assert iso_atlas.ground_problem(page.model.catalog), "the run would refuse the view"
    assert not page.model.set_view("isometric", "screen"), "and it cannot be set"
    assert page.model.draft.projection == "top_down"
    page.leave(state)
    assert state.config.projection == "top_down"
    # a config that asks for the view its packs no longer have goes back to squares
    page, state = _kind_page(qtbot, "turn_based", "basic16", projection="isometric")
    assert page.view_choice.projection() == "top_down" and page.view_choice.isHidden()
    page.leave(state)
    assert state.config.projection == "top_down"


def test_the_view_is_fixed_once_the_project_exists(qtbot, monkeypatch, tmp_path: Path) -> None:
    from rpggen import paths
    from rpggen.gui.models.options_model import VIEW_FIXED_TEXT

    _flags(monkeypatch)
    target = tmp_path / "game"
    page, state = _kind_page(qtbot, "turn_based", "iso_tiles", projection="isometric")
    state.target = target
    page.enter(state)
    assert page.view_choice.view_combo.isEnabled(), "no project yet: the view can be chosen"
    saved = paths.from_posix_rel(paths.CONFIG, target)  # a generation wrote the project
    saved.parent.mkdir(parents=True)
    saved.write_text("{}", encoding="utf-8")
    page.enter(state)
    view = page.view_choice
    assert not view.isHidden() and view.projection() == "isometric"
    assert not view.view_combo.isEnabled()
    assert view.view_combo.toolTip() == VIEW_FIXED_TEXT
    assert view.note.text() == "the view of a generated project cannot be changed"
    assert view.pad_combo.isEnabled(), "the pad is read on every run"
    view.pad_combo.setCurrentIndex(1)
    assert not page.model.set_view("top_down", "grid")
    page.leave(state)
    assert state.config.projection == "isometric" and state.config.iso_controls == "grid"
    # the same for a project that was opened to be generated again, seen from above
    other, opened = _kind_page(qtbot, "farm", "iso_tiles")
    opened.regenerating = True
    other.enter(opened)
    assert not other.view_choice.view_combo.isEnabled()
    assert other.view_choice.projection() == "top_down"


def test_the_preview_of_a_farm_is_drawn_from_its_plan_in_both_views(qtbot, monkeypatch) -> None:
    from rpggen.core import farm_plan, map_preview

    farm = farm_plan.plan({"animals": "coop"}, 7)
    flat = map_preview.render_farm(farm, scale=6)
    assert flat.size == (40 * 6, 30 * 6)
    diamond = map_preview.farm_diamond(6, (180, 104))
    assert diamond == (12, 6) and map_preview.farm_diamond(8) == (16, 8)
    iso = map_preview.render_farm(farm, scale=6, footprint=(180, 104))
    assert iso.width == (40 + 30) * diamond[0] // 2 and iso.height > (40 + 30) * diamond[1] // 2

    def colours(picture) -> set:  # noqa: ANN001
        return {colour for _count, colour in picture.getcolors(maxcolors=100000)}

    for kind in ("tillable", "water", "path", "building", "door", "bin", "yard", "exit", "start"):
        colour = map_preview.FARM_COLORS[kind]
        assert colour in colours(flat) and colour in colours(iso), kind
    assert map_preview.FARM_ISO_BACKGROUND in colours(iso), "the corners beside the diamond"
    # a cell is where its diamond is: the house, the plot and the way out
    cells = map_preview.farm_cells(farm)
    for cell in (tuple(farm["tillable"][0]), tuple(farm["exit"]["cell"]), (0, 0), (39, 29)):
        (ox, oy), _size = map_preview._iso_frame(
            [(x, y) for y in range(30) for x in range(40)], diamond, diamond[1] // 2 + 1, 1
        )
        x, y = map_preview.iso_math.cell_to_screen(cell[0], cell[1], *diamond)
        assert map_preview.farm_cell_at(farm, ox + x, oy + y, 6, (180, 104)) == cell
        front = [(cell[0] + dx, cell[1] + dy) for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
        if not any(cells.get(c) in map_preview.FARM_RAISED for c in front):
            # nothing that stands up is on it or before it: its own colour is in its middle
            assert (
                iso.getpixel((int(ox + x), int(oy + y)))
                == map_preview.FARM_COLORS[cells.get(cell, "ground")]
            )
    assert map_preview.farm_cell_at(farm, 13, 20, 6) == (2, 3)
    # the box draws the one or the other by the view of the project
    _flags(monkeypatch)
    page, state = _kind_page(qtbot, "farm", "iso_miniature", projection="isometric")
    box = page.farm_box
    assert page.view_choice.projection() == "isometric"
    assert box.footprint == (64, 32) and box.plan is not None
    on_diamonds = box._pixmap.toImage()
    assert on_diamonds.width() > on_diamonds.height() * 1.5
    page.view_choice.view_combo.setCurrentIndex(0)
    assert box.footprint is None
    on_squares = box._pixmap.toImage()
    assert (on_squares.width(), on_squares.height()) == (40 * 6, 30 * 6)
    assert box.plan["size"] == [40, 30], "the same plan in both"
    page.leave(state)
    assert state.config.projection == "top_down"


def test_the_village_of_a_farm_and_an_isometric_map_in_the_starter_preview() -> None:
    import io

    from PIL import Image

    from rpggen.core import map_preview
    from rpggen.core.orchestrator import Callbacks
    from rpggen.gui.widgets import map_preview as widget

    chosen = {**config.starter_map_defaults("farm"), "enemies": 3, "npcs": 4}
    plan = map_preview.plan(chosen, 5, {}, "farm")
    village = map_preview.village_of_farm(plan)
    assert len(plan["enemies"]) == 3 and village["enemies"] == []
    assert village["npcs"] == plan["npcs"][:1] and village["chests"] == plan["chests"]
    # the preview of an isometric project is its map on diamonds, made to fit
    cat = _cat("iso_tiles")
    root = SYNTH / "iso_tiles"

    def resolver(asset):  # noqa: ANN001, ANN202
        return root / asset.path.split("/", 3)[3]

    def picture(projection: str, archetype: str = "turn_based") -> Image.Image:
        png, _warnings, _interiors = widget.render_png(
            cat, resolver, chosen, 5, archetype, "", "", 2, projection, callbacks=Callbacks()
        )
        return Image.open(io.BytesIO(png))

    iso = picture("isometric")
    art = map_preview.load_art(cat, resolver, projection="isometric")
    assert art.footprint == (60, 34) and art.ground is not None
    # (64 cells across of 30 px each are 1,920 px: the pictures were made smaller first)
    assert 0.9 * widget.ISO_PREVIEW_WIDTH <= iso.width <= widget.ISO_PREVIEW_WIDTH
    assert iso.height < iso.width, "a diamond, wider than high"
    flat = picture("top_down")
    assert flat.size == (40 * 16 * 2, 24 * 16 * 2), "squares, as it was"
    # a pack of large diamonds is made smaller, with its origins
    small = map_preview.fitted_art(art, (40, 24), 600)
    assert small.footprint is not None and small.footprint[0] <= 20
    assert small.ground is not None and small.ground.width < art.ground.width
    assert id(small.ground) in small.origins and len(small.decorations) == len(art.decorations)
    shown = map_preview.render(village, small, 1)
    assert shown.width <= 660
    assert map_preview.fitted_art(art, (40, 24), 100000) is art
    assert map_preview.fitted_art(map_preview.Art(), (40, 24), 10).footprint is None


def test_a_farm_that_exists_shows_its_stored_plan_with_what_is_then_fixed(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    from rpggen import paths
    from rpggen.core import crop_plan, farm_plan, people_plan, world_plan

    _flags(monkeypatch)
    target = tmp_path / "game"
    crops = crop_plan.plan({}, 9, {})
    crops["people"] = people_plan.plan({"people": 2}, 9, {})["people"]
    assert len(crops["people"]) == 2
    world = crop_plan.world(crops, 9)
    stored = farm_plan.plan({"animals": "coop", "added_maps": [{"name": "Beach"}]}, 9)
    world_plan.save(target, farm_plan.attach(world, stored))
    for rel in (farm_plan.MAP_FILE, "game/maps/starter_map.tscn"):
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_text("", encoding="utf-8")
    saved = paths.from_posix_rel(paths.CONFIG, target)
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text("{}", encoding="utf-8")
    assert farm_plan.exists(target)
    cfg = config.default_for("T", [REF], archetype="farm")
    cfg.seed = 1234  # another seed than the farm was planned with: the stored plan is shown
    cfg.starter_map = {"animals": "coop", "added_maps": [{"name": "Beach"}], "buildings": 2}
    state = WizardState(config=cfg, archetype="farm", target=target, regenerating=True)
    page = OptionsPage()
    qtbot.addWidget(page)
    page.resize(828, 900)
    page.show()
    page.enter(state)
    box = page.farm_box
    assert page.model.farm_locked and page.model.starter_locked
    assert not box.note.isHidden() and "This project has its farm" in box.note.text()
    assert box.plan == stored and box.plans["stored"], "the plan of the project, not a new one"
    assert (box.plans["crops"], box.plans["people"]) == (len(crops["crops"]), 2)
    assert not box.preview.pixmap().isNull()
    for key in ("farm_size", "plot", "animals", "difficulty"):
        assert not box.combos[key].isEnabled(), f"{key} is fixed"
    assert not box.spins["starting_money"].isEnabled() and not box.reset.isEnabled()
    for key in ("days_per_season", "day_length"):
        assert box.combos[key].isEnabled(), f"{key} is read on every run"
    assert box.checks["fishing"].isEnabled() and box.checks["pass_out_loss"].isEnabled()
    assert not page.starter_box.counts["buildings"].isEnabled(), "the village exists too"
    assert not box.remove_row(), "a map the plan has stays"
    assert box.kind_combo(0).currentData() == "beach" and not box.kind_combo(0).isEnabled()
    assert box.add_row("Forest") and box.plan["added_maps"] == ["Beach", "Forest"]
    assert box.kind_combo(1).isEnabled(), "the kind of a new row can be chosen"
    # the stored map is the one that was planned, and the new row plans one more (T17.23)
    assert box.plan["added"][0] == stored["added"][0]
    assert [(e["id"], e["kind"]) for e in box.plan["added"]] == [
        ("farm_map_1", "beach"),
        ("farm_map_2", "forest"),
    ]
    assert {k: v for k, v in box.plan.items() if k not in ("added", "added_maps")} == {
        k: v for k, v in stored.items() if k not in ("added", "added_maps")
    }
    box.combos["days_per_season"].setCurrentIndex(box.combos["days_per_season"].findData(7))
    box.checks["pass_out_loss"].setChecked(False)
    page.leave(state)
    assert state.config.starter_map == {
        "animals": "coop",
        "buildings": 2,
        "added_maps": [{"name": "Beach", "kind": "beach"}, {"name": "Forest", "kind": "forest"}],
        "days_per_season": 7,
        "pass_out_loss": False,
    }
    # a preset of the kind sets what can still change and leaves what is fixed
    page.enter(state)
    assert page.apply_preset_named("__builtin__:cosy")
    page.leave(state)
    assert state.config.starter_map["day_length"] == "long"
    assert "starting_money" not in state.config.starter_map, "the game was started with 100"
    assert state.config.starter_map["animals"] == "coop"
    assert state.config.starter_map["buildings"] == 2

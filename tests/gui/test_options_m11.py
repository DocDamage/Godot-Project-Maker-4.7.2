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

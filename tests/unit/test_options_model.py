"""The Options page's decisions without Qt (T12.25)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rpggen.core import app_settings, options
from rpggen.core import config as config_mod
from rpggen.gui.models import options_model as om
from rpggen.gui.state import WizardState


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _model(**state_changes) -> om.OptionsModel:
    state = WizardState(config=config_mod.default_for("T", []), **state_changes)
    model = om.OptionsModel()
    model.enter(state)
    model.loaded()
    return model


def _values(model: om.OptionsModel, **changes) -> om.OptionValues:
    draft = model.draft
    assert draft is not None
    values = om.OptionValues(
        features=dict(draft.features),
        resolution=draft.resolution,
        window_size=draft.window_size,
        layers=list(draft.map_layers),
        seed=draft.seed,
        starter=dict(draft.starter_map_options()),
        imported=None,
        input_rows=model.input_rows(),
    )
    for key, value in changes.items():
        setattr(values, key, value)
    return values


def test_the_draft_is_a_copy_until_it_is_applied() -> None:
    model = _model()
    assert model.state is not None and model.state.config is not None
    cfg = model.state.config
    assert model.draft is not None
    model.draft.map_layers.append("Extra")
    model.draft.features["terrain"] = not cfg.features.get("terrain", False)
    assert "Extra" not in cfg.map_layers
    model.apply_to(cfg)
    assert "Extra" in cfg.map_layers
    assert model.draft.map_layers is not cfg.map_layers


def test_no_config_no_draft() -> None:
    model = om.OptionsModel()
    model.enter(WizardState())
    assert model.draft is None
    assert model.validate() == []


def test_the_demo_needs_its_features_and_comes_back_as_wished() -> None:
    model = _model()
    current = {k: True for k in options.FEATURE_INFO}
    assert model.dependent_features(current)["demo"] == om.FeatureState(
        True, True, options.FEATURE_INFO["demo"][2], ""
    )
    current["dialogue"] = False
    state = model.dependent_features(current)["demo"]
    assert not state.enabled and not state.checked
    assert state.needs == "Needs: Dialogue"
    assert state.tooltip == "Requires: Dialogue"
    model.feature_wish("demo", False)
    current["dialogue"] = True
    assert not model.dependent_features(current)["demo"].checked
    assert model.default_features()["demo"] is True and model.demo_wish


def test_an_existing_starter_map_locks_the_layout_options(tmp_path) -> None:
    (tmp_path / "game" / "maps").mkdir(parents=True)
    (tmp_path / "game" / "maps" / "starter_map.tscn").write_text("x")
    model = _model(regenerating=True, target=tmp_path)
    assert model.starter_locked
    state = model.starter_state()
    assert not state.layout_enabled and not state.imported_enabled and state.note_visible
    assert state.note == om.EXISTING_MAP_TEXT
    assert model.preview_options({}) is None
    cfg = config_mod.default_for("T", [])
    cfg.starter_map = {"npcs": 0}
    assert model.draft is not None
    model.draft.starter_map = {"npcs": 5}
    model.apply_to(cfg)
    assert cfg.starter_map == {"npcs": 0}  # the user's map keeps its options


def test_an_imported_starter_map_disables_only_the_layout() -> None:
    model = _model()
    assert model.starter_state() == om.StarterState(True, True, om.IMPORTED_STARTER_TEXT, False)
    assert model.draft is not None
    model.draft.imported_maps = {"include": ["town"], "starter": "town"}
    state = model.starter_state()
    assert not state.layout_enabled and state.imported_enabled and state.note_visible


def test_the_starter_map_stores_only_what_differs_from_the_defaults() -> None:
    model = _model()
    values = dict(model.starter_defaults())
    values["npcs"] = values["npcs"] + 1
    model.store_starter(values)
    assert model.draft is not None
    assert model.draft.starter_map == {"npcs": values["npcs"]}


def test_imported_maps_follow_the_catalog() -> None:
    model = _model()
    assert model.chosen_imported() is None
    assert model.imported_rows() == []
    maps = [
        {"id": "town", "pack_id": "p", "source": "maps/town.tmx", "size": [40, 24], "layers": []}
    ]
    assert model.state is not None
    model.state.catalog = SimpleNamespace(maps=maps, assets=[])  # type: ignore[assignment]
    assert model.imported_map_ids() == ["town"]
    assert [row[1:] for row in model.imported_rows()] == [("town", "maps/town.tmx")]
    assert model.normalize_imported([], "town") == {"include": ["town"], "starter": "town"}
    assert model.draft is not None
    model.draft.imported_maps = {"include": ["gone", "town"]}
    assert model.chosen_imported() == {"include": ["town"]}
    assert model.draft.imported_maps == {"include": ["town"]}


def test_input_cells_that_are_not_numbers_are_reported_and_not_applied() -> None:
    model = _model()
    rows = model.input_rows()
    action, cells = rows[0]
    bad = [cells[0], "1, two", cells[2]]
    assert model.draft is not None
    before = model.draft.input
    model.collect(_values(model, input_rows=[(action, bad), *rows[1:]]))
    assert model.input_errors == [
        f"{action}: Mouse buttons must be whole numbers separated by commas."
    ]
    assert model.draft.input == before
    assert model.validate() == model.input_errors
    model.collect(_values(model, input_rows=[(action, [cells[0], "1, 2", cells[2]]), *rows[1:]]))
    assert model.input_errors == []
    assert model.draft.input[action]["mouse_buttons"] == [1, 2]


def test_collect_forces_dependent_features_off_and_validates_layers() -> None:
    model = _model()
    features = {k: True for k in options.FEATURE_INFO}
    features["save"] = False
    model.collect(_values(model, features=features, layers=["Walls", "Walls"]))
    assert model.draft is not None
    assert model.draft.features["demo"] is False
    assert "The Ground layer is required." in model.validate()
    assert "Layer names must be unique." in model.validate()


def test_presets_keep_the_seed_and_round_trip_through_the_settings() -> None:
    model = _model()
    assert model.draft is not None
    model.draft.seed = 1234
    model.draft.resolution = (384, 216)
    assert model.save_preset("Big")
    assert not model.save_preset("Defaults")
    assert model.preset_names() == ["Big"]
    assert model.apply_preset(om.DEFAULTS_ITEM)
    assert model.draft.resolution != (384, 216) and model.draft.seed == 1234
    assert model.apply_preset("Big")
    assert model.draft.resolution == (384, 216)
    assert not model.apply_preset("missing")
    model.edit_presets({"Big": "Large"}, [])
    assert model.preset_names() == ["Large"]
    model.edit_presets({}, ["Large"])
    assert app_settings.load().option_presets == {}


def test_git_box_texts() -> None:
    model = _model()
    assert model.git_box(True) == ("Initialize git repository", "", True)
    assert model.git_box(False) == (
        "Initialize git repository",
        "git was not found on this computer",
        False,
    )
    model = _model(regenerating=True)
    assert model.git_box(True) == ("Commit regeneration", "", False)
    model.set_git(True)
    assert model.git_box(True)[2]
    model.set_pack_art("ignore")
    assert model.draft is not None and model.draft.pack_art == "ignore"
    model.set_pack_art("commit")
    assert "pack_art" not in model.draft.git


def test_summary_without_packs_has_no_size(tmp_path) -> None:
    model = _model()
    summary, _seconds, size = model.summary({}, (320, 180))
    assert isinstance(summary, options.Summary) and size is None
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"x" * 100)
    assert model.state is not None
    model.state.pack_sources = [pack]
    assert model.pack_size() == 100
    (pack / "b.png").write_bytes(b"x" * 100)
    assert model.pack_size() == 100  # read once per set of packs
    assert model.summary({}, (320, 180))[2] == options.estimate_project_bytes(100)


def test_screen_hint_suggests_a_preset_for_the_tile_size() -> None:
    model = _model()
    text, suggested = model.screen_hint((320, 180))
    assert text == options.tiles_hint((320, 180), 16)
    assert suggested == options.suggested_preset(options.RESOLUTION_PRESETS, 16)
    assert model.default_screen() == (
        config_mod.GeneratorConfig("x", []).resolution,
        config_mod.GeneratorConfig("x", []).window_size,
    )

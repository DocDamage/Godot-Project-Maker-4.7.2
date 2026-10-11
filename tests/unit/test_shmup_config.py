"""T16.04: what the Python side knows of the shoot 'em up: its config, its controls, its smoke
steps, what is installed for it and how a dry run and the options summary describe it."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import features, paths, schema
from rpggen.core import config, options, orchestrator, staging

REPO = Path(__file__).resolve().parents[2]


def _cfg(**changes) -> config.GeneratorConfig:
    ref = config.PackRef("shooter", "shooter", "0" * 64, "folder")
    cfg = config.default_for("Star Run", [ref], archetype="shmup")
    for key, value in changes.items():
        setattr(cfg, key, value)
    return cfg


def test_the_config_of_a_shoot_em_up_is_valid_and_keeps_its_orientation() -> None:
    cfg = _cfg()
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["archetype"] == "shmup" and "starter_map" not in data, "vertical is the default"
    assert config.starter_map_defaults("shmup") == {"orientation": "vertical"}
    assert cfg.starter_map_options() == {"orientation": "vertical"}
    sideways = _cfg(starter_map={"orientation": "horizontal"})
    data = sideways.to_json()
    schema.validate("config", data)
    assert data["starter_map"] == {"orientation": "horizontal"}
    again = config.GeneratorConfig.from_json(data)
    assert again.starter_map_options() == {"orientation": "horizontal"}
    assert again.to_json() == data
    data["starter_map"] = {"orientation": "diagonal"}
    with pytest.raises(Exception, match="CAT-002|orientation|diagonal"):
        schema.validate("config", data)
    # the kinds that cannot be built yet are still no archetype of a config
    for kind in ("run_and_gun", "racing"):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**cfg.to_json(), "archetype": kind})
    assert features.SHMUP_AVAILABLE is False, "the wizard does not offer it before its gate"


def test_the_controls_of_a_shoot_em_up() -> None:
    bindings = config.default_input("shmup")
    assert bindings["shoot"]["keys"] == ["Z", "J"] and bindings["shoot"]["joy_buttons"] == [0]
    assert bindings["bomb"]["keys"] == ["X", "K"] and bindings["bomb"]["joy_buttons"] == [1]
    assert bindings["focus"]["keys"] == ["Shift"] and bindings["focus"]["joy_axes"] == [[4, 1.0]]
    for action in ("move_up", "move_down", "move_left", "move_right", "menu", "confirm", "cancel"):
        assert action in bindings, action
    assert bindings["move_left"] == config.default_input("turn_based")["move_left"]
    assert _cfg().input == bindings
    for older in ("turn_based", "arpg", "metroidvania"):
        assert not {"shoot", "bomb", "focus"} & set(config.default_input(older)), older


def test_the_smoke_steps_and_the_installed_files_of_a_shoot_em_up(tmp_path: Path) -> None:
    own = orchestrator.smoke_steps_for("shmup")
    assert own.endswith("smoke_steps_shmup.gd") and "," not in own, "a sequence of its own"
    templates = paths.templates_root()
    written = staging.install_templates(staging.create_staging(tmp_path / "s"), templates, "shmup")
    folders = {w.split("/")[3] for w in written if w.startswith("addons/rpg_runtime/archetypes/")}
    assert folders == {"arcade", "shmup"}
    recipes = {
        w.split("/")[3]
        for w in written
        if w.startswith("generated/builder/recipes/") and w.count("/") > 3
    }
    assert recipes == {"arcade", "shmup"}
    smoke = [w.rsplit("/", 1)[-1] for w in written if "/smoke/smoke_steps_" in w]
    assert "smoke_steps_shmup.gd" in smoke
    assert not {"smoke_steps_arpg.gd", "smoke_steps_metroidvania.gd"} & set(smoke)
    for older in ("turn_based", "arpg", "metroidvania"):
        other = staging.install_templates(
            staging.create_staging(tmp_path / older), templates, older
        )
        assert not [w for w in other if "shmup" in w], older


def test_the_summary_of_the_options_names_the_stage() -> None:
    cfg = _cfg()
    summary = options.summarize(
        "shmup", cfg.features, cfg.starter_map_options(), 16, cfg.resolution
    )
    assert summary.maps == [] and summary.world == "1 stage, scrolling up"
    sideways = options.summarize(
        "shmup", cfg.features, {"orientation": "horizontal"}, 16, cfg.resolution
    )
    assert sideways.world == "1 stage, scrolling right"
    assert options.stages_text("shmup", {}) == "1 stage, scrolling up"

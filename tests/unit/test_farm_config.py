"""T17.04: what the Python side knows of the farm: its config, its controls, what is switched
off, its smoke steps, what is installed for it, and that the wizard does not offer it yet."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import errors_table, features, paths, schema
from rpggen.core import config, orchestrator, requirements, staging


def _cfg(**changes) -> config.GeneratorConfig:
    ref = config.PackRef("ranch", "ranch", "0" * 64, "folder")
    cfg = config.default_for("Green Acre", [ref], archetype="farm")
    for key, value in changes.items():
        setattr(cfg, key, value)
    return cfg


def test_the_config_of_a_farm_is_valid_and_its_map_is_the_top_down_one() -> None:
    cfg = _cfg()
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["archetype"] == "farm" and "starter_map" not in data
    # until the farm has a plan of its own (T17.06) its map is the starter map of every top-down game
    assert config.starter_map_defaults("farm") == config.starter_map_defaults("turn_based")
    again = config.GeneratorConfig.from_json(data)
    assert again.to_json() == data
    for kind in ("orchard",):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "archetype": kind})
    assert features.FARM_AVAILABLE is False, "the wizard does not offer it until its gate"
    assert "farm" in staging.ARCHETYPES


def test_the_controls_of_a_farm() -> None:
    bindings = config.default_input("farm")
    assert bindings["use"] == {"keys": ["Space", "J"], "mouse_buttons": [1], "joy_buttons": [0]}
    assert bindings["interact"] == {"keys": ["E"], "joy_buttons": [2]}, "Space uses, E talks"
    assert bindings["next_item"] == {"keys": ["R"], "joy_buttons": [10]}
    assert bindings["prev_item"] == {"keys": ["Q"], "joy_buttons": [9]}
    slots = [bindings[f"hotbar_{n}"]["keys"] for n in range(1, config.FARM_HOTBAR_SLOTS + 1)]
    assert slots == [[str(n)] for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)], "0 is the tenth slot"
    for action in ("move_up", "move_down", "move_left", "move_right", "menu", "confirm", "cancel"):
        assert bindings[action] == config.default_input("turn_based")[action], action
    assert _cfg().input == bindings
    own = {"use", "next_item", "prev_item", "hotbar_1", "hotbar_10"}
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        assert not own & set(config.default_input(older)), older
    # no two actions of a farm share a key, but the ones that never meet (a menu and the map)
    taken: dict[str, str] = {}
    for action in ("use", "interact", "next_item", "prev_item", "move_up", "move_down",
                   "move_left", "move_right", *(f"hotbar_{n}" for n in range(1, 11))):  # fmt: skip
        for key in bindings[action]["keys"]:
            assert key not in taken, f"{key}: {action} and {taken.get(key)}"
            taken[key] = action


def test_combat_is_off_for_a_farm_and_the_older_kinds_are_as_they_were() -> None:
    feats = _cfg().features
    assert [k for k, on in feats.items() if not on] == ["combat", "navigation"]
    assert feats["dialogue"] and feats["save"] and feats["demo"]
    older = {k: k != "navigation" for k in config.FEATURE_KEYS}
    for kind in ("turn_based", "arpg", "metroidvania"):
        assert config.default_features(kind) == older, kind
    for kind in config.ARCADE_KINDS:
        assert [k for k, on in config.default_features(kind).items() if not on] == [
            "dialogue",
            "navigation",
        ], kind
    # what a farm needs of the packs is what a top-down game needs
    assert requirements.REQUIRED.get("farm", requirements.REQUIRED["turn_based"]) == [
        "PLAYER",
        "GROUND",
    ]


def test_the_smoke_steps_and_the_installed_files_of_a_farm(tmp_path: Path) -> None:
    steps = orchestrator.smoke_steps_for("farm").split(",")
    assert steps == [orchestrator.SMOKE_STEPS, orchestrator.SMOKE_STEPS_FARM]
    assert steps[1].endswith("smoke_steps_farm.gd"), "after the shared top-down sequence"
    assert orchestrator.smoke_steps_for("turn_based").count(",") == 1
    assert "farm" not in orchestrator.smoke_steps_for("arpg")
    info = errors_table.CODES["SMOKE-013"]
    assert info.severity == "error" and "{step}" in info.message and "{detail}" in info.message
    templates = paths.templates_root()
    written = staging.install_templates(staging.create_staging(tmp_path / "s"), templates, "farm")
    folders = {w.split("/")[3] for w in written if w.startswith("addons/rpg_runtime/archetypes/")}
    assert folders == {"farm"}
    recipes = {
        w.split("/")[3]
        for w in written
        if w.startswith("generated/builder/recipes/") and w.count("/") > 3
    }
    assert recipes == {"farm"}
    smoke = sorted(
        w.rsplit("/", 1)[-1] for w in written if "/smoke/smoke_steps_" in w and w.endswith(".gd")
    )
    assert smoke == [
        "smoke_steps_farm.gd",
        "smoke_steps_m1.gd",
        "smoke_steps_m4.gd",
        "smoke_steps_m6.gd",
    ]
    # the calendar is shared (world/): a farm has it, and so has every other kind, inert
    assert "addons/rpg_runtime/world/calendar.gd" in written
    for name in ("farm_mode", "farmer", "field", "crop", "crop_data", "hotbar", "energy", "tool"):
        assert f"addons/rpg_runtime/archetypes/farm/{name}.gd" in written, name
    for name in ("farm_build", "farmer_recipe", "mode_recipe", "crop_recipes", "field_recipe"):
        assert f"generated/builder/recipes/farm/{name}.gd" in written, name
    for older in ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing"):
        other = staging.install_templates(
            staging.create_staging(tmp_path / older), templates, older
        )
        assert not [w for w in other if "farm" in w], older

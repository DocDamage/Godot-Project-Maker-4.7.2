"""T16.12: the racing game as a kind of a config: its options, its controls, the files a
project of it gets and what its packs must have."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import features, paths, schema
from rpggen.core import config, options, orchestrator, staging, track_plan

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _cfg(**changes) -> config.GeneratorConfig:
    ref = config.PackRef("racer", "racer", "0" * 64, "folder")
    cfg = config.default_for("Pro Am", [ref], archetype="racing")
    for key, value in changes.items():
        setattr(cfg, key, value)
    return cfg


def test_the_config_of_a_racing_game_is_valid_and_keeps_its_options() -> None:
    cfg = _cfg()
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["archetype"] == "racing"
    assert data["starter_map"] == {**track_plan.defaults(), "racers": True}, "a new race (T18.19)"
    rules = config.starter_map_defaults("racing")
    assert (rules["steering"], rules["camera"]) == ("relative", "follow")
    assert (rules["tracks"], rules["laps"], rules["track_size"]) == (4, 3, "medium"), "T16.13"
    assert (rules["rivals"], rules["rubber_band"]) == (3, True), "T16.14"
    assert rules["elimination"] is False, "T16.15: nobody is put out unless the game says so"
    easy = _cfg(starter_map={"steering": "absolute"})
    data = easy.to_json()
    schema.validate("config", data)
    # an option that differs writes the whole set, with the defaults of the others
    assert data["starter_map"] == {**rules, "steering": "absolute"}
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for bad in (
        {"steering": "tank"},
        {"camera": "chase"},
        {"tracks": 0},
        {"track_size": "huge"},
        {"rivals": 6},
        {"rubber_band": 1},
        {"elimination": "twice"},
    ):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": bad})
    assert features.RACING_AVAILABLE is True, "the wizard offers it since the gate of 1.4"
    assert [k for k, on in cfg.features.items() if not on] == [
        "dialogue",
        "navigation",
        "progression",
        "crafting",
    ]
    assert options.stages_text("racing", {}) == "4 tracks of 3 laps"


def test_the_controls_are_a_pedal_a_brake_and_a_boost() -> None:
    bindings = config.default_input("racing")
    assert bindings["accelerate"]["keys"] == ["Up", "W"]
    assert bindings["accelerate"]["joy_buttons"] == [0], "pad A"
    assert bindings["brake"]["keys"] == ["Down", "S"] and bindings["brake"]["joy_buttons"] == [1]
    assert bindings["boost"]["keys"] == ["Shift", "Space"]
    assert bindings["boost"]["joy_buttons"] == [2], "pad X"
    assert bindings["fire"] == {"keys": ["X", "K"], "joy_buttons": [3]}, "the weapon: pad Y"
    for action in ("move_left", "move_right", "move_up", "move_down", "menu"):
        assert action in bindings, action  # left and right steer; the stick is the heading
    assert not {"jump", "shoot", "attack", "bomb", "grapple"} & set(bindings)
    assert _cfg().input == bindings
    assert "accelerate" not in config.default_input("shmup")


def test_the_smoke_steps_and_the_installed_files_of_a_racing_game(tmp_path: Path) -> None:
    own = orchestrator.smoke_steps_for("racing")
    assert own.endswith("smoke_steps_racing.gd") and "," not in own
    templates = paths.templates_root()
    written = staging.install_templates(staging.create_staging(tmp_path / "s"), templates, "racing")
    folders = {w.split("/")[3] for w in written if w.startswith("addons/rpg_runtime/archetypes/")}
    assert folders == {"arcade", "racing"}
    recipes = {
        w.split("/")[3]
        for w in written
        if w.startswith("generated/builder/recipes/") and w.count("/") > 3
    }
    assert recipes == {"arcade", "racing"}
    for name in (
        "car.gd", "car_physics.gd", "car_input.gd", "heading_sprite.gd", "race_camera.gd",
        "racing_mode.gd", "racing_strings.gd", "track_surfaces.gd", "ui/racing_hud.gd",
        "race.gd", "rival.gd", "checkpoint.gd", "pickup.gd", "weapon.gd",
        "championship.gd", "ui/results.gd", "ui/race_minimap.gd",
    ):  # fmt: skip
        assert f"addons/rpg_runtime/archetypes/racing/{name}" in written, name
    smoke = [w for w in written if "smoke_steps_" in w and w.endswith(".gd")]
    assert any(w.endswith("smoke_steps_racing.gd") for w in smoke)
    assert not any("shmup" in w or "run_and_gun" in w for w in smoke)
    # another kind does not get the car
    other = staging.install_templates(staging.create_staging(tmp_path / "o"), templates, "shmup")
    assert not [w for w in other if "/racing/" in w or "smoke_steps_racing" in w]


def test_a_race_does_not_read_iso_controls_and_its_config_never_carries_it() -> None:
    """A race is steered (``starter_map.steering``), in both views: ``iso_controls`` is the
    pad of the kinds whose player walks. A config of a race that has the key is accepted, the
    key is read as the default and is not written back; a dry run never names it."""
    from rpggen.core import dry_run

    assert config.ISO_CONTROLS_KINDS == ("turn_based", "arpg", "farm")
    # nobody walks in a race, nor in an assets-only project (T17.33: no game)
    assert set(config.ISOMETRIC_KINDS) - set(config.ISO_CONTROLS_KINDS) == {"racing", "assets"}
    cfg = _cfg(projection="isometric", iso_controls="grid")
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["projection"] == "isometric" and "iso_controls" not in data
    carried = {**data, "iso_controls": "grid"}
    schema.validate("config", carried)  # accepted
    loaded = config.GeneratorConfig.from_json(carried)
    assert loaded.iso_controls == "screen" and loaded.to_json() == data
    for kind in config.ISO_CONTROLS_KINDS:
        ref = config.PackRef("p", "p", "0" * 64, "folder")
        walking = config.default_for("W", [ref], archetype=kind)
        walking.iso_controls = "grid"
        assert walking.to_json()["iso_controls"] == "grid", kind
        assert config.GeneratorConfig.from_json(walking.to_json()).iso_controls == "grid"
    source = Path(dry_run.__file__).read_text(encoding="utf-8")
    assert "iso_controls" not in source, "nothing of a dry run prints the pad"

"""T16.12: the racing game as a kind of a config: its options, its controls, the files a
project of it gets and what its packs must have."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import features, paths, schema
from rpggen.core import config, options, orchestrator, staging

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
    assert data["archetype"] == "racing" and "starter_map" not in data
    assert config.starter_map_defaults("racing") == {"steering": "relative", "camera": "follow"}
    easy = _cfg(starter_map={"steering": "absolute"})
    data = easy.to_json()
    schema.validate("config", data)
    assert data["starter_map"] == {"steering": "absolute", "camera": "follow"}
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for bad in ({"steering": "tank"}, {"camera": "chase"}, {"steering": True}):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": bad})
    assert features.RACING_AVAILABLE is False, "the wizard does not offer it before its gate"
    assert [k for k, on in cfg.features.items() if not on] == ["dialogue", "navigation"]
    assert options.stages_text("racing", {}) == "1 track"


def test_the_controls_are_a_pedal_a_brake_and_a_boost() -> None:
    bindings = config.default_input("racing")
    assert bindings["accelerate"]["keys"] == ["Up", "W"]
    assert bindings["accelerate"]["joy_buttons"] == [0], "pad A"
    assert bindings["brake"]["keys"] == ["Down", "S"] and bindings["brake"]["joy_buttons"] == [1]
    assert bindings["boost"]["keys"] == ["Shift", "Space"]
    assert bindings["boost"]["joy_buttons"] == [2], "pad X"
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
    ):  # fmt: skip
        assert f"addons/rpg_runtime/archetypes/racing/{name}" in written, name
    smoke = [w for w in written if "smoke_steps_" in w and w.endswith(".gd")]
    assert any(w.endswith("smoke_steps_racing.gd") for w in smoke)
    assert not any("shmup" in w or "run_and_gun" in w for w in smoke)
    # another kind does not get the car
    other = staging.install_templates(staging.create_staging(tmp_path / "o"), templates, "shmup")
    assert not [w for w in other if "/racing/" in w or "smoke_steps_racing" in w]

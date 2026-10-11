"""Milestone M16, the racing game (T16.12): the synthetic `racer` pack as a game with a car
on a flat test track, and a pack without a car or a road, which gets the drawn ones."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import arcade_kit, config, orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.racing]

REPO = Path(__file__).resolve().parents[2]
RACER = REPO / "test_packs" / "synthetic" / "racer"
BASIC = REPO / "test_packs" / "synthetic" / "basic16"
STEPS = [
    "title_new_game",
    "car_speeds_up_and_brakes",
    "car_steers",
    "camera_looks_ahead",
    "car_boosts",
    "grass_is_slower",
    "car_bumps_off_a_barrier",
    "car_drives_round_the_track",
    "track_ends_with_the_credits",
]
SCENES = [
    "generated/scenes/racing/car.tscn",
    "generated/scenes/stages/stage_01.tscn",
    "generated/scenes/combat/combat_mode.tscn",
    "generated/scenes/ui/hud_arcade.tscn",
]


def _config(pack: Path = RACER, **starter_map) -> config.GeneratorConfig:
    cfg = config.default_for(
        "Pro Am", [config.pack_ref_from_source(pack, pack.name)], archetype="racing"
    )
    cfg.starter_map = dict(starter_map)
    return cfg


def _errors(result) -> list[str]:
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value != "info"]


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def game(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m16_race") / "out"
    result = orchestrator.run_in_memory(_config(), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _text(target: Path, rel: str) -> str:
    return (target / rel).read_text(encoding="utf-8")


def test_the_racer_pack_is_a_racing_game(game) -> None:
    target, result = game
    assert _smoke(target) == STEPS
    for rel in SCENES:
        assert (target / rel).is_file(), rel
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "racing" and "starter_map" not in saved
    assert {"accelerate", "brake", "boost"} <= set(saved["input"])
    assert not [i for i in result.issues if i.code in ("ASSET-031", "ASSET-032")], (
        "the pack has its own car in sixteen headings and its own road"
    )
    (track,) = jsonio.read(target / "game/data/stages.json")["stages"]
    assert (track["axis"], track["exit"], track["waves"]) == ("none", "custom", [])
    assert track["scene"] == "res://generated/scenes/stages/stage_01.tscn"


def test_the_scenes_are_the_packs_car_on_the_packs_road(game) -> None:
    target, _result = game
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert "racing/car.gd" in car and "racing/heading_sprite.gd" in car
    assert "racing/car_input.gd" in car
    assert "assets/packs/racer/cars/player_car.png" in car, "the car of the pack"
    assert "hframes = 16" in car and "headings = 16" in car
    track = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert "arcade/stage.gd" in track and "racing/race_camera.gd" in track
    assert "racing/track_surfaces.gd" in track
    assert 'name="Ground" type="TileMapLayer"' in track and "tile_map_data" in track
    assert 'name="Road"' not in track, "the road is painted with the tiles of the pack"
    assert 'name="Barriers" type="StaticBody2D"' in track
    assert "generated/scenes/racing/car.tscn" in track
    assert "racing/racing_mode.gd" in _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "racing/ui/racing_hud.gd" in _text(target, "generated/scenes/ui/hud_arcade.tscn")
    assert "RACE_SPEED\t" in _text(target, "game/i18n/strings.tsv")


def test_the_project_has_the_racing_code_and_no_other_kind(game) -> None:
    target, _result = game
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arcade", "racing"]
    recipes = target / "generated/builder/recipes"
    assert (recipes / "racing/car_recipe.gd").is_file()
    assert not (recipes / "shmup").exists() and not (recipes / "run_and_gun").exists()
    smoke = sorted(p.name for p in (target / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert "smoke_steps_racing.gd" in smoke and "smoke_steps_shmup.gd" not in smoke
    assert not (target / "game/maps/starter_map.tscn").exists()
    assert not (target / "generated/scenes/actors/player.tscn").exists()


def test_a_second_run_changes_nothing(game, godot_exe: Path) -> None:
    target, _result = game
    kept = {rel: (target / rel).read_bytes() for rel in [*SCENES, "game/data/stages.json"]}
    again = orchestrator.run_in_memory(_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE]
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_a_pack_without_a_car_drives_the_drawn_one_on_a_drawn_road(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(
        _config(BASIC, steering="absolute", camera="fixed"), None, target, godot_exe
    )
    assert result.ok, _errors(result)
    assert _smoke(target) == STEPS
    drawn = sorted(i.detail["role"] for i in result.issues if i.code == "ASSET-031")
    assert drawn == ["VEHICLE"], "the pack has ground of its own, and no car"
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert f"{arcade_kit.KIT_DIR}/car.png" in car and "headings = 16" in car
    assert "absolute_steering = true" in car
    track = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert 'name="Road"' in track, "no ground of the pack is a road: the road is drawn"
    assert "fixed = true" in track
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["starter_map"] == {"steering": "absolute", "camera": "fixed"}

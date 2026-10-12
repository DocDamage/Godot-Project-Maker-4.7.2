"""Milestone M16, the racing game (T16.12 to T16.15): the synthetic `racer` pack as a game
with a car, three rivals and four planned tracks, a pack without a car or a road, which gets
the drawn ones, a track that is added later, and a game without rivals."""

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
    "pickup_is_taken_and_used",
    "race_is_driven_to_the_finish",
    "results_and_the_championship",
    "tracks_end_with_the_credits",
]
SCENES = [
    "generated/scenes/racing/car.tscn",
    "generated/scenes/racing/rival_1.tscn",
    "generated/scenes/racing/rival_2.tscn",
    "generated/scenes/racing/rival_3.tscn",
    "generated/scenes/racing/pickup.tscn",
    "generated/scenes/stages/stage_01.tscn",
    "generated/scenes/stages/stage_02.tscn",
    "generated/scenes/stages/stage_03.tscn",
    "generated/scenes/stages/stage_04.tscn",
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
    assert {"accelerate", "brake", "boost", "fire"} <= set(saved["input"])
    assert not [i for i in result.issues if i.code in ("ASSET-031", "ASSET-032")], (
        "the pack has its own car in sixteen headings and its own road"
    )
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    assert len(tracks) == 4, "four tracks, each a stage of the game"
    track = tracks[0]
    assert (track["axis"], track["exit"], track["waves"]) == ("none", "custom", [])
    assert track["scene"] == "res://generated/scenes/stages/stage_01.tscn"


def test_the_tracks_are_those_of_the_stored_plan(game) -> None:
    from PIL import Image

    from rpggen.core import track_plan, world_plan

    target, _result = game
    stored = world_plan.load(target)["stages"]
    saved = jsonio.read(target / paths.CONFIG)
    facts = track_plan.facts_of(saved["resolution"], 16)
    assert stored == track_plan.plan({}, saved["seed"], facts)
    assert track_plan.check(stored) == []
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    for planned, listed in zip(stored["list"], tracks, strict=True):
        assert listed["scene"] == planned["scene"]
        for key in ("laps", "start", "checkpoints", "waypoints", "pickups"):
            assert listed[key] == planned[key], key  # what the race reads
        for key in ("rows", "barriers", "tyres", "decoration", "loop"):
            assert key not in listed, key  # painted into the scene, not listed
        scene = _text(target, listed["scene"].removeprefix("res://"))
        assert "racing/track_surfaces.gd" in scene and "tile_map_data" in scene
        assert f'rows = PackedStringArray("{planned["rows"][0]}"' in scene
        assert scene.count("CircleShape2D_") >= len(planned["tyres"]), "a tyre at every corner"
        assert "racer/props/" in scene, "the tyres and cones of the pack"
        assert 'name="Marks"' in scene, "the start line, and what lies on the road"
        assert scene.count('name="Pickup') - 1 == len(planned["pickups"])
        kinds = [p["kind"] for p in planned["pickups"]]
        assert sum(k in track_plan.PARTS for k in kinds) == 1, "a part lies on every track"
        for kind in kinds:
            assert f'kind = "{kind}"' in scene or kind == "boost", kind  # boost is the default
    # the picture of the tracks, side by side, for the Results page
    picture = Image.open(target / orchestrator.STARTER_PICTURE)
    widths = [len(t["rows"][0]) * 4 for t in stored["list"]]
    assert picture.size[0] == sum(widths) + 6 * (len(widths) - 1)


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
    assert 'name="Road"' not in track, "the road is painted with a tile of the pack"
    assert 'name="Barriers" type="StaticBody2D"' in track
    assert "generated/scenes/racing/car.tscn" in track
    # the race, the rivals on the grid and what lies on the road (T16.14)
    assert "racing/race.gd" in track and 'name="Race"' in track
    for number in (1, 2, 3):
        assert f"generated/scenes/racing/rival_{number}.tscn" in track
        assert f'name="Rival{number}"' in track
        rival = _text(target, f"generated/scenes/racing/rival_{number}.tscn")
        assert "racing/rival.gd" in rival and "racing/car_input.gd" not in rival
        assert "is_player = false" in rival
        assert f"assets/packs/racer/cars/rival_car_{number}.png" in rival, "a car of the pack"
        assert "modulate" not in rival, "its own picture, not the player's in another colour"
    assert "skill = 0.9" in _text(target, "generated/scenes/racing/rival_1.tscn")
    assert "racing/pickup.gd" in _text(target, "generated/scenes/racing/pickup.tscn")
    assert "generated/scenes/racing/pickup.tscn" in track
    assert "boosts = 1" in car, "one boost to start with: the rest lie on the track"
    assert "racing/racing_mode.gd" in _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "racing/ui/racing_hud.gd" in _text(target, "generated/scenes/ui/hud_arcade.tscn")
    strings = _text(target, "game/i18n/strings.tsv")
    assert "RACE_SPEED\t" in strings and "RACE_WRONG_WAY\t" in strings


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
    for number in (1, 2, 3):
        assert (target / f"generated/scenes/racing/rival_{number}.tscn").is_file()
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert f"{arcade_kit.KIT_DIR}/car.png" in car and "headings = 16" in car
    assert "absolute_steering = true" in car
    track = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert 'name="Road"' in track, "no ground of the pack is a road: the road is drawn"
    assert "fixed = true" in track
    saved = jsonio.read(target / paths.CONFIG)
    assert (saved["starter_map"]["steering"], saved["starter_map"]["camera"]) == (
        "absolute",
        "fixed",
    )


def test_an_added_track_grows_the_game(godot_exe: Path, cache: Path, tmp_path: Path) -> None:
    from rpggen.core import world_plan

    target = tmp_path / "out"
    first = orchestrator.run_in_memory(
        _config(tracks=1, track_size="small", laps=1), None, target, godot_exe
    )
    assert first.ok, _errors(first)
    assert len(jsonio.read(target / "game/data/stages.json")["stages"]) == 1
    second = orchestrator.run_in_memory(
        _config(tracks=5, track_size="small", laps=1, added_tracks=[{"name": "Dunes"}]),
        None,
        target,
        godot_exe,
    )
    assert second.ok, _errors(second)
    stored = world_plan.load(target)["stages"]
    assert [t["id"] for t in stored["list"]] == ["stage_01", "stage_02"], "the stored plan counts"
    assert stored["added"] == ["Dunes"]
    planned = jsonio.read(target / "generated/data/stages.json")["stages"]
    assert [t["title"] for t in planned] == ["", "Dunes"]
    assert (target / "generated/scenes/stages/stage_02.tscn").is_file()
    assert _smoke(target)[-1] == "tracks_end_with_the_credits"


def test_a_game_without_rivals_is_a_race_against_the_clock(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(
        _config(
            tracks=1, track_size="small", laps=1, rivals=0, rubber_band=False, elimination=True
        ),
        None,
        target,
        godot_exe,
    )
    assert result.ok, _errors(result)
    assert _smoke(target) == STEPS
    assert not (target / "generated/scenes/racing/rival_1.tscn").exists()
    track = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert 'name="Race"' in track and 'name="Rival1"' not in track
    assert "rubber_band = false" in track
    assert "elimination = true" in _text(target, "generated/scenes/combat/combat_mode.tscn")


def test_the_readme_explains_the_kind(game) -> None:
    target, _result = game
    readme = _text(target, "README.md")
    assert "**This game is a racing game**" in readme
    assert "## 22. Tracks, rivals and the championship (racing)" in readme
    for needle in (
        "game/data/stages.json",
        "generated/scenes/racing/",
        "| Points | 10 | 6 | 4 | 3 | 2 | 1 |",
        "| Use the weapon | X, K |",
        "starter_map.elimination",
        "Added tracks",
    ):
        assert needle in readme, needle
    assert "shoot" not in readme.split("## 22.")[1]
    # what the README says of a track is what a track of the game has
    track = jsonio.read(target / "game/data/stages.json")["stages"][0]
    for key in ("title", "laps", "checkpoints", "waypoints", "start"):
        assert key in track and f"`{key}`" in readme, key
    # the HUD of the race and the mode's rule
    hud = _text(target, "generated/scenes/ui/hud_arcade.tscn")
    assert "racing/ui/racing_hud.gd" in hud and "track_map = false" not in hud
    assert "elimination = true" not in _text(target, "generated/scenes/combat/combat_mode.tscn")
    strings = _text(target, "game/i18n/strings.tsv")
    assert "RACE_TABLE\t" in strings and "RACE_CHAMPION\t" in strings

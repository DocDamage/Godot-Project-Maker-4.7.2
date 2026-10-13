"""Milestone M17, the isometric race (T17.15): the two synthetic isometric packs together as a
racing game with ``projection: isometric``, the ground of one (``iso_tiles``, a diamond of
60 x 34) and the car of the other (``iso_miniature``, eight headings as eight files). The
tracks are those of the plan, cell for cell; they are painted on diamonds, the race is driven on
the flat plan, and the eleven steps of the racing game's smoke sequence pass. A pack without a
car gets the drawn one, with the stick as the heading and the camera over the whole track."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import arcade_kit, config, orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.isometric]

REPO = Path(__file__).resolve().parents[2]
TILES = REPO / "test_packs" / "synthetic" / "iso_tiles"
MINIATURE = REPO / "test_packs" / "synthetic" / "iso_miniature"
GROUND = "iso_tiles.png.isotile_001_0"
FOOT = (60, 34)
# the sequence of every racing game (tests/integration/test_m16_racing.py)
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


def _config(packs: tuple[Path, ...] = (TILES, MINIATURE), **starter_map) -> config.GeneratorConfig:  # noqa: ANN003
    cfg = config.default_for(
        "Diamond Cup",
        [config.pack_ref_from_source(pack, pack.name) for pack in packs],
        archetype="racing",
    )
    cfg.projection = "isometric"
    cfg.starter = {"ground": GROUND}  # the Mapping page's choice: the ground of iso_tiles
    cfg.starter_map = dict(starter_map)
    return cfg


def _errors(result) -> list[str]:  # noqa: ANN001
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]


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
def race(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    target = tmp_path_factory.mktemp("iso_race") / "out"
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


def _node(scene: str, name: str) -> str:
    """The lines of the node ``name`` of a scene's text."""
    found = re.search(rf'\[node name="{name}"[^\n]*\n(.*?)(?=\n\[|\Z)', scene, re.S)
    assert found, f"no node {name}"
    return found.group(0)


def test_the_two_packs_make_an_isometric_race_that_passes_its_smoke_run(race) -> None:  # noqa: ANN001
    target, result = race
    assert not _errors(result)
    assert _smoke(target) == STEPS, "the eleven steps of every racing game"
    for rel in SCENES:
        assert (target / rel).is_file(), rel
    saved = jsonio.read(target / paths.CONFIG)
    assert (saved["archetype"], saved["projection"]) == ("racing", "isometric")
    # the ground is the one pack's, the car the other's; nothing is drawn for either
    assert not [i for i in result.issues if i.code in ("ASSET-031", "ASSET-032")]
    assert not (target / arcade_kit.KIT_DIR).exists()
    assert not (target / "generated/iso_kit").exists(), "a race has no people to draw"
    left_out = [i for i in result.issues if i.code == "TILE-012"]
    assert len(left_out) == 1 and "iso_miniature" in left_out[0].message, (
        "the tiles of the other pack stand on another diamond; its car is no tile"
    )


def test_the_car_is_the_strip_of_eight_headings(race) -> None:  # noqa: ANN001
    target, _result = race
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert "generated/frame_strips/" in car and "racing/heading_sprite.gd" in car
    assert "hframes = 8" in car and "headings = 8" in car
    assert "racing/car.gd" in car and "racing/car_input.gd" in car
    # its body is measured in the plan: a picture of 21 x 18 px on a road whose tile is 11 px
    body = re.search(r"radius = ([0-9.]+)", car)
    assert body and 0.4 * 16 <= float(body.group(1)) <= 0.65 * 16
    for number in (1, 2, 3):  # the pack has one car: the rivals drive it in other colours
        rival = _text(target, f"generated/scenes/racing/rival_{number}.tscn")
        assert "generated/frame_strips/" in rival and "headings = 8" in rival
        assert "modulate = " in rival and "racing/rival.gd" in rival


def test_the_tracks_are_the_plans_painted_on_diamonds(race) -> None:  # noqa: ANN001
    from rpggen.core import track_plan, world_plan

    target, _result = race
    stored = world_plan.load(target)["stages"]
    saved = jsonio.read(target / paths.CONFIG)
    facts = track_plan.facts_of(saved["resolution"], saved["base_tile_size"])
    assert stored == track_plan.plan({}, saved["seed"], facts), "the plan knows no view"
    assert track_plan.check(stored) == []
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    for planned, listed in zip(stored["list"], tracks, strict=True):
        for key in ("start", "checkpoints", "waypoints", "pickups", "laps"):
            assert listed[key] == planned[key], f"{key} of {planned['id']} is the plan's"
    tile = facts["tile"]
    for index, planned in enumerate(stored["list"]):
        scene = _text(target, f"generated/scenes/stages/stage_{index + 1:02d}.tscn")
        # how it is seen: the diamond of the ground, and how many px of the plan one is wide
        assert "racing/race_view.gd" in scene and "racing/race_camera.gd" in scene
        view = _node(scene, "View")
        assert f"footprint = Vector2i({FOOT[0]}, {FOOT[1]})" in view
        # (48 px, three tiles of 16, is what the node has when the scene says nothing)
        said = re.search(r"cell_px = ([0-9.]+)", view)
        assert (float(said.group(1)) if said else 48.0) == 3 * tile, (
            "a car of 21 px on these diamonds: three tiles a diamond"
        )
        assert f"origin = Vector2({tile}, {tile})" in view, "behind the wall round the field"
        # the ground is the tile set of diamonds; the road is drawn (the packs name no piece)
        assert "generated/tilesets/iso.tres" in scene and "tile_map_data" in scene
        road_rows = sum(1 for row in planned["rows"] if set(row) - {"g", "."})
        assert scene.count('parent="Road"') >= road_rows, "a run of road for every row that has one"
        assert 'name="Marks"' in scene and 'name="Walls"' in scene
        # what a car can touch is where the plan has it: the first barrier is the top wall
        width = len(planned["rows"][0])
        barriers = scene[scene.index('[node name="Barriers"') :]
        assert f"position = Vector2({width * tile / 2:g}, {tile / 2:g})" in barriers
        assert 'parent="Barriers"' in scene and 'Polygon2D" parent="Barriers"' not in scene
        # the cars stand on the grid of the plan
        car = _node(scene, "Car")
        at = re.search(r"position = Vector2\(([-0-9.]+), ([-0-9.]+)\)", car)
        assert at, "the car has a place"
        x, y = float(at.group(1)), float(at.group(2))
        start = planned["start"]["position"]
        assert abs(x - start[0]) <= 3 * tile and abs(y - start[1]) <= 3 * tile
        assert "racing/race.gd" in scene and 'name="Race"' in scene
    # the picture of the Results page stays the plan from above, as the map in the corner does
    assert (target / "rpggen/results/starter_map.png").is_file()


def test_a_second_run_changes_nothing(race, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = race
    kept = {
        rel: (target / rel).read_bytes()
        for rel in [
            *SCENES,
            "generated/tilesets/iso.tres",
            "game/data/stages.json",
            "generated/data/stages.json",
            "project.godot",
            paths.CATALOG,
            paths.CONFIG,
            paths.LEDGER,
            "rpggen/build_state.json",
        ]
    }
    again = orchestrator.run_in_memory(_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_a_pack_without_a_car_races_the_drawn_one_with_the_stick_and_a_fixed_camera(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    cfg = _config((TILES,), steering="absolute", camera="fixed", tracks=2, rivals=2)
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    assert _smoke(target) == STEPS
    drawn = sorted(i.detail["thing"] for i in result.issues if i.code == "ASSET-031")
    assert drawn == ["car in sixteen headings"], "the drawn car; the ground is the pack's"
    assert not [i for i in result.issues if i.code == "TILE-012"]
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert f"{arcade_kit.KIT_DIR}/car.png" in car and "headings = 16" in car
    assert "absolute_steering = true" in car
    track = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert "fixed = true" in _node(track, "Camera")
    # a car of 24 px on diamonds of 60 x 34: two tiles a diamond
    assert "cell_px = 32.0" in _node(track, "View")
    assert not (target / "generated/scenes/stages/stage_03.tscn").exists()
    assert not (target / "generated/scenes/racing/rival_3.tscn").exists()

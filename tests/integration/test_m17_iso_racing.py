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


# ------------------------------------------------- Dirt cup on Stone isle (T17.18)
#
# The racing sample's plan on isometric tiles, as far as the two sample packs allow: the
# ground and the road pieces are *Stone isle*'s, the car, the rivals, the pickups and the
# hazards *Dirt cup*'s (drawn from above: they look flat on diamonds, which the Mapping page
# says). The square tiles of *Dirt cup* are left out, which is said (`TILE-011`).

ISLE = REPO / "sample_pack_iso"
CUP = REPO / "sample_pack_race"
ISLE_FOOT = (40, 22)


def _cup_config() -> config.GeneratorConfig:
    from rpggen.core import archive, catalog, inventory, mapping, profiles

    profiles.install_profile(ISLE / "sample_iso.rpgprofile.json")
    profiles.install_profile(CUP / "sample_race.rpgprofile.json")
    opened = [archive.open_pack(pack, set(), pack_id=pack.name) for pack in (ISLE, CUP)]
    cat, _issues, _made = catalog.assemble(
        [(pack, inventory.build_inventory(pack)) for pack in opened], None, []
    )
    cfg = config.default_for(
        "Dirt Cup",
        [config.pack_ref_from_source(pack, pack.name) for pack in (ISLE, CUP)],
        archetype="racing",
    )
    cfg.projection = "isometric"
    cfg.starter = mapping.default_starter(cat, "racing", "isometric")
    return cfg


def test_dirt_cup_is_raced_on_the_diamonds_of_stone_isle(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    from rpggen.core import track_plan, world_plan

    cfg = _cup_config()
    assert cfg.starter["vehicle"] == "sample_pack_race.cars.player_car"
    assert cfg.starter["ground"] == "sample_pack_iso.png.grass"
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    assert _smoke(target) == STEPS, "the eleven steps of every racing game, as they are"
    left_out = [i for i in result.issues if i.code == "TILE-011"]
    assert len(left_out) == 1 and "sample_pack_iso.png.grass" in left_out[0].message
    saved = jsonio.read(target / paths.CONFIG)
    assert (saved["archetype"], saved["projection"]) == ("racing", "isometric")
    # the plan is the one the sample has seen from above: it knows no view
    stored = world_plan.load(target)["stages"]
    facts = track_plan.facts_of(saved["resolution"], saved["base_tile_size"])
    assert stored == track_plan.plan({}, saved["seed"], facts)
    assert track_plan.check(stored) == [] and len(stored["list"]) == 4
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    for planned, listed in zip(stored["list"], tracks, strict=True):
        for key in ("start", "checkpoints", "waypoints", "laps"):
            assert listed[key] == planned[key], f"{key} of {planned['id']} is the plan's"
    car = _text(target, "generated/scenes/racing/car.tscn")
    assert "sample_pack_race" in car and "racing/heading_sprite.gd" in car
    for index in range(len(stored["list"])):
        scene = _text(target, f"generated/scenes/stages/stage_{index + 1:02d}.tscn")
        assert "generated/tilesets/iso.tres" in scene and "racing/race_view.gd" in scene
        # the diamond of the pack, as many times larger as the car's picture asks (T17.15)
        said = re.search(r"footprint = Vector2i\((\d+), (\d+)\)", _node(scene, "View"))
        assert said is not None
        wide, high = int(said[1]), int(said[2])
        assert wide % ISLE_FOOT[0] == 0 and wide * ISLE_FOOT[1] == high * ISLE_FOOT[0], (wide, high)
    # the lap of the sequence went through every checkpoint of the first track
    log = _text(target, "rpggen/logs/godot_smoke.log")
    lap = [line for line in log.splitlines() if "INFO race_is_driven" in line]
    found = re.search(r"(\d+) checkpoints", lap[0]) if lap else None
    assert found is not None and int(found[1]) == len(tracks[0]["checkpoints"]), lap


# --------------------------------------------------------- round corners (T17.22)
#
# The synthetic pack ``iso_kit`` has road pieces that name their sides, in the manner of
# *Vector Roads*: straights, and corners that turn in a quarter circle. A race on them is
# planned with round corners, so that what the plan calls road is what a piece shows as road:
# the race is driven on the flat plan, as ever, and a car is never seen on the verge while the
# plan has it on the road, nor the other way round.

KIT = REPO / "test_packs" / "synthetic" / "iso_kit"
KIT_FOOT = (64, 36)
ASPHALT = (84, 84, 92)
VERGE = (104, 170, 84)


def _kit_config() -> config.GeneratorConfig:
    from rpggen.core import archive, catalog, inventory, mapping

    opened = [archive.open_pack(pack, set(), pack_id=pack.name) for pack in (KIT, MINIATURE)]
    cat, _issues, _made = catalog.assemble(
        [(pack, inventory.build_inventory(pack)) for pack in opened], None, []
    )
    cfg = config.default_for(
        "Kit Cup",
        [config.pack_ref_from_source(pack, pack.name) for pack in (KIT, MINIATURE)],
        archetype="racing",
    )
    cfg.projection = "isometric"
    cfg.starter = mapping.default_starter(cat, "racing", "isometric")
    return cfg


@pytest.fixture(scope="module")
def round_race(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    target = tmp_path_factory.mktemp("iso_round") / "out"
    result = orchestrator.run_in_memory(_kit_config(), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _ground_cells(scene: str) -> dict[tuple[int, int], tuple[int, int, int]]:
    """cell -> (source, column, row) of the tiles of a scene's ``Ground`` layer, read from the
    bytes Godot stores a layer's cells in: a version, then twelve bytes a cell."""
    import base64
    import struct

    node = _node(scene, "Ground")
    found = re.search(r'tile_map_data = PackedByteArray\("([^"]*)"\)', node)
    assert found, "the ground layer has cells"
    raw = base64.b64decode(found[1])
    out = {}
    for at in range(2, len(raw) - 11, 12):
        x, y, source, column, row, _alternative = struct.unpack_from("<hhHHHH", raw, at)
        out[(x, y)] = (source, column, row)
    return out


def test_a_race_on_round_corner_pieces_is_planned_with_round_corners_and_passes(round_race) -> None:  # noqa: ANN001
    from rpggen.core import track_plan, world_plan

    target, result = round_race
    assert not _errors(result)
    assert _smoke(target) == STEPS, "the eleven steps of every racing game"
    assert not [i for i in result.issues if i.code == "VAL-029"]
    stored = world_plan.load(target)["stages"]
    saved = jsonio.read(target / paths.CONFIG)
    assert stored["corners"] == "round"
    facts = track_plan.facts_of(saved["resolution"], saved["base_tile_size"], "round")
    assert stored == track_plan.plan({}, saved["seed"], facts), "the plan of round corners"
    assert track_plan.check(stored) == []
    tracks = jsonio.read(target / "game/data/stages.json")["stages"]
    for planned, listed in zip(stored["list"], tracks, strict=True):
        for key in ("start", "checkpoints", "waypoints", "pickups", "laps"):
            assert listed[key] == planned[key], f"{key} of {planned['id']} is the plan's"
    # the lap of the sequence went through every checkpoint of the first track
    log = _text(target, "rpggen/logs/godot_smoke.log")
    lap = [line for line in log.splitlines() if "INFO race_is_driven" in line]
    found = re.search(r"(\d+) checkpoints", lap[0]) if lap else None
    assert found is not None and int(found[1]) == len(tracks[0]["checkpoints"]), lap


def test_what_the_plan_calls_road_is_what_the_pieces_show_as_road(round_race) -> None:  # noqa: ANN001
    import math

    from PIL import Image

    from rpggen.core import catalog, track_plan, world_plan

    target, _result = round_race
    stored = world_plan.load(target)["stages"]
    data = jsonio.read(target / paths.CATALOG)
    cat = catalog.Catalog.from_json(data)
    (definition,) = [t for t in data["tilesets"] if t.get("projection") == "isometric"]
    by_tile = {
        (at["source"], *at["coords"]): asset_id for asset_id, at in definition["tiles"].items()
    }
    block, tile = track_plan.BLOCK, stored["tile"]
    pictures: dict[str, Image.Image] = {}

    def shown(asset_id: str, east: float, south: float) -> tuple[int, int, int]:
        """The colour a piece shows at a point of its diamond (east, south: -0.5 to 0.5)."""
        asset = cat.asset(asset_id)
        facets = catalog.effective(asset)
        if asset_id not in pictures:
            pictures[asset_id] = Image.open(KIT / "PNG" / Path(asset.path).name).convert("RGB")
        (ox, oy), (fw, fh) = facets["origin"], facets["footprint"]
        x = int(round(ox + (east - south) * fw / 2.0))
        y = int(round(oy + (east + south) * fh / 2.0))
        return pictures[asset_id].getpixel((x, y))

    sides_of = {(0, -1): "n", (1, 0): "e", (0, 1): "s", (-1, 0): "w"}
    checked = corners = 0
    for index, planned in enumerate(stored["list"]):
        scene = _text(target, f"generated/scenes/stages/stage_{index + 1:02d}.tscn")
        ground = _ground_cells(scene)
        loop = [tuple(c) for c in planned["loop"]]
        rows = planned["rows"]
        laid = {}
        for i, cell in enumerate(loop):
            arms = [
                (loop[i - 1][0] - cell[0], loop[i - 1][1] - cell[1]),
                (loop[(i + 1) % len(loop)][0] - cell[0], loop[(i + 1) % len(loop)][1] - cell[1]),
            ]
            asset_id = by_tile[ground[cell]]
            laid[cell] = asset_id
            facets = catalog.effective(cat.asset(asset_id))
            wanted = sorted((sides_of[arm] for arm in arms), key="nesw".index)
            assert facets["role"] == "ROAD" and facets["joins"] == wanted, (cell, asset_id)
            if arms[0] != (-arms[1][0], -arms[1][1]):
                corners += 1
                assert facets["corner"] == "round", f"{cell}: a round piece on a corner of the plan"
            # every tile of the cell's block: road in the plan is asphalt or kerb in the picture,
            # grass in the plan is verge or kerb, never the other's. (A tile of the plan is three
            # and a half px of this pack's diamond: a tile on the very edge of the road, with
            # the other ground beside it, may show a pixel of either and is not asked.)
            ox, oy = track_plan.BORDER + cell[0] * block, track_plan.BORDER + cell[1] * block
            for ty in range(block):
                for tx in range(block):
                    colour = shown(asset_id, (tx + 0.5) / block - 0.5, (ty + 0.5) / block - 0.5)
                    on_road = rows[oy + ty][ox + tx] != "g"
                    beside = {
                        rows[oy + ty + dy][ox + tx + dx] != "g"
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    }
                    if beside != {on_road}:
                        continue
                    assert colour != (VERGE if on_road else ASPHALT), (
                        f"track {index + 1}, cell {cell}, tile ({tx}, {ty}): the plan says "
                        f"{'road' if on_road else 'grass'} and the piece shows {colour}"
                    )
                    checked += 1
        # the lap: the line from waypoint to waypoint, a step of a third of a tile, lies on the
        # road of the plan and on the asphalt of the pieces all the way round
        points = [w["position"] for w in planned["waypoints"]]
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            steps = max(1, int(math.dist(a, b) / (tile / 3)))
            for n in range(steps):
                x = (a[0] + (b[0] - a[0]) * n / steps) / tile
                y = (a[1] + (b[1] - a[1]) * n / steps) / tile
                assert rows[int(y)][int(x)] != "g", f"track {index + 1}: the lap leaves the road"
                cx, cy = (x - track_plan.BORDER) / block, (y - track_plan.BORDER) / block
                cell = (int(cx), int(cy))
                colour = shown(laid[cell], cx - cell[0] - 0.5, cy - cell[1] - 0.5)
                assert colour != VERGE, f"track {index + 1}: a car on the lap is seen on the verge"
                checked += 1
    assert corners >= 4 * len(stored["list"]) and checked > 2000

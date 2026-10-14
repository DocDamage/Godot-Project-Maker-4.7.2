"""T17.22: real isometric packs in the builder, the Python side, on the synthetic pack
``iso_kit`` (walls along one side of a diamond, a wall with a door, a roof, road corners that
are round and square): how round a road's corner is, read from its picture; the planners count
a kit of pieces as a building; and a race whose corner pieces are round is planned with round
corners, while every other race is planned as it always was."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from rpggen import schema
from rpggen.core import (
    archive,
    catalog,
    config,
    inventory,
    map_preview,
    orchestrator,
    track_plan,
)
from rpggen.core.analyzer import isometric as measure

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
FOOT = (64, 36)
GRASS = (104, 170, 84, 255)
ASPHALT = (84, 84, 92, 255)
KERB = (226, 222, 206, 255)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(name: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / name, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


@pytest.fixture(scope="module")
def kit() -> catalog.Catalog:
    import os
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rpggen_iso_kit_") as tmp:
        old = os.environ.get("RPGGEN_CACHE_DIR")
        os.environ["RPGGEN_CACHE_DIR"] = tmp
        try:
            return _assemble("iso_kit")
        finally:
            if old is None:
                os.environ.pop("RPGGEN_CACHE_DIR", None)
            else:
                os.environ["RPGGEN_CACHE_DIR"] = old


def _facets(cat: catalog.Catalog, stem: str) -> dict:
    return catalog.effective(next(a for a in cat.assets if a.id == f"iso_kit.png.{stem}"))


# --------------------------------------------------------------------------- the corner's shape


def _face(colour_at) -> tuple[np.ndarray, tuple[float, float]]:  # noqa: ANN001
    """A flat diamond of ``FOOT`` in a picture, every pixel the colour ``colour_at`` gives its
    place on the grid (east, south, from -0.5 to 0.5), and the middle of the diamond."""
    w, h = FOOT
    rgba = np.zeros((h + 8, w + 8, 4), dtype=np.uint8)
    middle = (4 + w / 2.0, 4 + h / 2.0)
    for y in range(rgba.shape[0]):
        for x in range(rgba.shape[1]):
            u = (x + 0.5 - middle[0]) / (w / 2.0)
            v = (y + 0.5 - middle[1]) / (h / 2.0)
            if abs(u) + abs(v) <= 1.0:
                rgba[y, x] = colour_at((u + v) / 2.0, (v - u) / 2.0)
    return rgba, middle


def _corner(
    shape: str, pivot: tuple[float, float], reach_to: float = 7 / 9, reach_from: float = 2 / 9
):
    """The face of a road that turns about ``pivot`` (a corner of the diamond)."""

    def colour(east: float, south: float) -> tuple[int, int, int, int]:
        dx, dy = abs(east - pivot[0]), abs(south - pivot[1])
        reach = max(dx, dy) if shape == "square" else math.hypot(dx, dy)
        low = 0.0 if shape == "square" else reach_from
        return ASPHALT if low <= reach <= reach_to else GRASS

    return colour


@pytest.mark.parametrize(
    ("joins", "pivot"),
    [
        (["e", "s"], (0.5, 0.5)),
        (["n", "e"], (0.5, -0.5)),
        (["s", "w"], (-0.5, 0.5)),
        (["n", "w"], (-0.5, -0.5)),
    ],
)
def test_a_corner_that_turns_in_a_quarter_circle_is_round_and_one_cut_square_is_square(
    joins: list[str], pivot: tuple[float, float]
) -> None:
    rgba, middle = _face(_corner("round", pivot))
    assert measure.corner_shape(rgba, middle, FOOT, joins) == "round"
    rgba, middle = _face(_corner("square", pivot))
    assert measure.corner_shape(rgba, middle, FOOT, joins) == "square"
    # a wider and a narrower road are told the same way: the measure is a ratio
    for reach in (0.6, 0.95):
        rgba, middle = _face(_corner("round", pivot, reach, 0.1))
        assert measure.corner_shape(rgba, middle, FOOT, joins) == "round", reach
        rgba, middle = _face(_corner("square", pivot, reach))
        assert measure.corner_shape(rgba, middle, FOOT, joins) == "square", reach


def test_what_is_no_corner_of_a_road_has_no_shape() -> None:
    rgba, middle = _face(_corner("round", (0.5, 0.5)))
    assert measure.corner_shape(rgba, middle, FOOT, ["n", "s"]) is None, "a straight"
    assert measure.corner_shape(rgba, middle, FOOT, ["e"]) is None, "an end"
    assert measure.corner_shape(rgba, middle, FOOT, ["n", "e", "s"]) is None, "a junction"
    # the reader asks only about the sides the surface runs out on (a name may say the sides a
    # kerb is on): for this piece they are e and s
    assert measure.open_sides(rgba, middle, FOOT) == ["e", "s"]
    plain, middle = _face(lambda _east, _south: GRASS)
    assert measure.corner_shape(plain, middle, FOOT, ["e", "s"]) == "square", (
        "a face of one colour fills its corner: who asks must know that it is a road's"
    )
    empty = np.zeros((40, 72, 4), dtype=np.uint8)
    assert measure.corner_shape(empty, (36.0, 20.0), FOOT, ["e", "s"]) is None


def test_the_reader_says_how_the_corners_of_the_pack_turn(kit: catalog.Catalog) -> None:
    for sides in ("ne", "es", "sw", "nw"):
        road, street = _facets(kit, f"road{sides}"), _facets(kit, f"street{sides}")
        assert (road["role"], road["joins"], road["corner"]) == ("ROAD", list(sides), "round")
        assert (street["joins"], street["corner"]) == (list(sides), "square")
    for stem in ("roadns", "roadew", "grass_01_0", "plate_road_01_0", "stone_wall_01_0"):
        assert "corner" not in _facets(kit, stem), stem
    schema.validate("catalog", kit.to_json())


# --------------------------------------------------------------------------- a house of pieces


def test_the_pieces_of_the_pack_are_walls_by_their_sides(kit: catalog.Catalog) -> None:
    # turn 0 stands along the east side in this pack: the side is measured, not the turn
    for turn, side in enumerate("eswn"):
        wall = _facets(kit, f"stone_wall_01_{turn}")
        assert (wall["usage"], wall["role"], wall["edge"], wall["turn"]) == (
            "iso_tile",
            "WALL",
            side,
            turn,
        )
        assert "door" in _facets(kit, f"stone_door_01_{turn}")["tags"]
        assert "window" in _facets(kit, f"stone_window_01_{turn}")["tags"]
        fence = _facets(kit, f"wood_fence_01_{turn}")
        assert fence["edge"] == side and "fence" in fence["tags"], "a fence along a side says so"
        roof = _facets(kit, f"roof_point_01_{turn}")
        assert (roof["usage"], roof["role"]) == ("iso_tile", "DECORATION") and "roof" in roof[
            "tags"
        ]
        assert "edge" not in roof
    assert _facets(kit, "stone_wall_01_3")["rise"] > _facets(kit, "stone_wall_01_0")["rise"], (
        "more of a wall shows above its diamond on a far side"
    )
    assert not [a for a in kit.assets if catalog.effective(a).get("role") == "BUILDING"]


def test_the_planners_count_a_kit_of_pieces_as_a_building(kit: catalog.Catalog) -> None:
    assert map_preview.iso_house_kit(kit) == {
        "wall": "iso_kit.png.stone_short_wall_01_0",
        "door": "iso_kit.png.stone_door_01_0",
    }
    assert map_preview.iso_buildings(kit) == [], "the pack drew no whole house"
    house = map_preview.building_info_for(kit, "", "isometric")
    assert house == {"size": [2, 2], "door": [0, 2]}, "the footprint a village's plan wants"
    assert map_preview.building_info_for(kit) == {}, "nothing of it in a top-down plan"
    cfg = config.default_for(
        "x", [config.PackRef("iso_kit", str(SYNTH / "iso_kit"), "0" * 64, "folder")]
    )
    cfg.projection = "isometric"
    village = map_preview.plan(cfg.starter_map_options(), cfg.seed, house, cfg.archetype)
    assert village["buildings"], "a village of such a pack has houses"
    # a farm's planner is told no house of the packs: it plans its own footprints, and the
    # builder puts the pieces together on each
    cfg.archetype = "farm"
    facts = orchestrator.farm_facts(cfg, kit)
    assert "house" not in facts and "coop" not in facts and "barn" not in facts
    people = orchestrator.people_facts(cfg, kit, {"crops": []})
    assert people["houses"] == len(village["buildings"]) > 0, "people live in the houses of pieces"


def test_a_pack_without_a_door_or_without_a_wall_on_every_side_has_no_kit(
    kit: catalog.Catalog,
) -> None:
    import copy

    doorless = copy.deepcopy(kit)
    for asset in doorless.assets:
        if "stone_door" in asset.id:
            asset.status = "UNUSED"
    assert map_preview.iso_house_kit(doorless) == {}
    assert map_preview.building_info_for(doorless, "", "isometric") == {}
    three_sides = copy.deepcopy(kit)
    for asset in three_sides.assets:
        facets = catalog.effective(asset)
        if facets.get("edge") == "n" and not set(facets.get("tags", [])) & {
            "door",
            "window",
            "fence",
        }:
            asset.status = "UNUSED"
    assert map_preview.iso_house_kit(three_sides) == {}
    # a fence is no wall of a house, and its gate no door
    fences = copy.deepcopy(kit)
    for asset in fences.assets:
        if "stone_" in asset.id and catalog.effective(asset).get("edge"):
            asset.overrides = {"tags": [*catalog.effective(asset).get("tags", []), "fence"]}
    assert map_preview.iso_house_kit(fences) == {}


def test_a_pack_with_a_whole_house_is_planned_as_it_was(tmp_path: Path) -> None:
    tiles = _assemble("iso_tiles")
    assert map_preview.iso_house_kit(tiles) == {}, "no walls along a side"
    assert map_preview.building_info_for(tiles, "", "isometric") == {"size": [1, 1], "door": [0, 1]}


# --------------------------------------------------------------------------- round corners


def _block(track: dict, cell: list[int]) -> list[str]:
    ox, oy = (
        track_plan.BORDER + cell[0] * track_plan.BLOCK,
        track_plan.BORDER + cell[1] * track_plan.BLOCK,
    )
    return [row[ox : ox + track_plan.BLOCK] for row in track["rows"][oy : oy + track_plan.BLOCK]]


def _corners(track: dict) -> list[tuple[list[int], list[tuple[int, int]]]]:
    loop = track["loop"]
    out = []
    for i, cell in enumerate(loop):
        before, after = loop[i - 1], loop[(i + 1) % len(loop)]
        arms = [
            (before[0] - cell[0], before[1] - cell[1]),
            (after[0] - cell[0], after[1] - cell[1]),
        ]
        if arms[0] != (-arms[1][0], -arms[1][1]):
            out.append((cell, arms))
    return out


def test_a_race_on_round_corner_pieces_is_planned_with_round_corners(kit: catalog.Catalog) -> None:
    assert track_plan.round_corners(kit, "isometric") == "round"
    assert track_plan.round_corners(kit, "top_down") == "", (
        "a race seen from above is drawn, not laid"
    )
    assert track_plan.round_corners(_assemble("iso_tiles"), "isometric") == "", "no pieces"
    facts = track_plan.facts_of((640, 360), 16, "round")
    assert facts == {"view": [640, 360], "tile": 16, "corners": "round"}
    assert track_plan.facts_of((640, 360), 16) == {"view": [640, 360], "tile": 16}
    for options in ({}, {"track_size": "large", "difficulty": "hard", "tracks": 6}):
        plan = track_plan.plan(options, 12345, facts)
        square = track_plan.plan(options, 12345, track_plan.facts_of((640, 360), 16))
        assert plan["corners"] == "round" and "corners" not in square
        assert track_plan.check(plan) == [], "VAL-029: closed, in order, wide enough for two cars"
        schema.validate("world_plan", track_plan.world(plan, 12345))
        lo, hi = track_plan.VERGE, track_plan.VERGE + track_plan.ROAD
        for track, flat in zip(plan["list"], square["list"], strict=True):
            assert track["loop"] == flat["loop"], "the same loop: only its corners are rounded"
            assert (
                track["checkpoints"] == flat["checkpoints"]
                and track["barriers"] == flat["barriers"]
            )
            assert track["start"] == flat["start"] and track["pickups"] == flat["pickups"]
            corners = _corners(track)
            assert corners
            waypoints = {tuple(w["cell"]): w["position"] for w in track["waypoints"]}
            for cell, arms in corners:
                px, py = track_plan.corner_pivot(arms)
                block = _block(track, cell)
                for y, row in enumerate(block):
                    for x, letter in enumerate(row):
                        reach = math.hypot(
                            x + 0.5 - px * track_plan.BLOCK, y + 0.5 - py * track_plan.BLOCK
                        )
                        assert (letter != "g") == (lo <= reach <= hi), (cell, x, y)
                # the road leaves the cell where the square corner's does: five tiles in the middle
                for dx, dy in arms:
                    edge = [block[y][x] for x in range(9) for y in range(9)
                            if (dx and x == (8 if dx > 0 else 0)) or (dy and y == (8 if dy > 0 else 0))]  # fmt: skip
                    assert "".join(edge) == "ggrrrrrgg"
                # the car's line goes through the middle of the ring, not the middle of the block
                at = waypoints[tuple(cell)]
                tile = plan["tile"]
                middle = track_plan.corner_middle(tuple(cell), arms)
                assert at == [round(middle[0] * tile, 2), round(middle[1] * tile, 2)]
                pivot = (
                    (track_plan.BORDER + (cell[0] + px) * 9) * tile,
                    (track_plan.BORDER + (cell[1] + py) * 9) * tile,
                )
                assert math.isclose(math.dist(at, pivot), 4.5 * tile, abs_tol=0.02)
            # a straight is what it was
            straight = next(c for c in track["loop"] if c not in [cell for cell, _ in corners])
            assert _block(track, straight) == _block(flat, straight)
    # a track added later is planned like the rest
    more, added = track_plan.extend(plan, [{"name": "One more"}], 12345)
    assert added == ["One more"] and more["corners"] == "round"
    last = more["list"][-1]
    cell, arms = _corners(last)[0]
    px, py = track_plan.corner_pivot(arms)
    far = _block(last, cell)[0 if py else 8][0 if px else 8]
    assert far == "g", "the outside of its corners is grass too"


def test_a_square_piece_among_the_corners_keeps_the_square_plan(kit: catalog.Catalog) -> None:
    import copy

    mixed = copy.deepcopy(kit)
    for asset in mixed.assets:
        if asset.id == "iso_kit.png.streetne":
            asset.overrides = {"role": "ROAD"}
        if asset.id == "iso_kit.png.roadne":
            asset.status = "UNUSED"
    assert track_plan.round_corners(mixed, "isometric") == "", "one of the four is cut square"
    unknown = copy.deepcopy(kit)
    for asset in unknown.assets:
        if asset.id == "iso_kit.png.roadsw":
            asset.overrides = {"corner": None}
    assert track_plan.round_corners(unknown, "isometric") == ""

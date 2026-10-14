"""T17.12: isometric packs, one picture a tile. The footprint from a pack's words and measured
from its flat tiles, turns and headings, sides in names, the two views, the zip in a folder,
the atlas beside its pictures, and the two synthetic packs."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import (
    archive,
    catalog,
    classifier,
    config,
    explain,
    inventory,
    labels,
    mapping,
    pack_sniff,
    requirements,
)
from rpggen.core.adapters import isometric, kenney_atlas, naming, sequences
from rpggen.core.analyzer import isometric as measure

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _catalog(source: Path) -> tuple[catalog.Catalog, list]:
    opened = archive.open_pack(source, set())
    cat, issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat, list(issues)


def _by_path(cat: catalog.Catalog) -> dict[str, catalog.Asset]:
    return {a.path.split("/", 3)[-1]: a for a in cat.assets}


def _footprint(cat: catalog.Catalog) -> tuple[int, int, str] | None:
    return catalog.isometric_footprint(cat.packs[0])


def _save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _tiles(tool, pack: Path, foot, side: int, canvas, count: int = 6, stem: str = "tile") -> None:  # noqa: ANN001
    """``count`` flat tiles turned four ways, in the manner of the rendered packs."""
    for i in range(1, count + 1):
        for turn in range(4):
            block = tool._iso_block(canvas, foot, side, tool.pal(i), turn=turn)
            _save(block, pack / "PNG" / f"{stem}_{i:03d}_{turn}.png")


# ------------------------------------------------------------------------------ measuring


def _mask(img: Image.Image) -> np.ndarray:
    return measure.painted(np.asarray(img.convert("RGBA"), dtype=np.uint8))


@pytest.mark.parametrize(
    ("foot", "side"),
    [
        ((64, 32), 0),  # twice as wide as high, no block under it
        ((64, 32), 9),
        ((180, 104), 21),  # the 30 degree diamond of the rendered packs
        ((180, 125), 0),
        ((180, 125), 12),
        ((120, 69), 5),
    ],
)
def test_the_diamond_of_a_flat_tile_is_measured_whatever_its_shape(tool, foot, side) -> None:  # noqa: ANN001
    canvas = (foot[0] + 8, foot[1] + side + 30)
    tile = measure.flat_tile(_mask(tool._iso_block(canvas, foot, side, tool.pal(3))))
    assert tile is not None and tile.width == foot[0]
    found = measure.diamond_height(tile)
    assert found is not None and found[0] == foot[1], found
    diamond = measure.measure([tile] * 3)
    assert diamond is not None
    assert (diamond.width, diamond.height, diamond.side) == (*foot, side)


@pytest.mark.parametrize("side", [0, 6])
@pytest.mark.parametrize("foot", [(28, 16), (32, 18), (34, 18), (36, 20), (40, 22)])
def test_a_small_diamond_is_not_measured_a_pixel_too_high(tool, foot, side) -> None:  # noqa: ANN001
    """An edge 16 columns long is a staircase of nine steps, and a line fitted to it is 18.85
    high for a diamond 32 x 18: the height is one the staircase can have."""
    canvas = (foot[0] + 8, foot[1] + side + 30)
    tile = measure.flat_tile(_mask(tool._iso_block(canvas, foot, side, tool.pal(3))))
    assert tile is not None and tile.width == foot[0]
    above, below = measure.slope_bounds(tile)
    assert above < foot[1] / foot[0] < below
    assert above < measure.edge_slope(tile) < below
    found = measure.diamond_height(tile)
    assert found is not None and found[0] == foot[1], found
    diamond = measure.measure([tile] * 3)
    assert diamond is not None
    assert (diamond.width, diamond.height, diamond.side) == (*foot, side)


def _drawn(foot: tuple[int, int], lift: float, side: int = 0) -> np.ndarray:
    """The painted pixels of a diamond drawn by hand: ``lift`` 0.0 gives the top a row of four
    pixels (every step of the edge is cut where it begins), 0.5 a row of two (where its
    middle is), as the two habits of pixel art are."""
    w, h = foot
    tops = [int(abs(2 * x + 1 - w) * h / (2 * w) + lift) for x in range(w)]
    rows = h if lift == 0.0 else h + 1  # the widest row is drawn twice, or once
    mask = np.zeros((rows + side + 2, w + 4), dtype=bool)
    for x, top in enumerate(tops):
        mask[top : rows - top + side, 2 + x] = True
    return mask


@pytest.mark.parametrize("lift", [0.0, 0.5])
@pytest.mark.parametrize("foot", [(32, 16), (32, 18), (36, 20), (40, 22), (48, 24), (64, 32)])
def test_a_diamond_is_measured_whichever_way_its_tip_is_drawn(foot, lift) -> None:  # noqa: ANN001
    mask = _drawn(foot, lift)
    assert int(mask[mask.any(axis=1).argmax()].sum()) == (4 if lift == 0.0 else 2)
    tile = measure.flat_tile(mask)
    assert tile is not None and tile.width == foot[0]
    diamond = measure.measure([tile] * 3)
    assert diamond is not None and (diamond.width, diamond.height) == foot


def test_a_fitted_slope_the_staircase_can_have_is_left_as_it_is(tool) -> None:  # noqa: ANN001
    """Only a fit that the pixels rule out is replaced, and where they say nothing sure (a
    tip cut off: no staircase of one line) the fit stands."""
    kept = 0
    for foot in ((64, 32), (100, 50), (120, 69), (180, 104), (256, 128)):
        block = tool._iso_block((foot[0] + 8, foot[1] + 40), foot, 9, tool.pal(2))
        tile = measure.flat_tile(_mask(block))
        assert tile is not None
        above, below = measure.slope_bounds(tile)
        edges = measure._upper_edges(tile)[1]
        fitted = sum(abs(float(np.polyfit(c, tile.top[c], 1)[0])) for c in edges) / len(edges)
        assert above < foot[1] / foot[0] < below
        if above < fitted < below:
            kept += 1
            assert measure.edge_slope(tile) == fitted
        assert round(foot[0] * measure.edge_slope(tile)) == round(foot[0] * fitted) == foot[1]
    assert kept >= 3
    blunt = _drawn((64, 32), 0.0)
    blunt[: blunt.any(axis=1).argmax() + 1] = False
    tile = measure.flat_tile(blunt)
    assert tile is not None
    above, below = measure.slope_bounds(tile)
    edges = measure._upper_edges(tile)[1]
    fitted = sum(abs(float(np.polyfit(c, tile.top[c], 1)[0])) for c in edges) / len(edges)
    assert not above < below and measure.edge_slope(tile) == fitted


def test_laying_two_whole_blocks_shows_no_gap_until_the_side_is_used_up(tool) -> None:  # noqa: ANN001
    """What was measured on the real packs, and why the side is taken off before laying: a
    block 180 x 104 on a side of 21 opens no gap from 104 up to 104 + 2 * 21."""
    foot, side = (180, 104), 21
    mask = _mask(tool._iso_block((180, 184), foot, side, tool.pal(1)))
    tile = measure.flat_tile(mask)
    assert tile is not None
    whole = measure.FlatTile(tile.box, 1, tile.top, tile.bottom + (side - 0))
    assert [measure.lay(whole, h)[0] for h in (104, 125, 104 + 2 * side - 2)] == [0, 0, 0]
    assert measure.lay(whole, 104 + 2 * side + 8)[0] > 0
    # the faces alone meet at the diamond's height and nowhere else
    assert sum(measure.lay(tile, 104)) <= tile.width  # a pixel a column at most
    assert measure.lay(tile, 125)[0] > 4 * tile.width
    assert measure.lay(tile, 84)[1] > 4 * tile.width


def test_a_picture_that_is_no_diamond_is_no_flat_tile(tool) -> None:  # noqa: ANN001
    box = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    box.paste((200, 60, 60, 255), (8, 8, 56, 56))
    assert measure.flat_tile(_mask(box)) is None
    assert measure.flat_tile(_mask(tool._iso_tree((60, 64), (60, 34), 8))) is None
    assert measure.flat_tile(_mask(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))) is None
    assert measure.measure([]) is None


def test_how_many_diamonds_a_base_stands_on() -> None:
    assert measure.stands_on(20, 60) == (1, 1)
    assert measure.stands_on(60, 60) == (1, 1)
    assert measure.stands_on(90, 60) == (2, 1)
    assert measure.stands_on(120, 60) == (2, 2)
    assert measure.stands_on(180, 60) == (3, 3)


# ------------------------------------------------------------------- the pack's own words


def test_tile_information_gives_the_width_and_the_height_is_measured(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """*Tile size* is the diamond with the side of the block under it: 60 x 42 for a diamond
    of 60 x 34 on a side of 8."""
    pack = tmp_path / "town"
    _tiles(tool, pack, (60, 34), 8, (70, 64))
    (pack / "Tile information.txt").write_text(
        "\n\tImage size : 70 x 64 px\n\tTile size  :  60 x  42 px\n", encoding="utf-8"
    )
    cat, issues = _catalog(pack)
    assert _footprint(cat) == (60, 34, "tile_information")
    assert catalog.pack_view(cat.packs[0]) == "isometric"
    tile = _by_path(cat)["PNG/tile_001_0.png"].detected
    assert tile["usage"] == "iso_tile" and tile["projection"] == "isometric"
    assert tile["canvas"] == [70, 64] and tile["footprint"] == [60, 34]
    assert tile["rise"] == 0 and tile["origin"] == [35, 64 - 8 - 17]
    assert not [i for i in issues if i.code == "TILE-010"]
    schema.validate("catalog", cat.to_json())


def test_the_map_tile_size_of_tiled_wins(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "golf"
    _tiles(tool, pack, (60, 34), 8, (60, 64))
    (pack / "Tile information.txt").write_text("Tile size : 60 x 42 px\n", encoding="utf-8")
    (pack / "Tiled (settings).txt").write_text(
        "Orientation: Isometric\nMap tile size: 60 x 36 px\nTileset tile size: 60 x 64 px\n",
        encoding="utf-8",
    )
    cat, _issues = _catalog(pack)
    assert _footprint(cat) == (60, 36, "tiled")


def test_an_isometric_tiled_map_in_a_sample_archive_says_the_footprint(
    tool,  # noqa: ANN001
    tmp_path: Path,
) -> None:
    pack = tmp_path / "isometric bases"
    for turn, letter in enumerate("NESW"):
        # a round base narrower than its cell: nothing to measure the cell by
        base = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
        base.paste((120, 90 + turn, 60, 255), (12, 70, 52, 90))
        _save(base, pack / "Isometric" / f"base_{letter}.png")
    (pack / "Samples").mkdir()
    tmx = (
        '<?xml version="1.0"?>\n<map version="1.2" orientation="isometric" width="4" '
        'height="4" tilewidth="64" tileheight="32">\n</map>\n'
    )
    with zipfile.ZipFile(pack / "Samples" / "Tiled Sample.zip", "w") as zf:
        zf.writestr("Sample.tmx", tmx)
    cat, issues = _catalog(pack)
    assert _footprint(cat) == (64, 32, "tiled")
    base = _by_path(cat)["Isometric/base_N.png"].detected
    assert base["usage"] == "sprite" and base["stands_on"] == [1, 1]
    assert not [i for i in issues if i.code == "TILE-010"]


@pytest.mark.parametrize("foot", [(64, 32), (180, 104), (180, 125)])
def test_a_pack_without_words_is_measured(tool, tmp_path: Path, foot) -> None:  # noqa: ANN001
    """Drawn at 2:1, at 30 degrees and at 180 x 125: never assumed to be half the width."""
    pack = tmp_path / "isometric_ground"
    _tiles(tool, pack, foot, 10, (foot[0], foot[1] + 40), count=3)
    cat, _issues = _catalog(pack)
    assert _footprint(cat) == (*foot, "measured")


def test_a_pack_that_says_nothing_is_isometric_when_its_pictures_show_it(
    tool,  # noqa: ANN001
    tmp_path: Path,
) -> None:
    pack = tmp_path / "landscape"
    _tiles(tool, pack, (64, 32), 6, (64, 48), count=3)
    _save(Image.new("RGBA", (16, 16), (200, 60, 60, 255)), pack / "icons" / "gem.png")
    cat, _issues = _catalog(pack)
    assert _footprint(cat) == (64, 32, "measured")
    assets = _by_path(cat)
    assert assets["PNG/tile_001_0.png"].detected["usage"] == "iso_tile"
    assert "projection" not in assets["icons/gem.png"].detected, "only where the pictures show it"


def test_a_pack_where_no_height_fits_is_tile_010(tmp_path: Path) -> None:
    pack = tmp_path / "isometric_things"
    for i in range(4):
        blob = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        blob.paste((90 + i * 20, 120, 60, 255), (6, 10, 34, 34))
        _save(blob, pack / "PNG" / f"thing{i}.png")
    cat, issues = _catalog(pack)
    found = [i for i in issues if i.code == "TILE-010"]
    assert len(found) == 1 and found[0].severity.value == "warning"
    assert "isometric_things" in found[0].message
    assert _footprint(cat) is None
    assert all("projection" not in a.detected for a in cat.assets), "the pictures stay pictures"


def test_axonometric_is_not_isometric(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "Axonometric Blocks"
    _tiles(tool, pack, (64, 32), 20, (64, 60), count=3)
    cat, issues = _catalog(pack)
    assert catalog.pack_view(cat.packs[0]) != "isometric"
    assert all(a.detected["usage"] != "iso_tile" for a in cat.assets)
    assert not [i for i in issues if i.code == "TILE-010"]


def test_one_width_and_three_heights_is_one_footprint_with_rises(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """The older packs: pictures cut to their tile, 132 x 83, 132 x 99 and 132 x 131, and a
    width one pixel off is the same tile."""
    pack = tmp_path / "Isometric Tiles"
    foot = (132, 66)
    for i in range(6):
        _save(tool._iso_block((132, 99), foot, 33, tool.pal(i)), pack / f"land_{i:03d}.png")
    _save(tool._iso_block((132, 83), foot, 17, tool.pal(7)), pack / "land_006.png")
    _save(tool._iso_block((132, 131), foot, 65, tool.pal(8)), pack / "land_007.png")
    wide = Image.new("RGBA", (133, 99), (0, 0, 0, 0))
    wide.paste(tool._iso_block((132, 99), foot, 33, tool.pal(9)), (0, 0))
    _save(wide, pack / "land_008.png")
    cat, _issues = _catalog(pack)
    assert _footprint(cat) == (132, 66, "measured")
    assets = _by_path(cat)
    assert {a.detected["usage"] for a in cat.assets} == {"iso_tile"}
    assert assets["land_000.png"].detected["rise"] == 0
    assert assets["land_006.png"].detected["rise"] == 0  # a lower tile: nothing above the diamond
    assert assets["land_007.png"].detected["rise"] == 32
    assert assets["land_007.png"].detected["canvas"] == [132, 131]
    assert assets["land_008.png"].detected["footprint"] == [132, 66]
    assert assets["land_008.png"].detected["canvas"] == [133, 99]


# ----------------------------------------------------------------------- turns and names


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("roadTile_001_0", ("roadTile_001", "", 0, "")),
        ("watercraftPack_001_7", ("watercraftPack_001", "", 7, "")),
        ("cornDouble_E", ("cornDouble", "E", 2, "")),
        ("taxi_NW", ("taxi", "NW", 7, "")),
        ("taxi_NEU", ("taxi", "NE", 1, "up")),
        ("taxi_SWD", ("taxi", "SW", 5, "down")),
    ],
)
def test_the_turn_a_name_ends_in(stem: str, expected: tuple) -> None:
    turn = naming.split_turn(stem)
    assert turn is not None
    assert (turn.base, turn.word, turn.number, turn.slope) == expected


@pytest.mark.parametrize("stem", ["roadTile_008", "hero_walk_n", "tree", "item_9", "walk3"])
def test_names_that_end_in_no_turn(stem: str) -> None:
    assert naming.split_turn(stem) is None


def _turns(*stems: str) -> int:
    found = [naming.split_turn(s) for s in stems]
    return naming.turns_of([t for t in found if t is not None])


def test_a_set_of_turns_is_all_four_or_all_eight() -> None:
    assert _turns("a_0", "a_1", "a_2", "a_3") == 4
    assert _turns(*(f"a_{n}" for n in range(8))) == 8
    assert _turns("a_N", "a_E", "a_S", "a_W") == 4
    assert _turns(*(f"a_{w}" for w in naming.COMPASS)) == 8
    assert _turns(*(f"a_{w}" for w in naming.COMPASS), "a_NEU", "a_NED") == 8
    assert _turns("a_1", "a_2", "a_3") == 0, "three variants numbered from one"
    assert _turns("a_0", "a_1", "a_2") == 0
    assert _turns("a_N", "a_E", "a_S") == 0
    assert _turns("a_N", "a_NE", "a_E", "a_S", "a_W") == 0
    assert _turns("a_0", "a_1", "a_2", "a_3", "a_N") == 0


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("beachCornerES", ("beachCorner", ["e", "s"])),
        ("beachE", ("beach", ["e"])),
        ("waterSW", ("water", ["s", "w"])),
        ("bridgeHighEW", ("bridgeHigh", ["e", "w"])),
        ("crossroadNSW", ("crossroad", ["n", "s", "w"])),
        ("roadHill2E", ("roadHill2", ["e"])),
    ],
)
def test_the_sides_a_name_ends_in(stem: str, expected: tuple) -> None:
    assert naming.split_joins(stem) == expected


@pytest.mark.parametrize("stem", ["Blue", "House", "News", "NEWS", "grass", "wallEE", "tree_N"])
def test_names_that_end_in_letters_and_are_no_sides(stem: str) -> None:
    assert naming.split_joins(stem) is None


def _still(path: str) -> SimpleNamespace:
    return SimpleNamespace(path=path, kind="image", ext=".png", image={"w": 8, "h": 8})


def test_sides_count_only_when_several_files_share_the_name() -> None:
    paths = ["PNG/beach.png", "PNG/beachE.png", "PNG/beachES.png", "PNG/waterS.png",
             "PNG/waterW.png", "PNG/HouseE.png", "PNG/poolNS.png", "PNG/Blue.png",
             "PNG/News.png"]  # fmt: skip
    found = isometric.joins_of([_still(p) for p in paths])  # type: ignore[list-item]
    assert found == {
        "PNG/beachE.png": ["e"],
        "PNG/beachES.png": ["e", "s"],
        "PNG/waterS.png": ["s"],
        "PNG/waterW.png": ["w"],
    }


def test_the_turns_of_a_tile_are_one_group_and_no_animation(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_roads"
    _tiles(tool, pack, (60, 34), 8, (60, 64), count=3, stem="roadTile")
    for letter in "NESW":
        _save(
            tool._iso_block((60, 64), (60, 34), 8, tool.pal(9)), pack / "PNG" / f"corn_{letter}.png"
        )
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    assert all(not a.detected.get("animations") for a in cat.assets)
    assert [assets[f"PNG/roadTile_001_{n}.png"].detected["turn"] for n in range(4)] == [0, 1, 2, 3]
    assert [assets[f"PNG/corn_{w}.png"].detected["turn"] for w in "NESW"] == [0, 1, 2, 3]
    first = assets["PNG/roadTile_001_0.png"]
    groups = catalog.colour_groups(cat)
    assert len(groups) == 4 and all(len(members) == 3 for members in groups.values())
    assert sorted(groups[first.id]) == sorted(
        assets[f"PNG/roadTile_001_{n}.png"].id for n in (1, 2, 3)
    )
    group = catalog.colour_group(cat, assets["PNG/roadTile_001_2.png"].id)
    assert [catalog.colour_name(a) for a in group] == ["", "turn_1", "turn_2", "turn_3"]
    assert "turn:2" in assets["PNG/roadTile_001_2.png"].detected["tags"]
    assert "turned" in explain.why(assets["PNG/roadTile_001_2.png"])
    assert catalog.season_groups(cat) == {}


def test_turns_in_two_colours_are_one_group(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_roofs"
    for colour in ("green", "red"):
        for turn in range(4):
            block = tool._iso_block((60, 64), (60, 34), 8, tool.pal(2), turn=turn)
            _save(block, pack / "PNG" / f"roof_{colour}_01_{turn}.png")
    cat, _issues = _catalog(pack)
    groups = catalog.colour_groups(cat)
    assert len(groups) == 1 and len(next(iter(groups.values()))) == 7
    names = [catalog.colour_name(a) for a in catalog.colour_group(cat, next(iter(groups)))]
    assert sorted(names) == sorted(
        ["green", "green_turn_1", "green_turn_2", "green_turn_3", "red", "red_turn_1",
         "red_turn_2", "red_turn_3"]
    )  # fmt: skip


def test_walk_0_to_walk_3_is_still_an_animation(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_hero"
    _tiles(tool, pack, (60, 34), 8, (60, 64), count=2)
    for n in range(4):
        frame = Image.new("RGBA", (16, 24), (0, 0, 0, 0))
        frame.paste((200, 60 + n * 20, 60, 255), (4 + n % 2, 4, 12, 23))
        _save(frame, pack / "hero" / f"walk_{n}.png")
    opened = archive.open_pack(pack, set())
    assert len(sequences.find_sequences(inventory.build_inventory(opened), set())) == 1
    cat, _issues = _catalog(pack)
    hero = _by_path(cat)["hero/walk_0.png"]
    assert hero.detected_by == "sequences" and list(hero.detected["animations"]) == ["walk_down"]
    assert len(hero.detected["animations"]["walk_down"]["frames"]) == 4
    assert "turn" not in hero.detected and "projection" not in hero.detected


# -------------------------------------------------------------------------------- headings


def _car(tool, heading: int, colour=(214, 64, 60, 255)) -> Image.Image:  # noqa: ANN001
    return tool._iso_car(heading, colour)


def test_a_car_in_eight_lettered_files_is_one_rotation_sheet(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_cars"
    for heading, letter in enumerate(naming.COMPASS):
        _save(_car(tool, heading), pack / "Taxi" / f"taxi_{letter}.png")
    _save(_car(tool, 1), pack / "Taxi" / "taxi_NEU.png")
    opened = archive.open_pack(pack, set())
    cat, _issues, generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    cars = [a for a in cat.assets if a.detected.get("headings")]
    assert len(cars) == 1
    car = cars[0]
    facets = car.detected
    assert facets["headings"] == 8 and facets["heading_order"] == "up_cw"
    assert facets["role"] == "VEHICLE" and facets["projection"] == "isometric"
    assert facets["heading_files"] == [f"Taxi/taxi_{w}.png" for w in naming.COMPASS]
    assert car.path.startswith("generated/frame_strips/") and car.path in generated
    with Image.open(generated[car.path]) as strip:
        assert list(strip.size) == facets["size"] == [8 * facets["frame"][0], facets["frame"][1]]
        cell = strip.crop((0, 0, *facets["frame"]))
        north = _car(tool, 0)
        assert cell.getchannel("A").getbbox() is not None
        assert np.asarray(cell).sum() == np.asarray(north.convert("RGBA")).sum()
    slope = _by_path(cat)["Taxi/taxi_NEU.png"].detected
    assert slope["role"] == "NONE" and "slope:up" in slope["tags"]
    assert "unused_because:slope" in slope["tags"]
    assert explain.unused_reason(slope)
    assert len(cat.assets) == 2, "the seven other headings are part of the sheet"
    schema.validate("catalog", cat.to_json())


def test_numbered_headings_start_with_the_narrow_one_that_points_up(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """``boat_0`` to ``_7`` go round clockwise; in the packs that were listed the first points
    up and to the left, so ``_1`` is the view from behind: the narrow one."""
    pack = tmp_path / "isometric_watercraft"
    for number in range(8):
        canvas = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        boat = _car(tool, (number - 1) % 8, (220, 110, 90, 255))
        canvas.paste(boat, ((48 - boat.width) // 2, (48 - boat.height) // 2))
        _save(canvas, pack / "PNG" / f"boat_003_{number}.png")
    cat, _issues = _catalog(pack)
    boats = [a for a in cat.assets if a.detected.get("headings")]
    assert len(boats) == 1 and len(cat.assets) == 1
    facets = boats[0].detected
    assert facets["headings"] == 8 and facets["role"] == "DECORATION" and "boat" in facets["tags"]
    assert facets["heading_files"][0] == "PNG/boat_003_1.png"
    assert facets["heading_files"][-1] == "PNG/boat_003_0.png"
    assert facets["frame"][0] < 48, "cut to what the eight views paint"
    assert boats[0].status == "NEEDS_REVIEW", "which number points up is a guess"


def test_a_car_in_four_headings(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_karts"
    for heading, letter in zip((0, 2, 4, 6), "NESW", strict=True):
        _save(_car(tool, heading), pack / f"kart_{letter}.png")
    cat, _issues = _catalog(pack)
    kart = next(a for a in cat.assets if a.detected.get("headings"))
    assert kart.detected["headings"] == 4 and kart.detected["role"] == "VEHICLE"
    schema.validate("catalog", cat.to_json())


def test_cars_in_two_colours_are_variants(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_vehicles"
    for colour, rgb in (("Black", (40, 40, 44, 255)), ("Red", (214, 64, 60, 255))):
        for heading, letter in enumerate(naming.COMPASS):
            _save(_car(tool, heading, rgb), pack / colour / "Sedan 1" / f"sedan_{letter}.png")
    cat, _issues = _catalog(pack)
    cars = sorted((a for a in cat.assets if a.detected.get("headings")), key=lambda a: a.id)
    assert len(cars) == 2
    assert catalog.colour_groups(cat) == {cars[0].id: [cars[1].id]}
    assert [catalog.colour_name(a) for a in cars] == ["black", "red"]


# ------------------------------------------------------------------------------- two views


def test_of_isometric_and_angle_the_first_is_used(tmp_path: Path) -> None:
    cat, _issues = _catalog(SYNTH / "iso_miniature")
    assets = _by_path(cat)
    for letter in "NESW":
        angle = assets[f"Angle/floorWood_{letter}.png"]
        assert angle.status == "UNUSED" and angle.detected["role"] == "NONE"
        assert "unused_because:other_view" in angle.detected["tags"]
        assert "Isometric" in explain.why(angle)
        assert assets[f"Isometric/floorWood_{letter}.png"].detected["usage"] == "iso_tile"
    assert not any(a.detected.get("projection") for p, a in assets.items() if p.startswith("Angle"))


def test_an_angle_folder_alone_is_read(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_alone"
    for letter in "NESW":
        _save(
            tool._iso_block((60, 64), (60, 34), 8, tool.pal(1)), pack / "Angle" / f"a_{letter}.png"
        )
    cat, _issues = _catalog(pack)
    assert all(a.detected["role"] != "NONE" for a in cat.assets)


# ------------------------------------------------------------------- the zip in its folder


def test_a_folder_that_is_one_archive_beside_previews_is_opened_as_it(tmp_path: Path) -> None:
    folder = SYNTH / "iso_miniature"
    lone = archive.lone_archive(folder)
    assert lone is not None and lone.suffix == ".zip"
    opened = archive.open_pack(folder, set())
    assert opened.kind == "zip" and opened.pack_id == "iso_miniature"
    assert (opened.root / "Isometric" / "floorWood_N.png").exists()
    pinned = archive.open_pack(folder, set(), "my_pack")
    assert pinned.pack_id == "my_pack"
    sniffed = pack_sniff.sniff(folder)
    assert sniffed.has_license is True and "view:isometric" in sniffed.marks


def test_a_folder_with_art_of_its_own_beside_an_archive_stays_a_folder(tmp_path: Path) -> None:
    def pack(name: str, *files: str) -> Path:
        root = tmp_path / name
        for rel in files:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith(".zip"):
                with zipfile.ZipFile(target, "w") as zf:
                    zf.writestr("a.txt", "a")
            else:
                Image.new("RGBA", (8, 8), (9, 9, 9, 255)).save(target)
        return root

    assert archive.lone_archive(pack("a", "pack.zip", "Preview.png", "Sample.png")) is not None
    assert archive.lone_archive(pack("b", "pack.zip", "Samples/shot.png")) is not None
    assert archive.lone_archive(pack("c", "pack.zip", "hero.png")) is None
    assert archive.lone_archive(pack("d", "pack.zip", "tiles/grass.png")) is None
    assert archive.lone_archive(pack("e", "one.zip", "two.zip")) is None
    assert archive.lone_archive(pack("f", "Preview.png")) is None
    assert archive.open_pack(pack("g", "pack.zip", "hero.png"), set()).kind == "folder"


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("Sample.png", classifier.UNUSED_GUIDE_PICTURE),
        ("Sample 2.png", classifier.UNUSED_GUIDE_PICTURE),
        ("Information.png", classifier.UNUSED_GUIDE_PICTURE),
        ("Samples/Tiled Sample_extracted/Sprites/crate_E.png", classifier.UNUSED_PREVIEW_FOLDER),
        ("sample/shot.png", classifier.UNUSED_PREVIEW_FOLDER),
        ("tiles/sample_tree.png", None),
        ("tiles/information_board.png", None),
    ],
)
def test_samples_and_information_are_previews(path: str, reason: str | None) -> None:
    assert classifier.not_game_art(path) == reason


# ---------------------------------------------------------------------------------- atlas


def test_the_sheet_beside_its_pictures_is_unused() -> None:
    cat, _issues = _catalog(SYNTH / "iso_tiles")
    sheet = _by_path(cat)["Spritesheet/isoTiles_sheet.png"]
    assert sheet.detected_by == "kenney_atlas" and sheet.status == "UNUSED"
    assert "unused_because:atlas_copy" in sheet.detected["tags"]
    assert "single pictures" in explain.why(sheet)
    assert cat.objects == []


def test_a_pack_with_only_the_sheet_is_read_through_its_list(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "sheet_only"
    sheet = Image.new("RGBA", (96, 48), (0, 0, 0, 0))
    entries = []
    for i, name in enumerate(("tree.png", "rock.png", "bush.png")):
        sheet.paste(tool.pal(i), (i * 32 + 4, 6, i * 32 + 28, 44))
        entries.append((name, i * 32, 0, 32, 48))
    _save(sheet, pack / "Spritesheet" / "things_sheet.png")
    (pack / "Spritesheet" / "things_sheet.xml").write_text(
        tool._texture_atlas("sheet.png", entries), encoding="utf-8"
    )
    cat, _issues = _catalog(pack)
    assert [(o.name, o.region) for o in sorted(cat.objects, key=lambda o: o.name)] == [
        ("bush", [64, 0, 32, 48]),
        ("rock", [32, 0, 32, 48]),
        ("tree", [0, 0, 32, 48]),
    ]
    asset = _by_path(cat)["Spritesheet/things_sheet.png"]
    assert asset.detected["role"] != "NONE" and all(o.sheet == asset.id for o in cat.objects)
    schema.validate("catalog", cat.to_json())


def test_reading_an_atlas_file(tool, tmp_path: Path) -> None:  # noqa: ANN001
    path = tmp_path / "a.xml"
    path.write_text(tool._texture_atlas("old name.png", [("a.png", 1, 2, 3, 4)]), encoding="utf-8")
    assert kenney_atlas.read_atlas(path) == ("old name.png", [("a.png", 1, 2, 3, 4)])
    path.write_text("<map/>", encoding="utf-8")
    with pytest.raises(ValueError, match="not a texture atlas"):
        kenney_atlas.read_atlas(path)
    path.write_text('<TextureAtlas><SubTexture name="a" x="1"/></TextureAtlas>', encoding="utf-8")
    with pytest.raises(ValueError, match="no rectangle"):
        kenney_atlas.read_atlas(path)
    path.write_text("<TextureAtlas", encoding="utf-8")
    with pytest.raises(ValueError):
        kenney_atlas.read_atlas(path)


# --------------------------------------------------------------------------------- objects


def test_a_tree_and_a_house_are_objects_on_one_diamond() -> None:
    cat, _issues = _catalog(SYNTH / "iso_tiles")
    assets = _by_path(cat)
    tree, house = assets["PNG/tree_01_0.png"].detected, assets["PNG/house_01_0.png"].detected
    for thing in (tree, house):
        assert thing["usage"] == "sprite" and thing["projection"] == "isometric"
        assert thing["stands_on"] == [1, 1] and thing["footprint"] == [60, 34]
        assert thing["origin"] == [30, 39], "the middle of the diamond, where the thing stands"
    assert tree["rise"] > house["rise"] > 0
    block = assets["PNG/isoTile_024_0.png"].detected
    assert block["usage"] == "iso_tile" and block["rise"] == 12, "a block is still a tile"
    assert assets["PNG/isoTile_001_0.png"].detected["rise"] == 0


def test_a_wide_thing_stands_on_several_diamonds(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_hall"
    _tiles(tool, pack, (40, 22), 4, (96, 64), count=3)
    (pack / "Tile information.txt").write_text("Tile size : 40 x 26 px\n", encoding="utf-8")
    _save(tool._iso_block((96, 64), (80, 44), 12, tool.pal(5)), pack / "PNG" / "hall.png")
    cat, _issues = _catalog(pack)
    hall = _by_path(cat)["PNG/hall.png"].detected
    assert hall["usage"] == "sprite" and hall["stands_on"] == [2, 2]


# ------------------------------------------------------------------------ what a game gets


def test_an_isometric_tile_fills_no_role_of_a_game_yet() -> None:
    cat, _issues = _catalog(SYNTH / "iso_tiles")
    ground = [a for a in cat.assets if a.detected.get("role") == "GROUND"]
    assert ground and all(catalog.is_iso_tile(a) for a in ground)
    assert cat.tilesets == [], "no tile set is made of them"
    assert mapping.best_for(cat, "GROUND") is None
    assert mapping.candidates(cat, "GROUND") == []
    assert not mapping.valid_selection(cat, "GROUND", ground[0].id)
    cfg = config.GeneratorConfig(project_name="x", packs=[])
    issues = requirements.check(cat, cfg)
    missing = [i for i in issues if i.code == "ASSET-010" and i.severity.value == "error"]
    assert "GROUND" in {i.detail["role"] for i in missing}
    assert not [i for i in issues if i.code == "TILE-011"]
    assert labels.usage_label("iso_tile") == "Isometric tile" and labels.usage_help("iso_tile")


def test_isometric_and_square_ground_in_one_project_is_tile_011() -> None:
    packs = []
    for source in (SYNTH / "iso_tiles", SYNTH / "basic16"):
        opened = archive.open_pack(source, {p[0].pack_id for p in packs})
        packs.append((opened, inventory.build_inventory(opened)))
    cat, _issues, _generated = catalog.assemble(packs, None, [], use_cache=False)
    mixed = requirements.mixed_ground(cat)
    assert mixed is not None and mixed.startswith("iso_tiles.")
    cfg = config.GeneratorConfig(project_name="x", packs=[])
    found = [i for i in requirements.check(cat, cfg) if i.code == "TILE-011"]
    assert len(found) == 1 and found[0].severity.value == "warning"
    assert mapping.best_for(cat, "GROUND") == "basic16.tiles.terrain"
    assert [t.name for t in cat.tilesets] == ["overworld"], "the square tile set is as it was"


# ------------------------------------------------------------------------------- the view


def _inv(*paths: str, pack_id: str = "") -> SimpleNamespace:
    return SimpleNamespace(files=[SimpleNamespace(path=p) for p in paths], pack_id=pack_id)


def test_the_pack_view_is_isometric() -> None:
    assert classifier.pack_view(_inv("PNG/a.png", pack_id="isometric_roads")) == "isometric"
    assert classifier.pack_view(_inv("Isometric/a.png")) == "isometric"
    assert classifier.pack_view(_inv("iso/a.png")) == "isometric"
    assert classifier.pack_view(_inv("PNG/a.png", pack_id="axonometric_blocks")) == "top"
    assert classifier.pack_view(_inv("tiles/isolated.png")) == "top"
    read = [{"usage": "iso_tile", "projection": "isometric"}]
    assert classifier.pack_view(_inv("a.png"), read) == "isometric"
    assert (
        classifier.pack_view(_inv("a.png", pack_id="isometric_x"), [{"usage": "sprite"}]) == "top"
    ), "with the pictures read, they say it"
    # a pack seen at an angle is not seen from the side, whatever its folders are called
    # (*Isometric Blocks* has a folder "Platformer tiles"); one that is not isometric still is
    assert classifier.made_for(_inv("Platformer Pack/a.png", pack_id="isometric_x")) == "top"
    assert classifier.made_for(_inv("Platformer Pack/a.png", pack_id="blocks_x")) == "side"


def test_the_sniff_marks_an_isometric_pack(tmp_path: Path) -> None:
    pack = tmp_path / "Isometric Roads"
    _save(Image.new("RGBA", (8, 8), (9, 9, 9, 255)), pack / "PNG" / "a.png")
    assert pack_sniff.sniff(pack).marks == ("view:isometric",)
    assert pack_sniff.sniff(SYNTH / "basic16").marks == ()


# ------------------------------------------------------------------------------ characters


def test_ne_nw_se_sw_are_the_diagonals_of_a_character(tmp_path: Path) -> None:
    for word, direction in (("ne", "up_right"), ("nw", "up_left"), ("se", "down_right"),
                            ("sw", "down_left")):  # fmt: skip
        assert naming.normalize_name(f"walk_{word}").name == f"walk_{direction}"
    pack = tmp_path / "people"
    for word in ("n", "ne", "e", "se", "s", "sw", "w", "nw"):
        for n in range(3):
            frame = Image.new("RGBA", (16, 24), (0, 0, 0, 0))
            frame.paste((60 + n * 30, 90, 200, 255), (4 + n, 4, 12, 23))
            _save(frame, pack / "hero" / f"hero_walk_{word}_{n + 1:02d}.png")
    cat, _issues = _catalog(pack)
    hero = next(a for a in cat.assets if a.detected.get("animations"))
    assert hero.detected["directions"] == 8
    assert sorted(hero.detected["animations"]) == sorted(
        f"walk_{d}" for d in (*naming.CARDINALS, *naming.DIAGONALS)
    )


# ----------------------------------------------------------------------- the synthetic packs


def test_the_iso_tiles_pack() -> None:
    cat, issues = _catalog(SYNTH / "iso_tiles")
    pack = cat.packs[0]
    assert _footprint(cat) == (60, 34, "tile_information"), "the words say 60 x 42, with the side"
    assert catalog.pack_view(pack) == "isometric"
    assert pack.adapters_matched == ["kenney_atlas", "isometric", "generic_grid"]
    tiles = [a for a in cat.assets if a.detected["usage"] == "iso_tile"]
    assert len(tiles) == 96 and {a.detected["role"] for a in tiles} == {"GROUND"}
    groups = catalog.colour_groups(cat)
    assert len(groups) == 26 and all(len(members) == 3 for members in groups.values())
    assert _by_path(cat)["Preview.png"].detected["role"] == "NONE"
    assert not [i for i in issues if i.severity.value in ("warning", "error")]
    expected = json.loads((SYNTH / "iso_tiles.expected.json").read_text(encoding="utf-8"))
    assert set(expected) <= set(_by_path(cat))


def test_the_iso_miniature_pack() -> None:
    cat, issues = _catalog(SYNTH / "iso_miniature")
    assert _footprint(cat) == (64, 32, "measured")
    assets = _by_path(cat)
    assert "Sample.png" not in assets, "the previews beside the archive are no part of the pack"
    car = next(a for a in cat.assets if a.detected.get("headings"))
    assert car.detected["headings"] == 8 and car.detected["role"] == "VEHICLE"
    assert assets["Cars/car_NED.png"].detected["tags"] == [
        "car", "slope:down", "unused_because:slope",
    ]  # fmt: skip
    corn = assets["Isometric/cornDouble_N.png"].detected
    assert corn["usage"] == "sprite" and "crop" in corn["tags"] and corn["stands_on"] == [1, 1]
    assert assets["Isometric/blockStone_S.png"].detected["rise"] == 20
    assert assets["Isometric/blockStone_S.png"].detected["turn"] == 2
    assert len(catalog.colour_groups(cat)) == 6
    assert not [i for i in issues if i.code in ("TILE-010", "ADAPT-001")]

"""What the real isometric packs taught after T17.20, on pictures drawn in their shapes: cars
whose files are numbered in no order, a pack whose flat pieces are roofs, wall segments along
one side of a diamond, the compass of a pack's names, a character in eight numbered facings,
the ground of an isometric map, and what an isometric pack is not taken for."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from rpggen import schema
from rpggen.core import archive, catalog, classifier, inventory, mapping
from rpggen.core.adapters import isometric, naming, sequences
from rpggen.core.analyzer import isometric as measure
from rpggen.core.analyzer import views

REPO = Path(__file__).resolve().parents[2]
CANVAS, FOOT, SIDE = (60, 64), (60, 34), 8
GRASS = (96, 160, 80, 255)
ASPHALT = (104, 104, 108, 255)
STONE = (190, 186, 170, 255)
SLOPES = (("NEU", 1, 1), ("NED", 1, -1), ("SWU", 5, 1), ("SWD", 5, -1))


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


def _save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _view(img: Image.Image) -> views.View:
    found = views.view(np.asarray(img.convert("RGBA"), dtype=np.uint8))
    assert found is not None
    return found


def _ground(tool, pack: Path, count: int = 6, face=None, stem: str = "plate") -> None:  # noqa: ANN001
    """Flat tiles turned four ways on the shared canvas, and the pack's own words."""
    (pack / "PNG").mkdir(parents=True, exist_ok=True)
    (pack / "Tile information.txt").write_text(
        f"\n\tImage size : {CANVAS[0]} x {CANVAS[1]} px\n"
        f"\tTile size  : {FOOT[0]} x {FOOT[1] + SIDE} px\n",
        encoding="utf-8",
    )
    for i in range(1, count + 1):
        for turn in range(4):
            block = tool._iso_block(CANVAS, FOOT, SIDE, face or tool.pal(i), turn=turn)
            _save(block, pack / "PNG" / f"{stem}_{i:02d}_{turn}.png")


# -------------------------------------------------------------------- which view a picture is


def test_two_cars_of_one_shape_are_alike_whatever_their_colour(tool) -> None:  # noqa: ANN001
    red = [_view(tool._iso_car(h, (214, 64, 60, 255))) for h in range(8)]
    black = [_view(tool._iso_car(h, (40, 40, 44, 255))) for h in range(8)]
    for heading in range(8):
        scores = [views.likeness(black[heading], other) for other in red]
        assert scores[heading] == max(scores) and scores[heading] > 0.7
    # the car seen from behind has the silhouette of the car seen from the front: the edges
    # inside it (its windscreen) tell them apart
    assert red[0].key() == red[4].key()
    assert views.likeness(red[0], red[4]) < views.likeness(red[0], red[0])
    order, alike = views.lay(list(reversed(black)), red)
    assert order == list(reversed(range(8))) and alike > 0.7


def test_every_row_takes_a_column_of_its_own() -> None:
    scores = np.array([[0.9, 0.8, 0.1], [0.9, 0.2, 0.1], [0.1, 0.2, 0.3]])
    assert views.assign(scores) == [1, 0, 2], "both would take the first: the sum decides"
    assert views.assign(np.eye(4)[::-1].copy()) == [3, 2, 1, 0]


def test_two_pictures_of_other_sizes_are_not_laid(tool) -> None:  # noqa: ANN001
    car = _view(tool._iso_car(2, (214, 64, 60, 255)))
    large = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(large).ellipse([2, 2, 60, 60], fill=(214, 64, 60, 255))
    assert views.likeness(car, _view(large)) == 0.0
    assert views.likeness(car, _view(large), None) > 0.0, "unless every size is asked for"


def _named_cars(tool, pack: Path, swapped: str = "") -> None:  # noqa: ANN001
    """Three cars whose names say their views, eight headings and four on a slope; the files
    of ``swapped``'s N and S are exchanged, as the taxi's are in the pack that was looked at."""
    colours = {
        "taxi": (236, 180, 60, 255),
        "police": (90, 130, 200, 255),
        "van": (232, 232, 236, 255),
    }
    for name, colour in colours.items():
        for heading, letter in enumerate(naming.COMPASS):
            shown = {0: 4, 4: 0}.get(heading, heading) if name == swapped else heading
            _save(tool._iso_car(shown, colour), pack / name.title() / f"{name}_{letter}.png")
        for letter, heading, slope in SLOPES:
            _save(tool._iso_car(heading, colour, slope=slope), pack / name.title() / f"{name}_{letter}.png")  # fmt: skip


def _numbered_car(tool, folder: Path, stem: str, colour, first: int) -> list[str]:  # noqa: ANN001
    """A car in the twelve views of the named ones as ``<stem>_000`` to ``_011``, beginning
    at another view in every folder. Returns the file of every heading, N first."""
    shown = [(h, 0) for h in range(8)] + [(h, s) for _l, h, s in SLOPES]
    shown = [shown[(i * 5 + first) % len(shown)] for i in range(len(shown))]  # no order at all
    files = {}
    for number, (heading, slope) in enumerate(shown):
        _save(tool._iso_car(heading, colour, slope=slope), folder / f"{stem}_{number:03d}.png")
        if not slope:
            files[heading] = f"{stem}_{number:03d}.png"
    return [files[heading] for heading in range(8)]


def test_a_car_with_numbered_views_is_read_from_the_cars_whose_names_say_them(
    tool,  # noqa: ANN001
    tmp_path: Path,
) -> None:
    pack = tmp_path / "isometric_vehicles"
    _named_cars(tool, pack)
    black = _numbered_car(tool, pack / "Civilian" / "Black" / "Sedan 1", "carBlack2", (40, 40, 44, 255), 0)  # fmt: skip
    red = _numbered_car(tool, pack / "Civilian" / "Red" / "Sedan 1", "carRed2", (214, 64, 60, 255), 7)  # fmt: skip
    assert [f[-7:] for f in black] != [f[-7:] for f in red], "the numbers begin elsewhere"
    cat, issues = _catalog(pack)
    assert not [i for i in issues if i.code.startswith(("TILE", "ADAPT"))]
    cars = {a.detected["heading_files"][0]: a for a in cat.assets if a.detected.get("headings")}
    assert len(cars) == 5
    for colour, files, stem in (("Black", black, "carBlack2"), ("Red", red, "carRed2")):
        car = cars[f"Civilian/{colour}/Sedan 1/{files[0]}"]
        facets = car.detected
        assert facets["headings"] == 8 and facets["role"] == "VEHICLE"
        assert facets["heading_files"] == [f"Civilian/{colour}/Sedan 1/{f}" for f in files]
        assert car.confidence >= catalog.AUTO_CONFIDENCE and car.status != "NEEDS_REVIEW"
        slopes = [
            a
            for a in cat.assets
            if stem in a.path and "unused_because:slope" in (a.detected.get("tags") or [])
        ]
        assert len(slopes) == len(SLOPES) and all(a.detected["role"] == "NONE" for a in slopes)
    # no picture of a car is left a picture to stand about a map
    assert not [a for a in cat.assets if a.detected.get("role") in ("DECORATION", "ITEM")]
    # the two colours of one model are one car in two colours, whatever their numbers
    first = cars[f"Civilian/Black/Sedan 1/{black[0]}"]
    second = cars[f"Civilian/Red/Sedan 1/{red[0]}"]
    assert catalog.colour_groups(cat) == {first.id: [second.id]}
    assert [catalog.colour_name(a) for a in (first, second)] == ["black", "red"]
    schema.validate("catalog", cat.to_json())


def test_a_view_the_pack_names_wrongly_takes_the_name_its_picture_has(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_vehicles"
    _named_cars(tool, pack, swapped="taxi")
    files = _numbered_car(tool, pack / "Civilian" / "Blue" / "Sedan 1", "carBlue2", (60, 90, 200, 255), 3)  # fmt: skip
    cat, _issues = _catalog(pack)
    cars = {a.detected["heading_files"][0]: a for a in cat.assets if a.detected.get("headings")}
    taxi = next(a for path, a in cars.items() if path.startswith("Taxi/"))
    assert taxi.detected["heading_files"][0] == "Taxi/taxi_S.png", "its S shows what N shows"
    assert taxi.detected["heading_files"][4] == "Taxi/taxi_N.png"
    police = next(a for path, a in cars.items() if path.startswith("Police/"))
    assert police.detected["heading_files"][0] == "Police/police_N.png"
    blue = cars[f"Civilian/Blue/Sedan 1/{files[0]}"]
    assert blue.detected["heading_files"] == [f"Civilian/Blue/Sedan 1/{f}" for f in files]
    assert blue.status != "NEEDS_REVIEW", "the named cars agree once the taxi is put right"


def test_two_named_cars_that_disagree_leave_a_numbered_one_for_review(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """With two named cars only nobody says which of them is wrong: the numbered car is read
    from the one it is most like and is marked for review."""
    pack = tmp_path / "isometric_vehicles"
    _named_cars(tool, pack, swapped="taxi")
    for f in (pack / "Van").iterdir():
        f.unlink()
    _numbered_car(tool, pack / "Civilian" / "Blue" / "Sedan 1", "carBlue2", (60, 90, 200, 255), 3)
    cat, _issues = _catalog(pack)
    blue = next(a for a in cat.assets if "carBlue2" in str(a.detected.get("heading_files")))
    assert blue.detected["headings"] == 8 and blue.status == "NEEDS_REVIEW"


def test_numbered_views_like_no_named_car_stay_unread_with_the_reason(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_vehicles"
    _named_cars(tool, pack)
    for number in range(12):
        blob = Image.new("RGBA", (40 + number, 40), (0, 0, 0, 0))
        ImageDraw.Draw(blob).ellipse([1, 1, 38 + number, 38], fill=(90, 90, 200, 255))
        _save(blob, pack / "Civilian" / "Blue" / "Truck 1" / f"carBlue6_{number:03d}.png")
    cat, _issues = _catalog(pack)
    blobs = [a for a in cat.assets if "carBlue6" in a.path]
    assert len(blobs) == 12
    for asset in blobs:
        assert asset.detected["role"] == "NONE" and asset.status == "UNUSED"
        assert "unused_because:" + isometric.UNUSED_VIEWS in asset.detected["tags"]


def test_numbered_pictures_without_a_named_car_are_left_alone(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_vehicles"
    _numbered_car(tool, pack / "Civilian" / "Blue" / "Sedan 1", "carBlue2", (60, 90, 200, 255), 3)
    cat, _issues = _catalog(pack)
    assert not [a for a in cat.assets if a.detected.get("headings")]
    assert not [a for a in cat.assets if isometric.UNUSED_VIEWS in str(a.detected.get("tags"))]


# ------------------------------------------------------------ the diamond of a pack of houses


def _house(tool, colour) -> Image.Image:  # noqa: ANN001
    """A ground floor on its block of ground: the block as wide as the picture, the house
    three quarters of it, as the wide pieces of *Tiles Buildings* are."""
    canvas, foot = (64, 84), (64, 32)
    img = tool._iso_block(canvas, foot, 12, STONE)
    small = (48, 24)
    lift = 12 + (foot[1] - small[1]) // 2
    house = tool._iso_block(canvas, small, 22, colour, bottom=lift)
    img.alpha_composite(house)
    return img


def test_the_ground_of_a_pack_is_its_widest_block_not_its_flat_roofs(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_buildings"
    for i in range(10):  # roofs and upper storeys: flat, and narrower than the ground
        slab = tool._iso_block((48, 28 + (i % 3)), (48, 24), 3 + (i % 3), tool.pal(i))
        _save(slab, pack / "PNG" / f"buildingTiles_{i:03d}.png")
    for i in range(10, 18):
        _save(_house(tool, tool.pal(i)), pack / "PNG" / f"buildingTiles_{i:03d}.png")
    cat, issues = _catalog(pack)
    assert not [i for i in issues if i.code.startswith("TILE")]
    assert catalog.isometric_footprint(cat.packs[0]) == (64, 32, "measured")
    assets = _by_path(cat)
    house = assets["PNG/buildingTiles_012.png"].detected
    assert house["usage"] == "iso_tile" and house["footprint"] == [64, 32] and house["rise"] > 0
    roof = assets["PNG/buildingTiles_003.png"].detected
    assert roof["usage"] == "sprite" and roof["stands_on"] == [1, 1]
    assert roof["role"] == "DECORATION", "what fills no diamond is not what a map is laid with"


def test_a_pack_of_flat_tiles_keeps_their_width(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """Two wider pictures are no ground: a fair share of the pack must stand on the block."""
    pack = tmp_path / "isometric_buildings"
    for i in range(12):
        slab = tool._iso_block((48, 28), (48, 24), 4, tool.pal(i))
        _save(slab, pack / "PNG" / f"buildingTiles_{i:03d}.png")
    for i in range(12, 14):
        _save(_house(tool, tool.pal(i)), pack / "PNG" / f"buildingTiles_{i:03d}.png")
    cat, _issues = _catalog(pack)
    assert catalog.isometric_footprint(cat.packs[0]) == (48, 24, "measured")


def test_the_foot_of_a_block_is_measured_whatever_stands_on_it(tool) -> None:  # noqa: ANN001
    mask = measure.painted(np.asarray(_house(tool, tool.pal(1)), dtype=np.uint8))
    foot = measure.block_base(mask)
    assert foot is not None and foot.width == 64 and abs(foot.slope - 0.5) < 0.03
    assert 12 <= foot.side <= 14, "the rows of the block's side, within a row or two"
    tree = measure.painted(np.asarray(tool._iso_tree(CANVAS, FOOT, SIDE), dtype=np.uint8))
    assert measure.block_base(tree) is None


# ---------------------------------------------------------------- a piece along one side


def _corners() -> dict[str, tuple[int, int]]:
    """The corners of the diamond of the shared canvas, at the foot of its block."""
    top = CANVAS[1] - SIDE - FOOT[1] + SIDE
    cx, cy = CANVAS[0] // 2, top + FOOT[1] // 2
    return {
        "top": (cx, top),
        "right": (CANVAS[0] - 1, cy),
        "bottom": (cx, top + FOOT[1] - 1),
        "left": (0, cy),
    }


EDGE_ENDS = {"n": ("top", "right"), "e": ("right", "bottom"), "s": ("bottom", "left"), "w": ("left", "top")}  # fmt: skip


def _wall(side: str, height: int = 22, opening: str = "") -> Image.Image:
    """A thin wall along one side of the diamond, as high as a storey; with a doorway (a gap
    at its foot) or a window (a hole) when asked."""
    corners = _corners()
    (ax, ay), (bx, by) = (corners[name] for name in EDGE_ENDS[side])
    img = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(ax, ay), (bx, by), (bx, by - height), (ax, ay - height)], fill=STONE)
    mx, my = (ax + bx) // 2, (ay + by) // 2
    if opening == "door":
        draw.rectangle([mx - 4, my - 14, mx + 4, my + 6], fill=(0, 0, 0, 0))
    elif opening == "window":
        draw.rectangle([mx - 3, my - 16, mx + 3, my - 9], fill=(0, 0, 0, 0))
    return img


@pytest.fixture
def town(tool, tmp_path: Path) -> Path:  # noqa: ANN001
    """In the manner of *Medieval Town*: plates, wall segments turned four ways (turn 0 on the
    upper right side), walls with a window and with a door, a roof, a post and a tree."""
    pack = tmp_path / "isometric_town"
    _ground(tool, pack)
    for turn, side in enumerate(measure.EDGE_SIDES):
        _save(_wall(side), pack / "PNG" / f"grey_wall_01_{turn}.png")
        _save(_wall(side, 10), pack / "PNG" / f"castle_wall_01_{turn}.png")
        _save(_wall(side, opening="window"), pack / "PNG" / f"wood_window_square_01_{turn}.png")
        _save(_wall(side, opening="door"), pack / "PNG" / f"grey_door_round_01_{turn}.png")
        roof = tool._iso_block(CANVAS, FOOT, SIDE + 14, (176, 70, 58, 255), turn=turn)
        _save(roof, pack / "PNG" / f"roof_point_red_01_{turn}.png")
        _save(tool._iso_tree(CANVAS, FOOT, SIDE), pack / "PNG" / f"tree_01_{turn}.png")
        post = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        x, y = list(_corners().values())[turn]
        ImageDraw.Draw(post).rectangle([max(0, x - 2), y - 20, min(CANVAS[0] - 1, x + 2), y], fill=STONE)  # fmt: skip
        _save(post, pack / "PNG" / f"grey_pole_01_{turn}.png")
    return pack


def test_a_wall_segment_is_a_tile_along_one_side_of_its_diamond(town: Path) -> None:
    cat, issues = _catalog(town)
    assert not [i for i in issues if i.code.startswith("TILE")]
    assets = _by_path(cat)
    for turn, side in enumerate(measure.EDGE_SIDES):
        for stem in ("grey_wall_01", "castle_wall_01", "wood_window_square_01", "grey_door_round_01"):  # fmt: skip
            facets = assets[f"PNG/{stem}_{turn}.png"].detected
            assert facets["usage"] == "iso_tile", stem
            assert facets["edge"] == side and facets["turn"] == turn, (stem, turn)
            assert facets["role"] == "WALL", "a wall with a window is no window of a menu"
            assert "stands_on" not in facets
        assert "window" in assets[f"PNG/wood_window_square_01_{turn}.png"].detected["tags"]
        assert "door" in assets[f"PNG/grey_door_round_01_{turn}.png"].detected["tags"]
        assert "door" not in (assets[f"PNG/grey_wall_01_{turn}.png"].detected.get("tags") or [])
        tree = assets[f"PNG/tree_01_{turn}.png"].detected
        assert "edge" not in tree and tree["usage"] == "sprite"
        # a post on a corner of its diamond is a tile of its own, no wall (after T17.30)
        post = assets[f"PNG/grey_pole_01_{turn}.png"].detected
        assert "edge" not in post and post["usage"] == "iso_tile" and post["role"] == "DECORATION"
        assert post["post"] in ("nw", "ne", "es", "sw") and "post" in post["tags"]
        roof = assets[f"PNG/roof_point_red_01_{turn}.png"].detected
        assert roof["usage"] == "iso_tile" and "edge" not in roof
        assert "roof" in roof["tags"] and roof["role"] == "DECORATION"
        plate = assets[f"PNG/plate_01_{turn}.png"].detected
        assert plate["usage"] == "iso_tile" and "edge" not in plate
    schema.validate("catalog", cat.to_json())


def test_the_side_is_measured_and_not_taken_from_the_turn(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """The miniature packs name the piece on the upper right side ``_S``: the letter is not
    the side."""
    pack = tmp_path / "isometric_farm"
    _ground(tool, pack)
    for letter, side in (("S", "n"), ("W", "e"), ("N", "s"), ("E", "w")):
        _save(_wall(side), pack / "PNG" / f"woodWall_{letter}.png")
        _save(_wall(side, 8), pack / "PNG" / f"fenceLow_{letter}.png")
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    for letter, side in (("S", "n"), ("W", "e"), ("N", "s"), ("E", "w")):
        for stem in ("woodWall", "fenceLow"):
            facets = assets[f"PNG/{stem}_{letter}.png"].detected
            assert facets["edge"] == side and facets["role"] == "WALL"


def test_a_set_of_which_one_turn_lies_along_a_side_is_no_set_of_walls(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_town"
    _ground(tool, pack)
    _save(_wall("e"), pack / "PNG" / "roof_corner_red_01_1.png")
    for turn in (0, 2, 3):
        _save(tool._iso_tree(CANVAS, FOOT, SIDE), pack / "PNG" / f"roof_corner_red_01_{turn}.png")
    _save(_wall("s"), pack / "PNG" / "hedge.png")
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    for turn in range(4):
        facets = assets[f"PNG/roof_corner_red_01_{turn}.png"].detected
        assert "edge" not in facets and facets["usage"] == "sprite"
    assert assets["PNG/hedge.png"].detected["edge"] == "s", "a piece that is not turned is read"


def test_the_foot_of_a_piece_says_its_side() -> None:
    corners = _corners()
    middle = (CANVAS[0] // 2, corners["top"][1] + FOOT[1] // 2)
    for side in measure.EDGE_SIDES:
        mask = np.asarray(_wall(side))[..., 3] >= 128
        box, _top, low = measure.outline(mask)
        got = measure.edge_side(box[0] + np.arange(box[2]), box[1] + low, middle, FOOT)
        assert got == side
    assert measure.turned_sides(["n", "e"], 1) == ["e", "s"]
    assert measure.turned_sides(["n", "s"], 3) == ["e", "w"]


# ------------------------------------------------------------- the compass of a pack's names


def _road(tool, sides: str) -> Image.Image:  # noqa: ANN001
    """A flat tile of verge with a road from its middle out to the grid's ``sides``."""
    img = tool._iso_block((60, 42), FOOT, SIDE, GRASS)
    face = np.asarray(img)[..., :3] == np.array(GRASS[:3])
    drawn = img.copy()
    cx, cy = 30, FOOT[1] // 2
    ends = {"n": (15, -9), "e": (15, 9), "s": (-15, 9), "w": (-15, -9)}
    draw = ImageDraw.Draw(drawn)
    for side in sides:
        dx, dy = ends[side]
        draw.line([(cx, cy), (cx + dx * 2, cy + dy * 2)], fill=ASPHALT, width=9)
    draw.ellipse([cx - 5, cy - 4, cx + 5, cy + 4], fill=ASPHALT)
    out = np.asarray(img).copy()
    keep = face.all(axis=-1)
    out[keep] = np.asarray(drawn)[keep]
    return Image.fromarray(out)


ROADS = ("NS", "EW", "ES", "NE", "SW", "NW", "NES", "ESW")


@pytest.mark.parametrize(
    ("north", "quarters"),
    [("n", 0), ("w", 3), ("e", 1)],  # as the grid has it; the upper left (*Vector Roads*); ...
)
def test_where_the_north_of_a_packs_names_is_the_pictures_say(
    tool,  # noqa: ANN001
    tmp_path: Path,
    north: str,
    quarters: int,
) -> None:
    pack = tmp_path / "isometric_roads"
    _save(_road(tool, "nesw"), pack / "PNG" / "road.png")
    for letters in ROADS:
        painted = measure.turned_sides(list(letters.lower()), quarters)
        _save(_road(tool, "".join(painted)), pack / "PNG" / f"road{letters}.png")
    for i in range(4):
        _save(tool._iso_block((60, 42), FOOT, SIDE, tool.pal(i)), pack / "PNG" / f"plain{i}.png")
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    assert measure.turned_sides(["n"], quarters) == [north]
    for letters in ROADS:
        want = measure.turned_sides(list(letters.lower()), quarters)
        assert assets[f"PNG/road{letters}.png"].detected["joins"] == want, letters


def test_the_sides_a_surface_runs_out_on(tool) -> None:  # noqa: ANN001
    rgba = np.asarray(_road(tool, "ns"), dtype=np.uint8)
    middle = (30.0, FOOT[1] / 2.0)
    assert measure.open_sides(rgba, middle, FOOT) == ["n", "s"]
    assert measure.open_sides(np.asarray(_road(tool, "esw"), dtype=np.uint8), middle, FOOT) == [
        "e",
        "s",
        "w",
    ]


# ------------------------------------------------------- a character in eight numbered facings


def _person(facing: int, step: int = 0, order=sequences.FACINGS) -> Image.Image:  # noqa: ANN001
    """A figure looking one of eight ways: a body, and a head and a hand towards where it
    looks. A figure seen in a mirror is the figure that looks the other way across."""
    vectors = {
        "up": (0, -1), "up_right": (1, -1), "right": (1, 0), "down_right": (1, 1),
        "down": (0, 1), "down_left": (-1, 1), "left": (-1, 0), "up_left": (-1, -1),
    }  # fmt: skip
    dx, dy = vectors[order[facing]]
    img = Image.new("RGBA", (48, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 26, 27, 50 + step], fill=(150, 90, 60, 255))
    draw.ellipse([19 + dx * 3, 14 + dy * 2, 28 + dx * 3, 23 + dy * 2], fill=(224, 180, 150, 255))
    draw.rectangle([23 + dx * 8, 34 + dy * 4, 25 + dx * 8, 37 + dy * 4], fill=(224, 180, 150, 255))
    return img


def _people(pack: Path, order=sequences.FACINGS, name: str = "Male") -> None:  # noqa: ANN001
    folder = pack / "Characters" / name
    for facing in range(8):
        _save(_person(facing, 0, order), folder / f"{name}_{facing}_Idle0.png")
        for frame in range(3):
            _save(_person(facing, frame, order), folder / f"{name}_{facing}_Run{frame}.png")
        for frame in range(2):
            _save(_person(facing, 3 + frame, order), folder / f"{name}_{facing}_Pickup{frame}.png")


def test_a_character_in_eight_numbered_facings_is_one_sprite(tool, tmp_path: Path) -> None:  # noqa: ANN001
    pack = tmp_path / "isometric_dungeon"
    _ground(tool, pack)
    _people(pack)
    opened = archive.open_pack(pack, set())
    cat, issues, generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    assert not [i for i in issues if i.code.startswith("ADAPT")]
    people = [a for a in cat.assets if a.detected.get("animations")]
    assert len(people) == 1 and not [a for a in cat.assets if "Characters" in a.path and a is not people[0]]  # fmt: skip
    facets = people[0].detected
    assert facets["directions"] == 8 and facets["role"] in ("PLAYER", "NPC")
    assert facets["usage"] == "sprite" and facets["frame"] == [48, 64]
    assert "projection" not in facets
    names = {f"{a}_{d}" for a in ("idle", "walk", "pickup") for d in naming.DIRECTIONS}
    assert set(facets["animations"]) == names, "a run is the walk; all eight directions"
    walk = facets["animations"]["walk_down"]
    assert len(walk["frames"]) == 3 and walk["loop"] is True
    assert facets["animations"]["pickup_left"]["loop"] is False
    assert facets["animations"]["idle_up"]["loop"] is True
    # facing 3 looks at the camera, 7 away from it, 1 to the right and 5 to the left
    for direction, facing in (("down", 3), ("up", 7), ("right", 1), ("left", 5), ("up_right", 0)):
        with Image.open(generated[facets["animations"][f"walk_{direction}"]["source"]]) as strip:
            first = strip.crop((0, 0, 48, 64))
            assert np.array_equal(np.asarray(first), np.asarray(_person(facing, 0))), direction
    schema.validate("catalog", cat.to_json())


def test_the_facings_are_checked_against_the_pictures(tmp_path: Path) -> None:
    pack = tmp_path / "isometric_dungeon"
    _people(pack)
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    (found,) = sequences.find_facings(inv, set())
    assert found.name == "Male" and sorted(found.actions) == ["Idle", "Pickup", "Run"]
    assert sequences.facings_mirror(opened.root, found) is True
    # the same figures numbered from another facing do not mirror as the numbers say
    other = tmp_path / "isometric_other"
    turned = sequences.FACINGS[1:] + sequences.FACINGS[:1]
    _people(other, turned)
    opened = archive.open_pack(other, set())
    inv = inventory.build_inventory(opened)
    (found,) = sequences.find_facings(inv, set())
    assert sequences.facings_mirror(opened.root, found) is False
    cat, _issues = _catalog(other)
    person = next(a for a in cat.assets if a.detected.get("animations"))
    assert person.status == "NEEDS_REVIEW" and person.confidence <= 0.5


def _inv(*paths: str, pack_id: str = "") -> SimpleNamespace:
    return SimpleNamespace(pack_id=pack_id, files=[SimpleNamespace(path=p) for p in paths])


def test_names_that_are_no_character_in_facings() -> None:
    def stills(*paths: str) -> SimpleNamespace:
        files = [
            SimpleNamespace(path=p, kind="image", image={"w": 8, "h": 8}, ext=".png") for p in paths
        ]
        return SimpleNamespace(pack_id="x", files=files)

    seven = [f"Male_{k}_Run{n}.png" for k in range(7) for n in range(2)]
    assert not sequences.find_facings(stills(*seven), set()), "a facing is missing"
    things = [f"tile_{k}_a{n}.png" for k in range(8) for n in range(2)]
    assert not sequences.find_facings(stills(*things), set()), "no word for what a person does"
    uneven = [f"Male_{k}_Run{n}.png" for k in range(8) for n in range(2 + (k == 3))]
    assert not sequences.find_facings(stills(*uneven), set())
    whole = [f"Male_{k}_Run{n}.png" for k in range(8) for n in range(2)]
    assert len(sequences.find_facings(stills(*whole), set())) == 1


# ------------------------------------------------------------- the ground of an isometric map


def test_the_ground_of_an_isometric_map_is_a_meadow_before_a_paving(tool, tmp_path: Path) -> None:  # noqa: ANN001
    """The first ground tile by name is a paving; the plain green one is the meadow, though
    no name says so (*Nature* calls it ``naturePack_001``)."""
    pack = tmp_path / "isometric_town"
    _ground(tool, pack, count=4, face=STONE, stem="aaa_plate")
    for turn in range(4):
        paving = tool._iso_block(CANVAS, FOOT, SIDE, STONE)
        ImageDraw.Draw(paving).line([(14, 38), (46, 38)], fill=(120, 116, 104, 255), width=3)
        _save(paving, pack / "PNG" / f"aaa_slabs_01_{turn}.png")
        _save(tool._iso_block(CANVAS, FOOT, SIDE, GRASS), pack / "PNG" / f"naturePack_001_{turn}.png")  # fmt: skip
        raised = tool._iso_block(CANVAS, FOOT, SIDE + 12, GRASS)
        _save(raised, pack / "PNG" / f"aaa_block_01_{turn}.png")
    cat, _issues = _catalog(pack)
    assets = _by_path(cat)
    meadow = assets["PNG/naturePack_001_0.png"]
    assert "surface:grass" in meadow.detected["tags"]
    for other in ("aaa_plate_01", "aaa_slabs_01", "aaa_block_01"):
        assert "surface:grass" not in (assets[f"PNG/{other}_0.png"].detected.get("tags") or [])
    assert [mapping.open_ground_rank(assets[f"PNG/{name}_0.png"]) for name in ("naturePack_001", "aaa_plate_01", "aaa_slabs_01", "aaa_block_01")] == [0, 2, 2, 3]  # fmt: skip
    assert mapping.best_for(cat, "GROUND", "isometric") == meadow.id
    without = catalog.Catalog.from_json(cat.to_json())
    without.assets = [a for a in without.assets if "naturePack" not in a.path]
    assert mapping.best_for(without, "GROUND", "isometric") == assets["PNG/aaa_plate_01_0.png"].id


def test_the_colour_of_a_face() -> None:
    def face(colour, mark=None) -> str | None:  # noqa: ANN001
        img = Image.new("RGBA", (64, 32), colour)
        if mark:
            ImageDraw.Draw(img).rectangle([20, 10, 44, 22], fill=mark)
        return measure.face_colour(np.asarray(img, dtype=np.uint8), (32.0, 16.0), (64, 32))

    assert face(GRASS) == "grass"
    assert face((137, 180, 72, 255)) == "grass" and face((100, 140, 120, 255)) == "grass"
    assert face(STONE) == "plain" and face((186, 140, 93, 255)) == "plain"
    assert face((156, 212, 226, 255)) is None, "the blue of water is nobody's meadow"
    assert face(GRASS, ASPHALT) is None, "a road is drawn on it"


# ------------------------------------------------------- what an isometric pack is not taken for


def test_one_thing_turned_four_ways_is_one_name_of_an_isometric_pack() -> None:
    road = [f"PNG/plate_road_01_{turn}.png" for turn in range(4)]
    beam = [f"PNG/woodenSupportsBeam_{letter}.png" for letter in "NESW"]
    plates = [f"PNG/plate_{i:02d}_0.png" for i in range(6)]
    tile = [{"usage": "iso_tile", "projection": "isometric"}]
    assert classifier.made_for(_inv(*road, *plates, pack_id="isometric_medieval_town"), tile) == "top"  # fmt: skip
    assert classifier.made_for(_inv(*beam, *plates, pack_id="isometric_dungeon"), tile) == "top"
    # the same names in a pack seen from above are four names, as they were
    assert classifier.made_for(_inv(*road, *plates, pack_id="medieval_town")) == "racing"
    assert classifier.made_for(_inv(*beam, *plates, pack_id="dungeon")) == "shmup"
    # a pack of roads is still one: three road pieces, each turned four ways
    roads = [f"PNG/roadTile_{i:03d}_{turn}.png" for i in range(3) for turn in range(4)]
    assert classifier.made_for(_inv(*roads, pack_id="isometric_roads"), tile) == "racing"
    cars = [{"usage": "sprite", "projection": "isometric", "headings": 8}]
    assert classifier.made_for(_inv("PNG/car_N.png", "PNG/car_S.png", pack_id="isometric_vehicles"), cars) == "racing"  # fmt: skip


def test_an_isometric_pack_is_not_seen_from_the_side() -> None:
    files = [f"PNG/Platformer tiles/platformerTile_{i:02d}.png" for i in range(12)]
    tile = [{"usage": "iso_tile", "projection": "isometric"}]
    assert classifier.made_for(_inv(*files, pack_id="isometric_blocks"), tile) == "top"
    assert classifier.made_for(_inv(*files, pack_id="blocks")) == "side"


def test_silver_is_a_colour() -> None:
    assert classifier.colour_key("Civilian/Silver/Sedan 1/car.png") == ("civilian/sedan 1/car", "silver")  # fmt: skip
    assert catalog._headings_name("Black/Sedan 1/carBlack2_003.png") == "Black/Sedan 1/car_Black2"
    assert catalog._headings_name("Taxi/taxi_N.png") == "Taxi/taxi_N.png"
    assert math.isclose(isometric.VIEWS_LIKENESS_MIN, 0.6)

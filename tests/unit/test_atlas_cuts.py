"""T17.34: sheets a cutting tool cut into named pictures (``_atlas.json``), read back as the
sheets they are (``atlas_cuts``): a sheet of outlined blocks out of its outlines into a
generated copy that joins, the cells' names saying what the pixels cannot, strips of frames
animated, and a stage set seen from the side because its collection says so."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, atlas_cuts, catalog, classifier, inventory, side_tiles

CELL = 16
EARTH = (110, 78, 52, 255)
GRASS = (96, 150, 60, 255)
OUTLINE = (12, 10, 8, 255)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _block(top: int, colour: tuple[int, int, int, int], grass: bool = False) -> np.ndarray:
    """A tile drawn as a block of its own: a see-through margin of 1 px and a dark outline of
    1 px round art that starts `top` px down (the sky above a surface)."""
    cell = np.zeros((CELL, CELL, 4), np.uint8)
    cell[top:, 1 : CELL - 1] = OUTLINE
    cell[top + 1 : CELL - 1, 2 : CELL - 2] = colour
    if grass:
        cell[top + 1 : top + 4, 2 : CELL - 2] = GRASS
    return cell


def _shape(rows: slice, cols: slice, colour: tuple[int, int, int, int]) -> np.ndarray:
    cell = np.zeros((CELL, CELL, 4), np.uint8)
    cell[rows, cols] = OUTLINE
    inner_rows = slice(rows.start + 1, rows.stop - 1)
    inner_cols = slice(cols.start + 1, cols.stop - 1)
    cell[inner_rows, inner_cols] = colour
    return cell


LAYOUT = {
    (0, 0): ("dirt_fill", _block(0, EARTH)),
    (1, 0): ("dirt_fill_2", _block(0, EARTH)),
    (2, 0): ("grass_ground", _block(4, EARTH, grass=True)),
    (3, 0): ("grass_ground_b", _block(4, EARTH, grass=True)),
    (0, 1): ("red_mushroom", _shape(slice(8, 15), slice(5, 11), (190, 40, 40, 255))),
    (1, 1): ("fallen_log", _shape(slice(10, 16), slice(2, 14), (120, 90, 50, 255))),
    (2, 1): ("thorn_patch", _shape(slice(9, 16), slice(3, 13), (90, 110, 60, 255))),
}


def _pack(tmp_path: Path) -> Path:
    """A stage set of a collection called *sidescroller*, its ground sheet cut into pictures."""
    stage = tmp_path / "my sidescroller collection" / "Stages" / "Forest"
    pieces = stage / "1. Ground"
    pieces.mkdir(parents=True)
    sheet = np.zeros((2 * CELL, 4 * CELL, 4), np.uint8)
    sprites = []
    for (x, y), (name, cell) in LAYOUT.items():
        sheet[y * CELL : (y + 1) * CELL, x * CELL : (x + 1) * CELL] = cell
        Image.fromarray(cell).save(pieces / f"{name}.png")
        sprites.append({"name": name, "file": f"{name}.png", "x": x * CELL, "y": y * CELL,
                        "w": CELL, "h": CELL})  # fmt: skip
    Image.fromarray(sheet).save(stage / "1. Ground.png")
    manifest = {"source": "1. Ground.png", "cell": CELL, "sprites": sprites}
    (pieces / "_atlas.json").write_text(json.dumps(manifest), encoding="utf-8")
    # a strip of frames cut one picture a frame
    frames = stage / "Bees"
    frames.mkdir()
    strip = np.zeros((8, 32, 4), np.uint8)
    strip[2:6, :, :] = (230, 200, 40, 255)
    Image.fromarray(strip).save(stage / "bees 8x8.png")
    cut = []
    for i in range(4):
        Image.fromarray(strip[:, i * 8 : (i + 1) * 8].copy()).save(
            frames / f"bees_frame{i + 1:02d}.png"
        )
        cut.append({"name": f"bees_frame{i + 1:02d}", "file": f"bees_frame{i + 1:02d}.png",
                    "x": i * 8, "y": 0, "w": 8, "h": 8})  # fmt: skip
    (frames / "_atlas.json").write_text(
        json.dumps({"source": "bees 8x8.png", "frame": [8, 8], "sprites": cut}), encoding="utf-8"
    )
    return stage


def _assemble(stage: Path, tmp_path: Path) -> catalog.Catalog:
    opened = archive.open_pack(stage, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inv)], None, [], work_dir=tmp_path / "work"
    )
    return cat


# ------------------------------------------------------------------ outlines


def test_a_block_loses_its_outline_on_the_sides_its_art_fills() -> None:
    fill = _block(0, EARTH)
    assert atlas_cuts.joins(fill) == set("NESW")
    surface = _block(4, EARTH, grass=True)
    assert atlas_cuts.joins(surface) == set("ESW"), "the sky above a surface joins nothing"
    assert atlas_cuts.outlined([fill, surface])
    fixed = atlas_cuts.deoutline(fill, set("NESW"))
    assert (fixed[:, :, 3] == 255).all(), "no see-through margin left"
    assert fixed[:, :, :3].max(axis=2).min() > 40, "and no dark line"
    # two side by side: no dark column where they meet
    row = np.concatenate([fixed, fixed], axis=1)
    assert row[4:12, CELL - 1 : CELL + 1, :3].max(axis=2).min() > 40
    # a surface keeps its top outline: the ground's silhouette
    top = atlas_cuts.deoutline(surface, set("ESW"))
    assert (top[4, 4:12, :3] == OUTLINE[:3]).all()
    assert (top[:4, :, 3] == 0).all(), "the sky stays sky"


def test_a_sheet_of_tiles_that_join_is_no_sheet_of_blocks() -> None:
    """GandalfHardcore's sheets: the ground runs on from cell to cell, no margin inside it."""
    plain = np.zeros((CELL, CELL, 4), np.uint8)
    plain[:, :] = EARTH
    surface = plain.copy()
    surface[:4] = 0
    surface[4] = OUTLINE  # a dark line along the top of the ground is no block's outline
    assert not atlas_cuts.outlined([plain, plain, surface])
    assert atlas_cuts.deoutline(plain, set()).tobytes() == plain.tobytes()


def test_a_block_with_a_margin_and_no_outline_is_a_block() -> None:
    """*Medievil Kingdom*'s bricks: a see-through margin of 1 px round them, no dark line."""
    brick = np.zeros((CELL, CELL, 4), np.uint8)
    brick[1 : CELL - 1, 1 : CELL - 1] = (140, 137, 129, 255)
    assert atlas_cuts.outlined([brick, brick])
    fixed = atlas_cuts.deoutline(brick, set("NESW"))
    assert (fixed[:, :, 3] == 255).all()


def test_blocks_that_join_no_seam_make_a_terrain_by_their_names() -> None:
    """Variants drawn each on its own: a fill of speckled earth and a grass top on plain earth
    whose seams the reader cannot match. Their names say ground, the sides they fill say how
    they join."""
    rng = np.random.default_rng(3)
    fill = np.zeros((CELL, CELL, 4), np.uint8)
    fill[:, :] = EARTH
    fill[:, :, :3] = np.clip(fill[:, :, :3] + rng.integers(-30, 30, (CELL, CELL, 3)), 0, 255)
    top = np.zeros((CELL, CELL, 4), np.uint8)
    top[4:] = (150, 100, 60, 255)
    top[4:7] = GRASS
    loose = np.zeros((CELL, CELL, 4), np.uint8)
    loose[10:] = EARTH
    loose[:, :2] = 0
    pictures = {"dirt_fill": fill, "grass_ground": top, "pebbles": loose}
    keys = {"0,0": "dirt_fill", "1,0": "grass_ground", "2,0": "pebbles"}
    joined = {name: atlas_cuts.joins(p) for name, p in pictures.items()}
    read = side_tiles.SheetRead(cell=(CELL, CELL))
    sheet = np.concatenate([fill, top, loose], axis=1)
    atlas_cuts.named_terrains(pictures, joined, keys, read, sheet, CELL)
    ((surface, members),) = read.terrains
    assert surface == "grass"
    assert members == {"0,0": side_tiles.ALL, "1,0": side_tiles.E | side_tiles.S | side_tiles.W}


def test_what_a_cells_name_says() -> None:
    assert atlas_cuts.mds_kind("green_mushroom_cluster") == "mushroom"
    assert atlas_cuts.mds_kind("hanging_vines_thin_a") == "hanging_moss"
    assert atlas_cuts.mds_kind("giant_stalactite") == "stalactite_large"
    assert atlas_cuts.mds_kind("ferns_and_flowers") == "", "a mix says no kind"
    blank = np.zeros((CELL, CELL, 4), np.uint8)
    assert atlas_cuts.named_override("mossy_ledge_mid", blank, set(), CELL)["collision"] == {
        "profile": "ONE_WAY"
    }
    assert atlas_cuts.named_override("thorn_bush", blank, set(), CELL)["custom"] == {"hazard": True}
    assert atlas_cuts.named_override("stone_brick", blank, set("NESW"), CELL)["collision"] == {
        "profile": "FULL"
    }
    assert atlas_cuts.named_override("stone_brick", blank, {"S"}, CELL) == {}, "a loose brick"
    assert atlas_cuts.named_override("campfire", blank, set(), CELL) == {}
    assert atlas_cuts.named_override("rope_ladder", blank, set(), CELL)["custom"] == {
        "ladder": True
    }
    assert atlas_cuts.named_override("treehouse_ladder", blank, set(), CELL) == {}, (
        "a treehouse with its ladder is a thing to place"
    )


def test_dark_rock_is_no_water() -> None:
    """GandalfHardcore's cave rock, #0a0a14, is blue by the numbers and black to the eye."""
    rock = np.zeros((CELL * 2, CELL * 2, 4), np.uint8)
    rock[:, :] = (10, 10, 20, 255)
    read = side_tiles.read(rock, (CELL, CELL))
    assert side_tiles.WATER not in read.kinds.values()
    water = rock.copy()
    water[:, :] = (40, 90, 200, 255)
    assert set(side_tiles.read(water, (CELL, CELL)).kinds.values()) == {side_tiles.WATER}


# ------------------------------------------------------------------ a pack


def test_a_collection_called_sidescroller_makes_its_stage_sets_side_view(tmp_path: Path) -> None:
    class Inv:
        pack_id = "forest"
        files: list[object] = []

    assert classifier.made_for(Inv(), [], "Forest") == "top"
    assert (
        classifier.made_for(Inv(), [], "Forest", ["Stages", "my sidescroller collection"]) == "side"
    )


def test_an_atlas_of_outlined_blocks_becomes_a_sheet_that_joins(tmp_path: Path) -> None:
    stage = _pack(tmp_path)
    cat = _assemble(stage, tmp_path)
    assert "view:side" in cat.packs[0].warnings, "the collection's name says side view"
    (sheet,) = [a for a in cat.assets if atlas_cuts.OUTLINE_TAG in (a.detected.get("tags") or [])]
    assert sheet.path.startswith("generated/side_terrain/")
    facets = sheet.detected
    assert facets["usage"] == "tiles" and facets["grid"]["cell"] == [CELL, CELL]
    over = facets["tile_overrides"]
    assert "terrain" in over["0,0"] and "terrain" in over["2,0"], "the fill and the surface join"
    assert over["0,1"]["custom"] == {"mds_kind": "mushroom"}
    assert over["0,1"]["collision"] == {"profile": "NONE"}
    assert over["2,1"]["custom"] == {"hazard": True}
    assert "1,1" not in over, "a log on the ground is a thing, not a tile"
    by_name = {
        a.path.rsplit("/", 1)[-1]: a for a in cat.assets if a.pack_id == cat.packs[0].pack_id
    }
    source = by_name["1. Ground.png"]
    assert any(
        t.startswith("unused_because:" + atlas_cuts.SOURCE_ASIDE) for t in source.detected["tags"]
    )
    aside = [
        n
        for n, a in by_name.items()
        if any(atlas_cuts.CELL_ASIDE in t for t in a.detected.get("tags") or [])
    ]
    assert {"dirt_fill.png", "grass_ground.png", "thorn_patch.png"} <= set(aside)
    assert "fallen_log.png" not in aside and "red_mushroom.png" not in aside, (
        "things stay in the dock"
    )
    (tileset,) = [t for t in cat.tilesets if any(s["asset"] == sheet.id for s in t.sources)]
    assert [s for s in tileset.terrain_sets if s["sheet"] == sheet.id], "a terrain set of its own"


def test_a_strip_cut_into_frames_is_one_animated_picture(tmp_path: Path) -> None:
    stage = _pack(tmp_path)
    cat = _assemble(stage, tmp_path)
    by_name = {a.path.rsplit("/", 1)[-1]: a for a in cat.assets}
    strip = by_name["bees 8x8.png"].detected
    assert strip["frame"] == [8, 8]
    assert strip["animations"]["idle"]["frames"] == [[0, 0], [1, 0], [2, 0], [3, 0]]
    frames = by_name["bees_frame01.png"].detected
    assert frames["role"] == "NONE", "a frame on its own is set aside"


def test_a_strip_keeps_no_walk_or_set_aside_its_frames_gave_it() -> None:
    """GandalfHardcore's bees: a sheet of 96x48 frames a motion reader took for somebody walking
    (the pack's player), and a garden pool pack_forms set aside as compiled of its frames."""
    bees = catalog.Asset(
        "g.small_bees_sheet", "g", "assets/packs/g/small_bees_sheet_96x48.png", "", "image",
        "AUTO_DETECTED",
        {"usage": "sprite", "role": "PLAYER", "tags": ["motion_named", "unused_because:x"]},
    )  # fmt: skip
    atlas_cuts._strip(bees, {"sprites": [{"x": 0, "y": 0}, {"x": 96, "y": 0}]}, (96, 48))
    assert bees.detected["role"] == "DECORATION"
    assert bees.detected["tags"] == [atlas_cuts.ATLAS_TAG]
    hero = catalog.Asset(
        "g.hero_run", "g", "assets/packs/g/Hero/hero_run.png", "", "image", "AUTO_DETECTED",
        {"usage": "sprite", "role": "PLAYER"},
    )  # fmt: skip
    atlas_cuts._strip(hero, {"sprites": [{"x": 0, "y": 0}]}, (32, 32))
    assert hero.detected["role"] == "PLAYER", "a hero's name says who it is"


def test_the_sheet_of_things_a_tool_cut_is_set_aside_for_its_things(tmp_path: Path) -> None:
    """*Village*'s full sheet: houses and stalls cut out where they lie, no grid."""
    stage = tmp_path / "my sidescroller collection" / "Stages" / "Village"
    cut = stage / "Village Sheet Sprites"
    cut.mkdir(parents=True)
    sheet = np.zeros((40, 80, 4), np.uint8)
    sheet[2:38, 2:38] = (150, 90, 60, 255)
    sheet[10:38, 44:78] = (90, 90, 140, 255)
    Image.fromarray(sheet).save(stage / "village full sheet.png")
    sprites = []
    for name, (x, y, w, h) in {"tavern": (2, 2, 36, 36), "market_stall": (44, 10, 34, 28)}.items():
        Image.fromarray(sheet[y : y + h, x : x + w].copy()).save(cut / f"{name}.png")
        sprites.append({"name": name, "file": f"{name}.png", "x": x, "y": y, "w": w, "h": h})
    (cut / "_atlas.json").write_text(
        json.dumps({"source": "village full sheet.png", "sprites": sprites}), encoding="utf-8"
    )
    cat = _assemble(stage, tmp_path)
    by_name = {a.path.rsplit("/", 1)[-1]: catalog.effective(a) for a in cat.assets}
    assert by_name["village full sheet.png"]["role"] == "NONE"
    assert "unused_because:" + atlas_cuts.SOURCE_ASIDE in by_name["village full sheet.png"]["tags"]
    assert by_name["tavern.png"]["role"] not in ("NONE", "GROUND")

"""The loose things of a tile sheet (T17.33, ``sheet_things``), on the synthetic pack
``sheet_things``: Kenney's *Tiny Farm* shape, one sheet of 16 px tiles a pixel apart holding
ground and the things a level is furnished with."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, inventory, sheet_things

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
sys.path.insert(0, str(REPO / "tools"))
import make_synthetic_packs as synth  # noqa: E402


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(tmp_path: Path) -> tuple[catalog.Catalog, dict[str, str]]:
    opened = archive.open_pack(SYNTH / "sheet_things", set())
    cat, _issues, generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], work_dir=tmp_path / "work"
    )
    return cat, generated


def _cell(c: int, r: int) -> list[int]:
    step = synth.ST_CELL + synth.ST_GAP
    return [c * step, r * step, synth.ST_CELL, synth.ST_CELL]


def test_the_things_of_a_sheet_of_tiles_are_in_the_dock(tmp_path: Path) -> None:
    cat, generated = _assemble(tmp_path)
    sheet = next(a for a in cat.assets if a.path.endswith("Tilemap/tilemap.png"))
    assert catalog.effective(sheet)["usage"] == "tiles", "the sheet stays a sheet of tiles"
    things = {tuple(o.region): o for o in cat.objects if sheet_things.TAG in o.tags}
    rock, bucket, flower = (things[tuple(_cell(*at))] for at in
                            (synth.ST_ROCK, synth.ST_BUCKET, synth.ST_FLOWER))  # fmt: skip
    assert len(things) == 3, "the rock, the bucket and the flower; no fence, no grass"
    for thing in (rock, bucket, flower):
        assert thing.sheet == sheet.id and thing.role == "DECORATION"
        assert thing.origin == [synth.ST_CELL // 2, synth.ST_CELL - 1], "it stands on its foot"
    assert rock.name == "grey_round" and rock.collision["profile"] == "CUSTOM"
    fx, fy, fw, fh = rock.footprint
    assert fy + fh == 15 and fw < synth.ST_CELL, "its collision is at its foot, narrower"
    assert flower.name.endswith("_small") and flower.collision == {"profile": "NONE"}
    schema.validate("catalog", cat.to_json())


def test_a_thing_over_two_cells_a_pixel_apart_is_a_picture_of_its_own(tmp_path: Path) -> None:
    cat, generated = _assemble(tmp_path)
    (tree,) = [a for a in cat.assets if sheet_things.TAG in (a.detected.get("tags") or [])]
    facets = catalog.effective(tree)
    assert facets["role"] == "DECORATION" and facets["usage"] == "sprite"
    assert facets["size"] == [synth.ST_CELL, 2 * synth.ST_CELL], "the crown and the trunk"
    assert f"cell:{synth.ST_TREE[0]}:{synth.ST_TREE[1]}" in facets["tags"]
    with Image.open(generated[tree.path]) as im:
        picture = np.asarray(im.convert("RGBA"))
    # no line of space through the middle: the leaves go on from the crown into the trunk
    assert (picture[synth.ST_CELL - 1 : synth.ST_CELL + 1, 6:10, 3] == 255).all()


def test_the_pieces_of_something_larger_stay_tiles() -> None:
    picture = np.asarray(synth._sheet_things())
    step = synth.ST_CELL + synth.ST_GAP

    def cell(c: int, r: int) -> np.ndarray:
        return picture[r * step : r * step + synth.ST_CELL, c * step : c * step + synth.ST_CELL]

    fence = [cell(c, r) for c, r in synth.ST_FENCE]
    assert sheet_things._continues(fence[0][:, -1], fence[1][:, 0]), "a rail goes on"
    assert not sheet_things.is_thing(cell(0, 0)), "a whole tile of grass is ground"
    assert sheet_things.is_thing(cell(*synth.ST_ROCK))
    rock, bucket = cell(*synth.ST_ROCK), cell(*synth.ST_BUCKET)
    assert not sheet_things._continues(rock[:, -1], bucket[:, 0]), "two things side by side"
    cells = {(c, r): cell(c, r) for c, r in synth.ST_FENCE}
    assert sheet_things._groups(cells) == [], "three pieces of a fence: larger than a thing"


def test_a_name_says_the_colour_and_the_shape() -> None:
    blank = np.zeros((16, 16, 4), np.uint8)
    tall = blank.copy()
    tall[1:15, 6:10] = (60, 160, 60, 255)
    assert sheet_things.name_of(tall) == "green_tall"
    wide = blank.copy()
    wide[2:14, 1:15] = (150, 96, 60, 255)
    wide[2, 1:15] = (62, 38, 50, 255)  # an outline is no colour of it
    assert sheet_things.name_of(wide).startswith("brown_")
    assert sheet_things.name_of(blank) == "thing"

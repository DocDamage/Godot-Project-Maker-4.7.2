"""The plain ground of a farm, the water of a farming pack and the crops of a mixed sheet (after
T17.24, T17.29 and T17.30), on the synthetic packs `farm_cave` and `mixed_sheet`."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, catalog, farm_ground, inventory
from rpggen.core.adapters import sheet_parts

REPO = Path(__file__).resolve().parents[2]
CAVE = REPO / "test_packs" / "synthetic" / "farm_cave"
MEADOW = CAVE / "Farm Cave Pack" / "Tileset" / "Tileset Grass Meadow.png"
MIXED = (
    REPO / "test_packs" / "synthetic" / "mixed_sheet" / "Synthetic Farm Tileset" / "farm" / "1.png"
)
GRID16 = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _picture(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        return np.asarray(opened.convert("RGBA"), dtype=np.uint8)


def test_the_ground_is_the_plainest_tile_not_the_first() -> None:
    sheet = _picture(MEADOW)
    # the first tile is the edge of a bed of soil: striped, it does not tile with itself
    assert farm_ground.tile_facts(sheet[0:16, 0:16]) is None
    assert farm_ground.choose(sheet, GRID16, "grass") == {"surface": "grass", "base": [1, 0]}
    # earth when the sheet says so; the most even of it
    assert farm_ground.choose(sheet, GRID16, "earth") == {"surface": "earth", "base": [0, 1]}


def test_a_tile_that_is_not_one_surface_or_has_holes_is_no_ground() -> None:
    sheet = _picture(MEADOW)
    assert farm_ground.tile_facts(sheet[16:32, 16:32]) is None  # water
    assert farm_ground.tile_facts(sheet[16:32, 32:48]) is None  # a blob on see-through ground
    half = sheet[0:16, 16:32].copy()
    half[:, 8:, :3] = (170, 130, 80)  # half grass, half earth
    assert farm_ground.tile_facts(half) is None


def test_a_sheet_without_plain_ground_gets_one_drawn_in_its_own_grass() -> None:
    sheet = _picture(MEADOW).copy()
    sheet[:, 16:] = 0
    sheet[16:] = 0  # only the edge of the bed is left
    assert farm_ground.choose(sheet, GRID16) is None
    assert farm_ground.grass_colour(sheet) == (90, 160, 70)
    drawn = np.asarray(farm_ground.draw(16, (90, 160, 70)))
    assert drawn.shape == (16, 16, 4) and (drawn[..., :3] == (90, 160, 70)).all()


def test_the_plan_names_the_plain_tile_of_the_chosen_sheet(tmp_path: Path) -> None:
    opened = archive.open_pack(CAVE, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    root = tmp_path / "project"
    for asset in cat.assets:
        source = CAVE / asset.path.split("/", 3)[-1]
        if source.is_file():
            target = root / asset.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    meadow = "farm_cave.farm_cave_pack.tileset.tileset_grass_meadow"
    cfg = SimpleNamespace(starter={"ground": meadow}, starter_map={}, projection="top_down")
    assert farm_ground.plan(cat, cfg, root) == {
        "v": farm_ground.VERSION, "asset": meadow, "surface": "grass", "base": [1, 0],
    }  # fmt: skip
    # a config that names no ground: the one the Mapping page chooses first (the meadow, not
    # the sheet of rock that comes before it in the tile set)
    unnamed = SimpleNamespace(starter={}, starter_map={}, projection="top_down")
    assert farm_ground.plan(cat, unnamed, root) == farm_ground.plan(cat, cfg, root)
    assert not farm_ground.add(cat, cfg, 16, root)  # a plain tile: nothing is drawn
    assert (
        farm_ground.plan(cat, SimpleNamespace(**{**vars(cfg), "projection": "isometric"}), root)
        is None
    )


def test_a_fish_icon_is_no_water_and_a_picture_of_water_is() -> None:
    opened = archive.open_pack(CAVE, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    roles = {a.id.rsplit(".", 1)[-1]: catalog.effective(a) for a in cat.assets}
    assert roles["dolphin"]["role"] == "ITEM"
    assert roles["water_tile"]["role"] == "WATER" and roles["water_tile"]["usage"] == "tiles"
    sources = {s["asset"] for t in cat.tilesets for s in t.sources}
    assert "farm_cave.farm_cave_pack.tileset.water_tile" in sources
    assert "farm_cave.farm_cave_pack.icons.fish.sea.dolphin" not in sources


def test_a_row_of_growth_stages_on_a_mixed_sheet_is_a_crop() -> None:
    sheet = _picture(MIXED)
    cell = sheet_parts.grid_cell(sheet)
    assert cell == 48
    cut = sheet_parts.sort_cells(sheet, cell, crops=True)
    crops = [p for p in cut.parts if p.facets.get("usage") == "growth_strip"]
    assert [(p.variant, p.facets["stages"], p.facets["frame"]) for p in crops] == [
        ("crop48_432", 4, [48, 96])
    ]
    assert crops[0].facets["role"] == "CROP" and crops[0].picture.shape == (96, 4 * 48, 4)
    # the produce after the stages stands in no soil: a thing of its own
    assert "o256_500" in {p.variant for p in cut.parts}
    # a mixed sheet of a pack that is no farm's keeps its rows as things
    plain = sheet_parts.sort_cells(sheet, cell)
    assert not [p for p in plain.parts if p.facets.get("usage") == "growth_strip"]

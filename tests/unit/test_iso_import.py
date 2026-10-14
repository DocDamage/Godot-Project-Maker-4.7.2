"""T17.28: imported maps in the isometric view, the Python side. An isometric Tiled map is read
(its tile sets may be collections of images), its pictures are measured as isometric pictures
wherever they lie, the catalog stores it by the pictures' asset ids with the pictures that block,
the tile set of an isometric project that imports it holds those pictures, and a map of the other
view is reported (TILE-013) and not planned as the starter map. A map of squares is read and
stored as before. The pack is drawn by ``tests/iso_tiled_pack.py``."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from rpggen import schema
from rpggen.core import archive, catalog, config, dry_run, inventory, iso_atlas, requirements
from rpggen.core.adapters import AdapterContext
from rpggen.core.adapters.tiled import TiledAdapter, map_pictures

REPO = Path(__file__).resolve().parents[2]
SAMPLE = "iso_tiled.samples.tiled_sample_extracted.sample"
CELLAR = "iso_tiled.samples.tiled_sample_extracted.cellar"
SPRITES = "iso_tiled.samples.tiled_sample_extracted.sprites."
SPRITES_PATH = "Samples/Tiled Sample_extracted/Sprites/"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DRAWN = _load("iso_tiled_pack", REPO / "tests" / "iso_tiled_pack.py")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return DRAWN.draw(tmp_path_factory.mktemp("iso_tiled"))


@pytest.fixture(scope="module")
def cat(pack: Path, tmp_path_factory: pytest.TempPathFactory) -> catalog.Catalog:
    import os

    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(tmp_path_factory.mktemp("cache"))
    try:
        opened = archive.open_pack(pack, set())
        found, _issues, _made = catalog.assemble(
            [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
        )
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old
    return found


def _maps(cat: catalog.Catalog) -> dict[str, dict]:
    return {m["id"]: m for m in cat.maps}


def _cfg(pack: Path, projection: str, selection: dict | None = None) -> config.GeneratorConfig:
    cfg = config.default_for(
        "x", [config.pack_ref_from_source(pack, "iso_tiled")], archetype="turn_based"
    )
    cfg.projection = projection
    cfg.imported_maps = selection if selection is not None else {"starter": SAMPLE}
    return cfg


def _write(folder: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (folder / "License.txt").write_text("CC0", encoding="utf-8")
    return folder


def _extract(folder: Path):
    opened = archive.open_pack(folder, set())
    inv = inventory.build_inventory(opened)
    adapter = TiledAdapter()
    return adapter.match(inv, opened.root), adapter.extract(
        inv, opened.root, AdapterContext(pack_id=inv.pack_id)
    )


def _png(folder: Path, rel: str) -> None:
    from PIL import Image

    path = folder / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 96), (0, 0, 0, 0)).save(path)


# --------------------------------------------------------------------------- the reader


def test_an_isometric_map_is_read_with_the_pictures_of_its_tiles(pack: Path) -> None:
    _match, res = _extract(pack)
    raw = {m["name"]: m for m in res.maps}
    sample = raw["Sample"]
    assert sample["projection"] == "isometric" and sample["tile_size"] == [64, 32]
    assert sample["pictures"] == sorted(
        SPRITES_PATH + f"{name}.png" for name in DRAWN.TILES.values()
    )
    layers = {layer["name"]: layer for layer in sample["layers"]}
    # one picture a tile: the picture is the tile, its column and row are 0
    walls = {(t[0], t[1]): (t[2], t[3], t[4]) for t in layers["Walls"]["tiles"]}
    assert walls[(0, 0)] == (SPRITES_PATH + "wall_E.png", 0, 0)
    assert walls[DRAWN.CRATE] == (SPRITES_PATH + "crate_E.png", 0, 0)
    assert len(walls) == len(DRAWN.WALL_CELLS) + 1
    assert layers["Upper"]["offset"] == [0, DRAWN.UPPER_OFFSET]
    assert "offset" not in layers["Floor"]
    # objects keep Tiled's coordinates, both axes counted in the height of a diamond
    start = next(o for o in layers["Objects"]["objects"] if o["name"] == "start")
    assert (start["x"], start["y"]) == ((DRAWN.SPAWN[0] + 0.5) * 32, (DRAWN.SPAWN[1] + 0.5) * 32)
    assert map_pictures([res]) == set(sample["pictures"])


def test_an_isometric_map_in_json_with_its_own_collection_is_read(tmp_path: Path) -> None:
    folder = tmp_path / "pk"
    _png(folder, "art/a.png")
    _png(folder, "art/b.png")
    tmj = {
        "orientation": "isometric", "width": 2, "height": 1, "tilewidth": 64, "tileheight": 32,
        "infinite": False,
        "tilesets": [{"firstgid": 1, "name": "c", "tilewidth": 64, "tileheight": 96, "columns": 0,
                      "tiles": [{"id": 0, "image": "art/a.png"}, {"id": 5, "image": "art/b.png"}]}],
        "layers": [
            {"type": "group", "offsetx": 2, "layers": [
                {"type": "tilelayer", "name": "L", "width": 2, "height": 1, "data": [6, 1],
                 "offsety": -8}]},
            {"type": "objectgroup", "name": "Objects", "objects": [
                {"name": "here", "type": "spawn", "x": 48, "y": 16}]},
        ],
    }  # fmt: skip
    _write(folder, {"m.tmj": json.dumps(tmj)})
    score, res = _extract(folder)
    assert score >= 0.5, "an isometric map whose tile set is its own collection is a reason to run"
    (raw,) = res.maps
    assert raw["projection"] == "isometric" and res.issues == []
    layer = raw["layers"][0]
    assert layer["tiles"] == [[0, 0, "art/b.png", 0, 0, 0], [1, 0, "art/a.png", 0, 0, 0]]
    assert layer["offset"] == [2, -8], "a layer's offset with its group's"


@pytest.mark.parametrize(
    ("orientation", "reason"),
    [("staggered", "staggered"), ("hexagonal", "hexagonal")],
)
def test_a_staggered_or_hexagonal_map_is_still_refused(
    tmp_path: Path, orientation: str, reason: str
) -> None:
    text = DRAWN.cellar_tmx().replace('orientation="isometric"', f'orientation="{orientation}"')
    folder = _write(tmp_path / "pk", {"m.tmx": text, "Sample.tsx": DRAWN.sample_tsx()})
    _score, res = _extract(folder)
    assert res.maps == []
    assert [(i.code, i.detail["reason"]) for i in res.issues] == [
        ("TILE-009", f"{reason} maps are not imported")
    ]


def test_a_map_of_squares_is_read_as_before(tmp_path: Path) -> None:
    from PIL import Image

    folder = tmp_path / "pk"
    folder.mkdir()
    Image.new("RGBA", (32, 32), (200, 40, 40, 255)).save(folder / "sheet.png")
    text = """<map orientation="orthogonal" width="2" height="1" tilewidth="16" tileheight="16" infinite="0">
 <tileset firstgid="1" name="s" tilewidth="16" tileheight="16" columns="2"><image source="sheet.png" width="32" height="32"/></tileset>
 <layer id="1" name="L" width="2" height="1" offsety="-8"><data encoding="csv">1,4</data></layer>
</map>"""
    _write(folder, {"a.tmx": text})
    _score, res = _extract(folder)
    (raw,) = res.maps
    assert set(raw) == {"name", "source", "format", "tile_size", "size", "layers"}
    assert raw["layers"] == [
        {
            "name": "L",
            "kind": "tiles",
            "tiles": [[0, 0, "sheet.png", 0, 0, 0], [1, 0, "sheet.png", 1, 1, 0]],
        }
    ]


# --------------------------------------------------------------------------- the catalog


def test_the_pictures_of_the_sample_are_measured_and_stay_unused(cat: catalog.Catalog) -> None:
    by_id = {a.id: a for a in cat.assets}
    for name in DRAWN.TILES.values():
        asset = by_id[SPRITES + name.lower()]
        facets = catalog.effective(asset)
        assert facets["projection"] == "isometric" and facets["footprint"] == list(DRAWN.FOOT)
        assert asset.status == "UNUSED", "a picture of the samples is used by its map alone"
    assert catalog.effective(by_id[SPRITES + "crate_e"])["usage"] == "sprite"  # an object
    assert catalog.effective(by_id[SPRITES + "floorwood_e"])["usage"] == "iso_tile"
    # the pack's own pictures say what the diamond is, as before
    assert catalog.effective(by_id["iso_tiled.isometric.floorwood_n"])["usage"] == "iso_tile"


def test_the_catalog_stores_the_map_by_its_pictures(cat: catalog.Catalog) -> None:
    from rpggen.core.adapters import maps as maps_mod

    schema.validate("catalog", cat.to_json())
    sample = _maps(cat)[SAMPLE]
    assert sample["projection"] == "isometric" and sample["size"] == list(DRAWN.SAMPLE_SIZE)
    assert sample["walls"] == [SPRITES + "wall_e"], "the wall by its name; the crate does not block"
    layers = {layer["name"]: layer for layer in sample["layers"]}
    assert [layer["kind"] for layer in sample["layers"]] == ["iso_tiles"] * 3 + ["objects"]
    floor = layers["Floor"]
    assert floor["pictures"] == [SPRITES + "floorstone_e", SPRITES + "floorwood_e"]
    cells = maps_mod.unrle(floor["cells"])
    width = DRAWN.SAMPLE_SIZE[0]
    assert cells[0] == (1, 0) and cells[7 * width] == (0, 0), "wood, and stone on row 7"
    walls = maps_mod.unrle(layers["Walls"]["cells"])
    assert walls[DRAWN.CRATE[1] * width + DRAWN.CRATE[0]] == (0, 0)  # the crate
    assert walls[1 * width + 1] == catalog.ISO_MAP_EMPTY
    assert layers["Upper"]["offset"] == [0, DRAWN.UPPER_OFFSET]
    cellar = _maps(cat)[CELLAR]
    assert cellar["walls"] == [] and cellar["layers"][0]["pictures"] == [SPRITES + "floorstone_e"]


def test_a_picture_that_is_not_isometric_is_found_by_its_bytes(cat: catalog.Catalog) -> None:
    copied = copy.deepcopy(cat)
    by_path = {a.path: a for a in copied.assets}
    own = by_path[f"assets/packs/iso_tiled/{SPRITES_PATH}floorWood_E.png"]
    own.detected = {k: v for k, v in own.detected.items() if k != "projection"}
    found = catalog._iso_picture(copied, "iso_tiled", f"{SPRITES_PATH}floorWood_E.png", by_path)
    # the pack's own picture of the same bytes, the first by id
    assert found is not None and found.id == "iso_tiled.isometric.floorwood_e"
    assert catalog._iso_picture(copied, "iso_tiled", "nowhere.png", by_path) is None


def test_a_map_fits_a_project_seen_as_it_is_drawn(cat: catalog.Catalog) -> None:
    sample = _maps(cat)[SAMPLE]
    square = {"id": "x", "layers": []}
    assert catalog.map_projection(sample) == "isometric"
    assert catalog.map_projection(square) == "top_down"
    assert catalog.map_fits(sample, "isometric") and not catalog.map_fits(sample, "top_down")
    assert catalog.map_fits(square, "top_down") and not catalog.map_fits(square, "isometric")


# --------------------------------------------------------------------------- the project


def test_the_tile_set_holds_the_pictures_of_the_maps_chosen(
    cat: catalog.Catalog, pack: Path, tmp_path: Path
) -> None:
    alone = copy.deepcopy(cat)
    iso_atlas.add(alone, _cfg(pack, "isometric", {}), tmp_path)
    tiles = iso_atlas.existing_def(alone)
    assert tiles is not None and not any(t.startswith(SPRITES) for t in tiles.tiles)
    chosen = copy.deepcopy(cat)
    iso_atlas.add(chosen, _cfg(pack, "isometric"), tmp_path)
    tdef = iso_atlas.existing_def(chosen)
    assert tdef is not None
    for name in ("wall_e", "crate_e", "floorwood_e", "floorstone_e"):
        assert tdef.tiles[SPRITES + name]["maps_only"] is True
    # the pack's own tiles keep their cells, and are no map's alone
    for tile_id, entry in tiles.tiles.items():
        assert (
            tdef.tiles[tile_id]["coords"] == entry["coords"]
            and "maps_only" not in tdef.tiles[tile_id]
        )
    schema.validate("catalog", chosen.to_json())


def test_a_map_of_the_other_view_is_reported(cat: catalog.Catalog, pack: Path) -> None:
    def tile013(cfg: config.GeneratorConfig) -> list[dict]:
        return [i.detail for i in requirements.check(cat, cfg) if i.code == "TILE-013"]

    assert tile013(_cfg(pack, "isometric")) == []
    (found,) = tile013(_cfg(pack, "top_down"))
    assert found["map"] == SAMPLE and found["drawn"] == "on diamonds"
    assert found["view"] == "seen from above"
    squares = copy.deepcopy(cat)
    squares.maps.append({"id": "pk.town", "pack_id": "iso_tiled", "source": "assets/packs/iso_tiled/town.tmx",
                         "format": "tiled", "tile_size": [16, 16], "size": [2, 2], "layers": []})  # fmt: skip
    cfg = _cfg(pack, "isometric", {"include": ["pk.town"]})
    (found,) = [i for i in requirements.check(squares, cfg) if i.code == "TILE-013"]
    assert found.detail["drawn"] == "on squares" and found.detail["view"] == "isometric"
    assert "is not imported" in found.message


def test_the_dry_run_plans_the_starter_map_for_a_map_of_the_other_view(
    cat: catalog.Catalog, pack: Path
) -> None:
    iso = dry_run._plan(_cfg(pack, "isometric"), cat)
    assert iso["imported"] == SAMPLE
    top = dry_run._plan(_cfg(pack, "top_down"), cat)
    assert "imported" not in top

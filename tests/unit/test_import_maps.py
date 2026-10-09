"""T12.49: Tiled and LDtk maps are read by the adapters and stored in the catalog."""

from __future__ import annotations

import base64
import gzip
import json
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from rpggen import jsonio, schema
from rpggen.core import archive, catalog, config, dry_run, inventory, options
from rpggen.core.adapters import AdapterContext, maps
from rpggen.core.adapters.ldtk import LdtkAdapter
from rpggen.core.adapters.tiled import TiledAdapter

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
FLIP_H, FLIP_V, FLIP_D = 0x80000000, 0x40000000, 0x20000000


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _assemble(pack: Path, previous: catalog.Catalog | None = None):
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    return catalog.assemble([(opened, inv)], previous, [], use_cache=False)


def _extract(adapter, pack: Path):
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    return adapter.extract(inv, opened.root, AdapterContext(pack_id=inv.pack_id))


def _by_id(cat: catalog.Catalog) -> dict[str, dict]:
    return {m["id"]: m for m in cat.maps}


def _layer(m: dict, name: str) -> dict:
    return next(layer for layer in m["layers"] if layer["name"] == name)


def _cells(layer: dict) -> list[tuple]:
    return maps.unrle(layer["cells"])


# ------------------------------------------------------------------------------- run lengths


def test_runs_round_trip() -> None:
    items = [(1, 0), (1, 0), (2, 5), (1, 0), (1, 0), (1, 0)]
    runs = maps.rle(items)
    assert runs == [[2, 1, 0], [1, 2, 5], [3, 1, 0]]
    assert maps.unrle(runs) == items
    assert maps.rle([]) == [] and maps.unrle([]) == []


# ------------------------------------------------------------------------------- Tiled


def test_every_tile_encoding_is_read_from_the_synthetic_pack() -> None:
    cat, issues, _ = _assemble(SYNTH / "tiled_map")
    by_id = _by_id(cat)
    assert sorted(by_id) == [
        "tiled_map.maps.cave",
        "tiled_map.maps.infinite",
        "tiled_map.maps.town",
        "tiled_map.maps.zstd_layer",
    ]
    town = by_id["tiled_map.maps.town"]
    assert town["size"] == [6, 4] and town["tile_size"] == [16, 16] and town["format"] == "tiled"
    assert town["source"] == "assets/packs/tiled_map/maps/town.tmx"
    ground = _cells(_layer(town, "Ground"))  # CSV
    assert len(ground) == 24 and ground[0] == (0, 0, 0, 0)
    assert ground[8] == (0, 1, 2, 0)  # the sand tile, gid 18: column 1, row 2
    walls = _cells(_layer(town, "Walls"))  # base64 + zlib
    assert walls[0] == (0, 0, 1, 0)
    assert sum(1 for c in walls if c[0] == -1) == 8
    cave = by_id["tiled_map.maps.cave"]  # base64 + gzip, and a plain JSON list
    assert _cells(_layer(cave, "Floor"))[3] == (0, 1, 2, 0)
    assert _cells(_layer(cave, "Plain"))[1] == (0, 0, 1, 0)
    # base64 + zstd (T13.14); only the layer with an unknown compression is lost, with TILE-009
    zstd = by_id["tiled_map.maps.zstd_layer"]
    assert [layer["name"] for layer in zstd["layers"]] == ["Ground", "Detail"]
    assert _cells(_layer(zstd, "Detail"))[1] == (0, 1, 2, 0)  # gid 18 again
    skipped = [i for i in issues if i.code == "TILE-009"]
    assert len(skipped) == 1
    assert skipped[0].detail["layer"] == "Lost"
    assert skipped[0].detail["reason"] == "it uses an unsupported compression (lz4)"
    assert skipped[0].severity.value == "warning"


def test_flip_flags_become_transform_bits() -> None:
    cat, _, _ = _assemble(SYNTH / "tiled_map")
    walls = _cells(_layer(_by_id(cat)["tiled_map.maps.town"], "Walls"))
    assert walls[6] == (0, 0, 1, maps.FLIP_H)  # row 1, column 0
    assert walls[11] == (0, 0, 1, maps.FLIP_V)
    assert walls[17] == (0, 0, 1, maps.FLIP_D)
    assert walls[1] == (0, 0, 1, 0)


def test_marker_objects_are_kept_with_their_properties() -> None:
    cat, _, _ = _assemble(SYNTH / "tiled_map")
    town = _by_id(cat)["tiled_map.maps.town"]
    spawn = _layer(town, "spawn")["objects"]
    assert spawn == [
        {"name": "start", "type": "spawn", "x": 24, "y": 40, "w": 0, "h": 0, "props": {}}
    ]
    door = _layer(town, "door")["objects"][0]
    assert door["type"] == "door" and door["props"] == {
        "target_map": "cave",
        "target_spawn": "default",
    }
    sign = _layer(town, "Notices")["objects"][0]  # recognised by its type, not by the layer name
    assert sign["type"] == "sign" and sign["props"]["text"] == "Welcome to town"


def test_an_infinite_map_is_flattened_to_the_bounds_of_its_tiles() -> None:
    cat, _, _ = _assemble(SYNTH / "tiled_map")
    infinite = _by_id(cat)["tiled_map.maps.infinite"]
    assert infinite["size"] == [6, 4]  # chunks at (-4, -2) and (0, 0): x -2..3, y -2..1
    cells = _cells(_layer(infinite, "Ground"))
    painted = {(i % 6, i // 6): c for i, c in enumerate(cells) if c[0] >= 0}
    assert set(painted) == {(0, 0), (1, 0), (2, 2), (3, 2), (5, 3)}
    assert painted[(3, 2)] == (0, 0, 1, 0)  # the wall tile of the second chunk


def test_catalog_with_maps_validates_and_survives_a_save(tmp_path: Path) -> None:
    cat, _, _ = _assemble(SYNTH / "tiled_map")
    schema.validate("catalog", cat.to_json())
    path = tmp_path / "catalog.json"
    catalog.save(cat, path)
    assert catalog.load(path).maps == cat.maps


def test_a_catalog_without_maps_has_no_maps_key() -> None:
    cat, _, _ = _assemble(SYNTH / "basic16")
    assert "maps" not in cat.to_json()
    assert cat.maps == []


def _pack(tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    pack = tmp_path / "pk"
    pack.mkdir(parents=True)
    Image.new("RGBA", (32, 32), (200, 40, 40, 255)).save(pack / "sheet.png")
    (pack / "LICENSE.txt").write_text("CC0")
    for rel, content in files.items():
        path = pack / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return pack


def _tmx(layer_data: str, width: int = 2, height: int = 2, extra: str = "") -> str:
    return f"""<map orientation="orthogonal" width="{width}" height="{height}" tilewidth="16" tileheight="16" infinite="0">
 <tileset firstgid="1" name="s" tilewidth="16" tileheight="16" columns="2"><image source="sheet.png" width="32" height="32"/></tileset>
 <layer id="1" name="L" width="{width}" height="{height}">{layer_data}</layer>{extra}
</map>"""


def _b64(gids: list[int], compression: str) -> str:
    raw = struct.pack(f"<{len(gids)}I", *gids)
    if compression == "zlib":
        raw = zlib.compress(raw)
    elif compression == "gzip":
        raw = gzip.compress(raw)
    return base64.b64encode(raw).decode()


@pytest.mark.parametrize("compression", ["", "zlib", "gzip"])
def test_base64_layers_with_each_compression(tmp_path: Path, compression: str) -> None:
    comp = f' compression="{compression}"' if compression else ""
    data = f'<data encoding="base64"{comp}>{_b64([1, 2, 3, 4], compression)}</data>'
    res = _extract(TiledAdapter(), _pack(tmp_path, {"a.tmx": _tmx(data)}))
    assert res.issues == []
    tiles = res.maps[0]["layers"][0]["tiles"]
    assert tiles == [[0, 0, "sheet.png", 0, 0, 0], [1, 0, "sheet.png", 1, 0, 0],
                     [0, 1, "sheet.png", 0, 1, 0], [1, 1, "sheet.png", 1, 1, 0]]  # fmt: skip


def test_a_damaged_or_unknown_layer_is_skipped_with_tile009(tmp_path: Path) -> None:
    damaged = '<data encoding="base64" compression="zlib">AAAA</data>'
    unknown = '<data encoding="base64" compression="lz4">AAAA</data>'
    short = '<data encoding="csv">1,2,3</data>'
    for data, reason in ((damaged, "damaged"), (unknown, "lz4"), (short, "does not fit")):
        res = _extract(TiledAdapter(), _pack(tmp_path / reason.split()[0], {"a.tmx": _tmx(data)}))
        assert res.maps == []
        assert [i.code for i in res.issues] == ["TILE-009"]
        assert reason in res.issues[0].detail["reason"]


def test_a_decompression_bomb_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rpggen.core.adapters import tiled

    monkeypatch.setattr(tiled, "MAX_TILE_BYTES", 8)
    data = f'<data encoding="base64" compression="zlib">{_b64([1, 2, 3, 4], "zlib")}</data>'
    res = _extract(TiledAdapter(), _pack(tmp_path, {"a.tmx": _tmx(data)}))
    assert res.maps == [] and "too large" in res.issues[0].detail["reason"]


def test_a_layer_whose_tile_sheet_is_missing_is_skipped(tmp_path: Path) -> None:
    pack = _pack(
        tmp_path,
        {"a.tmx": _tmx('<data encoding="csv">1,2,3,4</data>').replace("sheet.png", "gone.png")},
    )
    res = _extract(TiledAdapter(), pack)
    assert res.maps == []
    codes = sorted(i.code for i in res.issues)
    assert codes == ["ADAPT-002", "TILE-009"]


def test_a_map_that_is_not_orthogonal_is_skipped(tmp_path: Path) -> None:
    text = _tmx('<data encoding="csv">1,2,3,4</data>').replace("orthogonal", "isometric")
    res = _extract(TiledAdapter(), _pack(tmp_path, {"a.tmx": text}))
    assert res.maps == [] and [i.code for i in res.issues] == ["TILE-009"]


def test_gids_of_a_second_tileset_use_its_own_image(tmp_path: Path) -> None:
    text = """<map orientation="orthogonal" width="2" height="1" tilewidth="16" tileheight="16" infinite="0">
 <tileset firstgid="1" name="a" tilewidth="16" tileheight="16" columns="2"><image source="sheet.png" width="32" height="32"/></tileset>
 <tileset firstgid="5" name="b" tilewidth="16" tileheight="16" columns="2"><image source="other.png" width="32" height="32"/></tileset>
 <layer id="1" name="L" width="2" height="1"><data encoding="csv">4,6</data></layer>
</map>"""
    pack = _pack(tmp_path, {"a.tmx": text})
    Image.new("RGBA", (32, 32), (10, 200, 10, 255)).save(pack / "other.png")
    tiles = _extract(TiledAdapter(), pack).maps[0]["layers"][0]["tiles"]
    assert tiles == [[0, 0, "sheet.png", 1, 1, 0], [1, 0, "other.png", 1, 0, 0]]


def test_a_layer_with_two_tile_sets_becomes_one_layer_each(tmp_path: Path) -> None:
    text = """<map orientation="orthogonal" width="2" height="1" tilewidth="16" tileheight="16" infinite="0">
 <tileset firstgid="1" name="a" tilewidth="16" tileheight="16" columns="2"><image source="sheet.png" width="32" height="32"/></tileset>
 <tileset firstgid="5" name="b" tilewidth="32" tileheight="32" columns="2"><image source="big.png" width="64" height="64"/></tileset>
 <layer id="1" name="L" width="2" height="1"><data encoding="csv">1,5</data></layer>
</map>"""
    pack = _pack(tmp_path, {"a.tmx": text})
    Image.new("RGBA", (64, 64), (10, 10, 200, 255)).save(pack / "big.png")  # 32 px tiles
    cat, _, _ = _assemble(pack)
    # the common size keeps the plain name; the layer is split by tile set, first tile first
    assert sorted(t.name for t in cat.tilesets) == ["overworld", "overworld_16"]
    layers = cat.maps[0]["layers"]
    assert [(ly["name"], ly["tileset"]) for ly in layers] == [
        ("L (overworld_16)", "overworld_16"),
        ("L (overworld)", "overworld"),
    ]
    first, second = (_cells(ly) for ly in layers)
    assert first[0][0] >= 0 and first[1][0] == -1
    assert second[0][0] == -1 and second[1][1:] == (0, 0, 0)


def test_tiles_of_a_sheet_that_is_no_tile_set_make_tile009(tmp_path: Path) -> None:
    pack = _pack(tmp_path, {"a.tmx": _tmx('<data encoding="csv">1,2,3,4</data>')})
    cat, issues, _ = _assemble(pack)
    assert len(cat.maps) == 1 and len(cat.maps[0]["layers"]) == 1  # the sheet is a tile set
    # the user marks the sheet as something else: the layer has no tile set any more
    asset = cat.assets[0]
    asset.overrides = {"usage": "sprites", "role": "NONE"}
    opened = archive.open_pack(pack, set())
    cat2, issues2, _ = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], cat, [], use_cache=False
    )
    assert cat2.maps == []
    skipped = [i for i in issues2 if i.code == "TILE-009"]
    assert skipped and "not part of a tile set" in skipped[0].detail["reason"]


def test_map_ids_are_unique(tmp_path: Path) -> None:
    data = '<data encoding="csv">1,2,3,4</data>'
    pack = _pack(tmp_path, {"a.tmx": _tmx(data), "a.tmj": json.dumps({
        "orientation": "orthogonal", "width": 2, "height": 1, "tilewidth": 16, "tileheight": 16,
        "tilesets": [{"firstgid": 1, "name": "s", "tilewidth": 16, "tileheight": 16, "columns": 2,
                      "image": "sheet.png", "imagewidth": 32, "imageheight": 32}],
        "layers": [{"type": "tilelayer", "name": "L", "width": 2, "height": 1, "data": [1, 2]}],
    })})  # fmt: skip
    cat, _, _ = _assemble(pack)
    assert len(cat.maps) == 2 and len({m["id"] for m in cat.maps}) == 2


# ------------------------------------------------------------------------------- LDtk


def test_ldtk_level_becomes_a_map() -> None:
    cat, issues, _ = _assemble(SYNTH / "ldtk_level")
    assert issues == []
    level = _by_id(cat)["ldtk_level.world.level_0"]
    assert level["format"] == "ldtk" and level["size"] == [6, 4] and level["tile_size"] == [16, 16]
    # bottom layer first (LDtk lists the top layer first)
    assert [layer["name"] for layer in level["layers"]] == ["Ground", "Collisions", "Entities"]
    ground = _cells(level["layers"][0])
    assert ground[0] == (0, 0, 0, 0)
    assert ground[8] == (0, 0, 1, maps.FLIP_H)  # f=1: flipped in x
    assert ground[15] == (0, 1, 1, maps.FLIP_H | maps.FLIP_V)  # f=3: x and y
    markers = {o["type"]: o for o in level["layers"][2]["objects"]}
    assert sorted(markers) == ["sign", "spawn"]  # the chest is not a marker
    assert markers["sign"]["props"] == {"text": "Hello"}
    assert (markers["spawn"]["x"], markers["spawn"]["y"]) == (24, 40)


def test_intgrid_values_named_wall_are_solid() -> None:
    cat, _, _ = _assemble(SYNTH / "ldtk_level")
    layer = _layer(_by_id(cat)["ldtk_level.world.level_0"], "Collisions")
    assert layer["kind"] == "intgrid"
    assert layer["values"] == [
        {"value": 1, "name": "wall", "solid": True},
        {"value": 2, "name": "water", "solid": False},
    ]
    cells = [c[0] for c in maps.unrle(layer["cells"])]
    assert len(cells) == 24 and cells[:7] == [1] * 7 and cells[9:11] == [2, 2]


def test_the_choice_of_solid_values_survives_regeneration() -> None:
    first, _, _ = _assemble(SYNTH / "ldtk_level")
    level = _layer(first.maps[0], "Collisions")
    for value in level["values"]:
        value["solid"] = not value["solid"]  # the user's choice: water blocks, walls do not
    again, _, _ = _assemble(SYNTH / "ldtk_level", first)
    values = _layer(again.maps[0], "Collisions")["values"]
    assert [(v["value"], v["solid"]) for v in values] == [(1, False), (2, True)]


def _ldtk(tmp_path: Path, level: dict, defs: dict | None = None) -> Path:
    project = {
        "defs": defs
        or {"layers": [], "tilesets": [{"uid": 1, "relPath": "sheet.png", "tileGridSize": 16}]},
        "levels": [dict({"identifier": "L", "pxWid": 32, "pxHei": 32}, **level)],
    }
    return _pack(tmp_path, {"w.ldtk": json.dumps(project)})


def _instance(identifier: str, kind: str, **extra) -> dict:
    return {"__identifier": identifier, "__type": kind, "__cWid": 2, "__cHei": 2,
            "__gridSize": 16, "layerDefUid": 5, **extra}  # fmt: skip


def test_an_intgrid_layer_with_auto_rules_gives_a_tile_layer_too(tmp_path: Path) -> None:
    tiles = [{"px": [0, 0], "src": [16, 0], "f": 0, "t": 1}]
    defs = {
        "layers": [{"uid": 5, "identifier": "Collision", "type": "IntGrid", "intGridValues": []}],
        "tilesets": [{"uid": 1, "relPath": "sheet.png", "tileGridSize": 16}],
    }
    layer = _instance(
        "Collision", "IntGrid", intGridCsv=[1, 0, 0, 1], autoLayerTiles=tiles, __tilesetDefUid=1
    )
    res = _extract(LdtkAdapter(), _ldtk(tmp_path, {"layerInstances": [layer]}, defs))
    layers = {ly["name"]: ly for ly in res.maps[0]["layers"]}
    assert set(layers) == {"Collision", "Collision_tiles"}
    assert layers["Collision_tiles"]["tiles"] == [[0, 0, "sheet.png", 1, 0, 0]]
    # no value has a name, but the layer says collision: every value is solid
    assert layers["Collision"]["values"] == [{"value": 1, "name": "", "solid": True}]


def test_ldtk_padding_and_spacing_are_taken_out_of_the_source_position(tmp_path: Path) -> None:
    defs = {
        "layers": [],
        "tilesets": [
            {"uid": 1, "relPath": "sheet.png", "tileGridSize": 16, "spacing": 1, "padding": 2}
        ],
    }
    tiles = [{"px": [16, 0], "src": [2 + 17, 2 + 17], "f": 0, "t": 3}]
    layer = _instance("Tiles", "Tiles", gridTiles=tiles, __tilesetDefUid=1)
    res = _extract(LdtkAdapter(), _ldtk(tmp_path, {"layerInstances": [layer]}, defs))
    assert res.maps[0]["layers"][0]["tiles"] == [[1, 0, "sheet.png", 1, 1, 0]]


def test_an_ldtk_layer_with_a_missing_tile_sheet_is_skipped(tmp_path: Path) -> None:
    defs = {"layers": [], "tilesets": [{"uid": 1, "relPath": "gone.png", "tileGridSize": 16}]}
    tiles = [{"px": [0, 0], "src": [0, 0], "f": 0, "t": 0}]
    layer = _instance("Tiles", "Tiles", gridTiles=tiles, __tilesetDefUid=1)
    res = _extract(LdtkAdapter(), _ldtk(tmp_path, {"layerInstances": [layer]}, defs))
    assert res.maps == []
    assert "TILE-009" in [i.code for i in res.issues]


def test_ldtk_levels_in_separate_files(tmp_path: Path) -> None:
    tiles = [{"px": [0, 0], "src": [0, 0], "f": 0, "t": 0}]
    layer = _instance("Tiles", "Tiles", gridTiles=tiles, __tilesetDefUid=1)
    project = {
        "defs": {"layers": [], "tilesets": [{"uid": 1, "relPath": "sheet.png", "tileGridSize": 16}]},
        "levels": [{"identifier": "Out", "pxWid": 32, "pxHei": 32, "layerInstances": None,
                    "externalRelPath": "levels/out.ldtkl"}],
    }  # fmt: skip
    pack = _pack(tmp_path, {
        "w.ldtk": json.dumps(project),
        "levels/out.ldtkl": json.dumps({"identifier": "Out", "pxWid": 32, "pxHei": 32, "layerInstances": [layer]}),
    })  # fmt: skip
    res = _extract(LdtkAdapter(), pack)
    assert [m["name"] for m in res.maps] == ["Out"]


# ------------------------------------------------------------------------------- config, options


def test_the_config_stores_the_selection_only_when_there_is_one() -> None:
    cfg = config.default_for("T", [config.PackRef("x", "C:/x", "0" * 64, "folder")])
    assert "imported_maps" not in cfg.to_json()
    cfg.imported_maps = {"include": ["b", "a"], "starter": "c"}
    data = cfg.to_json()
    assert data["imported_maps"] == {"include": ["a", "b", "c"], "starter": "c"}
    schema.validate("config", data)
    again = config.GeneratorConfig.from_json(data)
    assert again.imported_map_selection() == {"include": ["a", "b", "c"], "starter": "c"}
    cfg.imported_maps = {"include": ["a"]}
    assert cfg.to_json()["imported_maps"] == {"include": ["a"]}


def test_a_selection_is_checked_against_the_catalog() -> None:
    known = ["p.a", "p.b"]
    assert options.normalize_imported_maps({}, known) == {}
    assert options.normalize_imported_maps(
        {"include": ["p.b", "gone"], "starter": "gone"}, known
    ) == {"include": ["p.b"]}
    assert options.normalize_imported_maps({"starter": "p.a"}, known) == {
        "include": ["p.a"],
        "starter": "p.a",
    }


def test_the_summary_names_the_imported_maps() -> None:
    features = {"demo": True}
    plain = options.summarize("turn_based", features, {"buildings": 1}, 16, (640, 360))
    assert plain.maps == ["Starter map", "Second area", "1 interior"]
    chosen = {"include": ["p.a", "p.b"], "starter": "p.a"}
    summary = options.summarize("turn_based", features, {"buildings": 1}, 16, (640, 360), chosen)
    assert summary.maps == ["Starter map (imported)", "1 imported map"]


def test_a_dry_run_reports_the_imported_starter_instead_of_planning() -> None:
    cat, _, _ = _assemble(SYNTH / "ldtk_level")
    cfg = config.default_for("T", [config.PackRef("ldtk_level", "C:/x", "0" * 64, "folder")])
    cfg.imported_maps = {"starter": "ldtk_level.world.level_0"}
    plan = dry_run._plan(cfg, cat)
    assert plan["imported"] == "ldtk_level.world.level_0" and plan["size"] == [6, 4]
    lines = dry_run.format_summary({**_summary_stub(), "map": plan})
    assert any("ldtk_level.world.level_0 (imported), 6 x 4 tiles" in line for line in lines)


def _summary_stub() -> dict:
    return {
        "project_name": "T", "archetype": "turn_based", "regeneration": False,
        "packs": ["ldtk_level"], "tile_size": 16, "tile_size_from": "packs",
        "resolution": [640, 360], "assets": 1, "objects": 0, "tilesets": 1,
        "roles": {}, "placeholders": [],
    }  # fmt: skip


def test_the_catalog_json_of_both_packs_matches_the_golden_files() -> None:
    for name in ("tiled_map", "ldtk_level"):
        cat, _, _ = _assemble(SYNTH / name)
        golden = Path(__file__).resolve().parents[2] / "tests" / "golden" / f"{name}.catalog.json"
        assert jsonio.dumps(cat.to_json()) == golden.read_text(encoding="utf-8")


def test_the_solid_values_can_be_listed_and_changed() -> None:
    cat, _, _ = _assemble(SYNTH / "ldtk_level")
    rows = options.intgrid_rows(cat.maps)
    assert [(r["layer"], r["value"], r["name"], r["solid"]) for r in rows] == [
        ("Collisions", 1, "wall", True),
        ("Collisions", 2, "water", False),
    ]
    assert rows[1]["label"] == "world/level_0 · ldtk_level · 6 × 4 tiles · Collisions · 2 (water)"
    key = ("ldtk_level.world.level_0", "Collisions", 2)
    wall = ("ldtk_level.world.level_0", "Collisions", 1)
    assert options.set_solid(cat.maps, {key: True, wall: True, ("x", "y", 3): True}) == 1
    assert [r["solid"] for r in options.intgrid_rows(cat.maps)] == [True, True]
    assert options.set_solid(cat.maps, {key: True}) == 0

"""Terrain blocks inside sheets and isometric terrains (T17.31), on the synthetic packs
``terrain_blocks`` (a block of every layout inside one mixed sheet) and ``iso_terrain``."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, inventory, iso_atlas
from rpggen.core.archive import Cancelled
from rpggen.core.terrain import blocks, iso
from rpggen.errors import IssueList

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
SHEET = SYNTH / "terrain_blocks" / "Terrain Blocks" / "Tilesets" / "Ground Terrain Mix.png"
sys.path.insert(0, str(REPO / "tools"))
import make_synthetic_packs as synth  # noqa: E402


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _found() -> dict[str, blocks.Block]:
    rgba = np.asarray(Image.open(SHEET).convert("RGBA"))
    found = blocks.find(rgba, 16, 16, {"ground", "terrain", "mix"})
    return {b.layout: b for b in found}


def test_a_block_of_every_layout_is_found_where_it_lies() -> None:
    found = _found()
    for layout, at in synth.TB_AT.items():
        assert layout in found, layout
        assert found[layout].origin == at, layout
    assert found["blob47_godot_12x4"].mode == "corners_and_sides"
    assert found["corners16_4x4"].mode == "corners"
    assert found["corners16_drawn_4x4"].mode == "corners"
    assert found["sides16_drawn_4x4"].mode == "sides"
    assert found["strips"].mode == "sides"
    assert len(found["blob47_godot_12x4"].cells) == 47
    assert len(found["rpg13_3x3"].cells) == 13
    assert len(found["minimal9_3x3"].cells) == 9


def test_what_a_block_is_drawn_over_and_its_surface() -> None:
    found = _found()
    assert found["blob47_godot_12x4"].over == "ground"
    assert found["corners16_drawn_4x4"].over == "nothing"
    assert found["minimal9_3x3"].over == "nothing"
    assert found["blob47_godot_12x4"].surface == "dirt"
    assert found["blob47_12x4"].surface == "water"
    assert found["rpg13_3x3"].surface == "sand"
    assert found["rpgmaker_2x3"].surface == "water"
    assert found["strips"].surface == "dirt"
    assert found["rpg13_3x3"].shape == "area"
    assert found["blob47_godot_12x4"].shape == "any"
    assert found["strips"].shape == "path"


def test_the_inner_corners_and_the_variants_of_a_3x3_block() -> None:
    block = _found()["rpg13_3x3"]
    ix, iy = synth.TB_INNER_AT
    by_cell = dict(block.cells)
    assert by_cell[(ix, iy)] == 127  # the notch at the top left
    assert by_cell[(ix + 1, iy)] == 253
    assert by_cell[(ix, iy + 1)] == 223
    assert by_cell[(ix + 1, iy + 1)] == 247
    assert sorted(block.variants) == sorted(synth.TB_VARIANTS_AT)
    entries = blocks.entries(block, "sand_block")
    chances = []
    for x, y in synth.TB_VARIANTS_AT:
        entry = entries[f"{x},{y}"]
        assert 0 < entry["probability"] <= blocks.VARIANT_PROBABILITY
        assert set(entry["terrain"]["peering"].values()) == {0}
        chances.append(entry["probability"])
    # T17.33: the middle (probability 1) is most of the ground, the variants details in it
    assert sum(chances) / (1.0 + sum(chances)) <= blocks.VARIANTS_SHARE + 1e-3


def test_the_peering_of_a_tile_follows_its_mask() -> None:
    block = _found()["rpg13_3x3"]
    x0, y0 = synth.TB_AT["rpg13_3x3"]
    entries = blocks.entries(block, "s")
    corner = entries[f"{x0},{y0}"]["terrain"]["peering"]  # the top left corner: 28 = E SE S
    assert corner["right_side"] == 0 and corner["bottom_side"] == 0
    assert corner["bottom_right_corner"] == 0
    assert corner["top_side"] == -1 and corner["left_side"] == -1
    strips = _found()["strips"]
    by_cell = dict(strips.cells)
    sx, sy = synth.TB_AT["strips"]
    assert by_cell[(sx, sy)] == 16 and by_cell[(sx, sy + 1)] == 17 and by_cell[(sx, sy + 2)] == 1
    assert by_cell[(sx + 6, sy)] == 0  # the single bed


def test_a_sheet_of_objects_has_no_terrain() -> None:
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for k in range(16):
        x, y = (k % 8) * 16, (k // 8) * 16
        Image.Image.paste(img, (40 + k * 9, 160 - k * 5, 90, 255), (x + 3, y + 3, x + 13, y + 13))
    assert blocks.find(np.asarray(img), 16, 16) == []
    plain = Image.new("RGBA", (64, 64), (90, 160, 70, 255))
    assert [b.layout for b in blocks.find(np.asarray(plain), 16, 16)] == [], "one flat colour"


def test_reading_is_the_same_twice() -> None:
    one = [(b.layout, b.origin, b.cells, b.variants) for b in _found().values()]
    two = [(b.layout, b.origin, b.cells, b.variants) for b in _found().values()]
    assert one == two


def _assemble(name: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / name, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    return cat


def test_the_catalog_holds_the_terrains_of_the_sheet() -> None:
    cat = _assemble("terrain_blocks")
    schema.validate("catalog", cat.to_json())
    overworld = next(t for t in cat.tilesets if t.name == "overworld")
    layouts = {t.get("layout") for t in overworld.terrain_sets}
    assert set(synth.TB_AT) - {"rpgmaker_2x3"} <= layouts
    assert "rpgmaker_a2" in layouts  # the 2x3 block composed into an atlas of its own
    sheet = cat.asset("terrain_blocks.terrain_blocks.tilesets.ground_terrain_mix")
    assert sheet is not None
    overrides = catalog.effective(sheet)["tile_overrides"]
    sets = {t["name"] for t in overworld.terrain_sets}
    assert all(
        entry["terrain"]["set"] in sets for entry in overrides.values() if "terrain" in entry
    )
    composed = [a for a in cat.assets if a.pack_id == "generated"]
    assert len(composed) == 1 and len(catalog.effective(composed[0])["tile_overrides"]) == 47


def test_a_cancel_stops_the_reading(tmp_path: Path) -> None:
    from rpggen.core import terrain

    opened = archive.open_pack(SYNTH / "terrain_blocks", set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    for a in cat.assets:
        a.detected.pop("tile_overrides", None)
    with pytest.raises(Cancelled):
        terrain.generate(cat, {"terrain_blocks": opened.root}, tmp_path, IssueList(), lambda: True)


def test_isometric_pieces_make_terrains_by_their_names_and_by_their_edges() -> None:
    cat = _assemble("iso_terrain")
    schema.validate("catalog", cat.to_json())
    pieces: dict[str, dict] = {}
    for a in cat.assets:
        found = catalog.effective(a).get(iso.FACET)
        if found:
            pieces[a.id.rsplit(".", 1)[-1]] = found
    water = {k: v for k, v in pieces.items() if k.startswith("water")}
    assert len(water) == len(synth.IT_WATER_PIECES)
    assert {v["mode"] for v in water.values()} == {"corners_and_sides"}
    assert {v["surface"] for v in water.values()} == {"water"}
    # waterE has its land on e: the water goes on at n, s and w
    peering = water["watere"]["peering"]
    assert [
        k for k in ("top_side", "right_side", "bottom_side", "left_side") if peering[k] == 0
    ] == [
        "top_side",
        "bottom_side",
        "left_side",
    ]
    # the inner corner: every side, the land in the corner between e and s
    inner = water["watercorneres"]["peering"]
    assert inner["bottom_right_corner"] == -1 and inner["top_left_corner"] == 0
    paths = {k: v for k, v in pieces.items() if "path" in k}
    assert len(paths) == 11
    assert {v["mode"] for v in paths.values()} == {"sides"}
    assert {v["over"] for v in paths.values()} == {"nothing"}
    cross = paths["path_stone_01_64x32#c0_0"]["peering"]
    assert all(cross[k] == 0 for k in ("top_side", "right_side", "bottom_side", "left_side"))


def test_the_isometric_tile_set_gathers_the_terrain_sets() -> None:
    cat = _assemble("iso_terrain")
    members = [a for a in cat.assets if catalog.effective(a).get(iso.FACET)]
    sets = iso.terrain_sets(members, [])
    assert [s["mode"] for s in sets] == sorted(
        {s["mode"] for s in sets}, key=[s["mode"] for s in sets].index
    )
    assert {s["surface"] for s in sets} == {"water", "path"}
    kept = iso.terrain_sets(members, [{"name": "mine", "mode": "sides", "terrains": []}])
    assert kept[0]["name"] == "mine", "the sets the tile set had keep their place"
    assert len(kept) == len(sets) + 1
    assert iso_atlas.TILESET == "iso"

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from rpggen import jsonio, schema
from rpggen.core import archive, catalog, inventory
from rpggen.core.terrain import rpgmaker_a2 as a2

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
Q = 4  # quarter size of the synthetic block (tile = 8 px)
TILE = 2 * Q


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def coord_color(qx: int, qy: int) -> tuple[int, int, int, int]:
    return (40 * qx + 20, 30 * qy + 20, 200, 255)


def coded_block() -> Image.Image:
    """A 4x6 quarter block where every quarter has its own color encoding (qx, qy)."""
    img = Image.new("RGBA", (4 * Q, 6 * Q))
    for qy in range(6):
        for qx in range(4):
            img.paste(coord_color(qx, qy), (qx * Q, qy * Q, (qx + 1) * Q, (qy + 1) * Q))
    return img


def quarter_colors(tile: Image.Image) -> dict[str, tuple[int, ...]]:
    return {
        "TL": tile.getpixel((0, 0)),
        "TR": tile.getpixel((TILE - 1, 0)),
        "BL": tile.getpixel((0, TILE - 1)),
        "BR": tile.getpixel((TILE - 1, TILE - 1)),
    }


def test_there_are_47_normalized_masks_ordered_ascending() -> None:
    masks = a2.blob_masks()
    assert len(masks) == 47 and masks == sorted(masks) and len(set(masks)) == 47
    assert masks[0] == 0 and masks[-1] == 255
    assert {a2.normalize_mask(m) for m in range(256)} == set(masks)


def test_normalize_mask_clears_corners_without_both_sides() -> None:
    assert a2.normalize_mask(a2.NE) == 0
    assert a2.normalize_mask(a2.NE | a2.N) == a2.N
    assert a2.normalize_mask(a2.NE | a2.N | a2.E) == a2.NE | a2.N | a2.E
    assert a2.normalize_mask(255) == 255
    assert all(a2.normalize_mask(m) == m for m in a2.blob_masks())


def test_composer_returns_47_unique_tiles_from_coded_quarters() -> None:
    tiles = a2.compose_block(coded_block(), 0, 0, TILE)
    assert len(tiles) == 47 and all(t.size == (TILE, TILE) for t in tiles)
    assert len({t.tobytes() for t in tiles}) == 47


def test_quarters_follow_the_card_table() -> None:
    tiles = dict(zip(a2.blob_masks(), a2.compose_block(coded_block(), 0, 0, TILE), strict=True))
    c = coord_color
    assert quarter_colors(tiles[255]) == {
        "TL": c(2, 4),
        "TR": c(1, 4),
        "BL": c(2, 3),
        "BR": c(1, 3),
    }
    assert quarter_colors(tiles[0]) == {"TL": c(0, 2), "TR": c(3, 2), "BL": c(0, 5), "BR": c(3, 5)}
    sides = a2.N | a2.E | a2.S | a2.W  # all sides, no corners: inner corners
    assert quarter_colors(tiles[sides]) == {
        "TL": c(2, 0),
        "TR": c(3, 0),
        "BL": c(2, 1),
        "BR": c(3, 1),
    }
    # only an east neighbor: the right quarters have R but not U/D -> horizontal edge
    assert quarter_colors(tiles[a2.E]) == {
        "TL": c(0, 2),
        "TR": c(1, 2),
        "BL": c(0, 5),
        "BR": c(1, 5),
    }
    # only a north neighbor: U and not L -> vertical edge on top, outer corner below
    assert quarter_colors(tiles[a2.N]) == {
        "TL": c(0, 4),
        "TR": c(3, 4),
        "BL": c(0, 5),
        "BR": c(3, 5),
    }


def test_peering_matches_the_mask() -> None:
    entries = a2.atlas_tile_overrides("grass_b0")
    assert len(entries) == 47
    keys = list(entries)
    assert keys[0] == "0,0" and keys[8] == "0,1" and keys[46] == "6,5"
    for key, mask in zip(keys, a2.blob_masks(), strict=True):
        terrain = entries[key]["terrain"]
        assert terrain["set"] == "grass_b0" and terrain["terrain"] == 0
        p = terrain["peering"]
        assert (p["top_side"] == 0) == bool(mask & a2.N)
        assert (p["right_side"] == 0) == bool(mask & a2.E)
        assert (p["bottom_left_corner"] == 0) == bool(mask & a2.SW)
        assert (p["top_left_corner"] == 0) == bool(mask & a2.NW)
        if p["top_right_corner"] == 0:  # a corner is only set together with both sides
            assert p["top_side"] == 0 and p["right_side"] == 0
        assert set(p.values()) <= {-1, 0}
    assert all(v == -1 for v in entries["0,0"]["terrain"]["peering"].values())
    assert all(v == 0 for v in entries["6,5"]["terrain"]["peering"].values())


def test_compose_atlas_is_deterministic_and_8_columns(tmp_path: Path) -> None:
    sheet = Image.new("RGBA", (16 * Q, 12 * Q))
    sheet.paste(coded_block(), (4 * Q, 6 * Q))  # block (1, 1) of a 2 x 2 block sheet
    a, b = tmp_path / "a" / "x_b3.png", tmp_path / "b" / "x_b3.png"
    tiles = a2.compose_atlas(sheet, 1, 1, TILE, a)
    a2.compose_atlas(sheet, 1, 1, TILE, b)
    assert a.read_bytes() == b.read_bytes()
    atlas = Image.open(a)
    assert atlas.size == (8 * TILE, 6 * TILE)
    assert atlas.crop((TILE, TILE, 2 * TILE, 2 * TILE)).tobytes() == tiles[9].tobytes()
    assert a2.block_is_empty(sheet, 0, 0, TILE) and not a2.block_is_empty(sheet, 1, 1, TILE)
    with pytest.raises(ValueError):
        a2.compose_block(sheet, 9, 9, TILE)


def test_assemble_adds_generated_atlas_assets_for_a2_blocks(tmp_path: Path) -> None:
    opened = archive.open_pack(SYNTH / "rpgmaker_like", set())
    inv = inventory.build_inventory(opened)
    cat, _issues, generated = catalog.assemble([(opened, inv)], None, [], work_dir=tmp_path / "w")
    schema.validate("catalog", cat.to_json())
    new = [a for a in cat.assets if a.pack_id == "generated"]
    assert new and all(a.path.startswith("generated/terrain_atlases/") for a in new)
    assert set(generated) >= {a.path for a in new}
    assert all(Path(generated[a.path]).is_file() for a in new)
    asset = new[0]
    facets = catalog.effective(asset)
    assert facets["tags"] == ["generated_terrain"] and facets["usage"] == "tiles"
    assert len(facets["tile_overrides"]) == 47
    set_name = facets["tile_overrides"]["0,0"]["terrain"]["set"]
    assert set_name.startswith("outside_a2_b")
    holder = next(t for t in cat.tilesets if any(s["asset"] == asset.id for s in t.sources))
    terrain_set = next(t for t in holder.terrain_sets if t["name"] == set_name)
    assert terrain_set["mode"] == "corners_and_sides" and len(terrain_set["terrains"]) == 1
    # the source sheet stays a plain atlas source
    source = cat.asset("rpgmaker_like.img.tilesets.outside_a2")
    assert source is not None and "tile_overrides" not in source.detected
    assert any(s["asset"] == source.id for t in cat.tilesets for s in t.sources)
    again = catalog.assemble([(opened, inv)], None, [], work_dir=tmp_path / "w2")[0]
    assert jsonio.dumps(again.to_json()) == jsonio.dumps(cat.to_json())


def test_a1_a3_a4_sheets_report_tile_006(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    (pack / "img" / "tilesets").mkdir(parents=True)
    (pack / "LICENSE.txt").write_text("CC0\n")
    for name in ("Outside_A2", "Outside_B"):
        shutil.copy(
            SYNTH / "rpgmaker_like" / "img" / "tilesets" / f"{name}.png", pack / "img" / "tilesets"
        )
    for name in ("Dungeon_A1", "Dungeon_A3", "Dungeon_A4"):
        shutil.copy(
            pack / "img" / "tilesets" / "Outside_A2.png", pack / "img" / "tilesets" / f"{name}.png"
        )
    opened = archive.open_pack(pack, set())
    _cat, issues, _gen = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], work_dir=tmp_path / "w"
    )
    reported = sorted(i.detail["asset"] for i in issues if i.code == "TILE-006")
    assert [r.rsplit(".", 1)[-1] for r in reported] == ["dungeon_a1", "dungeon_a3", "dungeon_a4"]

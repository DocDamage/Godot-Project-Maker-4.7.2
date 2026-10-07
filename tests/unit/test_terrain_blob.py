from __future__ import annotations

import random
from pathlib import Path

import pytest
from PIL import Image

from rpggen import schema
from rpggen.core import archive, catalog, inventory
from rpggen.core.terrain import blob
from rpggen.core.terrain import rpgmaker_a2 as a2

Q = 8
TILE = 2 * Q
KIND_COLORS = {
    "outer": (200, 40, 40, 255),
    "horizontal": (40, 200, 40, 255),
    "vertical": (40, 40, 200, 255),
    "center": (200, 200, 40, 255),
    "inner": (200, 40, 200, 255),
}


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def kind_block() -> Image.Image:
    """An A2 block whose quarters are colored by their *kind*, so neighbors join seamlessly."""
    img = Image.new("RGBA", (4 * Q, 6 * Q))
    for table in a2.QUARTER_TABLE.values():
        for kind, (qx, qy) in table.items():
            img.paste(KIND_COLORS[kind], (qx * Q, qy * Q, (qx + 1) * Q, (qy + 1) * Q))
    return img


def blob_sheet(columns: int = 12) -> Image.Image:
    tiles = a2.compose_block(kind_block(), 0, 0, TILE)
    sheet = Image.new("RGBA", (columns * TILE, 4 * TILE))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * TILE, (i // columns) * TILE))
    return sheet


def corner_sheet() -> Image.Image:
    """16 corner tiles; bit order TL=1, TR=2, BR=4, BL=8; an 'on' corner quarter is green."""
    on, off = (40, 200, 40, 255), (120, 90, 60, 255)
    sheet = Image.new("RGBA", (4 * TILE, 4 * TILE))
    for i in range(1, 16):  # tile 0 (no corners) stays empty
        for bit, dx, dy in ((1, 0, 0), (2, 1, 0), (4, 1, 1), (8, 0, 1)):
            x, y = (i % 4) * TILE + dx * Q, (i // 4) * TILE + dy * Q
            sheet.paste(on if i & bit else off, (x, y, x + Q, y + Q))
    return sheet


def test_recognizes_a_47_tile_blob_sheet() -> None:
    result = blob.recognize(blob_sheet(), TILE)
    assert result is not None and result.accepted and result.layout == blob.BLOB47
    assert result.confidence == 1.0 and result.expected > 100
    proposal, _ = blob.propose(blob_sheet(), TILE, TILE, "sheet_terrain")
    assert proposal is not None and len(proposal["tile_overrides"]) == 47
    assert proposal["mode"] == "corners_and_sides"
    assert proposal["terrain_set"]["name"] == "sheet_terrain"
    # same tiles and entries as the A2 composer's atlas, only laid out 12 columns wide
    expected = {
        f"{i % 12},{i // 12}": v
        for i, v in enumerate(a2.atlas_tile_overrides("sheet_terrain").values())
    }
    assert proposal["tile_overrides"] == expected
    assert set(proposal["tile_overrides"]["10,3"]["terrain"]["peering"].values()) == {0}  # mask 255


def test_recognizes_a_16_tile_corner_set() -> None:
    proposal, result = blob.propose(corner_sheet(), TILE, TILE, "c")
    assert result is not None and result.layout == blob.CORNERS16 and result.accepted
    assert proposal is not None and proposal["mode"] == "corners"
    assert "0,0" not in proposal["tile_overrides"]  # the empty tile
    peering = proposal["tile_overrides"]["3,0"]["terrain"]["peering"]  # index 3: TL and TR
    assert {k for k, v in peering.items() if v == 0} == {"top_left_corner", "top_right_corner"}
    assert peering["right_side"] == -1


def test_rejects_noise_and_flat_sheets() -> None:
    rng = random.Random(7)
    noise = Image.new("RGBA", (12 * TILE, 4 * TILE))
    noise.putdata(
        [
            (rng.randrange(256), rng.randrange(256), rng.randrange(256), 255)
            for _ in range(noise.width * noise.height)
        ]
    )
    result = blob.recognize(noise, TILE)
    assert result is not None and not result.accepted and result.confidence < 0.5
    assert blob.propose(noise, TILE, TILE, "n")[0] is None
    flat = Image.new("RGBA", (12 * TILE, 4 * TILE), (10, 200, 10, 255))
    assert not blob.recognize(flat, TILE).accepted  # all tiles alike
    assert not blob.recognize(Image.new("RGBA", (12 * TILE, 4 * TILE)), TILE).accepted
    assert blob.recognize(Image.new("RGBA", (5 * TILE, 3 * TILE)), TILE) is None  # no such layout


def shuffled_sheet() -> Image.Image:
    tiles = a2.compose_block(kind_block(), 0, 0, TILE)
    random.Random(3).shuffle(tiles)
    sheet = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 12) * TILE, (i // 12) * TILE))
    return sheet


def test_shuffled_tiles_are_not_recognized() -> None:
    sheet = shuffled_sheet()
    result = blob.recognize(sheet, TILE)
    assert result is not None and not result.accepted


def _pack(tmp_path: Path, name: str, sheet: Image.Image) -> Path:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "LICENSE.txt").write_text("CC0\n")
    sheet.save(pack / name)
    return pack


def _assemble(pack: Path):
    opened = archive.open_pack(pack, set())
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])


def test_assemble_stores_a_proposal_and_accept_moves_it_into_overrides(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "blob_terrain.png", blob_sheet())
    cat, issues, _gen = _assemble(pack)
    schema.validate("catalog", cat.to_json())
    asset = next(a for a in cat.assets if "terrain_proposal" in a.detected)
    assert not any(i.code == "TILE-006" for i in issues)
    assert "tile_overrides" not in catalog.effective(asset)  # a proposal is not applied
    assert blob.has_proposal(asset)

    accepted = blob.accept_proposal(asset)
    eff = catalog.effective(accepted)
    assert "terrain_proposal" not in eff and len(eff["tile_overrides"]) == 47
    assert accepted.overrides["terrain_proposal"] is None and accepted.status == "CONFIRMED"
    assert asset.overrides == {}  # copy on write

    rejected = blob.reject_proposal(asset)
    assert "terrain_proposal" not in catalog.effective(rejected)
    assert "tile_overrides" not in catalog.effective(rejected)

    in_catalog = blob.accept_in_catalog(cat, asset.id)
    schema.validate("catalog", in_catalog.to_json())
    holder = next(t for t in in_catalog.tilesets if any(s["asset"] == asset.id for s in t.sources))
    assert [t["name"] for t in holder.terrain_sets] == ["blob_terrain_terrain"]
    assert not blob.has_proposal(in_catalog.asset(asset.id))
    assert blob.accept_in_catalog(in_catalog, asset.id) is in_catalog  # nothing left to accept


def test_a_rejection_survives_a_new_analysis(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "blob_terrain.png", blob_sheet())
    cat, _issues, _gen = _assemble(pack)
    asset = next(a for a in cat.assets if "terrain_proposal" in a.detected)
    rejected = blob.reject_in_catalog(cat, asset.id)
    opened = archive.open_pack(pack, set())
    again = catalog.assemble([(opened, inventory.build_inventory(opened))], rejected, [])[0]
    assert not blob.has_proposal(again.asset(asset.id))


def test_assemble_reports_tile_006_for_a_hinted_sheet_that_fails(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "blob_terrain.png", shuffled_sheet())
    cat, issues, _gen = _assemble(pack)
    assert any(i.code == "TILE-006" for i in issues)
    assert not any(blob.has_proposal(a) for a in cat.assets)

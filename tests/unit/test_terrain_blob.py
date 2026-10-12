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


# ----------------------------------------------------------------- Godot's 3x3 minimal layout


def godot_sheet(grain: int = 0, seed: int = 5) -> Image.Image:
    """The 47 tiles in the order of Godot's 3x3 minimal template, the cell at 10,1 empty.
    With ``grain`` every pixel is off by up to that much: drawn art, not flat colour."""
    by_mask = dict(zip(a2.blob_masks(), a2.compose_block(kind_block(), 0, 0, TILE), strict=True))
    sheet = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, mask in enumerate(blob.GODOT_3X3_MINIMAL):
        if mask is not None:
            sheet.paste(by_mask[mask], ((i % 12) * TILE, (i // 12) * TILE))
    if grain:
        rng = random.Random(seed)
        sheet.putdata(
            [
                (*(max(0, min(255, c + rng.randint(-grain, grain))) for c in px[:3]), px[3])
                if px[3]
                else px
                for px in sheet.getdata()
            ]
        )
    return sheet


def test_the_godot_template_has_every_mask_once_and_one_empty_cell() -> None:
    masks = [m for m in blob.GODOT_3X3_MINIMAL if m is not None]
    assert len(blob.GODOT_3X3_MINIMAL) == 48 and sorted(masks) == a2.blob_masks()
    assert blob.GODOT_3X3_MINIMAL.index(None) == 1 * 12 + 10
    # the corners of the template: a tile with a neighbour below only, the full tile, a single
    assert blob.GODOT_3X3_MINIMAL[0] == a2.S and blob.GODOT_3X3_MINIMAL[36] == 0
    assert blob.GODOT_3X3_MINIMAL[2 * 12 + 9] == 255


def test_recognizes_a_sheet_in_godots_layout() -> None:
    proposal, result = blob.propose(godot_sheet(), TILE, TILE, "track_terrain")
    assert result is not None and result.accepted and result.layout == blob.BLOB47_GODOT
    assert result.confidence == 1.0 and result.contrast == 0.0
    assert proposal is not None and len(proposal["tile_overrides"]) == 47
    assert proposal["mode"] == "corners_and_sides" and "10,1" not in proposal["tile_overrides"]
    full = proposal["tile_overrides"]["9,2"]["terrain"]["peering"]
    assert set(full.values()) == {0}
    below_only = proposal["tile_overrides"]["0,0"]["terrain"]["peering"]
    assert {k for k, v in below_only.items() if v == 0} == {"bottom_side"}
    single = proposal["tile_overrides"]["0,3"]["terrain"]["peering"]
    assert set(single.values()) == {-1}
    # the other order of the same tiles is still told apart
    old = blob.recognize(blob_sheet(), TILE)
    assert old is not None and old.accepted and old.layout == blob.BLOB47


def test_drawn_art_is_recognized_by_how_much_better_its_seams_fit() -> None:
    """Grainy tiles never meet pixel for pixel, so the exact test fails; the seams that belong
    together still differ far less than the others."""
    grainy = godot_sheet(grain=30)
    result = blob.recognize(grainy, TILE)
    assert result is not None and result.layout == blob.BLOB47_GODOT
    assert result.matched < result.expected * blob.ACCEPT_RATIO, "the exact test alone would fail"
    assert result.accepted and result.contrast <= blob.CONTRAST_LIMIT
    assert blob.propose(grainy, TILE, TILE, "g")[0] is not None


def test_shuffled_grainy_tiles_and_noise_have_no_such_contrast() -> None:
    tiles = a2.compose_block(kind_block(), 0, 0, TILE)
    random.Random(11).shuffle(tiles)
    sheet = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 12) * TILE, (i // 12) * TILE))
    result = blob.recognize(sheet, TILE)
    assert result is not None and not result.accepted and result.contrast > blob.CONTRAST_LIMIT


def test_a_plain_ground_in_the_shape_of_an_autotile_sheet_is_no_failed_terrain(
    tmp_path: Path,
) -> None:
    flat = Image.new("RGBA", (12 * TILE, 4 * TILE), (10, 200, 10, 255))
    result = blob.recognize(flat, TILE)
    assert result is not None and result.flat and not result.accepted
    pack = _pack(tmp_path, "grass_autotile.png", flat)
    cat, issues, _gen = _assemble(pack)
    assert not any(i.code == "TILE-006" for i in issues), "nothing was skipped"
    assert not any(blob.has_proposal(a) for a in cat.assets)


def test_assemble_proposes_a_terrain_for_a_godot_sheet_in_a_tile_set_folder(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "wheels"
    (pack / "Tilesets").mkdir(parents=True)
    godot_sheet(grain=20).save(pack / "Tilesets" / "race_track_1.png")
    cat, issues, _gen = _assemble(pack)
    track = next(a for a in cat.assets if a.path.endswith("race_track_1.png"))
    assert catalog.effective(track)["usage"] == "tiles"
    proposal = catalog.effective(track)["terrain_proposal"]
    assert proposal["layout"] == blob.BLOB47_GODOT and len(proposal["tile_overrides"]) == 47
    assert not any(i.code == "TILE-006" for i in issues)
    accepted = blob.accept_in_catalog(cat, track.id)
    schema.validate("catalog", accepted.to_json())
    assert any(t.terrain_sets for t in accepted.tilesets)


# --------------------------------------------------------------- T17.01: fences, any-order corners

N, E, S, W = 1, 4, 16, 64


def fence_tile(sides: int, post: tuple[int, int, int, int] = (110, 78, 48, 255)) -> Image.Image:
    """A post in the middle and a rail to every side that joins: nothing at the corners."""
    tile = Image.new("RGBA", (TILE, TILE))
    rail = (150, 110, 70, 255)
    mid = TILE // 2
    for bit, box in (
        (N, (mid - 1, 0, mid + 1, mid)),
        (S, (mid - 1, mid, mid + 1, TILE)),
        (W, (0, mid - 1, mid, mid + 1)),
        (E, (mid, mid - 1, TILE, mid + 1)),
    ):
        if sides & bit:
            tile.paste(rail, box)
    tile.paste(post, (mid - 2, mid - 2, mid + 2, mid + 2))
    return tile


def fence_sheet(extra: tuple[int, ...] = (4, 5, 6, 7, 16, 17), leave: int = -1) -> Image.Image:
    """A fence in the cells of Godot's template: the sixteen cells whose masks have no corner,
    and ``extra`` cells drawn as other posts (22 tiles, as packs ship it). ``leave`` is one of
    the sixteen that is left out."""
    sheet = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, mask in enumerate(blob.GODOT_3X3_MINIMAL):
        if mask is None or i == leave:
            continue
        if mask & ~(N | E | S | W) == 0:
            tile = fence_tile(mask)
        elif i in extra:
            tile = fence_tile(mask & (N | E | S | W), (190, 190, 200, 255))
        else:
            continue
        sheet.paste(tile, ((i % 12) * TILE, (i // 12) * TILE))
    return sheet


def test_a_fence_sheet_is_a_sides_only_terrain() -> None:
    sheet = fence_sheet()
    filled = sum(
        1
        for i in range(48)
        if sheet.crop(
            ((i % 12) * TILE, (i // 12) * TILE, (i % 12 + 1) * TILE, (i // 12 + 1) * TILE)
        )
        .getchannel("A")
        .getbbox()
    )
    assert filled == 22
    proposal, result = blob.propose(sheet, TILE, TILE, "fence_terrain")
    assert result is not None and result.accepted and result.layout == blob.SIDES16_GODOT
    assert proposal is not None and proposal["mode"] == "sides"
    assert proposal["terrain_set"]["mode"] == "sides"
    # the sixteen combinations of sides once each, in the template's first four columns
    assert sorted(proposal["tile_overrides"]) == sorted(
        f"{x},{y}" for x in range(4) for y in range(4)
    )
    joined = {
        key: {k for k, v in entry["terrain"]["peering"].items() if v == 0}
        for key, entry in proposal["tile_overrides"].items()
    }
    assert len({frozenset(v) for v in joined.values()}) == 16
    assert joined["0,0"] == {"bottom_side"} and joined["0,3"] == set()  # masks 16 and 0
    assert joined["2,1"] == {"top_side", "right_side", "bottom_side", "left_side"}  # mask 85
    assert all(not k.endswith("_corner") for v in joined.values() for k in v)


def test_a_fence_drawn_into_other_cells_is_read_by_the_sides_of_their_masks() -> None:
    """Which cells a pack fills is its own business: a combination of sides that is missing
    from the first four columns is taken from a cell whose mask has corners as well."""
    index = blob.GODOT_3X3_MINIMAL.index(85)  # the crossing, mask N+E+S+W
    sheet = fence_sheet(leave=index)
    proposal, result = blob.propose(sheet, TILE, TILE, "f")
    assert result is not None and result.accepted and proposal is not None
    assert "2,1" not in proposal["tile_overrides"] and len(proposal["tile_overrides"]) == 15 + 1
    crossing = [
        k for k, e in proposal["tile_overrides"].items()
        if sum(1 for v in e["terrain"]["peering"].values() if v == 0) == 4
    ]  # fmt: skip
    assert crossing == ["4,0"], "mask 213: all four sides and three corners"
    assert not blob.recognize(fence_sheet(extra=(), leave=index), TILE).accepted, "15 of 16"


def test_pictures_in_the_cells_of_the_template_are_no_fence() -> None:
    icons = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i in range(22):  # 22 things that touch no edge: nothing joins, nothing to tell
        x, y = (i % 12) * TILE, (i // 12) * TILE
        icons.paste((40 + i * 9, 90, 200 - i * 5, 255), (x + 3, y + 3, x + 12 - i % 4, y + 12))
    result = blob.recognize(icons, TILE)
    assert result is not None and not result.accepted
    rng = random.Random(11)
    order = [i for i, m in enumerate(blob.GODOT_3X3_MINIMAL) if m is not None][:22]
    tiles = [fence_tile(blob.GODOT_3X3_MINIMAL[i] & (N | E | S | W)) for i in order]
    rng.shuffle(tiles)
    shuffled = Image.new("RGBA", (12 * TILE, 4 * TILE))
    for i, tile in zip(order, tiles, strict=True):
        shuffled.paste(tile, ((i % 12) * TILE, (i // 12) * TILE))
    assert not blob.recognize(shuffled, TILE).accepted
    # a 47-tile sheet that fails is not tried as a fence
    assert blob.recognize(shuffled_sheet(), TILE).layout != blob.SIDES16_GODOT


def drawn_corner_sheet(order: list[int], opaque: bool = False) -> Image.Image:
    """The 16 corner tiles over nothing, tile ``order[k]`` in cell ``k``."""
    on, off = (40, 200, 40, 255), ((120, 90, 60, 255) if opaque else (0, 0, 0, 0))
    sheet = Image.new("RGBA", (4 * TILE, 4 * TILE))
    for k, bits in enumerate(order):
        for bit, dx, dy in ((1, 0, 0), (2, 1, 0), (4, 1, 1), (8, 0, 1)):
            x, y = (k % 4) * TILE + dx * Q, (k // 4) * TILE + dy * Q
            sheet.paste(on if bits & bit else off, (x, y, x + Q, y + Q))
    return sheet


def test_a_corner_set_in_another_order_is_read_off_its_drawn_corners() -> None:
    order = list(range(16))
    random.Random(4).shuffle(order)
    assert order != list(range(16))
    proposal, result = blob.propose(drawn_corner_sheet(order), TILE, TILE, "c")
    assert result is not None and result.accepted and result.layout == blob.CORNERS16_DRAWN
    assert proposal is not None and proposal["mode"] == "corners"
    assert len(proposal["tile_overrides"]) == 15, "the tile without a corner is empty"
    names = (("top_left_corner", 1), ("top_right_corner", 2), ("bottom_right_corner", 4),
             ("bottom_left_corner", 8))  # fmt: skip
    for k, bits in enumerate(order):
        if not bits:
            continue
        peering = proposal["tile_overrides"][f"{k % 4},{k // 4}"]["terrain"]["peering"]
        assert {n for n, bit in names if bits & bit} == {n for n, v in peering.items() if v == 0}
    # the order the reader knew stays what it was called
    assert blob.recognize(drawn_corner_sheet(list(range(16))), TILE).layout == blob.CORNERS16


def test_an_opaque_corner_set_in_another_order_is_not_read() -> None:
    order = list(range(16))
    random.Random(4).shuffle(order)
    result = blob.recognize(drawn_corner_sheet(order, opaque=True), TILE)
    assert result is not None and not result.accepted, "its corners are all drawn: nothing to tell"


def test_assemble_proposes_a_sides_terrain_for_a_fence_sheet(tmp_path: Path) -> None:
    pack = tmp_path / "farm"
    (pack / "autotiles").mkdir(parents=True)
    fence_sheet().save(pack / "autotiles" / "03_fence.png")
    cat, issues, _gen = _assemble(pack)
    fence = next(a for a in cat.assets if a.path.endswith("03_fence.png"))
    proposal = catalog.effective(fence)["terrain_proposal"]
    assert proposal["layout"] == blob.SIDES16_GODOT and len(proposal["tile_overrides"]) == 16
    assert not any(i.code == "TILE-006" for i in issues)
    accepted = blob.accept_in_catalog(cat, fence.id)
    schema.validate("catalog", accepted.to_json())
    assert [t["mode"] for d in accepted.tilesets for t in d.terrain_sets] == ["sides"]

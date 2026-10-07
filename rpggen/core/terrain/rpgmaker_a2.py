"""RPG Maker A2 autotile blocks -> a 47-tile blob atlas with terrain peering (T8.06b).

An A2 sheet holds blocks of 2x3 tiles (MV/MZ: 96x144 px for 48 px tiles), 8 blocks across and 4
down. Everything is addressed in quarter-tiles (half-tile units): a block is 4 x 6 quarters.
Each of the 47 blob tiles is composed from four quarters chosen by the neighbors of the quarter.

Neighbor mask bits (clockwise from north): N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128.
The 47 normalized masks are ordered by mask value ascending; tile ``i`` of the atlas is the
``i``-th mask, placed at column ``i % 8``, row ``i // 8``.

The quarter table is taken from the task card and is NOT verified against a real sheet; use
``tools/debug_a2_sheet.py`` to look at the composed tiles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128
ATLAS_COLUMNS = 8
BLOCKS_PER_ROW = 8
BLOCK_TILES = (2, 3)  # tiles wide / high
TERRAIN_DIR = "generated/terrain_atlases"

# Quarter source coordinates (qx, qy) inside a block, per output quarter.
# kind order: outer corner, horizontal edge, vertical edge, center, inner corner
QUARTER_TABLE: dict[str, dict[str, tuple[int, int]]] = {
    "TL": {
        "outer": (0, 2),
        "horizontal": (2, 2),
        "vertical": (0, 4),
        "center": (2, 4),
        "inner": (2, 0),
    },
    "TR": {
        "outer": (3, 2),
        "horizontal": (1, 2),
        "vertical": (3, 4),
        "center": (1, 4),
        "inner": (3, 0),
    },
    "BL": {
        "outer": (0, 5),
        "horizontal": (2, 5),
        "vertical": (0, 3),
        "center": (2, 3),
        "inner": (2, 1),
    },
    "BR": {
        "outer": (3, 5),
        "horizontal": (1, 5),
        "vertical": (3, 3),
        "center": (1, 3),
        "inner": (3, 1),
    },
}
# (quarter, vertical neighbor bit, horizontal neighbor bit, diagonal bit, dx, dy in quarters)
QUARTERS = (
    ("TL", N, W, NW, 0, 0),
    ("TR", N, E, NE, 1, 0),
    ("BL", S, W, SW, 0, 1),
    ("BR", S, E, SE, 1, 1),
)


def normalize_mask(mask: int) -> int:
    """Clear a corner bit unless both adjacent side bits are set."""
    out = mask & (N | E | S | W)
    for corner, a, b in ((NE, N, E), (SE, S, E), (SW, S, W), (NW, N, W)):
        if mask & corner and mask & a and mask & b:
            out |= corner
    return out


def blob_masks() -> list[int]:
    """The 47 unique normalized 8-neighbor masks, ascending."""
    return sorted({normalize_mask(m) for m in range(256)})


def quarter_kind(vertical: bool, horizontal: bool, diagonal: bool) -> str:
    if vertical and horizontal:
        return "center" if diagonal else "inner"
    if vertical:
        return "vertical"
    if horizontal:
        return "horizontal"
    return "outer"


def quarter_sources(mask: int) -> dict[str, tuple[int, int]]:
    """Source quarter (qx, qy) inside the block for each output quarter of a tile."""
    out: dict[str, tuple[int, int]] = {}
    for name, v, h, d, _dx, _dy in QUARTERS:
        out[name] = QUARTER_TABLE[name][
            quarter_kind(bool(mask & v), bool(mask & h), bool(mask & d))
        ]
    return out


def peering_for_mask(mask: int, set_name: str, terrain: int = 0) -> dict[str, Any]:
    """``tile_overrides`` terrain entry (mode corners_and_sides) of a normalized mask."""
    m = normalize_mask(mask)
    bits = {
        "right_side": E,
        "bottom_right_corner": SE,
        "bottom_side": S,
        "bottom_left_corner": SW,
        "left_side": W,
        "top_left_corner": NW,
        "top_side": N,
        "top_right_corner": NE,
    }
    peering = {key: (terrain if m & bit else -1) for key, bit in bits.items()}
    return {"set": set_name, "terrain": terrain, "peering": peering}


def block_size(tile_w: int, tile_h: int | None = None) -> tuple[int, int]:
    return BLOCK_TILES[0] * tile_w, BLOCK_TILES[1] * (tile_h or tile_w)


def block_is_empty(sheet: Image.Image, block_x: int, block_y: int, tile_w: int) -> bool:
    bw, bh = block_size(tile_w)
    box = (block_x * bw, block_y * bh, (block_x + 1) * bw, (block_y + 1) * bh)
    if box[2] > sheet.width or box[3] > sheet.height:
        return True
    alpha = sheet.convert("RGBA").crop(box).getchannel("A")
    return alpha.getbbox() is None


def compose_block(sheet: Image.Image, block_x: int, block_y: int, tile_w: int) -> list[Image.Image]:
    """Compose the 47 blob tiles (ordered by normalized mask) of one A2 block."""
    if tile_w < 2 or tile_w % 2:
        raise ValueError("tile width must be an even number of pixels")
    q = tile_w // 2
    bw, bh = block_size(tile_w)
    x0, y0 = block_x * bw, block_y * bh
    if x0 + bw > sheet.width or y0 + bh > sheet.height:
        raise ValueError("block lies outside the sheet")
    block = sheet.convert("RGBA").crop((x0, y0, x0 + bw, y0 + bh))
    tiles: list[Image.Image] = []
    for mask in blob_masks():
        tile = Image.new("RGBA", (tile_w, tile_w), (0, 0, 0, 0))
        sources = quarter_sources(mask)
        for name, _v, _h, _d, dx, dy in QUARTERS:
            qx, qy = sources[name]
            piece = block.crop((qx * q, qy * q, (qx + 1) * q, (qy + 1) * q))
            tile.paste(piece, (dx * q, dy * q))
        tiles.append(tile)
    return tiles


def atlas_from_tiles(tiles: list[Image.Image], tile_w: int) -> Image.Image:
    rows = (len(tiles) + ATLAS_COLUMNS - 1) // ATLAS_COLUMNS
    atlas = Image.new("RGBA", (ATLAS_COLUMNS * tile_w, rows * tile_w), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        atlas.paste(tile, ((i % ATLAS_COLUMNS) * tile_w, (i // ATLAS_COLUMNS) * tile_w))
    return atlas


def save_png(img: Image.Image, out: Path) -> Path:
    """Deterministic PNG (no metadata, fixed compression)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    return out


def compose_atlas(
    sheet: Image.Image, block_x: int, block_y: int, tile_w: int, out: Path
) -> list[Image.Image]:
    """Write the 47-tile atlas (8 columns) of a block to ``out`` and return the tiles."""
    tiles = compose_block(sheet, block_x, block_y, tile_w)
    save_png(atlas_from_tiles(tiles, tile_w), out)
    return tiles


def atlas_tile_overrides(set_name: str) -> dict[str, Any]:
    """``tile_overrides`` of a composed atlas: peering per tile, keyed ``"col,row"``."""
    overrides: dict[str, Any] = {}
    for i, mask in enumerate(blob_masks()):
        overrides[f"{i % ATLAS_COLUMNS},{i // ATLAS_COLUMNS}"] = {
            "terrain": peering_for_mask(mask, set_name)
        }
    return overrides


# Deterministic terrain colors per block (picked by block index).
_COLORS = ("#4caf50", "#8d6e63", "#2196f3", "#ffc107", "#9c27b0", "#00bcd4", "#e91e63", "#795548")


def terrain_set_def(set_name: str, block_index: int) -> dict[str, Any]:
    return {
        "name": set_name,
        "mode": "corners_and_sides",
        "terrains": [{"name": set_name, "color": _COLORS[block_index % len(_COLORS)]}],
    }

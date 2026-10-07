"""Compose the 47 blob tiles of one RPG Maker A2 block into a labeled contact sheet.

Usage:
    python tools/debug_a2_sheet.py <a2.png> --block N --out sheet.png [--tile 48] [--scale 2]

``N`` counts blocks row by row (8 blocks per row in a 768 px wide MV/MZ sheet). Each tile is
labeled with its index and normalized neighbor mask (N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64,
NW=128). A human must compare the result with the real sheet: the quarter table in
``rpggen/core/terrain/rpgmaker_a2.py`` comes from the task card and is not verified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpggen.core.terrain import rpgmaker_a2 as a2  # noqa: E402

BACKGROUND = (48, 48, 48, 255)
LABEL = (255, 255, 255, 255)
LABEL_HEIGHT = 12
COLUMNS = a2.ATLAS_COLUMNS


def contact_sheet(sheet: Image.Image, block_index: int, tile_w: int, scale: int = 2) -> Image.Image:
    """The labeled contact sheet of one block (a PIL image)."""
    bw, bh = a2.block_size(tile_w)
    per_row = max(1, sheet.width // bw)
    tiles = a2.compose_block(sheet, block_index % per_row, block_index // per_row, tile_w)
    masks = a2.blob_masks()
    cell_w = tile_w * scale + 4
    cell_h = tile_w * scale + LABEL_HEIGHT + 4
    rows = (len(tiles) + COLUMNS - 1) // COLUMNS
    out = Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h), BACKGROUND)
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default_imagefont()
    for i, (tile, mask) in enumerate(zip(tiles, masks, strict=True)):
        x, y = (i % COLUMNS) * cell_w + 2, (i // COLUMNS) * cell_h + 2
        big = tile.resize((tile_w * scale, tile_w * scale), Image.Resampling.NEAREST)
        out.alpha_composite(big, (x, y))
        draw.text((x, y + tile_w * scale + 1), f"{i}:{mask}", fill=LABEL, font=font)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sheet", type=Path, help="an RPG Maker A2 sheet (PNG)")
    parser.add_argument("--block", type=int, default=0, help="block index, row by row")
    parser.add_argument("--out", type=Path, default=Path("a2_contact_sheet.png"))
    parser.add_argument("--tile", type=int, default=48, help="tile size in pixels (MV/MZ: 48)")
    parser.add_argument("--scale", type=int, default=2, help="preview magnification")
    args = parser.parse_args(argv)
    with Image.open(args.sheet) as opened:
        sheet = opened.convert("RGBA")
    result = contact_sheet(sheet, args.block, args.tile, args.scale)
    a2.save_png(result, args.out)
    print(f"wrote {args.out} ({result.width}x{result.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

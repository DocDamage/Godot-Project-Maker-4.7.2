"""Create deterministic synthetic asset packs for tests.

Usage: python tools/make_synthetic_packs.py --out test_packs/synthetic

Every pixel is drawn explicitly with integer coordinates (no antialiasing, no randomness) and
PNGs are saved without metadata, so two runs produce byte-identical files.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpggen import jsonio  # noqa: E402

Color = tuple[int, int, int, int]

GROUND_COLORS: list[Color] = [
    (76, 175, 80, 255),
    (139, 195, 74, 255),
    (121, 85, 72, 255),
    (158, 158, 158, 255),
    (205, 190, 112, 255),
    (96, 125, 139, 255),
    (62, 110, 60, 255),
    (183, 140, 90, 255),
]
WALL_FILL: Color = (64, 64, 64, 255)
WALL_BORDER: Color = (0, 0, 0, 255)
WATER: Color = (33, 150, 243, 255)
SAND: Color = (244, 220, 150, 255)
HERO_ROW_COLORS: list[Color] = [
    (200, 60, 60, 255),  # down
    (60, 140, 200, 255),  # left
    (60, 200, 100, 255),  # right
    (220, 180, 60, 255),  # up
]
EYE: Color = (255, 255, 255, 255)
BLACK: Color = (0, 0, 0, 255)


def _save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=False, compress_level=9, pnginfo=None)


def _terrain() -> Image.Image:
    img = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for col, color in enumerate(GROUND_COLORS):
        x = col * 16
        draw.rectangle([x, 0, x + 15, 15], fill=color)
    for col in range(8):
        x = col * 16
        draw.rectangle([x, 16, x + 15, 31], fill=WALL_BORDER)
        draw.rectangle([x + 1, 17, x + 14, 30], fill=WALL_FILL)
    draw.rectangle([0, 32, 15, 47], fill=WATER)
    draw.rectangle([16, 32, 31, 47], fill=SAND)
    return img


def _hero() -> Image.Image:
    img = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for row, color in enumerate(HERO_ROW_COLORS):
        for col in range(4):
            ox, oy = col * 16, row * 24
            draw.rounded_rectangle([ox + 3, oy + 5, ox + 12, oy + 22], radius=2, fill=color)
            ex = ox + 5 + col
            draw.rectangle([ex, oy + 9, ex + 1, oy + 10], fill=EYE)
            draw.line([ox + 3, oy + 23, ox + 12, oy + 23], fill=BLACK)
    return img


def make_basic16(out: Path) -> None:
    pack = out / "basic16"
    pack.mkdir(parents=True, exist_ok=True)
    with open(pack / "LICENSE.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "tiles" / "terrain.png")
    _save_png(_hero(), pack / "characters" / "hero.png")
    jsonio.write(
        out / "basic16.expected.json",
        {
            "tiles/terrain.png": {
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [0, 0],
                "nonempty": 18,
                "role": "GROUND",
            },
            "characters/hero.png": {
                "frame": [16, 24],
                "rows": ["down", "left", "right", "up"],
                "cols": 4,
                "role": "PLAYER",
                "baseline_y": 23,
            },
        },
    )


# M2 (T2.01) extends this registry with more packs.
PACKS: dict[str, Callable[[Path], None]] = {"basic16": make_basic16}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    for name in sorted(PACKS):
        PACKS[name](args.out)
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

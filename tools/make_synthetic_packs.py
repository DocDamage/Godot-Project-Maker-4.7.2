# ruff: noqa: E501
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


# ------------------------------------------------------------------------------------------
# M2 packs (T2.01)
# ------------------------------------------------------------------------------------------

ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def pal(i: int) -> Color:
    """Deterministic, well-separated palette (no randomness)."""
    return (60 + (i * 53) % 150, 60 + (i * 97) % 150, 60 + (i * 29) % 150, 255)


def _tile(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, i: int, step: int = 2) -> None:
    """A flat-ish tile: base colour with a horizontal gradient that is smooth inside the tile."""
    base = pal(i)
    for dx in range(w):
        shade = (dx * step) // 1
        color = (min(255, base[0] + shade), min(255, base[1] + shade // 2), base[2], 255)
        draw.line([(x + dx, y), (x + dx, y + h - 1)], fill=color)


def _write_json_ordered(path: Path, obj: object) -> None:
    """JSON with insertion order kept (needed for Aseprite's hash format)."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _png_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    return buf.getvalue()


def _write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    """Deterministic zip: stored (no compression), fixed timestamps, given entry order."""
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def _character(
    draw: ImageDraw.ImageDraw,
    ox: int,
    oy: int,
    fw: int,
    fh: int,
    color: Color,
    shift: int,
    baseline: int,
) -> None:
    """A bottom-aligned figure whose lowest occupied row is ``baseline`` (frame-relative)."""
    bw = max(6, fw * 5 // 8)
    x0 = ox + (fw - bw) // 2
    top = oy + max(2, baseline - (fh * 3) // 4)
    draw.rounded_rectangle([x0, top, x0 + bw - 1, oy + baseline - 1], radius=2, fill=color)
    ex = x0 + 2 + (shift % max(1, bw - 6))
    draw.rectangle([ex, top + 3, ex + 1, top + 4], fill=EYE)
    draw.line([x0, oy + baseline, x0 + bw - 1, oy + baseline], fill=BLACK)


def _expected(out: Path, name: str, data: dict) -> None:
    jsonio.write(out / f"{name}.expected.json", data)


def make_gutter32(out: Path) -> None:
    pack = out / "gutter32"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    w, h = 2 * 1 + 6 * 32 + 5 * 1, 2 * 1 + 5 * 32 + 4 * 1
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(5):
        for c in range(6):
            _tile(d, 1 + c * 33, 1 + r * 33, 32, 32, r * 6 + c, step=1)
    _save_png(img, pack / "tiles" / "world.png")
    _expected(
        out,
        "gutter32",
        {
            "tiles/world.png": {
                "usage": "tiles",
                "role": "GROUND",
                "cell": [32, 32],
                "margin": [1, 1],
                "separation": [1, 1],
            }
        },
    )


def make_gutterless48(out: Path) -> None:
    pack = out / "gutterless48"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    cols, rows = 5, 3
    img = Image.new("RGBA", (cols * 48, rows * 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    empty = {(4, 2), (3, 2)}
    for r in range(rows):
        for c in range(cols):
            if (c, r) in empty:
                continue
            _tile(d, c * 48, r * 48, 48, 48, r * cols + c + 3, step=2)
    _save_png(img, pack / "Tilesets" / "ground.png")
    _expected(
        out,
        "gutterless48",
        {
            "Tilesets/ground.png": {
                "usage": "tiles",
                "role": "GROUND",
                "cell": [48, 48],
                "margin": [0, 0],
                "separation": [0, 0],
            }
        },
    )


def _item_icon(i: int) -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = pal(i + 20)
    shape = i % 3
    if shape == 0:
        d.ellipse([3, 3, 12, 12], fill=color, outline=BLACK)
    elif shape == 1:
        d.polygon([(8, 2), (13, 8), (8, 13), (3, 8)], fill=color, outline=BLACK)
    else:
        d.rectangle([4, 4, 11, 11], fill=color, outline=BLACK)
    return img


def make_mixed(out: Path) -> None:
    pack = out / "mixed"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    img16 = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img16)
    for r in range(4):
        for c in range(8):
            _tile(d, c * 16, r * 16, 16, 16, r * 8 + c, step=2)
    _save_png(img16, pack / "tiles" / "ground16.png")
    img32 = Image.new("RGBA", (128, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img32)
    for r in range(3):
        for c in range(4):
            _tile(d, c * 32, r * 32, 32, 32, r * 4 + c + 40, step=2)
    _save_png(img32, pack / "tiles" / "ground32.png")
    bg = Image.new("RGBA", (512, 288), (0, 0, 0, 255))
    d = ImageDraw.Draw(bg)
    for y in range(288):
        for x in range(0, 512, 2):
            d.line([(x, y), (x + 1, y)], fill=(x * 255 // 511, y * 255 // 287, 160, 255))
    _save_png(bg, pack / "backgrounds" / "sky.png")
    for i in range(12):
        _save_png(_item_icon(i), pack / "items" / f"item_{i + 1:02d}.png")
    expected: dict[str, dict] = {
        "tiles/ground16.png": {
            "usage": "tiles",
            "role": "GROUND",
            "cell": [16, 16],
            "margin": [0, 0],
            "separation": [0, 0],
        },
        "tiles/ground32.png": {
            "usage": "tiles",
            "role": "GROUND",
            "cell": [32, 32],
            "margin": [0, 0],
            "separation": [0, 0],
        },
        "backgrounds/sky.png": {"usage": "background", "role": "BACKGROUND"},
    }
    for i in range(12):
        expected[f"items/item_{i + 1:02d}.png"] = {"usage": "sprite", "role": "ITEM"}
    _expected(out, "mixed", expected)


def _strip(frames: int, color_index: int, fw: int = 16, fh: int = 16) -> Image.Image:
    img = Image.new("RGBA", (frames * fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(frames):
        _character(d, i * fw, 0, fw, fh, pal(color_index), i, fh - 1)
    return img


def make_strips(out: Path) -> None:
    pack = out / "strips"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    for n, direction in enumerate(("down", "up", "left", "right")):
        _save_png(_strip(4, n), pack / f"hero_walk_{direction}.png")
    _save_png(_strip(3, 5), pack / "hero_attack_down.png")
    _save_png(_strip(4, 9), pack / "slime_idle.png")
    _expected(
        out,
        "strips",
        {
            # The hero group is one asset whose primary path is the first file in sorted order.
            "hero_attack_down.png": {
                "usage": "sprite",
                "role": "PLAYER",
                "anims": ["attack_down", "walk_down", "walk_left", "walk_right", "walk_up"],
            },
            "slime_idle.png": {"usage": "sprite", "role": "ENEMY", "anims": ["idle_down"]},
        },
    )


def make_rpgmaker_like(out: Path) -> None:
    pack = out / "rpgmaker_like"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    # Outside_A2.png: 768x576 (16x12 tiles of 48 px), every tile filled.
    a2 = Image.new("RGBA", (768, 576), (0, 0, 0, 0))
    d = ImageDraw.Draw(a2)
    for r in range(12):
        for c in range(16):
            _tile(d, c * 48, r * 48, 48, 48, r * 16 + c, step=2)
    _save_png(a2, pack / "img" / "tilesets" / "Outside_A2.png")
    # Outside_B.png: 768x768 (16x16 tiles), a sparse set of tiles.
    b = Image.new("RGBA", (768, 768), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    for r in range(16):
        for c in range(16):
            if (r * 7 + c * 3) % 5 in (0, 1):
                _tile(d, c * 48, r * 48, 48, 48, r * 16 + c + 7, step=2)
    _save_png(b, pack / "img" / "tilesets" / "Outside_B.png")
    # Actor1.png: 8 characters in a 4x2 arrangement of 3x4-frame blocks of 48x48.
    actor = Image.new("RGBA", (576, 384), (0, 0, 0, 0))
    d = ImageDraw.Draw(actor)
    for i in range(8):
        bx, by = (i % 4) * 144, (i // 4) * 192
        for row in range(4):
            for col in range(3):
                _character(d, bx + col * 48, by + row * 48, 48, 48, pal(i * 4 + row), col, 47)
    _save_png(actor, pack / "img" / "characters" / "Actor1.png")
    big = Image.new("RGBA", (144, 192), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    for row in range(4):
        for col in range(3):
            _character(d, col * 48, row * 48, 48, 48, pal(60 + row), col, 47)
    _save_png(big, pack / "img" / "characters" / "$Big.png")
    faces = Image.new("RGBA", (576, 288), (0, 0, 0, 0))
    d = ImageDraw.Draw(faces)
    for i in range(8):
        fx, fy = (i % 4) * 144, (i // 4) * 144
        d.rectangle([fx + 8, fy + 8, fx + 135, fy + 135], fill=pal(i + 70), outline=BLACK)
        d.ellipse([fx + 40, fy + 24, fx + 103, fy + 87], fill=(240, 210, 180, 255), outline=BLACK)
    _save_png(faces, pack / "img" / "faces" / "Actor1.png")
    _expected(
        out,
        "rpgmaker_like",
        {
            "img/tilesets/Outside_A2.png": {
                "usage": "tiles",
                "role": "AUTOTILE",
                "cell": [48, 48],
                "margin": [0, 0],
                "separation": [0, 0],
            },
            "img/tilesets/Outside_B.png": {
                "usage": "tiles",
                "role": "DECORATION",
                "cell": [48, 48],
                "margin": [0, 0],
                "separation": [0, 0],
            },
            "img/characters/Actor1.png#c0": {
                "usage": "sprite",
                "role": "PLAYER",
                "frame": [48, 48],
                "anims": ["idle_down", "walk_down", "walk_left", "walk_right", "walk_up"],
            },
            "img/characters/Actor1.png#c1": {"usage": "sprite", "role": "NPC", "frame": [48, 48]},
            "img/characters/$Big.png": {"usage": "sprite", "role": "NPC", "frame": [48, 48]},
            "img/faces/Actor1.png#f0": {"usage": "portrait", "role": "PORTRAIT"},
        },
    )


LPC_ROWS = [(7, "spellcast"), (8, "thrust"), (9, "walk"), (6, "slash"), (13, "shoot")]


def make_lpc_like(out: Path) -> None:
    pack = out / "lpc_like"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    img = Image.new("RGBA", (832, 1344), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    row = 0
    for count, _action in LPC_ROWS:
        for direction in range(4):
            for col in range(count):
                _character(d, col * 64, row * 64, 64, 64, pal(direction * 3 + 1), col, 60)
            row += 1
    for col in range(6):  # row 20: hurt
        _character(d, col * 64, 20 * 64, 64, 64, pal(50), col, 60)
    _save_png(img, pack / "characters" / "body.png")
    _expected(
        out,
        "lpc_like",
        {
            "characters/body.png": {
                "usage": "sprite",
                "role": "NPC",
                "frame": [64, 64],
                "baseline_y": 60,
                "anims": [
                    "attack_down",
                    "attack_left",
                    "attack_right",
                    "attack_up",
                    "death",
                    "hurt",
                    "idle_down",
                    "idle_left",
                    "idle_right",
                    "idle_up",
                    "walk_down",
                    "walk_left",
                    "walk_right",
                    "walk_up",
                ],
            }
        },
    )


TILED_POLY = "0,0 16,0 16,16"


def make_tiled_meta(out: Path) -> None:
    pack = out / "tiled_meta"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    img = Image.new("RGBA", (135, 135), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(8):
        for c in range(8):
            _tile(d, c * 17, r * 17, 16, 16, r * 8 + c, step=2)
    _save_png(img, pack / "tiles.png")
    tsx = """<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.2" name="ground" tilewidth="16" tileheight="16" spacing="1" margin="0" tilecount="64" columns="8">
 <image source="tiles.png" width="135" height="135"/>
 <tile id="5">
  <properties>
   <property name="footstep" value="grass"/>
   <property name="comment" value="ignored"/>
  </properties>
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="8" width="16" height="8"/>
  </objectgroup>
 </tile>
 <tile id="9">
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="0">
    <polygon points="0,0 16,0 16,16"/>
   </object>
  </objectgroup>
 </tile>
 <tile id="17">
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="0" width="16" height="16"/>
  </objectgroup>
 </tile>
 <wangsets>
  <wangset name="ground" type="corner" tile="-1">
   <wangcolor name="grass" color="#00ff00" tile="-1" probability="1"/>
   <wangcolor name="dirt" color="#aa5500" tile="-1" probability="1"/>
   <wangtile tileid="0" wangid="0,1,0,1,0,1,0,1"/>
   <wangtile tileid="1" wangid="0,2,0,2,0,2,0,2"/>
  </wangset>
 </wangsets>
</tileset>
"""
    _write_text(pack / "tiles.tsx", tsx)
    _expected(
        out,
        "tiled_meta",
        {
            "tiles.png": {
                "usage": "tiles",
                "role": "GROUND",
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [1, 1],
            }
        },
    )


ASE_FRAMES = [
    # (tag, trimmed w, trimmed h, duration ms)
    ("idle_down", 20, 30, 200),
    ("idle_down", 21, 30, 200),
    ("walk_down", 20, 29, 100),
    ("walk_down", 22, 30, 100),
    ("walk_down", 20, 28, 100),
    ("walk_down", 22, 30, 100),
    ("walk_side", 18, 30, 100),
    ("walk_side", 19, 29, 100),
    ("walk_side", 20, 30, 200),
    ("walk_side", 19, 28, 100),
]
ASE_SOURCE = (24, 32)


def make_aseprite_meta(out: Path) -> None:
    pack = out / "aseprite_meta"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    sheet_w = 96
    x = y = row_h = 0
    placed: list[tuple[int, int, int, int]] = []
    for _tag, w, h, _dur in ASE_FRAMES:  # shelf packing with a 1 px gap, no grid
        if x + w > sheet_w:
            x, y, row_h = 0, y + row_h + 1, 0
        placed.append((x, y, w, h))
        x += w + 1
        row_h = max(row_h, h)
    sheet_h = y + row_h
    img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    frames: dict[str, dict] = {}
    for i, ((_tag, w, h, dur), (fx, fy, _, _)) in enumerate(zip(ASE_FRAMES, placed, strict=True)):
        d.rounded_rectangle([fx, fy, fx + w - 1, fy + h - 1], radius=2, fill=pal(i + 11))
        d.rectangle([fx + 3 + i % 4, fy + 4, fx + 4 + i % 4, fy + 5], fill=EYE)
        ox = (ASE_SOURCE[0] - w) // 2
        oy = ASE_SOURCE[1] - h
        frames[f"knight {i}.aseprite"] = {
            "frame": {"x": fx, "y": fy, "w": w, "h": h},
            "rotated": False,
            "trimmed": True,
            "spriteSourceSize": {"x": ox, "y": oy, "w": w, "h": h},
            "sourceSize": {"w": ASE_SOURCE[0], "h": ASE_SOURCE[1]},
            "duration": dur,
        }
    _save_png(img, pack / "knight.png")
    tags = []
    start = 0
    for name in ("idle_down", "walk_down", "walk_side"):
        count = sum(1 for f in ASE_FRAMES if f[0] == name)
        tags.append(
            {
                "name": name,
                "from": start,
                "to": start + count - 1,
                "direction": "forward",
                "color": "#000000ff",
            }
        )
        start += count
    doc = {
        "frames": frames,
        "meta": {
            "app": "https://www.aseprite.org/",
            "version": "1.3.2",
            "image": "knight.png",
            "format": "RGBA8888",
            "size": {"w": sheet_w, "h": sheet_h},
            "scale": "1",
            "frameTags": tags,
            "layers": [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}],
            "slices": [],
        },
    }
    _write_json_ordered(pack / "knight.json", doc)
    _expected(
        out,
        "aseprite_meta",
        {
            "knight.png": {
                "usage": "sprite",
                "role": "NPC",
                "anims": ["idle_down", "walk_down", "walk_left", "walk_right"],
            }
        },
    )


# Objects inside town.png (pixel rects), used by the expected file and the region tests.
TOWN_HOUSE = [16, 16, 80, 64]
TOWN_TREE = [112, 0, 32, 48]


def make_objects_in_sheet(out: Path) -> None:
    pack = out / "objects_in_sheet"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    img = Image.new("RGBA", (160, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # house: 5x4 tiles at (16,16); roof is a trapezoid so the top cells are not fully opaque
    d.rectangle([16, 40, 95, 79], fill=(222, 184, 135, 255))
    for y in range(16, 40):
        inset = (39 - y) // 2
        d.line([(16 + inset, y), (95 - inset, y)], fill=(178, 34, 34, 255))
    d.rectangle([48, 56, 63, 79], fill=(101, 67, 33, 255))  # door
    d.rectangle([24, 48, 35, 59], fill=(135, 206, 235, 255))  # windows
    d.rectangle([76, 48, 87, 59], fill=(135, 206, 235, 255))
    # tree: crown across 2x2 tiles, trunk straddling the cell border below
    d.ellipse([112, 0, 143, 31], fill=(34, 139, 34, 255))
    d.rectangle([124, 32, 131, 47], fill=(101, 67, 33, 255))
    # scattered single tiles
    singles = [(0, 0), (9, 3), (0, 5), (6, 5), (9, 5), (0, 7), (2, 7), (4, 7), (6, 7), (8, 7)]
    for n, (cx, cy) in enumerate(singles):
        _tile(d, cx * 16, cy * 16, 16, 16, n + 30, step=2)
    _save_png(img, pack / "town.png")
    _expected(
        out,
        "objects_in_sheet",
        {
            "town.png": {
                "usage": "tiles",
                "role": "GROUND",
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [0, 0],
                "regions": [TOWN_TREE, TOWN_HOUSE],
            }
        },
    )


def _sign() -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 13, 8], fill=(160, 110, 60, 255), outline=BLACK)
    d.rectangle([7, 9, 8, 15], fill=(110, 70, 40, 255))
    return img


def _tree32() -> Image.Image:
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 2, 27, 21], fill=(34, 139, 34, 255), outline=BLACK)
    d.rectangle([14, 22, 17, 30], fill=(101, 67, 33, 255))
    return img


def make_weird_names(out: Path) -> None:
    """A zip with Unicode names, a case collision, a nested zip and macOS junk."""
    extra = _png_bytes(_sign())
    nested = out / "_weird_extra.tmp"
    _write_zip(nested, [("sign.png", extra)])
    nested_bytes = nested.read_bytes()
    nested.unlink()
    tree = _png_bytes(_tree32())
    _write_zip(
        out / "weird_names.zip",
        [
            ("LICENSE.txt", b"CC0-1.0 synthetic test pack\n"),
            ("Árbol Grande.png", _png_bytes(_tree32())),
            ("Tree.PNG", tree),
            ("tree.png", tree),
            ("extra.zip", nested_bytes),
            ("__MACOSX/._tree.png", b"junk"),
            (".DS_Store", b"junk"),
        ],
    )
    _expected(
        out,
        "weird_names",
        {
            "Tree.PNG": {"usage": "sprite", "role": "DECORATION"},
            "Árbol Grande.png": {"usage": "sprite"},
            "extra_extracted/sign.png": {"usage": "sprite", "role": "DECORATION"},
        },
    )


def make_zipped(out: Path) -> None:
    """The basic16 pack as a zip with the pack files at the archive root."""
    tmp = out / "_zipped_tmp"
    make_basic16(tmp)
    pack = tmp / "basic16"
    entries = [
        (p.relative_to(pack).as_posix(), p.read_bytes())
        for p in sorted(pack.rglob("*"), key=lambda q: q.relative_to(pack).as_posix())
        if p.is_file()
    ]
    _write_zip(out / "zipped.zip", entries)
    import shutil

    expected = jsonio.read(tmp / "basic16.expected.json")
    shutil.rmtree(tmp)
    _expected(out, "zipped", expected)


PACKS: dict[str, Callable[[Path], None]] = {
    "basic16": make_basic16,
    "gutter32": make_gutter32,
    "gutterless48": make_gutterless48,
    "mixed": make_mixed,
    "strips": make_strips,
    "rpgmaker_like": make_rpgmaker_like,
    "lpc_like": make_lpc_like,
    "tiled_meta": make_tiled_meta,
    "aseprite_meta": make_aseprite_meta,
    "objects_in_sheet": make_objects_in_sheet,
    "weird_names": make_weird_names,
    "zipped": make_zipped,
}


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

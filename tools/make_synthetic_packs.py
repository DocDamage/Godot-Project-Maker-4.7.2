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


def _frame(color_index: int, shift: int, fw: int = 16, fh: int = 16) -> Image.Image:
    img = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    _character(ImageDraw.Draw(img), 0, 0, fw, fh, pal(color_index), shift, fh - 1)
    return img


def make_sequences(out: Path) -> None:
    """One image per frame (T12.50): numbered, ``(n)``, a folder per animation, and a gap."""
    pack = out / "sequences"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    # numbers without zero padding: 10 must play after 9
    for i in range(10):
        _save_png(_frame(0, i), pack / f"hero_walk_down_{i + 1}.png")
    for i in range(4):
        _save_png(_frame(1, i), pack / f"hero_walk_up_{i + 1:02d}.png")
        _save_png(_frame(2, i), pack / f"hero_walk_side_{i + 1:02d}.png")
    for n, direction in enumerate(("down_left", "down_right", "up_left", "up_right")):
        for i in range(2):
            _save_png(_frame(3 + n, i), pack / f"hero_walk_{direction}_{i + 1:02d}.png")
    for i in range(3):
        _save_png(_frame(7, i), pack / f"hero-cast-{i + 1}.png")
    for i in range(4):
        _save_png(_frame(9, i), pack / "slime" / f"Idle ({i + 1}).png")
    for i in range(4):
        _save_png(_frame(10, i, 24, 24), pack / "enemies" / "bat" / "move" / f"{i + 1:04d}.png")
    for i in range(3):
        _save_png(_frame(11, i, 24, 24), pack / "enemies" / "bat" / "attack" / f"{i + 1:04d}.png")
    for number in (1, 2, 4):  # frame 3 is missing: ADAPT-004
        _save_png(_frame(12, number), pack / f"skeleton_idle_{number:02d}.png")
    # numbered files without an action word are variants, not frames
    for i in range(3):
        _save_png(_item_icon(i), pack / "items" / f"gem_{i + 1:02d}.png")
    expected: dict[str, dict] = {
        # The asset of a character is the first frame of its first sequence.
        "hero-cast-1.png": {
            "usage": "sprite",
            "role": "PLAYER",
            "frame": [16, 16],
            "anims": [
                "cast_down",
                "walk_down",
                "walk_down_left",
                "walk_down_right",
                "walk_left",
                "walk_right",
                "walk_up",
                "walk_up_left",
                "walk_up_right",
            ],
        },
        "slime/Idle (1).png": {"usage": "sprite", "role": "ENEMY", "anims": ["idle_down"]},
        "enemies/bat/attack/0001.png": {
            "usage": "sprite",
            "role": "ENEMY",
            "frame": [24, 24],
            "anims": ["attack_down", "walk_down"],
        },
        "skeleton_idle_01.png": {"usage": "sprite", "role": "ENEMY", "anims": ["idle_down"]},
    }
    for i in range(3):
        expected[f"items/gem_{i + 1:02d}.png"] = {"usage": "sprite", "role": "ITEM"}
    _expected(out, "sequences", expected)


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
                "anims": [
                    "idle_down",
                    "idle_left",
                    "idle_right",
                    "idle_up",
                    "walk_down",
                    "walk_left",
                    "walk_right",
                    "walk_up",
                ],
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


# Tiled and LDtk maps (T12.49). The compressed layers use stored blocks (level 0), which every zlib
# build writes alike, so the pack stays byte-identical across machines.
FLIP_H_GID, FLIP_V_GID, FLIP_D_GID = 0x80000000, 0x40000000, 0x20000000


def _gids_base64(gids: list[int], compression: str) -> str:
    import base64
    import gzip
    import struct
    import zlib

    raw = struct.pack(f"<{len(gids)}I", *gids)
    if compression == "gzip":
        # byte 9 of the header names the OS that wrote it (Windows 10, Unix 3): 255, "unknown",
        # keeps the pack byte-identical on every platform
        packed = bytearray(gzip.compress(raw, compresslevel=0, mtime=0))
        packed[9] = 255
        raw = bytes(packed)
    elif compression == "zlib":
        raw = zlib.compress(raw, 0)
    elif compression == "zstd":
        # written by hand, so the pack needs no Zstandard library and never changes with one:
        # the magic number, a single-segment frame header with a one-byte content size, and one
        # last raw block (3-byte header: size << 3 | last)
        assert len(raw) < 256
        header = bytes.fromhex("28b52ffd20") + bytes([len(raw)])
        raw = header + (len(raw) << 3 | 1).to_bytes(3, "little") + raw
    return base64.b64encode(raw).decode("ascii")


def _csv(gids: list[int], width: int) -> str:
    rows = [",".join(str(g) for g in gids[i : i + width]) for i in range(0, len(gids), width)]
    return "\n" + ",\n".join(rows) + "\n"


TERRAIN_TSX = """<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.2" name="terrain" tilewidth="16" tileheight="16" tilecount="32" columns="8">
 <image source="terrain.png" width="128" height="64"/>
</tileset>
"""


def make_tiled_map(out: Path) -> None:
    pack = out / "tiled_map"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "terrain.png")
    _write_text(pack / "terrain.tsx", TERRAIN_TSX)
    # town: 6 x 4, ground in CSV, walls in base64 + zlib (some of them flipped), three marker layers
    ground = [1] * 24
    ground[8], ground[9] = 18, 18  # sand
    walls = [9, 9, 9, 9, 9, 9]
    walls += [9 | FLIP_H_GID, 0, 0, 0, 0, 9 | FLIP_V_GID]
    walls += [9, 0, 0, 0, 0, 9 | FLIP_D_GID]
    walls += [9, 9, 9, 9, 9, 9]
    town = f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="6" height="4" tilewidth="16" tileheight="16" infinite="0" nextlayerid="6" nextobjectid="4">
 <tileset firstgid="1" source="../terrain.tsx"/>
 <layer id="1" name="Ground" width="6" height="4">
  <data encoding="csv">{_csv(ground, 6)}</data>
 </layer>
 <layer id="2" name="Walls" width="6" height="4">
  <data encoding="base64" compression="zlib">{_gids_base64(walls, "zlib")}</data>
 </layer>
 <objectgroup id="3" name="spawn">
  <object id="1" name="start" x="24" y="40"/>
 </objectgroup>
 <objectgroup id="4" name="door">
  <object id="2" name="to_cave" x="64" y="16" width="16" height="16">
   <properties>
    <property name="target_map" value="cave"/>
    <property name="target_spawn" value="default"/>
   </properties>
  </object>
 </objectgroup>
 <objectgroup id="5" name="Notices">
  <object id="3" name="notice" type="sign" x="40" y="24" width="16" height="16">
   <properties>
    <property name="text" value="Welcome to town"/>
   </properties>
  </object>
 </objectgroup>
</map>
"""
    _write_text(pack / "maps" / "town.tmx", town)
    # a JSON map with gzip data and a plain list
    cave = {
        "type": "map", "version": "1.10", "orientation": "orthogonal", "width": 3, "height": 2,
        "tilewidth": 16, "tileheight": 16, "infinite": False,
        "tilesets": [{"firstgid": 1, "source": "../terrain.tsx"}],
        "layers": [
            {
                "type": "tilelayer", "name": "Floor", "width": 3, "height": 2,
                "encoding": "base64", "compression": "gzip",
                "data": _gids_base64([1, 1, 1, 18, 1, 1], "gzip"),
            },
            {
                "type": "tilelayer", "name": "Plain", "width": 3, "height": 2,
                "data": [0, 9, 0, 0, 0, 0],
            },
        ],
    }  # fmt: skip
    _write_json_ordered(pack / "maps" / "cave.tmj", cave)
    # a layer saved with zstd (T13.14) is read like the others; one with a compression nobody
    # knows is skipped, the other layers are imported
    zstd = f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal" width="3" height="2" tilewidth="16" tileheight="16" infinite="0">
 <tileset firstgid="1" source="../terrain.tsx"/>
 <layer id="1" name="Ground" width="3" height="2">
  <data encoding="csv">1,1,1,
1,1,1</data>
 </layer>
 <layer id="2" name="Detail" width="3" height="2">
  <data encoding="base64" compression="zstd">{_gids_base64([0, 18, 0, 0, 0, 2], "zstd")}</data>
 </layer>
 <layer id="3" name="Lost" width="3" height="2">
  <data encoding="base64" compression="lz4">AAAAAA==</data>
 </layer>
</map>
"""
    _write_text(pack / "maps" / "zstd_layer.tmx", zstd)
    # an infinite map: chunks at negative coordinates, flattened to the bounds of the tiles
    chunk_a = [0, 0, 1, 1, 0, 0, 0, 0]
    chunk_b = [1, 9, 0, 0, 0, 0, 0, 1]
    infinite = f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal" tilewidth="16" tileheight="16" infinite="1">
 <tileset firstgid="1" source="../terrain.tsx"/>
 <layer id="1" name="Ground" width="0" height="0">
  <data encoding="csv">
   <chunk x="-4" y="-2" width="4" height="2">{_csv(chunk_a, 4)}</chunk>
   <chunk x="0" y="0" width="4" height="2">{_csv(chunk_b, 4)}</chunk>
  </data>
 </layer>
</map>
"""
    _write_text(pack / "maps" / "infinite.tmx", infinite)
    _expected(
        out,
        "tiled_map",
        {
            "terrain.png": {
                "usage": "tiles",
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [0, 0],
            }
        },
    )


def make_ldtk_level(out: Path) -> None:
    pack = out / "ldtk_level"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "terrain.png")
    walls = [1] * 6 + [1, 0, 0, 2, 2, 1] + [1, 0, 0, 0, 0, 1] + [1] * 6
    ground = []
    for y in range(4):
        for x in range(6):
            tile = {"px": [x * 16, y * 16], "src": [0, 0], "f": 0, "t": 0}
            if (x, y) == (2, 1):
                tile = {"px": [32, 16], "src": [0, 16], "f": 1, "t": 8}  # flipped in x
            if (x, y) == (3, 2):
                tile = {"px": [48, 32], "src": [16, 16], "f": 3, "t": 9}  # flipped in x and y
            ground.append(tile)

    def layer(identifier: str, kind: str, uid: int, **extra: object) -> dict:
        return {
            "__identifier": identifier, "__type": kind, "__cWid": 6, "__cHei": 4,
            "__gridSize": 16, "layerDefUid": uid, **extra,
        }  # fmt: skip

    def entity(identifier: str, iid: str, x: int, y: int, **fields: object) -> dict:
        return {
            "__identifier": identifier, "iid": iid, "px": [x, y], "width": 16, "height": 16,
            "fieldInstances": [{"__identifier": k, "__value": v} for k, v in fields.items()],
        }  # fmt: skip

    project = {
        "jsonVersion": "1.5.3",
        "defaultGridSize": 16,
        "defs": {
            "layers": [
                {"uid": 1, "identifier": "Entities", "type": "Entities"},
                {
                    "uid": 2, "identifier": "Collisions", "type": "IntGrid",
                    "intGridValues": [
                        {"value": 1, "identifier": "wall"},
                        {"value": 2, "identifier": "water"},
                    ],
                },
                {"uid": 3, "identifier": "Ground", "type": "Tiles"},
            ],
            "tilesets": [
                {
                    "uid": 10, "identifier": "Terrain", "relPath": "terrain.png",
                    "tileGridSize": 16, "spacing": 0, "padding": 0,
                }
            ],
        },
        "levels": [
            {
                "identifier": "Level_0", "uid": 100, "pxWid": 96, "pxHei": 64,
                "layerInstances": [
                    layer(
                        "Entities", "Entities", 1,
                        entityInstances=[
                            entity("Spawn", "0a1b2c3d", 24, 40),
                            entity("Sign", "1a2b3c4d", 56, 24, text="Hello"),
                            entity("Chest", "2a3b4c5d", 16, 16),
                        ],
                    ),
                    layer("Collisions", "IntGrid", 2, intGridCsv=walls, gridTiles=[], autoLayerTiles=[]),
                    layer(
                        "Ground", "Tiles", 3, __tilesetDefUid=10, __tilesetRelPath="terrain.png",
                        gridTiles=ground, autoLayerTiles=[],
                    ),
                ],
            }
        ],
    }  # fmt: skip
    _write_json_ordered(pack / "world.ldtk", project)
    _expected(
        out,
        "ldtk_level",
        {
            "terrain.png": {
                "usage": "tiles",
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [0, 0],
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
    "sequences": make_sequences,
    "rpgmaker_like": make_rpgmaker_like,
    "lpc_like": make_lpc_like,
    "tiled_meta": make_tiled_meta,
    "tiled_map": make_tiled_map,
    "ldtk_level": make_ldtk_level,
    "aseprite_meta": make_aseprite_meta,
    "objects_in_sheet": make_objects_in_sheet,
    "weird_names": make_weird_names,
    "zipped": make_zipped,
    "audio_basic": lambda out: make_audio_basic(out),
}


# ----------------------------------------------------------------------------- audio fixtures
# Hand-built headers, enough for the duration parser (rpggen.core.audio_info), not for players.


def wav_bytes(seconds: float, rate: int = 8000) -> bytes:
    """Silent 16-bit mono WAV of the given length."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def _ogg_page(kind: int, granule: int, seq: int, payload: bytes) -> bytes:
    import struct

    segments = [255] * (len(payload) // 255) + [len(payload) % 255]
    head = b"OggS" + bytes([0, kind]) + struct.pack("<qIII", granule, 1, seq, 0)
    return head + bytes([len(segments)]) + bytes(segments) + payload


def ogg_vorbis_bytes(seconds: float, rate: int = 22050) -> bytes:
    import struct

    ident = b"\x01vorbis" + struct.pack("<IBIiii", 0, 1, rate, 0, 64000, 0) + b"\xb8\x01"
    return _ogg_page(2, 0, 0, ident) + _ogg_page(4, int(seconds * rate), 1, b"\x00" * 40)


def ogg_opus_bytes(seconds: float, pre_skip: int = 312) -> bytes:
    import struct

    head = b"OpusHead" + bytes([1, 1]) + struct.pack("<HIhB", pre_skip, 48000, 0, 0)
    return _ogg_page(2, 0, 0, head) + _ogg_page(4, int(seconds * 48000) + pre_skip, 1, b"\x00" * 40)


def mp3_bytes(seconds: float, *, xing: bool = False, id3: bool = False) -> bytes:
    """CBR MPEG-1 Layer III, 128 kbit/s, 44.1 kHz stereo; optionally a Xing frame count."""
    frames = -(-int(seconds * 44100) // 1152)
    frame = b"\xff\xfb\x90\x00" + b"\x00" * 413  # 417 bytes
    out = b""
    if id3:  # an ID3v2 tag with 100 bytes of payload (synchsafe size)
        out += b"ID3\x03\x00\x00\x00\x00\x00\x64" + b"\x00" * 100
    if xing:
        tag = b"Xing" + (1).to_bytes(4, "big") + frames.to_bytes(4, "big")
        out += b"\xff\xfb\x90\x00" + b"\x00" * 32 + tag + b"\x00" * (413 - 32 - len(tag))
    return out + frame * frames


def flac_bytes(seconds: float, rate: int = 22050) -> bytes:
    total = int(seconds * rate)
    info = bytearray(34)
    info[0:2] = (4096).to_bytes(2, "big")
    info[2:4] = (4096).to_bytes(2, "big")
    packed = (rate << 44) | (0 << 41) | (15 << 36) | total  # rate:20 ch-1:3 bps-1:5 samples:36
    info[10:18] = packed.to_bytes(8, "big")
    return b"fLaC" + bytes([0x80, 0, 0, 34]) + bytes(info)


def make_audio_basic(out: Path) -> None:
    """basic16's images plus audio in three formats (wav, ogg, mp3), to check durations, roles and slot defaults."""
    pack = out / "audio_basic"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "tiles" / "terrain.png")
    _save_png(_hero(), pack / "characters" / "hero.png")
    files = {
        "music/overworld_theme.wav": wav_bytes(30.0, rate=2000),
        "music/battle_bgm.ogg": ogg_vorbis_bytes(24.0),
        "sfx/cursor_move.ogg": ogg_vorbis_bytes(0.4),
        "sfx/confirm.mp3": mp3_bytes(0.5),
        "sfx/hit.wav": wav_bytes(0.3),
        "sfx/chest_open.wav": wav_bytes(0.6),
    }
    for rel, data in files.items():
        target = pack / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # The .ogg stubs only have headers; Godot cannot load them. A real encoded file (made once
        # with ffmpeg, libvorbis, same length) that is already there is kept so the pack can be built.
        if target.suffix == ".ogg" and target.exists() and target.stat().st_size > 1000:
            continue
        target.write_bytes(data)
    expected = {
        "tiles/terrain.png": {"role": "GROUND"},
        "characters/hero.png": {"role": "PLAYER"},
        "music/overworld_theme.wav": {"role": "AUDIO_MUSIC"},
        "music/battle_bgm.ogg": {"role": "AUDIO_MUSIC"},
        "sfx/cursor_move.ogg": {"role": "AUDIO_SFX"},
        "sfx/confirm.mp3": {"role": "AUDIO_SFX"},
        "sfx/hit.wav": {"role": "AUDIO_SFX"},
        "sfx/chest_open.wav": {"role": "AUDIO_SFX"},
    }
    _expected(out, "audio_basic", expected)
    jsonio.write(
        out / "audio_basic.slots.json",
        {
            "music_map": "audio_basic.music.overworld_theme",
            "music_battle": "audio_basic.music.battle_bgm",
            "music_title": "audio_basic.music.overworld_theme",
            "sfx_ui_move": "audio_basic.sfx.cursor_move",
            "sfx_ui_confirm": "audio_basic.sfx.confirm",
            "sfx_hit": "audio_basic.sfx.hit",
            "sfx_chest": "audio_basic.sfx.chest_open",
        },
    )


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

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
    # the same file in a second folder: the catalog tags it as a duplicate of the first (T13.04)
    _save_png(_item_icon(0), pack / "items" / "spare" / "item_01.png")
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
    expected["items/spare/item_01.png"] = {"usage": "sprite", "role": "ITEM"}
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
                "anims": sorted(
                    [
                        "death",
                        "hurt",
                        *(
                            f"{action}_{direction}"
                            for action in ("attack", "cast", "idle", "shoot", "thrust", "walk")
                            for direction in ("down", "left", "right", "up")
                        ),
                    ]
                ),
            }
        },
    )


LPC_FILES = {  # the collection's animations: frames in a row, rows
    "walk": (9, 4), "slash": (6, 4), "hurt": (6, 1), "idle": (2, 4), "run": (8, 4),
    "jump": (5, 4), "climb": (6, 1), "spellcast": (7, 4),
}  # fmt: skip


def _lpc_file(action: str, color: int, band: tuple[int, int] = (0, 64)) -> Image.Image:
    """An animation of the collection: a figure in every cell. ``band`` keeps only the rows of
    each cell from its first to its second number: a layer covers a part of the body (hair its
    top, a shirt its middle), not all of it."""
    count, rows = LPC_FILES[action]
    img = Image.new("RGBA", (count * 64, rows * 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for row in range(rows):
        for col in range(count):
            _character(d, col * 64, row * 64, 64, 64, pal(color + row), col, 60)
        for top, bottom in ((0, band[0]), (band[1], 64)):
            if bottom > top:
                d.rectangle(
                    [0, row * 64 + top, img.width - 1, row * 64 + bottom - 1], fill=(0, 0, 0, 0)
                )
    return img


def make_lpc_parts(out: Path) -> None:
    """The LPC collection's shape (M16): a picture per animation for a body and for a layer,
    a folder per animation with a picture per colour, an oversize weapon sheet, and a
    universal sheet that goes on under the classic 21 rows."""
    pack = out / "lpc_parts"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    sheets = pack / "spritesheets"
    for action in LPC_FILES:
        _save_png(_lpc_file(action, 1), sheets / "body" / "bodies" / "male" / f"{action}.png")
    for action in ("walk", "slash", "hurt"):
        _save_png(
            _lpc_file(action, 9, (0, 26)), sheets / "hair" / "afro" / "adult" / f"{action}.png"
        )
        for n, colour in enumerate(("red", "blue")):
            shirt = sheets / "torso" / "clothes" / "shirt" / "male" / action / f"{colour}.png"
            _save_png(_lpc_file(action, 20 + 5 * n, (26, 46)), shirt)
    # a weapon drawn in 192 px frames: not the collection's 64 px layout
    big = Image.new("RGBA", (1152, 768), (0, 0, 0, 0))
    ImageDraw.Draw(big).rectangle([80, 80, 110, 110], fill=pal(40))
    _save_png(big, sheets / "weapon" / "blunt" / "mace" / "attack_slash" / "mace.png")
    # the generator's sheet: the classic rows, then climb (row 21) and idle (rows 22 to 25)
    full = Image.new("RGBA", (832, 26 * 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(full)
    for row, count in ((8, 9), (9, 9), (10, 9), (11, 9), (12, 6), (13, 6), (14, 6), (15, 6),
                       (20, 6), (21, 6), (22, 2), (23, 2), (24, 2), (25, 2)):  # fmt: skip
        for col in range(count):
            _character(d, col * 64, row * 64, 64, 64, pal(60 + row % 4), col, 60)
    _save_png(full, pack / "characters" / "guard.png")
    body = "spritesheets/body/bodies/male/walk.png"
    _expected(
        out,
        "lpc_parts",
        {
            body: {
                "usage": "sprite",
                "role": "NONE",  # it is in the character its hair makes with it
                "frame": [64, 64],
                "anims": sorted(
                    [
                        "climb_up",
                        "death",
                        "hurt",
                        *(
                            f"{action}_{direction}"
                            for action in ("attack", "cast", "idle", "jump", "run", "walk")
                            for direction in ("down", "left", "right", "up")
                        ),
                    ]
                ),
            },
            "spritesheets/hair/afro/adult/walk.png": {"usage": "sprite", "role": "NONE"},
            "spritesheets/torso/clothes/shirt/male/walk/red.png": {
                "usage": "sprite",
                "role": "NONE",
            },
            "spritesheets/torso/clothes/shirt/male/walk/blue.png": {
                "usage": "sprite",
                "role": "NONE",
            },
            "characters/guard.png": {
                "usage": "sprite",
                "role": "NPC",
                "frame": [64, 64],
                "anims": sorted(
                    [
                        "climb_up",
                        "death",
                        "hurt",
                        *(
                            f"{action}_{direction}"
                            for action in ("attack", "idle", "walk")
                            for direction in ("down", "left", "right", "up")
                        ),
                    ]
                ),
            },
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


# ------------------------------------------------------------------------------------------
# M14: a side-view pack (T14.02)
# ------------------------------------------------------------------------------------------

ROCK: Color = (92, 84, 110, 255)
ROCK_LIGHT: Color = (132, 122, 150, 255)
ROCK_DARK: Color = (58, 52, 74, 255)
MOSS: Color = (88, 150, 96, 255)
WOOD: Color = (150, 104, 58, 255)
WOOD_DARK: Color = (98, 64, 34, 255)
SPIKE: Color = (214, 214, 224, 255)


def _side_ground() -> Image.Image:
    """4 x 2 solid tiles: a mossy top row and a plain rock row."""
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for col in range(4):
        x = col * 16
        d.rectangle([x, 0, x + 15, 15], fill=ROCK)
        d.rectangle([x, 0, x + 15, 3], fill=MOSS)
        d.point([(x + 3 + col, 7), (x + 10 - col, 11)], fill=ROCK_LIGHT)
        d.rectangle([x, 16, x + 15, 31], fill=ROCK_DARK if col % 2 else ROCK)
        d.point([(x + 4, 20 + col), (x + 11, 27 - col)], fill=ROCK_LIGHT)
    return img


def _side_platform() -> Image.Image:
    """Three thin planks (left end, middle, right end): the top 5 px of each cell."""
    img = Image.new("RGBA", (48, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 47, 4], fill=WOOD)
    d.line([(0, 4), (47, 4)], fill=WOOD_DARK)
    d.line([(0, 0), (0, 4)], fill=WOOD_DARK)
    d.line([(47, 0), (47, 4)], fill=WOOD_DARK)
    for x in (15, 31):
        d.point([(x, 1), (x, 2)], fill=WOOD_DARK)
    return img


def _side_ladder() -> Image.Image:
    """Three ladder cells, one above the other."""
    img = Image.new("RGBA", (16, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([3, 0, 4, 47], fill=WOOD_DARK)
    d.rectangle([11, 0, 12, 47], fill=WOOD_DARK)
    for y in range(3, 48, 6):
        d.rectangle([3, y, 12, y + 1], fill=WOOD)
    return img


def _side_spikes() -> Image.Image:
    """Two spike cells: four teeth each, on a dark base."""
    img = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for col in range(2):
        x = col * 16
        d.rectangle([x, 13, x + 15, 15], fill=ROCK_DARK)
        for t in range(4):
            tx = x + t * 4
            d.polygon([(tx, 12), (tx + 1, 5 + col), (tx + 2, 5 + col), (tx + 3, 12)], fill=SPIKE)
    return img


def _side_strip(frames: int, color: Color, fw: int, fh: int, pose: str) -> Image.Image:
    """A strip of a figure facing right: a body, an eye on its right side, feet on the baseline.
    ``pose`` moves the body so that every animation has its own pixels."""
    img = Image.new("RGBA", (frames * fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(frames):
        ox = i * fw
        lift = {"jump": 3, "fall": 1, "climb": i % 2, "dash": 0}.get(pose, 0)
        lean = {"run": i % 2, "dash": 2, "attack": 1}.get(pose, 0)
        bw = max(6, fw * 5 // 8)
        x0 = ox + (fw - bw) // 2 + lean
        top = max(1, fh // 4 - lift)
        bottom = fh - 2 - lift
        d.rounded_rectangle([x0, top, x0 + bw - 1, bottom], radius=2, fill=color)
        d.rectangle([x0 + bw - 3, top + 3, x0 + bw - 2, top + 4], fill=EYE)
        d.line([x0 + 1, bottom + 1, x0 + bw - 2, bottom + 1], fill=BLACK)
        if pose == "attack" and i >= 1:
            d.line([x0 + bw, top + 5, min(ox + fw - 1, x0 + bw + 2 + i), top + 5], fill=EYE)
        if pose == "hurt":
            d.point([(x0 + 1, top + 1)], fill=(255, 80, 80, 255))
    return img


def _side_bench() -> Image.Image:
    img = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 7, 29, 9], fill=WOOD, outline=WOOD_DARK)
    d.rectangle([4, 10, 6, 15], fill=WOOD_DARK)
    d.rectangle([25, 10, 27, 15], fill=WOOD_DARK)
    d.point([(15, 4), (16, 3), (16, 5), (17, 4)], fill=(255, 236, 140, 255))
    return img


def _side_orb(i: int) -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = pal(31 + i * 7)
    d.ellipse([3, 3, 12, 12], fill=color, outline=BLACK)
    d.point([(6, 6), (7, 5)], fill=EYE)
    d.point([(8 + i, 9)], fill=BLACK)
    return img


def _side_background(depth: int) -> Image.Image:
    """A 320 x 180 layer: the farthest is an opaque sky, the nearer ones are hills with holes."""
    img = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if depth == 1:
        for y in range(180):
            d.line([(0, y), (319, y)], fill=(24 + y // 6, 22 + y // 8, 52 + y // 4, 255))
        return img
    base = 96 if depth == 2 else 132
    color = (52, 46, 78, 255) if depth == 2 else (34, 30, 52, 255)
    for x in range(320):
        wave = ((x * (5 - depth)) % 64) - 32
        height = base + abs(wave) // (4 - depth + 1)
        d.line([(x, height), (x, 179)], fill=color)
    return img


def make_platformer(out: Path) -> None:
    """A side-view pack: every part a metroidvania uses, named the way platformer packs name
    them, so that detection gives the tags, the roles and the pack's point of view."""
    pack = out / "platformer"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_side_ground(), pack / "tiles" / "ground.png")
    _save_png(_side_platform(), pack / "tiles" / "platforms" / "oneway_planks.png")
    _save_png(_side_ladder(), pack / "tiles" / "ladders" / "ladder.png")
    _save_png(_side_spikes(), pack / "tiles" / "hazards" / "spikes.png")
    hero = (214, 96, 64, 255)
    for action, frames in (
        ("idle", 2), ("run", 4), ("jump", 2), ("fall", 2), ("climb", 2), ("attack", 3), ("dash", 2),
    ):  # fmt: skip
        _save_png(
            _side_strip(frames, hero, 24, 24, action), pack / "characters" / f"hero_{action}.png"
        )
    _save_png(
        _side_strip(2, (96, 170, 90, 255), 16, 16, "run"), pack / "enemies" / "crawler_walk.png"
    )
    _save_png(
        _side_strip(2, (150, 90, 170, 255), 16, 16, "idle"), pack / "enemies" / "bat_idle.png"
    )
    for action, frames in (("idle", 2), ("walk", 2), ("attack", 2)):
        _save_png(
            _side_strip(
                frames, (190, 60, 80, 255), 32, 32, "attack" if action == "attack" else "idle"
            ),
            pack / "boss" / f"guardian_{action}.png",
        )
    _save_png(
        _side_strip(2, (90, 140, 210, 255), 24, 24, "idle"), pack / "npc" / "villager_idle.png"
    )
    _save_png(_side_bench(), pack / "objects" / "save_bench.png")
    _save_png(_sign(), pack / "objects" / "sign.png")
    for i in range(2):
        _save_png(_side_orb(i), pack / "items" / f"powerup_orb_{i + 1}.png")
    for depth, name in ((1, "far"), (2, "mid"), (3, "near")):
        _save_png(_side_background(depth), pack / "backgrounds" / f"bg_{name}.png")
    _expected(
        out,
        "platformer",
        {
            "tiles/ground.png": {
                "usage": "tiles",
                "role": "GROUND",
                "cell": [16, 16],
                "margin": [0, 0],
                "separation": [0, 0],
            },
            # the three sparse sheets are tiles by their tags, on the pack's grid (not by pixels)
            "tiles/platforms/oneway_planks.png": {"usage": "tiles", "role": "DECORATION"},
            "tiles/ladders/ladder.png": {"usage": "tiles", "role": "DECORATION"},
            "tiles/hazards/spikes.png": {"usage": "tiles", "role": "DECORATION"},
            "characters/hero_attack.png": {
                "usage": "sprite",
                "role": "PLAYER",
                "anims": [
                    "attack_down",
                    "climb_down",
                    "dash_down",
                    "fall_down",
                    "idle_down",
                    "jump_down",
                    "walk_down",
                ],
            },  # fmt: skip
            "enemies/crawler_walk.png": {"usage": "sprite", "role": "ENEMY"},
            "enemies/bat_idle.png": {"usage": "sprite", "role": "ENEMY"},
            "boss/guardian_attack.png": {"usage": "sprite", "role": "BOSS"},
            "npc/villager_idle.png": {"usage": "sprite", "role": "NPC"},
            "objects/save_bench.png": {"usage": "sprite", "role": "DECORATION"},
            "items/powerup_orb_1.png": {"usage": "sprite", "role": "ITEM"},
            "items/powerup_orb_2.png": {"usage": "sprite", "role": "ITEM"},
            "backgrounds/bg_far.png": {"usage": "background", "role": "BACKGROUND"},
            "backgrounds/bg_mid.png": {"usage": "background", "role": "BACKGROUND"},
            "backgrounds/bg_near.png": {"usage": "background", "role": "BACKGROUND"},
        },
    )


# ------------------------------------------------------------------------------------------
# What real packs look like (T16.21): a numbered frame export, one art for several engines, a
# bundle of packs.


def _blank(fw: int = 16, fh: int = 16) -> Image.Image:
    return Image.new("RGBA", (fw, fh), (0, 0, 0, 0))


def _sheet(size: int, cell: int, start: int) -> Image.Image:
    """An opaque sheet of ``cell`` px tiles, each in a colour of its own."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    per_row = size // cell
    for row in range(per_row):
        for col in range(per_row):
            _tile(draw, col * cell, row * cell, cell, cell, start + row * per_row + col, step=1)
    return img


def _numbered_frames(folder: Path, stem: str, runs: list[int], blanks: list[int], color: int,
                     form: str = "{0}{1}") -> int:  # fmt: skip
    """Frames ``<stem><n>.png``: ``runs`` of drawn frames with ``blanks[i]`` empty ones after
    run ``i``. Returns how many files were written."""
    number = 0
    for index, count in enumerate(runs):
        for i in range(count):
            number += 1
            _save_png(_frame(color + index, i), folder / (form.format(stem, number) + ".png"))
        for _ in range(blanks[index] if index < len(blanks) else 0):
            number += 1
            _save_png(_blank(), folder / (form.format(stem, number) + ".png"))
    return number


def make_frames_export(out: Path) -> None:
    """One picture per frame with no action word in any name: blank frames between the
    animations, the ``.aseprite`` source beside some of them, a preview folder and a test
    picture, and a folder name with a letter missing."""
    from rpggen.core.adapters import aseprite_file
    from rpggen.core.adapters.aseprite_file import Tag

    pack = out / "frames_export"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "TERRAIN" / "TERRAIN.png")
    # the hero: 15 frames, three animations, and the source that names them
    count = _numbered_frames(pack / "HERO", "HERO", [4, 5, 3], [1, 2], 0)
    tags = [
        Tag("Idle", 0, 3, "forward", 0),
        Tag("Run", 5, 9, "forward", 0),
        Tag("Attack", 12, 14, "forward", 1),
    ]
    source = aseprite_file.write(16, 16, [250] * 5 + [100] * 7 + [80] * 3, tags)
    assert count == 15
    (pack / "HERO" / "HERO.aseprite").write_bytes(source)
    # the slime: the same kind of export, and nothing that names its animations
    _numbered_frames(pack / "ENEMY" / "SLIME", "SLIME", [3, 4], [1], 5, form="{0} {1}")
    # a prop: six frames, no blank one; its source says they are frames
    _numbered_frames(pack / "PROPS" / "FLAME", "FLAME", [6], [], 8)
    (pack / "PROPS" / "FLAME" / "FLAME.aseprite").write_bytes(
        aseprite_file.write(16, 16, [125] * 6, [])
    )
    # numbered pictures that are not frames: three coins, nothing says animation
    for i in range(3):
        _save_png(_item_icon(i), pack / "PROPS" / "COIN" / f"COIN{i + 1}.png")
    # two background layers beside the one-frame file they were drawn in
    for n in (1, 2):
        sky = Image.new("RGBA", (256, 256), pal(20 + n))
        _save_png(sky, pack / "BACKGROUD" / f"BACKGROUND ({n}) .png")
    (pack / "BACKGROUD" / "BACKGROUND.aseprite").write_bytes(
        aseprite_file.write(256, 256, [100], [])
    )
    _save_png(Image.new("RGBA", (64, 48), pal(30)), pack / "PREVIEW" / "Preview (1).png")
    _save_png(Image.new("RGBA", (64, 48), pal(31)), pack / "test.png")
    _expected(
        out,
        "frames_export",
        {
            "TERRAIN/TERRAIN.png": {"usage": "tiles", "role": "GROUND"},
            "HERO/HERO1.png": {
                "usage": "sprite",
                "role": "PLAYER",
                "frame": [16, 16],
                "anims": ["attack_down", "idle_down", "walk_down"],
            },
            "ENEMY/SLIME/SLIME 1.png": {
                "usage": "sprite",
                "role": "ENEMY",
                "anims": ["anim_1", "anim_2"],
            },
            "PROPS/FLAME/FLAME1.png": {
                "usage": "sprite",
                "role": "DECORATION",
                "anims": ["idle_down"],
            },
            "PROPS/COIN/COIN1.png": {"usage": "sprite"},
            "PROPS/COIN/COIN3.png": {"usage": "sprite"},
            "BACKGROUD/BACKGROUND (1) .png": {"usage": "background", "role": "BACKGROUND"},
            "BACKGROUD/BACKGROUND (2) .png": {"usage": "background", "role": "BACKGROUND"},
            "PREVIEW/Preview (1).png": {"role": "NONE"},
            "test.png": {"role": "NONE"},
        },
    )


def _blob_sheet(color: int) -> Image.Image:
    """192 x 64: the 12 x 4 layout of a 47-tile autotile, every tile drawn."""
    img = Image.new("RGBA", (192, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for row in range(4):
        for col in range(12):
            _tile(draw, col * 16, row * 16, 16, 16, color, step=1)
            draw.rectangle(
                [col * 16 + 4, row * 16 + 4, col * 16 + 11, row * 16 + 11], fill=pal(color + 7)
            )
    return img


def make_multi_engine(out: Path) -> None:
    """One art laid out for five engines, with sizes and frame counts in the file names, the
    colours of an animal as folders, and the files a pack carries that are no assets."""
    pack = out / "multi_engine"
    _write_text(pack / "info" / "License.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_terrain(), pack / "assets" / "tiles" / "ground_16x16.png")
    for n, colour in enumerate(("brown", "black", "black_white")):
        folder = pack / "assets" / "animals" / "cows" / "cow_01" / colour
        stem = f"cow_01_{colour}"
        _save_png(_strip(4, 3 + n), folder / "move" / f"{stem}_move_down_16x16_4frames.png")
        _save_png(_strip(2, 3 + n), folder / "sleep" / f"{stem}_sleep_16x16_2frames.png")
    _save_png(_strip(8, 12, 16, 32), pack / "assets" / "crops" / "corn_16x32_8frames.png")
    _save_png(_strip(5, 13, 16, 32), pack / "assets" / "crops" / "wheat_growth_16x32_5frames.png")
    raw = Image.new("RGBA", (16, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(raw)
    for row in range(6):
        _tile(draw, 0, row * 16, 16, 16, 40 + row, step=1)
    _save_png(raw, pack / "assets" / "autotiles" / "01_grass.png")
    godot = pack / "engines" / "Godot" / "autotiles"
    _save_png(_blob_sheet(40), godot / "3x3" / "01_grass.png")
    _save_png(_sheet(64, 16, 40), godot / "2x2" / "01_grass.png")
    for index, engine in enumerate(("RPG_Maker_MV_MZ", "RPG_Maker_VX_VXace", "RPG_Maker_XP")):
        _save_png(_sheet(96, 16, 50 + index), pack / "engines" / engine / "tiles" / "grass.png")
    _save_png(_sheet(80, 16, 60).crop((0, 0, 16, 80)), pack / "engines" / "Unity" / "grass.png")
    (pack / "assets" / "crops" / "In development").write_bytes(b"")
    _write_text(pack / "Please_rate.html", "<html><body>rate this pack</body></html>\n")
    junk = pack / "assets" / "__MACOSX"
    junk.mkdir(parents=True, exist_ok=True)
    (junk / "._ground_16x16.png").write_bytes(b"junk")
    cows = "assets/animals/cows/cow_01"
    expected: dict[str, dict] = {
        "assets/tiles/ground_16x16.png": {"usage": "tiles", "role": "GROUND"},
        # a crop's stages in a row are a growth strip, not an animation (T17.01): a CROP
        "assets/crops/corn_16x32_8frames.png": {
            "usage": "growth_strip",
            "role": "CROP",
            "frame": [16, 32],
        },
        "assets/crops/wheat_growth_16x32_5frames.png": {
            "usage": "growth_strip",
            "role": "CROP",
            "frame": [16, 32],
        },
        "engines/Godot/autotiles/3x3/01_grass.png": {"usage": "tiles"},
        "engines/Godot/autotiles/2x2/01_grass.png": {"role": "NONE"},
        "assets/autotiles/01_grass.png": {"role": "NONE"},
        "engines/Unity/grass.png": {"role": "NONE"},
    }
    for engine in ("RPG_Maker_MV_MZ", "RPG_Maker_VX_VXace", "RPG_Maker_XP"):
        expected[f"engines/{engine}/tiles/grass.png"] = {"role": "NONE"}
    for colour in ("brown", "black", "black_white"):
        expected[f"{cows}/{colour}/move/cow_01_{colour}_move_down_16x16_4frames.png"] = {
            "usage": "sprite",
            "role": "ANIMAL",  # a farm animal, not a villager (T17.02)
            "frame": [16, 16],
            "anims": ["walk_down"],
        }
        expected[f"{cows}/{colour}/sleep/cow_01_{colour}_sleep_16x16_2frames.png"] = {
            "usage": "sprite",
            "role": "ANIMAL",
            "anims": ["sleep_down"],
        }
    _expected(out, "multi_engine", expected)


BUNDLE_THEMES = (
    "Abandoned Hospital", "Alien Jungle", "Backrooms", "Cyberpunk City", "Desert Ruins",
    "Haunted Manor", "Medieval Fantasy Town", "Modern Gym", "Monder Interiors", "Pirate Cove",
    "Space Station", "WW1 Trench & Bunker",
)  # fmt: skip


def make_bundle(out: Path) -> None:
    """A zip that is a bundle: twelve pack folders under one top folder, their sheets named by a
    number only (with a gap), one of them with five 768 px sheets, one with what a
    sprite-cutting tool left in it."""
    import json

    top = "Bundle"
    entries: list[tuple[str, bytes]] = [(f"{top}/LICENSE.txt", b"CC0-1.0 synthetic test pack\n")]
    expected: dict[str, dict] = {}
    for index, theme in enumerate(BUNDLE_THEMES):
        suffix = " Tileset" if index % 3 == 0 else " Pixel Art Tileset Pack"
        folder = f"{top}/{theme}{suffix}"
        if theme == "Medieval Fantasy Town":  # five numbered sheets are five tile sheets
            for n in (1, 2, 3, 5, 6):
                sheet = _sheet(768, 48, 100 + n * 16)
                entries.append((f"{folder}/{n}.png", _png_bytes(sheet)))
                expected[f"{folder}/{n}.png"] = {"usage": "tiles"}
            continue
        for n in (1, 3):  # 2 is missing: a gap in the numbers of sheets is nothing
            data = _png_bytes(_sheet(256, 32, index * 16 + n))
            entries.append((f"{folder}/{n}.png", data))
            expected[f"{folder}/{n}.png"] = {"usage": "tiles"}
        if theme == "Abandoned Hospital":  # the output of a sprite cutter, with its manifest
            cut = f"{folder}/_organized_sprites"
            sprites = [
                ("sheet_01_beds_001", "sheet_01", "beds", 0, 0, 64, 32),
                ("sheet_01_carts_001", "sheet_01", "carts", 64, 0, 32, 32),
                ("sheet_03_beds_001", "sheet_03", "beds", 32, 64, 64, 64),
            ]
            manifest = [
                {
                    "id": name,
                    "source_sheet": sheet,
                    "source_file": "G:/Packs/" + theme + f" Tileset/{int(sheet[-2:])}.png",
                    "category": category,
                    "bbox": {"x": x, "y": y, "width": w, "height": h},
                }
                for name, sheet, category, x, y, w, h in sprites
            ]
            text = json.dumps(manifest, indent=2) + "\n"
            entries.append((f"{cut}/manifest/sprites.json", text.encode("utf-8")))
            for name, _sheet_name, category, _x, _y, w, h in sprites:
                picture = _png_bytes(Image.new("RGBA", (w, h), pal(len(entries))))
                entries.append((f"{cut}/sprites/{category}/{name}.png", picture))
                expected[f"{cut}/sprites/{category}/{name}.png"] = {"role": "NONE"}
            preview = _png_bytes(Image.new("RGBA", (128, 96), pal(77)))
            entries.append((f"{cut}/previews/sheet_01_contact.png", preview))
            expected[f"{cut}/previews/sheet_01_contact.png"] = {"role": "NONE"}
    # (The grids of these sheets are asserted in tests/unit/test_real_pack_shapes.py: the
    # expected file's "cell" is for the grid detector alone, and a numbered sheet gets its
    # grid from its size and its folder.)
    _write_zip(out / "bundle.zip", sorted(entries))
    _expected(out, "bundle", expected)


# ------------------------------------------------------------------------------------------
# The arcade kinds (T16.02): a shoot 'em up, a run and gun, a racing game.


def _turned(points: list[tuple[float, float]], turn: float, cx: float, cy: float) -> list[tuple[int, int]]:  # fmt: skip
    """``points`` (around 0,0; y down) turned clockwise by ``turn`` of a full turn, about
    ``cx, cy``, as whole pixels. The quarter turns are exact; the others are rounded from a
    value that is never near a half, so every machine draws the same pixels."""
    import math

    quarter = round(turn * 4)
    if abs(turn * 4 - quarter) < 1e-9:
        cos, sin = ((1, 0), (0, 1), (-1, 0), (0, -1))[quarter % 4]
    else:
        cos, sin = math.cos(turn * 2 * math.pi), math.sin(turn * 2 * math.pi)
    return [
        (int(math.floor(cx + x * cos - y * sin + 0.5)), int(math.floor(cy + x * sin + y * cos + 0.5)))
        for x, y in points
    ]  # fmt: skip


def _vehicle_ring(headings: int, cell: int, body: Color, roof: Color) -> Image.Image:
    """One vehicle seen from above in ``headings`` views in a row, the first pointing up, each
    turned clockwise by one step from the one before."""
    img = Image.new("RGBA", (headings * cell, cell), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    half = cell / 2 - 0.25
    w, length = cell * 0.23, cell * 0.41
    hull = [(-w, -length * 0.6), (0.0, -length), (w, -length * 0.6), (w, length), (-w, length)]
    cabin = [(-w * 0.6, -length * 0.15), (w * 0.6, -length * 0.15), (w * 0.6, length * 0.55),
             (-w * 0.6, length * 0.55)]  # fmt: skip
    for k in range(headings):
        cx = k * cell + half
        d.polygon(_turned(hull, k / headings, cx, half), fill=body, outline=BLACK)
        d.polygon(_turned(cabin, k / headings, cx, half), fill=roof)
    return img


def _ship(color: Color, size: int = 24, lean: int = 0) -> Image.Image:
    """A ship seen from above, its nose up; ``lean`` shifts the nose for a banking frame."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mid = size // 2
    d.polygon([(mid + lean, 1), (size - 3, size - 4), (mid, size - 7), (2, size - 4)], fill=color,
              outline=BLACK)  # fmt: skip
    d.rectangle([mid - 1, size // 3, mid, size // 3 + 3], fill=EYE)
    return img


def _burst(frames: int, size: int) -> Image.Image:
    """An explosion strip: a ring that grows and thins from frame to frame."""
    img = Image.new("RGBA", (frames * size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(frames):
        cx, cy = i * size + size // 2, size // 2
        r = 2 + i * (size // 2 - 3) // max(1, frames - 1)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 200 - i * 24, 40, 255))
        hole = r - max(1, (frames - i) * r // frames)
        if hole > 0:
            d.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0))
    return img


def _space(far: bool) -> Image.Image:
    """A background taller than wide, to scroll down: an opaque sky, or stars with holes."""
    img = Image.new("RGBA", (128, 256), (8, 8, 24, 255) if far else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(40):
        x, y = (i * 37) % 128, (i * 91) % 256
        d.point((x, y), fill=(200, 200, 255, 255) if far else (255, 255, 210, 255))
        if not far:
            d.rectangle([x, y, x + 1, y + 1], fill=(255, 255, 210, 255))
    return img


def _small(color: Color, size: int = 16, shape: str = "box") -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shape == "round":
        d.ellipse([2, 2, size - 3, size - 3], fill=color, outline=BLACK)
    elif shape == "cone":
        d.polygon([(size // 2, 1), (size - 3, size - 2), (2, size - 2)], fill=color, outline=BLACK)
    elif shape == "thin":
        d.rectangle([size // 2 - 1, 2, size // 2, size - 3], fill=color)
    else:
        d.rectangle([2, 4, size - 3, size - 5], fill=color, outline=BLACK)
    return img


def make_shooter(out: Path) -> None:
    """What a shoot 'em up pack holds, named the way such packs name it."""
    pack = out / "shooter"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    hero = (90, 170, 230, 255)
    bank = Image.new("RGBA", (72, 24), (0, 0, 0, 0))
    for i, lean in enumerate((-3, 0, 3)):
        bank.paste(_ship(hero, 24, lean), (i * 24, 0))
    _save_png(bank, pack / "ships" / "player_ship.png")
    for i in range(5):
        _save_png(_ship(pal(i + 3), 24).transpose(Image.Transpose.FLIP_TOP_BOTTOM),
                  pack / "enemies" / f"enemy_ship_{i + 1}.png")  # fmt: skip
    _save_png(_small((255, 240, 120, 255), 8, "thin"), pack / "bullets" / "bullet.png")
    _save_png(_small((255, 90, 90, 255), 8, "thin"), pack / "bullets" / "laser.png")
    _save_png(_burst(6, 24), pack / "fx" / "explosion_6frames.png")
    _save_png(_small(pal(9), 24, "round"), pack / "asteroids" / "asteroid_1.png")
    _save_png(_space(True), pack / "backgrounds" / "space_far.png")
    _save_png(_space(False), pack / "backgrounds" / "space_near.png")
    _save_png(_ship((200, 60, 90, 255), 48).transpose(Image.Transpose.FLIP_TOP_BOTTOM),
              pack / "boss" / "boss_ship.png")  # fmt: skip
    for i in range(3):
        _save_png(_small(pal(20 + i), 16, "round"), pack / "powerups" / f"capsule_{i + 1}.png")
    expected: dict[str, dict] = {
        "ships/player_ship.png": {"usage": "sprite", "frame": [24, 24]},
        "bullets/bullet.png": {"usage": "sprite", "role": "PROJECTILE"},
        "bullets/laser.png": {"usage": "sprite", "role": "PROJECTILE"},
        "fx/explosion_6frames.png": {"usage": "sprite", "role": "EXPLOSION", "frame": [24, 24]},
        "backgrounds/space_far.png": {"usage": "background", "role": "BACKGROUND"},
        "boss/boss_ship.png": {"usage": "sprite", "role": "BOSS"},
    }
    for i in range(5):
        expected[f"enemies/enemy_ship_{i + 1}.png"] = {"usage": "sprite", "role": "ENEMY"}
    _expected(out, "shooter", expected)


def make_gunner(out: Path) -> None:
    """What a run and gun pack holds: a soldier in strips, enemies, a turret, a boss, side
    tiles, two background layers, weapon pickups and a hook."""
    pack = out / "gunner"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_side_ground(), pack / "tiles" / "ground.png")
    soldier = (96, 150, 90, 255)
    for action, frames in (("idle", 2), ("run", 4), ("jump", 2), ("shoot", 3)):
        pose = action if action in ("idle", "run", "jump") else "attack"
        _save_png(_side_strip(frames, soldier, 24, 24, pose), pack / "soldier" / f"soldier_{action}.png")  # fmt: skip
    for i, name in enumerate(("trooper", "gunner", "commando")):
        _save_png(_side_strip(2, pal(30 + i), 24, 24, "run"), pack / "enemies" / f"{name}_walk.png")
    _save_png(_small((120, 120, 130, 255), 24, "cone"), pack / "enemies" / "turret.png")
    for action in ("idle", "attack"):
        _save_png(_side_strip(2, (190, 60, 80, 255), 32, 32, action), pack / "boss" / f"boss_{action}.png")  # fmt: skip
    for depth, name in ((1, "far"), (3, "near")):
        _save_png(_side_background(depth), pack / "backgrounds" / f"bg_{name}.png")
    for i, name in enumerate(("spread", "laser", "flame", "machinegun")):
        _save_png(_small(pal(40 + i), 16), pack / "pickups" / f"weapon_pickup_{name}.png")
    _save_png(_small((220, 220, 230, 255), 16, "cone"), pack / "grapple_hook.png")
    _expected(
        out,
        "gunner",
        {
            "tiles/ground.png": {"usage": "tiles", "role": "GROUND"},
            "soldier/soldier_idle.png": {
                "usage": "sprite",
                "role": "PLAYER",  # a soldier that can jump, in a pack without another player
                "frame": [24, 24],
                "anims": ["idle_down", "jump_down", "shoot_down", "walk_down"],
            },
            "enemies/trooper_walk.png": {"usage": "sprite", "role": "ENEMY"},
            "enemies/turret.png": {"usage": "sprite", "role": "ENEMY"},
            "boss/boss_attack.png": {"usage": "sprite", "role": "BOSS"},
            "backgrounds/bg_far.png": {"usage": "background", "role": "BACKGROUND"},
        },
    )


def _road_sheet() -> Image.Image:
    """A 16 px sheet: asphalt straights and curves, a start line, grass and a barrier."""
    img = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    asphalt, grass, line = (70, 70, 78, 255), (76, 150, 70, 255), (240, 240, 240, 255)
    for col in range(8):
        x = col * 16
        d.rectangle([x, 0, x + 15, 15], fill=asphalt if col < 6 else grass)
        d.rectangle([x, 16, x + 15, 31], fill=grass if col % 2 else asphalt)
    d.line([(8, 0), (8, 15)], fill=line)  # a straight with its centre line
    d.line([(16, 8), (31, 8)], fill=line)
    for i in range(0, 16, 4):  # the start line: a chequered tile
        d.rectangle([32 + i, 0, 33 + i, 15], fill=line)
    d.rectangle([48, 6, 63, 9], fill=(200, 40, 40, 255))  # a barrier across the road
    return img


def make_racer(out: Path) -> None:
    """What a racing pack holds: cars in 16 headings, a road sheet, and what lies on a track."""
    pack = out / "racer"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    _save_png(_vehicle_ring(16, 24, (220, 60, 60, 255), (250, 220, 220, 255)), pack / "cars" / "player_car.png")  # fmt: skip
    for i in range(3):
        _save_png(_vehicle_ring(16, 24, pal(50 + i), (230, 230, 240, 255)), pack / "cars" / f"rival_car_{i + 1}.png")  # fmt: skip
    _save_png(_road_sheet(), pack / "tiles" / "road.png")
    _save_png(_small((40, 40, 44, 255), 16, "round"), pack / "props" / "tyre.png")
    _save_png(_small((240, 130, 40, 255), 16, "cone"), pack / "props" / "cone.png")
    _save_png(_small((30, 30, 40, 255), 16, "round"), pack / "hazards" / "oil.png")
    _save_png(_small((90, 220, 255, 255), 16, "cone"), pack / "pickups" / "boost.png")
    for i in range(4):
        _save_png(_small(pal(60 + i), 16), pack / "pickups" / f"pickup_{i + 1}.png")
    expected: dict[str, dict] = {
        "cars/player_car.png": {"usage": "sprite", "frame": [24, 24]},
        "tiles/road.png": {"usage": "tiles"},
        "props/tyre.png": {"usage": "sprite"},
        "pickups/pickup_1.png": {"usage": "sprite", "role": "ITEM"},
    }
    for i in range(3):
        expected[f"cars/rival_car_{i + 1}.png"] = {"usage": "sprite", "frame": [24, 24]}
    _expected(out, "racer", expected)


# ------------------------------------------------------------------------------------------
# The farm (T17.01): a pack in the naming scheme of a farming pack, drawn from primitives.

# the eight neighbours of a tile, as rpggen.core.terrain.blob counts them
_N, _NE, _E, _SE, _S, _SW, _W, _NW = 1, 2, 4, 8, 16, 32, 64, 128


def _soil_tile(mask: int, fill: Color, furrow: Color) -> Image.Image:
    """One 16 px tile of a patch of soil over nothing, for the neighbours of ``mask``: the
    middle is always there, a band of 4 px on each side that has a neighbour, and a corner
    where both sides and the corner have one. The furrows lie on the same rows in every tile."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    spans = {0: (0, 3), 1: (4, 11), 2: (12, 15)}
    there = {
        (1, 1): True,
        (1, 0): bool(mask & _N), (2, 1): bool(mask & _E), (1, 2): bool(mask & _S), (0, 1): bool(mask & _W),
        (2, 0): mask & (_N | _E | _NE) == (_N | _E | _NE),
        (2, 2): mask & (_S | _E | _SE) == (_S | _E | _SE),
        (0, 2): mask & (_S | _W | _SW) == (_S | _W | _SW),
        (0, 0): mask & (_N | _W | _NW) == (_N | _W | _NW),
    }  # fmt: skip
    for (cx, cy), drawn in there.items():
        if not drawn:
            continue
        (x0, x1), (y0, y1) = spans[cx], spans[cy]
        d.rectangle([x0, y0, x1, y1], fill=fill)
        for y in range(y0, y1 + 1):
            if y % 4 == 1:
                d.line([(x0, y), (x1, y)], fill=furrow)
    return img


def _soil_sheet(fill: Color, furrow: Color) -> Image.Image:
    """192 x 64: the 47 tiles of a patch of soil in the cells of Godot's 3x3 minimal template."""
    from rpggen.core.terrain import blob

    img = Image.new("RGBA", (192, 64), (0, 0, 0, 0))
    for i, mask in enumerate(blob.GODOT_3X3_MINIMAL):
        if mask is not None:
            img.paste(_soil_tile(mask, fill, furrow), ((i % 12) * 16, (i // 12) * 16))
    return img


def _fence_tile(sides: int, post: Color) -> Image.Image:
    """One 16 px tile of a fence: a post in the middle and a rail to each side that joins."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rail = (150, 110, 70, 255)
    if sides & _N:
        d.rectangle([7, 0, 8, 7], fill=rail)
    if sides & _S:
        d.rectangle([7, 8, 8, 15], fill=rail)
    if sides & _W:
        d.rectangle([0, 7, 7, 8], fill=rail)
    if sides & _E:
        d.rectangle([8, 7, 15, 8], fill=rail)
    d.rectangle([6, 6, 9, 9], fill=post, outline=BLACK)
    return img


# the cells of the template a fence sheet fills beside the sixteen of its first four columns:
# six more posts (which six a real pack draws is not known; any cell is read by its sides)
FENCE_EXTRA_CELLS = (4, 5, 6, 7, 16, 17)


def _fence_sheet() -> Image.Image:
    """192 x 64 in the shape of the 47-tile template with 22 cells drawn: tiles that join at
    their sides only."""
    from rpggen.core.terrain import blob

    img = Image.new("RGBA", (192, 64), (0, 0, 0, 0))
    sides_only = _N | _E | _S | _W
    for i, mask in enumerate(blob.GODOT_3X3_MINIMAL):
        if mask is None:
            continue
        if mask & ~sides_only == 0:
            tile = _fence_tile(mask, (110, 78, 48, 255))
        elif i in FENCE_EXTRA_CELLS:
            tile = _fence_tile(mask & sides_only, (190, 190, 200, 255))
        else:
            continue
        img.paste(tile, ((i % 12) * 16, (i // 12) * 16))
    return img


def _season_grass(season: int) -> Image.Image:
    """128 x 64: a sheet of 16 px ground tiles in the colours of one season."""
    base = ((96, 176, 80), (70, 150, 60), (190, 140, 60), (214, 222, 236))[season]
    img = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for row in range(4):
        for col in range(8):
            i = row * 8 + col
            tint = (base[0] - (i * 7) % 30, base[1] - (i * 11) % 30, base[2] + (i * 5) % 30)
            for dx in range(16):  # a gradient that is smooth inside the tile, as _tile draws
                colour = (min(255, tint[0] + dx * 2), min(255, tint[1] + dx), tint[2], 255)
                d.line([(col * 16 + dx, row * 16), (col * 16 + dx, row * 16 + 15)], fill=colour)
    return img


def _crop_strip(stages: int, fw: int, fh: int, leaf: Color, fruit: Color) -> Image.Image:
    """A crop's stages in a row: a stalk that grows from stage to stage, with fruit on the last."""
    img = Image.new("RGBA", (stages * fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(stages):
        mid, foot = i * fw + fw // 2, fh - 1
        height = 2 + i * (fh - 6) // max(1, stages - 1)
        d.rectangle([mid - 1, foot - height, mid, foot], fill=leaf)
        for k in range(1, height // 5 + 1):  # a pair of leaves every five pixels
            y = foot - k * 5 + 1
            d.line([(mid - 3 - (k + i) % 2, y), (mid + 2 + (k + i) % 2, y)], fill=leaf)
        if i == stages - 1:
            d.rectangle([mid - 3, foot - height, mid + 2, foot - height + 3], fill=fruit)
    return img


def _rain(frames: int, size: int) -> Image.Image:
    """A rain overlay as a strip: thin slanted drops that move down from frame to frame."""
    img = Image.new("RGBA", (frames * size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in range(frames):
        for k in range(size // 2):
            x = (k * 13) % (size - 2)
            y = (k * 29 + f * 7) % (size - 5)
            d.line([(f * size + x + 1, y), (f * size + x, y + 3)], fill=(150, 190, 240, 255))
    return img


def _building(w: int, h: int, wall: Color, roof: Color) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([2, h // 3, w - 3, h - 1], fill=wall, outline=BLACK)
    d.polygon([(0, h // 3), (w // 2, 1), (w - 1, h // 3)], fill=roof, outline=BLACK)
    d.rectangle([w // 2 - 3, h - 10, w // 2 + 2, h - 1], fill=(70, 46, 30, 255))
    return img


def make_ranch(out: Path) -> None:
    """What a farming pack holds, named the way one such pack names it:
    ``<thing>_<nn>_<colour>_<action>_<direction>_<W>x<H>_<N>frames.png``."""
    pack = out / "ranch"
    _write_text(pack / "LICENSE.txt", "CC0-1.0 synthetic test pack\n")
    farmer = pack / "characters" / "farmer"
    for n, direction in enumerate(("down", "up", "left", "right")):
        _save_png(_strip(4, 20 + n), farmer / f"farmer_walk_{direction}_16x16_4frames.png")
    for n, tool in enumerate(("hoe", "water")):  # the farmer using a tool: no action word
        _save_png(_strip(3, 26 + n), farmer / f"farmer_{tool}_down_16x16_3frames.png")
    animals = (("cows", "cow_01", 32), ("chickens", "hen_01", 16))
    colours = ("brown", "black", "white")
    for folder, name, size in animals:
        for n, colour in enumerate(colours):
            base = pack / "animals" / folder / name / colour
            stem = f"{name}_{colour}"
            shade = 70 + n + (0 if size == 32 else 5)
            _save_png(_strip(4, shade, size, size), base / "move" / f"{stem}_move_down_{size}x{size}_4frames.png")  # fmt: skip
            _save_png(_strip(2, shade, size, size), base / "sleep" / f"{stem}_sleep_{size}x{size}_2frames.png")  # fmt: skip
    green = (70, 160, 70, 255)
    crops = (("corn", 8, (240, 210, 70, 255)), ("wheat", 5, (220, 190, 110, 255)),
             ("tomato", 12, (220, 60, 50, 255)))  # fmt: skip
    for name, stages, fruit in crops:
        _save_png(_crop_strip(stages, 16, 32, green, fruit), pack / "crops" / f"{name}_16x32_{stages}frames.png")  # fmt: skip
    _save_png(_small((230, 130, 40, 255), 16, "round"), pack / "crops" / "pumpkin_16x16.png")
    for n, tool in enumerate(("hoe", "shovel", "water", "sickle")):
        _save_png(_small(pal(80 + n), 16, ("thin", "cone", "round", "box")[n]), pack / "tools" / f"{tool}_16x16.png")  # fmt: skip
    tiles = pack / "tiles"
    _save_png(_soil_sheet((134, 96, 62, 255), (112, 78, 50, 255)), pack / "autotiles" / "01_soil_tilled.png")  # fmt: skip
    _save_png(_soil_sheet((92, 66, 48, 255), (74, 52, 40, 255)), pack / "autotiles" / "02_soil_watered.png")  # fmt: skip
    _save_png(_fence_sheet(), pack / "autotiles" / "03_fence.png")
    for n, season in enumerate(("spring", "summer", "autumn", "winter")):
        _save_png(_season_grass(n), tiles / season / "grass_16x16.png")
    _save_png(_rain(3, 64), pack / "weather" / "rain_64x64_3frames.png")
    _save_png(_building(48, 48, (200, 170, 130, 255), (170, 60, 50, 255)), pack / "buildings" / "house.png")  # fmt: skip
    _save_png(_building(32, 32, (220, 200, 150, 255), (120, 90, 60, 255)), pack / "buildings" / "coop.png")  # fmt: skip
    _save_png(_small((150, 110, 70, 255), 16), pack / "props" / "shipping_bin.png")
    expected: dict[str, dict] = {
        "characters/farmer/farmer_walk_down_16x16_4frames.png": {
            "usage": "sprite",
            "role": "PLAYER",  # the farmer of a farming pack without another player
            "frame": [16, 16],
            "anims": ["walk_down", "walk_left", "walk_right", "walk_up"],
        },
        # the farmer using a tool: an animation of the farmer, not a villager (T17.10)
        "characters/farmer/farmer_hoe_down_16x16_3frames.png": {"usage": "sprite", "role": "NONE"},
        "characters/farmer/farmer_water_down_16x16_3frames.png": {
            "usage": "sprite",
            "role": "NONE",
        },
        "crops/pumpkin_16x16.png": {"usage": "sprite", "role": "CROP"},  # one picture
        "autotiles/01_soil_tilled.png": {"usage": "tiles", "role": "GROUND"},
        "autotiles/02_soil_watered.png": {"usage": "tiles", "role": "GROUND"},
        "autotiles/03_fence.png": {"usage": "tiles", "role": "WALL"},
        # an overlay, nobody to talk to
        "weather/rain_64x64_3frames.png": {"usage": "sprite", "role": "EFFECT", "frame": [64, 64]},
        "buildings/house.png": {"role": "BUILDING"},
        "buildings/coop.png": {"role": "BUILDING"},
    }
    for name, stages, _fruit in crops:
        expected[f"crops/{name}_16x32_{stages}frames.png"] = {"usage": "growth_strip", "role": "CROP", "frame": [16, 32]}  # fmt: skip
    for tool in ("hoe", "shovel", "water", "sickle"):  # water in a folder of tools is the can
        expected[f"tools/{tool}_16x16.png"] = {"usage": "sprite", "role": "TOOL"}
    for season in ("spring", "summer", "autumn", "winter"):
        expected[f"tiles/{season}/grass_16x16.png"] = {"usage": "tiles", "role": "GROUND"}
    for folder, name, size in animals:
        for colour in colours:
            base = f"animals/{folder}/{name}/{colour}"
            expected[f"{base}/move/{name}_{colour}_move_down_{size}x{size}_4frames.png"] = {
                "usage": "sprite",
                "role": "ANIMAL",
                "frame": [size, size],
                "anims": ["walk_down"],
            }
            expected[f"{base}/sleep/{name}_{colour}_sleep_{size}x{size}_2frames.png"] = {
                "usage": "sprite",
                "role": "ANIMAL",
                "anims": ["sleep_down"],
            }
    _expected(out, "ranch", expected)


# ------------------------------------------------------------------------------------------
# Isometric packs (T17.12): one picture a tile, drawn in the shapes and the names of the packs
# that were listed (nothing of them is copied).

ISO_GRASS: Color = (104, 170, 84, 255)
ISO_SIDE_LEFT: Color = (122, 86, 58, 255)
ISO_SIDE_RIGHT: Color = (150, 108, 72, 255)
ISO_MARK: Color = (245, 240, 210, 255)


def _diamond_columns(w: int, h: int) -> list[tuple[int, int]]:
    """The first and the last row of every column of a diamond ``w`` wide and ``h`` high whose
    top corner is at row 0: its edges fall ``h / w`` rows a column, exactly."""
    out = []
    for x in range(w):
        top = (abs(2 * x + 1 - w) * h) // (2 * w)
        out.append((top, h - 1 - top))
    return out


def _iso_block(
    canvas: tuple[int, int],
    foot: tuple[int, int],
    side: int,
    face: Color,
    *,
    bottom: int = 0,
    turn: int | None = None,
    left: Color = ISO_SIDE_LEFT,
    right: Color = ISO_SIDE_RIGHT,
) -> Image.Image:
    """One isometric tile in its picture: a diamond ``foot`` with ``side`` rows of block under
    it, in the middle of the canvas, its lowest point ``bottom`` rows above the canvas's
    bottom. ``turn`` paints a mark on one of the face's four corners, so that four turns of a
    tile are four pictures of one outline."""
    w, h = foot
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    px = img.load()
    x0 = (canvas[0] - w) // 2
    y0 = canvas[1] - bottom - side - h
    for x, (top, low) in enumerate(_diamond_columns(w, h)):
        for y in range(top, low + 1):
            px[x0 + x, y0 + y] = face
        for y in range(low + 1, low + 1 + side):
            px[x0 + x, y0 + y] = left if x < w // 2 else right
    if turn is not None:
        cx, cy = x0 + w // 2, y0 + h // 2
        dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[turn % 4]
        mx, my = cx + dx * (w // 4), cy + dy * (h // 4)
        for y in range(my - 1, my + 1):
            for x in range(mx - 2, mx + 2):
                px[x, y] = ISO_MARK
    return img


def _iso_tree(canvas: tuple[int, int], foot: tuple[int, int], side: int) -> Image.Image:
    """A tree standing on the middle of a diamond: a trunk narrower than the diamond."""
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = canvas[0] // 2
    foot_y = canvas[1] - side - foot[1] // 2
    draw.rectangle([cx - 3, foot_y - 16, cx + 2, foot_y], fill=(110, 74, 46, 255))
    draw.ellipse([cx - 14, foot_y - 40, cx + 13, foot_y - 12], fill=(52, 128, 66, 255))
    return img


def _iso_house(canvas: tuple[int, int], foot: tuple[int, int], side: int) -> Image.Image:
    """A small house on the middle of a diamond: a block smaller than the diamond with a roof."""
    small = (foot[0] * 2 // 3, foot[1] * 2 // 3)
    lift = side + (foot[1] - small[1]) // 2
    return _iso_block(
        canvas, small, 16, (176, 70, 58, 255), bottom=lift,
        left=(214, 196, 160, 255), right=(236, 220, 186, 255),
    )  # fmt: skip


def _texture_atlas(image: str, entries: list[tuple[str, int, int, int, int]]) -> str:
    lines = [f'<TextureAtlas imagePath="{image}">']
    for name, x, y, w, h in entries:
        lines.append(f'\t<SubTexture name="{name}" x="{x}" y="{y}" width="{w}" height="{h}"/>')
    return "\n".join([*lines, "</TextureAtlas>", ""])


ISO_TILES_CANVAS = (60, 64)
ISO_TILES_FOOT = (60, 34)  # nearly the 30 degree diamond: not twice as wide as high
ISO_TILES_SIDE = 8
ISO_TILES_COUNT = 24
ISO_TILES_RAISED = 6  # the last so many tiles are blocks that stand higher


def make_iso_tiles(out: Path) -> None:
    """In the manner of the rendered isometric packs: 24 tiles turned four ways in one canvas,
    a ``Tile information.txt`` whose *Tile size* is the diamond with the block's side, a tree
    and a house as objects, a sheet with an atlas of the same pictures, and a preview."""
    pack = out / "iso_tiles"
    canvas, foot, side = ISO_TILES_CANVAS, ISO_TILES_FOOT, ISO_TILES_SIDE
    _write_text(pack / "License.txt", "CC0-1.0 synthetic test pack\n")
    _write_text(
        pack / "Tile information.txt",
        f"\n\tImage size : {canvas[0]} x {canvas[1]} px\n"
        f"\tTile size  : {foot[0]} x {foot[1] + side} px\n",
    )
    pictures: list[tuple[str, Image.Image]] = []
    expected: dict[str, dict] = {}
    for i in range(1, ISO_TILES_COUNT + 1):
        lift = 12 if i > ISO_TILES_COUNT - ISO_TILES_RAISED else 0
        for turn in range(4):
            name = f"isoTile_{i:03d}_{turn}.png"
            pictures.append((name, _iso_block(canvas, foot, side + lift, pal(i), turn=turn)))
            expected[f"PNG/{name}"] = {"usage": "iso_tile", "role": "GROUND"}
    for turn in range(4):
        pictures.append((f"tree_01_{turn}.png", _iso_tree(canvas, foot, side)))
        pictures.append((f"house_01_{turn}.png", _iso_house(canvas, foot, side)))
        expected[f"PNG/tree_01_{turn}.png"] = {"usage": "sprite", "role": "DECORATION", "frame": list(canvas)}  # fmt: skip
        expected[f"PNG/house_01_{turn}.png"] = {"usage": "sprite", "role": "BUILDING", "frame": list(canvas)}  # fmt: skip
    for name, img in pictures:
        _save_png(img, pack / "PNG" / name)
    # the same pictures packed into one sheet, with the list of its rectangles (whose
    # imagePath is the name the sheet had when it was packed, as in the real packs)
    cols = 13
    rows = -(-len(pictures) // cols)
    sheet = Image.new("RGBA", (cols * canvas[0], rows * canvas[1]), (0, 0, 0, 0))
    entries = []
    for index, (name, img) in enumerate(pictures):
        x, y = (index % cols) * canvas[0], (index // cols) * canvas[1]
        sheet.paste(img, (x, y))
        entries.append((name, x, y, canvas[0], canvas[1]))
    _save_png(sheet, pack / "Spritesheet" / "isoTiles_sheet.png")
    _write_text(pack / "Spritesheet" / "isoTiles_sheet.xml", _texture_atlas("sheet.png", entries))
    preview = Image.new("RGBA", (120, 68), (58, 58, 58, 255))
    for i in range(3):
        tile = _iso_block(canvas, foot, side, pal(i + 1))
        preview.alpha_composite(tile, (i * 30, 2))
    _save_png(preview, pack / "Preview.png")
    expected["Spritesheet/isoTiles_sheet.png"] = {"usage": "sprite", "role": "NONE"}
    expected["Preview.png"] = {"role": "NONE"}
    _expected(out, "iso_tiles", expected)


ISO_MINI_CANVAS = (64, 96)
ISO_MINI_FOOT = (64, 32)
ISO_MINI_SIDE = 6
COMPASS_FOUR = ("N", "E", "S", "W")
COMPASS_EIGHT = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def _iso_car(heading: int, body: Color, slope: int = 0) -> Image.Image:
    """A small car seen at an angle, pointing one of eight ways (0 is up, clockwise): a
    picture as large as the car, so the eight are of different sizes."""
    import math

    angle = heading * math.pi / 4
    dx, dy = math.sin(angle), -math.cos(angle) * 0.6 - slope * 0.2
    length, width = 9.0, 5.0
    nx, ny = dy, -dx * 0.6
    corners = [
        (dx * length + nx * width, dy * length + ny * width),
        (dx * length - nx * width, dy * length - ny * width),
        (-dx * length - nx * width, -dy * length - ny * width),
        (-dx * length + nx * width, -dy * length + ny * width),
    ]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    w = int(math.ceil(max(xs) - min(xs))) + 3
    h = int(math.ceil(max(ys) - min(ys))) + 6
    ox, oy = -min(xs) + 1, -min(ys) + 1
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    shifted = [(int(round(x + ox)), int(round(y + oy))) for x, y in corners]
    draw.polygon([(x, y + 3) for x, y in shifted], fill=(40, 40, 46, 255))
    draw.polygon(shifted, fill=body)
    fx, fy = int(round(dx * 5 + ox)), int(round(dy * 5 + oy))
    draw.rectangle([fx - 1, fy - 1, fx + 1, fy + 1], fill=(170, 214, 240, 255))
    return img


def make_iso_miniature(out: Path) -> None:
    """In the manner of the miniature packs: the pack is a zip in its folder beside previews;
    inside, the same names in a folder ``Isometric`` and a folder ``Angle`` (two views of one
    model), every name with ``_N``, ``_E``, ``_S``, ``_W``; a corn plant; and a car in eight
    headings by letters, with two of them on a slope."""
    canvas, foot, side = ISO_MINI_CANVAS, ISO_MINI_FOOT, ISO_MINI_SIDE
    entries: list[tuple[str, bytes]] = []
    expected: dict[str, dict] = {}

    def corn(view_foot: tuple[int, int]) -> Image.Image:
        img = Image.new("RGBA", canvas, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, foot_y = canvas[0] // 2, canvas[1] - side - view_foot[1] // 2
        for dx in (-5, 4):
            draw.rectangle([cx + dx, foot_y - 26, cx + dx + 1, foot_y], fill=(96, 150, 62, 255))
            draw.rectangle([cx + dx - 1, foot_y - 18, cx + dx + 2, foot_y - 11], fill=(232, 200, 72, 255))  # fmt: skip
        return img

    def fence(view_foot: tuple[int, int], turn: int) -> Image.Image:
        img = Image.new("RGBA", canvas, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, foot_y = canvas[0] // 2, canvas[1] - side - view_foot[1] // 2
        lean = (view_foot[1] // 4) * (1 if turn % 2 else -1)
        draw.line([(cx - 12, foot_y - 10 - lean), (cx + 12, foot_y - 10 + lean)], fill=WOOD, width=2)  # fmt: skip
        for dx in (-12, 0, 12):
            y = foot_y + (lean * dx) // 12
            draw.rectangle([cx + dx - 1, y - 14, cx + dx, y], fill=WOOD_DARK)
        return img

    views = (("Isometric", foot), ("Angle", (foot[0], foot[1] + 12)))
    for folder, view_foot in views:
        for turn, letter in enumerate(COMPASS_FOUR):
            things = {
                "floorWood": _iso_block(canvas, view_foot, side, (176, 132, 84, 255), turn=turn),
                "floorStone": _iso_block(canvas, view_foot, side, (150, 150, 158, 255), turn=turn),
                "dirtFarmland": _iso_block(canvas, view_foot, side, (128, 92, 60, 255), turn=turn),
                "blockStone": _iso_block(
                    canvas, view_foot, side + 20, (138, 138, 150, 255), turn=turn
                ),  # fmt: skip
                "cornDouble": corn(view_foot),
                "fenceWood": fence(view_foot, turn),
            }
            for name, img in things.items():
                entries.append((f"{folder}/{name}_{letter}.png", _png_bytes(img)))
    for heading, letter in enumerate(COMPASS_EIGHT):
        entries.append((f"Cars/car_{letter}.png", _png_bytes(_iso_car(heading, (214, 64, 60, 255)))))  # fmt: skip
    entries.append(("Cars/car_NEU.png", _png_bytes(_iso_car(1, (214, 64, 60, 255), slope=1))))
    entries.append(("Cars/car_NED.png", _png_bytes(_iso_car(1, (214, 64, 60, 255), slope=-1))))
    picture = Image.new("RGBA", (96, 54), (58, 58, 58, 255))
    picture.alpha_composite(_iso_block((64, 44), foot, side, (176, 132, 84, 255)), (16, 6))
    for name in ("Preview.png", "Information.png"):
        entries.append((name, _png_bytes(picture)))
    entries.append(("License.txt", b"CC0-1.0 synthetic test pack\n"))
    entries.append(("Instructions.url", b"[InternetShortcut]\nURL=https://example.invalid/\n"))
    entries.sort(key=lambda e: e[0])
    pack = out / "iso_miniature"
    _write_zip(pack / "Isometric Miniature Sample (1.0).zip", entries)
    _save_png(picture, pack / "Preview.png")
    _save_png(picture, pack / "Sample.png")
    for letter in COMPASS_FOUR:
        expected[f"Isometric/floorWood_{letter}.png"] = {"usage": "iso_tile", "role": "GROUND"}
        expected[f"Isometric/blockStone_{letter}.png"] = {"usage": "iso_tile"}
        expected[f"Isometric/cornDouble_{letter}.png"] = {"usage": "sprite", "frame": list(canvas)}
        expected[f"Isometric/fenceWood_{letter}.png"] = {"usage": "sprite", "role": "WALL"}
        expected[f"Angle/floorWood_{letter}.png"] = {"usage": "sprite", "role": "NONE"}
    expected["Cars/car_NEU.png"] = {"usage": "sprite", "role": "NONE"}
    expected["Preview.png"] = {"role": "NONE"}
    _expected(out, "iso_miniature", expected)


PACKS: dict[str, Callable[[Path], None]] = {
    "basic16": make_basic16,
    "gutter32": make_gutter32,
    "gutterless48": make_gutterless48,
    "mixed": make_mixed,
    "strips": make_strips,
    "sequences": make_sequences,
    "rpgmaker_like": make_rpgmaker_like,
    "lpc_like": make_lpc_like,
    "lpc_parts": make_lpc_parts,
    "tiled_meta": make_tiled_meta,
    "tiled_map": make_tiled_map,
    "ldtk_level": make_ldtk_level,
    "aseprite_meta": make_aseprite_meta,
    "objects_in_sheet": make_objects_in_sheet,
    "platformer": make_platformer,
    "weird_names": make_weird_names,
    "zipped": make_zipped,
    "frames_export": make_frames_export,
    "multi_engine": make_multi_engine,
    "bundle": make_bundle,
    "shooter": make_shooter,
    "gunner": make_gunner,
    "racer": make_racer,
    "ranch": make_ranch,
    "iso_tiles": make_iso_tiles,
    "iso_miniature": make_iso_miniature,
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

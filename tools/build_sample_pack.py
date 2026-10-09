"""Generate the bundled CC0 sample pack (``sample_pack/``) and its profile.

Usage:
    python tools/build_sample_pack.py            # write the pack next to this repo's root
    python tools/build_sample_pack.py --out DIR  # write somewhere else (used by the tests)
    python tools/build_sample_pack.py --no-profile
    python tools/build_sample_pack.py --side     # the side-view pack, sample_pack_side/ (T14.09)

Every pixel is drawn from integer arithmetic (no randomness, no antialiasing), so the images are
the same on every machine. The pack is original work released under CC0-1.0: nothing is copied
from another pack. ``sample.rpgprofile.json`` is made by auditing the generated pack with the
normal pipeline, confirming every asset and exporting the result, so the Audit page of the sample
pack is all CONFIRMED.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_audio  # noqa: E402

Color = tuple[int, int, int, int]
Px = tuple[int, int, int]

PACK_NAME = "sample_pack"
PROFILE_NAME = "sample.rpgprofile.json"
PROFILE_TITLE = "rpggen sample pack"

BLACK: Px = (24, 20, 28)
WHITE: Px = (250, 246, 240)


def rgba(c: Px, a: int = 255) -> Color:
    return (c[0], c[1], c[2], a)


def shade(c: Px, d: int) -> Px:
    return (max(0, min(255, c[0] + d)), max(0, min(255, c[1] + d)), max(0, min(255, c[2] + d)))


def noise(x: int, y: int, seed: int) -> int:
    """A small deterministic hash of a pixel position, 0..255."""
    n = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFF


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=False, compress_level=9, pnginfo=None)


def canvas(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


# ------------------------------------------------------------------------------ ground tiles

GRASS: Px = (92, 168, 76)
DIRT: Px = (148, 104, 68)
STONE: Px = (156, 156, 164)
SAND: Px = (222, 200, 140)


def _speckled(img: Image.Image, x0: int, y0: int, base: Px, seed: int, spread: int = 14) -> None:
    for y in range(16):
        for x in range(16):
            n = noise(x, y, seed)
            d = (n % (spread * 2 + 1)) - spread if n % 3 == 0 else 0
            img.putpixel((x0 + x, y0 + y), rgba(shade(base, d)))


def _tuft(img: Image.Image, x0: int, y0: int, base: Px, seed: int) -> None:
    dark, light = shade(base, -34), shade(base, 30)
    for k in range(4):
        x = 2 + noise(k, 1, seed) % 12
        y = 4 + noise(k, 2, seed) % 9
        img.putpixel((x0 + x, y0 + y), rgba(dark))
        img.putpixel((x0 + x, y0 + y - 1), rgba(light))
        img.putpixel((x0 + x + 1, y0 + y - 1), rgba(light))


def _cobbles(img: Image.Image, x0: int, y0: int, base: Px, seed: int) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y0, x0 + 15, y0 + 15], fill=rgba(shade(base, -40)))
    for row in range(2):
        off = 4 if row else 0
        for col in range(-1, 3):
            x = x0 + col * 8 + off
            y = y0 + row * 8
            tone = shade(base, (noise(col, row, seed) % 21) - 10)
            for yy in range(y + 1, y + 7):
                for xx in range(max(x0, x + 1), min(x0 + 16, x + 7)):
                    img.putpixel((xx, yy), rgba(tone))


def ground_sheet() -> Image.Image:
    """8 x 2 tiles: three ground kinds (grass, dirt, stone path), their variants and sand."""
    img, _ = canvas(128, 32)
    kinds = [GRASS, GRASS, DIRT, DIRT, STONE, STONE, SAND, SAND]
    for i, base in enumerate(kinds):
        for row in range(2):
            x0, y0 = i * 16, row * 16
            seed = i * 7 + row * 3 + 1
            if base is STONE:
                _cobbles(img, x0, y0, base, seed)
            else:
                _speckled(img, x0, y0, shade(base, (i % 2) * 22 - 12 + row * 10), seed)
                if base is GRASS and (i + row) % 2 == 0:
                    _tuft(img, x0, y0, base, seed)
    return img


def meadow_a2_sheet() -> Image.Image:
    """An RPG Maker A2-style sheet: two 2 x 3 tile autotile blocks (grass on dirt, sand on grass).

    A block is 4 x 6 quarter-tiles of 8 px. Each source quarter is drawn for the output quarter
    and edge kind it serves in ``rpggen/core/terrain/rpgmaker_a2.py`` (center, edges, outer and
    inner corners); the inside material fills the quarter and the outside shows on the open sides.
    """
    from rpggen.core.terrain import rpgmaker_a2 as a2

    img, _ = canvas(64, 48)
    q = 8
    # sides of the quarter that face outside, per (output quarter, kind)
    open_sides = {
        "TL": {"outer": "tl", "horizontal": "t", "vertical": "l", "center": "", "inner": "c"},
        "TR": {"outer": "tr", "horizontal": "t", "vertical": "r", "center": "", "inner": "c"},
        "BL": {"outer": "bl", "horizontal": "b", "vertical": "l", "center": "", "inner": "c"},
        "BR": {"outer": "br", "horizontal": "b", "vertical": "r", "center": "", "inner": "c"},
    }
    blocks = [(GRASS, DIRT, 3), (SAND, GRASS, 5)]
    for bi, (inside, outside, seed) in enumerate(blocks):
        for corner, table in a2.QUARTER_TABLE.items():
            for kind, (qx, qy) in table.items():
                sides = open_sides[corner][kind]
                for y in range(q):
                    for x in range(q):
                        out = False
                        if "t" in sides and y < 3 or "b" in sides and y >= q - 3:
                            out = True
                        if "l" in sides and x < 3 or "r" in sides and x >= q - 3:
                            out = True
                        if sides == "tl" and (x < 3 or y < 3):
                            out = True
                        if sides == "tr" and (x >= q - 3 or y < 3):
                            out = True
                        if sides == "bl" and (x < 3 or y >= q - 3):
                            out = True
                        if sides == "br" and (x >= q - 3 or y >= q - 3):
                            out = True
                        if sides == "c":  # inner corner: a notch at the corner of the tile
                            cx = x < 3 if corner in ("TL", "BL") else x >= q - 3
                            cy = y < 3 if corner in ("TL", "TR") else y >= q - 3
                            out = cx and cy
                        base = outside if out else inside
                        tone = (noise(x + qx * q, y + qy * q, seed) % 21) - 10
                        img.putpixel((bi * 32 + qx * q + x, qy * q + y), rgba(shade(base, tone)))
    return img


def water_sheet() -> Image.Image:
    """4 x 2 tiles of water with lighter wave lines."""
    img, d = canvas(64, 32)
    base: Px = (52, 120, 206)
    for ty in range(2):
        for tx in range(4):
            x0, y0 = tx * 16, ty * 16
            d.rectangle(
                [x0, y0, x0 + 15, y0 + 15], fill=rgba(shade(base, 22 * ((tx + ty) % 2) - 10))
            )
            for k in range(3):
                y = y0 + 3 + k * 5
                shift = noise(tx, ty * 3 + k, 5) % 6
                d.line([(x0 + 2 + shift, y), (x0 + 7 + shift, y)], fill=rgba(shade(base, 46)))
    return img


def wall_sheet() -> Image.Image:
    """4 x 2 tiles of stone brick wall."""
    img, d = canvas(64, 32)
    for ty in range(2):
        for tx in range(4):
            x0, y0 = tx * 16, ty * 16
            tone: Px = (92 + 36 * ((tx + ty) % 2), 100 + 10 * tx, 118)
            d.rectangle([x0, y0, x0 + 15, y0 + 15], fill=rgba(shade(tone, -46)))
            for row in range(4):
                off = 4 if row % 2 else 0
                for col in range(-1, 3):
                    bx = x0 + col * 8 + off
                    by = y0 + row * 4
                    c = shade(tone, (noise(col + tx * 3, row + ty * 5, 11) % 25) - 12)
                    xa, xb = max(x0, bx + 1), min(x0 + 15, bx + 7)
                    if xa <= xb:
                        d.rectangle([xa, by + 1, xb, by + 3], fill=rgba(c))
    return img


# ------------------------------------------------------------------------------ town objects


def _house(d: ImageDraw.ImageDraw, x0: int, y0: int) -> None:
    """A 5 x 4 tile house whose top-left cell is (x0, y0); the roof is a trapezoid."""
    wall: Px = (226, 190, 140)
    roof: Px = (176, 58, 52)
    d.rectangle([x0, y0 + 24, x0 + 79, y0 + 63], fill=rgba(wall), outline=rgba(shade(wall, -70)))
    for y in range(y0, y0 + 24):
        inset = (y0 + 23 - y) // 2
        tone = shade(roof, -22 if (y - y0) % 4 == 0 else 0)
        d.line([(x0 + inset, y), (x0 + 79 - inset, y)], fill=rgba(tone))
    d.line([(x0 + 12, y0 + 24), (x0 + 67, y0 + 24)], fill=rgba(shade(roof, -60)))
    d.rectangle([x0 + 32, y0 + 40, x0 + 47, y0 + 63], fill=rgba((104, 70, 40)))  # door
    d.rectangle([x0 + 44, y0 + 52, x0 + 45, y0 + 53], fill=rgba((240, 210, 90)))
    for wx in (x0 + 8, x0 + 60):  # windows
        d.rectangle([wx, y0 + 32, wx + 11, y0 + 43], fill=rgba((150, 210, 240)))
        d.rectangle([wx, y0 + 32, wx + 11, y0 + 43], outline=rgba((90, 60, 40)))
        d.line([(wx + 5, y0 + 32), (wx + 5, y0 + 43)], fill=rgba((90, 60, 40)))


def _tree(d: ImageDraw.ImageDraw, x0: int, y0: int) -> None:
    """A tree 32 px wide: crown over 2 x 2 tiles, trunk across the cell border below."""
    leaf: Px = (52, 142, 62)
    d.ellipse([x0, y0, x0 + 31, y0 + 31], fill=rgba(leaf), outline=rgba(shade(leaf, -50)))
    d.ellipse([x0 + 6, y0 + 4, x0 + 17, y0 + 13], fill=rgba(shade(leaf, 28)))
    d.rectangle([x0 + 12, y0 + 32, x0 + 19, y0 + 47], fill=rgba((110, 74, 44)))
    d.line([(x0 + 12, y0 + 32), (x0 + 12, y0 + 47)], fill=rgba((80, 52, 30)))


def town_sheet() -> Image.Image:
    """Objects in a tile sheet: a house and two trees among a few loose ground tiles."""
    img, d = canvas(192, 160)
    _house(d, 16, 16)
    _tree(d, 128, 0)
    _tree(d, 128, 80)
    loose = [(0, 0), (11, 3), (0, 6), (6, 6), (10, 7), (0, 9), (2, 9), (4, 9), (6, 9), (8, 9)]
    for n, (cx, cy) in enumerate(loose):
        _speckled(img, cx * 16, cy * 16, shade(GRASS if n % 2 else DIRT, -8 * (n % 3)), 40 + n)
    return img


# ------------------------------------------------------------------------------ characters


def _person(
    d: ImageDraw.ImageDraw,
    ox: int,
    oy: int,
    direction: str,
    step: int,
    cloth: Px,
    hair: Px,
    skin: Px = (240, 200, 160),
) -> None:
    """A 16 x 24 frame: ``step`` 0..3 is the walk cycle; the lowest row is y = 23."""
    bob = 1 if step in (1, 3) else 0
    swing = (0, 1, 0, -1)[step]
    d.ellipse([ox + 3, oy + 20, ox + 12, oy + 22], fill=(0, 0, 0, 70))  # shadow
    leg_l, leg_r = 6 + swing, 9 - swing
    d.rectangle([ox + leg_l, oy + 18, ox + leg_l + 1, oy + 21 - (step == 1)], fill=rgba(BLACK))
    d.rectangle([ox + leg_r, oy + 18, ox + leg_r + 1, oy + 21 - (step == 3)], fill=rgba(BLACK))
    d.rounded_rectangle([ox + 4, oy + 10 - bob, ox + 11, oy + 19 - bob], 2, fill=rgba(cloth))
    d.line([(ox + 4, oy + 16 - bob), (ox + 11, oy + 16 - bob)], fill=rgba(shade(cloth, -50)))
    d.rounded_rectangle([ox + 4, oy + 4 - bob, ox + 11, oy + 11 - bob], 3, fill=rgba(skin))
    if direction == "up":
        d.rounded_rectangle([ox + 4, oy + 3 - bob, ox + 11, oy + 10 - bob], 3, fill=rgba(hair))
        return
    d.rounded_rectangle([ox + 4, oy + 3 - bob, ox + 11, oy + 7 - bob], 2, fill=rgba(hair))
    if direction == "down":
        d.point([(ox + 6, oy + 8 - bob), (ox + 9, oy + 8 - bob)], fill=rgba(BLACK))
    elif direction == "left":
        d.rectangle([ox + 8, oy + 3 - bob, ox + 11, oy + 9 - bob], fill=rgba(hair))
        d.point([(ox + 5, oy + 8 - bob)], fill=rgba(BLACK))
    else:
        d.rectangle([ox + 4, oy + 3 - bob, ox + 7, oy + 9 - bob], fill=rgba(hair))
        d.point([(ox + 10, oy + 8 - bob)], fill=rgba(BLACK))


def character_sheet(cloth: Px, hair: Px) -> Image.Image:
    """4 columns (walk frames) x 4 rows (down, left, right, up) of 16 x 24 frames."""
    img, d = canvas(64, 96)
    for row, direction in enumerate(("down", "left", "right", "up")):
        for col in range(4):
            _person(d, col * 16, row * 24, direction, col, cloth, hair)
    return img


def slime_strip() -> Image.Image:
    """4 frames of 16 x 16: a slime squashing and stretching."""
    img, d = canvas(64, 16)
    body: Px = (96, 200, 96)
    for i in range(4):
        ox = i * 16
        squash = (0, 1, 2, 1)[i]
        top = 5 + squash
        d.ellipse([ox + 1, top, ox + 14, 15], fill=rgba(body), outline=rgba(shade(body, -70)))
        d.ellipse([ox + 3, top + 2, ox + 6, top + 4], fill=rgba(shade(body, 60)))
        d.point([(ox + 5, top + 6), (ox + 10, top + 6)], fill=rgba(BLACK))
    return img


def portrait() -> Image.Image:
    """A 48 x 48 face portrait."""
    img, d = canvas(48, 48)
    d.rectangle([0, 0, 47, 47], fill=rgba((70, 86, 120)))
    d.rounded_rectangle([12, 10, 35, 42], 8, fill=rgba((240, 200, 160)))
    d.rounded_rectangle([10, 6, 37, 20], 6, fill=rgba((90, 60, 40)))
    d.rectangle([17, 25, 20, 27], fill=rgba(BLACK))
    d.rectangle([28, 25, 31, 27], fill=rgba(BLACK))
    d.line([(20, 35), (28, 35)], fill=rgba((170, 80, 70)))
    d.rectangle([14, 40, 33, 47], fill=rgba((70, 120, 180)))
    return img


# ------------------------------------------------------------------------------ items and UI


def _icon() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    return canvas(16, 16)


def potion() -> Image.Image:
    img, d = _icon()
    d.rectangle([6, 2, 9, 4], fill=rgba((170, 130, 90)), outline=rgba(BLACK))
    d.ellipse([3, 5, 12, 14], fill=rgba((214, 60, 80)), outline=rgba(BLACK))
    d.rectangle([5, 7, 6, 8], fill=rgba((255, 170, 180)))
    return img


def sword() -> Image.Image:
    img, d = _icon()
    d.polygon([(3, 12), (11, 4), (13, 6), (5, 14)], fill=rgba((206, 214, 224)), outline=rgba(BLACK))
    d.rectangle([2, 11, 5, 14], fill=rgba((150, 100, 50)), outline=rgba(BLACK))
    return img


def coin() -> Image.Image:
    img, d = _icon()
    d.ellipse([3, 3, 12, 12], fill=rgba((246, 206, 70)), outline=rgba((140, 100, 20)))
    d.rectangle([7, 5, 8, 10], fill=rgba((200, 150, 30)))
    return img


def key() -> Image.Image:
    img, d = _icon()
    d.ellipse([2, 2, 8, 8], outline=rgba((240, 200, 60)))
    d.line([(7, 7), (13, 13)], fill=rgba((240, 200, 60)), width=2)
    d.line([(11, 11), (13, 9)], fill=rgba((240, 200, 60)))
    return img


def chest() -> Image.Image:
    """Two 16 x 16 frames side by side: closed, then open (the game swaps them on opening)."""
    img, d = canvas(32, 16)
    wood: Px = (150, 98, 50)
    d.rectangle([1, 5, 14, 14], fill=rgba(wood), outline=rgba(BLACK))
    d.rectangle([1, 5, 14, 8], fill=rgba(shade(wood, 28)), outline=rgba(BLACK))
    d.rectangle([6, 7, 9, 10], fill=rgba((240, 200, 60)), outline=rgba(BLACK))
    # open: the lid is raised behind the box and the inside shows gold
    d.rectangle([17, 8, 30, 14], fill=rgba(wood), outline=rgba(BLACK))
    d.rectangle([17, 8, 30, 9], fill=rgba((30, 20, 14)), outline=rgba(BLACK))
    d.rectangle([18, 10, 29, 11], fill=rgba((240, 200, 60)))
    d.rectangle([17, 1, 30, 6], fill=rgba(shade(wood, 28)), outline=rgba(BLACK))
    return img


def panel() -> Image.Image:
    """A 48 x 48 window panel with rounded corners (nine-slice border 6)."""
    img, d = canvas(48, 48)
    d.rounded_rectangle([0, 0, 47, 47], 6, fill=rgba((34, 38, 60)))
    d.rounded_rectangle([2, 2, 45, 45], 5, fill=rgba((52, 60, 96)), outline=rgba((190, 200, 230)))
    return img


# ------------------------------------------------------------------------------ the pack

FILES = {
    "tilesets/ground.png": ground_sheet,
    "tilesets/water.png": water_sheet,
    "tilesets/meadow_a2.png": meadow_a2_sheet,
    "tilesets/walls.png": wall_sheet,
    "objects/town.png": town_sheet,
    "characters/hero.png": lambda: character_sheet((60, 110, 200), (90, 52, 30)),
    "characters/npc_villager.png": lambda: character_sheet((190, 120, 60), (200, 200, 210)),
    "enemies/slime_idle.png": slime_strip,
    "portraits/elder.png": portrait,
    "items/potion.png": potion,
    "items/sword.png": sword,
    "items/coin.png": coin,
    "items/key.png": key,
    "items/chest.png": chest,
    "ui/panel.png": panel,
}

LICENSE_TEXT = """\
rpggen sample pack

This pack was generated by tools/build_sample_pack.py from this repository. Every image is
original work drawn by that script; nothing is copied from another asset pack.

To the extent possible under law, the author(s) have dedicated all copyright and related and
neighboring rights to this work to the public domain worldwide (CC0 1.0 Universal).
You can copy, modify, distribute and perform the work, even for commercial purposes, all
without asking permission. See https://creativecommons.org/publicdomain/zero/1.0/
"""

SOURCES_TEXT = """\
# Sources

This pack has no outside sources. Every file is generated by `tools/build_sample_pack.py`
(deterministic integer drawing with Pillow) and released under CC0-1.0.

| File | What it is |
| --- | --- |
| tilesets/ground.png | 8 x 2 ground tiles: grass, dirt, stone path and sand, with variants |
| tilesets/water.png | 4 x 2 water tiles |
| tilesets/meadow_a2.png | Two A2-style autotile blocks: grass on dirt, sand on grass |
| tilesets/walls.png | 4 x 2 stone brick wall tiles |
| objects/town.png | A house and two trees among a few loose tiles (objects in a sheet) |
| characters/hero.png | The hero: 4 walk frames in 4 directions, 16 x 24 per frame |
| characters/npc_villager.png | A villager with the same layout |
| enemies/slime_idle.png | A 4-frame slime strip |
| portraits/elder.png | A face portrait |
| items/*.png | Potion, sword, coin and key (16 x 16 each) and a chest (32 x 16: closed, open) |
| ui/panel.png | A window panel with a nine-slice border |
| music/town_theme.wav | A 24 second looping two-voice tune (map music) |
| music/battle_theme.wav | A 16 second looping battle tune |
| sfx/*.wav | Eight short effects: cursor blip, confirm, cancel, hit, swing, coin, chest, step |

The audio is synthesized from integer arithmetic (`tools/sample_audio.py`): mono, 16-bit, 22050 Hz,
about 2 MB in all.

`sample.rpgprofile.json` is the audit of this pack (made with the normal audit pipeline), so the
sample opens with every asset confirmed.
"""


def build_pack(out: Path) -> Path:
    """Write the images, LICENSE.txt and SOURCES.md into ``out``; returns ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    for rel, make in FILES.items():
        save_png(make(), out / rel)
    for rel, make_audio in sample_audio.FILES.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(make_audio())
    (out / "LICENSE.txt").write_text(LICENSE_TEXT, encoding="utf-8", newline="\n")
    (out / "SOURCES.md").write_text(SOURCES_TEXT, encoding="utf-8", newline="\n")
    return out


def _name_town_objects(cat, edits):  # noqa: ANN001, ANN202 - imported lazily with the pipeline
    """Give the three detected objects of the town sheet their real names and settings."""
    sheet = "sample_pack.objects.town"
    trees = 0
    for obj in sorted(cat.objects, key=lambda o: (o.region[1], o.region[0])):
        if obj.sheet != sheet:
            continue
        if obj.role == "BUILDING":
            changes = {
                "name": "house",
                "role": "BUILDING",
                "door": [40, 63],
                "tags": ["house", "door"],
            }
        else:
            trees += 1
            changes = {"name": f"tree_{trees}", "role": "DECORATION", "tags": ["tree"]}
        changes["id"] = f"{sheet}#{changes['name']}"
        changes["status"] = "CONFIRMED"
        cat = edits.update_object(cat, obj.id, **changes)
    return cat


def build_profile(pack: Path, profile_path: Path) -> dict:
    """Audit ``pack`` with the normal pipeline, confirm everything and export the profile."""
    import os

    from rpggen.core import archive, catalog, inventory, profiles
    from rpggen.gui import edits

    with tempfile.TemporaryDirectory() as cache:
        old = os.environ.get("RPGGEN_CACHE_DIR")
        os.environ["RPGGEN_CACHE_DIR"] = cache  # no installed profile may influence the audit
        try:
            opened = archive.open_pack(pack, set(), pack_id=PACK_NAME)
            inv = inventory.build_inventory(opened)
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
        finally:
            if old is None:
                del os.environ["RPGGEN_CACHE_DIR"]
            else:
                os.environ["RPGGEN_CACHE_DIR"] = old
    cat = _name_town_objects(cat, edits)
    cat = edits.set_override(cat, f"{PACK_NAME}.items.chest", "tags", ["chest"])
    # tagged as an A2 sheet, so the terrain step composes its blocks into 47-tile terrain atlases
    cat = edits.set_override(
        cat, f"{PACK_NAME}.tilesets.meadow_a2", "tags", ["rpgmaker_autotile", "A2"]
    )
    cat = edits.confirm(cat, [a.id for a in cat.assets if a.status != "UNUSED"])
    data = profiles.export_profile(
        cat,
        PACK_NAME,
        inv,
        {
            "profile_id": "rpggen_sample_pack",
            "title": PROFILE_TITLE,
            "author": "rpggen",
            "license": "CC0-1.0",
        },
    )
    profiles.write_profile(data, profile_path)
    return data


# ------------------------------------------------------------------------------ the side-view pack
# A second pack (T14.09): a cave seen from the side, for the metroidvania. Drawn the same way as
# the first, by this script only, so it needs no new licence.

SIDE_PACK_NAME = "sample_pack_side"
SIDE_PROFILE_NAME = "sample_side.rpgprofile.json"
SIDE_PROFILE_TITLE = "rpggen side-view sample pack"

CAVE: Px = (96, 88, 118)
CAVE_MOSS: Px = (96, 160, 104)
PLANK: Px = (156, 108, 62)
STEEL: Px = (206, 210, 222)
# cells of tiles/cave.png (column, row)
SIDE_ONE_WAY = ((4, 0), (5, 0), (6, 0))
SIDE_LADDER = ((7, 0), (7, 1))
SIDE_SPIKES = ((4, 1),)
SIDE_BREAKABLE = ((5, 1),)


def _rock(img: Image.Image, x0: int, y0: int, base: Px, seed: int, moss: bool) -> None:
    for y in range(16):
        for x in range(16):
            n = noise(x, y, seed)
            tone = shade(base, (n % 25) - 12 if n % 4 == 0 else 0)
            if (x + y * 3 + seed) % 11 == 0:
                tone = shade(base, -30)
            img.putpixel((x0 + x, y0 + y), rgba(tone))
    if moss:
        for x in range(16):
            depth = 3 + noise(x, 0, seed + 5) % 3
            for y in range(depth):
                img.putpixel((x0 + x, y0 + y), rgba(shade(CAVE_MOSS, 18 - y * 9)))


def cave_sheet() -> Image.Image:
    """8 x 2 tiles of 16 px. Columns 0 to 3: mossy ground (top row) and rock (bottom row).
    Top row, columns 4 to 6: a plank to jump through (left end, middle, right end); column 7: a
    ladder. Bottom row: spikes, a cracked block that breaks, a dark rock, the ladder's lower end."""
    img, d = canvas(128, 32)
    for col in range(4):
        _rock(img, col * 16, 0, shade(CAVE, col % 2 * 8), col + 1, True)
        _rock(img, col * 16, 16, shade(CAVE, -10 - col % 2 * 8), col + 9, False)
    # planks: the top 5 px of the cell
    d.rectangle([64, 0, 111, 4], fill=rgba(PLANK))
    d.line([(64, 4), (111, 4)], fill=rgba(shade(PLANK, -50)))
    d.line([(64, 0), (111, 0)], fill=rgba(shade(PLANK, 34)))
    for x in (64, 111):
        d.line([(x, 0), (x, 4)], fill=rgba(shade(PLANK, -50)))
    for x in (72, 88, 104):
        d.point([(x, 2)], fill=rgba(shade(PLANK, -60)))
    d.rectangle([66, 5, 67, 8], fill=rgba(shade(PLANK, -40)))  # brackets under both ends
    d.rectangle([108, 5, 109, 8], fill=rgba(shade(PLANK, -40)))
    # the ladder: two cells that join
    for y0 in (0, 16):
        d.rectangle([115, y0, 116, y0 + 15], fill=rgba(shade(PLANK, -46)))
        d.rectangle([123, y0, 124, y0 + 15], fill=rgba(shade(PLANK, -46)))
        for y in (2, 7, 12):
            d.rectangle([115, y0 + y, 124, y0 + y + 1], fill=rgba(PLANK))
    # spikes: four teeth on a base
    d.rectangle([64, 29, 79, 31], fill=rgba(shade(CAVE, -40)))
    for t in range(4):
        x = 64 + t * 4
        d.polygon([(x, 28), (x + 1, 20), (x + 2, 20), (x + 3, 28)], fill=rgba(STEEL))
        d.point([(x + 1, 20)], fill=rgba(WHITE))
    # the breakable block: lighter rock with cracks
    _rock(img, 80, 16, shade(CAVE, 34), 23, False)
    d.rectangle([80, 16, 95, 31], outline=rgba(shade(CAVE, -34)))
    d.line([(84, 17), (87, 22), (85, 26), (89, 30)], fill=rgba(BLACK))
    d.line([(87, 22), (92, 20)], fill=rgba(BLACK))
    _rock(img, 96, 16, shade(CAVE, -34), 31, False)
    return img


def _figure(
    d: ImageDraw.ImageDraw, ox: int, size: int, body: Px, hair: Px, pose: str, i: int
) -> None:
    """One frame of a person facing right, feet on the bottom row of a ``size`` px frame."""
    skin: Px = (240, 200, 160)
    lift = {"jump": 4, "fall": 2, "climb": 1 + i % 2}.get(pose, 0)
    lean = {"run": 1, "dash": 4, "attack": 1}.get(pose, 0)
    bob = i % 2 if pose in ("idle", "run") else 0
    cx = ox + size // 2 + lean
    feet = size - 1 - lift
    top = feet - 17 + bob
    d.rectangle(
        [cx - 4, top + 7, cx + 3, feet - 4], fill=rgba(body), outline=rgba(shade(body, -70))
    )
    d.rectangle([cx - 4, top, cx + 3, top + 6], fill=rgba(skin), outline=rgba(shade(skin, -90)))
    d.rectangle([cx - 4, top, cx + 3, top + 2], fill=rgba(hair))
    d.rectangle([cx - 4, top, cx - 3, top + 4], fill=rgba(hair))
    d.point([(cx + 1, top + 4)], fill=rgba(BLACK))  # one eye: the figure looks right
    stride = {"run": (i % 4 - 1) * 2 if i % 2 else 0, "jump": -1, "fall": 2, "dash": 3}.get(pose, 0)
    d.rectangle([cx - 3 - stride, feet - 3, cx - 2 - stride, feet], fill=rgba(shade(body, -60)))
    d.rectangle([cx + 1 + stride, feet - 3, cx + 2 + stride, feet], fill=rgba(shade(body, -60)))
    if pose == "attack":  # the blade swings out to the right
        reach = (2, 5, 4)[i % 3]
        d.line(
            [(cx + 4, top + 9), (cx + 4 + reach, top + 9 - (1 if i == 0 else 0))],
            fill=rgba(STEEL),
            width=2,
        )
    elif pose == "climb":
        d.point([(cx - 5, top + 8 + i % 2 * 3), (cx + 4, top + 11 - i % 2 * 3)], fill=rgba(skin))
    elif pose == "dash":
        d.line([(cx - 9, top + 9), (cx - 6, top + 9)], fill=rgba(WHITE))
        d.line([(cx - 10, top + 13), (cx - 6, top + 13)], fill=rgba(WHITE))
    elif pose == "hurt":
        d.rectangle([cx - 4, top + 7, cx + 3, feet - 4], fill=rgba((236, 232, 240)))


def side_strip(pose: str, frames: int, body: Px, hair: Px, size: int = 24) -> Image.Image:
    img, d = canvas(frames * size, size)
    for i in range(frames):
        _figure(d, i * size, size, body, hair, pose, i)
    return img


def crawler_strip() -> Image.Image:
    """A 4-frame beetle that walks to the right."""
    img, d = canvas(64, 16)
    shell: Px = (104, 168, 96)
    for i in range(4):
        ox = i * 16
        d.ellipse([ox + 2, 6, ox + 13, 14], fill=rgba(shell), outline=rgba(shade(shell, -70)))
        d.line([(ox + 5, 7), (ox + 5, 13)], fill=rgba(shade(shell, -40)))
        d.point([(ox + 11, 9)], fill=rgba(BLACK))
        step = i % 2
        d.point([(ox + 4 + step, 15), (ox + 8 - step, 15), (ox + 11 + step, 15)], fill=rgba(BLACK))
    return img


def bat_strip() -> Image.Image:
    """A 4-frame bat: the wings go up and down."""
    img, d = canvas(64, 16)
    fur: Px = (150, 96, 176)
    for i in range(4):
        ox = i * 16
        wing = (2, 5, 8, 5)[i]
        d.polygon([(ox + 7, 8), (ox + 1, wing), (ox + 3, 10)], fill=rgba(shade(fur, -30)))
        d.polygon([(ox + 8, 8), (ox + 14, wing), (ox + 12, 10)], fill=rgba(shade(fur, -30)))
        d.ellipse([ox + 5, 5, ox + 10, 11], fill=rgba(fur), outline=rgba(shade(fur, -70)))
        d.point([(ox + 6, 7), (ox + 9, 7)], fill=rgba(WHITE))
    return img


def guardian_strip(pose: str, frames: int) -> Image.Image:
    """The guardian, 32 x 32 per frame: a stone golem with one eye, facing right."""
    img, d = canvas(frames * 32, 32)
    stone: Px = (124, 112, 140)
    for i in range(frames):
        ox = i * 32
        bob = i % 2 if pose != "attack" else 0
        lean = 3 if pose == "attack" and i >= 1 else 0
        white = pose == "hurt"
        body = (236, 232, 240) if white else stone
        d.rounded_rectangle(
            [ox + 6 + lean, 6 + bob, ox + 25 + lean, 27],
            4,
            fill=rgba(body),
            outline=rgba(shade(stone, -70)),
        )
        d.rectangle([ox + 4 + lean, 12 + bob, ox + 7 + lean, 22], fill=rgba(shade(body, -24)))
        arm = 6 if pose == "attack" and i >= 1 else 0
        d.rectangle(
            [ox + 24 + lean, 12 + bob - arm // 2, ox + 28 + lean + arm // 2, 22 - arm],
            fill=rgba(shade(body, -24)),
        )
        d.rectangle([ox + 17 + lean, 11 + bob, ox + 22 + lean, 15 + bob], fill=rgba((250, 210, 90)))
        d.point([(ox + 20 + lean, 13 + bob)], fill=rgba(BLACK))
        step = (i % 2) * 2 if pose == "walk" else 0
        d.rectangle([ox + 8 + step, 28, ox + 13 + step, 31], fill=rgba(shade(stone, -50)))
        d.rectangle([ox + 18 - step, 28, ox + 23 - step, 31], fill=rgba(shade(stone, -50)))
    return img


def save_bench() -> Image.Image:
    """A 32 x 16 bench with a small light above it: a place to save."""
    img, d = canvas(32, 16)
    d.rectangle([2, 8, 29, 10], fill=rgba(PLANK), outline=rgba(shade(PLANK, -70)))
    d.rectangle([4, 11, 6, 15], fill=rgba(shade(PLANK, -50)))
    d.rectangle([25, 11, 27, 15], fill=rgba(shade(PLANK, -50)))
    d.rectangle([14, 2, 17, 5], fill=rgba((255, 236, 140)), outline=rgba((200, 150, 40)))
    d.point([(15, 6), (16, 7)], fill=rgba((255, 236, 140)))
    return img


def ability_orb(color: Px, mark: str) -> Image.Image:
    """A 16 x 16 orb; ``mark`` draws what it gives (two arrows up, or an arrow to the right)."""
    img, d = canvas(16, 16)
    d.ellipse([2, 2, 13, 13], fill=rgba(color), outline=rgba(shade(color, -90)))
    d.ellipse([4, 4, 6, 6], fill=rgba(shade(color, 70)))
    if mark == "up":
        d.line([(8, 5), (8, 11)], fill=rgba(WHITE))
        d.point([(7, 6), (9, 6), (7, 9), (9, 9)], fill=rgba(WHITE))
    else:
        d.line([(5, 8), (11, 8)], fill=rgba(WHITE))
        d.point([(10, 7), (10, 9)], fill=rgba(WHITE))
    return img


def side_sign() -> Image.Image:
    img, d = canvas(16, 16)
    d.rectangle([2, 2, 13, 9], fill=rgba(PLANK), outline=rgba(BLACK))
    d.line([(4, 5), (11, 5)], fill=rgba(shade(PLANK, -60)))
    d.rectangle([7, 10, 8, 15], fill=rgba(shade(PLANK, -50)))
    return img


def cave_background(depth: int) -> Image.Image:
    """A 320 x 180 parallax layer that repeats sideways. 1: the far wall, opaque. 2: columns of
    rock with gaps. 3: stalactites at the top and rubble at the bottom."""
    img, d = canvas(320, 180)
    if depth == 1:
        for y in range(180):
            for x in range(320):
                n = noise(x // 4, y // 4, 3)
                tone = shade((26, 24, 44), y // 14 + (6 if n % 5 == 0 else 0))
                img.putpixel((x, y), rgba(tone))
        return img
    if depth == 2:
        color: Px = (44, 40, 68)
        for k in range(5):
            x = k * 64 + 8
            width = 18 + noise(k, 1, 7) % 14
            d.rectangle([x, 0, x + width, 179], fill=rgba(shade(color, k % 2 * 6)))
            d.rectangle([x + width // 3, 0, x + width // 3 + 2, 179], fill=rgba(shade(color, -10)))
        return img
    color = (30, 26, 48)
    for k in range(16):
        x = k * 20
        length = 14 + noise(k, 2, 11) % 34
        d.polygon([(x, 0), (x + 19, 0), (x + 10, length)], fill=rgba(color))
        height = 4 + noise(k, 3, 11) % 12
        d.rectangle([x, 179 - height, x + 19, 179], fill=rgba(color))
    return img


def hermit_portrait() -> Image.Image:
    """A 48 x 48 face: the hermit of the last room."""
    img, d = canvas(48, 48)
    d.rectangle([0, 0, 47, 47], fill=rgba((52, 46, 78)))
    d.rounded_rectangle([12, 10, 35, 42], 8, fill=rgba((226, 190, 156)))
    d.rounded_rectangle([10, 6, 37, 18], 6, fill=rgba((206, 206, 216)))
    d.rectangle([17, 25, 20, 27], fill=rgba(BLACK))
    d.rectangle([28, 25, 31, 27], fill=rgba(BLACK))
    d.rounded_rectangle([15, 32, 32, 44], 5, fill=rgba((206, 206, 216)))
    d.line([(21, 35), (27, 35)], fill=rgba((150, 80, 70)))
    return img


HERO_BODY: Px = (60, 110, 200)
HERO_HAIR: Px = (90, 52, 30)
HERMIT_BODY: Px = (120, 96, 70)
HERMIT_HAIR: Px = (206, 206, 216)
HERO_STRIPS = (
    ("idle", 2), ("run", 4), ("jump", 2), ("fall", 2), ("climb", 2), ("attack", 3), ("dash", 2),
    ("hurt", 2),
)  # fmt: skip

SIDE_IMAGES = {
    "tiles/cave.png": cave_sheet,
    **{
        f"characters/hero_{pose}.png": (
            lambda pose=pose, n=n: side_strip(pose, n, HERO_BODY, HERO_HAIR)
        )
        for pose, n in HERO_STRIPS
    },
    "enemies/crawler_walk.png": crawler_strip,
    "enemies/bat_idle.png": bat_strip,
    **{
        f"boss/guardian_{pose}.png": (lambda pose=pose, n=n: guardian_strip(pose, n))
        for pose, n in (("idle", 2), ("walk", 2), ("attack", 3), ("hurt", 2))
    },
    "npc/hermit_idle.png": lambda: side_strip("idle", 2, HERMIT_BODY, HERMIT_HAIR),
    "portraits/hermit.png": hermit_portrait,
    "objects/save_bench.png": save_bench,
    "objects/sign.png": side_sign,
    "items/orb_double_jump.png": lambda: ability_orb((90, 190, 230), "up"),
    "items/orb_dash.png": lambda: ability_orb((240, 150, 70), "right"),
    "items/potion.png": potion,
    "items/coin.png": coin,
    "items/chest.png": chest,
    "backgrounds/bg_far.png": lambda: cave_background(1),
    "backgrounds/bg_mid.png": lambda: cave_background(2),
    "backgrounds/bg_near.png": lambda: cave_background(3),
    "ui/panel.png": panel,
}

SIDE_LICENSE_TEXT = LICENSE_TEXT.replace("rpggen sample pack", "rpggen side-view sample pack", 1)

SIDE_SOURCE_TEXT = """\
rpggen side-view sample pack: sources

This pack has no outside sources. Every file is generated by `tools/build_sample_pack.py --side`
(deterministic integer drawing with Pillow; the sounds by `tools/sample_audio.py`) and released
under CC0-1.0.

tiles/cave.png             8 x 2 tiles of 16 px: mossy ground and rock, a plank to jump through
                           (three cells), a ladder (two cells), spikes, a block that breaks
characters/hero_*.png      The hero facing right, 24 x 24 per frame: idle, run, jump, fall, climb,
                           attack, dash, hurt (one strip each)
enemies/crawler_walk.png   A beetle that walks its platform (4 frames)
enemies/bat_idle.png       A bat that flies (4 frames)
boss/guardian_*.png        The guardian, 32 x 32 per frame: idle, walk, attack, hurt
npc/hermit_idle.png        The hermit of the last room
portraits/hermit.png       His face
objects/save_bench.png     A bench to save at
objects/sign.png           A sign
items/orb_*.png            The orbs of two abilities: double jump and dash
items/*.png                Potion, coin (16 x 16 each) and a chest (32 x 16: closed, open)
backgrounds/bg_*.png       Three parallax layers of 320 x 180: far, mid, near
ui/panel.png               A window panel with a nine-slice border
music/*.wav, sfx/*.wav     The sounds of the first sample pack, and jump, land, dash, powerup

`sample_side.rpgprofile.json` is the audit of this pack (made with the normal audit pipeline), so
the sample opens with every asset confirmed.
"""


def build_side_pack(out: Path) -> Path:
    """Write the side-view pack into ``out``; returns ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    for rel, make in SIDE_IMAGES.items():
        save_png(make(), out / rel)
    for rel, make_audio in sample_audio.SIDE_FILES.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(make_audio())
    (out / "LICENSE.txt").write_text(SIDE_LICENSE_TEXT, encoding="utf-8", newline="\n")
    (out / "SOURCE.txt").write_text(SIDE_SOURCE_TEXT, encoding="utf-8", newline="\n")
    return out


def side_tile_overrides() -> dict[str, dict]:
    """What each special cell of tiles/cave.png is: the audit of the sheet, tile by tile."""
    out: dict[str, dict] = {}
    for col, row in SIDE_ONE_WAY:
        out[f"{col},{row}"] = {"collision": {"profile": "ONE_WAY"}}
    for col, row in SIDE_LADDER:
        out[f"{col},{row}"] = {"collision": {"profile": "LADDER"}}
    for col, row in SIDE_SPIKES:
        out[f"{col},{row}"] = {"collision": {"profile": "NONE"}, "custom": {"hazard": True}}
    for col, row in SIDE_BREAKABLE:
        out[f"{col},{row}"] = {"custom": {"breakable": True}}
    return dict(sorted(out.items()))


def build_side_profile(pack: Path, profile_path: Path) -> dict:
    """Audit the side-view pack with the normal pipeline, confirm everything, export the profile."""
    import os

    from rpggen.core import archive, catalog, inventory, profiles
    from rpggen.gui import edits

    with tempfile.TemporaryDirectory() as cache:
        old = os.environ.get("RPGGEN_CACHE_DIR")
        os.environ["RPGGEN_CACHE_DIR"] = cache  # no installed profile may influence the audit
        try:
            opened = archive.open_pack(pack, set(), pack_id=SIDE_PACK_NAME)
            inv = inventory.build_inventory(opened)
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
        finally:
            if old is None:
                del os.environ["RPGGEN_CACHE_DIR"]
            else:
                os.environ["RPGGEN_CACHE_DIR"] = old
    name = SIDE_PACK_NAME
    cat = edits.set_override(cat, f"{name}.tiles.cave", "tile_overrides", side_tile_overrides())
    cat = edits.set_override(cat, f"{name}.items.chest", "tags", ["chest"])
    cat = edits.set_override(cat, f"{name}.objects.save_bench", "role", "DECORATION")
    cat = edits.set_override(cat, f"{name}.objects.sign", "tags", ["sign"])
    cat = edits.confirm(cat, [a.id for a in cat.assets if a.status != "UNUSED"])
    data = profiles.export_profile(
        cat,
        name,
        inv,
        {
            "profile_id": "rpggen_sample_pack_side",
            "title": SIDE_PROFILE_TITLE,
            "author": "rpggen",
            "license": "CC0-1.0",
        },
    )
    profiles.write_profile(data, profile_path)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-profile", action="store_true")
    parser.add_argument(
        "--side", action="store_true", help="build the side-view pack (sample_pack_side/)"
    )
    args = parser.parse_args(argv)
    if args.side:
        out = args.out or REPO_ROOT / SIDE_PACK_NAME
        build_side_pack(out)
        print(f"wrote {len(SIDE_IMAGES)} images and {len(sample_audio.SIDE_FILES)} sounds to {out}")
        if not args.no_profile:
            build_side_profile(out, out / SIDE_PROFILE_NAME)
            print(f"wrote {out / SIDE_PROFILE_NAME}")
        return 0
    out = args.out or REPO_ROOT / PACK_NAME
    build_pack(out)
    print(f"wrote {len(FILES)} images and {len(sample_audio.FILES)} sounds to {out}")
    if not args.no_profile:
        build_profile(out, out / PROFILE_NAME)
        print(f"wrote {out / PROFILE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate the bundled CC0 sample pack (``sample_pack/``) and its profile.

Usage:
    python tools/build_sample_pack.py            # write the pack next to this repo's root
    python tools/build_sample_pack.py --out DIR  # write somewhere else (used by the tests)
    python tools/build_sample_pack.py --no-profile
    python tools/build_sample_pack.py --side     # the side-view pack, sample_pack_side/ (T14.09)
    python tools/build_sample_pack.py --kind shmup | gun | race   # an arcade pack (T16.17):
                                                 # sample_pack_shmup/, _gun/, _race/

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


# ------------------------------------------------------------------------------ the arcade packs
# Three small packs (T16.17), one for each kind of M16: *Star lane* for the shoot 'em up, *Jungle
# line* for the run and gun, *Dirt cup* for the racing game. Drawn the same way as the two
# above, by this script only; each is under 200 KB with its sounds and its profile.

SHOT: Px = (255, 240, 120)
FLAME: Px = (255, 150, 40)
HULL: Px = (90, 170, 230)
EARTH: Px = (126, 92, 60)
LEAF: Px = (70, 150, 74)
ASPHALT: Px = (112, 96, 76)  # the road of the Dirt cup is packed dirt
TURF: Px = (84, 156, 72)


def _strip(frames: list[Image.Image]) -> Image.Image:
    """The frames side by side, in one row."""
    w, h = frames[0].size
    img, _d = canvas(w * len(frames), h)
    for i, frame in enumerate(frames):
        img.paste(frame, (i * w, 0))
    return img


def _flipped(img: Image.Image) -> Image.Image:
    """Upside down: an enemy ship comes down the screen."""
    return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def explosion_strip() -> Image.Image:
    """Six frames of 24 x 24: a ball of fire that grows, then a ring that thins."""
    frames = []
    for i in range(6):
        img, d = canvas(24, 24)
        r = 3 + i * 8 // 5
        d.ellipse([12 - r, 12 - r, 11 + r, 11 + r], fill=rgba((255, 214 - i * 26, 60)))
        core = r - 2 - i
        if core > 0:
            d.ellipse([12 - core, 12 - core, 11 + core, 11 + core], fill=rgba(WHITE))
        hole = (i - 2) * 3
        if hole > 0:
            d.ellipse([12 - hole, 12 - hole, 11 + hole, 11 + hole], fill=(0, 0, 0, 0))
        frames.append(img)
    return _strip(frames)


def shot(kind: str) -> Image.Image:
    """An 8 x 8 shot that flies up: a bullet, a laser or a missile."""
    img, d = canvas(8, 8)
    if kind == "laser":
        d.rectangle([3, 0, 4, 7], fill=rgba((120, 240, 255)))
        d.point([(3, 0), (4, 7)], fill=rgba(WHITE))
    elif kind == "missile":
        d.rectangle([3, 1, 4, 5], fill=rgba((206, 210, 222)), outline=rgba(BLACK))
        d.point([(3, 0), (4, 0)], fill=rgba((220, 60, 60)))
        d.point([(3, 7), (4, 7)], fill=rgba(FLAME))
    else:
        d.rectangle([3, 2, 4, 5], fill=rgba(SHOT))
        d.point([(3, 1), (4, 6)], fill=rgba(WHITE))
    return img


# ---------------------------------------------------------------- Star lane (the shoot 'em up)

SHMUP_PACK_NAME = "sample_pack_shmup"


def player_ship() -> Image.Image:
    """Three frames of 24 x 24, the nose up: banking left, level, banking right."""
    frames = []
    for lean in (-2, 0, 2):
        img, d = canvas(24, 24)
        d.polygon([(2, 19), (11 + lean, 9), (12 + lean, 9), (21, 19), (12, 16)],
                  fill=rgba(shade(HULL, -40)), outline=rgba(BLACK))  # fmt: skip
        d.polygon([(11 + lean, 1), (12 + lean, 1), (15, 18), (8, 18)],
                  fill=rgba(HULL), outline=rgba(BLACK))  # fmt: skip
        d.rectangle([11 + lean // 2, 7, 12 + lean // 2, 10], fill=rgba(WHITE))
        d.rectangle([10, 19, 13, 21], fill=rgba(FLAME))
        d.point([(11, 22), (12, 22)], fill=rgba(SHOT))
        frames.append(img)
    return _strip(frames)


def enemy_ship(kind: int) -> Image.Image:
    """One of four small ships of 24 x 24, drawn nose up and turned to come down the screen."""
    img, d = canvas(24, 24)
    body: Px = ((214, 84, 84), (204, 120, 214), (236, 160, 70), (110, 200, 130))[kind]
    dark = rgba(shade(body, -60))
    if kind == 0:  # a dart
        d.polygon([(11, 2), (12, 2), (19, 20), (12, 16), (11, 16), (4, 20)],
                  fill=rgba(body), outline=rgba(BLACK))  # fmt: skip
    elif kind == 1:  # a saucer
        d.ellipse([3, 7, 20, 17], fill=rgba(body), outline=rgba(BLACK))
        d.ellipse([8, 4, 15, 11], fill=rgba(shade(body, 50)), outline=rgba(BLACK))
    elif kind == 2:  # a beetle with two wings
        d.rectangle([2, 10, 21, 13], fill=dark, outline=rgba(BLACK))
        d.rounded_rectangle([8, 3, 15, 20], 3, fill=rgba(body), outline=rgba(BLACK))
    else:  # a wing
        d.polygon([(2, 18), (11, 5), (12, 5), (21, 18), (17, 18), (12, 12), (11, 12), (6, 18)],
                  fill=rgba(body), outline=rgba(BLACK))  # fmt: skip
    d.rectangle([11, 8, 12, 10], fill=rgba((250, 236, 150)))
    return _flipped(img)


def turret() -> Image.Image:
    """A 24 x 24 gun on a round base: it stands on the stage and turns its barrel."""
    img, d = canvas(24, 24)
    d.ellipse([3, 3, 20, 20], fill=rgba((104, 112, 128)), outline=rgba(BLACK))
    d.ellipse([7, 7, 16, 16], fill=rgba((150, 160, 176)), outline=rgba(BLACK))
    d.rectangle([10, 12, 13, 22], fill=rgba((206, 210, 222)), outline=rgba(BLACK))
    return img


def carrier_ship() -> Image.Image:
    """A 32 x 24 ship with a hold: the one that carries a power-up."""
    img, d = canvas(32, 24)
    hold: Px = (96, 190, 214)
    d.polygon([(2, 14), (8, 4), (23, 4), (29, 14), (22, 20), (9, 20)],
              fill=rgba(hold), outline=rgba(BLACK))  # fmt: skip
    d.rectangle([12, 8, 19, 15], fill=rgba((250, 214, 90)), outline=rgba(BLACK))
    d.rectangle([4, 12, 7, 15], fill=rgba(shade(hold, -60)))
    d.rectangle([24, 12, 27, 15], fill=rgba(shade(hold, -60)))
    return _flipped(img)


def boss_ship() -> Image.Image:
    """The boss of a stage, 64 x 48: a hull with two engines and a core that glows."""
    img, d = canvas(64, 48)
    hull: Px = (170, 64, 96)
    d.polygon([(2, 20), (14, 6), (49, 6), (61, 20), (52, 40), (11, 40)],
              fill=rgba(hull), outline=rgba(BLACK))  # fmt: skip
    d.rectangle([6, 2, 15, 22], fill=rgba(shade(hull, -40)), outline=rgba(BLACK))
    d.rectangle([48, 2, 57, 22], fill=rgba(shade(hull, -40)), outline=rgba(BLACK))
    d.ellipse([24, 14, 39, 29], fill=rgba((250, 214, 90)), outline=rgba(BLACK))
    d.ellipse([28, 18, 35, 25], fill=rgba(WHITE))
    for x in (18, 30, 42):
        d.rectangle([x, 38, x + 3, 45], fill=rgba((206, 210, 222)), outline=rgba(BLACK))
    return _flipped(img)


def capsule(kind: int) -> Image.Image:
    """A 16 x 16 capsule: the stripe says what it gives (a weapon, a bomb, a life)."""
    img, d = canvas(16, 16)
    stripe: Px = ((250, 214, 90), (236, 110, 90), (110, 200, 130))[kind]
    d.rounded_rectangle([2, 4, 13, 11], 3, fill=rgba((230, 234, 244)), outline=rgba(BLACK))
    d.rectangle([6, 5, 9, 10], fill=rgba(stripe))
    d.point([(4, 6)], fill=rgba(WHITE))
    return img


def asteroid(size: int, seed: int) -> Image.Image:
    """A rock of ``size`` px: a round body with craters."""
    img, d = canvas(size, size)
    rock: Px = (136, 124, 116)
    d.ellipse([1, 2, size - 2, size - 3], fill=rgba(rock), outline=rgba(BLACK))
    for k in range(3):
        x = 4 + noise(k, 1, seed) % max(1, size - 10)
        y = 5 + noise(k, 2, seed) % max(1, size - 12)
        d.ellipse([x, y, x + 3, y + 2], fill=rgba(shade(rock, -40)))
    return img


def stars(far: bool) -> Image.Image:
    """A 128 x 256 layer that repeats downwards: the dark of space with small stars (opaque),
    or a few larger stars with nothing between them."""
    img = Image.new("RGBA", (128, 256), rgba((10, 10, 28)) if far else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(56 if far else 14):
        x, y = (i * 37 + 5) % 128, (i * 91 + 11) % 256
        if far:
            d.point([(x, y)], fill=rgba((170, 176, 220) if i % 3 else (110, 116, 170)))
        else:
            d.rectangle([x, y, x + 1, y + 1], fill=rgba((255, 250, 214)))
            d.point([(x - 1, y), (x + 2, y + 1)], fill=rgba((196, 190, 150)))
    return img


SHMUP_IMAGES = {
    "ships/player_ship.png": player_ship,
    **{f"enemies/enemy_ship_{k + 1}.png": (lambda k=k: enemy_ship(k)) for k in range(4)},
    "enemies/turret.png": turret,
    "enemies/carrier_ship.png": carrier_ship,
    "boss/boss_ship.png": boss_ship,
    "bullets/bullet.png": lambda: shot("bullet"),
    "bullets/laser.png": lambda: shot("laser"),
    "bullets/missile.png": lambda: shot("missile"),
    "fx/explosion_6frames.png": explosion_strip,
    **{f"powerups/capsule_{k + 1}.png": (lambda k=k: capsule(k)) for k in range(3)},
    "asteroids/asteroid_1.png": lambda: asteroid(24, 3),
    "asteroids/asteroid_2.png": lambda: asteroid(16, 8),
    "backgrounds/stars_far.png": lambda: stars(True),
    "backgrounds/stars_near.png": lambda: stars(False),
    "ui/panel.png": panel,
}

SHMUP_SOURCE_TEXT = """\
Star lane, the rpggen sample pack for a shoot 'em up: sources

This pack has no outside sources. Every file is generated by
`tools/build_sample_pack.py --kind shmup` (deterministic integer drawing with Pillow; the sounds
by `tools/sample_audio.py`) and released under CC0-1.0.

ships/player_ship.png      The ship, nose up, 24 x 24 per frame: banking left, level, right
enemies/enemy_ship_*.png   Four small ships that come down the screen
enemies/turret.png         A gun that stands on the stage
enemies/carrier_ship.png   A larger ship that carries a power-up
boss/boss_ship.png         The boss of a stage, 64 x 48
bullets/*.png              A bullet, a laser and a missile, 8 x 8 each, flying up
fx/explosion_6frames.png   An explosion in six frames of 24 x 24
powerups/capsule_*.png     Three capsules: a weapon, a bomb, a life
asteroids/asteroid_*.png   Two rocks to fly around
backgrounds/stars_*.png    Two layers of 128 x 256 that scroll: far and near
ui/panel.png               A window panel with a nine-slice border
music/*.wav                Three loops of 2.56 s: the stage, the boss, the title
sfx/*.wav                  Five sounds: shoot, explosion, powerup, bomb, hit

The sounds are mono, 8-bit, 11025 Hz, so that the whole pack is under 200 KB.
`sample_shmup.rpgprofile.json` is the audit of this pack (made with the normal audit pipeline),
so the sample opens with every asset confirmed.
"""


# ---------------------------------------------------------------- Jungle line (the run and gun)

GUN_PACK_NAME = "sample_pack_gun"
# cells of tiles/jungle.png (column, row)
GUN_ONE_WAY = ((4, 0), (5, 0), (6, 0))
GUN_SPIKES = ((4, 1),)
GUN_GRAPPLE = ((7, 0),)


def _earth(img: Image.Image, x0: int, y0: int, base: Px, seed: int, grass: bool) -> None:
    for y in range(16):
        for x in range(16):
            n = noise(x, y, seed)
            tone = shade(base, (n % 21) - 10 if n % 3 == 0 else 0)
            if (x * 2 + y + seed) % 13 == 0:
                tone = shade(base, -26)
            img.putpixel((x0 + x, y0 + y), rgba(tone))
    if grass:
        for x in range(16):
            depth = 3 + noise(x, 0, seed + 4) % 3
            for y in range(depth):
                img.putpixel((x0 + x, y0 + y), rgba(shade(LEAF, 20 - y * 10)))


def jungle_sheet() -> Image.Image:
    """8 x 2 tiles of 16 px. Columns 0 to 3: earth under grass (top row) and earth (bottom
    row). Top row, columns 4 to 6: a rope bridge to jump through (left end, middle, right end);
    column 7: a block with a ring under it, for the grapple. Bottom row: stakes, a crate, dark
    earth, stone."""
    img, d = canvas(128, 32)
    for col in range(4):
        _earth(img, col * 16, 0, shade(EARTH, col % 2 * 8), col + 1, True)
        _earth(img, col * 16, 16, shade(EARTH, -12 - col % 2 * 8), col + 9, False)
    # the bridge: the top 5 px of the cell
    d.rectangle([64, 0, 111, 4], fill=rgba(PLANK))
    d.line([(64, 0), (111, 0)], fill=rgba(shade(PLANK, 34)))
    d.line([(64, 4), (111, 4)], fill=rgba(shade(PLANK, -50)))
    for x in range(64, 112, 6):
        d.line([(x, 0), (x, 4)], fill=rgba(shade(PLANK, -50)))
    # the grapple block: stone with a ring that hangs from it
    _earth(img, 112, 0, (124, 124, 136), 41, False)
    d.rectangle([112, 0, 127, 15], outline=rgba((70, 70, 84)))
    d.ellipse([117, 9, 122, 14], outline=rgba((250, 214, 90)))
    # stakes: four points on a base
    d.rectangle([64, 29, 79, 31], fill=rgba(shade(EARTH, -40)))
    for t in range(4):
        x = 64 + t * 4
        d.polygon([(x, 28), (x + 1, 20), (x + 2, 20), (x + 3, 28)], fill=rgba((214, 200, 170)))
        d.point([(x + 1, 20)], fill=rgba(WHITE))
    # a crate
    d.rectangle([80, 16, 95, 31], fill=rgba(PLANK), outline=rgba(shade(PLANK, -70)))
    d.line([(80, 16), (95, 31)], fill=rgba(shade(PLANK, -50)))
    d.line([(95, 16), (80, 31)], fill=rgba(shade(PLANK, -50)))
    _earth(img, 96, 16, shade(EARTH, -40), 33, False)
    _earth(img, 112, 16, (124, 124, 136), 47, False)
    return img


def _soldier(
    d: ImageDraw.ImageDraw, ox: int, size: int, body: Px, band: Px, pose: str, i: int
) -> None:
    """One frame of a soldier facing right with a gun, feet on the bottom row of the frame."""
    skin: Px = (236, 196, 156)
    if pose == "death":  # falling back, then lying
        tilt = min(i, 2)
        y = size - 6 - (2 - tilt) * 3
        d.rectangle([ox + 5 - tilt, y, ox + 17 - tilt, y + 4], fill=rgba(body),
                    outline=rgba(shade(body, -70)))  # fmt: skip
        d.rectangle([ox + 2 - tilt, y - 1, ox + 6 - tilt, y + 4], fill=rgba(skin),
                    outline=rgba(shade(skin, -90)))  # fmt: skip
        d.rectangle([ox + 2 - tilt, y - 1, ox + 6 - tilt, y], fill=rgba(band))
        return
    lift = {"jump": 4, "fall": 2}.get(pose, 0)
    bob = i % 2 if pose in ("idle", "run") else 0
    cx = ox + size // 2 - 1 + (1 if pose == "run" else 0)
    feet = size - 1 - lift
    top = feet - 17 + bob
    torso = (236, 232, 240) if pose == "hurt" else body
    d.rectangle(
        [cx - 4, top + 7, cx + 3, feet - 4], fill=rgba(torso), outline=rgba(shade(body, -70))
    )
    d.rectangle([cx - 4, top, cx + 3, top + 6], fill=rgba(skin), outline=rgba(shade(skin, -90)))
    d.rectangle([cx - 4, top, cx + 3, top + 1], fill=rgba(band))  # a headband
    d.point([(cx - 5, top + 1), (cx - 6, top + 2)], fill=rgba(band))
    d.point([(cx + 1, top + 4)], fill=rgba(BLACK))
    stride = {"run": (i % 4 - 1) * 2 if i % 2 else 0, "jump": -1, "fall": 2}.get(pose, 0)
    d.rectangle([cx - 3 - stride, feet - 3, cx - 2 - stride, feet], fill=rgba(shade(body, -60)))
    d.rectangle([cx + 1 + stride, feet - 3, cx + 2 + stride, feet], fill=rgba(shade(body, -60)))
    # the gun: held forward; a shot kicks it back and shows a flash
    kick = (0, 1, 0)[i % 3] if pose == "shoot" else 0
    d.rectangle([cx + 2 - kick, top + 9, cx + 8 - kick, top + 10], fill=rgba((60, 62, 74)))
    d.point([(cx + 2 - kick, top + 11)], fill=rgba((60, 62, 74)))
    if pose == "shoot" and i % 3 == 1:
        d.rectangle([cx + 9, top + 8, cx + 10, top + 11], fill=rgba(SHOT))


def soldier_strip(pose: str, frames: int, body: Px, band: Px, size: int = 24) -> Image.Image:
    img, d = canvas(frames * size, size)
    for i in range(frames):
        _soldier(d, i * size, size, body, band, pose, i)
    return img


def gun_turret(wall: bool) -> Image.Image:
    """A 24 x 24 gun that looks left: on a base on the ground, or on a plate on a wall."""
    img, d = canvas(24, 24)
    steel: Px = (120, 126, 140)
    if wall:
        d.rectangle([16, 2, 23, 21], fill=rgba(shade(steel, -40)), outline=rgba(BLACK))
        d.ellipse([8, 6, 19, 17], fill=rgba(steel), outline=rgba(BLACK))
        d.rectangle([0, 10, 9, 13], fill=rgba((206, 210, 222)), outline=rgba(BLACK))
    else:
        d.polygon([(4, 23), (8, 14), (17, 14), (21, 23)], fill=rgba(shade(steel, -40)),
                  outline=rgba(BLACK))  # fmt: skip
        d.ellipse([7, 5, 18, 16], fill=rgba(steel), outline=rgba(BLACK))
        d.rectangle([0, 8, 9, 11], fill=rgba((206, 210, 222)), outline=rgba(BLACK))
    d.point([(13, 10)], fill=rgba((236, 110, 90)))
    return img


def wall_boss(pose: str) -> Image.Image:
    """The boss of a stage: a gate of steel, 64 x 64 per frame, two frames with a gap between
    them. It looks left; its core opens when it attacks."""
    img, d = canvas(128, 64)
    steel: Px = (98, 104, 122)
    for i in range(2):
        ox = i * 64
        d.rectangle([ox + 18, 0, ox + 59, 63], fill=rgba(steel), outline=rgba(BLACK))
        for y in (10, 30, 50):
            d.line([(ox + 19, y), (ox + 58, y)], fill=rgba(shade(steel, -36)))
            d.point([(ox + 22, y - 4), (ox + 55, y - 4)], fill=rgba(shade(steel, 50)))
        open_ = 6 if pose == "attack" and i == 1 else (1 if i else 0)
        d.rectangle(
            [ox + 28, 24 - open_, ox + 51, 39 + open_], fill=rgba((40, 30, 44)), outline=rgba(BLACK)
        )
        core: Px = (250, 120, 80) if pose == "attack" else (250, 214, 90)
        d.ellipse([ox + 35, 27, ox + 44, 36], fill=rgba(core), outline=rgba(BLACK))
        for y in (6, 52):  # two guns
            d.rectangle(
                [ox + 4, y, ox + 20, y + 4], fill=rgba((206, 210, 222)), outline=rgba(BLACK)
            )
    return img


def jungle_background(far: bool) -> Image.Image:
    """A 320 x 180 layer that repeats sideways: the sky over far hills (opaque), or trunks and
    leaves with the sky between them."""
    img, d = canvas(320, 180)
    if far:
        for y in range(180):
            d.line([(0, y), (319, y)], fill=rgba(shade((70, 130, 150), -y // 6)))
        for k in range(8):
            x = k * 40
            height = 40 + noise(k, 1, 5) % 30
            d.polygon([(x - 10, 179), (x + 20, 179 - height), (x + 50, 179)],
                      fill=rgba((40, 86, 78)))  # fmt: skip
        return img
    trunk: Px = (58, 44, 40)
    for k in range(5):
        x = k * 64 + 12
        width = 8 + noise(k, 2, 9) % 6
        d.rectangle([x, 30, x + width, 179], fill=rgba(trunk))
        d.ellipse([x - 22, 0, x + width + 22, 52], fill=rgba(shade(LEAF, -70 + k % 2 * 8)))
    return img


def weapon_pickup(kind: int) -> Image.Image:
    """A 16 x 16 badge with the mark of a weapon: spread, laser, flame, machine gun."""
    img, d = canvas(16, 16)
    tone: Px = ((236, 110, 90), (120, 240, 255), (255, 150, 40), (250, 214, 90))[kind]
    d.rounded_rectangle([1, 3, 14, 12], 2, fill=rgba((44, 48, 64)), outline=rgba(tone))
    if kind == 0:
        for dy in (-2, 0, 2):
            d.line([(4, 8), (11, 8 + dy)], fill=rgba(tone))
    elif kind == 1:
        d.line([(3, 8), (12, 8)], fill=rgba(tone))
        d.line([(3, 7), (12, 7)], fill=rgba(WHITE))
    elif kind == 2:
        d.polygon([(4, 10), (7, 5), (9, 8), (11, 5), (12, 10)], fill=rgba(tone))
    else:
        d.point([(4, 8), (6, 8), (8, 8), (10, 8), (12, 8)], fill=rgba(tone))
        d.point([(5, 6), (9, 6)], fill=rgba(tone))
    return img


def grapple_hook() -> Image.Image:
    """A 16 x 16 hook with three claws, pointing up."""
    img, d = canvas(16, 16)
    steel = rgba((206, 210, 222))
    d.line([(7, 6), (7, 15)], fill=steel, width=2)
    d.arc([2, 1, 8, 9], 180, 360, fill=steel)
    d.arc([7, 1, 13, 9], 180, 360, fill=steel)
    d.point([(2, 6), (13, 6), (7, 1), (8, 1)], fill=rgba(WHITE))
    return img


def mine() -> Image.Image:
    img, d = canvas(16, 16)
    d.ellipse([3, 7, 12, 15], fill=rgba((70, 74, 86)), outline=rgba(BLACK))
    d.rectangle([7, 4, 8, 7], fill=rgba((206, 210, 222)))
    d.point([(7, 3), (8, 3)], fill=rgba((236, 60, 60)))
    return img


def fern() -> Image.Image:
    """A 16 x 16 plant: scenery of a stage."""
    img, d = canvas(16, 16)
    for dx in (-5, -2, 2, 5):
        d.line([(8, 15), (8 + dx, 4 + abs(dx))], fill=rgba(shade(LEAF, dx * 4)), width=2)
    return img


GUN_BODY: Px = (86, 138, 84)
GUN_BAND: Px = (214, 70, 70)
SOLDIER_STRIPS = (
    ("idle", 2), ("run", 4), ("jump", 2), ("fall", 2), ("shoot", 3), ("hurt", 2), ("death", 3),
)  # fmt: skip

GUN_IMAGES = {
    "tiles/jungle.png": jungle_sheet,
    **{
        f"soldier/soldier_{pose}.png": (
            lambda pose=pose, n=n: soldier_strip(pose, n, GUN_BODY, GUN_BAND)
        )
        for pose, n in SOLDIER_STRIPS
    },
    "enemies/trooper_walk.png": lambda: soldier_strip("run", 4, (150, 96, 80), (60, 60, 70)),
    "enemies/leaper_walk.png": lambda: soldier_strip("run", 4, (120, 100, 160), (240, 220, 120)),
    "enemies/sniper_idle.png": lambda: soldier_strip("idle", 2, (96, 110, 130), (40, 40, 48)),
    "enemies/turret.png": lambda: gun_turret(False),
    "enemies/wall_cannon.png": lambda: gun_turret(True),
    "boss/gate_idle.png": lambda: wall_boss("idle"),
    "boss/gate_attack.png": lambda: wall_boss("attack"),
    "backgrounds/bg_far.png": lambda: jungle_background(True),
    "backgrounds/bg_near.png": lambda: jungle_background(False),
    **{
        f"pickups/weapon_pickup_{name}.png": (lambda k=k: weapon_pickup(k))
        for k, name in enumerate(("spread", "laser", "flame", "machinegun"))
    },
    "items/grapple_hook.png": grapple_hook,
    "bullets/bullet.png": lambda: shot("bullet"),
    "fx/explosion_6frames.png": explosion_strip,
    "hazards/mine.png": mine,
    "props/fern.png": fern,
    "ui/panel.png": panel,
}

GUN_SOURCE_TEXT = """\
Jungle line, the rpggen sample pack for a run and gun: sources

This pack has no outside sources. Every file is generated by
`tools/build_sample_pack.py --kind gun` (deterministic integer drawing with Pillow; the sounds
by `tools/sample_audio.py`) and released under CC0-1.0.

tiles/jungle.png           8 x 2 tiles of 16 px: earth under grass, a rope bridge to jump through
                           (three cells), a block with a ring for the grapple, stakes, a crate
soldier/soldier_*.png      The soldier facing right, 24 x 24 per frame: idle, run, jump, fall,
                           shoot, hurt, death (one strip each)
enemies/trooper_walk.png   A soldier that runs at you
enemies/leaper_walk.png    One that jumps
enemies/sniper_idle.png    One that stands and aims
enemies/turret.png         A gun on the ground
enemies/wall_cannon.png    A gun on a wall
boss/gate_*.png            The boss, a gate of steel, 64 x 64 per frame: idle, attack
backgrounds/bg_*.png       Two parallax layers of 320 x 180: far, near
pickups/weapon_pickup_*.png  Four weapons to pick up: spread, laser, flame, machine gun
items/grapple_hook.png     The hook of the grapple arm
bullets/bullet.png         A bullet, 8 x 8
fx/explosion_6frames.png   An explosion in six frames of 24 x 24
hazards/mine.png           A mine
props/fern.png             A plant
ui/panel.png               A window panel with a nine-slice border
music/*.wav                Two loops of 2.56 s: the stage, the boss
sfx/*.wav                  Six sounds: shoot, explosion, grenade, grapple, jump, weapon_pickup

The sounds are mono, 8-bit, 11025 Hz, so that the whole pack is under 200 KB.
`sample_gun.rpgprofile.json` is the audit of this pack (made with the normal audit pipeline), so
the sample opens with every asset confirmed.
"""


# ---------------------------------------------------------------- Dirt cup (the racing game)

RACE_PACK_NAME = "sample_pack_race"
CAR_HEADINGS = 16
CAR_CELL = 24


def car_ring(body: Px, stripe: Px) -> Image.Image:
    """A car seen from above in sixteen headings in a row of 24 x 24 cells, the first pointing
    up, each turned clockwise by one step from the one before. The points are turned by
    ``arcade_kit._turned``: exact for the quarter turns and rounded from values that are never
    near a half for the others, so every machine draws the same pixels."""
    from rpggen.core import arcade_kit

    img, d = canvas(CAR_HEADINGS * CAR_CELL, CAR_CELL)
    half = CAR_CELL / 2 - 0.25
    w, length = 5.52, 9.84
    hull = [(-w, -length * 0.55), (-w * 0.6, -length), (w * 0.6, -length), (w, -length * 0.55),
            (w, length), (-w, length)]  # fmt: skip
    cabin = [(-w * 0.62, -length * 0.2), (w * 0.62, -length * 0.2), (w * 0.62, length * 0.5),
             (-w * 0.62, length * 0.5)]  # fmt: skip
    band = [(-w * 0.2, -length * 0.95), (w * 0.2, -length * 0.95), (w * 0.2, -length * 0.25),
            (-w * 0.2, -length * 0.25)]  # fmt: skip
    for k in range(CAR_HEADINGS):
        cx = k * CAR_CELL + half
        d.polygon(arcade_kit._turned(hull, k, cx, half), fill=rgba(body), outline=rgba(BLACK))
        d.polygon(arcade_kit._turned(band, k, cx, half), fill=rgba(stripe))
        d.polygon(arcade_kit._turned(cabin, k, cx, half), fill=rgba((44, 52, 72)))
    return img


def road_sheet() -> Image.Image:
    """8 x 2 tiles of 16 px. Top row: packed dirt (plain, with ruts, with stones), the start
    line, and four tiles of grass. Bottom row: loose dirt, mud, and grass with flowers."""
    img, d = canvas(128, 32)
    for col in range(8):
        for row in range(2):
            x0, y0 = col * 16, row * 16
            dirt = (row == 0 and col < 4) or (row == 1 and col < 3)
            base = shade(ASPHALT if row == 0 else shade(ASPHALT, 16), 0) if dirt else TURF
            for y in range(16):
                for x in range(16):
                    n = noise(x, y, col + row * 8 + 1)
                    spread = 9 if dirt else 13
                    tone = shade(base, (n % spread) - spread // 2 if n % 3 == 0 else 0)
                    img.putpixel((x0 + x, y0 + y), rgba(tone))
    for x in (20, 27):  # ruts
        d.line([(x, 0), (x, 15)], fill=rgba(shade(ASPHALT, -22)))
    for x, y in ((35, 3), (41, 10), (38, 13), (45, 5)):  # stones
        d.point([(x, y)], fill=rgba(shade(ASPHALT, 46)))
    for i in range(0, 16, 4):  # the start line: chequered
        for j in range(0, 16, 4):
            tone = WHITE if (i + j) // 4 % 2 == 0 else BLACK
            d.rectangle([48 + i, j, 51 + i, j + 3], fill=rgba(tone))
    for x, y in ((6, 20), (11, 26), (3, 29)):  # mud
        d.ellipse([32 + x, y, 36 + x, y + 2], fill=rgba(shade(ASPHALT, -40)))
    for col in (5, 7):  # flowers
        for k in range(3):
            x = col * 16 + 3 + noise(k, col, 3) % 10
            y = 18 + noise(k, col, 4) % 10
            d.point([(x, y)], fill=rgba((250, 236, 150) if k % 2 else WHITE))
    return img


def cone() -> Image.Image:
    img, d = canvas(16, 16)
    d.polygon([(7, 2), (8, 2), (12, 13), (3, 13)], fill=rgba((240, 130, 40)), outline=rgba(BLACK))
    d.line([(5, 8), (10, 8)], fill=rgba(WHITE))
    d.rectangle([2, 13, 13, 14], fill=rgba((200, 100, 30)), outline=rgba(BLACK))
    return img


def tyre() -> Image.Image:
    img, d = canvas(16, 16)
    d.ellipse([2, 2, 13, 13], fill=rgba((44, 44, 50)), outline=rgba(BLACK))
    d.ellipse([5, 5, 10, 10], fill=rgba((90, 90, 100)), outline=rgba(BLACK))
    return img


def oil() -> Image.Image:
    img, d = canvas(16, 16)
    d.ellipse([1, 4, 14, 12], fill=rgba((26, 26, 36)))
    d.ellipse([4, 2, 10, 8], fill=rgba((26, 26, 36)))
    d.line([(5, 6), (8, 5)], fill=rgba((110, 120, 170)))
    return img


def boost_arrow() -> Image.Image:
    """A 16 x 16 arrow that points up: drive over it for a push."""
    img, d = canvas(16, 16)
    for y0 in (2, 8):
        arrow = [(8, y0), (13, y0 + 5), (10, y0 + 5), (8, y0 + 3), (7, y0 + 3), (5, y0 + 5),
                 (2, y0 + 5), (7, y0)]  # fmt: skip
        d.polygon(arrow, fill=rgba((90, 220, 255)), outline=rgba((30, 90, 130)))
    return img


def race_pickup(kind: int) -> Image.Image:
    """A 16 x 16 box with what it holds: a missile, a bomb, a shield."""
    img, d = canvas(16, 16)
    tone: Px = ((236, 110, 90), (250, 214, 90), (110, 200, 240))[kind]
    d.rounded_rectangle([2, 2, 13, 13], 2, fill=rgba((230, 234, 244)), outline=rgba(BLACK))
    if kind == 0:
        d.rectangle([7, 4, 8, 10], fill=rgba(tone))
        d.point([(6, 11), (9, 11)], fill=rgba(tone))
    elif kind == 1:
        d.ellipse([5, 6, 10, 11], fill=rgba((44, 44, 50)))
        d.point([(9, 5), (10, 4)], fill=rgba(tone))
    else:
        d.arc([4, 4, 11, 11], 0, 360, fill=rgba(tone))
        d.point([(7, 7), (8, 8)], fill=rgba(tone))
    return img


def trackside_tree() -> Image.Image:
    img, d = canvas(16, 16)
    d.ellipse([1, 1, 14, 14], fill=rgba(shade(LEAF, -30)), outline=rgba(shade(LEAF, -90)))
    d.ellipse([4, 3, 10, 9], fill=rgba(shade(LEAF, 16)))
    return img


def grandstand() -> Image.Image:
    """A 32 x 16 stand seen from above: rows of seats under a roof edge."""
    img, d = canvas(32, 16)
    d.rectangle([0, 0, 31, 15], fill=rgba((150, 156, 172)), outline=rgba(BLACK))
    for row in range(3):
        for seat in range(7):
            tone = ((214, 84, 84), (90, 170, 230), (250, 214, 90))[(row + seat) % 3]
            d.rectangle([3 + seat * 4, 3 + row * 4, 4 + seat * 4, 4 + row * 4], fill=rgba(tone))
    return img


RACE_IMAGES = {
    "cars/player_car.png": lambda: car_ring((220, 60, 60), (250, 236, 150)),
    "cars/rival_car_1.png": lambda: car_ring((70, 130, 220), WHITE),
    "cars/rival_car_2.png": lambda: car_ring((90, 180, 100), (250, 236, 150)),
    "cars/rival_car_3.png": lambda: car_ring((236, 170, 60), (60, 60, 70)),
    "tiles/road.png": road_sheet,
    "props/cone.png": cone,
    "props/tyre.png": tyre,
    "hazards/oil.png": oil,
    "pickups/boost.png": boost_arrow,
    **{
        f"pickups/pickup_{name}.png": (lambda k=k: race_pickup(k))
        for k, name in enumerate(("strike", "bomb", "shield"))
    },
    "scenery/tree.png": trackside_tree,
    "scenery/grandstand.png": grandstand,
    "ui/panel.png": panel,
}

RACE_SOURCE_TEXT = """\
Dirt cup, the rpggen sample pack for a racing game: sources

This pack has no outside sources. Every file is generated by
`tools/build_sample_pack.py --kind race` (deterministic integer drawing with Pillow; the sounds
by `tools/sample_audio.py`) and released under CC0-1.0.

cars/player_car.png        The car from above in 16 headings, 24 x 24 each, the first pointing up
cars/rival_car_*.png       Three rivals, drawn the same way
tiles/road.png             8 x 2 tiles of 16 px: packed dirt, the start line, grass, mud
props/cone.png             A cone
props/tyre.png             A tyre of the barriers
hazards/oil.png            An oil slick
pickups/boost.png          A boost arrow
pickups/pickup_*.png       Three boxes: a strike (a missile), a bomb, a shield
scenery/tree.png           A tree beside the track
scenery/grandstand.png     A stand, 32 x 16
ui/panel.png               A window panel with a nine-slice border
music/*.wav                Two loops of 2.56 s: the race, the results
sfx/*.wav                  Six sounds: engine, skid, bump, pickup, lap, countdown

The sounds are mono, 8-bit, 11025 Hz, so that the whole pack is under 200 KB.
`sample_race.rpgprofile.json` is the audit of this pack (made with the normal audit pipeline), so
the sample opens with every asset confirmed.
"""


# ---------------------------------------------------------------- building the three


def _gun_overrides(cat, edits, name):  # noqa: ANN001, ANN202 - imported lazily with the pipeline
    tiles: dict[str, dict] = {}
    for col, row in GUN_ONE_WAY:
        tiles[f"{col},{row}"] = {"collision": {"profile": "ONE_WAY"}}
    for col, row in GUN_SPIKES:
        tiles[f"{col},{row}"] = {"collision": {"profile": "NONE"}, "custom": {"hazard": True}}
    cat = edits.set_override(
        cat, f"{name}.tiles.jungle", "tile_overrides", dict(sorted(tiles.items()))
    )
    for weapon in ("spread", "laser", "flame", "machinegun"):  # a weapon to pick up is a power-up
        cat = edits.set_override(cat, f"{name}.pickups.weapon_pickup_{weapon}", "role", "POWERUP")
    cat = edits.set_override(cat, f"{name}.hazards.mine", "role", "HAZARD")
    cat = edits.set_override(cat, f"{name}.fx.explosion_6frames", "role", "EXPLOSION")
    return edits.set_override(cat, f"{name}.props.fern", "role", "DECORATION")


def _race_overrides(cat, edits, name):  # noqa: ANN001, ANN202
    for n in (1, 2, 3):  # the other cars are who you race against
        cat = edits.set_override(cat, f"{name}.cars.rival_car_{n}", "role", "ENEMY")
    for prop in ("tree", "grandstand"):
        cat = edits.set_override(cat, f"{name}.scenery.{prop}", "role", "DECORATION")
    return cat


# kind -> (folder, title, profile file, profile id, images, sounds, SOURCE.txt, the audit's edits)
ARCADE_PACKS: dict[str, tuple] = {
    "shmup": (SHMUP_PACK_NAME, "Star lane", "sample_shmup.rpgprofile.json",
              "rpggen_sample_pack_shmup", SHMUP_IMAGES, sample_audio.SHMUP_FILES,
              SHMUP_SOURCE_TEXT, None),
    "gun": (GUN_PACK_NAME, "Jungle line", "sample_gun.rpgprofile.json",
            "rpggen_sample_pack_gun", GUN_IMAGES, sample_audio.GUN_FILES, GUN_SOURCE_TEXT,
            _gun_overrides),
    "race": (RACE_PACK_NAME, "Dirt cup", "sample_race.rpgprofile.json",
             "rpggen_sample_pack_race", RACE_IMAGES, sample_audio.RACE_FILES, RACE_SOURCE_TEXT,
             _race_overrides),
}  # fmt: skip


def build_arcade_pack(kind: str, out: Path) -> Path:
    """Write the pack of ``kind`` (``shmup``, ``gun`` or ``race``) into ``out``; returns it."""
    _name, title, _profile, _id, images, sounds, source, _edit = ARCADE_PACKS[kind]
    out.mkdir(parents=True, exist_ok=True)
    for rel, make in images.items():
        save_png(make(), out / rel)
    for rel, make_audio in sounds.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(make_audio())
    licence = LICENSE_TEXT.replace("rpggen sample pack", f"{title}, an rpggen sample pack", 1)
    (out / "LICENSE.txt").write_text(licence, encoding="utf-8", newline="\n")
    (out / "SOURCE.txt").write_text(source, encoding="utf-8", newline="\n")
    return out


def build_arcade_profile(kind: str, pack: Path, profile_path: Path) -> dict:
    """Audit the pack with the normal pipeline, confirm everything and export the profile."""
    import os

    from rpggen.core import archive, catalog, inventory, profiles
    from rpggen.gui import edits

    name, title, _profile, profile_id, _images, _sounds, _source, edit = ARCADE_PACKS[kind]
    with tempfile.TemporaryDirectory() as cache:
        old = os.environ.get("RPGGEN_CACHE_DIR")
        os.environ["RPGGEN_CACHE_DIR"] = cache  # no installed profile may influence the audit
        try:
            opened = archive.open_pack(pack, set(), pack_id=name)
            inv = inventory.build_inventory(opened)
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
        finally:
            if old is None:
                del os.environ["RPGGEN_CACHE_DIR"]
            else:
                os.environ["RPGGEN_CACHE_DIR"] = old
    if edit is not None:
        cat = edit(cat, edits, name)
    cat = edits.confirm(cat, [a.id for a in cat.assets if a.status != "UNUSED"])
    data = profiles.export_profile(
        cat,
        name,
        inv,
        {
            "profile_id": profile_id,
            "title": f"{title} (rpggen sample pack)",
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
    parser.add_argument(
        "--kind",
        choices=sorted(ARCADE_PACKS),
        help="build the sample pack of an arcade kind (sample_pack_shmup/, _gun/, _race/)",
    )
    args = parser.parse_args(argv)
    if args.kind:
        name, _title, profile, _id, images, sounds, _source, _edit = ARCADE_PACKS[args.kind]
        out = args.out or REPO_ROOT / name
        build_arcade_pack(args.kind, out)
        print(f"wrote {len(images)} images and {len(sounds)} sounds to {out}")
        if not args.no_profile:
            build_arcade_profile(args.kind, out, out / profile)
            print(f"wrote {out / profile}")
        return 0
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

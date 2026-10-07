"""Generate the bundled CC0 sample pack (``sample_pack/``) and its profile.

Usage:
    python tools/build_sample_pack.py            # write the pack next to this repo's root
    python tools/build_sample_pack.py --out DIR  # write somewhere else (used by the tests)
    python tools/build_sample_pack.py --no-profile

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / PACK_NAME)
    parser.add_argument("--no-profile", action="store_true")
    args = parser.parse_args(argv)
    build_pack(args.out)
    print(f"wrote {len(FILES)} images and {len(sample_audio.FILES)} sounds to {args.out}")
    if not args.no_profile:
        build_profile(args.out, args.out / PROFILE_NAME)
        print(f"wrote {args.out / PROFILE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Drawn stand-ins for the farm (T17.02).

A farm needs crops that grow, soil that is tilled and watered, four tools, seeds, a hen and her
egg, a shipping bin, a bed and rain; and, for the pond and the edges of the farm (T17.10), a
fishing rod, fish to catch and things to forage. A pack made for another kind of game has none
of them, and
a farming pack may miss one. Rather than refusing to make a game, rpggen draws what is missing,
plainly, in the pack's tile size, and says so with a note (``ASSET-031``), as ``arcade_kit.py``
does for the arcade kinds. A pack's own asset always wins.

A crop the packs have as one picture (``ASSET-034``) gets a strip too: three drawn stages and a
bud, then its own picture as the ripe one (``grown``).

The pictures are drawn from integer arithmetic, so they are the same on every machine.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from rpggen.core import catalog as catalog_mod
from rpggen.errors import IssueList

KIT_PACK = "rpggen_farm_kit"
KIT_DIR = "generated/farm_kit"
KIT_TAG = "farm_kit"
GROWN_DIR = "grown"  # the strips made of a pack's single crop pictures, under KIT_DIR
GROWN_TAG = "grown_from:"  # ... each tagged with the id of the picture it ends in
CROP_STAGES = 5
MIN_CROPS = 2  # with fewer crops that grow the three drawn ones are added (crop_plan's rule)
HEN_FRAMES = 4
HEN_ROWS = ("down", "left", "right", "up")  # the rows of the hen's sheet, top to bottom
RAIN_FRAMES = 3
RAIN_TILES = 4  # the rain's cell is this many tiles a side; it repeats over the screen
_INACTIVE = {"UNUSED", "MISSING"}

Color = tuple[int, int, int, int]
CLEAR: Color = (0, 0, 0, 0)
DARK: Color = (44, 34, 30, 255)
WHITE: Color = (240, 240, 240, 255)
WOOD: Color = (140, 92, 51, 255)
WOOD_LIGHT: Color = (176, 124, 72, 255)
STEEL: Color = (191, 196, 204, 255)
CAN: Color = (102, 140, 178, 255)
BAG: Color = (204, 173, 115, 255)
LEAF: Color = (76, 158, 64, 255)
STEM: Color = (56, 118, 52, 255)
EARTH: Color = (120, 86, 56, 255)
TILLED: Color = (107, 74, 46, 255)
FURROW: Color = (80, 55, 34, 255)
WET: Color = (69, 51, 41, 255)
WET_FURROW: Color = (52, 38, 31, 255)
SEED: Color = (226, 208, 150, 255)
SHELL: Color = (246, 236, 212, 255)
RED: Color = (214, 60, 52, 255)
ORANGE: Color = (236, 150, 44, 255)
BLANKET: Color = (70, 110, 180, 255)
RAIN: Color = (170, 200, 255, 200)
# the three drawn crops and the colour of what they bear, as ``crop_plan.DRAWN`` names them
CROPS: tuple[tuple[str, Color], ...] = (
    ("turnip", (232, 224, 240, 255)),
    ("carrot", (232, 134, 46, 255)),
    ("berry", (212, 58, 92, 255)),
)
# The tools, and the words a pack's own picture of one is known by in its file name.
TOOL_WORDS: dict[str, tuple[str, ...]] = {
    "hoe": ("hoe",),
    "watering_can": ("watering", "water", "can", "wateringcan"),
    "sickle": ("sickle", "scythe"),
    "axe": ("axe", "hatchet"),
    "fishing_rod": ("rod", "fishingrod"),
}
TOOLS = tuple(TOOL_WORDS)
LINE: Color = (230, 232, 236, 255)
SCALE: Color = (250, 250, 250, 140)
# the three drawn fish and the colour of each, as ``forage_plan.DRAWN_FISH`` names them
FISH: tuple[tuple[str, Color], ...] = (
    ("perch", (126, 168, 92, 255)),
    ("carp", (226, 142, 62, 255)),
    ("eel", (84, 96, 132, 255)),
)
# the four drawn things to forage, one a season, as ``forage_plan.DRAWN_FORAGE`` names them
FORAGE = ("wild_herb", "wild_berries", "mushroom", "winter_root")
BERRY: Color = (112, 72, 168, 255)
CAP: Color = (190, 70, 56, 255)
ROOT: Color = (206, 170, 120, 255)


def _new(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (max(1, width), max(1, height)), CLEAR)
    return img, ImageDraw.Draw(img)


def _size(tile: int) -> int:
    return max(8, int(tile))


def _q(tile: int, sixteenths: int) -> int:
    """``sixteenths`` of a tile in pixels: the pictures are laid out on a grid of 16."""
    return sixteenths * tile // 16


def _box(t: int, x0: int, y0: int, x1: int, y1: int, dx: int = 0, dy: int = 0) -> list[int]:
    """The pixels from ``(x0, y0)`` up to, not with, ``(x1, y1)``, all in sixteenths of a tile:
    never thinner than a pixel."""
    left, top = dx + _q(t, x0), dy + _q(t, y0)
    return [left, top, max(left, dx + _q(t, x1) - 1), max(top, dy + _q(t, y1) - 1)]


# --------------------------------------------------------------------------- the pictures


def _plant(d: ImageDraw.ImageDraw, cx: int, base: int, t: int, stage: int, fruit: Color) -> None:
    """One stage of a crop that stands on the row ``base`` around the column ``cx``: seeds in a
    mound, a sprout, a plant, a plant in bud, and (the last of ``CROP_STAGES``) one that bears."""
    u = max(1, t // 8)
    d.ellipse([cx - 2 * u, base - u, cx + 2 * u - 1, base], fill=EARTH)
    if stage == 0:
        d.rectangle([cx - u, base - u, cx - u + max(0, u // 2 - 1), base - u], fill=SEED)
        d.rectangle([cx + u // 2, base - u, cx + u // 2 + max(0, u // 2 - 1), base - u], fill=SEED)
        return
    height = (0, t * 3 // 8, t * 3 // 4, t * 9 // 8, t * 3 // 2)[stage]
    d.rectangle([cx - (u + 1) // 2, base - height, cx - (u + 1) // 2 + u - 1, base - u], fill=STEM)
    pairs = min(stage, 3)
    reach = min(t // 2 - 1, u * (stage + 1))
    rows = [base - k * height // (pairs + 1) for k in range(1, pairs + 1)]
    for y in rows:
        d.ellipse([cx - reach, y - u, cx - 1, y], fill=LEAF)
        d.ellipse([cx, y - u, cx + reach - 1, y], fill=LEAF)
    if stage == 3:  # in bud
        d.rectangle([cx - (u + 1) // 2, base - height - u, cx + u // 2, base - height], fill=fruit)
    elif stage >= 4:
        r = max(2, t * 3 // 16)
        for fx, fy in ((cx, base - height), (cx - reach + r, rows[0]), (cx + reach - r, rows[0])):
            d.ellipse([fx - r, fy - r, fx + r - 1, fy + r - 1], fill=fruit, outline=DARK)


def crop(tile: int, fruit: Color = CROPS[0][1]) -> Image.Image:
    """A crop's growth in ``CROP_STAGES`` cells in a row, each a tile wide and two high, the
    last the ripe one. The three crops differ by the colour of what they bear."""
    t = _size(tile)
    img, d = _new(t * CROP_STAGES, t * 2)
    for stage in range(CROP_STAGES):
        _plant(d, stage * t + t // 2, t * 2 - 1, t, stage, fruit)
    return img


def _mean_color(picture: Image.Image) -> Color:
    """The colour of a picture: the mean of its pixels that are not clear (whole numbers)."""
    pixels = np.asarray(picture.convert("RGBA"))
    solid = pixels[pixels[..., 3] > 0]
    if not len(solid):
        return CROPS[0][1]
    r, g, b = (int(v) // len(solid) for v in solid[:, :3].sum(axis=0, dtype=np.int64))
    return (r, g, b, 255)


def grown(picture: Image.Image, tile: int) -> Image.Image:
    """The growth strip of a crop the packs have as one picture: the drawn stages, in bud in
    the picture's colour, and the picture itself as the ripe one. A cell is a tile wide and two
    high, or as large as the picture when that is larger."""
    t = _size(tile)
    ripe = picture.convert("RGBA")
    cw, ch = max(t, ripe.width), max(t * 2, ripe.height)
    img, d = _new(cw * CROP_STAGES, ch)
    fruit = _mean_color(ripe)
    for stage in range(CROP_STAGES - 1):
        _plant(d, stage * cw + cw // 2, ch - 1, t, stage, fruit)
    left = (CROP_STAGES - 1) * cw + (cw - ripe.width) // 2
    img.paste(ripe, (left, ch - ripe.height))
    return img


def _soil(tile: int, ground: Color, furrow: Color) -> Image.Image:
    t = _size(tile)
    img, d = _new(t, t)
    d.rectangle([0, 0, t - 1, t - 1], fill=ground)
    for row in (2, 6, 10, 14):
        d.rectangle(_box(t, 1, row, 15, row + 1), fill=furrow)
    return img


def soil(tile: int) -> Image.Image:
    """Tilled soil: one tile with its furrows."""
    return _soil(tile, TILLED, FURROW)


def watered(tile: int) -> Image.Image:
    """Watered soil: the same tile, dark with water."""
    return _soil(tile, WET, WET_FURROW)


def tool_icon(tile: int, kind: str) -> Image.Image:
    """The icon of one of ``TOOLS``, a tile a side."""
    t = _size(tile)
    img, d = _new(t, t)
    if kind == "hoe":
        d.rectangle(_box(t, 7, 3, 9, 15), fill=WOOD)
        d.rectangle(_box(t, 4, 2, 11, 5), fill=STEEL, outline=DARK)
    elif kind == "watering_can":
        d.rectangle(_box(t, 1, 7, 4, 12), outline=CAN)  # the handle
        d.rectangle(_box(t, 12, 5, 15, 7), fill=CAN)  # the spout
        d.rectangle(_box(t, 4, 6, 12, 14), fill=CAN, outline=DARK)
        d.rectangle(_box(t, 5, 7, 11, 8), fill=WHITE)
    elif kind == "sickle":
        d.rectangle(_box(t, 7, 9, 9, 15), fill=WOOD)
        d.arc([_q(t, 3), _q(t, 1), _q(t, 13), _q(t, 12)], start=170, end=20, fill=STEEL,
              width=max(2, t // 8))  # fmt: skip
    elif kind == "axe":
        d.rectangle(_box(t, 7, 3, 9, 15), fill=WOOD)
        head = [(_q(t, 9), _q(t, 3)), (_q(t, 13), _q(t, 2)), (_q(t, 13), _q(t, 9)),
                (_q(t, 9), _q(t, 8))]  # fmt: skip
        d.polygon(head, fill=STEEL, outline=DARK)
    elif kind == "fishing_rod":
        d.line([(_q(t, 3), _q(t, 14)), (_q(t, 13), _q(t, 2))], fill=WOOD, width=max(1, t // 8))
        d.rectangle(_box(t, 4, 10, 7, 13), fill=STEEL, outline=DARK)  # the reel
        d.line([(_q(t, 13), _q(t, 2)), (_q(t, 13), _q(t, 10))], fill=LINE)
        d.rectangle(_box(t, 12, 10, 14, 12), fill=RED)  # the float
    else:
        raise ValueError(f"no such tool: {kind}")
    return img


def fish(tile: int, body: Color = FISH[0][1]) -> Image.Image:
    """A fish seen from the side, its head to the left, a tile a side. The three fish differ by
    their colour."""
    t = _size(tile)
    img, d = _new(t, t)
    tail = [(_q(t, 11), _q(t, 8)), (_q(t, 15), _q(t, 4)), (_q(t, 15), _q(t, 12))]
    d.polygon(tail, fill=body, outline=DARK)
    d.ellipse(_box(t, 1, 4, 13, 12), fill=body, outline=DARK)
    d.rectangle(_box(t, 6, 6, 10, 7), fill=SCALE)
    d.rectangle(_box(t, 3, 7, 4, 8), fill=DARK)
    return img


def forage(tile: int, kind: str) -> Image.Image:
    """One of ``FORAGE`` as it lies on the ground, a tile a side: a herb in spring, berries in
    summer, a mushroom in autumn, a root in winter."""
    t = _size(tile)
    img, d = _new(t, t)
    if kind == "wild_herb":
        d.rectangle(_box(t, 7, 6, 9, 15), fill=STEM)
        for x0, y0 in ((2, 4), (9, 3), (3, 9), (9, 8)):
            d.ellipse(_box(t, x0, y0, x0 + 5, y0 + 4), fill=LEAF, outline=STEM)
    elif kind == "wild_berries":
        d.ellipse(_box(t, 2, 6, 14, 15), fill=LEAF, outline=STEM)
        for x0, y0 in ((4, 8), (9, 7), (7, 11)):
            d.ellipse(_box(t, x0, y0, x0 + 3, y0 + 3), fill=BERRY, outline=DARK)
    elif kind == "mushroom":
        d.rectangle(_box(t, 6, 9, 10, 15), fill=SHELL, outline=DARK)
        d.pieslice([_q(t, 2), _q(t, 3), _q(t, 14) - 1, _q(t, 17) - 1], start=180, end=360,
                   fill=CAP, outline=DARK)  # fmt: skip
        d.rectangle(_box(t, 5, 6, 6, 7), fill=WHITE)
        d.rectangle(_box(t, 9, 5, 11, 7), fill=WHITE)
    elif kind == "winter_root":
        root = [(_q(t, 4), _q(t, 6)), (_q(t, 12), _q(t, 6)), (_q(t, 8), _q(t, 15))]
        d.polygon(root, fill=ROOT, outline=DARK)
        d.rectangle(_box(t, 7, 2, 9, 6), fill=STEM)
        d.rectangle(_box(t, 5, 3, 7, 5), fill=LEAF)
        d.rectangle(_box(t, 9, 3, 11, 5), fill=LEAF)
    else:
        raise ValueError(f"no such thing to forage: {kind}")
    return img


def seed_bag(tile: int) -> Image.Image:
    """A bag of seeds with a sprout on it."""
    t = _size(tile)
    img, d = _new(t, t)
    d.rectangle(_box(t, 6, 2, 10, 5), fill=WOOD_LIGHT, outline=DARK)
    d.rectangle(_box(t, 3, 5, 13, 15), fill=BAG, outline=DARK)
    d.rectangle(_box(t, 7, 8, 9, 12), fill=LEAF)
    return img


def egg(tile: int) -> Image.Image:
    """An egg."""
    t = _size(tile)
    img, d = _new(t, t)
    d.ellipse(_box(t, 4, 3, 12, 14), fill=SHELL, outline=DARK)
    d.rectangle(_box(t, 6, 5, 7, 7), fill=WHITE)
    return img


def shipping_bin(tile: int) -> Image.Image:
    """The bin what is sold goes into: a wooden box with a lid, a tile a side."""
    t = _size(tile)
    img, d = _new(t, t)
    d.rectangle(_box(t, 1, 5, 15, 16), fill=WOOD, outline=DARK)
    d.rectangle(_box(t, 0, 2, 16, 6), fill=WOOD_LIGHT, outline=DARK)
    for x in (5, 10):
        d.rectangle(_box(t, x, 7, x + 1, 15), fill=DARK)
    return img


def bed(tile: int) -> Image.Image:
    """A bed seen from above, its head up: a tile wide and two long."""
    t = _size(tile)
    img, d = _new(t, t * 2)
    d.rectangle(_box(t, 1, 1, 15, 31), fill=WOOD, outline=DARK)
    d.rectangle(_box(t, 3, 3, 13, 9), fill=WHITE)
    d.rectangle(_box(t, 2, 11, 14, 30), fill=BLANKET)
    d.rectangle(_box(t, 2, 11, 14, 13), fill=WHITE)
    return img


def _hen_cell(t: int, direction: str, frame: int) -> Image.Image:
    """One frame of the hen's walk on a canvas of its own. ``left`` is drawn and ``right`` is
    its mirror; in frames 1 and 3 one leg is lifted."""
    if direction == "right":
        return ImageOps.mirror(_hen_cell(t, "left", frame))
    cell, d = _new(t, t)
    side = direction == "left"
    legs = (7, 10) if side else (6, 9)
    for n, x in enumerate(legs):
        lifted = frame == 1 + 2 * n
        d.rectangle(_box(t, x, 12, x + 1, 14 if lifted else 16), fill=ORANGE)
    if side:
        d.rectangle(_box(t, 12, 5, 15, 9), fill=WHITE, outline=DARK)  # the tail
        d.ellipse(_box(t, 4, 6, 14, 14), fill=WHITE, outline=DARK)
        d.ellipse(_box(t, 2, 3, 8, 9), fill=WHITE, outline=DARK)
        d.rectangle(_box(t, 3, 2, 6, 3), fill=RED)
        d.rectangle(_box(t, 0, 5, 2, 7), fill=ORANGE)
        d.rectangle(_box(t, 3, 5, 4, 6), fill=DARK)
        return cell
    d.ellipse(_box(t, 3, 6, 13, 14), fill=WHITE, outline=DARK)
    d.ellipse(_box(t, 5, 2, 11, 8), fill=WHITE, outline=DARK)
    d.rectangle(_box(t, 7, 1, 9, 2), fill=RED)
    if direction == "down":
        d.rectangle(_box(t, 7, 5, 9, 7), fill=ORANGE)
        d.rectangle(_box(t, 6, 4, 7, 5), fill=DARK)
        d.rectangle(_box(t, 9, 4, 10, 5), fill=DARK)
    else:  # from behind: the tail, no face
        d.rectangle(_box(t, 6, 8, 10, 11), fill=WHITE, outline=DARK)
    return cell


def hen(tile: int) -> Image.Image:
    """A hen's walk: ``HEN_FRAMES`` columns and a row for each of ``HEN_ROWS``, a tile a cell."""
    t = _size(tile)
    img, _d = _new(t * HEN_FRAMES, t * len(HEN_ROWS))
    for row, direction in enumerate(HEN_ROWS):
        for frame in range(HEN_FRAMES):
            img.paste(_hen_cell(t, direction, frame), (frame * t, row * t))
    return img


def rain(tile: int) -> Image.Image:
    """Rain to lay over the screen: ``RAIN_FRAMES`` cells in a row, each ``RAIN_TILES`` tiles a
    side and mostly clear. The streaks fall a third of their spacing from frame to frame, so
    the strip loops, and a cell repeats in both directions."""
    t = _size(tile)
    cell = t * RAIN_TILES
    img, _d = _new(cell * RAIN_FRAMES, cell)
    length, slant = t // 2, t // 4
    for frame in range(RAIN_FRAMES):
        one, d = _new(cell, cell)
        for row in range(-1, RAIN_TILES + 1):
            for col in range(-1, RAIN_TILES + 1):
                x = col * t + (row % 2) * (t // 2) + t // 4 - frame * (t // 6)
                y = row * t + frame * (t // 3)
                d.line([(x, y), (x - slant, y + length)], fill=RAIN, width=max(1, t // 16))
        img.paste(one, (frame * cell, 0))
    return img


# --------------------------------------------------------------------------- the catalog


@dataclass(frozen=True)
class StandIn:
    """One thing the kit can draw for a farm, and how a pack's own is known."""

    name: str  # the file's name and the end of the asset's id
    role: str
    thing: str  # what the note calls it
    draw: Callable[[int], Image.Image]
    tags: tuple[str, ...] = ()  # the drawn asset's tags, beside the kit's
    own_tag: str = ""  # the tag a pack's own has (none: any)
    words: tuple[str, ...] = ()  # ... and one of these words in its file name (none: any name)
    roles: tuple[str, ...] | None = ()  # the roles a pack's own may have: its own, or (None) any
    usage: str = "sprite"  # of the drawn asset: sprite, object, tiles or growth_strip
    fills: bool = True  # drawn, the role is not also reported as missing (ASSET-010)


def _crop_stand_in(name: str, fruit: Color) -> StandIn:
    return StandIn(name, "CROP", f"crop that grows ({name})", partial(crop, fruit=fruit),
                   ("crop",), "crop", usage="growth_strip")  # fmt: skip


def _tool_stand_in(name: str) -> StandIn:
    return StandIn(name, "TOOL", name.replace("_", " "), partial(tool_icon, kind=name),
                   ("tool",), "tool", TOOL_WORDS[name])  # fmt: skip


def _fish_stand_in(name: str, body: Color) -> StandIn:
    return StandIn(name, "ITEM", f"fish ({name})", partial(fish, body=body), ("fish",), "fish",
                   usage="object")  # fmt: skip


def _forage_stand_in(name: str) -> StandIn:
    thing = f"thing to forage ({name.replace('_', ' ')})"
    return StandIn(name, "ITEM", thing, partial(forage, kind=name), ("forage",), "forage",
                   usage="object")  # fmt: skip


CROP_STAND_INS = tuple(_crop_stand_in(name, fruit) for name, fruit in CROPS)
SOIL = StandIn("soil", "DECORATION", "tilled soil", soil, ("soil",), "soil", roles=None,
               usage="tiles", fills=False)  # fmt: skip
WATERED = StandIn("watered", "DECORATION", "watered soil", watered, ("watered",), "watered",
                  roles=None, usage="tiles", fills=False)  # fmt: skip
TOOL_STAND_INS = tuple(_tool_stand_in(name) for name in TOOLS)
SEED_BAG = StandIn("seed_bag", "ITEM", "bag of seeds", seed_bag, ("seed",), "seed",
                   usage="object")  # fmt: skip
HEN = StandIn("hen", "ANIMAL", "farm animal", hen, ("animal", "hen"))  # any animal of a pack
EGG = StandIn("egg", "ITEM", "egg", egg, ("product", "egg"), "product", ("egg", "eggs"),
              usage="object")  # fmt: skip
BIN = StandIn("shipping_bin", "DECORATION", "shipping bin", shipping_bin, ("bin",), "bin",
              roles=("DECORATION", "ITEM", "BUILDING"), usage="object", fills=False)  # fmt: skip
# a pack's own bed has no tag of the farm's: it is known by its name
BED = StandIn("bed", "DECORATION", "bed", bed, ("bed",), words=("bed", "beds"),
              roles=("DECORATION", "INTERIOR", "ITEM"), usage="object", fills=False)  # fmt: skip
RAIN_OVERLAY = StandIn("rain", "EFFECT", "rain", rain, ("weather",), "weather",
                       ("rain", "storm"))  # fmt: skip
# a pack with a fish, or with a thing to forage, has its own: none of the drawn ones is added
FISH_STAND_INS = tuple(_fish_stand_in(name, body) for name, body in FISH)
FORAGE_STAND_INS = tuple(_forage_stand_in(name) for name in FORAGE)
# what a farm gets when the packs lack it, in the order of the notes
STAND_INS: tuple[StandIn, ...] = (
    *CROP_STAND_INS, SOIL, WATERED, *TOOL_STAND_INS, SEED_BAG, HEN, EGG, BIN, BED, RAIN_OVERLAY,
    *FISH_STAND_INS, *FORAGE_STAND_INS,
)  # fmt: skip


def _name_words(asset: catalog_mod.Asset) -> set[str]:
    from rpggen.core import classifier

    stem = asset.path.rsplit("/", 1)[-1]
    return set(classifier.tokens(f"x/{stem}")[1])


def _own(catalog: catalog_mod.Catalog) -> list[catalog_mod.Asset]:
    """The pictures of the packs that are in use, by id: no stand-in of a last run."""
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.status not in _INACTIVE and a.pack_id != KIT_PACK and a.kind == "image"
    ]


def is_own(asset: catalog_mod.Asset, stand_in: StandIn) -> bool:
    """True when ``asset`` does what ``stand_in`` would stand in for. It has the role: a tag
    alone does not count (the farmer's strip with the hoe is tagged ``tool`` and is no icon,
    T16.09), except for soil, which has no role of its own and is known by its tag."""
    facets = catalog_mod.effective(asset)
    role = facets.get("role")
    if stand_in.roles is None:
        if role in (None, "NONE"):
            return False
    elif role not in (stand_in.roles or (stand_in.role,)):
        return False
    usages = ("tiles",) if stand_in.usage == "tiles" else ("sprite", "object")
    if facets.get("usage") not in usages:
        return False
    if stand_in.own_tag and stand_in.own_tag not in (facets.get("tags") or []):
        return False
    return not stand_in.words or bool(_name_words(asset) & set(stand_in.words))


def own_asset(catalog: catalog_mod.Catalog, stand_in: StandIn) -> catalog_mod.Asset | None:
    """The asset of the packs that does what ``stand_in`` is for, the first by id, or None."""
    return next((a for a in _own(catalog) if is_own(a, stand_in)), None)


def to_grow(catalog: catalog_mod.Catalog) -> list[catalog_mod.Asset]:
    """The crops the packs have as one picture (``ASSET-034``), by id: each gets a strip of
    drawn stages that ends in it. A colour variant made by rpggen is none."""
    found = []
    for asset in _own(catalog):
        facets = catalog_mod.effective(asset)
        if facets.get("role") != "CROP" or facets.get("usage") not in ("sprite", "object"):
            continue
        if facets.get("animations") or facets.get("headings") or "#" in asset.id:
            continue
        found.append(asset)
    return found


def growing(catalog: catalog_mod.Catalog) -> int:
    """How many crops of the packs can grow: their growth strips with the role, and the single
    pictures that get drawn stages."""
    strips = [
        a
        for a in _own(catalog)
        if catalog_mod.effective(a).get("role") == "CROP"
        and catalog_mod.effective(a).get("usage") == "growth_strip"
        and int(catalog_mod.effective(a).get("stages") or 0) >= 2
    ]
    return len(strips) + len(to_grow(catalog))


def lacking(catalog: catalog_mod.Catalog) -> list[StandIn]:
    """What the kit has to draw for a farm with this catalog. The three crops are drawn
    together, when fewer than ``MIN_CROPS`` crops of the packs can grow."""
    crops_lack = growing(catalog) < MIN_CROPS
    return [
        s for s in STAND_INS if (crops_lack if s.role == "CROP" else own_asset(catalog, s) is None)
    ]


def asset_id(stand_in: StandIn) -> str:
    return f"{KIT_PACK}.{stand_in.name}"


def grown_names(sources: list[catalog_mod.Asset]) -> dict[str, str]:
    """``{id of a single crop picture: the name of its strip}``: the last part of the id, with
    a number when two pictures share it."""
    names: dict[str, str] = {}
    taken: set[str] = set()
    for source in sources:
        base = source.id.rsplit(".", 1)[-1].lower()
        name, n = base, 1
        while name in taken:
            n += 1
            name = f"{base}_{n}"
        taken.add(name)
        names[source.id] = name
    return names


def _facets(stand_in: StandIn, image: Image.Image, t: int) -> dict[str, Any]:
    w, h = image.size
    grid = {"margin": [0, 0], "separation": [0, 0]}
    if stand_in.usage == "growth_strip":
        facets = _strip_facets(image)
    elif stand_in.usage == "tiles":
        facets = {
            "usage": "tiles",
            "grid": {"cell": [t, t], **grid},
            "collision": {"profile": "NONE"},
            "size": [w, h],
        }
    elif stand_in.name == "hen":
        animations: dict[str, Any] = {}
        for row, direction in enumerate(HEN_ROWS):
            animations[f"walk_{direction}"] = {
                "frames": [[i, row] for i in range(HEN_FRAMES)],
                "fps": 6.0,
                "loop": True,
            }
            animations[f"idle_{direction}"] = {"frames": [[0, row]], "fps": 1.0, "loop": True}
        facets = {
            "usage": "sprite",
            "grid": {"cell": [t, t], **grid},
            "frame": [t, t],
            "origin": [t // 2, t - 1],
            "animations": animations,
            "size": [w, h],
        }
    elif stand_in.name == "rain":
        cell = w // RAIN_FRAMES
        facets = {
            "usage": "sprite",
            "grid": {"cell": [cell, h], **grid},
            "frame": [cell, h],
            "origin": [cell // 2, h // 2],
            "animations": {
                "idle_down": {
                    "frames": [[i, 0] for i in range(RAIN_FRAMES)],
                    "fps": 9.0,
                    "loop": True,
                }
            },
            "size": [w, h],
        }
    else:
        # a single picture. One with a role the top-down recipes scatter over a map or take
        # for a chest (ITEM, DECORATION) is an ``object``: only the farm's recipes place it.
        facets = {"usage": stand_in.usage, "frame": [w, h], "origin": [w // 2, h - 1],
                  "size": [w, h]}  # fmt: skip
    facets["role"] = stand_in.role
    facets["tags"] = sorted({KIT_TAG, *stand_in.tags})
    return facets


def _strip_facets(image: Image.Image) -> dict[str, Any]:
    """A growth strip of ``CROP_STAGES`` cells, as detection writes one (T17.01)."""
    w, h = image.size
    cell = w // CROP_STAGES
    return {
        "usage": "growth_strip",
        "grid": {"cell": [cell, h], "margin": [0, 0], "separation": [0, 0]},
        "frame": [cell, h],
        "origin": [cell // 2, h - 1],
        "stages": CROP_STAGES,
        "size": [w, h],
    }


def _append(
    catalog: catalog_mod.Catalog, staging_root: Path, ident: str, rel: str, image: Image.Image,
    facets: dict[str, Any],
) -> None:  # fmt: skip
    target = Path(staging_root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    catalog.assets.append(
        catalog_mod.Asset(
            id=ident,
            pack_id=KIT_PACK,
            path=rel,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            kind="image",
            status="CONFIRMED",
            detected=facets,
            detected_by="placeholder",
            confidence=1.0,
        )
    )


def _ripe_picture(source: catalog_mod.Asset, staging_root: Path) -> Image.Image | None:
    """The picture of a single crop from the staging copy (its first frame), or None when the
    file is not there: its strip is then not made."""
    path = Path(staging_root) / source.path
    if not path.is_file():
        return None
    frame = catalog_mod.effective(source).get("frame")
    with Image.open(path) as opened:
        picture = opened.convert("RGBA")
    if isinstance(frame, list) and len(frame) == 2:
        picture = picture.crop((0, 0, min(picture.width, frame[0]), min(picture.height, frame[1])))
    return picture


def add(catalog: catalog_mod.Catalog, tile: int, staging_root: Path) -> tuple[list[str], IssueList]:
    """Draw what a farm needs and the packs lack into the staging copy, add it to the catalog
    and return the names with one ``ASSET-031`` note each; then the strip of every crop that is
    one picture (no note: ``ASSET-034`` has said it). The kit of the last run (a regeneration
    finds it in the catalog, without its files) is replaced."""
    issues = IssueList()
    catalog.assets[:] = [a for a in catalog.assets if a.pack_id != KIT_PACK]
    t = _size(tile)
    added: list[str] = []
    for stand_in in lacking(catalog):
        image = stand_in.draw(t)
        rel = f"{KIT_DIR}/{stand_in.name}.png"
        _append(catalog, staging_root, asset_id(stand_in), rel, image, _facets(stand_in, image, t))
        issues.add("ASSET-031", role=stand_in.role, thing=stand_in.thing, file=rel)
        added.append(stand_in.name)
    sources = to_grow(catalog)
    for source in sources:
        ripe = _ripe_picture(source, staging_root)
        if ripe is None:
            continue
        name = grown_names(sources)[source.id]
        image = grown(ripe, t)
        facets = _strip_facets(image)
        facets["role"] = "CROP"
        facets["tags"] = sorted({KIT_TAG, "crop", GROWN_TAG + source.id})
        rel = f"{KIT_DIR}/{GROWN_DIR}/{name}.png"
        _append(catalog, staging_root, f"{KIT_PACK}.{GROWN_DIR}.{name}", rel, image, facets)
        added.append(f"{GROWN_DIR}/{name}")
    if added:
        if not any(p.pack_id == KIT_PACK for p in catalog.packs):
            catalog.packs.append(
                catalog_mod.CatalogPack(KIT_PACK, "0" * 64, KIT_DIR, [], [], None, [])
            )
        if {"soil", "watered"} & set(added):
            previous = catalog_mod.Catalog.from_json(catalog.to_json())
            catalog_mod.assign_tilesets(catalog, previous)
        catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    return added, issues

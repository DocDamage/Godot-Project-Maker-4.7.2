"""People and farm animals told from a tile's picture (T17.33).

Kenney's *Tiny Farm* draws its farmer, its hen, its cow and its sheep as numbered tiles among
crops and crates (``Tiles/tile_0108.png``): no name says which is which. This module tells them
by what they look like, one picture at a time:

* **A person seen from the front** stands on the bottom of the picture, is as tall as most of
  it, is the same on its left and its right (a mirror of itself), and has a face: a patch of
  skin in its upper half with two dark eyes side by side in it.
* **A farm animal seen from the side** stands on the bottom too, is not a mirror of itself, and
  is told by its colours: a **hen** is white or cream with a red comb on top and is small; a
  **cow** is white with large black patches; a **sheep** is a white fleece with a dark face
  and legs; a **pig** is pink all over; a **duck** is white or yellow with an orange bill and
  no comb.

Anything that is none of these says None. Only what the picture leaves no doubt about is named:
the rest is left to a person or, later, to a vision model (T17.34). Float arithmetic on the
pixels only: the same picture gives the same answer everywhere.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ALPHA = 128
PERSON = "person"


def _hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = rgb.astype(np.float32) / 255.0
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    safe = np.maximum(d, 1e-6)
    hue = np.where(
        mx == r, (g - b) / safe % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)
    )
    return (hue * 60.0) % 360.0, sat, mx


def _box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def mirror_share(rgba: np.ndarray, mask: np.ndarray, box: tuple[int, int, int, int]) -> float:
    """How much a figure is its own mirror image about the middle of its box (0..1)."""
    x0, y0, x1, y1 = box
    part = mask[y0 : y1 + 1, x0 : x1 + 1]
    flipped = part[:, ::-1]
    union = int((part | flipped).sum())
    shape = int((part & flipped).sum()) / union if union else 0.0
    rgb = rgba[y0 : y1 + 1, x0 : x1 + 1, :3].astype(np.float32)
    both = part & flipped
    if not both.any():
        return 0.0
    colour = float((np.abs(rgb - rgb[:, ::-1]).max(axis=-1)[both] <= 40).mean())
    return min(shape, colour)


def _skin(rgba: np.ndarray) -> np.ndarray:
    hue, sat, val = _hsv(rgba[..., :3])
    return (hue >= 8) & (hue <= 42) & (sat >= 0.18) & (sat <= 0.65) & (val >= 0.55)


def is_person(rgba: np.ndarray) -> bool:
    """A person seen from the front (see the module's text)."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return False
    h, w = rgba.shape[:2]
    mask = rgba[:, :, 3] >= ALPHA
    box = _box(mask)
    if box is None:
        return False
    x0, y0, x1, y1 = box
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if y1 < h - 2 or bh < 0.7 * h or bh < 0.9 * bw:
        return False
    if mirror_share(rgba, mask, box) < 0.8:
        return False
    return _has_eyes(rgba, mask, box)


def _has_eyes(rgba: np.ndarray, mask: np.ndarray, box: tuple[int, int, int, int]) -> bool:
    """Two dark eyes on one row of the upper two thirds of the figure, either side of its middle
    and mirrors of each other, each with skin left and right of it and above and below it (a
    face; the strings tying a sack sit at its top edge, with no skin above them)."""
    x0, y0, x1, y1 = box
    bh = y1 - y0 + 1
    skin = _skin(rgba) & mask
    _hue, _sat, val = _hsv(rgba[..., :3])
    dark = mask & (val < 0.35)
    axis = (x0 + x1) / 2.0
    h, w = mask.shape

    def eye(y: int, x: int) -> bool:
        if not dark[y, x] or x <= 0 or x >= w - 1 or y <= 0:
            return False
        if not (skin[y, x - 1] and skin[y, x + 1] and skin[y - 1, x]):
            return False
        return any(skin[yy, x] for yy in range(y + 1, min(h, y + 3)))

    for y in range(y0 + 1, y0 + max(2, bh * 2 // 3)):
        xs = [x for x in range(x0, x1 + 1) if eye(y, x)]
        for xa in xs:
            for xb in xs:
                if xa < axis < xb and abs((xa + xb) / 2.0 - axis) <= 1.0:
                    return True
    return False


ANIMALS = ("chicken", "cow", "sheep", "pig", "duck")


def animal_of(rgba: np.ndarray, above: bool = True) -> str | None:
    """The farm animal a picture shows from the side, or None (see the module's text)."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return None
    h, w = rgba.shape[:2]
    mask = rgba[:, :, 3] >= ALPHA
    box = _box(mask)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if y1 < h - 3 or bh < 0.35 * h or mask.mean() < 0.15:
        return None
    if mirror_share(rgba, mask, box) >= 0.8:
        # a mirror of itself: seen from above or the front (SakPix's *13. Farm animals*), or
        # a thing (a sack, a pot); only colours that leave no doubt say what it is
        return _from_above(rgba, mask) if above else None
    hue, sat, val = _hsv(rgba[..., :3])
    body = mask & (val >= 0.35)  # without the outline
    if body.sum() < 8:
        return None
    n = float(body.sum())
    white = body & (sat <= 0.12) & (val >= 0.98)  # a coat or feathers of plain white
    red = body & ((hue <= 12) | (hue >= 345)) & (sat >= 0.5) & (val >= 0.45)
    pink = body & ((hue >= 330) | (hue <= 15)) & (sat >= 0.2) & (sat < 0.55) & (val >= 0.7)
    orange = body & (hue > 15) & (hue <= 45) & (sat >= 0.55) & (val >= 0.6)
    yellow = body & (hue > 45) & (hue <= 65) & (sat >= 0.5) & (val >= 0.7)
    warm = body & (sat >= 0.25) & ((hue <= 60) | (hue >= 330)) & (val >= 0.6)
    w_share = float(white.sum()) / n
    top = slice(y0, y0 + max(1, bh * 2 // 5))
    comb = bool(red[top].sum() >= 2)
    if float(pink.sum()) / n >= 0.5:
        return "pig"
    if w_share < 0.15 and float(yellow.sum()) / n < 0.3:
        return None  # no white coat, no feathers: grey stones, a butterfly, a crate
    if comb and bh <= 0.9 * h:
        return "chicken"
    if not comb and orange.sum() >= 2 and bh <= 0.7 * h and bw <= 1.2 * bh:
        return "duck"
    if bw >= 1.1 * bh and w_share >= 0.15:
        # a coat of white: with a muzzle, horns or patches of warm colours a cow, else a sheep's
        # fleece with its grey face and legs
        return "cow" if int(warm.sum()) >= 5 else "sheep"
    return None


def _from_above(rgba: np.ndarray, mask: np.ndarray) -> str | None:
    """A farm animal seen from above, by its colours alone: a pig is pink; a bird has an orange
    bill and feet (a hen also a red comb and wattle, a chick a yellow down); a sheep is a white
    or cream fleece with no bill. Cows, goats, horses and the rest look too much alike from
    above to be told by colours: None (T17.34's vision step)."""
    hue, sat, val = _hsv(rgba[..., :3])
    body = mask & (val >= 0.35)
    n = float(body.sum())
    if n < 40:
        return None
    pink = body & ((hue >= 330) | (hue <= 15)) & (sat >= 0.2) & (sat < 0.6) & (val >= 0.7)
    red = body & ((hue <= 12) | (hue >= 345)) & (sat >= 0.6) & (val >= 0.45)
    orange = body & (hue > 18) & (hue <= 42) & (sat >= 0.7) & (val >= 0.75)
    yellow = body & (hue > 42) & (hue <= 62) & (sat >= 0.5) & (val >= 0.75)
    fleece = body & (sat <= 0.25) & (val >= 0.72)
    if float(pink.sum()) / n >= 0.35:
        return "pig"
    if float(yellow.sum()) / n >= 0.4:
        return "chicken"  # a chick
    brown = body & (hue > 12) & (hue <= 40) & (sat >= 0.35) & (val < 0.72)
    if float(orange.sum()) / n >= 0.01:
        if float(red.sum()) / n >= 0.01:
            return "chicken"
        if float(brown.sum()) / n < 0.3:
            return "duck"  # a brown coat with a light on it is a horse's, no duck's
        return None
    if float(fleece.sum()) / n >= 0.45:
        return "sheep"
    return None


def is_tree(rgba: np.ndarray, least: int = 40) -> bool:
    """A tree seen from the front or from above at an angle (T17.33: the trees CuteSCKR's sheets
    draw among their things): a wide crown of leaves (green, or a season's red, orange or
    yellow) over a narrow trunk of wood, the crown at least as wide as two thirds of the thing,
    the trunk at most two fifths of it, in the band between the crown and the ground."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return False
    mask = rgba[:, :, 3] >= ALPHA
    box = _box(mask)
    if box is None:
        return False
    x0, y0, x1, y1 = box
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if bh < least or bw < least * 3 // 5 or bh < 0.8 * bw:
        return False
    hue, sat, val = _hsv(rgba[..., :3])
    crown = slice(y0, y0 + int(bh * 0.75))
    leafy = (
        mask
        & (sat >= 0.25)
        & (val >= 0.25)
        & (((hue >= 60) & (hue < 170)) | (hue < 60) | (hue >= 330))
    )
    green = mask & (hue >= 60) & (hue < 170) & (sat >= 0.2)
    crown_mask = mask[crown]
    if not crown_mask.any():
        return False
    cols = np.nonzero(crown_mask.any(axis=0))[0]
    if cols.size == 0 or (cols.max() - cols.min() + 1) < 0.66 * bw:
        return False
    if float(green[crown].sum()) < 0.35 * float(crown_mask.sum()) and float(
        leafy[crown].sum()
    ) < 0.6 * float(crown_mask.sum()):
        return False
    # the trunk: below the crown, a row whose colour (the outline left out) is narrow, of wood
    body = mask & (val >= 0.3)
    narrow = []
    for y in range(y0 + int(bh * 0.7), y1 + 1):
        width = int(body[y].sum())
        if 0 < width <= 0.4 * bw:
            narrow.append(y)
    if not narrow:
        return False
    if float(green[crown].sum()) < 0.45 * float(crown_mask.sum()):
        return False  # a crown of leaves is green (a hay bale, a sack, a hive are not)
    # the trunk's row: the narrow row most of wood (a shadow's edge under it is grey)
    best = 0.0
    middle = (x0 + x1) / 2.0
    for y in narrow:
        row = body[y]
        xs = np.nonzero(row)[0]
        # one run of colour in the middle of the thing: a trunk, not the feet of a crate
        if (
            xs.size == 0
            or xs.max() - xs.min() + 1 != xs.size
            or abs(xs.mean() - middle) > 0.15 * bw
        ):
            continue
        wood = row & (hue[y] >= 10) & (hue[y] < 50) & (sat[y] >= 0.2)
        best = max(best, float(wood.sum()) / max(1.0, float(row.sum())))
    return best >= 0.5


HOUSE_LEAST = 64  # px each way: a kennel, a well, a sign are smaller


def is_house(rgba: np.ndarray, least: int = HOUSE_LEAST) -> bool:
    """A house or a barn seen from the front (T17.33: the houses CuteSCKR's sheets draw among
    their things): a roof narrowing to its ridge over solid walls, the walls as wide as the
    house in the lower part and painted all over, with a darker opening (a door, windows) in
    them; not a tree (its crown is no wall)."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return False
    mask = rgba[:, :, 3] >= ALPHA
    box = _box(mask)
    if box is None:
        return False
    x0, y0, x1, y1 = box
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if bh < least or bw < least or bw < 0.6 * bh or bw > 2.5 * bh:
        return False
    extent = np.zeros(bh)
    fill = np.zeros(bh)
    for i, y in enumerate(range(y0, y1 + 1)):
        xs = np.nonzero(mask[y, x0 : x1 + 1])[0]
        if xs.size:
            extent[i] = xs.max() - xs.min() + 1
            fill[i] = xs.size / extent[i]
    lower = slice(int(bh * 0.6), int(bh * 0.95))
    # the walls: wide and solid
    if float(np.median(extent[lower])) < 0.8 * bw or float(np.median(fill[lower])) < 0.95:
        return False
    # the roof: its first rows narrower than the walls (a ridge, a gable, a peak)
    top = extent[: max(2, int(bh * 0.05))]
    foot = slice(int(bh * 0.9), bh)
    if float(np.median(fill[foot])) < 0.9 or float(np.median(extent[foot])) < 0.75 * bw:
        return False  # its walls stand on the ground: not the wheels of a cart or a tractor
    if (
        float(top.mean()) > 0.4 * bw
        or float(extent[int(bh * 0.1)]) > 0.6 * bw  # a roof widens slowly to its eaves
        or float(extent[int(bh * 0.3)]) < float(top.mean()) + 0.2 * bw
    ):
        return False  # a crate of produce, a pen: as wide at the top as below
    # the roof is painted all over, not the tips of the produce in a crate
    eaves = next((i for i in range(bh) if extent[i] >= 0.9 * bw), bh)
    roof = fill[max(1, int(bh * 0.05)) : eaves]
    if roof.size == 0 or float(np.median(roof)) < 0.85:
        return False
    hue, sat, val = _hsv(rgba[..., :3])
    leaf = (hue >= 70) & (hue < 170) & (sat >= 0.3)
    over = mask[y0 : y0 + max(1, eaves), x0 : x1 + 1]
    if float(leaf[y0 : y0 + max(1, eaves), x0 : x1 + 1][over].mean()) > 0.6:
        return False  # a melon in its crate, a tree's crown: green and round, no roof
    walls = mask[y0 + int(bh * 0.5) : y1 + 1, x0 : x1 + 1]
    if (
        float(
            ((hue >= 70) & (hue < 170) & (sat >= 0.3))[y0 + int(bh * 0.5) : y1 + 1, x0 : x1 + 1][
                walls
            ].mean()
        )
        > 0.5
    ):
        return False  # green all over: a hedge, a tree's crown
    # an opening: a dark patch in the walls (a door, a window)
    dark = walls & (val[y0 + int(bh * 0.5) : y1 + 1, x0 : x1 + 1] < 0.3)
    return float(dark.sum()) >= 0.01 * float(walls.sum())


def thing_kind(rgba: np.ndarray, least: int = 40) -> str | None:
    """What a small thing of nature is by its colours and shape (T17.33): ``tree``, ``bush``
    (a round mass of leaves), ``rock`` (grey and compact), ``flowers`` (spots of a bright colour
    among green), ``grass`` (a low tuft of green), ``stump`` (wood, wider than tall and low);
    None for anything else."""
    if is_tree(rgba, least):
        return "tree"
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return None
    mask = rgba[:, :, 3] >= ALPHA
    box = _box(mask)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    n = float(mask.sum())
    if n < 12:
        return None
    hue, sat, val = _hsv(rgba[..., :3])
    body = mask & (val >= 0.3)
    nb = float(body.sum()) or 1.0
    green = float((body & (hue >= 60) & (hue < 170) & (sat >= 0.25)).sum()) / nb
    grey = float((body & (sat < 0.18)).sum()) / nb
    wood = float((body & (hue >= 15) & (hue < 45) & (sat >= 0.3) & (val < 0.75)).sum()) / nb
    bright = float((body & (sat >= 0.45) & (val >= 0.6) & ~((hue >= 60) & (hue < 170))).sum()) / nb
    fill = n / float(bh * bw)
    if grey >= 0.6 and fill >= 0.5 and 0.5 <= bw / bh <= 2.5:
        return "rock"
    if green >= 0.25 and bright >= 0.1 and bright <= 0.6:
        return "flowers"
    if green >= 0.6 and bh <= 0.75 * bw and fill < 0.55:
        return "grass"
    if green >= 0.6 and fill >= 0.55 and 0.6 <= bw / bh <= 1.8:
        return "bush"
    if wood >= 0.5 and bw >= 1.1 * bh and fill >= 0.4:
        return "stump"
    return None


FIGURE_CONFIDENCE = 0.8
FIGURE_TAG = "figure:"
_NUMBERED = re.compile(r"^(?:[a-z]+[_\- ]?)?\d+$")
# a numbered picture's word that names nothing (``tile_0108``, ``sprite12``)
GENERIC_STEMS = frozenset({"", "tile", "tiles", "sprite", "sprites", "image", "img", "frame"})


def numbered(stem: str) -> bool:
    """A name that says nothing but a number (``tile_0108``, ``42``)."""
    s = stem.casefold()
    if not _NUMBERED.match(s):
        return False
    return re.sub(r"[_\- ]?\d+$", "", s) in GENERIC_STEMS


def read_numbered(assets: list[Any], pack_root: Path, root: str) -> int:
    """The people and animals among a farming pack's numbered pictures (T17.33: *Tiny Farm*'s
    ``tile_0108`` farmer, ``tile_0122`` hen): told from their pictures. The first person is the
    player and the others villagers; each animal is an ``ANIMAL`` of its species. Each stands in
    one frame, its feet at the bottom middle. A copy of a sheet's cell set aside comes back:
    the sheet's cell is no character, the single picture is."""
    found = 0
    people = 0
    for asset in sorted(assets, key=lambda a: a.id):
        if "#" in asset.id or asset.kind != "image" or asset.detected_by in ("profile", "learned"):
            continue
        facets = asset.detected
        size = facets.get("size") or [0, 0]
        w, h = int(size[0]), int(size[1])
        if not (8 <= w <= 64 and 8 <= h <= 64) or not asset.path.startswith(root + "/"):
            continue
        stem = posixpath.splitext(posixpath.basename(asset.path))[0]
        if not numbered(stem):
            continue
        if facets.get("role") in ("PLAYER", "NPC", "ANIMAL") and asset.confidence >= 0.75:
            continue
        try:
            with Image.open(pack_root / asset.path[len(root) + 1 :]) as im:
                rgba = np.asarray(im.convert("RGBA"))
        except (OSError, ValueError):
            continue
        species = None
        role = None
        if is_person(rgba):
            role = "PLAYER" if people == 0 else "NPC"
            people += 1
        else:
            species = animal_of(rgba, above=False)
            role = "ANIMAL" if species else None
        if role is None:
            kind = "tree" if is_tree(rgba, least=12) else None
            if kind is not None:
                # a thing of nature among the numbered tiles (T17.33: *Tiny Farm*'s pines,
                # bushes, rocks and flowers): the farm's scenery
                tags = {
                    t
                    for t in facets.get("tags") or []
                    if not t.startswith(("unused_because:", "same_as:"))
                }
                facets.update({"usage": "sprite", "role": "DECORATION",
                               "frame": [w, h], "origin": [w // 2, h - 1],
                               "tags": sorted(tags | {kind, FIGURE_TAG + kind})})  # fmt: skip
                for key in ("animations", "grid", "tile_overrides", "roles_alt"):
                    facets.pop(key, None)
                asset.confidence = max(float(asset.confidence or 0.0), FIGURE_CONFIDENCE)
                found += 1
            continue
        tags = {
            t for t in facets.get("tags") or [] if not t.startswith(("unused_because:", "same_as:"))
        }
        tags.add(FIGURE_TAG + (species or PERSON))
        if species:
            tags |= {"animal", species}
        one = {"fps": 1.0, "loop": True, "frames": [[0, 0]]}
        facets.update({
            "usage": "sprite",
            "role": role,
            "frame": [w, h],
            "origin": [w // 2, h - 1],
            "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
            "animations": {"idle_down": dict(one), "walk_down": dict(one)},
            "tags": sorted(tags),
        })  # fmt: skip
        facets.pop("roles_alt", None)
        facets.pop("tile_overrides", None)
        asset.confidence = max(float(asset.confidence or 0.0), FIGURE_CONFIDENCE)
        found += 1
    return found


def _islands_in(part: np.ndarray, around: np.ndarray) -> list[tuple[int, float]]:
    """The connected pieces of ``part``, each with its size and the share of the pixels just
    outside it that are ``around`` (a patch inside a white coat is ringed by white)."""
    hh, ww = part.shape
    seen = np.zeros_like(part)
    out: list[tuple[int, float]] = []
    for sy, sx in zip(*np.nonzero(part), strict=True):
        if seen[sy, sx]:
            continue
        stack = [(int(sy), int(sx))]
        seen[sy, sx] = True
        size = 0
        ring: set[tuple[int, int]] = set()
        while stack:
            y, x = stack.pop()
            size += 1
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if not (0 <= ny < hh and 0 <= nx < ww):
                    continue
                if part[ny, nx]:
                    if not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
                else:
                    ring.add((ny, nx))
        share = sum(1 for y, x in ring if around[y, x]) / len(ring) if ring else 0.0
        out.append((size, share))
    return out

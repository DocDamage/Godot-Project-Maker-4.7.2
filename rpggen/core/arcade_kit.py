"""Drawn stand-ins for the arcade kinds (T16.03).

A shoot 'em up needs a ship, a bullet and an explosion; a racing game a car in sixteen headings
and a road. A pack made for another kind of game has none of them, and a pack made for this
kind may miss one. Rather than refusing to make a game, rpggen draws what is missing, plainly,
in the pack's tile size, and says so with a note (``ASSET-031``): every kind plays from a pack
that has nothing made for it. A pack's own asset always wins.

The pictures are drawn from integer arithmetic (the car's turned views from sines rounded well
away from a half), so they are the same on every machine.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from rpggen.core import catalog as catalog_mod
from rpggen.errors import IssueList

KIT_PACK = "rpggen_arcade_kit"
KIT_DIR = "generated/arcade_kit"
KIT_TAG = "arcade_kit"
ARCADE_KINDS = ("shmup", "run_and_gun", "racing")
CAR_HEADINGS = 16
EXPLOSION_FRAMES = 6
# the road sheet's tiles, left to right: what each cell is for
ROAD_TILES = (
    "straight_v", "straight_h", "curve_ne", "curve_nw", "curve_se", "curve_sw", "start",
    "grass", "barrier",
)  # fmt: skip
WEAPONS = ("spread", "laser", "flame", "machinegun", "missile")
_INACTIVE = {"UNUSED", "MISSING"}

Color = tuple[int, int, int, int]
CLEAR: Color = (0, 0, 0, 0)
BLACK: Color = (20, 20, 28, 255)
WHITE: Color = (240, 240, 240, 255)
STEEL: Color = (150, 160, 175, 255)
HULL: Color = (90, 170, 230, 255)
SHOT: Color = (255, 240, 120, 255)
BEAM: Color = (120, 240, 255, 255)
FIRE: Color = (255, 150, 40, 255)
RED: Color = (220, 60, 60, 255)
ASPHALT: Color = (70, 70, 78, 255)
GRASS: Color = (76, 150, 70, 255)


def _new(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (max(1, width), max(1, height)), CLEAR)
    return img, ImageDraw.Draw(img)


def _size(tile: int) -> int:
    return max(8, int(tile))


# --------------------------------------------------------------------------- the pictures


def bullet(tile: int) -> Image.Image:
    """A round shot, half a tile across."""
    s = max(4, _size(tile) // 2)
    img, d = _new(s, s)
    d.ellipse([1, 1, s - 2, s - 2], fill=SHOT, outline=BLACK)
    return img


def laser(tile: int) -> Image.Image:
    """A beam: a quarter of a tile wide, one tile long."""
    t = _size(tile)
    w = max(2, t // 4)
    img, d = _new(w, t)
    d.rectangle([0, 0, w - 1, t - 1], fill=BEAM)
    d.line([(w // 2, 0), (w // 2, t - 1)], fill=WHITE)
    return img


def missile(tile: int) -> Image.Image:
    """A missile pointing up: half a tile wide, one tile long, with a flame."""
    t = _size(tile)
    w = max(4, t // 2)
    img, d = _new(w, t)
    d.polygon([(w // 2, 0), (w - 1, t // 3), (0, t // 3)], fill=RED)
    d.rectangle([w // 4, t // 3, w - 1 - w // 4, t - 1 - t // 4], fill=STEEL, outline=BLACK)
    d.rectangle([w // 3, t - t // 4, w - 1 - w // 3, t - 1], fill=FIRE)
    return img


def explosion(tile: int) -> Image.Image:
    """Six frames in a row: a ball that grows, then a ring that thins."""
    t = _size(tile)
    img, d = _new(t * EXPLOSION_FRAMES, t)
    for i in range(EXPLOSION_FRAMES):
        cx, cy = i * t + t // 2, t // 2
        r = 2 + i * (t // 2 - 3) // (EXPLOSION_FRAMES - 1)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 220 - i * 26, 60, 255))
        hole = r * i // EXPLOSION_FRAMES
        if hole > 0:
            d.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=CLEAR)
    return img


def capsule(tile: int) -> Image.Image:
    """A power-up: a capsule with a letter-like mark."""
    t = _size(tile)
    img, d = _new(t, t)
    m = t // 6
    box = [m, t // 4, t - 1 - m, t - 1 - t // 4]
    d.rounded_rectangle(box, radius=t // 4, fill=RED, outline=BLACK)
    d.rectangle([t // 2 - 1, t // 3, t // 2, t - 1 - t // 3], fill=WHITE)
    return img


def ship(tile: int) -> Image.Image:
    """The player's ship, seen from above, its nose up: a tile and a half across."""
    s = _size(tile) * 3 // 2
    img, d = _new(s, s)
    mid = s // 2
    d.polygon([(mid, 1), (s - 3, s - 4), (mid, s - s // 4), (2, s - 4)], fill=HULL, outline=BLACK)
    d.rectangle([mid - 1, s // 3, mid, s // 3 + max(2, s // 8)], fill=WHITE)
    return img


def _turned(
    points: list[tuple[float, float]], k: int, cx: float, cy: float
) -> list[tuple[int, int]]:
    """``points`` turned clockwise by ``k`` sixteenths of a full turn about ``cx, cy``. The
    quarter turns are exact; elsewhere the rounding is of values that are never near a half."""
    quarter, rest = divmod(k, CAR_HEADINGS // 4)
    if rest == 0:
        cos, sin = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[quarter % 4]
    else:
        angle = k * 2 * math.pi / CAR_HEADINGS
        cos, sin = math.cos(angle), math.sin(angle)
    return [
        (math.floor(cx + x * cos - y * sin + 0.5), math.floor(cy + x * sin + y * cos + 0.5))
        for x, y in points
    ]


def car(tile: int) -> Image.Image:
    """A car seen from above in sixteen headings in a row: the first points up, each next one
    is turned clockwise by a sixteenth. A cell is a tile and a half."""
    cell = _size(tile) * 3 // 2
    img, d = _new(cell * CAR_HEADINGS, cell)
    half = cell / 2 - 0.25
    w, length = cell * 0.23, cell * 0.41
    hull = [(-w, -length * 0.6), (0.0, -length), (w, -length * 0.6), (w, length), (-w, length)]
    roof = [(-w * 0.6, -length * 0.15), (w * 0.6, -length * 0.15), (w * 0.6, length * 0.55),
            (-w * 0.6, length * 0.55)]  # fmt: skip
    for k in range(CAR_HEADINGS):
        cx = k * cell + half
        d.polygon(_turned(hull, k, cx, half), fill=RED, outline=BLACK)
        d.polygon(_turned(roof, k, cx, half), fill=WHITE)
    return img


def _shade(colour: Color, by: float) -> Color:
    """``colour`` lighter (``by`` above 1) or darker (below 1), whole numbers."""
    r, g, b, a = colour
    return (min(255, round(r * by)), min(255, round(g * by)), min(255, round(b * by)), a)


def _iso_point(gx: float, gy: float, half_w: float, half_h: float) -> tuple[float, float]:
    """A place of the ground (cells) on the screen of a view of diamonds ``2 half_w`` by
    ``2 half_h`` px: what RpgIso does with the grid."""
    return (gx - gy) * half_w, (gx + gy) * half_h


def iso_car(footprint: tuple[int, int], colour: Color = RED) -> Image.Image:
    """A car seen at the angle of an isometric view (T18.19), in sixteen headings in a row: the
    first points up on the screen, each next one is turned clockwise on the screen by a sixteenth
    (the order RpgHeadingSprite reads, ``up_cw``). For each heading the screen's direction is
    taken back to the ground, where the car is a box (a body, a cabin on it, four wheels) 0.8 of
    a cell long and 0.42 wide, which is then seen from the view's angle: the faces that look at
    the viewer are drawn, the sides darker than the top. A cell of the sheet is a diamond and a
    half wide."""
    fw, fh = max(8, int(footprint[0])), max(4, int(footprint[1]))
    cell_w, cell_h = fw * 3 // 2, fh * 2 + fh // 2
    img, d = _new(cell_w * CAR_HEADINGS, cell_h)
    body_h, cabin_h = fh * 0.45, fh * 0.35
    length, width = 0.8, 0.21
    for k in range(CAR_HEADINGS):
        angle = k * 2 * math.pi / CAR_HEADINGS
        sx, sy = math.sin(angle), -math.cos(angle)  # the screen's direction
        gx, gy = sy + sx / 2.0, sy - sx / 2.0  # ... taken back to the ground
        norm = math.hypot(gx, gy) or 1.0
        centre = (k * cell_w + cell_w / 2.0, cell_h * 0.62)
        view = _IsoCar(d, centre, (gx / norm, gy / norm), fw, fh)
        for along in (-length * 0.3, length * 0.3):
            for across in (-width * 1.05, width * 1.05):
                wx, wy = view.ground(along, across, 1)
                d.ellipse([wx - 2, wy - 2, wx + 2, wy + 1], fill=BLACK)
        view.box((length, width, -length / 2), (1.0, body_h), colour)
        roof = (length * 0.42, width * 0.8, -length * 0.25)
        view.box(roof, (body_h, body_h + cabin_h), _shade(WHITE, 0.92))
    return img


class _IsoCar:
    """One heading of ``iso_car``: the ground of the car (along it and across it) on the screen."""

    def __init__(
        self,
        d: ImageDraw.ImageDraw,
        centre: tuple[float, float],
        along: tuple[float, float],
        fw: int,
        fh: int,
    ) -> None:
        self.d = d
        self.cx, self.cy = centre
        self.ax, self.ay = along
        self.px, self.py = -along[1], along[0]
        self.half_w, self.half_h = fw / 2.0, fh / 2.0

    def ground(self, along: float, across: float, up: float = 0.0) -> tuple[int, int]:
        gx = self.ax * along + self.px * across
        gy = self.ay * along + self.py * across
        x, y = _iso_point(gx, gy, self.half_w, self.half_h)
        return round(self.cx + x), round(self.cy + y - up)

    def box(
        self, size: tuple[float, float, float], heights: tuple[float, float], top: Color
    ) -> None:
        """A box ``size`` (length, half its width, where its back is along the car) from height
        ``low`` to ``high`` px: the sides that face the viewer (down on the screen), then the
        top."""
        length, width, back = size
        low, high = heights
        corners = [(back + length, -width), (back + length, width), (back, width), (back, -width)]
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            nx = (b[1] - a[1]) * self.ax + (a[0] - b[0]) * self.px
            ny = (b[1] - a[1]) * self.ay + (a[0] - b[0]) * self.py
            if nx + ny > 0:
                side = [self.ground(*a, low), self.ground(*b, low)]
                side += [self.ground(*b, high), self.ground(*a, high)]
                shade = 0.62 if abs(nx) > abs(ny) else 0.78
                self.d.polygon(side, fill=_shade(top, shade), outline=BLACK)
        self.d.polygon([self.ground(x, y, high) for x, y in corners], fill=top, outline=BLACK)


def _road_cell(name: str, t: int) -> Image.Image:
    """One tile of the road sheet, drawn on a canvas of its own."""
    cell, d = _new(t, t)
    d.rectangle([0, 0, t - 1, t - 1], fill=GRASS)
    edge = max(1, t // 8)
    if name == "grass":
        return cell
    if name.startswith("curve_"):
        # the quarter of a road around the corner where the two sides it joins meet
        cx = t - 1 if "e" in name[6:] else 0
        cy = 0 if "n" in name[6:] else t - 1
        d.ellipse([cx - t + edge, cy - t + edge, cx + t - edge, cy + t - edge], fill=ASPHALT)
        return cell
    if name == "straight_h":
        d.rectangle([0, edge, t - 1, t - 1 - edge], fill=ASPHALT)
        d.line([(t // 4, t // 2), (t - 1 - t // 4, t // 2)], fill=WHITE)
        return cell
    d.rectangle([edge, 0, t - 1 - edge, t - 1], fill=ASPHALT)
    if name == "straight_v":
        d.line([(t // 2, t // 4), (t // 2, t - 1 - t // 4)], fill=WHITE)
    elif name == "start":
        step = max(2, t // 8)
        for n, x in enumerate(range(edge, t - edge, step)):
            y = t // 2 - step if n % 2 == 0 else t // 2
            d.rectangle([x, y, min(t - 1 - edge, x + step - 1), y + step - 1], fill=WHITE)
    elif name == "barrier":
        d.rectangle([edge, t // 2 - edge, t - 1 - edge, t // 2 + edge - 1], fill=RED)
    return cell


def road(tile: int) -> Image.Image:
    """The road sheet, one row of ``ROAD_TILES``: two straights, four curves (named by the two
    sides they join), a start line, grass, and a barrier across the road."""
    t = _size(tile)
    img, _d = _new(t * len(ROAD_TILES), t)
    for index, name in enumerate(ROAD_TILES):
        img.paste(_road_cell(name, t), (index * t, 0))
    return img


def hook(tile: int) -> Image.Image:
    """A grapple hook pointing up."""
    t = _size(tile)
    img, d = _new(t, t)
    mid = t // 2
    d.rectangle([mid - 1, t // 3, mid, t - 1], fill=STEEL)
    box = [t // 6, 0, t - 1 - t // 6, t * 2 // 3]
    d.arc(box, start=180, end=360, fill=STEEL, width=max(2, t // 8))
    return img


def chain(tile: int) -> Image.Image:
    """One link of the grapple's chain, to be repeated: half a tile."""
    s = max(4, _size(tile) // 2)
    img, d = _new(s, s)
    d.ellipse([s // 4, 0, s - 1 - s // 4, s - 1], outline=STEEL, width=max(1, s // 6))
    return img


def weapon_icon(tile: int, kind: str) -> Image.Image:
    """The pickup of one weapon kind: a plate with the weapon's mark."""
    t = _size(tile)
    img, d = _new(t, t)
    d.rounded_rectangle([1, 1, t - 2, t - 2], radius=max(1, t // 6), fill=BLACK, outline=STEEL)
    mid, q = t // 2, max(2, t // 4)
    if kind == "spread":
        for dx in (-q, 0, q):
            d.line([(mid, t - q), (mid + dx, q)], fill=SHOT)
    elif kind == "laser":
        d.rectangle([mid - 1, q, mid, t - 1 - q], fill=BEAM)
    elif kind == "flame":
        d.polygon([(mid, q), (t - q, t - q), (q, t - q)], fill=FIRE)
    elif kind == "machinegun":
        for y in range(q, t - q, max(2, t // 8)):
            d.point((mid, y), fill=SHOT)
            d.point((mid - 1, y), fill=SHOT)
    elif kind == "missile":
        d.rectangle([mid - 1, q + 1, mid, t - 1 - q], fill=STEEL)
        d.point((mid, q), fill=RED)
        d.point((mid - 1, q), fill=RED)
    else:
        raise ValueError(f"no such weapon: {kind}")
    return img


# --------------------------------------------------------------------------- the catalog


@dataclass(frozen=True)
class StandIn:
    """One thing the kit can draw for a kind of game."""

    name: str  # the file's name and the end of the asset's id
    role: str
    thing: str  # what the note calls it
    draw: Callable[[int], Image.Image]
    tags: tuple[str, ...] = ()  # an asset of the packs with one of these does the job as well
    required: bool = False  # the kind cannot be made without the role: the kit fills it


def _sprite(image: Image.Image) -> dict[str, Any]:
    w, h = image.size
    return {"usage": "sprite", "frame": [w, h], "origin": [w // 2, h - 1], "size": [w, h]}


def _facets(stand_in: StandIn, image: Image.Image, tile: int) -> dict[str, Any]:
    w, h = image.size
    grid = {"margin": [0, 0], "separation": [0, 0]}
    if stand_in.name == "car":
        cell = w // CAR_HEADINGS
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [cell, h], **grid},
            "frame": [cell, h],
            "origin": [cell // 2, h - 1],
            "headings": CAR_HEADINGS,
            "heading_order": "up_cw",
            "size": [w, h],
        }
    elif stand_in.name == "explosion":
        cell = w // EXPLOSION_FRAMES
        facets = {
            "usage": "sprite",
            "grid": {"cell": [cell, h], **grid},
            "frame": [cell, h],
            "origin": [cell // 2, h // 2],
            "animations": {
                "idle_down": {
                    "frames": [[i, 0] for i in range(EXPLOSION_FRAMES)],
                    "fps": 12.0,
                    "loop": False,
                }
            },
            "size": [w, h],
        }
    elif stand_in.name == "road":
        facets = {
            "usage": "tiles",
            "grid": {"cell": [h, h], **grid},
            "collision": {"profile": "NONE"},
            "tile_overrides": {
                f"{i},0": {"custom": {"road": name}}
                for i, name in enumerate(ROAD_TILES)
                if name != "grass"
            },
            "size": [w, h],
        }
        facets["tile_overrides"][f"{ROAD_TILES.index('barrier')},0"]["collision"] = {
            "profile": "FULL"
        }
    else:
        facets = _sprite(image)
    facets["role"] = stand_in.role
    facets["tags"] = sorted({KIT_TAG, *stand_in.tags[:1]})
    return facets


SHIP = StandIn("ship", "PLAYER", "ship", ship, ("ship",), required=True)
BULLET = StandIn("bullet", "PROJECTILE", "bullet", bullet, ("bullet",))
EXPLOSION = StandIn("explosion", "EXPLOSION", "explosion", explosion, ("explosion",))
CAPSULE = StandIn("capsule", "POWERUP", "power-up", capsule, ("powerup",))
CAR = StandIn("car", "VEHICLE", "car in sixteen headings", car, required=True)
ROAD = StandIn("road", "GROUND", "road", road, ("road",), required=True)
HOOK = StandIn("hook", "ITEM", "grapple hook", hook, ("grapple",))
STAND_INS: dict[str, tuple[StandIn, ...]] = {
    "shmup": (SHIP, BULLET, EXPLOSION, CAPSULE),
    "run_and_gun": (BULLET, EXPLOSION, CAPSULE, HOOK),
    "racing": (CAR, ROAD),
}


def drawn_roles(archetype: str) -> frozenset[str]:
    """The roles the kit fills for ``archetype`` when the packs do not: a kind of game is
    never refused for the lack of one of them."""
    return frozenset(s.role for s in STAND_INS.get(archetype, ()) if s.required)


def _has(catalog: catalog_mod.Catalog, stand_in: StandIn, projection: str = "top_down") -> bool:
    """See ``_has_role``; on an isometric track a car is one of eight headings or more (T18.19):
    a single picture of a car is rotated flat, which looks wrong at the view's angle."""
    if stand_in.name == "car" and projection == catalog_mod.PROJECTION_ISOMETRIC:
        return any(
            asset.status not in _INACTIVE
            and asset.pack_id != KIT_PACK
            and catalog_mod.effective(asset).get("role") == stand_in.role
            and int(catalog_mod.effective(asset).get("headings", 1) or 1) >= 8
            for asset in catalog.assets
        )
    return _has_role(catalog, stand_in, projection)


def _has_role(
    catalog: catalog_mod.Catalog, stand_in: StandIn, projection: str = "top_down"
) -> bool:
    """True when the packs have what ``stand_in`` would stand in for: an asset in use with its
    role. A tag alone does not count: the recipes of the kinds look for the role, so a pickup
    that is only tagged ``bullet`` would leave the game without a bullet (T16.09)."""
    for asset in catalog.assets:
        if asset.status in _INACTIVE or asset.pack_id == KIT_PACK:
            continue
        # what was drawn for the other view is not there for this one (T17.13): a top-down
        # race does not drive the car of an isometric pack
        if not catalog_mod.fits_projection(asset, projection):
            continue
        if catalog_mod.effective(asset).get("role") == stand_in.role:
            return True
    return False


def lacking(
    catalog: catalog_mod.Catalog, archetype: str, projection: str = "top_down"
) -> list[StandIn]:
    """What the kit has to draw for ``archetype`` with this catalog."""
    return [s for s in STAND_INS.get(archetype, ()) if not _has(catalog, s, projection)]


def asset_id(stand_in: StandIn) -> str:
    return f"{KIT_PACK}.{stand_in.name}"


def add(
    catalog: catalog_mod.Catalog,
    archetype: str,
    tile: int,
    staging_root: Path,
    projection: str = "top_down",
    footprint: tuple[int, int] | None = None,
) -> tuple[list[str], IssueList]:
    """Draw what ``archetype`` needs and the packs lack into the staging copy, add it to the
    catalog and return the names with one ``ASSET-031`` note each. The stand-ins of the last
    run (a regeneration finds them in the catalog, without their files) are replaced."""
    issues = IssueList()
    own = {asset_id(s) for group in STAND_INS.values() for s in group}
    catalog.assets[:] = [a for a in catalog.assets if a.id not in own]
    added: list[str] = []
    for stand_in in lacking(catalog, archetype, projection):
        iso = stand_in.name == "car" and projection == catalog_mod.PROJECTION_ISOMETRIC
        image = iso_car(footprint or (tile * 2, tile)) if iso else stand_in.draw(tile)
        rel = f"{KIT_DIR}/{stand_in.name}.png"
        target = Path(staging_root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG", optimize=False, compress_level=9, pnginfo=None)
        catalog.assets.append(
            catalog_mod.Asset(
                id=asset_id(stand_in),
                pack_id=KIT_PACK,
                path=rel,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                kind="image",
                status="CONFIRMED",
                detected={
                    **_facets(stand_in, image, tile),
                    **({"projection": projection} if iso else {}),
                },
                detected_by="placeholder",
                confidence=1.0,
            )
        )
        issues.add("ASSET-031", role=stand_in.role, thing=stand_in.thing, file=rel)
        added.append(stand_in.name)
    if added:
        if not any(p.pack_id == KIT_PACK for p in catalog.packs):
            catalog.packs.append(
                catalog_mod.CatalogPack(KIT_PACK, "0" * 64, KIT_DIR, [], [], None, [])
            )
        if "road" in added:
            previous = catalog_mod.Catalog.from_json(catalog.to_json())
            catalog_mod.assign_tilesets(catalog, previous)
        catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    return added, issues

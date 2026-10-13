"""Drawn people for the isometric view (T17.14).

None of the isometric packs that were listed has a character: they are tiles, trees and houses.
A character drawn from the front or for a top-down game stands on an isometric map as it is
(the usual look of such games), so a project that has one from another pack uses it. A project
that has none gets a hero, a villager and an enemy drawn here, each with a walk in four
directions, plainly, as wide as one step on the diamonds of its ground, and says so with a note
(``ASSET-031``), as ``arcade_kit.py`` and ``farm_kit.py`` do for their kinds. A pack's own
asset always wins by its role.

The debug placeholders (``placeholders.py``) draw a player too, when one is asked for with
``--placeholder PLAYER``: a magenta checkerboard that says *missing*. That is a tool for finding
what a pack lacks, not a figure to play with, and nobody gets one unasked; so the people of an
isometric project are drawn here, and a placeholder that was asked for still wins (it is an
asset with the role).

The pictures are drawn from integer arithmetic, so they are the same on every machine.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from rpggen.core import catalog as catalog_mod
from rpggen.core import iso_math
from rpggen.errors import IssueList

KIT_PACK = "rpggen_iso_kit"
KIT_DIR = "generated/iso_kit"
KIT_TAG = "iso_kit"
PROJECTION = catalog_mod.PROJECTION_ISOMETRIC
DIRECTIONS = ("down", "left", "right", "up")  # the rows of a sheet, top to bottom
FRAMES = 4  # the columns: a walk of four frames, the first of which is the figure standing
MIN_WIDTH = 12
_INACTIVE = {"UNUSED", "MISSING"}

Color = tuple[int, int, int, int]
CLEAR: Color = (0, 0, 0, 0)
DARK: Color = (34, 30, 40, 255)
SKIN: Color = (236, 196, 160, 255)
EYE: Color = (30, 30, 40, 255)
SHADOW: Color = (0, 0, 0, 70)


@dataclass(frozen=True)
class StandIn:
    name: str
    role: str
    thing: str  # what the note calls it
    body: Color
    legs: Color
    hair: Color
    eye: Color = EYE
    skin: Color = SKIN
    horns: bool = False


HERO = StandIn("hero", "PLAYER", "hero", (58, 110, 200, 255), (60, 50, 70, 255), (120, 78, 40, 255))
VILLAGER = StandIn(
    "villager", "NPC", "villager", (190, 150, 70, 255), (96, 70, 50, 255), (70, 50, 40, 255)
)
ENEMY = StandIn(
    "enemy", "ENEMY", "enemy", (150, 50, 60, 255), (70, 30, 40, 255), (90, 160, 80, 255),
    eye=(250, 230, 80, 255), skin=(110, 170, 90, 255), horns=True,
)  # fmt: skip
STAND_INS: tuple[StandIn, ...] = (HERO, VILLAGER, ENEMY)


def frame_size(footprint: tuple[int, int]) -> tuple[int, int]:
    """The frame of a drawn figure for a diamond of ``footprint``: as wide as one step from a
    diamond to the next (``iso_math.unit``, an even number, at least 12) and half as high
    again. A figure of a top-down pack is a tile wide; this one is what the isometric view has
    for a tile, so a reach, a hit and a body are in the proportion the kinds were made with."""
    width = max(MIN_WIDTH, iso_math.unit(int(footprint[0]), int(footprint[1])))
    width -= width % 2
    return width, width * 3 // 2


def _cell(stand_in: StandIn, w: int, h: int, direction: str, frame: int) -> Image.Image:
    """One frame: a figure seen from the front (down), the back (up) or the side, its legs
    apart on the second and the fourth frame of the walk and its body a pixel lower then."""
    img = Image.new("RGBA", (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    u = max(1, w // 12)  # the unit every measure is counted in
    cx = w // 2
    stride = (0, 1, 0, -1)[frame % FRAMES]
    bob = u if stride else 0
    foot = h - 1
    d.ellipse([cx - 4 * u, foot - 2 * u, cx + 4 * u, foot], fill=SHADOW)
    leg_top = foot - 5 * u
    head_r = 3 * u
    body_top = leg_top - 6 * u + bob
    head_cy = body_top - head_r + u
    side = direction in ("left", "right")
    turn = -1 if direction == "left" else 1
    # legs: apart sideways from the front, one ahead of the other from the side
    for leg in (-1, 1):
        if side:
            x = cx + leg * stride * 2 * u - u
            lift = u if leg * stride > 0 else 0
        else:
            x = cx + leg * 2 * u - u
            lift = u if leg * stride > 0 else 0
        d.rectangle([x, leg_top, x + 2 * u - 1, foot - u - lift], fill=stand_in.legs, outline=DARK)
    # body, and an arm that swings against the legs
    half = 3 * u if side else 4 * u
    d.rectangle([cx - half, body_top, cx + half - 1, leg_top], fill=stand_in.body, outline=DARK)
    if side:
        ax = cx - stride * turn * 2 * u
        d.rectangle([ax - u, body_top + u, ax + u - 1, leg_top - u], fill=stand_in.skin)
    else:
        for arm in (-1, 1):
            ax = cx + arm * (half + u) - (u if arm < 0 else 0)
            swing = u if arm * stride > 0 else 0
            d.rectangle(
                [ax - (0 if arm < 0 else u), body_top + u + swing, ax + (u if arm < 0 else 0),
                 leg_top - 2 * u + swing],
                fill=stand_in.skin,
            )  # fmt: skip
    # head
    box = [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r]
    d.ellipse(box, fill=stand_in.skin, outline=DARK)
    if direction == "up":
        d.ellipse(box, fill=stand_in.hair, outline=DARK)
    else:
        d.pieslice(box, 180, 360, fill=stand_in.hair, outline=DARK)
        if side:
            d.rectangle([cx + turn * u, head_cy, cx + turn * u + u - 1, head_cy + u - 1],
                        fill=stand_in.eye)  # fmt: skip
        else:
            for eye in (-1, 1):
                ex = cx + eye * u - (u if eye < 0 else 0)
                d.rectangle([ex, head_cy, ex + u - 1, head_cy + u - 1], fill=stand_in.eye)
    if stand_in.horns:
        for horn in (-1, 1):
            hx = cx + horn * (head_r - u)
            d.polygon(
                [(hx - u, head_cy - head_r + u), (hx + u, head_cy - head_r + u),
                 (hx + horn * u, head_cy - head_r - 2 * u)],
                fill=(230, 230, 220, 255), outline=DARK,
            )  # fmt: skip
    return img


def sheet(stand_in: StandIn, footprint: tuple[int, int]) -> Image.Image:
    """The sheet of a figure: four rows (down, left, right, up) of four frames."""
    w, h = frame_size(footprint)
    img = Image.new("RGBA", (w * FRAMES, h * len(DIRECTIONS)), CLEAR)
    for row, direction in enumerate(DIRECTIONS):
        for frame in range(FRAMES):
            img.paste(_cell(stand_in, w, h, direction, frame), (frame * w, row * h))
    return img


def _facets(stand_in: StandIn, image: Image.Image, footprint: tuple[int, int]) -> dict[str, Any]:
    w, h = frame_size(footprint)
    animations: dict[str, Any] = {}
    for row, direction in enumerate(DIRECTIONS):
        animations[f"walk_{direction}"] = {
            "frames": [[c, row] for c in range(FRAMES)],
            "fps": 8.0,
            "loop": True,
        }
        animations[f"idle_{direction}"] = {"frames": [[0, row]], "fps": 1.0, "loop": True}
    return {
        "usage": "sprite",
        "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
        "frame": [w, h],
        "origin": [w // 2, h - 1],
        "directions": 4,
        "animations": animations,
        "size": [image.width, image.height],
        "role": stand_in.role,
        "tags": [KIT_TAG],
    }


def _has(catalog: catalog_mod.Catalog, stand_in: StandIn) -> bool:
    """True when the packs have what ``stand_in`` would stand in for: an asset in use with its
    role that an isometric project can use (a character drawn for any view; a debug
    placeholder that was asked for)."""
    for asset in catalog.assets:
        if asset.status in _INACTIVE or asset.pack_id == KIT_PACK:
            continue
        if not catalog_mod.fits_projection(asset, PROJECTION):
            continue
        if catalog_mod.effective(asset).get("role") == stand_in.role:
            return True
    return False


def lacking(catalog: catalog_mod.Catalog, projection: str = PROJECTION) -> list[StandIn]:
    """The people the kit has to draw for a project seen in ``projection`` with this catalog:
    none for a project seen from above."""
    if projection != PROJECTION:
        return []
    return [s for s in STAND_INS if not _has(catalog, s)]


def drawn_roles(catalog: catalog_mod.Catalog, projection: str = PROJECTION) -> frozenset[str]:
    """The roles the kit fills for this catalog: an isometric project is never refused for the
    lack of a hero."""
    return frozenset(s.role for s in lacking(catalog, projection))


def asset_id(stand_in: StandIn) -> str:
    return f"{KIT_PACK}.{stand_in.name}"


def add(
    catalog: catalog_mod.Catalog,
    footprint: tuple[int, int] | None,
    staging_root: Path,
    projection: str = PROJECTION,
) -> tuple[list[str], IssueList]:
    """Draw the people an isometric project lacks into the staging copy, add them to the
    catalog and return their names with one ``ASSET-031`` note each. The kit of the last run
    (a regeneration finds it in the catalog, without its files) is replaced; a project seen
    from above gets nothing and loses what a last run left."""
    issues = IssueList()
    catalog.assets[:] = [a for a in catalog.assets if a.pack_id != KIT_PACK]
    added: list[str] = []
    if footprint is not None:
        for stand_in in lacking(catalog, projection):
            image = sheet(stand_in, footprint)
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
                    detected=_facets(stand_in, image, footprint),
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
        catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    else:
        catalog.packs[:] = [p for p in catalog.packs if p.pack_id != KIT_PACK]
    return added, issues

"""The side-view kit (T14.06): four generated tiles for a metroidvania whose packs lack them.

A room needs a platform to jump through, a ladder, spikes and a block that breaks. A top-down
pack has none of them, and a platformer pack may miss one. Rather than leaving a room without its
ladder, rpggen adds one small generated sheet to the catalog (``generated/side_kit/side_kit.png``,
four tiles in a row) whose tiles are marked as those four kinds. The rooms recipe uses a pack's
own tile for a kind when there is one and the kit's only for what is missing.

The sheet is drawn from integer arithmetic, so it is the same on every machine.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from rpggen.core import catalog as catalog_mod

KIT_PACK = "rpggen_side_kit"
KIT_DIR = "generated/side_kit"
KIT_FILE = "side_kit.png"
KIT_ASSET = f"{KIT_PACK}.side_kit"
KINDS = ("one_way", "ladder", "hazard", "breakable")
# what each cell of the sheet is, as the audit would write it
TILE_OVERRIDES: dict[str, dict[str, Any]] = {
    "0,0": {"collision": {"profile": "ONE_WAY"}},
    "1,0": {"collision": {"profile": "LADDER"}},
    "2,0": {"collision": {"profile": "NONE"}, "custom": {"hazard": True}},
    "3,0": {"collision": {"profile": "FULL"}, "custom": {"breakable": True}},
}
_INACTIVE = {"UNUSED", "MISSING"}

WOOD = (156, 108, 62, 255)
WOOD_DARK = (98, 64, 34, 255)
STEEL = (212, 214, 226, 255)
BASE = (62, 56, 78, 255)
BLOCK = (148, 140, 160, 255)
CRACK = (36, 30, 44, 255)


def _tile_kinds(facets: dict[str, Any], override: dict[str, Any]) -> set[str]:
    """The kinds one tile is, read like ``builder/lib/side_tileset.gd`` reads them."""
    tags = set(facets.get("tags") or [])
    collision = override.get("collision") or facets.get("collision") or {}
    profile = collision.get("profile")
    if "collision" not in override and "collision" not in facets:
        profile = "ONE_WAY" if "one_way" in tags else "LADDER" if "ladder" in tags else None
    custom = override.get("custom") or {}
    own = "collision" in override
    out = set()
    if profile == "ONE_WAY":
        out.add("one_way")
    if profile == "LADDER" or custom.get("ladder"):
        out.add("ladder")
    if custom.get("hazard", "hazard" in tags and not own):
        out.add("hazard")
    if custom.get("breakable", "breakable" in tags and not own):
        out.add("breakable")
    return out


def kinds_in(catalog: catalog_mod.Catalog) -> set[str]:
    """The side-view kinds the packs' own tile sheets have (the kit itself does not count)."""
    found: set[str] = set()
    for asset in catalog.assets:
        if asset.status in _INACTIVE or asset.pack_id == KIT_PACK:
            continue
        facets = catalog_mod.effective(asset)
        if facets.get("usage") != "tiles":
            continue
        found |= _tile_kinds(facets, {})
        for override in (facets.get("tile_overrides") or {}).values():
            if isinstance(override, dict):
                found |= _tile_kinds(facets, override)
    return found


def missing_kinds(catalog: catalog_mod.Catalog) -> list[str]:
    have = kinds_in(catalog)
    return [k for k in KINDS if k not in have]


def make_image(tile: int) -> Image.Image:
    """The kit sheet for ``tile`` px tiles: a plank, a ladder, spikes and a cracked block."""
    t = max(8, int(tile))
    img = Image.new("RGBA", (t * 4, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    thick = max(2, t * 5 // 16)
    d.rectangle([0, 0, t - 1, thick - 1], fill=WOOD)  # the plank: the top of the cell
    d.line([(0, thick - 1), (t - 1, thick - 1)], fill=WOOD_DARK)
    rail = max(1, t // 8)
    x0 = t + t * 3 // 16
    x1 = t + t - 1 - t * 3 // 16
    d.rectangle([x0, 0, x0 + rail - 1, t - 1], fill=WOOD_DARK)  # the ladder: two rails, rungs
    d.rectangle([x1 - rail + 1, 0, x1, t - 1], fill=WOOD_DARK)
    for y in range(t // 8, t, max(3, t * 5 // 16)):
        d.rectangle([x0, y, x1, y + rail - 1], fill=WOOD)
    base = max(1, t * 3 // 16)
    d.rectangle([2 * t, t - base, 3 * t - 1, t - 1], fill=BASE)  # spikes: four teeth on a base
    tooth = t // 4
    for i in range(4):
        left = 2 * t + i * tooth
        d.polygon(
            [(left, t - base - 1), (left + tooth // 2, t // 4), (left + tooth - 1, t - base - 1)],
            fill=STEEL,
        )
    d.rectangle([3 * t, 0, 4 * t - 1, t - 1], fill=BLOCK, outline=CRACK)  # the cracked block
    d.line([(3 * t + t // 4, 1), (3 * t + t // 2, t // 2), (3 * t + t // 3, t - 2)], fill=CRACK)
    d.line([(3 * t + t // 2, t // 2), (3 * t + t * 3 // 4, t // 3)], fill=CRACK)
    return img


def add(catalog: catalog_mod.Catalog, tile: int, staging_root: Path) -> list[str]:
    """Write the kit sheet into the staging copy and add it to the catalog when the packs lack a
    side-view kind. Returns the kinds the kit stands in for (empty: nothing was added). Calling
    it again on a catalog that has the kit changes nothing."""
    lacking = missing_kinds(catalog)
    if not lacking:
        return []
    rel = f"{KIT_DIR}/{KIT_FILE}"
    target = Path(staging_root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    make_image(tile).save(target, format="PNG", optimize=False, compress_level=9, pnginfo=None)
    if catalog.asset(KIT_ASSET) is not None:
        return lacking
    facets: dict[str, Any] = {
        "usage": "tiles",
        "role": "DECORATION",
        "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
        "collision": {"profile": "NONE"},
        "tile_overrides": copy.deepcopy(TILE_OVERRIDES),
        "tags": ["side_kit"],
        "size": [tile * 4, tile],
    }
    catalog.assets.append(
        catalog_mod.Asset(
            id=KIT_ASSET,
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
    if not any(p.pack_id == KIT_PACK for p in catalog.packs):
        catalog.packs.append(catalog_mod.CatalogPack(KIT_PACK, "0" * 64, KIT_DIR, [], [], None, []))
    previous = catalog_mod.Catalog.from_json(catalog.to_json())
    catalog_mod.assign_tilesets(catalog, previous)
    catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    return lacking

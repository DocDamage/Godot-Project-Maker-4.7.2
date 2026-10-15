"""The plain ground of a farm (after T17.29).

Every map of a farm was painted with the first tile of its ground sheet, and on the real
farming packs that tile is no ground one walks on: Kenney's *Tiny Farm* starts its sheet with
the corner of a bed of soil (orange on green), EmanuelleDev's *Farm RPG* with the corner of a
blob of grass on transparency. The ground is chosen from the pictures instead:

* every tile of the sheet is measured: is it **opaque** all over, does it **tile with itself**
  (laid beside itself its left column meets its right one and its top row its bottom one about
  as smoothly as its own neighbouring pixels meet, within ``SEAM_RATIO``), is it **one
  surface** (``SURFACE_SHARE`` of its pixels are grass, or are earth), and how **even** it is
  (``spread``: the sum of the standard deviations of its colour channels);
* the ground is the most even tile of the surface the sheet says (``surface:grass``), else
  of grass, else of earth: the first of the sheet when several are as even.

It is one tile, laid everywhere: varying the ground and joining it to soil, water and paths is
painting with the terrains of the tile set, which is a card of its own (T17.31). A sheet that has
no such tile (*Tiny Farm*, whose grass is only the green round its beds) gets a plain ground
drawn by the farm kit in the sheet's own grass colour (``rpggen_farm_kit.ground``, the note
``ASSET-031``). An isometric farm is left as it is: its ground is the plainest flat tile already
(``iso_tileset.plain_tile``).

What was chosen goes into the farm's section of the plan file (``farm.ground``: the asset and the
cell ``[column, row]`` of the tile), measured again on every run; the recipes read it
(``builder/lib/plain_ground.gd``).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import catalog as catalog_mod
from rpggen.errors import IssueList

VERSION = 1
OPAQUE = 230  # alpha: a tile is opaque when every pixel has this much
SEAM_RATIO = 3.0  # it tiles when its seams differ this little from its neighbouring pixels
NEAR_FLOOR = 1.0 / 255.0  # ... a tile of one colour has no neighbouring difference at all
SURFACE_SHARE = 0.85  # a tile is of one surface when this share of its pixels are of it
MAX_SPREAD = 0.35  # a tile more uneven than this is no plain ground, whatever it is
GRASS, EARTH = "grass", "earth"
KIT_NAME = "ground"  # rpggen_farm_kit.ground
KIT_TAG = "plain_ground"


def surfaces(rgb: np.ndarray) -> np.ndarray:
    """The surface of every pixel (``rgb`` in 0..1, ... x 3): 1 grass (a green or a teal of some
    colour), 2 earth (a brown, a sand, an orange), 0 anything else (an outline, water, stone)."""
    flat = rgb.reshape(-1, 3).astype(np.float64)
    v = flat.max(axis=1)
    low = flat.min(axis=1)
    chroma = v - low
    s = np.where(v > 0, chroma / np.where(v > 0, v, 1.0), 0.0)
    r, g, b = flat[:, 0], flat[:, 1], flat[:, 2]
    safe = np.where(chroma > 0, chroma, 1.0)
    h = np.where(
        v == r, ((g - b) / safe) % 6.0, np.where(v == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0)
    )
    h = np.where(chroma > 0, h * 60.0, 0.0)
    out = np.zeros(len(flat), dtype=np.int8)
    out[(h >= 60) & (h <= 175) & (s >= 0.2) & (v >= 0.15)] = 1
    out[(h >= 10) & (h < 60) & (s >= 0.2) & (v >= 0.25)] = 2
    return out.reshape(rgb.shape[:-1])


def tile_facts(tile: np.ndarray) -> dict[str, Any] | None:
    """What a tile (h x w x 4, uint8) is as ground: ``{surface, spread, mean}``, or None when it
    is not opaque all over, does not tile with itself or is not one surface."""
    if tile.size == 0 or int(tile[..., 3].min()) < OPAQUE:
        return None
    rgb = tile[..., :3].astype(np.float64) / 255.0
    near = float((np.abs(np.diff(rgb, axis=0)).mean() + np.abs(np.diff(rgb, axis=1)).mean()) / 2.0)
    seam = max(float(np.abs(rgb[:, 0] - rgb[:, -1]).mean()), float(np.abs(rgb[0] - rgb[-1]).mean()))
    if seam > SEAM_RATIO * max(near, NEAR_FLOOR):
        return None
    kinds = surfaces(rgb)
    counts = Counter(int(k) for k in kinds.ravel())
    kind, count = max(
        ((k, c) for k, c in counts.items() if k), key=lambda kc: kc[1], default=(0, 0)
    )
    if not kind or count < SURFACE_SHARE * kinds.size:
        return None
    spread = float(rgb.reshape(-1, 3).std(axis=0).sum())
    if spread > MAX_SPREAD:
        return None
    return {
        "surface": GRASS if kind == 1 else EARTH,
        "spread": spread,
        "mean": rgb.reshape(-1, 3).mean(axis=0),
    }


def cells_of(
    size: tuple[int, int], grid: dict[str, Any]
) -> list[tuple[int, int, int, int, int, int]]:
    """``(column, row, x, y, w, h)`` of every cell of a sheet of ``size`` cut by ``grid``."""
    cell = grid.get("cell") or [0, 0]
    margin = grid.get("margin") or [0, 0]
    sep = grid.get("separation") or [0, 0]
    cw, ch = int(cell[0]), int(cell[1])
    if cw <= 0 or ch <= 0:
        return []
    out = []
    row, y = 0, int(margin[1])
    while y + ch <= size[1]:
        col, x = 0, int(margin[0])
        while x + cw <= size[0]:
            out.append((col, row, x, y, cw, ch))
            col += 1
            x += cw + int(sep[0])
        row += 1
        y += ch + int(sep[1])
    return out


def choose(picture: np.ndarray, grid: dict[str, Any], said: str = "") -> dict[str, Any] | None:
    """The plain ground of a sheet (see the module): ``{surface, base}`` with the cell as
    ``[column, row]``, or None when it has no plain tile. ``said`` is the surface the sheet's
    tags say (``grass``), which goes first."""
    found = []
    seen: set[bytes] = set()
    for col, row, x, y, w, h in cells_of((picture.shape[1], picture.shape[0]), grid):
        tile = picture[y : y + h, x : x + w]
        digest = hashlib.sha1(np.ascontiguousarray(tile).tobytes()).digest()
        if digest in seen:
            continue  # a copy of a tile counts once
        seen.add(digest)
        facts = tile_facts(tile)
        if facts is not None:
            found.append((col, row, facts))
    if not found:
        return None
    order = [said] if said in (GRASS, EARTH) else []
    order += [s for s in (GRASS, EARTH) if s not in order]
    for surface in order:
        same = [f for f in found if f[2]["surface"] == surface]
        if not same:
            continue
        # the most even; of two as even the first of the sheet (rows, then columns)
        base = min(same, key=lambda f: (round(f[2]["spread"], 4), f[1], f[0]))
        return {"surface": surface, "base": [base[0], base[1]]}
    return None


def grass_colour(picture: np.ndarray) -> tuple[int, int, int] | None:
    """The sheet's own grass: its most frequent colour of grass among the opaque pixels, or None
    when the sheet has no grass to speak of."""
    opaque = picture[picture[..., 3] >= OPAQUE][:, :3]
    if not len(opaque):
        return None
    counts = Counter(map(tuple, opaque.tolist()))
    greens = [
        (c, n)
        for c, n in counts.most_common()
        if surfaces(np.array([c], dtype=np.float64) / 255.0)[0] == 1
    ]
    if not greens or greens[0][1] < 64:
        return None
    r, g, b = (int(v) for v in greens[0][0])
    return r, g, b


def draw(tile: int, colour: tuple[int, int, int]) -> Image.Image:
    """A plain ground of one tile in ``colour``."""
    t = max(4, int(tile))
    a = np.zeros((t, t, 4), dtype=np.uint8)
    a[..., :3] = colour
    a[..., 3] = 255
    return Image.fromarray(a, "RGBA")


def ground_asset(catalog: catalog_mod.Catalog, cfg: Any) -> catalog_mod.Asset | None:
    """The ground sheet the farm's maps are painted with: the one the config chooses (the
    village's ground, else the starter's, else the ground the Mapping page would choose first),
    when it is a sheet of tiles."""
    from rpggen.core import mapping

    wanted = None
    for section in (getattr(cfg, "starter_map", {}) or {}, getattr(cfg, "starter", {}) or {}):
        wanted = section.get("ground") if isinstance(section, dict) else None
        if wanted:
            break
    if not wanted:
        projection = getattr(cfg, "projection", mapping.TOP_DOWN) or mapping.TOP_DOWN
        wanted = mapping.best_for(catalog, "GROUND", projection)
    asset = catalog.asset(str(wanted)) if wanted else None
    if asset is not None and catalog_mod.effective(asset).get("usage") == "tiles":
        return asset
    return None


def _picture(asset: catalog_mod.Asset, root: Path) -> np.ndarray | None:
    path = Path(root) / asset.path
    if not path.is_file():
        return None
    try:
        with Image.open(path) as opened:
            return np.asarray(opened.convert("RGBA"), dtype=np.uint8)
    except (OSError, ValueError):
        return None


def _said(asset: catalog_mod.Asset) -> str:
    tags = {str(t) for t in catalog_mod.effective(asset).get("tags") or []}
    return (
        GRASS
        if "surface:grass" in tags
        else EARTH
        if tags & {"surface:dirt", "surface:earth"}
        else ""
    )


def kit_id() -> str:
    from rpggen.core import farm_kit

    return f"{farm_kit.KIT_PACK}.{KIT_NAME}"


def plan(catalog: catalog_mod.Catalog, cfg: Any, root: Path) -> dict[str, Any] | None:
    """``farm.ground`` of the plan file (see the module), or None: an isometric farm, a ground
    that is no sheet of tiles, a sheet that cannot be read."""
    if getattr(cfg, "projection", "top_down") == catalog_mod.PROJECTION_ISOMETRIC:
        return None
    drawn = catalog.asset(kit_id())
    if drawn is not None:
        return {"v": VERSION, "asset": drawn.id, "surface": GRASS, "base": [0, 0]}
    asset = ground_asset(catalog, cfg)
    if asset is None:
        return None
    picture = _picture(asset, root)
    grid = catalog_mod.effective(asset).get("grid") or {}
    if picture is None or not grid:
        return None
    chosen = choose(picture, grid, _said(asset))
    if chosen is None:
        return None
    return {"v": VERSION, "asset": asset.id, **chosen}


def add(catalog: catalog_mod.Catalog, cfg: Any, tile: int, root: Path) -> IssueList:
    """Draw the plain ground of a farm whose ground sheet has none (see the module) into the
    staging copy and add it to the catalog, with its note. The drawn ground of the last run is
    taken out first; a farm whose sheet has a plain tile, an isometric farm and a ground that is
    no sheet get none."""
    from rpggen.core import farm_kit

    issues = IssueList()
    catalog.assets[:] = [a for a in catalog.assets if a.id != kit_id()]
    if getattr(cfg, "projection", "top_down") == catalog_mod.PROJECTION_ISOMETRIC:
        return issues
    asset = ground_asset(catalog, cfg)
    if asset is None:
        return issues
    picture = _picture(asset, root)
    grid = catalog_mod.effective(asset).get("grid") or {}
    if picture is None or not grid or choose(picture, grid, _said(asset)) is not None:
        return issues
    colour = grass_colour(picture)
    if colour is None:
        return issues
    image = draw(tile, colour)
    rel = f"{farm_kit.KIT_DIR}/{KIT_NAME}.png"
    t = max(4, int(tile))
    facets = {
        "usage": "tiles",
        "role": "DECORATION",  # never the ground another recipe finds by its role
        "grid": {"cell": [t, t], "margin": [0, 0], "separation": [0, 0]},
        "collision": {"profile": "NONE"},
        "size": [image.width, image.height],
        "tags": sorted({farm_kit.KIT_TAG, KIT_TAG, "surface:grass", "drawn_from:" + asset.id}),
    }
    farm_kit._append(catalog, root, kit_id(), rel, image, facets)
    if not any(p.pack_id == farm_kit.KIT_PACK for p in catalog.packs):
        catalog.packs.append(
            catalog_mod.CatalogPack(farm_kit.KIT_PACK, "0" * 64, farm_kit.KIT_DIR, [], [], None, [])
        )
    previous = catalog_mod.Catalog.from_json(catalog.to_json())
    catalog_mod.assign_tilesets(catalog, previous)
    catalog.assets.sort(key=lambda a: (a.id.casefold(), a.id))
    issues.add("ASSET-031", role="GROUND", thing="plain ground", file=rel)
    return issues

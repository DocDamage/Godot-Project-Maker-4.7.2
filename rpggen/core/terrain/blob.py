"""Recognizer for generic blob / corner terrain sheets (T8.06c). Best effort, confidence scored.

Two layouts are recognized, both read row-major (left to right, top to bottom), tiles of
``cell`` pixels without margin or separation:

* ``blob47_12x4`` - the "Godot/Tilesetter blob" arrangement: 47 tiles in a 12 x 4 grid (the 48th
  cell stays empty). ASSUMED ORDER: the 47 normalized 8-neighbor masks ascending by mask value,
  with the bits N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128 and a corner bit only set when
  both adjacent side bits are set (the same order ``rpgmaker_a2`` composes). Sheets that use a
  different order are not recognized (their borders do not match) and report TILE-006.
* ``corners16_4x4`` - 16 corner-only tiles in a 4 x 4 grid. ASSUMED ORDER: tile index bits
  top_left=1, top_right=2, bottom_right=4, bottom_left=8.

Every pair of tiles that must meet in a seamless map (their shared edge describes the same
neighbor states) is checked: the mean absolute difference of the touching pixel rows/columns
must stay below ``MATCH_THRESHOLD``. A layout is accepted when at least ``ACCEPT_RATIO`` of those
expected adjacencies match, almost all cells are drawn and the tiles are not all alike.

Results are *proposals* (facet ``terrain_proposal``). ``accept_proposal`` moves one into the
asset's ``tile_overrides`` override, ``reject_proposal`` hides it; the user decides.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import catalog as catalog_mod
from rpggen.core.terrain import rpgmaker_a2 as a2
from rpggen.core.terrain.tiled_wang import empty_peering

MATCH_THRESHOLD = 12.0  # mean absolute channel difference (0..255) of two touching edges
ACCEPT_RATIO = 0.9
MIN_FILLED = 0.9  # share of expected tiles that must contain pixels
MIN_DISTINCT = 0.9  # share of tiles that must differ from every other tile

BLOB47 = "blob47_12x4"
CORNERS16 = "corners16_4x4"
LAYOUT_SHAPES = {BLOB47: (12, 4), CORNERS16: (4, 4)}

_TL, _TR, _BR, _BL = 1, 2, 4, 8
_Edges = dict[str, tuple[bool, ...] | None]


@dataclass
class Recognition:
    layout: str
    confidence: float  # matched / expected adjacencies
    accepted: bool
    matched: int = 0
    expected: int = 0
    tile_overrides: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- tile semantics


def _blob_edges(mask: int) -> _Edges:
    """Edge descriptors of a tile; ``None`` when that side faces outside the terrain."""
    n, ne, e, se, s, sw, w, nw = (bool(mask & b) for b in (1, 2, 4, 8, 16, 32, 64, 128))
    return {
        "right": (n, ne, se, s) if e else None,
        "left": (n, nw, sw, s) if w else None,
        "bottom": (w, sw, se, e) if s else None,
        "top": (w, nw, ne, e) if n else None,
    }


def _corner_edges(bits: int) -> _Edges:
    tl, tr, br, bl = (bool(bits & b) for b in (_TL, _TR, _BR, _BL))
    return {"right": (tr, br), "left": (tl, bl), "bottom": (bl, br), "top": (tl, tr)}


def _tile_table(layout: str) -> list[tuple[tuple[int, int], _Edges]]:
    if layout == BLOB47:
        return [((i % 12, i // 12), _blob_edges(m)) for i, m in enumerate(a2.blob_masks())]
    return [((i % 4, i // 4), _corner_edges(i)) for i in range(16)]


def _proposal_entry(layout: str, index: int, set_name: str) -> dict[str, Any]:
    if layout == BLOB47:
        return {"terrain": a2.peering_for_mask(a2.blob_masks()[index], set_name)}
    peering = empty_peering()
    for key, bit in (
        ("top_left_corner", _TL),
        ("top_right_corner", _TR),
        ("bottom_right_corner", _BR),
        ("bottom_left_corner", _BL),
    ):
        if index & bit:
            peering[key] = 0
    return {"terrain": {"set": set_name, "terrain": 0, "peering": peering}}


# --------------------------------------------------------------------------- recognition


def _load(sheet: Image.Image) -> np.ndarray:
    arr = np.array(sheet.convert("RGBA"), dtype=np.int16)
    arr[arr[..., 3] == 0] = 0  # transparent pixels carry no color
    return arr


def _cut(pixels: np.ndarray, cell: tuple[int, int], cx: int, cy: int) -> np.ndarray:
    return pixels[cy * cell[1] : (cy + 1) * cell[1], cx * cell[0] : (cx + 1) * cell[0]]


def recognize(sheet: Image.Image, cell_w: int, cell_h: int | None = None) -> Recognition | None:
    """Try the known layouts on a sheet whose size is exactly cols x rows cells.

    Returns ``None`` when no layout has the right shape (nothing to judge); otherwise a
    ``Recognition`` whose ``accepted`` flag tells whether the 90% rule held.
    """
    cell_h = cell_h or cell_w
    if cell_w < 1 or cell_h < 1 or sheet.width % cell_w or sheet.height % cell_h:
        return None
    shape = (sheet.width // cell_w, sheet.height // cell_h)
    layout = next((name for name, s in LAYOUT_SHAPES.items() if s == shape), None)
    if layout is None:
        return None
    pixels = _load(sheet)
    table = _tile_table(layout)
    tiles = [_cut(pixels, (cell_w, cell_h), cx, cy) for (cx, cy), _e in table]
    filled = [bool(t[..., 3].any()) for t in tiles]
    distinct = sum(
        1 for i, t in enumerate(tiles) if not any(np.array_equal(t, o) for o in tiles[:i])
    )
    matched = expected = 0
    for i, (_c, ea) in enumerate(table):
        for j, (_d, eb) in enumerate(table):
            for side_a, side_b in (("right", "left"), ("bottom", "top")):
                da, db = ea[side_a], eb[side_b]
                if da is None or db is None or da != db:
                    continue
                expected += 1
                if side_a == "right":
                    diff = float(np.abs(tiles[i][:, -1] - tiles[j][:, 0]).mean())
                else:
                    diff = float(np.abs(tiles[i][-1, :] - tiles[j][0, :]).mean())
                if diff < MATCH_THRESHOLD:
                    matched += 1
    confidence = matched / expected if expected else 0.0
    n = len(table)
    accepted = (
        expected > 0
        and confidence >= ACCEPT_RATIO
        and sum(filled) >= MIN_FILLED * n
        and distinct >= MIN_DISTINCT * n
    )
    return Recognition(layout, round(confidence, 4), accepted, matched, expected)


def propose(
    sheet: Image.Image, cell_w: int, cell_h: int | None, set_name: str
) -> tuple[dict[str, Any] | None, Recognition | None]:
    """``(terrain_proposal facet or None, recognition)`` for one sheet.

    The facet holds the layout, confidence, the terrain set to create and the proposed
    ``tile_overrides``; ``None`` when the sheet was not accepted (callers report TILE-006).
    """
    result = recognize(sheet, cell_w, cell_h)
    if result is None or not result.accepted:
        return None, result
    cell_h = cell_h or cell_w
    pixels = _load(sheet)
    overrides: dict[str, Any] = {}
    for i, ((cx, cy), _edges) in enumerate(_tile_table(result.layout)):
        if not _cut(pixels, (cell_w, cell_h), cx, cy)[..., 3].any():
            continue  # an empty cell (e.g. the "no corners" tile) gets no terrain
        overrides[f"{cx},{cy}"] = _proposal_entry(result.layout, i, set_name)
    mode = "corners_and_sides" if result.layout == BLOB47 else "corners"
    set_def = a2.terrain_set_def(set_name, 0)
    set_def["mode"] = mode
    facet = {
        "layout": result.layout,
        "confidence": result.confidence,
        "mode": mode,
        "terrain_set": set_def,
        "tile_overrides": {k: overrides[k] for k in sorted(overrides)},
    }
    return facet, result


# --------------------------------------------------------------------------- accept / reject


def has_proposal(asset: catalog_mod.Asset) -> bool:
    return bool(catalog_mod.effective(asset).get("terrain_proposal"))


def _with_overrides(asset: catalog_mod.Asset, overrides: dict[str, Any]) -> catalog_mod.Asset:
    edited = dataclasses.replace(asset, overrides=overrides)
    return dataclasses.replace(
        edited, status=catalog_mod.recompute_status(edited, file_missing=asset.status == "MISSING")
    )


def accept_proposal(asset: catalog_mod.Asset) -> catalog_mod.Asset:
    """New asset whose overrides carry the proposed terrain tiles; the proposal is cleared.

    Existing per-tile overrides (collision, custom data) are kept; only ``terrain`` is replaced.
    """
    proposal = catalog_mod.effective(asset).get("terrain_proposal")
    if not proposal:
        return asset
    overrides = copy.deepcopy(asset.overrides)
    tile_overrides = overrides.setdefault("tile_overrides", {})
    for key, entry in proposal["tile_overrides"].items():
        tile_overrides[key] = catalog_mod.merge(tile_overrides.get(key, {}), entry)
    overrides["terrain_proposal"] = None
    return _with_overrides(asset, overrides)


def reject_proposal(asset: catalog_mod.Asset) -> catalog_mod.Asset:
    """New asset with the proposal hidden (it stays hidden when the packs are analyzed again)."""
    if not has_proposal(asset):
        return asset
    overrides = copy.deepcopy(asset.overrides)
    overrides["terrain_proposal"] = None
    return _with_overrides(asset, overrides)


def accept_in_catalog(catalog: catalog_mod.Catalog, asset_id: str) -> catalog_mod.Catalog:
    """Accept the proposal of an asset and add its terrain set to the asset's TileSetDef."""
    asset = catalog.asset(asset_id)
    if asset is None or not has_proposal(asset):
        return catalog
    proposal = catalog_mod.effective(asset)["terrain_proposal"]
    tilesets = copy.deepcopy(catalog.tilesets)
    for tdef in tilesets:
        if any(src["asset"] == asset_id for src in tdef.sources) and not any(
            t["name"] == proposal["terrain_set"]["name"] for t in tdef.terrain_sets
        ):
            tdef.terrain_sets.append(copy.deepcopy(proposal["terrain_set"]))
    assets = [accept_proposal(a) if a.id == asset_id else a for a in catalog.assets]
    return dataclasses.replace(catalog, assets=assets, tilesets=tilesets)


def reject_in_catalog(catalog: catalog_mod.Catalog, asset_id: str) -> catalog_mod.Catalog:
    asset = catalog.asset(asset_id)
    if asset is None or not has_proposal(asset):
        return catalog
    assets = [reject_proposal(a) if a.id == asset_id else a for a in catalog.assets]
    return dataclasses.replace(catalog, assets=assets)

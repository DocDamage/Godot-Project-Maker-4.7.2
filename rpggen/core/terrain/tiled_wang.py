"""Tiled Wang sets -> Godot terrain peering bits (T8.06a).

The Tiled adapter (T2.09) records ``{"set": name, "wangid": [8 ints]}`` per tile. The Godot
builder wants ``{"set", "terrain", "peering"}`` with the peering keys named after
``TileSet.CELL_NEIGHBOR_*``; this module converts between the two.
"""

from __future__ import annotations

import copy
from typing import Any

# Tiled wangid order: [top, top_right, right, bottom_right, bottom, bottom_left, left, top_left]
WANGID_KEYS = (
    "top_side",
    "top_right_corner",
    "right_side",
    "bottom_right_corner",
    "bottom_side",
    "bottom_left_corner",
    "left_side",
    "top_left_corner",
)
# Order of the peering dict in the catalog (matches the card's example).
PEERING_KEYS = (
    "right_side",
    "bottom_right_corner",
    "bottom_side",
    "bottom_left_corner",
    "left_side",
    "top_left_corner",
    "top_side",
    "top_right_corner",
)
SIDE_KEYS = frozenset(k for k in PEERING_KEYS if k.endswith("_side"))
CORNER_KEYS = frozenset(k for k in PEERING_KEYS if k.endswith("_corner"))
MODES = ("corners_and_sides", "corners", "sides")


def empty_peering() -> dict[str, int]:
    return {key: -1 for key in PEERING_KEYS}


def wangid_to_peering(wangid: list[int], mode: str) -> tuple[int, dict[str, int]]:
    """Convert a Tiled wangid to ``(center terrain, peering)``.

    Terrain = color - 1 (0 = no color -> -1). Only corner keys are filled for ``corners``, only
    side keys for ``sides``; the others stay -1. The center terrain is the most frequent
    non-negative peering value (ties -> the lowest value); -1 when there is none.
    """
    if mode not in MODES:
        raise ValueError(f"unknown terrain mode {mode!r}")
    if len(wangid) != 8:
        raise ValueError(f"a wangid has 8 values, got {len(wangid)}")
    peering = empty_peering()
    for key, color in zip(WANGID_KEYS, wangid, strict=True):
        if mode == "corners" and key in SIDE_KEYS:
            continue
        if mode == "sides" and key in CORNER_KEYS:
            continue
        peering[key] = int(color) - 1 if color > 0 else -1
    counts: dict[int, int] = {}
    for value in peering.values():
        if value >= 0:
            counts[value] = counts.get(value, 0) + 1
    center = min(counts, key=lambda v: (-counts[v], v)) if counts else -1
    return center, {key: peering[key] for key in PEERING_KEYS}


def apply_to_tile_overrides(
    tile_overrides: dict[str, Any], terrain_sets: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return a copy of ``tile_overrides`` with every ``terrain.wangid`` turned into peering.

    ``terrain_sets`` supply the mode of each set by name (default ``corners_and_sides``). Entries
    that already carry a ``peering`` (or have no ``wangid``) are kept as they are.
    """
    modes = {t["name"]: t.get("mode", "corners_and_sides") for t in terrain_sets}
    out = copy.deepcopy(tile_overrides)
    for entry in out.values():
        terrain = entry.get("terrain")
        if not isinstance(terrain, dict) or "wangid" not in terrain or "peering" in terrain:
            continue
        center, peering = wangid_to_peering(
            list(terrain["wangid"]), modes.get(terrain.get("set", ""), "corners_and_sides")
        )
        entry["terrain"] = {"set": terrain.get("set", ""), "terrain": center, "peering": peering}
    return out

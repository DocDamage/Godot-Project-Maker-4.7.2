"""Pieces the Tiled and LDtk readers share when they read maps (T12.49).

A reader returns a *raw map*: tile layers list their cells as ``[x, y, image, col, row, alt]``
(``image`` is the pack-relative path of the tile sheet), so the reader needs no tile set. The
catalog turns raw maps into catalog maps once the tile sets and their source ids exist.
"""

from __future__ import annotations

from typing import Any

# Tile transforms, in the bits Godot uses (see map_build.gd): flip x, flip y, transpose.
FLIP_H = 1
FLIP_V = 2
FLIP_D = 4

MARKER_KINDS = ("spawn", "door", "sign")
MAX_CELLS = 4_000_000


def marker_kind(*names: str) -> str | None:
    """``spawn``, ``door`` or ``sign`` when one of ``names`` says so (case does not matter)."""
    for name in names:
        folded = (name or "").strip().casefold()
        if folded in MARKER_KINDS:
            return folded
    return None


def num(value: Any) -> int | float:
    """An int for whole numbers, else a float rounded to 3 places."""
    f = float(value)
    return int(f) if f.is_integer() else round(f, 3)


def rle(items: list[tuple[Any, ...]]) -> list[list[Any]]:
    """Run-length encoding: ``[count, *item]`` for each run of equal items."""
    runs: list[list[Any]] = []
    for item in items:
        if runs and tuple(runs[-1][1:]) == item:
            runs[-1][0] += 1
        else:
            runs.append([1, *item])
    return runs


def unrle(runs: list[list[Any]]) -> list[tuple[Any, ...]]:
    """The inverse of ``rle``."""
    out: list[tuple[Any, ...]] = []
    for run in runs:
        out.extend([tuple(run[1:])] * int(run[0]))
    return out


def tile_layer(name: str, tiles: list[list[Any]]) -> dict[str, Any]:
    return {"name": name, "kind": "tiles", "tiles": tiles}


def intgrid_layer(
    name: str, size: tuple[int, int], data: list[int], values: list[dict[str, Any]]
) -> dict[str, Any]:
    return {"name": name, "kind": "intgrid", "size": list(size), "data": data, "values": values}


def objects_layer(name: str, objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "kind": "objects", "objects": objects}

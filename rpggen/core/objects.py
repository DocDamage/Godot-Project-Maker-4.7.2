"""Pure helpers for sheet objects (regions cut from a sheet): ids, defaults and snapping."""

from __future__ import annotations

import copy
from typing import Any

from rpggen import ids
from rpggen.core.adapters.generic_grid import GENERIC_CONSTANTS
from rpggen.core.catalog import SheetObject

Rect = tuple[int, int, int, int]  # x, y, w, h


def default_footprint(width: int, height: int) -> list[int]:
    """Bottom 30% of the region at full width (02_SCHEMAS §4.5)."""
    fh = max(1, round(height * GENERIC_CONSTANTS["FOOTPRINT_FRACTION"]))
    return [0, height - fh, width, fh]


def polygon_of(footprint: list[int]) -> list[list[int]]:
    x, y, w, h = footprint
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def custom_collision(footprint: list[int]) -> dict[str, Any]:
    return {"profile": "CUSTOM", "polygon": polygon_of(footprint)}


def unique_object_id(sheet_id: str, name: str, taken: set[str]) -> str:
    base = f"{sheet_id}#{ids.slug(name)}"
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        candidate = f"{base}__{n}"
    return candidate


def make_object(
    sheet_id: str,
    name: str,
    region: Rect,
    taken_ids: set[str],
    *,
    role: str = "DECORATION",
) -> SheetObject:
    """A user-made object with the default origin (bottom-center) and footprint."""
    x, y, w, h = region
    footprint = default_footprint(w, h)
    return SheetObject(
        id=unique_object_id(sheet_id, name, taken_ids),
        sheet=sheet_id,
        name=name,
        role=role,
        region=[x, y, w, h],
        origin=[w // 2, h - 1],
        footprint=footprint,
        collision=custom_collision(footprint),
        tags=[],
        status="CONFIRMED",
        source="user",
    )


def clamp_rect(rect: Rect, width: int, height: int) -> Rect:
    x, y, w, h = rect
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return x, y, w, h


def snap_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    grid: dict[str, list[int]] | None,
    size: tuple[int, int],
    *,
    snap: bool = True,
) -> Rect:
    """Rectangle of a drag from (x0, y0) to (x1, y1), snapped outward to grid cells.

    Without a grid, or with ``snap=False`` (Alt held), the rectangle is pixel exact.
    """
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    width, height = size
    if not snap or not grid or grid["cell"][0] < 1 or grid["cell"][1] < 1:
        rect = (int(left), int(top), int(right) - int(left) + 1, int(bottom) - int(top) + 1)
        return clamp_rect(rect, width, height)
    cw, ch = grid["cell"]
    mx, my = grid.get("margin", [0, 0])
    sx, sy = grid.get("separation", [0, 0])

    def span(lo: float, hi: float, c: int, m: int, s: int) -> tuple[int, int]:
        first = max(0, int((lo - m) // (c + s)))
        last = max(first, int((hi - m) // (c + s)))
        start = m + first * (c + s)
        end = m + last * (c + s) + c
        return start, end - start

    x, w = span(left, right, cw, mx, sx)
    y, h = span(top, bottom, ch, my, sy)
    return clamp_rect((x, y, w, h), width, height)


def clamp_inner(rect: Rect, region: list[int]) -> list[int]:
    """Keep an object-relative rectangle inside the object's region."""
    x, y, w, h = rect
    rw, rh = region[2], region[3]
    x = max(0, min(x, rw - 1))
    y = max(0, min(y, rh - 1))
    return [x, y, max(1, min(w, rw - x)), max(1, min(h, rh - y))]


def with_footprint(obj: SheetObject, footprint: list[int]) -> SheetObject:
    """Copy of ``obj`` with a new footprint; a CUSTOM collision follows it."""
    out = copy.deepcopy(obj)
    out.footprint = clamp_inner(tuple(footprint), obj.region)  # type: ignore[arg-type]
    if out.collision.get("profile") == "CUSTOM":
        out.collision = custom_collision(out.footprint)
    return out

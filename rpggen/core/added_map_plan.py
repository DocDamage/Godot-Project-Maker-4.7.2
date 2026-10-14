"""The added maps of a farm (T17.23): a forest and a beach beside the farm, each a map of its own.

A row of *Added maps* (``starter_map.added_maps``, ``{name, kind}``) is a map **planned here, on
a grid of cells like the farm** (``farm_plan.py``): whole numbers only, kinds and never tiles, so
the same plan is painted with squares or with diamonds. A plan is made once, from the farm's
seed and the map's index, and stored in the farm's own plan (``farm.map.added``, one entry a
map); a later row plans one more map and leaves the stored ones as they are.

* A **forest**: trees thick at the edge and scattered inside, a clearing with a path to it,
  bushes, rocks and flowers, branches, stumps and grass to clear, and places where things to
  forage lie.
* A **beach**: sand, the sea along one side (its cells carry the ``water`` data of the ``Soil``
  layer, so the rod is cast there), a place to fish from, driftwood and beach grass to clear,
  rocks, a few trees at the far side, and places where the things of a beach lie.
* A **cave** (T17.24): rock, chambers hollowed out of it and joined by tunnels to the way in,
  enemies in the chambers away from the way in, and places where the things of a cave lie
  (ore, a crystal, a mushroom of the dark). A cave is where a farm fights: a farm has one when
  the feature *Combat* is on (``with_cave``: the cave is added to the rows by itself, unless a
  row is a cave already), and a cave row without *Combat* is refused with a sentence.

**The door pair.** An added map has one way in: a gap in its edge (``door``), which leads back
to the farm. The farm's side is one of the farm's **trails** (``farm.map.trails``, reserved by
``farm_plan`` when the farm is planned, so that a map added later needs nothing of the farm
rebuilt): the entry's ``trail`` is the index of the one it uses.

``check`` is the farm's check for one of these maps: nothing lies on something else, the way in
is at the edge, and from it the farmer walks to every forage place, to the clearing, and to the
place the rod is cast from, which lies beside the sea. No Qt, no Godot.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from random import Random
from typing import Any

PLAN_VERSION = 1
FOREST = "forest"
BEACH = "beach"
CAVE = "cave"
# what a row may be, in the order a choice lists it; RESERVED are known and not built yet
BUILT = (FOREST, BEACH, CAVE)
RESERVED: tuple[str, ...] = ()
KNOWN = (*BUILT, *RESERVED)
DEFAULT_KIND = FOREST
# the words of a name that choose a kind, the first kind that has one of them
NAME_WORDS: dict[str, tuple[str, ...]] = {
    BEACH: ("beach", "shore", "coast", "seaside", "sea", "bay", "strand"),
    FOREST: ("forest", "wood", "woods", "grove"),
    CAVE: ("cave", "cavern", "caves", "mine", "mines", "grotto", "tunnel", "tunnels"),
}
SIZES: dict[str, tuple[int, int]] = {FOREST: (28, 22), BEACH: (30, 20), CAVE: (26, 20)}
# the name of the cave a farm gets with *Combat* on and no row of the kind (``with_cave``)
CAVE_NAME = "Cave"
MAP_DIR = "game/maps"
SEA = "sea"  # the water of a beach (forage_plan: the fish of the sea bite there)
REROLLS = 12
EDGES = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
INWARD = {"N": (0, 1), "E": (-1, 0), "S": (0, -1), "W": (1, 0)}
FACING_IN = {"N": "down", "E": "left", "S": "up", "W": "right"}
# what blocks the way (farm_plan.BLOCKING, and a tree)
BLOCKING = frozenset({"branch", "stump", "bush", "rock"})
FOREST_TREES = {1: 0.85, 2: 0.6, 3: 0.4}  # how likely a tree is, by the cells from the edge
FOREST_INSIDE = 0.2  # ... and further in
FOREST_SPOTS = 8
FOREST_DEBRIS = 12
FOREST_SCENERY = 10
BEACH_SPOTS = 6
BEACH_DEBRIS = 6
BEACH_SCENERY = 5
SEA_DEPTH = (3, 5)  # cells of sea from the edge, the edge's own row among them
SPOTS_APART = 3
CAVE_CHAMBERS = 3  # hollowed out of the rock away from the way in
CAVE_SPOTS = 6
CAVE_ENEMIES = 3
CAVE_BOULDERS = 3
ENEMY_AWAY = 6  # the cells (along the axes) an enemy stands at least from where the farmer arrives

Cell = tuple[int, int]
STEPS: tuple[Cell, ...] = ((0, 1), (1, 0), (-1, 0), (0, -1))
AROUND: tuple[Cell, ...] = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
_WORD = re.compile(r"[a-z]+")


class AddedMapError(ValueError):
    """A row that cannot be an added map; the message says why."""


# --------------------------------------------------------------------------- the rows


def kind_of_name(name: str) -> str:
    """The kind a name chooses when the row says none: "North beach" a beach, "Old woods" a
    forest, anything else a forest."""
    words = set(_WORD.findall(str(name).lower()))
    for kind, known in NAME_WORDS.items():
        if words & set(known):
            return kind
    return DEFAULT_KIND


def row(raw: Any) -> dict[str, str]:
    """A row of *Added maps* as the planner reads it: ``{name, kind}``, the kind from the name
    when the row has none. ``AddedMapError`` for a row without a name, of a kind nobody knows,
    or of a kind that is not built yet."""
    given = raw if isinstance(raw, dict) else {"name": raw}
    name = str(given.get("name", "") or "").strip()
    if not name:
        raise AddedMapError("an added map needs a name")
    kind = str(given.get("kind", "") or "").strip() or kind_of_name(name)
    if kind in RESERVED and kind not in PLANNERS:
        raise AddedMapError(f"{name}: an added map of the kind {kind} is not built yet")
    if kind not in PLANNERS:
        raise AddedMapError(f"{name}: an added map is one of {', '.join(BUILT)}, not {kind}")
    return {"name": name, "kind": kind}


class CaveNeedsCombat(AddedMapError):
    """A cave row in a farm without the feature *Combat*."""


def with_cave(rows: Any, combat: bool, stored: Any = None) -> list[Any]:
    """The rows of *Added maps* as a farm plans them (T17.24). With *Combat* on the farm has a
    cave: a row of the kind (by its ``kind``, else by its name) is that cave, and without one a
    row ``{"name": CAVE_NAME, "kind": "cave"}`` is added at the end. With *Combat* off a row of
    the kind is refused (``CaveNeedsCombat``): a cave is the place a farm fights in, and a farm
    that does not fight has none. ``stored`` are the entries the farm's plan has
    (``farm.map.added``): a row whose name is among them is not read again, whatever it says
    now, and a farm that has its cave gets no second one. A row that cannot be read is left as
    it is (the planner says what is wrong with it)."""
    given = list(rows) if isinstance(rows, list) else []
    have = {str(e.get("name", "")).casefold() for e in stored or [] if isinstance(e, dict)}
    has_one = any(isinstance(e, dict) and e.get("kind") == CAVE for e in stored or [])
    new: list[Any] = []
    for raw in given:
        named = str(raw.get("name", "") if isinstance(raw, dict) else raw).strip()
        if named.casefold() in have:
            continue
        try:
            if row(raw)["kind"] == CAVE:
                new.append(raw)
        except AddedMapError:
            continue
    if new and not combat:
        name = row(new[0])["name"]
        raise CaveNeedsCombat(
            f"{name}: a cave is where a farm fights; switch on the feature Combat to have one"
        )
    if combat and not new and not has_one:
        names = have | {
            str(r.get("name", "") if isinstance(r, dict) else r).strip().casefold() for r in given
        }
        name, n = CAVE_NAME, 2
        while name.casefold() in names:
            name, n = f"{CAVE_NAME} {n}", n + 1
        given.append({"name": name, "kind": CAVE})
    return given


def kinds_of(rows: Any) -> list[str]:
    """The kinds of the rows of an options table that can be read, in their order (a row that
    cannot is left out: the planner says what is wrong with it)."""
    out: list[str] = []
    for raw in rows if isinstance(rows, list) else []:
        try:
            out.append(row(raw)["kind"])
        except AddedMapError:
            continue
    return out


def fights(combat: Any, stored: Any = None) -> bool:
    """True when a farm fights (T17.24): the feature *Combat* is on, or its plan has a cave
    (``stored``: ``farm.map.added``), which is never taken away again."""
    return bool(combat) or has_cave(stored)


def kinds_for(rows: Any, combat: Any, stored: Any = None) -> list[str]:
    """``kinds_of`` the rows, with the cave of a farm that fights: what the kit draws for and
    the requirement check notes."""
    kinds = kinds_of(rows)
    if fights(combat, stored) and CAVE not in kinds:
        kinds.append(CAVE)
    return kinds


def map_id(index: int) -> str:
    """The id of the ``index``-th added map of a farm (from 1): the name of its scene. It is
    the number and not the name, so that no name can be the id of another map."""
    return f"farm_map_{int(index)}"


# --------------------------------------------------------------------------- cells


def _cell(value: Any) -> Cell:
    return int(value[0]), int(value[1])


def _lists(cells: Any) -> list[list[int]]:
    return [[c[0], c[1]] for c in cells]


def _beside(cell: Cell) -> list[Cell]:
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in STEPS]


def _rect_cells(rect: Any) -> list[Cell]:
    x0, y0, w, h = (int(v) for v in rect)
    return [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]


def _edge_cells(size: Cell) -> set[Cell]:
    cols, rows = size
    return {
        (x, y) for y in range(rows) for x in range(cols) if x in (0, cols - 1) or y in (0, rows - 1)
    }


def _from_edge(cell: Cell, size: Cell) -> int:
    return min(cell[0], cell[1], size[0] - 1 - cell[0], size[1] - 1 - cell[1])


def _door(edge: str, size: Cell, rng: Random) -> dict[str, Any]:
    """The way in: a gap in the edge, never near a corner, and the floor before it."""
    cols, rows = size
    along = rng.randint(5, (cols if edge in ("N", "S") else rows) - 6)
    gap = {"N": (along, 0), "S": (along, rows - 1), "E": (cols - 1, along), "W": (0, along)}[edge]
    spawn = (gap[0] + INWARD[edge][0], gap[1] + INWARD[edge][1])
    return {
        "edge": edge,
        "cell": list(gap),
        "spawn": list(spawn),
        "facing": FACING_IN[edge],
        "to": "farm",
    }


def _walk(start: Cell, goal: Cell, x_first: bool) -> list[Cell]:
    """The cells from ``start`` to ``goal``, both among them: along one axis, then the other."""
    out = [start]
    at = list(start)
    for axis in (0, 1) if x_first else (1, 0):
        while at[axis] != goal[axis]:
            at[axis] += 1 if goal[axis] > at[axis] else -1
            out.append((at[0], at[1]))
    return out


def _flood(start: Cell, size: Cell, blocked: set[Cell]) -> set[Cell]:
    cols, rows = size
    if start in blocked or not (0 <= start[0] < cols and 0 <= start[1] < rows):
        return set()
    seen = {start}
    todo = [start]
    while todo:
        for nxt in _beside(todo.pop()):
            inside = 0 <= nxt[0] < cols and 0 <= nxt[1] < rows
            if inside and nxt not in seen and nxt not in blocked:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _apart(cells: list[Cell], count: int, apart: int) -> list[Cell]:
    """``count`` of ``cells`` in their order, no two nearer than ``apart`` while that leaves
    enough of them."""
    chosen: list[Cell] = []
    for least in range(apart, 0, -1):
        for cell in cells:
            if len(chosen) >= count:
                break
            if cell not in chosen and all(
                abs(cell[0] - c[0]) + abs(cell[1] - c[1]) >= least for c in chosen
            ):
                chosen.append(cell)
    return chosen


class _Things:
    """What is scattered over a map: nothing lies on a kept cell or on another thing, and what
    blocks the way never touches another thing that does (so no wall grows)."""

    def __init__(self, rng: Random, keep: set[Cell], blockers: set[Cell]) -> None:
        self.rng = rng
        self.used = set(keep) | set(blockers)
        self.blockers = set(blockers)

    def scatter(
        self, spots: list[Cell], count: int, kinds: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        spots = list(spots)
        self.rng.shuffle(spots)
        for spot in spots:
            if len(out) >= count:
                break
            kind = self.rng.choice(kinds)
            lonely = all((spot[0] + dx, spot[1] + dy) not in self.blockers for dx, dy in AROUND)
            if spot in self.used or (kind in BLOCKING and not lonely):
                continue
            self.used.add(spot)
            if kind in BLOCKING:
                self.blockers.add(spot)
            out.append({"kind": kind, "cell": list(spot)})
        out.sort(key=lambda d: (d["cell"][1], d["cell"][0]))
        return out


def _entry(kind: str, index: int, name: str, size: Cell, facts: dict[str, Any]) -> dict[str, Any]:
    ident = map_id(index)
    return {
        "plan_version": PLAN_VERSION,
        "seed": 0,
        "index": int(index),
        "id": ident,
        "name": name,
        "kind": kind,
        "map": f"{MAP_DIR}/{ident}.tscn",
        "size": [size[0], size[1]],
        "ground": str((facts.get("grounds") or {}).get(kind, "")),
    }


# --------------------------------------------------------------------------- a forest


def _forest(index: int, name: str, facts: dict[str, Any], rng: Random) -> dict[str, Any] | None:
    size = SIZES[FOREST]
    cols, rows = size
    out = _entry(FOREST, index, name, size, facts)
    door = _door(rng.choice(EDGES), size, rng)
    spawn = _cell(door["spawn"])
    # the clearing, somewhere in the middle, and the path to it from the way in
    c_wide, c_high = rng.randint(6, 8), rng.randint(4, 6)
    cx = rng.randint(6, cols - 6 - c_wide)
    cy = rng.randint(5, rows - 5 - c_high)
    clearing = (cx, cy, c_wide, c_high)
    centre = (cx + c_wide // 2, cy + c_high // 2)
    path = _walk(spawn, centre, door["edge"] in ("E", "W"))  # into the wood first
    keep: set[Cell] = set(path) | set(_rect_cells(clearing)) | {_cell(door["cell"])}
    keep.update((spawn[0] + dx, spawn[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    trees: list[Cell] = []
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            chance = FOREST_TREES.get(_from_edge((x, y), size), FOREST_INSIDE)
            if rng.random() < chance and (x, y) not in keep:
                trees.append((x, y))
    walls = _edge_cells(size) - {_cell(door["cell"])}
    things = _Things(rng, set(path) | {spawn, _cell(door["cell"])}, walls | set(trees))
    open_cells = sorted(_flood(spawn, size, walls | set(trees)) - set(path) - {spawn})
    inside = [c for c in open_cells if c not in set(_rect_cells(clearing))]
    in_clearing = [c for c in _rect_cells(clearing) if c not in set(path)]
    scenery = things.scatter(in_clearing, 3, ("flowers",))
    scenery += things.scatter(inside, FOREST_SCENERY, ("bush", "rock", "flowers", "bush"))
    scenery.sort(key=lambda d: (d["cell"][1], d["cell"][0]))
    debris = things.scatter(inside, FOREST_DEBRIS, ("branch", "stump", "grass", "branch"))
    reached = _flood(spawn, size, walls | things.blockers)
    free = sorted(c for c in reached if c not in things.used and c != _cell(door["cell"]))
    rng.shuffle(free)
    spots = _apart(free, FOREST_SPOTS, SPOTS_APART)
    if len(spots) < FOREST_SPOTS // 2:
        return None
    out.update(
        {
            "door": door,
            "clearing": list(clearing),
            "paths": _lists(path),
            "trees": _lists(trees),
            "scenery": scenery,
            "debris": debris,
            "spots": _lists(sorted(spots, key=lambda c: (c[1], c[0]))),
            "notes": [],
        }
    )
    return out


# --------------------------------------------------------------------------- a beach


def _sea(side: str, size: Cell, rng: Random) -> list[Cell]:
    """The cells of the sea along one side, the edge's own cells among them: a shore that
    wanders by a cell at a time."""
    cols, rows = size
    length = cols if side in ("N", "S") else rows
    depth = rng.randint(*SEA_DEPTH)
    cells: list[Cell] = []
    for along in range(length):
        if along % 2 == 0:
            depth = max(SEA_DEPTH[0], min(SEA_DEPTH[1], depth + rng.choice((-1, 0, 0, 1))))
        for d in range(depth):
            cells.append(
                {
                    "N": (along, d),
                    "S": (along, rows - 1 - d),
                    "W": (d, along),
                    "E": (cols - 1 - d, along),
                }[side]
            )
    return cells


def _beach(index: int, name: str, facts: dict[str, Any], rng: Random) -> dict[str, Any] | None:
    size = SIZES[BEACH]
    cols, rows = size
    out = _entry(BEACH, index, name, size, facts)
    side = rng.choice(("S", "E", "W", "N"))
    sea = _sea(side, size, rng)
    wet = set(sea)
    # the way in is on the side away from the sea, or on one beside it away from the water
    edge = rng.choice(
        (OPPOSITE[side], OPPOSITE[side], *(e for e in EDGES if e not in (side, OPPOSITE[side])))
    )
    door = _door(edge, size, rng)
    for _ in range(8):
        near = {
            (door["cell"][0] + dx, door["cell"][1] + dy)
            for dx in range(-3, 4)
            for dy in range(-3, 4)
        }
        if not near & wet:
            break
        door = _door(OPPOSITE[side], size, rng)
    spawn = _cell(door["spawn"])
    walls = _edge_cells(size) - wet - {_cell(door["cell"])}
    keep: set[Cell] = {(spawn[0] + dx, spawn[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    keep.add(_cell(door["cell"]))
    # where the rod is cast from: sand beside the sea, as near the middle of the shore as it is
    land = _flood(spawn, size, walls | wet)
    shore = sorted(
        c for c in land if any(n in wet for n in _beside(c)) and _from_edge(c, size) >= 2
    )
    if not shore:
        return None
    middle = (cols // 2, rows // 2)
    stand = min(shore, key=lambda c: (abs(c[0] - middle[0]) + abs(c[1] - middle[1]), c))
    cast_at = next(n for n in _beside(stand) if n in wet)
    keep.add(stand)
    # a few trees on the side away from the sea, then what lies about
    trees: list[Cell] = []
    for cell in sorted(land):
        far = {
            "N": rows - 1 - cell[1],
            "S": cell[1],
            "W": cols - 1 - cell[0],
            "E": cell[0],
        }[side]
        if far <= 2 and cell not in keep and rng.random() < 0.3:
            trees.append(cell)
    things = _Things(rng, keep, walls | wet | set(trees))
    open_cells = sorted(_flood(spawn, size, walls | wet | set(trees)) - keep)
    scenery = things.scatter(open_cells, BEACH_SCENERY, ("rock", "rock", "bush"))
    debris = things.scatter(open_cells, BEACH_DEBRIS, ("branch", "grass", "grass"))
    reached = _flood(spawn, size, walls | wet | things.blockers)
    if stand not in reached:
        return None
    free = sorted(c for c in reached if c not in things.used and c != _cell(door["cell"]))
    rng.shuffle(free)
    # most of what a beach has lies near the water
    by_sea = [
        c
        for c in free
        if any((c[0] + dx, c[1] + dy) in wet for dx in range(-3, 4) for dy in range(-3, 4))
    ]
    spots = _apart(by_sea, BEACH_SPOTS - 2, SPOTS_APART)
    spots = _apart([*spots, *free], BEACH_SPOTS, SPOTS_APART)
    if len(spots) < BEACH_SPOTS // 2:
        return None
    out.update(
        {
            "door": door,
            "water": {"kind": SEA, "side": side, "cells": _lists(sea)},
            "fish": {"from": list(stand), "at": list(cast_at)},
            "paths": [],
            "trees": _lists(trees),
            "scenery": scenery,
            "debris": debris,
            "spots": _lists(sorted(spots, key=lambda c: (c[1], c[0]))),
            "notes": [],
        }
    )
    return out


# --------------------------------------------------------------------------- a cave


def _tunnel(cells: set[Cell], start: Cell, goal: Cell, x_first: bool) -> list[Cell]:
    """A tunnel two cells wide from ``start`` to ``goal`` (``_walk``, and the cell to the right
    of and below each step), added to ``cells``; returns its middle line."""
    line = _walk(start, goal, x_first)
    for x, y in line:
        cells.update({(x, y), (x + 1, y), (x, y + 1)})
    return line


def _apart_rects(rect: tuple[int, int, int, int], others: list[tuple[int, int, int, int]]) -> bool:
    """True when ``rect`` keeps a cell of rock to every rect of ``others``."""
    x0, y0, w, h = rect
    return all(
        x0 + w + 1 < ox or ox + ow + 1 < x0 or y0 + h + 1 < oy or oy + oh + 1 < y0
        for ox, oy, ow, oh in others
    )


def _cave(index: int, name: str, facts: dict[str, Any], rng: Random) -> dict[str, Any] | None:
    size = SIZES[CAVE]
    cols, rows = size
    out = _entry(CAVE, index, name, size, facts)
    door = _door(rng.choice(EDGES), size, rng)
    spawn = _cell(door["spawn"])
    gap = _cell(door["cell"])
    hollow: set[Cell] = {(spawn[0] + dx, spawn[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    # the chambers: rooms hollowed out of the rock, apart from one another and from the way in
    chambers: list[tuple[int, int, int, int]] = []
    for _ in range(60):
        if len(chambers) >= CAVE_CHAMBERS:
            break
        wide, high = rng.randint(5, 7), rng.randint(4, 5)
        rect = (rng.randint(2, cols - 2 - wide), rng.randint(2, rows - 2 - high), wide, high)
        middle = (rect[0] + wide // 2, rect[1] + high // 2)
        if abs(middle[0] - spawn[0]) + abs(middle[1] - spawn[1]) < ENEMY_AWAY + 2:
            continue
        if _apart_rects(rect, chambers):
            chambers.append(rect)
    if len(chambers) < 2:
        return None
    # the nearest first: a tunnel leads from the way in to the first and on from each to the next
    chambers.sort(
        key=lambda c: (abs(c[0] + c[2] // 2 - spawn[0]) + abs(c[1] + c[3] // 2 - spawn[1]), c)
    )
    paths: list[Cell] = []
    at = spawn
    for chamber in chambers:
        hollow.update(_rect_cells(chamber))
        middle = (chamber[0] + chamber[2] // 2, chamber[1] + chamber[3] // 2)
        paths += _tunnel(hollow, at, middle, rng.random() < 0.5)
        at = middle
    inside = {(x, y) for y in range(1, rows - 1) for x in range(1, cols - 1)}
    hollow &= inside
    walls = sorted(inside - hollow, key=lambda c: (c[1], c[0]))
    edge = _edge_cells(size) - {gap}
    keep = set(paths) | {spawn, gap}
    keep.update((spawn[0] + dx, spawn[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    things = _Things(rng, keep, edge | set(walls))
    in_chambers = sorted({c for ch in chambers for c in _rect_cells(ch)} - keep)
    # a few boulders where they block nothing (one that would touch the rock is not set down)
    scenery = things.scatter(in_chambers, CAVE_BOULDERS, ("rock",))
    reached = _flood(spawn, size, edge | set(walls) | things.blockers)
    free = [c for c in in_chambers if c in reached and c not in things.used]
    far = [c for c in free if abs(c[0] - spawn[0]) + abs(c[1] - spawn[1]) >= ENEMY_AWAY]
    rng.shuffle(far)
    enemies = _apart(far, CAVE_ENEMIES, SPOTS_APART)
    if not enemies:
        return None
    things.used.update(enemies)
    left = sorted(c for c in reached if c not in things.used and c not in keep)
    rng.shuffle(left)
    spots = _apart(left, CAVE_SPOTS, SPOTS_APART)
    if len(spots) < CAVE_SPOTS // 2:
        return None
    out.update(
        {
            "door": door,
            "chambers": [list(c) for c in chambers],
            "walls": _lists(walls),
            "enemies": [{"cell": list(c)} for c in sorted(enemies, key=lambda c: (c[1], c[0]))],
            "paths": _lists(dict.fromkeys(c for c in paths if c in inside)),
            "trees": [],
            "scenery": scenery,
            "debris": [],
            "spots": _lists(sorted(spots, key=lambda c: (c[1], c[0]))),
            "notes": [],
        }
    )
    return out


# What plans a kind: (the map's number from 1, its name, the facts of the packs, the dice) ->
# the entry, or None when this arrangement did not work out.
Planner = Callable[[int, str, dict[str, Any], Random], "dict[str, Any] | None"]
PLANNERS: dict[str, Planner] = {FOREST: _forest, BEACH: _beach, CAVE: _cave}


# --------------------------------------------------------------------------- the check


def water_cells(entry: dict[str, Any]) -> set[Cell]:
    return {_cell(c) for c in (entry.get("water") or {}).get("cells", [])}


def blocked_cells(entry: dict[str, Any]) -> set[Cell]:
    """The cells of an added map nobody walks on: its edge (but for the way in), the sea, the
    trees, and what of the scenery and of the things to clear stands in the way."""
    size = _cell(entry["size"])
    out = _edge_cells(size) - {_cell(entry["door"]["cell"])}
    out |= water_cells(entry)
    out.update(_cell(c) for c in entry.get("trees", []))
    out.update(_cell(c) for c in entry.get("walls", []))
    for thing in [*entry.get("scenery", []), *entry.get("debris", [])]:
        if thing["kind"] in BLOCKING:
            out.add(_cell(thing["cell"]))
    return out


def reached_cells(entry: dict[str, Any]) -> set[Cell]:
    """The cells the farmer can walk to from where he arrives."""
    return _flood(_cell(entry["door"]["spawn"]), _cell(entry["size"]), blocked_cells(entry))


def check(entry: dict[str, Any]) -> list[str]:
    """What keeps an added map from being used (an empty list: nothing). The way in is a cell
    of the edge with the floor before it; nothing lies on something else or outside the map;
    from the way in the farmer walks to every forage place and, on a beach, to the place the
    rod is cast from, which lies beside the sea."""
    problems: list[str] = []
    cols, rows = _cell(entry["size"])
    door = entry.get("door") or {}
    if not door:
        return ["there is no way in"]
    gap, spawn = _cell(door["cell"]), _cell(door["spawn"])
    if not (0 <= gap[0] < cols and 0 <= gap[1] < rows) or _from_edge(gap, (cols, rows)) != 0:
        problems.append(f"the way in is not at the edge: {list(gap)}")
    if spawn not in _beside(gap):
        problems.append("the farmer does not arrive before the way in")
    wet = water_cells(entry)
    claims: dict[Cell, str] = {}
    told: set[tuple[str, str]] = set()

    def claim(cells: Any, what: str, on: tuple[str, ...] = ()) -> None:
        for cell in (_cell(c) for c in cells):
            if not (0 <= cell[0] < cols and 0 <= cell[1] < rows):
                if (what, "") not in told:
                    told.add((what, ""))
                    problems.append(f"{what} is outside the map at {list(cell)}")
                continue
            other = claims.get(cell)
            if other is None or other in on:
                claims[cell] = what if other is None else other
            elif (what, other) not in told:
                told.add((what, other))
                problems.append(f"{what} overlaps {other} at {list(cell)}")

    claim(wet, "the sea")
    claim(_edge_cells((cols, rows)) - wet - {gap}, "the edge")
    claim([gap], "the way in")
    claim([spawn], "where the farmer arrives")
    claim(entry.get("paths", []), "a path", on=("where the farmer arrives",))
    claim(entry.get("trees", []), "a tree")
    claim(entry.get("walls", []), "the rock")
    for thing in entry.get("scenery", []):
        claim([thing["cell"]], f"scenery ({thing['kind']})")
    for thing in entry.get("debris", []):
        claim([thing["cell"]], f"a thing to clear ({thing['kind']})")
    claim(entry.get("spots", []), "a forage place")
    claim([e["cell"] for e in entry.get("enemies", [])], "an enemy")
    reached = reached_cells(entry)
    if not reached:
        return [*problems, "the way in is blocked"]
    for spot in entry.get("spots", []):
        if _cell(spot) not in reached:
            problems.append(f"the forage place {list(spot)} cannot be reached from the way in")
    if entry.get("clearing") and not set(_rect_cells(entry["clearing"])) & reached:
        problems.append("the clearing cannot be reached from the way in")
    if entry.get("kind") == CAVE:
        enemies = [_cell(e["cell"]) for e in entry.get("enemies", [])]
        if not enemies:
            problems.append("the cave has no enemy")
        for cell in enemies:
            if cell not in reached:
                problems.append(f"the enemy at {list(cell)} cannot be reached from the way in")
            elif abs(cell[0] - spawn[0]) + abs(cell[1] - spawn[1]) < ENEMY_AWAY:
                problems.append(f"the enemy at {list(cell)} stands at the way in")
    if entry.get("kind") == BEACH:
        fish = entry.get("fish") or {}
        if not wet:
            problems.append("the beach has no sea")
        elif not fish:
            problems.append("the beach has no place to fish from")
        elif _cell(fish["from"]) not in reached:
            problems.append("the place to fish from cannot be reached from the way in")
        elif _cell(fish["at"]) not in wet or _cell(fish["at"]) not in _beside(_cell(fish["from"])):
            problems.append("the place to fish from is not beside the sea")
    return problems


# --------------------------------------------------------------------------- the plan


def plan(kind: str, index: int, seed: int, name: str, facts: Any = None) -> dict[str, Any]:
    """The ``index``-th added map of a farm (from 1) of a kind: one entry of ``farm.map.added``.
    Deterministic for the seed and the index; an arrangement that fails its check is thrown
    again (``REROLLS`` times at most; the notes say so)."""
    if kind not in PLANNERS:
        raise AddedMapError(f"{name}: an added map of the kind {kind} is not built yet")
    known = dict(facts or {})
    found = ["the map has no room"]
    for attempt in range(REROLLS):
        rng = Random(f"farm_added:{int(seed)}:{int(index)}:{attempt}")
        out = PLANNERS[kind](int(index), str(name), known, rng)
        if out is None:
            continue
        found = check(out)
        if not found:
            out["seed"] = int(seed)
            if attempt:
                out["notes"].append(f"{name} was planned at the {attempt + 1}. try.")
            return out
    raise AddedMapError(f"{name}: no {kind} that can be walked: " + "; ".join(found[:3]))


def has_cave(entries: Any) -> bool:
    """True when one of the added maps is a cave (T17.24): the farm fights."""
    return any(str(entry.get("kind", "")) == CAVE for entry in entries or [])


def has_sea(entries: Any) -> bool:
    """True when one of the added maps has water the rod is cast into."""
    return any(water_cells(entry) for entry in entries or [])


def article(kind: str) -> str:
    return f"a {kind}"


def summary(entries: Any) -> str:
    """ "a forest (Old woods) and a beach (North shore)"; "" without added maps."""
    parts = [f"{article(str(e['kind']))} ({e['name']})" for e in entries or []]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]

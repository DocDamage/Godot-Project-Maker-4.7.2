"""The map of a farm (T17.06): where the house, the plot, the water, the bin and the animals are.

A farm's world is two maps or more: the village (the starter map of the top-down kinds, planned
by its own planner) and the **farm**, which is planned here. On a field of ``farm_size`` cells
stand the farmhouse with the shipping bin beside it, a plot of tillable ground, a pond or a well
to fill the can, a coop and a barn when the options have animals (each with a fenced yard and a
gate), branches, stumps and grass to clear, trees and scenery at the edges, and the way out to
the village. The farmer starts in the house, by the bed.

**The plan is a grid of cells and says kinds, never tiles and never a place on the screen**: a
cell is ``[x, y]`` with ``x`` to the east and ``y`` to the south, and the same plan is painted
with square tiles or with diamonds (T17.14).

``plan(options, seed, facts)`` is deterministic. Everything that stands on the field is laid out
as a block with a free cell round it, so the ground between the blocks is one piece; paths are
then led from the door of the house to the way out, the plot, the water and every gate, and
nothing is put on a path. ``check`` (``VAL-031``) floods the walkable cells from the door of the
house all the same, and a plan that fails is planned again with the next seed (the notes say so).
The plan is **stored** in the project (``rpggen/world_plan.json``, ``farm.map``, beside the crops
of ``crop_plan.py``) and reused: once the farm's map exists, the seed and the options no longer
change it. *Added maps* (T17.23) are maps of their own beside the farm, planned by
``added_map_plan.py`` and kept here as ``added`` (one entry a map; ``added_maps`` are their
names): a row that is new plans one more map and nothing that is stored changes. Each is joined
to the farm by a door pair whose farm side is one of the **trails** (``trails``): places beside
the edge of the farm that are set aside when the farm is planned, whether or not it has added
maps, so that a map added later needs nothing of the farm built again. No Qt, no Godot.
"""

from __future__ import annotations

import copy
from random import Random
from typing import Any

from rpggen.core import added_map_plan

PLAN_VERSION = 1
KIND = "farm"
MAP_ID = "farm"
MAP_FILE = "game/maps/farm.tscn"
VILLAGE_ID = "starter_map"  # world_plan.VILLAGE_ID: where the way out leads
SIZES = {"small": (32, 24), "medium": (40, 30), "large": (48, 36)}  # cells of the field
PLOTS = {"small": (6, 4), "medium": (12, 8), "large": (16, 10)}  # cells of the plot
ANIMALS: dict[str, tuple[str, ...]] = {
    "none": (),
    "coop": ("coop",),
    "coop_and_barn": ("coop", "barn"),
}
DIFFICULTIES = ("easy", "normal", "hard")
MIN_PLOT = 12
MAX_ADDED = 8
TRAILS = MAX_ADDED  # the places set aside for the doors to added maps
TRAILS_APART = 6  # cells between two of them, and between one and the way out
REROLLS = 12
LAYOUTS = 8  # how often one seed lays the field out before the plot is made smaller
MARGIN = 2  # cells between the edge of the field and what stands on it

# What a building is when the packs say nothing of it: (cells wide, cells high, the column of
# its door). The door is in the bottom row of the picture; the cell before it is ``door``.
BUILDINGS = {"house": (6, 4, 2), "coop": (4, 3, 1), "barn": (6, 4, 2)}
BUILDING_RANGE = ((2, 10), (2, 8))  # what a pack's building is cut to: wide, high
YARD_DEPTH = {"coop": 3, "barn": 4}  # cells of yard before an animal house
STALLS = {"coop": 4, "barn": 4}  # how many animals a house has room for
INTERIORS = {"house": (8, 7), "coop": (8, 6), "barn": (10, 7)}  # the least a room is
EXIT_EDGES = ("E", "S", "W")  # the house stands in the north
FACING_IN = {"N": "down", "E": "left", "S": "up", "W": "right"}
INWARD = {"N": (0, 1), "E": (-1, 0), "S": (0, -1), "W": (1, 0)}

DEBRIS = ("branch", "stump", "grass")
SCENERY = ("bush", "rock", "flowers")
# what the farmer cannot walk through: grass and flowers are walked over
BLOCKING = frozenset({"branch", "stump", "bush", "rock"})
DEBRIS_ON_PLOT = {"easy": 0.10, "normal": 0.18, "hard": 0.28}  # of the cells of the plot
TREES = {1: 0.55, 2: 0.30, 3: 0.10}  # how likely a tree is, by the cells from the edge

Cell = tuple[int, int]
STEPS: tuple[Cell, ...] = ((0, 1), (1, 0), (-1, 0), (0, -1))
AROUND: tuple[Cell, ...] = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)


class FarmPlanError(ValueError):
    """The options cannot make a farm; the message names the key."""


# --------------------------------------------------------------------------- the options


def defaults() -> dict[str, Any]:
    """The farm's own options (keys of ``config.starter_map`` beside the village's)."""
    return {
        "farm_size": "medium",
        "plot": "medium",
        "animals": "none",
        "difficulty": "normal",
        "added_maps": [],
    }


def normalized(options: Any) -> dict[str, Any]:
    """The options the planner reads, with the defaults filled in, or a ``FarmPlanError`` naming
    what is wrong. The section holds the village's options too: keys that are not the farm's are
    not looked at."""
    out = defaults()
    given = options if isinstance(options, dict) else {}
    out.update({key: given[key] for key in out if key in given})
    for key, allowed in (
        ("farm_size", tuple(SIZES)),
        ("plot", tuple(PLOTS)),
        ("animals", tuple(ANIMALS)),
        ("difficulty", DIFFICULTIES),
    ):
        if out[key] not in allowed:
            raise FarmPlanError(f"{key} must be one of {', '.join(allowed)}")
    rows = out["added_maps"]
    if not isinstance(rows, list) or len(rows) > MAX_ADDED:
        raise FarmPlanError(f"added_maps must be a list of at most {MAX_ADDED} maps")
    clean: list[dict[str, str]] = []
    for raw in rows:
        try:
            row = added_map_plan.row(raw)
        except added_map_plan.AddedMapError as exc:
            raise FarmPlanError(str(exc)) from None
        if row["name"].casefold() in {r["name"].casefold() for r in clean}:
            raise FarmPlanError(f"two added maps are called {row['name']}")
        clean.append(row)
    out["added_maps"] = clean
    return out


def facts_of(
    house: Any = None, water: bool = True, coop: Any = None, barn: Any = None, grounds: Any = None
) -> Any:
    """What the planner needs to know of the packs: the footprint of the building that is the
    farmhouse (``map_preview.building_info_for``: ``{"size": [w, h], "door": [dx, dy]}`` in
    cells, or nothing), of a coop and a barn when the packs have their own, whether the packs
    have water tiles (a pond) or not (a well), and the ground tile they have for a kind of
    added map (``grounds``: ``{"beach": the id of a sand tile}``; a kind without one is drawn)."""
    out: dict[str, Any] = {"water": bool(water)}
    if grounds:
        out["grounds"] = {str(k): str(v) for k, v in sorted(dict(grounds).items()) if v}
    for key, value in (("house", house), ("coop", coop), ("barn", barn)):
        if value:
            out[key] = {"size": list(value["size"]), "door": list(value["door"])}
    return out


def _footprint(kind: str, facts: dict[str, Any]) -> tuple[int, int, int]:
    """(cells wide, cells high, the column of the door) of a building."""
    wide, high, door = BUILDINGS[kind]
    given = facts.get(kind) or (facts.get("building") if kind == "house" else None)
    if isinstance(given, dict) and given.get("size"):
        (w_lo, w_hi), (h_lo, h_hi) = BUILDING_RANGE
        wide = max(w_lo, min(w_hi, int(given["size"][0])))
        high = max(h_lo, min(h_hi, int(given["size"][1])))
        door = int((given.get("door") or [wide // 2])[0])
    return wide, high, max(0, min(wide - 1, door))


# --------------------------------------------------------------------------- cells


def _rect_cells(rect: Any) -> list[Cell]:
    x0, y0, w, h = (int(v) for v in rect)
    return [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]


def _cell(value: Any) -> Cell:
    return int(value[0]), int(value[1])


def _lists(cells: Any) -> list[list[int]]:
    return [[c[0], c[1]] for c in cells]


def _beside(cell: Cell) -> list[Cell]:
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in STEPS]


def _candidates(taken: list[list[int]], wide: int, high: int) -> list[Cell]:
    """Every top left cell at which a block of ``wide`` by ``high`` stands ``MARGIN`` cells
    inside the field with a free cell all round it."""
    rows, cols = len(taken), len(taken[0])
    total = [[0] * (cols + 1) for _ in range(rows + 1)]
    for y in range(rows):
        run = 0
        for x in range(cols):
            run += taken[y][x]
            total[y + 1][x + 1] = total[y][x + 1] + run
    out: list[Cell] = []
    for y in range(MARGIN, rows - MARGIN - high + 1):
        for x in range(MARGIN, cols - MARGIN - wide + 1):
            x0, y0, x1, y1 = x - 1, y - 1, x + wide + 1, y + high + 1
            if total[y1][x1] - total[y0][x1] - total[y1][x0] + total[y0][x0] == 0:
                out.append((x, y))
    return out


def _route(sources: list[Cell], goals: set[Cell], closed: set[Cell], size: Cell) -> list[Cell]:
    """The shortest way from one of ``sources`` to one of ``goals`` over the cells inside the
    edge that are not ``closed``: its cells after the source, or nothing when there is none."""
    came: dict[Cell, Cell | None] = {s: None for s in sources}
    todo = list(sources)
    at = 0
    while at < len(todo):
        here = todo[at]
        at += 1
        if here in goals:
            way: list[Cell] = []
            back: Cell | None = here
            while back is not None and came[back] is not None:
                way.append(back)
                back = came[back]
            return way[::-1]
        for nxt in _beside(here):
            inside = 1 <= nxt[0] <= size[0] - 2 and 1 <= nxt[1] <= size[1] - 2
            if inside and nxt not in came and nxt not in closed:
                came[nxt] = here
                todo.append(nxt)
    return []


# --------------------------------------------------------------------------- the rooms


def _interior(kind: str, building_id: str, wide: int, door: int) -> dict[str, Any]:
    """The room inside a building: its walls are the outermost cells, its way out is a cell of
    the bottom wall. The house has the bed (its head at ``cell``; since T17.26 a bed for two,
    ``sleepers`` 2: two cells wide and two long, where a plan from before has one cell wide) and
    the cell the farmer starts on; an animal house has a trough and a place for every animal."""
    least_w, high = INTERIORS[kind]
    width = max(least_w, wide + 2)
    column = max(1, min(width - 2, door + 1))
    room: dict[str, Any] = {
        "id": building_id,
        "size": [width, high],
        "door": [column, high - 1],
        "arrive": [column, high - 2],
    }
    if kind == "house":
        # a bed for two (T17.26): two beds side by side, planned whether or not anybody marries,
        # since a room that exists is never built again
        room["bed"] = {"cell": [1, 1], "size": [2, 2], "sleepers": 2}
        room["start"] = [3, 2]
    else:
        room["trough"] = [1, 1]
        room["stalls"] = [[3 + i, 1] for i in range(STALLS[kind])]
    return room


# --------------------------------------------------------------------------- one layout


def _smaller(plot: Cell) -> Cell | None:
    """The next smaller plot to try, or None when it would have fewer than twelve cells."""
    wide, high = plot
    for nxt in ((wide - 2, high), (wide, high - 1), (wide - 1, high)):
        if nxt[0] >= 3 and nxt[1] >= 3 and nxt[0] * nxt[1] >= MIN_PLOT and nxt[0] >= nxt[1]:
            return nxt
    return None


def _lay_out(
    opts: dict[str, Any], plot: Cell, facts: dict[str, Any], rng: Random
) -> dict[str, Any] | None:
    """One farm, or None when this arrangement has no room for something."""
    cols, rows = SIZES[opts["farm_size"]]
    scale = tuple(SIZES).index(opts["farm_size"])
    hard = DIFFICULTIES.index(opts["difficulty"])
    taken = [[0] * cols for _ in range(rows)]

    def take(x0: int, y0: int, wide: int = 1, high: int = 1) -> None:
        for y in range(y0, y0 + high):
            for x in range(x0, x0 + wide):
                taken[y][x] = 1

    # the house in the north, the bin at one of its sides, the cells before its door kept free
    h_wide, h_high, h_door = _footprint("house", facts)
    places = list(range(MARGIN + 1, cols - MARGIN - h_wide))
    if not places or MARGIN + 1 + h_high + 3 > rows - MARGIN:
        return None
    hx, hy = rng.choice(places), MARGIN + rng.randint(0, 1)
    bin_cell = (hx - 1 if rng.random() < 0.5 else hx + h_wide, hy + h_high - 1)
    door = (hx + h_door, hy + h_high)
    take(hx, hy, h_wide, h_high)
    take(*bin_cell)
    take(bin_cell[0], bin_cell[1] + 1)
    take(door[0], door[1], 1, 3)
    house: dict[str, Any] = {
        "id": "farm_house",
        "kind": "house",
        "rect": [hx, hy, h_wide, h_high],
        "door": list(door),
        "interior": _interior("house", "farm_house", h_wide, h_door),
    }

    # the plot, near the door
    found = _candidates(taken, plot[0], plot[1])
    if not found:
        return None
    found.sort(
        key=lambda c: (abs(c[0] + plot[0] // 2 - door[0]) + abs(c[1] + plot[1] // 2 - door[1]), c)
    )
    px, py = rng.choice(found[: max(1, len(found) // 3)])
    take(px, py, plot[0], plot[1])
    tillable = _rect_cells((px, py, plot[0], plot[1]))

    # the animal houses, the larger first: the building, and before it a yard with a fence
    animal_houses: dict[str, dict[str, Any]] = {}
    for kind in sorted(ANIMALS[opts["animals"]], key=lambda k: -BUILDINGS[k][0]):
        b_wide, b_high, b_door = _footprint(kind, facts)
        depth = YARD_DEPTH[kind]
        found = _candidates(taken, b_wide + 4, b_high + depth + 1)
        if not found:
            return None
        cx, cy = rng.choice(found)
        take(cx, cy, b_wide + 4, b_high + depth + 1)
        bx, by = cx + 2, cy
        yard = (bx - 1, by + b_high, b_wide + 2, depth)  # the ground inside the fence
        built = set(_rect_cells((bx, by, b_wide, b_high)))
        outer = (yard[0] - 1, yard[1] - 1, yard[2] + 2, yard[3] + 2)
        fence = [
            c
            for c in _rect_cells(outer)
            if c not in built
            and (
                c[0] in (outer[0], outer[0] + outer[2] - 1)
                or c[1] in (outer[1], outer[1] + outer[3] - 1)
            )
        ]
        side = rng.choice(("S", "E", "W"))
        if side == "S":
            gate = (rng.randint(yard[0], yard[0] + yard[2] - 1), yard[1] + yard[3])
        else:
            gate = (
                outer[0] if side == "W" else outer[0] + outer[2] - 1,
                rng.randint(yard[1], yard[1] + yard[3] - 1),
            )
        fence.remove(gate)
        animal_houses[kind] = {
            "id": f"farm_{kind}",
            "kind": kind,
            "rect": [bx, by, b_wide, b_high],
            "door": [bx + b_door, by + b_high],
            "interior": _interior(kind, f"farm_{kind}", b_wide, b_door),
            "yard": {
                "rect": list(yard),
                "fence": _lists(fence),
                "gate": list(gate),
                "side": side,
            },
        }

    # the water: a pond when the packs have water, else a well; the can is filled south of it
    if facts.get("water", True):
        w_wide, w_high = rng.randint(3, 4 + scale), rng.randint(2, 3 + min(scale, 1))
    else:
        w_wide, w_high = 1, 1
    found = _candidates(taken, w_wide, w_high)
    if not found:
        return None
    wx, wy = rng.choice(found)
    take(wx, wy, w_wide, w_high)
    water = _rect_cells((wx, wy, w_wide, w_high))
    if w_wide >= 4 and w_high >= 3:  # a pond is no rectangle: some of its corners are land
        for corner in ((wx, wy), (wx + w_wide - 1, wy), (wx, wy + w_high - 1)):
            if rng.random() < 0.6:
                water.remove(corner)
    fill = (wx + w_wide - 1 - (w_wide - 1) // 2, wy + w_high)

    # the way out: a gap in the edge, never in a corner
    edge = rng.choice(EXIT_EDGES)
    along = rng.randint(3, (cols if edge == "S" else rows) - 4)
    gap = {"S": (along, rows - 1), "E": (cols - 1, along), "W": (0, along)}[edge]
    arrive = (gap[0] + INWARD[edge][0], gap[1] + INWARD[edge][1])

    # paths from the door: to the way out, the plot, the water and every gate. A path does not
    # cross the plot or a yard.
    solid: set[Cell] = set(_rect_cells(house["rect"])) | {bin_cell} | set(water)
    closed = set(solid) | set(tillable)
    gates: list[Cell] = []
    for animal_house in animal_houses.values():
        yard_plan = animal_house["yard"]
        fenced = {_cell(c) for c in yard_plan["fence"]}
        solid |= set(_rect_cells(animal_house["rect"])) | fenced
        closed |= set(_rect_cells(animal_house["rect"])) | fenced
        closed |= set(_rect_cells(yard_plan["rect"])) | {_cell(yard_plan["gate"])}
        step = {"S": (0, 1), "E": (1, 0), "W": (-1, 0)}[yard_plan["side"]]
        gates.append((yard_plan["gate"][0] + step[0], yard_plan["gate"][1] + step[1]))
    paths: list[Cell] = [door]
    goals: list[set[Cell]] = [{arrive}, {n for c in tillable for n in _beside(c)}, {fill}]
    goals += [{g} for g in gates]
    for goal in goals:
        way = _route(list(paths), goal - closed, closed, (cols, rows))
        if not way and not goal & set(paths):
            return None
        paths += [c for c in way if c not in paths]
    paths.append(gap)

    # what nothing is put on: the paths, every block and the cells round it
    keep: set[Cell] = set(paths)
    for y in range(rows):
        for x in range(cols):
            if taken[y][x]:
                keep.update((x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    blockers: set[Cell] = set()  # what was put down and cannot be walked through
    used: set[Cell] = set()

    def lonely(cell: Cell) -> bool:
        """No other blocker touches it, so blockers never join to a wall."""
        return all((cell[0] + dx, cell[1] + dy) not in blockers for dx, dy in AROUND)

    trees: list[Cell] = []
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            from_edge = min(x, y, cols - 1 - x, rows - 1 - y)
            chance = TREES.get(from_edge, 0.0) if from_edge < 3 or scale == 2 else 0.0
            if rng.random() < chance and (x, y) not in keep:
                trees.append((x, y))
    blockers.update(trees)
    used.update(trees)

    free = [
        (x, y)
        for y in range(1, rows - 1)
        for x in range(1, cols - 1)
        if (x, y) not in keep and (x, y) not in used
    ]

    def scatter(spots: list[Cell], count: int, kinds: tuple[str, ...]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        rng.shuffle(spots)
        for spot in spots:
            if len(out) >= count:
                break
            kind = rng.choice(kinds)
            if spot in used or (kind in BLOCKING and not lonely(spot)):
                continue
            used.add(spot)
            if kind in BLOCKING:
                blockers.add(spot)
            out.append({"kind": kind, "cell": list(spot)})
        return out

    at_edge = [c for c in free if min(c[0], c[1], cols - 1 - c[0], rows - 1 - c[1]) <= 5]
    scenery = scatter(at_edge, (cols + rows) // 8 + 2 * scale, SCENERY)
    # more to clear on a larger field and a harder game; grass twice as often as wood
    litter = (*DEBRIS, "grass")
    on_plot = [c for c in tillable if c not in paths]
    debris = scatter(on_plot, round(len(tillable) * DEBRIS_ON_PLOT[opts["difficulty"]]), litter)
    near = [
        c for c in free if px - 5 <= c[0] < px + plot[0] + 5 and py - 5 <= c[1] < py + plot[1] + 5
    ]
    debris += scatter(near, 4 + 4 * scale + 3 * hard, litter)
    debris.sort(key=lambda d: (d["cell"][1], d["cell"][0]))
    scenery.sort(key=lambda d: (d["cell"][1], d["cell"][0]))

    return {
        "plan_version": PLAN_VERSION,
        "seed": 0,
        "id": MAP_ID,
        "map": MAP_FILE,
        "farm_size": opts["farm_size"],
        "plot": opts["plot"],
        "animals": opts["animals"],
        "difficulty": opts["difficulty"],
        "size": [cols, rows],
        "house": house,
        "bin": {"cell": list(bin_cell), "front": [bin_cell[0], bin_cell[1] + 1]},
        "tillable": _lists(tillable),
        "water": {
            "kind": "pond" if len(water) > 1 else "well",
            "cells": _lists(water),
            "fill": list(fill),
        },
        "animal_houses": [animal_houses[kind] for kind in ANIMALS[opts["animals"]]],
        "paths": _lists(paths),
        "debris": debris,
        "trees": _lists(trees),
        "scenery": scenery,
        "exit": {
            "edge": edge,
            "cell": list(gap),
            "spawn": list(arrive),
            "facing": FACING_IN[edge],
            "to": VILLAGE_ID,
        },
        "start": {"map": house["id"], "cell": list(house["interior"]["start"]), "facing": "down"},
        "added_maps": [],
        "notes": [],
    }


def _farm(opts: dict[str, Any], seed: int, facts: dict[str, Any]) -> dict[str, Any] | None:
    """The farm of a seed: laid out again while something has no room, with a smaller plot when
    the field cannot hold the one that was asked for, and on the next larger field when the
    buildings of the packs leave no room for a plot at all."""
    rng = Random(f"{KIND}:{int(seed)}")
    wanted = PLOTS[opts["plot"]]
    sizes = tuple(SIZES)
    for size in sizes[sizes.index(opts["farm_size"]) :]:
        plot: Cell | None = wanted
        while plot is not None:
            for _ in range(LAYOUTS):
                out = _lay_out({**opts, "farm_size": size}, plot, facts, rng)
                if out is None:
                    continue
                if size != opts["farm_size"]:
                    out["notes"].append(
                        f"The field is {size}: a {opts['farm_size']} one has no room for the "
                        "buildings of the packs."
                    )
                if plot != wanted:
                    out["notes"].append(
                        f"The plot is {plot[0]} x {plot[1]}: the field has no room for "
                        f"{wanted[0]} x {wanted[1]} beside what else stands on it."
                    )
                return out
            plot = _smaller(plot)
    return None


# --------------------------------------------------------------------------- the trails


def _trail_cells(section: dict[str, Any]) -> set[Cell]:
    """The cells of the trails of a farm: where each door lies and where the farmer arrives."""
    return {_cell(t[key]) for t in section.get("trails", []) for key in ("cell", "spawn")}


def _before(cell: Cell) -> set[Cell]:
    """The cells before a cell as the game shows it: what stands on one of them is drawn over
    the cell, seen from above (the two rows south of it) and on diamonds (east of it too)."""
    x, y = cell
    return {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (1, 2)} | {(x + 1, y)}


def _trails(section: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """The places set aside for the doors to added maps (T17.23): ``TRAILS`` of them at most,
    each the cell beside the edge where a door lies (``cell``) and the cell one further in where
    the farmer arrives (``spawn``). Both can be walked to from the house, and nothing of the
    plan lies on them, stands beside a door of a building, or is a place where a thing to forage
    lies (``forage_plan.spots_for``, which reads this map with the same seed). They are chosen
    after everything else and with dice of their own, so the farm is the farm it was without
    them; and they are chosen once, whether or not a map is added, so that a map added later
    finds its place without anything of the farm being built again. They are taken in an order
    of the seed's, the ones that no tree hides first (``_before``)."""
    from rpggen.core import forage_plan

    cols, rows = (int(v) for v in section["size"])
    reached = reached_cells(section)
    taken: set[Cell] = {_cell(c) for c in section.get("paths", [])}
    taken.update(_cell(c) for c in section["tillable"])
    taken.update(
        _cell(t["cell"]) for t in [*section.get("scenery", []), *section.get("debris", [])]
    )
    taken.update(_cell(c) for c in forage_plan.spots_for(section, seed))
    for building in [section["house"], *section.get("animal_houses", [])]:
        door = _cell(building["door"])
        taken.update((door[0] + dx, door[1] + dy) for dx in (-1, 0, 1) for dy in (0, 1))
        yard = building.get("yard") or {}
        if yard.get("rect"):
            taken.update(_rect_cells(yard["rect"]))
        if yard.get("gate"):
            taken.add(_cell(yard["gate"]))
    taken.update(_cell(section["bin"][key]) for key in ("cell", "front"))
    if section["water"].get("fill"):
        taken.add(_cell(section["water"]["fill"]))
    for cell in (_cell(c) for c in section["water"]["cells"]):
        taken.update(_beside(cell))
    way_out = section.get("exit") or {}
    gap = _cell(way_out["cell"]) if way_out else None
    found: list[dict[str, Any]] = []
    for edge in ("N", "E", "S", "W"):
        for along in range(4, (cols if edge in ("N", "S") else rows) - 4):
            wall = {
                "N": (along, 0),
                "S": (along, rows - 1),
                "E": (cols - 1, along),
                "W": (0, along),
            }[edge]
            step = INWARD[edge]
            door = (wall[0] + step[0], wall[1] + step[1])
            spawn = (door[0] + step[0], door[1] + step[1])
            if not {door, spawn} <= reached or {door, spawn} & taken:
                continue
            if gap is not None and abs(wall[0] - gap[0]) + abs(wall[1] - gap[1]) < TRAILS_APART:
                continue
            found.append(
                {"edge": edge, "cell": list(door), "spawn": list(spawn), "facing": FACING_IN[edge]}
            )
    Random(f"{KIND}:trails:{int(seed)}").shuffle(found)
    # a trail is a mark on the ground: the ones no tree stands before come first, so that the
    # first maps a farm adds have a door that is seen (a tree's crown hangs over the cells behind
    # its trunk, in both views)
    trees = {_cell(c) for c in section.get("trees", [])}
    found.sort(key=lambda trail: bool(_before(_cell(trail["cell"])) & trees))
    chosen: list[dict[str, Any]] = []
    for trail in found:
        if len(chosen) >= TRAILS:
            break
        here = _cell(trail["cell"])
        if all(
            abs(here[0] - t["cell"][0]) + abs(here[1] - t["cell"][1]) >= TRAILS_APART
            for t in chosen
        ):
            chosen.append(trail)
    return chosen


# --------------------------------------------------------------------------- the check


def blocked_cells(section: dict[str, Any]) -> set[Cell]:
    """The cells of a farm nobody walks on: its edge (but for the way out), its buildings, the
    bin, the water, the fences (a gate is none), the trees, and what of the scenery and of the
    things to clear stands in the way (a bush, a rock, a branch, a stump)."""
    cols, rows = (int(v) for v in section["size"])
    way_out = _cell(section["exit"]["cell"]) if section.get("exit") else None
    out = {
        (x, y)
        for y in range(rows)
        for x in range(cols)
        if (x in (0, cols - 1) or y in (0, rows - 1)) and (x, y) != way_out
    }
    for building in [section["house"], *section.get("animal_houses", [])]:
        out.update(_rect_cells(building["rect"]))
        out.update(_cell(c) for c in (building.get("yard") or {}).get("fence", []))
    out.add(_cell(section["bin"]["cell"]))
    out.update(_cell(c) for c in section["water"]["cells"])
    out.update(_cell(c) for c in section.get("trees", []))
    for thing in [*section.get("scenery", []), *section.get("debris", [])]:
        if thing["kind"] in BLOCKING:
            out.add(_cell(thing["cell"]))
    return out


def reached_cells(section: dict[str, Any]) -> set[Cell]:
    """The cells the farmer can walk to from the door of the house (to the four sides)."""
    cols, rows = (int(v) for v in section["size"])
    blocked = blocked_cells(section)
    start = _cell(section["house"]["door"])
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


def _overlaps(section: dict[str, Any]) -> list[str]:
    """Two things on one cell, or a thing outside the field. Only a thing to clear may lie on
    the plot, only a door on a yard, and a path may begin at a door and end at the way out."""
    cols, rows = (int(v) for v in section["size"])
    problems: list[str] = []
    told: set[tuple[str, str]] = set()
    claims: dict[Cell, str] = {}

    def claim(cells: Any, what: str, on: tuple[str, ...] = ()) -> None:
        for cell in (_cell(c) for c in cells):
            if not (0 <= cell[0] < cols and 0 <= cell[1] < rows):
                if (what, "") not in told:
                    told.add((what, ""))
                    problems.append(f"{what} is outside the field at {list(cell)}")
                continue
            other = claims.get(cell)
            if other is None or (other in on and other != what):
                claims[cell] = what if other is None else other
            elif (what, other) not in told:
                told.add((what, other))
                problems.append(f"{what} overlaps {other} at {list(cell)}")

    way_out = section.get("exit") or {}
    gap = _cell(way_out["cell"]) if way_out else None
    if gap is not None and not (gap[0] in (0, cols - 1) or gap[1] in (0, rows - 1)):
        problems.append(f"the way out is not at the edge of the field: {list(gap)}")
    border = [
        (x, y)
        for y in range(rows)
        for x in range(cols)
        if (x in (0, cols - 1) or y in (0, rows - 1)) and (x, y) != gap
    ]
    claim(border, "the edge")
    if gap is not None:
        claim([gap], "the way out")
    claim(_rect_cells(section["house"]["rect"]), "the house")
    claim([section["house"]["door"]], "the door of the house")
    claim([section["bin"]["cell"]], "the shipping bin")
    for building in section.get("animal_houses", []):
        name = f"the {building['kind']}"
        yard = building.get("yard") or {}
        claim(_rect_cells(building["rect"]), name)
        claim(yard.get("fence", []), f"the fence of {name}")
        if yard.get("gate"):
            claim([yard["gate"]], f"the gate of {name}")
        if yard.get("rect"):
            claim(_rect_cells(yard["rect"]), f"the yard of {name}")
        claim([building["door"]], f"the door of {name}", on=(f"the yard of {name}",))
    claim(section["water"]["cells"], "the water")
    claim(section["tillable"], "the plot")
    claim(section.get("paths", []), "a path", on=("the door of the house", "the way out"))
    claim(section.get("trees", []), "a tree")
    for thing in section.get("scenery", []):
        claim([thing["cell"]], f"scenery ({thing['kind']})")
    seen: set[Cell] = set()
    for thing in section.get("debris", []):
        cell = _cell(thing["cell"])
        if cell in seen:
            problems.append(f"two things to clear lie at {list(cell)}")
        seen.add(cell)
        claim([cell], f"a thing to clear ({thing['kind']})", on=("the plot",))
    for number, trail in enumerate(section.get("trails", []), 1):
        claim([trail["cell"], trail["spawn"]], f"trail {number}")
    return problems


def _room_problems(section: dict[str, Any]) -> list[str]:
    """The house from the inside: the bed is in the room, the farmer starts beside it on the
    floor and can walk to the way out of the room."""
    room = section["house"].get("interior") or {}
    bed = room.get("bed")
    if not bed or not room.get("size"):
        return ["the house has no bed"]
    wide, high = (int(v) for v in room["size"])
    floor = {(x, y) for y in range(1, high - 1) for x in range(1, wide - 1)}
    lying = set(_rect_cells([*bed["cell"], *bed["size"]]))
    if not lying <= floor:
        return ["the bed is not in the room of the house"]
    start = _cell(section["start"]["cell"])
    if section["start"].get("map") != room.get("id") or start not in floor - lying:
        return ["the farmer does not start on the floor of the house"]
    if not any(n in lying for n in _beside(start)):
        return ["the farmer does not start by the bed"]
    seen = {start}
    todo = [start]
    while todo:
        for nxt in _beside(todo.pop()):
            if nxt in floor - lying and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    arrive, way_out = _cell(room["arrive"]), _cell(room["door"])
    if arrive not in seen or way_out not in _beside(arrive) or way_out in floor:
        return ["the door of the house cannot be reached from the bed"]
    return []


def check(section: dict[str, Any]) -> list[str]:
    """What keeps a farm from being worked (``VAL-031``; an empty list: nothing). From the door
    of the house the farmer walks to the plot, to a cell beside the water, to the bin, into every
    yard and to the way out; the plot has twelve cells; nothing lies on something else."""
    problems = _overlaps(section)
    plot = {_cell(c) for c in section["tillable"]}
    if len(plot) < MIN_PLOT:
        cells = "cell" if len(plot) == 1 else "cells"
        problems.append(f"the plot has {len(plot)} {cells}, {MIN_PLOT} are needed")
    reached = reached_cells(section)
    if not reached:
        return [*problems, "the door of the house is blocked"]

    def beside_reached(cells: Any) -> bool:
        return any(n in reached for c in cells for n in _beside(_cell(c)))

    if plot and not plot & reached:
        problems.append("the plot cannot be reached from the house")
    water = {_cell(c) for c in section["water"]["cells"]}
    fill = _cell(section["water"]["fill"]) if section["water"].get("fill") else None
    if not water:
        problems.append("there is no water to fill the can")
    elif not beside_reached(water):
        problems.append("the water cannot be reached from the house")
    elif fill is not None and (fill not in reached or not water & set(_beside(fill))):
        problems.append("the can cannot be filled where the plan says")
    if not beside_reached([section["bin"]["cell"]]):
        problems.append("the shipping bin cannot be reached from the house")
    for building in section.get("animal_houses", []):
        name = f"the {building['kind']}"
        yard = building.get("yard") or {}
        inside = set(_rect_cells(yard["rect"])) if yard.get("rect") else set()
        if not yard.get("gate"):
            problems.append(f"the yard of {name} has no gate")
        elif _cell(yard["gate"]) not in reached or not inside & reached:
            problems.append(f"the yard of {name} cannot be reached from the house")
        elif _cell(building["door"]) not in reached:
            problems.append(f"the door of {name} cannot be reached from the house")
    if not section.get("exit"):
        problems.append("there is no way out to the village")
    elif _cell(section["exit"]["cell"]) not in reached:
        problems.append("the way out cannot be reached from the house")
    return problems + _room_problems(section) + _added_problems(section, reached)


def _added_problems(section: dict[str, Any], reached: set[Cell]) -> list[str]:
    """The ways to the added maps (T17.23): every trail can be walked to from the house and
    lies beside the edge; every added map has a trail of its own and passes its own check."""
    problems: list[str] = []
    cols, rows = (int(v) for v in section["size"])
    trails = section.get("trails", [])
    for number, trail in enumerate(trails, 1):
        door, spawn = _cell(trail["cell"]), _cell(trail["spawn"])
        if door not in reached or spawn not in reached:
            problems.append(f"trail {number} cannot be reached from the house")
        if min(door[0], door[1], cols - 1 - door[0], rows - 1 - door[1]) != 1:
            problems.append(f"trail {number} is not beside the edge of the field: {list(door)}")
    used: set[int] = set()
    for entry in section.get("added", []):
        name = str(entry.get("name", entry.get("id", "")))
        at = entry.get("trail")
        if not isinstance(at, int) or not 0 <= at < len(trails) or at in used:
            problems.append(f"{name} has no trail of its own on the farm")
        else:
            used.add(at)
        problems += [f"{name}: {problem}" for problem in added_map_plan.check(entry)]
    return problems


# --------------------------------------------------------------------------- the plan


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The map of a farm (the section ``farm.map`` of the plan file). A farm that cannot be
    worked is planned again with the next seed (``REROLLS`` times at most); the notes say so."""
    opts = normalized(options)
    known = dict(facts or {})
    found = ["the field has no room for a farm"]
    for attempt in range(REROLLS):
        out = _farm(opts, int(seed) + attempt, known)
        if out is None:
            continue
        found = check(out)
        if not found:
            out["seed"] = int(seed)
            if attempt:
                out["notes"].append(f"The farm was planned with seed {int(seed) + attempt}.")
            out["trails"] = _trails(out, int(seed))
            out["added"] = []
            out, _added = extend(out, opts["added_maps"], known)
            return out
    raise FarmPlanError("no farm that can be worked: " + "; ".join(found[:3]))


def extend(
    stored: dict[str, Any], added_rows: Any, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """``stored`` with the rows of *Added maps* it does not have yet, each planned as a map of
    its own (``added_map_plan``: a forest, a beach) from the farm's seed and the map's number,
    on the next trail of the farm that is free. **Nothing that is stored changes**: not the
    farm, and not a map that was added before (a row whose name the farm has is not looked at
    again, whatever kind it now says). A farm planned before it had trails keeps a new row as a
    name, as it did, and the caller says so (``names_only``). Returns (section, the names that
    were added)."""
    out = copy.deepcopy(stored)
    have = {str(n).casefold() for n in out.get("added_maps", [])}
    added: list[str] = []
    for raw in added_rows or []:
        given = str(raw.get("name", "") if isinstance(raw, dict) else raw).strip()
        if given.casefold() in have:
            continue  # stored already: what the row says now is not read
        try:
            row = added_map_plan.row(raw)
        except added_map_plan.AddedMapError as exc:
            raise FarmPlanError(str(exc)) from None
        name = row["name"]
        if len(have) >= MAX_ADDED:
            raise FarmPlanError(f"a farm has {MAX_ADDED} added maps at most")
        if "trails" in out:
            entries = out.setdefault("added", [])
            free = [i for i in range(len(out["trails"])) if i not in {e["trail"] for e in entries}]
            if not free:
                raise FarmPlanError(
                    f"{name}: the farm has room for {len(out['trails'])} added maps "
                    "(no place is left at its edge for another door)"
                )
            try:
                entry = added_map_plan.plan(
                    row["kind"], len(entries) + 1, int(out.get("seed", 0)), name, facts
                )
            except added_map_plan.AddedMapError as exc:
                raise FarmPlanError(str(exc)) from None
            entry["trail"] = free[0]
            entries.append(entry)
        out.setdefault("added_maps", []).append(name)
        have.add(name.casefold())
        added.append(name)
    return out, added


def names_only(section: dict[str, Any]) -> list[str]:
    """The added maps of a farm that are names and no maps: those of a farm that was planned
    before a farm had trails (before T17.23). Its map has no place for their doors, and a map
    that exists is not built again, so they stay names."""
    built = {str(e["name"]).casefold() for e in section.get("added", [])}
    return [str(n) for n in section.get("added_maps", []) if str(n).casefold() not in built]


def plot_size(section: dict[str, Any]) -> int:
    """How many cells of a farm can be tilled."""
    return len({_cell(c) for c in section["tillable"]})


def summary(section: dict[str, Any]) -> str:
    """ "a farm of 40 x 30 with a plot of 96 cells, a pond, a coop"."""
    cols, rows = section["size"]
    parts = [f"a farm of {cols} x {rows} with a plot of {plot_size(section)} cells"]
    parts.append(f"a {section['water']['kind']}")
    parts += [f"a {b['kind']}" for b in section.get("animal_houses", [])]
    parts += [f"a {e['kind']} ({e['name']})" for e in section.get("added", [])]
    return ", ".join(parts)


def describe(options: Any) -> str:
    """What the options make, without planning: "a medium farm with a medium plot, a coop"."""
    opts = normalized(options)
    animals = "".join(f", a {kind}" for kind in ANIMALS[opts["animals"]])
    added = "".join(f", a {row['kind']}" for row in opts["added_maps"])
    return f"a {opts['farm_size']} farm with a {opts['plot']} plot{animals}{added}"


# --------------------------------------------------------------------------- the stored plan


def stored_in(world: Any) -> dict[str, Any] | None:
    """The farm's map in a world plan (``farm.map``), or None."""
    found = ((world or {}).get("farm") or {}).get("map")
    return found if isinstance(found, dict) else None


def attach(world: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    """``world`` (a copy) with the farm's map in its section ``farm``, beside the crops. The
    crops are planned first (``crop_plan``): the section ``farm`` is theirs, and a world plan
    without it cannot take the map."""
    out = copy.deepcopy(world)
    if not isinstance(out.get("farm"), dict):
        raise FarmPlanError("the plan of the world has no farm section: plan the crops first")
    out["farm"]["map"] = copy.deepcopy(section)
    return out


def exists(project: Any) -> bool:
    """True when the project has its farm already: a stored plan and the map made from it."""
    from pathlib import Path

    from rpggen.core import world_plan

    stored = stored_in(world_plan.load(project)) if project else None
    return bool(stored) and (Path(project) / str((stored or {}).get("map", MAP_FILE))).is_file()


def for_project(
    project: Any, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The farm's map a generation uses: a fresh one while the project has no farm, else the
    stored one, never planned again, with the *Added maps* it does not have yet planned beside it.
    Returns (section, notes); ``attach`` puts the section into the world plan."""
    from rpggen.core import world_plan

    opts = normalized(options)
    if project and exists(project):
        stored = stored_in(world_plan.load(project)) or {}
        extended, added = extend(stored, opts["added_maps"], facts)
        notes = [f"The farm kept its plan; added: {', '.join(added)}."] if added else []
        left = names_only(extended)
        if left:
            notes.append(
                f"The farm was made before added maps were built: {', '.join(left)} "
                f"{'stays a name' if len(left) == 1 else 'stay names'} (its map has no place "
                "for a door to another map, and a map that exists is not built again)."
            )
        return extended, notes
    fresh = plan(opts, seed, facts)
    return fresh, list(fresh["notes"])


if __name__ == "__main__":  # pragma: no cover
    # python -m rpggen.core.farm_plan [seed] [farm_size] [plot] [animals]: a plan, as JSON
    import json
    import sys

    args = sys.argv[1:]
    chosen = dict(zip(("farm_size", "plot", "animals"), args[1:], strict=False))
    print(json.dumps(plan(chosen, int(args[0]) if args else 12345), indent=1))

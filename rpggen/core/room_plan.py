"""The rooms of a metroidvania and the graph that joins them (T14.06).

Pure Python: the plan is deterministic from the options, the seed and nothing else. It is
stored in the project (``rpggen/world_plan.json``, the ``rooms`` section) and the builder's rooms
recipe paints it; the Options page's preview draws it. One module decides the geometry, so the
picture, the game and the tests cannot disagree.

A room is a grid of ``room_size`` tiles. ``tiles`` is one string per row:

    ``#`` solid ground      ``.`` empty             ``=`` one-way platform
    ``H`` ladder            ``T`` ladder with a one-way platform on top
    ``^`` hazard (spikes)   ``B`` a block that breaks

Everything that stands in a room is given by its *feet cell*: the empty cell whose bottom edge is
the floor it stands on.

The rooms form a chain from the start room to the end room. ``abilities`` are the keys of the
chain (``lockkey``, T13.21): a gate that needs an ability lies on the way out of a room, and the
ability lies in a room before it. The first ability is the guardian's, the others are pickups.
"""

from __future__ import annotations

import copy
import math
from random import Random
from typing import Any

from rpggen.core import lockkey

PLAN_VERSION = 1
ROOMS_DIR = "game/maps/rooms"
ABILITIES = ("double_jump", "dash", "wall_jump", "high_jump", "break_blocks")
MIN_ROOMS = 5
MAX_ROOMS = 12
EXTRA_ROOMS = 3  # rooms >= len(abilities) + EXTRA_ROOMS
SIZE_RANGE = ((32, 80), (23, 45))  # width and height in tiles
DEFAULT_SIZE = (40, 23)
DEFAULT_ROOMS = 6
DEFAULT_ABILITIES = ("double_jump", "dash")
ENEMY_RANGE = (0, 4)  # per room with enemies
PICKUP_RANGE = (0, 12)  # in the whole world
MAX_ADDED = 12
EDGES = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
KINDS = ("start", "corridor", "shaft", "guardian", "pickup", "end")

# the platform actor's defaults (RpgPlatformActor), in tiles and seconds
JUMP_TILES = 3.25
HIGH_JUMP_TILES = 1.25
TIME_TO_PEAK = 0.38
FALL_MUL = 1.6
RUN_TILES = 110.0 / 16.0
DASH_TILES = RUN_TILES * 3.0 * 0.18
GRAVITY = 2.0 * JUMP_TILES / (TIME_TO_PEAK * TIME_TO_PEAK)
# what a full jump reaches without any ability, with a margin: the rule for every platform
STEP_UP = 3
GAP_ACROSS = 3

LEDGE_LIP = 2  # how far the top of a ledge reaches out over its face

GATE_KINDS = {
    "double_jump": "ledge",
    "high_jump": "ledge",
    "dash": "gap",
    "break_blocks": "wall",
    "wall_jump": "shaft",
}
GATE_LETTERS = {
    "double_jump": "J",
    "dash": "D",
    "wall_jump": "W",
    "high_jump": "H",
    "break_blocks": "B",
}

Cell = tuple[int, int]


class RoomPlanError(ValueError):
    """The options cannot make a world. ``reason`` says why in a sentence."""


# --------------------------------------------------------------------------- options


def defaults() -> dict[str, Any]:
    """The *Starter world* options of a metroidvania (``config.starter_map`` for the archetype)."""
    return {
        "rooms": DEFAULT_ROOMS,
        "room_size": list(DEFAULT_SIZE),
        "abilities": list(DEFAULT_ABILITIES),
        "enemies": 2,
        "pickups": 4,
    }


def min_rooms(abilities: Any) -> int:
    """The fewest rooms a list of abilities needs: a start, an end, a room per ability to lie
    in, and one to spare."""
    count = len(abilities) if isinstance(abilities, (list, tuple)) else 0
    return max(MIN_ROOMS, count + EXTRA_ROOMS)


def normalized(options: Any) -> dict[str, Any]:
    """The options in their canonical form (defaults filled in, abilities in the table's
    order), or ``RoomPlanError``."""
    given = dict(options) if isinstance(options, dict) else {}
    out = defaults()
    for key in out:
        if key in given:
            out[key] = copy.deepcopy(given[key])
    abilities = out["abilities"]
    if not isinstance(abilities, list) or any(a not in ABILITIES for a in abilities):
        raise RoomPlanError(f"abilities must be a list from {', '.join(ABILITIES)}")
    if len(set(abilities)) != len(abilities):
        raise RoomPlanError("an ability is listed twice")
    out["abilities"] = [a for a in ABILITIES if a in abilities]
    rooms = out["rooms"]
    if not isinstance(rooms, int) or isinstance(rooms, bool):
        raise RoomPlanError("rooms must be a whole number")
    if not MIN_ROOMS <= rooms <= MAX_ROOMS:
        raise RoomPlanError(f"rooms must be {MIN_ROOMS} to {MAX_ROOMS}")
    if rooms < min_rooms(out["abilities"]):
        raise RoomPlanError(
            f"{len(out['abilities'])} abilities need at least {min_rooms(out['abilities'])} rooms"
        )
    size = out["room_size"]
    ok = (
        isinstance(size, (list, tuple))
        and len(size) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in size)
    )
    if not ok or any(not lo <= v <= hi for v, (lo, hi) in zip(size, SIZE_RANGE, strict=False)):
        raise RoomPlanError(
            f"room_size must be [{SIZE_RANGE[0][0]}..{SIZE_RANGE[0][1]}, "
            f"{SIZE_RANGE[1][0]}..{SIZE_RANGE[1][1]}] tiles"
        )
    out["room_size"] = [int(size[0]), int(size[1])]
    for key, (lo, hi) in (("enemies", ENEMY_RANGE), ("pickups", PICKUP_RANGE)):
        value = out[key]
        if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
            raise RoomPlanError(f"{key} must be {lo} to {hi}")
    added = given.get("added_rooms", [])
    if not isinstance(added, list) or len(added) > MAX_ADDED:
        raise RoomPlanError(f"added_rooms must be a list of at most {MAX_ADDED} rows")
    rows = []
    for row in added:
        if not isinstance(row, dict) or not str(row.get("name", "")).strip():
            raise RoomPlanError("an added room needs a name")
        rows.append({"name": str(row["name"]).strip(), "join": str(row.get("join", "")).strip()})
    if rows:
        out["added_rooms"] = rows
    return out


# --------------------------------------------------------------------------- reach


def _jump_height(abilities: Any) -> float:
    return JUMP_TILES + (HIGH_JUMP_TILES if "high_jump" in abilities else 0.0)


def vertical_reach(abilities: Any) -> float:
    """How many tiles up the player gets from flat ground with ``abilities`` (no wall jump)."""
    jumps = 2 if "double_jump" in abilities else 1
    return jumps * _jump_height(abilities)


def horizontal_reach(abilities: Any) -> float:
    """How many tiles the player crosses from an edge to ground on the same level."""
    jumps = 2 if "double_jump" in abilities else 1
    height = _jump_height(abilities)
    rise = jumps * math.sqrt(2.0 * height / GRAVITY)
    fall = math.sqrt(2.0 * jumps * height / (GRAVITY * FALL_MUL))
    return RUN_TILES * (rise + fall) + (DASH_TILES if "dash" in abilities else 0.0)


def gate_size(ability: str, before: Any) -> int:
    """The size of the gate that ``ability`` passes and the abilities ``before`` it do not: the
    height of a ledge or of a shaft, the width of a gap; 1 for a wall of blocks."""
    held = list(before)
    if ability == "double_jump":
        return math.floor(vertical_reach(held)) + 2
    if ability == "high_jump":
        return math.floor(vertical_reach(held)) + 1
    if ability == "dash":
        return math.ceil(horizontal_reach(held) + 0.6)
    if ability == "wall_jump":
        return math.ceil(vertical_reach(held) + 1.5)
    return 1


# --------------------------------------------------------------------------- one room


class _Room:
    """A room being drawn: the grid, what stands in it and which columns are still free."""

    def __init__(self, room_id: str, kind: str, size: Cell) -> None:
        self.id = room_id
        self.kind = kind
        self.w, self.h = size
        self.floor = self.h - 3  # the first solid row of the base floor
        self.g = [["."] * self.w for _ in range(self.h)]
        for x in range(self.w):
            self.g[0][x] = self.g[1][x] = "#"
            for y in range(self.floor, self.h):
                self.g[y][x] = "#"
        for y in range(self.h):
            self.g[y][0] = self.g[y][self.w - 1] = "#"
        self.taken: set[int] = set()  # columns a feature or a thing uses
        self.data: dict[str, Any] = {
            "exits": [],
            "gates": [],
            "enemies": [],
            "items": [],
        }

    def fill(self, x0: int, y0: int, x1: int, y1: int, char: str) -> None:
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            for x in range(max(0, x0), min(self.w - 1, x1) + 1):
                self.g[y][x] = char

    def take(self, x0: int, x1: int, margin: int = 1) -> None:
        self.taken.update(range(x0 - margin, x1 + margin + 1))

    def flat(self, x: int) -> bool:
        """A column of plain base floor with head room, used by nothing."""
        if x in self.taken or not 2 <= x <= self.w - 3:
            return False
        if self.g[self.floor][x] != "#":
            return False
        return all(self.g[y][x] == "." for y in range(self.floor - 4, self.floor))

    def feet(self, x: int) -> list[int]:
        return [x, self.floor - 1]

    def place(self, wanted: int, width: int = 1) -> int | None:
        """The flat column nearest to ``wanted`` with ``width`` flat columns, or None."""
        for offset in range(self.w):
            for x in (wanted + offset, wanted - offset):
                if all(self.flat(c) for c in range(x, x + width)):
                    self.take(x, x + width - 1)
                    return x
        return None

    def tiles(self) -> list[str]:
        return ["".join(row) for row in self.g]


def _pit(room: _Room, x: int, width: int) -> None:
    """A pit with spikes: whoever falls in is hurt and put back on safe ground."""
    f = room.floor
    room.fill(x, f, x + width - 1, f, ".")
    room.fill(x, f + 1, x + width - 1, f + 1, "^")
    room.take(x, x + width - 1, 2)


def _plateau(room: _Room, x: int, height: int) -> int:
    """A raised block ``height`` tiles high from column ``x``, 4 wide, then steps of 3 tiles down
    to the floor again (2 columns each), so the way back is a plain jump. Returns its end."""
    f = room.floor
    room.fill(x, f - height, x + 3, f - 1, "#")
    at = x + 4
    for step in range(height - STEP_UP, 0, -STEP_UP):
        room.fill(at, f - step, at + 1, f - 1, "#")
        at += 2
    room.take(x, at - 1, 2)
    return at - 1


def _gate_width(kind: str, size: int) -> int:
    steps = 2 * len(range(size - STEP_UP, 0, -STEP_UP))
    if kind == "ledge":
        return LEDGE_LIP + 4 + steps
    if kind == "shaft":
        return 4 + 4 + steps
    if kind == "gap":
        return size
    return 1


def _gate(room: _Room, ability: str, before: list[str]) -> int:
    """The gate on the way out of the room to the east: geometry only ``ability`` passes.
    Returns its first column."""
    kind = GATE_KINDS[ability]
    size = gate_size(ability, before)
    width = _gate_width(kind, size)
    x = room.w - 4 - width  # three flat columns between the gate and the exit
    first = x
    f = room.floor
    if kind == "ledge":
        # The top reaches out over the face: whoever has the wall jump cannot climb the face
        # and step on, so the ledge asks for the jump it was sized for.
        x += LEDGE_LIP
        room.fill(x - LEDGE_LIP, f - size, x - 1, f - size, "#")
        _plateau(room, x, size)
        x -= LEDGE_LIP
    elif kind == "shaft":
        # a pillar from the ceiling and the face of a tall block, three columns apart
        room.fill(x, 2, x, f - 4, "#")
        room.take(x, x, 1)
        x += 4
        _plateau(room, x, size)
    elif kind == "gap":
        _pit(room, x, size)
    else:
        room.fill(x, 2, x, f - 3, "#")
        room.fill(x, f - 2, x, f - 1, "B")
        room.take(x, x, 2)
    room.data["gates"].append(
        {"ability": ability, "kind": kind, "size": size, "cell": [x - 1, f - 1]}
    )
    return first


def _feature(room: _Room, name: str, x: int) -> int:
    """Draw a feature from column ``x``; returns its width."""
    f = room.floor
    if name == "pit":
        _pit(room, x, GAP_ACROSS)
        return GAP_ACROSS
    if name == "spikes":
        room.g[f - 1][x] = "^"
        room.take(x, x, 2)
        return 1
    if name == "bump":
        room.fill(x, f - 2, x + 2, f - 1, "#")
        room.take(x, x + 2, 1)
        return 3
    if name == "plank":
        room.fill(x, f - STEP_UP, x + 3, f - STEP_UP, "=")
        room.data["perches"].append([x + 1, f - STEP_UP - 1])
        return 4
    # "floats": two solid platforms, the second higher and further on
    room.fill(x, f - 3, x + 2, f - 3, "#")
    room.fill(x + 5, f - 5, x + 7, f - 5, "#")
    room.data["perches"].append([x + 6, f - 6])
    return 8


FEATURE_WIDTHS = {"pit": 3, "spikes": 1, "bump": 3, "plank": 4, "floats": 8}
CORRIDOR_FEATURES = ("bump", "plank", "pit", "floats", "spikes")
# A room with a gate has nothing to stand on but the floor: a platform before a ledge or a gap
# would be a way past it without the ability.
GROUND_FEATURES = ("pit", "spikes")


def _clear(room: _Room, x: int, width: int) -> bool:
    return all(c not in room.taken for c in range(x - 1, x + width + 1))


def _decorate(
    room: _Room, rng: Random, x0: int, x1: int, features: tuple[str, ...] = CORRIDOR_FEATURES
) -> None:
    """Features between the columns ``x0`` and ``x1``, with flat ground between them and never
    over an exit, a gate or something that stands there already."""
    x = x0
    while x <= x1:
        fitting = [
            n
            for n in features
            if x + FEATURE_WIDTHS[n] - 1 <= x1 and _clear(room, x, FEATURE_WIDTHS[n])
        ]
        if not fitting:
            x += 1
            continue
        name = fitting[rng.randrange(len(fitting))]
        x += _feature(room, name, x) + 4 + rng.randrange(3)


def _exit_cell(room: _Room, edge: str, column: int) -> list[int]:
    if edge == "E":
        return [room.w - 1, room.floor - 1]
    if edge == "W":
        return [0, room.floor - 1]
    return [column, 0 if edge == "N" else room.h - 1]


def _open_exit(room: _Room, edge: str, column: int) -> None:
    f = room.floor
    if edge in ("E", "W"):
        x = room.w - 1 if edge == "E" else 0
        room.fill(x, f - 3, x, f - 1, ".")
        room.take(x - 2, x + 2, 0)
        return
    if edge == "N":  # a ladder from the floor through the ceiling
        room.fill(column, 0, column, f - 1, "H")
    else:  # a ladder up through the floor, with a platform to stand on over the hole
        room.fill(column, f + 1, column, room.h - 1, "H")
        room.g[f][column] = "T"
        room.fill(column, f - 2, column, f - 1, "H")
    room.take(column, column, 2)


def _draw_room(spec: dict[str, Any], options: dict[str, Any], rng: Random) -> dict[str, Any]:
    """The tiles and the things of one room. ``spec`` has id, kind, exits (each with an edge and
    an optional gate) and what the room holds."""
    size = (int(options["room_size"][0]), int(options["room_size"][1]))
    room = _Room(spec["id"], spec["kind"], size)
    room.data["perches"] = []
    column = size[0] // 2
    for exit_ in spec["exits"]:
        _open_exit(room, exit_["edge"], column)
    gate = next((e for e in spec["exits"] if e.get("needs")), None)
    east_end = size[0] - 4
    if gate is not None:
        east_end = _gate(room, gate["needs"], spec["held"]) - 3

    kind = spec["kind"]
    out = room.data
    if kind == "start":
        # the first room teaches: a sign, a place to save, a gap, a platform, spikes
        out["spawn"] = room.feet(3)
        room.take(3, 3)
        out["sign"] = room.feet(5)
        room.take(5, 5)
        out["station"] = room.feet(8)
        room.take(8, 9)
        _feature(room, "pit", 13)
        _feature(room, "plank", 19)
        _feature(room, "spikes", 26)
    elif kind == "guardian":
        at = room.place(int(size[0] * 0.62), 3)
        out["guardian"] = {
            "cell": room.feet(at + 1 if at is not None else column),
            "grants": spec.get("grants", ""),
        }
    elif kind == "end":
        at = room.place(int(size[0] * 0.55))
        out["npc"] = room.feet(at if at is not None else column)
    elif kind in ("corridor", "pickup", "shaft"):
        if kind == "pickup":
            at = room.place(min(east_end - 4, size[0] // 2), 3)
            pedestal = at if at is not None else column
            if gate is None:  # a pedestal; in a room with a gate the pickup lies on the floor
                room.fill(pedestal, room.floor - 1, pedestal + 2, room.floor - 1, "#")
            lift = 2 if gate is None else 1
            out["pickup"] = {"ability": spec["grants"], "cell": [pedestal + 1, room.floor - lift]}
        _decorate(
            room, rng, 6, east_end, GROUND_FEATURES if gate is not None else CORRIDOR_FEATURES
        )

    if kind in ("corridor", "pickup"):
        for _ in range(int(options["enemies"])):
            wanted = 9 + rng.randrange(max(1, east_end - 12))
            at = room.place(wanted, 2)
            if at is not None and at >= 8:
                out["enemies"].append(room.feet(at))
    for _ in range(int(spec.get("items", 0))):
        if out["perches"]:
            out["items"].append(out["perches"].pop(0))
            continue
        at = room.place(6 + rng.randrange(max(1, east_end - 8)))
        if at is not None:
            out["items"].append(room.feet(at))
    if spec.get("chest"):
        at = room.place(max(6, east_end - 3))
        if at is not None:
            out["chest"] = room.feet(at)
    out.pop("perches")
    out["exits"] = [
        {
            "id": e["id"],
            "edge": e["edge"],
            "cell": _exit_cell(room, e["edge"], column),
            "to": e["to"],
            "to_exit": e["to_exit"],
            **({"needs": e["needs"]} if e.get("needs") else {}),
        }
        for e in spec["exits"]
    ]
    out["tiles"] = room.tiles()
    return out


# --------------------------------------------------------------------------- the world


def room_id(index: int) -> str:
    return f"room_{index + 1:02d}"


def exit_id(room: str, edge: str) -> str:
    return f"{room}_exit_{edge.lower()}"


def _chain(count: int, abilities: list[str], rng: Random) -> dict[str, Any]:
    """Which edges of the chain are gated, which room is the shaft, and where the abilities
    lie (``lockkey``)."""
    gated = sorted(rng.sample(range(1, count - 1), len(abilities)))
    needs = {edge: ability for edge, ability in zip(gated, abilities, strict=True)}
    ids = [room_id(i) for i in range(count)]
    graph: dict[str, list[Any]] = {r: [] for r in ids}
    for i in range(count - 1):
        key = needs.get(i)
        graph[ids[i]].append((ids[i + 1], key) if key else ids[i + 1])
        graph[ids[i + 1]].append((ids[i], key) if key else ids[i])
    try:
        found = lockkey.plan(graph, abilities, ids[0], ids[-1], rng)
    except lockkey.LockKeyError as exc:  # the bounds of the options rule this out
        raise RoomPlanError(str(exc)) from exc
    return {"ids": ids, "needs": needs, "placements": found.placements, "path": found.path}


def plan(options: Any, seed: int, catalog: Any = None) -> dict[str, Any]:
    """The rooms of a world: deterministic from the options and the seed. ``catalog`` is not
    needed for the geometry (the recipe picks the tiles) and is accepted for the callers that
    plan every kind of world the same way."""
    del catalog
    opts = normalized(options)
    count = int(opts["rooms"])
    abilities: list[str] = list(opts["abilities"])
    rng = Random(f"{int(seed)}:rooms")
    chain = _chain(count, abilities, rng)
    ids: list[str] = chain["ids"]
    holder = {room: ability for ability, room in chain["placements"].items()}
    kinds = ["corridor"] * count
    kinds[0], kinds[-1] = "start", "end"
    for i, room in enumerate(ids):
        if room in holder:
            kinds[i] = "guardian" if abilities and holder[room] == abilities[0] else "pickup"
    # one shaft: a plain room whose way on is not gated, and neither end of it the guardian's
    shafts = [
        i
        for i in range(1, count - 1)
        if kinds[i] == "corridor" and i not in chain["needs"] and kinds[i + 1] != "guardian"
    ]
    shaft = shafts[rng.randrange(len(shafts))] if shafts else -1
    if shaft >= 0:
        kinds[shaft] = "shaft"

    cells: list[Cell] = [(0, 0)]
    for i in range(1, count):
        px, py = cells[-1]
        cells.append((px, py - 1) if i - 1 == shaft else (px + 1, py))

    plain = [i for i in range(count) if kinds[i] in ("corridor", "pickup", "shaft")]
    items = {i: 0 for i in range(count)}
    for n in range(int(opts["pickups"]) if plain else 0):
        items[plain[n % len(plain)]] += 1
    chest_room = next((i for i in range(count) if kinds[i] == "corridor"), -1)

    rooms: list[dict[str, Any]] = []
    for i, room in enumerate(ids):
        exits = []
        if i > 0:
            edge = "S" if i - 1 == shaft else "W"
            other = "N" if edge == "S" else "E"
            exits.append({"id": exit_id(room, edge), "edge": edge, "to": ids[i - 1],
                          "to_exit": exit_id(ids[i - 1], other)})  # fmt: skip
        if i < count - 1:
            edge = "N" if i == shaft else "E"
            other = "S" if edge == "N" else "W"
            exits.append(
                {
                    "id": exit_id(room, edge),
                    "edge": edge,
                    "to": ids[i + 1],
                    "to_exit": exit_id(ids[i + 1], other),
                    "needs": chain["needs"].get(i),
                }
            )
        held = [a for edge, a in sorted(chain["needs"].items()) if edge < i]
        spec = {
            "id": room,
            "kind": kinds[i],
            "exits": exits,
            "held": held,
            "grants": holder.get(room, ""),
            "items": items[i],
            "chest": i == chest_room,
        }
        drawn = _draw_room(spec, opts, Random(f"{int(seed)}:{room}"))
        rooms.append(
            {
                "id": room,
                "name": f"Room {i + 1}",
                "kind": kinds[i],
                "map": f"{ROOMS_DIR}/{room}.tscn",
                "cell": [cells[i][0], cells[i][1]],
                "size": list(opts["room_size"]),
                **drawn,
            }
        )
    return {
        "version": PLAN_VERSION,
        "room_size": list(opts["room_size"]),
        "abilities": abilities,
        "start": ids[0],
        "end": ids[-1],
        "guardian": next((r for r, k in zip(ids, kinds, strict=True) if k == "guardian"), ""),
        "path": [str(r) for r in chain["path"]],
        "list": rooms,
    }


def room_of(rooms: dict[str, Any], ident: str) -> dict[str, Any] | None:
    return next((r for r in rooms.get("list", []) if r["id"] == ident), None)


def _slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_")
    return out or "room"


def _free_edges(rooms: dict[str, Any], room: dict[str, Any]) -> list[str]:
    """The side edges of a room that have no exit and no room behind them."""
    used = {e["edge"] for e in room["exits"]}
    cells = {(r["cell"][0], r["cell"][1]) for r in rooms["list"]}
    out = []
    for edge in ("E", "W"):
        behind = (room["cell"][0] + STEP[edge][0], room["cell"][1] + STEP[edge][1])
        if edge not in used and behind not in cells:
            out.append(edge)
    return out


def extend(stored: dict[str, Any], added_rows: Any, seed: int) -> tuple[dict[str, Any], list[str]]:
    """The stored rooms with the rows they do not have yet appended (by name). A new room is a
    plain room beside the room its ``join`` names, on a side that is free; when that room has no
    free side, beside the nearest room that has one. It gets an exit to that room; the exit on
    the other side is added to the neighbour's scene by the world repair, because a room that
    exists is never rebuilt. No ability is involved. Returns the rooms and the ids added."""
    out = copy.deepcopy(stored)
    known = {_slug(r["name"]) for r in out["list"]}
    added: list[str] = []
    for row in added_rows or []:
        name = str(row.get("name", "")).strip()
        if not name or _slug(name) in known:
            continue
        wanted = next(
            (r for r in out["list"] if _slug(r["name"]) == _slug(str(row.get("join", "")))), None
        )
        order = sorted(
            out["list"],
            key=lambda r: (
                0 if r is wanted else 1,
                abs(r["cell"][0] - wanted["cell"][0]) + abs(r["cell"][1] - wanted["cell"][1])
                if wanted
                else 0,
                r["id"],
            ),
        )
        host = next((r for r in order if _free_edges(out, r)), None)
        if host is None:
            raise RoomPlanError(f"no room has a free side for {name!r}")
        edge = _free_edges(out, host)[0]
        ident = f"room_{_slug(name)}"
        taken = {r["id"] for r in out["list"]}
        n = 2
        while ident in taken:
            ident = f"room_{_slug(name)}_{n}"
            n += 1
        back = OPPOSITE[edge]
        spec = {
            "id": ident,
            "kind": "corridor",
            "exits": [{"id": exit_id(ident, back), "edge": back, "to": host["id"],
                       "to_exit": exit_id(host["id"], edge)}],
            "held": [],
            "grants": "",
            "items": 1,
            "chest": False,
        }  # fmt: skip
        opts = {**defaults(), "room_size": out["room_size"]}
        drawn = _draw_room(spec, opts, Random(f"{int(seed)}:extend:{ident}"))
        out["list"].append(
            {
                "id": ident,
                "name": name,
                "kind": "corridor",
                "map": f"{ROOMS_DIR}/{ident}.tscn",
                "cell": [host["cell"][0] + STEP[edge][0], host["cell"][1] + STEP[edge][1]],
                "size": list(out["room_size"]),
                "added": True,
                **drawn,
            }
        )
        known.add(_slug(name))
        added.append(ident)
    return out, added


def graph_of(rooms: dict[str, Any]) -> dict[str, list[Any]]:
    """Room -> the rooms its exits lead to, with the ability an exit needs (``lockkey``'s form).
    Only exits whose partner exists count."""
    by_id = {r["id"]: r for r in rooms.get("list", [])}
    graph: dict[str, list[Any]] = {r: [] for r in by_id}
    for room in by_id.values():
        for exit_ in room["exits"]:
            target = by_id.get(exit_["to"])
            if target is None:
                continue
            needs = exit_.get("needs")
            if not needs:  # the gate of a pair is written on the side it stands on
                partner = next((e for e in target["exits"] if e["id"] == exit_["to_exit"]), None)
                needs = partner.get("needs") if partner else None
            graph[room["id"]].append((target["id"], needs) if needs else target["id"])
    return graph


def placements(rooms: dict[str, Any]) -> dict[str, str]:
    """Ability -> the room it lies in (the guardian's or a pickup's)."""
    out: dict[str, str] = {}
    for room in rooms.get("list", []):
        grants = (room.get("guardian") or {}).get("grants") or (room.get("pickup") or {}).get(
            "ability"
        )
        if grants:
            out[str(grants)] = room["id"]
    return {a: out[a] for a in rooms.get("abilities", []) if a in out}


def check(rooms: dict[str, Any]) -> dict[str, list[str]]:
    """What a validator would say: ``unreachable`` (rooms the start room cannot reach through
    exits, with the abilities picked up on the way: VAL-027) and ``unpaired`` (exits whose target
    room or exit does not exist: VAL-028). Both are empty for every plan this module makes; a
    room added by ``extend`` is unpaired on its neighbour's side until the repair has run."""
    by_id = {r["id"]: r for r in rooms.get("list", [])}
    unpaired = []
    for room in by_id.values():
        for exit_ in room["exits"]:
            target = by_id.get(exit_["to"])
            if target is None or not any(e["id"] == exit_["to_exit"] for e in target["exits"]):
                unpaired.append(exit_["id"])
    found = lockkey.check(graph_of(rooms), placements(rooms), rooms["start"], rooms["end"])
    return {"unreachable": [str(n) for n in found.unreachable], "unpaired": sorted(unpaired)}


def summary(rooms: dict[str, Any]) -> str:
    """One line for the report and the summary panel: "6 rooms, 2 abilities, a guardian"."""
    count = len(rooms.get("list", []))
    abilities = len(rooms.get("abilities", []))
    parts = [f"{count} room{'s' if count != 1 else ''}"]
    parts.append(f"{abilities} abilit{'ies' if abilities != 1 else 'y'}")
    if rooms.get("guardian"):
        parts.append("a guardian")
    return ", ".join(parts)


def describe(options: Any) -> str:
    """``summary`` for options that have not been planned yet (the Options page, the dry run)."""
    opts = normalized(options)
    abilities = len(opts["abilities"])
    count = int(opts["rooms"]) + len(opts.get("added_rooms", []))
    text = f"{count} rooms, {abilities} abilit{'ies' if abilities != 1 else 'y'}"
    return text + (", a guardian" if abilities else "")


# --------------------------------------------------------------------------- the stored plan


def world(rooms: dict[str, Any], seed: int, notes: list[str] | None = None) -> dict[str, Any]:
    """The world plan file of a metroidvania: no areas, the rooms."""
    return {
        "world_plan_version": 1,
        "seed": int(seed),
        "areas": [],
        "grid": {r["id"]: list(r["cell"]) for r in rooms["list"]},
        "notes": list(notes or []),
        "maps": {},
        "rooms": rooms,
    }


def existing_rooms(project: Any, rooms: dict[str, Any] | None) -> set[str]:
    """The ids of the planned rooms whose scene exists in the project folder."""
    from pathlib import Path

    if not rooms:
        return set()
    return {r["id"] for r in rooms.get("list", []) if (Path(project) / r["map"]).is_file()}


def exists(project: Any) -> bool:
    """True when the project has its world already: a stored plan and one of its rooms."""
    from rpggen.core import world_plan

    stored = world_plan.load(project) if project else None
    return bool(existing_rooms(project, (stored or {}).get("rooms")))


def for_project(
    project: Any, options: Any, seed: int, catalog: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The world plan a generation uses: a fresh one while no room of the stored plan exists
    (the seed and the options still count), else the stored one, never planned again, with the
    rows of ``added_rooms`` it does not have yet appended. Returns (world plan, notes)."""
    from rpggen.core import world_plan

    opts = normalized(options)
    stored = world_plan.load(project) if project else None
    rooms = (stored or {}).get("rooms")
    if stored and rooms and existing_rooms(project, rooms):
        extended, added = extend(rooms, opts.get("added_rooms", []), seed)
        out = copy.deepcopy(stored)
        out["rooms"] = extended
        out["grid"] = {r["id"]: list(r["cell"]) for r in extended["list"]}
        kept = [f"The world kept its plan; added: {', '.join(added)}."] if added else []
        return out, kept
    fresh = plan(opts, seed, catalog)
    notes: list[str] = []
    if opts.get("added_rooms"):
        fresh, _added = extend(fresh, opts["added_rooms"], seed)
    return world(fresh, seed), notes

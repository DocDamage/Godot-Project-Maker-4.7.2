"""The tracks of a racing game (T16.13).

A track is a **closed loop** of road on a coarse grid. Every cell of that grid is a block of
``BLOCK`` tiles; a cell of the loop has a road ``ROAD`` tiles wide through its middle, straight
on or round a corner, with a verge of grass at its sides. The loop begins as the ring round a
rectangle and is then pushed out, a piece at a time: two neighbouring cells of the loop are
joined through the two free cells beside them instead. A ring stays a ring under that, so the
loop never crosses itself; every push adds two corners (two of them in a row are an S-bend).
The field is cut to the loop, walled at its edges, and the cells the loop does not use are
barriers with scenery on them.

A track has a start line on a straight, **checkpoints** in the order they are passed,
**waypoints** along the middle of the road with the speed the car's own arithmetic
(``car_math``) allows there, patches of dirt and oil and boost arrows that grow in number
from track to track, tyres at the outside of its corners and places for pickups.

``plan(options, seed, facts)`` is deterministic; a project keeps the plan it stored
(``rpggen/world_plan.json``, the section ``stages``, where the other arcade kinds have their
stages: a track is a stage of the game), and *Added tracks* appends to it (``for_project``).
A plan is checked (``check``, ``VAL-029``): the loop is closed and does not cross, the road is
one piece that holds the start, every checkpoint and every waypoint, the checkpoints are in the
order of the loop, and the road is at least two cars wide. No Qt, no Godot.
"""

from __future__ import annotations

import copy
import math
from random import Random
from typing import Any

from rpggen.core import car_math, wave_plan

PLAN_VERSION = 1
KIND = "racing"
SIZES = {"small": (4, 3), "medium": (5, 4), "large": (6, 4)}  # cells of the coarse grid
DIFFICULTIES = ("easy", "normal", "hard")
TRACK_RANGE = (1, 8)
DEFAULT_TRACKS = 4
LAP_RANGE = (1, 9)
MAX_ADDED = 8
MAX_TRACKS = 12
STAGES_FILE = wave_plan.STAGES_FILE

BLOCK = 9  # tiles a cell of the coarse grid is wide and high
ROAD = 5  # tiles the road is wide
VERGE = (BLOCK - ROAD) // 2  # grass at each side of it
BORDER = 1  # the wall round the field
CAR = 1.5  # tiles a car is wide, at most
CORNER_RADIUS = 2.5  # tiles: the curve a car drives through a corner cell
PICKUPS = ("boost", "missile", "bomb", "shield")  # T16.14 makes them; the plan says where
ROAD_LETTERS = "rdobs"  # road, dirt, oil, a boost arrow, the start line
GRASS = "g"
REROLLS = 12

Cell = tuple[int, int]
STEPS: dict[str, Cell] = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
HEADINGS = {(1, 0): 0.0, (0, 1): math.pi * 0.5, (-1, 0): math.pi, (0, -1): -math.pi * 0.5}


class TrackPlanError(ValueError):
    """The options cannot make a set of tracks."""


def defaults() -> dict[str, Any]:
    """The *Tracks* options of a racing game (``config.starter_map`` for the archetype)."""
    return {
        "tracks": DEFAULT_TRACKS,
        "laps": 3,
        "track_size": "medium",
        "difficulty": "normal",
        "steering": "relative",
        "camera": "follow",
        "added_tracks": [],
    }


def normalized(options: Any) -> dict[str, Any]:
    """The options with the defaults filled in, or a ``TrackPlanError`` naming what is wrong."""
    out = defaults()
    given = dict(options or {})
    unknown = sorted(set(given) - set(out))
    if unknown:
        raise TrackPlanError(f"unknown option: {unknown[0]}")
    out.update(given)
    for key, allowed in (
        ("track_size", tuple(SIZES)),
        ("difficulty", DIFFICULTIES),
        ("steering", ("relative", "absolute")),
        ("camera", ("follow", "fixed")),
    ):
        if out[key] not in allowed:
            raise TrackPlanError(f"{key} must be one of {', '.join(allowed)}")
    for key, (low, high) in (("tracks", TRACK_RANGE), ("laps", LAP_RANGE)):
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise TrackPlanError(f"{key} must be a whole number from {low} to {high}")
    rows = out["added_tracks"]
    if not isinstance(rows, list) or len(rows) > MAX_ADDED:
        raise TrackPlanError(f"added_tracks must be a list of at most {MAX_ADDED} tracks")
    names: set[str] = set()
    for row in rows:
        name = str(row.get("name", "")).strip() if isinstance(row, dict) else ""
        if not name:
            raise TrackPlanError("an added track needs a name")
        if name.casefold() in names:
            raise TrackPlanError(f"two added tracks are called {name}")
        names.add(name.casefold())
    out["added_tracks"] = [{"name": str(r["name"]).strip()} for r in rows]
    return out


def facts_of(resolution: Any, tile: int) -> dict[str, Any]:
    """What the plan needs to know of the project: the size of the screen and of a tile."""
    return {"view": [int(resolution[0]), int(resolution[1])], "tile": max(8, int(tile))}


stage_id = wave_plan.stage_id
stage_scene = wave_plan.stage_scene


# --------------------------------------------------------------------------- the loop


def _ring(x0: int, y0: int, w: int, h: int) -> list[Cell]:
    """The cells round a rectangle, clockwise from its top left corner."""
    top = [(x, y0) for x in range(x0, x0 + w)]
    right = [(x0 + w - 1, y) for y in range(y0 + 1, y0 + h)]
    bottom = [(x, y0 + h - 1) for x in range(x0 + w - 2, x0 - 1, -1)]
    left = [(x0, y) for y in range(y0 + h - 2, y0, -1)]
    return top + right + bottom + left


def _push_out(loop: list[Cell], cols: int, rows: int, rng: Random) -> bool:
    """Joins two neighbours of the loop through the two free cells beside them. False when no
    piece of the loop has room for that."""
    used = set(loop)
    order = list(range(len(loop)))
    rng.shuffle(order)
    for i in order:
        a, b = loop[i], loop[(i + 1) % len(loop)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        sides = [(-dy, dx), (dy, -dx)]
        rng.shuffle(sides)
        for nx, ny in sides:
            c, e = (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)
            if c in used or e in used:
                continue
            if not (
                0 <= c[0] < cols and 0 <= c[1] < rows and 0 <= e[0] < cols and 0 <= e[1] < rows
            ):
                continue
            loop[i + 1 : i + 1] = [c, e]
            return True
    return False


def _step(a: Cell, b: Cell) -> Cell:
    return b[0] - a[0], b[1] - a[1]


def _is_straight(loop: list[Cell], i: int) -> bool:
    n = len(loop)
    return _step(loop[i - 1], loop[i]) == _step(loop[i], loop[(i + 1) % n])


def _start_index(loop: list[Cell]) -> int | None:
    """Where a race starts: the first cell of the longest run of straight cells (two at least,
    so that the cars have room to get going), or None for a loop without one."""
    n = len(loop)
    best, best_len = None, 1
    for i in range(n):
        if not _is_straight(loop, i) or _is_straight(loop, i - 1):
            continue
        length = 0
        while length < n and _is_straight(loop, (i + length) % n):
            length += 1
        if length > best_len:
            best, best_len = i, length
    return best


def loop_of(size: str, pushes: int, rng: Random) -> list[Cell] | None:
    """A loop on the grid of ``size``, pushed out ``pushes`` times (fewer when it has no room),
    cut to the cells it uses and begun at its start cell; None when it has no straight to
    start on."""
    cols, rows = SIZES[size]
    w = rng.randint(max(4, cols - 1), cols)
    h = rng.randint(max(2, rows - 1), rows)
    loop = _ring(rng.randint(0, cols - w), rng.randint(0, rows - h), w, h)
    for _ in range(pushes):
        if not _push_out(loop, cols, rows, rng):
            break
    left = min(c[0] for c in loop)
    top = min(c[1] for c in loop)
    loop = [(c[0] - left, c[1] - top) for c in loop]
    start = _start_index(loop)
    if start is None:
        return None
    return loop[start:] + loop[:start]


# --------------------------------------------------------------------------- one track


def _origin(cell: Cell) -> Cell:
    """The top left tile of the block of a cell."""
    return BORDER + cell[0] * BLOCK, BORDER + cell[1] * BLOCK


def center_tiles(cell: Cell) -> tuple[float, float]:
    """The middle of the block of a cell, in tiles."""
    ox, oy = _origin(cell)
    return ox + BLOCK * 0.5, oy + BLOCK * 0.5


def _paint(rows: list[list[str]], x0: int, y0: int, x1: int, y1: int, letter: str) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            rows[y][x] = letter


def _paint_road(rows: list[list[str]], loop: list[Cell]) -> None:
    n = len(loop)
    for i, cell in enumerate(loop):
        ox, oy = _origin(cell)
        lo, hi = VERGE, VERGE + ROAD - 1
        _paint(rows, ox + lo, oy + lo, ox + hi, oy + hi, "r")
        arms = [_step(cell, loop[i - 1]), _step(cell, loop[(i + 1) % n])]
        for dx, dy in arms:
            if dx:
                x0, x1 = (ox + hi + 1, ox + BLOCK - 1) if dx > 0 else (ox, ox + lo - 1)
                _paint(rows, x0, oy + lo, x1, oy + hi, "r")
            else:
                y0, y1 = (oy + hi + 1, oy + BLOCK - 1) if dy > 0 else (oy, oy + lo - 1)
                _paint(rows, ox + lo, y0, ox + hi, y1, "r")
        if arms[0][0] != -arms[1][0] or arms[0][1] != -arms[1][1]:
            # a corner: its outside is cut off, where no car drives
            sx = -(arms[0][0] + arms[1][0])
            sy = -(arms[0][1] + arms[1][1])
            rows[oy + (hi if sy > 0 else lo)][ox + (hi if sx > 0 else lo)] = GRASS


def counts_of(level: int, difficulty: str) -> dict[str, int]:
    """How many of each a track has: more from track to track, more on a harder setting."""
    more = DIFFICULTIES.index(difficulty)
    return {
        "dirt": (level + more) // 2,
        "oil": (level + 1 + more) // 2,
        "boost": 1 + level // 3,
        "pickups": 2 + level // 2,
    }


def _track(
    index: int, options: dict[str, Any], facts: dict[str, Any], seed: int, title: str = ""
) -> dict[str, Any] | None:
    rng = Random(f"{KIND}:{seed}:{index}")
    tile = facts["tile"]
    pushes = 1 + index + DIFFICULTIES.index(options["difficulty"])
    loop = loop_of(options["track_size"], pushes, rng)
    if loop is None:
        return None
    n = len(loop)
    cols = max(c[0] for c in loop) + 1
    rows_n = max(c[1] for c in loop) + 1
    width, height = cols * BLOCK + 2 * BORDER, rows_n * BLOCK + 2 * BORDER
    rows = [[GRASS] * width for _ in range(height)]
    _paint_road(rows, loop)

    def px(x: float, y: float) -> list[float]:
        return [round(x * tile, 2), round(y * tile, 2)]

    # the start: a line across the road, three tiles into the first cell; the car behind it
    way = _step(loop[0], loop[1])
    heading = HEADINGS[way]
    cx, cy = center_tiles(loop[0])
    back = BLOCK * 0.5
    line = (cx - way[0] * (back - 3.5), cy - way[1] * (back - 3.5))
    car = (cx - way[0] * (back - 1.5), cy - way[1] * (back - 1.5))
    for across in range(-(ROAD // 2), ROAD // 2 + 1):
        rows[math.floor(line[1] + abs(way[0]) * across)][
            math.floor(line[0] + abs(way[1]) * across)
        ] = "s"

    # what lies on the road: on straights, away from where the race starts
    straights = [i for i in range(2, n) if _is_straight(loop, i)]
    rng.shuffle(straights)
    counts = counts_of(index, options["difficulty"])
    # pickups lie anywhere beyond the first two cells, one to a cell
    places = list(range(2, n))
    rng.shuffle(places)
    pickups: list[dict[str, Any]] = [
        {"position": px(*center_tiles(loop[i])), "kind": rng.choice(PICKUPS)}
        for i in sorted(places[: counts_of(index, options["difficulty"])["pickups"]])
    ]
    for kind in ("boost", "oil", "dirt"):
        for _ in range(counts[kind]):
            if not straights:
                break
            i = straights.pop()
            ox, oy = _origin(loop[i])
            lo, hi, mid = VERGE, VERGE + ROAD - 1, BLOCK // 2
            along = _step(loop[i], loop[(i + 1) % n])
            if kind == "dirt":
                _paint(rows, ox + lo, oy + lo, ox + hi, oy + hi, "d")
            elif kind == "oil":
                side = rng.choice((-1, 0))  # one side of the road: there is a way past it
                if along[0]:
                    _paint(rows, ox + mid - 1, oy + mid + side, ox + mid, oy + mid + side + 1, "o")
                else:
                    _paint(rows, ox + mid + side, oy + mid - 1, ox + mid + side + 1, oy + mid, "o")
            elif along[0]:  # a boost arrow: a strip across the middle of the road
                _paint(rows, ox + mid, oy + mid - 1, ox + mid, oy + mid + 1, "b")
            else:
                _paint(rows, ox + mid - 1, oy + mid, ox + mid + 1, oy + mid, "b")

    waypoints: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    for i, cell in enumerate(loop):
        x, y = center_tiles(cell)
        letter = rows[math.floor(y)][math.floor(x)]
        surface = {"d": "dirt", "o": "oil"}.get(letter, "road")
        speed = car_math.top_speed(surface)
        if not _is_straight(loop, i):
            speed = min(speed, car_math.curve_speed(CORNER_RADIUS, surface))
        waypoints.append({"cell": list(cell), "position": px(x, y), "speed": round(speed, 2)})
        if i and i % 2 == 0:
            checkpoints.append(
                {
                    "id": f"c{len(checkpoints) + 1:02d}",
                    "cell": list(cell),
                    "position": px(x, y),
                    "heading": round(HEADINGS[_step(loop[i - 1], cell)], 6),
                    "width": float(BLOCK * tile),
                }
            )

    # the edges of the field, and every cell the loop does not use, run by run
    barriers = [[0, 0, width, 1], [0, height - 1, width, 1]]
    barriers += [[0, 0, 1, height], [width - 1, 0, 1, height]]
    used = set(loop)
    decoration: list[list[float]] = []
    for gy in range(rows_n):
        gx = 0
        while gx < cols:
            if (gx, gy) in used:
                gx += 1
                continue
            end = gx
            while end < cols and (end, gy) not in used:
                end += 1
            ox, oy = _origin((gx, gy))
            barriers.append([ox, oy, (end - gx) * BLOCK, BLOCK])
            for cell_x in range(gx, end):
                bx, by = _origin((cell_x, gy))
                for _ in range(2):
                    decoration.append(
                        px(bx + rng.uniform(1.5, BLOCK - 1.5), by + rng.uniform(1.5, BLOCK - 1.5))
                    )
            gx = end
    tyres = []
    for i, cell in enumerate(loop):
        if _is_straight(loop, i):
            continue
        arms = [_step(cell, loop[i - 1]), _step(cell, loop[(i + 1) % n])]
        sx, sy = -(arms[0][0] + arms[1][0]), -(arms[0][1] + arms[1][1])
        ox, oy = _origin(cell)
        tyres.append(
            px(ox + (BLOCK - 1.5 if sx > 0 else 1.5), oy + (BLOCK - 1.5 if sy > 0 else 1.5))
        )

    laps = options["laps"]
    return {
        "id": stage_id(index),
        "scene": "res://" + stage_scene(index),
        "title": title,
        "level": index,
        "axis": "none",
        "speed": 0.0,
        "length": 0.0,
        "exit": "custom",  # the race says when it is over
        "par_time_s": float(math.ceil(laps * n * BLOCK / (car_math.TOP * 0.7))),
        "waves": [],
        "laps": laps,
        "cells": [cols, rows_n],
        "loop": [list(c) for c in loop],
        "rows": ["".join(row) for row in rows],
        "start": {"position": px(*car), "heading": round(heading, 6), "line": px(*line)},
        "checkpoints": checkpoints,
        "waypoints": waypoints,
        "barriers": barriers,
        "tyres": tyres,
        "decoration": decoration,
        "pickups": pickups,
    }


# --------------------------------------------------------------------------- the check


def _cell_at(position: Any, tile: int) -> tuple[int, int]:
    return math.floor(position[0] / tile), math.floor(position[1] / tile)


def check_track(track: dict[str, Any], tile: int) -> list[str]:
    """What keeps a track from being raced (an empty list: nothing)."""
    problems: list[str] = []
    loop = [tuple(c) for c in track.get("loop", [])]
    rows = track.get("rows", [])
    if len(loop) < 4 or not rows:
        return ["no loop"]
    if len(set(loop)) != len(loop):
        problems.append("the loop crosses itself")
    for i, cell in enumerate(loop):
        dx, dy = _step(loop[i - 1], cell)  # type: ignore[arg-type]
        if abs(dx) + abs(dy) != 1:
            problems.append(f"the loop is not closed at cell {list(cell)}")
            break

    def letter(at: tuple[int, int]) -> str:
        x, y = at
        return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else GRASS

    # the road is one piece: from the start line every tile of it is reached
    line = _cell_at(track["start"]["line"], tile)
    if letter(line) not in ROAD_LETTERS:
        return [*problems, "the start line is not on the road"]
    seen = {line}
    todo = [line]
    while todo:
        x, y = todo.pop()
        for dx, dy in STEPS.values():
            nxt = (x + dx, y + dy)
            if nxt not in seen and letter(nxt) in ROAD_LETTERS:
                seen.add(nxt)
                todo.append(nxt)
    road = sum(1 for row in rows for c in row if c in ROAD_LETTERS)
    if len(seen) != road:
        problems.append(f"{road - len(seen)} tiles of road cannot be reached from the start")
    if _cell_at(track["start"]["position"], tile) not in seen:
        problems.append("the car does not start on the road")
    order = {cell: i for i, cell in enumerate(loop)}
    last = 0
    for point in track.get("checkpoints", []):
        if _cell_at(point["position"], tile) not in seen:
            problems.append(f"checkpoint {point['id']} is not on the road")
        at = order.get(tuple(point.get("cell", [])), -1)
        if at <= last:
            problems.append(f"checkpoint {point['id']} is not after the one before it")
        last = max(last, at)
    if not track.get("checkpoints"):
        problems.append("no checkpoint")
    for n, point in enumerate(track.get("waypoints", [])):
        if _cell_at(point["position"], tile) not in seen:
            problems.append(f"waypoint {n + 1} is not on the road")

    # two cars side by side: across the road where it leaves a cell, to either neighbour
    def across(x: int, y: int, dx: int, dy: int) -> int:
        """How many tiles of road lie side by side at (x, y), across the way (dx, dy)."""
        if letter((x, y)) not in ROAD_LETTERS:
            return 0
        count = 1
        for sign in (-1, 1):
            k = 1
            while k <= BLOCK and letter((x + sign * k * dy, y + sign * k * dx)) in ROAD_LETTERS:
                count += 1
                k += 1
        return count

    for i, cell in enumerate(loop):
        cx, cy = (math.floor(v) for v in center_tiles(cell))  # type: ignore[arg-type]
        for other in (loop[i - 1], loop[(i + 1) % len(loop)]):
            dx, dy = _step(cell, other)  # type: ignore[arg-type]
            width = across(cx + dx * (ROAD // 2 + 1), cy + dy * (ROAD // 2 + 1), abs(dx), abs(dy))
            if width < 2 * CAR:
                problems.append(f"the road is {width} tiles wide at cell {list(cell)}")
                return problems
    return problems


def check(stages: dict[str, Any]) -> list[str]:
    """What keeps a plan from being raced, track by track (``VAL-029``)."""
    problems: list[str] = []
    for track in stages["list"]:
        problems.extend(f"{track['id']}: {p}" for p in check_track(track, stages["tile"]))
    return problems


# --------------------------------------------------------------------------- the whole set


def _planned(
    index: int, options: dict[str, Any], facts: dict[str, Any], seed: int, title: str = ""
) -> tuple[dict[str, Any], int]:
    """The track ``index``, planned again with the next seed while it cannot be raced.
    Returns (track, the seed it took)."""
    found: list[str] = ["no straight to start on"]
    for attempt in range(REROLLS):
        track = _track(index, options, facts, seed + attempt, title)
        if track is None:
            continue
        found = check_track(track, facts["tile"])
        if not found:
            return track, seed + attempt
    raise TrackPlanError(f"no track {index + 1} that can be raced: " + "; ".join(found[:3]))


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The tracks of a game. A track that cannot be raced is planned again with the next seed
    (``REROLLS`` times at most); the notes of the plan say which."""
    opts = normalized(options)
    known = facts_of((facts or {}).get("view", (640, 360)), (facts or {}).get("tile", 16))
    tracks, notes = [], []
    for index in range(opts["tracks"]):
        track, took = _planned(index, opts, known, int(seed))
        if took != int(seed):
            notes.append(f"Track {index + 1} was planned with seed {took}.")
        tracks.append(track)
    return {
        "plan_version": PLAN_VERSION,
        "kind": KIND,
        "seed": int(seed),
        "orientation": "horizontal",
        "difficulty": opts["difficulty"],
        "track_size": opts["track_size"],
        "laps": opts["laps"],
        "view": list(known["view"]),
        "tile": known["tile"],
        "block": BLOCK,
        "road": ROAD,
        "list": tracks,
        "added": [],
        "notes": notes,
    }


def extend(stored: dict[str, Any], added_rows: Any, seed: int) -> tuple[dict[str, Any], list[str]]:
    """``stored`` with a track for every row of *Added tracks* it does not have yet, each after
    the last and harder than it. Returns (stages, the names that were added)."""
    out = copy.deepcopy(stored)
    have = {str(n).casefold() for n in out.get("added", [])}
    added: list[str] = []
    options = {
        **defaults(),
        "difficulty": out["difficulty"],
        "track_size": out.get("track_size", "medium"),
        "laps": int(out.get("laps", 3)),
    }
    facts = {"view": out["view"], "tile": out["tile"]}
    for row in added_rows or []:
        name = str(row.get("name", "")).strip()
        if not name or name.casefold() in have:
            continue
        if len(out["list"]) >= MAX_TRACKS:
            raise TrackPlanError(f"a game has {MAX_TRACKS} tracks at most")
        track, _took = _planned(len(out["list"]), options, facts, int(seed), name)
        out["list"].append(track)
        out.setdefault("added", []).append(name)
        have.add(name.casefold())
        added.append(name)
    return out, added


def summary(stages: dict[str, Any]) -> str:
    """ "4 tracks of 3 laps, 14 to 22 cells round"."""
    count = len(stages["list"])
    sizes = [len(t["loop"]) for t in stages["list"]]
    laps = stages.get("laps", 3)
    span = f"{min(sizes)} to {max(sizes)}" if min(sizes) != max(sizes) else str(sizes[0])
    return (
        f"{count} track{'s' if count != 1 else ''} of {laps} lap{'s' if laps != 1 else ''}, "
        f"{span} cells round"
    )


def describe(options: Any) -> str:
    """What the options make, without planning: "4 tracks of 3 laps"."""
    opts = normalized(options)
    count = opts["tracks"] + len(opts["added_tracks"])
    laps = opts["laps"]
    return f"{count} track{'s' if count != 1 else ''} of {laps} lap{'s' if laps != 1 else ''}"


def world(stages: dict[str, Any], seed: int) -> dict[str, Any]:
    """The world plan file of a racing game: no areas, the tracks."""
    return wave_plan.world(stages, seed)


exists = wave_plan.exists


def for_project(
    project: Any, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The world plan a generation uses: a fresh one while the project has no tracks, else the
    stored one, never planned again, with the rows of ``added_tracks`` it does not have yet
    appended. Returns (world plan, notes)."""
    from rpggen.core import world_plan

    opts = normalized(options)
    if project and exists(project):
        stored = world_plan.load(project) or {}
        extended, added = extend(stored["stages"], opts["added_tracks"], seed)
        out = copy.deepcopy(stored)
        out["stages"] = extended
        kept = [f"The game kept its tracks; added: {', '.join(added)}."] if added else []
        return out, kept
    fresh = plan(opts, seed, facts)
    if opts["added_tracks"]:
        fresh, _added = extend(fresh, opts["added_tracks"], seed)
    return world(fresh, seed), []

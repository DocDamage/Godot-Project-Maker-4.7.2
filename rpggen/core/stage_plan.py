"""The stages of a run and gun (T16.10).

A stage is a row of **chunks**, each half a screen wide and as high as the screen, drawn in the
room plan's alphabet (``#`` ground, ``.`` air, ``=`` a one-way plank, ``^`` spikes): flat
ground, a gap to jump, a step up or down, planks to stand on, spikes, a low wall. The first
chunks are flat (where the game begins), the last is the boss's arena, a whole screen of flat
ground where the camera stops. Every chunk between them gets the enemies of its place on a
difficulty curve, every third a weapon on its carrier, and one of them is a trap of turrets
that holds the camera.

``plan(options, seed, facts)`` is deterministic; a project keeps the plan it stored
(``rpggen/world_plan.json``, the section ``stages``), and *Added stages* appends to it
(``for_project``), as the shoot 'em up's wave plan does.

A plan is checked (``check``): walking the stage from left to right, every piece of ground is
reached from the one before it by the soldier's jump, worked out with the room plan's numbers
(the same the platform actor moves by); every wave comes before the stage ends; and the boss's
bullets stay under the ceiling. No Qt, no Godot.
"""

from __future__ import annotations

import copy
import math
from random import Random
from typing import Any

from rpggen.core import room_plan, wave_plan

PLAN_VERSION = 1
KIND = "run_and_gun"
LENGTHS = {"short": 6, "medium": 9, "long": 13}  # chunks between the start and the arena
DIFFICULTIES = wave_plan.DIFFICULTIES
STAGE_RANGE = (1, 8)
DEFAULT_STAGES = 3
LIVES_RANGE = (1, 9)
HEALTH_RANGE = (1, 5)
MAX_ADDED = 8
MAX_STAGES = 12
STAGES_DIR = wave_plan.STAGES_DIR
STAGES_FILE = wave_plan.STAGES_FILE

GROUND_ROWS = 3  # rows of ground under the soldier's feet (stage_recipe.gd)
START_CHUNKS = 3  # flat chunks where a stage begins: nothing comes there
ARENA_CHUNKS = 2  # the boss's arena is a whole screen
FEATURES = ("flat", "gap", "step", "planks", "spikes", "wall")
WALKERS = ("runner", "jumper", "sniper")
WEAPONS = ("spread", "laser", "flame")
BOSSES = ("wall", "walker", "flyer")
BOSS_ATTACKS = {
    "wall": ("aimed", "fan", "burst"),
    "walker": ("aimed", "fan", "burst"),
    "flyer": ("rain", "fan", "aimed", "ring"),
}
WEAPON_EVERY = 3  # a weapon carrier in every third chunk
THREAT_PER_STAGE = 4
# a wave comes when its chunk is this much of a screen away from the right edge of the screen
LEAD = 0.25
TRAP_AT = 0.7  # ... and a trap when it is at this part of the screen (it stops the camera)
BULLET_TILES_PER_S = 110.0 / 16.0  # RpgGunEnemy.bullet_speed at 16 px tiles

# what the soldier can do, in tiles, with the numbers the platform actor moves by; a planned
# feature stays a tile inside it, the check allows all of it
JUMP_UP = math.floor(room_plan.vertical_reach(()))  # 3
JUMP_ACROSS = math.floor(room_plan.horizontal_reach(()))  # 4
PLAN_UP = 2
PLAN_ACROSS = 3

BULLET_CEILING = 150
REROLLS = 8


class StagePlanError(ValueError):
    """The options cannot make a run of stages."""


def defaults() -> dict[str, Any]:
    """The *Stages* options of a run and gun (``config.starter_map`` for the archetype)."""
    return {
        "stages": DEFAULT_STAGES,
        "length": "medium",
        "lives": 3,
        "health": 1,
        "keep_weapon": False,
        "left_edge_kills": True,
        "difficulty": "normal",
        "added_stages": [],
    }


def normalized(options: Any) -> dict[str, Any]:
    """The options with the defaults filled in, or a ``StagePlanError`` naming what is wrong."""
    out = defaults()
    given = dict(options or {})
    unknown = sorted(set(given) - set(out))
    if unknown:
        raise StagePlanError(f"unknown option: {unknown[0]}")
    out.update(given)
    if out["length"] not in LENGTHS:
        raise StagePlanError(f"length must be one of {', '.join(LENGTHS)}")
    if out["difficulty"] not in DIFFICULTIES:
        raise StagePlanError(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    for key, (low, high) in (
        ("stages", STAGE_RANGE),
        ("lives", LIVES_RANGE),
        ("health", HEALTH_RANGE),
    ):
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise StagePlanError(f"{key} must be a whole number from {low} to {high}")
    for key in ("keep_weapon", "left_edge_kills"):
        if not isinstance(out[key], bool):
            raise StagePlanError(f"{key} must be true or false")
    rows = out["added_stages"]
    if not isinstance(rows, list) or len(rows) > MAX_ADDED:
        raise StagePlanError(f"added_stages must be a list of at most {MAX_ADDED} stages")
    names: set[str] = set()
    for row in rows:
        name = str(row.get("name", "")).strip() if isinstance(row, dict) else ""
        if not name:
            raise StagePlanError("an added stage needs a name")
        if name.casefold() in names:
            raise StagePlanError(f"two added stages are called {name}")
        names.add(name.casefold())
    out["added_stages"] = [{"name": str(r["name"]).strip()} for r in rows]
    return out


def facts_of(resolution: Any, tile: int) -> dict[str, Any]:
    """What the plan needs to know of the project: the size of the screen and of a tile."""
    return {"view": [int(resolution[0]), int(resolution[1])], "tile": max(8, int(tile))}


def chunk_cols(facts: dict[str, Any]) -> int:
    """How many tiles wide a chunk is: half a screen."""
    return max(8, math.ceil(facts["view"][0] / facts["tile"] / 2))


def stage_rows(facts: dict[str, Any]) -> int:
    """How many tiles high a stage is: the screen."""
    return max(8, math.ceil(facts["view"][1] / facts["tile"]))


def floor_row(rows: int) -> int:
    """The row of the top of the base floor."""
    return rows - GROUND_ROWS


stage_id = wave_plan.stage_id
stage_scene = wave_plan.stage_scene


# --------------------------------------------------------------------------- chunks


class _Chunk:
    """One chunk being drawn: its grid and where things can stand in it."""

    def __init__(self, kind: str, cols: int, rows: int) -> None:
        self.kind = kind
        self.w, self.h = cols, rows
        self.floor = floor_row(rows)
        self.g = [["."] * cols for _ in range(rows)]
        for y in range(self.floor, rows):
            for x in range(cols):
                self.g[y][x] = "#"
        # where enemies stand: [column, row of the feet (the row of the ground under them)]
        self.spots: list[list[int]] = []
        self.perch: list[int] | None = None  # on a plank or a step: a sniper's place
        self.mount: list[int] | None = None  # on a wall: a cannon's place

    def fill(self, x0: int, y0: int, x1: int, y1: int, char: str) -> None:
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            for x in range(max(0, x0), min(self.w - 1, x1) + 1):
                self.g[y][x] = char

    def ground_spots(self, x0: int, x1: int, row: int | None = None) -> None:
        for x in range(x0, x1 + 1, 2):
            self.spots.append([x, self.floor if row is None else row])


def _draw(kind: str, cols: int, rows: int, rng: Random) -> _Chunk:
    chunk = _Chunk(kind, cols, rows)
    f = chunk.floor
    mid = cols // 2
    if kind == "gap":
        width = rng.randint(2, PLAN_ACROSS)
        x0 = mid - width // 2
        chunk.fill(x0, f, x0 + width - 1, rows - 1, ".")  # no bottom: a fall is a death
        chunk.ground_spots(x0 + width + 2, cols - 3)
    elif kind == "step":
        height = rng.randint(1, PLAN_UP)
        x0, x1 = mid - 3, cols - 4
        chunk.fill(x0, f - height, x1, f - 1, "#")
        chunk.ground_spots(x0 + 1, x1 - 1, f - height)
        chunk.perch = [x1 - 1, f - height]
    elif kind == "planks":
        height = rng.randint(2, PLAN_UP + 1)
        x0 = mid - 3
        chunk.fill(x0, f - height, x0 + 5, f - height, "=")
        chunk.perch = [x0 + 4, f - height]
        chunk.ground_spots(3, cols - 3)
    elif kind == "spikes":
        width = rng.randint(1, 2)
        x0 = mid - 1
        chunk.fill(x0, f - 1, x0 + width - 1, f - 1, "^")
        chunk.ground_spots(x0 + width + 2, cols - 3)
    elif kind == "wall":
        height = PLAN_UP
        x0 = mid
        chunk.fill(x0, f - height, x0 + 1, f - 1, "#")
        chunk.mount = [x0 - 1, f - 1]  # on the face of the wall, a tile above the floor
        chunk.ground_spots(x0 + 4, cols - 3)
    else:  # flat, trap, arena
        chunk.ground_spots(3, cols - 3)
    return chunk


def _layout(length: int, rng: Random) -> list[str]:
    """The kinds of the chunks of a stage: the start, the features, the arena. No two gaps in a
    row, and the trap in a flat chunk after the middle."""
    kinds: list[str] = []
    last = ""
    for _ in range(length):
        choices = [k for k in FEATURES if k != last or k == "flat"]
        last = rng.choice(choices)
        kinds.append(last)
    trap = length // 2 + 1 if length > 2 else length - 1
    kinds[trap] = "trap"
    if trap > 0:
        kinds[trap - 1] = "flat"  # the camera stops with this chunk on the screen too
    return ["flat"] * START_CHUNKS + kinds + ["arena"] * ARENA_CHUNKS


# --------------------------------------------------------------------------- waves and bosses


def threat_of(level: int, fraction: float) -> int:
    """How hard a chunk is: its stage and how far along the stage it is. It never falls."""
    return level * THREAT_PER_STAGE + round(fraction * THREAT_PER_STAGE)


def hardness(threat: int, difficulty: str) -> dict[str, Any]:
    """What a threat means: how many, how fast, how tough, and who may come."""
    speed, count, _health = DIFFICULTIES[difficulty]
    allowed = ["runner"]
    if threat >= 1:
        allowed.append("jumper")
    if threat >= 2:
        allowed.append("sniper")
    return {
        "count": min(5, 2 + threat // 3),
        "fast": round(speed * (1.0 + 0.04 * threat), 2),
        "tough": 1 + threat // 6,
        "fan": max(1, round((3 + 2 * (threat // 5)) * count)),
        "walkers": allowed,
    }


def _px(cell: list[int], x0: int, tile: int) -> list[float]:
    """The feet of something that stands on the cell ``[column, row of its ground]``."""
    return [float((x0 + cell[0]) * tile + tile // 2), float(cell[1] * tile)]


def _waves(
    chunks: list[_Chunk], level: int, options: dict[str, Any], facts: dict[str, Any], rng: Random
) -> list[dict[str, Any]]:
    tile, view_w = facts["tile"], facts["view"][0]
    cols = chunks[0].w
    middle = range(START_CHUNKS, len(chunks) - ARENA_CHUNKS)
    out: list[dict[str, Any]] = []

    def entry(index: int, enemy: str, at: float, threat: int, **more: Any) -> dict[str, Any]:
        hard = hardness(threat, options["difficulty"])
        made = {
            "id": f"w{len(out) + 1:02d}",
            "enemy": enemy,
            "chunk": index,
            "formation": "line",
            "count": 1,
            "gap": tile * 2.0,
            "trigger": "progress",
            "at": round(max(0.0, at), 2),
            "anchor": "stage",
            "threat": threat,
            "fast": hard["fast"],
            "tough": hard["tough"],
        }
        made.update(more)
        out.append(made)
        return made

    for n, index in enumerate(middle):
        chunk = chunks[index]
        x0 = index * cols
        fraction = n / max(1, len(middle) - 1)
        threat = threat_of(level, fraction)
        hard = hardness(threat, options["difficulty"])
        at = x0 * tile - view_w * (1.0 - LEAD)
        if chunk.kind == "trap":
            first = _px(chunk.spots[len(chunk.spots) // 2], x0, tile)
            entry(
                index, "turret", x0 * tile - view_w * TRAP_AT + first[0] - x0 * tile, threat,
                count=2, gap=tile * 3.0, blocking=True, fan=hard["fan"],
                position=[first[0] + tile * 1.5, first[1]],
            )  # fmt: skip
            continue
        if chunk.mount is not None:
            entry(index, "wall_cannon", at, threat, position=_px(chunk.mount, x0, tile))
        if chunk.perch is not None and "sniper" in hard["walkers"]:
            entry(index, "sniper", at, threat, position=_px(chunk.perch, x0, tile))
        elif chunk.spots:
            who = rng.choice([w for w in hard["walkers"] if w != "sniper"] or ["runner"])
            count = min(hard["count"], max(1, len(chunk.spots)))
            first = _px(chunk.spots[0], x0, tile)
            entry(
                index, who, at, threat, count=count,
                position=[first[0] + (count - 1) * tile, first[1]],
            )  # fmt: skip
        if n % WEAPON_EVERY == WEAPON_EVERY - 1:
            entry(
                index, "pickup", at, threat, weapon=rng.choice(WEAPONS),
                position=[float((x0 + cols) * tile), float((chunk.floor - 5) * tile)],
            )  # fmt: skip
    return out


def _boss(
    level: int, options: dict[str, Any], facts: dict[str, Any], rng: Random
) -> dict[str, Any]:
    speed, count, health = DIFFICULTIES[options["difficulty"]]
    tile, view = facts["tile"], facts["view"]
    rows = stage_rows(facts)
    kind = BOSSES[(level + rng.randrange(len(BOSSES))) % len(BOSSES)]
    phases = min(4, 2 + level)
    attacks = rng.sample(BOSS_ATTACKS[kind], min(phases, len(BOSS_ATTACKS[kind])))
    while len(attacks) < phases:
        attacks.append(rng.choice(BOSS_ATTACKS[kind]))
    out_phases = []
    for i, attack in enumerate(attacks):
        base = {"aimed": 1, "fan": 3, "burst": 3, "rain": 4, "ring": 8}[attack]
        out_phases.append(
            {
                "until": round(1.0 - (i + 1) / phases, 3),
                "movement": {"wall": "still", "walker": "walk", "flyer": "sweep"}[kind],
                "attacks": [attack],
                "interval": round(max(0.9, 2.2 - 0.15 * level - 0.1 * i), 2),
                "telegraph_s": 0.5,
                "speed": round(1.0 + 0.2 * level, 2),
                "count": max(1, round((base + (level + i) // 2) * count)),
                "fast": round(speed * (1.0 + 0.08 * level + 0.04 * i), 2),
            }
        )
    # where it stands, from the middle of the screen: on the floor at the right, or in the air
    floor_y = floor_row(rows) * tile - view[1] * 0.5
    position = {
        "wall": [view[0] * 0.38, floor_y],
        "walker": [view[0] * 0.25, floor_y],
        "flyer": [view[0] * 0.2, floor_y - tile * 7.0],
    }[kind]
    return {
        "kind": kind,
        "name": "",
        "health": round(30 * (1.0 + 0.6 * level) * health),
        "points": 5000 * (level + 1),
        "position": [round(position[0], 2), round(position[1], 2)],
        "phases": out_phases,
    }


def _stage(
    index: int, options: dict[str, Any], facts: dict[str, Any], seed: int, title: str = ""
) -> dict[str, Any]:
    rng = Random(f"{KIND}:{seed}:{index}")
    cols, rows, tile = chunk_cols(facts), stage_rows(facts), facts["tile"]
    kinds = _layout(LENGTHS[options["length"]], rng)
    chunks = [_draw(kind, cols, rows, rng) for kind in kinds]
    tiles = ["".join("".join(c.g[y]) for c in chunks) for y in range(rows)]
    width_px = len(chunks) * cols * tile
    length = float(width_px - facts["view"][0])  # the camera stops with the arena on the screen
    return {
        "id": stage_id(index),
        "scene": "res://" + stage_scene(index),
        "title": title,
        "level": index,
        "axis": "right",
        "speed": 0.0,  # the soldier leads the camera
        "length": length,
        "exit": "reach_end",
        "par_time_s": float(math.ceil(width_px / (tile * 5.0)) + 60),
        "chunks": kinds,
        "tiles": tiles,
        "start": [float(tile * 3 + tile // 2), float(floor_row(rows) * tile)],
        "waves": _waves(chunks, index, options, facts, rng),
        "boss": _boss(index, options, facts, rng),
    }


# --------------------------------------------------------------------------- the check


def ground(tiles: list[str]) -> list[int | None]:
    """For every column, the row of the highest solid ground (planks do not count: a soldier
    can pass under them), or None for a pit."""
    out: list[int | None] = []
    for x in range(len(tiles[0]) if tiles else 0):
        top: int | None = None
        for y, row in enumerate(tiles):
            if row[x] in "#B":
                top = y
                break
        out.append(top)
    return out


def walk(tiles: list[str]) -> list[str]:
    """What stops a soldier that walks a stage from its left end to its right: nothing (an
    empty list), a step higher than a jump, or a gap wider than one."""
    tops = ground(tiles)
    problems: list[str] = []
    x = 0
    while x < len(tops) - 1:
        here = tops[x]
        if here is None:
            problems.append(f"column {x}: no ground to stand on")
            break
        nxt = tops[x + 1]
        if nxt is not None:
            if here - nxt > JUMP_UP:
                problems.append(
                    f"column {x + 1}: a step of {here - nxt} tiles (a jump rises {JUMP_UP})"
                )
            x += 1
            continue
        end = x + 1
        while end < len(tops) and tops[end] is None:
            end += 1
        width = end - (x + 1)
        if end >= len(tops):
            problems.append(f"column {x + 1}: the ground ends and does not begin again")
            break
        rise = here - tops[end]  # type: ignore[operator]
        reach = JUMP_ACROSS - (1 if rise > 0 else 0)
        if width > reach or rise > JUMP_UP:
            problems.append(
                f"column {x + 1}: a gap of {width} tiles"
                + (f" up {rise}" if rise > 0 else "")
                + f" (a jump crosses {reach})"
            )
        x = end
    return problems


def boss_bullets(boss: dict[str, Any], lifetime_s: float) -> float:
    """The most bullets a phase of the boss can have on the screen at once."""
    worst = 0.0
    for phase in boss.get("phases", []):
        life = lifetime_s / max(0.1, float(phase.get("fast", 1.0)))
        per_attack = float(phase.get("count", 1))
        if "burst" in phase.get("attacks", []):
            per_attack *= 3
        worst = max(worst, per_attack * life / max(0.1, float(phase.get("interval", 2.0))))
    return worst


def check(stages: dict[str, Any]) -> list[str]:
    """What keeps a plan from being finished (an empty list: nothing): ground the soldier's
    jump does not reach, a wave that comes after the stage has ended, or a boss with more
    bullets than the ceiling."""
    problems: list[str] = []
    view, tile = stages["view"], stages["tile"]
    lifetime = math.hypot(view[0], view[1]) / (tile * BULLET_TILES_PER_S)
    for stage in stages["list"]:
        name = stage["id"]
        problems.extend(f"{name}: {p}" for p in walk(stage.get("tiles", [])))
        for wave in stage.get("waves", []):
            if float(wave.get("at", 0.0)) > float(stage["length"]):
                problems.append(f"{name}: wave {wave['id']} comes after the stage has ended")
        worst = boss_bullets(stage.get("boss") or {}, lifetime)
        if worst > BULLET_CEILING:
            problems.append(
                f"{name}: up to {round(worst)} bullets of the boss at once "
                f"(the ceiling is {BULLET_CEILING})"
            )
        if not stage.get("tiles"):
            problems.append(f"{name}: no ground")
    return problems


# --------------------------------------------------------------------------- the whole run


def _plan_once(options: dict[str, Any], seed: int, facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_version": PLAN_VERSION,
        "kind": KIND,
        "seed": int(seed),
        "orientation": "horizontal",
        "difficulty": options["difficulty"],
        "length": options["length"],
        "view": list(facts["view"]),
        "tile": facts["tile"],
        "chunk_cols": chunk_cols(facts),
        "rows": stage_rows(facts),
        "list": [_stage(i, options, facts, seed) for i in range(options["stages"])],
        "added": [],
        "notes": [],
    }


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The stages of a run. Planned again with the next seed while the check finds a problem
    (``REROLLS`` times at most); the notes of the plan say which seed it took."""
    opts = normalized(options)
    known = facts_of((facts or {}).get("view", (640, 360)), (facts or {}).get("tile", 16))
    found: list[str] = []
    for attempt in range(REROLLS):
        candidate = _plan_once(opts, int(seed) + attempt, known)
        found = check(candidate)
        if not found:
            if attempt:
                candidate["notes"].append(
                    f"The stages were planned with seed {int(seed) + attempt}: "
                    f"the plan of seed {int(seed)} could not be finished."
                )
            return candidate
    raise StagePlanError("no plan that can be finished: " + "; ".join(found[:3]))


def extend(stored: dict[str, Any], added_rows: Any, seed: int) -> tuple[dict[str, Any], list[str]]:
    """``stored`` with a stage for every row of *Added stages* it does not have yet, each after
    the last and harder than it. Returns (stages, the names that were added)."""
    out = copy.deepcopy(stored)
    have = {str(n).casefold() for n in out.get("added", [])}
    added: list[str] = []
    options = {
        **defaults(),
        "difficulty": out["difficulty"],
        "length": out.get("length", "medium"),
    }
    facts = {"view": out["view"], "tile": out["tile"]}
    for row in added_rows or []:
        name = str(row.get("name", "")).strip()
        if not name or name.casefold() in have:
            continue
        if len(out["list"]) >= MAX_STAGES:
            raise StagePlanError(f"a run has {MAX_STAGES} stages at most")
        index = len(out["list"])
        for attempt in range(REROLLS):
            stage = _stage(index, options, facts, int(seed) + attempt, name)
            if not check({**out, "list": [stage]}):
                break
        else:
            raise StagePlanError(f"no stage called {name} that can be finished")
        out["list"].append(stage)
        out.setdefault("added", []).append(name)
        have.add(name.casefold())
        added.append(name)
    return out, added


def summary(stages: dict[str, Any]) -> str:
    """ "3 stages, 3 bosses, seen from the side"."""
    count = len(stages["list"])
    bosses = sum(1 for s in stages["list"] if s.get("boss"))
    return (
        f"{count} stage{'s' if count != 1 else ''}, "
        f"{bosses} boss{'es' if bosses != 1 else ''}, seen from the side"
    )


def describe(options: Any) -> str:
    """What the options make, without planning: "3 stages, seen from the side"."""
    opts = normalized(options)
    count = opts["stages"] + len(opts["added_stages"])
    return f"{count} stage{'s' if count != 1 else ''}, seen from the side"


def world(stages: dict[str, Any], seed: int) -> dict[str, Any]:
    """The world plan file of a run and gun: no areas, the stages."""
    return wave_plan.world(stages, seed)


exists = wave_plan.exists


def for_project(
    project: Any, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The world plan a generation uses: a fresh one while the project has no stages, else the
    stored one, never planned again, with the rows of ``added_stages`` it does not have yet
    appended. Returns (world plan, notes)."""
    from rpggen.core import world_plan

    opts = normalized(options)
    if project and exists(project):
        stored = world_plan.load(project) or {}
        extended, added = extend(stored["stages"], opts["added_stages"], seed)
        out = copy.deepcopy(stored)
        out["stages"] = extended
        kept = [f"The run kept its plan; added: {', '.join(added)}."] if added else []
        return out, kept
    fresh = plan(opts, seed, facts)
    if opts["added_stages"]:
        fresh, _added = extend(fresh, opts["added_stages"], seed)
    return world(fresh, seed), []

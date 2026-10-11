"""The stages of a shoot 'em up and the waves of each (T16.06).

``plan(options, seed, facts)`` makes the whole run: for every stage its length, its waves (where
along the stage each comes, its formation, the behaviour of its enemies, how many, what they
fire), a carrier in the middle and a boss with two to four phases. Everything comes from the
seed, so a project plans the same run every time; a project that has its stages keeps the plan
it stored (``rpggen/world_plan.json``, the section ``stages``) and is never planned again, and
*Added stages* appends to it (``for_project``).

Difficulty rises along a stage and from stage to stage. It is one number per wave, the
``threat``, and everything that makes a wave harder is worked out from it: more enemies, more
of them firing, faster bullets, tougher hulls, wider fans.

A plan is checked before it is used (``check``): the bullets that can be on the screen at the
hardest moment stay under a ceiling, and every wave comes before its stage ends. A plan that
fails is planned again with the next seed, and the plan's notes say so.

No Qt, no Godot: the numbers the runtime needs (px, px a second) are worked out here from the
size of the screen and of a tile.
"""

from __future__ import annotations

import copy
import math
from random import Random
from typing import Any

PLAN_VERSION = 1
ORIENTATIONS = ("vertical", "horizontal")
LENGTHS = {"short": 4, "medium": 6, "long": 9}  # screens along the way the stage scrolls
DIFFICULTIES = {  # bullet speed, bullets, health of a boss
    "easy": (0.8, 0.75, 0.8),
    "normal": (1.0, 1.0, 1.0),
    "hard": (1.25, 1.3, 1.25),
}
STAGE_RANGE = (1, 8)
DEFAULT_STAGES = 3
LIVES_RANGE = (1, 9)
BOMBS_RANGE = (0, 9)
MAX_ADDED = 8
MAX_STAGES = 12  # with the added ones
STAGES_DIR = "generated/scenes/stages"
STAGES_FILE = "game/data/stages.json"

FORMATIONS = ("line", "v", "sine", "circle", "column")
BOSS_PATTERNS = ("ring", "fan", "spiral", "aimed", "sweep")
# px a second, in tiles: what the recipes of the kind use (shmup_build.gd, enemy_recipes.gd)
SCROLL_TILES_PER_S = 2.5
BULLET_TILES_PER_S = 5.5
AHEAD = 24.0  # how far beyond the front edge of the screen a wave appears, in px
FORMATION_BONUS = 500
DROP_EVERY = 5  # every fifth formation of small enemies carries a power-up
THREAT_PER_STAGE = 4

# the budget of the check
BULLET_CEILING = 300  # enemy bullets on the screen at once (the pool holds 1,000)
REROLLS = 8


class WavePlanError(ValueError):
    """The options cannot make a run of stages."""


def defaults() -> dict[str, Any]:
    """The *Stages* options of a shoot 'em up (``config.starter_map`` for the archetype)."""
    return {
        "orientation": "vertical",
        "stages": DEFAULT_STAGES,
        "length": "medium",
        "lives": 3,
        "bombs": 3,
        "auto_fire": True,
        "difficulty": "normal",
        "added_stages": [],
    }


def normalized(options: Any) -> dict[str, Any]:
    """The options with the defaults filled in, or a ``WavePlanError`` naming what is wrong."""
    out = defaults()
    given = dict(options or {})
    unknown = sorted(set(given) - set(out))
    if unknown:
        raise WavePlanError(f"unknown option: {unknown[0]}")
    out.update(given)
    if out["orientation"] not in ORIENTATIONS:
        raise WavePlanError(f"orientation must be one of {', '.join(ORIENTATIONS)}")
    if out["length"] not in LENGTHS:
        raise WavePlanError(f"length must be one of {', '.join(LENGTHS)}")
    if out["difficulty"] not in DIFFICULTIES:
        raise WavePlanError(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    for key, (low, high) in (
        ("stages", STAGE_RANGE),
        ("lives", LIVES_RANGE),
        ("bombs", BOMBS_RANGE),
    ):
        value = out[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise WavePlanError(f"{key} must be a whole number from {low} to {high}")
    if not isinstance(out["auto_fire"], bool):
        raise WavePlanError("auto_fire must be true or false")
    rows = out["added_stages"]
    if not isinstance(rows, list) or len(rows) > MAX_ADDED:
        raise WavePlanError(f"added_stages must be a list of at most {MAX_ADDED} stages")
    names: set[str] = set()
    for row in rows:
        name = str(row.get("name", "")).strip() if isinstance(row, dict) else ""
        if not name:
            raise WavePlanError("an added stage needs a name")
        if name.casefold() in names:
            raise WavePlanError(f"two added stages are called {name}")
        names.add(name.casefold())
    out["added_stages"] = [{"name": str(r["name"]).strip()} for r in rows]
    return out


def facts_of(resolution: Any, tile: int) -> dict[str, Any]:
    """What the plan needs to know of the project: the size of the screen and of a tile."""
    return {"view": [int(resolution[0]), int(resolution[1])], "tile": max(8, int(tile))}


# --------------------------------------------------------------------------- geometry


def _forward(orientation: str) -> tuple[float, float]:
    return (1.0, 0.0) if orientation == "horizontal" else (0.0, -1.0)


def _sideways(orientation: str) -> tuple[float, float]:
    fx, fy = _forward(orientation)
    return (-fy, fx)


def along_px(orientation: str, view: Any) -> float:
    """The length of the screen along the way the game scrolls."""
    return float(view[0] if orientation == "horizontal" else view[1])


def across_px(orientation: str, view: Any) -> float:
    """The width of the play area across the way the game scrolls (RpgShmupMath.play_area)."""
    if orientation == "horizontal":
        return float(view[1])
    return float(min(view[0], math.floor(view[1] * 4.0 / 3.0)))


def stage_id(index: int) -> str:
    return f"stage_{index + 1:02d}"


def stage_scene(index: int) -> str:
    return f"{STAGES_DIR}/{stage_id(index)}.tscn"


# --------------------------------------------------------------------------- one stage


def threat_of(level: int, fraction: float) -> int:
    """How hard a wave is: its stage (0 is the first) and how far along the stage it comes
    (0..1). It never falls from one wave to the next, nor from one stage to the next."""
    return level * THREAT_PER_STAGE + round(fraction * THREAT_PER_STAGE)


def hardness(threat: int, difficulty: str) -> dict[str, Any]:
    """What a threat means for a wave: how many, how fast, how tough."""
    speed, count, _health = DIFFICULTIES[difficulty]
    return {
        "count": min(8, 4 + threat // 3),
        "shoot_chance": min(0.9, 0.2 + threat * 0.08),
        "fast": round(speed * (1.0 + 0.04 * threat), 2),
        "tough": 1 + threat // 6,
        "fan": max(1, round((3 + 2 * (threat // 5)) * count)),
    }


def _place(orientation: str, view: Any, at: float, lateral: float, in_stage: bool) -> list[float]:
    fx, fy = _forward(orientation)
    sx, sy = _sideways(orientation)
    ahead = along_px(orientation, view) * 0.5 + AHEAD
    aside = lateral * across_px(orientation, view) * 0.5 * 0.7
    x = fx * ahead + sx * aside
    y = fy * ahead + sy * aside
    if in_stage:  # it sits in the stage: ahead of where the screen is when the wave comes
        x += view[0] * 0.5 + fx * at
        y += view[1] * 0.5 + fy * at
    return [round(x, 2), round(y, 2)]


def _waves(
    level: int, screens: int, options: dict[str, Any], facts: dict[str, Any], rng: Random
) -> list[dict[str, Any]]:
    orientation, view, tile = options["orientation"], facts["view"], facts["tile"]
    along = along_px(orientation, view)
    slots = screens * 2 - 2  # a wave every half screen, the first and the last screen kept free
    middle = slots // 2
    out: list[dict[str, Any]] = []
    formations = 0
    for slot in range(slots):
        fraction = slot / max(1, slots - 1)
        threat = threat_of(level, fraction)
        hard = hardness(threat, options["difficulty"])
        at = round((0.4 + slot * 0.5) * along, 2)
        entry: dict[str, Any] = {
            "id": f"w{slot + 1:02d}",
            "trigger": "progress",
            "at": at,
            "threat": threat,
            "fast": hard["fast"],
            "tough": hard["tough"],
        }
        if slot == middle:
            behaviour, lateral = "carrier", 0.0
            entry.update({"formation": "line", "count": 1, "gap": tile * 1.75})
        elif slot % 3 == 2:
            behaviour = rng.choice(("turret", "asteroid"))
            lateral = rng.choice((-0.3, 0.0, 0.3))
            count = 2 if behaviour == "turret" else 3
            entry.update({"formation": "line", "count": count, "gap": tile * 4.5})
            entry["anchor"] = "stage"
            if behaviour == "turret":
                entry["fan"] = hard["fan"]
        else:
            behaviour = "popcorn"
            lateral = rng.choice((-0.6, -0.3, 0.0, 0.3, 0.6))
            entry.update(
                {
                    "formation": rng.choice(FORMATIONS),
                    "count": hard["count"],
                    "gap": tile * 1.75,
                    "bonus": FORMATION_BONUS,
                    "look": formations,
                }
            )
            formations += 1
            if rng.random() < hard["shoot_chance"]:
                entry["shoots"] = True
            if formations % DROP_EVERY == 0:
                entry["drop"] = "weapon_up"
        entry["enemy"] = behaviour
        entry["position"] = _place(orientation, view, at, lateral, "anchor" in entry)
        out.append(entry)
    return out


def _boss(level: int, options: dict[str, Any], rng: Random) -> dict[str, Any]:
    speed, count, health = DIFFICULTIES[options["difficulty"]]
    phases = min(4, 2 + level)
    patterns = rng.sample(BOSS_PATTERNS, phases)
    fx, fy = _forward(options["orientation"])
    out_phases = []
    for i, pattern in enumerate(patterns):
        base = {"ring": 10, "fan": 5, "spiral": 4, "aimed": 3, "sweep": 3}[pattern]
        out_phases.append(
            {
                "until": round(1.0 - (i + 1) / phases, 3),
                "movement": "sweep" if i % 2 == 0 else "still",
                "attacks": [pattern],
                "interval": round(max(0.8, 2.0 - 0.15 * level - 0.1 * i), 2),
                "telegraph_s": 0.5,
                "speed": round(1.0 + 0.2 * level, 2),
                "count": max(1, round((base + level + i) * count)),
                "fast": round(speed * (1.0 + 0.1 * level + 0.05 * i), 2),
            }
        )
    return {
        "name": "",
        "health": round(40 * (1.0 + 0.6 * level) * health),
        "points": 5000 * (level + 1),
        # a quarter of the way in from the front edge of the screen
        "position": [fx * 0.25, fy * 0.25],
        "phases": out_phases,
    }


def _stage(
    index: int, options: dict[str, Any], facts: dict[str, Any], seed: int, title: str = ""
) -> dict[str, Any]:
    rng = Random(f"{seed}:{index}")
    orientation, view, tile = options["orientation"], facts["view"], facts["tile"]
    screens = LENGTHS[options["length"]]
    along = along_px(orientation, view)
    speed = tile * SCROLL_TILES_PER_S
    length = along * screens
    boss = _boss(index, options, rng)
    boss["position"] = [
        round(boss["position"][0] * view[0], 2),
        round(boss["position"][1] * view[1], 2),
    ]
    return {
        "id": stage_id(index),
        "scene": "res://" + stage_scene(index),
        "title": title,
        "level": index,
        "axis": "right" if orientation == "horizontal" else "up",
        "speed": speed,
        "length": length,
        "exit": "reach_end",
        "par_time_s": float(math.ceil(length / speed) + 30),
        "waves": _waves(index, screens, options, facts, rng),
        "boss": boss,
    }


# --------------------------------------------------------------------------- the check


def bullets_of(wave: dict[str, Any], lifetime_s: float) -> float:
    """How many bullets of this wave can be on the screen at once."""
    count = int(wave.get("count", 1))
    fast = float(wave.get("fast", 1.0))
    life = lifetime_s / max(0.1, fast)
    if wave.get("enemy") == "turret":
        return count * int(wave.get("fan", 3)) * life / 2.0  # a fan every two seconds
    if wave.get("enemy") == "popcorn" and wave.get("shoots"):
        return float(count)  # one shot each
    return 0.0


def boss_bullets(boss: dict[str, Any], lifetime_s: float) -> float:
    """The most bullets a phase of the boss can have on the screen at once."""
    worst = 0.0
    for phase in boss.get("phases", []):
        life = lifetime_s / max(0.1, float(phase.get("fast", 1.0)))
        per_attack = float(phase.get("count", 1))
        if "aimed" in phase.get("attacks", []) or "sweep" in phase.get("attacks", []):
            per_attack *= 3  # bursts of three
        worst = max(worst, per_attack * life / max(0.1, float(phase.get("interval", 2.0))))
    return worst


def check(stages: dict[str, Any]) -> list[str]:
    """What keeps a plan from being finished (an empty list: nothing). The bullets that can be
    on the screen at the hardest moment of every stage stay under ``BULLET_CEILING``, and every
    wave comes before its stage ends."""
    problems: list[str] = []
    view, tile = stages["view"], stages["tile"]
    along = along_px(stages["orientation"], view)
    lifetime = math.hypot(view[0], view[1]) / (tile * BULLET_TILES_PER_S)
    for stage in stages["list"]:
        name = stage["id"]
        waves = stage.get("waves", [])
        for wave in waves:
            if float(wave.get("at", 0.0)) > float(stage["length"]) - along * 0.5:
                problems.append(f"{name}: wave {wave['id']} comes after the stage has ended")
        worst = 0.0
        for wave in waves:  # the waves that are on the screen together: a screen apart at most
            window = [w for w in waves if 0.0 <= float(w["at"]) - float(wave["at"]) <= along]
            worst = max(worst, sum(bullets_of(w, lifetime) for w in window))
        worst = max(worst, boss_bullets(stage.get("boss") or {}, lifetime))
        if worst > BULLET_CEILING:
            problems.append(
                f"{name}: up to {round(worst)} enemy bullets at once "
                f"(the ceiling is {BULLET_CEILING})"
            )
        if not waves and not stage.get("boss"):
            problems.append(f"{name}: no wave and no boss")
    return problems


# --------------------------------------------------------------------------- the whole run


def _plan_once(options: dict[str, Any], seed: int, facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_version": PLAN_VERSION,
        "seed": int(seed),
        "orientation": options["orientation"],
        "difficulty": options["difficulty"],
        "length": options["length"],
        "view": list(facts["view"]),
        "tile": facts["tile"],
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
    raise WavePlanError("no plan that can be finished: " + "; ".join(found[:3]))


def extend(stored: dict[str, Any], added_rows: Any, seed: int) -> tuple[dict[str, Any], list[str]]:
    """``stored`` with a stage for every row of *Added stages* it does not have yet, each after
    the last and harder than it. Returns (stages, the names that were added)."""
    out = copy.deepcopy(stored)
    have = {str(n).casefold() for n in out.get("added", [])}
    added: list[str] = []
    options = {
        **defaults(),
        "orientation": out["orientation"],
        "difficulty": out["difficulty"],
        "length": out.get("length", "medium"),
    }
    facts = {"view": out["view"], "tile": out["tile"]}
    for row in added_rows or []:
        name = str(row.get("name", "")).strip()
        if not name or name.casefold() in have:
            continue
        if len(out["list"]) >= MAX_STAGES:
            raise WavePlanError(f"a run has {MAX_STAGES} stages at most")
        index = len(out["list"])
        for attempt in range(REROLLS):
            stage = _stage(index, options, facts, int(seed) + attempt, name)
            if not check({**out, "list": [stage]}):
                break
        else:
            raise WavePlanError(f"no stage called {name} that can be finished")
        out["list"].append(stage)
        out.setdefault("added", []).append(name)
        have.add(name.casefold())
        added.append(name)
    return out, added


def summary(stages: dict[str, Any]) -> str:
    """ "3 stages, 3 bosses, scrolling up"."""
    count = len(stages["list"])
    bosses = sum(1 for s in stages["list"] if s.get("boss"))
    way = "right" if stages["orientation"] == "horizontal" else "up"
    return (
        f"{count} stage{'s' if count != 1 else ''}, "
        f"{bosses} boss{'es' if bosses != 1 else ''}, scrolling {way}"
    )


def describe(options: Any) -> str:
    """What the options make, without planning: "3 stages, scrolling up"."""
    opts = normalized(options)
    count = opts["stages"] + len(opts["added_stages"])
    way = "right" if opts["orientation"] == "horizontal" else "up"
    return f"{count} stage{'s' if count != 1 else ''}, scrolling {way}"


def world(stages: dict[str, Any], seed: int) -> dict[str, Any]:
    """The world plan file of a shoot 'em up: no areas, the stages."""
    return {
        "world_plan_version": 1,
        "seed": int(seed),
        "areas": [],
        "grid": {},
        "notes": list(stages.get("notes", [])),
        "maps": {},
        "stages": stages,
    }


def exists(project: Any) -> bool:
    """True when the project has its stages already: a stored plan and the list the game reads."""
    from pathlib import Path

    from rpggen.core import world_plan

    stored = world_plan.load(project) if project else None
    return bool((stored or {}).get("stages")) and (Path(project) / STAGES_FILE).is_file()


def for_project(
    project: Any, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The world plan a generation uses: a fresh one while the project has no stages (the seed
    and the options still count), else the stored one, never planned again, with the rows of
    ``added_stages`` it does not have yet appended. Returns (world plan, notes)."""
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

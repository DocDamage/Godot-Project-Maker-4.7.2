"""The crops of a farm (T17.05): which crops the game has, how long each takes, when it grows
and what it is worth.

Every growth strip of the catalog (usage ``growth_strip``, role ``CROP``) is a crop. Its
**days** come from the number of its pictures and the difficulty, its **seasons** are shared
out so that every season has at least two crops, every third crop grows again after a harvest,
and its prices come from its days. A project whose packs have fewer than two crops has the
three drawn ones of the farm kit (``farm_kit.py``, T17.02) in its catalog, and they are planned
like any other; a plan made without the kit (``facts`` with fewer than two crops) names the
same three (``DRAWN``) with a colour and no picture, and the builder draws a plain stand-in.

The plan is deterministic for a seed and is **stored** in the project (``rpggen/world_plan.json``,
the section ``farm``) and reused: once it is there the seed and the options no longer change
it, and a crop added to the packs later is appended (``extend``). The builder writes it with
the scenes of the crops to ``generated/data/crops.json`` on every build and to
``game/data/crops.json`` once; that file is the user's. No Qt, no Godot.
"""

from __future__ import annotations

import copy
import re
from random import Random
from typing import Any

from rpggen.core import calendar_math

PLAN_VERSION = 1
SEASONS = calendar_math.SEASONS
CROPS_FILE = "game/data/crops.json"
PLANNED_FILE = "generated/data/crops.json"
MIN_PER_SEASON = 2
# how many watered nights one picture of a strip stands for
DIFFICULTIES = {"easy": 0.75, "normal": 1.0, "hard": 1.5}
DAYS_RANGE = (2, 14)
REGROW_EVERY = 3  # every third crop of the plan grows again
# The crops rpggen draws when the packs have none: (name, the colour of what is harvested).
DRAWN = (("turnip", "#e8e0f0"), ("carrot", "#e8862e"), ("berry", "#d43a5c"))
DRAWN_STAGES = 5

_SIZE = re.compile(r"_?\d+x\d+")
_FRAMES = re.compile(r"_?\d+_?frames?")
_SLUG = re.compile(r"[^a-z0-9]+")


class CropPlanError(ValueError):
    """Options that cannot be planned; the message names the key."""


def normalized(options: Any) -> dict[str, Any]:
    """The options the planner reads: ``difficulty`` (``normal`` when it is not given)."""
    raw = options if isinstance(options, dict) else {}
    difficulty = str(raw.get("difficulty", "normal"))
    if difficulty not in DIFFICULTIES:
        raise CropPlanError(f"difficulty: {difficulty!r} is not one of {sorted(DIFFICULTIES)}")
    return {"difficulty": difficulty}


def crop_name(asset_id: str) -> str:
    """``ranch.crops.corn_16x32_8frames`` -> ``corn``: the last part of an asset id without the
    cell size and the frame count its name carries."""
    last = asset_id.rsplit(".", 1)[-1].lower()
    name = _FRAMES.sub("", _SIZE.sub("", last))
    return _SLUG.sub("_", name).strip("_") or "crop"


def facts_of(catalog: Any) -> dict[str, Any]:
    """What the planner needs to know of the packs: their growth strips with the role ``CROP``,
    sorted by id, each ``{asset, name, stages}``. The strips rpggen drew for the run (the kit of
    T17.02: its three crops, and the strip grown from a crop of one picture) are among them. A
    strip that is switched off or has fewer than two pictures is no crop."""
    from rpggen.core import catalog as catalog_mod

    crops = []
    for asset in sorted(getattr(catalog, "assets", []), key=lambda a: a.id):
        facets = catalog_mod.effective(asset)
        if facets.get("usage") != "growth_strip" or facets.get("role") != "CROP":
            continue
        if asset.status in ("UNUSED", "MISSING"):
            continue
        stages = int(facets.get("stages") or 0)
        if stages >= 2:
            name = crop_name(str(asset.id))
            crops.append({"asset": str(asset.id), "name": name, "stages": stages})
    return {"crops": crops}


def days_of(stages: int, difficulty: str) -> int:
    """The watered nights from seed to harvest: a night a picture after the first, longer on
    ``hard`` and shorter on ``easy``, within ``DAYS_RANGE``."""
    lo, hi = DAYS_RANGE
    return max(lo, min(hi, round((max(2, stages) - 1) * DIFFICULTIES[difficulty])))


def stage_of(grown: int, days: int, stages: int) -> int:
    """The picture a crop shows after ``grown`` of its ``days`` (``RpgCropData.stage_of``)."""
    total = max(1, days)
    return max(0, min(grown, total)) * (max(1, stages) - 1) // total


def seasons_for(index: int, count: int) -> list[str]:
    """The seasons of the crop at ``index`` of ``count``: a run of seasons that begins one later
    for every crop, long enough that every season has ``MIN_PER_SEASON`` crops (two crops grow
    all year, three for three seasons, four to seven for two, eight and more for one)."""
    need = len(SEASONS) * MIN_PER_SEASON
    span = max(1, min(len(SEASONS), -(-need // max(1, count))))
    return [SEASONS[(index + k) % len(SEASONS)] for k in range(span)]


def _prices(days: int, regrow: int) -> tuple[int, int]:
    """(what a bag of seeds costs, what one harvest sells for). A crop that grows again is
    harvested often, so one harvest pays less."""
    seed_price = 5 * days
    price = max(1, seed_price * 2 // 3) if regrow else seed_price * 2
    return seed_price, price


def _unique(name: str, used: set[str]) -> str:
    out, n = name, 2
    while out in used:
        out = f"{name}_{n}"
        n += 1
    used.add(out)
    return out


def _entry(
    fact: dict[str, Any], index: int, count: int, difficulty: str, used: set[str]
) -> dict[str, Any]:
    crop_id = _unique(str(fact["name"]), used)
    stages = int(fact["stages"])
    days = days_of(stages, difficulty)
    regrow = max(1, days // 3) if index % REGROW_EVERY == REGROW_EVERY - 1 else 0
    seed_price, price = _prices(days, regrow)
    entry: dict[str, Any] = {
        "id": crop_id,
        "name": crop_id.replace("_", " ").capitalize(),
        "asset": str(fact.get("asset", "")),
        "seed": f"seed_{crop_id}",
        "produce": f"crop_{crop_id}",
        "seasons": seasons_for(index, count),
        "days": days,
        "stages": stages,
        "regrow": regrow,
        "seed_price": seed_price,
        "price": price,
        "energy": 8 + 2 * days,
    }
    if fact.get("color"):
        entry["color"] = str(fact["color"])
    return entry


def _with_drawn(found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """The crops of the packs, with the drawn ones when there are fewer than two."""
    if len(found) >= MIN_PER_SEASON:
        return found, []
    taken = {str(f["name"]) for f in found}
    drawn = [
        {"asset": "", "name": name, "stages": DRAWN_STAGES, "color": color}
        for name, color in DRAWN
        if name not in taken
    ]
    what = "no crop" if not found else "one crop"
    names = ", ".join(str(d["name"]) for d in drawn)
    return [*found, *drawn], [f"The packs have {what}: the drawn crops ({names}) were added."]


def plan(options: Any, seed: int, facts: Any = None) -> dict[str, Any]:
    """The ``farm`` section of a new project: the crops, in an order the seed gives. The first
    crop of the plan grows in spring (a new game starts with its seeds)."""
    opts = normalized(options)
    found = [dict(f) for f in (facts or {}).get("crops", [])]
    found.sort(key=lambda f: (str(f.get("asset", "")), str(f["name"])))
    crops, notes = _with_drawn(found)
    Random(f"{int(seed)}:crops").shuffle(crops)
    used: set[str] = set()
    return {
        "plan_version": PLAN_VERSION,
        "seed": int(seed),
        "difficulty": opts["difficulty"],
        "crops": [
            _entry(fact, i, len(crops), opts["difficulty"], used) for i, fact in enumerate(crops)
        ],
        "notes": notes,
    }


def per_season(section: dict[str, Any]) -> dict[str, int]:
    """How many crops of a plan grow in each season."""
    return {
        season: sum(1 for c in section.get("crops", []) if season in c.get("seasons", []))
        for season in SEASONS
    }


def extend(stored: dict[str, Any], facts: Any) -> tuple[dict[str, Any], list[str]]:
    """The stored plan with the growth strips of ``facts`` it does not have yet appended (a crop
    added to the packs later). Nothing of what is there changes. Returns (plan, names added)."""
    out = copy.deepcopy(stored)
    have = {str(c.get("asset", "")) for c in out["crops"]}
    used = {str(c["id"]) for c in out["crops"]}
    added: list[str] = []
    new = [f for f in (facts or {}).get("crops", []) if str(f.get("asset", "")) not in have]
    for fact in sorted(new, key=lambda f: str(f.get("asset", ""))):
        index = len(out["crops"])
        entry = _entry(fact, index, max(index + 1, 4), str(out.get("difficulty", "normal")), used)
        # it grows where the fewest crops grow, and in the season after
        counts = per_season(out)
        first = min(range(len(SEASONS)), key=lambda s: (counts[SEASONS[s]], s))
        entry["seasons"] = [SEASONS[first], SEASONS[(first + 1) % len(SEASONS)]]
        out["crops"].append(entry)
        added.append(str(entry["name"]))
    return out, added


def check(section: dict[str, Any]) -> list[str]:
    """What is wrong with a plan (an empty list for a good one): a season with fewer than two
    crops, a crop that can never be ripe, two crops of one id."""
    problems = [
        f"{season}: {count} crop{'' if count == 1 else 's'}, {MIN_PER_SEASON} are needed"
        for season, count in per_season(section).items()
        if count < MIN_PER_SEASON
    ]
    seen: set[str] = set()
    for crop in section.get("crops", []):
        if crop["id"] in seen:
            problems.append(f"{crop['id']}: listed twice")
        seen.add(crop["id"])
        if not 0 <= int(crop["regrow"]) <= int(crop["days"]):
            problems.append(f"{crop['id']}: grows again after more days than it takes")
    return problems


def summary(section: dict[str, Any]) -> str:
    """One line for the log and the report: "3 crops: Turnip (4 days), Carrot (4 days), ..."."""
    crops = section.get("crops", [])
    parts = [f"{c['name']} ({c['days']} days)" for c in crops]
    return f"{len(crops)} crop{'' if len(crops) == 1 else 's'}: {', '.join(parts)}"


def crops_file(section: dict[str, Any], scenes: dict[str, str] | None = None) -> dict[str, Any]:
    """What ``game/data/crops.json`` holds for a plan (the builder writes the same): the crops
    without what only the planner needs, with the scene of each when ``scenes`` names it."""
    out = []
    for crop in section.get("crops", []):
        entry = {k: copy.deepcopy(v) for k, v in crop.items() if k not in ("asset", "color")}
        entry["scene"] = (scenes or {}).get(str(crop["id"]), "")
        out.append(entry)
    return {"crops": out}


def world(section: dict[str, Any], seed: int) -> dict[str, Any]:
    """The world plan file of a farm that has no areas yet: nothing but its ``farm`` section."""
    return {
        "world_plan_version": 1,
        "seed": int(seed),
        "areas": [],
        "grid": {},
        "notes": [],
        "maps": {},
        "farm": section,
    }


def for_project(
    stored: dict[str, Any] | None, options: Any, seed: int, facts: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The ``farm`` section a generation uses: a fresh plan while the project has none (``stored``
    is the section of its plan file, or None), else the stored one, never planned again, with
    the crops the packs have gained. Returns (section, notes)."""
    if stored and stored.get("crops"):
        extended, added = extend(stored, facts)
        return extended, [f"The farm kept its crops; added: {', '.join(added)}."] if added else []
    fresh = plan(options, seed, facts)
    return fresh, list(fresh["notes"])

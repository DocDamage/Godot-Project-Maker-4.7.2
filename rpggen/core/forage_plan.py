"""Fishing and foraging on a farm (T17.10): what lies at the edges of the farm in which season,
which fish the pond has when, what each is worth, and where the things to forage lie.

Every ``ITEM`` of the catalog tagged ``forage`` is a thing to forage and every ``ITEM`` tagged
``fish`` a fish; a project whose packs have neither has the drawn ones of the farm kit
(``farm_kit.py``) in its catalog, and they are planned like any other. A plan made without the
kit (``facts`` without them) names the same ones (``DRAWN_FORAGE``, ``DRAWN_FISH``) with a colour
and no picture, and the builder draws a plain icon.

* **Forage**: each thing lies in the seasons its tags say (``season:<name>``), else in a season
  of its own, shared out so that every season has something.
* **Fish**: each bites at two of the three times of day (``TIMES``) and in three of the four
  seasons, shared out so that at every time of every season something bites. The water is the
  farm's pond; a well has no fish.
* **Spots**: the cells of the farm where a thing may lie in the morning, chosen by the seed among
  the cells the farmer can walk to that are near the edge and away from the plot, the paths, the
  yards and whatever stands on the farm. They are read off the farm's map (``farm_plan.py``),
  which is not changed; the builder writes them into the map as markers. **Which spot has what
  on which day is not planned**: the game derives it from its seed and the date (``RpgForage``).
* ``fishing`` says whether the rod is sold: the option of that name, and a farm with a pond
  or with a beach among its added maps. It follows the option and the farm's map on every
  generation.
* **Added maps** (T17.23). The places of an added map are part of its own plan
  (``added_map_plan.py``, ``spots``). What lies there is this table's: a thing whose entry
  says ``maps`` lies only on maps of those kinds, and on a map whose kind has things of its own
  only those lie (a beach: shells and seaweed), so a forest has what the farm has. A fish whose
  ``water`` is ``sea`` bites at a beach and nowhere else. The things and the fish of a beach are
  the packs' (an ``ITEM`` tagged ``forage`` and ``beach``, or ``fish`` and ``sea``), else the
  kit's drawn ones; they are appended when the farm gets its first beach.

The plan is deterministic for a seed and is **stored** in the project (``rpggen/world_plan.json``,
``farm.forage``) and reused: once it is there the seed no longer changes it, and a fish or a
thing to forage added to the packs later is appended. The builder writes it to
``generated/data/forage.json`` on every build and to ``game/data/forage.json`` once; that file is
the user's. No Qt, no Godot.
"""

from __future__ import annotations

import copy
from random import Random
from typing import Any

from rpggen.core import calendar_math, crop_plan

PLAN_VERSION = 1
SEASONS = calendar_math.SEASONS
TIMES = ("morning", "day", "evening")
POND = "pond"
FORAGE_FILE = "game/data/forage.json"
PLANNED_FILE = "generated/data/forage.json"
ROD_ITEM = "fishing_rod"
SEASON_TAG = "season:"
# The things rpggen draws when the packs have none: (name, its season, its colour), and the
# fish: (name, its colour). ``farm_kit.FORAGE`` and ``farm_kit.FISH`` draw the same ones.
DRAWN_FORAGE = (
    ("wild_herb", "spring", "#4c9e40"),
    ("wild_berries", "summer", "#7048a8"),
    ("mushroom", "autumn", "#be4638"),
    ("winter_root", "winter", "#ceaa78"),
)
DRAWN_FISH = (("perch", "#7ea85c"), ("carp", "#e28e3e"), ("eel", "#546084"))
# ... and for a beach (T17.23): (name, its seasons, its colour), and the fish of the sea.
# ``farm_kit.BEACH_FORAGE`` and ``farm_kit.SEA_FISH`` draw the same ones.
BEACH = "beach"
SEA = "sea"  # added_map_plan.SEA: the water of a beach
BEACH_TAG = "beach"
SEA_TAG = "sea"
DRAWN_BEACH_FORAGE = (
    ("shell", ("spring", "summer", "autumn", "winter"), "#f2e2c4"),
    ("seaweed", ("spring", "summer", "autumn"), "#3f8f6a"),
)
DRAWN_SEA_FISH = (("sardine", "#96b4d2"), ("sea_bass", "#5a7896"))
# how many places a farm of a size has, how near the edge they lie (cells), how far apart
SPOTS = {"small": 6, "medium": 8, "large": 10}
EDGE = 5
APART = 4
# what a thing is worth and what eating one restores
FORAGE_PRICES = (15, 20, 25)
FORAGE_ENERGY = 8
FISH_PRICES = (30, 45, 60)
FISH_ENERGY = 12
FISH_SPEEDS = (1.0, 1.2, 1.4)  # how fast the mark of the bar moves: the dearer, the faster

Cell = tuple[int, int]


def normalized(options: Any) -> dict[str, Any]:
    """The option the planner reads: ``fishing`` (true when it is not given)."""
    raw = options if isinstance(options, dict) else {}
    return {"fishing": bool(raw.get("fishing", True))}


def facts_of(catalog: Any) -> dict[str, Any]:
    """What the planner needs to know of the packs: their ``ITEM`` pictures tagged ``forage``
    (each ``{asset, name, seasons}``, the seasons from its ``season:`` tags) and tagged ``fish``
    (``{asset, name}``), sorted by id. The ones rpggen drew for the run (the kit) are among them.
    A picture that is switched off, and a colour variant made by rpggen, is none. The things of
    a beach (tagged ``beach`` as well) and the fish of the sea (tagged ``sea``) are lists of
    their own, ``beach`` and ``sea``, which are there only when the packs have such pictures."""
    from rpggen.core import catalog as catalog_mod

    out: dict[str, list[dict[str, Any]]] = {"forage": [], "fish": []}
    beach: list[dict[str, Any]] = []
    sea: list[dict[str, Any]] = []
    for asset in sorted(getattr(catalog, "assets", []), key=lambda a: a.id):
        facets = catalog_mod.effective(asset)
        if asset.kind != "image" or asset.status in ("UNUSED", "MISSING") or "#" in asset.id:
            continue
        if facets.get("role") != "ITEM" or facets.get("usage") not in ("sprite", "object"):
            continue
        tags = [str(t) for t in facets.get("tags") or []]
        name = crop_plan.crop_name(str(asset.id))
        if "fish" in tags:
            (sea if SEA_TAG in tags else out["fish"]).append({"asset": str(asset.id), "name": name})
        elif "forage" in tags:
            seasons = [t[len(SEASON_TAG) :] for t in tags if t.startswith(SEASON_TAG)]
            (beach if BEACH_TAG in tags else out["forage"]).append(
                {
                    "asset": str(asset.id),
                    "name": name,
                    "seasons": [s for s in SEASONS if s in seasons],
                }
            )
    if beach:
        out["beach"] = beach
    if sea:
        out["sea"] = sea
    return out


def _item_id(kind: str, name: str, used: set[str]) -> str:
    base = name if name.startswith(kind) else f"{kind}_{name}"
    out, n = base, 2
    while out in used:
        out = f"{base}_{n}"
        n += 1
    used.add(out)
    return out


def _title(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _forage_entry(fact: dict[str, Any], index: int, used: set[str]) -> dict[str, Any]:
    name = str(fact["name"])
    item = _item_id("forage", name, used)
    seasons = [s for s in SEASONS if s in (fact.get("seasons") or [])]
    entry: dict[str, Any] = {
        "id": item,
        "name": _title(name),
        "asset": str(fact.get("asset", "")),
        "item": item,
        "seasons": seasons or [SEASONS[index % len(SEASONS)]],
        "price": FORAGE_PRICES[index % len(FORAGE_PRICES)],
        "energy": FORAGE_ENERGY,
    }
    if fact.get("color"):
        entry["color"] = str(fact["color"])
    return entry


def _fish_entry(fact: dict[str, Any], index: int, used: set[str]) -> dict[str, Any]:
    name = str(fact["name"])
    item = _item_id("fish", name, used)
    skipped = SEASONS[(len(SEASONS) - 1 - index) % len(SEASONS)]
    step = index % len(FISH_PRICES)
    entry: dict[str, Any] = {
        "id": item,
        "name": _title(name),
        "asset": str(fact.get("asset", "")),
        "item": item,
        "seasons": [s for s in SEASONS if s != skipped],
        "times": [t for t in TIMES if t in (TIMES[index % 3], TIMES[(index + 1) % 3])],
        "water": [POND],
        "price": FISH_PRICES[step],
        "energy": FISH_ENERGY,
        "speed": FISH_SPEEDS[step],
    }
    if fact.get("color"):
        entry["color"] = str(fact["color"])
    return entry


def _cover_seasons(forage: list[dict[str, Any]]) -> None:
    """Every season has a thing to forage: a season that has none is given to the thing that
    lies in the fewest."""
    for season in SEASONS:
        if forage and not any(season in f["seasons"] for f in forage):
            least = min(forage, key=lambda f: len(f["seasons"]))
            least["seasons"] = [s for s in SEASONS if s in (*least["seasons"], season)]


def _cover_times(fish: list[dict[str, Any]]) -> None:
    """At every time of every season a fish bites: a time that has none is given to the fish
    that bites least often."""
    for season in SEASONS:
        for time in TIMES:
            if not fish or any(season in f["seasons"] and time in f["times"] for f in fish):
                continue
            least = min(fish, key=lambda f: len(f["seasons"]) * len(f["times"]))
            least["seasons"] = [s for s in SEASONS if s in (*least["seasons"], season)]
            least["times"] = [t for t in TIMES if t in (*least["times"], time)]


def _with_drawn(facts: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """(the things to forage, the fish, notes): the packs', else the drawn ones."""
    forage = [dict(f) for f in (facts or {}).get("forage", [])]
    fish = [dict(f) for f in (facts or {}).get("fish", [])]
    notes: list[str] = []
    seasons = {name: season for name, season, _color in DRAWN_FORAGE}
    for fact in forage:  # the kit's pictures: each has the season it was drawn for
        if not fact.get("seasons") and str(fact["name"]) in seasons:
            fact["seasons"] = [seasons[str(fact["name"])]]
    if not forage:
        forage = [
            {"asset": "", "name": name, "seasons": [season], "color": color}
            for name, season, color in DRAWN_FORAGE
        ]
        notes.append("The packs have nothing to forage: four drawn things were added.")
    if not fish:
        fish = [{"asset": "", "name": name, "color": color} for name, color in DRAWN_FISH]
        notes.append("The packs have no fish: three drawn ones were added.")
    return forage, fish, notes


# --------------------------------------------------------------------------- the spots


def _cell(value: Any) -> Cell:
    return (int(value[0]), int(value[1]))


def _rect_cells(rect: Any) -> set[Cell]:
    x, y, wide, high = (int(v) for v in rect)
    return {(x + dx, y + dy) for dy in range(high) for dx in range(wide)}


def free_cells(farm_map: dict[str, Any]) -> list[Cell]:
    """The cells of a farm's map a thing to forage may lie on, sorted: the farmer can walk to
    them, they are within ``EDGE`` cells of the edge, and they are not the plot nor beside it,
    not a path, not in a yard, not before a door, the bin, the water or the way out, and nothing
    of the plan lies or stands on them."""
    from rpggen.core import farm_plan

    cols, rows = (int(v) for v in farm_map["size"])
    taken: set[Cell] = set()
    plot = {_cell(c) for c in farm_map.get("tillable", [])}
    taken.update((x + dx, y + dy) for x, y in plot for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    taken.update(_cell(c) for c in farm_map.get("paths", []))
    for thing in [*farm_map.get("scenery", []), *farm_map.get("debris", [])]:
        taken.add(_cell(thing["cell"]))
    for building in [farm_map["house"], *farm_map.get("animal_houses", [])]:
        door = _cell(building["door"])
        taken.update((door[0] + dx, door[1]) for dx in (-1, 0, 1))  # the weather's sign too
        yard = building.get("yard") or {}
        if yard.get("rect"):
            taken.update(_rect_cells(yard["rect"]))
        if yard.get("gate"):
            taken.add(_cell(yard["gate"]))
    taken.update(_cell(farm_map["bin"][key]) for key in ("cell", "front"))
    if farm_map["water"].get("fill"):
        taken.add(_cell(farm_map["water"]["fill"]))
    for x, y in (_cell(c) for c in farm_map["water"].get("cells", [])):
        taken.update(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))  # where one stands to fish
    way_out = farm_map.get("exit") or {}
    taken.update(_cell(way_out[key]) for key in ("cell", "spawn") if way_out.get(key))
    return sorted(
        (x, y)
        for x, y in farm_plan.reached_cells(farm_map)
        if (x, y) not in taken and 1 <= min(x, y, cols - 1 - x, rows - 1 - y) <= EDGE
    )


def spots_for(farm_map: dict[str, Any] | None, seed: int) -> list[list[int]]:
    """The places of a farm where a thing may lie in the morning, as cells sorted from the top:
    as many as ``SPOTS`` gives a farm of its size, chosen by the seed among ``free_cells``, no two
    nearer than ``APART`` cells while the farm has room for that."""
    if not farm_map:
        return []
    cells = free_cells(farm_map)
    Random(f"forage:{int(seed)}").shuffle(cells)
    count = SPOTS.get(str(farm_map.get("farm_size", "medium")), SPOTS["medium"])
    chosen: list[Cell] = []
    for apart in range(APART, 0, -1):
        for cell in cells:
            if len(chosen) >= count:
                break
            if all(abs(cell[0] - c[0]) + abs(cell[1] - c[1]) >= apart for c in chosen):
                chosen.append(cell)
    return [list(c) for c in sorted(chosen, key=lambda c: (c[1], c[0]))]


def has_pond(farm_map: dict[str, Any] | None) -> bool:
    return str(((farm_map or {}).get("water") or {}).get("kind", "")) == POND


def has_sea(farm_map: dict[str, Any] | None) -> bool:
    """True when one of the farm's added maps is a beach (T17.23)."""
    from rpggen.core import added_map_plan

    return added_map_plan.has_sea((farm_map or {}).get("added"))


def has_fish(farm_map: dict[str, Any] | None) -> bool:
    """True when the farm has water with fish in it: a pond, or the sea of a beach."""
    return has_pond(farm_map) or has_sea(farm_map)


def _of_beach(row: dict[str, Any]) -> bool:
    return BEACH in (row.get("maps") or []) or SEA in (row.get("water") or [])


def with_beach(section: dict[str, Any], facts: Any) -> list[str]:
    """Appends the things and the fish of a beach to a plan that has none yet (in place): the
    packs' (``facts["beach"]``, ``facts["sea"]``), else the drawn ones. Every season has a
    thing of the beach and at every time of every season a fish of the sea bites. Returns the
    names that were added; nothing when the plan has them already."""
    if any(_of_beach(row) for key in ("forage", "fish") for row in section.get(key, [])):
        return []
    used = {str(row["id"]) for key in ("forage", "fish") for row in section.get(key, [])}
    drawn_seasons = {name: list(seasons) for name, seasons, _color in DRAWN_BEACH_FORAGE}
    things = [dict(f) for f in (facts or {}).get("beach", [])] or [
        {"asset": "", "name": name, "seasons": list(seasons), "color": color}
        for name, seasons, color in DRAWN_BEACH_FORAGE
    ]
    fish = [dict(f) for f in (facts or {}).get("sea", [])] or [
        {"asset": "", "name": name, "color": color} for name, color in DRAWN_SEA_FISH
    ]
    for found in (things, fish):
        found.sort(key=lambda f: (str(f.get("asset", "")), str(f["name"])))
    forage_rows: list[dict[str, Any]] = []
    for i, fact in enumerate(things):
        if not fact.get("seasons") and str(fact["name"]) in drawn_seasons:
            fact["seasons"] = drawn_seasons[str(fact["name"])]  # the kit's pictures
        forage_rows.append({**_forage_entry(fact, i, used), "maps": [BEACH]})
    fish_rows = [{**_fish_entry(fact, i, used), "water": [SEA]} for i, fact in enumerate(fish)]
    _cover_seasons(forage_rows)
    _cover_times(fish_rows)
    section.setdefault("forage", []).extend(forage_rows)
    section.setdefault("fish", []).extend(fish_rows)
    return [str(row["name"]) for row in (*forage_rows, *fish_rows)]


# --------------------------------------------------------------------------- the plan


def plan(
    options: Any, seed: int, facts: Any = None, farm_map: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The ``farm.forage`` section of a new project. ``farm_map`` is the farm's own map
    (``farm.map``): without one the plan has no spots and no fishing."""
    opts = normalized(options)
    forage, fish, notes = _with_drawn(facts)
    for found in (forage, fish):
        found.sort(key=lambda f: (str(f.get("asset", "")), str(f["name"])))
    Random(f"{int(seed)}:forage").shuffle(forage)
    Random(f"{int(seed)}:fish").shuffle(fish)
    used: set[str] = set()
    forage_rows = [_forage_entry(fact, i, used) for i, fact in enumerate(forage)]
    fish_rows = [_fish_entry(fact, i, used) for i, fact in enumerate(fish)]
    _cover_seasons(forage_rows)
    _cover_times(fish_rows)
    section = {
        "plan_version": PLAN_VERSION,
        "seed": int(seed),
        "fishing": opts["fishing"] and has_fish(farm_map),
        "forage": forage_rows,
        "fish": fish_rows,
        "spots": spots_for(farm_map, seed),
        "notes": notes,
    }
    if has_sea(farm_map):
        with_beach(section, facts)
    return section


def extend(stored: dict[str, Any], facts: Any) -> tuple[dict[str, Any], list[str]]:
    """The stored plan with the pictures of ``facts`` it does not have yet appended (a fish
    added to the packs later). Nothing of what is there changes. Returns (plan, names added)."""
    out = copy.deepcopy(stored)
    used = {str(row["id"]) for key in ("forage", "fish") for row in out.get(key, [])}
    added: list[str] = []
    for key, make in (("forage", _forage_entry), ("fish", _fish_entry)):
        rows = out.setdefault(key, [])
        have = {str(row.get("asset", "")) for row in rows}
        new = [f for f in (facts or {}).get(key, []) if str(f.get("asset", "")) not in have]
        for fact in sorted(new, key=lambda f: str(f.get("asset", ""))):
            entry = make(dict(fact), len(rows), used)
            rows.append(entry)
            added.append(str(entry["name"]))
    return out, added


def check(section: dict[str, Any]) -> list[str]:
    """What is wrong with a plan (an empty list for a good one): a season with nothing to
    forage, a time of a season at which no fish bites, two things of one id."""
    problems: list[str] = []
    forage = [f for f in section.get("forage", []) if not _of_beach(f)]
    fish = [f for f in section.get("fish", []) if not _of_beach(f)]
    for season in SEASONS:
        if not any(season in f["seasons"] for f in forage):
            problems.append(f"{season}: nothing to forage")
        for time in TIMES:
            if not any(season in f["seasons"] and time in f["times"] for f in fish):
                problems.append(f"{season}, {time}: no fish bites")
    seen: set[str] = set()
    for row in [*section.get("forage", []), *section.get("fish", [])]:
        if row["id"] in seen:
            problems.append(f"{row['id']}: listed twice")
        seen.add(row["id"])
    return problems


def summary(section: dict[str, Any]) -> str:
    """One line for the log: "4 things to forage at 8 places, 3 fish (the rod is sold)"."""
    rod = "the rod is sold" if section.get("fishing") else "no fishing"
    return (
        f"{len(section.get('forage', []))} things to forage at {len(section.get('spots', []))} "
        f"places, {len(section.get('fish', []))} fish ({rod})"
    )


def forage_file(section: dict[str, Any]) -> dict[str, Any]:
    """What ``game/data/forage.json`` holds for a plan (the builder writes the same): the things
    and the fish without what only the planner needs."""

    def rows(key: str) -> list[dict[str, Any]]:
        return [
            {k: copy.deepcopy(v) for k, v in row.items() if k not in ("asset", "color")}
            for row in section.get(key, [])
        ]

    return {"forage": rows("forage"), "fish": rows("fish")}


def stored_in(world: Any) -> dict[str, Any] | None:
    """The plan in a world plan (``farm.forage``), or None."""
    found = ((world or {}).get("farm") or {}).get("forage")
    return found if isinstance(found, dict) else None


def store(farm: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    """The ``farm`` section (a copy) with the plan in it, beside the crops and the map."""
    out = copy.deepcopy(farm)
    out["forage"] = copy.deepcopy(section)
    return out


def for_project(
    stored: dict[str, Any] | None,
    options: Any,
    seed: int,
    facts: Any = None,
    farm_map: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """The plan a generation uses: a fresh one while the project has none (``stored`` is the
    ``farm.forage`` of its plan file, or None), else the stored one, never planned again, with
    what the packs have gained. ``fishing`` follows the option and the farm's map every time.
    The places follow the map while it can still change: a stored plan without places gets them
    once the farm has a map, and places that are no free cells of the map any more (the farm
    was planned again before its map was built) are chosen again. Returns (section, notes)."""
    opts = normalized(options)
    if stored and stored.get("forage") and stored.get("fish") is not None:
        section, added = extend(stored, facts)
        free = set(free_cells(farm_map)) if farm_map else set()
        if farm_map and not (section.get("spots") and {_cell(c) for c in section["spots"]} <= free):
            section["spots"] = spots_for(farm_map, int(section.get("seed", seed)))
        section["fishing"] = opts["fishing"] and has_fish(farm_map)
        if has_sea(farm_map):
            added += with_beach(section, facts)
        notes = [f"The farm kept its fish and forage; added: {', '.join(added)}."] if added else []
        return section, notes
    fresh = plan(opts, seed, facts, farm_map)
    return fresh, list(fresh["notes"])

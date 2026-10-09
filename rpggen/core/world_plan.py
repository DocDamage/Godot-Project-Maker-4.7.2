"""A world of connected maps (T13.20): the areas of ``starter_map.areas`` laid on a grid, joined
by door pairs, with chests, enemies, decorations and one key before the gate that closes the cave.

``plan`` is a pure function of the areas table, the seed and (for the biomes) the catalog. The
result is stored in the project as ``rpggen/world_plan.json`` and **reused**: once any area map
exists the world is never planned again (``reuse``); a new row of the table is appended with
``extend`` and nothing else moves. The Godot recipes read the stored plan and build the areas whose
map does not exist yet.

The village is the starter map: its inside is laid out by the starter-map planner, so its entry in
the plan only has its doors. Every other area is laid out here, cell by cell.
"""

from __future__ import annotations

import copy
import re
from random import Random
from typing import Any

from rpggen.core import lockkey

PLAN_VERSION = 1
PLAN_FILE = "rpggen/world_plan.json"
BIOMES = ("village", "field", "forest", "cave", "shore")
# a biome whose assets are missing becomes the one before it
PREVIOUS = {"shore": "cave", "cave": "forest", "forest": "field", "field": "village"}
VILLAGE_ID = "starter_map"
DEFAULT_SIZE = (32, 20)
MIN_SIZE, MAX_SIZE = 16, 96
MAX_AREAS = 12
KEY_ITEM = "cave_key"
EDGES = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
FACING_IN = {"N": "down", "E": "left", "S": "up", "W": "right"}  # where a player who arrives looks
DECORATIONS = {"village": 0, "field": 10, "forest": 28, "cave": 8, "shore": 6}
DECOR_WORDS = {"forest": ["tree", "bush"], "cave": ["rock", "stone"], "shore": ["shell", "rock"]}
ENEMY_DISTANCE = 6
WATER_BAND = 3
Cell = tuple[int, int]
_SLUG = re.compile(r"[^a-z0-9]+")


class WorldPlanError(ValueError):
    """An areas table that cannot be planned (the message says why)."""


# --------------------------------------------------------------------------- the table


def default_areas() -> list[dict[str, Any]]:
    """What a new table starts with: the village and a field (today's two maps)."""
    return [
        {"name": "Village", "biome": "village"},
        {"name": "Field", "biome": "field", "size": list(DEFAULT_SIZE), "enemies": 2, "chests": 1},
    ]


def slug(name: str) -> str:
    return _SLUG.sub("_", name.strip().lower()).strip("_") or "area"


def normalized(areas: Any) -> list[dict[str, Any]]:
    """The table in its canonical form (``WorldPlanError`` when it cannot be used): at most
    ``MAX_AREAS`` rows, every row a name, a known biome, a size inside the limits and counts of
    0 to 12; names are unique."""
    if not isinstance(areas, list) or not areas:
        raise WorldPlanError("the areas table is empty")
    if len(areas) > MAX_AREAS:
        raise WorldPlanError(f"a world has at most {MAX_AREAS} areas")
    out: list[dict[str, Any]] = []
    names: set[str] = set()
    for row in areas:
        if not isinstance(row, dict):
            raise WorldPlanError("an area is a table of name, biome, size, enemies and chests")
        name = str(row.get("name", "")).strip()
        if not name:
            raise WorldPlanError("every area needs a name")
        if slug(name) in names:
            raise WorldPlanError(f"two areas are called '{name}'")
        names.add(slug(name))
        biome = str(row.get("biome", "field"))
        if biome not in BIOMES:
            raise WorldPlanError(f"'{biome}' is not a biome ({', '.join(BIOMES)})")
        size = row.get("size", list(DEFAULT_SIZE))
        if (
            not isinstance(size, (list, tuple))
            or len(size) != 2
            or not all(isinstance(v, int) and MIN_SIZE <= v <= MAX_SIZE for v in size)
        ):
            raise WorldPlanError(f"the size of '{name}' must be {MIN_SIZE} to {MAX_SIZE} tiles")
        clean: dict[str, Any] = {"name": name, "biome": biome, "size": [size[0], size[1]]}
        for key, default in (("enemies", 2), ("chests", 1)):
            value = row.get(key, default)
            if not isinstance(value, int) or not 0 <= value <= 12:
                raise WorldPlanError(f"'{key}' of '{name}' must be 0 to 12")
            clean[key] = value
        if row.get("join"):
            clean["join"] = str(row["join"])
        reroll = row.get("reroll", 0)
        if not isinstance(reroll, int) or reroll < 0:
            raise WorldPlanError(f"'reroll' of '{name}' must be 0 or more")
        if reroll:
            clean["reroll"] = reroll  # another arrangement of this area only
        out.append(clean)
    return out


def village_index(areas: list[dict[str, Any]]) -> int:
    """The row that is the starter map: the first village, else the first row."""
    return next((i for i, a in enumerate(areas) if a["biome"] == "village"), 0)


# --------------------------------------------------------------------------- biomes


def _words(text: str) -> set[str]:
    from rpggen.core import classifier

    folders, file_tokens = classifier.tokens(
        text if "." in text.rsplit("/", 1)[-1] else text + ".x"
    )
    return set(folders) | set(file_tokens)


def _ground_with(catalog: Any, words: tuple[str, ...]) -> str:
    """The id of an active GROUND tile asset named or tagged with one of ``words``, or ""."""
    from rpggen.core import catalog as catalog_mod

    for asset in sorted(catalog.assets, key=lambda a: a.id):
        facets = catalog_mod.effective(asset)
        if facets.get("role") != "GROUND" or asset.status in ("UNUSED", "MISSING"):
            continue
        tags = {str(t) for t in facets.get("tags") or []}
        named = _words(asset.path) | tags | {t.removeprefix("surface:") for t in tags}
        if named & set(words):
            return str(asset.id)
    return ""


def _has_role(catalog: Any, roles: tuple[str, ...]) -> bool:
    from rpggen.core import catalog as catalog_mod

    return any(
        catalog_mod.effective(a).get("role") in roles and a.status not in ("UNUSED", "MISSING")
        for a in catalog.assets
    )


def _has_tree(catalog: Any) -> bool:
    from rpggen.core import catalog as catalog_mod

    for obj in catalog.objects:
        if (
            obj.role == "DECORATION"
            and obj.status != "UNUSED"
            and _words(obj.name) & {"tree", "trees"}
        ):
            return True
    return any(
        catalog_mod.effective(a).get("role") == "DECORATION" and _words(a.path) & {"tree", "trees"}
        for a in catalog.assets
    )


def available(biome: str, catalog: Any) -> tuple[bool, str]:
    """(whether the packs have what ``biome`` needs, the ground asset it prefers: "" is the
    packs' first ground). A forest needs tree decorations and prefers grass; a cave needs wall
    or cliff tiles and prefers stone; a shore needs water and prefers sand."""
    if catalog is None or biome in ("village", "field"):
        return True, ""
    if biome == "forest":
        return _has_tree(catalog), _ground_with(catalog, ("grass", "forest", "meadow", "lawn"))
    if biome == "cave":
        ground = _ground_with(catalog, ("stone", "cave", "rock", "dungeon"))
        return _has_role(catalog, ("WALL", "CLIFF")), ground
    return _has_role(catalog, ("WATER",)), _ground_with(catalog, ("sand", "beach", "shore"))


def resolve_biome(wanted: str, catalog: Any) -> tuple[str, str]:
    """(the biome an area gets, its ground asset): ``wanted``, or the first one before it that
    the packs can fill."""
    biome = wanted
    while True:
        ok, ground = available(biome, catalog)
        if ok or biome not in PREVIOUS:
            return biome, ground
        biome = PREVIOUS[biome]


# --------------------------------------------------------------------------- the grid


def _neighbours(cell: Cell) -> list[tuple[str, Cell]]:
    return [(edge, (cell[0] + STEP[edge][0], cell[1] + STEP[edge][1])) for edge in EDGES]


def _edge_toward(a: Cell, b: Cell) -> str:
    """The edge of an area at ``a`` that faces ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "S" if dy > 0 else "N"


def _free_cell(grid: dict[Cell, str], near: Cell | None, rng: Random) -> Cell:
    """A free grid cell beside ``near`` when there is one, else the free cell nearest to it
    that touches the world (any cell that touches the world when ``near`` is None)."""
    taken = set(grid)
    frontier = sorted({c for cell in taken for _edge, c in _neighbours(cell) if c not in taken})
    if near is None:
        return frontier[rng.randrange(len(frontier))]
    beside = [c for _edge, c in _neighbours(near) if c not in taken]
    if beside:
        return beside[rng.randrange(len(beside))]
    return min(frontier, key=lambda c: (abs(c[0] - near[0]) + abs(c[1] - near[1]), c))


# --------------------------------------------------------------------------- inside an area


def _inside(edge: str, cell: Cell) -> Cell:
    """The floor cell in front of a door in the wall."""
    return (cell[0] - STEP[edge][0], cell[1] - STEP[edge][1])


def _door_cell(area: dict[str, Any], edge: str) -> Cell | None:
    """A cell of the wall on ``edge`` for a new door: the middle first, then outwards, never
    within three cells of a door that edge already has, nor in a corner."""
    w, h = area["size"]
    along = w if edge in ("N", "S") else h
    used = [d["cell"][0 if edge in ("N", "S") else 1] for d in area["doors"] if d["edge"] == edge]
    middle = along // 2
    for offset in range(along):
        for at in (middle + offset, middle - offset):
            if 3 <= at <= along - 4 and all(abs(at - other) >= 3 for other in used):
                if edge == "N":
                    return (at, 0)
                if edge == "S":
                    return (at, h - 1)
                return (0, at) if edge == "W" else (w - 1, at)
    return None


def _corridor(start: Cell, size: tuple[int, int]) -> list[Cell]:
    """The cells from a door's floor cell to the middle of the area (along x, then y)."""
    cx, cy = size[0] // 2, size[1] // 2
    x, y = start
    cells = [(x, y)]
    while x != cx:
        x += 1 if cx > x else -1
        cells.append((x, y))
    while y != cy:
        y += 1 if cy > y else -1
        cells.append((x, y))
    return cells


def _water_rect(area: dict[str, Any]) -> list[int] | None:
    """A band of water along an edge that has no door (a shore), or None."""
    w, h = area["size"]
    with_doors = {d["edge"] for d in area["doors"]}
    for edge in ("S", "E", "N", "W"):
        if edge in with_doors:
            continue
        if edge == "S":
            return [1, h - 1 - WATER_BAND, w - 2, WATER_BAND]
        if edge == "N":
            return [1, 1, w - 2, WATER_BAND]
        if edge == "E":
            return [w - 1 - WATER_BAND, 1, WATER_BAND, h - 2]
        return [1, 1, WATER_BAND, h - 2]
    return None


def lay_out(area: dict[str, Any], rng: Random) -> None:
    """Fill in what stands in an area (not the village): chests, enemies, decorations and, for
    a shore, the water. Nothing stands on the way from a door to the middle, so every door can
    be reached from every other one; enemies keep away from the doors."""
    w, h = area["size"]
    area.pop("reroll", None)  # the caller's: it is part of the seed of ``rng``
    reserved: set[Cell] = set()
    arrivals: list[Cell] = []
    for door in area["doors"]:
        start = (door["spawn"][0], door["spawn"][1])
        arrivals.append(start)
        reserved.update(_corridor(start, (w, h)))
        reserved.update((start[0] + dx, start[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    if area["biome"] == "shore":
        rect = _water_rect(area)
        if rect is not None:
            area["water"] = rect
            reserved.update(
                (x, y)
                for x in range(rect[0], rect[0] + rect[2])
                for y in range(rect[1], rect[1] + rect[3])
            )
    free = [(x, y) for y in range(2, h - 2) for x in range(2, w - 2) if (x, y) not in reserved]
    rng.shuffle(free)

    def take(count: int, far_from_doors: bool = False) -> list[Cell]:
        out: list[Cell] = []
        for cell in list(free):
            if len(out) == count:
                break
            if far_from_doors and any(
                abs(cell[0] - a[0]) + abs(cell[1] - a[1]) < ENEMY_DISTANCE for a in arrivals
            ):
                continue
            out.append(cell)
            free.remove(cell)
        return out

    area["chests"] = [
        {"id": f"{area['id']}_chest_{i + 1:03d}", "cell": list(cell), "gold": 20 + 10 * i,
         "items": [{"item_id": "potion", "qty": 1}]}
        for i, cell in enumerate(take(area.pop("chest_count")))
    ]  # fmt: skip
    area["enemies"] = [
        {"id": f"{area['id']}_enemy_{i + 1:03d}", "cell": list(cell)}
        for i, cell in enumerate(take(area.pop("enemy_count"), far_from_doors=True))
    ]
    area["decorations"] = [list(cell) for cell in take(DECORATIONS[area["biome"]])]
    area["decor_words"] = list(DECOR_WORDS.get(area["biome"], []))


# --------------------------------------------------------------------------- doors


def _door_name(a: dict[str, Any], b: dict[str, Any]) -> str:
    return f"{a['id']}_door_{b['id']}"


def _spawn_name(other: dict[str, Any]) -> str:
    return f"from_{other['id']}"


def connect(a: dict[str, Any], b: dict[str, Any], grid: dict[str, Cell]) -> bool:
    """A door pair between two areas, on the edges that face each other. False when one of the
    edges has no room left for a door."""
    edge_a = _edge_toward(grid[a["id"]], grid[b["id"]])
    edge_b = OPPOSITE[edge_a]
    made = []
    for area, other, edge in ((a, b, edge_a), (b, a, edge_b)):
        cell = _door_cell(area, edge)
        if cell is None:
            return False
        made.append(
            {
                "id": _door_name(area, other),
                "edge": edge,
                "cell": list(cell),
                "spawn": list(_inside(edge, cell)),
                "spawn_id": _spawn_name(other),
                "facing": FACING_IN[edge],
                "to": other["id"],
                "to_map": other["map"],
                "to_spawn": _spawn_name(area),
            }
        )
    a["doors"].append(made[0])
    b["doors"].append(made[1])
    return True


def graph_of(plan: dict[str, Any]) -> dict[str, list[tuple[str, str | None]]]:
    """The areas and their doors as a lock-and-key graph (a door with ``key`` needs that item)."""
    return {
        area["id"]: [(door["to"], door.get("key")) for door in area["doors"]]
        for area in plan["areas"]
    }


def _lock_the_cave(plan: dict[str, Any], rng: Random) -> None:
    """One key before the gate that closes the cave: every door into the first cave gets a gate,
    and the lock-and-key planner puts the key in an area that is reachable without it."""
    cave = next((a for a in plan["areas"] if a["biome"] == "cave" and a["id"] != VILLAGE_ID), None)
    if cave is None:
        return
    entrances = [
        door for area in plan["areas"] for door in area["doors"] if door["to"] == cave["id"]
    ]
    for door in entrances:
        door["key"] = KEY_ITEM
    try:
        found = lockkey.plan(graph_of(plan), [KEY_ITEM], VILLAGE_ID, cave["id"], rng)
    except lockkey.LockKeyError:
        for door in entrances:
            del door["key"]
        plan["notes"].append(
            f"{cave['name']} is not locked: there is no area between the village and it "
            "to hide the key in."
        )
        return
    holder = area_of(plan, found.placements[KEY_ITEM])
    assert holder is not None
    plan["key"] = {"item": KEY_ITEM, "area": holder["id"], "opens": cave["id"]}
    for area in plan["areas"]:
        for door in area["doors"]:
            if door.get("key"):
                area.setdefault("gates", []).append(
                    {
                        "id": f"{area['id']}_gate_{len(area.get('gates', [])) + 1:03d}",
                        "cell": list(door["cell"]),
                        "key_item": KEY_ITEM,
                        "door": door["id"],
                    }
                )


def _place_key(plan: dict[str, Any]) -> None:
    """The key lies in a chest of its area (one more chest when the area has none)."""
    key = plan.get("key")
    if not key:
        return
    holder = area_of(plan, key["area"])
    assert holder is not None
    if not holder["chests"]:
        spare = holder["decorations"].pop() if holder["decorations"] else [2, 2]
        holder["chests"].append(
            {"id": f"{holder['id']}_chest_001", "cell": list(spare), "gold": 0, "items": []}
        )
    holder["chests"][0]["items"].append({"item_id": KEY_ITEM, "qty": 1})
    key["chest"] = holder["chests"][0]["id"]


# --------------------------------------------------------------------------- the plan


def area_of(plan: dict[str, Any], area_id: str) -> dict[str, Any] | None:
    return next((a for a in plan["areas"] if a["id"] == area_id), None)


def _new_area(
    row: dict[str, Any], taken: set[str], catalog: Any, notes: list[str], village: bool
) -> dict[str, Any]:
    if village:
        area_id = VILLAGE_ID
    else:
        area_id = base = slug(row["name"])
        n = 2
        while area_id in taken or area_id == VILLAGE_ID:
            area_id = f"{base}_{n}"
            n += 1
    biome, ground = ("village", "") if village else resolve_biome(row["biome"], catalog)
    if biome != row["biome"] and not village:
        notes.append(
            f"{row['name']}: the packs have nothing for a {row['biome']}, so it is a {biome}."
        )
    area: dict[str, Any] = {
        "id": area_id,
        "name": row["name"],
        "biome": biome,
        "size": list(row["size"]),
        "map": f"game/maps/{area_id}.tscn",
        "ground": ground,
        "doors": [],
    }
    if biome != row["biome"]:
        area["wanted_biome"] = row["biome"]
    if not village:
        area["enemy_count"] = row["enemies"]
        area["chest_count"] = row["chests"]
        area["reroll"] = row.get("reroll", 0)
    return area


def plan(
    areas: Any, seed: int, catalog: Any = None, starter_size: tuple[int, int] = (40, 30)
) -> dict[str, Any]:
    """The world for an areas table: deterministic from the table, the seed and the catalog."""
    rows = normalized(areas)
    rng = Random(f"{int(seed)}:world")
    notes: list[str] = []
    at_village = village_index(rows)
    order = [rows[at_village]] + [r for i, r in enumerate(rows) if i != at_village]
    out: dict[str, Any] = {
        "world_plan_version": PLAN_VERSION,
        "seed": int(seed),
        "areas": [],
        "grid": {},
        "notes": notes,
        "maps": {},
    }
    cells: dict[Cell, str] = {}
    for index, row in enumerate(order):
        area = _new_area(row, {a["id"] for a in out["areas"]}, catalog, notes, index == 0)
        if index == 0:
            area["size"] = [starter_size[0], starter_size[1]]
            cell: Cell = (0, 0)
        elif index == 1:
            cell = (1, 0)  # the village's road leads east
        else:
            cell = _free_cell(cells, None, rng)
        cells[cell] = area["id"]
        out["grid"][area["id"]] = [cell[0], cell[1]]
        out["areas"].append(area)
        if index == 0:
            continue
        grid = {k: (v[0], v[1]) for k, v in out["grid"].items()}
        beside = sorted(cells[c] for _edge, c in _neighbours(cell) if c in cells)
        first = beside[rng.randrange(len(beside))]
        for other_id in beside:
            other = area_of(out, other_id)
            assert other is not None
            if other_id == first or rng.random() < 0.35:  # every area hangs on one neighbour
                connect(other, area, grid)
    _lock_the_cave(out, rng)
    for area in out["areas"][1:]:
        again = area.get("reroll", 0)
        lay_out(area, Random(f"{int(seed)}:{area['id']}" + (f":{again}" if again else "")))
    _place_key(out)
    return out


def extend(
    stored: dict[str, Any], areas: Any, seed: int, catalog: Any = None
) -> tuple[dict[str, Any], list[str]]:
    """The stored plan with the rows of the table it does not have yet appended (by name), each
    joined to the area its ``join`` names (else to any area with room). Returns the new plan and
    the ids of the areas that were added. Nothing of an area that was planned before changes,
    except that it gets the door to its new neighbour."""
    rows = normalized(areas)
    out = copy.deepcopy(stored)
    known = {slug(a["name"]) for a in out["areas"]}
    added: list[str] = []
    for row in rows:
        if slug(row["name"]) in known:
            continue
        rng = Random(f"{int(seed)}:extend:{slug(row['name'])}")
        area = _new_area(row, {a["id"] for a in out["areas"]}, catalog, out["notes"], False)
        cells = {(v[0], v[1]): k for k, v in out["grid"].items()}
        wanted = next(
            (a for a in out["areas"] if slug(a["name"]) == slug(str(row.get("join", "")))), None
        )
        near = (out["grid"][wanted["id"]][0], out["grid"][wanted["id"]][1]) if wanted else None
        cell = _free_cell(cells, near, rng)
        out["grid"][area["id"]] = [cell[0], cell[1]]
        out["areas"].append(area)
        grid = {k: (v[0], v[1]) for k, v in out["grid"].items()}
        partners = [wanted] if wanted else []
        partners += [
            a
            for a in sorted(out["areas"][:-1], key=lambda a: (
                abs(grid[a["id"]][0] - cell[0]) + abs(grid[a["id"]][1] - cell[1]), a["id"]))
            if a is not wanted
        ]  # fmt: skip
        for partner in partners:
            if connect(partner, area, grid):
                break
        lay_out(area, rng)
        known.add(slug(row["name"]))
        added.append(area["id"])
    return out, added


def check(plan_data: dict[str, Any]) -> dict[str, list[str]]:
    """What a validator would say about the plan: ``unreachable`` (areas the village cannot
    reach through door pairs: VAL-027) and ``unpaired`` (doors whose target area or spawn does
    not exist: VAL-028). Both are empty for every plan this module makes."""
    by_id = {a["id"]: a for a in plan_data["areas"]}
    unpaired = []
    for area in plan_data["areas"]:
        for door in area["doors"]:
            target = by_id.get(door["to"])
            if target is None or not any(
                d["spawn_id"] == door["to_spawn"] for d in target["doors"]
            ):
                unpaired.append(door["id"])
    placements = {}
    key = plan_data.get("key")
    if key:
        placements[key["item"]] = key["area"]
    goal = key["opens"] if key else VILLAGE_ID
    found = lockkey.check(graph_of(plan_data), placements, VILLAGE_ID, goal)
    return {"unreachable": [str(n) for n in found.unreachable], "unpaired": sorted(unpaired)}


def reuse(
    stored: dict[str, Any] | None, areas: Any, seed: int, catalog: Any, existing_maps: set[str],
    starter_size: tuple[int, int] = (40, 30),
) -> tuple[dict[str, Any], list[str]]:  # fmt: skip
    """The plan a generation uses: a fresh one while no map of the stored plan exists (the seed
    and the table still count), else the stored one with the new rows appended. ``existing_maps``
    are the project-relative paths of the map files that exist. Returns (plan, notes)."""
    if stored and any(a["map"] in existing_maps for a in stored.get("areas", [])):
        extended, added = extend(stored, areas, seed, catalog)
        notes = [f"The world kept its plan; added: {', '.join(added)}."] if added else []
        return extended, notes
    return plan(areas, seed, catalog, starter_size), []


def summary(plan_data: dict[str, Any]) -> str:
    """One line for the report: "3 areas: Village, Woods (forest), Old mine (cave, locked)"."""
    locked = (plan_data.get("key") or {}).get("opens")
    parts = []
    for area in plan_data["areas"]:
        if area["id"] == VILLAGE_ID:
            parts.append(area["name"])
            continue
        extra = area["biome"] + (", locked" if area["id"] == locked else "")
        parts.append(f"{area['name']} ({extra})")
    count = len(plan_data["areas"])
    return f"{count} area{'s' if count != 1 else ''}: {', '.join(parts)}"


# --------------------------------------------------------------------------- the stored plan


def load(project: Any) -> dict[str, Any] | None:
    """The plan stored in a project folder, or None (no file, or one that cannot be read)."""
    from pathlib import Path

    from rpggen import jsonio, schema
    from rpggen.errors import RpgGenError

    path = Path(project) / PLAN_FILE
    if not path.is_file():
        return None
    try:
        data = jsonio.read(path)
        schema.validate("world_plan", data)
    except (OSError, ValueError, RpgGenError):
        return None
    return data if isinstance(data, dict) else None


def save(project: Any, plan_data: dict[str, Any]) -> None:
    from pathlib import Path

    from rpggen import jsonio, schema

    schema.validate("world_plan", plan_data)
    path = Path(project) / PLAN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonio.write(path, plan_data)


def existing_maps(project: Any, plan_data: dict[str, Any] | None) -> set[str]:
    """The maps of the plan that exist in the project folder (project-relative paths)."""
    from pathlib import Path

    if not plan_data:
        return set()
    return {a["map"] for a in plan_data.get("areas", []) if (Path(project) / a["map"]).is_file()}


def exists(project: Any) -> bool:
    """True when the project has its world already: a stored plan and at least one of its maps
    other than the starter map (the Options page then shows the table disabled)."""
    plan_data = load(project) if project else None
    return any(m != f"game/maps/{VILLAGE_ID}.tscn" for m in existing_maps(project, plan_data))


def for_project(
    project: Any,
    areas: Any,
    seed: int,
    catalog: Any,
    starter_size: tuple[int, ...] = (40, 30),
) -> tuple[dict[str, Any], list[str]]:
    """``reuse`` with the plan and the maps of a project folder (the staging copy)."""
    stored = load(project)
    size = (int(starter_size[0]), int(starter_size[1]))
    # the starter map alone does not fix the world: it is laid out by its own planner
    built = {m for m in existing_maps(project, stored) if m != f"game/maps/{VILLAGE_ID}.tscn"}
    return reuse(stored, areas, seed, catalog, built, size)


def record_hashes(project: Any, plan_data: dict[str, Any], previous: Any = None) -> bool:
    """Note ``map_hash`` for every area map that exists in ``project`` and has no hash yet, and
    that the project before this run (``previous``, a regeneration) did not have: those are the
    maps this run built. True when something was added."""
    from pathlib import Path

    from rpggen.core import ledger

    changed = False
    for area in plan_data["areas"]:
        file = Path(project) / area["map"]
        if area["id"] in plan_data["maps"] or not file.is_file():
            continue
        if previous is not None and (Path(previous) / area["map"]).is_file():
            continue  # it was there before: a person may have made or changed it
        plan_data["maps"][area["id"]] = {"map_hash": ledger.file_hash(file)}
        changed = True
    return changed

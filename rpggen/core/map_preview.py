"""The starter map's layout, in Python (T11.25, T11.26).

``plan`` is the same algorithm as ``MapBuild.plan`` in ``godot_templates/builder/lib/map_build.gd``.
The two are kept equal by ``godot_templates/tests/fixtures/map_plan_cases.json``, which both a
Python test and a GDScript test check. That is why the planner uses only integer arithmetic and
its own small random generator (a 32-bit LCG seeded with an FNV-1a hash), never Godot's or
Python's.

With the default options the plan is the map of every project made before M11, constant for
constant, so existing goldens, smoke steps and the determinism test do not move.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from rpggen.core import config as config_mod

Tile = tuple[int, int]

DEFAULT_HOUSE: Tile = (8, 6)
DEFAULT_SPAWN: Tile = (12, 12)
DEFAULT_NPC: Tile = (16, 12)
DEFAULT_CHEST: Tile = (18, 8)
DEFAULT_ENEMY: Tile = (28, 12)
ENEMY_OFFSET_TILES = 4
DEFAULT_DECOR: list[Tile] = [
    (20, 4), (24, 5), (30, 8), (33, 14), (6, 17), (14, 19), (26, 18), (35, 20),
]  # fmt: skip
ENEMY_MIN_DISTANCE = 8
CLEARANCE = 3
ATTEMPTS = 20


# ------------------------------------------------------------------------------ random numbers


def fnv1a32(text: str) -> int:
    h = 2166136261
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def stream_seed(seed: int, label: str) -> int:
    """The seed of one named random stream of a map (``field_1``, ``starter_map``, ...)."""
    return fnv1a32(f"{seed}:{label}")


class Rng:
    """A 32-bit LCG; ``range`` is inclusive on both ends."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state >> 8

    def range(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo + 1)

    def shuffle(self, items: list[Any]) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.range(0, i)
            items[i], items[j] = items[j], items[i]


# ------------------------------------------------------------------------------------- the plan


def is_default(options: dict[str, Any], archetype: str) -> bool:
    """True when the options (``ground`` aside) are the defaults of ``archetype``."""
    defaults = config_mod.starter_map_defaults(archetype)
    return all(options.get(k) == v for k, v in defaults.items() if k != "ground") and list(
        options.get("size", [])
    ) == list(defaults["size"])


def path_cells(spawn: Tile, door: Tile) -> list[Tile]:
    """A road from the spawn along its row to the door's column, then up to the door."""
    step = 1 if door[0] >= spawn[0] else -1
    cells: list[Tile] = [(x, spawn[1]) for x in range(spawn[0], door[0] + step, step)]
    cells += [(door[0], y) for y in range(door[1], spawn[1] + 1)]
    return cells


def exit_route(spawn: Tile, size: tuple[int, int]) -> tuple[Tile, list[Tile]]:
    """The east exit: (the gap in the east wall, the road to it). The road goes down from the
    spawn to a row three tiles lower, then east to the wall."""
    exit_y = min(spawn[1] + 3, size[1] - 3)
    cells: list[Tile] = [(spawn[0], y) for y in range(spawn[1], exit_y + 1)]
    cells += [(x, exit_y) for x in range(spawn[0] + 1, size[0] - 1)]
    return (size[0] - 1, exit_y), cells


def _rect_contains(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


INTERIOR_MIN_WIDTH = 10
INTERIOR_DEPTH = 8


def interiors_for(count: int, building: dict[str, Any]) -> list[dict[str, Any]]:
    """The interior of each house (T13.12), in the order of the houses: its map id
    (``interior_<n>``), its size in tiles (as wide as the house, at least 10, by 8) and the
    column of its exit on the bottom wall (the house's door column, kept off the corners)."""
    if not building or count <= 0:
        return []
    width = max(INTERIOR_MIN_WIDTH, int(building["size"][0]))
    door = min(max(int(building["door"][0]), 1), width - 2)
    return [
        {"id": f"interior_{n}", "size": [width, INTERIOR_DEPTH], "door": door}
        for n in range(1, count + 1)
    ]


def _default_plan(options: dict[str, Any], building: dict[str, Any]) -> dict[str, Any]:
    size = (int(options["size"][0]), int(options["size"][1]))
    has_building = bool(building) and options["buildings"] > 0
    buildings: list[Tile] = [DEFAULT_HOUSE] if has_building else []
    doors: list[Tile] = []
    path: list[Tile] = []
    if has_building:
        door = (DEFAULT_HOUSE[0] + building["door"][0], DEFAULT_HOUSE[1] + building["door"][1])
        doors.append(door)
        path = path_cells(DEFAULT_SPAWN, door)
    enemies = [
        (DEFAULT_ENEMY[0] + ENEMY_OFFSET_TILES * i, DEFAULT_ENEMY[1])
        for i in range(options["enemies"])
    ]
    gap, exit_path = exit_route(DEFAULT_SPAWN, size)
    return {
        "size": list(size),
        "exit_gap": list(gap),
        "exit_path": [list(c) for c in exit_path],
        "buildings": [list(b) for b in buildings],
        "interiors": interiors_for(len(buildings), building),
        "doors": [list(d) for d in doors],
        "spawn": list(DEFAULT_SPAWN),
        "npcs": [list(DEFAULT_NPC)][: options["npcs"]],
        "chests": [list(DEFAULT_CHEST)][: options["chests"]],
        "enemies": [list(e) for e in enemies],
        "decorations": [list(t) for t in DEFAULT_DECOR],
        "path": [list(c) for c in path],
        "patches": [],
        "legacy_patches": True,  # the recipe paints these with its own seeded generator
        "patch_count": options["ground_patches"],
        "warnings": [],
        "is_default": True,
    }


def plan(
    options: dict[str, Any],
    seed: int,
    building: dict[str, Any] | None = None,
    archetype: str = "turn_based",
) -> dict[str, Any]:
    """The layout of the starter map.

    ``building`` is ``{"size": [w, h], "door": [dx, dy]}`` in tiles (door relative to the
    building's top-left corner, one row below its base) or empty when the packs have none. The
    result holds lists of ``[x, y]`` tiles; every name is also a key of the GDScript plan.
    """
    opts = {**config_mod.starter_map_defaults(archetype), **options}
    building = building or {}
    if is_default(opts, archetype):
        return _default_plan(opts, building)

    w, h = int(opts["size"][0]), int(opts["size"][1])
    rng = Rng(stream_seed(seed, "starter_map"))
    warnings: list[str] = []

    # buildings on a coarse grid with 3 tiles of clearance; the door side stays free
    rects: list[tuple[int, int, int, int]] = []
    doors: list[Tile] = []
    if building and opts["buildings"] > 0:
        bw, bh = int(building["size"][0]), int(building["size"][1])
        cell = (bw + 2 * CLEARANCE, bh + 2 * CLEARANCE)
        candidates: list[Tile] = []
        y = 2
        while y + bh + 2 <= h - 2:
            x = CLEARANCE
            while x + bw + CLEARANCE <= w - 1:
                candidates.append((x, y))
                x += cell[0]
            y += cell[1]
        rng.shuffle(candidates)
        for bx, by in candidates[: opts["buildings"]]:
            rects.append((bx, by, bw, bh))
            doors.append((bx + int(building["door"][0]), by + int(building["door"][1])))

    # the spawn in front of the first door, else the centre
    if doors:
        spawn = (min(max(doors[0][0], 2), w - 3), min(doors[0][1] + 3, h - 3))
    else:
        spawn = (w // 2, h // 2)

    # No road may run through a house: the road to the east exit and the roads to the doors. The
    # first house cannot be in its own way; the others are dropped when they are.
    gap, exit_path = exit_route(spawn, (w, h))
    if len(rects) > 1:
        kept_rects, kept_doors = rects[:1], doors[:1]
        roads: set[Tile] = set(exit_path) | set(path_cells(spawn, doors[0]))
        for rect, door in zip(rects[1:], doors[1:], strict=True):
            road = path_cells(spawn, door)
            hits_road = any(_rect_contains(rect, cx, cy) for cx, cy in roads)
            in_the_way = any(_rect_contains(r, cx, cy) for r in kept_rects for cx, cy in road)
            if not hits_road and not in_the_way:
                kept_rects.append(rect)
                kept_doors.append(door)
                roads.update(road)
        rects, doors = kept_rects, kept_doors
    if building and len(rects) < opts["buildings"]:
        warnings.append(f"buildings: placed {len(rects)} of {opts['buildings']}")

    path: list[Tile] = []
    seen_path: set[Tile] = set()
    for door in doors:
        for cell_ in path_cells(spawn, door):
            if cell_ not in seen_path:
                seen_path.add(cell_)
                path.append(cell_)

    reserved: set[Tile] = set(seen_path)
    reserved.update(exit_path)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            reserved.add((spawn[0] + dx, spawn[1] + dy))
    for door in doors:
        reserved.update({door, (door[0], door[1] + 1), (door[0], door[1] + 2)})

    occupied: set[Tile] = set()

    def inside(x: int, y: int) -> bool:
        return 1 <= x <= w - 2 and 1 <= y <= h - 2

    def in_building(x: int, y: int) -> bool:
        return any(_rect_contains(r, x, y) for r in rects)

    def free(x: int, y: int) -> bool:
        return (
            inside(x, y)
            and not in_building(x, y)
            and (x, y) not in occupied
            and (x, y) not in reserved
        )

    def scan(predicate) -> list[Tile]:  # type: ignore[no-untyped-def]
        return [(x, y) for y in range(1, h - 1) for x in range(1, w - 1) if predicate(x, y)]

    def pick(candidates: list[Tile]) -> Tile | None:
        if not candidates:
            return None
        return candidates[rng.range(0, len(candidates) - 1)]

    # NPCs beside the road
    npcs: list[Tile] = []
    for _ in range(opts["npcs"]):
        beside: list[Tile] = []
        for px, py in path:
            for cand in ((px - 1, py), (px + 1, py)):
                if free(*cand) and cand not in beside:
                    beside.append(cand)
        near = beside or scan(
            lambda x, y: abs(x - spawn[0]) <= 4 and abs(y - spawn[1]) <= 4 and free(x, y)
        )
        found = pick(near)
        if found is None:
            warnings.append(f"npcs: placed {len(npcs)} of {opts['npcs']}")
            break
        occupied.add(found)
        npcs.append(found)

    # chests against a building or the border
    chests: list[Tile] = []
    for _ in range(opts["chests"]):

        def against(x: int, y: int) -> bool:
            if not free(x, y):
                return False
            if x == 1 or y == 1 or x == w - 2 or y == h - 2:
                return True
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if in_building(nx, ny):
                    return True
            return False

        found = pick(scan(against)) or pick(scan(free))
        if found is None:
            warnings.append(f"chests: placed {len(chests)} of {opts['chests']}")
            break
        occupied.add(found)
        chests.append(found)

    # enemies at least 8 tiles from the spawn
    enemies: list[Tile] = []
    for _ in range(opts["enemies"]):

        def far(x: int, y: int, d: int = ENEMY_MIN_DISTANCE) -> bool:
            return free(x, y) and max(abs(x - spawn[0]), abs(y - spawn[1])) >= d

        found = pick(scan(far)) or pick(scan(lambda x, y: far(x, y, 4)))
        if found is None:
            warnings.append(f"enemies: placed {len(enemies)} of {opts['enemies']}")
            break
        occupied.add(found)
        enemies.append(found)

    # decorations anywhere left: never on the road, a door approach or within 1 tile of an entity
    keep_clear: set[Tile] = set(occupied)
    keep_clear.update(seen_path)
    keep_clear.update(exit_path)
    for door in doors:
        keep_clear.update({door, (door[0], door[1] + 1), (door[0], door[1] + 2)})

    def clear_of_entities(x: int, y: int) -> bool:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (x + dx, y + dy) in keep_clear or in_building(x + dx, y + dy):
                    return False
        return True

    decorations: list[Tile] = []
    # Decorations do not block each other, so the candidates are scanned once and each pick only
    # removes itself (the same result as scanning again, much faster on a large map).
    spots = scan(lambda x, y: free(x, y) and clear_of_entities(x, y))
    for _ in range(opts["decorations"]):
        if not spots:
            warnings.append(f"decorations: placed {len(decorations)} of {opts['decorations']}")
            break
        decorations.append(spots.pop(rng.range(0, len(spots) - 1)))

    # patches of other ground, away from the buildings
    patches: list[dict[str, Any]] = []
    for i in range(opts["ground_patches"]):
        pw, ph = rng.range(2, 4), rng.range(2, 4)
        patch_rect: tuple[int, int, int, int] | None = None
        for _attempt in range(ATTEMPTS):
            px, py = rng.range(2, w - pw - 2), rng.range(2, h - ph - 2)
            candidate = (px, py, pw, ph)
            if not any(
                _intersects(candidate, (r[0] - 2, r[1] - 2, r[2] + 4, r[3] + 4)) for r in rects
            ):
                patch_rect = candidate
                break
        if patch_rect is not None:
            patches.append({"rect": list(patch_rect), "index": i})

    return {
        "size": [w, h],
        "exit_gap": list(gap),
        "exit_path": [list(c) for c in exit_path],
        "buildings": [[r[0], r[1]] for r in rects],
        "interiors": interiors_for(len(rects), building),
        "doors": [list(d) for d in doors],
        "spawn": list(spawn),
        "npcs": [list(t) for t in npcs],
        "chests": [list(t) for t in chests],
        "enemies": [list(t) for t in enemies],
        "decorations": [list(t) for t in decorations],
        "path": [list(c) for c in path],
        "patches": patches,
        "legacy_patches": False,
        "patch_count": opts["ground_patches"],
        "warnings": warnings,
        "is_default": False,
    }


# ------------------------------------------------------------------------------------ drawing

MARKER_COLORS = {
    "spawn": (255, 255, 255),
    "npc": (66, 165, 245),
    "enemy": (229, 57, 53),
    "chest": (255, 193, 7),
    "exit": (171, 71, 188),
}
MARKER_ORDER = ("spawn", "npc", "enemy", "chest", "exit")  # the legend's order
FLAT_GROUND = (86, 140, 72)
FLAT_WALL = (70, 70, 80)
FLAT_ROAD = (176, 150, 100)
FLAT_PATCHES = ((140, 110, 80), (160, 160, 150), (205, 190, 125))


@dataclasses.dataclass
class Art:
    """Pictures the preview draws with; every one may be None (a flat colour is used)."""

    tile_px: int = 16
    ground: Image.Image | None = None
    patches: list[Image.Image] = dataclasses.field(default_factory=list)
    wall: Image.Image | None = None
    road: Image.Image | None = None
    building: Image.Image | None = None
    building_size: tuple[int, int] = (0, 0)  # in tiles
    building_door: tuple[int, int] = (0, 0)
    decorations: list[tuple[Image.Image, tuple[int, int]]] = dataclasses.field(
        default_factory=list
    )  # (picture, origin in pixels)


def _tile_images(path: Path, grid: dict[str, Any], count: int) -> list[Image.Image]:
    """The first ``count`` non-empty cells of a tile sheet, row by row."""
    out: list[Image.Image] = []
    with Image.open(path) as opened:
        sheet = opened.convert("RGBA")
    cw, ch = grid["cell"]
    mx, my = grid.get("margin", [0, 0])
    sx, sy = grid.get("separation", [0, 0])
    cols = max(1, (sheet.width - mx + sx) // (cw + sx))
    rows = max(1, (sheet.height - my + sy) // (ch + sy))
    for row in range(rows):
        for col in range(cols):
            x, y = mx + col * (cw + sx), my + row * (ch + sy)
            cell = sheet.crop((x, y, x + cw, y + ch))
            if cell.getchannel("A").getbbox() is not None:
                out.append(cell)
                if len(out) >= count:
                    return out
    return out


def _overworld(catalog: Any) -> Any:
    found = next((t for t in catalog.tilesets if t.name == "overworld"), None)
    return found if found is not None else (catalog.tilesets[0] if catalog.tilesets else None)


def building_geometry(
    region: tuple[int, int], door: list[int] | None, tile: int
) -> tuple[tuple[int, int], tuple[int, int]]:
    """``(size, door)`` in tiles of a building cut from a sheet: ``region`` is its width and
    height in pixels, ``door`` the pixel of its doorway (the middle of the bottom row when none
    is set). The door lies one row below the base."""
    width, height = region
    size = (-(-width // tile), -(-height // tile))
    x, y = door or [width // 2, height - 1]
    return size, (int(x) // tile, int(y) // tile + 1)


def starter_buildings(catalog: Any, building_id: str = "") -> list[Any]:
    """The sheet objects that can be the starter building, the chosen one first."""
    houses = [o for o in catalog.objects if o.status != "UNUSED" and o.role == "BUILDING"]
    if building_id:
        houses = [o for o in houses if o.id == building_id] or houses
    return houses


def building_info_for(catalog: Any, building_id: str = "") -> dict[str, Any]:
    """``building_info`` from the catalog alone: no picture is opened, so the plan of a project
    that has not been generated yet (``rpggen generate --dry-run``) can be made."""
    houses = starter_buildings(catalog, building_id)
    if not houses:
        return {}
    overworld = _overworld(catalog)
    tile = int(overworld.tile_size[0]) if overworld is not None else Art.tile_px
    _x, _y, w, h = houses[0].region
    size, door = building_geometry((w, h), houses[0].door, tile)
    return {"size": list(size), "door": list(door)}


def load_art(catalog: Any, resolver: Any, ground_id: str = "", building_id: str = "") -> Art:
    """Pictures for the preview from a catalog: the ground set, wall, road, the starter building
    and the decorations. ``resolver(asset)`` gives the file of an asset."""
    from rpggen.core import catalog as catalog_mod  # imported late: the planner needs none of it

    art = Art()
    overworld = _overworld(catalog)
    if overworld is not None:
        art.tile_px = int(overworld.tile_size[0])
    sources = sorted(overworld.sources, key=lambda s: s["source_id"]) if overworld else []

    def tiles_for(role: str, asset_id: str = "", count: int = 1) -> list[Image.Image]:
        for source in sources:
            asset = catalog.asset(source["asset"])
            if asset is None or (asset_id and asset.id != asset_id):
                continue
            eff = catalog_mod.effective(asset)
            if not asset_id and eff.get("role") != role:
                continue
            path = resolver(asset)
            grid = eff.get("grid")
            if path is None or not grid:
                continue
            found = _tile_images(Path(path), grid, count)
            if found:
                return found
        return []

    ground = tiles_for("GROUND", ground_id, 4)
    if ground:
        art.ground, art.patches = ground[0], ground[1:]
    wall = tiles_for("WALL")
    art.wall = wall[0] if wall else None
    road = tiles_for("ROAD")
    art.road = road[0] if road else None

    def object_image(obj: Any) -> tuple[Image.Image, tuple[int, int]] | None:
        sheet = catalog.asset(obj.sheet)
        path = resolver(sheet) if sheet is not None else None
        if path is None:
            return None
        x, y, w, h = obj.region
        with Image.open(path) as opened:
            picture = opened.convert("RGBA").crop((x, y, x + w, y + h))
        return picture, (int(obj.origin[0]), int(obj.origin[1]))

    objects = [o for o in catalog.objects if o.status != "UNUSED"]
    houses = starter_buildings(catalog, building_id)
    if houses:
        found = object_image(houses[0])
        if found is not None:
            art.building = found[0]
            art.building_size, art.building_door = building_geometry(
                found[0].size, houses[0].door, art.tile_px
            )
    for obj in objects:
        if obj.role == "DECORATION":
            found = object_image(obj)
            if found is not None:
                art.decorations.append(found)
    return art


def building_info(art: Art) -> dict[str, Any]:
    """The ``building`` argument of ``plan`` for the pictures of ``art`` ({} when none)."""
    if art.building is None:
        return {}
    return {"size": list(art.building_size), "door": list(art.building_door)}


def _scaled(picture: Image.Image, scale: int) -> Image.Image:
    if scale == 1:
        return picture
    return picture.resize((picture.width * scale, picture.height * scale), Image.Resampling.NEAREST)


def render(plan: dict[str, Any], art: Art, scale: int = 2) -> Image.Image:
    """A picture of the plan: ground, patches, the wall border and the exit gap, the road,
    buildings, decorations and coloured markers (start, villagers, enemies, chests). The legend
    is the widget's (``MARKER_NAMES`` has the kinds). It is a preview, not a pixel-exact render."""
    w, h = plan["size"]
    tile = art.tile_px
    px = tile * scale
    canvas = Image.new("RGBA", (w * px, h * px), FLAT_GROUND + (255,))

    def tile_pic(picture: Image.Image | None, colour: tuple[int, int, int]) -> Image.Image:
        base = picture if picture is not None else Image.new("RGBA", (tile, tile), colour + (255,))
        return base.resize((px, px), Image.Resampling.NEAREST)

    ground = tile_pic(art.ground, FLAT_GROUND)
    for y in range(h):
        for x in range(w):
            canvas.paste(ground, (x * px, y * px))
    patch_pics = [tile_pic(p, FLAT_PATCHES[i % 3]) for i, p in enumerate(art.patches)] or [
        tile_pic(None, c) for c in FLAT_PATCHES
    ]
    for patch in plan["patches"]:
        pic = patch_pics[patch["index"] % len(patch_pics)]
        x0, y0, pw, ph = patch["rect"]
        for y in range(y0, y0 + ph):
            for x in range(x0, x0 + pw):
                canvas.paste(pic, (x * px, y * px))
    gap = tuple(plan.get("exit_gap", (-1, -1)))
    wall = tile_pic(art.wall, FLAT_WALL)
    for x in range(w):
        for y in (0, h - 1):
            if (x, y) != gap:
                canvas.paste(wall, (x * px, y * px))
    for y in range(1, h - 1):
        for x in (0, w - 1):
            if (x, y) != gap:
                canvas.paste(wall, (x * px, y * px))
    road = tile_pic(art.road, FLAT_ROAD)
    for cx, cy in [*plan["path"], *plan.get("exit_path", [])]:
        canvas.alpha_composite(road, (cx * px, cy * px))
    draw = ImageDraw.Draw(canvas)
    for bx, by in plan["buildings"]:
        if art.building is not None:
            canvas.alpha_composite(_scaled(art.building, scale), (bx * px, by * px))
        else:
            bw, bh = art.building_size if art.building_size != (0, 0) else (5, 4)
            draw.rectangle(
                [bx * px, by * px, (bx + bw) * px - 1, (by + bh) * px - 1], fill=(150, 90, 60, 255)
            )
    for i, (dx, dy) in enumerate(plan["decorations"]):
        if art.decorations:
            picture, origin = art.decorations[i % len(art.decorations)]
            scaled = _scaled(picture, scale)
            x = dx * px + px // 2 - origin[0] * scale
            y = dy * px + px - scale - origin[1] * scale
            x = min(max(x, 0), canvas.width - scaled.width)
            y = min(max(y, 0), canvas.height - scaled.height)
            canvas.alpha_composite(scaled, (x, y))
        else:
            draw.ellipse(
                [
                    dx * px + px // 4,
                    dy * px + px // 4,
                    dx * px + 3 * px // 4,
                    dy * px + 3 * px // 4,
                ],
                fill=(40, 110, 50, 255),
            )
    marks = [("spawn", [tuple(plan["spawn"])])]
    marks += [
        (kind, [tuple(t) for t in plan[key]])
        for kind, key in (("npc", "npcs"), ("enemy", "enemies"), ("chest", "chests"))
    ]
    if "exit_gap" in plan:
        marks.append(("exit", [tuple(plan["exit_gap"])]))
    for kind, tiles in marks:
        for tx, ty in tiles:
            draw.ellipse(
                [
                    tx * px + px // 5,
                    ty * px + px // 5,
                    tx * px + 4 * px // 5,
                    ty * px + 4 * px // 5,
                ],
                fill=MARKER_COLORS[kind] + (255,),
                outline=(0, 0, 0, 255),
            )
    return canvas


# --------------------------------------------------------------- the map that was really built

ENTITY_COLORS = {
    "player": (255, 255, 255),
    "npc": (66, 165, 245),
    "enemy": (229, 57, 53),
    "chest": (255, 193, 7),
}


def _res_file(root: Path, res_path: str) -> Path:
    return root / res_path.removeprefix("res://")


def render_view(view: dict[str, Any], project_root: Path, scale: int = 2) -> Image.Image:
    """The picture of a map from ``builder/tools/dump_map_view.gd``: the painted cells (their
    tiles are cut from the project's own atlas files), then the entities with the first picture
    they show (a plain marker when they have none)."""
    tile_w, tile_h = view.get("tile_size", [16, 16])
    cells = [c for layer in view["layers"] for c in layer["cells"]]
    width = max((c[0] for c in cells), default=0) + 1
    height = max((c[1] for c in cells), default=0) + 1
    for entity in view.get("entities", []):
        width = max(width, int(entity["x"] // tile_w) + 1)
        height = max(height, int(entity["y"] // tile_h) + 1)
    canvas = Image.new("RGBA", (width * tile_w, height * tile_h), (24, 24, 30, 255))
    sheets: dict[str, Image.Image | None] = {}

    def sheet(res_path: str) -> Image.Image | None:
        if res_path not in sheets:
            try:
                with Image.open(_res_file(project_root, res_path)) as opened:
                    sheets[res_path] = opened.convert("RGBA")
            except (OSError, ValueError):
                sheets[res_path] = None
        return sheets[res_path]

    ordered = sorted(enumerate(view["layers"]), key=lambda item: (item[1].get("z", 0), item[0]))
    for _index, layer in ordered:
        for x, y, source_id, ax, ay, *_rest in layer["cells"]:
            source = view["sources"].get(str(source_id))
            image = sheet(source["path"]) if source else None
            if source is None or image is None:
                continue
            rw, rh = source["region_size"]
            mx, my = source.get("margins", [0, 0])
            sx, sy = source.get("separation", [0, 0])
            left, top = mx + ax * (rw + sx), my + ay * (rh + sy)
            tile = image.crop((left, top, left + rw, top + rh))
            canvas.alpha_composite(tile, (x * tile_w, y * tile_h))
    draw = ImageDraw.Draw(canvas)
    for entity in sorted(view.get("entities", []), key=lambda e: e["y"]):
        sprite = entity.get("sprite") or {}
        image = sheet(sprite["path"]) if sprite else None
        x, y = float(entity["x"]), float(entity["y"])
        if image is not None:
            rx, ry, rw, rh = (int(v) for v in sprite["region"])
            picture = image.crop((rx, ry, rx + rw, ry + rh))
            ox, oy = sprite.get("offset", [0, 0])
            left, top = round(x + ox), round(y + oy)
            if 0 <= left <= canvas.width - rw and 0 <= top <= canvas.height - rh:
                canvas.alpha_composite(picture, (left, top))
                continue
        scene = entity.get("scene", "").lower()
        colour = next((c for key, c in ENTITY_COLORS.items() if key in scene), (180, 180, 180))
        draw.ellipse([x - 4, y - 10, x + 4, y - 2], fill=colour + (255,), outline=(0, 0, 0, 255))
    return _scaled(canvas, scale)


# ------------------------------------------------------------------------------------ side view
# The world of a metroidvania (T14.06): the rooms of ``room_plan.plan`` on their grid of screens,
# a pixel (times ``scale``) per tile. Flat colours: the preview shows the shape of the world, the
# gates and where the abilities lie, not the pack's art.

SIDE_COLORS: dict[str, tuple[int, int, int]] = {
    "#": (92, 84, 110),  # ground
    ".": (28, 26, 46),  # air
    "=": (176, 124, 70),  # a one-way platform
    "H": (140, 96, 54),  # a ladder
    "T": (176, 124, 70),
    "^": (224, 224, 234),  # spikes
    "B": (160, 150, 172),  # a block that breaks
}
SIDE_GAP = 4  # px between two rooms of the grid
SIDE_BACKGROUND = (14, 13, 24)
SIDE_EDGE = (58, 54, 80)
SIDE_MARKERS = {
    "spawn": (255, 255, 255),
    "station": (120, 220, 140),
    "pickup": (255, 193, 7),
    "guardian": (229, 57, 53),
    "enemy": (229, 120, 100),
    "npc": (66, 165, 245),
    "exit": (171, 71, 188),
}
SIDE_MARKER_ORDER = ("spawn", "station", "pickup", "guardian", "enemy", "npc", "exit")


def _grid_bounds(rooms: dict[str, Any]) -> tuple[int, int, int, int]:
    xs = [r["cell"][0] for r in rooms["list"]]
    ys = [r["cell"][1] for r in rooms["list"]]
    return min(xs), min(ys), max(xs), max(ys)


def world_rects(rooms: dict[str, Any], scale: int = 3) -> dict[str, tuple[int, int, int, int]]:
    """Room id -> (left, top, width, height) of its cell in the picture of ``render_world``."""
    if not rooms.get("list"):
        return {}
    w, h = rooms["room_size"]
    left, top, _right, _bottom = _grid_bounds(rooms)
    out = {}
    for room in rooms["list"]:
        gx, gy = room["cell"][0] - left, room["cell"][1] - top
        out[room["id"]] = (
            SIDE_GAP + gx * (w * scale + SIDE_GAP),
            SIDE_GAP + gy * (h * scale + SIDE_GAP),
            w * scale,
            h * scale,
        )
    return out


def room_at(rooms: dict[str, Any], x: float, y: float, scale: int = 3) -> str | None:
    """The room whose cell holds the point (x, y) of the world picture, or None."""
    for ident, (left, top, width, height) in world_rects(rooms, scale).items():
        if left <= x < left + width and top <= y < top + height:
            return ident
    return None


def _room_tiles(room: dict[str, Any]) -> Image.Image:
    rows = room["tiles"]
    picture = Image.new("RGB", (len(rows[0]), len(rows)), SIDE_COLORS["."])
    pixels = picture.load()
    assert pixels is not None
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            pixels[x, y] = SIDE_COLORS.get(char, SIDE_COLORS["."])
    return picture


def _room_markers(room: dict[str, Any]) -> list[tuple[str, list[int]]]:
    """(kind, feet cell) of what stands in a room, in drawing order."""
    out: list[tuple[str, list[int]]] = [("enemy", cell) for cell in room.get("enemies", [])]
    for key in ("spawn", "station", "npc"):
        if key in room:
            out.append((key, room[key]))
    if "pickup" in room:
        out.append(("pickup", room["pickup"]["cell"]))
    if "guardian" in room:
        out.append(("guardian", room["guardian"]["cell"]))
    return out


def _draw_marker(draw: ImageDraw.ImageDraw, x: float, y: float, kind: str, size: float) -> None:
    colour = SIDE_MARKERS[kind] + (255,)
    draw.ellipse([x - size, y - size, x + size, y + size], fill=colour, outline=(0, 0, 0, 255))


def _draw_room(room: dict[str, Any], scale: int) -> Image.Image:
    """One room at ``scale`` px per tile with its markers, exits and gate letters."""
    from rpggen.core import room_plan

    picture = _scaled(_room_tiles(room).convert("RGBA"), scale)
    draw = ImageDraw.Draw(picture)
    w, h = picture.size
    for exit_ in room["exits"]:  # a notch on the edge the exit is in
        x, y = exit_["cell"]
        colour = SIDE_MARKERS["exit"] + (255,)
        if exit_["edge"] in ("E", "W"):
            left = w - scale if exit_["edge"] == "E" else 0
            draw.rectangle(
                [left, (y - 2) * scale, left + scale - 1, (y + 1) * scale - 1], fill=colour
            )
        else:
            top = 0 if exit_["edge"] == "N" else h - scale
            draw.rectangle([x * scale, top, (x + 1) * scale - 1, top + scale - 1], fill=colour)
    dot = max(1.5, scale * 0.75)
    for kind, (x, y) in _room_markers(room):
        _draw_marker(draw, (x + 0.5) * scale, (y + 0.5) * scale, kind, dot)
    for gate in room.get("gates", []):  # the letter of the ability a gate asks for
        letter = room_plan.GATE_LETTERS.get(gate["ability"], "?")
        x, y = gate["cell"]
        at = ((x - 1) * scale, max(0, (y - 7) * scale))
        # the built-in bitmap font is pixel exact; the default one may be an anti-aliased TTF
        font = ImageFont.load_default_imagefont()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw.text((at[0] + dx, at[1] + dy), letter, font=font, fill=(0, 0, 0, 255))
        draw.text(at, letter, font=font, fill=(255, 235, 150, 255))
    return picture


def render_world(rooms: dict[str, Any], scale: int = 3, selected: str | None = None) -> Image.Image:
    """The world as a grid of screens: one cell per room where the plan put it, each drawn tile
    by tile in side-view colours, with a notch per exit, a dot for the start, the save station,
    the pickups, the guardian, the enemies and the hermit, and the letter of every gate
    (``room_plan.GATE_LETTERS``). ``selected`` gets a bright frame."""
    rects = world_rects(rooms, scale)
    if not rects:
        return Image.new("RGBA", (SIDE_GAP * 2, SIDE_GAP * 2), SIDE_BACKGROUND + (255,))
    width = max(left + w for left, _top, w, _h in rects.values()) + SIDE_GAP
    height = max(top + h for _left, top, _w, h in rects.values()) + SIDE_GAP
    canvas = Image.new("RGBA", (width, height), SIDE_BACKGROUND + (255,))
    draw = ImageDraw.Draw(canvas)
    for room in rooms["list"]:
        left, top, w, h = rects[room["id"]]
        canvas.paste(_draw_room(room, scale), (left, top))
        frame = (255, 255, 255, 255) if room["id"] == selected else SIDE_EDGE + (255,)
        draw.rectangle([left - 1, top - 1, left + w, top + h], outline=frame)
    return canvas


def render_room(room: dict[str, Any], scale: int = 8) -> Image.Image:
    """One room large enough to see its platforms (the preview shows it for a clicked room)."""
    return _draw_room(room, scale)


def world_markers(rooms: dict[str, Any]) -> dict[str, int]:
    """How many of each marker kind the world has, for the preview's legend."""
    counts = {kind: 0 for kind in SIDE_MARKER_ORDER}
    for room in rooms.get("list", []):
        counts["exit"] += len(room["exits"])
        for kind, _cell in _room_markers(room):
            counts[kind] += 1
    return counts


# --------------------------------------------------------------------------- tracks (T16.13)

TRACK_COLORS = {
    "g": (76, 150, 70),
    "r": (70, 70, 78),
    "s": (240, 240, 240),
    "d": (150, 112, 70),
    "o": (24, 24, 32),
    "b": (90, 220, 255),
}
TRACK_BARRIER = (38, 84, 44)
TRACK_WALL = (200, 40, 40)
TRACK_CHECKPOINT = (250, 210, 60)
TRACK_PICKUP = (236, 120, 220)
TRACK_CAR = (220, 60, 60)
TRACK_GAP = 6  # px between two tracks of the picture


def render_track(track: dict[str, Any], scale: int = 4, tile: int = 16) -> Image.Image:
    """One track of a racing game's plan at ``scale`` px a tile: the road and what lies on
    it, the barriers, the start line, the checkpoints (dots) and the car with the way it starts.
    ``tile`` is the px of a tile in the plan."""
    rows = track["rows"]
    picture = Image.new("RGB", (len(rows[0]), len(rows)), TRACK_COLORS["g"])
    pixels = picture.load()
    assert pixels is not None
    for x, y, w, h in track.get("barriers", []):
        edge = w == 1 or h == 1
        for py in range(y, min(len(rows), y + h)):
            for px in range(x, min(len(rows[0]), x + w)):
                pixels[px, py] = TRACK_WALL if edge else TRACK_BARRIER
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != "g":
                pixels[x, y] = TRACK_COLORS.get(char, TRACK_COLORS["r"])
    picture = picture.resize(
        (picture.width * scale, picture.height * scale), Image.Resampling.NEAREST
    )
    draw = ImageDraw.Draw(picture)
    k = scale / max(1, tile)
    half = scale * 0.75
    for pickup in track.get("pickups", []):  # under the checkpoints: a small square each
        x, y = pickup["position"][0] * k, pickup["position"][1] * k
        draw.rectangle([x - half, y - half, x + half, y + half], fill=TRACK_PICKUP)
    for point in track.get("checkpoints", []):
        x, y = point["position"][0] * k, point["position"][1] * k
        draw.ellipse([x - scale, y - scale, x + scale, y + scale], fill=TRACK_CHECKPOINT)
    start = track.get("start")
    if start:
        x, y = start["position"][0] * k, start["position"][1] * k
        dx, dy = math.cos(start["heading"]), math.sin(start["heading"])
        reach = scale * 3.0
        draw.line([(x, y), (x + dx * reach, y + dy * reach)], fill=(255, 255, 255), width=2)
        draw.ellipse([x - scale, y - scale, x + scale, y + scale], fill=TRACK_CAR)
    return picture


def track_rects(stages: dict[str, Any], scale: int = 4) -> dict[str, tuple[int, int, int, int]]:
    """Track id -> (left, top, width, height) of its picture in ``render_tracks``."""
    out: dict[str, tuple[int, int, int, int]] = {}
    left = 0
    for track in stages["list"]:
        rows = track["rows"]
        out[track["id"]] = (left, 0, len(rows[0]) * scale, len(rows) * scale)
        left += len(rows[0]) * scale + TRACK_GAP
    return out


def render_tracks(stages: dict[str, Any], scale: int = 4) -> Image.Image:
    """Every track of a racing game's plan, side by side."""
    rects = track_rects(stages, scale)
    width = max(r[0] + r[2] for r in rects.values())
    height = max(r[3] for r in rects.values())
    picture = Image.new("RGB", (width, height), (24, 24, 28))
    for track in stages["list"]:
        left, top, _w, _h = rects[track["id"]]
        picture.paste(render_track(track, scale, int(stages.get("tile", 16))), (left, top))
    return picture


# --------------------------------------------------------------------------- waves (T16.16)

WAVE_BACKGROUND = (16, 18, 34)
WAVE_LANE = (30, 34, 58)
WAVE_BOSS = (214, 92, 214)
WAVE_COLORS = {
    "popcorn": (240, 160, 60),
    "turret": (224, 80, 80),
    "asteroid": (150, 150, 160),
    "carrier": (90, 220, 255),
}
WAVE_ORDER = ("popcorn", "turret", "asteroid", "carrier", "boss")  # the legend's order
WAVE_COLUMN = 30  # px a stage's column is wide at scale 1
WAVE_HEIGHT = 64  # ... and high
WAVE_GAP = 4


def wave_rects(stages: dict[str, Any], scale: int = 2) -> dict[str, tuple[int, int, int, int]]:
    """Stage id -> (left, top, width, height) of its column in ``render_waves``."""
    step = (WAVE_COLUMN + WAVE_GAP) * scale
    return {
        stage["id"]: (i * step, 0, WAVE_COLUMN * scale, WAVE_HEIGHT * scale)
        for i, stage in enumerate(stages["list"])
    }


def render_waves(stages: dict[str, Any], scale: int = 2) -> Image.Image:
    """The wave chart of a shoot 'em up's plan: a column for every stage, read from the bottom
    (where the stage starts) to the top; a mark for every wave, as wide as it has enemies and
    coloured by what comes, and the boss as a block at the top."""
    rects = wave_rects(stages, scale)
    width = max((r[0] + r[2] for r in rects.values()), default=WAVE_COLUMN * scale)
    picture = Image.new("RGB", (width, WAVE_HEIGHT * scale), WAVE_BACKGROUND)
    draw = ImageDraw.Draw(picture)
    head = 10 * scale  # the room of the boss at the top of a column
    for stage in stages["list"]:
        left, top, w, h = rects[stage["id"]]
        draw.rectangle([left, top, left + w - 1, top + h - 1], fill=WAVE_LANE)
        length = max(1.0, float(stage.get("length", 1.0)))
        for wave in stage.get("waves", []):
            part = min(1.0, max(0.0, float(wave.get("at", 0.0)) / length))
            y = top + h - 2 * scale - part * (h - head - 4 * scale)
            mark = min(w - 4 * scale, (3 + 3 * int(wave.get("count", 1))) * scale)
            x = left + (w - mark) / 2
            colour = WAVE_COLORS.get(str(wave.get("enemy")), WAVE_COLORS["popcorn"])
            draw.rectangle([x, y - scale, x + mark - 1, y + scale - 1], fill=colour)
        if stage.get("boss"):
            draw.rectangle(
                [left + 3 * scale, top + 2 * scale, left + w - 3 * scale - 1, top + head - scale],
                fill=WAVE_BOSS,
            )
    return picture


# --------------------------------------------------------------------------- stages (T16.16)

STRIP_SKY = (28, 30, 52)
STRIP_ARENA = (52, 34, 60)
STRIP_TILES = {"#": (104, 92, 120), "=": (166, 122, 76), "^": (222, 74, 74)}
STRIP_CHUNK = (44, 47, 74)  # the line between two chunks
STRIP_MARKERS = {
    "start": (96, 160, 232),
    "enemy": (236, 120, 70),
    "pickup": (90, 220, 255),
    "boss": WAVE_BOSS,
    "grapple": (250, 214, 90),
}
STRIP_ORDER = ("start", "enemy", "pickup", "boss", "grapple")
STRIP_GAP = 3  # px between two stages of the picture
ARENA_CHUNKS = 2  # stage_plan.ARENA_CHUNKS (that module imports this one's neighbours)


def grapple_points(tiles: list[str]) -> list[tuple[int, int]]:
    """The cells of a stage a hook can hold on to from below: a solid tile or a plank with air
    under it (the ground and what stands on it have none)."""
    return [
        (x, y)
        for y, row in enumerate(tiles[:-1])
        for x, char in enumerate(row)
        if char in "#=" and tiles[y + 1][x] == "."
    ]


def strip_rects(stages: dict[str, Any], scale: int = 2) -> dict[str, tuple[int, int, int, int]]:
    """Stage id -> (left, top, width, height) of its strip in ``render_stage_strip``."""
    out: dict[str, tuple[int, int, int, int]] = {}
    top = 0
    for stage in stages["list"]:
        tiles = stage.get("tiles") or ["."]
        out[stage["id"]] = (0, top, len(tiles[0]) * scale, len(tiles) * scale)
        top += len(tiles) * scale + STRIP_GAP
    return out


def render_stage_strip(stages: dict[str, Any], scale: int = 2) -> Image.Image:
    """Every stage of a run and gun's plan as a strip seen from the side, one under the other:
    the ground, the planks and the spikes of its chunks, where the soldier starts, where the
    enemies and the weapons come, the boss in its arena, and (for a soldier that does not jump)
    the blocks its arm can hold on to."""
    rects = strip_rects(stages, scale)
    width = max((r[2] for r in rects.values()), default=scale)
    height = max((r[1] + r[3] for r in rects.values()), default=scale)
    picture = Image.new("RGB", (width, height), SIDE_BACKGROUND)
    tile = max(1, int(stages.get("tile", 16)))
    cols = max(1, int(stages.get("chunk_cols", 20)))
    k = scale / tile
    dot = max(2.0, scale * 1.5)
    draw = ImageDraw.Draw(picture)
    for stage in stages["list"]:
        tiles = stage.get("tiles") or ["."]
        _left, top, w, h = rects[stage["id"]]
        strip = Image.new("RGB", (len(tiles[0]), len(tiles)), STRIP_SKY)
        pixels = strip.load()
        assert pixels is not None
        arena = len(tiles[0]) - ARENA_CHUNKS * cols
        for y, row in enumerate(tiles):
            for x, char in enumerate(row):
                if char in STRIP_TILES:
                    pixels[x, y] = STRIP_TILES[char]
                elif x >= arena:
                    pixels[x, y] = STRIP_ARENA
                elif x % cols == 0 and x:
                    pixels[x, y] = STRIP_CHUNK
        if not stages.get("jump", True):
            for x, y in grapple_points(tiles):
                pixels[x, y] = STRIP_MARKERS["grapple"]
        picture.paste(strip.resize((w, h), Image.Resampling.NEAREST), (0, top))
        marks: list[tuple[Any, str, float]] = [
            (wave["position"], "pickup" if wave.get("enemy") == "pickup" else "enemy", dot)
            for wave in stage.get("waves", [])
            if wave.get("position")
        ]
        if stage.get("start"):
            marks.append((stage["start"], "start", dot))
        if stage.get("boss"):
            floor = next((y for y, row in enumerate(tiles) if row[-1] == "#"), len(tiles) - 1)
            marks.append(([(len(tiles[0]) - cols * 0.5) * tile, floor * tile], "boss", dot * 2.0))
        for position, kind, size in marks:  # a mark stands on its place: the feet are the point
            mx, my = float(position[0]) * k, top + float(position[1]) * k - size
            draw.ellipse([mx - size, my - size, mx + size, my + size], fill=STRIP_MARKERS[kind])
    return picture

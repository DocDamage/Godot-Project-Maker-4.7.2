"""Packs that describe themselves in JSON: Gridwright's isometric kits (2026-10-25).

Gridwright's packs (*Isometric Tiles*, *City*, *Interiors*, *Dungeon & Caves*, ... and the
characters of *Isometric Characters*, *Monsters*, *Animals*, *Army* and the two creators) are
drawn on one grid, a ground diamond of 32 x 16 px at 1x, each at 1x, 2x and 3x, and say what
every picture is in JSON beside them. Measuring the pictures read them wrong (the 3x copies as
the tiles, the 1x ones as copies of the sheets), so this reader takes the pack at its word:

* **A tile kit** has a manifest (``isometric.json``) whose ``sprites`` give every piece its
  ``file`` (at 1x), ``size``, ``footprint`` (cells along col and row), ``anchor`` (the back
  corner of the cells it stands on, at the height of the ground) and ``height``, and for some
  ``frame``, ``joins`` (fences, roofs: NE = 1, SE = 2, SW = 4, NW = 8), ``corners`` (paths),
  ``up`` (ramps), ``wall`` (the edge it stands on or hangs from), ``on_storey`` and ``shadow``.
  A flat piece (a floor, a path, a shore of water) is a tile of the ground; a fence a tile along
  the sides it joins; a wall a tile on its edge, a door one with an opening; a tree, a prop, a
  crop and a building things standing on their cells. The ``origin`` is the middle of the cell
  nearest the camera (``iso_tileset.stand``), the ``rise`` the height of the anchor.
* **What is stacked** (2026-10-26) is a tile with the facet ``stack``, painted on a height
  layer of the level (a TileMapLayer drawn higher by its height, ``rpg_project_tools``): a
  block (``block``) and a ramp or a stair (``ramp``, its tag ``up:<side>`` and its facet
  ``ramp``: [low, high, side], T18.20) of the ground, a
  storey of a building (``storey``, its tags ``facade:``, ``level:`` and ``storey:``), a roof
  (``roof``), what stands on a roof (``on_roof``), an awning or a sign on a storey's face
  (``on_storey``, ``face:``), a lantern or a picture on a wall (``on_wall``, ``wall:<side>``),
  and what lies over another tile (``overlay``: shore foam, waterfalls, mist, mine rails, road
  markings). ``lift`` is how high a piece raises what stands on it (a block 16 px, a storey
  20), what a height layer above it is drawn at. A block's ``side_terrain`` is what it is made
  of (``surface_word``): its sides are the faces of raised ground of that surface (T18.20).
* **What moves**: the frames of a piece (``_f1`` to ``_f4``) are one tile that Godot animates
  (``tile_frames``, ``tile_fps``) or one thing whose strip is put together from them
  (``idle_down``). A door, a gate or a siege engine whose frames are poses (``open_degrees``,
  ``raised_degrees``, ``arm_degrees``) is a tile a pose, or a thing that plays them once.
  ``shadow`` names the picture drawn under a thing or a character.
* **A character** has a JSON of its own (``Sheets/1x/knight/knight.json``) with its ``cell``,
  its ``anchor`` (the feet), its ``rows`` (the eight directions, ``s`` first) and an
  ``animations`` table: a sheet each, of ``frames`` columns, with its ``fps`` and ``loop``. The
  character is one asset, the picture of its first animation; the others are the sources of
  their animations. Its role is its ``side`` (hero, npc, enemy), else what its JSON says of it
  (``role_of``), else the pack's name's (the animals, the monsters).
* **A creator** (``layers.json``) has layers, a sheet each with every animation side by side:
  they are the pieces of a layered character (``lpc_compose``), a body a build and its clothes,
  hair and weapons the choices; its ready-made characters are characters.
* **The effects** of a character pack (an arrow, bolts, impacts) are sprites that play.

What is set aside is only what another picture of the pack shows again: the 2x and 3x copies
(``other_size``), the sheets that hold the tile kit's pieces (``atlas_copy``), the single frames
a character pack has as well as its sheets (``sheet_frame``), the later frames of an animation
(drawn by its first) and the shadows (drawn under what they belong to). No Qt, no Godot.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.adapters.kenney_atlas import UNUSED_ATLAS_COPY
from rpggen.core.inventory import Inventory, InventoryFile

NAME = "gridwright"
MANIFEST_TAG = "pack_manifest"  # read from the pack's own JSON: no other form replaces it
PROJECTION = "isometric"
USAGE_TILE = "iso_tile"
SCALE = 1  # the size that is read; the others are set aside
DIAMOND = (32, 16)  # px at 1x, when the manifest does not say
JSON_MAX_BYTES = 8 * 1024 * 1024
CONFIDENCE = 0.9
UNUSED_OTHER_SIZE = "other_size"  # pack_forms.OTHER_SIZE
UNUSED_SHADOW = "shadow"
UNUSED_FRAME = "animation_frame"
UNUSED_SHEET_FRAME = "sheet_frame"
UNUSED_SOURCE = "animation_sheet"
_SCALE_FOLDER = re.compile(r"^(\d+)x$")
_FRAME = re.compile(r"_f(\d+)$")
_DIAMOND = re.compile(r"(\d+)\s*x\s*(\d+)")
WORK_FOLDER = "gridwright_strips"
STRIP_DIR = "generated/frame_strips"  # sequences.FRAME_STRIP_DIR: the strips put together
# a manifest's rows, ``s`` (towards the viewer) first, as rpggen names its directions
DIRECTIONS = {
    "s": "down", "sw": "down_left", "w": "left", "nw": "up_left",
    "n": "up", "ne": "up_right", "e": "right", "se": "down_right",
}  # fmt: skip
# the sides of a diamond in rpggen's names (``n`` the upper right, ``e`` the lower right)
JOIN_SIDES = ((1, "n"), (2, "e"), (4, "s"), (8, "w"))
# the screen's directions of a manifest (``ne`` towards row - 1) as the sides of a diamond
SCREEN_SIDES = {"ne": "n", "se": "e", "sw": "s", "nw": "w"}
SIDE_ROLES = {"hero": "PLAYER", "player": "PLAYER", "npc": "NPC", "enemy": "ENEMY"}
PACK_ROLES = (
    (frozenset({"animal", "animals"}), "ANIMAL"),
    (frozenset({"monster", "monsters"}), "ENEMY"),
)
# what a character that names no side is, by what its JSON says of it instead: an animal by its
# group (a pet walks about as a farm animal does but lives in no coop or barn, as in the farm
# reader; of the wild ones the beasts that hunt are enemies), a unit of an army by whether it
# fights, a ready-made character of a creator by the creator it is of
ANIMAL_GROUPS = {"farm": ("ANIMAL", "animal"), "pets": ("DECORATION", "pet"),
                 "pet": ("DECORATION", "pet"), "wild": ("DECORATION", "wild")}  # fmt: skip
PREDATORS = frozenset({"bear", "wolf", "boar"})
HERO_WORDS = frozenset({"hero", "heroes"})
# the effects of a character pack (``Effects/1x/arrow.png``): cells of 32 px, a row a direction
# (in the characters' order) for what flies, one row for what bursts where it happens
EFFECTS_FOLDER = "effects"
EFFECT_CELL = 32
PROJECTILE_WORDS = frozenset({"arrow", "arrows", "bolt", "bolts", "fireball", "missile"})
EFFECT_FPS = 12.0
TILE_FPS = 8.0  # the kits' water, foam, flames and fountains (their READMEs: 4 to 8)
# a piece whose frames are poses, the key that says so, and what the poses do played in turn
POSE_KEYS = {"open_degrees": "open", "raised_degrees": "open", "portcullis_lift": "open",
             "arm_degrees": "use"}  # fmt: skip
# what a manifest's categories hold beside its things: the ground, its blocks, the pieces that
# join (paths, roads, fences, walls), and the pieces of a building stacked on each other
GROUND_CATEGORIES = frozenset({"floors"})
BLOCK_CATEGORIES = frozenset({"blocks"})
LIQUID_CATEGORIES = frozenset({"liquids"})
ROAD_CATEGORIES = frozenset({"paths", "roads"})
RAMP_CATEGORIES = frozenset({"ramps"})
STOREY_CATEGORIES = frozenset({"storeys"})
ROOF_CATEGORIES = frozenset({"roofs"})
ROOFTOP_CATEGORIES = frozenset({"rooftop"})
FACADE_CATEGORIES = frozenset({"facade"})
DOOR_CATEGORIES = frozenset({"doors"})  # a door stands in a wall: a wall piece with an opening
WALL_CATEGORIES = frozenset({"walls"})
OVERLAY_WORDS = frozenset({"foam", "waterfall", "waterfalls", "mist", "rail", "rails"})
WATER_WORDS = frozenset({"water", "cavewater", "ice"})
WALL_EDGES = {"ne": "n", "nw": "w"}  # a wall on the back edge towards row - 1, col - 1
# a post, and a corner where the walls of both back edges meet, stand on the back corner of
# their cell, between the sides n and w (a ``wall`` that names its stuff, ``scrap``, says none)
WALL_POSTS = {"post": "nw", "ne+nw": "nw"}
# the groups of a creator's layers as the parts of a layered character (lpc_compose.PART_ORDER)
GROUP_PARTS = {
    "body": "body", "shoes": "feet", "legs": "legs", "bottom": "legs", "chest": "torso",
    "top": "torso", "gloves": "arms", "cape": "cape", "shoulders": "shoulders",
    "accessory": "neck", "facial": "facial", "hair": "hair", "helmet": "hat",
    "headwear": "hat", "weapon": "weapon", "held": "tools",
}  # fmt: skip
SHADOW_FILES = ("Effects/1x/shadow.png", "Effects/shadow_1x.png")


def _load(root: Path, f: InventoryFile) -> dict[str, Any] | None:
    if f.ext != ".json" or int(getattr(f, "size", 0) or 0) > JSON_MAX_BYTES:
        return None
    try:
        data = json.loads((root / f.path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def is_tile_manifest(data: dict[str, Any]) -> bool:
    sprites = data.get("sprites")
    if not isinstance(sprites, dict) or not sprites:
        return False
    return all(
        isinstance(s, dict) and {"file", "anchor", "footprint"} <= set(s) for s in sprites.values()
    )


def is_character(data: dict[str, Any]) -> bool:
    anims = data.get("animations")
    return (
        isinstance(anims, dict)
        and bool(anims)
        and all(isinstance(a, dict) and "image" in a and "frames" in a for a in anims.values())
        and isinstance(data.get("rows"), list)
        and all(r in DIRECTIONS for r in data["rows"])
        and isinstance(data.get("cell"), list)
        and isinstance(data.get("anchor"), list)
    )


def is_layer_kit(data: dict[str, Any]) -> bool:
    """A creator's ``layers.json``: builds of layers, the animations' columns, the order."""
    anims = data.get("animations")
    return (
        isinstance(data.get("layers"), dict)
        and isinstance(anims, list)
        and all(isinstance(a, dict) and {"name", "frames", "column"} <= set(a) for a in anims)
        and isinstance(data.get("rows"), list)
        and all(r in DIRECTIONS for r in data["rows"])
    )


def _scale(path: str) -> int | None:
    """The scale of the folder a picture lies in (``PNG/2x/...``), None when it says none."""
    for part in path.split("/")[:-1]:
        m = _SCALE_FOLDER.match(part)
        if m:
            return int(m.group(1))
    return None


Manifests = tuple[list[tuple[str, dict]], list[tuple[str, dict]], list[tuple[str, dict]]]


def _manifests(inv: Inventory, root: Path) -> Manifests:
    tiles, characters, layers = [], [], []
    for f in sorted(inv.files, key=lambda f: f.path):
        if f.ext != ".json":
            continue
        data = _load(root, f)
        if data is None:
            continue
        if is_tile_manifest(data):
            tiles.append((f.path, data))
        elif is_character(data):
            characters.append((f.path, data))
        elif is_layer_kit(data):
            layers.append((f.path, data))
    return tiles, characters, layers


def _aside(f: InventoryFile, reason: str) -> AssetFragment:
    w, h = (f.image or {}).get("w", 1), (f.image or {}).get("h", 1)
    facets = {
        "usage": "sprite",
        "frame": [w, h],
        "origin": [w // 2, max(0, h - 1)],
        "role": "NONE",
        "tags": [classifier.UNUSED_TAG + reason],
    }
    return AssetFragment(f.path, facets, CONFIDENCE, "full")


def _diamond(data: dict[str, Any]) -> tuple[int, int]:
    m = _DIAMOND.search(str(data.get("grid", "")))
    return (int(m.group(1)), int(m.group(2))) if m else DIAMOND


def _pair(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, int | float) for v in value)
    ):
        return int(value[0]), int(value[1])
    return default


def _low(height: Any) -> int:
    """The lowest point of a piece's ``height``: the low end of a ramp's [low, high], else 0."""
    if isinstance(height, list):
        return min([int(v) for v in height if isinstance(v, int | float)] or [0])
    return 0


def _top(height: Any) -> int:
    """The highest point of a piece's ``height``: a number, or [low, high] of a ramp."""
    if isinstance(height, list):
        return max([int(v) for v in height if isinstance(v, int | float)] or [0])
    return int(height) if isinstance(height, int | float) else 0


def origin_of(
    anchor: tuple[int, int], footprint: tuple[int, int], diamond: tuple[int, int]
) -> list[int]:
    """The middle of the cell nearest the camera of a piece whose ``anchor`` is the back corner
    of its ``footprint`` (cells along col, to the lower right, and along row, to the lower
    left) on a ground ``diamond``: the point ``iso_tileset.stand`` puts on a cell."""
    half_w, half_h = diamond[0] // 2, diamond[1] // 2
    cols, rows = max(1, footprint[0]) - 1, max(1, footprint[1]) - 1
    return [anchor[0] + half_w * (cols - rows), anchor[1] + half_h * (cols + rows) + half_h]


# the words of a piece's name that say what kind of piece it is, not what it is made of
PIECE_WORDS = frozenset({"block", "blocks", "floor", "floors", "half", "tile", "tiles", "top"})


def surface_word(name: str) -> str:
    """What a piece is made of, by its name: ``block_grass_01`` and ``floor_grass_02`` are
    grass, ``block_sidewalk_03`` sidewalk; "" when the name says nothing more."""
    for word in classifier.name_words(name):
        if word not in PIECE_WORDS and not word.isdigit():
            return word
    return ""


def joins_of(mask: int) -> list[str]:
    return [side for bit, side in JOIN_SIDES if mask & bit]


def project_path(pack_id: str, rel: str) -> str:
    return f"assets/packs/{pack_id}/{rel}"


def tile_facets(
    name: str, sprite: dict[str, Any], diamond: tuple[int, int], pose: bool = False
) -> tuple[dict[str, Any], str]:
    """The facets of one piece of a tile kit, and the reason it is set aside ("" when it is
    used). A later frame (unless the frames are poses: ``pose``) is drawn by the first and a
    shadow under what it belongs to; the rest is used. What the manifest says decides, then
    its category: a ramp, a storey, a roof, what stands on a roof or on a storey's face, what
    hangs on a wall and what lies over another tile are stacked (the module's docstring); a
    floor is ground (water a liquid's), a path or a road a road, a piece that joins or stands on
    a cell's edge a wall (a door one with an opening; a post, or the corner of two walls, on the
    back corner), a block a decoration standing up from the ground, and the rest things
    standing on their cells."""
    category = sprite["file"].split("/")[-2] if "/" in sprite["file"] else ""
    words = {category} | set(classifier.name_words(name))
    frame = sprite.get("frame")
    if isinstance(frame, int) and frame > 1 and not pose:
        return {}, UNUSED_FRAME
    if category == "shadows":
        return {}, UNUSED_SHADOW
    w, h = _pair(sprite.get("size"), (diamond[0], diamond[1]))
    anchor = _pair(sprite.get("anchor"), (w // 2, 0))
    footprint = _pair(sprite.get("footprint"), (1, 1))
    tags = [MANIFEST_TAG]
    if pose and isinstance(frame, int):
        tags.append(f"pose:{frame}")
    facets: dict[str, Any] = {
        "projection": PROJECTION,
        "canvas": [w, h],
        "footprint": [diamond[0], diamond[1]],
        "origin": origin_of(anchor, footprint, diamond),
        "rise": max(0, anchor[1]),
        "tags": tags,
    }
    tile = {**facets, "usage": USAGE_TILE}
    height = sprite.get("height")
    lift = _top(height)

    def stacked(role: str, stack: str, *more: str) -> dict[str, Any]:
        out = {**tile, "role": role, "stack": stack, "tags": [*tags, *more]}
        if lift > 0 and stack in ("block", "ramp", "storey", "roof"):
            out["lift"] = lift
        if isinstance(sprite.get("joins"), int) and joins_of(int(sprite["joins"])):
            out["joins"] = joins_of(int(sprite["joins"]))
        return out

    wall = str(sprite.get("wall") or "")
    if sprite.get("up") or category in RAMP_CATEGORIES:
        up = SCREEN_SIDES.get(str(sprite.get("up") or ""), "n")
        ramp = stacked("GROUND", "ramp", f"up:{up}")
        # its two ends and the side it rises to (T18.20): an actor walks up it
        ramp["ramp"] = [_low(height), lift, up]
        return ramp, ""
    if category in STOREY_CATEGORIES or "storey" in sprite:
        said = [f"{k}:{sprite[k]}" for k in ("facade", "level", "storey") if sprite.get(k)]
        return stacked("BUILDING", "storey", *said), ""
    if category in ROOF_CATEGORIES:
        return stacked("BUILDING", "roof"), ""
    if category in ROOFTOP_CATEGORIES:
        return stacked("DECORATION", "on_roof"), ""
    if category in FACADE_CATEGORIES or sprite.get("on_storey"):
        face = SCREEN_SIDES.get(str(sprite.get("face") or ""), "")
        return stacked("DECORATION", "on_storey", *([f"face:{face}"] if face else [])), ""
    overlay = bool(sprite.get("overlay")) and category not in ROAD_CATEGORIES
    if overlay or "tile" in sprite or words & OVERLAY_WORDS:
        if words & {"rail", "rails"} and isinstance(sprite.get("joins"), int):
            return stacked("ROAD", "overlay", "rail"), ""  # a mine's track: a road of rails
        return stacked("DECORATION", "overlay"), ""
    door = category in DOOR_CATEGORIES and wall in WALL_EDGES
    hung = sprite.get("on_wall") or (
        wall and category not in WALL_CATEGORIES and not door and "against" not in sprite
    )
    if hung:
        side = WALL_EDGES.get(wall, "")
        return stacked("DECORATION", "on_wall", *([f"wall:{side}"] if side else [])), ""
    if category in ROAD_CATEGORIES or "corners" in sprite:
        out = {**tile, "role": "ROAD"}
        if isinstance(sprite.get("joins"), int) and joins_of(int(sprite["joins"])):
            out["joins"] = joins_of(int(sprite["joins"]))
        return out, ""
    if (
        footprint == (1, 1)
        and (isinstance(sprite.get("joins"), int) or wall)
        and "against" not in sprite
    ):
        out = {**tile, "role": "WALL"}
        sides = joins_of(int(sprite["joins"])) if isinstance(sprite.get("joins"), int) else []
        if sides:
            out["joins"] = sides  # a piece that joins nothing stands alone: a plain wall tile
        elif wall in WALL_EDGES:
            out["edge"] = WALL_EDGES[wall]
            if door:
                out["tags"] = [*tags, "door"]
        elif wall in WALL_POSTS:
            out["post"] = WALL_POSTS[wall]
            if wall != "post":
                out["tags"] = [*tags, "corner"]
        return out, ""
    flat = height in (0, None) and anchor[1] == 0
    if category in GROUND_CATEGORIES or (category in LIQUID_CATEGORIES and flat):
        if words & WATER_WORDS and "ice" not in words:
            return {**tile, "role": "WATER"}, ""
        if category in LIQUID_CATEGORIES and "ice" not in words:
            return {**tile, "role": "DECORATION", "tags": [*tags, "liquid"]}, ""  # lava
        return {**tile, "role": "GROUND"}, ""
    if category in BLOCK_CATEGORIES | LIQUID_CATEGORIES:
        # it stands up from the ground and what stands on it stands higher (``lift``); its sides
        # are the faces of raised ground of its surface (T18.20: a terrain of sides)
        block = stacked("DECORATION", "block", "block")
        surface = surface_word(name)
        if surface and category in BLOCK_CATEGORIES:
            block["side_terrain"] = surface
        return block, ""
    # a thing of the kit's scenery (a car parked in a street, a tombstone, a chest): only its
    # buildings are houses, and nothing is an item to pick up because it is small
    role = "BUILDING" if category == "buildings" else "DECORATION"
    return {**facets, "usage": "sprite", "frame": [w, h], "stands_on": list(footprint),
            "role": role}, ""  # fmt: skip


def frame_groups(sprites: dict[str, Any]) -> dict[str, list[tuple[int, str]]]:
    """The pieces of a manifest by the name they have without their frame (``fountain_f2`` ->
    ``fountain``), each list [(frame, name)] in the order of the frames."""
    groups: dict[str, list[tuple[int, str]]] = {}
    for name, sprite in sprites.items():
        m = _FRAME.search(name)
        key = name[: m.start()] if m else name
        number = int(m.group(1)) if m else int(sprite.get("frame") or 1)
        groups.setdefault(key, []).append((number, name))
    return {k: sorted(v) for k, v in groups.items()}


def _work(ctx: AdapterContext) -> Path:
    work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
    work.mkdir(parents=True, exist_ok=True)
    return work


def compose(root: Path, work: Path, rows: list[list[InventoryFile]], cell: tuple[int, int]) -> str:
    """Puts pictures together into one sheet (``rows`` of cells of ``cell``, each picture on the
    bottom of its cell, in the middle) in ``work``, named by what is in it. Returns the name."""
    columns = max(len(r) for r in rows)
    text = "\n".join([f"{columns}x{len(rows)}:{cell[0]}x{cell[1]}"] + [
        ",".join(f.sha256 for f in r) for r in rows
    ])  # fmt: skip
    name = hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"
    dest = work / name
    if not dest.is_file():
        sheet = Image.new("RGBA", (columns * cell[0], len(rows) * cell[1]), (0, 0, 0, 0))
        for y, row in enumerate(rows):
            for x, f in enumerate(row):
                with Image.open(root / f.path) as opened:
                    picture = opened.convert("RGBA")
                at = (
                    x * cell[0] + (cell[0] - picture.width) // 2,
                    (y + 1) * cell[1] - picture.height,
                )
                sheet.paste(picture, at)
        partial = dest.with_suffix(".partial")
        sheet.save(partial, format="PNG")
        partial.replace(dest)
    return name


def thing_animations(
    frames: list[str], pose_action: str, strip: str, fps: float = TILE_FPS
) -> dict[str, Any]:
    """The animations of a thing of a tile kit whose frames make one strip (``strip``, its
    project path): a loop of them all (``idle_down``), or, when they are poses, the first
    standing still and the poses played once (``<action>_down``)."""
    cells = [[i, 0] for i in range(len(frames))]
    if pose_action:
        return {
            "idle_down": {"frames": cells[:1], "fps": fps, "loop": True, "source": strip},
            f"{pose_action}_down": {"frames": cells, "fps": fps, "loop": False, "source": strip},
        }
    return {"idle_down": {"frames": cells, "fps": fps, "loop": True, "source": strip}}


def character_facets(
    rel: str, data: dict[str, Any], pack_id: str, pack_role: str
) -> tuple[str, dict[str, Any]] | None:
    """(the pack path of the character's picture, its facets) from its JSON at ``rel``."""
    folder = posixpath.dirname(rel)
    anims = data["animations"]
    first = "idle" if "idle" in anims else sorted(anims)[0]
    own = posixpath.join(folder, str(anims[first]["image"]))
    cw, ch = _pair(data.get("cell"), (64, 64))
    ax, ay = _pair(data.get("anchor"), (cw // 2, ch - 1))
    animations: dict[str, Any] = {}
    for action in sorted(anims):
        spec = anims[action]
        image = posixpath.join(folder, str(spec["image"]))
        count = int(spec.get("frames") or 0)
        if count < 1:
            continue
        for row, direction in enumerate(data["rows"]):
            entry: dict[str, Any] = {
                "frames": [[c, row] for c in range(count)],
                "fps": float(spec.get("fps") or 8),
                "loop": bool(spec.get("loop", True)),
            }
            if image != own:
                entry["source"] = project_path(pack_id, image)
            animations[f"{action}_{DIRECTIONS[direction]}"] = entry
    if not animations:
        return None
    facets: dict[str, Any] = {
        "usage": "sprite",
        "grid": {"cell": [cw, ch], "margin": [0, 0], "separation": [0, 0]},
        "frame": [cw, ch],
        "origin": [ax, ay],
        "directions": 8 if len(data["rows"]) >= 8 else 4,
        "animations": animations,
        "projection": PROJECTION,
        "tags": [MANIFEST_TAG],
    }
    role, tag = role_of(data, pack_role)
    if role:
        facets["role"] = role
    if tag:
        facets["tags"] = [MANIFEST_TAG, tag]
    return own, facets


def pack_folder(rel: str) -> str:
    """The folder of the pack a file of a character pack lies in: what is above ``Sheets`` or
    ``Characters`` (the creators' ready-made ones)."""
    parts = rel.split("/")
    for i, part in enumerate(parts):
        if part in ("Sheets", "Characters", "Layers"):
            return "/".join(parts[:i])
    return posixpath.dirname(rel)


def shadow_of(rel: str, data: dict[str, Any], files: dict[str, InventoryFile]) -> str:
    """The pack path of the shadow a character is drawn over: the one its JSON names, else the
    pack's (``SHADOW_FILES``); "" when there is none."""
    base = pack_folder(rel)
    said = data.get("shadow")
    wanted = [str(said)] if isinstance(said, str) and "<" not in said else []
    for candidate in [*wanted, *SHADOW_FILES]:
        path = posixpath.join(base, candidate) if base else candidate
        if path in files:
            return path
    return ""


def effect_facets(path: str, size: tuple[int, int]) -> dict[str, Any] | None:
    """The facets of a sheet of a character pack's effects: a row a direction of what flies (an
    arrow, a bolt, a fireball: ``fly_<direction>``, looping), one row of what bursts where it
    happens (an impact, a heal: ``idle_down``, once); the middle of a cell is the point it is
    put at. None for a picture of another shape."""
    w, h = size
    cell = EFFECT_CELL
    if w < cell or w % cell or h not in (cell, cell * len(DIRECTIONS)):
        return None
    count = w // cell
    words = set(classifier.name_words(posixpath.splitext(posixpath.basename(path))[0]))
    flies = bool(words & PROJECTILE_WORDS)
    animations: dict[str, Any] = {}
    if h == cell:
        animations["idle_down"] = {
            "frames": [[c, 0] for c in range(count)], "fps": EFFECT_FPS, "loop": flies,
        }  # fmt: skip
    else:
        for row, direction in enumerate(DIRECTIONS.values()):
            animations[f"{'fly' if flies else 'idle'}_{direction}"] = {
                "frames": [[c, row] for c in range(count)], "fps": EFFECT_FPS, "loop": True,
            }  # fmt: skip
    return {
        "usage": "sprite",
        "grid": {"cell": [cell, cell], "margin": [0, 0], "separation": [0, 0]},
        "frame": [cell, cell],
        "origin": [cell // 2, cell // 2],
        "directions": 8 if h > cell else 1,
        "animations": animations,
        "projection": PROJECTION,
        "role": "PROJECTILE" if flies else "EFFECT",
        "tags": [MANIFEST_TAG],
    }


def role_of(data: dict[str, Any], pack_role: str) -> tuple[str, str]:
    """(the role of a character from its own JSON, a tag that says more): its ``side``, else
    an animal's ``group``, a unit's ``unit`` (it fights or it does not), a creator's ready-made
    character (its ``layers``: a hero of a hero creator, else a person of the village), else the
    pack's role (``pack_role``: "HERO" for a creator of heroes)."""
    side = SIDE_ROLES.get(str(data.get("side") or "").casefold(), "")
    if side:
        return side, ""
    group = str(data.get("group") or "").casefold()
    if group in ANIMAL_GROUPS:
        if group == "wild" and str(data.get("species") or "").casefold() in PREDATORS:
            return "ENEMY", "wild"
        return ANIMAL_GROUPS[group]
    anims = data.get("animations") or {}
    if data.get("unit"):
        return ("ENEMY" if "attack" in anims else "NPC"), ""
    if isinstance(data.get("layers"), list):
        return ("PLAYER" if pack_role == "HERO" else "NPC"), ""
    return ("" if pack_role == "HERO" else pack_role), ""


def layer_pieces(
    rel: str, data: dict[str, Any], files: dict[str, InventoryFile]
) -> list[AssetFragment]:
    """The layers of a creator (``layers.json`` at ``rel``) as the pieces of a layered character
    (``lpc_compose``, as the farm reader's): a body and the layers of each build, every one a
    sheet with the creator's animations side by side and a row a direction. The pieces of one
    build of one creator are one character's (its set)."""
    from rpggen.core import lpc_compose

    base = posixpath.dirname(rel)
    cw, ch = _pair(data.get("cell"), (64, 64))
    ax, ay = _pair(data.get("anchor"), (cw // 2, ch - 1))
    animations: dict[str, Any] = {}
    for spec in data["animations"]:
        count, column = int(spec.get("frames") or 0), int(spec.get("column") or 0)
        for row, direction in enumerate(data["rows"]):
            animations[f"{spec['name']}_{DIRECTIONS[direction]}"] = {
                "frames": [[column + c, row] for c in range(count)],
                "fps": float(spec.get("fps") or 8),
                "loop": bool(spec.get("loop", True)),
            }
    said = data.get("styles")
    styles: dict[str, Any] = said if isinstance(said, dict) else {}
    out: list[AssetFragment] = []
    for build, groups in sorted(data["layers"].items()):
        if not isinstance(groups, dict):
            continue
        owner = f"{base}/{build}"
        for style, colours in sorted(groups.items()):
            group = str((styles.get(style) or {}).get("group") or style.split("_", 1)[0])
            part = GROUP_PARTS.get(group, group)
            for colour, file in sorted((colours or {}).items()):
                path = posixpath.join(base, str(file))
                if path not in files:
                    continue
                kind = (
                    [lpc_compose.BODY_TAG]
                    if part == "body"
                    else [lpc_compose.LAYER_TAG, lpc_compose.PART_TAG + part]
                )
                tags = [*kind, lpc_compose.LAYERED_TAG, lpc_compose.LAYERED_UNUSED,
                        lpc_compose.LAYERED_SET_TAG + owner, MANIFEST_TAG,
                        f"piece:{style}_{colour}"]  # fmt: skip
                facets = {
                    "usage": "sprite",
                    "role": "NONE",
                    "grid": {"cell": [cw, ch], "margin": [0, 0], "separation": [0, 0]},
                    "frame": [cw, ch],
                    "origin": [ax, ay],
                    "directions": 8 if len(data["rows"]) >= 8 else 4,
                    "animations": animations,
                    "projection": PROJECTION,
                    "tags": tags,
                }
                out.append(AssetFragment(path, facets, CONFIDENCE, "full"))
    return out


# a shadow of a character pack (``shadow``, ``shadow_large``, ``shadow_1x``), not the cultist's
# ``shadow_bolt``
_SHADOW_FILE = re.compile(r"^shadow(?:_(?:small|medium|large|\d+x))?$")
_EFFECT_FILE = re.compile(r"^(?P<base>.+?)(?:_(?P<dir>se|sw|ne|nw|s|w|n|e))?(?:_(?P<n>\d+))?$")


class GridwrightAdapter:
    name = NAME
    priority = 42  # a reader of a whole format: before the cutter, the facings and isometric

    def match(self, inv: Inventory, root: Path) -> float:
        tiles, characters, layers = _manifests(inv, root)
        return 1.0 if tiles or characters or layers else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        tiles, characters, layer_kits = _manifests(inv, root)
        if not tiles and not characters and not layer_kits:
            return result
        files = {f.path: f for f in inv.files if f.path not in ctx.claimed}
        done: set[str] = set()

        def add(fragment: AssetFragment) -> None:
            if fragment.path in files and fragment.path not in done:
                done.add(fragment.path)
                result.assets.append(fragment)

        def strip_of(rows: list[list[InventoryFile]], cell: tuple[int, int]) -> str:
            name = compose(root, _work(ctx), rows, cell)
            target = f"{STRIP_DIR}/{name}"
            result.generated[target] = str(_work(ctx) / name)
            return target

        diamond = DIAMOND
        for rel, data in tiles:
            base = posixpath.dirname(rel)
            diamond = _diamond(data)
            sprites = data["sprites"]
            groups = frame_groups(sprites)
            group_of = {name: key for key, members in groups.items() for _n, name in members}
            for name in sorted(sprites):
                sprite = sprites[name]
                path = posixpath.join(base, str(sprite["file"]))
                if path not in files:
                    continue
                members = groups[group_of[name]]
                pose_key = next((k for _n, m in members for k in POSE_KEYS if k in sprites[m]), "")
                tiles_posed = bool(pose_key) and facets_are_tiles(sprites, members, diamond)
                facets, reason = tile_facets(name, sprite, diamond, pose=tiles_posed)
                if reason:
                    add(_aside(files[path], reason))
                    continue
                later = [
                    posixpath.join(base, str(sprites[m]["file"]))
                    for n, m in members
                    if m != name and n > (int(sprite.get("frame") or 1))
                ]
                later = [p for p in later if p in files]
                posed = any(str(t).startswith("pose:") for t in facets.get("tags", []))
                if later and not posed:  # a pose of a door is a tile of its own
                    if facets["usage"] == USAGE_TILE:
                        facets["tile_frames"] = [project_path(inv.pack_id, p) for p in later]
                        facets["tile_fps"] = TILE_FPS
                    else:
                        w, h = facets["frame"]
                        frames = [files[path], *(files[p] for p in later)]
                        strip = strip_of([frames], (w, h))
                        facets["grid"] = {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]}
                        facets["animations"] = thing_animations(
                            [f.path for f in frames], POSE_KEYS.get(pose_key, ""), strip
                        )
                shadow = sprite.get("shadow")
                if isinstance(shadow, str) and isinstance(sprites.get(shadow), dict):
                    shadow_path = posixpath.join(base, str(sprites[shadow]["file"]))
                    if shadow_path in files:
                        facets["shadow"] = project_path(inv.pack_id, shadow_path)
                add(AssetFragment(path, facets, CONFIDENCE, "full"))
            # the sheets hold the pieces again: the single pictures are used
            for path, f in files.items():
                if f.kind == "image" and path.startswith(base + "/Sheets/"):
                    add(_aside(f, UNUSED_ATLAS_COPY))
        words = set(classifier.name_words(inv.pack_id.replace("_", " ")))
        for path in files:
            words.update(classifier.name_words(path.split("/", 1)[0]))
        pack_role = next((role for said, role in PACK_ROLES if words & said), "")
        if not pack_role and words & HERO_WORDS:
            pack_role = "HERO"
        sources: set[str] = set()
        character_roots: set[str] = set()
        for rel, data in characters:
            if (_scale(rel) or SCALE) != SCALE:
                continue
            read = character_facets(rel, data, inv.pack_id, pack_role)
            if read is None or read[0] not in files:
                continue
            own, facets = read
            shadow = shadow_of(rel, data, files)
            if shadow:
                facets["shadow"] = project_path(inv.pack_id, shadow)
            add(AssetFragment(own, facets, CONFIDENCE, "full"))
            folder = posixpath.dirname(rel)
            sources.update(
                posixpath.join(folder, str(a["image"])) for a in data["animations"].values()
            )
            character_roots.add(rel.split("/", 1)[0])
        for rel, data in layer_kits:
            for fragment in layer_pieces(rel, data, files):
                add(fragment)
            character_roots.add(rel.split("/", 1)[0])
        for path in sorted(sources):
            if path in files:
                add(_aside(files[path], UNUSED_SOURCE))
        result.pack_warnings.append(
            f"{classifier.ISOMETRIC_MARK}{diamond[0]}x{diamond[1]}:manifest"
        )
        effects: dict[tuple[str, str], list[tuple[str, int, InventoryFile]]] = {}
        for path, f in sorted(files.items()):
            if f.kind != "image" or path in done:
                continue
            parts = path.split("/")
            scale = _scale(path)
            if scale is not None and scale != SCALE:
                add(_aside(f, UNUSED_OTHER_SIZE))
            elif parts[0] in character_roots and len(parts) > 1 and parts[1] == "PNG":
                add(_aside(f, UNUSED_SHEET_FRAME))  # the frames the sheets hold
            elif _SHADOW_FILE.match(posixpath.splitext(parts[-1])[0]):
                add(_aside(f, UNUSED_SHADOW))  # drawn under the characters (``shadow``)
            elif EFFECTS_FOLDER in {p.casefold() for p in parts[:-1]}:
                if "frames" in parts[:-1]:
                    add(_aside(f, UNUSED_SHEET_FRAME))  # the frames the effect sheets hold
                    continue
                stem = posixpath.splitext(parts[-1])[0]
                m = _EFFECT_FILE.match(stem)
                if m and (m.group("dir") or m.group("n")):
                    key = (posixpath.dirname(path), m.group("base"))
                    effects.setdefault(key, []).append(
                        (m.group("dir") or "", int(m.group("n") or 1), f)
                    )
                    continue
                effect = effect_facets(
                    path, ((f.image or {}).get("w", 0), (f.image or {}).get("h", 0))
                )
                if effect is not None:
                    add(AssetFragment(path, effect, CONFIDENCE, "full"))
        for (_folder, _base), pictures in sorted(effects.items()):
            self._effect_of_pictures(pictures, add, strip_of)
        return result

    @staticmethod
    def _effect_of_pictures(
        pictures: list[tuple[str, int, InventoryFile]], add: Any, strip_of: Any
    ) -> None:
        """An effect drawn a picture a direction and a frame (the hero creator's
        ``arrow_<dir>.png``, ``bolt_arcane_<dir>_<n>.png``, ``impact_arcane_<n>.png``): one asset,
        the first picture, whose sheet is put together from them all in the shape of the other
        packs' effects (a row a direction, in the characters' order)."""
        dirs = sorted({d for d, _n, _f in pictures})
        numbers = sorted({n for _d, n, _f in pictures})
        by = {(d, n): f for d, n, f in pictures}
        order = [d for d in DIRECTIONS if d in dirs] if dirs != [""] else [""]
        if dirs != [""] and len(order) != len(DIRECTIONS):
            for _d, _n, f in pictures:
                add(_aside(f, UNUSED_SOURCE))  # an effect missing a direction: none of it
            return
        rows = [[by[(d, n)] for n in numbers if (d, n) in by] for d in order]
        if any(len(r) != len(numbers) for r in rows):
            return
        first = rows[0][0]
        cell = (
            (first.image or {}).get("w", EFFECT_CELL),
            (first.image or {}).get("h", EFFECT_CELL),
        )
        strip = strip_of(rows, cell)
        facets = effect_facets(first.path, (cell[0] * len(numbers), cell[1] * len(rows)))
        if facets is None:
            return
        for spec in facets["animations"].values():
            spec["source"] = strip
        add(AssetFragment(first.path, facets, CONFIDENCE, "full"))
        for row in rows:
            for f in row:
                if f is not first:
                    add(_aside(f, UNUSED_SOURCE))


def facets_are_tiles(
    sprites: dict[str, Any], members: list[tuple[int, str]], diamond: tuple[int, int]
) -> bool:
    """True when the pieces of a group whose frames are poses are tiles (a door in a wall: each
    pose a tile of its own); a thing that moves through its poses plays them instead."""
    first = sprites[members[0][1]]
    facets, _reason = tile_facets(members[0][1], {**first, "frame": 1}, diamond)
    return facets.get("usage") == USAGE_TILE

"""Packs that describe themselves in JSON: Gridwright's isometric kits (2026-10-25).

Gridwright's packs (*Isometric Tiles*, *City*, *Interiors*, *Dungeon & Caves*, ... and the
characters of *Isometric Characters*, *Monsters*, *Animals*, *Army* and the two creators) are
drawn on one grid, a ground diamond of 32 x 16 px at 1x, each at 1x, 2x and 3x, and say what
every picture is in JSON beside them. Measuring the pictures read them wrong (the 3x copies as
the tiles, the 1x ones as copies of the sheets), so this reader takes the pack at its word:

* **A tile kit** has a manifest (``isometric.json``) whose ``sprites`` give every piece its
  ``file`` (at 1x), ``size``, ``footprint`` (cells along col and row), ``anchor`` (the back
  corner of the cells it stands on, at the height of the ground) and ``height``, and for some
  ``frame``, ``joins`` (fences: NE = 1, SE = 2, SW = 4, NW = 8), ``corners`` (paths), ``up``
  (ramps) and ``shadow``. A flat piece (a floor, a path, a shore of water) is a tile of the
  ground; a fence a tile along the sides it joins; a block, a half block and lava are tiles
  that stand up from the ground (decorations, as a block of stone is); a tree, a prop, a crop
  and a building are things standing on their cells. The ``origin`` is the middle of the cell
  nearest the camera (``iso_tileset.stand``), the ``rise`` the height of the anchor.
* **A character** has a JSON of its own (``Sheets/1x/knight/knight.json``) with its ``cell``,
  its ``anchor`` (the feet), its ``rows`` (the eight directions, ``s`` first) and an
  ``animations`` table: a sheet each, of ``frames`` columns, with its ``fps`` and ``loop``. The
  character is one asset, the picture of its first animation; the others are the sources of
  their animations. Its role is its ``side`` (hero, npc, enemy), else the pack's name's (the
  animals, the monsters).

What is set aside: the 2x and 3x copies (``other_size``), the sheets that hold the tile
kit's pieces again (``atlas_copy``), the shadow sprites, the frames of an animated tile after
its first (rpggen's isometric tiles do not animate), the pieces laid over another tile (shore
foam, waterfalls) and the ramps and stairs (its maps are flat), the single frames a character
pack has as well as its sheets, and the layers of the creators (their ready-made characters
are read). The pictures of the effects are left to the other readers. No Qt, no Godot.
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any

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
UNUSED_OVERLAY = "overlay_tile"
UNUSED_RAMP = "ramp"
UNUSED_SHEET_FRAME = "sheet_frame"
UNUSED_SOURCE = "animation_sheet"
UNUSED_LAYER = "layered_piece"
UNUSED_STACKED = "building_piece"
UNUSED_ON_WALL = "on_wall"
_SCALE_FOLDER = re.compile(r"^(\d+)x$")
_FRAME = re.compile(r"_f(\d+)$")
_DIAMOND = re.compile(r"(\d+)\s*x\s*(\d+)")
# a manifest's rows, ``s`` (towards the viewer) first, as rpggen names its directions
DIRECTIONS = {
    "s": "down", "sw": "down_left", "w": "left", "nw": "up_left",
    "n": "up", "ne": "up_right", "e": "right", "se": "down_right",
}  # fmt: skip
# the sides of a diamond in rpggen's names (``n`` the upper right, ``e`` the lower right)
JOIN_SIDES = ((1, "n"), (2, "e"), (4, "s"), (8, "w"))
SIDE_ROLES = {"hero": "PLAYER", "player": "PLAYER", "npc": "NPC", "enemy": "ENEMY"}
PACK_ROLES = (
    (frozenset({"animal", "animals"}), "ANIMAL"),
    (frozenset({"monster", "monsters"}), "ENEMY"),
)
# what a manifest's categories hold beside its things: the ground, its blocks, the pieces that
# join (paths, roads, fences, walls), and the pieces of a building stacked on each other
GROUND_CATEGORIES = frozenset({"floors"})
BLOCK_CATEGORIES = frozenset({"blocks"})
LIQUID_CATEGORIES = frozenset({"liquids"})
ROAD_CATEGORIES = frozenset({"paths", "roads"})
STACKED_CATEGORIES = frozenset({"storeys", "roofs", "rooftop", "facade"})
OVERLAY_WORDS = frozenset({"foam", "waterfall", "waterfalls", "mist", "rail", "rails"})
WATER_WORDS = frozenset({"water", "cavewater", "ice"})
WALL_EDGES = {"ne": "n", "nw": "w"}  # a wall on the back edge towards row - 1, col - 1


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


def _scale(path: str) -> int | None:
    """The scale of the folder a picture lies in (``PNG/2x/...``), None when it says none."""
    for part in path.split("/")[:-1]:
        m = _SCALE_FOLDER.match(part)
        if m:
            return int(m.group(1))
    return None


def _manifests(inv: Inventory, root: Path) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    tiles, characters = [], []
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
    return tiles, characters


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


def origin_of(
    anchor: tuple[int, int], footprint: tuple[int, int], diamond: tuple[int, int]
) -> list[int]:
    """The middle of the cell nearest the camera of a piece whose ``anchor`` is the back corner
    of its ``footprint`` (cells along col, to the lower right, and along row, to the lower
    left) on a ground ``diamond``: the point ``iso_tileset.stand`` puts on a cell."""
    half_w, half_h = diamond[0] // 2, diamond[1] // 2
    cols, rows = max(1, footprint[0]) - 1, max(1, footprint[1]) - 1
    return [anchor[0] + half_w * (cols - rows), anchor[1] + half_h * (cols + rows) + half_h]


def joins_of(mask: int) -> list[str]:
    return [side for bit, side in JOIN_SIDES if mask & bit]


def tile_facets(
    name: str, sprite: dict[str, Any], diamond: tuple[int, int]
) -> tuple[dict[str, Any], str]:
    """The facets of one piece of a tile kit, and the reason it is set aside ("" when it is
    used). What the manifest says decides, then its category: a later frame, a shadow, a ramp,
    an overlay, a piece of a building stacked on others and a thing hung on a wall are set
    aside; a floor is ground (water a liquid's), a path or a road a road, a piece that joins or
    stands on a cell's edge a wall, a block a decoration standing up from the ground, and the
    rest things standing on their cells."""
    category = sprite["file"].split("/")[-2] if "/" in sprite["file"] else ""
    words = {category} | set(classifier.name_words(name))
    frame = sprite.get("frame")
    if isinstance(frame, int) and frame > 1:
        return {}, UNUSED_FRAME
    if category == "shadows":
        return {}, UNUSED_SHADOW
    if sprite.get("up") or category == "ramps":
        return {}, UNUSED_RAMP
    if sprite.get("overlay") and category not in ROAD_CATEGORIES or "tile" in sprite:
        return {}, UNUSED_OVERLAY
    if words & OVERLAY_WORDS:
        return {}, UNUSED_OVERLAY
    if category in STACKED_CATEGORIES or sprite.get("on_storey") or "storey" in sprite:
        return {}, UNUSED_STACKED
    wall = str(sprite.get("wall") or "")
    if sprite.get("on_wall") or (wall and category != "walls"):
        return {}, UNUSED_ON_WALL
    w, h = _pair(sprite.get("size"), (diamond[0], diamond[1]))
    anchor = _pair(sprite.get("anchor"), (w // 2, 0))
    footprint = _pair(sprite.get("footprint"), (1, 1))
    facets: dict[str, Any] = {
        "projection": PROJECTION,
        "canvas": [w, h],
        "footprint": [diamond[0], diamond[1]],
        "origin": origin_of(anchor, footprint, diamond),
        "rise": max(0, anchor[1]),
        "tags": [MANIFEST_TAG],
    }
    tile = {**facets, "usage": USAGE_TILE}
    height = sprite.get("height")
    flat = height in (0, None) and anchor[1] == 0
    if category in ROAD_CATEGORIES or "corners" in sprite:
        out = {**tile, "role": "ROAD"}
        if isinstance(sprite.get("joins"), int):
            out["joins"] = joins_of(int(sprite["joins"]))
        return out, ""
    if footprint == (1, 1) and (isinstance(sprite.get("joins"), int) or wall):
        out = {**tile, "role": "WALL"}
        if isinstance(sprite.get("joins"), int):
            out["joins"] = joins_of(int(sprite["joins"]))
        elif wall in WALL_EDGES:
            out["edge"] = WALL_EDGES[wall]
        elif wall:
            out["post"] = True  # a corner of two walls, or the end of one
        return out, ""
    if category in GROUND_CATEGORIES or (category in LIQUID_CATEGORIES and flat):
        if words & WATER_WORDS and "ice" not in words:
            return {**tile, "role": "WATER"}, ""
        if category in LIQUID_CATEGORIES and "ice" not in words:
            return {**tile, "role": "DECORATION", "tags": [MANIFEST_TAG, "liquid"]}, ""  # lava
        return {**tile, "role": "GROUND"}, ""
    if category in BLOCK_CATEGORIES | LIQUID_CATEGORIES:
        # it stands up from the ground: no ground of a flat map, a block as a block of stone is
        return {**tile, "role": "DECORATION", "tags": [MANIFEST_TAG, "block"]}, ""
    # a thing of the kit's scenery (a car parked in a street, a tombstone, a chest): only its
    # buildings are houses, and nothing is an item to pick up because it is small
    role = "BUILDING" if category == "buildings" else "DECORATION"
    return {**facets, "usage": "sprite", "frame": [w, h], "stands_on": list(footprint),
            "role": role}, ""  # fmt: skip


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
                entry["source"] = f"assets/packs/{pack_id}/{image}"
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
    role = SIDE_ROLES.get(str(data.get("side") or "").casefold(), "") or pack_role
    if role:
        facets["role"] = role
    return own, facets


class GridwrightAdapter:
    name = NAME
    priority = 42  # a reader of a whole format: before the cutter, the facings and isometric

    def match(self, inv: Inventory, root: Path) -> float:
        tiles, characters = _manifests(inv, root)
        return 1.0 if tiles or characters else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        tiles, characters = _manifests(inv, root)
        if not tiles and not characters:
            return result
        files = {f.path: f for f in inv.files if f.path not in ctx.claimed}
        done: set[str] = set()

        def add(fragment: AssetFragment) -> None:
            if fragment.path in files and fragment.path not in done:
                done.add(fragment.path)
                result.assets.append(fragment)

        diamond = DIAMOND
        for rel, data in tiles:
            base = posixpath.dirname(rel)
            diamond = _diamond(data)
            for name in sorted(data["sprites"]):
                sprite = data["sprites"][name]
                path = posixpath.join(base, str(sprite["file"]))
                if path not in files:
                    continue
                facets, reason = tile_facets(name, sprite, diamond)
                add(
                    _aside(files[path], reason)
                    if reason
                    else AssetFragment(path, facets, CONFIDENCE, "full")
                )
            # the sheets hold the pieces again: the single pictures are used
            for path, f in files.items():
                if f.kind == "image" and path.startswith(base + "/Sheets/"):
                    add(_aside(f, UNUSED_ATLAS_COPY))
        words = set(classifier.name_words(inv.pack_id.replace("_", " ")))
        for path in files:
            words.update(classifier.name_words(path.split("/", 1)[0]))
        pack_role = next((role for said, role in PACK_ROLES if words & said), "")
        sources: set[str] = set()
        character_roots: set[str] = set()
        for rel, data in characters:
            if (_scale(rel) or SCALE) != SCALE:
                continue
            read = character_facets(rel, data, inv.pack_id, pack_role)
            if read is None or read[0] not in files:
                continue
            own, facets = read
            add(AssetFragment(own, facets, CONFIDENCE, "full"))
            folder = posixpath.dirname(rel)
            sources.update(
                posixpath.join(folder, str(a["image"])) for a in data["animations"].values()
            )
            character_roots.add(rel.split("/", 1)[0])
        for path in sorted(sources):
            if path in files:
                add(_aside(files[path], UNUSED_SOURCE))
        if tiles or characters:
            result.pack_warnings.append(
                f"{classifier.ISOMETRIC_MARK}{diamond[0]}x{diamond[1]}:manifest"
            )
        for path, f in sorted(files.items()):
            if f.kind != "image" or path in done:
                continue
            parts = path.split("/")
            scale = _scale(path)
            if scale is not None and scale != SCALE:
                add(_aside(f, UNUSED_OTHER_SIZE))
            elif parts[0] in character_roots and len(parts) > 1 and parts[1] == "PNG":
                add(_aside(f, UNUSED_SHEET_FRAME))  # the frames the sheets hold
            elif parts[0] in character_roots and len(parts) > 1 and parts[1] == "Layers":
                add(_aside(f, UNUSED_LAYER))
            elif posixpath.basename(path).startswith("shadow"):
                add(_aside(f, UNUSED_SHADOW))
        return result

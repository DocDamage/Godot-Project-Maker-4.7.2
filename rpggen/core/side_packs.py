"""What real side-view packs need after the readers (T17.32).

``catalog.assemble`` calls the functions of this module for the packs it found to be seen from
the side (``classifier.made_for`` says ``side``):

* ``characters`` — a character read from its action folders (``adapters.action_frames``) that
  only a folder called *characters* made an NPC, or no word made anything, is an **enemy**: a
  side-view pack's creatures are what the hero fights; its hero says *hero*, *heroine* or
  *player*, a villager says so too.
* ``props`` — a picture or a thing cut from a sheet in a folder of props is a decoration,
  never a character (pozak's *Dark Castle Interior* had 200 NPC objects).
* ``parallax_sets`` — the pictures of a folder of background layers are one **parallax set**,
  ordered far to near: by the words of their names (sky, back, far, clouds, mid, near, front),
  else by their numbers (``1 (2)`` ... ``1 (5)``), turned round when the nearest by number is
  the opaque one, else by how much of each is see-through (the opaque one is the farthest).
  Each picture gets ``parallax:<n>`` and ``parallax_set:<folder>``; a room or stage uses one
  set (``parallax_recipe.gd``: the set nearest the ground's sheet).
* ``character_sheets`` — a tile sheet whose name or folder says characters, in a cell of its
  own (Kenney's ``tilemap-characters``, 24 px beside tiles of 18), is characters: its cells in
  runs of alike pictures, each run a character with ``idle`` and ``walk``; the first of the
  sheet is the player (Kenney draws the players first), the others enemies.
* ``read_tiles`` (after every pack) — the roles of the cells of each tile sheet that nothing
  named (``side_tiles``), the **side-view terrains** of the pieces a pack names by their place
  (``grassLeft``, ``grassMid``, ``grassRight``, ``grassCenter``, ``grassHalf_left``,
  ``grassCliff_left``, ``grassHill_right``), put into a sheet of their own, and **one tile
  size a pack**: a sheet of another size is cut again at the pack's size when it divides, else
  read as a picture.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import motion, side_tiles
from rpggen.errors import IssueList

UNUSED = "unused_because:"
SAME_AS = "same_as:"
PARALLAX = "parallax:"
PARALLAX_SET = "parallax_set:"
ACTION_TAG = "action_folders"
FOLDER_TAG = "character_folder:"
SAYS_TAG = "says:"
SIDE_TERRAIN = "side"
SIDE_DIR = "generated/side_terrain"
SIDE_TAG = "side_terrain"
PIECE_ASIDE = "terrain_piece"
CHARACTERS_CUT = "characters_cut"
OTHER_SIZE = "other_size"
PREVIEW_PICTURE = "preview_picture"
PREVIEW_WORDS = frozenset({"preview", "previews", "example", "examples", "sample", "mockup",
                           "screenshot", "demo"})  # fmt: skip
CONFIDENCE = 0.85
ENEMY_CONFIDENCE = 0.8

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORDS = re.compile(r"[^0-9a-z]+")


def words(text: str) -> list[str]:
    """The small-letter words of a name, camel case split, a number glued to a word dropped
    (``castleHillRight2`` is castle, hill, right)."""
    out = [w.rstrip("0123456789") for w in _WORDS.split(_CAMEL.sub(" ", text).casefold())]
    return [w for w in out if w]


def _rel(asset: Any, root: str) -> str:
    return asset.path[len(root) + 1 :] if asset.path.startswith(root + "/") else asset.path


def _tags(asset: Any) -> set[str]:
    return {str(t) for t in asset.detected.get("tags") or []}


def _add_tags(asset: Any, *tags: str) -> None:
    asset.detected["tags"] = sorted(_tags(asset) | set(tags))


def _aside(asset: Any, reason: str, same_as: str = "") -> None:
    from rpggen.core import pack_forms

    pack_forms.aside(asset, reason, same_as)


def _set_aside(asset: Any) -> bool:
    return asset.detected.get("role") == "NONE"


# --------------------------------------------------------------------------- characters

ROLE_WORDS = {
    "PLAYER": frozenset({"player", "players", "hero", "heroine", "protagonist"}),
    "BOSS": frozenset({"boss", "bosses"}),
    "NPC": frozenset({"npc", "npcs", "villager", "merchant", "townsfolk", "shopkeeper"}),
}


def characters(assets: list[Any], root: str) -> int:
    """The roles of the action-folder characters of a side-view pack: the one its words call a
    player, a boss or a villager is that, with the confidence of a reader that read its
    animations by name; the others are enemies."""
    changed = 0
    folders: dict[str, str] = {}  # character folder -> the character's first frame
    for asset in assets:
        for tag in _tags(asset):
            if tag.startswith(FOLDER_TAG):
                folders[tag[len(FOLDER_TAG) :] + "/"] = _rel(asset, root)
    base_rel = {a.id: _rel(a, root) for a in assets if "#" not in a.id}
    for asset in assets:
        # the character again in its folder (a strip, a sheet cut in parts, an Aseprite file
        # drawn): set aside, the character is read from its frames
        rel = base_rel.get(asset.id.split("#", 1)[0], _rel(asset, root))
        home = next((f for f in folders if rel.startswith(f)), None)
        if (
            home is not None
            and ACTION_TAG not in _tags(asset)
            and asset.detected.get("role") in CHARACTER_ROLES | {"DECORATION"}
            and asset.detected_by not in ("profile", "learned")
        ):
            _aside(asset, "same_frames", folders[home])
            continue
        if ACTION_TAG not in _tags(asset) or asset.detected_by in ("profile", "learned"):
            continue
        said = set(words(_rel(asset, root))) | {
            t[len(SAYS_TAG) :] for t in _tags(asset) if t.startswith(SAYS_TAG)
        }
        role = next((r for r, ws in ROLE_WORDS.items() if said & ws), "ENEMY")
        asset.detected["role"] = role
        asset.detected["tags"] = sorted(t for t in _tags(asset) if not t.startswith(PARALLAX))
        asset.detected.pop("roles_alt", None)
        asset.confidence = max(
            asset.confidence, CONFIDENCE if role != "ENEMY" else ENEMY_CONFIDENCE
        )
        changed += 1
    return changed


# --------------------------------------------------------------------------- props

PROP_WORDS = frozenset({"prop", "props", "decor", "decoration", "decorations"})
CHARACTER_ROLES = frozenset({"NPC", "PLAYER", "ENEMY", "BOSS"})


def is_prop_path(rel: str) -> bool:
    folders = rel.split("/")[:-1]
    return any(set(words(f)) & PROP_WORDS for f in folders) or bool(
        set(words(posixpath.splitext(posixpath.basename(rel))[0])) & PROP_WORDS
    )


def props(assets: list[Any], root: str) -> int:
    changed = 0
    for asset in assets:
        if asset.detected.get("role") not in CHARACTER_ROLES or ACTION_TAG in _tags(asset):
            continue
        if asset.detected_by in ("profile", "learned") or not is_prop_path(_rel(asset, root)):
            continue
        asset.detected["role"] = "DECORATION"
        asset.detected.pop("roles_alt", None)
        changed += 1
    return changed


NOT_GROUND_ROLES = frozenset({"GROUND", "CLIFF", "WALL"})


def not_ground(assets: list[Any], root: str) -> int:
    """A sign, a door or a ledge's decoration among a side-view pack's ground pieces is a
    decoration (Kenney's ``grassLedgeLeft`` hangs under a surface; ``signRight`` points)."""
    changed = 0
    for asset in assets:
        if asset.detected.get("role") not in NOT_GROUND_ROLES or asset.detected_by in (
            "profile",
            "learned",
        ):
            continue
        if asset.detected.get("usage") != "sprite" or "#" in asset.id:
            continue
        stem = posixpath.splitext(posixpath.basename(_rel(asset, root)))[0]
        if not set(words(stem)) & (NOT_GROUND_WORDS | {"ledge"}):
            continue
        asset.detected["role"] = "DECORATION"
        asset.detected.pop("roles_alt", None)
        changed += 1
    return changed


def prop_objects(catalog: Any, side_ids: set[str]) -> int:
    """The things cut from a sheet of a side-view pack's folder of props: decorations."""
    by_id = {a.id: a for a in catalog.assets}
    changed = 0
    packs = {p.pack_id: p.root for p in catalog.packs}
    for obj in catalog.objects:
        sheet = by_id.get(obj.sheet)
        if sheet is None or sheet.pack_id not in side_ids:
            continue
        if FRAME_SHEET in _tags(sheet) and obj.source == "auto" and obj.status != "CONFIRMED":
            obj.status = "UNUSED"  # the frames of a character's sheet are no things
            changed += 1
            continue
        if obj.role not in CHARACTER_ROLES:
            continue
        if obj.source != "auto" or not is_prop_path(_rel(sheet, packs.get(sheet.pack_id, ""))):
            continue
        obj.role = "DECORATION"
        changed += 1
    return changed


# --------------------------------------------------------------------------- parallax sets

LAYER_WORDS = frozenset(
    {"background", "backgrounds", "backgroud", "bg", "parallax", "layer", "layers", "layered",
     "sky", "back", "far", "middle", "mid", "front", "near", "fore", "foreground", "clouds"}
)  # fmt: skip
DEPTH_WORDS = {
    "sky": 0, "space": 0, "background": 1, "back": 1, "far": 1, "bg": 1, "clouds": 2,
    "mountains": 2, "middle": 3, "mid": 3, "near": 5, "front": 6, "fore": 6, "foreground": 6,
}  # fmt: skip
NOT_LAYER_WORDS = frozenset(
    {"tile", "tiles", "tileset", "tilemap", "props", "prop", "preview", "previews", "example",
     "sample", "character", "characters", "player", "sprite", "sprites", "icon", "ui"}
)  # fmt: skip
MIN_LAYER_HEIGHT = 64
# a layer see-through for less than this share of it is a whole picture (the farthest of a set)
OPAQUE_LAYER = 0.01
_NUMBER = re.compile(r"(\d+)")


def _see_through(path: Path) -> float:
    try:
        with Image.open(path) as im:
            alpha = np.asarray(im.convert("RGBA"))[:, :, 3]
    except (OSError, ValueError):
        return 0.0
    return float((alpha < 128).mean())


def _number(stem: str) -> int | None:
    found = _NUMBER.findall(stem)
    return int(found[-1]) if found else None


def parallax_sets(assets: list[Any], pack_root: Path, root: str) -> int:
    """Tags the layers of every folder of background layers with their order (far first)."""
    by_folder: dict[str, list[Any]] = {}
    for asset in assets:
        if asset.kind != "image" or "#" in asset.id or _set_aside(asset):
            continue
        rel = _rel(asset, root)
        if rel.casefold().endswith(".gif"):
            continue
        facets = asset.detected
        if facets.get("usage") not in ("background", "sprite", "tiles"):
            continue
        if facets.get("animations") and asset.detected_by != "generic_grid":
            continue  # frames a reader named (a guessed grid of frames does not count)
        size = facets.get("size") or [0, 0]
        if int(size[1]) < MIN_LAYER_HEIGHT or 2 * int(size[0]) < int(size[1]):
            continue  # a layer is half as wide as high at least (it repeats sideways)
        stem_words = set(words(posixpath.splitext(posixpath.basename(rel))[0]))
        if stem_words & NOT_LAYER_WORDS:
            continue
        by_folder.setdefault(posixpath.dirname(rel), []).append(asset)
    tagged = 0
    for folder in sorted(by_folder):
        members = by_folder[folder]
        if len(members) < 2:
            continue
        folder_words = set(words(folder.rsplit("/", 1)[-1])) if folder else set()
        stems = {a.id: posixpath.splitext(posixpath.basename(_rel(a, root)))[0] for a in members}
        named = all(set(words(s)) & LAYER_WORDS for s in stems.values())
        if not (folder_words & LAYER_WORDS or named):
            continue
        # the layers of one scene are as high as one another: the most of one height are the
        # scene (pozak's ``1 (3) 2.png``, an animated layer 16 times as high, is not)
        heights = Counter(int((a.detected.get("size") or [0, 0])[1]) for a in members)
        height, count = max(heights.items(), key=lambda hc: (hc[1], hc[0]))
        members = [a for a in members if int((a.detected.get("size") or [0, 0])[1]) == height]
        if count < 2:
            continue
        if all(any(t.startswith(PARALLAX) for t in _tags(a)) for a in members):
            continue  # their names said their depths already
        clear = {a.id: _see_through(pack_root / _rel(a, root)) for a in members}
        if all(clear[a.id] < OPAQUE_LAYER for a in members):
            continue  # whole pictures only: backgrounds to choose from, not layers of one
        order = _order(members, stems, pack_root, root)
        # a whole picture is the farthest layer or none: one nearer would hide the others
        order = [order[0], *(a for a in order[1:] if clear[a.id] >= OPAQUE_LAYER)]
        set_name = folder or "."
        for depth, asset in enumerate(order, start=1):
            facets = asset.detected
            tags = {t for t in _tags(asset) if not t.startswith(PARALLAX)}
            tags |= {f"{PARALLAX}{min(depth, 9)}", f"{PARALLAX_SET}{set_name}"}
            facets["tags"] = sorted(tags)
            facets["usage"] = "background"
            facets["role"] = "BACKGROUND"
            for key in ("frame", "origin", "grid", "roles_alt", "tile_overrides", "tileset",
                        "animations", "terrain_proposal"):  # fmt: skip
                facets.pop(key, None)
            asset.confidence = max(asset.confidence, CONFIDENCE)
            tagged += 1
    return tagged


def _order(members: list[Any], stems: dict[str, str], pack_root: Path, root: str) -> list[Any]:
    """Far to near: by depth words, else by number (turned round when the nearest is the opaque
    one), else by how much is see-through (opaque first)."""
    ranks: dict[str, int] = {}
    for a in members:
        found = [DEPTH_WORDS[w] for w in words(stems[a.id]) if w in DEPTH_WORDS]
        if found:
            ranks[a.id] = min(found)
    clear = {a.id: _see_through(pack_root / _rel(a, root)) for a in members}
    if len(ranks) == len(members) and len(set(ranks.values())) == len(members):
        return sorted(members, key=lambda a: ranks[a.id])
    numbers = {a.id: _number(stems[a.id]) for a in members}
    if all(n is not None for n in numbers.values()) and len(set(numbers.values())) == len(members):
        by_number = sorted(members, key=lambda a: int(numbers[a.id] or 0))
        if clear[by_number[-1].id] < clear[by_number[0].id]:
            by_number.reverse()  # the opaque sky is the last by number
        return by_number
    return sorted(members, key=lambda a: (clear[a.id], a.id))


# --------------------------------------------------------------------------- sheets of frames

_SIZE = re.compile(r"(?<![0-9])([0-9]{2,3})\s*[xX]\s*([0-9]{2,3})(?![0-9])")
FRAME_SHEET = "frame_sheet"
FRAMES_OF_SHEET = "frames_of_sheet"
UNNAMED_CONFIDENCE = 0.5  # needs review: the rows' animations have no names
MOTION_NAMED = "motion_named"  # T17.33: the animations were named from what the frames do
MOTION_CONFIDENCE = 0.8
TILE_SHEET_WORDS = frozenset({"tilemap", "tileset", "tiles", "terrain"})


def frame_sheets(assets: list[Any], pack_root: Path, root: str) -> int:
    """pozak's characters (``Character 120x120.png``, ``Character 160x160 (1).png``): a sheet
    whose name gives a frame size that divides it is one character, each row of painted frames
    an animation (``anim_<row>``: no name says which, so it needs review); the islands another
    reader cut of it are set aside, and so are the numbered pictures of the pack that are its
    frames exported one by one (``Player/Character (2) 15.png``)."""
    sizes: set[tuple[int, int]] = set()
    made = 0
    for asset in assets:
        if "#" in asset.id or asset.kind != "image" or asset.detected_by in ("profile", "learned"):
            continue
        rel = _rel(asset, root)
        if rel.casefold().endswith(".gif"):
            continue
        m = _SIZE.search(posixpath.splitext(posixpath.basename(rel))[0])
        size = asset.detected.get("size") or [0, 0]
        if m is None or asset.detected.get("animations") and asset.detected_by != "generic_grid":
            continue
        cw, ch = int(m.group(1)), int(m.group(2))
        w, h = int(size[0]), int(size[1])
        if not cw or not ch or w % cw or h % ch or (w // cw) * (h // ch) < 4:
            continue
        if set(words(rel)) & TILE_SHEET_WORDS:
            continue  # pozak's ``Terrain/Tilemap 24x24 (3).png``: tiles, no character
        rgba = _load(pack_root / rel)
        if rgba is None:
            continue
        # the frames may be drawn at a part of the size the name says (T17.33)
        cw, ch = motion.cell_of(rgba, (cw, ch))
        frames = motion.frames_of(rgba, cw, ch)
        seqs = motion.sequences(frames, w // cw)
        fig = motion.figure(seqs)
        if fig is None:
            continue
        # every animation named by what its frames do (T17.33: standing, steps, a swing, ...)
        named = motion.names(seqs, fig)
        facets = asset.detected
        tags = {t for t in _tags(asset) if not t.startswith(UNUSED) and not t.startswith(SAME_AS)}
        once = {"death", "get_up", "hurt", "attack", "jump", "fall", "action"}
        facets.update({
            "usage": "sprite",
            "grid": {"cell": [cw, ch], "margin": [0, 0], "separation": [0, 0]},
            "frame": [cw, ch],
            "origin": [cw // 2, ch - 1],
            "animations": {
                f"{name}_down": {
                    "frames": [[f.col, f.row] for f in seq],
                    "fps": 8.0 if name.split("_")[0] in ("idle", "crouch") else 10.0,
                    "loop": name.rsplit("_", 1)[0] not in once and name not in once,
                }
                for name, seq in zip(named, seqs, strict=True)
            },
            "tags": sorted(tags | {FRAME_SHEET, MOTION_NAMED}),
        })  # fmt: skip
        said = set(words(rel))
        facets["role"] = next((r for r, ws in ROLE_WORDS.items() if said & ws), "PLAYER")
        facets.pop("roles_alt", None)
        # named from the frames: sure when it stands and walks, as a reader of names would be
        basics = {n.split("_")[0] for n in named}
        asset.confidence = (
            MOTION_CONFIDENCE
            if {"idle"} <= basics and basics & {"walk", "run"}
            else UNNAMED_CONFIDENCE
        )
        sizes.add((cw, ch))
        sizes.add((int(m.group(1)), int(m.group(2))))
        made += 1
        for other in assets:
            if other.id.startswith(asset.id + "#") and not _set_aside(other):
                _aside(other, FRAMES_OF_SHEET, rel)
    if not sizes:
        return 0
    for asset in assets:
        if "#" in asset.id or FRAME_SHEET in _tags(asset) or _set_aside(asset):
            continue
        size = asset.detected.get("size") or [0, 0]
        stem = posixpath.splitext(posixpath.basename(asset.path))[0]
        if (int(size[0]), int(size[1])) in sizes and _number(stem) is not None:
            _aside(asset, FRAMES_OF_SHEET)
    return made


# --------------------------------------------------------------------------- tiles twice

SAME_TILES = "same_tiles"
TILE_COPY_SIZES = (8, 160)  # single square tiles of this many px
MIN_COPIES = 8
COPY_SHARE = 0.6  # of a size's single tiles found among the cells of one sheet
TILE_COPY_CONFIDENCE = 0.8


COPY_DIFF = 2.0  # mean difference (0..255) of a single tile and its cell: the export's rounding


def _premultiplied(part: np.ndarray) -> np.ndarray:
    a = part.astype(np.float32)
    a[:, :, :3] *= a[:, :, 3:4] / 255.0
    return a


def _matches(singles: np.ndarray, cells: np.ndarray) -> np.ndarray:
    """For each single tile (premultiplied, n x h x w x 4), the index of the cell (premultiplied,
    m x h x w x 4) it is the same picture as within ``COPY_DIFF``, else -1. Two copies of one
    picture exported apart differ in a few edge pixels, so they are compared, not hashed."""
    out = np.full(len(singles), -1, dtype=np.int64)
    if not len(singles) or not len(cells):
        return out
    k = max(1, singles.shape[1] // 10)
    coarse_c = cells[:, ::k, ::k].reshape(len(cells), -1)
    coarse_s = singles[:, ::k, ::k].reshape(len(singles), -1)
    flat_c = cells.reshape(len(cells), -1)
    for i in range(len(singles)):
        near = np.abs(coarse_c - coarse_s[i][None, :]).mean(axis=1)
        for j in np.argsort(near, kind="stable")[:3]:
            if float(near[j]) > 4.0 * COPY_DIFF:
                break
            if float(np.abs(flat_c[j] - singles[i].reshape(-1)).mean()) <= COPY_DIFF:
                out[i] = int(j)
                break
    return out


def tile_copies(assets: list[Any], pack_root: Path, root: str) -> int:
    """A side-view pack that ships its tiles twice (T17.33: Kenney's *Platformer Pack Medieval*,
    *Nautical*, *Industrial*: ``PNG/medievalTile_001.png`` to ``_268`` and
    ``Tilesheet/medieval_tilesheet.png``): a sheet whose cells are most of the pack's single
    square tiles of one size is that size's tile sheet (another reader may have cut it as a sheet
    of objects), read as tiles on its grid; the single tiles found in it are set aside as its
    copies, and so is a second sheet of the same cells (the ``_2X`` file). Returns the sheets
    read so."""
    singles: dict[int, list[Any]] = {}
    for asset in assets:
        size = asset.detected.get("size") or [0, 0]
        w, h = int(size[0]), int(size[1])
        if "#" in asset.id or asset.kind != "image" or w != h:
            continue
        if not TILE_COPY_SIZES[0] <= w <= TILE_COPY_SIZES[1] or _set_aside(asset):
            continue
        if asset.detected_by in ("profile", "learned") or asset.path.casefold().endswith(".gif"):
            continue
        if asset.detected.get("animations") and asset.detected_by != "generic_grid":
            continue
        if asset.confidence >= AUTO_SURE:
            continue  # read surely already (a character, a piece of the strips reader)
        stem = posixpath.splitext(posixpath.basename(asset.path))[0]
        piece = _piece(stem)
        if piece is not None and _layout(piece[1]) is not None:
            continue  # named by its place: the pieces' own sheet is made from the names
        singles.setdefault(w, []).append(asset)
    made = 0
    made_sheets: list[tuple[int, Any]] = []
    for n, group in sorted(singles.items()):
        if len(group) < MIN_COPIES:
            continue
        loaded: list[tuple[Any, np.ndarray]] = []
        for asset in group:
            rgba = _load(pack_root / _rel(asset, root))
            if rgba is not None and rgba.shape[0] == n and rgba.shape[1] == n:
                loaded.append((asset, _premultiplied(rgba)))
        if len(loaded) < MIN_COPIES:
            continue
        stack = np.stack([p for _a, p in loaded])
        taken: Any = None
        for sheet in sorted(assets, key=lambda a: a.id):
            size = sheet.detected.get("size") or [0, 0]
            w, h = int(size[0]), int(size[1])
            if "#" in sheet.id or sheet.kind != "image" or w < 4 * n or h < 2 * n:
                continue
            if sheet.detected_by in ("profile", "learned") or sheet in group:
                continue
            if UNUSED + "atlas_copy" in _tags(sheet):
                continue  # a packed atlas with its XML: the single files are the art
            rgba = None
            for sep in (0, 1, 2):
                if (w + sep) % (n + sep) or (h + sep) % (n + sep):
                    continue
                rgba = rgba if rgba is not None else _load(pack_root / _rel(sheet, root))
                if rgba is None:
                    break
                cells = [
                    c
                    for c in side_tiles.cells_of(rgba, n, n, (0, 0), (sep, sep))
                    if c.cover >= side_tiles.EMPTY
                ]
                if not cells:
                    continue
                hit = _matches(stack, np.stack([_premultiplied(c.rgba) for c in cells]))
                found = {i: loaded[i][0] for i in range(len(loaded)) if hit[i] >= 0}
                if len(found) < max(MIN_COPIES, COPY_SHARE * len(loaded)):
                    continue
                rel = _rel(sheet, root)
                if taken is not None:
                    _aside(sheet, SAME_TILES, taken)  # the same sheet again
                    _as_picture(sheet)
                else:
                    taken = rel
                    _tile_sheet(sheet, n, sep)
                    made_sheets.append((n, sheet))
                    made += 1
                for copy_ in found.values():
                    if not _set_aside(copy_):
                        _aside(copy_, SAME_TILES, rel)
                        _as_picture(copy_)
                for other in assets:
                    if other.id.startswith(sheet.id + "#") and not _set_aside(other):
                        _aside(other, SAME_TILES, rel)
                break
    # the same sheet drawn twice as large (``_tilesheet@2.png``, the *Retina* tiles): the
    # smaller is used, as of every pack drawn in several sizes
    for n, small in made_sheets:
        sw, sh = (int(v) for v in small.detected.get("size") or [0, 0])
        for m, big in made_sheets:
            bw, bh = (int(v) for v in big.detected.get("size") or [0, 0])
            if m > n and m % n == 0 and (bw, bh) == (sw * m // n, sh * m // n):
                _aside(big, OTHER_SIZE, _rel(small, root))
                _as_picture(big)
    return made


def _tile_sheet(sheet: Any, n: int, sep: int) -> None:
    """Makes a sheet a sheet of ground tiles of ``n`` px (its other readings dropped)."""
    facets = sheet.detected
    tags = {t for t in _tags(sheet) if not t.startswith(UNUSED) and not t.startswith(SAME_AS)}
    for key in ("animations", "frame", "origin", "roles_alt", "directions"):
        facets.pop(key, None)
    facets.update({
        "usage": "tiles",
        "grid": {"cell": [n, n], "margin": [0, 0], "separation": [sep, sep]},
        "tags": sorted(tags),
    })  # fmt: skip
    if facets.get("role") not in ("GROUND", "WALL", "CLIFF"):
        facets["role"] = "GROUND"
    sheet.confidence = max(float(sheet.confidence or 0.0), TILE_COPY_CONFIDENCE)


# --------------------------------------------------------------------------- character sheets

CHARACTER_SHEET_WORDS = frozenset({"character", "characters", "player", "players", "enemies"})
ALIKE = 0.6


def _load(path: Path) -> np.ndarray | None:
    try:
        with Image.open(path) as im:
            return np.asarray(im.convert("RGBA"))
    except (OSError, ValueError):
        return None


def character_sheets(assets: list[Any], pack_root: Path, root: str) -> list[Any]:
    """The characters of a side-view pack's character sheet, as new assets (variants)."""
    from rpggen.core.catalog import Asset

    cells = {
        int(a.detected["grid"]["cell"][0])
        for a in assets
        if a.detected.get("usage") == "tiles" and isinstance(a.detected.get("grid"), dict)
        and not _set_aside(a)
    }  # fmt: skip
    added: list[Any] = []
    for asset in list(assets):
        facets = asset.detected
        if _set_aside(asset) or facets.get("usage") not in ("tiles", "sprite"):
            continue
        if facets.get("usage") != "tiles" and asset.detected_by != "generic_grid":
            continue  # a sheet whose frames a reader named is a character already
        if asset.detected_by in ("profile", "learned") or "#" in asset.id:
            continue
        rel = _rel(asset, root)
        said = set(words(posixpath.splitext(posixpath.basename(rel))[0]))
        if not said & CHARACTER_SHEET_WORDS:
            continue  # the sheet's own name says so (a folder of characters holds sheets of one)
        rgba = _load(pack_root / rel)
        if rgba is None:
            continue
        grid = facets.get("grid")
        if not isinstance(grid, dict):
            guessed = _guess_cell(rgba)
            if guessed is None:
                continue
            grid = {"cell": [guessed, guessed], "margin": [0, 0], "separation": [0, 0]}
        cw, ch = (int(v) for v in grid["cell"])
        if cells and not cells - {cw}:
            continue  # a cell of its own beside the pack's tiles
        margin = [int(v) for v in grid.get("margin") or [0, 0]]
        sep = [int(v) for v in grid.get("separation") or [0, 0]]
        parts = side_tiles.cells_of(rgba, cw, ch, (margin[0], margin[1]), (sep[0], sep[1]))
        runs: list[list[side_tiles.Cell]] = []
        for c in parts:
            if c.cover < side_tiles.EMPTY:
                continue
            if runs and _alike(runs[-1][-1], c) and len(runs[-1]) < 4:
                runs[-1].append(c)
            else:
                runs.append([c])
        if len(runs) < 2:
            continue
        for i, run in enumerate(runs):
            first = run[0]
            ys = np.nonzero(first.alpha.any(axis=1))[0]
            baseline = int(ys.max()) if ys.size else ch - 1
            frames = [[c.x, c.y] for c in run]
            new = {
                "usage": "sprite",
                "grid": {"cell": [cw, ch], "margin": margin, "separation": sep},
                "frame": [cw, ch],
                "origin": [cw // 2, baseline],
                "animations": {
                    "idle_down": {"frames": frames[:1], "fps": 4.0, "loop": True},
                    "walk_down": {"frames": frames, "fps": 8.0, "loop": True},
                },
                "role": "PLAYER" if i == 0 else "ENEMY",
                "size": list(facets.get("size") or [0, 0]),
                "tags": [CHARACTERS_CUT],
            }
            added.append(
                Asset(
                    id=f"{asset.id}#ch{first.x}_{first.y}",
                    pack_id=asset.pack_id,
                    path=asset.path,
                    sha256=asset.sha256,
                    kind="image",
                    status="AUTO_DETECTED",
                    detected=new,
                    detected_by="side_packs",
                    confidence=ENEMY_CONFIDENCE,
                )
            )
        _aside(asset, CHARACTERS_CUT)
        # a sheet of characters joins no tile set: the rooms are painted with the ground's
        facets["usage"] = "sprite"
        for key in ("tileset", "tile_overrides", "terrain_proposal"):
            facets.pop(key, None)
        facets["frame"] = list(facets.get("size") or [cw, ch])
    return added


CHARACTER_CELLS = (16, 18, 24, 32, 48, 64)


def _guess_cell(rgba: np.ndarray) -> int | None:
    """The cell of a sheet of characters no reader cut: of the sizes that divide it into four
    cells or more, the one whose borders the figures cross least (a figure is drawn inside its
    cell); None when every size cuts through figures."""
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3] >= side_tiles.ALPHA
    best: tuple[float, int] | None = None
    for c in CHARACTER_CELLS:
        if w % c or h % c or (w // c) * (h // c) < 4:
            continue
        across = alpha[:, c - 1 : w - 1 : c] & alpha[:, c:w:c]
        crossed = float(across.mean()) if across.size else 0.0
        if best is None or crossed < best[0] - 1e-9:
            best = (crossed, c)
    return best[1] if best is not None and best[0] < 0.02 else None


def _alike(a: side_tiles.Cell, b: side_tiles.Cell) -> bool:
    """Two frames of one character: painted about as much, in the same colours."""
    if not 0.6 <= (b.cover / max(a.cover, 1e-6)) <= 1.6:
        return False
    return side_tiles._palette_share(b, a) >= ALIKE and side_tiles._palette_share(a, b) >= ALIKE


# --------------------------------------------------------------------------- terrain by name

PLACE_WORDS = frozenset(
    {"left", "right", "mid", "middle", "center", "centre", "cliff", "cliffalt", "hill", "ledge",
     "half", "corner", "alt", "round", "rounded", "top", "single"}
)  # fmt: skip
NOT_GROUND_WORDS = frozenset(
    {"sign", "door", "arrow", "lever", "switch", "fence", "ladder", "lock", "window", "rope",
     "chain", "spike", "spikes", "bridge", "torch", "lamp", "flag", "water", "lava", "key"}
)  # fmt: skip


def _piece(stem: str) -> tuple[str, frozenset[str]] | None:
    """(surface prefix, place words) of a piece's name, or None when it names no place."""
    ws = words(stem)
    if not ws:
        return None
    k = next((i for i, w in enumerate(ws) if w in PLACE_WORDS), len(ws))
    prefix, place = ws[:k], frozenset(ws[k:])
    if not prefix or (place and not place <= PLACE_WORDS) or set(prefix) & NOT_GROUND_WORDS:
        return None
    return "_".join(prefix), place


# (place words) -> (row of the generated sheet, peering mask or None, kind, probability)
Layout = tuple[int, int | None, str, float]


def _layout(place: frozenset[str]) -> Layout | None:
    s = side_tiles
    if "ledge" in place:
        return None  # a ledge's decoration hangs under the surface: no ground
    if "half" in place:
        if "left" in place:
            return (1, None, "one_way_left", 1.0)
        if "right" in place:
            return (1, None, "one_way_right", 1.0)
        return (1, None, "one_way_mid" if "mid" in place or "middle" in place else "one_way", 1.0)
    if "hill" in place:
        return (2, None, "slope_left" if "left" in place else "slope_right", 1.0)
    if "corner" in place:
        return (2, None, "inner_left" if "left" in place else "inner_right", 1.0)
    variant = bool(place & {"alt", "round", "rounded", "cliffalt"})
    if "cliff" in place or "cliffalt" in place:
        mask = s.E | s.S if "left" in place else s.S | s.W
        return (0, mask, "cliff", 0.0)
    if "center" in place or "centre" in place:
        return (0, s.ALL, "center", 0.0 if variant else 1.0)
    if "mid" in place or "middle" in place or "top" in place:
        return (0, s.E | s.S | s.W, "mid", 0.0 if variant else 1.0)
    if place == frozenset({"left"}):
        return (0, s.E | s.S, "left", 1.0)
    if place == frozenset({"right"}):
        return (0, s.S | s.W, "right", 1.0)
    if not place or place == frozenset({"single"}):
        return (0, s.S, "single", 1.0)
    return None


def _named_groups(assets: list[Any], root: str) -> dict[tuple[str, str], list[tuple[Any, Layout]]]:
    groups: dict[tuple[str, str], list[tuple[Any, Layout]]] = {}
    for asset in assets:
        facets = asset.detected
        if asset.kind != "image" or "#" in asset.id:
            continue
        if facets.get("animations") and asset.detected_by != "generic_grid":
            continue  # frames a reader named: no piece of ground
        if asset.detected_by in ("profile", "learned") or facets.get("usage") not in (
            "sprite",
            "tiles",
        ):
            continue
        tags = _tags(asset)
        if any(t.startswith(UNUSED) for t in tags) and UNUSED + "compiled_sheet" not in tags:
            continue
        size = facets.get("size") or [0, 0]
        if int(size[0]) != int(size[1]) or int(size[0]) < 8:
            continue
        rel = _rel(asset, root)
        stem = posixpath.splitext(posixpath.basename(rel))[0]
        found = _piece(stem)
        if found is None:
            continue
        layout = _layout(found[1])
        if layout is None:
            continue
        groups.setdefault((posixpath.dirname(rel), found[0]), []).append((asset, layout))
    return groups


def _make_sheet(
    key: tuple[str, str],
    members: list[tuple[Any, Layout]],
    pack_root: Path,
    root: str,
    work: Path,
) -> tuple[Path, dict[str, dict[str, Any]], list[tuple[Any, str]], int, np.ndarray] | None:
    """The pieces of one surface laid into one sheet: row 0 the terrain (``center`` first),
    row 1 the planks, row 2 the slopes and corners."""
    sizes = {int((a.detected.get("size") or [0])[0]) for a, _l in members}
    kinds = {lay[2] for _a, lay in members}
    if len(sizes) != 1 or "center" not in kinds or "mid" not in kinds:
        return None
    tile = sizes.pop()
    rows: dict[int, list[tuple[Any, Layout]]] = {}
    order = {"center": 0, "mid": 1, "left": 2, "right": 3, "single": 4, "cliff": 5,
             "one_way_left": 0, "one_way_mid": 1, "one_way": 1, "one_way_right": 2}  # fmt: skip
    for asset, lay in sorted(
        members, key=lambda m: (m[1][0], order.get(m[1][2], 9), m[1][3] == 0.0, m[0].id)
    ):
        rows.setdefault(lay[0], []).append((asset, lay))
    cols = max(len(v) for v in rows.values())
    sheet = Image.new("RGBA", (cols * tile, (max(rows) + 1) * tile), (0, 0, 0, 0))
    overrides: dict[str, dict[str, Any]] = {}
    used: list[tuple[Any, str]] = []
    for r, row in sorted(rows.items()):
        for c, (asset, (_row, mask, kind, prob)) in enumerate(row):
            try:
                with Image.open(pack_root / _rel(asset, root)) as im:
                    piece = im.convert("RGBA")
                    sheet.paste(piece, (c * tile, r * tile))
            except (OSError, ValueError):
                continue
            k = f"{c},{r}"
            entry: dict[str, Any] = {"custom": {"side": kind}}
            slope = (
                side_tiles.slope_of(np.asarray(piece)[:, :, 3] >= side_tiles.ALPHA)
                if kind.startswith("slope")
                else None
            )
            under = side_tiles.corner_under(np.asarray(piece)) if kind.startswith("inner") else None
            if slope is not None:
                # a hill's side (T17.33): its collision is the slope its picture draws
                entry["custom"]["slope"] = slope
                entry["collision"] = side_tiles.slope_collision(slope, tile, tile)
            elif under is not None:
                # the earth under the foot of a slope, its surface going on in one top corner
                entry["custom"]["under_slope"] = under
                entry["collision"] = {"profile": "FULL"}
            elif mask is not None:
                entry["terrain"] = {"set": "", "terrain": 0, "peering": _peering(mask)}
                if prob != 1.0:
                    entry["probability"] = prob
            elif kind.startswith("one_way"):
                entry["collision"] = {"profile": "ONE_WAY"}
            else:
                entry["collision"] = {"profile": "NONE"}
            overrides[k] = entry
            used.append((asset, k))
    pixels = np.asarray(sheet)
    digest = hashlib.sha256(pixels.tobytes() + repr(pixels.shape).encode()).hexdigest()
    out = work / f"{digest[:24]}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        sheet.save(out, format="PNG", optimize=False)
    return out, overrides, used, tile, pixels


LOOSE_MIN = 8
LOOSE_COLUMNS = 8


def _loose_tiles(assets: list[Any], root: str) -> dict[str, list[Any]]:
    """Single square pictures of one size, eight or more in one folder, that no reader took as
    anything sure and that are not set aside: a folder of loose tiles (T17.33)."""
    by: dict[tuple[str, int], list[Any]] = {}
    # a folder whose pieces were laid by their names already is read so
    named = {posixpath.dirname(_rel(a, root)) for a in assets if UNUSED + PIECE_ASIDE in _tags(a)}
    for asset in assets:
        facets = asset.detected
        size = facets.get("size") or [0, 0]
        w, h = int(size[0]), int(size[1])
        if "#" in asset.id or asset.kind != "image" or w != h or not 8 <= w <= 160:
            continue
        if _set_aside(asset) or asset.detected_by in ("profile", "learned"):
            continue
        if asset.path.casefold().endswith(".gif") or facets.get("usage") not in ("sprite", "tiles"):
            continue
        if facets.get("animations") and asset.detected_by != "generic_grid":
            continue
        if facets.get("role") in CHARACTER_ROLES or asset.confidence >= AUTO_SURE:
            continue
        rel = _rel(asset, root)
        if posixpath.dirname(rel) in named:
            continue
        by.setdefault((posixpath.dirname(rel), w), []).append(asset)
    out: dict[str, list[Any]] = {}
    for (folder, _w), members in sorted(by.items()):
        if len(members) >= LOOSE_MIN and folder not in out:
            out[folder] = sorted(members, key=lambda a: _natural(_rel(a, root)))
    return out


AUTO_SURE = 0.75


def _natural(text: str) -> list[Any]:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text.casefold())]


def _read_loose(
    folder: str, members: list[Any], pack_root: Path, root: str, work: Path
) -> tuple[Path, side_tiles.SheetRead, list[tuple[Any, str]], int, np.ndarray] | None:
    """The loose tiles of a folder laid in a sheet in their names' order and read from their
    pictures (``side_tiles.read``); None when nothing of them was read."""
    tile = int((members[0].detected.get("size") or [0])[0])
    placed: list[tuple[Any, str]] = []
    rows = (len(members) + LOOSE_COLUMNS - 1) // LOOSE_COLUMNS
    sheet = Image.new("RGBA", (LOOSE_COLUMNS * tile, rows * tile), (0, 0, 0, 0))
    for i, asset in enumerate(members):
        try:
            with Image.open(pack_root / _rel(asset, root)) as im:
                piece = im.convert("RGBA")
        except (OSError, ValueError):
            continue
        if piece.size != (tile, tile):
            continue
        c, r = i % LOOSE_COLUMNS, i // LOOSE_COLUMNS
        sheet.paste(piece, (c * tile, r * tile))
        placed.append((asset, f"{c},{r}"))
    pixels = np.asarray(sheet)
    read = side_tiles.read(pixels, (tile, tile))
    if not read.terrains and not read.kinds:
        return None
    digest = hashlib.sha256(pixels.tobytes() + repr(pixels.shape).encode()).hexdigest()
    out = work / f"{digest[:24]}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        sheet.save(out, format="PNG", optimize=False)
    del folder
    return out, read, placed, tile, pixels


def _peering(mask: int) -> dict[str, int]:
    from rpggen.core.terrain import blocks, tiled_wang

    peering = tiled_wang.empty_peering()
    for side_key, bit in blocks.SIDE_KEYS:
        if mask & bit:
            peering[side_key] = 0
    return peering


def terrain_set_def(name: str, surface: str, sheet: str, index: int) -> dict[str, Any]:
    from rpggen.core.terrain import rpgmaker_a2

    out = rpgmaker_a2.terrain_set_def(name, index)
    out["mode"] = "sides"
    out["terrains"][0]["name"] = surface
    out.update({"surface": surface, "over": "nothing", "shape": SIDE_TERRAIN,
                "layout": SIDE_TERRAIN, "sheet": sheet})  # fmt: skip
    return out


def _surface(prefix: str) -> str:
    for word in prefix.split("_"):
        if word in ("grass", "dirt", "sand", "snow", "stone", "ice", "castle", "planet", "cake",
                    "choco", "candy", "tundra", "metal", "brick", "wood"):  # fmt: skip
            return {"castle": "stone", "brick": "stone", "metal": "stone", "tundra": "snow",
                    "planet": "rock"}.get(word, word)  # fmt: skip
    return prefix.split("_")[0]


# --------------------------------------------------------------------------- after every pack


def _sheet_job(item: tuple[Any, Path, dict[str, Any]]) -> side_tiles.SheetRead | None:
    asset, file, grid = item
    rgba = _load(file)
    if rgba is None:
        return None
    cell = (int(grid["cell"][0]), int(grid["cell"][1]))
    margin = tuple(int(v) for v in grid.get("margin") or [0, 0])
    sep = tuple(int(v) for v in grid.get("separation") or [0, 0])
    return side_tiles.read(rgba, cell, (margin[0], margin[1]), (sep[0], sep[1]))


def _plain_sheet(asset: Any) -> bool:
    facets = asset.detected
    return (
        asset.kind == "image"
        and facets.get("usage") == "tiles"
        and isinstance(facets.get("grid"), dict)
        and not _set_aside(asset)
        and asset.detected_by not in ("profile", "learned")
        and not any("terrain" in v for v in (facets.get("tile_overrides") or {}).values())
        and "terrain_proposal" not in facets
        and facets.get("role") in ("GROUND", "WALL", "CLIFF", "AUTOTILE", "DECORATION", "INTERIOR")
        and SIDE_TAG not in _tags(asset)
        and "collision" not in facets  # a ladder, a plank, spikes the names said (T14.02)
        and not _tags(asset) & {"platform", "one_way", "ladder", "hazard", "breakable"}
    )


def read_tiles(
    catalog: Any,
    roots: dict[str, Path],
    side_ids: set[str],
    work_dir: Path | None,
    issues: IssueList,
    in_parallel: Callable[[Callable[[Any], Any], list[Any]], list[Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Terrains and roles of the side-view packs' tiles, and one tile size a pack. Returns the
    terrain sets by asset id and the generated files (project path -> file)."""
    from rpggen import paths
    from rpggen.core.catalog import Asset
    from rpggen.core.terrain import GENERATED_PACK

    sets: dict[str, list[dict[str, Any]]] = {}
    generated: dict[str, str] = {}
    if not side_ids:
        return sets, generated
    packs = {p.pack_id: p.root for p in catalog.packs}
    work = (work_dir or paths.cache_dir()) / "side_terrain"
    index = 0
    # pieces named by their place: a sheet of their own a surface
    added: list[Any] = []
    for pack_id in sorted(side_ids):
        root = packs.get(pack_id, "")
        assets = [a for a in catalog.assets if a.pack_id == pack_id]
        for (folder, prefix), members in sorted(_named_groups(assets, root).items()):
            made = _make_sheet((folder, prefix), members, roots[pack_id], root, work)
            if made is None:
                continue
            out, overrides, used, tile, pixels = made
            slug = re.sub(r"[^a-z0-9]+", "_", f"{pack_id}_{folder}_{prefix}".casefold()).strip("_")
            asset_id = f"{GENERATED_PACK}.{slug}_side"
            rel = f"{SIDE_DIR}/{out.name}"
            name = f"{slug}_side"
            for entry in overrides.values():
                if "terrain" in entry:
                    entry["terrain"]["set"] = name
            surface = _surface(prefix)
            facets: dict[str, Any] = {
                "usage": "tiles",
                "role": "GROUND",
                "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
                "tags": sorted({SIDE_TAG, f"surface:{surface}", f"side_pack:{pack_id}"}),
                "tile_overrides": overrides,
                "size": [int(pixels.shape[1]), int(pixels.shape[0])],
            }
            added.append(
                Asset(asset_id, GENERATED_PACK, rel, hashlib.sha256(pixels.tobytes()).hexdigest(),
                      "image", "AUTO_DETECTED", facets, {}, "side_packs", 0.9)
            )  # fmt: skip
            generated[rel] = str(out)
            sets[asset_id] = [terrain_set_def(name, surface, asset_id, index)]
            index += 1
            for piece, _key in used:
                _aside(piece, PIECE_ASIDE, rel)
                _as_picture(piece)
        # loose tiles a folder (T17.33: Kenney's *Tile Extensions*, ``slice01_01.png`` and
        # ``grassHalfLeft.png`` with no ``center`` beside them): laid into a sheet, read from
        # their pictures as a sheet's cells are
        for folder, members in sorted(_loose_tiles(assets, root).items()):
            made_loose = _read_loose(folder, members, roots[pack_id], root, work)
            if made_loose is None:
                continue
            out, read, placed, tile, pixels = made_loose
            slug = re.sub(r"[^a-z0-9]+", "_", f"{pack_id}_{folder}".casefold()).strip("_")
            asset_id = f"{GENERATED_PACK}.{slug}_loose"
            rel = f"{SIDE_DIR}/{out.name}"
            names = [f"{slug}_loose_{s}_{i}" for i, (s, _m) in enumerate(read.terrains)]
            overrides = side_tiles.overrides(read, names)
            surface = read.terrains[0][0] if read.terrains else "ground"
            added.append(
                Asset(asset_id, GENERATED_PACK, rel, hashlib.sha256(pixels.tobytes()).hexdigest(),
                      "image", "AUTO_DETECTED",
                      {"usage": "tiles", "role": "GROUND",
                       "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
                       "tags": sorted({SIDE_TAG, f"surface:{surface}", f"side_pack:{pack_id}"}),
                       "tile_overrides": dict(sorted(overrides.items(), key=lambda kv: _xy(kv[0]))),
                       "size": [int(pixels.shape[1]), int(pixels.shape[0])]},
                      {}, "side_packs", CONFIDENCE)
            )  # fmt: skip
            generated[rel] = str(out)
            if read.terrains:
                sets[asset_id] = [
                    terrain_set_def(n, s, asset_id, index + i)
                    for i, (n, (s, _m)) in enumerate(zip(names, read.terrains, strict=True))
                ]
                index += len(names)
            for piece, key in placed:
                if key in overrides:
                    _aside(piece, PIECE_ASIDE, rel)
                    _as_picture(piece)
    if added:
        from rpggen.core.catalog import CatalogPack
        from rpggen.core.terrain import rpgmaker_a2

        catalog.assets.extend(added)
        if not any(p.pack_id == GENERATED_PACK for p in catalog.packs):
            catalog.packs.append(
                CatalogPack(GENERATED_PACK, "0" * 64, rpgmaker_a2.TERRAIN_DIR, [], [], None, [])
            )
    # a picture of a stage put together (a preview, an example) is no sheet of tiles, and a
    # sheet set aside joins no tile set
    for asset in catalog.assets:
        if asset.pack_id not in side_ids or asset.detected.get("usage") != "tiles":
            continue
        if asset.detected_by in ("profile", "learned"):
            continue
        stem = posixpath.splitext(posixpath.basename(asset.path))[0]
        if not _set_aside(asset) and set(words(stem)) & PREVIEW_WORDS:
            _aside(asset, PREVIEW_PICTURE)
        if _set_aside(asset):
            _as_picture(asset)
    # one tile size a pack
    for pack_id in sorted(side_ids):
        _one_size(catalog, pack_id, added)
    # the cells of the sheets nothing named
    jobs: list[tuple[Any, Path, dict[str, Any]]] = []
    for asset in sorted(catalog.assets, key=lambda a: a.id):
        if asset.pack_id not in side_ids or not _plain_sheet(asset):
            continue
        rel = _rel(asset, packs.get(asset.pack_id, ""))
        jobs.append((asset, roots[asset.pack_id] / rel, asset.detected["grid"]))
    for (asset, _file, _grid), read in zip(jobs, in_parallel(_sheet_job, jobs), strict=True):
        if read is None or read.painted == 0:
            continue
        stem = re.sub(r"[^a-z0-9]+", "_", asset.id.rsplit(".", 1)[-1].casefold())
        names = [f"{stem}_side_{surface}_{i}" for i, (surface, _m) in enumerate(read.terrains)]
        entries = side_tiles.overrides(read, names)
        if not entries:
            if read.unread:
                issues.add("TILE-016", asset=asset.id, unread=read.unread, painted=read.painted,
                           file=asset.path)  # fmt: skip
            continue
        overrides = asset.detected.setdefault("tile_overrides", {})
        for key, entry in entries.items():
            overrides[key] = {**overrides.get(key, {}), **entry}
        asset.detected["tile_overrides"] = dict(
            sorted(overrides.items(), key=lambda kv: _xy(kv[0]))
        )
        sets[asset.id] = [
            terrain_set_def(name, surface, asset.id, index + i)
            for i, (name, (surface, _m)) in enumerate(zip(names, read.terrains, strict=True))
        ]
        index += len(names)
        _add_tags(asset, SIDE_TAG)
        if read.terrains:
            asset.confidence = max(asset.confidence, CONFIDENCE)
        if read.unread:
            issues.add("TILE-016", asset=asset.id, unread=read.unread, painted=read.painted,
                       file=asset.path)  # fmt: skip
    return sets, generated


def _as_picture(asset: Any) -> None:
    """A set-aside picture joins no tile set and has no frames: it is one picture."""
    facets = asset.detected
    w, h = (int(v) for v in (facets.get("size") or [0, 0]))
    facets["usage"] = "sprite"
    for key in ("grid", "tile_overrides", "terrain_proposal", "tileset", "animations",
                "directions", "roles_alt"):  # fmt: skip
        facets.pop(key, None)
    facets["frame"] = [w, h]
    facets["origin"] = [w // 2, max(0, h - 1)]


def _xy(key: str) -> tuple[int, int]:
    x, _sep, y = key.partition(",")
    return (int(y), int(x)) if x.isdigit() and y.isdigit() else (1 << 30, 0)


# the roles of the sheets that say what size a pack is drawn in: its ground
SIZE_ROLES = frozenset({"GROUND", "WALL", "CLIFF", "AUTOTILE", "INTERIOR"})


def _one_size(catalog: Any, pack_id: str, added: list[Any]) -> None:
    """No tile set in a size the pack is not drawn in: the pack's size is the cell of most of
    its tile sheets (its named pieces' sheets count); a sheet of another cell is cut again at
    that size when it divides it and the sheet, else read as a picture."""
    sheets = [
        a for a in catalog.assets
        if a.pack_id == pack_id and a.detected.get("usage") == "tiles"
        and isinstance(a.detected.get("grid"), dict) and not _set_aside(a)
        and a.detected_by not in ("profile", "learned")
    ]  # fmt: skip
    mine = [a for a in added if f"side_pack:{pack_id}" in _tags(a)]
    counts: dict[int, int] = {}
    for a in sheets:
        if a.detected.get("role") in SIZE_ROLES:
            cell = int(a.detected["grid"]["cell"][0])
            counts[cell] = counts.get(cell, 0) + 1
    for a in mine:
        cell = int(a.detected["grid"]["cell"][0])
        counts[cell] = counts.get(cell, 0) + 3
    if not counts or len({int(a.detected["grid"]["cell"][0]) for a in sheets} | set(counts)) < 2:
        return
    size = max(counts, key=lambda c: (counts[c], c))
    for a in sheets:
        grid = a.detected["grid"]
        cw, ch = (int(v) for v in grid["cell"])
        if cw == size and ch == size:
            continue
        w, h = (int(v) for v in (a.detected.get("size") or [0, 0]))
        plain = not any(int(v) for v in grid.get("margin") or [0, 0]) and not any(
            int(v) for v in grid.get("separation") or [0, 0]
        )
        if plain and size % cw == 0 and w % size == 0 and h % size == 0 and size > cw:
            grid["cell"] = [size, size]
            a.detected.pop("tile_overrides", None)
            a.detected.pop("terrain_proposal", None)
            _add_tags(a, f"recut_from:{cw}")
            continue
        a.detected["usage"] = "sprite"
        for key in ("grid", "tile_overrides", "terrain_proposal", "tileset"):
            a.detected.pop(key, None)
        a.detected["frame"] = [w, h]
        a.detected["origin"] = [w // 2, max(0, h - 1)]
        _add_tags(a, f"{OTHER_SIZE}:{cw}")

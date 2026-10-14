"""A pack of isometric tiles: one picture a tile (T17.12).

The isometric packs that were listed (Kenney's, CC0) are no sheets of diamonds on a grid: every
tile is a picture of its own, all pictures of a pack one size or one width, the tile at the
bottom of its picture. This reader makes a **tile asset** of every such picture
(``usage: iso_tile``, ``projection: isometric``, ``canvas``, ``footprint``, ``rise``) and an
object of every picture that stands on a diamond without filling it (a tree, a sign).

* **The footprint** (the diamond a tile stands on) is the pack's: from its own words when it
  has them (``Tiled (settings).txt``: *Map tile size*; a Tiled map of the pack that is
  isometric), else measured from its flat tiles (``analyzer.isometric``). *Tile size* in a
  ``Tile information.txt`` is the diamond **with the side of the block under it** (measured:
  180 x 125 for a diamond of 180 x 104 on a block 21 high), so its width is taken and the
  height is measured. A pack that says it is isometric and has no flat tile is ``TILE-010``,
  and its pictures stay pictures.
* **Turns.** ``roadTile_001_0`` to ``_3`` and ``cornDouble_N`` / ``_E`` / ``_S`` / ``_W`` are
  one thing turned: every picture gets its ``turn``, and the catalog shows the set as one
  (``catalog.mark_turns``). The turns of a car or a boat are its headings: they are put into
  one strip, in the work folder, which is a rotation sheet like any other (T16.02).
* **Sides in a name** (``beachCornerES``) are recorded as ``joins``.
* **Two views of one model**: of sibling folders ``Isometric`` and ``Angle`` the first is used.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters import iso_sheets, naming, sequences, tiled
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.adapters.kenney_atlas import UNUSED_ATLAS_COPY
from rpggen.core.analyzer import image_facts, views
from rpggen.core.analyzer import isometric as measure
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

PROJECTION = "isometric"
USAGE_TILE = "iso_tile"
UNUSED_OTHER_VIEW = "other_view"
UNUSED_SLOPE = "slope"
UNUSED_VIEWS = "views_not_told"  # numbered views of a car that no named car says the order of
SLOPE_TAG = "slope:"
KEPT_VIEW, DROPPED_VIEW = "isometric", "angle"
VIEW_SHARE = 0.5  # this share of a dropped view's names in the kept one: the same models
SHEET_FOLDERS = frozenset({"spritesheet", "spritesheets", "tilesheet", "tilesheets"})
CHARACTER_FOLDERS = frozenset({"character", "characters"})
SAMPLE_FOLDERS = frozenset({"sample", "samples"})
TEXT_MAX_BYTES = 16 * 1024
MAP_HEAD_BYTES = 64 * 1024
# "Map tile size: 180 x 104 px" (Tiled's settings: the diamond) and, on a line of its own,
# "Tile size  : 180 x 115 px" (the diamond with the side of its block)
_MAP_TILE = re.compile(r"map\s+tile\s+size\s*:\s*(\d+)\s*x\s*(\d+)", re.IGNORECASE)
_TILE = re.compile(r"^\s*tile\s+size\s*:\s*(\d+)\s*x\s*(\d+)", re.IGNORECASE | re.MULTILINE)
_ORIENTATION = re.compile(r"orientation\s*:\s*isometric", re.IGNORECASE)
_TMX_MAP = re.compile(r"<map\b[^>]*>", re.IGNORECASE)
_TMX_ATTR = re.compile(r'\b(orientation|tilewidth|tileheight)\s*=\s*"([^"]*)"')
# what a pack's turned things are when they are no tiles
CAR_WORDS = frozenset(
    {"car", "cars", "vehicle", "vehicles", "taxi", "sedan", "truck", "trucks", "van", "bus",
     "police", "ambulance", "kart", "karts", "buggy", "tractor", "pickup"}
)  # fmt: skip
BOAT_WORDS = frozenset(
    {"boat", "boats", "ship", "ships", "watercraft", "vessel", "vessels", "yacht", "canoe",
     "raft", "sailboat", "submarine"}
)  # fmt: skip
SOURCE_TILED, SOURCE_TEXT, SOURCE_MEASURED = "tiled", "tile_information", "measured"
MEASURED_MIN_PICTURES = 8  # a folder of this many pictures of one size may be tiles ...
MEASURED_SAMPLE = 12  # ... and this many of them are looked at
MEASURED_MIN_FLAT = 4  # ... of which this many must be flat tiles that agree
TILE_CONFIDENCE = 0.85
OBJECT_CONFIDENCE = 0.8
EDGE_CONFIDENCE = 0.8  # a thin piece along one side of its diamond
HEADINGS_CONFIDENCE = 0.9
NUMBERED_HEADINGS_CONFIDENCE = 0.7  # needs review: which number points up is a guess
WIDER_SLOPE_SHARE = 0.1  # a wider block is the ground when its edges fall as the flat pieces'
COMPASS_MIN_PIECES = 4  # this many flat pieces with sides in their names say where north is
COMPASS_SHARE = 2 / 3  # ... when this share of them fit their pictures at one turn
VIEWS_MIN = 4  # numbered pictures of one name are views of a thing from this many on
VIEWS_LIKENESS_MIN = 0.6  # a numbered set is read from a named one it is this alike (0 to 1)
VIEWS_ALIKE_SHARE = 0.9  # ... and every named set this near the best has to agree with it
FIGURE_ROLES = frozenset({"PLAYER", "NPC", "ENEMY"})  # whose frames give a ground picture its scale
# the folders of a pack read by its ground pictures whose pictures stand on no diamond (T17.30)
NOT_STANDING_FOLDERS = frozenset(
    {"ui", "interface", "hud", "menu", "menus", "vfx", "fx", "effect", "effects", "cursor",
     "cursors", "filter", "filters", "icon", "icons"}
)  # fmt: skip


def says_isometric(words: set[str]) -> bool:
    """True when the words of a pack's name and folders say it is isometric."""
    return bool(words & classifier.ISOMETRIC_WORDS) and not words & classifier.NOT_ISOMETRIC_WORDS


@dataclass(frozen=True)
class PackWords:
    """What a pack says about itself."""

    isometric: bool = False  # its name, its folders or a text file say so
    excluded: bool = False  # it says it is something else (*Axonometric*)
    map_tile: tuple[int, int] | None = None  # Tiled's map tile size: the diamond
    tile: tuple[int, int] | None = None  # "Tile size": the diamond with its block's side


def _tmx_tile(text: str) -> tuple[int, int] | None:
    """The tile size of an isometric Tiled map, from its ``<map>`` tag."""
    m = _TMX_MAP.search(text)
    if m is None:
        return None
    attrs = dict(_TMX_ATTR.findall(m.group(0)))
    try:
        size = (int(attrs["tilewidth"]), int(attrs["tileheight"]))
    except (KeyError, ValueError):
        return None
    return size if attrs.get("orientation") == PROJECTION and min(size) > 0 else None


def _zip_tmx(path: Path) -> str:
    """The head of the first Tiled map in a sample archive of a pack, read in place."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = sorted(n for n in zf.namelist() if n.casefold().endswith(".tmx"))
            if not names or zf.getinfo(names[0]).flag_bits & 0x1:
                return ""
            with zf.open(names[0]) as fh:
                return fh.read(MAP_HEAD_BYTES).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, OSError):
        return ""


def pack_words(inv: Inventory, root: Path) -> PackWords:
    """What the pack's name, its folders, its text files and its sample map say."""
    words = set(classifier.name_words(inv.pack_id))
    for f in inv.files:
        for folder in posixpath.dirname(f.path).split("/"):
            words.update(classifier.name_words(folder))
    isometric = says_isometric(words)
    map_tile: tuple[int, int] | None = None
    tile: tuple[int, int] | None = None
    for f in inv.files:
        folders = {p.casefold() for p in posixpath.dirname(f.path).split("/")}
        text = ""
        try:
            if f.ext == ".txt" and f.kind == "doc" and f.size <= TEXT_MAX_BYTES:
                text = (root / f.path).read_text(encoding="utf-8", errors="replace")
            elif f.ext == ".tmx":
                with open(root / f.path, "rb") as fh:
                    text = fh.read(MAP_HEAD_BYTES).decode("utf-8", errors="replace")
            elif f.ext == ".zip" and folders & SAMPLE_FOLDERS:
                text = _zip_tmx(root / f.path)
        except OSError:
            continue
        if f.ext == ".txt":
            said = _MAP_TILE.search(text)
            if said and map_tile is None:
                map_tile = (int(said.group(1)), int(said.group(2)))
            said = _TILE.search(text)
            if said and tile is None:
                tile = (int(said.group(1)), int(said.group(2)))
            isometric = isometric or bool(_ORIENTATION.search(text))
        elif text and map_tile is None:
            map_tile = _tmx_tile(text)
    excluded = bool(words & classifier.NOT_ISOMETRIC_WORDS)
    said_so = isometric or map_tile is not None or tile is not None
    return PackWords(said_so and not excluded, excluded, map_tile, tile)


@dataclass(eq=False)
class _Picture:
    """What is measured of one picture."""

    f: InventoryFile
    size: tuple[int, int]
    box: tuple[int, int, int, int]  # x, y, w, h of the painted part
    left: np.ndarray  # the first and the last painted column of every row of the box
    right: np.ndarray
    flat: measure.FlatTile | None
    foot: measure.Base | None = None  # its lower outline, when that is a block of ground
    low: np.ndarray | None = None  # the last painted row of every column of the box

    @property
    def free(self) -> int:
        """The see-through rows under the painted part."""
        return self.size[1] - (self.box[1] + self.box[3])

    def base(self, rows: int) -> int:
        """How wide the painted part is in its lowest ``rows`` rows."""
        left, right = self.left[-max(1, rows) :], self.right[-max(1, rows) :]
        return max(0, int(right.max()) - int(left.min()) + 1)


def _look(root: Path, f: InventoryFile) -> _Picture | None:
    """The picture measured, or None when it cannot be read or nothing is painted in it."""
    try:
        mask = measure.painted(image_facts.load_rgba(root / f.path))
    except (OSError, ValueError):
        return None
    found = measure.outline(mask)
    if found is None:
        return None
    box, low = found[0], found[2]
    part = mask[box[1] : box[1] + box[3], box[0] : box[0] + box[2]]
    painted_rows = part.any(axis=1)
    left = np.where(painted_rows, part.argmax(axis=1), box[2])
    right = np.where(painted_rows, box[2] - 1 - part[:, ::-1].argmax(axis=1), -1)
    size = (mask.shape[1], mask.shape[0])
    return _Picture(
        f, size, box, left, right, measure.flat_tile(mask), measure.block_base(mask), low
    )


@dataclass(frozen=True)
class Ground:
    """The diamond of a pack and where it lies in a picture."""

    width: int
    height: int
    side: int  # rows of block under the top of the pack's usual ground tile
    down: int  # see-through rows under a tile that stands on the ground
    canvas_width: int  # how wide the pictures that share the tiles' canvas are
    source: str


def _mode(values: list[int]) -> int:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return min(counts, key=lambda v: (-counts[v], v)) if counts else 0


def find_ground(pictures: list[_Picture], words: PackWords) -> Ground | None:
    """The pack's diamond: its own words first, else measured; None when neither says it."""
    flats = [p for p in pictures if p.flat is not None]
    tiles = [p.flat for p in flats if p.flat is not None]
    if words.map_tile is not None:
        width, height = words.map_tile
        found = measure.measure(tiles, width)
        source, side = SOURCE_TILED, found.side if found else 0
    elif words.tile is not None:
        width = words.tile[0]
        found = measure.measure(tiles, width)
        # the words give the diamond with its block's side: the height is what was measured
        height = int(round(width * found.slope)) if found else words.tile[1]
        source, side = SOURCE_TEXT, max(0, words.tile[1] - height)
    else:
        found = measure.measure(tiles)
        if found is None:
            return None
        on = [p for p in flats if p.flat is not None and abs(p.flat.width - found.width) <= 1]
        width = found.width
        canvas = _mode([p.size[0] for p in on])
        if 0 <= canvas - width <= 2:
            width = canvas  # a picture cut to its tile: the soft edge is part of the diamond
        height = int(round(width * found.slope))
        source, side = SOURCE_MEASURED, max(0, _mode([p.box[3] for p in on]) - height)
        wider = _wider_ground(pictures, found)
        if wider is not None:
            return wider
    if found is not None:
        on = [p for p in flats if p.flat is not None and abs(p.flat.width - found.width) <= 1]
    else:
        on = pictures
    return Ground(
        width, height, side, _mode([p.free for p in on]), _mode([p.size[0] for p in on]), source
    )


def _wider_ground(pictures: list[_Picture], found: measure.Diamond) -> Ground | None:
    """The diamond of a pack whose flat pieces are not its ground (*Tiles Buildings*: the
    flat pieces are roofs and upper storeys 99 wide, and the ground is the block 132 wide
    that every ground floor stands on). Pictures that are wider than the flat pieces and stand
    on a whole block of ground (``measure.block_base``), a fair share of them of one width and
    at the angle of the flat pieces, say the diamond: a pack's ground is its widest."""
    wide = [
        p
        for p in pictures
        if p.foot is not None
        and p.foot.width > found.width * measure.TILE_BASE_MAX
        and abs(p.foot.slope - found.slope) <= found.slope * WIDER_SLOPE_SHARE
    ]
    counts: dict[int, int] = {}
    for p in wide:
        if p.foot is not None:
            counts[p.foot.width] = counts.get(p.foot.width, 0) + 1
    near = {w: counts[w] + counts.get(w - 1, 0) + counts.get(w + 1, 0) for w in counts}
    fair = max(MEASURED_MIN_FLAT, int(found.tiles * measure.WIDTH_SHARE))
    widths = [w for w in near if near[w] >= fair]
    if not widths:
        return None
    width = max(widths, key=lambda w: (near[w], w))
    on = [p for p in wide if p.foot is not None and abs(p.foot.width - width) <= 1]
    canvas = _mode([p.size[0] for p in on])
    if 0 <= canvas - width <= 2:
        width = canvas
    slopes = sorted(p.foot.slope for p in on if p.foot is not None)
    slope = (slopes[(len(slopes) - 1) // 2] + found.slope) / 2
    side = max(0, _mode([p.foot.side for p in on if p.foot is not None]) - 1)
    return Ground(
        width, int(round(width * slope)), side, _mode([p.free for p in on]), canvas, SOURCE_MEASURED
    )


def _folders(path: str) -> list[str]:
    return [p for p in posixpath.dirname(path).split("/") if p]


def _stem(path: str) -> str:
    return posixpath.splitext(posixpath.basename(path))[0]


def _is_still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext != ".gif"


def _size(f: InventoryFile) -> tuple[int, int]:
    image = f.image or {}
    return int(image.get("w", 0)), int(image.get("h", 0))


def _wrapper(inv: Inventory) -> str:
    """The one folder an archive wraps everything in ("" without one), as the catalog has it."""
    tops = {f.path.split("/", 1)[0] for f in inv.files if "/" in f.path}
    loose = any("/" not in f.path and f.kind != "license" for f in inv.files)
    return next(iter(tops)) if len(tops) == 1 and not loose else ""


def other_views(stills: list[InventoryFile]) -> set[str]:
    """The pictures of an ``Angle`` folder that a folder ``Isometric`` beside it has too: the
    same models seen another way."""
    by_folder: dict[str, dict[str, str]] = {}
    for f in stills:
        folder = posixpath.dirname(f.path)
        by_folder.setdefault(folder, {})[posixpath.basename(f.path).casefold()] = f.path
    dropped: set[str] = set()
    for folder, names in by_folder.items():
        if posixpath.basename(folder).casefold() != DROPPED_VIEW:
            continue
        parent = posixpath.dirname(folder)
        kept = next(
            (
                other
                for other in by_folder
                if posixpath.dirname(other) == parent
                and posixpath.basename(other).casefold() == KEPT_VIEW
            ),
            None,
        )
        if kept is None:
            continue
        shared = [path for name, path in names.items() if name in by_folder[kept]]
        if len(shared) >= max(1, len(names) * VIEW_SHARE):
            dropped.update(shared)
    return dropped


def _unused(f: InventoryFile, reason: str, *tags: str) -> AssetFragment:
    w, h = (f.image or {}).get("w", 1), (f.image or {}).get("h", 1)
    facets = {
        "usage": "sprite",
        "frame": [w, h],
        "origin": [w // 2, h - 1],
        "role": "NONE",
        "tags": sorted({*tags, classifier.UNUSED_TAG + reason}),
    }
    return AssetFragment(f.path, facets, 0.9, "full")


def joins_of(stills: list[InventoryFile]) -> dict[str, list[str]]:
    """``{path: sides}`` for the pictures whose names end in the sides they join on. The
    capitals are sides only when several files of the folder share the name before them
    (``beach``, ``beachE``, ``beachES``): one file that ends in ``E`` says nothing."""
    names: dict[tuple[str, str], int] = {}
    found: dict[str, tuple[tuple[str, str], list[str]]] = {}
    for f in stills:
        folder, stem = posixpath.dirname(f.path), _stem(f.path)
        names[(folder, stem)] = names.get((folder, stem), 0) + 1
        split = naming.split_joins(stem)
        if split is not None:
            found[f.path] = ((folder, split[0]), split[1])
    shared: dict[tuple[str, str], int] = {}
    for key, _sides in found.values():
        shared[key] = shared.get(key, 0) + 1
    return {
        path: sides for path, (key, sides) in found.items() if shared[key] + names.get(key, 0) >= 2
    }


@dataclass
class _TurnSet:
    """The files of one thing turned."""

    folder: str
    base: str
    count: int  # 4 or 8
    members: list[tuple[naming.Turn, InventoryFile]]  # the turns, then the ones on a slope


def turn_sets(stills: list[InventoryFile]) -> list[_TurnSet]:
    """The sets of files that are one thing turned, by folder and name."""
    groups: dict[tuple[str, str], list[tuple[naming.Turn, InventoryFile]]] = {}
    for f in stills:
        turn = naming.split_turn(_stem(f.path))
        if turn is not None:
            key = (posixpath.dirname(f.path), turn.base.casefold())
            groups.setdefault(key, []).append((turn, f))
    found: list[_TurnSet] = []
    for key in sorted(groups):
        members = sorted(
            groups[key], key=lambda m: (m[0].slope != "", m[0].number, m[0].slope, m[1].path)
        )
        count = naming.turns_of([turn for turn, _f in members])
        if count:
            found.append(_TurnSet(key[0], members[0][0].base, count, members))
    return found


def numbered_sets(stills: list[InventoryFile]) -> list[tuple[str, str, list[InventoryFile]]]:
    """``(folder, name, files in the order of their numbers)`` for the pictures of one folder
    that share a name and are numbered without a gap from 0 or 1 (``carBlack2_000`` to
    ``_015``): the views of one thing, when a set whose names say its views has as many."""
    groups: dict[tuple[str, str], list[tuple[int, InventoryFile]]] = {}
    for f in stills:
        split = sequences.split_number(_stem(f.path))
        if split is not None and split[0]:
            key = (posixpath.dirname(f.path), split[0])
            groups.setdefault(key, []).append((split[1], f))
    found = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda m: (m[0], m[1].path))
        numbers = [number for number, _f in members]
        whole = numbers == list(range(numbers[0], numbers[0] + len(numbers)))
        if len(members) >= VIEWS_MIN and numbers[0] in (0, 1) and whole:
            found.append((key[0], key[1], [f for _n, f in members]))
    return found


def _views(root: Path, files: list[InventoryFile]) -> list[views.View] | None:
    """What the pictures show, or None when one of them cannot be read or is empty."""
    found = []
    for f in files:
        try:
            shown = views.view(image_facts.load_rgba(root / f.path))
        except (OSError, ValueError):
            return None
        if shown is None:
            return None
        found.append(shown)
    return found


@dataclass
class _Named:
    """A car or a boat whose file names say its views, and what the pictures show."""

    group: _TurnSet
    kind: str
    shown: list[views.View] | None

    @property
    def names(self) -> tuple[tuple[str, str], ...]:
        return tuple((turn.word, turn.slope) for turn, _f in self.group.members)


def renamed(named: list[_Named]) -> None:
    """Give the views of a named set that the pack names wrongly (``views.misnamed``) the
    names their pictures belong under: the files change places among the names."""
    by_names: dict[tuple[tuple[str, str], ...], list[_Named]] = {}
    for one in named:
        if one.shown is not None and one.group.members[0][0].word:
            by_names.setdefault(one.names, []).append(one)
    for sets in by_names.values():
        moves = views.misnamed([one.shown for one in sets if one.shown is not None])
        for one, moved in zip(sets, moves, strict=True):
            if not moved or one.shown is None:
                continue
            members, shown = list(one.group.members), list(one.shown)
            for place, target in moved.items():
                members[target] = (one.group.members[target][0], one.group.members[place][1])
                shown[target] = one.shown[place]
            one.group.members, one.shown = members, shown


def _turn_number(turn: naming.Turn, count: int) -> int:
    """The turn of a file among ``count``: its number, or its compass word's place going
    round clockwise from N."""
    if not turn.word:
        return turn.number
    return turn.number * count // len(naming.COMPASS)


def _named_diamond(results: list[AdapterResult]) -> tuple[int, int] | None:
    """The diamond an earlier reader took from the pack's names (``isometric:WxH:named``)."""
    for res in results:
        for mark in res.pack_warnings:
            size, _, source = mark.removeprefix(classifier.ISOMETRIC_MARK).partition(":")
            width, _, height = size.partition("x")
            said = mark.startswith(classifier.ISOMETRIC_MARK) and source == "named"
            if said and width.isdigit() and height.isdigit():
                return int(width), int(height)
    return None


def strip_name(files: list[InventoryFile], cols: int) -> str:
    """Named after the pictures it is made of, so that the same pictures give the same file."""
    text = "\n".join([f"headings/{cols}", *(f.sha256 for f in files)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


class IsometricAdapter:
    name = "isometric"
    priority = 50  # before the numbered frames: a tile's turns are no animation

    def match(self, inv: Inventory, root: Path) -> float:
        words = pack_words(inv, root)
        if words.excluded:
            return 0.0
        return 1.0 if words.isometric or self._candidates(inv, set()) else 0.0

    @staticmethod
    def _candidates(inv: Inventory, claimed: set[str]) -> list[list[InventoryFile]]:
        """The folders of a pack that says nothing whose pictures may be tiles: enough
        see-through pictures of one size."""
        folders: dict[str, list[InventoryFile]] = {}
        for f in inv.files:
            if _is_still(f) and f.path not in claimed:
                folders.setdefault(posixpath.dirname(f.path), []).append(f)
        found = []
        for folder in sorted(folders):
            files = folders[folder]
            enough = len(files) >= MEASURED_MIN_PICTURES and len({_size(f) for f in files}) == 1
            if enough and all((f.image or {}).get("has_alpha") for f in files):
                found.append(files)
        return found

    def _measured(self, inv: Inventory, root: Path, claimed: set[str]) -> set[str]:
        """The folders of a pack that does not say it is isometric whose pictures show it:
        the first pictures of such a folder are flat tiles that agree on a diamond."""
        folders: set[str] = set()
        for files in self._candidates(inv, claimed):
            looked = [_look(root, f) for f in files[:MEASURED_SAMPLE]]
            tiles = [p.flat for p in looked if p is not None and p.flat is not None]
            found = measure.measure(tiles) if len(tiles) >= MEASURED_MIN_FLAT else None
            if found is not None and found.tiles >= MEASURED_MIN_FLAT:
                folders.add(posixpath.dirname(files[0].path))
        return folders

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        words = pack_words(inv, root)
        if words.excluded:
            return result
        # a pack that says nothing is read where its pictures show it, and only there
        shown = None if words.isometric else self._measured(inv, root, ctx.claimed)
        if shown is not None and not shown:
            return result
        wrapper = _wrapper(inv)
        animated = {
            f.path for seq in sequences.find_sequences(inv, ctx.claimed) for _n, f in seq.frames
        }
        for character in sequences.find_facings(inv, ctx.claimed):
            animated.update(f.path for f in character.files)  # "Male_3_Run7": a person
        # the pictures an isometric Tiled map of the pack paints with are measured wherever
        # they lie (T17.28): the Tiled sample of a pack lies in a folder of samples
        painted = tiled.map_pictures(ctx.results)
        stills = [
            f
            for f in inv.files
            if _is_still(f)
            and f.path not in ctx.claimed
            and f.path not in animated  # "walk_0" to "walk_3" is the sequence reader's
            and (
                f.path in painted
                or (
                    (shown is None or posixpath.dirname(f.path) in shown)
                    and not classifier.not_game_art(f.path, wrapper)
                    and not {p.casefold() for p in _folders(f.path)} & CHARACTER_FOLDERS
                )
            )
        ]
        # ... but only the pack's own pictures say what its diamond is, when it has any
        only_painted = {
            f.path for f in stills if f.path in painted and classifier.not_game_art(f.path, wrapper)
        }
        taken: set[str] = set()
        for path in sorted(other_views(stills)):
            taken.add(path)
        packed = [
            f
            for f in stills
            if f.path not in taken and {p.casefold() for p in _folders(f.path)} & SHEET_FOLDERS
        ]
        if len(packed) < len(stills) - len(taken):  # the loose pictures are there as well
            taken.update(f.path for f in packed)
        else:
            packed = []
        for f in stills:
            if f.path in taken:
                reason = UNUSED_ATLAS_COPY if f in packed else UNUSED_OTHER_VIEW
                result.assets.append(_unused(f, reason))
        stills = [f for f in stills if f.path not in taken]

        pack = set(classifier.name_words(inv.pack_id))
        turned: dict[str, tuple[int, int]] = {}  # path -> (its turn, of how many)
        work = (ctx.work_dir or paths.cache_dir()) / sequences.WORK_FOLDER

        def kind_of(name: str, path: str) -> str:
            said = pack | set(classifier.name_words(name))
            for folder in _folders(path):
                said.update(classifier.name_words(folder))
            return "car" if said & CAR_WORDS else "boat" if said & BOAT_WORDS else ""

        named: list[_Named] = []
        turn_groups: list[set[str]] = []
        for group in turn_sets(stills):
            kind = kind_of(group.base, group.members[0][1].path)
            if kind:
                named.append(_Named(group, kind, _views(root, [f for _t, f in group.members])))
                continue
            if len({_size(f) for _turn, f in group.members}) != 1:
                continue  # turns of a tile are all of one size: these are something else
            for turn, f in group.members:
                turned[f.path] = (_turn_number(turn, group.count), group.count)
            turn_groups.append({f.path for _turn, f in group.members})
        renamed(named)
        for one in named:
            taken.update(self._headings(root, one.group, one.kind, work, result, issues))
        # the cars whose names are numbers: which view a picture is, the named cars say
        told = [one for one in named if one.shown is not None and one.group.members[0][0].word]
        for folder, name, files in numbered_sets([f for f in stills if f.path not in taken]):
            kind = kind_of(name, files[0].path)
            if kind and any(one.kind == kind and len(one.names) == len(files) for one in told):
                taken.update(
                    self._numbered_views(
                        root, _TurnSet(folder, name, 0, []), files, kind, told, work, result, issues
                    )
                )
        stills = [f for f in stills if f.path not in taken]

        pictures = [p for p in (_look(root, f) for f in stills) if p is not None]
        own = [p for p in pictures if p.f.path not in only_painted]
        ground = find_ground(own or pictures, words) if pictures else None
        by_name = _named_diamond(ctx.results)
        if by_name is not None and (ground is None or (ground.width, ground.height) != by_name):
            # the names gave the diamond (T17.30): the flat tiles that are there are checked
            # against it, and what is left of the pack is no reason for TILE-010
            if ground is not None:
                issues.add(
                    "TILE-014",
                    pack_id=inv.pack_id,
                    named=f"{by_name[0]}x{by_name[1]}",
                    measured=f"{ground.width}x{ground.height}",
                    file=f"({inv.pack_id})",
                )
            result.issues = list(issues)
            return result
        if ground is None and words.isometric:
            # no flat tile, no size in a name: a large ground picture that tiles on its diamond
            # says it (T17.30)
            said = iso_sheets.ground_pictures(
                root,
                stills,
                (ctx.work_dir or paths.cache_dir()) / iso_sheets.WORK_FOLDER,
                result,
                ctx,
                [
                    int(frag.facets["frame"][0])
                    for res in ctx.results
                    for frag in res.assets
                    if frag.facets.get("animations")
                    and frag.facets.get("role") in FIGURE_ROLES
                    and frag.facets.get("frame")
                ],
            )
            if said is not None:
                # the other pictures are things standing on that diamond, each on its own foot
                # (their canvases are no tile's: *Lords Of Pain* draws a crate in the middle of
                # 256 x 256)
                ground = Ground(said[0], said[1], 0, 0, 0, iso_sheets.SOURCE_GROUND)
                read_ground = {f.path for f in result.assets}
                # ... but the pictures of its menus and its effects are none (a vignette over the
                # whole screen stood on 30 diamonds and walled an enemy in)
                read_ground |= {
                    p.f.path
                    for p in pictures
                    if set(classifier.tokens(p.f.path)[0]) & NOT_STANDING_FOLDERS
                }
                pictures = [p for p in pictures if p.f.path not in read_ground]
                stills = [f for f in stills if f.path not in read_ground]
        if ground is None:
            if pictures:
                reason = (
                    "its flat tiles do not agree on one height"
                    if any(p.flat is not None for p in pictures)
                    else "none of its pictures is a flat tile to measure it by"
                )
                issues.add("TILE-010", pack_id=inv.pack_id, reason=reason, file=f"({inv.pack_id})")
            result.issues = list(issues)
            return result
        result.pack_warnings.append(
            f"{classifier.ISOMETRIC_MARK}{ground.width}x{ground.height}:{ground.source}"
        )
        joins = joins_of(stills)
        read = {p.f.path: self._facets(p, ground) for p in pictures}
        for members in turn_groups:
            # a wall turned four ways stands along four sides: a set of which only some turns
            # seem to stand along one (the corner of a roof, a carpet) is no set of walls
            sides = [read[path][0].get("edge") for path in members if path in read]
            if len(sides) != len(members) or None in sides or len(set(sides)) != len(sides):
                for picture in pictures:
                    if picture.f.path in members and "edge" in read[picture.f.path][0]:
                        read[picture.f.path] = self._facets(picture, ground, edges=False)
        quarters = self._compass(root, pictures, read, joins)
        if quarters:
            joins = {path: measure.turned_sides(sides, quarters) for path, sides in joins.items()}
        for picture in pictures:
            facets, confidence = read[picture.f.path]
            path = picture.f.path
            if path in turned:
                facets["turn"] = turned[path][0]
            if path in joins:
                facets["joins"] = joins[path]
            face = self._face(root, picture, facets)
            if face:
                facets["tags"] = [face]
            shape = self._corner(root, picture, facets)
            if shape:
                facets["corner"] = shape
            result.assets.append(AssetFragment(path, facets, confidence, "full"))
        result.issues = list(issues)
        return result

    @staticmethod
    def _facets(
        picture: _Picture, ground: Ground, edges: bool = True
    ) -> tuple[dict[str, Any], float]:
        """The facets of one picture of the pack: a tile when it stands on the ground and its
        base is as wide as the diamond, else an object standing on one or several."""
        w, h = picture.size
        bx, by, bw, bh = picture.box
        shared = abs(w - ground.canvas_width) <= 1
        if shared:
            top = h - ground.down - ground.side - ground.height
            origin = [w // 2, top + ground.height // 2]
        else:  # a picture cut to what is in it: it stands on its own foot
            origin = [bx + bw // 2, by + bh - 1]
            top = origin[1] - ground.height // 2
        base = picture.base(ground.height // 2 + ground.side + 1)
        grounded = shared and abs(picture.free - ground.down) <= max(2, ground.height // 8)
        fills = measure.TILE_BASE_MIN * ground.width <= base <= measure.TILE_BASE_MAX * ground.width
        facets: dict[str, Any] = {
            "projection": PROJECTION,
            "canvas": [w, h],
            "footprint": [ground.width, ground.height],
            "origin": origin,
            "rise": max(0, top - by),
        }
        if grounded and fills:
            return {"usage": USAGE_TILE, **facets}, TILE_CONFIDENCE
        if edges and shared and picture.low is not None:
            # a wall segment, a fence: it fills no diamond and is a tile all the same, the
            # piece of one side of its cell, as a road piece is the piece of the sides it joins
            edge = measure.edge_side(
                bx + np.arange(bw),
                by + picture.low,
                (origin[0], origin[1] + ground.side),
                (ground.width, ground.height),
            )
            if edge is not None:
                return {"usage": USAGE_TILE, **facets, "edge": edge}, EDGE_CONFIDENCE
        stands = measure.stands_on(base, ground.width)
        for _again in range(2):
            if stands == (1, 1):
                break
            # a wide thing is widest higher up: where a block of that many diamonds is
            rows = sum(stands) * ground.height // 4 + ground.side + 1
            stands = measure.stands_on(picture.base(rows), ground.width)
        return {"usage": "sprite", "frame": [w, h], **facets, "stands_on": list(stands)}, (
            OBJECT_CONFIDENCE
        )

    @staticmethod
    def _compass(
        root: Path,
        pictures: list[_Picture],
        read: dict[str, tuple[dict[str, Any], float]],
        joins: dict[str, list[str]],
    ) -> int:
        """How many quarter turns clockwise the compass of a pack's names lies from the
        grid's (``n`` the upper right side of a diamond). The names say which sides a piece
        joins on and not where their north is: in *Vector Roads* ``N`` is the upper left, a
        quarter turn back. The pictures say it: of every flat piece with sides in its name
        the sides are looked up on which its own surface runs out (``measure.open_sides``),
        and the turn is taken at which most names fit their pictures (the sides named, or the
        sides not named: ``lotE`` names the side its kerb is on). 0 when no turn fits two
        thirds of the pieces, or when another fits as many: then the names stand."""
        found: list[tuple[list[str], list[str]]] = []
        for picture in pictures:
            path = picture.f.path
            facets = read[path][0]
            if path not in joins or facets.get("usage") != USAGE_TILE or facets.get("rise"):
                continue
            try:
                rgba = image_facts.load_rgba(root / path)
            except (OSError, ValueError):
                continue
            origin, foot = facets["origin"], facets["footprint"]
            shown = measure.open_sides(rgba, (origin[0], origin[1]), (foot[0], foot[1]))
            if shown is not None and 0 < len(shown) < len(measure.EDGE_SIDES):
                found.append((joins[path], shown))
        if len(found) < COMPASS_MIN_PIECES:
            return 0
        fits = []
        for quarters in range(len(measure.EDGE_SIDES)):
            count = 0
            for named, shown in found:
                turned = set(measure.turned_sides(named, quarters))
                count += turned == set(shown) or turned == set(measure.EDGE_SIDES) - set(shown)
            fits.append(count)
        best = max(range(len(fits)), key=lambda q: (fits[q], -q))
        clear = fits[best] >= len(found) * COMPASS_SHARE and sorted(fits)[-2] < fits[best]
        return best if clear else 0

    @staticmethod
    def _corner(root: Path, picture: _Picture, facets: dict[str, Any]) -> str:
        """``"round"`` or ``"square"`` for a flat tile that joins two adjacent sides, as its
        picture shows it (``measure.corner_shape``, T17.22: a race is planned with the corners
        its road pieces have); "" for every other picture. The sides are the grid's: the names'
        compass has been turned to it by then."""
        joins = facets.get("joins") or []
        if facets.get("usage") != USAGE_TILE or facets.get("rise") or facets.get("edge"):
            return ""
        if len(joins) != 2:
            return ""
        try:
            rgba = image_facts.load_rgba(root / picture.f.path)
        except (OSError, ValueError):
            return ""
        origin, foot = facets["origin"], facets["footprint"]
        middle, diamond = (origin[0], origin[1]), (foot[0], foot[1])
        # the sides a name says are not always the ones its surface runs out on (``lotES`` of
        # *Vector Roads* names the sides its kerb is on): such a piece is no corner of a road
        if set(measure.open_sides(rgba, middle, diamond) or []) != set(joins):
            return ""
        return measure.corner_shape(rgba, middle, diamond, joins) or ""

    @staticmethod
    def _face(root: Path, picture: _Picture, facets: dict[str, Any]) -> str:
        """The tag the colour of a flat tile's top gives it (``measure.face_colour``):
        ``surface:grass`` for a plain green one whose name says no surface, "" for any other
        picture. What a map's ground is chosen by when no name says *grass* (*Nature* calls
        its meadow ``naturePack_001``)."""
        if facets.get("usage") != USAGE_TILE or facets.get("rise") or facets.get("edge"):
            return ""
        try:
            rgba = image_facts.load_rgba(root / picture.f.path)
        except (OSError, ValueError):
            return ""
        origin, foot = facets["origin"], facets["footprint"]
        found = measure.face_colour(rgba, (origin[0], origin[1]), (foot[0], foot[1]))
        if found != measure.FACE_GRASS or classifier.suggested_surface(picture.f.path):
            return ""
        return f"surface:{found}"

    def _numbered_views(
        self,
        root: Path,
        group: _TurnSet,
        files: list[InventoryFile],
        kind: str,
        named: list[_Named],
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> set[str]:
        """A car whose pictures are numbered in no order (``carBlack2_000`` to ``_015``): every
        picture takes the view of the named car it is most like (``analyzer.views``), and the
        set is then read as a named one is. The named car that is most alike says the views;
        when another that is nearly as alike says other headings, the car needs review. A set
        that is like no named car stays unread, with the reason: a car driving sideways is
        worse than a car that is not offered."""
        paths_ = {f.path for f in files}
        shown = _views(root, files)
        found: list[tuple[float, int, list[int]]] = []
        for index, one in enumerate(named):
            if shown is None or one.shown is None:
                break
            if one.kind == kind and len(one.shown) == len(shown):
                order, alike = views.lay(shown, one.shown)
                found.append((alike, -index, order))
        found.sort(reverse=True)
        if not found or found[0][0] < VIEWS_LIKENESS_MIN:
            result.assets.extend(_unused(f, UNUSED_VIEWS, kind) for f in files)
            return paths_
        alike, index, order = found[0]
        best = named[-index]
        flat = {place for place, (_word, slope) in enumerate(best.names) if not slope}
        headings = {place: i for i, place in enumerate(order) if place in flat}
        sure = all(
            {place: i for i, place in enumerate(other) if place in flat} == headings
            for nearly, _index, other in found[1:]
            if nearly >= alike * VIEWS_ALIKE_SHARE
        )
        members = sorted(
            ((best.group.members[place][0], files[i]) for i, place in enumerate(order)),
            key=lambda m: (m[0].slope != "", m[0].number, m[0].slope, m[1].path),
        )
        group = _TurnSet(group.folder, group.base, best.group.count, members)
        confidence = HEADINGS_CONFIDENCE if sure else NUMBERED_HEADINGS_CONFIDENCE
        done = self._headings(root, group, kind, work, result, issues, confidence)
        if not done:
            result.assets.extend(_unused(f, UNUSED_VIEWS, kind) for f in files)
        return paths_

    def _headings(
        self,
        root: Path,
        group: _TurnSet,
        kind: str,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
        confidence: float = HEADINGS_CONFIDENCE,
    ) -> set[str]:
        """A car or a boat in four or eight headings, a picture each: the pictures are put
        into one strip, the first pointing up and each next one a step clockwise, which is the
        rotation sheet a racing game drives (T16.02). Lettered headings say their order;
        numbered ones go round clockwise, and the one that points up is taken to be the first
        of the two narrowest that face each other. Headings on a slope are left unused."""
        flat = [(turn, f) for turn, f in group.members if not turn.slope]
        slopes = [(turn, f) for turn, f in group.members if turn.slope]
        images: list[Image.Image] = []
        try:
            for _turn, f in flat:
                with Image.open(root / f.path) as opened:
                    images.append(opened.convert("RGBA"))
        except (OSError, ValueError) as exc:
            issues.add("ADAPT-001", adapter=self.name, file=flat[0][1].path, reason=str(exc))
            return set()
        count = group.count
        order = sorted(range(count), key=lambda i: _turn_number(flat[i][0], count))
        boxes = [im.getchannel("A").getbbox() for im in images]
        if any(box is None for box in boxes):
            return set()  # an empty picture among them: no sheet of headings
        if not flat[0][0].word:
            # which number points up the names do not say
            widths = [box[2] - box[0] for box in boxes if box is not None]
            half = count // 2
            up = min(range(half), key=lambda k: (widths[order[k]] + widths[order[k + half]], k))
            order = order[up:] + order[:up]
            confidence = NUMBERED_HEADINGS_CONFIDENCE
        if len({im.size for im in images}) == 1:
            # one canvas: cut to what all of them paint, so that they stay in register
            found = [box for box in boxes if box is not None]
            cut = (
                min(b[0] for b in found),
                min(b[1] for b in found),
                max(b[2] for b in found),
                max(b[3] for b in found),
            )
            images = [im.crop(cut) for im in images]
        fw, fh = max(im.width for im in images), max(im.height for im in images)
        cols, rows = sequences.layout(count, fw)
        if rows != 1:
            return set()  # too wide for one row: the pictures stay pictures
        strip = Image.new("RGBA", (count * fw, fh), (0, 0, 0, 0))
        for cell, index in enumerate(order):
            view = images[index]
            strip.paste(view, (cell * fw + (fw - view.width) // 2, (fh - view.height) // 2))
        files = [flat[index][1] for index in order]
        file_name = strip_name(files, cols)
        dest = work / file_name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            strip.save(dest, format="PNG", optimize=False, pnginfo=None)
        except OSError as exc:
            issues.add("ADAPT-001", adapter=self.name, file=files[0].path, reason=str(exc))
            return set()
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
            "frame": [fw, fh],
            "origin": [fw // 2, fh - 1],
            "size": [strip.width, strip.height],
            "headings": count,
            "heading_order": "up_cw",
            "heading_files": [f.path for f in files],
            "projection": PROJECTION,
            "tags": [kind],
        }
        if kind == "car":
            facets["role"] = "VEHICLE"
        first = flat[0][1]
        project_path = f"{sequences.FRAME_STRIP_DIR}/{file_name}"
        result.assets.append(AssetFragment(first.path, facets, confidence, "full"))
        result.generated[project_path] = str(dest)
        result.rendered[first.path] = project_path
        result.consumed.extend(f.path for _turn, f in flat if f.path != first.path)
        for turn, f in slopes:
            result.assets.append(_unused(f, UNUSED_SLOPE, kind, SLOPE_TAG + turn.slope))
        return {f.path for _turn, f in group.members}

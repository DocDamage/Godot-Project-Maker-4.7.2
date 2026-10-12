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
from rpggen.core.adapters import naming, sequences
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.adapters.kenney_atlas import UNUSED_ATLAS_COPY
from rpggen.core.analyzer import image_facts
from rpggen.core.analyzer import isometric as measure
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

PROJECTION = "isometric"
USAGE_TILE = "iso_tile"
UNUSED_OTHER_VIEW = "other_view"
UNUSED_SLOPE = "slope"
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
HEADINGS_CONFIDENCE = 0.9
NUMBERED_HEADINGS_CONFIDENCE = 0.7  # needs review: which number points up is a guess


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
    box = found[0]
    part = mask[box[1] : box[1] + box[3], box[0] : box[0] + box[2]]
    painted_rows = part.any(axis=1)
    left = np.where(painted_rows, part.argmax(axis=1), box[2])
    right = np.where(painted_rows, box[2] - 1 - part[:, ::-1].argmax(axis=1), -1)
    return _Picture(f, (mask.shape[1], mask.shape[0]), box, left, right, measure.flat_tile(mask))


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
    if found is not None:
        on = [p for p in flats if p.flat is not None and abs(p.flat.width - found.width) <= 1]
    else:
        on = pictures
    return Ground(
        width, height, side, _mode([p.free for p in on]), _mode([p.size[0] for p in on]), source
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


def _turn_number(turn: naming.Turn, count: int) -> int:
    """The turn of a file among ``count``: its number, or its compass word's place going
    round clockwise from N."""
    if not turn.word:
        return turn.number
    return turn.number * count // len(naming.COMPASS)


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
        stills = [
            f
            for f in inv.files
            if _is_still(f)
            and f.path not in ctx.claimed
            and f.path not in animated  # "walk_0" to "walk_3" is the sequence reader's
            and (shown is None or posixpath.dirname(f.path) in shown)
            and not classifier.not_game_art(f.path, wrapper)
            and not {p.casefold() for p in _folders(f.path)} & CHARACTER_FOLDERS
        ]
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
        for group in turn_sets(stills):
            said = pack | set(classifier.name_words(group.base))
            for folder in _folders(group.members[0][1].path):
                said.update(classifier.name_words(folder))
            kind = "car" if said & CAR_WORDS else "boat" if said & BOAT_WORDS else ""
            if kind:
                done = self._headings(root, group, kind, work, result, issues)
                taken.update(done)
                continue
            if len({_size(f) for _turn, f in group.members}) != 1:
                continue  # turns of a tile are all of one size: these are something else
            for turn, f in group.members:
                turned[f.path] = (_turn_number(turn, group.count), group.count)
        stills = [f for f in stills if f.path not in taken]

        pictures = [p for p in (_look(root, f) for f in stills) if p is not None]
        ground = find_ground(pictures, words) if pictures else None
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
        for picture in pictures:
            facets, confidence = self._facets(picture, ground)
            path = picture.f.path
            if path in turned:
                facets["turn"] = turned[path][0]
            if path in joins:
                facets["joins"] = joins[path]
            result.assets.append(AssetFragment(path, facets, confidence, "full"))
        result.issues = list(issues)
        return result

    @staticmethod
    def _facets(picture: _Picture, ground: Ground) -> tuple[dict[str, Any], float]:
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

    def _headings(
        self,
        root: Path,
        group: _TurnSet,
        kind: str,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
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
        confidence = HEADINGS_CONFIDENCE
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

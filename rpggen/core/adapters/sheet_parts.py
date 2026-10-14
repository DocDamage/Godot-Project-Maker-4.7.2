"""Sheets of many things: object sheets and mixed tile sheets (T17.30).

Two kinds of real packs draw many things on one large sheet, and every such sheet was one
sprite or one sheet of ground:

* **Object sheets** (SakPix's stage packs: about twenty sheets of 1536 x 1024 a pack, named by
  what they hold, *13. Farm animals*, *6. Barns and silos*). The things lie loose on
  transparency, under a banner with the sheet's name. A sheet is cut into its **islands** of
  painted pixels (blocks of ``BLOCK`` px that touch, so that the parts of one thing that lie a
  few pixels apart stay together); the banner (an island across the top of the sheet) and
  specks are left out. Every island is an asset of its own, a variant ``o<x>_<y>`` named by
  where it lies on the sheet (so the same sheet gives the same ids), with its picture drawn into
  the work folder. Its role is the sheet's name's (an animal of *Farm animals*, a building of
  *Barns and silos* when it is large enough to be one, a fence of *fences and gates*); a sheet
  whose name says nothing gives things that need review.
* **A sheet whose name says tiles** (*1. Fertile soil tiles*) holds loose squares of ground that
  lie on no grid, each with a rough rim. Each is cut to the square every one of them holds
  (``tile_side``), and the squares, side by side, are a sheet of tiles of that size: no tile
  set is made in a size the sheet is not drawn in, and nothing is scaled.
* **Mixed tile sheets** (CuteSCKR's tile sets: a few sheets of 768 x 768 in 48 px cells mixing
  ground, fences, crops, buildings and things). A sheet of a pack that says it is a tile set is
  sorted cell by cell: cells whose art goes on into the next cell are one thing; a thing of at
  least two by two whole cells is ground (a sheet of tiles of its cells, ``g<x>_<y>``), a thing
  of several cells that are not all whole is one object, and a cell alone a decoration
  (``o<x>_<y>``). A sheet is no longer ground because it is a sheet.

The sheet itself is set aside (``object_sheet`` or ``sorted_sheet``): its parts are the assets.
The cutting runs in a pool of threads and polls the worker's cancel (``iso_sheets.in_parallel``).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters import iso_sheets
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

NAME = "sheet_parts"
RENDER_DIR = "generated/sheet_parts"
WORK_FOLDER = "sheet_parts"
RENDER_VERSION = 1
UNUSED_OBJECT_SHEET = "object_sheet"
UNUSED_SORTED_SHEET = "sorted_sheet"
MIN_SHEET = 512  # a sheet of things is at least this wide and high
B_TO_E = frozenset({(768, 768)})  # generic_grid.NUMBERED_SHEET_CELLS: offered as 48 px tiles
MIN_CLEAR = 0.2  # ... and this share of it is see-through
MIN_ISLANDS = 4
MIN_NAMED_ISLANDS = 2  # ... or this many, when its name says what they are
BLOCK = 6  # px: islands closer than this are one thing
SPECK = 0.0004  # an island smaller than this share of the sheet is a speck
BANNER_TOP = 0.2  # the banner lies in this top share of the sheet ...
BANNER_WIDTH = 0.35  # ... and is this share of its width at least, three times as wide as high
PAINTED_ALPHA = 128
TILE_CELLS = (16, 24, 32, 48, 64)
MIN_GRID_CELLS = 12  # a mixed sheet has at least this many cells each way
JOIN_SHARE = 0.25  # art goes on into the next cell along this share of the border
GROUND_WHOLE_SHARE = 0.8  # a thing whose cells are this whole may be a patch of ground
CELL_SPECK = 0.02  # a thing of a mixed sheet painting less of a cell than this is a speck
WHOLE = 0.97  # a whole cell is painted this much
TILE_SIDE_STEP = 16
TILE_SHARE = 0.75  # the tiles of a sheet of loose tiles are the square this share of them hold
LOOSE_TILE_MAX = 64  # a larger square of a sheet of loose tiles is cut in quarters
NAMED_CONFIDENCE = 0.8
UNNAMED_CONFIDENCE = 0.5  # nothing says what the thing is: needs review
GROUND_CONFIDENCE = 0.8
TILESET_WORDS = frozenset({"tileset", "tilesets", "tile", "tiles"})
OBJECT_WORDS = frozenset({"asset", "assets", "objects", "props", "stage"})
# the words of a sheet's name -> (role, tag) of the things on it, the first that matches
ROLE_WORDS: tuple[tuple[frozenset[str], str, str], ...] = (
    (frozenset({"animal", "animals", "cow", "cows", "pig", "pigs", "sheep", "chicken", "chickens",
                "hen", "hens", "duck", "ducks", "goat", "goats", "horse", "horses", "livestock"}),
     "ANIMAL", "animal"),
    (frozenset({"barn", "barns", "silo", "silos", "house", "houses", "cottage", "cottages",
                "windmill", "windmills", "mill", "mills", "building", "buildings", "shop",
                "shops", "tower", "towers", "cabin", "cabins", "hut", "huts", "temple"}),
     "BUILDING", ""),
    (frozenset({"fence", "fences", "gate", "gates"}), "DECORATION", "fence"),
    (frozenset({"tool", "tools"}), "TOOL", "tool"),
    (frozenset({"tree", "trees"}), "DECORATION", "tree"),
    (frozenset({"weapon", "weapons", "sword", "swords"}), "WEAPON", ""),
    (frozenset({"item", "items", "potion", "potions", "food", "loot", "coins"}), "ITEM", ""),
    (frozenset({"furniture", "interior", "interiors"}), "INTERIOR", ""),
    (frozenset({"decoration", "decorations", "lantern", "lanterns", "sign", "signs", "hay",
                "bales", "sacks", "flower", "flowers", "patches", "scarecrow", "scarecrows",
                "well", "wells", "pump", "pumps", "stall", "stalls", "garden", "gardens",
                "rock", "rocks", "plant", "plants", "bush", "bushes", "barrel", "barrels",
                "crate", "crates", "props", "objects"}),
     "DECORATION", ""),
)  # fmt: skip
TILE_ROLE_WORDS: tuple[tuple[frozenset[str], str, str], ...] = (
    (frozenset({"soil", "tilled", "fertile", "field"}), "GROUND", "soil"),
    (frozenset({"grass", "meadow", "lawn"}), "GROUND", "surface:grass"),
    (frozenset({"wall", "walls"}), "WALL", ""),
    (frozenset({"roof", "roofs"}), "DECORATION", "roof"),
    (frozenset({"water", "pond", "river"}), "WATER", ""),
    (frozenset({"path", "paths", "road", "roads"}), "ROAD", ""),
)  # fmt: skip
BUILDING_MIN = 96  # px each way: a smaller thing of a sheet of buildings is a part of one


@dataclass
class _Part:
    variant: str
    picture: np.ndarray
    facets: dict[str, Any]
    confidence: float


@dataclass
class _Cut:
    parts: list[_Part] = field(default_factory=list)
    reason: str = UNUSED_OBJECT_SHEET
    error: str = ""


def _words(path: str) -> set[str]:
    folders, stem = classifier.tokens(path)
    return {w.casefold().rstrip("0123456789") for w in stem} | {w.casefold() for w in folders[-1:]}


def _size(f: InventoryFile) -> tuple[int, int]:
    image = f.image or {}
    return int(image.get("w", 0)), int(image.get("h", 0))


def _load(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8)


def is_tileset_pack(inv: Inventory) -> bool:
    """Whether the pack says it is a tile set: its name, or the one folder it is wrapped in."""
    tops = {f.path.split("/", 1)[0] for f in inv.files if "/" in f.path}
    names = [inv.pack_id.replace("_", " ")] + (sorted(tops) if len(tops) == 1 else [])
    return any(set(classifier.name_words(name)) & TILESET_WORDS for name in names)


def candidates(inv: Inventory, claimed: set[str]) -> list[InventoryFile]:
    """The large still pictures with transparency that may be sheets of things."""
    out = []
    for f in sorted(inv.files, key=lambda f: f.path):
        if f.kind != "image" or f.ext != ".png" or f.path in claimed or f.image is None:
            continue
        w, h = _size(f)
        if w >= MIN_SHEET and h >= MIN_SHEET and (f.image or {}).get("has_alpha", True):
            out.append(f)
    return out


def grid_cell(a: np.ndarray) -> int | None:
    """The cell of a mixed tile sheet: of the usual tile sizes that divide the sheet into at
    least ``MIN_GRID_CELLS`` each way, the one whose borders the art crosses least (the art of
    a cell keeps to it; a thing of several cells crosses only where it goes on)."""
    mask = a[..., 3] >= PAINTED_ALPHA
    h, w = mask.shape
    best: tuple[float, int] | None = None
    for cell in TILE_CELLS:
        if w % cell or h % cell or w // cell < MIN_GRID_CELLS or h // cell < MIN_GRID_CELLS:
            continue
        cols = mask[:, cell - 1 : w - 1 : cell] & mask[:, cell:w:cell]
        rows = mask[cell - 1 : h - 1 : cell, :] & mask[cell:h:cell, :]
        crossing = (cols.mean() + rows.mean()) / 2
        # a cell is penalised for being small: every cut of a coarser grid is one of it
        score = crossing * (1.0 + 8.0 / cell)
        if best is None or score < best[0] - 1e-9:
            best = (score, cell)
    return best[1] if best else None


def islands(mask: np.ndarray) -> list[tuple[int, int, int, int, np.ndarray]]:
    """The islands of painted pixels: ``(x, y, w, h, own)`` with ``own`` the island's own
    pixels inside its box. Pixels in blocks of ``BLOCK`` that touch (also by a corner) are one
    island. By the top, then the left."""
    h, w = mask.shape
    bh, bw = -(-h // BLOCK), -(-w // BLOCK)
    padded = np.zeros((bh * BLOCK, bw * BLOCK), dtype=bool)
    padded[:h, :w] = mask
    blocks = padded.reshape(bh, BLOCK, bw, BLOCK).any(axis=(1, 3))
    labels = np.zeros((bh, bw), dtype=np.int32)
    count = 0
    for y0, x0 in zip(*np.nonzero(blocks), strict=True):
        if labels[y0, x0]:
            continue
        count += 1
        stack = [(int(y0), int(x0))]
        labels[y0, x0] = count
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < bh and 0 <= nx < bw and blocks[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = count
                        stack.append((ny, nx))
    full = np.repeat(np.repeat(labels, BLOCK, axis=0), BLOCK, axis=1)[:h, :w]
    found = []
    for label in range(1, count + 1):
        own = mask & (full == label)
        ys, xs = np.nonzero(own)
        if not xs.size:
            continue
        x, y = int(xs.min()), int(ys.min())
        x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
        found.append((x, y, x1 - x, y1 - y, own[y:y1, x:x1]))
    found.sort(key=lambda i: (i[1], i[0]))
    return found


def tile_side(island: np.ndarray) -> int:
    """The side of the largest square in the middle of an island's box that is painted all
    over, in steps of ``TILE_SIDE_STEP`` (0 for none): the rim is trimmed from the outside in."""
    h, w = island.shape
    side = min(w, h) // TILE_SIDE_STEP * TILE_SIDE_STEP
    while side >= TILE_SIDE_STEP:
        x, y = (w - side) // 2, (h - side) // 2
        if island[y : y + side, x : x + side].all():
            return side
        side -= TILE_SIDE_STEP
    return 0


def _role(words: set[str], table: tuple[tuple[frozenset[str], str, str], ...]) -> tuple[str, str]:
    for said, role, tag in table:
        if words & said:
            return role, tag
    return "", ""


def _thing(picture: np.ndarray, role: str, tag: str, sure: bool) -> tuple[dict[str, Any], float]:
    """The facets of one thing cut from a sheet."""
    h, w = picture.shape[:2]
    if role == "BUILDING" and (w < BUILDING_MIN or h < BUILDING_MIN):
        role = "DECORATION"  # a sign, a door, a sack beside the barns
    facets: dict[str, Any] = {
        "usage": "sprite" if role == "ANIMAL" else "object",
        "frame": [w, h],
        "origin": [w // 2, h - 1],
        "size": [w, h],
    }
    if role:
        facets["role"] = role
    if tag:
        facets["tags"] = [tag]
    if role == "ANIMAL":
        # one picture: it stands and walks in it
        facets["grid"] = {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]}
        facets["animations"] = {
            "idle_down": {"frames": [[0, 0]], "fps": 1.0, "loop": True},
            "walk_down": {"frames": [[0, 0]], "fps": 1.0, "loop": True},
        }
    return facets, NAMED_CONFIDENCE if sure else UNNAMED_CONFIDENCE


def cut_objects(f: InventoryFile, a: np.ndarray) -> _Cut:
    """An object sheet, or a sheet of loose tiles when its name says tiles."""
    cut = _Cut()
    mask = a[..., 3] >= PAINTED_ALPHA
    h, w = mask.shape
    found = [
        i
        for i in islands(mask)
        if int(i[4].sum()) >= SPECK * w * h
        and not (  # the banner with the sheet's name
            i[1] < BANNER_TOP * h and i[2] >= BANNER_WIDTH * w and i[2] >= 3 * i[3]
        )
    ]
    words = _words(f.path)
    role, tag = _role(words, ROLE_WORDS)
    # a sheet named by what it holds may hold only a few large things (*6. Barns and silos*:
    # two barns and a silo); one that says nothing needs more to be a sheet of things
    if len(found) < (MIN_NAMED_ISLANDS if role else MIN_ISLANDS):
        return _Cut(reason="")
    if words & TILESET_WORDS:
        if len(found) < MIN_ISLANDS:
            return _Cut(reason="")
        return _loose_tiles(f, a, found, words)
    for x, y, iw, ih, own in found:
        picture = a[y : y + ih, x : x + iw].copy()
        picture[~own] = 0
        facets, confidence = _thing(picture, role, tag, bool(role))
        cut.parts.append(_Part(f"o{x}_{y}", picture, facets, confidence))
    return cut


def _loose_tiles(
    f: InventoryFile,
    a: np.ndarray,
    found: list[tuple[int, int, int, int, np.ndarray]],
    words: set[str],
) -> _Cut:
    sides = [tile_side(own) for *_box, own in found]
    usable = [s for s in sides if s > 0]
    if len(usable) < MIN_ISLANDS:
        return _Cut(reason="")
    # the largest square three in four of them hold: the others (a broken one) are left out
    side = max(s for s in usable if sum(u >= s for u in usable) >= TILE_SHARE * len(usable))
    tiles = []
    for (x, y, iw, ih, _own), s in zip(found, sides, strict=True):
        if s < side:
            continue
        tx, ty = x + (iw - side) // 2, y + (ih - side) // 2
        tiles.append(a[ty : ty + side, tx : tx + side])
    sheet = np.concatenate(tiles, axis=1)
    # a large square is cut into quarters, not scaled, till a tile is no larger than
    # LOOSE_TILE_MAX (SakPix's squares of 192 are tiles of 48, the size of the usual tile sets
    # drawn at that scale: a villager of the same artist is a tile and a half tall)
    cell = side
    while cell > LOOSE_TILE_MAX and cell % 2 == 0:
        cell //= 2
    role, tag = _role(words, TILE_ROLE_WORDS)
    facets: dict[str, Any] = {
        "usage": "tiles",
        "grid": {"cell": [cell, cell], "margin": [0, 0], "separation": [0, 0]},
        "size": [sheet.shape[1], sheet.shape[0]],
        "role": role or "GROUND",
    }
    if tag:
        facets["tags"] = [tag]
    return _Cut([_Part("tiles", sheet, facets, GROUND_CONFIDENCE)])


def _grass(picture: np.ndarray) -> bool:
    rgb = picture[..., :3].reshape(-1, 3).astype(np.float64).mean(axis=0) / 255.0
    r, g, b = rgb
    return g > r * 1.1 and g > b * 1.2


def sort_cells(a: np.ndarray, cell: int) -> _Cut:
    """A mixed tile sheet sorted cell by cell (see the module)."""
    cut = _Cut(reason=UNUSED_SORTED_SHEET)
    mask = a[..., 3] >= PAINTED_ALPHA
    rows, cols = mask.shape[0] // cell, mask.shape[1] // cell
    share = mask.reshape(rows, cell, cols, cell).mean(axis=(1, 3))
    painted = share > 0
    whole = share >= WHOLE
    parent = list(range(rows * cols))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for r in range(rows):
        for c in range(cols):
            if not painted[r, c]:
                continue
            if c + 1 < cols and painted[r, c + 1]:
                edge = mask[r * cell : (r + 1) * cell, (c + 1) * cell - 1 : (c + 1) * cell + 1]
                if (edge[:, 0] & edge[:, 1]).mean() >= JOIN_SHARE:
                    parent[find(r * cols + c + 1)] = find(r * cols + c)
            if r + 1 < rows and painted[r + 1, c]:
                edge = mask[(r + 1) * cell - 1 : (r + 1) * cell + 1, c * cell : (c + 1) * cell]
                if (edge[0] & edge[1]).mean() >= JOIN_SHARE:
                    parent[find((r + 1) * cols + c)] = find(r * cols + c)
    groups: dict[int, list[tuple[int, int]]] = {}
    for r in range(rows):
        for c in range(cols):
            if painted[r, c]:
                groups.setdefault(find(r * cols + c), []).append((r, c))
    for group in sorted(groups.values(), key=lambda m: (min(m), m)):
        full = {(r, c) for r, c in group if whole[r, c]}
        # a patch of ground is whole cells nearly all over; a building has a ragged outline
        mostly = len(full) >= GROUND_WHOLE_SHARE * len(group)
        ground = _ground_cells(a, cell, full) if mostly else set()
        for block in _connected(ground):
            tiles = [a[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell] for r, c in block]
            sheet = np.concatenate(tiles, axis=1)
            r0, c0 = block[0]
            facets: dict[str, Any] = {
                "usage": "tiles",
                "grid": {"cell": [cell, cell], "margin": [0, 0], "separation": [0, 0]},
                "size": [sheet.shape[1], sheet.shape[0]],
                "role": "GROUND",
            }
            if _grass(sheet):
                facets["tags"] = ["surface:grass"]
            cut.parts.append(_Part(f"g{c0 * cell}_{r0 * cell}", sheet, facets, GROUND_CONFIDENCE))
        for members in _connected({m for m in group if m not in ground}):
            if sum(share[r, c] for r, c in members) >= CELL_SPECK:
                cut.parts.append(_object_of(a, mask, cell, members))
    return cut


def _ground_cells(a: np.ndarray, cell: int, full: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """The whole cells of a thing that are ground: those of every block of two by two whole
    cells that tiles with itself (laid beside itself its left column meets its right one, and
    its top row its bottom one, as smoothly as its own neighbouring pixels meet, within
    ``iso_sheets.SEAM_RATIO``). A house drawn over four cells does not tile; grass does."""
    out: set[tuple[int, int]] = set()
    for r, c in sorted(full):
        window = {(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)}
        if not window <= full:
            continue
        block = a[r * cell : (r + 2) * cell, c * cell : (c + 2) * cell, :3].astype(np.int16)
        near = (
            float(np.abs(np.diff(block, axis=0)).mean() + np.abs(np.diff(block, axis=1)).mean()) / 2
        )
        seam = max(
            float(np.abs(block[:, 0] - block[:, -1]).mean()),
            float(np.abs(block[0] - block[-1]).mean()),
        )
        if seam <= iso_sheets.SEAM_RATIO * max(near, 1.0):
            out |= window
    return out


def _connected(cells: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """``cells`` in groups that touch by a side, each sorted, by their first cell."""
    left, out = set(cells), []
    while left:
        start = min(left)
        stack, group = [start], {start}
        left.discard(start)
        while stack:
            r, c = stack.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in left:
                    left.discard(n)
                    group.add(n)
                    stack.append(n)
        out.append(sorted(group))
    return sorted(out)


def _object_of(a: np.ndarray, mask: np.ndarray, cell: int, members: list[tuple[int, int]]) -> _Part:
    """The thing the cells ``members`` of a mixed sheet hold, as one picture."""
    r0 = min(r for r, _c in members)
    c0 = min(c for _r, c in members)
    r1 = max(r for r, _c in members) + 1
    c1 = max(c for _r, c in members) + 1
    box = np.zeros(mask.shape, dtype=bool)
    for r, c in members:
        box[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell] = True
    own = (mask & box)[r0 * cell : r1 * cell, c0 * cell : c1 * cell]
    ys, xs = np.nonzero(own)
    y, x = int(ys.min()), int(xs.min())
    y1, x1 = int(ys.max()) + 1, int(xs.max()) + 1
    picture = a[r0 * cell + y : r0 * cell + y1, c0 * cell + x : c0 * cell + x1].copy()
    picture[~own[y:y1, x:x1]] = 0
    facets, confidence = _thing(picture, "DECORATION", "", False)
    return _Part(f"o{c0 * cell + x}_{r0 * cell + y}", picture, facets, confidence)


def _render_name(f: InventoryFile, variant: str) -> str:
    text = f"sheet_part/{RENDER_VERSION}\n{f.sha256}\n{variant}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


class SheetPartsAdapter:
    name = NAME
    priority = 53  # after the readers of whole formats, LPC, isometric and the farm; before frames

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if len(candidates(inv, set())) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        files = candidates(inv, ctx.claimed)
        tileset = is_tileset_pack(inv)

        def one(f: InventoryFile) -> _Cut:
            ctx.check_cancel()
            try:
                a = _load(root / f.path)
            except (OSError, ValueError) as exc:
                return _Cut(reason="", error=str(exc))
            if float((a[..., 3] < PAINTED_ALPHA).mean()) < MIN_CLEAR:
                return _Cut(reason="")
            cell = grid_cell(a) if tileset else None
            if cell is None and _size(f) in B_TO_E:
                # a sheet of the size of RPG Maker's B to E sheets in a pack that says no tile
                # set is offered as tiles of 48 px by the grid reader (T16.21), as it was
                return _Cut(reason="")
            cut = sort_cells(a, cell) if cell else cut_objects(f, a)
            for part in cut.parts:
                dest = work / _render_name(f, part.variant)
                try:
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        Image.fromarray(part.picture, "RGBA").save(dest, format="PNG")
                except OSError as exc:
                    return _Cut(reason="", error=str(exc))
                part.picture = np.zeros((0, 0, 4), dtype=np.uint8)
            return cut

        cuts = iso_sheets.in_parallel(one, files, ctx)
        for f, cut in zip(files, cuts, strict=True):
            if cut.error:
                issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=cut.error)
            if not cut.parts:
                continue
            for part in cut.parts:
                name = _render_name(f, part.variant)
                project = f"{RENDER_DIR}/{name}"
                result.assets.append(
                    AssetFragment(f.path, part.facets, part.confidence, "full", part.variant)
                )
                result.generated[project] = str(work / name)
                result.rendered[f"{f.path}#{part.variant}"] = project
            result.assets.append(iso_sheets.aside(f, cut.reason or UNUSED_OBJECT_SHEET))
        result.issues = list(issues)
        return result


def counts(result: AdapterResult) -> Counter[str]:
    """How many parts of each role a run cut (for the notes and the tests)."""
    return Counter(str(f.facets.get("role", "")) for f in result.assets if f.variant)

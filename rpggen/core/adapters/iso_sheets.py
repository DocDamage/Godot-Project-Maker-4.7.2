"""Isometric sheets read by the cell their names state (T17.30).

Screaming Brain's isometric packs are no pictures of one tile each: a file is a sheet of
diamonds or of wall faces on a background of one colour (magenta, or black), and the cell is in
its name (``Floor_Dry_01-256x128.png``, ``Flat_Brick_01-SE-128x192.png``) or in the Tiled tile
set beside it (``tilewidth``, ``tileheight`` and the colour that is see-through, ``trans``). No
picture of theirs is a flat tile the isometric reader could measure: eleven of the thirteen
packs stopped with ``TILE-010``. This reader runs before the Tiled reader (whose tile set would
make square tiles of the diamonds) and cuts such a sheet cell by cell:

* **A cell twice as wide as high** is a diamond: the pack's diamond, read from its names. A
  cell that is a flat diamond is a tile (``iso_tile``) standing on it; one that lies inside it
  without filling it (a path, a grid line) is a tile that needs review.
* **A cell as wide as a diamond and higher** is a block: the diamond with its side under it.
* **A square cell** in a pack that names no diamond is a cube on the diamond half as high.
* **A cell half as wide as a diamond and higher than half of it** is a wall face, its top and
  its foot slanting one way (``/``) or the other (``\\``). A face that slants as the upper left
  side of a diamond stands along that side (``w``) or, a diamond further on, along the lower
  right one (``e``); the other along ``n`` or ``s``. Two faces side by side, one each way, are
  one wall: it is put together into four pieces, one for each side of a diamond (``edge``),
  four turns of one set, so that the builder lays a wall along an edge and a house of pieces
  (T17.22). *Doorway* and *Window* in the name tag the pieces ``door`` and ``window``. The
  ``SE`` and ``SW`` in these names say where the light falls (the same faces, lit from the
  other side), so the side is taken from the picture, not from the word.

Every cell is an asset of its own: a variant ``c<column>_<row>`` (and ``_n``, ``_e``, ``_s``,
``_w`` for the pieces of a wall) of its sheet, with its picture drawn into the work folder
with the background made see-through. The sheet itself is set aside (``iso_sheet``). Packs that
draw their diamond in two sizes (*Small* and *Large*) are one set in two sizes (T17.29): every
cell is tagged with its diamond's width and the project uses one. A cell this reader cannot
read (Screaming Brain's thick walls, its corner pieces) stays unread with the reason.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import os
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters import naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import isometric as measure
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

NAME = "iso_sheets"
RENDER_DIR = "generated/iso_cells"
WORK_FOLDER = "iso_cells"
RENDER_VERSION = 1
SOURCE_NAMED = "named"  # the source of the pack's diamond in its warning ``isometric:WxH:named``
UNUSED_SHEET = "iso_sheet"  # the sheet whose cells are assets of their own
UNUSED_PIECE = "iso_piece_not_read"
TURN_GROUP_TAG = "turn_group:"  # the cells of one wall: catalog.turn_sets groups them by it
SIDES = ("n", "e", "s", "w")
TILE_CONFIDENCE = 0.85
WALL_CONFIDENCE = 0.85
LOOSE_CONFIDENCE = 0.6  # a cell inside its diamond that does not fill it: needs review
KEY_TOLERANCE = 8  # a pixel this near the background colour in every channel is background
KEY_SHARE = 0.05  # the corner's colour is a background when this share of the sheet has it
PAINTED_SHARE = 0.01  # a cell with fewer painted pixels than this share of it is empty
SLANT_SHARE = 0.25  # a face slants when its foot falls this share of the diamond's height
# a sheet may be this many pixels wider or higher than its whole cells (the *Town Pack*'s roofs:
# 432 wide in cells of 143); what is left over at the right and the bottom is no cell
SHEET_SLACK = 4
_TSX_TILE = re.compile(r"<tileset\b[^>]*>", re.IGNORECASE)
_TSX_IMAGE = re.compile(r"<image\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r'\b([a-z]+)\s*=\s*"([^"]*)"', re.IGNORECASE)
_WORDS_DOOR = frozenset({"door", "doors", "doorway", "doorways", "gate", "entrance"})
_WORDS_WINDOW = frozenset({"window", "windows", "windowa", "windowb", "windowc"})
_WORDS_WATER = frozenset({"water", "sea", "ocean", "lake", "river", "shoals"})
_WORDS_ROAD = frozenset({"road", "roads", "path", "paths", "pathway", "pathways", "street"})
_WORDS_ROOF = frozenset({"roof", "roofs", "roofing"})
_WORDS_POST = frozenset({"corner", "corners", "pillar", "pillars", "post", "posts", "pole"})
ROOF_WIDER = 1.3  # a roof's cell is at most this many times as wide as its diamond
THICK_WIDER = 1.25  # a thick wall's face is at most this many times as wide as a flat one's
POST_CONFIDENCE = 0.85
ROOF_CONFIDENCE = 0.85


@dataclass(frozen=True)
class Diamond:
    width: int
    height: int


@dataclass
class _Sheet:
    """A picture whose cell is stated, and how its background is told."""

    f: InventoryFile
    cell: tuple[int, int]
    key: tuple[int, int, int] | None  # the background's colour; None: the see-through pixels
    kind: str = ""  # "diamond", "block", "cube", "wall", or "" (not read)
    diamond: Diamond | None = None


@dataclass
class _Read:
    """What the reader made, before it becomes fragments."""

    fragments: list[AssetFragment] = field(default_factory=list)
    rendered: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (project, file)
    pictures: dict[str, np.ndarray] = field(default_factory=dict)  # key -> the cell's picture


MAX_WORKERS = 8


def in_parallel[T, R](
    job: Callable[[T], R], items: list[T], ctx: AdapterContext | None = None
) -> list[R]:
    """``job`` of every item, in a pool of threads as the images are analysed
    (``analyzer.prewarm``), the results in the order of ``items`` so that nothing depends on
    which thread was first. The worker's cancel is polled before every item and after every
    result: a cancel raises ``archive.Cancelled`` and drops what has not started."""
    if not items:
        return []
    workers = max(1, min(len(items), os.cpu_count() or 1, MAX_WORKERS))
    if workers == 1:
        out = []
        for item in items:
            if ctx is not None:
                ctx.check_cancel()
            out.append(job(item))
        return out
    pool = concurrent.futures.ThreadPoolExecutor(workers)
    try:
        futures = [pool.submit(job, item) for item in items]
        out = []
        for future in futures:
            out.append(future.result())
            if ctx is not None:
                ctx.check_cancel()
    except BaseException:
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return out


def _is_still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext in (".png", ".bmp")


def _size(f: InventoryFile) -> tuple[int, int]:
    image = f.image or {}
    return int(image.get("w", 0)), int(image.get("h", 0))


def _words(path: str) -> set[str]:
    folders, stem = classifier.tokens(path)
    return {w.casefold() for w in (*folders, *stem)}


def tsx_cells(inv: Inventory, root: Path) -> dict[str, tuple[tuple[int, int], tuple[int, ...]]]:
    """``{picture path: (cell, background colour or ())}`` from the Tiled tile sets of a pack
    that name a picture of it (``<tileset tilewidth tileheight>``, ``<image source trans>``)."""
    by_lower = {f.path.casefold(): f.path for f in inv.files}
    out: dict[str, tuple[tuple[int, int], tuple[int, ...]]] = {}
    for f in sorted(inv.files, key=lambda f: f.path):
        if f.ext != ".tsx" or f.size > 64 * 1024:
            continue
        try:
            text = (root / f.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        head, image = _TSX_TILE.search(text), _TSX_IMAGE.search(text)
        if head is None or image is None:
            continue
        attrs, img = dict(_ATTR.findall(head.group(0))), dict(_ATTR.findall(image.group(0)))
        try:
            cell = (int(attrs["tilewidth"]), int(attrs["tileheight"]))
        except (KeyError, ValueError):
            continue
        source = posixpath.normpath(
            posixpath.join(posixpath.dirname(f.path), img.get("source", ""))
        )
        target = by_lower.get(source.casefold())
        trans = img.get("trans", "").lstrip("#")
        key: tuple[int, ...] = ()
        if re.fullmatch(r"[0-9a-fA-F]{6}", trans):
            key = (int(trans[0:2], 16), int(trans[2:4], 16), int(trans[4:6], 16))
        if target is not None and min(cell) > 0 and target not in out:
            out[target] = (cell, key)
    return out


def _named(f: InventoryFile) -> tuple[int, int] | None:
    """The cell a picture's name states, else its folder's (``Large 256x128/Floor_01.png``)."""
    stem = posixpath.splitext(posixpath.basename(f.path))[0]
    found = naming.named_cell(stem)
    if found is None:
        found = naming.named_cell(posixpath.basename(posixpath.dirname(f.path)))
    return found


def candidates(inv: Inventory, root: Path, claimed: set[str]) -> list[_Sheet]:
    """The pictures of a pack whose cell is stated and that hold whole cells of it."""
    from_tsx = tsx_cells(inv, root)
    found: list[_Sheet] = []
    for f in sorted(inv.files, key=lambda f: f.path):
        if not _is_still(f) or f.path in claimed:
            continue
        said = from_tsx.get(f.path)
        cell = said[0] if said else _named(f)
        if cell is None:
            continue
        w, h = _size(f)
        if w < cell[0] or h < cell[1] or w % cell[0] > SHEET_SLACK or h % cell[1] > SHEET_SLACK:
            continue
        key = tuple(said[1]) if said and said[1] else None
        found.append(_Sheet(f, cell, key))  # type: ignore[arg-type]
    return found


def pack_diamonds(sheets: list[_Sheet]) -> list[Diamond]:
    """The diamonds the cells of a pack name (twice as wide as high), smallest first; a pack
    that names none but square cells (a pack of crates) stands them on the diamond half as
    high as they are wide."""
    named = sorted({(s.cell[0], s.cell[1]) for s in sheets if abs(s.cell[0] - 2 * s.cell[1]) <= 1})
    if not named:
        named = sorted({(s.cell[0], s.cell[0] // 2) for s in sheets if s.cell[0] == s.cell[1]})
    return [Diamond(w, h) for w, h in named]


def face_diamonds(
    root: Path, sheets: list[_Sheet], ctx: AdapterContext | None = None
) -> list[Diamond]:
    """The diamonds of a pack of wall faces that names none (Screaming Brain's *Wall Pack*:
    cells of 128 x 192 and 64 x 96): a face as high as it is wide and more whose foot falls
    from one of its sides to the other stands along a side of a diamond twice as wide, as high
    as twice that fall. Only faces of the 2 : 1 angle are read so (the fall half the width).
    One sheet of each cell size is looked at."""
    found: set[tuple[int, int]] = set()
    for sheet in sheets:
        cw, ch = sheet.cell
        if ch <= cw or (2 * cw, cw) in found:
            continue
        if ctx is not None:
            ctx.check_cancel()
        try:
            a = _load(root / sheet.f.path)
        except (OSError, ValueError):
            continue
        a = keyed(a, _key_of(a, sheet.key))
        for row in range(a.shape[0] // ch):
            for col in range(a.shape[1] // cw):
                mask = measure.painted(a[row * ch : (row + 1) * ch, col * cw : (col + 1) * cw])
                if mask.mean() < PAINTED_SHARE:
                    continue
                if slant(mask, cw / 2) and _straight_ends(mask):
                    found.add((2 * cw, cw))
                break
            else:
                continue
            break
    return [Diamond(w, h) for w, h in sorted(found)]


def classify_sheets(sheets: list[_Sheet], diamonds: list[Diamond]) -> None:
    """Give every sheet the kind of its cell and the diamond it stands on."""
    tests = (
        ("diamond", lambda cw, ch, d: (cw, ch) == (d.width, d.height)),
        ("wall", lambda cw, ch, d: 2 * cw == d.width and ch > cw),
        ("cube", lambda cw, ch, d: cw == ch == d.width == 2 * d.height),
        ("block", lambda cw, ch, d: cw == d.width and d.height < ch <= d.height * 3 // 2),
    )
    # after T17.30: the pieces of Screaming Brain's walls and towns, by their names and cells
    named_tests = (
        # a roof over one diamond, its eaves a little wider (*Town Roofing*, 143 x 92 on 128)
        ("roof", _WORDS_ROOF, lambda cw, ch, d: d.width < cw <= d.width * ROOF_WIDER),
        # a post at a corner of walls (*Corner_Brick*, 80 x 100 beside walls of 64 x 96)
        ("post", _WORDS_POST, lambda cw, ch, d: d.width // 2 < cw <= d.width and ch > cw),
    )
    for sheet in sheets:
        for kind, fits in tests:
            d = next((d for d in diamonds if fits(sheet.cell[0], sheet.cell[1], d)), None)
            if d is not None:
                sheet.kind, sheet.diamond = kind, d
                break
        if sheet.kind:
            continue
        said = _words(sheet.f.path)
        for kind, words, named_fit in named_tests:
            d = next((d for d in diamonds if named_fit(sheet.cell[0], sheet.cell[1], d)), None)
            if d is not None and said & words:
                sheet.kind, sheet.diamond = kind, d
                break
        if sheet.kind:
            continue
        # a thick wall's face: half a diamond wide and the end of the wall beside it
        cw, ch = sheet.cell
        d = next(
            (d for d in diamonds if d.width // 2 < cw <= d.width // 2 * THICK_WIDER and ch > cw),
            None,
        )
        if d is not None:
            sheet.kind, sheet.diamond = "thick", d


def _key_of(a: np.ndarray, said: tuple[int, int, int] | None) -> tuple[int, int, int] | None:
    """The colour of a sheet's background: the tile set's ``trans``, else the colour of its
    corner when a fair share of the opaque sheet has it, else None (the see-through pixels)."""
    if said is not None:
        return said
    corner = a[0, 0]
    if int(corner[3]) < 128:
        return None
    near = (np.abs(a[..., :3].astype(np.int16) - corner[:3].astype(np.int16)) <= KEY_TOLERANCE).all(
        axis=2
    )
    if near.mean() >= KEY_SHARE:
        return (int(corner[0]), int(corner[1]), int(corner[2]))
    return _border_key(a)


BORDER_SHARE = 0.25  # the commonest colour of a sheet's border is its background from this share


def _border_key(a: np.ndarray) -> tuple[int, int, int] | None:
    """The background of a sheet whose corner is painted (the *Town Pack*'s walls fill their
    cells to the top left corner): the commonest colour of its outermost rows and columns, when
    a quarter of that border and ``KEY_SHARE`` of the sheet have it and the sheet is opaque.
    None otherwise (a texture has no colour that common)."""
    if not bool((a[..., 3] == 255).all()):
        return None
    border = np.concatenate([a[0, :, :3], a[-1, :, :3], a[:, 0, :3], a[:, -1, :3]])
    colours, counts = np.unique(border, axis=0, return_counts=True)
    best = colours[int(counts.argmax())]
    if counts.max() < BORDER_SHARE * len(border):
        return None
    near = (np.abs(a[..., :3].astype(np.int16) - best.astype(np.int16)) <= KEY_TOLERANCE).all(
        axis=2
    )
    if near.mean() < KEY_SHARE:
        return None
    return (int(best[0]), int(best[1]), int(best[2]))


def keyed(a: np.ndarray, key: tuple[int, int, int] | None) -> np.ndarray:
    """``a`` with its background made see-through."""
    out = a.copy()
    if key is not None:
        near = (
            np.abs(a[..., :3].astype(np.int16) - np.array(key, dtype=np.int16)) <= KEY_TOLERANCE
        ).all(axis=2)
        out[near] = 0
    return out


def slant(mask: np.ndarray, drop: float) -> str:
    """``"/"`` when the foot of a wall face rises from its left to its right column by about
    ``drop`` rows, ``"\\"`` when it falls by as much, "" otherwise."""
    cols = mask.any(axis=0)
    if not cols[0] or not cols[-1]:
        return ""
    left = mask.shape[0] - 1 - int(mask[::-1, 0].argmax())
    right = mask.shape[0] - 1 - int(mask[::-1, -1].argmax())
    if abs(abs(left - right) - drop) > drop * SLANT_SHARE + 1:
        return ""
    return "/" if left > right else "\\"


END_SHARE = 0.15  # the columns at each end of a face whose foot must run one way


def _straight_ends(mask: np.ndarray) -> bool:
    """True when the foot of a wall face runs one way at both of its ends, as a flat face's
    does. A thick wall's face (Screaming Brain's *Thick* walls) shows the end of the wall at
    one side, its foot running back the other way: its cell is wider than half its diamond,
    and it is no face to take the diamond from (it gave 144 x 72 for walls of 128 x 64)."""
    columns = np.nonzero(mask.any(axis=0))[0]
    if columns.size < 8:
        return False
    foot = np.array([mask.shape[0] - 1 - int(mask[::-1, c].argmax()) for c in columns])
    end = max(2, int(round(columns.size * END_SHARE)))
    steps = np.diff(foot.astype(int))
    for part in (steps[:end], steps[-end:]):
        if (part > 0).any() and (part < 0).any():
            return False
    return bool(np.sign(steps[:end].sum()) == np.sign(steps[-end:].sum()))


SEAM_RATIO = 3.0  # a texture tiles on its diamond when its seams differ this little


def diamond_of(a: np.ndarray, d: Diamond) -> np.ndarray | None:
    """The diamond ``d`` cut from the middle of an opaque picture that tiles on it (T17.30: a
    large ground picture, a texture of an isometric pack), or None when it does not: laid on
    the grid of the diamond, a copy half a diamond right and down meets this one along the
    lower right edge, so the pixels just inside that edge are compared with the ones just
    inside the upper left edge (and the lower left with the upper right). The seams may differ
    ``SEAM_RATIO`` times as much as two neighbouring pixels inside the picture do, at most."""
    h, w = a.shape[:2]
    if w < d.width or h < d.height:
        return None
    x0, y0 = (w - d.width) // 2, (h - d.height) // 2
    part = a[y0 : y0 + d.height, x0 : x0 + d.width].astype(np.int16)
    ys, xs = np.mgrid[0 : d.height, 0 : d.width]
    u = (xs + 0.5 - d.width / 2) / (d.width / 2)
    v = (ys + 0.5 - d.height / 2) / (d.height / 2)
    inside = np.abs(u) + np.abs(v) <= 1.0
    rgb = part[..., :3]
    near = float(np.abs(np.diff(rgb, axis=1)).mean() + np.abs(np.diff(rgb, axis=0)).mean()) / 2
    seams = []
    for t in np.linspace(0.1, 0.9, 17):
        # (lower right edge, upper left edge) and (lower left, upper right), a pixel inside
        for (ax, ay), (bx, by) in (
            ((0.5 + t / 2, 0.5 + (1 - t) / 2), (t / 2, (1 - t) / 2)),
            ((0.5 - t / 2, 0.5 + (1 - t) / 2), (1 - t / 2, (1 - t) / 2)),
        ):
            pa = rgb[min(d.height - 1, int(ay * d.height) - 1), min(d.width - 1, int(ax * d.width))]
            pb = rgb[min(d.height - 1, int(by * d.height) + 1), min(d.width - 1, int(bx * d.width))]
            seams.append(float(np.abs(pa - pb).mean()))
    if not seams or float(np.mean(seams)) > SEAM_RATIO * max(near, 1.0):
        return None
    out = part.astype(np.uint8)
    out[~inside] = 0
    return out


GROUND_WORDS = frozenset({"ground", "floor", "floors", "terrain", "grass", "dirt", "earth"})
SOURCE_GROUND = "ground_picture"
FIGURE_SCALE = 1.0  # a ground picture's diamond is halved while it stays this wide, of a figure
MIN_GROUND = 32
PLAIN_STD = 2.0  # a ground picture whose colours vary less than this is a plain overlay


def ground_pictures(
    root: Path,
    stills: list[InventoryFile],
    work: Path,
    result: AdapterResult,
    ctx: AdapterContext | None = None,
    figures: list[int] | None = None,
) -> tuple[int, int] | None:
    """The ground of an isometric pack whose diamond nothing else says (*Lords Of Pain*: four
    pictures of 256 x 256 in ``environment/``, no flat tile, no size in a name): an opaque
    picture named ground or floor that tiles on a diamond of the 2 : 1 angle of the classic
    isometric packs is that diamond's ground, cut from its middle. The diamond is as wide as
    the largest such picture, halved while the half is still as wide as ``FIGURE_SCALE`` times
    the pack's own characters (``figures``: the widths of their frames, the middle one; *Lords
    Of Pain*'s figures of about 100 px would stand on diamonds of 256 a speck), and never under
    ``MIN_GROUND``. None when no
    picture tiles. The pictures read so are added to ``result`` as variants ``diamond`` of their
    files, the files set aside."""
    pictures = [
        f
        for f in sorted(stills, key=lambda f: f.path)
        if _words(f.path) & GROUND_WORDS
        and _size(f)[0] >= MIN_GROUND
        and _size(f)[1] >= _size(f)[0] // 2
    ]
    if not pictures:
        return None
    width = max(_size(f)[0] for f in pictures)
    if figures:
        target = FIGURE_SCALE * sorted(figures)[(len(figures) - 1) // 2]
        while width // 2 >= target and width % 2 == 0 and width // 2 >= MIN_GROUND:
            width //= 2
    d = Diamond(width, width // 2)
    found: list[tuple[InventoryFile, np.ndarray]] = []
    for f in pictures:
        if ctx is not None:
            ctx.check_cancel()
        try:
            a = _load(root / f.path)
        except (OSError, ValueError):
            continue
        if not bool((a[..., 3] == 255).all()) or float(a[..., :3].std()) < PLAIN_STD:
            continue  # see-through, or one colour all over (a darkening overlay): no ground
        cut = diamond_of(a, d)
        if cut is not None:
            found.append((f, cut))
    if not found:
        return None
    for f, cut in found:
        facets: dict[str, Any] = {
            "usage": "iso_tile",
            "projection": "isometric",
            "canvas": [d.width, d.height],
            "footprint": [d.width, d.height],
            "origin": [d.width // 2, d.height // 2],
            "rise": 0,
            "size": [d.width, d.height],
            "role": "GROUND",
        }
        name = _render_name(f, "diamond")
        dest = work / name
        try:
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                _save(cut, dest)
        except OSError:
            continue
        key = f"{f.path}#diamond"
        result.assets.append(AssetFragment(f.path, facets, TILE_CONFIDENCE, "full", "diamond"))
        result.assets.append(aside(f, UNUSED_SHEET))
        result.generated[f"{RENDER_DIR}/{name}"] = str(dest)
        result.rendered[key] = f"{RENDER_DIR}/{name}"
    return d.width, d.height


def _render_name(sheet: InventoryFile, part: str) -> str:
    text = f"iso_cell/{RENDER_VERSION}\n{sheet.sha256}\n{part}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


class IsoSheetsAdapter:
    name = NAME
    priority = 8  # before the Tiled reader, whose tile sets would cut the diamonds in squares

    def match(self, inv: Inventory, root: Path) -> float:
        from rpggen.core.adapters import isometric

        words = isometric.pack_words(inv, root)
        if not words.isometric or words.excluded:
            return 0.0
        sheets = candidates(inv, root, set())
        diamonds = pack_diamonds(sheets) or face_diamonds(root, sheets)
        classify_sheets(sheets, diamonds)
        return 1.0 if any(s.kind for s in sheets) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        from rpggen.core.adapters import isometric

        result = AdapterResult(self.name)
        issues = IssueList()
        words = isometric.pack_words(inv, root)
        if not words.isometric or words.excluded:
            return result
        sheets = candidates(inv, root, ctx.claimed)
        diamonds = pack_diamonds(sheets) or face_diamonds(root, sheets, ctx)
        classify_sheets(sheets, diamonds)
        if not any(s.kind for s in sheets):
            return result
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        several = len({d.width for d in diamonds}) > 1
        cut = [s for s in sheets if s.kind]

        def one(sheet: _Sheet) -> tuple[_Read, str]:
            """Cut one sheet and draw its cells into the work folder (in a worker thread)."""
            ctx.check_cancel()
            try:
                a = _load(root / sheet.f.path)
                read = self._cells(sheet, keyed(a, _key_of(a, sheet.key)))
                for key, (_project, picture) in read.rendered.items():
                    dest = work / picture
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        _save(read.pictures[key], dest)
            except (OSError, ValueError) as exc:
                return _Read(), str(exc)
            read.pictures.clear()
            return read, ""

        for sheet, (read, error) in zip(cut, in_parallel(one, cut, ctx), strict=True):
            if error:
                issues.add("ADAPT-001", adapter=self.name, file=sheet.f.path, reason=error)
                continue
            size_tag = f"size_form:{sheet.diamond.width}" if several and sheet.diamond else ""
            for frag in read.fragments:
                if size_tag:
                    frag.facets["tags"] = sorted({*frag.facets.get("tags", []), size_tag})
                key = f"{frag.path}#{frag.variant}"
                project, picture = read.rendered[key]
                result.assets.append(frag)
                result.generated[project] = str(work / picture)
                result.rendered[key] = project
            reason = UNUSED_SHEET if read.fragments else UNUSED_PIECE
            result.assets.append(aside(sheet.f, reason))
        for sheet in sheets:
            if not sheet.kind:
                result.assets.append(aside(sheet.f, UNUSED_PIECE))
        if diamonds:
            d = diamonds[0]
            result.pack_warnings.append(
                f"{classifier.ISOMETRIC_MARK}{d.width}x{d.height}:{SOURCE_NAMED}"
            )
        result.issues = list(issues)
        return result

    # ------------------------------------------------------------------ cells

    def _cells(self, sheet: _Sheet, a: np.ndarray) -> _Read:
        read = _Read()
        cw, ch = sheet.cell
        rows, cols = a.shape[0] // ch, a.shape[1] // cw
        if bool((a[..., 3] == 255).all()):
            # no background at all: a texture (*Isometric Floor Texture Pack*), ground only
            # when it is a diamond's picture that tiles on the diamond (see ``diamond_of``)
            if sheet.kind == "diamond" and (rows, cols) == (1, 1) and sheet.diamond is not None:
                cut = diamond_of(a, sheet.diamond)
                if cut is not None:
                    facets, confidence = self._tile(sheet, cut)
                    if facets is not None:
                        self._add(read, sheet, "diamond", cut, facets, confidence)
            return read

        cells: dict[tuple[int, int], np.ndarray] = {}
        for row in range(rows):
            for col in range(cols):
                part = a[row * ch : (row + 1) * ch, col * cw : (col + 1) * cw]
                if (part[..., 3] >= measure.PAINTED_ALPHA).mean() >= PAINTED_SHARE:
                    cells[(col, row)] = part
        if sheet.kind == "wall":
            self._walls(sheet, cells, read)
            return read
        if sheet.kind == "thick":
            self._walls(sheet, self._thick_faces(sheet, cells), read, ("thick",))
            return read
        if sheet.kind == "post":
            self._posts(sheet, cells, read)
            return read
        if sheet.kind == "roof":
            self._roofs(sheet, cells, read)
            return read
        for (col, row), part in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            facets, confidence = self._tile(sheet, part)
            if facets is None:
                continue
            self._add(read, sheet, f"c{col}_{row}", part, facets, confidence)
        return read

    def _tile(self, sheet: _Sheet, part: np.ndarray) -> tuple[dict[str, Any] | None, float]:
        """The facets of a cell that is a diamond, a block or a cube."""
        d = sheet.diamond
        assert d is not None
        h, w = part.shape[:2]
        mask = measure.painted(part)
        facets: dict[str, Any] = {
            "usage": "iso_tile",
            "projection": "isometric",
            "canvas": [w, h],
            "footprint": [d.width, d.height],
            "origin": [w // 2, d.height // 2],
            "rise": 0,
            "size": [w, h],
        }
        role = self._role(sheet.f.path)
        if role:
            facets["role"] = role
        if sheet.kind == "diamond":
            flat = measure.flat_tile(mask)
            if flat is not None and flat.width >= d.width - 2:
                face = measure.face_colour(part, (w / 2, h / 2), (d.width, d.height))
                if face == measure.FACE_GRASS and not classifier.suggested_surface(sheet.f.path):
                    facets["tags"] = [f"surface:{face}"]
                return facets, TILE_CONFIDENCE
            return facets, LOOSE_CONFIDENCE  # a path, a line of a grid: inside, not filling
        base = measure.block_base(mask)
        if base is not None and abs(base.width - d.width) <= 2:
            return facets, TILE_CONFIDENCE
        return facets, LOOSE_CONFIDENCE

    @staticmethod
    def _role(path: str) -> str:
        said = _words(path)
        if said & _WORDS_WATER:
            return "WATER"
        if said & _WORDS_ROAD:
            return "ROAD"
        if said & {"crate", "crates", "box", "boxes", "barrel", "barrels"}:
            return "DECORATION"
        return "GROUND"

    @staticmethod
    def _thick_faces(
        sheet: _Sheet, cells: dict[tuple[int, int], np.ndarray]
    ) -> dict[tuple[int, int], np.ndarray]:
        """The faces of a thick wall's cells, each as wide as a flat face: a face slanting
        ``/`` shows the wall's end at its left (the wall's thickness, behind the face), one
        slanting ``\\`` at its right; the end is cut off and the face is read as a flat one.
        Its top keeps the wall's thickness. The posts of the pack stand where two such walls
        meet. A cell whose face slants neither way is left out."""
        d = sheet.diamond
        assert d is not None
        half = d.width // 2
        out: dict[tuple[int, int], np.ndarray] = {}
        for at, part in cells.items():
            extra = part.shape[1] - half
            left_cut, right_cut = part[:, extra:], part[:, :half]
            if slant(measure.painted(left_cut), d.height / 2) == "/":
                out[at] = left_cut
            elif slant(measure.painted(right_cut), d.height / 2) == "\\":
                out[at] = right_cut
        return out

    def _posts(self, sheet: _Sheet, cells: dict[tuple[int, int], np.ndarray], read: _Read) -> None:
        """Posts (*Corner_Brick*: a narrow upright block that stands where two walls meet),
        each put at the four corners of a diamond's canvas: four pieces, turns of one set, each
        with the facet ``post`` (the corner: ``nw`` the top one, ``ne``, ``es``, ``sw``), so
        that the builder puts one where the sides of a wall meet."""
        d = sheet.diamond
        assert d is not None
        for (col, row), part in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            found = measure.outline(measure.painted(part))
            if found is None:
                continue
            x, y, pw, ph = found[0]
            if pw > measure.POST_WIDTH * d.width or ph < measure.POST_HEIGHT * pw:
                continue
            post = part[y : y + ph, x : x + pw]
            fx, fy = (pw - 1) / 2.0, ph - 1 - pw / 4.0
            ox = int(np.ceil(d.width / 2 + fx)) + 1
            oy = int(np.ceil(d.height / 2 + fy)) + 1
            cw = ox + int(np.ceil(d.width / 2 + pw - fx)) + 1
            ch = oy + int(np.ceil(d.height / 2 + ph - fy)) + 1
            group = f"c{col}_{row}"
            for turn, (corner, (cu, cv)) in enumerate(measure.CORNERS.items()):
                canvas = np.zeros((ch, cw, 4), dtype=np.uint8)
                px = int(round(ox + (cu - cv) * d.width / 2 - fx))
                py = int(round(oy + (cu + cv - 1) * d.height / 2 - fy))
                canvas[py : py + ph, px : px + pw] = post
                facets: dict[str, Any] = {
                    "usage": "iso_tile",
                    "projection": "isometric",
                    "canvas": [cw, ch],
                    "footprint": [d.width, d.height],
                    "origin": [ox, oy],
                    "rise": max(0, oy - d.height // 2 - py),
                    "size": [cw, ch],
                    "role": "DECORATION",
                    "post": corner,
                    "turn": turn,
                    "tags": sorted({"post", f"{TURN_GROUP_TAG}{group}"}),
                }
                measured = measure.post_corner(canvas, (ox, oy), (d.width, d.height))
                confidence = POST_CONFIDENCE if measured == corner else LOOSE_CONFIDENCE
                self._add(read, sheet, f"{group}_{corner}", canvas, facets, confidence)

    def _roofs(self, sheet: _Sheet, cells: dict[tuple[int, int], np.ndarray], read: _Read) -> None:
        """Roofs over one diamond (*Town Roofing*): each cell a tile tagged ``roof`` whose
        ``origin`` is the middle of the diamond its eaves cover (as wide as the roof, its lowest
        corner the roof's lowest pixel). Each is a whole roof of one cell (low hipped roofs,
        flat ones with a parapet): no piece of a larger roof, so it has no ``roof`` shape and
        a house of several cells gets one a cell."""
        d = sheet.diamond
        assert d is not None
        for (col, row), part in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            box = measure.outline(measure.painted(part))
            if box is None:
                continue
            x, y, bw, bh = box[0]
            origin = [int(round(x + (bw - 1) / 2.0)), int(round(y + bh - 1 - bw / 4.0))]
            h, w = part.shape[:2]
            facets: dict[str, Any] = {
                "usage": "iso_tile",
                "projection": "isometric",
                "canvas": [w, h],
                "footprint": [d.width, d.height],
                "origin": origin,
                "rise": max(0, origin[1] - d.height // 2 - y),
                "size": [w, h],
                "role": "DECORATION",
                "tags": ["roof"],
            }
            self._add(read, sheet, f"c{col}_{row}", part, facets, ROOF_CONFIDENCE)

    def _walls(
        self,
        sheet: _Sheet,
        cells: dict[tuple[int, int], np.ndarray],
        read: _Read,
        more_tags: tuple[str, ...] = (),
    ) -> None:
        """Wall faces in pairs, one slanting each way, put together into the four pieces of a
        wall (see the module). ``more_tags`` are given to every piece (``thick``)."""
        d = sheet.diamond
        assert d is not None
        said = _words(sheet.f.path)
        tags = sorted(
            ({"door"} if said & _WORDS_DOOR else set())
            | ({"window"} if said & _WORDS_WINDOW else set())
            | set(more_tags)
        )
        faces = {at: slant(measure.painted(part), d.height / 2) for at, part in cells.items()}
        done: set[tuple[int, int]] = set()
        for col, row in sorted(cells, key=lambda at: (at[1], at[0])):
            if (col, row) in done or not faces[(col, row)]:
                continue
            pair = {faces[(col, row)]: (col, row)}
            other = (col + 1, row)
            if other in cells and faces.get(other) and faces[other] != faces[(col, row)]:
                pair[faces[other]] = other
                done.add(other)
            done.add((col, row))
            group = f"c{col}_{row}"
            pieces: list[tuple[str, np.ndarray]] = []
            if "/" in pair:
                face = cells[pair["/"]]
                pieces += [("w", self._piece(face, d, 0, 0)), ("e", self._piece(face, d, 1, 1))]
            if "\\" in pair:
                face = cells[pair["\\"]]
                pieces += [("n", self._piece(face, d, 1, 0)), ("s", self._piece(face, d, 0, 1))]
            for side, picture in sorted(pieces, key=lambda p: SIDES.index(p[0])):
                facets, confidence = self._wall_facets(picture, d, side)
                facets["turn"] = SIDES.index(side)
                facets["tags"] = sorted({*tags, f"{TURN_GROUP_TAG}{group}"})
                self._add(read, sheet, f"{group}_{side}", picture, facets, confidence)

    @staticmethod
    def _piece(face: np.ndarray, d: Diamond, right: int, low: int) -> np.ndarray:
        """A wall face on the canvas of a diamond: as wide as the diamond and half its height
        higher than the face, the diamond at the bottom, the face along the side it is put on
        (on the left or the right half, at the top or half a diamond down)."""
        ch, cw = face.shape[:2]
        canvas = np.zeros((ch + d.height // 2, d.width, 4), dtype=np.uint8)
        x, y = right * cw, low * (d.height // 2)
        canvas[y : y + ch, x : x + cw] = face
        return canvas

    @staticmethod
    def _wall_facets(picture: np.ndarray, d: Diamond, side: str) -> tuple[dict[str, Any], float]:
        h, w = picture.shape[:2]
        origin = [w // 2, h - d.height // 2]
        mask = measure.painted(picture)
        rows = np.nonzero(mask.any(axis=1))[0]
        top = int(rows[0]) if rows.size else 0
        facets: dict[str, Any] = {
            "usage": "iso_tile",
            "projection": "isometric",
            "canvas": [w, h],
            "footprint": [d.width, d.height],
            "origin": origin,
            "rise": max(0, origin[1] - d.height // 2 - top),
            "edge": side,
            "role": "WALL",
            "size": [w, h],
        }
        # the side the face was put on, checked as the isometric reader measures a wall
        columns = np.nonzero(mask.any(axis=0))[0]
        foot = np.array([h - 1 - int(mask[::-1, c].argmax()) for c in columns])
        measured = measure.edge_side(columns, foot, (origin[0], origin[1]), (d.width, d.height))
        return facets, WALL_CONFIDENCE if measured == side else LOOSE_CONFIDENCE

    @staticmethod
    def _add(
        read: _Read,
        sheet: _Sheet,
        variant: str,
        picture: np.ndarray,
        facets: dict[str, Any],
        confidence: float,
    ) -> None:
        key = f"{sheet.f.path}#{variant}"
        name = _render_name(sheet.f, variant)
        read.rendered[key] = (f"{RENDER_DIR}/{name}", name)
        read.pictures[key] = picture
        read.fragments.append(AssetFragment(sheet.f.path, facets, confidence, "full", variant))


def _load(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8)


def _save(a: np.ndarray, dest: Path) -> None:
    Image.fromarray(a, "RGBA").save(dest, format="PNG", optimize=False, pnginfo=None)


def aside(f: InventoryFile, reason: str) -> AssetFragment:
    w, h = _size(f)
    facets = {
        "usage": "sprite",
        "frame": [w, h],
        "origin": [w // 2, max(0, h - 1)],
        "role": "NONE",
        "tags": [classifier.UNUSED_TAG + reason],
    }
    return AssetFragment(f.path, facets, 0.9, "full")

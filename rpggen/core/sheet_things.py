"""The loose things of a tile sheet (T17.33): what the dock places of a sheet of tiles.

A tile sheet often holds more than ground. Kenney's *Tiny Farm* has one sheet of 132 tiles: its
paths of soil, and beside them trees, bushes, rocks, buckets, sacks, crates and flowers, each
standing in a cell of its own on see-through pixels. The 132 single files the pack ships are
set aside as copies of the sheet's cells (``pack_forms``), so without this the trees and rocks
were only tiles of the sheet: a user building a level had to paint them as tiles, with no
collision and no sorting by depth, instead of placing them from the dock.

A cell of a used sheet of tiles is a **thing** when:

* no terrain and no tile of its own takes it (``tile_overrides``), and no part of the sheet cut
  by another reader (a character, a crop) and no object of the sheet lies on it;
* it is painted in part on see-through pixels (``MIN_COVER`` to ``MAX_COVER`` of the cell): a
  whole cell is a piece of ground, a speck is nothing;
* its art stays in its cell: at most one of its four borders is painted along more than
  ``EDGE_SHARE`` of it (a tree stands on the bottom one). The pieces of something larger (the
  walls and the roof of a barn drawn over several cells) go on over two borders or more and
  stay tiles, as their sheet draws them;
* it is not a copy of a picture of the pack that is used on its own (a character, an animal).

Each thing is a ``DECORATION`` object of its sheet (``SheetObject``) named by how it looks
(its colour and shape, ``green_tall``), tagged ``sheet_thing``, with a footprint and a
collision at the foot of what it paints; a small thing (a flower, a tuft) has no collision. A
sheet with more than ``MAX_THINGS`` such cells is a sheet of tiles to paint and gives none.
No Qt; Pillow and NumPy.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

TAG = "sheet_thing"
PAINTED_ALPHA = 128
MIN_COVER = 0.08
MAX_COVER = 0.9
EDGE_SHARE = 0.5
SOLID_COVER = 0.2  # a thing painting less of its cell than this is walked through
OUTLINE_VALUE = 0.35  # a pixel this dark or darker is an outline
MAX_THINGS = 300
JOIN_SHARE = 0.25  # art goes on into the next cell along this share of their border
JOIN_PIXELS = 2
JOIN_COLOUR = 80  # of 255 per channel: much the same colour across the line between cells
JOIN_MATCH = 0.25  # of the pixels both borders paint
MAX_GROUP = 2  # cells each way: a larger group is part of a building, drawn as tiles
GLYPH_RUN = 6  # glyphs side by side in a row, at least, make a font
GLYPH_COVER = 0.55  # a glyph paints at most this share of its cell
GLYPH_COLOURS = 4  # ... in at most this many colours, for the whole row
CONFIDENCE = 0.6
WORK_FOLDER = "sheet_things"
RENDER_DIR = "generated/sheet_things"
PART_OF_THING = "part_of_thing"  # a piece of a thing of a sheet, shipped alone
# the roles of a picture of one cell that keeps its cell out of the sheet's things
PEOPLE = frozenset({"PLAYER", "NPC", "ENEMY", "BOSS", "ANIMAL", "PORTRAIT"})
MIN_CELL = 8
UNUSED = frozenset({"UNUSED", "MISSING"})
# a hue's name, by the hue it is below (sheet_parts.LOOKS_COLOURS)
COLOURS = (
    (15, "red"), (40, "orange"), (65, "yellow"), (170, "green"), (250, "blue"), (345, "purple"),
    (360, "red"),
)  # fmt: skip


def _grid(facets: dict[str, Any]) -> tuple[int, int, int, int, int, int] | None:
    grid = facets.get("grid") or {}
    cell = grid.get("cell") or []
    if len(cell) != 2 or int(cell[0]) < MIN_CELL or int(cell[1]) < MIN_CELL:
        return None
    margin = grid.get("margin") or [0, 0]
    sep = grid.get("separation") or [0, 0]
    return (int(cell[0]), int(cell[1]), int(margin[0]), int(margin[1]), int(sep[0]), int(sep[1]))


def _cells_of_tags(tags: list[str]) -> set[tuple[int, int]]:
    """The cells a crop of the sheet takes (``cells:<col>:<row>:<count>``): its stages along a
    row or a column, so both are kept out."""
    out: set[tuple[int, int]] = set()
    for tag in tags:
        parts = str(tag).split(":")
        if len(parts) == 4 and parts[0] == "cells" and all(p.isdigit() for p in parts[1:]):
            c, r, n = int(parts[1]), int(parts[2]), int(parts[3])
            for i in range(n):
                out.add((c + i, r))
                out.add((c, r + i))
    return out


def name_of(picture: np.ndarray) -> str:
    """``<colour>_<shape>`` of a thing: the colour most of it is (``grey`` for little colour,
    ``brown`` for a dark red or orange, ``white``, ``black``) and its shape (``tall``, ``wide``,
    ``small`` when it paints little, else ``round``)."""
    mask = picture[..., 3] >= PAINTED_ALPHA
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return "thing"
    h = int(ys.max()) - int(ys.min()) + 1
    w = int(xs.max()) - int(xs.min()) + 1
    cover = float(mask.mean())
    shape = (
        "small"
        if cover < SOLID_COVER
        else "tall"
        if h >= 1.4 * w
        else "wide"
        if w >= 1.4 * h
        else "round"
    )
    rgb = picture[..., :3][mask].astype(np.float32) / 255.0
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    d = mx - mn
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0)
    # the outline of pixel art (its darkest pixels, often a dark purple or brown) is no colour
    # of the thing
    body = mx >= max(OUTLINE_VALUE, float(np.percentile(mx, 25)))
    if not body.any():
        return f"black_{shape}"
    coloured = body & (sat >= 0.25)
    if int(coloured.sum()) < 0.3 * int(body.sum()):
        light = float(np.median(mx[body]))
        return f"{'white' if light >= 0.85 else 'grey'}_{shape}"
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    safe = np.maximum(d, 1e-6)
    hue = (
        np.where(
            mx == r, (g - b) / safe % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)
        )
        * 60.0
    ) % 360.0
    counts: dict[str, int] = {}
    for value in hue[coloured]:
        colour = next(name for top, name in COLOURS if value < top)
        counts[colour] = counts.get(colour, 0) + 1
    colour = max(sorted(counts), key=lambda k: counts[k])
    if colour in ("red", "orange") and float(np.median(mx[coloured])) < 0.6:
        colour = "brown"
    return f"{colour}_{shape}"


def is_thing(cell: np.ndarray) -> bool:
    """True for a cell that holds a thing standing on see-through pixels (the module's rules)."""
    mask = cell[..., 3] >= PAINTED_ALPHA
    cover = float(mask.mean())
    if not MIN_COVER <= cover <= MAX_COVER:
        return False
    edges = (mask[0, :].mean(), mask[-1, :].mean(), mask[:, 0].mean(), mask[:, -1].mean())
    return sum(1 for e in edges if float(e) > EDGE_SHARE) <= 1


def _foot(cell: np.ndarray) -> tuple[list[int], dict[str, Any]]:
    """The footprint ([x, y, w, h] in the cell) and the collision of a thing: the lowest quarter
    of what it paints, half as wide; nothing to bump into for a small thing."""
    mask = cell[..., 3] >= PAINTED_ALPHA
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    w, h = x1 - x0, y1 - y0
    fw, fh = max(2, w // 2), max(2, h // 4)
    fx, fy = x0 + (w - fw) // 2, y1 - fh
    foot = [fx, fy, fw, fh]
    if float(mask.mean()) < SOLID_COVER:
        return foot, {"profile": "NONE"}
    polygon = [[fx, fy], [fx + fw, fy], [fx + fw, fy + fh], [fx, fy + fh]]
    return foot, {"profile": "CUSTOM", "polygon": polygon}


def _load(file: Path) -> np.ndarray | None:
    try:
        with Image.open(file) as im:
            return np.asarray(im.convert("RGBA"))
    except (OSError, ValueError):
        return None


def _digest(picture: np.ndarray) -> str:
    return hashlib.sha1(np.ascontiguousarray(picture).tobytes()).hexdigest()


def _continues(edge: np.ndarray, other: np.ndarray) -> bool:
    """True when the art of a cell carries on into the next across their border: of the pixels
    the two borders both paint, a quarter at least are of much the same colour and no outline
    (two things in cells side by side meet with their outlines; a trunk under a crown goes on
    in its brown)."""
    both = (edge[:, 3] >= PAINTED_ALPHA) & (other[:, 3] >= PAINTED_ALPHA)
    if int(both.sum()) < JOIN_PIXELS or float(both.mean()) < JOIN_SHARE / 2:
        return False
    a = edge[both, :3].astype(np.int16)
    b = other[both, :3].astype(np.int16)
    same = np.abs(a - b).max(axis=1) <= JOIN_COLOUR
    bright = (a.max(axis=1) >= OUTLINE_VALUE * 255) & (b.max(axis=1) >= OUTLINE_VALUE * 255)
    return int((same & bright).sum()) >= max(JOIN_PIXELS, int(JOIN_MATCH * int(both.sum())))


def _glyph_rows(cells: dict[tuple[int, int], np.ndarray]) -> list[tuple[int, int]]:
    """The cells of rows of glyphs (T17.33: *Pixel Platformer*'s digits 0 to 9, twice, and its
    signs, which were placed from the dock as decorations): ``GLYPH_RUN`` cells or more one after
    the other in reading order (a run goes on from the end of a row to the start of the next),
    each painting little (``GLYPH_COVER``), all of them in at most ``GLYPH_COLOURS`` colours.
    A font, not things."""
    if not cells:
        return []
    last_col = max(c for c, _r in cells)
    out: list[tuple[int, int]] = []
    run: list[tuple[int, int]] = []
    palette: frozenset[tuple[int, int, int]] = frozenset()
    for key in [*sorted(cells, key=lambda k: (k[1], k[0])), (-99, -99)]:
        colours = _palette(cells[key]) if key in cells else None
        if run and colours is not None:
            c0, r0 = run[-1]
            follows = key == (c0 + 1, r0) or (c0 == last_col and key == (0, r0 + 1))
            if follows and len(palette | colours) <= GLYPH_COLOURS:
                run.append(key)
                palette = palette | colours
                continue
        if len(run) >= GLYPH_RUN:
            out.extend(run)
        run = [key] if colours is not None else []
        palette = colours or frozenset()
    return out


def _palette(cell: np.ndarray) -> frozenset[tuple[int, int, int]] | None:
    """The colours of a cell that paints little in few colours (a glyph), else None."""
    mask = cell[..., 3] >= PAINTED_ALPHA
    if float(mask.mean()) > GLYPH_COVER:
        return None
    colours = {tuple(int(v) for v in px) for px in cell[..., :3][mask]}
    if len(colours) > GLYPH_COLOURS:
        return None
    return frozenset(colours)  # type: ignore[arg-type]


def _groups(cells: dict[tuple[int, int], np.ndarray]) -> list[list[tuple[int, int]]]:
    """The painted cells joined where their art carries on into the next (``_continues``: the
    line of space between them aside), as lists of cells; groups larger than ``MAX_GROUP`` cells
    each way are left out (the walls of a barn)."""
    parent = {k: k for k in cells}

    def find(k: tuple[int, int]) -> tuple[int, int]:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for (c, r), cell in cells.items():
        right, below = (c + 1, r), (c, r + 1)
        if right in cells and _continues(cell[:, -1], cells[right][:, 0]):
            parent[find((c, r))] = find(right)
        if below in cells and _continues(cell[-1, :], cells[below][0, :]):
            parent[find((c, r))] = find(below)
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for k in sorted(cells, key=lambda k: (k[1], k[0])):
        groups.setdefault(find(k), []).append(k)
    out = []
    for members in groups.values():
        cs = [c for c, _r in members]
        rs = [r for _c, r in members]
        if max(cs) - min(cs) + 1 <= MAX_GROUP and max(rs) - min(rs) + 1 <= MAX_GROUP:
            out.append(members)
    return out


def _stitched(
    members: list[tuple[int, int]], cells: dict[tuple[int, int], np.ndarray], cw: int, ch: int
) -> tuple[np.ndarray, int, int]:
    """The picture of a group of cells side by side without the space between them, and its
    top-left cell."""
    c0, r0 = min(c for c, _r in members), min(r for _c, r in members)
    w = (max(c for c, _r in members) - c0 + 1) * cw
    h = (max(r for _c, r in members) - r0 + 1) * ch
    out = np.zeros((h, w, 4), np.uint8)
    for c, r in members:
        out[(r - r0) * ch : (r - r0 + 1) * ch, (c - c0) * cw : (c - c0 + 1) * cw] = cells[(c, r)]
    return out, c0, r0


def _taken(catalog: Any, sheet: Any, facets: dict[str, Any]) -> set[tuple[int, int]]:
    """The cells of ``sheet`` that a terrain, a tile of its own or a crop cut from it takes."""
    from rpggen.core import catalog as catalog_mod

    taken: set[tuple[int, int]] = set()
    for key in facets.get("tile_overrides") or {}:
        col, _sep, row = str(key).partition(",")
        if col.isdigit() and row.isdigit():
            taken.add((int(col), int(row)))
    for other in catalog.assets:
        tags = catalog_mod.effective(other).get("tags") or []
        if other.id.startswith(sheet.id + "#") or f"duplicate_of:{sheet.id}" in tags:
            taken |= _cells_of_tags(tags)
    return taken


def _used_singles(
    catalog: Any, sheet: Any, root: str, local: Path, size: tuple[int, int]
) -> tuple[dict[str, Any], list[list[int]]]:
    """The pack's pictures of one cell that are used on their own, by their digest, and the
    regions of the parts cut from ``sheet`` and of its objects."""
    from rpggen.core import catalog as catalog_mod

    regions: list[list[int]] = [list(o.region) for o in catalog.objects if o.sheet == sheet.id]
    singles: dict[str, Any] = {}
    for other in catalog.assets:
        if other.pack_id != sheet.pack_id or other.status in UNUSED or other is sheet:
            continue
        own = catalog_mod.effective(other)
        if other.id.startswith(sheet.id + "#"):
            region = own.get("region")
            if isinstance(region, list) and len(region) == 4:
                regions.append([int(v) for v in region])
            continue
        if own.get("role") == "NONE":
            continue  # set aside (the statuses are worked out after this runs)
        if list(own.get("size") or []) == list(size) and other.path.startswith(root + "/"):
            single = _load(local / other.path[len(root) + 1 :])
            if single is not None and single.shape[:2] == (size[1], size[0]):
                singles[_digest(single)] = other
    return singles, regions


def _person(asset: Any) -> bool:
    from rpggen.core import catalog as catalog_mod

    return catalog_mod.effective(asset).get("role") in PEOPLE


def _render(whole: np.ndarray, work: Path) -> tuple[str, Path, str]:
    digest = hashlib.sha256(whole.tobytes() + repr(whole.shape).encode()).hexdigest()
    file = work / f"{digest[:24]}.png"
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.is_file():
        Image.fromarray(whole, "RGBA").save(file, format="PNG", optimize=False)
    return f"{RENDER_DIR}/{file.name}", file, digest


def _sheet_of(catalog: Any, sheet: Any) -> bool:
    """True for a used, square sheet of tiles."""
    from rpggen.core import catalog as catalog_mod

    facets = catalog_mod.effective(sheet)
    return not (
        sheet.kind != "image"
        or "#" in sheet.id
        or sheet.status in UNUSED
        or facets.get("usage") != "tiles"
        or facets.get("role") == "NONE"
        or catalog_mod.is_iso_tile(sheet)
        or "isometric" in (facets.get("tags") or [])
    )


def drop_misread(catalog: Any) -> int:
    """Takes out the objects a sheet should not have given (T17.33): the shapes the grid reader
    found in a background (the hills of a far backdrop were placed from the dock as dark
    blocks), and those lying on cells of a tile sheet that are read as tiles of a kind (a ladder,
    a plank, spikes): they are painted, not placed. A user's object or a confirmed one stays.
    Returns how many."""
    from rpggen.core import catalog as catalog_mod

    by_id = {a.id: a for a in catalog.assets}
    keep = []
    for obj in catalog.objects:
        sheet = by_id.get(obj.sheet)
        if sheet is None or obj.source != "auto" or obj.status == "CONFIRMED":
            keep.append(obj)
            continue
        facets = catalog_mod.effective(sheet)
        if facets.get("usage") == "background" or facets.get("role") == "BACKGROUND":
            continue
        grid = _grid(facets) if facets.get("usage") == "tiles" else None
        if grid is not None and _on_special_cells(obj.region, facets, grid):
            continue
        keep.append(obj)
    dropped = len(catalog.objects) - len(keep)
    catalog.objects[:] = keep
    return dropped


def _on_special_cells(region: list[int], facets: dict[str, Any], grid: tuple[int, ...]) -> bool:
    """True when ``region`` of a tile sheet lies on a cell whose tile is of a kind of its own
    (``tile_overrides`` with ``custom``: a ladder, a plank, spikes, water)."""
    cw, ch, mx, my, sx, sy = grid
    x, y, w, h = (int(v) for v in region)
    for key, override in (facets.get("tile_overrides") or {}).items():
        if not isinstance(override, dict) or not override.get("custom") or override.get("terrain"):
            continue
        col, _sep, row = str(key).partition(",")
        if not (col.isdigit() and row.isdigit()):
            continue
        cx, cy = mx + int(col) * (cw + sx), my + int(row) * (ch + sy)
        if x < cx + cw and cx < x + w and y < cy + ch and cy < y + h:
            return True
    return False


def add(catalog: Any, roots: dict[str, Path], work_dir: Path | None = None) -> dict[str, str]:
    """Adds the things of every used, square sheet of tiles of ``catalog`` (the module's rules):
    an object of the sheet each, or, for a thing over several cells of a sheet whose cells lie
    apart, a picture of its own drawn into ``work_dir`` (its cells without the space between
    them: a ``DECORATION`` asset of the generated pack). ``roots``: the folder of each pack.
    Returns the generated files (project path -> file)."""
    from rpggen import paths
    from rpggen.core import catalog as catalog_mod
    from rpggen.core import pack_forms
    from rpggen.core.catalog import Asset, CatalogPack, SheetObject
    from rpggen.core.terrain import GENERATED_PACK, rpgmaker_a2

    pack_roots = {p.pack_id: p.root for p in catalog.packs}
    have = {o.id for o in catalog.objects} | {a.id for a in catalog.assets}
    generated: dict[str, str] = {}
    work = (work_dir or paths.cache_dir()) / WORK_FOLDER
    for sheet in sorted(catalog.assets, key=lambda a: a.id):
        if not _sheet_of(catalog, sheet):
            continue
        facets = catalog_mod.effective(sheet)
        grid = _grid(facets)
        root = pack_roots.get(sheet.pack_id, "")
        local = roots.get(sheet.pack_id)
        if grid is None or local is None or not sheet.path.startswith(root + "/"):
            continue
        picture = _load(local / sheet.path[len(root) + 1 :])
        if picture is None:
            continue
        cw, ch, mx, my, sx, sy = grid
        cols = (picture.shape[1] - mx + sx) // (cw + sx)
        rows = (picture.shape[0] - my + sy) // (ch + sy)
        if cols * rows < 2:
            continue
        taken = _taken(catalog, sheet, facets)
        singles, regions = _used_singles(catalog, sheet, root, local, (cw, ch))
        painted: dict[tuple[int, int], np.ndarray] = {}
        for r in range(rows):
            for c in range(cols):
                x, y = mx + c * (cw + sx), my + r * (ch + sy)
                if (c, r) in taken or any(
                    x < rx + rw and rx < x + cw and y < ry + rh and ry < y + ch
                    for rx, ry, rw, rh in regions
                ):
                    continue
                cell = picture[y : y + ch, x : x + cw]
                if float((cell[..., 3] >= PAINTED_ALPHA).mean()) < MIN_COVER:
                    continue
                single = singles.get(_digest(cell))
                if single is not None and _person(single):
                    continue  # a character or an animal the pack has on its own, used as it is
                painted[(c, r)] = cell
        for cell_key in _glyph_rows(painted):
            painted.pop(cell_key, None)
        found: list[tuple[list[tuple[int, int]], np.ndarray, int, int]] = []
        for members in _groups(painted):
            whole, c0, r0 = _stitched(members, painted, cw, ch)
            if not is_thing(whole):
                continue
            found.append((members, whole, c0, r0))
            if len(members) > 1:
                # a piece of the thing that the pack also has alone (half a tree) is set aside
                # for the whole of it
                for member in members:
                    piece = singles.get(_digest(painted[member]))
                    if piece is not None:
                        pack_forms.aside(piece, PART_OF_THING, sheet.path.split("/", 3)[-1])
        if not found or len(found) > MAX_THINGS:
            continue
        used_names: dict[str, int] = {}
        for members, whole, c0, r0 in found:
            name = name_of(whole)
            used_names[name] = used_names.get(name, 0) + 1
            if used_names[name] > 1:
                name = f"{name}_{used_names[name]}"
            object_id = f"{sheet.id}#{name}"
            asset_id = f"{GENERATED_PACK}.{sheet.id.replace('.', '_')}__{name}"
            if object_id in have or asset_id in have:
                continue
            have.add(object_id)
            foot, collision = _foot(whole)
            h, w = whole.shape[:2]
            tags = [TAG, f"cell:{c0}:{r0}"]
            x, y = mx + c0 * (cw + sx), my + r0 * (ch + sy)
            if len(members) == 1 or (sx == 0 and sy == 0):
                catalog.objects.append(
                    SheetObject(
                        object_id,
                        sheet.id,
                        name,
                        "DECORATION",
                        [x, y, w, h],
                        [w // 2, h - 1],
                        foot,
                        collision,
                        tags,
                    )  # fmt: skip
                )
                continue
            # cells that lie apart: a picture of its own, without the lines between them
            rel, file, digest = _render(whole, work)
            generated[rel] = str(file)
            have.add(asset_id)
            catalog.assets.append(
                Asset(
                    asset_id,
                    GENERATED_PACK,
                    rel,
                    digest,
                    "image",
                    "AUTO_DETECTED",
                    {
                        "usage": "sprite",
                        "role": "DECORATION",
                        "size": [w, h],
                        "frame": [w, h],
                        "origin": [w // 2, h - 1],
                        "collision": collision,
                        "tags": [*tags, f"cut_from:{sheet.id}"],
                    },
                    {},
                    "sheet_things",
                    CONFIDENCE,
                )  # fmt: skip
            )
    if generated and not any(p.pack_id == GENERATED_PACK for p in catalog.packs):
        catalog.packs.append(
            CatalogPack(GENERATED_PACK, "0" * 64, rpgmaker_a2.TERRAIN_DIR, [], [], None, [])
        )
    return generated

"""Terrain assignments for the catalog (T8.06).

The Python side only produces data; the Godot builder applies it to the TileSet:

* ``tiled_wang``: Tiled wangids -> peering bits in ``tile_overrides``.
* ``rpgmaker_a2``: RPG Maker A2 blocks -> generated 47-tile atlases with peering.
* ``blob``: generic 47-tile blob / 16-tile corner sheets -> ``terrain_proposal`` facets.

``rpggen.core.catalog.assemble`` calls the functions of this module; they only read the pack
files and the detected facets, so the result is deterministic.
"""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import os
import posixpath
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import ids, paths
from rpggen.core import catalog as catalog_mod
from rpggen.core.archive import Cancelled
from rpggen.core.terrain import blob, blocks, iso, rpgmaker_a2, tiled_wang
from rpggen.errors import IssueList

GENERATED_PACK = "generated"
GENERATED_TAG = "generated_terrain"
DEFERRED_A_SHEETS = ("A1", "A3", "A4")
TERRAIN_HINTS = ("blob", "wang", "autotile", "terrain", "corner")

__all__ = [
    "GENERATED_PACK",
    "GENERATED_TAG",
    "TerrainResult",
    "apply_tiled_wang",
    "attach_terrain_sets",
    "blob",
    "blocks",
    "iso",
    "generate",
    "rpgmaker_a2",
    "tiled_wang",
]


@dataclass
class TerrainResult:
    # project-relative path -> absolute file to install (generated atlases)
    generated: dict[str, str] = field(default_factory=dict)
    # asset id -> TileSetDef terrain sets that must join the asset's tile set
    terrain_sets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def apply_tiled_wang(catalog: catalog_mod.Catalog, adapter_tilesets: list[dict[str, Any]]) -> None:
    """Turn the recorded wangids of every asset into terrain/peering (in ``detected``)."""
    sets = [t for entry in adapter_tilesets for t in entry.get("terrain_sets", [])]
    if not sets:
        return
    for asset in catalog.assets:
        overrides = asset.detected.get("tile_overrides")
        if overrides:
            asset.detected["tile_overrides"] = tiled_wang.apply_to_tile_overrides(overrides, sets)


def _tags(facets: dict[str, Any]) -> set[str]:
    return {str(t) for t in facets.get("tags", [])}


def _cell(facets: dict[str, Any]) -> tuple[int, int] | None:
    grid = facets.get("grid") or {}
    cell = grid.get("cell")
    if not cell or list(grid.get("margin", [0, 0])) != [0, 0]:
        return None
    if list(grid.get("separation", [0, 0])) != [0, 0]:
        return None
    return int(cell[0]), int(cell[1])


def _pixel_sha(img: Image.Image) -> str:
    """Hash of the pixels, not of the PNG bytes: the encoder (zlib) may differ between machines."""
    return hashlib.sha256(f"{img.mode}{img.size}".encode() + img.tobytes()).hexdigest()


def generate(
    catalog: catalog_mod.Catalog,
    roots: dict[str, Path],
    work_dir: Path | None,
    issues: IssueList,
    is_cancelled: Callable[[], bool] | None = None,
    pictures: dict[str, str] | None = None,
) -> TerrainResult:
    """A2 composites, blob proposals, terrain blocks inside sheets (T17.31) and TILE-006
    reports for the tile sheets of ``catalog``.

    ``roots`` maps pack ids to the folder holding the pack files. New assets are appended to
    ``catalog.assets`` (pack ``generated``); the atlases are written below ``work_dir``. The
    sheets are searched for blocks in a pool of threads, ``is_cancelled`` polled between them.
    """
    result = TerrainResult()
    work = (work_dir or paths.cache_dir()) / "terrain_atlases"
    used_sets: set[str] = set()
    added: list[catalog_mod.Asset] = []
    searched: list[tuple[catalog_mod.Asset, Path, dict[str, Any], str]] = []
    failed: list[tuple[catalog_mod.Asset, Path, str]] = []  # layouts not recognised
    for asset in sorted(catalog.assets, key=lambda a: catalog_mod._sort_key(a.id)):
        facets = asset.detected
        if (
            asset.kind == "image"
            and facets.get("usage") != "tiles"
            and asset.pack_id in roots
            and facets.get("role") not in NO_LAYOUT_ROLES
            and GENERATED_TAG not in _tags(facets)
        ):
            rel = asset.path.split("/", 3)[-1]
            _animated_layout(asset, roots[asset.pack_id] / rel, work, used_sets, result, added)
            continue
        if (
            asset.kind != "image"
            or facets.get("usage") != "tiles"
            or asset.pack_id not in roots
            or GENERATED_TAG in _tags(facets)
        ):
            continue
        root = roots[asset.pack_id]
        rel = asset.path.split("/", 3)[-1]
        file = root / rel
        if pictures and asset.path in pictures:  # a picture rpggen cut (a part of a sheet)
            file = Path(pictures[asset.path])
        tags = _tags(facets)
        cell = _cell(facets)
        stem = ids.slug(posixpath.splitext(posixpath.basename(rel))[0])
        if pictures and asset.path in pictures:  # named after the asset, not its file's hash
            stem = ids.slug(asset.id.rsplit(".", 1)[-1])
        if "rpgmaker_autotile" in tags:
            sheet_kind = next((t for t in tags if t in ("A1", "A2", "A3", "A4")), "")
            if sheet_kind in DEFERRED_A_SHEETS:
                issues.add("TILE-006", asset=asset.id, file=asset.path)
            elif sheet_kind == "A2" and cell and file.is_file():
                _a2_blocks(asset, file, cell, stem, work, used_sets, result, added, issues)
            continue
        if any("terrain" in v for v in (facets.get("tile_overrides") or {}).values()):
            continue  # terrain already known (Tiled wang sets)
        if _animated_layout(asset, file, work, used_sets, result, added):
            continue
        if _blob_proposal(asset, file, cell, stem):
            failed.append((asset, file, stem))
        grid = facets.get("grid") or {}
        if (
            grid.get("cell")
            and "terrain_proposal" not in asset.detected
            and file.is_file()
            and _holds_terrains(facets)
        ):
            searched.append((asset, file, grid, stem))
    for asset, file, stem in failed:
        set_aside = asset.detected.get("role") == "NONE"  # another engine's copy: no warning
        if not _family_layout(asset, file, stem, catalog.assets) and not set_aside:
            issues.add("TILE-006", asset=asset.id, file=asset.path)
    for (asset, _path, _size, stem), found in zip(
        searched, _in_parallel(_read_blocks, searched, is_cancelled), strict=True
    ):
        _apply_blocks(asset, [b for b in found if b.a2 is None], stem, used_sets, result)
        for b in found:
            if b.a2 is not None and b.picture is not None:
                _compose_2x3(asset, b, stem, work, used_sets, result, added)
    for asset in added:
        if ANIMATED_TAG not in _tags(asset.detected):  # an animated layout says its own
            _describe_a2(asset, work, result)
    if added:
        catalog.assets.extend(added)
        if not any(p.pack_id == GENERATED_PACK for p in catalog.packs):
            catalog.packs.append(
                catalog_mod.CatalogPack(
                    GENERATED_PACK, "0" * 64, rpgmaker_a2.TERRAIN_DIR, [], [], None, []
                )
            )
    return result


def _a2_blocks(
    asset: catalog_mod.Asset,
    file: Path,
    cell: tuple[int, int],
    stem: str,
    work: Path,
    used_sets: set[str],
    result: TerrainResult,
    added: list[catalog_mod.Asset],
    issues: IssueList,
) -> None:
    tile = cell[0]
    if tile != cell[1] or tile % 2:
        issues.add("TILE-006", asset=asset.id, file=asset.path)
        return
    with Image.open(file) as opened:
        sheet = opened.convert("RGBA")
    bw, bh = rpgmaker_a2.block_size(tile)
    cols, rows = sheet.width // bw, sheet.height // bh
    asset_slug = asset.id.replace(".", "_").replace("#", "_")
    for by in range(rows):
        for bx in range(cols):
            if rpgmaker_a2.block_is_empty(sheet, bx, by, tile):
                continue
            index = by * cols + bx
            set_name = f"{stem}_b{index}"
            if set_name in used_sets:
                set_name = f"{asset_slug}_b{index}"
            used_sets.add(set_name)
            name = f"{asset_slug}_b{index}.png"
            out = work / name
            tiles = rpgmaker_a2.compose_atlas(sheet, bx, by, tile, out)
            rel = f"{rpgmaker_a2.TERRAIN_DIR}/{name}"
            atlas_rows = (47 + rpgmaker_a2.ATLAS_COLUMNS - 1) // rpgmaker_a2.ATLAS_COLUMNS
            facets: dict[str, Any] = {
                "usage": "tiles",
                "role": asset.detected.get("role", "AUTOTILE"),
                "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
                "collision": {"profile": "NONE"},
                "tags": [GENERATED_TAG],
                "tile_overrides": rpgmaker_a2.atlas_tile_overrides(set_name),
                "size": [rpgmaker_a2.ATLAS_COLUMNS * tile, atlas_rows * tile],
            }
            if asset.detected.get("tileset"):
                facets["tileset"] = asset.detected["tileset"]
            new_id = f"{GENERATED_PACK}.{asset_slug}_b{index}"
            added.append(
                catalog_mod.Asset(
                    id=new_id,
                    pack_id=GENERATED_PACK,
                    path=rel,
                    sha256=_pixel_sha(rpgmaker_a2.atlas_from_tiles(tiles, tile)),
                    kind="image",
                    status="AUTO_DETECTED",
                    detected=facets,
                    detected_by="terrain_a2",
                    confidence=1.0,
                )
            )
            result.generated[rel] = str(out)
            result.terrain_sets[new_id] = [rpgmaker_a2.terrain_set_def(set_name, index)]


# A sheet this small is an icon, not a terrain layout: a coincidental border match is not reported.
TINY_SHEET = 32


def _blob_proposal(
    asset: catalog_mod.Asset,
    file: Path,
    cell: tuple[int, int] | None,
    stem: str,
) -> bool:
    """A blob proposal for a sheet in a 47-tile or corner layout. True when a layout was likely
    but none was recognised (TILE-006, unless its family says it: ``_family_layout``)."""
    if not file.is_file():
        return False
    size = asset.detected.get("size")
    if not size:
        return False
    cells = [cell] if cell else []
    if size[0] % 12 == 0 and size[1] % 4 == 0 and size[0] // 12 == size[1] // 4:
        derived = (size[0] // 12, size[1] // 4)
        if derived not in cells:
            cells.append(derived)
    cells = [
        c
        for c in cells
        if c[0] > 0
        and c[1] > 0
        and (size[0] // c[0], size[1] // c[1]) in blob.LAYOUT_SHAPES.values()
    ]
    if not cells:
        return False
    with Image.open(file) as opened:
        sheet = opened.convert("RGBA")
    hinted = any(h in asset.path.casefold() for h in TERRAIN_HINTS)
    for c in cells:
        proposal, recognition = blob.propose(sheet, c[0], c[1], f"{stem}_terrain")
        if proposal is not None:
            asset.detected["terrain_proposal"] = proposal
            return False
        if recognition is not None and recognition.flat:
            return False  # a plain ground in the shape of an autotile sheet: nothing was skipped
        if recognition is not None and max(size) > TINY_SHEET:
            hinted = hinted or recognition.confidence >= 0.5
    return hinted


# a layout taken from the family of a sheet needs this many sheets of the family recognised alike
FAMILY_SHEETS = 3


def _family_layout(
    asset: catalog_mod.Asset, file: Path, stem: str, assets: list[catalog_mod.Asset]
) -> bool:
    """A sheet no layout was recognised in whose family says its layout (Super Retro Ranch's
    fences in engines/Godot/autotiles/3x3: drawn over nothing, their seams alike in any order):
    the sheets of its size below the same folder (its folder's parent) recognised in one 47-tile
    layout, FAMILY_SHEETS of them at least. True when it was given that layout's proposal."""
    size = asset.detected.get("size") or [0, 0]
    family = posixpath.dirname(posixpath.dirname(asset.path)) + "/"
    layouts = [
        str(a.detected["terrain_proposal"]["layout"])
        for a in assets
        if a is not asset
        and a.pack_id == asset.pack_id
        and a.path.startswith(family)
        and a.detected.get("size") == size
        and a.detected.get("terrain_proposal")
    ]
    if (
        len(layouts) < FAMILY_SHEETS
        or len(set(layouts)) != 1
        or layouts[0] not in blob.BLOB_LAYOUTS
    ):
        return False
    tile = int(size[0]) // 12
    if tile < 1 or (int(size[0]), int(size[1])) != (12 * tile, 4 * tile) or not file.is_file():
        return False
    with Image.open(file) as opened:
        sheet = opened.convert("RGBA")
    proposal = blob.propose_layout(sheet, tile, layouts[0], f"{stem}_terrain")
    if proposal is None:
        return False
    asset.detected["terrain_proposal"] = proposal
    return True


# A picture of an animated 47-tile layout (Super Retro Ranch's water, engines/Godot/autotiles/3x3):
# this many copies of the layout side by side at most, each one frame, laid this long
MAX_LAYOUT_FRAMES = 8
LAYOUT_FRAME_MS = 250
ANIMATED_TAG = "animated_terrain"
ANIMATED_ASIDE = "animated_layout"  # the picture whose frames a generated atlas lays side by side


# a picture of these is no layout of tiles (a strip of a character's frames is cut alike too)
NO_LAYOUT_ROLES = frozenset({"NONE", "PLAYER", "NPC", "ENEMY", "BOSS", "ANIMAL", "PORTRAIT"})
LAYOUT_SHAPE_AGREEMENT = 0.95  # of the pixels that are drawn (or not) alike in every frame


def _same_shapes(frames: list[Image.Image]) -> bool:
    """Frames of one layout cut alike: each draws (nearly) the pixels the first draws, which
    is cheap to see before any frame is recognised."""
    first = np.asarray(frames[0].getchannel("A")) > 0
    if not first.any():
        return False
    return all(
        float(((np.asarray(f.getchannel("A")) > 0) == first).mean()) >= LAYOUT_SHAPE_AGREEMENT
        for f in frames[1:]
    )


def _animated_layout(
    asset: catalog_mod.Asset,
    file: Path,
    work: Path,
    used_sets: set[str],
    result: TerrainResult,
    added: list[catalog_mod.Asset],
) -> bool:
    """A picture of several frames of one 47-tile layout side by side (each a whole 12 x 4
    sheet, recognised alike): an atlas whose tiles have their frames in the cells to their
    right, as Godot animates a tile, each the layout's terrain; the picture is set aside. True
    when it was such a picture."""
    from rpggen.core import pack_forms

    size = asset.detected.get("size") or [0, 0]
    w, h = int(size[0]), int(size[1])
    tile = h // 4
    if tile < 8 or h % 4 or w % (12 * tile) or not 2 <= w // (12 * tile) <= MAX_LAYOUT_FRAMES:
        return False
    if not file.is_file():
        return False
    count = w // (12 * tile)
    with Image.open(file) as opened:
        sheet = opened.convert("RGBA")
    frames = [sheet.crop((i * 12 * tile, 0, (i + 1) * 12 * tile, h)) for i in range(count)]
    if not _same_shapes(frames):
        return False
    found: list[blob.Recognition] = []
    for frame in frames:  # the first frame that is no such layout ends the reading
        r = blob.recognize(frame, tile)
        if r is None or not r.accepted or r.flat or r.layout not in blob.BLOB_LAYOUTS:
            return False
        if found and r.layout != found[0].layout:
            return False
        found.append(r)
    layout = found[0].layout
    stem = ids.slug(posixpath.splitext(posixpath.basename(asset.path))[0])
    set_name = f"{stem}_terrain"
    if set_name in used_sets:
        set_name = f"{asset.id.replace('.', '_').replace('#', '_')}_terrain"
    used_sets.add(set_name)
    proposal, _r = blob.propose(frames[0], tile, tile, set_name)
    if proposal is None:
        return False
    # each tile's frames side by side: the tile of column c is at column c * count
    atlas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for f, frame in enumerate(frames):
        for cx in range(12):
            for cy in range(4):
                cell = frame.crop((cx * tile, cy * tile, (cx + 1) * tile, (cy + 1) * tile))
                atlas.paste(cell, ((cx * count + f) * tile, cy * tile))
    overrides: dict[str, Any] = {}
    for key, entry in proposal["tile_overrides"].items():
        cx, cy = (int(v) for v in key.split(","))
        first = cx * count
        overrides[f"{first},{cy}"] = {
            **entry,
            "anim": {
                "frames": [[first + f, cy] for f in range(count)],
                "durations_ms": [LAYOUT_FRAME_MS] * count,
            },
        }
    digest = _pixel_sha(atlas)
    name = f"{digest[:24]}.png"
    out = work / name
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        atlas.save(out, format="PNG", optimize=False)
    rel = f"{rpgmaker_a2.TERRAIN_DIR}/{name}"
    role = str(asset.detected.get("role") or "")
    facets: dict[str, Any] = {
        "usage": "tiles",
        "role": role if role in TERRAIN_ROLES else "GROUND",
        "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
        "collision": {"profile": "NONE"},
        "tags": [GENERATED_TAG, ANIMATED_TAG],
        "tile_overrides": {k: overrides[k] for k in sorted(overrides, key=_xy)},
        "size": [w, h],
    }
    new_id = f"{GENERATED_PACK}.{asset.id.replace('.', '_').replace('#', '_')}_animated"
    added.append(
        catalog_mod.Asset(
            id=new_id, pack_id=GENERATED_PACK, path=rel, sha256=digest, kind="image",
            status="AUTO_DETECTED", detected=facets, detected_by="terrain_animated",
            confidence=min(r.confidence for r in found),
        )
    )  # fmt: skip
    result.generated[rel] = str(out)
    pixels = np.asarray(frames[0])
    middle = next((key for key, mask in _layout_masks(layout) if mask == 255), None)
    colour = np.zeros(3)
    if middle is not None:
        mx, my = middle
        inner = pixels[my * tile : (my + 1) * tile, mx * tile : (mx + 1) * tile]
        painted = inner[..., 3] > 0
        if painted.any():
            colour = inner[..., :3][painted].mean(axis=0) / 255.0
    terrain_set = dict(proposal["terrain_set"])
    terrain_set.update({
        "sheet": new_id, "surface": blocks.surface_of(colour, _words(asset.path)),
        "over": "ground", "shape": "any", "layout": layout,
    })  # fmt: skip
    result.terrain_sets[new_id] = [terrain_set]
    pack_forms.aside(asset, ANIMATED_ASIDE, rel)
    return True


def _layout_masks(layout: str) -> list[tuple[tuple[int, int], int]]:
    return blob._blob_cells(layout)


MAX_WORKERS = 8
# The sheets whose blocks are read (T17.31): the grounds, waters, roads, walls and cliffs, and a
# sheet of soil (a farm's, whatever its role); a sheet of objects or one set aside is not.
TERRAIN_ROLES = frozenset({"GROUND", "WATER", "ROAD", "WALL", "CLIFF", "AUTOTILE", "INTERIOR"})
TERRAIN_TAGS = frozenset({"soil", "watered"})


def _holds_terrains(facets: dict[str, Any]) -> bool:
    return facets.get("role") in TERRAIN_ROLES or bool(_tags(facets) & TERRAIN_TAGS)


def _in_parallel(
    job: Callable[[Any], Any], items: list[Any], is_cancelled: Callable[[], bool] | None
) -> list[Any]:
    """``job`` of every item in a pool of threads, the results in the order of ``items``;
    ``is_cancelled`` is polled before the first and after every result (``archive.Cancelled``)."""
    if not items:
        return []

    def check() -> None:
        if is_cancelled is not None and is_cancelled():
            raise Cancelled

    check()
    workers = max(1, min(len(items), os.cpu_count() or 1, MAX_WORKERS))
    if workers == 1:
        out = []
        for item in items:
            out.append(job(item))
            check()
        return out
    pool = concurrent.futures.ThreadPoolExecutor(workers)
    try:
        futures = [pool.submit(job, item) for item in items]
        out = []
        for future in futures:
            out.append(future.result())
            check()
    except BaseException:
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return out


def _words(path: str) -> set[str]:
    from rpggen.core import classifier

    folders, stem = classifier.tokens(path)
    return set(folders) | set(stem)


def _read_blocks(item: tuple[catalog_mod.Asset, Path, dict[str, Any], str]) -> list[blocks.Block]:
    """The terrain blocks of one sheet, cut as its grid says (a margin and a separation too)."""
    asset, file, grid, _stem = item
    cell = [int(v) for v in grid["cell"]]
    margin = [int(v) for v in grid.get("margin") or [0, 0]]
    sep = [int(v) for v in grid.get("separation") or [0, 0]]
    try:
        with Image.open(file) as opened:
            rgba = np.asarray(opened.convert("RGBA"))
    except (OSError, ValueError):
        return []
    rgba = blocks.packed(rgba, cell[0], cell[1], (margin[0], margin[1]), (sep[0], sep[1]))
    found = blocks.find(rgba, cell[0], cell[1], _words(asset.path))
    for b in found:
        if b.a2 is not None:
            x, y = b.a2[0] * cell[0], b.a2[1] * cell[1]
            crop = np.ascontiguousarray(rgba[y : y + 3 * cell[1], x : x + 2 * cell[0]])
            b.picture = Image.fromarray(crop, "RGBA")
    return found


def _apply_blocks(
    asset: catalog_mod.Asset,
    found: list[blocks.Block],
    stem: str,
    used_sets: set[str],
    result: TerrainResult,
) -> None:
    """The blocks of a sheet as terrains of its tiles (``tile_overrides``) and terrain sets."""
    if not found:
        return
    overrides = asset.detected.setdefault("tile_overrides", {})
    sets = result.terrain_sets.setdefault(asset.id, [])
    for b in found:
        x, y = b.origin
        name = f"{stem}_{b.surface}_{x}_{y}"
        if name in used_sets:
            name = f"{asset.id.replace('.', '_').replace('#', '_')}_{b.surface}_{x}_{y}"
        used_sets.add(name)
        for key, entry in blocks.entries(b, name).items():
            overrides[key] = catalog_mod.merge(overrides.get(key, {}), entry)
        terrain_set = blocks.terrain_set(b, name, len(used_sets) - 1)
        terrain_set["sheet"] = asset.id
        sets.append(terrain_set)
    asset.detected["tile_overrides"] = {k: overrides[k] for k in sorted(overrides, key=_xy)}


def _compose_2x3(
    asset: catalog_mod.Asset,
    block: blocks.Block,
    stem: str,
    work: Path,
    used_sets: set[str],
    result: TerrainResult,
    added: list[catalog_mod.Asset],
) -> None:
    """The 47 tiles of an RPG Maker block of 2 x 3 cells found inside a sheet (T17.31), composed
    into an atlas of their own as the blocks of an A2 sheet are (``_a2_blocks``)."""
    if block.a2 is None or block.picture is None:
        return
    tile = int(block.picture.width // rpgmaker_a2.BLOCK_TILES[0])
    x, y = block.a2
    asset_slug = asset.id.replace(".", "_").replace("#", "_")
    set_name = f"{stem}_a2_{x}_{y}"
    if set_name in used_sets:
        set_name = f"{asset_slug}_a2_{x}_{y}"
    used_sets.add(set_name)
    name = f"{asset_slug}_a2_{x}_{y}.png"
    out = work / name
    tiles = rpgmaker_a2.compose_atlas(block.picture, 0, 0, tile, out)
    rel = f"{rpgmaker_a2.TERRAIN_DIR}/{name}"
    atlas_rows = (47 + rpgmaker_a2.ATLAS_COLUMNS - 1) // rpgmaker_a2.ATLAS_COLUMNS
    facets: dict[str, Any] = {
        "usage": "tiles",
        "role": asset.detected.get("role", "AUTOTILE"),
        "grid": {"cell": [tile, tile], "margin": [0, 0], "separation": [0, 0]},
        "collision": {"profile": "NONE"},
        "tags": [GENERATED_TAG],
        "tile_overrides": rpgmaker_a2.atlas_tile_overrides(set_name),
        "size": [rpgmaker_a2.ATLAS_COLUMNS * tile, atlas_rows * tile],
    }
    if asset.detected.get("tileset"):
        facets["tileset"] = asset.detected["tileset"]
    new_id = f"{GENERATED_PACK}.{asset_slug}_a2_{x}_{y}"
    added.append(
        catalog_mod.Asset(
            id=new_id,
            pack_id=GENERATED_PACK,
            path=rel,
            sha256=_pixel_sha(rpgmaker_a2.atlas_from_tiles(tiles, tile)),
            kind="image",
            status="AUTO_DETECTED",
            detected=facets,
            detected_by="terrain_blocks",
            confidence=1.0,
        )
    )
    result.generated[rel] = str(out)
    set_def = rpgmaker_a2.terrain_set_def(set_name, len(used_sets) - 1)
    result.terrain_sets[new_id] = [set_def]


def _xy(key: str) -> tuple[int, int]:
    x, _sep, y = key.partition(",")
    return (int(y), int(x)) if x.isdigit() and y.isdigit() else (1 << 30, 0)


def _describe_a2(asset: catalog_mod.Asset, work: Path, result: TerrainResult) -> None:
    """Gives the terrain set of an RPG Maker A2 block what the painting asks (T17.31): the
    surface of its middle, whether it is drawn over nothing, and that it has every shape."""
    sets = result.terrain_sets.get(asset.id) or []
    rel = asset.path
    file = Path(result.generated.get(rel, work / posixpath.basename(rel)))
    if not sets or not file.is_file():
        return
    tile = int(asset.detected["grid"]["cell"][0])
    masks = rpgmaker_a2.blob_masks()
    try:
        with Image.open(file) as opened:
            atlas = np.asarray(opened.convert("RGBA"))
    except (OSError, ValueError):
        return
    columns = rpgmaker_a2.ATLAS_COLUMNS

    def cell_of(mask: int) -> np.ndarray:
        i = masks.index(mask)
        cx, cy = i % columns, i // columns
        return atlas[cy * tile : (cy + 1) * tile, cx * tile : (cx + 1) * tile]

    middle = cell_of(255)
    painted = middle[..., 3] > 0
    colour = middle[..., :3][painted].mean(axis=0) / 255.0 if painted.any() else np.zeros(3)
    single = cell_of(0)
    edge = np.concatenate([single[0, :, 3], single[-1, :, 3], single[:, 0, 3], single[:, -1, 3]])
    for terrain_set in sets:
        terrain_set["surface"] = blocks.surface_of(colour, _words(asset.path))
        terrain_set["over"] = "nothing" if float((edge > 0).mean()) < 0.5 else "ground"
        terrain_set["shape"] = "any"
        terrain_set["layout"] = "rpgmaker_a2"
        terrain_set["sheet"] = asset.id


def attach_terrain_sets(catalog: catalog_mod.Catalog, result: TerrainResult) -> None:
    """Add the terrain sets of generated assets to the tile set that holds the asset."""
    for tdef in catalog.tilesets:
        existing = {t["name"] for t in tdef.terrain_sets}
        for src in tdef.sources:
            for terrain_set in result.terrain_sets.get(src["asset"], []):
                if terrain_set["name"] not in existing:
                    tdef.terrain_sets.append(copy.deepcopy(terrain_set))
                    existing.add(terrain_set["name"])

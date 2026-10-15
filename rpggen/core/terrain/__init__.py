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
from rpggen.core.terrain import blob, blocks, rpgmaker_a2, tiled_wang
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
    for asset in sorted(catalog.assets, key=lambda a: catalog_mod._sort_key(a.id)):
        facets = asset.detected
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
        tags = _tags(facets)
        cell = _cell(facets)
        stem = ids.slug(posixpath.splitext(posixpath.basename(rel))[0])
        if "rpgmaker_autotile" in tags:
            sheet_kind = next((t for t in tags if t in ("A1", "A2", "A3", "A4")), "")
            if sheet_kind in DEFERRED_A_SHEETS:
                issues.add("TILE-006", asset=asset.id, file=asset.path)
            elif sheet_kind == "A2" and cell and file.is_file():
                _a2_blocks(asset, file, cell, stem, work, used_sets, result, added, issues)
            continue
        if any("terrain" in v for v in (facets.get("tile_overrides") or {}).values()):
            continue  # terrain already known (Tiled wang sets)
        _blob_proposal(asset, file, cell, stem, issues)
        grid = facets.get("grid") or {}
        if (
            grid.get("cell")
            and "terrain_proposal" not in asset.detected
            and file.is_file()
            and _holds_terrains(facets)
        ):
            searched.append((asset, file, grid, stem))
    for (asset, _path, _size, stem), found in zip(
        searched, _in_parallel(_read_blocks, searched, is_cancelled), strict=True
    ):
        _apply_blocks(asset, found, stem, used_sets, result)
    for asset in added:
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
    issues: IssueList,
) -> None:
    if not file.is_file():
        return
    size = asset.detected.get("size")
    if not size:
        return
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
        return
    with Image.open(file) as opened:
        sheet = opened.convert("RGBA")
    hinted = any(h in asset.path.casefold() for h in TERRAIN_HINTS)
    for c in cells:
        proposal, recognition = blob.propose(sheet, c[0], c[1], f"{stem}_terrain")
        if proposal is not None:
            asset.detected["terrain_proposal"] = proposal
            return
        if recognition is not None and recognition.flat:
            return  # a plain ground in the shape of an autotile sheet: nothing was skipped
        if recognition is not None and max(size) > TINY_SHEET:
            hinted = hinted or recognition.confidence >= 0.5
    if hinted:
        issues.add("TILE-006", asset=asset.id, file=asset.path)


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
    return blocks.find(rgba, cell[0], cell[1], _words(asset.path))


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

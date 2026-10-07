"""Terrain assignments for the catalog (T8.06).

The Python side only produces data; the Godot builder applies it to the TileSet:

* ``tiled_wang``: Tiled wangids -> peering bits in ``tile_overrides``.
* ``rpgmaker_a2``: RPG Maker A2 blocks -> generated 47-tile atlases with peering.
* ``blob``: generic 47-tile blob / 16-tile corner sheets -> ``terrain_proposal`` facets.

``rpggen.core.catalog.assemble`` calls the functions of this module; they only read the pack
files and the detected facets, so the result is deterministic.
"""

from __future__ import annotations

import copy
import hashlib
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen import ids, paths
from rpggen.core import catalog as catalog_mod
from rpggen.core.terrain import blob, rpgmaker_a2, tiled_wang
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
) -> TerrainResult:
    """A2 composites, blob proposals and TILE-006 reports for the tile sheets of ``catalog``.

    ``roots`` maps pack ids to the folder holding the pack files. New assets are appended to
    ``catalog.assets`` (pack ``generated``); the atlases are written below ``work_dir``.
    """
    result = TerrainResult()
    work = (work_dir or paths.local_cache_dir()) / "terrain_atlases"
    used_sets: set[str] = set()
    added: list[catalog_mod.Asset] = []
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
        if recognition is not None and max(size) > TINY_SHEET:
            hinted = hinted or recognition.confidence >= 0.5
    if hinted:
        issues.add("TILE-006", asset=asset.id, file=asset.path)


def attach_terrain_sets(catalog: catalog_mod.Catalog, result: TerrainResult) -> None:
    """Add the terrain sets of generated assets to the tile set that holds the asset."""
    for tdef in catalog.tilesets:
        existing = {t["name"] for t in tdef.terrain_sets}
        for src in tdef.sources:
            for terrain_set in result.terrain_sets.get(src["asset"], []):
                if terrain_set["name"] not in existing:
                    tdef.terrain_sets.append(copy.deepcopy(terrain_set))
                    existing.add(terrain_set["name"])

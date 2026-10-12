"""The tile set of an isometric project (T17.13): the atlases its single tiles are packed into.

An isometric pack is one picture a tile (T17.12). Godot's tile set wants an atlas, so for a
project with ``projection: isometric`` rpggen packs the tiles of each pack into atlas pictures
(``generated/iso_atlases/<pack>_<n>.png``), every tile in a cell of the pack's canvas, and
describes one tile set, ``iso``, whose sources are those pictures and whose tile size is the
diamond of the project's ground. The builder (``builder/lib/iso_tileset.gd``) makes the Godot
``TileSet`` from it.

**A painted cell never moves.** A map stores a tile as a source id and atlas coordinates. So
the cell of every tile is written down once, in ``id_allocations.iso_atlases`` of the catalog
(beside the source ids the M5 merge keeps), and never changes: a tile that is added gets the
next free cell, a tile that is gone leaves its cell empty, and a second picture is begun when
the first is full. The number of columns and of rows of a pack's pictures is fixed when its
first tile is placed. Only the size of a cell may grow (a pack of one width and several
heights that gets a taller picture): the coordinates stay, and every picture is put on the
bottom of its cell again.

**One diamond a project.** The project has the footprint of its ground: of the tile chosen as
``starter.ground``, else of the first isometric ground tile; once the tile set exists, of the
tile set. Isometric tiles drawn on another diamond are left out (``TILE-012``).

Nothing here looks at a pixel to decide anything: the layout follows from the catalog alone,
so the dry run, which has no pack files in front of it, describes the same tile set (and the
same fingerprint) as the run that writes the pictures.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen.core import catalog as catalog_mod
from rpggen.core.config import PROJECTION_ISOMETRIC, GeneratorConfig
from rpggen.errors import RpgGenError

ATLAS_PACK = "rpggen_iso"
ATLAS_DIR = "generated/iso_atlases"
ATLAS_TAG = "iso_atlas"
TILESET = "iso"
ALLOCATIONS = "iso_atlases"  # the key in ``Catalog.id_allocations``
# A picture is at most this many cells wide and high, and about this many px: 64 tiles of
# 180 x 256 are 1440 x 2048, 32 of 256 x 512 are 2048 x 2048.
MAX_COLUMNS = 8
MAX_ROWS = 8
MAX_SIDE = 2048
# What the maps ask a tile (as the top-down tile set and the farm's soil have them): which
# asset it is, what it sounds like underfoot, what it costs to cross, whether a hoe can till it
# and whether it fills a watering can.
CUSTOM_DATA: list[dict[str, str]] = [
    *catalog_mod.DEFAULT_CUSTOM_DATA,
    {"name": "tillable", "type": "bool"},
    {"name": "water", "type": "bool"},
]
_INACTIVE = {"UNUSED", "MISSING"}


def wanted(cfg: GeneratorConfig) -> bool:
    return cfg.projection == PROJECTION_ISOMETRIC


def footprint_of(asset: catalog_mod.Asset) -> tuple[int, int] | None:
    """The diamond an isometric tile stands on, or None when its facets do not say one."""
    found = catalog_mod.effective(asset).get("footprint")
    if isinstance(found, list) and len(found) == 2 and all(int(v) > 0 for v in found):
        return int(found[0]), int(found[1])
    return None


def iso_tiles(catalog: catalog_mod.Catalog) -> list[catalog_mod.Asset]:
    """The isometric tiles of the packs that are in use, in the order of their ids."""
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: catalog_mod._sort_key(a.id))
        if a.kind == "image"
        and a.status not in _INACTIVE
        and catalog_mod.is_iso_tile(a)
        and footprint_of(a) is not None
    ]


def ground_tiles(catalog: catalog_mod.Catalog) -> list[catalog_mod.Asset]:
    return [a for a in iso_tiles(catalog) if catalog_mod.effective(a).get("role") == "GROUND"]


def project_ground(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> catalog_mod.Asset | None:
    """The ground tile an isometric project is laid with: the one chosen on the Mapping page
    (``starter.ground``) when it is an isometric ground tile, else the default choice."""
    from rpggen.core import mapping

    grounds = {a.id: a for a in ground_tiles(catalog)}
    chosen = (cfg.starter or {}).get("ground", "")
    if chosen in grounds:
        return grounds[chosen]
    best = mapping.best_for(catalog, "GROUND", PROJECTION_ISOMETRIC)
    return grounds.get(best or "")


def existing_def(catalog: catalog_mod.Catalog) -> catalog_mod.TileSetDef | None:
    """The isometric tile set a last run described (a regeneration finds it in the catalog)."""
    return next((t for t in catalog.tilesets if t.projection == PROJECTION_ISOMETRIC), None)


def project_footprint(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> tuple[int, int] | None:
    """The diamond of the project: of its tile set when it has one (maps are painted with it),
    else of its ground. None when the packs have no isometric ground tile."""
    known = existing_def(catalog)
    if known is not None:
        return int(known.tile_size[0]), int(known.tile_size[1])
    ground = project_ground(catalog, cfg)
    return footprint_of(ground) if ground is not None else None


def check_ground(catalog: catalog_mod.Catalog, cfg: GeneratorConfig) -> None:
    """CAT-002 for an isometric project whose packs have no isometric ground tile: no ground is
    drawn for this view, so there is nothing to lay a map with."""
    if wanted(cfg) and not ground_tiles(catalog):
        raise RpgGenError(
            "CAT-002",
            file="config",
            reason="/projection: the packs have no isometric ground tile, and an isometric "
            "project needs one (no ground is drawn for this view); add a pack of isometric "
            "tiles, give one of its tiles the role GROUND in the audit, or leave the "
            "projection top_down",
        )


def other_footprints(
    catalog: catalog_mod.Catalog, cfg: GeneratorConfig
) -> list[tuple[str, tuple[int, int], tuple[int, int]]]:
    """``(pack id, its diamond, the project's diamond)`` for every pack whose isometric tiles
    stand on another diamond than the project's ground: they are left out of the tile set
    (``TILE-012``). One row a pack and a diamond, sorted."""
    footprint = project_footprint(catalog, cfg)
    if footprint is None:
        return []
    found = {
        (a.pack_id, footprint_of(a)) for a in iso_tiles(catalog) if footprint_of(a) != footprint
    }
    return [(pack_id, own, footprint) for pack_id, own in sorted(found) if own is not None]


def _size(asset: catalog_mod.Asset) -> tuple[int, int]:
    facets = catalog_mod.effective(asset)
    size = facets.get("size") or facets.get("canvas") or [1, 1]
    return int(size[0]), int(size[1])


def _grid(cell: tuple[int, int]) -> tuple[int, int]:
    """How many columns and rows a pack's pictures have, from the size of its cell."""
    columns = max(1, min(MAX_COLUMNS, MAX_SIDE // max(1, cell[0])))
    rows = max(1, min(MAX_ROWS, MAX_SIDE // max(1, cell[1])))
    return columns, rows


def allocate(entry: dict[str, Any], members: list[catalog_mod.Asset]) -> None:
    """Give every tile of ``members`` (one pack's, in the order of their ids) a cell in the
    pack's record ``entry``: a tile that has one keeps it, a new tile gets the next. The cell
    grows to the largest picture and never shrinks."""
    cell = list(entry.get("cell") or [0, 0])
    for asset in members:
        w, h = _size(asset)
        cell = [max(int(cell[0]), w), max(int(cell[1]), h)]
    entry["cell"] = cell
    if not entry.get("columns"):
        entry["columns"], entry["rows"] = _grid((cell[0], cell[1]))
    cells: dict[str, int] = entry.setdefault("cells", {})
    following = int(entry.get("next_cell", 0))
    for asset in members:
        if asset.id not in cells:
            cells[asset.id] = following
            following += 1
    entry["next_cell"] = following
    entry.setdefault("sources", [])


def place(entry: dict[str, Any], asset_id: str) -> tuple[int, int, int]:
    """``(picture, column, row)`` of a tile from its cell number."""
    index = int(entry["cells"][asset_id])
    columns, rows = int(entry["columns"]), int(entry["rows"])
    page, within = divmod(index, columns * rows)
    return page, within % columns, within // columns


def _layout_hash(layout: dict[str, Any]) -> str:
    """The identity of an atlas picture: what is in which cell, by the hashes of the pack's
    files. Not the hash of the PNG, which the dry run does not write and whose bytes follow the
    encoder."""
    text = json.dumps(layout, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atlas_id(pack_id: str, page: int) -> str:
    return f"{ATLAS_PACK}.{pack_id}_{page}"


def add(catalog: catalog_mod.Catalog, cfg: GeneratorConfig, staging_root: Path) -> list[str]:
    """Describe the isometric tile set of ``catalog`` and write its atlas pictures under
    ``staging_root`` (where the packs' files are installed; a root without them, as the dry
    run's, gets the description only). What a last run left (the atlas assets, the tile set)
    is replaced; the cells and the source ids in ``id_allocations`` are kept and added to.
    Returns the ids of the atlas assets."""
    footprint = project_footprint(catalog, cfg)
    known = existing_def(catalog)
    catalog.assets[:] = [a for a in catalog.assets if a.pack_id != ATLAS_PACK]
    catalog.tilesets[:] = [t for t in catalog.tilesets if not t.projection]
    if footprint is None:
        return []
    by_pack: dict[str, list[catalog_mod.Asset]] = {}
    for asset in iso_tiles(catalog):
        if footprint_of(asset) == footprint:
            by_pack.setdefault(asset.pack_id, []).append(asset)
    custom = copy.deepcopy(known.custom_data) if known else []
    for layer in CUSTOM_DATA:  # layers are added, never removed or retyped
        if not any(c["name"] == layer["name"] for c in custom):
            custom.append(dict(layer))
    tdef = catalog_mod.TileSetDef(
        name=TILESET,
        tile_size=[footprint[0], footprint[1]],
        physics_layers=copy.deepcopy(
            known.physics_layers if known else catalog_mod.DEFAULT_PHYSICS_LAYERS
        ),
        custom_data=custom,
        terrain_sets=copy.deepcopy(known.terrain_sets) if known else [],
        navigation=known.navigation if known else False,
        patterns_from_objects=False,
        projection=PROJECTION_ISOMETRIC,
    )
    # which pictures are one tile turned: the first turn of each set names it
    turned = catalog_mod.turn_sets([a for members in by_pack.values() for a in members])
    records: dict[str, Any] = catalog.id_allocations.setdefault(ALLOCATIONS, {})
    made: list[str] = []
    # the pictures are written where the packs are installed; the dry run's folder has none
    writes = (Path(staging_root) / "assets").is_dir()
    # a pack whose tiles are all gone keeps its pictures' sources: painted maps name them
    for pack_id in sorted(set(by_pack) | set(records)):
        members = by_pack.get(pack_id, [])
        entry = records.setdefault(pack_id, {})
        allocate(entry, members)
        columns, rows = int(entry["columns"]), int(entry["rows"])
        cell_w, cell_h = (int(v) for v in entry["cell"])
        per_page = columns * rows
        pages = -(-int(entry["next_cell"]) // per_page)
        while len(entry["sources"]) < pages:
            entry["sources"].append(catalog.allocate_source_id(TILESET))
        for page in range(pages):
            # as many rows as cells were ever given out on this picture: it never shrinks
            given = min(int(entry["next_cell"]) - page * per_page, per_page)
            size = (columns * cell_w, -(-given // columns) * cell_h)
            sheet = Image.new("RGBA", size if writes else (1, 1), (0, 0, 0, 0))
            layout: dict[str, Any] = {"cell": [cell_w, cell_h], "size": list(size), "tiles": []}
            for asset in members:
                where = place(entry, asset.id)
                if where[0] != page:
                    continue
                w, h = _size(asset)
                at = [(cell_w - w) // 2, cell_h - h]  # on the bottom of its cell, in the middle
                tdef.tiles[asset.id] = {
                    "source": int(entry["sources"][page]),
                    "coords": [where[1], where[2]],
                    "at": at,
                }
                if asset.id in turned:
                    tdef.tiles[asset.id]["of"] = turned[asset.id]
                layout["tiles"].append([where[1], where[2], at[0], at[1], asset.sha256])
                file = Path(staging_root) / asset.path
                if writes and file.is_file():
                    with Image.open(file) as opened:
                        picture = opened.convert("RGBA")
                    sheet.paste(picture, (where[1] * cell_w + at[0], where[2] * cell_h + at[1]))
            rel = f"{ATLAS_DIR}/{pack_id}_{page}.png"
            if writes:
                target = Path(staging_root) / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                sheet.save(target, format="PNG", optimize=False, compress_level=9, pnginfo=None)
            layout["tiles"].sort()
            facets: dict[str, Any] = {
                "usage": catalog_mod.ISO_ATLAS_USAGE,
                "role": "NONE",
                "projection": PROJECTION_ISOMETRIC,
                "footprint": [footprint[0], footprint[1]],
                "grid": {"cell": [cell_w, cell_h], "margin": [0, 0], "separation": [0, 0]},
                "size": list(size),
                "tags": [ATLAS_TAG],
                "tileset": TILESET,
            }
            catalog.assets.append(
                catalog_mod.Asset(
                    id=atlas_id(pack_id, page),
                    pack_id=ATLAS_PACK,
                    path=rel,
                    sha256=_layout_hash(layout),
                    kind="image",
                    status="CONFIRMED",
                    detected=facets,
                    detected_by="iso_atlas",
                    confidence=1.0,
                )
            )
            tdef.sources.append(
                {"asset": atlas_id(pack_id, page), "source_id": int(entry["sources"][page])}
            )
            made.append(atlas_id(pack_id, page))
    tdef.sources.sort(key=lambda s: s["source_id"])
    if not any(p.pack_id == ATLAS_PACK for p in catalog.packs):
        catalog.packs.append(
            catalog_mod.CatalogPack(ATLAS_PACK, "0" * 64, ATLAS_DIR, [], [], None, [])
        )
    catalog.tilesets.append(tdef)
    catalog.tilesets.sort(key=lambda t: catalog_mod._sort_key(t.name))
    catalog.assets.sort(key=lambda a: catalog_mod._sort_key(a.id))
    return made

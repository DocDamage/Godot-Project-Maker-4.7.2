from __future__ import annotations

import json
import posixpath
from pathlib import Path
from typing import Any

from rpggen.core.adapters import maps as maps_mod
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

COLLISION_VALUE_NAMES = {"wall", "solid", "collision"}
COLLISION_LAYER_TOKENS = ("collision", "wall", "solid")
MAX_LDTK_BYTES = 32 * 1024 * 1024


def _load(root: Path, rel: str) -> dict[str, Any] | None:
    path = root / rel
    if path.stat().st_size > MAX_LDTK_BYTES:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _solid_default(layer_name: str, names: dict[int, str], value: int) -> bool:
    """A value is solid when it is named wall, solid or collision; in a layer with such a name
    and no named value at all, every value is."""
    if names.get(value, "").casefold() in COLLISION_VALUE_NAMES:
        return True
    unnamed = not any(n.casefold() in COLLISION_VALUE_NAMES for n in names.values())
    return unnamed and any(token in layer_name.casefold() for token in COLLISION_LAYER_TOKENS)


def _level_layers(
    level: dict[str, Any],
    defs: dict[str, Any],
    project_dir: str,
    by_lower: dict[str, str],
    rel: str,
    issues: IssueList,
) -> tuple[list[dict[str, Any]], int]:
    """The raw layers of one level, bottom layer first, and the level's cell size."""
    tilesets = {t.get("uid"): t for t in defs.get("tilesets", []) if isinstance(t, dict)}
    layer_defs = {d.get("uid"): d for d in defs.get("layers", []) if isinstance(d, dict)}
    out: list[dict[str, Any]] = []
    grid_size = 0
    for inst in reversed(level.get("layerInstances") or []):  # LDtk lists the top layer first
        kind = inst.get("__type")
        name = str(inst.get("__identifier", "layer"))
        size = int(inst.get("__gridSize", 0))
        grid_size = grid_size or size
        if size <= 0:
            continue
        ts = tilesets.get(inst.get("__tilesetDefUid"))
        tiles_raw = (inst.get("gridTiles") or []) + (inst.get("autoLayerTiles") or [])
        if kind == "IntGrid":
            names = {
                int(v.get("value", 0)): str(v.get("identifier") or "")
                for v in (layer_defs.get(inst.get("layerDefUid")) or {}).get("intGridValues", [])
            }
            data = [int(v) for v in inst.get("intGridCsv") or []]
            width, height = int(inst.get("__cWid", 0)), int(inst.get("__cHei", 0))
            if len(data) == width * height and any(data):
                used = sorted({v for v in data if v})
                values = [
                    {"value": v, "name": names.get(v, ""), "solid": _solid_default(name, names, v)}
                    for v in used
                ]
                out.append(maps_mod.intgrid_layer(name, (width, height), data, values))
                if tiles_raw:  # auto-layer rules draw the IntGrid: the tiles are a layer too
                    name = f"{name}_tiles"
        if kind in ("Tiles", "AutoLayer", "IntGrid") and tiles_raw:
            image = None
            if ts is not None and ts.get("relPath"):
                joined = posixpath.normpath(posixpath.join(project_dir, str(ts["relPath"])))
                image = by_lower.get(joined.casefold())
            if image is None or ts is None:
                issues.add(
                    "TILE-009", file=rel, layer=name, map=rel,
                    reason="its tile sheet was not found in the pack",
                )  # fmt: skip
                continue
            tile_size = int(ts.get("tileGridSize", 0)) or size
            step = tile_size + int(ts.get("spacing", 0))
            padding = int(ts.get("padding", 0))
            cells: dict[tuple[int, int], list[Any]] = {}
            for t in tiles_raw:
                px, src, flip = t.get("px", [0, 0]), t.get("src", [0, 0]), int(t.get("f", 0))
                x, y = int(px[0]) // size, int(px[1]) // size
                alt = (maps_mod.FLIP_H if flip & 1 else 0) | (maps_mod.FLIP_V if flip & 2 else 0)
                col, row = (int(src[0]) - padding) // step, (int(src[1]) - padding) // step
                cells[(x, y)] = [x, y, image, col, row, alt]
            out.append(
                maps_mod.tile_layer(
                    name, [cells[k] for k in sorted(cells, key=lambda k: (k[1], k[0]))]
                )
            )
        elif kind == "Entities":
            objects = []
            for e in inst.get("entityInstances") or []:
                marker = maps_mod.marker_kind(str(e.get("__identifier", "")), name)
                if marker is None:
                    continue
                px = e.get("px", [0, 0])
                props = {
                    str(f.get("__identifier", "")): f.get("__value")
                    for f in e.get("fieldInstances") or []
                    if isinstance(f, dict)
                }
                objects.append({
                    "name": str(props.get("name") or str(e.get("iid", ""))[:8]),
                    "type": marker, "x": int(px[0]), "y": int(px[1]),
                    "w": int(e.get("width", 0)), "h": int(e.get("height", 0)), "props": props,
                })  # fmt: skip
            if objects:
                out.append(maps_mod.objects_layer(name, objects))
    return out, grid_size


def _read_levels(
    data: dict[str, Any], root: Path, rel: str, by_lower: dict[str, str], issues: IssueList
) -> list[dict[str, Any]]:
    """One raw map per level of the project."""
    project_dir = posixpath.dirname(rel)
    maps: list[dict[str, Any]] = []
    for level in data.get("levels", []):
        if not isinstance(level, dict):
            continue
        if level.get("layerInstances") is None and level.get("externalRelPath"):
            ext = by_lower.get(
                posixpath.normpath(posixpath.join(project_dir, level["externalRelPath"])).casefold()
            )
            loaded = _load(root, ext) if ext else None
            if loaded is None:
                issues.add("ADAPT-001", adapter="ldtk", file=rel, reason="a level file is missing")
                continue
            level = loaded
        layers, grid_size = _level_layers(
            level, data.get("defs", {}), project_dir, by_lower, rel, issues
        )
        if not layers:
            continue
        cell = max(grid_size, 1)
        width = max(int(level.get("pxWid", 0)) // cell, 1)
        height = max(int(level.get("pxHei", 0)) // cell, 1)
        for lay in layers:
            if lay["kind"] == "intgrid":
                width, height = max(width, lay["size"][0]), max(height, lay["size"][1])
            for t in lay.get("tiles", []):
                width, height = max(width, int(t[0]) + 1), max(height, int(t[1]) + 1)
        maps.append({
            "name": str(level.get("identifier", "level")),
            "source": rel,
            "format": "ldtk",
            "tile_size": [grid_size, grid_size],
            "size": [width, height],
            "layers": layers,
        })  # fmt: skip
    return maps


class LdtkAdapter:
    name = "ldtk"
    priority = 30

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if any(f.ext == ".ldtk" for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        by_lower = {f.path.casefold(): f.path for f in inv.files}
        for f in inv.files:
            if f.ext != ".ldtk":
                continue
            data = _load(root, f.path)
            if data is None:
                issues.add(
                    "ADAPT-001", adapter=self.name, file=f.path, reason="not a valid LDtk project"
                )
                continue
            defs = data.get("defs", {})
            for ts in defs.get("tilesets", []):
                rel = ts.get("relPath")
                if not rel:
                    continue  # embedded atlas without an image file
                joined = posixpath.normpath(posixpath.join(posixpath.dirname(f.path), str(rel)))
                image = by_lower.get(joined.casefold())
                if image is None:
                    issues.add("ADAPT-002", file=f.path, image=str(rel))
                    continue
                size = int(ts.get("tileGridSize", 0))
                if size <= 0:
                    issues.add(
                        "ADAPT-001", adapter=self.name, file=f.path, reason="invalid tileGridSize"
                    )
                    continue
                spacing, padding = int(ts.get("spacing", 0)), int(ts.get("padding", 0))
                facets = {
                    "usage": "tiles",
                    "grid": {
                        "cell": [size, size],
                        "margin": [padding, padding],
                        "separation": [spacing, spacing],
                    },
                }
                result.assets.append(AssetFragment(image, facets, 1.0, "full"))
            result.maps.extend(_read_levels(data, root, f.path, by_lower, issues))
            for layer in defs.get("layers", []):
                names = {
                    str(v.get("identifier", "")).casefold() for v in layer.get("intGridValues", [])
                }
                if names & COLLISION_VALUE_NAMES:
                    result.pack_warnings.append("ldtk_intgrid_collision_available")
                    break
        result.issues = list(issues)
        return result

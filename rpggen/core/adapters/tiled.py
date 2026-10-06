from __future__ import annotations

import json
import posixpath
import xml.etree.ElementTree as ET  # noqa: S405 - local pack files; size-limited below
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

MAX_METADATA_BYTES = 8 * 1024 * 1024
CUSTOM_DATA_NAMES = ("footstep", "move_cost")  # the TileSetDef custom data layers (T1.10)
WANG_MODES = {"corner": "corners", "edge": "sides", "mixed": "corners_and_sides"}
FLOAT_PROPERTIES = {"move_cost"}


@dataclass
class _Tile:
    props: dict[str, Any] = field(default_factory=dict)
    objects: list[list[list[float]]] = field(default_factory=list)  # polygons
    animation: list[tuple[int, int]] = field(default_factory=list)  # (tileid, duration ms)


@dataclass
class _Wang:
    name: str
    mode: str
    colors: list[tuple[str, str]]
    tiles: list[tuple[int, list[int]]]


@dataclass
class _Tileset:
    name: str
    tile_w: int
    tile_h: int
    spacing: int
    margin: int
    columns: int
    image: str
    tiles: dict[int, _Tile]
    wangsets: list[_Wang]
    base_dir: str  # pack-relative folder of the defining file
    source_file: str


def _num(value: Any) -> float | int:
    f = float(value)
    return int(f) if f.is_integer() else round(f, 6)


# --------------------------------------------------------------------------- parsing


def _rect_poly(x: float, y: float, w: float, h: float) -> list[list[float]]:
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def _parse_points(text: str) -> list[list[float]]:
    pts = []
    for pair in text.split():
        a, _, b = pair.partition(",")
        pts.append([float(a), float(b)])
    return pts


def _xml_tileset(el: ET.Element, base_dir: str, source_file: str) -> _Tileset | None:
    image = el.find("image")
    if image is None or not image.get("source"):
        return None
    tw, th = int(el.get("tilewidth", 0)), int(el.get("tileheight", 0))
    spacing, margin = int(el.get("spacing", 0)), int(el.get("margin", 0))
    columns = int(el.get("columns", 0))
    image_width = image.get("width")
    if columns <= 0 and tw > 0 and image_width:
        columns = (int(image_width) - 2 * margin + spacing) // (tw + spacing)
    tiles: dict[int, _Tile] = {}
    for t in el.findall("tile"):
        tile = tiles.setdefault(int(t.get("id", -1)), _Tile())
        for prop in t.findall("./properties/property"):
            tile.props[prop.get("name", "")] = _prop_value(
                prop.get("type"), prop.get("value", prop.text or "")
            )
        for obj in t.findall("./objectgroup/object"):
            x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
            poly = obj.find("polygon")
            if poly is not None:
                tile.objects.append(
                    [[x + px, y + py] for px, py in _parse_points(poly.get("points", ""))]
                )
            elif (
                (ow := obj.get("width"))
                and (oh := obj.get("height"))
                and obj.find("ellipse") is None
            ):
                tile.objects.append(_rect_poly(x, y, float(ow), float(oh)))
        for fr in t.findall("./animation/frame"):
            tile.animation.append(
                (int(fr.get("tileid", 0)), int(fr.get("duration", fr.get("tileduration", 100))))
            )
    wangsets = []
    for ws in el.findall("./wangsets/wangset"):
        colors = [(c.get("name", ""), c.get("color", "#000000")) for c in ws.findall("wangcolor")]
        wtiles = [
            (int(wt.get("tileid", 0)), [int(v) for v in wt.get("wangid", "").split(",") if v != ""])
            for wt in ws.findall("wangtile")
        ]
        wangsets.append(_Wang(ws.get("name", "terrain"), ws.get("type", "corner"), colors, wtiles))
    return _Tileset(
        el.get("name", "tileset"), tw, th, spacing, margin, columns, image.get("source", ""),
        tiles, wangsets, base_dir, source_file,
    )  # fmt: skip


def _prop_value(ptype: str | None, value: Any) -> Any:
    if ptype in ("int", "float"):
        try:
            return _num(value)
        except (TypeError, ValueError):
            return value
    if ptype == "bool":
        return str(value).lower() == "true"
    return value


def _json_tileset(d: dict[str, Any], base_dir: str, source_file: str) -> _Tileset | None:
    if not d.get("image"):
        return None
    tw, th = int(d.get("tilewidth", 0)), int(d.get("tileheight", 0))
    spacing, margin = int(d.get("spacing", 0)), int(d.get("margin", 0))
    columns = int(d.get("columns", 0))
    if columns <= 0 and tw > 0 and d.get("imagewidth"):
        columns = (int(d["imagewidth"]) - 2 * margin + spacing) // (tw + spacing)
    tiles: dict[int, _Tile] = {}
    for t in d.get("tiles", []):
        tile = tiles.setdefault(int(t.get("id", -1)), _Tile())
        for prop in t.get("properties", []):
            tile.props[prop.get("name", "")] = _prop_value(prop.get("type"), prop.get("value"))
        for obj in (t.get("objectgroup") or {}).get("objects", []):
            x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
            if obj.get("polygon"):
                tile.objects.append([[x + p["x"], y + p["y"]] for p in obj["polygon"]])
            elif obj.get("width") and obj.get("height") and not obj.get("ellipse"):
                tile.objects.append(_rect_poly(x, y, float(obj["width"]), float(obj["height"])))
        for fr in t.get("animation", []):
            tile.animation.append((int(fr.get("tileid", 0)), int(fr.get("duration", 100))))
    wangsets = []
    for ws in d.get("wangsets", []):
        colors = [(c.get("name", ""), c.get("color", "#000000")) for c in ws.get("colors", [])]
        wtiles = [
            (int(wt["tileid"]), [int(v) for v in wt.get("wangid", [])])
            for wt in ws.get("wangtiles", [])
        ]
        wangsets.append(_Wang(ws.get("name", "terrain"), ws.get("type", "corner"), colors, wtiles))
    return _Tileset(
        d.get("name", "tileset"), tw, th, spacing, margin, columns, str(d["image"]),
        tiles, wangsets, base_dir, source_file,
    )  # fmt: skip


def _read_limited(path: Path) -> str | None:
    if path.stat().st_size > MAX_METADATA_BYTES:
        return None
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _collect(inv: Inventory, root: Path, issues: IssueList) -> tuple[list[_Tileset], bool]:
    """All Tiled tilesets of the pack and whether any standalone .tsx/.tsj file exists."""
    found: list[_Tileset] = []
    standalone = False
    for f in inv.files:
        ext = f.ext
        if ext not in (".tsx", ".tsj", ".tmx", ".tmj"):
            continue
        base = posixpath.dirname(f.path)
        try:
            text = _read_limited(root / f.path)
            if text is None:
                continue
            if ext == ".tsx":
                standalone = True
                ts = _xml_tileset(ET.fromstring(text), base, f.path)  # noqa: S314
                if ts:
                    found.append(ts)
            elif ext == ".tsj":
                standalone = True
                ts = _json_tileset(json.loads(text), base, f.path)
                if ts:
                    found.append(ts)
            elif ext == ".tmx":
                for el in ET.fromstring(text).findall("tileset"):  # noqa: S314
                    ts = _xml_tileset(el, base, f.path)
                    if ts:
                        found.append(ts)
            else:
                for d in json.loads(text).get("tilesets", []):
                    ts = _json_tileset(d, base, f.path) if isinstance(d, dict) else None
                    if ts:
                        found.append(ts)
        except (ET.ParseError, json.JSONDecodeError, ValueError, OSError) as exc:
            issues.add("ADAPT-001", adapter="tiled", file=f.path, reason=str(exc))
    return found, standalone


# --------------------------------------------------------------------------- conversion


def _convex_hull(points: list[list[float]]) -> list[list[float]]:
    pts = sorted({(p[0], p[1]) for p in points})
    if len(pts) <= 2:
        return [list(p) for p in pts]

    def cross(o, a, b) -> float:  # noqa: ANN001
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


def _coords(tile_id: int, columns: int) -> str:
    return f"{tile_id % columns},{tile_id // columns}"


def _resolve_image(ts: _Tileset) -> str | None:
    joined = posixpath.normpath(posixpath.join(ts.base_dir, ts.image.replace("\\", "/")))
    if joined.startswith("..") or joined.startswith("/"):
        return None
    return joined


class TiledAdapter:
    name = "tiled"
    priority = 10

    def match(self, inv: Inventory, root: Path) -> float:
        tilesets, standalone = _collect(inv, root, IssueList())
        if standalone:
            return 1.0
        return 0.6 if tilesets else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        tilesets, _ = _collect(inv, root, issues)
        by_lower = {f.path.casefold(): f.path for f in inv.files}
        ignored: set[str] = set()
        hulled = False
        for ts in tilesets:
            image = _resolve_image(ts)
            image = by_lower.get(image.casefold()) if image else None
            if image is None:
                issues.add("ADAPT-002", file=ts.source_file, image=ts.image)
                continue
            if ts.columns <= 0 or ts.tile_w <= 0 or ts.tile_h <= 0:
                issues.add(
                    "ADAPT-001",
                    adapter=self.name,
                    file=ts.source_file,
                    reason="invalid tile size or columns",
                )
                continue
            overrides: dict[str, dict[str, Any]] = {}

            def entry(
                tile_id: int, columns: int = ts.columns, store: dict = overrides
            ) -> dict[str, Any]:
                return store.setdefault(_coords(tile_id, columns), {})

            for tile_id, tile in sorted(ts.tiles.items()):
                if tile.objects:
                    if len(tile.objects) == 1:
                        poly = tile.objects[0]
                    else:
                        poly = _convex_hull([p for o in tile.objects for p in o])
                        hulled = True
                    entry(tile_id)["collision"] = {
                        "profile": "CUSTOM",
                        "polygon": [[_num(x), _num(y)] for x, y in poly],
                    }
                custom = {}
                for key, value in sorted(tile.props.items()):
                    if key in CUSTOM_DATA_NAMES:
                        custom[key] = (
                            float(value)
                            if key in FLOAT_PROPERTIES and not isinstance(value, bool)
                            else value
                        )
                    else:
                        ignored.add(key)
                if custom:
                    entry(tile_id)["custom"] = custom
                if tile.animation:
                    entry(tile_id)["anim"] = {
                        "frames": [
                            [fid % ts.columns, fid // ts.columns] for fid, _ in tile.animation
                        ],
                        "durations_ms": [dur for _, dur in tile.animation],
                    }
            terrain_sets = []
            for ws in ts.wangsets:
                terrain_sets.append(
                    {
                        "name": ws.name,
                        "mode": WANG_MODES.get(ws.mode, "corners_and_sides"),
                        "terrains": [{"name": n, "color": c} for n, c in ws.colors],
                    }
                )
                for tile_id, wangid in ws.tiles:
                    entry(tile_id)["terrain"] = {"set": ws.name, "wangid": wangid}
            facets: dict[str, Any] = {
                "usage": "tiles",
                "grid": {
                    "cell": [ts.tile_w, ts.tile_h],
                    "margin": [ts.margin, ts.margin],
                    "separation": [ts.spacing, ts.spacing],
                },
            }
            if overrides:
                facets["tile_overrides"] = {k: overrides[k] for k in sorted(overrides)}
            result.assets.append(AssetFragment(image, facets, 1.0, "full"))
            result.tilesets.append(
                {
                    "name": ts.name,
                    "tile_size": [ts.tile_w, ts.tile_h],
                    "sources": [{"path": image}],
                    "terrain_sets": terrain_sets,
                }
            )
        if hulled:
            result.pack_warnings.append("tiled_multi_object_collision_hulled")
        if ignored:
            result.pack_warnings.append("tiled_ignored_properties:" + ",".join(sorted(ignored)))
        result.issues = list(issues)
        return result

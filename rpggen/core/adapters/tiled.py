from __future__ import annotations

import base64
import binascii
import importlib
import io
import json
import posixpath
import re
import struct
import xml.etree.ElementTree as ET  # noqa: S405 - local pack files; size-limited below
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen.core.adapters import maps as maps_mod
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_TILE_BYTES = 64 * 1024 * 1024  # decompressed tile data of one layer
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
    # A collection of images (T17.28): tile id -> the picture of that tile, as the file names
    # it. Read only for an isometric map; a sheet's tile set leaves it empty.
    images: dict[int, str] = field(default_factory=dict)


ISOMETRIC = "isometric"
# Why a map of another shape is not imported (TILE-009).
REFUSED_ORIENTATIONS = {
    "staggered": "staggered maps are not imported",
    "hexagonal": "hexagonal maps are not imported",
}


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


def _xml_tileset(
    el: ET.Element, base_dir: str, source_file: str, collections: bool = False
) -> _Tileset | None:
    """A tile set of a sheet; with ``collections``, a collection of images too (T17.28)."""
    image = el.find("image")
    if image is None or not image.get("source"):
        return _xml_collection(el, base_dir, source_file) if collections else None
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


def _xml_collection(el: ET.Element, base_dir: str, source_file: str) -> _Tileset | None:
    """A tile set that is a collection of images (one picture a tile, as the isometric packs
    ship theirs): None when no tile of it names a picture."""
    images: dict[int, str] = {}
    for t in el.findall("tile"):
        image = t.find("image")
        if image is not None and image.get("source"):
            images[int(t.get("id", -1))] = image.get("source", "")
    if not images:
        return None
    return _Tileset(
        el.get("name", "tileset"), int(el.get("tilewidth", 0)), int(el.get("tileheight", 0)),
        0, 0, 0, "", {}, [], base_dir, source_file, images,
    )  # fmt: skip


def _json_collection(d: dict[str, Any], base_dir: str, source_file: str) -> _Tileset | None:
    """``_xml_collection`` of a JSON tile set."""
    images = {
        int(t.get("id", -1)): str(t["image"])
        for t in d.get("tiles", [])
        if isinstance(t, dict) and t.get("image")
    }
    if not images:
        return None
    return _Tileset(
        str(d.get("name", "tileset")), int(d.get("tilewidth", 0)), int(d.get("tileheight", 0)),
        0, 0, 0, "", {}, [], base_dir, source_file, images,
    )  # fmt: skip


def _json_tileset(
    d: dict[str, Any], base_dir: str, source_file: str, collections: bool = False
) -> _Tileset | None:
    """A tile set of a sheet; with ``collections``, a collection of images too (T17.28)."""
    if not d.get("image"):
        return _json_collection(d, base_dir, source_file) if collections else None
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


# --------------------------------------------------------------------------- maps (T12.49)

GID_MASK = 0x1FFFFFFF
GID_FLIP_H = 0x80000000
GID_FLIP_V = 0x40000000
GID_FLIP_D = 0x20000000


class _Unsupported(Exception):
    """Tile data this reader cannot use; the message becomes the reason of TILE-009."""


@dataclass
class _Ref:
    firstgid: int
    tileset: _Tileset | None


@dataclass
class _Layer:
    name: str
    kind: str  # "tiles" | "objects"
    cells: dict[tuple[int, int], int] = field(default_factory=dict)
    objects: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    # how far Tiled draws the layer from its place, in px (its own and its groups' offsets);
    # only an isometric map keeps it (T17.28: a second floor is drawn higher)
    offset: tuple[float, float] = (0.0, 0.0)


@dataclass
class _TiledMap:
    tile_w: int
    tile_h: int
    width: int
    height: int
    infinite: bool
    orientation: str
    refs: list[_Ref] = field(default_factory=list)
    layers: list[_Layer] = field(default_factory=list)


def _inflate(raw: bytes, wbits: int) -> bytes:
    inflater = zlib.decompressobj(wbits)
    out = inflater.decompress(raw, MAX_TILE_BYTES + 1)
    if len(out) > MAX_TILE_BYTES:
        raise _Unsupported("the tile data is too large")
    return out


def _zstd_module() -> tuple[str, Any] | None:
    """The Zstandard reader that can be imported: the ``zstandard`` package (the ``maps`` extra,
    always in the packages), else the reader py7zr brings along. None in a checkout with neither."""
    for name in ("zstandard", "compression.zstd", "backports.zstd"):
        try:
            return name, importlib.import_module(name)
        except ImportError:
            continue
    return None


def _unzstd(raw: bytes) -> bytes:
    found = _zstd_module()
    if found is None:
        raise _Unsupported("it is compressed with Zstandard: install the zstandard package")
    name, module = found
    try:
        if name == "zstandard":
            with module.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as reader:
                out = bytes(reader.read(MAX_TILE_BYTES + 1))
        else:
            out = bytes(module.ZstdDecompressor().decompress(raw, MAX_TILE_BYTES + 1))
    except (module.ZstdError, EOFError) as exc:
        raise _Unsupported("the tile data is damaged") from exc
    if len(out) > MAX_TILE_BYTES:
        raise _Unsupported("the tile data is too large")
    return out


def _decode(data: Any, encoding: str | None, compression: str | None) -> list[int]:
    """The global tile ids of one ``data`` element (CSV, a JSON list, or base64 with zlib, gzip
    or Zstandard). Anything else raises ``_Unsupported``."""
    if isinstance(data, list):
        return [int(v) for v in data]
    text = str(data or "").strip()
    if encoding in (None, "", "csv"):
        try:
            return [int(v) for v in text.split(",") if v.strip() != ""]
        except ValueError as exc:
            raise _Unsupported("the tile data is damaged") from exc
    if encoding != "base64":
        raise _Unsupported(f"{encoding} encoding is not supported")
    try:
        raw = base64.b64decode(text, validate=False)
        if compression == "zlib":
            raw = _inflate(raw, zlib.MAX_WBITS)
        elif compression == "gzip":
            raw = _inflate(raw, 16 + zlib.MAX_WBITS)
        elif compression == "zstd":
            raw = _unzstd(raw)
        elif compression:
            raise _Unsupported(f"it uses an unsupported compression ({compression})")
    except (binascii.Error, zlib.error, ValueError) as exc:
        raise _Unsupported("the tile data is damaged") from exc
    if len(raw) % 4:
        raise _Unsupported("the tile data is damaged")
    return list(struct.unpack(f"<{len(raw) // 4}I", raw))


def _place(layer: _Layer, values: list[int], x0: int, y0: int, width: int) -> None:
    if width <= 0 or len(values) % width:
        raise _Unsupported("the tile data does not fit the layer")
    for i, gid in enumerate(values):
        if gid & GID_MASK:
            layer.cells[(x0 + i % width, y0 + i // width)] = gid


def _properties_xml(el: ET.Element) -> dict[str, Any]:
    return {
        p.get("name", ""): _prop_value(p.get("type"), p.get("value", p.text or ""))
        for p in el.findall("./properties/property")
    }


def _properties_json(items: Any) -> dict[str, Any]:
    return {
        str(p.get("name", "")): _prop_value(p.get("type"), p.get("value"))
        for p in items or []
        if isinstance(p, dict)
    }


def _object(
    name: str, kind: str, x: Any, y: Any, w: Any, h: Any, props: dict[str, Any]
) -> dict[str, Any]:
    return {
        "name": name,
        "type": kind,
        "x": _num(x or 0),
        "y": _num(y or 0),
        "w": _num(w or 0),
        "h": _num(h or 0),
        "props": props,
    }


def _xml_offset(el: ET.Element, at: tuple[float, float]) -> tuple[float, float]:
    try:
        return at[0] + float(el.get("offsetx", 0)), at[1] + float(el.get("offsety", 0))
    except ValueError:
        return at


def _json_offset(item: dict[str, Any], at: tuple[float, float]) -> tuple[float, float]:
    try:
        return at[0] + float(item.get("offsetx", 0)), at[1] + float(item.get("offsety", 0))
    except (TypeError, ValueError):
        return at


def _xml_layers(
    parent: ET.Element, out: list[_Layer], at: tuple[float, float] = (0.0, 0.0)
) -> None:
    for el in parent:
        if el.tag == "group":
            _xml_layers(el, out, _xml_offset(el, at))
        elif el.tag == "layer":
            layer = _Layer(el.get("name", "layer"), "tiles", offset=_xml_offset(el, at))
            data = el.find("data")
            try:
                if data is not None:
                    enc, comp = data.get("encoding"), data.get("compression")
                    chunks = data.findall("chunk")
                    if chunks:
                        for ch in chunks:
                            _place(
                                layer,
                                _decode(ch.text, enc, comp),
                                int(ch.get("x", 0)),
                                int(ch.get("y", 0)),
                                int(ch.get("width", 0)),
                            )
                    elif enc is None and data.findall("tile"):
                        values = [int(t.get("gid", 0)) for t in data.findall("tile")]
                        _place(layer, values, 0, 0, int(el.get("width", 0)))
                    else:
                        width = int(el.get("width", 0))
                        values = _decode(data.text, enc, comp)
                        if len(values) != width * int(el.get("height", 0)):
                            raise _Unsupported("the tile data does not fit the layer")
                        _place(layer, values, 0, 0, width)
            except _Unsupported as exc:
                layer.error = str(exc)
            out.append(layer)
        elif el.tag == "objectgroup":
            layer = _Layer(el.get("name", "objects"), "objects")
            for o in el.findall("object"):
                kind = o.get("type") or o.get("class") or ""
                layer.objects.append(
                    _object(
                        o.get("name", ""),
                        kind,
                        o.get("x"),
                        o.get("y"),
                        o.get("width"),
                        o.get("height"),
                        _properties_xml(o),
                    )  # fmt: skip
                )
            out.append(layer)


def _json_layers(items: Any, out: list[_Layer], at: tuple[float, float] = (0.0, 0.0)) -> None:
    for item in items or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "group":
            _json_layers(item.get("layers"), out, _json_offset(item, at))
        elif kind == "tilelayer":
            layer = _Layer(str(item.get("name", "layer")), "tiles", offset=_json_offset(item, at))
            enc, comp = item.get("encoding"), item.get("compression")
            try:
                if item.get("chunks"):
                    for ch in item["chunks"]:
                        _place(
                            layer,
                            _decode(ch.get("data"), enc, comp),
                            int(ch.get("x", 0)),
                            int(ch.get("y", 0)),
                            int(ch.get("width", 0)),
                        )
                else:
                    width = int(item.get("width", 0))
                    values = _decode(item.get("data"), enc, comp)
                    if len(values) != width * int(item.get("height", 0)):
                        raise _Unsupported("the tile data does not fit the layer")
                    _place(layer, values, 0, 0, width)
            except _Unsupported as exc:
                layer.error = str(exc)
            out.append(layer)
        elif kind == "objectgroup":
            layer = _Layer(str(item.get("name", "objects")), "objects")
            for o in item.get("objects", []):
                layer.objects.append(
                    _object(
                        str(o.get("name", "")),
                        str(o.get("type") or o.get("class") or ""),
                        o.get("x"),
                        o.get("y"),
                        o.get("width"),
                        o.get("height"),
                        _properties_json(o.get("properties")),
                    )  # fmt: skip
                )
            out.append(layer)


def _external_tileset(
    map_dir: str, source: str, root: Path, by_lower: dict[str, str], collections: bool = False
) -> _Tileset | None:
    joined = posixpath.normpath(posixpath.join(map_dir, source.replace("\\", "/")))
    path = by_lower.get(joined.casefold())
    if path is None:
        return None
    text = _read_limited(root / path)
    if text is None:
        return None
    base = posixpath.dirname(path)
    if path.casefold().endswith(".tsx"):
        return _xml_tileset(ET.fromstring(text), base, path, collections)  # noqa: S314
    return _json_tileset(json.loads(text), base, path, collections)


def _read_tiled_map(
    ext: str, text: str, rel: str, root: Path, by_lower: dict[str, str]
) -> _TiledMap:
    base = posixpath.dirname(rel)
    if ext == ".tmx":
        el = ET.fromstring(text)  # noqa: S314
        tm = _TiledMap(
            int(el.get("tilewidth", 0)), int(el.get("tileheight", 0)),
            int(el.get("width", 0)), int(el.get("height", 0)),
            el.get("infinite", "0") == "1", el.get("orientation", "orthogonal"),
        )  # fmt: skip
        # the tiles of an isometric map are pictures of their own (T17.28)
        iso = tm.orientation == ISOMETRIC
        for t in el.findall("tileset"):
            src = t.get("source")
            ts = (
                _external_tileset(base, src, root, by_lower, iso)
                if src
                else _xml_tileset(t, base, rel, iso)
            )
            tm.refs.append(_Ref(int(t.get("firstgid", 1)), ts))
        _xml_layers(el, tm.layers)
    else:
        d = json.loads(text)
        tm = _TiledMap(
            int(d.get("tilewidth", 0)), int(d.get("tileheight", 0)),
            int(d.get("width", 0)), int(d.get("height", 0)),
            bool(d.get("infinite", False)), str(d.get("orientation", "orthogonal")),
        )  # fmt: skip
        iso = tm.orientation == ISOMETRIC
        for t in d.get("tilesets", []):
            if not isinstance(t, dict):
                continue
            src = t.get("source")
            ts = (
                _external_tileset(base, src, root, by_lower, iso)
                if src
                else _json_tileset(t, base, rel, iso)
            )
            tm.refs.append(_Ref(int(t.get("firstgid", 1)), ts))
        _json_layers(d.get("layers"), tm.layers)
    tm.refs.sort(key=lambda r: r.firstgid)
    return tm


def _raw_map(
    tm: _TiledMap, rel: str, by_lower: dict[str, str], issues: IssueList
) -> dict[str, Any] | None:
    """The raw map (adapters.maps) of one Tiled map; None when nothing in it can be imported."""
    stem = posixpath.splitext(posixpath.basename(rel))[0]
    iso = tm.orientation == ISOMETRIC
    if (tm.orientation != "orthogonal" and not iso) or tm.tile_w <= 0 or tm.tile_h <= 0:
        reason = REFUSED_ORIENTATIONS.get(
            tm.orientation, "only orthogonal and isometric maps are imported"
        )
        issues.add(
            "TILE-009", file=rel, layer="(all layers)", map=rel, reason=reason,
        )  # fmt: skip
        return None
    if tm.infinite:  # flattened to the bounds of the tiles
        keys = [k for ly in tm.layers if not ly.error for k in ly.cells]
        if keys:
            ox, oy = min(k[0] for k in keys), min(k[1] for k in keys)
            width = max(k[0] for k in keys) - ox + 1
            height = max(k[1] for k in keys) - oy + 1
        else:
            ox = oy = 0
            width = height = 1
    else:
        ox = oy = 0
        width, height = tm.width, tm.height
    if width <= 0 or height <= 0 or width * height > maps_mod.MAX_CELLS:
        issues.add(
            "TILE-009", file=rel, layer="(all layers)", map=rel,
            reason="the map is empty or larger than 4,000,000 cells",
        )  # fmt: skip
        return None

    images: dict[int, str | None] = {}

    def image_of(ref: _Ref) -> str | None:
        if id(ref) not in images:
            ts = ref.tileset
            found = _resolve_image(ts) if ts and ts.columns > 0 else None
            images[id(ref)] = by_lower.get(found.casefold()) if found else None
        return images[id(ref)]

    def picture_of(ts: _Tileset, tid: int) -> str | None:
        """The pack path of the picture of tile ``tid`` of a collection of images."""
        source = ts.images.get(tid)
        if not source:
            return None
        joined = posixpath.normpath(posixpath.join(ts.base_dir, source.replace("\\", "/")))
        if joined.startswith("..") or joined.startswith("/"):
            return None
        return by_lower.get(joined.casefold())

    # Objects of an isometric map are placed in a space whose two axes are the map's rows and
    # columns, each counted in the height of a diamond (Tiled's isometric object coordinates).
    step_x, step_y = (tm.tile_h, tm.tile_h) if iso else (tm.tile_w, tm.tile_h)
    layers: list[dict[str, Any]] = []
    pictures: set[str] = set()  # of an isometric map's collections of images
    for layer in tm.layers:
        if layer.kind == "tiles":
            if layer.error:
                issues.add("TILE-009", file=rel, layer=layer.name, map=rel, reason=layer.error)
                continue
            tiles: list[list[Any]] = []
            lost = 0
            for (x, y), raw in sorted(layer.cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
                gid = raw & GID_MASK
                ref = next((r for r in reversed(tm.refs) if r.firstgid <= gid), None)
                tid = gid - ref.firstgid if ref else 0
                collection = (
                    iso and ref is not None and ref.tileset is not None and ref.tileset.images
                )
                if collection and ref is not None and ref.tileset is not None:
                    # one picture a tile: the picture is the tile (its column and row are 0)
                    image = picture_of(ref.tileset, tid)
                    if image is not None:
                        pictures.add(image)
                else:
                    image = image_of(ref) if ref else None
                if ref is None or ref.tileset is None or image is None:
                    lost += 1
                    continue
                alt = (
                    (maps_mod.FLIP_H if raw & GID_FLIP_H else 0)
                    | (maps_mod.FLIP_V if raw & GID_FLIP_V else 0)
                    | (maps_mod.FLIP_D if raw & GID_FLIP_D else 0)
                )
                if collection:
                    tiles.append([x - ox, y - oy, image, 0, 0, alt])
                    continue
                columns = ref.tileset.columns
                tiles.append([x - ox, y - oy, image, tid % columns, tid // columns, alt])
            if not tiles and lost:
                issues.add(
                    "TILE-009", file=rel, layer=layer.name, map=rel,
                    reason="its tile sheet was not found in the pack",
                )  # fmt: skip
            if tiles:
                found = maps_mod.tile_layer(layer.name, tiles)
                if iso and layer.offset != (0.0, 0.0):
                    found["offset"] = [_num(layer.offset[0]), _num(layer.offset[1])]
                layers.append(found)
        else:
            objects = []
            for o in layer.objects:
                kind = maps_mod.marker_kind(layer.name, o["type"])
                if kind is None:
                    continue
                marker = dict(o, type=kind)
                marker["x"] = _num(o["x"] - ox * step_x)
                marker["y"] = _num(o["y"] - oy * step_y)
                objects.append(marker)
            if objects:
                layers.append(maps_mod.objects_layer(layer.name, objects))
    if not layers:
        return None
    out: dict[str, Any] = {
        "name": stem,
        "source": rel,
        "format": "tiled",
        "tile_size": [tm.tile_w, tm.tile_h],
        "size": [width, height],
        "layers": layers,
    }
    if iso:  # a map of squares says nothing of its view, as before (T17.28)
        out["projection"] = ISOMETRIC
        out["pictures"] = sorted(pictures)
    return out


_ORIENTATION_XML = re.compile(r"<map\b[^>]*\borientation\s*=\s*\"isometric\"", re.IGNORECASE)
_ORIENTATION_JSON = re.compile(r"\"orientation\"\s*:\s*\"isometric\"")
MAP_HEAD_BYTES = 64 * 1024


def _says_isometric(root: Path, rel: str, ext: str) -> bool:
    """True for a Tiled map whose head says it is isometric."""
    if ext not in (".tmx", ".tmj"):
        return False
    try:
        with open(root / rel, "rb") as fh:
            head = fh.read(MAP_HEAD_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return False
    found = _ORIENTATION_XML if ext == ".tmx" else _ORIENTATION_JSON
    return found.search(head) is not None


def map_pictures(results: list[AdapterResult]) -> set[str]:
    """The pack paths of the pictures that the isometric Tiled maps among ``results`` paint
    with (T17.28): pictures, wherever they lie, that the isometric reader must measure."""
    found: set[str] = set()
    for res in results:
        for raw in res.maps:
            if raw.get("projection") != ISOMETRIC:
                continue
            found.update(str(p) for p in raw.get("pictures", []))
    return found


class TiledAdapter:
    name = "tiled"
    priority = 10

    def match(self, inv: Inventory, root: Path) -> float:
        tilesets, standalone = _collect(inv, root, IssueList())
        if standalone:
            return 1.0
        if tilesets:
            return 0.6
        # an isometric map whose tile set is a collection of images in the map itself (T17.28)
        return 0.6 if any(_says_isometric(root, f.path, f.ext) for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        tilesets, _ = _collect(inv, root, issues)
        by_lower = {f.path.casefold(): f.path for f in inv.files}
        ignored: set[str] = set()
        hulled = False
        # the isometric sheets cut by the cell their tile sets state (T17.30) are no tile sets
        # of squares
        cut = {f.path for r in ctx.results if r.adapter == "iso_sheets" for f in r.assets}
        for ts in tilesets:
            image = _resolve_image(ts)
            image = by_lower.get(image.casefold()) if image else None
            if image is None:
                issues.add("ADAPT-002", file=ts.source_file, image=ts.image)
                continue
            if image in cut:
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
        for f in inv.files:
            if f.ext not in (".tmx", ".tmj"):
                continue
            try:
                text = _read_limited(root / f.path)
                if text is None:
                    continue
                parsed = _read_tiled_map(f.ext, text, f.path, root, by_lower)
                raw = _raw_map(parsed, f.path, by_lower, issues)
            except (ET.ParseError, json.JSONDecodeError, ValueError, KeyError, OSError) as exc:
                if not any(i.code == "ADAPT-001" and i.file == f.path for i in issues):
                    issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=str(exc))
                continue
            if raw is not None:
                result.maps.append(raw)
        if hulled:
            result.pack_warnings.append("tiled_multi_object_collision_hulled")
        if ignored:
            result.pack_warnings.append("tiled_ignored_properties:" + ",".join(sorted(ignored)))
        result.issues = list(issues)
        return result

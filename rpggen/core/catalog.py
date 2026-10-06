from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen import __version__, ids, jsonio, schema
from rpggen.core.config import folder_sha256
from rpggen.errors import RpgGenError

CATALOG_VERSION = 2


def _sort_key(s: str) -> tuple[str, str]:
    return (s.casefold(), s)


# --------------------------------------------------------------------------- effective facets


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Deep merge of ``over`` onto ``base``.

    A ``None`` value in ``over`` deletes the key. Dictionaries merge recursively; every other
    value (including lists) replaces. Mirrors ``catalog_reader.gd: merge``.
    """
    result = copy.deepcopy(base)
    for key, value in over.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            existing = result.get(key)
            result[key] = merge(existing if isinstance(existing, dict) else {}, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def effective(asset: dict[str, Any] | Asset) -> dict[str, Any]:
    """Effective facets of an asset: ``detected`` merged with ``overrides``."""
    if isinstance(asset, Asset):
        return merge(asset.detected, asset.overrides)
    return merge(asset.get("detected", {}), asset.get("overrides", {}))


# --------------------------------------------------------------------------- data classes


@dataclass(slots=True)
class CatalogPack:
    pack_id: str
    source_sha256: str
    root: str
    license_files: list[str] = field(default_factory=list)
    adapters_matched: list[str] = field(default_factory=list)
    profile_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "source_sha256": self.source_sha256,
            "root": self.root,
            "license_files": list(self.license_files),
            "adapters_matched": list(self.adapters_matched),
            "profile_id": self.profile_id,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> CatalogPack:
        return cls(
            d["pack_id"],
            d["source_sha256"],
            d["root"],
            list(d["license_files"]),
            list(d["adapters_matched"]),
            d["profile_id"],
            list(d["warnings"]),
        )


@dataclass(slots=True)
class Asset:
    id: str
    pack_id: str
    path: str
    sha256: str
    kind: str
    status: str
    detected: dict[str, Any]
    overrides: dict[str, Any] = field(default_factory=dict)
    detected_by: str = ""
    confidence: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pack_id": self.pack_id,
            "path": self.path,
            "sha256": self.sha256,
            "kind": self.kind,
            "status": self.status,
            "detected": copy.deepcopy(self.detected),
            "overrides": copy.deepcopy(self.overrides),
            "detected_by": self.detected_by,
            "confidence": self.confidence,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Asset:
        return cls(
            d["id"],
            d["pack_id"],
            d["path"],
            d["sha256"],
            d["kind"],
            d["status"],
            copy.deepcopy(d["detected"]),
            copy.deepcopy(d["overrides"]),
            d["detected_by"],
            d["confidence"],
        )


@dataclass(slots=True)
class SheetObject:
    id: str
    sheet: str
    name: str
    role: str
    region: list[int]
    origin: list[int]
    footprint: list[int]
    collision: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    status: str = "AUTO_DETECTED"
    source: str = "auto"
    door: list[int] | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "sheet": self.sheet,
            "name": self.name,
            "role": self.role,
            "region": list(self.region),
            "origin": list(self.origin),
            "footprint": list(self.footprint),
            "collision": copy.deepcopy(self.collision),
            "tags": list(self.tags),
            "status": self.status,
            "source": self.source,
        }
        if self.door is not None:
            out["door"] = list(self.door)
        return out

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> SheetObject:
        return cls(
            d["id"],
            d["sheet"],
            d["name"],
            d["role"],
            list(d["region"]),
            list(d["origin"]),
            list(d["footprint"]),
            copy.deepcopy(d["collision"]),
            list(d["tags"]),
            d["status"],
            d["source"],
            list(d["door"]) if "door" in d else None,
        )


@dataclass(slots=True)
class TileSetDef:
    name: str
    tile_size: list[int]
    sources: list[dict[str, Any]] = field(default_factory=list)  # {"asset": id, "source_id": n}
    terrain_sets: list[dict[str, Any]] = field(default_factory=list)
    physics_layers: list[dict[str, Any]] = field(default_factory=list)
    custom_data: list[dict[str, Any]] = field(default_factory=list)
    navigation: bool = False
    patterns_from_objects: bool = True

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tile_size": list(self.tile_size),
            "sources": [dict(s) for s in sorted(self.sources, key=lambda s: s["source_id"])],
            "terrain_sets": copy.deepcopy(self.terrain_sets),
            "physics_layers": copy.deepcopy(self.physics_layers),
            "custom_data": copy.deepcopy(self.custom_data),
            "navigation": self.navigation,
            "patterns_from_objects": self.patterns_from_objects,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> TileSetDef:
        return cls(
            d["name"],
            list(d["tile_size"]),
            [dict(s) for s in d["sources"]],
            copy.deepcopy(d.get("terrain_sets", [])),
            copy.deepcopy(d["physics_layers"]),
            copy.deepcopy(d["custom_data"]),
            d.get("navigation", False),
            d.get("patterns_from_objects", True),
        )


@dataclass(slots=True)
class FolderRule:
    pack_id: str
    glob: str
    set: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"pack_id": self.pack_id, "glob": self.glob, "set": copy.deepcopy(self.set)}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> FolderRule:
        return cls(d["pack_id"], d["glob"], copy.deepcopy(d["set"]))


@dataclass(slots=True)
class Catalog:
    packs: list[CatalogPack] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    objects: list[SheetObject] = field(default_factory=list)
    tilesets: list[TileSetDef] = field(default_factory=list)
    id_allocations: dict[str, Any] = field(default_factory=lambda: {"tilesets": {}, "entities": {}})
    folder_rules: list[FolderRule] = field(default_factory=list)
    generator_version: str = __version__
    catalog_version: int = CATALOG_VERSION

    def allocate_source_id(self, tileset: str) -> int:
        """Return the next never-reused source id of ``tileset`` and advance the counter."""
        entry = self.id_allocations["tilesets"].setdefault(
            tileset, {"next_source_id": 0, "retired": []}
        )
        value = entry["next_source_id"]
        entry["next_source_id"] = value + 1
        return value

    def asset(self, asset_id: str) -> Asset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def to_json(self) -> dict[str, Any]:
        return {
            "catalog_version": self.catalog_version,
            "generator_version": self.generator_version,
            "packs": [p.to_json() for p in sorted(self.packs, key=lambda p: _sort_key(p.pack_id))],
            "assets": [a.to_json() for a in sorted(self.assets, key=lambda a: _sort_key(a.id))],
            "objects": [o.to_json() for o in sorted(self.objects, key=lambda o: _sort_key(o.id))],
            "tilesets": [
                t.to_json() for t in sorted(self.tilesets, key=lambda t: _sort_key(t.name))
            ],
            "id_allocations": copy.deepcopy(self.id_allocations),
            "folder_rules": [r.to_json() for r in self.folder_rules],
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Catalog:
        return cls(
            packs=[CatalogPack.from_json(p) for p in d["packs"]],
            assets=[Asset.from_json(a) for a in d["assets"]],
            objects=[SheetObject.from_json(o) for o in d["objects"]],
            tilesets=[TileSetDef.from_json(t) for t in d["tilesets"]],
            id_allocations=copy.deepcopy(d["id_allocations"]),
            folder_rules=[FolderRule.from_json(r) for r in d["folder_rules"]],
            generator_version=d["generator_version"],
            catalog_version=d["catalog_version"],
        )


def load(path: Path) -> Catalog:
    data = jsonio.read(path)
    version = data.get("catalog_version") if isinstance(data, dict) else None
    if isinstance(version, int) and version > CATALOG_VERSION:
        raise RpgGenError("CAT-003", found=version, file=str(path))
    schema.validate("catalog", data)
    return Catalog.from_json(data)


def save(catalog: Catalog, path: Path) -> None:
    data = catalog.to_json()
    schema.validate("catalog", data)
    jsonio.write(path, data)


# --------------------------------------------------------------------------- M1 temporary builder

_DIRECTIONS = ("down", "left", "right", "up")  # sheet rows 0..3


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_minimal_catalog(
    pack_dir: Path, pack_id: str, project_rel_root: str, tile_size: int
) -> Catalog:
    """TEMPORARY (M1). Replaced by analysis pipeline in T2.14.

    Assumes the synthetic ``basic16`` layout: PNGs under ``tiles/`` are ground tile sheets and PNGs
    under ``characters/`` are 16x24 player sheets (4 columns x 4 direction rows).
    """
    pack_dir = Path(pack_dir)
    cat = Catalog()
    license_files = sorted(
        (
            f"{project_rel_root}/{p.name}"
            for p in pack_dir.iterdir()
            if p.name.upper().startswith("LICENSE")
        ),
        key=_sort_key,
    )
    cat.packs.append(CatalogPack(pack_id, folder_sha256(pack_dir), project_rel_root, license_files))
    tileset = TileSetDef(
        name="overworld",
        tile_size=[tile_size, tile_size],
        physics_layers=[{"name": "world", "layer_bits": 1, "mask_bits": 0}],
        custom_data=[
            {"name": "asset_id", "type": "string"},
            {"name": "footstep", "type": "string"},
            {"name": "move_cost", "type": "float"},
        ],
    )
    cat.tilesets.append(tileset)

    def pngs(sub: str) -> list[Path]:
        folder = pack_dir / sub
        if not folder.is_dir():
            return []
        return sorted(
            (p for p in folder.rglob("*.png")),
            key=lambda p: _sort_key(p.relative_to(pack_dir).as_posix()),
        )

    for png in pngs("tiles"):
        rel = png.relative_to(pack_dir).as_posix()
        asset_id = ids.asset_id(pack_id, rel)
        with Image.open(png) as im:
            cols = im.width // tile_size
        detected: dict[str, Any] = {
            "role": "GROUND",
            "usage": "tiles",
            "grid": {"cell": [tile_size, tile_size], "margin": [0, 0], "separation": [0, 0]},
            "tileset": tileset.name,
            "collision": {"profile": "NONE"},
        }
        if png.name == "terrain.png":
            # Hard-coded for basic16: row 1 holds the wall tiles.
            detected["tile_overrides"] = {
                f"{x},1": {"collision": {"profile": "FULL"}, "custom": {"role": "WALL"}}
                for x in range(cols)
            }
        cat.assets.append(
            Asset(
                id=asset_id,
                pack_id=pack_id,
                path=f"{project_rel_root}/{rel}",
                sha256=_file_sha256(png),
                kind="image",
                status="AUTO_DETECTED",
                detected=detected,
                detected_by="m1_minimal",
                confidence=0.9,
            )
        )
        tileset.sources.append(
            {"asset": asset_id, "source_id": cat.allocate_source_id(tileset.name)}
        )

    for png in pngs("characters"):
        rel = png.relative_to(pack_dir).as_posix()
        animations: dict[str, Any] = {}
        for row, direction in enumerate(_DIRECTIONS):
            animations[f"walk_{direction}"] = {
                "frames": [[col, row] for col in range(4)],
                "fps": 8.0,
                "loop": True,
            }
            animations[f"idle_{direction}"] = {"frames": [[0, row]], "fps": 1.0, "loop": True}
        cat.assets.append(
            Asset(
                id=ids.asset_id(pack_id, rel),
                pack_id=pack_id,
                path=f"{project_rel_root}/{rel}",
                sha256=_file_sha256(png),
                kind="image",
                status="AUTO_DETECTED",
                detected={
                    "role": "PLAYER",
                    "usage": "sprite",
                    "grid": {"cell": [16, 24], "margin": [0, 0], "separation": [0, 0]},
                    "frame": [16, 24],
                    "origin": [8, 23],
                    "directions": 4,
                    "animations": animations,
                },
                detected_by="m1_minimal",
                confidence=0.9,
            )
        )
    return cat

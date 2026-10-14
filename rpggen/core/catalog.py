from __future__ import annotations

import copy
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, ids, jsonio, schema
from rpggen.core import licenses
from rpggen.core.adapters.base import AssetFragment
from rpggen.core.archive import Cancelled, OpenedPack, Progress
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList, RpgGenError

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
    """Effective facets of an asset: ``detected`` <- ``rule`` <- ``overrides``."""
    if isinstance(asset, Asset):
        detected, rule, overrides = asset.detected, asset.rule, asset.overrides
    else:
        detected = asset.get("detected", {})
        rule = asset.get("rule", {})
        overrides = asset.get("overrides", {})
    return merge(merge(detected, rule), overrides)


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
    # what the licence files say (licenses.PackLicense as JSON) and the Audit page's corrections
    license: dict[str, Any] = field(default_factory=lambda: licenses.PackLicense().to_json())
    license_overrides: dict[str, Any] = field(default_factory=dict)

    def effective_license(self) -> licenses.PackLicense:
        return licenses.effective(self.license, self.license_overrides)

    def to_json(self) -> dict[str, Any]:
        out = {
            "pack_id": self.pack_id,
            "source_sha256": self.source_sha256,
            "root": self.root,
            "license_files": list(self.license_files),
            "adapters_matched": list(self.adapters_matched),
            "profile_id": self.profile_id,
            "warnings": list(self.warnings),
            "license": licenses.PackLicense.from_json(self.license).to_json(),
        }
        if self.license_overrides:
            out["license_overrides"] = dict(sorted(self.license_overrides.items()))
        return out

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
            licenses.PackLicense.from_json(d.get("license")).to_json(),
            dict(d.get("license_overrides", {})),
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
    rule: dict[str, Any] = field(default_factory=dict)  # facets written by folder rules
    renamed_from: str | None = None  # path the vendor's earlier release used (T5.05)

    def to_json(self) -> dict[str, Any]:
        out = {
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
        if self.rule:
            out["rule"] = copy.deepcopy(self.rule)
        if self.renamed_from:
            out["renamed_from"] = self.renamed_from
        return out

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
            copy.deepcopy(d.get("rule", {})),
            d.get("renamed_from"),
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
    # T17.13: "isometric" for the tile set of an isometric project (its sources are the atlases
    # ``iso_atlas.py`` packs the single tiles into, its ``tile_size`` the diamond); "" for
    # every other, whose JSON has neither key
    projection: str = ""
    # ... and where every tile of it is: asset id -> {"source", "coords": [column, row],
    # "at": [x, y]} (the atlas source, the atlas cell, and where in the cell its picture lies)
    tiles: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "tile_size": list(self.tile_size),
            "sources": [dict(s) for s in sorted(self.sources, key=lambda s: s["source_id"])],
            "terrain_sets": copy.deepcopy(self.terrain_sets),
            "physics_layers": copy.deepcopy(self.physics_layers),
            "custom_data": copy.deepcopy(self.custom_data),
            "navigation": self.navigation,
            "patterns_from_objects": self.patterns_from_objects,
        }
        if self.projection:
            out["projection"] = self.projection
            out["tiles"] = {
                key: copy.deepcopy(self.tiles[key]) for key in sorted(self.tiles, key=_sort_key)
            }
        return out

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
            d.get("projection", ""),
            copy.deepcopy(d.get("tiles", {})),
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
    # Maps read from Tiled and LDtk files (T12.49); see ``resolve_maps`` for the shape.
    maps: list[dict[str, Any]] = field(default_factory=list)
    # Recolour variants (T13.18): [{id, source, name, op, params, stats?}]; see ``variants``.
    variants: list[dict[str, Any]] = field(default_factory=list)
    # LPC characters put together from a body and layers (M16): [{id, name, body, layers,
    # auto?}]; see ``lpc_compose``.
    characters: list[dict[str, Any]] = field(default_factory=list)
    # The size a pack drawn in several sizes is used in (T17.29): {pack id: px}; see
    # ``pack_forms.choose_sizes``. Only the packs that have several sizes are listed.
    pack_sizes: dict[str, int] = field(default_factory=dict)

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
        out = self._to_json()
        if self.maps:  # optional: a catalog without maps is unchanged
            out["maps"] = [
                copy.deepcopy(m) for m in sorted(self.maps, key=lambda m: _sort_key(m["id"]))
            ]
        if self.variants:  # optional too
            out["variants"] = copy.deepcopy(self.variants)
        if self.characters:
            out["characters"] = copy.deepcopy(self.characters)
        if self.pack_sizes:  # optional: a catalog of packs of one size each is unchanged
            out["pack_sizes"] = {k: int(v) for k, v in sorted(self.pack_sizes.items())}
        return out

    def _to_json(self) -> dict[str, Any]:
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
            maps=copy.deepcopy(d.get("maps", [])),
            variants=copy.deepcopy(d.get("variants", [])),
            characters=copy.deepcopy(d.get("characters", [])),
            pack_sizes={str(k): int(v) for k, v in (d.get("pack_sizes") or {}).items()},
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


# --------------------------------------------------------------------------- status

CONFIRMED_CONFIDENCE = 0.999
AUTO_CONFIDENCE = 0.75


def recompute_status(
    asset: Asset, *, file_missing: bool = False, user_confirmed: bool = False
) -> str:
    """Status of an asset (02_SCHEMAS §4.3). CONFLICT stays until the user resolves it."""
    effective_facets = effective(asset)
    if file_missing:
        return "MISSING"
    if asset.status == "CONFLICT":
        return "CONFLICT"
    if effective_facets.get("role") == "NONE":
        return "UNUSED"
    if asset.overrides or asset.confidence >= CONFIRMED_CONFIDENCE or user_confirmed:
        return "CONFIRMED"
    if asset.confidence >= AUTO_CONFIDENCE:
        return "AUTO_DETECTED"
    return "NEEDS_REVIEW"


# --------------------------------------------------------------------------- folder rules


def _pack_relative(asset: Asset, packs: dict[str, CatalogPack]) -> str:
    root = packs[asset.pack_id].root if asset.pack_id in packs else ""
    prefix = root + "/"
    return asset.path[len(prefix) :] if asset.path.startswith(prefix) else asset.path


def apply_folder_rules(catalog: Catalog, extra_rules: list[FolderRule] | None = None) -> None:
    """Rebuild every asset's ``rule`` layer from the folder rules, in order.

    Rules are applied after detection and before overrides: effective = detected <- rule <-
    overrides. ``extra_rules`` (profile rules) are appended to the catalog's own rules once.
    """
    from rpggen import paths as paths_mod

    for rule in extra_rules or []:
        if not any(
            (r.pack_id, r.glob, r.set) == (rule.pack_id, rule.glob, rule.set)
            for r in catalog.folder_rules
        ):
            catalog.folder_rules.append(rule)
    packs = {p.pack_id: p for p in catalog.packs}
    for asset in catalog.assets:
        asset.rule = {}
    for rule in catalog.folder_rules:
        for asset in catalog.assets:
            if asset.pack_id != rule.pack_id:
                continue
            if paths_mod.glob_match(_pack_relative(asset, packs), rule.glob):
                asset.rule = merge(asset.rule, rule.set)


# --------------------------------------------------------------------------- tile sets

DEFAULT_PHYSICS_LAYERS = [{"name": "world", "layer_bits": 1, "mask_bits": 0}]
DEFAULT_CUSTOM_DATA = [
    {"name": "asset_id", "type": "string"},
    {"name": "footstep", "type": "string"},
    {"name": "move_cost", "type": "float"},
]
INTERIOR_TOKENS = {"interior", "inside"}


def _is_interior(asset: Asset) -> bool:
    from rpggen.core import classifier

    folders, file_tokens = classifier.tokens(asset.path)
    return effective(asset).get("role") == "INTERIOR" or bool(
        INTERIOR_TOKENS & (set(folders) | set(file_tokens))
    )


def _tile_cell(asset: Asset) -> int:
    grid = effective(asset).get("grid") or {}
    return int((grid.get("cell") or [0, 0])[0])


def _group_names(tile_assets: list[Asset]) -> dict[str, tuple[str, int]]:
    """asset id -> (tileset name, tile size) following the naming rules of T2.14."""
    explicit: dict[str, str] = {}
    computed: list[Asset] = []
    for a in tile_assets:
        hint = effective(a).get("tileset")
        if hint:
            explicit[a.id] = str(hint)
        else:
            computed.append(a)
    names: dict[str, tuple[str, int]] = {}
    for interior in (False, True):
        group = [a for a in computed if _is_interior(a) == interior]
        sizes: dict[int, int] = {}
        for a in group:
            sizes[_tile_cell(a)] = sizes.get(_tile_cell(a), 0) + 1
        if not sizes:
            continue
        common = max(sizes, key=lambda s: (sizes[s], s))
        base = "interior" if interior else "overworld"
        for a in group:
            size = _tile_cell(a)
            names[a.id] = (base if size == common else f"{base}_{size}", size)
    for a in tile_assets:
        if a.id in explicit:
            names[a.id] = (explicit[a.id], _tile_cell(a))
    # One name must describe one tile size: the most common size keeps the plain name.
    by_name: dict[str, dict[int, int]] = {}
    for name, size in names.values():
        by_name.setdefault(name, {}).setdefault(size, 0)
        by_name[name][size] += 1
    for aid, (name, size) in list(names.items()):
        sizes_for_name = by_name[name]
        if len(sizes_for_name) > 1:
            keeper = max(sizes_for_name, key=lambda s: (sizes_for_name[s], s))
            if size != keeper:
                names[aid] = (f"{name}_{size}", size)
    return names


NOT_A_HOUSE_WORDS = frozenset(
    {"bridge", "bridges", "fence", "fences", "tree", "trees", "rock", "rocks", "stone", "stones",
     "cliff", "cliffs", "water", "path", "paths", "bush", "bushes", "boat", "boats"}
)  # fmt: skip
HOUSE_WORDS = frozenset({"house", "houses", "home", "building", "buildings", "barn", "shop"})


def _another_form(asset: Asset) -> bool:
    """True for a sheet set aside as another form of the tiles the pack has (T17.29: the same
    tiles once more, or a size of the pack that is not used), while nobody gave it a role: it
    joins no tile set, so that no tile set is made in a size the project does not use."""
    from rpggen.core import classifier, pack_forms

    eff = effective(asset)
    if eff.get("role") != "NONE":
        return False
    if asset.pack_id == "generated" and "generated_terrain" in (eff.get("tags") or []):
        # the terrain drawn from a sheet set aside: a sheet of another engine (the source's
        # role was NONE when it was drawn, and a terrain of the packs has a role)
        return True
    reasons = {
        pack_forms.SAME_TILES,
        pack_forms.COMPILED_SHEET,
        pack_forms.OTHER_SIZE,
        pack_forms.CHARACTER_SHEET,
        pack_forms.ENGINE_COPY,
    }
    return any(
        str(t).startswith(classifier.UNUSED_TAG) and str(t)[len(classifier.UNUSED_TAG) :] in reasons
        for t in eff.get("tags") or []
    )


def assign_tilesets(
    catalog: Catalog,
    previous: Catalog | None,
    adapter_tilesets: list[dict[str, Any]] | None = None,
) -> None:
    """Group tile sheets into TileSetDefs and allocate source ids (never renumbered)."""
    # the tile set of an isometric project is ``iso_atlas.add``'s (T17.13): it is kept as it
    # is here, and no sheet of squares joins it
    isometric = [
        TileSetDef.from_json(t.to_json())
        for t in (previous.tilesets if previous else catalog.tilesets)
        if t.projection
    ]
    prev_defs = {t.name: t for t in previous.tilesets if not t.projection} if previous else {}
    # tile set definitions of a matched profile apply to tile sets the catalog has not seen yet
    profile_defs = {
        e["name"]: e for e in adapter_tilesets or [] if e.get("from_profile") and "name" in e
    }
    prev_source_of: dict[str, tuple[str, int]] = {}
    for tdef in prev_defs.values():
        for src in tdef.sources:
            prev_source_of[src["asset"]] = (tdef.name, int(src["source_id"]))
    if previous:
        catalog.id_allocations = copy.deepcopy(previous.id_allocations)

    tile_assets = [
        a
        for a in sorted(catalog.assets, key=lambda a: _sort_key(a.id))
        if effective(a).get("usage") == "tiles" and a.status != "MISSING" and not _another_form(a)
    ]
    missing_sources = {
        a.id for a in catalog.assets if a.status == "MISSING" and a.id in prev_source_of
    }
    names = _group_names(tile_assets)

    defs: dict[str, TileSetDef] = {}
    for aid, (name, size) in sorted(names.items()):
        if name not in defs:
            prev = prev_defs.get(name)
            if prev is None and name in profile_defs:
                prof = profile_defs[name]
                prev = TileSetDef(
                    name,
                    [size, size],
                    [],
                    copy.deepcopy(prof.get("terrain_sets", [])),
                    copy.deepcopy(prof["physics_layers"]),
                    copy.deepcopy(prof["custom_data"]),
                    prof.get("navigation", False),
                    prof.get("patterns_from_objects", True),
                )
            defs[name] = TileSetDef(
                name=name,
                tile_size=[size, size],
                physics_layers=copy.deepcopy(
                    prev.physics_layers if prev else DEFAULT_PHYSICS_LAYERS
                ),
                custom_data=copy.deepcopy(prev.custom_data if prev else DEFAULT_CUSTOM_DATA),
                terrain_sets=copy.deepcopy(prev.terrain_sets) if prev else [],
                navigation=prev.navigation if prev else False,
                patterns_from_objects=prev.patterns_from_objects if prev else True,
            )
        tdef = defs[name]
        prev_name, prev_id = prev_source_of.get(aid, (None, None))
        if prev_name == name and prev_id is not None:
            source_id = prev_id
        else:
            source_id = catalog.allocate_source_id(name)
            if prev_name is not None and prev_id is not None:
                retired = catalog.id_allocations["tilesets"].setdefault(
                    prev_name, {"next_source_id": prev_id + 1, "retired": []}
                )
                if prev_id not in retired["retired"]:
                    retired["retired"].append(prev_id)
        tdef.sources.append({"asset": aid, "source_id": source_id})
        asset = catalog.asset(aid)
        assert asset is not None
        asset.detected["tileset"] = name

    # Sources of assets whose files vanished stay in their tile set (REGEN-003 handles removal).
    for aid in sorted(missing_sources):
        name, source_id = prev_source_of[aid]
        if name in defs:
            defs[name].sources.append({"asset": aid, "source_id": source_id})
        elif name in prev_defs:
            old = prev_defs[name]
            defs[name] = TileSetDef(
                old.name,
                list(old.tile_size),
                [{"asset": aid, "source_id": source_id}],
                copy.deepcopy(old.terrain_sets),
                copy.deepcopy(old.physics_layers),
                copy.deepcopy(old.custom_data),
                old.navigation,
                old.patterns_from_objects,
            )

    # Terrain sets reported by adapters (Tiled wang sets) join the tile set of their image.
    path_to_name = {a.path.split("/", 3)[-1]: names[a.id][0] for a in tile_assets if a.id in names}
    for entry in adapter_tilesets or []:
        for src in entry.get("sources", []):
            src_path = src.get("path")
            set_name = path_to_name.get(src_path) if src_path else None
            if set_name and set_name in defs:
                existing = {t["name"] for t in defs[set_name].terrain_sets}
                for terrain in entry.get("terrain_sets", []):
                    if terrain["name"] not in existing:
                        defs[set_name].terrain_sets.append(copy.deepcopy(terrain))
                        existing.add(terrain["name"])
    for tdef in defs.values():
        tdef.sources.sort(key=lambda s: s["source_id"])
    for tdef in isometric:
        defs.setdefault(tdef.name, tdef)
    catalog.tilesets = [defs[n] for n in sorted(defs, key=_sort_key)]


# --------------------------------------------------------------------------- assembly


def _merge_fragments(
    fragments: list[tuple[int, AssetFragment]],
) -> tuple[dict[str, Any], float, int]:
    """Merge fragments for one asset: full claims first, then the user's learned values
    (T12.59), then confidence; first value wins."""
    ordered = sorted(
        fragments,
        key=lambda item: (
            item[1].claim != "full",
            not item[1].preferred,
            -item[1].confidence,
            item[0],
        ),
    )
    facets: dict[str, Any] = {}
    for _, frag in ordered:
        for key, value in frag.facets.items():
            facets.setdefault(key, copy.deepcopy(value))
    first = min(index for index, _ in fragments)
    confidence = max(f.confidence for _, f in fragments)
    for _, frag in fragments:
        # a learned value that was taken keeps the asset under review (confidence capped)
        if frag.preferred and any(facets.get(k) == v for k, v in frag.facets.items()):
            confidence = min(confidence, frag.confidence)
    return facets, confidence, first


def _learned_decided(fragments: list[tuple[int, AssetFragment]], facets: dict[str, Any]) -> bool:
    """True when a learned value decided the asset's role or usage (the audit says so)."""
    return any(
        frag.preferred
        and any(k in ("role", "usage") and facets.get(k) == v for k, v in frag.facets.items())
        for _, frag in fragments
    )


def _picture_hash(analyze: Callable[[str], dict[str, Any]], path: str) -> str | None:
    """The difference hash of a pack's image, from its (cached) analysis. A file that cannot be
    read has none: the adapter that needed it has reported that already."""
    try:
        value = analyze(path).get("dhash")
    except (OSError, ValueError):
        return None
    return value if isinstance(value, str) else None


def _suggest_tags(facets: dict[str, Any], path: str) -> None:
    """Add the tags the file name suggests ("light" for a torch, T12.62) to detected facets."""
    from rpggen.core import classifier

    suggested = classifier.suggested_tags(path)
    if facets.get("role") == "GROUND":  # what the player walks on (T13.16)
        surface = classifier.suggested_surface(path)
        if surface is not None:
            suggested = [*suggested, f"surface:{surface}"]
    side = classifier.side_view_tags(path)
    # an ability to find is the metroidvania's word for it: it is not also a power-up
    arcade = [t for t in classifier.arcade_tags(path) if not (t == "powerup" and "ability" in side)]
    # rain and snow are overlays over the whole screen (T17.01): a sheet of snow tiles is ground
    farm = [
        t
        for t in classifier.farm_tags(path)
        if not (t == "weather" and facets.get("usage") == "tiles")
    ]
    suggested = [*suggested, *side, *arcade, *farm]
    if suggested:
        facets["tags"] = sorted(set(facets.get("tags") or []) | set(suggested))


SIDE_TILE_TAGS = frozenset({"platform", "one_way", "ladder", "hazard"})
SIDE_TILE_COLLISION = {"one_way": "ONE_WAY", "ladder": "LADDER"}
TILE_FOLDER_WORDS = frozenset({"tile", "tiles", "tileset", "tilesets"})


def _side_view_usage(assets: list[Asset]) -> None:
    """What the side-view tags say about a picture the generic rules took for a single sprite
    (T14.02). A platformer's platforms, ladders and spikes are sheets with more holes than
    paint, and its parallax layers are small or have holes, so neither looks like a tile sheet
    or a background by its pixels.

    * A ``parallax:<n>`` picture with the role BACKGROUND becomes a ``background``, also when
      its texture looked like a grid of tiles.
    * A picture tagged ``platform``, ``one_way``, ``ladder`` or ``hazard`` under a tiles folder,
      as large as a whole number of the pack's tiles, becomes a ``tiles`` sheet on that grid:
      ``one_way`` with the collision ``ONE_WAY``, ``ladder`` with ``LADDER``. Its role is
      DECORATION, so that it is never taken for the ground of a map.

    Only assets with one of these tags are touched; a top-down pack has none.
    """
    from rpggen.core import classifier

    cells: dict[tuple[int, int], int] = {}
    for asset in assets:
        grid = asset.detected.get("grid")
        if asset.detected.get("usage") == "tiles" and isinstance(grid, dict):
            cell = (int(grid["cell"][0]), int(grid["cell"][1]))
            cells[cell] = cells.get(cell, 0) + 1
    tile = min(cells, key=lambda c: (-cells[c], c)) if cells else None
    for asset in assets:
        facets = asset.detected
        if asset.kind != "image" or asset.detected_by != "generic_grid":
            continue
        if facets.get("animations"):
            continue
        tags = set(facets.get("tags") or [])
        size = facets.get("size") or [0, 0]
        if facets.get("role") == "BACKGROUND" and any(t.startswith("parallax:") for t in tags):
            # also an opaque layer whose texture happened to look like a grid of tiles
            if facets.get("usage") in ("sprite", "tiles"):
                facets["usage"] = "background"
                for key in ("frame", "origin", "grid"):
                    facets.pop(key, None)
            continue
        if facets.get("usage") != "sprite":
            continue
        folders, _stem = classifier.tokens(asset.path)
        if tile is None or not tags & SIDE_TILE_TAGS or not set(folders) & TILE_FOLDER_WORDS:
            continue
        if size[0] < tile[0] or size[1] < tile[1] or size[0] % tile[0] or size[1] % tile[1]:
            continue
        facets["usage"] = "tiles"
        facets["grid"] = {"cell": list(tile), "margin": [0, 0], "separation": [0, 0]}
        facets["role"] = "DECORATION"
        for key in ("frame", "origin", "roles_alt"):
            facets.pop(key, None)
        for tag in sorted(tags):
            if tag in SIDE_TILE_COLLISION:
                facets["collision"] = {"profile": SIDE_TILE_COLLISION[tag]}
                break


# A pack warning: the pack looks like a side-view (platformer) pack (T14.02).
VIEW_SIDE = "view:side"


def _side_view_soldier(assets: list[Asset]) -> None:
    """A side-view pack whose hero is called a soldier (T16.09): the word makes it an NPC for
    the classifier, which leaves the pack without a player. When no asset of the pack is the
    player, the first soldier that can jump is."""
    if any(a.detected.get("role") == "PLAYER" for a in assets):
        return
    for asset in sorted(assets, key=lambda a: a.id):
        facets = asset.detected
        if asset.detected_by in ("profile", "learned") or facets.get("role") != "NPC":
            continue
        animations = facets.get("animations") or {}
        if "soldier" in (facets.get("tags") or []) and any(
            str(name).split("_", 1)[0] == "jump" for name in animations
        ):
            facets["role"] = "PLAYER"
            facets.pop("roles_alt", None)
            return


def _farm_farmer(assets: list[Asset]) -> None:
    """A farming pack whose hero is called a farmer (T17.01): the classifier takes a character
    in a folder of characters for an NPC, which leaves the pack without a player. When no asset
    of the pack is the player, the first farmer that walks is."""
    from rpggen.core import classifier

    if any(a.detected.get("role") == "PLAYER" for a in assets):
        return
    for asset in sorted(assets, key=lambda a: a.id):
        facets = asset.detected
        if asset.detected_by in ("profile", "learned") or facets.get("role") != "NPC":
            continue
        _folders, words = classifier.tokens(asset.path)
        animations = facets.get("animations") or {}
        if "farmer" in words and any(str(n).split("_", 1)[0] == "walk" for n in animations):
            facets["role"] = "PLAYER"
            facets.pop("roles_alt", None)
            return


FARM_CHARACTER_ROLES = frozenset({"PLAYER", "NPC"})


def _farm_use_strips(assets: list[Asset]) -> None:
    """A farming pack's strips of a character using a tool (T17.10):
    ``farmer_hoe_down_16x16_3frames`` beside ``farmer_walk_down_...`` is an animation of the
    farmer, not a villager. A character strip whose name is the name of another character of its
    folder and then a tool word is left unused (the role ``NONE``, with the reason), and tagged
    ``use_anim:<tool>`` and ``of:<the character's id>``, so that nobody takes the farmer hoeing
    for a person of the village. Its animations stay read. Never over a profile or a learned
    value."""
    from rpggen.core import classifier

    def character(asset: Asset) -> bool:
        facets = asset.detected
        return (
            asset.kind == "image"
            and facets.get("usage") == "sprite"
            and bool(facets.get("animations"))
            and facets.get("role") in FARM_CHARACTER_ROLES
        )

    found = [(a, *classifier.character_words(a.path)) for a in assets if character(a)]
    who: dict[tuple[str, tuple[str, ...]], Asset] = {}
    for asset, words, tool in sorted(found, key=lambda row: row[0].id):
        if words and not tool:
            who.setdefault((asset.path.rsplit("/", 1)[0], tuple(words)), asset)
    for asset, words, tool in found:
        owner = who.get((asset.path.rsplit("/", 1)[0], tuple(words)))
        if not tool or owner is None or asset.detected_by in ("profile", "learned"):
            continue
        facets = asset.detected
        facets["role"] = "NONE"
        facets.pop("roles_alt", None)
        facets["tags"] = sorted(
            {
                *facets.get("tags", []),
                classifier.UNUSED_TAG + classifier.UNUSED_USE_ANIM,
                classifier.USE_ANIM_TAG + tool,
                classifier.USE_ANIM_OF_TAG + owner.id,
            }
        )


# the roles the classifier gives the things of a farming pack for want of a better one
FARM_REPLACED_ROLES = frozenset({"DECORATION", "EFFECT", "ITEM", "NPC"})
FARM_TOOL_REPLACED_ROLES = FARM_REPLACED_ROLES | {"WATER", "WEAPON"}  # tools/water.png, an axe


def _farm_roles(assets: list[Asset], root: str) -> None:
    """The roles of a farming pack's things (T17.02), where the words of a file say so and no
    reader or rule has decided: an animal with an animation (it walks, or sleeps) is an
    ``ANIMAL`` and not a villager, a picture tagged ``tool`` is a ``TOOL`` (``water`` in a
    folder of tools is the watering can, not a pond), a crop of one picture is a ``CROP``, and
    an animated overlay tagged ``weather`` is an ``EFFECT``, so that the rain is nobody to talk
    to. A growth strip is a ``CROP`` in every pack, where it is read."""
    from rpggen.core import classifier, pack_forms
    from rpggen.core.adapters import farm

    # a pack whose crops were read from their pictures (T17.29) grows those: its single
    # pictures of a crop (*Modern Farm*'s baskets of cabbages, a fruitless vine) are no crops
    read_crops = any(
        a.detected_by == farm.NAME and a.detected.get("usage") == "growth_strip" for a in assets
    )
    for asset in assets:
        facets = asset.detected
        # what the farming packs' reader decided (T17.29: a food icon is an item) stays too
        if asset.kind != "image" or asset.detected_by in ("profile", "learned", "farm_pack"):
            continue
        if facets.get("usage") != "sprite" or facets.get("headings"):
            continue
        current, tags = facets.get("role"), set(facets.get("tags") or [])
        role = None
        folders, stem_words = classifier.tokens(asset.path[len(root) + 1 :])
        if current == "NPC" and (set(folders) | set(stem_words)) & {"portrait", "portraits"}:
            # a portrait in a folder of NPCs is nobody to meet (T17.29: *Farm RPG*'s villagers
            # were the pieces of its portraits)
            facets["role"] = "PORTRAIT"
            facets.pop("roles_alt", None)
            continue
        if current == "NPC":
            # ... nor a horse in a folder of its own (``Animals/Farm/Horse/1/Run.png``), a
            # deer of the forest or a butterfly: an animal of the farm, or something that lives
            # about it; nor a piece of a character it could not put together, nor the copy an
            # Aseprite folder exports
            said = set(folders)
            found = None
            if said & farm.ANIMAL_WORDS:
                found = "ANIMAL"  # without animations it is planned for nothing, and no prop
            elif (
                said & farm.CRITTER_WORDS
                or (said & {"animal", "animals"} and "animal" not in tags)
                or said & pack_forms.HOUSE_NAMES  # ``NPCS houses/Blacksmith/Blacksmith.png``
            ):
                found = "DECORATION"
            elif (
                said & {"aseprite"}
                or "aseprite" in asset.id.split(".")  # drawn from a folder Aseprite's source
                or any(farm._part_of(p) for p in folders)
                or set(stem_words) & {"body", "bodies", "skin", "skins"}  # a bare body
            ):
                found = "NONE"
                facets["tags"] = sorted(
                    {*facets.get("tags", []), classifier.UNUSED_TAG + "layered_piece"}
                )
            if found is not None:
                facets["role"] = found
                facets.pop("roles_alt", None)
                continue
        if facets.get("animations"):
            if current in FARM_REPLACED_ROLES and tags & {"animal", "weather"}:
                role = "ANIMAL" if "animal" in tags else "EFFECT"
        elif "tool" in tags:
            role = "TOOL" if current in FARM_TOOL_REPLACED_ROLES else None
        elif (
            not read_crops
            and current in FARM_REPLACED_ROLES
            and classifier.is_single_crop(asset.path[len(root) + 1 :])
        ):
            role = "CROP"
        if role is not None and role != current:
            facets["role"] = role
            facets.pop("roles_alt", None)


# What the pieces of an isometric pack's houses are called (the tags of ``_iso_roles``).
ISO_PIECE_WORDS: tuple[tuple[str, frozenset[str]], ...] = (
    ("door", frozenset({"door", "doors", "doorway", "gate", "gateway", "archway"})),
    ("window", frozenset({"window", "windows"})),
    ("roof", frozenset({"roof", "roofs", "chimney"})),
    ("fence", frozenset({"fence", "fences"})),
)
# the roles of what a map is laid with: nothing that fills no diamond has one of them
ISO_LAID_ROLES = frozenset({"GROUND", "ROAD", "WATER"})


def _iso_roles(assets: list[Asset], root: str) -> None:
    """The roles of an isometric pack's pieces (after T17.20), where the picture says more
    than the words: never over a profile or a learned value, never for a picture left unused.

    * **A piece along one side of its diamond** (``edge``: a wall segment, a wall with a
      window or a door, a fence) is a ``WALL``, whatever its name made of it: a wall with a
      window is no ``UI`` because *window* is a word of menus. It is tagged ``door`` or
      ``window`` when its name says so, so that a house can be given a door.
    * **A roof** (``roof``, ``chimney`` in its name) is tagged ``roof`` and is nobody's ground
      or room: it fills a diamond, a storey up.
    * **An object**, which fills no diamond, is not what a map is laid with: a carpet, the
      upper storey of a house with *tiles* in its name are ``DECORATION``, not ``GROUND``."""
    from rpggen.core import classifier

    for asset in assets:
        facets = asset.detected
        if asset.kind != "image" or asset.detected_by in ("profile", "learned"):
            continue
        if facets.get("projection") != PROJECTION_ISOMETRIC or facets.get("role") == "NONE":
            continue
        if facets.get("animations") or facets.get("headings"):
            continue
        _folders, words = classifier.tokens(asset.path[len(root) + 1 :])
        said = {tag for tag, names in ISO_PIECE_WORDS if set(words) & names}
        role = current = facets.get("role")
        # ... and no wall of a map's edge either, whatever else its name says (T17.22: the
        # ``roofSingleWall`` of *Miniature Farm* was laid round the farm as its wall)
        roof = "roof" in said and current in ISO_LAID_ROLES | {"INTERIOR", "WALL"}
        thing = facets.get("usage") == "sprite" and current in ISO_LAID_ROLES
        if facets.get("edge"):
            role = "WALL"
        elif roof or thing:
            role = "DECORATION"
        if not facets.get("edge"):
            said &= {"roof"}  # a door leaf by itself is no wall with a door
        if said:
            facets["tags"] = sorted(set(facets.get("tags") or []) | said)
        if role != current:
            facets["role"] = role
            facets.pop("roles_alt", None)


ROTATION_SHEET_ROLES = frozenset({"DECORATION", "EFFECT", "PROJECTILE", "NONE"})
# the roles the classifier gives the things of an arcade pack for want of a better one
ARCADE_REPLACED_ROLES = frozenset({"DECORATION", "EFFECT", "ITEM", "ENEMY", "NPC"})
VIEW_SHMUP = "view:shmup"  # T16.02: the pack looks like one for a shoot 'em up
VIEW_RACING = "view:racing"  # ... for a racing game
VIEW_FARM = "view:farm"  # T17.01: ... for a farm
VIEW_ISOMETRIC = "view:isometric"  # T17.12: the pack is one of isometric tiles
ISO_TILE_USAGE = "iso_tile"  # one isometric tile a picture: a tile of an isometric project
TURN_TAG = "turn:"
# The readers whose one-row strips can be a crop's growth (T17.01): the ones that cut a strip
# by its name's frame count or by the picture, and give it no action.
GROWTH_READERS = frozenset({"strips", "generic_grid"})
GROWTH_REVIEW_CONFIDENCE = 0.5  # a growth strip told by its folder and its size: needs review


def pack_view(pack: CatalogPack) -> str:
    """``"side"``, ``"top"`` or ``"isometric"``: what detection said about a pack's point of
    view."""
    if VIEW_ISOMETRIC in pack.warnings:
        return "isometric"
    return "side" if VIEW_SIDE in pack.warnings else "top"


def is_iso_tile(asset: Asset) -> bool:
    """True for a picture that is one isometric tile (T17.12): a tile of the tile set of an
    isometric project (T17.13), and nothing to a project that is seen from above."""
    return effective(asset).get("usage") == ISO_TILE_USAGE


ISO_ATLAS_USAGE = "iso_atlas"  # a picture rpggen packed the tiles of an isometric pack into
PROJECTION_ISOMETRIC = "isometric"


def fits_projection(asset: Asset, projection: str = "top_down") -> bool:
    """Whether ``asset`` can fill a role in a project that is seen in ``projection`` (T17.13).
    One rule for the mapping, the requirements and (as ``CatalogReader.fits_projection``) the
    builder's lookups by role: **a top-down project uses nothing that was drawn for the
    isometric view** (no isometric tile, no tree or house or car drawn at that angle), and **an
    isometric project paints with no sheet of square tiles**. A character, an item or a sound
    drawn for a top-down game is used by both (the isometric packs that were listed have no
    people: T17.14 lets a top-down hero walk an isometric map)."""
    facets = effective(asset)
    usage = facets.get("usage")
    if usage == ISO_ATLAS_USAGE:
        return False  # the atlas is the tile set's picture: nobody's ground, nobody's choice
    if projection == PROJECTION_ISOMETRIC:
        return usage != "tiles"
    return facets.get("projection") != PROJECTION_ISOMETRIC


def _diamond_of_tiles(sheets: list[dict[str, Any]]) -> tuple[int, int] | None:
    """The diamond most isometric tiles among ``sheets`` (detected facets) stand on, or None
    when none says one. Of two that as many tiles stand on, the smaller."""
    counts: dict[tuple[int, int], int] = {}
    for facets in sheets:
        foot = facets.get("footprint")
        if facets.get("usage") != "iso_tile" or not isinstance(foot, list | tuple):
            continue
        if len(foot) == 2 and all(isinstance(n, int) and n > 0 for n in foot):
            counts[(foot[0], foot[1])] = counts.get((foot[0], foot[1]), 0) + 1
    if not counts:
        return None
    return min(counts, key=lambda foot: (-counts[foot], foot))


def isometric_footprint(pack: CatalogPack) -> tuple[int, int, str] | None:
    """``(width, height, where it came from)`` of the diamond of an isometric pack, from its
    warning ``isometric:180x104:measured`` (the source is ``tiled``, ``tile_information`` or
    ``measured``, or ``profile`` for a pack whose installed profile said its tiles); None for
    a pack that is not one."""
    from rpggen.core import classifier

    for mark in pack.warnings:
        if not mark.startswith(classifier.ISOMETRIC_MARK):
            continue
        size, _, source = mark[len(classifier.ISOMETRIC_MARK) :].partition(":")
        width, _, height = size.partition("x")
        if width.isdigit() and height.isdigit():
            return int(width), int(height), source
    return None


_GLUED_WORDS = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _headings_name(path: str) -> str:
    """The path a car in several headings is told from its other colours by. A car whose
    files say their headings (``taxi_N.png``) keeps its first file's path. One whose files are
    numbered views (``Black/Sedan 1/carBlack2_003.png``, which is ``carRed2_002.png`` in the
    red folder: the numbers follow no order) is named without the number, its glued words
    apart, so that the colour in the name is found: ``Black/Sedan 1/car_Black2``."""
    from rpggen.core.adapters import naming, sequences

    folder, stem = posixpath.split(posixpath.splitext(path)[0])
    if naming.split_turn(stem) is not None:
        return path
    split = sequences.split_number(stem)
    name = _GLUED_WORDS.sub("_", split[0] if split is not None and split[0] else stem)
    return posixpath.join(folder, name)


def mark_colour_variants(catalog: Catalog) -> None:
    """Tag the pictures a pack ships in several colours (T16.21): every one gets
    ``colour:<name>`` when its name or folder says one, and every one but the first of a group
    ``variant_of:<id of the first>``. The first is the file without a colour word when there is
    one (``Classic_Bug.png`` beside ``Classic_Bug_red.png``), else the first colour by name.
    Only pictures of one pack, one size and one usage are a group; information only: every
    variant stays an asset of its own with its own role."""
    from rpggen.core import classifier

    groups: dict[tuple[Any, ...], list[tuple[str, Asset]]] = {}
    for asset in catalog.assets:
        if asset.kind != "image" or "#" in asset.id or asset.status == "MISSING":
            continue
        root = f"assets/packs/{asset.pack_id}/"
        facets = asset.detected
        made_of = facets.get("heading_files") or []
        if made_of:  # a car's headings put into one strip (T17.12): its files say the colour
            key, colour = classifier.colour_key(_headings_name(str(made_of[0])))
        elif asset.path.startswith(root):
            key, colour = classifier.colour_key(asset.path[len(root) :])
        else:
            continue  # a generated picture
        if facets.get("role") == "NONE":
            continue  # a preview, another engine's copy: not offered as a variant
        size = tuple(facets.get("size") or ())
        groups.setdefault((asset.pack_id, key, size, facets.get("usage")), []).append(
            (colour, asset)
        )
    for members in groups.values():
        if len({colour for colour, _a in members}) < 2:
            continue
        members.sort(key=lambda m: (m[0] != "", m[0], _sort_key(m[1].id)))
        first = members[0][1]
        for colour, asset in members:
            tags = [
                t
                for t in asset.detected.get("tags", [])
                if not str(t).startswith((classifier.VARIANT_TAG, classifier.COLOUR_TAG))
            ]
            if colour:
                tags.append(classifier.COLOUR_TAG + colour)
            if asset is not first:
                tags.append(classifier.VARIANT_TAG + first.id)
            asset.detected["tags"] = sorted(tags)


def mark_season_variants(catalog: Catalog) -> None:
    """Group the sheets a pack ships once a season (T17.01), as ``mark_colour_variants`` groups
    colours: pictures of one pack, one size and one usage that differ only by a season word
    (a folder ``winter/`` or a word of the name) in two seasons or more. Every member gets
    ``season:<name>`` and every one but the first ``variant_of:<id of the first>``; the first is
    the sheet without a season when there is one, else the earliest season of the year. A
    picture that is a colour variant already stays in its colour group."""
    from rpggen.core import classifier

    order = {name: index for index, name in enumerate(("", *classifier.SEASONS))}
    groups: dict[tuple[Any, ...], list[tuple[str, Asset]]] = {}
    for asset in catalog.assets:
        if asset.kind != "image" or "#" in asset.id or asset.status == "MISSING":
            continue
        root = f"assets/packs/{asset.pack_id}/"
        facets = asset.detected
        if not asset.path.startswith(root) or facets.get("role") == "NONE":
            continue
        if any(str(t).startswith(classifier.VARIANT_TAG) for t in facets.get("tags") or []):
            continue
        key, season = classifier.season_key(asset.path[len(root) :])
        size = tuple(facets.get("size") or ())
        groups.setdefault((asset.pack_id, key, size, facets.get("usage")), []).append(
            (season, asset)
        )
    for members in groups.values():
        if len({season for season, _a in members if season}) < 2:
            continue
        members.sort(key=lambda m: (order[m[0]], _sort_key(m[1].id)))
        first = members[0][1]
        for season, asset in members:
            tags = [
                t
                for t in asset.detected.get("tags", [])
                if not str(t).startswith(classifier.SEASON_TAG)
            ]
            if season:
                tags.append(classifier.SEASON_TAG + season)
            if asset is not first:
                tags.append(classifier.VARIANT_TAG + first.id)
            asset.detected["tags"] = sorted(tags)


def mark_turns(catalog: Catalog) -> None:
    """Group the pictures that are one tile turned (T17.12): ``roadTile_001_0`` to ``_3``,
    ``cornDouble_N`` / ``_E`` / ``_S`` / ``_W``. The reader gave every one its ``turn``; here
    every one gets the tag ``turn:<n>`` and every one but the first ``variant_of:<id of the
    first>``, so that the audit shows the set as one card, as it shows a picture in several
    colours. A set whose first turn is itself a colour of another picture joins that picture's
    group, so that a group is never inside a group. Information only: every turn stays an asset
    of its own."""
    from rpggen.core import classifier
    from rpggen.core.adapters import naming

    groups: dict[tuple[str, str, str], list[Asset]] = {}
    for asset in catalog.assets:
        if asset.kind != "image" or "#" in asset.id or asset.status == "MISSING":
            continue
        root = f"assets/packs/{asset.pack_id}/"
        if "turn" not in asset.detected or not asset.path.startswith(root):
            continue
        rel = asset.path[len(root) :]
        turn = naming.split_turn(posixpath.splitext(posixpath.basename(rel))[0])
        if turn is not None:
            key = (asset.pack_id, posixpath.dirname(rel), turn.base.casefold())
            groups.setdefault(key, []).append(asset)
    for members in groups.values():
        members.sort(key=lambda a: (int(a.detected["turn"]), _sort_key(a.id)))
        first = members[0]
        said = next(
            (
                str(t)[len(classifier.VARIANT_TAG) :]
                for t in first.detected.get("tags") or []
                if str(t).startswith(classifier.VARIANT_TAG)
            ),
            first.id,
        )
        for asset in members:
            tags = [
                t
                for t in asset.detected.get("tags", [])
                if not str(t).startswith(TURN_TAG)
                and not (asset is not first and str(t).startswith(classifier.VARIANT_TAG))
            ]
            tags.append(f"{TURN_TAG}{int(asset.detected['turn'])}")
            if asset is not first:
                tags.append(classifier.VARIANT_TAG + said)
            asset.detected["tags"] = sorted(tags)


def turn_sets(assets: list[Asset]) -> dict[str, str]:
    """``{asset id: id of the first turn of its set}`` for every picture of ``assets`` that is
    one turn of a thing (T17.13), by the names ``mark_turns`` groups them by. A tile drawn in
    two colours is two sets here, each with its own first turn: ``variant_of`` names the first
    colour's, which is no help to somebody who wants *this* tile turned east."""
    from rpggen.core.adapters import naming

    groups: dict[tuple[str, str, str], list[Asset]] = {}
    for asset in assets:
        root = f"assets/packs/{asset.pack_id}/"
        facets = effective(asset)
        if "turn" not in facets or not asset.path.startswith(root):
            continue
        rel = asset.path[len(root) :]
        turn = naming.split_turn(posixpath.splitext(posixpath.basename(rel))[0])
        if turn is not None:
            key = (asset.pack_id, posixpath.dirname(rel), turn.base.casefold())
            groups.setdefault(key, []).append(asset)
    out: dict[str, str] = {}
    for members in groups.values():
        members.sort(key=lambda a: (int(effective(a)["turn"]), _sort_key(a.id)))
        for asset in members:
            out[asset.id] = members[0].id
    return out


def turn_name(asset: Asset) -> str:
    """``turn_2`` for a picture that is a tile's second turn; empty for the first turn and for
    a picture that is no turn."""
    tags = asset.detected.get("tags") or []
    found = next((str(t)[len(TURN_TAG) :] for t in tags if str(t).startswith(TURN_TAG)), "")
    return f"turn_{found}" if found not in ("", "0") else ""


def season_name(asset: Asset) -> str:
    """The season a sheet is drawn for (``winter``); empty for one that is for the whole year."""
    from rpggen.core import classifier

    tags = asset.detected.get("tags") or []
    found = next((str(t) for t in tags if str(t).startswith(classifier.SEASON_TAG)), "")
    return found[len(classifier.SEASON_TAG) :]


def season_groups(catalog: Catalog) -> dict[str, dict[str, str]]:
    """``{id of a group's first sheet: {season: id of the sheet for it}}`` for the sheets a
    catalog has once a season (T17.01): what the farm swaps the ground and the trees by. The
    first sheet is in its own group, under its season or under ``""`` when it names none."""
    groups: dict[str, dict[str, str]] = {}
    for first, others in colour_groups(catalog).items():
        members = [a for a in (catalog.asset(i) for i in (first, *others)) if a is not None]
        if any(colour_name(a) != season_name(a) for a in members):
            continue  # a group of colours
        seasons = {season_name(a): a.id for a in reversed(members)}
        if len([s for s in seasons if s]) >= 2:
            groups[first] = {s: seasons[s] for s in sorted(seasons)}
    return groups


def colour_variants(catalog: Catalog, asset_id: str) -> list[Asset]:
    """The assets tagged as colour variants of ``asset_id``, by id."""
    from rpggen.core import classifier

    tag = classifier.VARIANT_TAG + asset_id
    return sorted(
        (a for a in catalog.assets if tag in (a.detected.get("tags") or [])),
        key=lambda a: _sort_key(a.id),
    )


def colour_groups(catalog: Catalog) -> dict[str, list[str]]:
    """``{id of a group's first picture: the ids of its other colours, by id}`` for the colour
    variants of a catalog (T16.21): what the audit shows as one card and the Mapping page
    offers as the colours of a choice. A group whose first picture is not in the catalog (a
    list of candidates that leaves it out) is no group."""
    from rpggen.core import classifier

    present = {a.id for a in catalog.assets}
    groups: dict[str, list[str]] = {}
    for asset in catalog.assets:
        for tag in asset.detected.get("tags") or []:
            if not str(tag).startswith(classifier.VARIANT_TAG):
                continue
            first = str(tag)[len(classifier.VARIANT_TAG) :]
            if first in present and first != asset.id:
                groups.setdefault(first, []).append(asset.id)
            break
    return {first: sorted(members, key=_sort_key) for first, members in groups.items()}


def colour_group(catalog: Catalog, asset_id: str) -> list[Asset]:
    """The colour variants ``asset_id`` is one of, the group's first picture first; empty for
    a picture that comes in one colour."""
    groups = colour_groups(catalog)
    first = next((f for f, members in groups.items() if asset_id == f or asset_id in members), "")
    found = [catalog.asset(i) for i in ([first, *groups[first]] if first else [])]
    return [a for a in found if a is not None]


GROUP_COLOURS = "colours"
GROUP_TURNS = "turns"
GROUP_SEASONS = "seasons"


def group_kind(group: list[Asset]) -> str:
    """What the pictures of a ``colour_group`` are to each other (T17.16): ``"turns"`` when
    they are one thing turned (``roadTile_001_0`` to ``_3``) and nothing else tells them apart,
    ``"seasons"`` when they are one sheet a season, else ``"colours"`` (a group that is turned
    *and* drawn in several colours is one of colours: the audit lists ``red turn 2``)."""
    from rpggen.core import classifier

    def tags(asset: Asset, prefix: str) -> list[str]:
        return [str(t) for t in asset.detected.get("tags") or [] if str(t).startswith(prefix)]

    if not group:
        return GROUP_COLOURS
    if any(tags(a, classifier.COLOUR_TAG) for a in group):
        return GROUP_COLOURS
    seasons = {season_name(a) for a in group} - {""}
    if len(seasons) >= 2 and not any(turn_name(a) for a in group):
        return GROUP_SEASONS
    if all(tags(a, TURN_TAG) for a in group) and not seasons:
        return GROUP_TURNS
    return GROUP_COLOURS


def member_name(asset: Asset, kind: str = GROUP_COLOURS) -> str:
    """How a picture of a group is called beside the others, in the words of the group's kind:
    ``turn 2`` (the first turn is ``turn 0``), ``winter``, ``red`` or ``red turn 2``; empty for
    the picture of a group of colours that names none."""
    if kind == GROUP_TURNS:
        tags = asset.detected.get("tags") or []
        found = next((str(t)[len(TURN_TAG) :] for t in tags if str(t).startswith(TURN_TAG)), "0")
        return f"turn {found}"
    return colour_name(asset).replace("_", " ")


def colour_name(asset: Asset) -> str:
    """The colour a variant's name or folder says (``red``, ``black_white``), or its season for
    a sheet that comes once a season, and its turn for a tile turned (``turn_2``,
    ``red_turn_2``); empty for the picture of a group that names none of them."""
    from rpggen.core import classifier

    tags = asset.detected.get("tags") or []
    found = next((str(t) for t in tags if str(t).startswith(classifier.COLOUR_TAG)), "")
    name = found[len(classifier.COLOUR_TAG) :] or season_name(asset)
    return "_".join(part for part in (name, turn_name(asset)) if part)


def _licence_paths(inv: Inventory, folder: Path) -> list[str]:
    """The pack's licence files relative to its folder: the files named as licences, and the
    documentation files that hold the licence (T17.29: ``Documentation.txt`` at the root or one
    folder down, saying licence, credit or commercial)."""
    named = [f.path for f in inv.files if f.kind == "license"]
    return named + licenses.doc_licence_files(folder, [(f.path, f.kind) for f in inv.files])


def _license_files(rel_paths: list[str], root: str) -> list[str]:
    return sorted((f"{root}/{rel}" for rel in rel_paths), key=_sort_key)


REVIEWED_STATUSES = frozenset({"CONFIRMED", "UNUSED"})
ATTENTION_STATUSES = frozenset({"CONFLICT", "NEEDS_REVIEW", "MISSING"})
# Packs whose assets a run makes itself, every time it needs them (``placeholders.py``,
# ``side_kit.py``): no pack file is behind them, so one of them is never reported as vanished.
RUN_MADE_PACKS = frozenset(
    {
        "debug_placeholders",
        "rpggen_side_kit",
        "rpggen_arcade_kit",
        "rpggen_farm_kit",
        "rpggen_iso",  # iso_atlas.ATLAS_PACK: the atlases of an isometric project (T17.13)
        "rpggen_iso_kit",  # iso_kit.KIT_PACK: its drawn hero, villager and enemy (T17.14)
    }
)


def folder_of(catalog: Catalog, asset: Asset) -> str:
    """The asset's folder relative to its pack ("" for the pack's top folder): what a folder
    rule's glob starts with and what the audit grid groups by (T13.02)."""
    root = next((p.root for p in catalog.packs if p.pack_id == asset.pack_id), "")
    rel = asset.path[len(root) + 1 :] if root and asset.path.startswith(root + "/") else asset.path
    return posixpath.dirname(rel)


def review_progress(catalog: Catalog) -> tuple[int, int, int]:
    """(reviewed, needing attention, total) assets of a catalog: reviewed is CONFIRMED or UNUSED,
    attention is CONFLICT, NEEDS_REVIEW or MISSING; the rest were auto-detected."""
    done = attention = 0
    for asset in catalog.assets:
        if asset.status in REVIEWED_STATUSES:
            done += 1
        elif asset.status in ATTENTION_STATUSES:
            attention += 1
    return done, attention, len(catalog.assets)


def _tile_count(catalog: Catalog, tileset: TileSetDef) -> int:
    """How many tiles the sheets of a tile set hold (cells of each sheet's grid)."""
    total = 0
    for source in tileset.sources:
        asset = catalog.asset(source["asset"])
        if asset is None:
            continue
        facets = effective(asset)
        grid = facets.get("grid") or {}
        size = facets.get("size") or asset.detected.get("size")
        cell = grid.get("cell")
        if not cell or not size or min(cell) <= 0:
            continue
        margin = grid.get("margin") or [0, 0]
        gap = grid.get("separation") or [0, 0]
        cols = (size[0] - 2 * margin[0] + gap[0]) // (cell[0] + gap[0])
        rows = (size[1] - 2 * margin[1] + gap[1]) // (cell[1] + gap[1])
        total += max(cols, 0) * max(rows, 0)
    return total


def dominant_tile_size(catalog: Catalog) -> int | None:
    """The tile size of a catalog's packs: the cell size of the ``overworld`` tile set, else of
    the tile set with the most tiles (a tie goes to the smaller size); None without tile sets."""
    # the diamond of an isometric tile set (T17.13) is no tile size of square tiles
    sets = [t for t in catalog.tilesets if t.tile_size and t.tile_size[0] > 0 and not t.projection]
    if not sets:
        return None
    overworld = next((t for t in sets if t.name == "overworld"), None)
    if overworld is not None:
        return int(overworld.tile_size[0])
    best = max(sets, key=lambda t: (_tile_count(catalog, t), -t.tile_size[0]))
    return int(best.tile_size[0])


class AssemblyCancelled(Cancelled):
    """``assemble`` stopped because the caller cancelled (between packs or between images)."""


def assemble(
    packs: list[tuple[OpenedPack, Inventory]],
    previous: Catalog | None,
    profiles: list[Any] | None = None,
    *,
    work_dir: Path | None = None,
    use_cache: bool = True,
    is_cancelled: Callable[[], bool] | None = None,
    progress: Progress | None = None,
    learned: list[Any] | None = None,
) -> tuple[Catalog, IssueList, dict[str, str]]:
    """Run adapters, classify and merge everything into a Catalog.

    ``learned`` are the rules learned from the user's fixes (T12.59; only the wizard passes
    them): the learned adapter proposes their values.

    ``progress`` receives ``("Analyzing images", done, total)`` per pack and ``is_cancelled`` is
    polled before every image, so a cancel raises ``AssemblyCancelled`` within one image.

    Returns ``(catalog, issues, generated_files)`` where generated_files maps project-relative
    paths (GIF strips) to the absolute files the installer must copy.
    """
    from rpggen.core import adapters, classifier, pack_forms, terrain
    from rpggen.core.adapters import farm, strips
    from rpggen.core.analyzer import analyzer_for, prewarm

    adapters.register_defaults()
    issues = IssueList()
    catalog = Catalog()
    generated: dict[str, str] = {}
    adapter_tilesets: list[dict[str, Any]] = []
    objects_raw: list[tuple[str, dict[str, Any]]] = []  # (pack_id, adapter object dict)
    maps_raw: list[tuple[str, dict[str, Any]]] = []  # (pack_id, raw map of a Tiled/LDtk file)
    present_ids: set[str] = set()
    all_results: dict[str, list[Any]] = {}
    extra_rules: list[FolderRule] = []
    pack_roots: dict[str, Path] = {}
    picture_hashes: dict[str, str] = {}  # asset id -> difference hash (T13.04)
    farm_ids: set[str] = set()  # the farming packs (T17.29)

    for opened, inv in sorted(packs, key=lambda pair: _sort_key(pair[1].pack_id)):
        if is_cancelled is not None and is_cancelled():
            raise AssemblyCancelled
        pack_id = inv.pack_id
        root = f"assets/packs/{pack_id}"
        pack_roots[pack_id] = opened.root
        issues.extend(opened.issues)
        issues.extend(i for i in inv.issues if i not in opened.issues)
        try:
            # the images are analyzed in parallel first; the adapters then read the results
            warm = prewarm(
                inv,
                opened.root,
                use_cache=use_cache,
                is_cancelled=is_cancelled,
                on_progress=progress,
            )
            ctx = adapters.AdapterContext(
                pack_id=pack_id,
                analyze=analyzer_for(
                    inv,
                    opened.root,
                    use_cache=use_cache,
                    is_cancelled=is_cancelled,
                    prewarmed=warm,
                ),
                work_dir=work_dir,
                learned=list(learned or []),
            )
            results = adapters.run_adapters(inv, opened.root, ctx)
        except Cancelled as exc:
            raise AssemblyCancelled from exc
        all_results[pack_id] = results
        warnings: list[str] = []
        for res in results:
            extra_rules.extend(
                FolderRule(pack_id, r["glob"], copy.deepcopy(r["set"])) for r in res.folder_rules
            )
            issues.extend(res.issues)
            warnings.extend(res.pack_warnings)
            generated.update(res.generated)
            adapter_tilesets.extend(res.tilesets)
            objects_raw.extend((pack_id, o) for o in res.objects)
            maps_raw.extend((pack_id, m) for m in res.maps)

        # collect fragments per (path, variant)
        by_key: dict[tuple[str, str], list[tuple[int, AssetFragment]]] = {}
        for index, res in enumerate(results):
            for frag in res.assets:
                by_key.setdefault((frag.path, frag.variant), []).append((index, frag))

        paths_sorted = [f.path for f in inv.files if f.kind == "image"]
        tops = {f.path.split("/", 1)[0] for f in inv.files if "/" in f.path}
        loose = any("/" not in f.path and f.kind != "license" for f in inv.files)
        wrapper = next(iter(tops)) if len(tops) == 1 and not loose else ""
        engines = classifier.engine_plan(paths_sorted, wrapper)
        stems = {
            (
                posixpath.dirname(p).casefold(),
                posixpath.splitext(posixpath.basename(p))[0].casefold(),
            )
            for p in paths_sorted
        }
        base_ids = ids.disambiguate([ids.asset_id(pack_id, p) for p in paths_sorted])
        id_for_path = dict(zip(paths_sorted, base_ids, strict=True))
        files = {f.path: f for f in inv.files}
        farm_pack = farm.is_farm_pack(inv)
        if farm_pack:
            farm_ids.add(pack_id)
        # a source rpggen drew (a .aseprite, T16.21; a car's headings put into one strip,
        # T17.12): the strip in the work folder is the asset's picture
        drawn = {p: rel for res in results for p, rel in res.rendered.items()}
        for path in paths_sorted:
            variants = sorted(v for (p, v) in by_key if p == path)
            for variant in variants:
                facets, confidence, first = _merge_fragments(by_key[(path, variant)])
                detected_by = results[first].adapter
                if _learned_decided(by_key[(path, variant)], facets):
                    detected_by = "learned"
                role_conf = None
                grown = None
                if "role" not in facets and detected_by in GROWTH_READERS:
                    stages = strips.growth_stages(facets)
                    if stages:
                        grown = classifier.growth_evidence(path, facets.get("frame"), stages)
                    if (
                        grown
                        and farm_pack
                        and not farm.counted(path)
                        and not farm.frames_grow(opened.root, path, facets.get("frame"), stages)
                    ):
                        # a butterfly called *Cabbage White*, a horse eating a carrot, a food
                        # icon that shines: their pictures do not grow (T17.29)
                        grown = None
                    if grown:  # a crop's stages in a row (T17.01): no animation
                        strips.as_growth_strip(facets)
                if "role" not in facets:
                    role, role_conf, alt = classifier.classify(facets, path, None)
                    facets["role"] = role
                    if alt:
                        facets["roles_alt"] = alt
                if grown:
                    # a crop (T17.02): a role only the farm reads, so no older kind picks it
                    # for anything; told by its name it needs no review
                    facets["role"] = "CROP"
                    facets.pop("roles_alt", None)
                    role_conf = confidence if grown == "name" else GROWTH_REVIEW_CONFIDENCE
                turning = role_conf is not None and bool(facets.get("headings"))
                if turning and {"car", "bike"} & set(classifier.arcade_tags(path)):
                    # a car or a bike in N headings is a vehicle (T16.03): what a racing game
                    # drives; the older kinds have no use for the role and leave it alone
                    facets["role"] = "VEHICLE"
                    facets.pop("roles_alt", None)
                elif turning and facets["role"] not in ROTATION_SHEET_ROLES:
                    # One thing in N headings has no walk and no attack: it is nothing the
                    # older kinds can make an actor or an item of, whatever its folder says.
                    facets["role"] = "DECORATION"
                    facets.pop("roles_alt", None)
                if role_conf is not None:
                    confidence = min(confidence, role_conf)
                    reason = classifier.not_game_art(path, wrapper)
                    if not reason and engines is not None:
                        reason = classifier.not_this_engine(path, engines, wrapper)
                    if not reason and classifier.copy_of(path, stems):
                        reason = classifier.UNUSED_COPY
                    if reason:  # a preview, a guide, another engine's copy: unused, says why
                        facets["role"] = "NONE"
                        facets.pop("roles_alt", None)
                        facets["tags"] = sorted(
                            {*facets.get("tags", []), classifier.UNUSED_TAG + reason}
                        )
                f = files[path]
                # a picture rpggen drew from a part of a sheet is the variant's (T17.29: a crop
                # cut from a sheet of tiles)
                drawn_key = (
                    f"{path}#{variant}" if variant and f"{path}#{variant}" in drawn else path
                )
                if f.image and drawn_key not in drawn:
                    facets["size"] = [f.image["w"], f.image["h"]]
                _suggest_tags(facets, path)
                asset_id = id_for_path[path] + (f"#{variant}" if variant else "")
                picture = _picture_hash(ctx.analyze, path) if ctx.analyze else None
                if picture is not None and drawn_key == path:
                    picture_hashes[asset_id] = picture
                catalog.assets.append(
                    Asset(
                        id=asset_id,
                        pack_id=pack_id,
                        path=drawn.get(drawn_key) or f"{root}/{path}",
                        sha256=f.sha256,
                        kind="image",
                        status="AUTO_DETECTED",
                        detected=facets,
                        detected_by=detected_by,
                        confidence=round(confidence, 6),
                    )
                )
                present_ids.add(asset_id)

        # a source that is no picture and that rpggen drew for want of an export (a .aseprite,
        # T16.21): the strip is the asset's picture, as a terrain atlas is of the asset made
        # from it
        for path in sorted(drawn, key=_sort_key):
            if (path, "") not in by_key or path in id_for_path:
                continue
            facets, confidence, first = _merge_fragments(by_key[(path, "")])
            if "role" not in facets:
                role, role_conf, alt = classifier.classify(facets, path, None)
                facets["role"] = role
                if alt:
                    facets["roles_alt"] = alt
                confidence = min(confidence, role_conf)
                reason = classifier.not_game_art(path, wrapper)
                if reason:
                    facets["role"] = "NONE"
                    facets.pop("roles_alt", None)
                    facets["tags"] = sorted(
                        {*facets.get("tags", []), classifier.UNUSED_TAG + reason}
                    )
            _suggest_tags(facets, path)
            asset_id = ids.asset_id(pack_id, path)
            while asset_id in present_ids:  # "hero 1.aseprite" beside "hero_1.png"
                asset_id += "_source"
            catalog.assets.append(
                Asset(
                    id=asset_id,
                    pack_id=pack_id,
                    path=drawn[path],
                    sha256=files[path].sha256,
                    kind="image",
                    status="AUTO_DETECTED",
                    detected=facets,
                    detected_by=results[first].adapter,
                    confidence=round(confidence, 6),
                )
            )
            present_ids.add(asset_id)

        for f in inv.files:
            if f.kind not in ("audio", "font"):
                continue
            analysis: dict[str, Any] = {"kind": f.kind}
            facets = {"usage": f.kind}
            if f.kind == "audio":
                duration = classifier.audio_duration(opened.root / f.path)
                if duration is not None:
                    analysis["duration_s"] = duration
            role, role_conf, _ = classifier.classify(facets, f.path, analysis)
            facets["role"] = role
            if f.kind == "audio":
                music = role == "AUDIO_MUSIC"
                facets["audio"] = {"type": "music" if music else "sfx", "loop": music}
                if duration is not None:
                    facets["audio"]["duration_s"] = round(duration, 3)
            detected_by = "inventory"
            if (f.path, "") in by_key:  # an installed profile decided this file
                measured = (facets.get("audio") or {}).get("duration_s")
                decided, role_conf, first = _merge_fragments(by_key[(f.path, "")])
                facets = {**facets, **decided}
                if measured is not None and isinstance(facets.get("audio"), dict):
                    facets["audio"].setdefault("duration_s", round(measured, 3))
                detected_by = results[first].adapter
                if _learned_decided(by_key[(f.path, "")], facets):
                    detected_by = "learned"
            asset_id = ids.asset_id(pack_id, f.path)
            catalog.assets.append(
                Asset(asset_id, pack_id, f"{root}/{f.path}", f.sha256, f.kind, "AUTO_DETECTED",
                      facets, {}, detected_by, role_conf)
            )  # fmt: skip
            present_ids.add(asset_id)

        licence_paths = _licence_paths(inv, opened.root)
        license_files = _license_files(licence_paths, root)
        if not license_files:
            issues.add("ASSET-021", pack_id=pack_id, file=root)
        _side_view_usage([a for a in catalog.assets if a.pack_id == pack_id])
        sheets = [a.detected for a in catalog.assets if a.pack_id == pack_id and a.kind == "image"]
        view = classifier.made_for(inv, sheets)
        if farm_pack and view == "top" and not classifier.isometric_view(inv, sheets):
            view = "farm"  # its own name says farm and its files nothing else (T17.29)
        elif (
            view == "racing"
            and classifier.farm_view(inv, sheets)
            and not classifier.isometric_view(inv, sheets)
        ):
            # a farm with a tractor in a folder of vehicles is no racing pack (T17.29)
            view = "farm"
        pack_forms.apply(
            [a for a in catalog.assets if a.pack_id == pack_id], inv, opened.root, root, farm_pack
        )
        if classifier.isometric_view(inv, sheets):
            # how the pack is seen (T17.12); what it was made for is said beside it
            warnings.append(VIEW_ISOMETRIC)
            if not any(w.startswith(classifier.ISOMETRIC_MARK) for w in warnings):
                # a pack read through its profile: the profile claims every picture, so the
                # isometric reader looked at none and said no diamond. The tiles say it.
                said = _diamond_of_tiles(sheets)
                if said is not None:
                    warnings.append(f"{classifier.ISOMETRIC_MARK}{said[0]}x{said[1]}:profile")
        if view in ("shmup", "racing"):
            # what such a pack calls a power-up is one: "ability" is the metroidvania's word
            for asset in catalog.assets:
                tags = asset.detected.get("tags") or []
                if asset.pack_id == pack_id and "ability" in tags:
                    rel = asset.path[len(root) + 1 :]
                    if "powerup" in classifier.arcade_tags(rel):
                        kept = {t for t in tags if t != "ability"} | {"powerup"}
                        asset.detected["tags"] = sorted(kept)
            # ... and its things have the roles of its kind (T16.03), where the words of a
            # file say so and no reader or rule has decided
            for asset in catalog.assets:
                if asset.pack_id != pack_id or asset.kind != "image":
                    continue
                if asset.detected_by in ("profile", "learned"):
                    continue
                kind_role = classifier.arcade_role(asset.detected.get("tags") or [])
                current = asset.detected.get("role")
                if kind_role and current in ARCADE_REPLACED_ROLES and kind_role != current:
                    asset.detected["role"] = kind_role
                    asset.detected.pop("roles_alt", None)
        if VIEW_ISOMETRIC in warnings:
            _iso_roles([a for a in catalog.assets if a.pack_id == pack_id], root)
        if view == "side":
            _side_view_soldier([a for a in catalog.assets if a.pack_id == pack_id])
        if view == "farm":
            _farm_farmer([a for a in catalog.assets if a.pack_id == pack_id])
            _farm_use_strips([a for a in catalog.assets if a.pack_id == pack_id])
            _farm_roles([a for a in catalog.assets if a.pack_id == pack_id], root)
            # a crop of one picture has no stages to grow through (T17.01): a note
            for asset in catalog.assets:
                facets = asset.detected
                if asset.pack_id != pack_id or asset.kind != "image" or "#" in asset.id:
                    continue
                if facets.get("usage") not in ("sprite", "object") or facets.get("role") == "NONE":
                    continue
                if asset.detected_by == farm.NAME:
                    continue  # a food icon is an item (T17.29), a crop of it was read whole
                if facets.get("animations") or facets.get("headings"):
                    continue
                if classifier.is_single_crop(asset.path[len(root) + 1 :]):
                    issues.add("ASSET-034", asset=asset.id, file=asset.path)
        if view != "top":  # a top-down pack, the usual kind, gets no line
            marks = {"side": VIEW_SIDE, "shmup": VIEW_SHMUP, "racing": VIEW_RACING}
            warnings.append(marks.get(view, VIEW_FARM))
        if engines is not None:
            warnings.append(engines.warning)  # "art for 5 engines: Godot's is used"
        catalog.packs.append(
            CatalogPack(
                pack_id,
                inv.source_sha256,
                root,
                license_files,
                [r.adapter for r in results if r.assets or r.objects or r.tilesets],
                next((r.profile_id for r in results if r.profile_id), None),
                sorted(set(warnings)),
                licenses.detect_files(opened.root, licence_paths).to_json(),
            )
        )

    # one size of a pack drawn in several, and no tile set in a size a pack does not draw
    catalog.pack_sizes = pack_forms.choose_sizes(
        catalog, dict(previous.pack_sizes) if previous is not None else {}, farm_ids
    )

    # the same picture twice: the later file says which one it repeats (information only)
    from rpggen.core.analyzer import similarity

    similarity.mark_duplicates(catalog, picture_hashes)
    mark_colour_variants(catalog)
    mark_season_variants(catalog)
    mark_turns(catalog)

    # terrain: Tiled wang sets -> peering, A2 composites (new assets), blob proposals (T8.06)
    terrain.apply_tiled_wang(catalog, adapter_tilesets)
    terrain_result = terrain.generate(catalog, pack_roots, work_dir, issues)
    generated.update(terrain_result.generated)
    present_ids.update(a.id for a in catalog.assets)

    if previous is not None:
        previous = apply_renames(catalog, previous)
    _carry_previous(catalog, previous, present_ids, issues)
    for profile in profiles or []:
        extra_rules.extend(getattr(profile, "folder_rules", []))
    if previous:
        catalog.folder_rules = copy.deepcopy(previous.folder_rules)
    apply_folder_rules(catalog, extra_rules)
    if previous is not None and previous.variants:  # after the rules: a variant has its
        from rpggen.core import variants as variants_mod  # source's effective facets

        generated.update(
            variants_mod.apply(catalog, previous.variants, pack_roots, issues, previous)
        )
    from rpggen.core import lpc_compose

    if (previous is not None and previous.characters) or lpc_compose.bodies(catalog):
        # LPC characters: a body with its layers drawn over it, rendered again from the packs
        generated.update(
            lpc_compose.apply(
                catalog,
                previous.characters if previous is not None else None,
                pack_roots,
                issues,
                previous,
            )
        )
    _add_objects(catalog, objects_raw, previous)
    # the things cut from a sheet set aside as another form are set aside too (T17.29: the
    # 16 000 objects of *Modern Farm*'s sheets at three sizes and in a complete set)
    by_id = {a.id: a for a in catalog.assets}
    for obj in catalog.objects:
        sheet = by_id.get(obj.sheet) if obj.source == "auto" else None
        if sheet is not None and _another_form(sheet) and obj.status != "CONFIRMED":
            obj.status = "UNUSED"
        elif (
            sheet is not None
            and sheet.pack_id in farm_ids
            and obj.status != "CONFIRMED"
            and effective(sheet).get("role") == "NONE"
            and classifier.UNUSED_TAG + pack_forms.MANY_BUILDINGS
            not in (effective(sheet).get("tags") or [])
        ):
            obj.status = "UNUSED"  # the things of a sheet set aside in a farming pack
        if sheet is not None and sheet.pack_id in farm_ids and obj.role == "BUILDING":
            # in a farming pack a large thing of a sheet of bridges or fences is no house: the
            # village of *Farm RPG* had its bridge as the house to walk into (T17.29)
            words = set(classifier.tokens(sheet.path)[0]) | set(classifier.tokens(sheet.path)[1])
            if words & NOT_A_HOUSE_WORDS and not words & HOUSE_WORDS:
                obj.role = "DECORATION"
    assign_tilesets(catalog, previous, adapter_tilesets)
    terrain.attach_terrain_sets(catalog, terrain_result)
    resolve_maps(catalog, maps_raw, previous, issues)
    for asset in catalog.assets:
        asset.status = recompute_status(
            asset,
            file_missing=asset.status == "MISSING",
            user_confirmed=asset.status == "CONFIRMED",
        )
    catalog.assets.sort(key=lambda a: _sort_key(a.id))
    return catalog, issues, generated


# --------------------------------------------------------------------------- maps (T12.49)

EMPTY_CELL = (-1, 0, 0, 0)  # source id, atlas column, atlas row, transform bits


def _previous_solid(previous: Catalog | None) -> dict[tuple[str, str, int], bool]:
    """The solid flag of every IntGrid value of the previous catalog: the user's choice stays."""
    out: dict[tuple[str, str, int], bool] = {}
    for m in previous.maps if previous else []:
        for layer in m.get("layers", []):
            for v in layer.get("values", []):
                out[(m["id"], layer["name"], int(v["value"]))] = bool(v["solid"])
    return out


ISO_MAP_EMPTY = (-1, 0)  # an isometric map's cell: picture index, transform bits


def map_projection(imported_map: dict[str, Any]) -> str:
    """How an imported map is drawn: ``isometric`` for a Tiled map of diamonds (T17.28), else
    ``top_down`` (a map of squares says nothing of its view)."""
    found = imported_map.get("projection")
    return PROJECTION_ISOMETRIC if found == PROJECTION_ISOMETRIC else "top_down"


def map_fits(imported_map: dict[str, Any], projection: str) -> bool:
    """Whether an imported map can be a map of a project seen in ``projection`` (T17.28): an
    isometric map only of an isometric project, a map of squares only of one seen from above."""
    wanted = PROJECTION_ISOMETRIC if projection == PROJECTION_ISOMETRIC else "top_down"
    return map_projection(imported_map) == wanted


def _iso_picture(
    catalog: Catalog, pack_id: str, image: str, by_path: dict[str, Asset]
) -> Asset | None:
    """The isometric picture of the catalog a Tiled tile shows (T17.28): the asset of its own
    file when that was read as isometric, else one of the same bytes that was (a sample that
    ships copies of the pack's pictures), the first by id; None when neither."""
    own = by_path.get(f"assets/packs/{pack_id}/{image}")
    if own is not None and effective(own).get("projection") == PROJECTION_ISOMETRIC:
        return own
    if own is None:
        return None
    twins = [
        a
        for a in catalog.assets
        if a.sha256 == own.sha256
        and a.kind == "image"
        and "#" not in a.id
        and effective(a).get("projection") == PROJECTION_ISOMETRIC
    ]
    return min(twins, key=lambda a: _sort_key(a.id)) if twins else None


def _blocks(asset: Asset, image: str) -> bool:
    """Whether a picture an isometric map paints blocks its diamond: its role is WALL, or it is
    unused (a picture of a pack's samples, T17.28) and its name and shape say WALL."""
    from rpggen.core import classifier

    facets = effective(asset)
    role = facets.get("role")
    if role == "WALL":
        return True
    if role != "NONE":
        return False
    plain = {k: v for k, v in asset.detected.items() if k not in ("role", "roles_alt", "tags")}
    return classifier.classify(plain, image, None)[0] == "WALL"


def _iso_map(
    catalog: Catalog,
    pack_id: str,
    raw: dict[str, Any],
    map_id: str,
    source: str,
    issues: IssueList,
) -> dict[str, Any] | None:
    """The catalog map of an isometric Tiled map (T17.28). Its tile layers are ``iso_tiles``:
    ``pictures`` lists the asset ids of the isometric pictures it paints, and ``cells`` is
    run-length encoded row by row as ``[count, picture index, transform]`` (index -1 for an
    empty cell); ``offset`` is how far Tiled draws the layer from its place, when it does. The
    map says ``projection: isometric`` and lists the pictures that block (``walls``). A layer
    none of whose tiles is an isometric picture is skipped with TILE-009."""
    from rpggen.core.adapters import maps as maps_mod

    width, height = int(raw["size"][0]), int(raw["size"][1])
    by_path = {a.path: a for a in catalog.assets if "#" not in a.id}
    chosen: dict[str, Asset | None] = {}
    layers: list[dict[str, Any]] = []
    walls: set[str] = set()
    for layer in raw["layers"]:
        if layer["kind"] != "tiles":
            layers.append({"name": layer["name"], "kind": "objects", "objects": layer["objects"]})
            continue
        cells: dict[tuple[int, int], tuple[str, int]] = {}
        for x, y, image, _col, _row, alt in layer["tiles"]:
            if image not in chosen:
                chosen[image] = _iso_picture(catalog, pack_id, image, by_path)
            asset = chosen[image]
            if asset is not None and 0 <= x < width and 0 <= y < height:
                cells[(x, y)] = (asset.id, int(alt))
                if _blocks(asset, image):
                    walls.add(asset.id)
        if not cells:
            issues.add(
                "TILE-009", file=source, layer=layer["name"], map=map_id,
                reason="its tiles are not isometric pictures of the packs",
            )  # fmt: skip
            continue
        pictures = sorted({asset_id for asset_id, _alt in cells.values()}, key=_sort_key)
        index = {asset_id: i for i, asset_id in enumerate(pictures)}
        grid = [
            (index[cells[(x, y)][0]], cells[(x, y)][1]) if (x, y) in cells else ISO_MAP_EMPTY
            for y in range(height)
            for x in range(width)
        ]
        found: dict[str, Any] = {
            "name": layer["name"],
            "kind": "iso_tiles",
            "pictures": pictures,
            "cells": maps_mod.rle(grid),
        }
        if layer.get("offset"):
            found["offset"] = list(layer["offset"])
        layers.append(found)
    if not any(layer["kind"] == "iso_tiles" for layer in layers):
        return None
    return {
        "id": map_id,
        "pack_id": pack_id,
        "source": source,
        "format": raw["format"],
        "tile_size": list(raw["tile_size"]),
        "size": [width, height],
        "layers": layers,
        "projection": PROJECTION_ISOMETRIC,
        "walls": sorted(walls, key=_sort_key),
    }


def resolve_maps(
    catalog: Catalog,
    maps_raw: list[tuple[str, dict[str, Any]]],
    previous: Catalog | None,
    issues: IssueList,
) -> None:
    """Fill ``catalog.maps`` from the raw maps of the adapters.

    A catalog map is ``{id, pack_id, source, format, tile_size, size, layers}``; a layer is
    ``{name, kind: tiles, tileset, cells}`` (``cells`` is run-length encoded row by row:
    ``[count, source_id, column, row, transform]``, source id -1 for an empty cell),
    ``{name, kind: intgrid, cells, values}`` (runs ``[count, value]``; ``values`` lists
    ``{value, name, solid}``) or ``{name, kind: objects, objects}`` (markers). A layer whose
    tiles belong to several tile sets becomes one layer per tile set. A layer whose tile sheets
    are in no tile set is skipped with TILE-009.
    """
    from rpggen.core.adapters import maps as maps_mod

    asset_of = {a.path: a.id for a in catalog.assets if "#" not in a.id}
    sheet_of = {
        src["asset"]: (tdef.name, int(src["source_id"]))
        for tdef in catalog.tilesets
        for src in tdef.sources
    }
    solid_before = _previous_solid(previous)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for pack_id, raw in maps_raw:
        base = ids.asset_id(pack_id, raw["source"])
        if raw.get("format") == "ldtk":
            base += "." + ids.slug(raw["name"])
        map_id, n = base, 1
        while map_id in seen:
            n += 1
            map_id = f"{base}__{n}"
        seen.add(map_id)
        width, height = int(raw["size"][0]), int(raw["size"][1])
        source = f"assets/packs/{pack_id}/{raw['source']}"
        if raw.get("projection") == PROJECTION_ISOMETRIC:
            found = _iso_map(catalog, pack_id, raw, map_id, source, issues)
            if found is not None:
                out.append(found)
            continue
        layers: list[dict[str, Any]] = []
        for layer in raw["layers"]:
            kind = layer["kind"]
            if kind == "tiles":
                by_sheet: dict[str, dict[tuple[int, int], tuple[int, int, int, int]]] = {}
                lost = 0
                for x, y, image, col, row, alt in layer["tiles"]:
                    ref = sheet_of.get(asset_of.get(f"assets/packs/{pack_id}/{image}", ""))
                    if ref is None:
                        lost += 1
                    elif 0 <= x < width and 0 <= y < height:
                        by_sheet.setdefault(ref[0], {})[(x, y)] = (ref[1], col, row, alt)
                if not by_sheet:
                    issues.add(
                        "TILE-009", file=source, layer=layer["name"], map=map_id,
                        reason="its tile sheets are not part of a tile set",
                    )  # fmt: skip
                    continue
                for tileset_name, cells in by_sheet.items():
                    grid = [
                        cells.get((x, y), EMPTY_CELL) for y in range(height) for x in range(width)
                    ]
                    name = (
                        layer["name"] if len(by_sheet) == 1 else f"{layer['name']} ({tileset_name})"
                    )
                    layers.append(
                        {
                            "name": name,
                            "kind": "tiles",
                            "tileset": tileset_name,
                            "cells": maps_mod.rle(grid),
                        }
                    )
            elif kind == "intgrid":
                values = [
                    {
                        "value": int(v["value"]),
                        "name": v["name"],
                        "solid": solid_before.get(
                            (map_id, layer["name"], int(v["value"])), v["solid"]
                        ),
                    }
                    for v in layer["values"]
                ]
                cells_int = [(int(v),) for v in layer["data"]]
                layers.append(
                    {
                        "name": layer["name"],
                        "kind": "intgrid",
                        "cells": maps_mod.rle(cells_int),
                        "values": values,
                    }
                )
            else:
                layers.append(
                    {"name": layer["name"], "kind": "objects", "objects": layer["objects"]}
                )
        if layers:
            out.append(
                {
                    "id": map_id,
                    "pack_id": pack_id,
                    "source": source,
                    "format": raw["format"],
                    "tile_size": list(raw["tile_size"]),
                    "size": [width, height],
                    "layers": layers,
                }
            )
    catalog.maps = out


def _variant(asset_id: str) -> str:
    return asset_id.partition("#")[2]


def apply_renames(catalog: Catalog, previous: Catalog) -> Catalog:
    """Match assets whose file the vendor renamed (T5.05).

    A previous asset that is gone from the new pack and whose sha256 equals that of exactly one
    new asset with no counterpart in ``previous`` (same variant suffix) is that asset under a new
    name. Returns a copy of ``previous`` with the renamed assets re-keyed to their new id and path
    (tile set sources and objects follow), so overrides and source ids carry over; the new asset
    records ``renamed_from``.
    """
    known = {a.id for a in previous.assets}
    new_ids = {a.id for a in catalog.assets}
    fresh = [a for a in catalog.assets if a.id not in known]
    renames: dict[str, Asset] = {}
    taken: set[str] = set()
    for old in previous.assets:
        if old.id in new_ids:
            continue
        found = [
            a
            for a in fresh
            if a.sha256 == old.sha256
            and a.pack_id == old.pack_id
            and _variant(a.id) == _variant(old.id)
            and a.id not in taken
        ]
        if len(found) == 1:
            renames[old.id] = found[0]
            taken.add(found[0].id)
    if not renames:
        return previous
    copied = Catalog.from_json(previous.to_json())
    id_map = {old_id: new.id for old_id, new in renames.items()}
    for asset in copied.assets:
        if asset.id in renames:
            new = renames[asset.id]
            asset.renamed_from = asset.path.partition(f"assets/packs/{asset.pack_id}/")[2]
            new.renamed_from = asset.renamed_from
            asset.id, asset.path = new.id, new.path
    for tdef in copied.tilesets:
        for src in tdef.sources:
            src["asset"] = id_map.get(src["asset"], src["asset"])
    for obj in copied.objects:
        if obj.sheet in id_map:
            obj.id = id_map[obj.sheet] + obj.id[len(obj.sheet) :]
            obj.sheet = id_map[obj.sheet]
    return copied


def _carry_previous(
    catalog: Catalog, previous: Catalog | None, present_ids: set[str], issues: IssueList
) -> None:
    """Overrides, confirmations and MISSING assets of the previous catalog (T2.14 steps 5-6)."""
    if previous is None:
        return
    old_packs = {p.pack_id: p for p in previous.packs}
    for pack in catalog.packs:
        if pack.pack_id in old_packs:  # the licence corrections of the Audit page stay
            pack.license_overrides = dict(old_packs[pack.pack_id].license_overrides)
    prev_tile_assets = {src["asset"] for tdef in previous.tilesets for src in tdef.sources}
    for asset in catalog.assets:
        old = previous.asset(asset.id)
        if old is None:
            continue
        asset.overrides = copy.deepcopy(old.overrides)
        if old.status == "CONFIRMED":
            asset.status = "CONFIRMED"
        old_facets, new_facets = effective(old), effective(asset)
        layout_changed = old_facets.get("grid") != new_facets.get("grid") or old_facets.get(
            "size"
        ) != new_facets.get("size")
        if (
            asset.id in prev_tile_assets and new_facets.get("usage") == "tiles" and layout_changed
        ) or old.status == "CONFLICT":
            asset.status = "CONFLICT"
            if old.status != "CONFLICT":
                issues.add("TILE-004", asset=asset.id, file=asset.path)
    variant_ids = {str(v.get("id")) for v in previous.variants}
    for old in previous.assets:
        if old.id in present_ids or old.id in variant_ids:  # variants are rendered again
            continue
        if old.detected_by == "lpc_compose":  # and so are LPC characters
            continue
        kept = Asset.from_json(old.to_json())
        kept.status = "MISSING"
        catalog.assets.append(kept)
        if old.pack_id not in RUN_MADE_PACKS:  # the run that needs it makes it again
            issues.add("CAT-004", asset=old.id, file=old.path)
        if not any(p.pack_id == old.pack_id for p in catalog.packs):
            prev_pack = next((p for p in previous.packs if p.pack_id == old.pack_id), None)
            if prev_pack is not None:
                catalog.packs.append(CatalogPack.from_json(prev_pack.to_json()))


def _add_objects(
    catalog: Catalog, objects_raw: list[tuple[str, dict[str, Any]]], previous: Catalog | None
) -> None:
    """SheetObjects from adapters; user objects of the previous catalog are kept."""
    by_path = {a.path: a for a in catalog.assets if not a.id.count("#")}
    # a profile's objects are the user's decisions: they replace the detection of their sheet
    curated = {(p, o["sheet_path"]) for p, o in objects_raw if o.get("authoritative")}
    objects_raw = [
        (p, o)
        for p, o in objects_raw
        if o.get("authoritative") or (p, o["sheet_path"]) not in curated
    ]
    seen: set[str] = set()
    for pack_id, raw in objects_raw:
        sheet = by_path.get(f"assets/packs/{pack_id}/{raw['sheet_path']}")
        if sheet is None:
            continue
        base = f"{sheet.id}#{ids.slug(raw['name'])}"
        object_id, n = base, 1
        while object_id in seen:
            n += 1
            object_id = f"{base}__{n}"
        seen.add(object_id)
        obj = SheetObject(
            id=object_id,
            sheet=sheet.id,
            name=raw["name"],
            role=raw["role"],
            region=list(raw["region"]),
            origin=list(raw["origin"]),
            footprint=list(raw["footprint"]),
            collision=copy.deepcopy(raw["collision"]),
            tags=list(raw.get("tags", [])),
            status=raw.get("status", "AUTO_DETECTED"),
            source=raw.get("source", "auto"),
            door=list(raw["door"]) if raw.get("door") else None,
        )
        from rpggen.core import classifier

        for tag in (*classifier.suggested_tags(obj.name), *classifier.side_view_tags(obj.name)):
            if tag not in obj.tags:
                obj.tags.append(tag)
        catalog.objects.append(obj)
    if previous:
        _carry_objects(catalog, previous)


def _carry_objects(catalog: Catalog, previous: Catalog) -> None:
    """User objects, rejected suggestions (role NONE) and confirmed suggestions survive."""
    for old in previous.objects:
        same = [
            o
            for o in catalog.objects
            if o.id == old.id or (o.sheet == old.sheet and o.region == old.region)
        ]
        if old.source == "user" or old.role == "NONE":
            # the user's version replaces whatever detection produced for the same object
            catalog.objects = [o for o in catalog.objects if o not in same]
            catalog.objects.append(SheetObject.from_json(old.to_json()))
        elif old.status == "CONFIRMED":
            for obj in same:
                if obj.source != "user" and obj.region == old.region:
                    obj.status = "CONFIRMED"

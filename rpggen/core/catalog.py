from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import __version__, ids, jsonio, schema
from rpggen.core.adapters.base import AssetFragment
from rpggen.core.archive import OpenedPack
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


def assign_tilesets(
    catalog: Catalog,
    previous: Catalog | None,
    adapter_tilesets: list[dict[str, Any]] | None = None,
) -> None:
    """Group tile sheets into TileSetDefs and allocate source ids (never renumbered)."""
    prev_defs = {t.name: t for t in previous.tilesets} if previous else {}
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
        if effective(a).get("usage") == "tiles" and a.status != "MISSING"
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
    catalog.tilesets = [defs[n] for n in sorted(defs, key=_sort_key)]


# --------------------------------------------------------------------------- assembly


def _merge_fragments(
    fragments: list[tuple[int, AssetFragment]],
) -> tuple[dict[str, Any], float, int]:
    """Merge fragments for one asset: full claims first, then confidence; first value wins."""
    ordered = sorted(
        fragments,
        key=lambda item: (item[1].claim != "full", -item[1].confidence, item[0]),
    )
    facets: dict[str, Any] = {}
    for _, frag in ordered:
        for key, value in frag.facets.items():
            facets.setdefault(key, copy.deepcopy(value))
    first = min(index for index, _ in fragments)
    return facets, max(f.confidence for _, f in fragments), first


def _license_files(inv: Inventory, root: str) -> list[str]:
    return sorted((f"{root}/{f.path}" for f in inv.files if f.kind == "license"), key=_sort_key)


def assemble(
    packs: list[tuple[OpenedPack, Inventory]],
    previous: Catalog | None,
    profiles: list[Any] | None = None,
    *,
    work_dir: Path | None = None,
    use_cache: bool = True,
) -> tuple[Catalog, IssueList, dict[str, str]]:
    """Run adapters, classify and merge everything into a Catalog.

    Returns ``(catalog, issues, generated_files)`` where generated_files maps project-relative
    paths (GIF strips) to the absolute files the installer must copy.
    """
    from rpggen.core import adapters, classifier, terrain
    from rpggen.core.analyzer import analyzer_for

    adapters.register_defaults()
    issues = IssueList()
    catalog = Catalog()
    generated: dict[str, str] = {}
    adapter_tilesets: list[dict[str, Any]] = []
    objects_raw: list[tuple[str, dict[str, Any]]] = []  # (pack_id, adapter object dict)
    present_ids: set[str] = set()
    all_results: dict[str, list[Any]] = {}
    extra_rules: list[FolderRule] = []
    pack_roots: dict[str, Path] = {}

    for opened, inv in sorted(packs, key=lambda pair: _sort_key(pair[1].pack_id)):
        pack_id = inv.pack_id
        root = f"assets/packs/{pack_id}"
        pack_roots[pack_id] = opened.root
        issues.extend(opened.issues)
        issues.extend(i for i in inv.issues if i not in opened.issues)
        ctx = adapters.AdapterContext(
            pack_id=pack_id,
            analyze=analyzer_for(inv, opened.root, use_cache=use_cache),
            work_dir=work_dir,
        )
        results = adapters.run_adapters(inv, opened.root, ctx)
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

        # collect fragments per (path, variant)
        by_key: dict[tuple[str, str], list[tuple[int, AssetFragment]]] = {}
        for index, res in enumerate(results):
            for frag in res.assets:
                by_key.setdefault((frag.path, frag.variant), []).append((index, frag))

        paths_sorted = [f.path for f in inv.files if f.kind == "image"]
        base_ids = ids.disambiguate([ids.asset_id(pack_id, p) for p in paths_sorted])
        id_for_path = dict(zip(paths_sorted, base_ids, strict=True))
        files = {f.path: f for f in inv.files}
        for path in paths_sorted:
            variants = sorted(v for (p, v) in by_key if p == path)
            for variant in variants:
                facets, confidence, first = _merge_fragments(by_key[(path, variant)])
                detected_by = results[first].adapter
                role_conf = None
                if "role" not in facets:
                    role, role_conf, alt = classifier.classify(facets, path, None)
                    facets["role"] = role
                    if alt:
                        facets["roles_alt"] = alt
                if role_conf is not None:
                    confidence = min(confidence, role_conf)
                f = files[path]
                if f.image:
                    facets["size"] = [f.image["w"], f.image["h"]]
                asset_id = id_for_path[path] + (f"#{variant}" if variant else "")
                catalog.assets.append(
                    Asset(
                        id=asset_id,
                        pack_id=pack_id,
                        path=f"{root}/{path}",
                        sha256=f.sha256,
                        kind="image",
                        status="AUTO_DETECTED",
                        detected=facets,
                        detected_by=detected_by,
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
            asset_id = ids.asset_id(pack_id, f.path)
            catalog.assets.append(
                Asset(asset_id, pack_id, f"{root}/{f.path}", f.sha256, f.kind, "AUTO_DETECTED",
                      facets, {}, "inventory", role_conf)
            )  # fmt: skip
            present_ids.add(asset_id)

        licenses = _license_files(inv, root)
        if not licenses:
            issues.add("ASSET-021", pack_id=pack_id, file=root)
        catalog.packs.append(
            CatalogPack(
                pack_id,
                inv.source_sha256,
                root,
                licenses,
                [r.adapter for r in results if r.assets or r.objects or r.tilesets],
                next((r.profile_id for r in results if r.profile_id), None),
                sorted(set(warnings)),
            )
        )

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
    _add_objects(catalog, objects_raw, previous)
    assign_tilesets(catalog, previous, adapter_tilesets)
    terrain.attach_terrain_sets(catalog, terrain_result)
    for asset in catalog.assets:
        asset.status = recompute_status(
            asset,
            file_missing=asset.status == "MISSING",
            user_confirmed=asset.status == "CONFIRMED",
        )
    catalog.assets.sort(key=lambda a: _sort_key(a.id))
    return catalog, issues, generated


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
    for old in previous.assets:
        if old.id in present_ids:
            continue
        kept = Asset.from_json(old.to_json())
        kept.status = "MISSING"
        catalog.assets.append(kept)
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

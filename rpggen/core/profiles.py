"""Pack profiles: shareable files that carry a user's audit decisions for a known pack."""

from __future__ import annotations

import copy
import logging
import shutil
from pathlib import Path
from typing import Any

from rpggen import ids, jsonio, paths, schema
from rpggen.core import catalog as catalog_mod
from rpggen.core.inventory import Inventory
from rpggen.errors import RpgGenError

log = logging.getLogger(__name__)

PROFILE_VERSION = 1
PROFILE_SUFFIX = ".rpgprofile.json"
FINGERPRINT_FILES = 20
DEFAULT_MIN_MATCH = 0.8
DEFAULT_LICENSE = "CC0-1.0"
_DROPPED_FACETS = {"roles_alt"}


def profiles_dir() -> Path:
    return paths.data_dir() / "profiles"


def _pack_relative(asset: catalog_mod.Asset, pack_id: str) -> str:
    prefix = f"assets/packs/{pack_id}/"
    return asset.path[len(prefix) :] if asset.path.startswith(prefix) else asset.path


def asset_key(asset: catalog_mod.Asset, pack_id: str) -> str:
    """The profile key of an asset: its pack-relative path, plus ``#<variant>`` for the
    per-character / per-face assets cut from one file."""
    variant = asset.id.split("#", 1)[1] if "#" in asset.id else ""
    rel = _pack_relative(asset, pack_id)
    return f"{rel}#{variant}" if variant else rel


def split_key(key: str) -> tuple[str, str]:
    path, _, variant = key.partition("#")
    return path, variant


def fingerprint(inv: Inventory, min_match: float = DEFAULT_MIN_MATCH) -> dict[str, Any]:
    """The largest image files by pixel count (ties broken by path) with their hashes."""
    images = [f for f in inv.files if f.kind == "image" and f.image]
    images.sort(key=lambda f: (-(f.image["w"] * f.image["h"]), f.path))  # type: ignore[index]
    return {
        "required_files": {f.path: f.sha256 for f in images[:FINGERPRINT_FILES]},
        "min_match": min_match,
    }


def export_profile(
    catalog: catalog_mod.Catalog,
    pack_id: str,
    inventory: Inventory,
    meta: dict[str, str],
) -> dict[str, Any]:
    """The profile of one pack: assets with overrides or CONFIRMED status, its objects, folder
    rules and tile set definitions, and a fingerprint of the pack's largest images."""
    title = meta.get("title", "").strip() or pack_id
    out_assets: dict[str, Any] = {}
    key_of: dict[str, str] = {}
    for asset in sorted(catalog.assets, key=lambda a: a.id):
        if asset.pack_id != pack_id or asset.status == "MISSING":
            continue
        key = asset_key(asset, pack_id)
        key_of[asset.id] = key
        if asset.overrides or asset.status == "CONFIRMED":
            facets = copy.deepcopy(catalog_mod.effective(asset))
            out_assets[key] = {k: v for k, v in facets.items() if k not in _DROPPED_FACETS}
            if isinstance(out_assets[key].get("audio"), dict):  # measured, not a decision
                out_assets[key]["audio"].pop("duration_s", None)

    objects: list[dict[str, Any]] = []
    for obj in sorted(catalog.objects, key=lambda o: o.id):
        sheet_key = key_of.get(obj.sheet)
        if sheet_key is None:
            continue
        data = obj.to_json()
        data.pop("id")
        data.pop("sheet")
        data["sheet_path"] = sheet_key
        objects.append(data)

    rules = [r.to_json() for r in catalog.folder_rules if r.pack_id == pack_id]

    tilesets: list[dict[str, Any]] = []
    for tdef in catalog.tilesets:
        sources = [{"asset": key_of[s["asset"]]} for s in tdef.sources if s["asset"] in key_of]
        if not sources:
            continue
        data = tdef.to_json()
        data["sources"] = sources
        tilesets.append(data)

    profile: dict[str, Any] = {
        "profile_version": PROFILE_VERSION,
        "profile_id": meta.get("profile_id") or ids.slug(title),
        "title": title,
        "fingerprint": fingerprint(inventory),
        "assets": out_assets,
        "objects": objects,
        "folder_rules": rules,
        "tilesets": tilesets,
        "author": meta.get("author", ""),
        "license": meta.get("license") or DEFAULT_LICENSE,
    }
    schema.validate("profile", profile)
    return profile


def match_profile(profile: dict[str, Any], inventory: Inventory) -> float:
    """The fraction of fingerprint files present with an identical sha256."""
    required: dict[str, str] = profile["fingerprint"]["required_files"]
    if not required:
        return 0.0
    have = {f.path: f.sha256 for f in inventory.files}
    return sum(1 for p, digest in required.items() if have.get(p) == digest) / len(required)


def write_profile(profile: dict[str, Any], path: Path) -> None:
    schema.validate("profile", profile)
    jsonio.write(path, profile)


def load_profile(path: Path) -> dict[str, Any]:
    data = jsonio.read(path)
    schema.validate("profile", data)
    return data  # type: ignore[no-any-return]


def installed() -> list[dict[str, Any]]:
    """Valid profiles in the profiles directory (invalid files are skipped), by file name."""
    folder = profiles_dir()
    if not folder.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(folder.glob(f"*{PROFILE_SUFFIX}")):
        try:
            found.append(load_profile(path))
        except (RpgGenError, OSError, ValueError):
            log.warning("ignoring invalid profile %s", path, exc_info=True)
    return found


def install_profile(path: Path) -> dict[str, Any]:
    """Validate ``path`` and copy it into the profiles directory; returns the profile."""
    profile = load_profile(path)
    folder = profiles_dir()
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, folder / f"{ids.slug(profile['profile_id'])}{PROFILE_SUFFIX}")
    return profile


def best_match(inventory: Inventory) -> tuple[float, dict[str, Any] | None]:
    """The installed profile that matches ``inventory`` best (ratio >= its ``min_match``)."""
    best: tuple[float, dict[str, Any] | None] = (0.0, None)
    for profile in installed():
        ratio = match_profile(profile, inventory)
        if ratio >= profile["fingerprint"]["min_match"] and ratio > best[0]:
            best = (ratio, profile)
    return best

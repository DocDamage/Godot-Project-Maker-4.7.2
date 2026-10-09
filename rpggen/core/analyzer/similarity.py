"""Which images look alike (T13.04).

Every analysed image has a 64-bit difference hash (``image_facts.dhash``) among its cached
facts, keyed by the file's hash like the rest of the analysis. Two pictures are near when few
bits differ. Nothing here changes a role or a usage: the audit page selects similar assets so a
bulk edit applies to them, and ``mark_duplicates`` adds an informational tag.
"""

from __future__ import annotations

from typing import Any

from rpggen.core import cache
from rpggen.core import catalog as catalog_mod
from rpggen.core.analyzer import ANALYZER_VERSION

MAX_DISTANCE = 10  # "similar": what Select similar selects
DUPLICATE_DISTANCE = 2  # "the same picture" across two packs
DUPLICATE_TAG = "duplicate_of:"
# A flat or nearly flat picture hashes to (almost) all zeros or ones, whatever its colour: such a
# hash says nothing, so it never makes two files duplicates.
MIN_BITS, MAX_BITS = 6, 58


def distance(a: str, b: str) -> int:
    """How many of the 64 bits of two hashes (hex, as cached) differ."""
    return (int(a, 16) ^ int(b, 16)).bit_count()


def informative(value: str) -> bool:
    return MIN_BITS <= int(value, 16).bit_count() <= MAX_BITS


def hash_of(asset: catalog_mod.Asset) -> str | None:
    """The cached hash of an image asset; None for audio and fonts, and for an image whose
    analysis is not in the cache (it was cleared, or the run did not use it)."""
    if asset.kind != "image" or not asset.sha256:
        return None
    entry = cache.get(asset.sha256, ANALYZER_VERSION)
    value = entry.get("dhash") if entry else None
    return value if isinstance(value, str) else None


def hashes_of(catalog: catalog_mod.Catalog) -> dict[str, str]:
    """``asset id -> hash`` of every image of the catalog that has one (one cache read a file)."""
    by_file: dict[str, str | None] = {}
    out: dict[str, str] = {}
    for asset in catalog.assets:
        if asset.kind != "image":
            continue
        if asset.sha256 not in by_file:
            by_file[asset.sha256] = hash_of(asset)
        value = by_file[asset.sha256]
        if value is not None:
            out[asset.id] = value
    return out


def near(
    catalog: catalog_mod.Catalog,
    asset_id: str,
    max_distance: int = MAX_DISTANCE,
    hashes: dict[str, str] | None = None,
) -> list[tuple[str, int]]:
    """The other assets at most ``max_distance`` bits from ``asset_id``, nearest first (then by
    id), each with its distance. Empty for a sound, a font or an image without a cached hash."""
    hashes = hashes_of(catalog) if hashes is None else hashes
    mine = hashes.get(asset_id)
    if mine is None:
        return []
    found = [(other, distance(mine, value)) for other, value in hashes.items() if other != asset_id]
    return sorted((pair for pair in found if pair[1] <= max_distance), key=lambda p: (p[1], p[0]))


def _size(asset: catalog_mod.Asset) -> tuple[int, int] | None:
    size = asset.detected.get("size")
    return (int(size[0]), int(size[1])) if size else None


def mark_duplicates(catalog: catalog_mod.Catalog, hashes: dict[str, str]) -> list[str]:
    """Tag the later of two files that show the same picture with ``duplicate_of:<id>`` and
    return the ids that were tagged. "The same": of the same size and, in two different packs,
    at most ``DUPLICATE_DISTANCE`` bits apart with a hash that says something; in one pack only
    a byte-identical file (a pack's own tiles are often near each other on purpose). The tag is
    information for the audit's Why line; no role or usage changes."""
    first_by_bytes: dict[tuple[str, str], catalog_mod.Asset] = {}  # (pack, sha256) -> first
    seen: dict[tuple[int, int], list[tuple[catalog_mod.Asset, int]]] = {}  # size -> (asset, hash)
    tagged: list[str] = []
    files_done: set[tuple[str, str]] = set()  # (pack, path): the variants of a file count once
    for asset in catalog.assets:
        size = _size(asset)
        if asset.kind != "image" or size is None or (asset.pack_id, asset.path) in files_done:
            continue
        files_done.add((asset.pack_id, asset.path))
        original: catalog_mod.Asset | None = first_by_bytes.get((asset.pack_id, asset.sha256))
        value = hashes.get(asset.id)
        number = int(value, 16) if value is not None and informative(value) else None
        if original is None and number is not None:
            best = DUPLICATE_DISTANCE + 1
            for other, other_number in seen.get(size, []):
                if other.pack_id == asset.pack_id:
                    continue
                apart = (number ^ other_number).bit_count()
                if apart < best:
                    original, best = other, apart
        if original is not None:
            tags: list[Any] = list(asset.detected.get("tags") or [])
            asset.detected["tags"] = sorted({*tags, DUPLICATE_TAG + original.id})
            tagged.append(asset.id)
            continue  # a copy is not what later files are compared with
        first_by_bytes[(asset.pack_id, asset.sha256)] = asset
        if number is not None:
            seen.setdefault(size, []).append((asset, number))
    return tagged


def duplicate_of(asset: catalog_mod.Asset) -> str | None:
    """The id an asset's ``duplicate_of:`` tag names, or None."""
    for tag in catalog_mod.effective(asset).get("tags") or []:
        if isinstance(tag, str) and tag.startswith(DUPLICATE_TAG):
            return tag[len(DUPLICATE_TAG) :]
    return None

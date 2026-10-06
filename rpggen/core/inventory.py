from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from rpggen import jsonio, paths, schema
from rpggen.core import archive as archive_mod
from rpggen.core.archive import OpenedPack
from rpggen.core.config import hash_file_list
from rpggen.errors import Issue, IssueList

log = logging.getLogger(__name__)

INVENTORY_VERSION = 1
POOL_THRESHOLD = 32  # use a process pool only for packs with at least this many files

EXT_KIND = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".bmp": "image",
    ".gif": "image",
    ".wav": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".ttf": "font",
    ".otf": "font",
    ".fnt": "font",
    ".txt": "doc",
    ".md": "doc",
    ".pdf": "doc",
    ".html": "doc",
    ".tsx": "metadata",
    ".tmx": "metadata",
    ".tsj": "metadata",
    ".tmj": "metadata",
    ".json": "metadata",
    ".ldtk": "metadata",
    ".aseprite": "metadata",
    ".ase": "metadata",
    ".xml": "metadata",
    ".rpgproject": "metadata",
}
LICENSE_PREFIXES = ("license", "licence", "credits", "readme", "copying", "attribution")


@dataclass(frozen=True, slots=True)
class InventoryFile:
    path: str
    sha256: str
    size: int
    ext: str
    kind: str
    image: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "ext": self.ext,
            "kind": self.kind,
        }
        if self.image is not None:
            out["image"] = dict(self.image)
        return out

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> InventoryFile:
        return cls(d["path"], d["sha256"], d["size"], d["ext"], d["kind"], d.get("image"))


@dataclass(slots=True)
class Inventory:
    pack_id: str
    source_sha256: str
    files: list[InventoryFile] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)  # in memory only

    def to_json(self) -> dict[str, Any]:
        return {
            "inventory_version": INVENTORY_VERSION,
            "pack_id": self.pack_id,
            "source_sha256": self.source_sha256,
            "files": [f.to_json() for f in self.files],
            "skipped": [dict(s) for s in self.skipped],
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Inventory:
        return cls(
            d["pack_id"],
            d["source_sha256"],
            [InventoryFile.from_json(f) for f in d["files"]],
            [dict(s) for s in d["skipped"]],
        )

    def file(self, path: str) -> InventoryFile | None:
        return next((f for f in self.files if f.path == path), None)


def classify_kind(rel_path: str) -> str:
    """Kind of a file by extension; license-like names win over the extension."""
    name = rel_path.rsplit("/", 1)[-1]
    stem, _, _ = name.rpartition(".")
    stem = (stem or name).casefold()
    if stem.startswith(LICENSE_PREFIXES):
        return "license"
    ext = os.path.splitext(name)[1].lower()
    return EXT_KIND.get(ext, "other")


def _image_facts(path: Path) -> dict[str, Any] | None:
    """Header-level facts only (no pixel decoding). None when Pillow cannot read the header."""
    try:
        with Image.open(path) as im:
            mode = im.mode
            has_alpha = mode in ("RGBA", "LA", "PA") or (mode == "P" and "transparency" in im.info)
            return {
                "w": im.size[0],
                "h": im.size[1],
                "mode": mode,
                "has_alpha": bool(has_alpha),
                "frames": int(getattr(im, "n_frames", 1)),
            }
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return None


def _scan_file(args: tuple[str, str]) -> tuple[str, str, int, dict[str, Any] | None]:
    """Worker: (rel path, absolute path) -> (rel, sha256, size, image facts)."""
    rel, abs_path = args
    h = hashlib.sha256()
    size = 0
    with open(abs_path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
            size += len(chunk)
    kind = classify_kind(rel)
    image = _image_facts(Path(abs_path)) if kind == "image" else None
    return rel, h.hexdigest(), size, image


def _cache_path(source_sha256: str) -> Path:
    return paths.local_cache_dir() / "inventories" / f"{source_sha256}.json"


def _list_files(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    rels: list[str] = []
    skipped: list[dict[str, str]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel == archive_mod.COMPLETE_MARKER or rel.endswith(".partial"):
            continue
        if archive_mod.is_junk(rel):
            skipped.append({"path": rel, "reason": "os_junk"})
            continue
        rels.append(rel)
    rels.sort(key=lambda s: (s.casefold(), s))
    skipped.sort(key=lambda s: (s["path"].casefold(), s["path"]))
    return rels, skipped


def build_inventory(pack: OpenedPack) -> Inventory:
    """Inventory of every file in the pack: hashes, sizes, kinds and image facts."""
    if pack.source_sha256:
        cache = _cache_path(pack.source_sha256)
        if cache.exists():
            try:
                data = jsonio.read(cache)
                schema.validate("inventory", data)
                inv = Inventory.from_json(data)
                inv.pack_id = pack.pack_id
                inv.issues = list(pack.issues) + _decode_issues(inv)
                return inv
            except Exception:  # noqa: BLE001 - a corrupt cache entry is just a miss
                log.debug("ignoring unreadable inventory cache %s", cache, exc_info=True)
                cache.unlink(missing_ok=True)

    rels, skipped = _list_files(pack.root)
    jobs = [(rel, str(pack.root / rel)) for rel in rels]
    if len(jobs) >= POOL_THRESHOLD:
        workers = min(8, os.cpu_count() or 1)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_scan_file, jobs, chunksize=8))
    else:
        results = [_scan_file(j) for j in jobs]
    results.sort(key=lambda r: (r[0].casefold(), r[0]))

    files = [
        InventoryFile(
            rel, digest, size, os.path.splitext(rel)[1].lower(), classify_kind(rel), image
        )
        for rel, digest, size, image in results
    ]
    source_sha = pack.source_sha256 or hash_file_list([(f.path, f.sha256) for f in files])
    inv = Inventory(pack.pack_id, source_sha, files, skipped, list(pack.issues))
    inv.issues.extend(_decode_issues(inv))
    cache = _cache_path(source_sha)
    try:
        data = inv.to_json()
        schema.validate("inventory", data)
        jsonio.write(cache, data)
    except OSError:
        log.debug("could not write inventory cache %s", cache, exc_info=True)
    return inv


def _decode_issues(inv: Inventory) -> list[Issue]:
    issues = IssueList()
    for f in inv.files:
        if f.kind == "image" and f.image is None:
            issues.add("ASSET-002", file=f.path)
    return list(issues)

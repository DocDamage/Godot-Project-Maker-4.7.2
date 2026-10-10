from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from rpggen import jsonio, paths, schema
from rpggen.core import archive as archive_mod
from rpggen.core.archive import OpenedPack
from rpggen.core.config import hash_file_list
from rpggen.errors import Issue, IssueList, RpgGenError

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
# What a pack carries that is no asset (T16.21): the resource forks macOS adds to an archive,
# links to a shop page, and the empty file some artists leave in a folder that is not ready.
LINK_EXTENSIONS = (".html", ".htm", ".url", ".webloc")
PLACEHOLDER_STEMS = frozenset({"in development", "coming soon", "placeholder"})


def not_an_asset(rel_path: str, size: int) -> bool:
    """True for a file of a pack that is neither an asset nor a licence text."""
    name = rel_path.rsplit("/", 1)[-1]
    if name.startswith("._"):
        return True
    if classify_kind(rel_path) == "license":
        return False  # an empty LICENSE is still the pack saying something
    stem, ext = os.path.splitext(name)
    return (
        size == 0 or ext.lower() in LINK_EXTENSIONS or stem.strip().casefold() in PLACEHOLDER_STEMS
    )


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


def _scan_batch(batch: list[tuple[str, str]]) -> list[tuple[str, str, int, dict[str, Any] | None]]:
    """Worker: one chunk of files (a future per chunk keeps the pool's overhead small)."""
    return [_scan_file(job) for job in batch]


CHUNK = 8  # files per task of the process pool


def _scan_all(
    jobs: list[tuple[str, str]],
    ctl: archive_mod.Control,
    already_done: int = 0,
    total: int | None = None,
) -> list[tuple[str, str, int, dict[str, Any] | None]]:
    """Hash and probe every file in ``jobs``. A big pack uses a process pool; progress arrives as
    results complete (``already_done`` files came from the cache, ``total`` is the pack's size),
    and a cancel drops the tasks that have not started."""
    count = len(jobs)
    total = already_done + count if total is None else total
    label = "Reading files"
    results: list[tuple[str, str, int, dict[str, Any] | None]] = []
    if count >= POOL_THRESHOLD:
        workers = min(8, os.cpu_count() or 1)
        pool = concurrent.futures.ProcessPoolExecutor(max_workers=workers)
        try:
            futures = [
                pool.submit(_scan_batch, jobs[i : i + CHUNK]) for i in range(0, count, CHUNK)
            ]
            for future in concurrent.futures.as_completed(futures):
                ctl.check()
                results.extend(future.result())
                ctl.report(label, already_done + len(results), total)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
    else:
        for job in jobs:
            ctl.check()
            results.append(_scan_file(job))
            ctl.report(label, already_done + len(results), total)
    return results


def _cache_path(source_sha256: str) -> Path:
    return paths.cache_dir() / "inventories" / f"{source_sha256}.json"


def _list_files(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    rels: list[str] = []
    skipped: list[dict[str, str]] = []
    files, links = archive_mod.walk_files(root)  # never follows a link out of the pack
    skipped.extend({"path": rel, "reason": "link"} for rel in links)
    for rel in files:
        if rel == archive_mod.COMPLETE_MARKER or rel.endswith(".partial"):
            continue
        if archive_mod.is_junk(rel):
            skipped.append({"path": rel, "reason": "os_junk"})
            continue
        try:
            size = (root / rel).stat().st_size
        except OSError:
            size = -1  # unreadable: the scan reports it
        if not_an_asset(rel, size):
            skipped.append({"path": rel, "reason": "not_an_asset"})
            continue
        rels.append(rel)
    rels.sort(key=lambda s: (s.casefold(), s))
    skipped.sort(key=lambda s: (s["path"].casefold(), s["path"]))
    return rels, skipped


FOLDER_CACHE_VERSION = 1


def _folder_cache_path(root: Path) -> Path:
    """``inventories/folder_<sha256(resolved path, case-folded)[:16]>.json``"""
    key = hashlib.sha256(str(Path(root).resolve()).casefold().encode("utf-8")).hexdigest()
    return paths.cache_dir() / "inventories" / f"folder_{key[:16]}.json"


def _load_folder_cache(root: Path) -> dict[str, dict[str, Any]]:
    """What the last build of this folder found, per file: size, mtime_ns, sha256 and image facts.
    Missing, unreadable or of another version: nothing."""
    path = _folder_cache_path(root)
    try:
        data = jsonio.read(path)
    except (OSError, RpgGenError):
        return {}
    if not isinstance(data, dict) or data.get("version") != FOLDER_CACHE_VERSION:
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def _save_folder_cache(root: Path, files: dict[str, dict[str, Any]]) -> None:
    try:
        jsonio.write(
            _folder_cache_path(root),
            {"version": FOLDER_CACHE_VERSION, "root": str(Path(root).resolve()), "files": files},
        )
    except OSError:
        log.debug("could not write the folder cache of %s", root, exc_info=True)


def _stat_key(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def build_inventory(
    pack: OpenedPack,
    *,
    progress: archive_mod.Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    use_cache: bool = True,
) -> Inventory:
    """Inventory of every file in the pack: hashes, sizes, kinds and image facts.

    ``progress`` receives ``("Reading files", done, total)``; ``is_cancelled`` is polled as files
    complete and a cancel raises ``archive.Cancelled``.

    An archive is cached by its hash. A folder is cached by its path: a file whose size and
    modification time are unchanged is not read again, only added or changed files are. (The one
    blind spot: a tool that rewrites a file and keeps both its size and its modification time;
    ``use_cache=False``, the command line's ``--no-cache``, reads everything.)
    """
    ctl = archive_mod.Control(progress, is_cancelled)
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
    folder_cache = _load_folder_cache(pack.root) if use_cache and not pack.source_sha256 else {}
    keys: dict[str, tuple[int, int]] = {}
    known: list[tuple[str, str, int, dict[str, Any] | None]] = []
    jobs: list[tuple[str, str]] = []
    for rel in rels:
        absolute = pack.root / rel
        keys[rel] = _stat_key(absolute)
        entry = folder_cache.get(rel)
        if entry and (entry.get("size"), entry.get("mtime_ns")) == keys[rel]:
            known.append((rel, entry["sha256"], entry["size"], entry.get("image")))
        else:
            jobs.append((rel, str(absolute)))
    ctl.check()
    scanned = _scan_all(jobs, ctl, already_done=len(known), total=len(rels))
    ctl.report("Reading files", len(rels), len(rels))
    results = known + scanned
    results.sort(key=lambda r: (r[0].casefold(), r[0]))
    if not pack.source_sha256:
        _save_folder_cache(
            pack.root,
            {
                rel: {
                    "size": keys[rel][0],
                    "mtime_ns": keys[rel][1],
                    "sha256": digest,
                    "image": image,
                }
                for rel, digest, _size, image in results
            },
        )

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
    for item in inv.skipped:
        if item.get("reason") == "link":
            issues.add("ARCH-009", entry=item["path"])
    return list(issues)

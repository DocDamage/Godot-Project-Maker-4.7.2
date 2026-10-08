"""What rpggen keeps on the user's disk, how much, and what it may delete (T12.10).

Three folders (``paths.config_dir()``, ``data_dir()``, ``cache_dir()``):

* the **cache** holds what can be made again and is bounded: extracted archives by least recent
  use (``cache_limit_gb``, default 10), and analysis, inventories and thumbnails together (1 GB);
* the **data** folder holds what a user would miss: drafts of unfinished audits, installed pack
  profiles, the downloaded Godot and the logs. Only a half-downloaded file of a week ago is ever
  pruned there;
* the **config** folder holds ``settings.json``.

Nothing here raises for a file system problem: pruning is a convenience.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from collections.abc import Iterable
from pathlib import Path

from rpggen import paths

log = logging.getLogger(__name__)

CACHE_ITEMS = (
    "extracted",
    "analysis",
    "inventories",
    "thumbs",
    "gif_strips",
    "frame_strips",
    "terrain_atlases",
)
DATA_ITEMS = ("drafts", "profiles", "godot", "logs")
SMALL_CACHES = ("analysis", "inventories", "thumbs")  # together at most SMALL_CAP_BYTES
SMALL_CAP_BYTES = 1 << 30
DEFAULT_LIMIT_GB = 10.0
PARTIAL_MAX_AGE_S = 7 * 24 * 3600  # a half-downloaded Godot (.part) is dropped after a week
STAMP_SUFFIX = ".last_used"
# What a user loses by clearing a data item (the confirmation lists these).
DATA_LOSSES = {
    "drafts": "your unfinished audits (the drafts of projects you have not generated)",
    "profiles": "the pack profiles you installed or downloaded",
    "godot": "the Godot that rpggen downloaded (it can be downloaded again)",
    "logs": "the logs of earlier runs",
}


# --------------------------------------------------------------------------- sizes


def folder_size(path: Path) -> int:
    """Bytes of every file below ``path`` (links are not followed); 0 when it does not exist."""
    total = 0
    pending = [Path(path)]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def category_folder(name: str) -> Path:
    return (paths.cache_dir() if name in CACHE_ITEMS else paths.data_dir()) / name


def category_sizes() -> dict[str, int]:
    """Bytes per cache category and per data item."""
    return {name: folder_size(category_folder(name)) for name in (*CACHE_ITEMS, *DATA_ITEMS)}


def clear(name: str) -> int:
    """Delete everything in a cache category or data item; returns the bytes freed."""
    if name not in (*CACHE_ITEMS, *DATA_ITEMS):
        raise KeyError(name)
    folder = category_folder(name)
    freed = folder_size(folder)
    shutil.rmtree(folder, ignore_errors=True)
    return freed


# --------------------------------------------------------------------------- migration


def migrate() -> list[str]:
    """Move what the single pre-M12 folder held to its new place, once. Nothing is overwritten:
    an item that already exists at the new place stays where it is. Returns what was moved."""
    legacy = paths.legacy_cache_dir()
    if legacy is None or not legacy.is_dir():
        return []
    moves: list[tuple[Path, Path]] = [
        (legacy / "settings.json", paths.config_dir() / "settings.json"),
        *((legacy / name, paths.data_dir() / name) for name in DATA_ITEMS),
    ]
    if legacy.resolve() != paths.cache_dir().resolve():  # macOS: the caches move as well
        moves += [(legacy / name, paths.cache_dir() / name) for name in CACHE_ITEMS]
    moved: list[str] = []
    for source, target in moves:
        if source.resolve() == target.resolve() or not source.exists() or target.exists():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        except OSError as exc:
            log.warning("could not move %s to %s: %s", source, target, exc)
            continue
        log.info("moved %s to %s", source, target)
        moved.append(f"{source} -> {target}")
    return moved


# --------------------------------------------------------------------------- extracted archives


def stamp_path(extracted: Path) -> Path:
    """The marker file next to ``extracted/<sha>`` that says when it was last used."""
    return extracted.with_name(extracted.name + STAMP_SUFFIX)


def touch_used(extracted: Path) -> None:
    """Remember that an extracted archive was used now (open_pack calls this)."""
    stamp = stamp_path(extracted)
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        os.utime(stamp, None)
    except OSError:
        log.debug("could not stamp %s", stamp, exc_info=True)


def _last_used(extracted: Path) -> float:
    for candidate in (stamp_path(extracted), extracted):
        try:
            return candidate.stat().st_mtime
        except OSError:
            continue
    return 0.0


def prune_extracted(limit_bytes: int, keep: Iterable[Path] = ()) -> list[str]:
    """Delete the least recently used extracted archives until the rest fits in ``limit_bytes``.
    An archive in ``keep`` (the ones in use) is never deleted. Returns the names removed."""
    root = paths.cache_dir() / "extracted"
    if not root.is_dir():
        return []
    protected = {Path(p).resolve() for p in keep}
    entries = [p for p in root.iterdir() if p.is_dir() and not p.name.endswith(".partial")]
    sizes = {p: folder_size(p) for p in entries}
    total = sum(sizes.values())
    removed: list[str] = []
    for folder in sorted(entries, key=_last_used):
        if total <= limit_bytes:
            break
        if folder.resolve() in protected:
            continue
        shutil.rmtree(folder, ignore_errors=True)
        stamp_path(folder).unlink(missing_ok=True)
        total -= sizes[folder]
        removed.append(folder.name)
    live = {p.name for p in root.iterdir() if p.is_dir()}
    for stamp in root.glob("*" + STAMP_SUFFIX):  # a stamp whose folder is gone
        if stamp.name.removesuffix(STAMP_SUFFIX) not in live:
            stamp.unlink(missing_ok=True)
    return removed


# --------------------------------------------------------------------------- small caches


def prune_small_caches(cap_bytes: int = SMALL_CAP_BYTES) -> int:
    """Analysis, inventories and thumbnails share one cap: the oldest files go first. Returns
    the bytes freed."""
    files: list[tuple[float, int, Path]] = []
    for name in SMALL_CACHES:
        base = paths.cache_dir() / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            try:
                if path.is_file() and not path.is_symlink():
                    stat = path.stat()
                    files.append((stat.st_mtime, stat.st_size, path))
            except OSError:
                continue
    total = sum(size for _m, size, _p in files)
    freed = 0
    for _mtime, size, path in sorted(files):
        if total <= cap_bytes:
            break
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        freed += size
    return freed


# --------------------------------------------------------------------------- downloads


def prune_partial_downloads(max_age_s: float = PARTIAL_MAX_AGE_S, now: float | None = None) -> int:
    """Drop ``.part`` files (and their ``.part.json``) of a download that was not resumed in a
    week. Returns how many files were removed."""
    base = paths.data_dir() / "godot"
    if not base.is_dir():
        return 0
    current = time.time() if now is None else now
    removed = 0
    for path in base.rglob("*.part*"):
        try:
            if path.is_file() and current - path.stat().st_mtime > max_age_s:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


# --------------------------------------------------------------------------- everything


def prune(limit_gb: float = DEFAULT_LIMIT_GB, keep: Iterable[Path] = ()) -> dict[str, int]:
    """The routine run at start-up and after an analysis (in a worker). Returns what it did."""
    result = {"extracted": 0, "small_bytes": 0, "partial": 0}
    try:
        result["extracted"] = len(prune_extracted(int(limit_gb * (1 << 30)), keep))
        result["small_bytes"] = prune_small_caches()
        result["partial"] = prune_partial_downloads()
    except OSError:
        log.debug("pruning stopped on a file system error", exc_info=True)
    return result

"""Checks that run before anything is written: the output folder, disk space and the packs."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from rpggen import paths
from rpggen.core import staging
from rpggen.errors import Issue, IssueList

CLOUD_FOLDERS = ("onedrive", "dropbox", "google drive", "icloud")
LONGEST_GENERATED_PATH = 140  # characters the generator appends to the output folder
SPACE_FACTOR = 3  # required free space = 3 x the uncompressed size of the packs
MIN_FREE_MB = 200


def is_rpggen_project(folder: Path) -> bool:
    return (Path(folder) / paths.CONFIG).is_file()


def pack_uncompressed_size(source: Path) -> int:
    """Bytes the pack occupies when extracted; archives are read from their directory."""
    source = Path(source)
    if source.is_dir():
        total = 0
        for p in source.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total
    suffix = source.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(source) as zf:
                return sum(i.file_size for i in zf.infolist())
        if suffix == ".7z":
            import py7zr

            with py7zr.SevenZipFile(source) as sz:
                return sum(int(getattr(f, "uncompressed", 0) or 0) for f in sz.list())
    except Exception:  # noqa: BLE001 - unreadable archives are reported by check_pack
        pass
    try:
        return source.stat().st_size * 4  # rar and unreadable archives: assume 4:1
    except OSError:
        return 0


def pack_stats(source: Path) -> tuple[str, int | None, int | None]:
    """(kind, file count, size in bytes) of a pack; the counts are None when they cannot be
    known without unpacking (7z and rar archives)."""
    source = Path(source)
    try:
        if source.is_dir():
            count = size = 0
            for p in source.rglob("*"):
                if p.is_file():
                    count += 1
                    size += p.stat().st_size
            return "folder", count, size
        kind = source.suffix.lower().lstrip(".") or "file"
        if kind == "zip":
            with zipfile.ZipFile(source) as zf:
                files = [i for i in zf.infolist() if not i.is_dir()]
                return "zip", len(files), sum(i.file_size for i in files)
        return kind, None, source.stat().st_size
    except (OSError, zipfile.BadZipFile):
        return source.suffix.lower().lstrip(".") or "?", None, None


def check_pack(source: Path) -> list[Issue]:
    """Quick readability check: a folder exists; a zip opens and lists its entries."""
    issues = IssueList()
    source = Path(source)
    if not source.exists():
        issues.add("ARCH-001", path=str(source), reason="does not exist")
    elif source.is_file() and source.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(source) as zf:
                zf.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            issues.add("ARCH-001", path=str(source), reason=str(exc))
    elif source.is_file() and source.suffix.lower() not in (".7z", ".rar"):
        issues.add("ARCH-001", path=str(source), reason="not a folder or a zip/7z/rar archive")
    return list(issues)


def _free_bytes(target: Path) -> int:
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def check_target(target: Path, packs: list[Path]) -> list[Issue]:
    """ENV-004 / 005 / 006 / 007 / 008 / 009 for an output folder and the packs it is built from."""
    issues = IssueList()
    target = Path(target).resolve()
    for src in (Path(p).resolve() for p in packs if Path(p).is_dir()):
        if target == src or src in target.parents:
            issues.add("ENV-008")
            break
    if target.exists():
        if not target.is_dir():
            issues.add("ENV-004", path=str(target))
        else:
            leftovers = [
                p
                for p in target.iterdir()
                if p.name not in (staging.STAGING_NAME, staging.FAILED_NAME)
            ]
            if leftovers and not is_rpggen_project(target):
                issues.add("ENV-009", path=str(target))
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not _writable(probe):
        issues.add("ENV-004", path=str(target))
    provider = next((p for p in target.parts if p.lower() in CLOUD_FOLDERS), None)
    if provider:
        issues.add("ENV-006", provider=provider)
    if len(str(target)) + LONGEST_GENERATED_PATH > 260:
        issues.add("ENV-007", length=len(str(target)) + LONGEST_GENERATED_PATH)
    need = max(
        MIN_FREE_MB * 1024 * 1024, SPACE_FACTOR * sum(pack_uncompressed_size(p) for p in packs)
    )
    try:
        free = _free_bytes(target)
    except OSError:
        free = need
    if free < need:
        issues.add("ENV-005", need_mb=need // (1024 * 1024), have_mb=free // (1024 * 1024))
    return list(issues)


def _writable(folder: Path) -> bool:
    import os

    return folder.is_dir() and os.access(folder, os.W_OK)

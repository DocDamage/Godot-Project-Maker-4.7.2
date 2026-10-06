from __future__ import annotations

import contextlib
import hashlib
import logging
import re
import shutil
import subprocess
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from rpggen import ids, jsonio, paths
from rpggen.errors import Issue, IssueList, RpgGenError

log = logging.getLogger(__name__)

LIMITS = dict(
    max_files=200_000,
    max_total_bytes=4 * 1024**3,
    max_entry_bytes=1024**3,
    max_ratio=200,
    ratio_min_bytes=10 * 1024**2,
)
JUNK = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}  # any path part equal to these
_JUNK_FOLDED = {j.casefold() for j in JUNK}
COMPLETE_MARKER = ".complete"
_WIN_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class OpenedPack:
    pack_id: str
    kind: Literal["zip", "7z", "rar", "folder"]
    root: Path  # directory to read files from (extracted cache dir or the folder)
    source_sha256: str  # archive file hash; "" for folders (filled in by the inventory)
    issues: list[Issue]


@dataclass(frozen=True)
class _Entry:
    name: str  # normalized posix name inside the archive
    raw: object  # format specific handle (ZipInfo / py7zr name / rar path)
    size: int
    compressed: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- name handling


def normalize_name(name: str, utf8_flag: bool = True) -> str:
    """Decode (cp437 -> utf-8 repair when the UTF-8 flag is unset), NFC-normalize, use "/"."""
    if not utf8_flag:
        with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
            name = name.encode("cp437").decode("utf-8")
    return unicodedata.normalize("NFC", name).replace("\\", "/")


def check_safe_name(name: str) -> None:
    """Raise ARCH-003 for absolute names, drive letters and ``..`` components."""
    parts = name.split("/")
    if name.startswith("/") or _WIN_DRIVE.match(name) or ".." in parts:
        raise RpgGenError("ARCH-003", entry=name)


def is_junk(name: str) -> bool:
    return any(part.casefold() in _JUNK_FOLDED for part in name.split("/"))


def _sort_key(s: str) -> tuple[str, str]:
    return (s.casefold(), s)


# --------------------------------------------------------------------------- validation


def _select_entries(entries: list[_Entry], issues: IssueList, source: str) -> list[_Entry]:
    """Apply safety rules, limits, junk and case-collision handling; returns entries to extract."""
    if len(entries) > LIMITS["max_files"]:
        raise RpgGenError("ARCH-004", reason=f"more than {LIMITS['max_files']} files", path=source)
    total = 0
    chosen: dict[str, _Entry] = {}
    for entry in sorted(entries, key=lambda e: _sort_key(e.name)):
        check_safe_name(entry.name)
        if is_junk(entry.name):
            issues.add("ARCH-008", entry=entry.name)
            continue
        if entry.size > LIMITS["max_entry_bytes"]:
            raise RpgGenError("ARCH-004", reason=f"entry {entry.name} is too large", path=source)
        if (
            entry.size > LIMITS["ratio_min_bytes"]
            and entry.compressed > 0
            and entry.size / entry.compressed > LIMITS["max_ratio"]
        ):
            raise RpgGenError(
                "ARCH-004",
                reason=f"entry {entry.name} has a suspicious compression ratio",
                path=source,
            )
        total += entry.size
        if total > LIMITS["max_total_bytes"]:
            raise RpgGenError("ARCH-004", reason="total uncompressed size too large", path=source)
        folded = entry.name.casefold()
        if folded in chosen:
            issues.add("ARCH-005", a=chosen[folded].name, b=entry.name, kept=chosen[folded].name)
            continue
        chosen[folded] = entry
    return sorted(chosen.values(), key=lambda e: _sort_key(e.name))


def _inside(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------- zip


def _zip_entries(zf: zipfile.ZipFile) -> list[_Entry]:
    entries: list[_Entry] = []
    for info in zf.infolist():
        if info.flag_bits & 0x1:
            raise RpgGenError("ARCH-002")
        name = normalize_name(info.filename, bool(info.flag_bits & 0x800))
        if name.endswith("/"):
            continue
        entries.append(_Entry(name, info, info.file_size, info.compress_size))
    return entries


def _extract_zip(archive: Path, dest: Path, issues: IssueList) -> None:
    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise RpgGenError("ARCH-001", path=str(archive), reason=str(exc)) from exc
    with zf:
        entries = _select_entries(_zip_entries(zf), issues, str(archive))
        total = 0
        for entry in entries:
            info = entry.raw
            assert isinstance(info, zipfile.ZipInfo)
            target = dest.joinpath(*PurePosixPath(entry.name).parts)
            if not _inside(dest, target):
                raise RpgGenError("ARCH-003", entry=entry.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with zf.open(info) as src, open(target, "wb") as out:
                while chunk := src.read(1024 * 1024):
                    written += len(chunk)
                    total += len(chunk)
                    if written > max(entry.size, 0) or written > LIMITS["max_entry_bytes"]:
                        raise RpgGenError(
                            "ARCH-004", reason=f"entry {entry.name} exceeds its declared size"
                        )
                    if total > LIMITS["max_total_bytes"]:
                        raise RpgGenError("ARCH-004", reason="total uncompressed size too large")
                    out.write(chunk)


# --------------------------------------------------------------------------- 7z


def _extract_7z(archive: Path, dest: Path, issues: IssueList) -> None:
    import py7zr

    try:
        with py7zr.SevenZipFile(archive) as z:
            if z.needs_password():
                raise RpgGenError("ARCH-002")
            infos = z.list()
    except RpgGenError:
        raise
    except Exception as exc:  # noqa: BLE001 - py7zr raises many different error types
        raise RpgGenError("ARCH-001", path=str(archive), reason=str(exc)) from exc
    entries = [
        _Entry(
            normalize_name(i.filename),
            i.filename,
            int(i.uncompressed or 0),
            int(i.compressed or 0) if getattr(i, "compressed", None) else 0,
        )
        for i in infos
        if not i.is_directory
    ]
    allowed = _select_entries(entries, issues, str(archive))
    names = [str(e.raw) for e in allowed]
    # All names were validated above; py7zr extracts only the allowed targets.
    with py7zr.SevenZipFile(archive) as z:
        z.extract(path=dest, targets=names)
    for entry in allowed:
        raw = dest.joinpath(*PurePosixPath(str(entry.raw)).parts)
        norm = dest.joinpath(*PurePosixPath(entry.name).parts)
        if raw != norm and raw.exists() and not norm.exists():
            norm.parent.mkdir(parents=True, exist_ok=True)
            raw.rename(norm)
    _check_extracted_size(dest)


def _check_extracted_size(dest: Path) -> None:
    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    if total > LIMITS["max_total_bytes"]:
        raise RpgGenError("ARCH-004", reason="total uncompressed size too large")


# --------------------------------------------------------------------------- rar via 7-Zip


def find_7z() -> Path | None:
    for candidate in (
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ):
        if candidate.exists():
            return candidate
    found = shutil.which("7z") or shutil.which("7za")
    return Path(found) if found else None


def _parse_7z_listing(text: str) -> list[_Entry]:
    entries: list[_Entry] = []
    block: dict[str, str] = {}
    for line in text.splitlines() + [""]:
        if not line.strip():
            if block.get("Path") and "Attributes" in block and "D" not in block["Attributes"][:1]:
                size = int(block.get("Size") or 0)
                comp = int(block.get("Packed Size") or 0)
                entries.append(_Entry(normalize_name(block["Path"]), block["Path"], size, comp))
            block = {}
            continue
        if " = " in line:
            key, _, value = line.partition(" = ")
            block[key.strip()] = value.strip()
    return entries


def _extract_rar(archive: Path, dest: Path, issues: IssueList) -> None:
    exe = find_7z()
    if exe is None:
        raise RpgGenError("ARCH-007")
    listing = subprocess.run(
        [str(exe), "l", "-slt", str(archive)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if listing.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=listing.stderr.strip()[:200])
    # The first block describes the archive itself ("Type = Rar"): it has no Attributes line.
    entries = _parse_7z_listing(listing.stdout)
    _select_entries(entries, issues, str(archive))
    run = subprocess.run(
        [str(exe), "x", f"-o{dest}", "-y", str(archive)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if run.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=run.stderr.strip()[:200])
    _check_extracted_size(dest)
    for p in sorted(dest.rglob("*")):
        if p.is_file() and is_junk(p.relative_to(dest).as_posix()):
            p.unlink()


# --------------------------------------------------------------------------- nested archives


def _extract_nested(root: Path, issues: IssueList) -> None:
    """Extract every .zip/.7z one level into ``<name>_extracted/`` and remove the archive."""
    nested = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".zip", ".7z")),
        key=lambda p: _sort_key(p.relative_to(root).as_posix()),
    )
    for archive in nested:
        rel = archive.relative_to(root).as_posix()
        dest = archive.with_name(archive.stem + "_extracted")
        dest.mkdir(parents=True, exist_ok=True)
        # Nested archives are only extracted one level: their own nested archives stay files.
        if archive.suffix.lower() == ".zip":
            _extract_zip(archive, dest, issues)
        else:
            _extract_7z(archive, dest, issues)
        archive.unlink()
        issues.add("ARCH-006", entry=rel)


# --------------------------------------------------------------------------- public API

_EXTRACTORS = {"zip": _extract_zip, "7z": _extract_7z, "rar": _extract_rar}


def _kind_of(source: Path) -> Literal["zip", "7z", "rar", "folder"]:
    if source.is_dir():
        return "folder"
    suffix = source.suffix.lower()
    if suffix == ".zip":
        return "zip"
    if suffix == ".7z":
        return "7z"
    if suffix == ".rar":
        return "rar"
    raise RpgGenError("ARCH-001", path=str(source), reason="unsupported file type")


def extracted_root(sha256: str) -> Path:
    return paths.local_cache_dir() / "extracted" / sha256


def open_pack(source: Path, existing_ids: set[str]) -> OpenedPack:
    """Open a pack folder or archive; archives are extracted (safely) into the cache."""
    source = Path(source)
    if not source.exists():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = _kind_of(source)
    pack_id = ids.pack_id_from_name(source.name if kind == "folder" else source.stem, existing_ids)
    if kind == "folder":
        return OpenedPack(pack_id, "folder", source, "", [])  # never written to

    digest = sha256_file(source)
    target = extracted_root(digest)
    marker = target / COMPLETE_MARKER
    if marker.exists():
        stored = jsonio.read(marker)
        issues = [
            Issue(
                i["code"],
                _severity(i["severity"]),
                i["message"],
                i["fix"],
                i.get("file"),
            )
            for i in stored.get("issues", [])
        ]
        return OpenedPack(pack_id, kind, target, digest, issues)

    partial = target.with_name(target.name + ".partial")
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    issues = IssueList()
    try:
        _EXTRACTORS[kind](source, partial, issues)
        _extract_nested(partial, issues)
        jsonio.write(partial / COMPLETE_MARKER, {"issues": issues.to_json()})
        if target.exists():
            shutil.rmtree(target)
        _move_dir(partial, target)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return OpenedPack(pack_id, kind, target, digest, list(issues))


def _move_dir(src: Path, dst: Path) -> None:
    """Rename a directory; on Windows a scanner may briefly hold handles, so retry then copy."""
    last: OSError | None = None
    for attempt in range(8):
        try:
            src.rename(dst)
            return
        except PermissionError as exc:
            last = exc
            time.sleep(0.1 * (attempt + 1))
    log.debug("rename failed (%s); copying instead", last)
    shutil.copytree(src, dst)
    shutil.rmtree(src, ignore_errors=True)


def _severity(value: str):
    from rpggen.errors import Severity

    return Severity(value)

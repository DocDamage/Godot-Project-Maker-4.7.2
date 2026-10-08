from __future__ import annotations

import contextlib
import functools
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from rpggen import ids, jsonio, paths
from rpggen.core import cache_policy
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

Progress = Callable[[str, int, int], None]  # (label, done, total); a total of 0 means unknown


class Cancelled(Exception):
    """A long step (extracting, hashing, analyzing) stopped because the caller cancelled."""


@dataclass
class Budget:
    """The files and bytes an archive and every archive nested in it may add up to (a nested
    archive does not get a fresh allowance)."""

    files: int = 0
    total_bytes: int = 0

    def charge(self, files: int, nbytes: int, source: str) -> None:
        self.files += files
        self.total_bytes += nbytes
        if self.files > LIMITS["max_files"]:
            raise RpgGenError(
                "ARCH-004", reason=f"more than {LIMITS['max_files']} files", path=source
            )
        if self.total_bytes > LIMITS["max_total_bytes"]:
            raise RpgGenError("ARCH-004", reason="total uncompressed size too large", path=source)


@dataclass(frozen=True)
class Control:
    """The progress and cancel callbacks of one operation (both optional) and the budget that its
    archive and the archives nested in it share."""

    progress: Progress | None = None
    is_cancelled: Callable[[], bool] | None = None
    budget: Budget = field(default_factory=Budget)

    def check(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise Cancelled

    def report(self, label: str, done: int, total: int) -> None:
        if self.progress is not None:
            self.progress(label, done, total)


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


def sha256_file(path: Path, ctl: Control | None = None, label: str = "") -> str:
    """sha256 of a file, streamed. With ``ctl`` the bytes read are reported under ``label`` and a
    cancel stops between two chunks."""
    h = hashlib.sha256()
    total = Path(path).stat().st_size if ctl is not None and ctl.progress is not None else 0
    done = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
            if ctl is not None:
                ctl.check()
                done += len(chunk)
                ctl.report(label or f"Reading {Path(path).name}", done, total)
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


def _select_entries(
    entries: list[_Entry], issues: IssueList, source: str, budget: Budget | None = None
) -> list[_Entry]:
    """Apply safety rules, limits, junk and case-collision handling; returns entries to extract.

    ``budget`` is shared with the nested archives: what is selected is charged to it."""
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
    if budget is not None:
        budget.charge(len(chosen), sum(max(e.size, 0) for e in chosen.values()), source)
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


def _extract_zip(archive: Path, dest: Path, issues: IssueList, ctl: Control) -> None:
    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise RpgGenError("ARCH-001", path=str(archive), reason=str(exc)) from exc
    with zf:
        entries = _select_entries(_zip_entries(zf), issues, str(archive), ctl.budget)
        total = 0
        declared = sum(max(e.size, 0) for e in entries)
        label = f"Extracting {archive.name}"
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
                    ctl.check()
                    written += len(chunk)
                    total += len(chunk)
                    if written > max(entry.size, 0) or written > LIMITS["max_entry_bytes"]:
                        raise RpgGenError(
                            "ARCH-004", reason=f"entry {entry.name} exceeds its declared size"
                        )
                    if total > LIMITS["max_total_bytes"]:
                        raise RpgGenError("ARCH-004", reason="total uncompressed size too large")
                    out.write(chunk)
                    ctl.report(label, total, declared)
        ctl.report(label, declared, declared)


# --------------------------------------------------------------------------- 7z


@functools.cache
def _seven_zip_factory_class() -> type:
    """The writer factory py7zr extracts through (py7zr is imported only when a 7z is opened).

    Writing the files ourselves, instead of letting py7zr extract to disk, gives a cancel point
    at every block (an exception raised in ``write`` reaches the caller of ``extract``),
    progress, and the same size checks the zip extractor has.
    """
    from py7zr.io import Py7zIO, WriterFactory

    class Writer(Py7zIO):
        def __init__(self, path: Path, entry: _Entry, owner: Factory) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.entry = entry
            self.owner = owner
            self.written = 0
            self.fh = open(path, "wb")  # noqa: SIM115 - closed by py7zr (close) or the factory

        def write(self, s: bytes | bytearray) -> int:
            self.owner.ctl.check()
            self.written += len(s)
            self.owner.total += len(s)
            if self.written > max(self.entry.size, 0) or self.written > LIMITS["max_entry_bytes"]:
                raise RpgGenError(
                    "ARCH-004", reason=f"entry {self.entry.name} exceeds its declared size"
                )
            if self.owner.total > LIMITS["max_total_bytes"]:
                raise RpgGenError("ARCH-004", reason="total uncompressed size too large")
            self.fh.write(s)
            self.owner.ctl.report(self.owner.label, self.owner.total, self.owner.declared)
            return len(s)

        def read(self, size: int | None = None) -> bytes:
            return b""

        def seek(self, offset: int, whence: int = 0) -> int:
            return self.fh.seek(offset, whence)

        def flush(self) -> None:
            self.fh.flush()

        def size(self) -> int:
            return self.written

        def close(self) -> None:
            self.fh.close()

    class Factory(WriterFactory):
        def __init__(
            self, dest: Path, entries: dict[str, _Entry], ctl: Control, label: str
        ) -> None:
            self.dest = dest
            self.entries = entries
            self.ctl = ctl
            self.label = label
            self.declared = sum(max(e.size, 0) for e in entries.values())
            self.total = 0
            self.writers: list[Writer] = []

        def create(self, filename: str) -> Py7zIO:
            entry = self.entries.get(filename)
            if entry is None:  # py7zr asked for an entry that was not selected
                raise RpgGenError("ARCH-003", entry=filename)
            target = self.dest.joinpath(*PurePosixPath(entry.name).parts)
            if not _inside(self.dest, target):
                raise RpgGenError("ARCH-003", entry=entry.name)
            writer = Writer(target, entry, self)
            self.writers.append(writer)
            return writer

        def close_all(self) -> None:
            for writer in self.writers:
                if not writer.fh.closed:
                    writer.fh.close()

    return Factory


def _extract_7z(archive: Path, dest: Path, issues: IssueList, ctl: Control) -> None:
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
    entries = []
    for info in infos:
        if info.is_directory:
            continue
        if getattr(info, "is_symlink", False) or getattr(info, "is_junction", False):
            issues.add("ARCH-009", entry=normalize_name(info.filename))
            continue
        entries.append(
            _Entry(
                normalize_name(info.filename),
                info.filename,
                int(info.uncompressed or 0),
                int(info.compressed or 0) if getattr(info, "compressed", None) else 0,
            )
        )
    allowed = _select_entries(entries, issues, str(archive), ctl.budget)
    by_raw = {str(e.raw): e for e in allowed}
    label = f"Extracting {archive.name}"
    factory = _seven_zip_factory_class()(dest, by_raw, ctl, label)
    try:
        # All names were validated above; only the allowed targets are handed to the factory.
        with py7zr.SevenZipFile(archive) as z:
            z.extract(targets=list(by_raw), factory=factory)
    finally:
        factory.close_all()
    ctl.report(label, factory.declared, factory.declared)
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


def _run_7z(command: list[str], ctl: Control) -> subprocess.CompletedProcess[str]:
    """Run 7-Zip, polling for a cancel (the process is killed, nothing is left half-written)."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        while True:
            try:
                out, err = process.communicate(timeout=0.2)
                return subprocess.CompletedProcess(command, process.returncode, out, err)
            except subprocess.TimeoutExpired:
                ctl.check()
    except BaseException:
        process.kill()
        process.communicate()
        raise


def _extract_rar(archive: Path, dest: Path, issues: IssueList, ctl: Control) -> None:
    exe = find_7z()
    if exe is None:
        raise RpgGenError("ARCH-007")
    ctl.report(f"Reading {archive.name}", 0, 0)
    listing = _run_7z([str(exe), "l", "-slt", str(archive)], ctl)
    if listing.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=listing.stderr.strip()[:200])
    # The first block describes the archive itself ("Type = Rar"): it has no Attributes line.
    entries = _parse_7z_listing(listing.stdout)
    allowed = _select_entries(entries, issues, str(archive), ctl.budget)
    ctl.report(f"Extracting {archive.name}", 0, 0)
    # Only the entries that passed the checks are extracted, named in a UTF-8 list file (-ssc: the
    # names match case-sensitively even on Windows): what ARCH-005 reports as kept is what lands
    # on disk, and junk and oversized files are never written.
    with tempfile.TemporaryDirectory(prefix="rpggen_rar_") as scratch:
        names = Path(scratch) / "names.txt"
        names.write_text("\n".join(str(e.raw) for e in allowed) + "\n", encoding="utf-8")
        run = _run_7z(
            [str(exe), "x", f"-o{dest}", "-y", "-ssc", "-scsUTF-8", str(archive), f"@{names}"], ctl
        )
    if run.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=run.stderr.strip()[:200])
    _check_extracted_size(dest)


# --------------------------------------------------------------------------- links


def walk_files(root: Path) -> tuple[list[str], list[str]]:
    """``(files, links)`` of a folder as POSIX paths relative to ``root``, sorted.

    A symbolic link or a junction is never followed: it is listed under ``links`` (a link to a
    folder is not entered), so that a pack cannot pull a file from outside itself.
    """
    files: list[str] = []
    links: list[str] = []
    pending = [Path(root)]
    while pending:
        folder = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                rel = Path(entry.path).relative_to(root).as_posix()
                if entry.is_symlink() or entry.is_junction():
                    links.append(rel)
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    files.append(rel)
    return sorted(files, key=_sort_key), sorted(links, key=_sort_key)


def _scrub_links(dest: Path, issues: IssueList) -> None:
    """After an extraction: remove every link (ARCH-009) and check that every file is inside."""
    files, links = walk_files(dest)
    for rel in links:
        link = dest.joinpath(*PurePosixPath(rel).parts)
        try:
            link.unlink()
        except (PermissionError, IsADirectoryError):
            os.rmdir(link)  # a junction or a directory link on Windows
        issues.add("ARCH-009", entry=rel)
    for rel in files:
        if not _inside(dest, dest.joinpath(*PurePosixPath(rel).parts)):
            raise RpgGenError("ARCH-003", entry=rel)


# --------------------------------------------------------------------------- nested archives


def _extract_nested(root: Path, issues: IssueList, ctl: Control) -> None:
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
            _extract_zip(archive, dest, issues, ctl)
        else:
            _extract_7z(archive, dest, issues, ctl)
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
    return paths.cache_dir() / "extracted" / sha256


def open_pack(
    source: Path,
    existing_ids: set[str],
    pack_id: str | None = None,
    *,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> OpenedPack:
    """Open a pack folder or archive; archives are extracted (safely) into the cache.

    ``pack_id`` pins the id (a regeneration reuses the id stored in the config). ``progress``
    receives ``(label, bytes done, bytes total)`` while an archive is hashed and extracted;
    ``is_cancelled`` is polled between chunks, and a cancel (``Cancelled``) removes the
    half-extracted folder.
    """
    ctl = Control(progress, is_cancelled)
    source = Path(source)
    if not source.exists():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = _kind_of(source)
    pack_id = pack_id or ids.pack_id_from_name(
        source.name if kind == "folder" else source.stem, existing_ids
    )
    if kind == "folder":
        return OpenedPack(pack_id, "folder", source, "", [])  # never written to

    digest = sha256_file(source, ctl, f"Reading {source.name}")
    target = extracted_root(digest)
    marker = target / COMPLETE_MARKER
    if marker.exists():
        cache_policy.touch_used(target)  # recently used archives are the last to be pruned
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
        _EXTRACTORS[kind](source, partial, issues, ctl)
        _extract_nested(partial, issues, ctl)
        _scrub_links(partial, issues)
        jsonio.write(partial / COMPLETE_MARKER, {"issues": issues.to_json()})
        if target.exists():
            shutil.rmtree(target)
        _move_dir(partial, target)
        cache_policy.touch_used(target)
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

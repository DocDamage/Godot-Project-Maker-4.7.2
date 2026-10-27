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
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from rpggen import ids, jsonio, paths, procenv
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


def _folder_entries(entries: list[_Entry], folder: str) -> list[_Entry]:
    """The entries of one pack folder of a bundle (T16.22), named from that folder on, with
    the licence files that lie beside the pack folders: a licence at the bundle's top level
    applies to every pack taken from it. A file of the pack's own with the same name wins."""
    if not folder:
        return entries
    from rpggen.core import inventory

    prefix = unicodedata.normalize("NFC", folder).strip("/") + "/"
    top = prefix[:-1].rpartition("/")[0]
    top = top + "/" if top else ""
    out = [replace(e, name=e.name[len(prefix) :]) for e in entries if e.name.startswith(prefix)]
    own = {e.name.casefold() for e in out}
    for entry in entries:
        rest = entry.name[len(top) :] if entry.name.startswith(top) else ""
        beside = bool(rest) and "/" not in rest and rest.casefold() not in own
        if beside and inventory.classify_kind(rest) == "license":
            out.append(replace(entry, name=rest))
    return out


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


def _extract_zip(
    archive: Path, dest: Path, issues: IssueList, ctl: Control, folder: str = ""
) -> None:
    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise RpgGenError("ARCH-001", path=str(archive), reason=str(exc)) from exc
    with zf:
        wanted = _folder_entries(_zip_entries(zf), folder)
        entries = _select_entries(wanted, issues, str(archive), ctl.budget)
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


def _extract_7z(
    archive: Path, dest: Path, issues: IssueList, ctl: Control, folder: str = ""
) -> None:
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
    allowed = _select_entries(_folder_entries(entries, folder), issues, str(archive), ctl.budget)
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
    return _run_tool(command, ctl, "utf-8")


def _run_tool(
    command: list[str],
    ctl: Control,
    encoding: str,
    *,
    stdout: int | IO[bytes] = subprocess.PIPE,
    poll: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an archive tool, polling for a cancel (and ``poll``, which may raise) every 0.2 s:
    on a cancel or an error the process is killed. ``stdout`` may be a file the output goes to."""
    process = subprocess.Popen(
        command,
        stdout=stdout,
        stderr=subprocess.PIPE,
        text=True,
        encoding=encoding,
        errors="replace",
        env=procenv.child_env(),
    )
    try:
        while True:
            try:
                out, err = process.communicate(timeout=0.2)
                return subprocess.CompletedProcess(command, process.returncode, out or "", err)
            except subprocess.TimeoutExpired:
                ctl.check()
                if poll is not None:
                    poll()
    except BaseException:
        process.kill()
        process.communicate()
        raise


def _extract_rar(
    archive: Path, dest: Path, issues: IssueList, ctl: Control, folder: str = ""
) -> None:
    """A rar is opened with 7-Zip when it is installed, else with the system's own tar when that
    is bsdtar (libarchive reads rar; Windows 10 and later ship it), else refused (ARCH-007)."""
    if folder:  # a rar is not listed by the sniff, so it is never offered as a bundle
        raise RpgGenError(
            "ARCH-001",
            path=str(archive),
            reason="a pack folder cannot be taken from a rar; extract it and add the folder",
        )
    exe = find_7z()
    if exe is None:
        tar = find_bsdtar()
        if tar is None:
            raise RpgGenError("ARCH-007")
        _extract_with_bsdtar(tar, archive, dest, issues, ctl)
        return
    ctl.report(f"Reading {archive.name}", 0, 0)
    # -sccUTF-8: the listing is read as UTF-8; in the console's code page a name such as
    # "Can’t" comes out as "Can't" and is then not found when the list file names it
    listing = _run_7z([str(exe), "l", "-slt", "-sccUTF-8", str(archive)], ctl)
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


# --------------------------------------------------------------------------- rar via bsdtar

# A line of ``tar -tv``: mode, links, owner, group, size, date (month, day, time or year; the
# month may be localized), one space, the name. A link names its target after " -> " (symbolic)
# or " link to " (hard).
_TAR_LINE = re.compile(
    r"^(?P<mode>\S{10})\S*\s+\d+\s+\S+\s+\S+\s+(?P<size>\d+)\s+"
    r"\S+\s+\d{1,2}\s+(?:\d{1,2}:\d{2}|\d{4}) (?P<name>.+)$"
)
_TAR_UNREADABLE = "unreadable filename"  # bsdtar skips a name the locale cannot represent
_TAR_GLOB = re.compile(r"[*?\[\\]")


def _tar_encoding() -> str:
    """What bsdtar writes names in: the ANSI code page on Windows, UTF-8 elsewhere."""
    return "mbcs" if os.name == "nt" else "utf-8"


@functools.cache
def _is_bsdtar(exe: str) -> bool:
    try:
        run = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            env=procenv.child_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    text = (run.stdout + run.stderr).casefold()
    return "bsdtar" in text or "libarchive" in text


def find_bsdtar() -> Path | None:
    """The system's tar when it is bsdtar (libarchive reads rar). On Windows the one in System32
    comes first: Git's GNU tar, often earlier on PATH, does not read rar."""
    candidates: list[str] = []
    if os.name == "nt":
        system_root = os.environ.get("SYSTEMROOT") or r"C:\Windows"
        candidates.append(str(Path(system_root) / "System32" / "tar.exe"))
    for name in ("bsdtar", "tar"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for candidate in candidates:
        if Path(candidate).is_file() and _is_bsdtar(candidate):
            return Path(candidate)
    return None


def _parse_tar_listing(text: str, issues: IssueList) -> list[_Entry]:
    """The regular files of a ``tar -tvf`` listing. A link is reported (ARCH-009) and left out;
    a folder or a line that is not an entry is ignored."""
    entries: list[_Entry] = []
    for line in text.splitlines():
        match = _TAR_LINE.match(line)
        if match is None:
            continue
        kind = match["mode"][0]
        name = match["name"]
        if kind in "lh":
            sep = " -> " if kind == "l" else " link to "
            issues.add("ARCH-009", entry=normalize_name(name.partition(sep)[0]))
            continue
        if kind != "-":
            continue
        entries.append(_Entry(normalize_name(name), name, int(match["size"]), 0))
    return entries


def _dir_size(root: Path) -> int:
    total = 0
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as found:
            for entry in found:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
    return total


def _extract_with_bsdtar(
    tar: Path, archive: Path, dest: Path, issues: IssueList, ctl: Control
) -> None:
    """List the archive, select its entries (``_select_entries``), extract it into a scratch
    folder beside ``dest`` and move the selected files alone into ``dest``: junk, links and the
    loser of a case collision never reach it. bsdtar cannot be handed a list of names (it reads
    them as patterns), hence the scratch folder."""
    encoding = _tar_encoding()
    ctl.report(f"Reading {archive.name}", 0, 0)
    listing = _run_tool([str(tar), "-tvf", str(archive)], ctl, encoding)
    unreadable = listing.stderr.count(_TAR_UNREADABLE)
    if listing.returncode != 0 and not unreadable:
        raise RpgGenError("ARCH-001", path=str(archive), reason=listing.stderr.strip()[:200])
    if unreadable:
        issues.add("ARCH-010", path=archive.name, count=unreadable)
    entries = _parse_tar_listing(listing.stdout, issues)
    if not entries and listing.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=listing.stderr.strip()[:200])
    allowed = _select_entries(entries, issues, str(archive), ctl.budget)
    # every regular file is written to the scratch folder, the ones left out too
    listed = sum(max(e.size, 0) for e in entries)
    declared = sum(max(e.size, 0) for e in allowed)
    label = f"Extracting {archive.name}"
    ctl.report(label, 0, declared)
    kept = {e.name for e in allowed}
    folded = {name.casefold() for name in kept}
    collided = {
        e.name.casefold()
        for e in entries
        if e.name not in kept and e.name.casefold() in folded and not is_junk(e.name)
    }
    with tempfile.TemporaryDirectory(prefix="rpggen_rar_", dir=dest.parent) as scratch_dir:
        scratch = Path(scratch_dir) / "x"
        scratch.mkdir()
        last = [0.0]

        def watch() -> None:  # the archive may lie about its sizes: what is written counts
            now = time.monotonic()
            if now - last[0] < 1.0:
                return
            last[0] = now
            written = _dir_size(scratch)
            if written > listed or written > LIMITS["max_total_bytes"]:
                raise RpgGenError("ARCH-004", reason=f"{archive.name} writes more than it declares")
            ctl.report(label, min(written, declared), declared)

        run = _run_tool(
            [str(tar), "-xf", str(archive), "-C", str(scratch)], ctl, encoding, poll=watch
        )
        moved = 0
        for entry in allowed:
            ctl.check()
            source = scratch.joinpath(*PurePosixPath(entry.name).parts)
            target = dest.joinpath(*PurePosixPath(entry.name).parts)
            if not _inside(dest, target) or not _inside(scratch, source):
                raise RpgGenError("ARCH-003", entry=entry.name)
            if source.is_symlink() or not source.is_file():
                reason = run.stderr.strip()[:200] or f"{entry.name} was not extracted"
                raise RpgGenError("ARCH-001", path=str(archive), reason=reason)
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.name.casefold() in collided:
                # on a case-insensitive disk the names that collide were written to one file,
                # the last one winning: the kept one is read again on its own
                _tar_entry_to(tar, archive, entry, target, ctl, encoding)
            else:
                os.replace(source, target)
            if target.stat().st_size > max(entry.size, 0):
                raise RpgGenError(
                    "ARCH-004", reason=f"entry {entry.name} exceeds its declared size"
                )
            moved += max(entry.size, 0)
            ctl.report(label, moved, declared)
    if run.returncode != 0:  # what was selected is all there: the error was about the rest
        log.debug("bsdtar on %s: %s", archive, run.stderr.strip()[:500])
    ctl.report(label, declared, declared)
    _check_extracted_size(dest)


def _tar_entry_to(
    tar: Path, archive: Path, entry: _Entry, target: Path, ctl: Control, encoding: str
) -> None:
    """Write one entry of the archive to ``target`` (``tar -xOf``). Its name is a pattern to
    bsdtar: a name with a wildcard is refused rather than matched loosely."""
    name = str(entry.raw)
    if _TAR_GLOB.search(name):
        raise RpgGenError(
            "ARCH-001",
            path=str(archive),
            reason=f"{entry.name} differs from another name only in case and has a wildcard",
        )
    with open(target, "wb") as out:
        run = _run_tool([str(tar), "-xOf", str(archive), name], ctl, encoding, stdout=out)
    if run.returncode != 0:
        raise RpgGenError("ARCH-001", path=str(archive), reason=run.stderr.strip()[:200])


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


# --------------------------------------------------------------------------- a zip in a folder

LONE_ARCHIVES = (".zip", ".7z")
BESIDE_KINDS = ("license", "doc")  # what may lie beside the archive and is no part of a pack


def lone_archive(folder: Path) -> Path | None:
    """The archive a pack folder is (T17.12): some packs are one zip in a folder with nothing
    but previews beside it (``Preview.png``, ``Sample.png``, a folder ``Samples``, links to a
    shop). None for a folder with a picture of its own that is no preview, with a folder that
    is no preview folder, with two archives or with none: that folder is the pack."""
    from rpggen.core import classifier, inventory

    found: list[Path] = []
    try:
        entries = sorted(os.scandir(folder), key=lambda e: _sort_key(e.name))
    except OSError:
        return None
    for entry in entries:
        name = entry.name
        if is_junk(name):
            continue
        if entry.is_dir(follow_symlinks=False):
            if name.strip().casefold() not in classifier.PREVIEW_FOLDERS:
                return None
            continue
        if not entry.is_file(follow_symlinks=False):
            return None
        if Path(name).suffix.lower() in LONE_ARCHIVES:
            found.append(Path(entry.path))
            continue
        kind = inventory.classify_kind(name)
        if kind in BESIDE_KINDS or inventory.not_an_asset(name, entry.stat().st_size):
            continue
        if kind == "image" and classifier.not_game_art(name):
            continue
        return None
    return found[0] if len(found) == 1 else None


# --------------------------------------------------------------------------- public API

_EXTRACTORS = {"zip": _extract_zip, "7z": _extract_7z, "rar": _extract_rar}


def pack_name(source: Path) -> str:
    """What a new pack's id is made from (``ids.pack_id_from_name``): a folder's name, an
    archive's stem; but a zip whose stem is longer than an id and that holds one folder and
    nothing beside it is named by that folder (2026-10-26: a shop's file name,
    ``isometric-map-builder-pixel-art-godot-tiled-pack-isometric-tiles``, whose ends alone
    tell thirteen packs apart, holds ``Gridwright Isometric Tiles``)."""
    source = Path(source)
    if source.is_dir():
        return source.name
    stem = source.stem
    if len(ids.slug(stem)) <= ids.PACK_ID_LENGTH or source.suffix.lower() != ".zip":
        return stem
    try:
        with zipfile.ZipFile(source) as zf:
            names = [n for n in zf.namelist() if not n.startswith("__MACOSX/")]
    except (OSError, zipfile.BadZipFile):
        return stem
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) == 1 and all("/" in n for n in names):
        return next(iter(tops))
    return stem


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


_DIGESTS: dict[tuple[str, int, int], str] = {}  # of the bundles opened in this process


def _bundle_digest(source: Path, ctl: Control) -> str:
    """sha256 of a bundle archive, read once for all the packs taken from it."""
    info = source.stat()
    key = (str(source.resolve()), info.st_size, info.st_mtime_ns)
    if key not in _DIGESTS:
        _DIGESTS[key] = sha256_file(source, ctl, f"Reading {source.name}")
    return _DIGESTS[key]


def open_pack(
    source: Path,
    existing_ids: set[str],
    pack_id: str | None = None,
    *,
    folder: str = "",
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> OpenedPack:
    """Open a pack folder or archive; archives are extracted (safely) into the cache.

    ``pack_id`` pins the id (a regeneration reuses the id stored in the config). ``progress``
    receives ``(label, bytes done, bytes total)`` while an archive is hashed and extracted;
    ``is_cancelled`` is polled between chunks, and a cancel (``Cancelled``) removes the
    half-extracted folder.

    A folder that holds one archive and nothing but previews beside it is opened as that
    archive (``lone_archive``, T17.12).

    ``folder`` names one pack folder of a bundle (T16.22): that folder alone is the pack. The
    wizard names such a pack by a path that does not exist, ``<archive>/<folder>``
    (``pack_sniff.member_path``); it is opened the same way.
    """
    from rpggen.core import pack_sniff

    ctl = Control(progress, is_cancelled)
    source = Path(source)
    member = None if folder or source.exists() else pack_sniff.split_member(source)
    if member is not None:
        source, folder = member
    if not source.exists():
        raise RpgGenError("ARCH-001", path=str(source), reason="does not exist")
    kind = _kind_of(source)
    inner = pack_sniff.folder_in_bundle(source, folder).path if folder else ""
    pack_id = pack_id or ids.pack_id_from_name(folder or pack_name(source), existing_ids)
    if inner and pack_sniff.is_inner_archive(inner):
        # a zip of zips (T16.21): the pack is an archive inside, opened as an archive is
        return pack_sniff.open_inner_archive(
            source, inner, existing_ids, pack_id, progress=progress, is_cancelled=is_cancelled
        )
    if kind == "folder":  # never written to
        root = source.joinpath(*PurePosixPath(inner).parts) if inner else source
        lone = None if inner else lone_archive(root)
        if lone is not None:
            # the pack is an archive in its folder, beside its previews (T17.12): it is opened
            # as that archive, under the folder's name
            return open_pack(
                lone, existing_ids, pack_id, progress=progress, is_cancelled=is_cancelled
            )
        return OpenedPack(pack_id, "folder", root, "", [])

    if inner:  # the pack's own identity: the archive's and the folder's
        whole = _bundle_digest(source, ctl)
        digest = hashlib.sha256(f"{whole}:{inner}".encode()).hexdigest()
    else:
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
        _EXTRACTORS[kind](source, partial, issues, ctl, inner)
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

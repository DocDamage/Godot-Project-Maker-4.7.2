"""What kind of pack is this? (T12.33)

Looks at the name list of a folder, a zip or a 7z (nothing is extracted) and, for a few files, the
first bytes: the width of one RPG Maker sheet, the size of an LPC sheet, the keys of an Aseprite
export. It never raises: a problem comes back as ``issue`` for the pack card to show. A listing is
read for at most ``BUDGET_S`` seconds.
"""

from __future__ import annotations

import json
import os
import re
import struct
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rpggen.core import inventory
from rpggen.errors import Issue, IssueList

BUDGET_S = 1.0
MAX_NAMES = 50_000
JSON_LIMIT = 256 * 1024

SHEET_NAME = re.compile(r"^(.*_)?(A[1-5]|B|C|D|E)\.png$", re.IGNORECASE)
TILED_SUFFIXES = (".tsx", ".tmx", ".tsj", ".tmj")
# the width of a tileset sheet tells the tile size: VX Ace 32 px sheets, MV and MZ 48 px sheets
SHEET_WIDTH_TILE = {256: 32, 512: 32, 384: 48, 576: 48, 768: 48}
LPC_WIDTH, LPC_MIN_HEIGHT = 832, 1344

FORMATS = ("rpgmaker", "lpc", "tiled", "ldtk", "aseprite", "generic")


@dataclass(frozen=True)
class PackSniff:
    """``format`` is one of ``FORMATS`` ("" when the pack could not be read)."""

    format: str = ""
    tile_size: int | None = None
    has_license: bool | None = None  # None: not known (a rar is not listed)
    issues: tuple[Issue, ...] = field(default_factory=tuple)


class _Source:
    """Names and the first bytes of a few files, whatever the container."""

    def names(self) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def head(self, name: str, size: int) -> bytes:
        return b""


class _Folder(_Source):
    def __init__(self, root: Path, deadline: float) -> None:
        self.root, self.deadline = root, deadline

    def names(self) -> list[str]:
        out: list[str] = []
        stack = [self.root]
        while stack and len(out) < MAX_NAMES and time.monotonic() < self.deadline:
            try:
                for entry in stack.pop().iterdir():
                    if entry.is_dir():
                        stack.append(entry)
                    else:
                        out.append(entry.relative_to(self.root).as_posix())
            except OSError:
                continue
        return out

    def head(self, name: str, size: int) -> bytes:
        try:
            with (self.root / name).open("rb") as fh:
                return fh.read(size)
        except OSError:
            return b""


class _Zip(_Source):
    def __init__(self, zf: zipfile.ZipFile) -> None:
        self.zf = zf

    def names(self) -> list[str]:
        return [i.filename for i in self.zf.infolist() if not i.is_dir()][:MAX_NAMES]

    def head(self, name: str, size: int) -> bytes:
        try:
            with self.zf.open(name) as fh:
                return fh.read(size)
        except (KeyError, RuntimeError, zipfile.BadZipFile, OSError):
            return b""


class _Names(_Source):
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def names(self) -> list[str]:
        return self._names[:MAX_NAMES]


def stamp(path: Path | str) -> str | None:
    """A cheap fingerprint of a pack as it is on disk now (T13.08), without reading a file: an
    archive's size and modification time, or a folder's file count, total size and newest
    modification time. None when the pack is not there."""
    source = Path(path)
    try:
        if source.is_file():
            info = source.stat()
            return f"file:{info.st_size}:{info.st_mtime_ns}"
        if not source.is_dir():
            return None
        count = size = newest = 0
        stack = [source]
        while stack:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        info = entry.stat(follow_symlinks=False)
                        count += 1
                        size += info.st_size
                        newest = max(newest, info.st_mtime_ns)
        return f"dir:{count}:{size}:{newest}"
    except OSError:
        return None


def changed_since(pack_path: Path | str, recorded: str) -> datetime | None:
    """When the pack last changed, if it is not as ``recorded`` (a ``stamp`` taken when the
    project was generated); None when it is the same, when nothing was recorded and when the
    pack cannot be reached now (that is not a change)."""
    current = stamp(pack_path)
    if not recorded or current is None or current == recorded:
        return None
    try:
        return datetime.fromtimestamp(int(current.rsplit(":", 1)[1]) / 1e9)
    except (ValueError, OSError, OverflowError):
        return datetime.now()


def _png_size(head: bytes) -> tuple[int, int] | None:
    if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])  # type: ignore[return-value]
    return None


def _norm(name: str) -> str:
    return name.replace("\\", "/")


def _has_license(names: list[str]) -> bool:
    return any(inventory.classify_kind(_norm(n)) == "license" for n in names)


def _tileset_sheets(names: list[str]) -> list[str]:
    return [
        n
        for n in names
        if SHEET_NAME.match(_norm(n).rsplit("/", 1)[-1])
        and "tilesets" in _norm(n).casefold().split("/")
    ]


def classify(source: _Source, names: list[str], deadline: float) -> tuple[str, int | None]:
    """The format of the pack and, for RPG Maker, the tile size read from one sheet."""
    lowered = [_norm(n).casefold() for n in names]
    if any(n.endswith(".ldtk") for n in lowered):
        return "ldtk", None
    if any(n.endswith(TILED_SUFFIXES) for n in lowered):
        return "tiled", None
    for name, low in zip(names, lowered, strict=True):
        if time.monotonic() > deadline:
            break
        if low.endswith(".json"):
            head = source.head(name, JSON_LIMIT)
            if b'"frames"' in head and b'"meta"' in head and _is_aseprite(head):
                return "aseprite", None
    sheets = _tileset_sheets(names)
    if sheets:
        size = _png_size(source.head(sheets[0], 32))
        return "rpgmaker", SHEET_WIDTH_TILE.get(size[0]) if size else None
    for name, low in zip(names, lowered, strict=True):
        if time.monotonic() > deadline:
            break
        if low.endswith(".png"):
            size = _png_size(source.head(name, 32))
            if size and size[0] == LPC_WIDTH and size[1] >= LPC_MIN_HEIGHT:
                return "lpc", None
    return "generic", None


def _is_aseprite(head: bytes) -> bool:
    try:
        data = json.loads(head.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return False  # a file cut at the limit is not read further
    return isinstance(data, dict) and "frames" in data and isinstance(data.get("meta"), dict)


def sniff(path: Path | str) -> PackSniff:
    """Sniff a pack folder or archive; see the module docstring."""
    path = Path(path)
    deadline = time.monotonic() + BUDGET_S
    issues = IssueList()
    if not path.exists():
        issues.add("ARCH-001", path=str(path), reason="does not exist")
        return PackSniff(issues=tuple(issues))
    try:
        if path.is_dir():
            source: _Source = _Folder(path, deadline)
            names = source.names()
            return _result(source, names, deadline)
        suffix = path.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                if any(i.flag_bits & 0x1 for i in zf.infolist()):
                    issues.add("ARCH-002")
                    return PackSniff(issues=tuple(issues))
                source = _Zip(zf)
                return _result(source, source.names(), deadline)
        if suffix == ".7z":
            import py7zr

            with py7zr.SevenZipFile(path) as z:
                if z.needs_password():
                    issues.add("ARCH-002")
                    return PackSniff(issues=tuple(issues))
                names = [n for n in z.getnames() if not n.endswith("/")]
            return _result(_Names(names), names, deadline)
        if suffix == ".rar":
            return PackSniff(format="generic", has_license=None)  # not listed without 7-Zip
        issues.add("ARCH-001", path=str(path), reason="not a folder or a zip/7z/rar archive")
    except Exception as exc:  # noqa: BLE001 - a broken archive is shown on its card
        name = type(exc).__name__
        if "Password" in name or "password" in str(exc).lower():
            issues.add("ARCH-002")
        else:
            issues.add("ARCH-001", path=str(path), reason=str(exc) or name)
    return PackSniff(issues=tuple(issues))


def _result(source: _Source, names: list[str], deadline: float) -> PackSniff:
    fmt, tile = classify(source, names, deadline)
    return PackSniff(format=fmt, tile_size=tile, has_license=_has_license(names))

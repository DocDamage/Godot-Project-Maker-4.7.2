"""What kind of pack is this? (T12.33)

Looks at the name list of a folder, a zip or a 7z (nothing is extracted) and, for a few files, the
first bytes: the width of one RPG Maker sheet, the size of an LPC sheet, the keys of an Aseprite
export. It never raises: a problem comes back as ``issue`` for the pack card to show. A listing is
read for at most ``BUDGET_S`` seconds.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import struct
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from rpggen.core import archive as archive_mod
from rpggen.core import inventory
from rpggen.errors import Issue, IssueList, RpgGenError

BUDGET_S = 1.0
MAX_NAMES = 50_000
JSON_LIMIT = 256 * 1024

SHEET_NAME = re.compile(r"^(.*_)?(A[1-5]|B|C|D|E)\.png$", re.IGNORECASE)
TILED_SUFFIXES = (".tsx", ".tmx", ".tsj", ".tmj")
# the width of a tileset sheet tells the tile size: VX Ace 32 px sheets, MV and MZ 48 px sheets
SHEET_WIDTH_TILE = {256: 32, 512: 32, 384: 48, 576: 48, 768: 48}
LPC_WIDTH, LPC_MIN_HEIGHT = 832, 1344

FORMATS = ("rpgmaker", "lpc", "tiled", "ldtk", "aseprite", "generic")

# A bundle (T16.21): one archive or folder that holds many packs, a folder each.
BUNDLE_MIN_PACKS = 10
# Words a folder that is a pack of its own carries in its name; the folders of one pack
# ("body", "hair", "Cars", "Tilesets") are named after what is in them instead.
BUNDLE_PACK_WORDS = frozenset(
    {"pack", "packs", "tileset", "tilesets", "asset", "assets", "kit", "bundle", "collection"}
)
_WORDS = re.compile(r"[A-Za-z]+")
# The checklist (T16.22) opens with every pack ticked up to this many, with none above.
BUNDLE_TICK_ALL = 20
BUNDLE_ARCHIVES = (".zip", ".7z")  # the archives that are listed, so a bundle is seen in them
MARK_NAMES = 5_000  # the names the view of a pack is read from


@dataclass(frozen=True)
class BundlePack:
    """One pack folder of a bundle, from the listing alone."""

    name: str  # the folder's name: the name of the pack it would be
    path: str  # the folder inside the archive or folder, with ``/``
    images: int
    bytes: int


@dataclass(frozen=True)
class PackSniff:
    """``format`` is one of ``FORMATS`` ("" when the pack could not be read)."""

    format: str = ""
    tile_size: int | None = None
    has_license: bool | None = None  # None: not known (a rar is not listed)
    issues: tuple[Issue, ...] = field(default_factory=tuple)
    # the pack folders when this is a bundle of packs (empty: one pack)
    bundle: tuple[BundlePack, ...] = field(default_factory=tuple)
    bundle_license: bool = False  # a licence file beside the pack folders: it is for them all
    # what the names say about the pack, as the catalog's pack warnings do: ``view:shmup``,
    # ``view:racing``, ``view:side``, ``engines:5:Godot``
    marks: tuple[str, ...] = field(default_factory=tuple)


class _Source:
    """Names and the first bytes of a few files, whatever the container."""

    def names(self) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def head(self, name: str, size: int) -> bytes:
        return b""

    def sizes(self) -> dict[str, int]:
        """Bytes per name, as far as the listing says (a name it does not have counts 0)."""
        return {}


class _Folder(_Source):
    def __init__(self, root: Path, deadline: float) -> None:
        self.root, self.deadline = root, deadline

    def names(self) -> list[str]:
        out: list[str] = []
        self._sizes: dict[str, int] = {}
        stack = [self.root]
        while stack and len(out) < MAX_NAMES and time.monotonic() < self.deadline:
            try:
                for entry in os.scandir(stack.pop()):
                    if entry.is_dir():
                        stack.append(Path(entry.path))
                    else:
                        name = Path(entry.path).relative_to(self.root).as_posix()
                        out.append(name)
                        self._sizes[name] = entry.stat().st_size
            except OSError:
                continue
        return out

    def sizes(self) -> dict[str, int]:
        return getattr(self, "_sizes", {})

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

    def sizes(self) -> dict[str, int]:
        return {i.filename: i.file_size for i in self.zf.infolist() if not i.is_dir()}

    def head(self, name: str, size: int) -> bytes:
        try:
            with self.zf.open(name) as fh:
                return fh.read(size)
        except (KeyError, RuntimeError, zipfile.BadZipFile, OSError):
            return b""


class _Names(_Source):
    def __init__(self, names: list[str], sizes: dict[str, int] | None = None) -> None:
        self._names = names
        self._sizes = sizes or {}

    def names(self) -> list[str]:
        return self._names[:MAX_NAMES]

    def sizes(self) -> dict[str, int]:
        return self._sizes


def find_bundle(names: list[str], sizes: dict[str, int] | None = None) -> tuple[BundlePack, ...]:
    """The pack folders of a bundle, or ``()`` for one pack. A bundle is ten or more folders
    with pictures in them, side by side at the top (inside the one folder an archive wraps
    everything in, when it has one), with no picture beside them, and at least half of them
    named as packs are (*... Tileset*, *... Asset Pack*). Read from the names alone."""
    sizes = sizes or {}
    files = [
        (_norm(n), sizes.get(n, 0))
        for n in names
        if not archive_mod.is_junk(_norm(n)) and not _norm(n).rsplit("/", 1)[-1].startswith("._")
    ]
    pictures = [(n, size) for n, size in files if inventory.classify_kind(n) == "image"]
    if not pictures:
        return ()
    tops = {n.split("/", 1)[0] for n, _size in pictures}
    prefix = ""
    if len(tops) == 1 and all("/" in n for n, _size in pictures):
        prefix = next(iter(tops)) + "/"
    folders: dict[str, list[int]] = {}
    for name, size in pictures:
        rest = name[len(prefix) :]
        if "/" not in rest:
            return ()  # a picture beside the folders: this is one pack
        folders.setdefault(rest.split("/", 1)[0], []).append(size)
    if len(folders) < BUNDLE_MIN_PACKS:
        return ()
    named = sum(
        1 for folder in folders if {w.lower() for w in _WORDS.findall(folder)} & BUNDLE_PACK_WORDS
    )
    if named * 2 < len(folders):
        return ()
    return tuple(
        BundlePack(folder, prefix + folder, len(folders[folder]), sum(folders[folder]))
        for folder in sorted(folders, key=lambda f: (f.casefold(), f))
    )


def _top_license(names: list[str], bundle: tuple[BundlePack, ...]) -> bool:
    """True when a licence file lies beside the pack folders of ``bundle``."""
    top = bundle[0].path.rpartition("/")[0]
    top = top + "/" if top else ""
    for name in map(_norm, names):
        rest = name[len(top) :] if name.startswith(top) else ""
        if rest and "/" not in rest and inventory.classify_kind(rest) == "license":
            return True
    return False


# A zip of zips (T16.21): an archive, or a folder, whose packs are archives of their own, side
# by side with no picture beside them. Two are enough: an archive inside is a unit by itself.
INNER_ARCHIVES = (".zip",)
INNER_MIN_PACKS = 2


def is_inner_archive(path: str) -> bool:
    """True when the ``path`` of a ``BundlePack`` names an archive inside the bundle, not a
    folder of it."""
    return _norm(path).casefold().endswith(INNER_ARCHIVES)


def _inner_pictures(source: _Source, name: str) -> tuple[int, int] | None:
    """``(pictures, their bytes)`` of the zip ``name`` inside ``source``, from its listing: the
    inner archive is read in place as far as its directory needs, and nothing is written.
    None when it cannot be listed (no zip, a password, a container that is not read in place)."""
    try:
        if isinstance(source, _Zip):
            stream = source.zf.open(name)
        elif isinstance(source, _Folder):
            stream = (source.root / name).open("rb")
        else:
            return None
        with stream, zipfile.ZipFile(stream) as inner:
            sizes = []
            for info in inner.infolist():
                entry = _norm(info.filename)
                if info.is_dir() or archive_mod.is_junk(entry):
                    continue
                if info.flag_bits & 0x1:
                    return None
                if inventory.classify_kind(entry) == "image" and not entry.rsplit("/", 1)[
                    -1
                ].startswith("._"):
                    sizes.append(info.file_size)
            return len(sizes), sum(sizes)
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, OSError):
        return None


def find_archive_bundle(
    source: _Source, names: list[str], deadline: float
) -> tuple[BundlePack, ...]:
    """The packs of a zip of zips, or ``()``: two or more zip archives in one folder of
    ``source`` with no picture anywhere beside them, each with pictures in it. A pack is named
    after its archive and its ``path`` is that archive's name inside ``source``
    (``is_inner_archive``); the pictures are counted from the inner listings. An archive the
    time did not reach (``deadline``) is listed with no picture and its own size."""
    files = [n for n in names if not archive_mod.is_junk(_norm(n))]
    if any(inventory.classify_kind(_norm(n)) == "image" for n in files):
        return ()  # pictures of its own: one pack, whose inner archives are unpacked with it
    archives = [n for n in files if is_inner_archive(n)]
    if len(archives) < INNER_MIN_PACKS or len({_norm(n).rpartition("/")[0] for n in archives}) > 1:
        return ()
    sizes = source.sizes()
    packs: list[BundlePack] = []
    listed = 0
    for name in sorted(archives, key=lambda n: (_norm(n).casefold(), n)):
        path = _norm(name)
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if time.monotonic() > deadline:
            packs.append(BundlePack(stem, path, 0, sizes.get(name, 0)))
            continue
        counted = _inner_pictures(source, name)
        if counted is None or counted[0] == 0:
            return ()  # an archive that is no pack: the whole is opened as before
        listed += 1
        packs.append(BundlePack(stem, path, counted[0], counted[1]))
    return tuple(packs) if listed else ()


def open_inner_archive(
    source: Path | str,
    inner: str,
    existing_ids: set[str],
    pack_id: str | None = None,
    **options: object,
) -> archive_mod.OpenedPack:
    """Open the archive ``inner`` (a ``BundlePack.path`` of a zip of zips) of ``source`` as a
    pack of its own. It is copied out to a temporary folder and opened like any archive, so
    the limits, the cache and the pack's identity are those of the inner archive; ``options``
    go to ``archive.open_pack`` (``progress``, ``is_cancelled``). ``ARCH-001`` when ``source``
    has no such archive."""
    import shutil
    import tempfile

    source = Path(source)
    parts = [p for p in _norm(inner).split("/") if p]
    if source.is_dir():
        return archive_mod.open_pack(source.joinpath(*parts), existing_ids, pack_id, **options)  # type: ignore[arg-type]
    with tempfile.TemporaryDirectory(prefix="rpggen_inner_") as tmp:
        copy = Path(tmp) / parts[-1]
        try:
            with zipfile.ZipFile(source) as zf:
                info = zf.getinfo("/".join(parts))
                if info.flag_bits & 0x1:
                    raise RpgGenError("ARCH-002")
                if info.file_size > archive_mod.LIMITS["max_total_bytes"]:
                    raise RpgGenError("ARCH-004", reason=f"{inner} is too large", path=str(source))
                with zf.open(info) as src, copy.open("wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
        except (KeyError, zipfile.BadZipFile, OSError) as exc:
            reason = f'it has no archive "{inner}" that can be read ({exc})'
            raise RpgGenError("ARCH-001", path=str(source), reason=reason) from exc
        return archive_mod.open_pack(copy, existing_ids, pack_id, **options)  # type: ignore[arg-type]


def member_path(bundle: Path | str, folder: str) -> Path:
    """The path a pack taken from a bundle goes by in the wizard: ``<bundle>/<folder name>``.
    For an archive nothing is there on the disk; ``archive.open_pack`` knows it."""
    return Path(bundle) / folder


def split_member(path: Path | str) -> tuple[Path, str] | None:
    """``(archive, folder name)`` when ``path`` names a pack folder of a bundle archive."""
    path = Path(path)
    parent = path.parent
    if parent.suffix.lower() in BUNDLE_ARCHIVES and parent.is_file():
        return parent, path.name
    return None


def nearest_folder(name: str, bundle: tuple[BundlePack, ...]) -> str:
    """The pack folder whose name is most like ``name`` ("" for an empty bundle)."""
    names = {p.name.casefold(): p.name for p in bundle}
    close = difflib.get_close_matches(name.casefold(), list(names), n=1, cutoff=0.0)
    return names[close[0]] if close else ""


def folder_in_bundle(source: Path | str, folder: str) -> BundlePack:
    """The pack folder ``folder`` (its name, or its path inside) of the bundle ``source``.
    ``ARCH-001`` when ``source`` is not a bundle, and when it has no such folder: the reason
    names the nearest one."""
    source = Path(source)
    sniffed = sniff(source)
    if sniffed.issues:
        first = sniffed.issues[0]
        raise RpgGenError(first.code, first.message)
    if not sniffed.bundle:
        raise RpgGenError(
            "ARCH-001",
            path=str(source),
            reason=f'it is not a bundle of packs, so it has no pack folder "{folder}" '
            "(folders, --pack-folder)",
        )
    wanted = _norm(folder).strip("/")
    for pack in sniffed.bundle:
        if wanted in (pack.name, pack.path):
            return pack
    for pack in sniffed.bundle:
        if wanted.casefold() == pack.name.casefold():
            return pack
    raise RpgGenError(
        "ARCH-001",
        path=str(source),
        reason=f'it has no pack folder "{folder}"; '
        f'the nearest is "{nearest_folder(wanted, sniffed.bundle)}"',
    )


def stamp(path: Path | str) -> str | None:
    """A cheap fingerprint of a pack as it is on disk now (T13.08), without reading a file: an
    archive's size and modification time, or a folder's file count, total size and newest
    modification time. None when the pack is not there."""
    source = Path(path)
    member = None if source.exists() else split_member(source)
    if member is not None:  # a pack taken from a bundle changes when its archive does
        source = member[0]
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
    from rpggen.core.adapters import lpc

    if lpc.looks_like_collection(names):
        return "lpc", None  # the collection's files: a picture or a folder per animation
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
                listed = [i for i in z.list() if not i.is_directory]
            names = [i.filename for i in listed]
            sized = {i.filename: int(i.uncompressed or 0) for i in listed}
            return _result(_Names(names, sized), names, deadline)
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


def _marks(names: list[str]) -> tuple[str, ...]:
    """What the names alone say about a pack: its point of view and the engines it ships its
    art for. The analysis says the same later, with the pictures to go by."""
    from rpggen.core import classifier

    normed = [_norm(n) for n in names[:MARK_NAMES]]
    marks: list[str] = []
    listed = SimpleNamespace(files=[SimpleNamespace(path=n) for n in normed])
    view = classifier.pack_view(listed)
    if view != "top":
        marks.append(f"view:{view}")
    tops = {n.split("/", 1)[0] for n in normed}
    wrapper = next(iter(tops)) if len(tops) == 1 and all("/" in n for n in normed) else ""
    engines = classifier.engine_plan(sorted(normed), wrapper)
    if engines is not None:
        marks.append(engines.warning)
    return tuple(marks)


def _result(source: _Source, names: list[str], deadline: float) -> PackSniff:
    bundle = find_bundle(names, source.sizes())
    if not bundle:  # ... or a zip of zips: its packs are the archives inside
        bundle = find_archive_bundle(source, names, deadline)
    if bundle:  # many packs: what one of them is, is asked when it is added; nothing is read
        return PackSniff(
            format="generic",
            has_license=_has_license(names),
            bundle=bundle,
            bundle_license=_top_license(names, bundle),
        )
    fmt, tile = classify(source, names, deadline)
    return PackSniff(
        format=fmt, tile_size=tile, has_license=_has_license(names), marks=_marks(names)
    )

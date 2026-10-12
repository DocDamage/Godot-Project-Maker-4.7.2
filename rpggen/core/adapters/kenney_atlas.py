"""A sheet with the list of its rectangles beside it (T17.12).

``<TextureAtlas imagePath="sheet.png">`` with one ``<SubTexture name x y width height/>`` a
picture is what ShoeBox and TexturePacker write, and what Kenney's packs ship in a
``Spritesheet`` folder beside the loose pictures: the same art, packed. When the pack has the
loose pictures of those names they are used, and the sheet is left unused with the reason (the
art is there twice). A pack with only the sheet is read through the list: its rectangles become
the objects of the sheet, as the rectangles of a sprite cutter's manifest do (``cutter.py``).
"""

from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET  # noqa: S405 - local pack files; size-limited below
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile

MAX_ATLAS_BYTES = 8 * 1024 * 1024
ROOT_TAG = "TextureAtlas"
ENTRY_TAG = "SubTexture"
UNUSED_ATLAS_COPY = "atlas_copy"
LOOSE_SHARE = 0.5  # this share of the names as loose pictures: the pack has its art twice
FOOTPRINT_FRACTION = 0.3
_HEAD = 1024


def _is_atlas(root: Path, f: InventoryFile) -> bool:
    """True for an XML file that begins as a texture atlas (only its head is read)."""
    if f.ext != ".xml":
        return False
    try:
        with open(root / f.path, "rb") as fh:
            return b"<" + ROOT_TAG.encode() in fh.read(_HEAD)
    except OSError:
        return False


def read_atlas(path: Path) -> tuple[str, list[tuple[str, int, int, int, int]]]:
    """``(image name, [(name, x, y, width, height), ...])`` of a texture atlas file, the
    entries in the file's order. ``ValueError`` when it is not one or an entry has no
    rectangle."""
    if path.stat().st_size > MAX_ATLAS_BYTES:
        raise ValueError("the atlas is larger than 8 MB")
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8-sig"))  # noqa: S314
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    if root.tag != ROOT_TAG:
        raise ValueError("not a texture atlas")
    entries: list[tuple[str, int, int, int, int]] = []
    for el in root.iter(ENTRY_TAG):
        try:
            rect = [int(float(el.attrib[key])) for key in ("x", "y", "width", "height")]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"an entry has no rectangle ({exc})") from exc
        entries.append((str(el.attrib.get("name", "")), rect[0], rect[1], rect[2], rect[3]))
    return posixpath.basename(str(root.attrib.get("imagePath", "")).replace("\\", "/")), entries


def _stem(name: str) -> str:
    return posixpath.splitext(posixpath.basename(name))[0].casefold()


def _sheet_of(atlas: str, image: str, pictures: list[InventoryFile]) -> InventoryFile | None:
    """The sheet an atlas file lists: the picture beside it with its own name, else the one
    its ``imagePath`` names (which is often the name the sheet had before it was renamed),
    else the only picture of its folder."""
    folder = posixpath.dirname(atlas)
    beside = [f for f in pictures if posixpath.dirname(f.path) == folder]
    for wanted in (_stem(atlas), _stem(image) if image else None):
        named = [f for f in beside if wanted is not None and _stem(f.path) == wanted]
        if named:
            return named[0]
    return beside[0] if len(beside) == 1 else None


def _object(sheet: str, name: str, rect: tuple[int, int, int, int]) -> dict[str, Any]:
    x, y, w, h = rect
    fh = max(1, round(h * FOOTPRINT_FRACTION))
    fy = h - fh
    return {
        "sheet_path": sheet,
        "name": posixpath.splitext(posixpath.basename(name))[0] or "sprite",
        "role": "DECORATION",
        "region": [x, y, w, h],
        "origin": [w // 2, h - 1],
        "footprint": [0, fy, w, fh],
        "collision": {"profile": "CUSTOM", "polygon": [[0, fy], [w, fy], [w, h], [0, h]]},
        "tags": [],
        "status": "AUTO_DETECTED",
        "source": "auto",
        "authoritative": True,  # the rectangles of the list replace the guessed ones
    }


class KenneyAtlasAdapter:
    name = "kenney_atlas"
    priority = 47  # after the sprite cutter's manifest, before the readers of single pictures

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if any(_is_atlas(root, f) for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        pictures = [f for f in inv.files if f.kind == "image" and f.image is not None]
        atlases: list[tuple[InventoryFile, list[tuple[str, int, int, int, int]]]] = []
        for f in inv.files:
            if not _is_atlas(root, f):
                continue
            try:
                image, entries = read_atlas(root / f.path)
            except (OSError, ValueError):
                continue  # not a list rpggen can read: its sheet stays a picture
            sheet = _sheet_of(f.path, image, pictures)
            if sheet is not None and entries and sheet.path not in ctx.claimed:
                atlases.append((sheet, entries))
        sheets = {sheet.path for sheet, _entries in atlases}
        loose = {_stem(f.path) for f in pictures if f.path not in sheets}
        seen: set[str] = set()
        for sheet, entries in atlases:
            if sheet.path in seen or sheet.image is None:
                continue
            seen.add(sheet.path)
            w, h = int(sheet.image["w"]), int(sheet.image["h"])
            found = sum(1 for name, *_rect in entries if _stem(name) in loose)
            if found >= max(1, len(entries) * LOOSE_SHARE):
                facets = {
                    "usage": "sprite",
                    "frame": [w, h],
                    "origin": [w // 2, h - 1],
                    "role": "NONE",
                    "tags": [f"unused_because:{UNUSED_ATLAS_COPY}"],
                }
                result.assets.append(AssetFragment(sheet.path, facets, 0.9, "full"))
                continue
            inside = [
                (name, (x, y, rw, rh))
                for name, x, y, rw, rh in entries
                if x >= 0 and y >= 0 and rw > 0 and rh > 0 and x + rw <= w and y + rh <= h
            ]
            if len(inside) != len(entries):
                continue  # the list is of another picture: the sheet stays what it looks like
            result.objects.extend(_object(sheet.path, name, rect) for name, rect in inside)
        return result

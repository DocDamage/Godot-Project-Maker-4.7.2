"""One tile set in several forms, a pack in several sizes, and previews (T17.29).

Real packs ship the same art more than once:

* **Forms.** Kenney's *Tiny Farm* has its 132 tiles as a sheet with spacing, a packed sheet and
  132 single files; *Farm RPG* has every crop as a strip of its own and all of them again in a
  sheet of the season. Pictures that are the same tiles are found **by their content**: every
  cell of every picture is hashed, and a picture whose cells are all in another is a form of
  it. One form is used, the others are set aside (the role ``NONE``) with the reason
  (``unused_because:same_tiles`` or ``compiled_sheet``) and ``same_as:<path>`` on their cards:
  of two sheets with the same tiles the one read as tiles is used; single files that are cells
  of a sheet are set aside for the sheet; a sheet that is nothing but strips the pack also has
  one a file is set aside for the strips (they are named).
* **Sizes.** LimeZu's *Modern Farm* ships the pack at 16, 32 and 48 px, a folder (or a name) a
  size. The pictures of a size are tagged ``size_form:<n>``; ``choose_sizes`` keeps one size
  (the user's choice, else the size the other packs use, else the smallest) and sets the
  others aside (``other_size``). No tile set is made in a size the pack does not draw: in a
  farming pack or a pack of sizes, a sheet read as tiles of another size is cut again at the
  pack's size when it divides, else it is a picture and not a tile set.
* **Previews.** A GIF beside the sheet it shows (``Animated_gifs_16x16/Barn_Door_16x16.gif``
  beside ``Animated_sheets_16x16/Barn_Door_16x16.png``) is unused (``preview_gif``).

Everything here only sets aside or re-cuts what the readers made; nothing is added. No Qt.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SAME_TILES = "same_tiles"
COMPILED_SHEET = "compiled_sheet"
OTHER_SIZE = "other_size"
PREVIEW_GIF = "preview_gif"
SAME_AS_TAG = "same_as:"
SIZE_TAG = "size_form:"
MANIFEST_TAG = "pack_manifest"  # adapters.gridwright.MANIFEST_TAG (the adapters import us)
# what a form must share before it is one: a few cells in common are no set
MIN_SHARED_CELLS = 8
COVER = 0.9
MAX_CELLS = 60_000  # a picture with more cells than this is not hashed
PROTECTED_ROLES = frozenset({"CROP", "ANIMAL"})
_SIZE_TOKEN = re.compile(r"(?<![0-9])([0-9]{1,3})x([0-9]{1,3})(?![0-9])", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\s_\-]+")
_SIZED = re.compile(r"[\s_\-]*(?<![0-9])[0-9]{1,3}x[0-9]{1,3}(?![0-9])", re.IGNORECASE)


_SOURCE = "source_file:"  # adapters.farm.SOURCE_TAG (not imported: the adapters import us)


def _tags(asset: Any) -> list[str]:
    return [str(t) for t in asset.detected.get("tags") or []]


def _protected(asset: Any) -> bool:
    from rpggen.core import lpc_compose

    tags = _tags(asset)
    facets = asset.detected
    return (
        facets.get("usage") == "growth_strip"
        or (facets.get("role") in PROTECTED_ROLES and bool(facets.get("animations")))
        or lpc_compose.BODY_TAG in tags
        or lpc_compose.LAYER_TAG in tags
        or asset.detected.get("role") == "NONE"
        or MANIFEST_TAG in tags  # what a pack's own JSON says it is (adapters.gridwright)
    )


def aside(asset: Any, reason: str, same_as: str = "") -> None:
    """Set an asset aside: the role ``NONE`` with the reason (and the form that is used)."""
    from rpggen.core import classifier

    asset.detected["role"] = "NONE"
    asset.detected.pop("roles_alt", None)
    tags = {t for t in _tags(asset) if not t.startswith(SAME_AS_TAG)}
    tags.add(classifier.UNUSED_TAG + reason)
    if same_as:
        tags.add(SAME_AS_TAG + same_as)
    asset.detected["tags"] = sorted(tags)


def _rel(asset: Any, prefix: str) -> str | None:
    if "#" in asset.id or not asset.path.startswith(prefix + "/"):
        return None
    return asset.path[len(prefix) + 1 :]


# --------------------------------------------------------------------------- previews


def _bare(stem: str) -> str:
    return _SEPARATORS.sub("_", _SIZE_TOKEN.sub("", stem)).strip("_").casefold()


def gif_previews(assets: list[Any], prefix: str) -> int:
    """Set aside the GIFs that show a sheet the pack also has as a PNG of the same name."""
    stills: set[str] = set()
    gifs: list[tuple[Any, str]] = []
    for asset in assets:
        rel = _rel(asset, prefix)
        if rel is None:
            continue
        stem, ext = posixpath.splitext(posixpath.basename(rel))
        if ext.lower() == ".gif":
            gifs.append((asset, _bare(stem)))
        elif ext.lower() == ".png":
            stills.add(_bare(stem))
    count = 0
    for asset, key in gifs:
        if key in stills and asset.detected.get("role") != "NONE":
            aside(asset, PREVIEW_GIF)
            count += 1
    return count


# --------------------------------------------------------------------------- forms


def _cell_keys(a: np.ndarray, cell: int, margin: int = 0, gap: int = 0) -> list[bytes]:
    """The hashes of the painted cells of a picture cut in squares of ``cell``."""
    h, w = a.shape[:2]
    step = cell + gap
    cols, rows = (w - 2 * margin + gap) // step, (h - 2 * margin + gap) // step
    if cols <= 0 or rows <= 0 or cols * rows > MAX_CELLS:
        return []
    out: list[bytes] = []
    clear = a.copy()
    clear[clear[..., 3] == 0] = 0
    for r in range(rows):
        y = margin + r * step
        for c in range(cols):
            x = margin + c * step
            part = clear[y : y + cell, x : x + cell]
            if not part[..., 3].any():
                continue
            out.append(hashlib.sha1(part.tobytes()).digest())
    return out


def _load(path: Path) -> np.ndarray | None:
    try:
        with Image.open(path) as opened:
            return np.asarray(opened.convert("RGBA"))
    except (OSError, ValueError):
        return None


def _spacing(a: np.ndarray, cell: int) -> tuple[int, int]:
    """(margin, gap) of a sheet cut in squares of ``cell``: a gap of 1 or 2 clear pixels between
    the cells (Kenney's spaced sheets), else none."""
    h, w = a.shape[:2]
    alpha = a[..., 3]
    for gap in (1, 2):
        step = cell + gap
        if (w + gap) % step or (h + gap) % step:
            continue
        cols = [x for k in range(1, w // step + 1) for x in range(k * step - gap, k * step)]
        if cols and all(x < w for x in cols) and not alpha[:, cols].any():
            return 0, gap
    return 0, 0


def same_forms(assets: list[Any], inv: Any, pack_root: Path, prefix: str) -> int:
    """Find the pictures that are forms of one set of tiles and set all but one aside. Every
    still picture of the pack counts, also one a reader made something else of (a crop's
    strip): only those that are assets are set aside."""
    by_rel = {rel: a for a in assets if (rel := _rel(a, prefix)) is not None}
    files: dict[str, tuple[int, int]] = {}
    for f in getattr(inv, "files", ()):
        if f.kind == "image" and f.image and f.ext != ".gif":
            files[f.path] = (int(f.image["w"]), int(f.image["h"]))
    sizes: Counter[int] = Counter(w for w, h in files.values() if w == h and 8 <= w <= 64)
    # the cells of single files a pack has many of, and the 16 px most packs are drawn in
    cells = {cell for cell, singles in sizes.items() if singles >= MIN_SHARED_CELLS} | {16}
    count = 0
    pictures: dict[str, np.ndarray | None] = {}  # each picture read once for every cell
    for cell in sorted(cells):
        count += _forms_at(by_rel, files, pack_root, cell, pictures)
    return count


def _forms_at(
    by_rel: dict[str, Any],
    files: dict[str, tuple[int, int]],
    pack_root: Path,
    cell: int,
    pictures: dict[str, np.ndarray | None] | None = None,
) -> int:
    pictures = {} if pictures is None else pictures

    def load(rel: str) -> np.ndarray | None:
        if rel not in pictures:
            pictures[rel] = _load(pack_root / rel)
        return pictures[rel]

    keys: dict[str, set[bytes]] = {}
    one_cell: dict[str, bytes] = {}
    for rel in sorted(files):
        w, h = files[rel]
        if (w, h) == (cell, cell):
            a = load(rel)
            found = _cell_keys(a, cell) if a is not None else []
            if found:
                one_cell[rel] = found[0]
            continue
        if w < cell * 2 and h < cell * 2:
            continue
        if (w // cell) * (h // cell) > MAX_CELLS:
            continue
        a = load(rel)
        if a is None:
            continue
        margin, gap = _spacing(a, cell)
        if not gap and (w % cell or h % cell):
            continue
        painted = set(_cell_keys(a, cell, margin, gap))
        if len(painted) >= 2:
            keys[rel] = painted
    changed = 0
    used: dict[str, str] = {}  # a picture set aside -> the form that is used
    holders: dict[bytes, list[str]] = {}
    for rel in sorted(keys):
        for key in keys[rel]:
            holders.setdefault(key, []).append(rel)

    def shared_with(rel: str) -> Counter[str]:
        found: Counter[str] = Counter()
        for key in keys[rel]:
            others = holders[key]
            if len(others) <= 64:  # a cell every sheet has (plain grass) says nothing
                found.update(o for o in others if o != rel)
        return found

    # two sheets with the same tiles: the one read as tiles (else the first by name) is used
    sheets = sorted(keys, key=lambda r: (-len(keys[r]), r))
    for a_rel in sheets:
        if a_rel in used:
            continue
        for b_rel, shared in sorted(shared_with(a_rel).items()):
            if b_rel in used or b_rel == a_rel:
                continue
            if files[a_rel] == files[b_rel]:
                continue  # one picture twice: the duplicate of T13.04, information only
            big = max(len(keys[a_rel]), len(keys[b_rel]))
            if shared >= MIN_SHARED_CELLS and shared >= COVER * big:
                keep, drop = _better(by_rel, a_rel, b_rel)
                used[drop] = keep
                if drop == a_rel:
                    break
    for drop, keep in sorted(used.items()):
        if drop in by_rel and not _protected(by_rel[drop]):
            aside(by_rel[drop], SAME_TILES, keep)
            changed += 1
    kept = {r for r in keys if r not in used}
    # a sheet that is nothing but strips the pack has one a file: the named strips are used
    for sheet in sorted(kept, key=lambda r: (-len(keys[r]), r)):
        parts = sorted(
            r
            for r, shared in shared_with(sheet).items()
            if r in kept and len(keys[r]) < len(keys[sheet]) and shared >= COVER * len(keys[r])
        )
        covered: set[bytes] = set()
        for r in parts:
            covered |= keys[r] & keys[sheet]
        if len(parts) >= 2 and len(covered) >= max(MIN_SHARED_CELLS, COVER * len(keys[sheet])):
            asset = by_rel.get(sheet)
            if asset is not None and not _protected(asset):
                aside(asset, COMPILED_SHEET, parts[0])
                used[sheet] = parts[0]
                changed += 1
    # single files that are cells of a sheet that is used: the sheet is the form used
    index: dict[bytes, str] = {}
    for rel in sorted(kept):
        if rel in used:
            continue
        for key in keys[rel]:
            index.setdefault(key, rel)
    folders: dict[str, list[str]] = {}
    for rel in one_cell:
        folders.setdefault(posixpath.dirname(rel), []).append(rel)
    for _folder, members in sorted(folders.items()):
        inside = [r for r in members if one_cell[r] in index]
        if len(inside) < MIN_SHARED_CELLS or len(inside) < COVER * len(members):
            continue
        for rel in inside:
            asset = by_rel.get(rel)
            if asset is not None and not _protected(asset):
                aside(asset, SAME_TILES, index[one_cell[rel]])
                changed += 1
    return changed


def _better(by_rel: dict[str, Any], a: str, b: str) -> tuple[str, str]:
    """(the form that is used, the one set aside): a sheet read as tiles before one that was
    not, then the one the reader was surer of, then the first by name."""

    def rank(rel: str) -> tuple[int, float, str]:
        asset = by_rel.get(rel)
        if asset is None:  # a file a reader made part of another asset: it is used
            return (0, -2.0, rel)
        return (asset.detected.get("usage") != "tiles", -float(asset.confidence), rel)

    first, second = sorted((a, b), key=rank)
    return first, second


# --------------------------------------------------------------------------- sizes


def _size_key(rel: str) -> tuple[str, int] | None:
    """(the path without its sizes, the size) of a path that says one size (``16x16``)."""
    found = {int(a) for a, b in _SIZE_TOKEN.findall(rel) if a == b and 8 <= int(a) <= 128}
    if len(found) != 1:
        return None
    # ``Animals_16x16/Cows/Cow_16x16.png`` and ``Animals_32x32/Cows_32x32/Cow_32x32.png``
    return _SIZED.sub("", rel).casefold(), found.pop()


def mark_sizes(assets: list[Any], prefix: str) -> list[int]:
    """Tag the pictures of a pack drawn in several sizes (``size_form:<n>``); the sizes the
    pack draws, smallest first ([] for a pack of one size). A size is one when three names
    or more come in it and in another size, and their pictures are as much larger as their
    sizes say."""
    found: dict[str, dict[int, Any]] = {}
    for asset in assets:
        rel = _rel(asset, prefix)
        crop = ""
        if rel is None:
            # a crop's strip drawn from the pack's file (adapters.farm.SOURCE_TAG): the
            # file's size is the strip's, and the crop's name tells the strips of a sheet
            said = _tags(asset)
            rel = next((t[len(_SOURCE) :] for t in said if t.startswith(_SOURCE)), None)
            crop = "#" + ",".join(t for t in said if t.startswith("produce:"))
        if rel is None:
            continue
        keyed = _size_key(rel)
        if keyed is not None:
            found.setdefault(keyed[0] + crop, {})[keyed[1]] = asset
    pairs: Counter[int] = Counter()
    for members in found.values():
        if len(members) < 2:
            continue
        sizes = sorted(members)
        base = members[sizes[0]].detected.get("size") or [0, 0]
        for n in sizes:
            size = members[n].detected.get("size") or [0, 0]
            scale = n / sizes[0]
            if (
                base[0]
                and abs(size[0] - base[0] * scale) <= 1
                and abs(size[1] - base[1] * scale) <= 1
            ):
                pairs[n] += 1
    offered = sorted(n for n, k in pairs.items() if k >= 3)
    if len(offered) < 2:
        return []
    for members in found.values():
        for n, asset in members.items():
            tags = {t for t in _tags(asset) if not t.startswith(SIZE_TAG)}
            tags.add(f"{SIZE_TAG}{n}")
            asset.detected["tags"] = sorted(tags)
    return offered


def size_of(asset: Any) -> int | None:
    for tag in _tags(asset):
        if tag.startswith(SIZE_TAG) and tag[len(SIZE_TAG) :].isdigit():
            return int(tag[len(SIZE_TAG) :])
    return None


# --------------------------------------------------------------------------- per pack


def apply(
    assets: list[Any], inv: Any, pack_root: Path, prefix: str, farm_pack: bool
) -> dict[str, Any]:
    """What this module does to one pack's assets, right after the readers (see the module)."""
    previews = gif_previews(assets, prefix)
    offered = mark_sizes(assets, prefix)
    forms = same_forms(assets, inv, pack_root, prefix)
    forms += trimmed_copies(assets, prefix)
    return {"previews": previews, "sizes": offered, "forms": forms, "farm": farm_pack}


TRIMMED = "trimmed_copy"
# the words of a folder of the same pictures cut to what they paint, each its own size
TRIMMED_WORDS = (frozenset({"variable", "sizes"}), frozenset({"variable", "size"}),
                 frozenset({"trimmed"}), frozenset({"cropped"}))  # fmt: skip


def trimmed_copies(assets: list[Any], prefix: str) -> int:
    """Kenney ships a platformer's people twice (T17.33: *Platformer Pack Remastered*'s
    ``Players/128x256/Beige/alienBeige_walk1.png`` and ``Players/Variable sizes/Beige/...``, the
    same frames cut to what they paint): the frames of fixed size are read as the animated player,
    and the trimmed ones were each a decoration of the dock. A picture in a folder named for
    trimmed copies (``Variable sizes``, ``Trimmed``) whose parent folder also holds a folder
    named by a size (``128x256``) is set aside (``trimmed_copy``). Returns how many."""
    folders: dict[str, set[str]] = {}
    for asset in assets:
        rel = _rel(asset, prefix)
        if rel is None:
            continue
        parts = rel.split("/")[:-1]
        for i in range(len(parts)):
            folders.setdefault("/".join(parts[:i]), set()).add(parts[i])
    changed = 0
    for asset in assets:
        rel = _rel(asset, prefix)
        if rel is None or _protected(asset):
            continue
        parts = rel.split("/")[:-1]
        for i, name in enumerate(parts):
            said = set(_SEPARATORS.split(name.casefold()))
            if not any(words <= said for words in TRIMMED_WORDS):
                continue
            parent = "/".join(parts[:i])
            sized = sorted(n for n in folders.get(parent, ()) if _SIZE_TOKEN.fullmatch(n.strip()))
            if sized:
                aside(asset, TRIMMED, "/".join([*parts[:i], sized[0]]))
                changed += 1
            break
    return changed


def offered_sizes(assets: list[Any]) -> list[int]:
    return sorted({n for a in assets if (n := size_of(a)) is not None})


def dominant_cell(assets: list[Any]) -> int | None:
    """The cell most of a pack's sheets of tiles are cut in (the smaller of a tie)."""
    cells: Counter[int] = Counter()
    for asset in assets:
        grid = asset.detected.get("grid") or {}
        cell = grid.get("cell")
        tiles = asset.detected.get("usage") == "tiles" and asset.detected.get("role") != "NONE"
        if tiles and cell and cell[0] == cell[1]:
            cells[int(cell[0])] += 1
    if not cells:
        return None
    return min(cells, key=lambda c: (-cells[c], c))


def choose_sizes(catalog: Any, chosen: dict[str, int], farm_packs: set[str]) -> dict[str, int]:
    """Keep one size of every pack drawn in several (``chosen[pack]`` when it is one of them,
    else the size the other packs use, else the smallest) and set the other sizes aside; then
    cut again (or make pictures of) the sheets of tiles of another size in such a pack and in a
    farming pack. Returns ``{pack: size}`` of the packs of several sizes."""
    by_pack: dict[str, list[Any]] = {}
    for asset in catalog.assets:
        if asset.kind == "image":
            by_pack.setdefault(asset.pack_id, []).append(asset)
    sizes = {p: offered_sizes(a) for p, a in by_pack.items()}
    out: dict[str, int] = {}
    for pack_id in sorted(by_pack):
        offered = sizes[pack_id]
        if not offered:
            continue
        others = [a for p, members in by_pack.items() if p != pack_id and not sizes[p]
                  for a in members]  # fmt: skip
        theirs = dominant_cell(others)
        size = chosen.get(pack_id)
        if size not in offered:
            size = theirs if theirs in offered else offered[0]
        out[pack_id] = int(size)
        for asset in by_pack[pack_id]:
            n = size_of(asset)
            if n is not None and n != size and asset.detected.get("role") != "NONE":
                aside(asset, OTHER_SIZE)
    for pack_id in sorted((farm_packs | set(out)) & set(by_pack)):
        _other_engine(by_pack[pack_id], f"assets/packs/{pack_id}")
    for pack_id in sorted(farm_packs & set(by_pack)):
        _character_sheets(by_pack[pack_id], f"assets/packs/{pack_id}")
        _sheets_of_buildings(by_pack[pack_id], out.get(pack_id) or dominant_cell(by_pack[pack_id]))
    for pack_id in sorted(by_pack):
        if pack_id not in out and pack_id not in farm_packs:
            continue
        size = out.get(pack_id) or dominant_cell(by_pack[pack_id])
        if size:
            _one_tile_size(by_pack[pack_id], int(size), sizes[pack_id])
    return out


def _other_engine(assets: list[Any], prefix: str) -> None:
    """In a farming pack or a pack of several sizes, a folder ``RPG_Maker_MV`` (or another RPG
    Maker's) beside the pack's own pictures is the same art laid out for another engine, at
    its own size (*Modern Farm*'s at 48 px): it is set aside, as the copies of a pack of
    engine folders are (T16.21), and its sheets make no terrain of the project's tile set."""

    inside, outside = [], 0
    for asset in assets:
        rel = _rel(asset, prefix)
        if rel is None:
            continue
        folders = [f.casefold() for f in rel.split("/")[:-1]]
        if any(re.sub(r"[^a-z]", "", f).startswith("rpgmaker") for f in folders):
            inside.append(asset)
        elif asset.detected.get("usage") == "tiles":
            outside += 1
    if not outside:
        return  # an RPG Maker pack: its folder is the pack
    for asset in inside:
        if asset.detected.get("role") != "NONE":
            aside(asset, ENGINE_COPY)


CHARACTER_SHEET = "character_sheet"
ENGINE_COPY = "engine_copy"
CHARACTER_FOLDER_WORDS = frozenset({"character", "characters", "animal", "animals", "npc", "npcs"})


def _character_sheets(assets: list[Any], prefix: str) -> None:
    """In a farming pack, a sheet of a folder of characters or animals that the readers took
    for tiles (LimeZu's 6144 px sheets of a farmer, a dog in rows, the guide to the rows) is no
    ground: it is set aside (``character_sheet``) rather than cut into thousands of things."""
    from rpggen.core import classifier

    for asset in assets:
        rel = _rel(asset, prefix)
        if rel is None or asset.detected.get("usage") != "tiles":
            continue
        if asset.detected.get("role") == "NONE":
            continue
        folders, stem = classifier.tokens(rel)
        if set(folders) & CHARACTER_FOLDER_WORDS or "guide" in stem:
            aside(asset, CHARACTER_SHEET)


MANY_BUILDINGS = "many_buildings"
CUT_PARTS = "generated/sheet_parts/"  # adapters.sheet_parts (not imported: they import us)
BUILDING_MAX_TILES = 12
# what a picture of one building of a farming pack is called (else it is a thing of one)
HOUSE_NAMES = frozenset(
    {"house", "houses", "home", "barn", "coop", "mill", "windmill", "shop", "store", "building",
     "cabin", "hut", "stable", "silo", "greenhouse", "farmhouse", "cottage", "shed", "bakery",
     "inn", "tavern", "church", "school", "market"}
)  # fmt: skip
BUILDING_PIECE_WORDS = frozenset(
    {"door", "doors", "window", "windows", "lamp", "lamps", "vane", "sign", "signs", "roof",
     "roofs", "chimney", "partition", "objects", "fence", "fences", "wall", "walls", "railing",
     "railings", "corner", "corners", "stairs", "steps", "part", "parts", "piece", "pieces"}
)  # fmt: skip


def _sheets_of_buildings(assets: list[Any], tile: int | None) -> None:
    """In a farming pack, a picture taken for one building that is more than twelve tiles wide
    or high is a sheet of several (*Farm RPG*'s ``Barn.png``, 496 x 176): the village's house
    with its door in the middle of three barns could not be entered. It is set aside; the
    things cut from it stay."""
    from rpggen.core import classifier

    size = int(tile or 16)
    for asset in assets:
        facets = asset.detected
        if facets.get("role") != "BUILDING" or facets.get("usage") not in ("sprite", "object"):
            continue
        if asset.path.startswith(CUT_PARTS):
            continue  # one thing cut from a sheet of buildings (T17.30): its reader measured it
        w, h = (facets.get("size") or [0, 0])[:2]
        if w > BUILDING_MAX_TILES * size or h > BUILDING_MAX_TILES * size:
            aside(asset, MANY_BUILDINGS)
            continue
        _folders, stem = classifier.tokens(asset.path)
        said = {word.rstrip("0123456789") for word in stem}
        if not said & HOUSE_NAMES or said & BUILDING_PIECE_WORDS or w < 2 * size or h < 2 * size:
            # a door, a window or a weather vane of a barn is a thing of a building, no house
            facets["role"] = "DECORATION"
            facets.pop("roles_alt", None)


def sizes_of(catalog: Any, pack_id: str) -> list[int]:
    """The sizes a pack of the catalog is drawn in ([] for a pack of one size)."""
    return offered_sizes([a for a in catalog.assets if a.pack_id == pack_id])


def use_size(catalog: Any, pack_id: str, size: int) -> bool:
    """Use another of a pack's sizes (the Audit page's choice): its pictures of that size are
    what the readers made of them again, those of the other sizes are set aside. False when
    the pack is not drawn in that size or uses it already."""
    from rpggen.core import catalog as catalog_mod
    from rpggen.core import classifier

    if size not in sizes_of(catalog, pack_id) or catalog.pack_sizes.get(pack_id) == size:
        return False
    reason = classifier.UNUSED_TAG + OTHER_SIZE
    for asset in catalog.assets:
        n = size_of(asset) if asset.pack_id == pack_id else None
        if n is None:
            continue
        if n != size:
            if asset.detected.get("role") != "NONE":
                aside(asset, OTHER_SIZE)
        elif reason in _tags(asset):
            tags = [t for t in _tags(asset) if t != reason and not t.startswith(SAME_AS_TAG)]
            bare = {k: v for k, v in asset.detected.items() if k not in ("role", "roles_alt")}
            rel = asset.path.split("/", 3)[-1]
            asset.detected["role"] = classifier.classify(bare, rel, None)[0]
            asset.detected["tags"] = sorted(tags)
        asset.status = catalog_mod.recompute_status(asset)
    catalog.pack_sizes = {**catalog.pack_sizes, pack_id: int(size)}
    return True


def _one_tile_size(assets: list[Any], size: int, offered: list[int]) -> None:
    """No tile set in a size the pack does not draw: a sheet of tiles of another cell is cut at
    ``size`` when the size divides it, is set aside when its cell is another size the pack is
    drawn in (an RPG Maker copy at 48 px), and is a picture otherwise."""
    for asset in assets:
        facets = asset.detected
        grid = facets.get("grid") or {}
        cell = grid.get("cell")
        if facets.get("usage") != "tiles" or not cell or facets.get("role") == "NONE":
            continue
        if list(cell) == [size, size]:
            continue
        if asset.path.startswith(CUT_PARTS):
            aside(asset, OTHER_SIZE)  # tiles cut from loose squares, of another size (T17.30)
            continue
        w, h = (facets.get("size") or [0, 0])[:2]
        own = size_of(asset) == size  # drawn at the size that is used: cut it at that size
        if not own and cell[0] == cell[1] and cell[0] in offered:
            aside(asset, OTHER_SIZE)
        elif w and h and w % size == 0 and h % size == 0:
            facets["grid"] = {"cell": [size, size], "margin": [0, 0], "separation": [0, 0]}
        else:
            facets["usage"] = "sprite"
            facets.pop("grid", None)
            facets["frame"] = [w, h]
            facets["origin"] = [w // 2, max(0, h - 1)]
            if facets.get("role") in ("GROUND", "WALL", "WATER", "AUTOTILE"):
                facets["role"] = "DECORATION"
                facets.pop("roles_alt", None)

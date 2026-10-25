"""Sheets a cutting tool cut into named pictures, read back as the sheets they are.

Some packs ship every tile and every thing of a sheet as a picture of its own, with an
``_atlas.json`` beside the pictures that says where each was cut (SakPix's stage sets,
GandalfHardcore's *Medieval Fantasy* assets as the owner's collection has them):

    {"source": "Dark Forest Tiles.png", "tile": 16,
     "sprites": [{"name": "dark_forest_r00_c00", "file": "tiles/dark_forest_r00_c00.png",
                  "x": 0, "y": 0, "w": 16, "h": 16}, ...]}

``cell`` (or ``tile``) is the tile size of a tile sheet; ``frame`` ([w, h]) makes the source a
strip of animation frames. The source sheet lies beside the folder of pictures (or in it).
Read one picture at a time, such a pack is hundreds of loose tiles no reader can join, and every
one of them is imported twice over. Here:

* a **tile sheet**'s source becomes the pack's tile sheet, read by the side-view reader
  (``side_tiles``) like any other, and the pictures of its cells are set aside as the same
  tiles. A sheet whose every tile is drawn as a block of its own, a see-through margin and
  mostly a dark outline round it (SakPix), is first **taken out of its outlines** into a
  generated copy: on each side a tile's art fills, the margin, the outline and the rim just
  inside it are drawn again from the pixels inside, so tiles side by side join; the outline
  along a side the art does not fill (a surface's top, a ledge's end) stays, it is the
  ground's silhouette. Its blocks seldom join one another by their seams (each is a variant
  drawn on its own), so the blocks the reader leaves whose name says a ground make
  **terrains by name**: the sides a block fills are its peering. The
  pack's own files are never changed. The cells' **names** then say what the pixels cannot: a
  ledge or a walkway is one-way, a slope slopes, spikes and thorns hurt, grass, ferns, flowers,
  mushrooms, stalactites, hanging vines and moss are decorations of a kind (``mds_kind``, as
  the Metroidvania Developer System reads them) and never collide. Things the sheet holds (a
  log, a cabin, a cart) stay in the dock as the pictures they were cut as.
* a **frame strip**'s source becomes one animated picture, and its frames' pictures are set
  aside.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen.core import side_tiles

MANIFEST = "_atlas.json"
ATLAS_TAG = "atlas_cut"
SOURCE_ASIDE = "atlas_source"  # the outlined source of a generated copy
CELL_ASIDE = "atlas_cell"  # the picture of a cell the sheet holds as a tile
FRAME_ASIDE = "atlas_frame"  # the picture of a frame of a strip
OUTLINE_TAG = "outlines_removed"

ALPHA = 128
DARK = 40  # the brightest channel of an outline pixel (0..255)
MAX_BAND = 3  # a margin and an outline are at most this many px together
RIM = 8  # brightness by which the pixel just inside an outline stands out as a rim
REACH = 0.7  # the share of a side's lines the art reaches for the side to join a neighbour
OUTLINED = 0.6  # the share of the sides tiles reach that have a margin: a block sheet
FRAME_FPS = 8.0
CHARACTER_ROLES = ("PLAYER", "NPC", "ENEMY", "BOSS")

# the words of a cell's name -> what the tile is; checked in this order
ONE_WAY_WORDS = frozenset({"ledge", "ledges", "platform", "platforms", "plank", "planks",
                           "walkway", "walkways", "bridge", "scaffold", "shelf"})  # fmt: skip
SLOPE_WORDS = frozenset({"slope", "slopes", "ramp", "ramps", "hill", "incline"})
HAZARD_WORDS = frozenset({"spike", "spikes", "thorn", "thorns", "thorny", "acid", "lava",
                          "bramble", "brambles", "trap"})  # fmt: skip
LADDER_WORDS = frozenset({"ladder", "ladders"})
# a building a cell holds whole, ladder and all (*Magic Forest*'s treehouse_ladder): a thing to
# place, not a ladder to climb
BUILDING_WORDS = frozenset({"house", "treehouse", "hut", "cabin", "cottage", "shack", "tower",
                            "home", "tent", "barn", "shop"})  # fmt: skip
# the decoration kinds of the Metroidvania Developer System (its tile palette's KNOWN_KINDS);
# builder/lib/side_tileset.gd reads the same words off a sheet's name
KIND_WORDS = {
    "grass": "grass", "grasses": "grass", "tuft": "grass", "tufts": "grass", "weed": "grass",
    "weeds": "grass", "sprout": "grass", "sprouts": "grass", "blades": "grass",
    "fern": "fern", "ferns": "fern", "plant": "fern", "plants": "fern",
    "flower": "flower", "flowers": "flower", "wildflowers": "flower", "bloom": "flower",
    "blossom": "flower", "blossoms": "flower",
    "mushroom": "mushroom", "mushrooms": "mushroom", "shroom": "mushroom", "fungus": "mushroom",
    "fungi": "mushroom", "toadstool": "mushroom",
    "stalactite": "stalactite_small", "stalactites": "stalactite_small",
    "icicle": "stalactite_small", "icicles": "stalactite_small",
    "foliage": "foliage", "leaves": "foliage", "leaf": "foliage", "bush": "foliage",
    "bushes": "foliage", "shrub": "foliage", "shrubs": "foliage", "hedge": "foliage",
}  # fmt: skip
HANGING_WORDS = frozenset({"vine", "vines", "moss", "roots", "root", "cobweb", "cobwebs"})
LARGE_WORDS = frozenset({"large", "big", "huge", "long", "giant"})
# pixel kinds the side-view reader may take a busy tile for: kept only when the name says so
NAMED_ONLY_KINDS = {side_tiles.DOOR: "door", side_tiles.KEY: "key", side_tiles.FLAG: "flag",
                    side_tiles.COIN: "coin"}  # fmt: skip
# a ground the name says: solid where the reader found no terrain for it
GROUND_WORDS = frozenset({"ground", "fill", "dirt", "soil", "earth", "stone", "brick", "bricks",
                          "cobble", "cobblestone", "rock", "mud", "floor", "block", "wall",
                          "slab", "flagstone", "gravel", "sand", "cliff", "strata"})  # fmt: skip


def manifests(pack_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every ``_atlas.json`` below a pack folder that names a source and its cuts, by path."""
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(pack_root.rglob(MANIFEST)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("sprites"), list):
            continue
        if not isinstance(data.get("source"), str):
            continue
        out.append((path, data))
    return out


def source_of(manifest: Path, data: dict[str, Any]) -> Path | None:
    """The sheet a manifest's pictures were cut from: beside its folder, else in it."""
    for folder in (manifest.parent.parent, manifest.parent):
        found = folder / str(data["source"])
        if found.is_file():
            return found
    return None


def cell_of(data: dict[str, Any]) -> int:
    """The tile size of a tile sheet's manifest; 0 for a strip of frames or a sheet of things."""
    if data.get("frame") is not None:
        return 0
    for key in ("cell", "tile"):
        value = data.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


def tile_sources(pack_root: Path, root: str) -> set[str]:
    """The catalog paths (``root``/...) of the sheets the pack's manifests say were cut into
    tiles."""
    out: set[str] = set()
    for manifest, data in manifests(pack_root):
        source = source_of(manifest, data)
        if source is not None and cell_of(data):
            out.add(posixpath.join(root, source.relative_to(pack_root).as_posix()))
    return out


def frame_of(data: dict[str, Any]) -> tuple[int, int] | None:
    value = data.get("frame")
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, int) and v > 0 for v in value)
    ):
        return int(value[0]), int(value[1])
    return None


# --------------------------------------------------------------------------- outlines


def _lines(side: str, h: int, w: int) -> list[list[tuple[int, int]]]:
    """For each line across ``side`` of a cell: its pixels from the edge inward."""
    if side == "W":
        return [[(y, x) for x in range(w)] for y in range(h)]
    if side == "E":
        return [[(y, w - 1 - x) for x in range(w)] for y in range(h)]
    if side == "N":
        return [[(y, x) for y in range(h)] for x in range(w)]
    return [[(h - 1 - y, x) for y in range(h)] for x in range(w)]


def reach(cell: np.ndarray, side: str) -> float:
    """The share of the lines across ``side`` whose art comes within MAX_BAND px of the edge."""
    h, w = cell.shape[:2]
    alpha = cell[:, :, 3] >= ALPHA
    lines = _lines(side, h, w)
    near = sum(1 for line in lines if any(alpha[p] for p in line[:MAX_BAND]))
    return near / len(lines) if lines else 0.0


def joins(cell: np.ndarray) -> set[str]:
    """The sides ("N", "E", "S", "W") a cell's art fills: those that join a neighbour."""
    return {side for side in "NESW" if reach(cell, side) >= REACH}


def _bordered(cell: np.ndarray, side: str) -> bool:
    """True when most lines across ``side`` in its middle third start with a see-through margin
    a pixel or two wide: a tile drawn as a block of its own. Its outline may be black, the dark
    of its own colours (*Magic Forest*'s moss) or none (*Medievil Kingdom*'s bricks)."""
    h, w = cell.shape[:2]
    alpha = cell[:, :, 3] >= ALPHA
    lines = _lines(side, h, w)
    middle = lines[len(lines) // 3 : 2 * len(lines) // 3] or lines
    hits = 0
    for line in middle:
        m = 0
        while m < MAX_BAND and not alpha[line[m]]:
            m += 1
        if 1 <= m < MAX_BAND:
            hits += 1
    return hits * 2 > len(middle)


def outlined(cells: list[np.ndarray]) -> bool:
    """True for a sheet whose tiles are blocks of their own (SakPix): of the sides its painted
    tiles reach, most have a see-through margin. A sheet of tiles that join (GandalfHardcore's)
    has no margin inside its ground."""
    sides = hit = 0
    for cell in cells:
        if (cell[:, :, 3] >= ALPHA).mean() < 0.3:
            continue
        for side in joins(cell) - {"S"}:  # a block's foot often has no margin, its sides do
            sides += 1
            hit += _bordered(cell, side)
    return sides > 0 and hit >= OUTLINED * sides


def deoutline(cell: np.ndarray, sides: set[str]) -> np.ndarray:
    """``cell`` with the margin, the outline and the rim of each of ``sides`` drawn again from
    the pixels inside, mirrored: neighbours on those sides join it without a dark line."""
    out = cell.copy()
    h, w = cell.shape[:2]
    for side in sorted(sides):
        alpha = out[:, :, 3] >= ALPHA
        dark = alpha & (out[:, :, :3].max(axis=2) <= DARK)
        for line in _lines(side, h, w):
            band = 0
            while band < len(line) and band < MAX_BAND and not alpha[line[band]]:
                band += 1
            while band < len(line) and band < MAX_BAND and dark[line[band]]:
                band += 1
            if band == 0 or band >= len(line) // 2 or not alpha[line[band]]:
                continue  # beside a rounded corner the sky goes on: nothing to carry out
            # the highlight or shadow just inside the outline goes too, when it stands out
            if band + 2 < len(line) // 2 and alpha[line[band + 1]]:
                rim = float(out[line[band]][:3].astype(int).mean())
                inner = float(out[line[band + 1]][:3].astype(int).mean())
                if abs(rim - inner) > RIM:
                    band += 1
            for k in range(band):
                out[line[k]] = out[line[2 * band - 1 - k]]
    return out


# --------------------------------------------------------------------------- names


def _words(name: str) -> set[str]:
    from rpggen.core.side_packs import words

    return set(words(name))


def mds_kind(name: str) -> str:
    """The decoration kind a cell's name says, "" for none, for a mix of kinds, or for a ground
    the name also says (``grass_ground``, ``moss_dirt_block``: the ground, not tufts on it)."""
    said = _words(name)
    if said & GROUND_WORDS:
        return ""
    found = {KIND_WORDS[w] for w in said if w in KIND_WORDS}
    if not found and said & HANGING_WORDS and ({"hanging", "hang"} & said or "moss" in said):
        return "hanging_moss"
    if len(found) != 1:
        return ""
    kind = found.pop()
    if kind == "stalactite_small" and said & LARGE_WORDS:
        return "stalactite_large"
    return kind


def named_override(name: str, cell: np.ndarray, joined: set[str], size: int) -> dict[str, Any]:
    """What a cell's name says it is, for a cell the side-view reader left unread: {} when the
    name says nothing a tile carries."""
    said = _words(name)
    if said & LADDER_WORDS and not said & BUILDING_WORDS:
        return {"collision": {"profile": "LADDER"}, "custom": {"ladder": True}}
    if said & HAZARD_WORDS:
        return {"collision": {"profile": "NONE"}, "custom": {"hazard": True}}
    if said & SLOPE_WORDS:
        slope = side_tiles.slope_of(cell[:, :, 3] >= side_tiles.ALPHA)
        if slope is not None:
            return {"collision": side_tiles.slope_collision(slope, size, size),
                    "custom": {"side": "slope_" + slope, "slope": slope}}  # fmt: skip
    if said & ONE_WAY_WORDS:
        return {"collision": {"profile": "ONE_WAY"}, "custom": {"side": "one_way"}}
    kind = mds_kind(name)
    if kind:
        return {"collision": {"profile": "NONE"}, "custom": {"mds_kind": kind}}
    if said & GROUND_WORDS and len(joined) >= 3:
        return {"collision": {"profile": "FULL"}, "custom": {"side": "ground"}}
    return {}


def _keep_read(name: str, entry: dict[str, Any], joined: set[str]) -> bool:
    """Whether what the side-view reader said of a cell stands against its name and shape: a
    terrain piece joins a neighbour on two sides at least (a log on the ground joins it on
    one), and a door, a key, a flag or a coin is one only when its name says so."""
    if "terrain" in entry:
        return len(joined) >= 2 and not mds_kind(name)
    side = str((entry.get("custom") or {}).get("side", ""))
    if side in NAMED_ONLY_KINDS:
        return NAMED_ONLY_KINDS[side] in _words(name)
    return True


SIDE_BITS = {"N": side_tiles.N, "E": side_tiles.E, "S": side_tiles.S, "W": side_tiles.W}
NOT_GROUND_WORDS = ONE_WAY_WORDS | SLOPE_WORDS | HAZARD_WORDS | LADDER_WORDS


def _earth(cell: np.ndarray) -> str:
    """The ground a block is of, by the colour of its lower third (under a grass top, the
    earth): grass, stone, dirt..."""
    h = cell.shape[0]
    band = cell[h - max(1, h // 3) :].reshape(-1, 4)
    painted = band[band[:, 3] >= ALPHA][:, :3].astype(np.float32) / 255.0
    return side_tiles.surface_of(painted.mean(axis=0) if painted.size else np.zeros(3))


def named_terrains(
    pictures: dict[str, np.ndarray], joined: dict[str, set[str]], keys: dict[str, str],
    read: side_tiles.SheetRead, pixels: np.ndarray, size: int,
) -> None:  # fmt: skip
    """Terrains of a block sheet out of the ground the reader left: its blocks join no other by
    their seams (each is drawn as a variant of its own), but taken out of their outlines, the
    sides a block fills are its peering. Blocks whose name says a ground go together by their
    earth; a terrain needs a fill and a top. Added to ``read``."""
    taken = set(read.kinds) | {k for _s, members in read.terrains for k in members}
    groups: dict[str, dict[str, int]] = {}
    for key, name in keys.items():
        said = _words(name)
        picture = pictures[name]
        if key in taken or not said & GROUND_WORDS or said & NOT_GROUND_WORDS or mds_kind(name):
            continue
        if (picture[:, :, 3] >= ALPHA).mean() < side_tiles.PIECE_COVER or len(joined[name]) < 2:
            continue
        bits = 0
        for side in joined[name]:
            bits |= SIDE_BITS[side]
        groups.setdefault(_earth(picture), {})[key] = bits
    tops = side_tiles.E | side_tiles.S | side_tiles.W
    room = side_tiles.MAX_TERRAINS - len(read.terrains)
    added: list[tuple[str, dict[str, int]]] = []
    for members in sorted(groups.values(), key=len, reverse=True):
        if len(added) >= room:
            break
        top = next((k for k, b in members.items() if b == tops), None)
        if top is None or side_tiles.ALL not in members.values():
            continue
        name = keys[top]
        surface = side_tiles.surface_of(side_tiles._top_band(side_tiles.Cell(0, 0, pictures[name])))
        added.append((surface, members))
    if not added:
        return
    mine = side_tiles.SheetRead(terrains=added)
    side_tiles._middles(side_tiles.cells_of(pixels, size, size, (0, 0), (0, 0)), mine)
    read.terrains.extend(added)
    read.alternates |= mine.alternates
    read.variants.update(mine.variants)


# --------------------------------------------------------------------------- reading a pack


def _cells(data: dict[str, Any], size: int, shape: tuple[int, ...]) -> list[dict[str, Any]]:
    """The sprites of a tile manifest that are one whole cell of the sheet."""
    h, w = shape[:2]
    out = []
    for s in data["sprites"]:
        try:
            x, y, sw, sh = (int(s[k]) for k in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError):
            continue
        if (
            sw == size
            and sh == size
            and x % size == 0
            and y % size == 0
            and x + sw <= w
            and y + sh <= h
        ):
            out.append({**s, "x": x, "y": y})
    return out


def _load(path: Path) -> np.ndarray | None:
    try:
        with Image.open(path) as im:
            return np.asarray(im.convert("RGBA")).copy()
    except (OSError, ValueError):
        return None


class SheetCut:
    """What reading one tile manifest gave: the asset that is the sheet now (the pack's source,
    or a generated copy out of its outlines), and the side-view reading of it."""

    def __init__(self, asset: Any, read: side_tiles.SheetRead | None, overrides: dict[str, Any],
                 generated: tuple[str, Path] | None) -> None:  # fmt: skip
        self.asset = asset
        self.read = read
        self.overrides = overrides
        self.generated = generated


def read_pack(
    assets: list[Any], pack_root: Path, root: str, work: Path, pack_id: str
) -> list[SheetCut]:
    """The atlas cuts of one side-view pack. Strips of frames become animated pictures in place;
    tile sheets come back as SheetCuts for ``side_packs.read_tiles`` to give terrain sets. The
    pictures a sheet or a strip already holds are set aside as the same art."""
    from rpggen.core.catalog import Asset
    from rpggen.core.side_packs import SIDE_DIR, SIDE_TAG, _add_tags, _as_picture, _aside
    from rpggen.core.terrain import GENERATED_PACK

    by_path = {a.path: a for a in assets if "#" not in a.id}
    out: list[SheetCut] = []
    exports: dict[str, str] = {}
    for manifest, data in manifests(pack_root):
        source = source_of(manifest, data)
        if source is None:
            continue
        source_rel = posixpath.join(root, source.relative_to(pack_root).as_posix())
        source_asset = by_path.get(source_rel)
        exports[" ".join(sorted(_words(source.stem)))] = source_rel
        folder_rel = manifest.parent.relative_to(pack_root).as_posix()

        def piece(entry: dict[str, Any], folder_rel: str = folder_rel) -> Any:
            rel = posixpath.normpath(posixpath.join(folder_rel, str(entry.get("file", ""))))
            return by_path.get(posixpath.join(root, rel))

        frame = frame_of(data)
        if frame is not None:
            if source_asset is not None:
                _strip(source_asset, data, frame)
                for entry in data["sprites"]:
                    got = piece(entry)
                    if got is not None and got is not source_asset:
                        _aside(got, FRAME_ASIDE, source_rel)
            continue
        size = cell_of(data)
        if source_asset is None:
            continue
        if size == 0:
            # a sheet of things (*Village*'s houses, stalls and roofs): the things are the
            # pictures cut from it, the sheet the same art once more
            if any(piece(entry) is not None for entry in data["sprites"]):
                _aside(source_asset, SOURCE_ASIDE, posixpath.join(root, folder_rel))
            continue
        sheet = _load(source)
        if sheet is None:
            continue
        cells = _cells(data, size, sheet.shape)
        if not cells:
            continue
        pictures = {c["name"]: sheet[c["y"] : c["y"] + size, c["x"] : c["x"] + size] for c in cells}
        is_block_sheet = outlined(list(pictures.values()))
        joined = {name: joins(p) for name, p in pictures.items()}
        pixels = sheet
        if is_block_sheet:
            pixels = sheet.copy()
            for c in cells:
                fixed = deoutline(pictures[c["name"]], joined[c["name"]])
                pixels[c["y"] : c["y"] + size, c["x"] : c["x"] + size] = fixed
                pictures[c["name"]] = fixed
        read = side_tiles.read(pixels, (size, size))
        by_key = {f"{c['x'] // size},{c['y'] // size}": c["name"] for c in cells}
        if is_block_sheet:
            named_terrains(pictures, joined, by_key, read, pixels, size)
        overrides: dict[str, dict[str, Any]] = {}
        names = [f"atlas_{i}" for i in range(len(read.terrains))]  # renamed by read_tiles
        for key, entry in side_tiles.overrides(read, names).items():
            name = by_key.get(key, "")
            if _keep_read(name, entry, joined.get(name, set())):
                overrides[key] = entry
        for key, name in by_key.items():
            if key not in overrides:
                said = named_override(name, pictures[name], joined[name], size)
                if said:
                    overrides[key] = said
        # a terrain the checks above emptied is no terrain
        kept_terrains = []
        for i, (surface, members) in enumerate(read.terrains):
            mine = {
                k: v
                for k, v in members.items()
                if overrides.get(k, {}).get("terrain", {}).get("set") == names[i]
            }
            kept_terrains.append((surface, mine))
        read.terrains = kept_terrains
        generated: tuple[str, Path] | None = None
        if is_block_sheet:
            digest = hashlib.sha256(pixels.tobytes() + repr(pixels.shape).encode()).hexdigest()
            out_file = work / f"{digest[:24]}.png"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            if not out_file.is_file():
                Image.fromarray(pixels).save(out_file, format="PNG", optimize=False)
            rel = f"{SIDE_DIR}/{out_file.name}"
            stem = posixpath.splitext(posixpath.basename(source_rel))[0]
            slug = "".join(
                ch if ch.isalnum() else "_" for ch in f"{pack_id}_{stem}".casefold()
            ).strip("_")
            while "__" in slug:
                slug = slug.replace("__", "_")
            sheet_asset = Asset(
                f"{GENERATED_PACK}.{slug}_atlas", GENERATED_PACK, rel,
                hashlib.sha256(pixels.tobytes()).hexdigest(), "image", "AUTO_DETECTED", {}, {},
                "atlas_cuts", 0.85,
            )  # fmt: skip
            generated = (rel, out_file)
            _aside(source_asset, SOURCE_ASIDE, rel)
            _as_picture(source_asset)
        else:
            sheet_asset = source_asset
        ground = any(
            "terrain" in v or (v.get("collision") or {}).get("profile") == "FULL"
            for v in overrides.values()
        )
        sheet_asset.detected.update({
            "usage": "tiles",
            "role": "GROUND" if ground else "DECORATION",
            "grid": {"cell": [size, size], "margin": [0, 0], "separation": [0, 0]},
            "size": [int(pixels.shape[1]), int(pixels.shape[0])],
        })  # fmt: skip
        sheet_asset.detected.pop("frame", None)
        sheet_asset.detected.pop("origin", None)
        sheet_asset.detected.pop("animations", None)
        tags = {ATLAS_TAG, SIDE_TAG, f"side_pack:{pack_id}"} | (
            {OUTLINE_TAG} if is_block_sheet else set()
        )
        _add_tags(sheet_asset, *sorted(tags))
        # the pictures of cells the sheet holds as tiles are the same tiles; the things it holds
        # (no tile of a kind: a log, a cart) stay pictures for the dock
        for c in cells:
            key = f"{c['x'] // size},{c['y'] // size}"
            got = piece(c)
            if (
                got is not None
                and key in overrides
                and "mds_kind" not in (overrides[key].get("custom") or {})
            ):
                _aside(got, CELL_ASIDE, sheet_asset.path)
                _as_picture(got)
        out.append(SheetCut(sheet_asset, read, overrides, generated))
    _drawn_sources_aside(assets, pack_root, pack_id, exports)
    return out


ASEPRITE_SUFFIXES = (".ase", ".aseprite")


def _drawn_sources_aside(
    assets: list[Any], pack_root: Path, pack_id: str, exports: dict[str, str]
) -> None:
    """An Aseprite source drawn for want of an export, when a manifest's sheet is its export by
    another name (*Small Bees.ase* beside ``small_bees_sheet_96x48.png``): the same art, set
    aside. ``exports``: the words of each sheet's name -> its catalog path."""
    from rpggen import ids
    from rpggen.core.side_packs import _aside

    if not exports:
        return
    by_id = {a.id: a for a in assets}
    export_words = [(set(k.split()), path) for k, path in exports.items()]
    for path in sorted(pack_root.rglob("*")):
        if path.suffix.casefold() not in ASEPRITE_SUFFIXES or not path.is_file():
            continue
        said = _words(path.stem)
        same = next((p for w, p in export_words if said and said <= w), None)
        got = by_id.get(ids.asset_id(pack_id, path.relative_to(pack_root).as_posix()))
        if same is not None and got is not None and got.path != same:
            _aside(got, SOURCE_ASIDE, same)


def _strip(asset: Any, data: dict[str, Any], frame: tuple[int, int]) -> None:
    """A strip of frames in the manifest's order: one looping animation of the picture."""
    from rpggen.core import classifier, pack_forms
    from rpggen.core.side_packs import MOTION_NAMED, _add_tags

    fw, fh = frame
    frames = []
    for s in data["sprites"]:
        try:
            frames.append([int(s["x"]) // fw, int(s["y"]) // fh])
        except (KeyError, TypeError, ValueError):
            continue
    if not frames:
        return
    facets = asset.detected
    facets.update({
        "usage": "sprite",
        "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
        "frame": [fw, fh],
        "origin": [fw // 2, fh - 1],
        "animations": {"idle": {"frames": frames, "fps": FRAME_FPS, "loop": True}},
    })  # fmt: skip
    role = str(facets.get("role") or "NONE")
    folders, file_words = classifier.tokens(asset.path)
    if role in CHARACTER_ROLES and not {*folders, *file_words} & set(
        classifier.KEYWORD_WEIGHTS.get(role, {})
    ):
        role = "NONE"  # the walks a motion reader saw in a strip of bees: its name says nobody
    facets["role"] = "DECORATION" if role in ("NONE", "UI") else role
    # the strip is the source its frames were cut from, not a sheet compiled of them
    # (pack_forms set it aside for one), and its animation is no longer named from its frames
    facets["tags"] = [
        t for t in facets.get("tags") or []
        if not t.startswith((classifier.UNUSED_TAG, pack_forms.SAME_AS_TAG)) and t != MOTION_NAMED
    ]  # fmt: skip
    _add_tags(asset, ATLAS_TAG)

"""The things of a farming pack that no other reader knows (T17.29).

Real farming packs (Kenney's *Tiny Farm*, EmanuelleDev's *Farm RPG*, LimeZu's *Modern Farm*)
ship their crops, their animals and their player in shapes the readers of names and strips do
not read:

* **A crop** is a row of cells whose plant grows: each cell covers more of itself than the one
  before (``Crops/Spring/Carrot.png``: seeds, a sprout, ..., the ripe plant, an empty cell and
  the carrot harvested; ``Carrot_Growth_Stages_16x16.png`` with a row of numbers under it), or
  such a run of cells in a sheet of tiles (*Tiny Farm*'s numbered tiles). The stages are drawn
  into a strip of their own in the work folder, which is the crop's picture. A picture in a
  folder of icons or of food is an item, never a crop.
* **A farm animal** (a chicken, a cow, a sheep, ... by its folder or name) in a sheet of rows is
  a sprite whose rows are its animations.
* **A layered character** is a folder of pieces of one character: bodies, eyes, hair, clothes
  and accessories, a file each for an action (``PNG/2. Walk/Hair's/Josh/Black.png``) or a sheet
  each with every action in its rows (``Character Pieces/Bodies/16x16/Body_1.png``). Every piece
  becomes one asset (a body or a layer, as an LPC part is: ``lpc_compose`` puts them together),
  its files of the other actions are the sources of its animations.

The adapter reads a pack only when it is a farming pack (``is_farm_pack``); it claims nothing
any other reader claimed before it. No Qt, no Godot.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters import naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

NAME = "farm_pack"
CROP_DIR = "generated/farm_crops"
WORK_FOLDER = "farm_crops"
RENDER_VERSION = 1

# what a pack's own name says when its files say nothing (Kenney's *Tiny Farm*: numbered tiles)
FARM_PACK_WORDS = frozenset({"farm", "farming", "farms", "harvest", "ranch", "crops"})
# the folders crops lie in; a season's folder counts only inside one of these (``Crops/Spring``,
# not ``Objects/Props/Fall``, where stones lie)
CROP_FOLDER_WORDS = frozenset({"crop", "crops", "plant", "plants", "growth", "seeds", "farming"})
TREE_WORDS = frozenset({"tree", "trees"})
# what flies or crawls about a farm: nobody to talk to
CRITTER_WORDS = classifier.CRITTER_WORDS
# a pet walks about like a farm animal but lives in no coop or barn: a decoration that moves
PET_WORDS = frozenset({"dog", "dogs", "cat", "cats", "puppy", "kitten"})
PORTRAIT_WORDS = frozenset({"portrait", "portraits", "face", "faces"})
ITEM_FOLDER_WORDS = frozenset({"icon", "icons", "food", "foods", "item", "items", "ui"})
ANIMAL_WORDS = frozenset(
    {"cow", "cows", "chicken", "chickens", "hen", "hens", "rooster", "roosters", "chick",
     "chicks", "sheep", "sheeps", "pig", "pigs", "piglet", "goat", "goats", "duck", "ducks",
     "duckling", "horse", "horses", "donkey", "donkeys", "rabbit", "rabbits", "ostrich"}
)  # fmt: skip
# The parts of a layered character (T17.29) by the words of their folders, as ``lpc_compose``
# names them: it draws them from the back to the front in its ``PART_ORDER``.
PART_WORDS: tuple[tuple[str, frozenset[str]], ...] = (
    ("body", frozenset({"skin", "skins", "body", "bodies", "base", "bases"})),
    ("eyes", frozenset({"eye", "eyes"})),
    ("hair", frozenset({"hair", "hairs", "hairstyle", "hairstyles"})),
    ("torso", frozenset({"cloth", "clothes", "clothers", "clothing", "outfit", "outfits",
                         "shirt", "shirts"})),
    ("hat", frozenset({"acc", "accs", "accessory", "accessories", "hat", "hats"})),
)  # fmt: skip
# The action folders of a character drawn a file an action (``2. Walk``, ``8. SwordAttack``):
# the first word of these that the folder's name has is the animation.
ACTION_FOLDER_WORDS: tuple[tuple[str, frozenset[str]], ...] = (
    ("idle", frozenset({"idle"})),
    ("walk", frozenset({"walk"})),
    ("run", frozenset({"run"})),
    ("attack", frozenset({"attack", "swordattack", "sword"})),
    ("hurt", frozenset({"damage", "hurt", "hit"})),
    ("die", frozenset({"death", "dead", "die"})),
)
# Rows of a sheet of pieces that has every action (LimeZu's farmer generator): the rows of four
# directions, in this order, are these animations; the order of the four is LimeZu's.
SHEET_ROW_ACTIONS = ("idle", "walk")
SHEET_DIRECTIONS = ("right", "up", "left", "down")
FILE_DIRECTIONS = ("down", "up", "left", "right")
SOURCE_TAG = "source_file:"  # the pack's file a drawn strip was cut from
LAYERED_TAG = "layered_piece"
SET_TAG = "layered_set:"  # the folder of the character a piece is of
FOOD_TAG = "food"
PRODUCE_TAG = "produce:"
MIN_STAGES = 3
GROWTH_RATIO = 1.4  # the ripe plant covers at least this much more than the first stage
GRID_GROWTH_RATIO = 1.8  # ... in a sheet of tiles, where nothing else says it is a crop
GREEN_SHARE = 0.1
_SIZE_TOKEN = re.compile(r"(?<![0-9])([0-9]{1,3})x([0-9]{1,3})(?![0-9])", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9]+")


def words(text: str) -> list[str]:
    from rpggen.core import classifier

    return [w for w in classifier._tokenize(text) if w]


def path_words(path: str) -> tuple[set[str], set[str]]:
    """(the words of the folders of ``path``, the words of its file name)."""
    folders, _, name = path.rpartition("/")
    found: set[str] = set()
    for folder in folders.split("/") if folders else []:
        found.update(words(folder))
    return found, set(words(posixpath.splitext(name)[0]))


def is_farm_pack(inv: Inventory) -> bool:
    """A farming pack: its names say so (``classifier.farm_view``), or the pack's own name does
    (*Tiny Farm*, whose files are numbered)."""
    from rpggen.core import classifier

    return bool(
        set(words(inv.pack_id.replace("_", " "))) & FARM_PACK_WORDS
    ) or classifier.farm_view(inv)


def size_token(path: str) -> int | None:
    """The tile size a path says (``16x16`` in a folder or the file name), None for none."""
    found = [int(a) for a, b in _SIZE_TOKEN.findall(path) if a == b and 4 <= int(a) <= 128]
    return found[-1] if found else None


def _load(root: Path, rel: str) -> np.ndarray:
    with Image.open(root / rel) as opened:
        return np.asarray(opened.convert("RGBA"))


def _still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext != ".gif"


# --------------------------------------------------------------------------- growth


def cell_counts(cells: list[np.ndarray]) -> list[tuple[int, int, float]]:
    """(opaque pixels, height of what is painted, share of green) of each cell; a cell with no
    transparent pixel at all (a label's background) counts as empty."""
    out = []
    for cell in cells:
        alpha = cell[..., 3] > 0
        count = int(alpha.sum())
        if count == alpha.size:
            out.append((0, 0, 0.0))
            continue
        rows = np.nonzero(alpha.any(axis=1))[0]
        height = int(rows[-1] - rows[0] + 1) if rows.size else 0
        rgb = cell[..., :3].astype(int)
        green = (rgb[..., 1] > rgb[..., 0]) & (rgb[..., 1] > rgb[..., 2]) & alpha
        out.append((count, height, float(green.sum()) / max(1, count)))
    return out


def stage_cells(counts: list[tuple[int, int, float]], start: int) -> list[int]:
    """The painted cells from ``start`` on that can be stages: next to one another, over one
    empty cell when two painted ones or more follow it (*Farm RPG*'s pumpkin has an empty
    second stage); the empty cell before the last picture (the produce) ends them."""
    out: list[int] = []
    i = start
    while i < len(counts):
        if counts[i][0]:
            out.append(i)
            i += 1
            continue
        after = 0
        for k in counts[i + 1 :]:
            if not k[0]:
                break
            after += 1
        if out and after >= 2:
            i += 1
            continue
        break
    return out


def growth_run(
    counts: list[tuple[int, int, float]], start: int, ratio: float, *, from_least: bool = False
) -> int:
    """How many of the ``stage_cells`` from ``start`` on are the stages of a growing plant:
    each covering about as much as the one before or more (one dip allowed), the last at least
    ``ratio`` times the first (``from_least``: the least, for seeds drawn on a patch of soil)
    and no shorter, and the ripe one about as large as the largest. 0 when they are not."""
    cells = [counts[i] for i in stage_cells(counts, start)]
    best = 0
    for end in range(MIN_STAGES, len(cells) + 1):
        part = cells[:end]
        dips = sum(1 for a, b in zip(part, part[1:], strict=False) if b[0] < a[0] * 0.85)
        base = min(c[0] for c in part) if from_least else part[0][0]
        low = min(c[1] for c in part) if from_least else part[0][1]
        if dips > (2 if from_least else 1) or part[-1][0] < base * ratio or part[-1][1] < low:
            continue
        if part[-1][0] < max(c[0] for c in part) * 0.85:
            continue  # it withers at the end: the dead plant is no stage
        best = end
    return best


def first_row(a: np.ndarray, width: int) -> int:
    """The top of the first band of ``width`` rows that has paint in it (0 for none)."""
    alpha = a[..., 3] > 0
    for top in range(0, a.shape[0], width):
        if alpha[top : top + width].any():
            return top
    return 0


def row_height(a: np.ndarray, width: int, top: int = 0) -> int:
    """The height of the row of cells at ``top`` of a sheet whose cells are ``width`` wide: the
    smallest multiple of the width that no plant crosses (a stalk two tiles high), counting
    no cell that is painted all over (the label under a row of LimeZu's stages)."""
    h = a.shape[0] - top
    alpha = a[top:, :, 3] > 0
    for k in range(1, 5):
        cut = k * width
        if cut >= h:
            return h
        below = alpha[cut]
        above = alpha[cut - 1]
        cross = above & below
        # a cell of the next row that is painted all over is a label: nothing crosses into it
        cols = a.shape[1] // width
        for c in range(cols):
            if alpha[cut : cut + width, c * width : (c + 1) * width].all():
                cross[c * width : (c + 1) * width] = False
        if not cross.any():
            return cut
    return min(h, 4 * width)


def counted(path: str) -> bool:
    """True for a file whose name gives its frame count (``corn_16x32_8frames``): the artist
    said it is a strip of stages, whatever the pictures look like."""
    stem = posixpath.splitext(posixpath.basename(path))[0]
    return bool(naming.name_facts(stem).frames)


def frames_grow(root: Path, rel: str, frame: Any, stages: int) -> bool:
    """True when the frames of a one-row strip (``frame`` wide) are the stages of a plant that
    grows (``growth_run``); a picture that cannot be read says nothing against it."""
    if not isinstance(frame, list | tuple) or len(frame) != 2 or min(frame) <= 0:
        return True
    try:
        a = _load(root, rel)
    except (OSError, ValueError):
        return True
    counts = cell_counts(strip_cells(a, int(frame[0]), int(frame[1]))[: max(stages, 1)])
    start = next((i for i, c in enumerate(counts) if c[0]), None)
    return start is not None and start <= 1 and growth_run(counts, start, GROWTH_RATIO) > 0


def strip_cells(a: np.ndarray, width: int, height: int, top: int = 0) -> list[np.ndarray]:
    cols = a.shape[1] // width
    return [a[top : top + height, c * width : (c + 1) * width] for c in range(cols)]


def crop_name(path: str) -> str:
    """``Crops/Spring/Carrot.png`` -> ``carrot``; ``Carrot_Growth_Stages_16x16`` -> ``carrot``."""
    stem = posixpath.splitext(posixpath.basename(path))[0]
    kept = [
        w
        for w in words(_SIZE_TOKEN.sub(" ", stem))
        if w not in naming.GROWTH_WORDS
        and w not in {"stage", "stages", "crop", "crops"}
        and not w.isdigit()
    ]
    return _SLUG.sub("_", "_".join(kept)).strip("_") or "crop"


def strip_name(pack_id: str, rel: str, variant: str = "") -> str:
    """The file a crop's strip is drawn to: named after its pack and its file (and the part of
    a sheet it is cut from), so that it keeps its name from one analysis to the next."""
    stem = _SLUG.sub("_", posixpath.splitext(rel)[0].casefold()).strip("_")
    return f"{pack_id}__{stem}{'__' + variant if variant else ''}.png"


def _save(strip: np.ndarray, work: Path, name: str) -> Path:
    """Write a strip to the work folder (in a folder of its own content, so that two packs or
    two versions never share a file) and return it."""
    digest = hashlib.sha256(
        f"{RENDER_VERSION}:{strip.shape}:".encode() + strip.tobytes()
    ).hexdigest()[:16]
    dest = work / digest / name
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(strip, "RGBA").save(dest, format="PNG", optimize=False, pnginfo=None)
    return dest


def _crop_facets(stages: int, width: int, height: int, name: str, how: str) -> dict[str, Any]:
    return {
        "usage": "growth_strip",
        "role": "CROP",
        "stages": stages,
        "grid": {"cell": [width, height], "margin": [0, 0], "separation": [0, 0]},
        "frame": [width, height],
        "origin": [width // 2, height - 1],
        "size": [stages * width, height],
        "tags": sorted({"crop", PRODUCE_TAG + name, "growth_by:" + how}),
    }


# --------------------------------------------------------------------------- the adapter


class FarmPackAdapter:
    name = NAME
    priority = 52  # after the readers of whole formats and isometric tiles, before frames
    pack_id = ""
    root = Path()

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if is_farm_pack(inv) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        self.pack_id = ctx.pack_id
        self.root = root
        result = AdapterResult(self.name)
        issues = IssueList()
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        files = [f for f in inv.files if _still(f) and f.path not in ctx.claimed]
        taken: set[str] = set()
        taken |= self._layered(files, result)
        taken |= self._premade(files, taken, result)
        crops: list[tuple[InventoryFile, bool]] = []
        folders = {posixpath.dirname(f.path).casefold() for f in inv.files}
        for f in files:
            if f.path in taken:
                continue
            if _aseprite_copy(f.path, folders):
                self._aside(f, "aseprite_copy", result)
                taken.add(f.path)
                continue
            if {"guide", "guides"} & path_words(f.path)[1]:
                # LimeZu's ``ANIMATIONS_GUIDE_CHARACTER.png``: the rows of a sheet named in
                # pictures, no villager of the village (T17.29)
                from rpggen.core import classifier

                self._aside(f, classifier.UNUSED_GUIDE_PICTURE, result)
                taken.add(f.path)
                continue
            folder_words, stem_words = path_words(f.path)
            if folder_words & PORTRAIT_WORDS:
                if self._portrait_piece(f, result):
                    taken.add(f.path)
                continue
            if folder_words & ITEM_FOLDER_WORDS:
                if folder_words & {"food", "foods"} or stem_words & _crop_names():
                    self._food(f, result)
                    taken.add(f.path)
                continue
            facts = naming.name_facts(posixpath.splitext(posixpath.basename(f.path))[0])
            if facts.frames or naming_has_action(f.path):
                continue  # the strips and sequences readers know these
            if (folder_words | stem_words) & (ANIMAL_WORDS | PET_WORDS):
                pet = not (folder_words | stem_words) & ANIMAL_WORDS
                if self._animal(root, f, result, issues, "DECORATION" if pet else "ANIMAL"):
                    taken.add(f.path)
                continue
            if (folder_words | stem_words) & TREE_WORDS:
                continue  # a fruit tree grows over years, not in a field
            if (folder_words & CROP_FOLDER_WORDS) or stem_words & _crop_names():
                crops.append((f, bool(folder_words & CROP_FOLDER_WORDS)))
        # the smallest first: a season's sheet of every crop comes after the crops it repeats,
        # and is left to the forms (``pack_forms``: ``compiled_sheet``)
        seen: set[bytes] = set()
        for f, in_folder in sorted(
            crops,
            key=lambda c: (
                (c[0].image or {}).get("w", 0) * (c[0].image or {}).get("h", 0),
                c[0].path,
            ),
        ):
            if self._crop(root, f, work, result, issues, in_folder, seen):
                taken.add(f.path)
        if not any(frag.facets.get("role") == "CROP" for frag in result.assets):
            self._grid_crops(root, files, taken, work, result, issues)
        result.issues = list(issues)
        return result

    def _aside(self, f: InventoryFile, reason: str, result: AdapterResult) -> None:
        from rpggen.core import classifier

        facets = {"usage": "sprite", "role": "NONE", "tags": [classifier.UNUSED_TAG + reason]}
        result.assets.append(AssetFragment(f.path, facets, 0.6, "full"))

    # ------------------------------------------------------------------ portraits

    def _portrait_piece(self, f: InventoryFile, result: AdapterResult) -> bool:
        """A piece of a portrait drawn in layers (in a folder of portraits, the eyes or the hair:
        *Farm RPG*'s ``Portrait - PNG and Aseprite/Eyes/Black.png``) is set aside, never a
        villager (T17.29: the people of the village were eyes). A whole portrait is left to the
        other readers."""
        from rpggen.core import classifier

        parts = f.path.split("/")
        if not any(_part_of(p) for p in parts[:-1]):
            return False
        facets: dict[str, Any] = {
            "usage": "sprite",
            "role": "NONE",
            "tags": [classifier.UNUSED_TAG + "portrait_piece"],
        }
        result.assets.append(AssetFragment(f.path, facets, 0.6, "full"))
        return True

    # ------------------------------------------------------------------ items

    def _food(self, f: InventoryFile, result: AdapterResult) -> None:
        """A picture of a food (an icon): an item, never a crop (T17.29)."""
        assert f.image is not None
        w, h = f.image["w"], f.image["h"]
        frame = [h, h] if w % h == 0 else [w, h]
        facets: dict[str, Any] = {
            "usage": "sprite",
            "role": "ITEM",
            "frame": frame,
            "origin": [frame[0] // 2, frame[1] - 1],
            "tags": [FOOD_TAG],
        }
        if frame[0] != w:
            facets["grid"] = {"cell": frame, "margin": [0, 0], "separation": [0, 0]}
        result.assets.append(AssetFragment(f.path, facets, 0.8, "full"))

    # ------------------------------------------------------------------ crops

    def _crop(
        self,
        root: Path,
        f: InventoryFile,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
        in_folder: bool = False,
        seen: set[bytes] | None = None,
    ) -> bool:
        """A strip of growth stages in a folder of crops or a season, or named after a crop.
        ``seen`` holds the cells of the crops read before: a picture whose painted cells are
        all among them repeats those crops and is not one."""
        assert f.image is not None
        w, h = f.image["w"], f.image["h"]
        if w < MIN_STAGES * 8 or w <= h:
            return False
        try:
            a = _load(root, f.path)
        except (OSError, ValueError) as exc:
            issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=str(exc))
            return False
        token = size_token(f.path)
        width = cell_width(a, (token,)) if token else cell_width(a, (16, 32, 8))
        if not width or w < MIN_STAGES * width or w % width or h > 6 * width:
            return False
        top = first_row(a, width)
        height = row_height(a, width, top)
        cells = strip_cells(a, width, height, top)
        counts = cell_counts(cells)
        start = next((i for i, c in enumerate(counts) if c[0]), None)
        if start is None or start > 1:
            return False
        # in a folder of crops the folder says it; a seed on a patch of soil may cover more
        # than the sprout after it, so the plant grows from its smallest stage
        stages = (
            growth_run(counts, start, 1.2, from_least=True)
            if in_folder
            else growth_run(counts, start, GROWTH_RATIO)
        )
        if not stages:
            if in_folder:  # the reason, on its card
                issues.add("ASSET-035", file=f.path)
            return False
        keys = [
            hashlib.sha1(c.tobytes()).digest() for c, k in zip(cells, counts, strict=True) if k[0]
        ]
        if seen is not None:
            if keys and sum(1 for k in keys if k in seen) >= 0.9 * len(keys):
                return False
            seen.update(keys)
        name = crop_name(f.path)
        chosen = stage_cells(counts, start)[:stages]
        strip = np.concatenate([cells[i] for i in chosen], axis=1)
        dest = _save(np.ascontiguousarray(strip), work, strip_name(self.pack_id, f.path))
        project_path = f"{CROP_DIR}/{dest.name}"
        facets = _crop_facets(stages, width, height, name, "strip")
        # the file it was drawn from: its size (``Crops_Growth_32x32``) is the pack's
        facets["tags"] = sorted({*facets["tags"], SOURCE_TAG + f.path})
        result.assets.append(AssetFragment(f.path, facets, 0.8, "full"))
        result.generated[project_path] = str(dest)
        result.rendered[f.path] = project_path
        return True

    def _grid_crops(
        self,
        root: Path,
        files: list[InventoryFile],
        taken: set[str],
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        """Crops in a sheet of tiles (*Tiny Farm*): a run of three cells or more in a row whose
        plant grows, green, beginning small. Each is a crop of its own, a variant of the sheet
        (``#crop_1``), named by its place since nothing names it. Only the largest sheet of the
        pack is read, and only when nothing else in the pack is a crop."""
        from rpggen.core import classifier

        sheets = [
            f
            for f in files
            if f.path not in taken
            and f.image
            and f.image["w"] * f.image["h"] >= 64 * 64
            and not classifier.not_game_art(f.path)
        ]
        if not sheets:
            return
        sheet = max(sheets, key=lambda f: (f.image["w"] * f.image["h"] if f.image else 0, f.path))
        try:
            a = _load(root, sheet.path)
        except (OSError, ValueError) as exc:
            issues.add("ADAPT-001", adapter=self.name, file=sheet.path, reason=str(exc))
            return
        cell, gap = _sheet_grid(a)
        if not cell:
            return
        step = cell + gap
        cols, rows = (a.shape[1] + gap) // step, (a.shape[0] + gap) // step
        from rpggen.core.adapters import sheet_parts

        number = 0
        said: dict[str, int] = {}
        for r in range(rows):
            cells = [a[r * step : r * step + cell, c * step : c * step + cell] for c in range(cols)]
            counts = cell_counts(cells)
            c = 0
            while c < cols:
                first = counts[c]
                small = 0 < first[0] <= cell * cell * 0.4
                # a plant is green at every stage: the withered one after the ripe, the seed
                # bag and the crate beside them are not
                end = c
                while end < cols and counts[end][0] and counts[end][2] >= GREEN_SHARE:
                    end += 1
                stages = growth_run(counts[:end], c, GRID_GROWTH_RATIO) if small else 0
                if stages:
                    number += 1
                    variant = f"crop_{number}"
                    # T17.33: named by its ripe stage's colour and shape (``orange_plant``),
                    # not ``crop_1``; a name twice gets a number
                    name = sheet_parts.looks_of(cells[c + stages - 1]) or variant
                    said[name] = said.get(name, 0) + 1
                    if said[name] > 1:
                        name = f"{name}_{said[name]}"
                    strip = np.concatenate(cells[c : c + stages], axis=1)
                    dest = _save(
                        np.ascontiguousarray(strip),
                        work,
                        strip_name(self.pack_id, sheet.path, variant),
                    )
                    project_path = f"{CROP_DIR}/{dest.name}"
                    facets = _crop_facets(stages, cell, cell, name, "grid")
                    facets["tags"] = sorted({*facets["tags"], f"cells:{r}:{c}:{stages}"})
                    result.assets.append(
                        AssetFragment(sheet.path, facets, 0.5, "partial", variant=variant)
                    )
                    result.generated[project_path] = str(dest)
                    result.rendered[f"{sheet.path}#{variant}"] = project_path
                    c += stages
                else:
                    c += 1

    # ------------------------------------------------------------------ animals

    def _animal(
        self,
        root: Path,
        f: InventoryFile,
        result: AdapterResult,
        issues: IssueList,
        role: str = "ANIMAL",
    ) -> bool:
        """A farm animal in a sheet of rows: every row of two frames or more an animation."""
        assert f.image is not None
        w, h = f.image["w"], f.image["h"]
        if w < 32 or h < 16:
            return False
        try:
            a = _load(root, f.path)
        except (OSError, ValueError) as exc:
            issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=str(exc))
            return False
        token = size_token(f.path)
        width = cell_width(a, (token, 2 * token, 3 * token)) if token else cell_width(a)
        if not width or w % width or h % width or w // width < 2:
            return False
        height = row_height(a, width)
        if h % height:
            height = width
        animations: dict[str, Any] = {}
        rows = h // height
        names = ["idle", "walk", "sleep"]
        used = 0
        for r in range(rows):
            counts = cell_counts(strip_cells(a, width, height, r * height))
            frames = 0
            for k in counts:
                if not k[0]:
                    break
                frames += 1
            median = sorted(k[0] for k in counts[:frames])[frames // 2] if frames else 0
            frames = next(
                (i for i, k in enumerate(counts[:frames]) if k[0] > 2.5 * median), frames
            )  # what follows the frames on their row (*ROW:4 COL:24*) is no frame
            if frames < 2 or used >= len(names):
                continue
            animations[f"{names[used]}_down"] = {
                "frames": [[i, r] for i in range(frames)],
                "fps": naming.fps(names[used]),
                "loop": True,
            }
            used += 1
        if "walk_down" not in animations:
            return False
        facets = {
            "usage": "sprite",
            "role": role,
            "grid": {"cell": [width, height], "margin": [0, 0], "separation": [0, 0]},
            "frame": [width, height],
            "origin": [width // 2, height - 1],
            "animations": animations,
            "tags": ["animal"] if role == "ANIMAL" else ["pet"],
        }
        result.assets.append(AssetFragment(f.path, facets, 0.7, "full"))
        return True

    # ------------------------------------------------------------------ whole characters

    def _premade(
        self, files: list[InventoryFile], taken: set[str], result: AdapterResult
    ) -> set[str]:
        """A character drawn whole, a file an action named by nothing but the action
        (``Pre-made/Alex/Walk.png``, ``Idle.png``, ``Hoe.png``): a sheet of a row a direction
        (down, up and one side, or down, up, left and right). It is one character; the other
        files of its folder (a bicycle, fishing) are parts of it."""
        folders: dict[str, list[InventoryFile]] = {}
        for f in files:
            if f.path not in taken:
                folders.setdefault(posixpath.dirname(f.path), []).append(f)
        out: set[str] = set()
        for folder in sorted(folders):
            if any(folder.startswith(o + "/") for o in out):
                continue
            actions: dict[str, InventoryFile] = {}
            for f in folders[folder]:
                found = words(posixpath.splitext(posixpath.basename(f.path))[0])
                action = _action_of(" ".join(found))
                if action and len(found) <= 2:
                    actions.setdefault(action, f)
            walk = actions.get("walk")
            if walk is None or len(actions) < 2 or walk.image is None:
                continue
            w, h = walk.image["w"], walk.image["h"]
            # a row a direction, frames as high as wide and of 16 px or more; one row is a
            # strip, which the strips reader knows
            rows = next((n for n in (4, 3) if h % n == 0 and h // n >= 16 and w % (h // n) == 0), 0)
            if not rows:
                continue
            size = h // rows
            directions = FILE_DIRECTIONS if rows == 4 else ("down", "up", "right")
            animations: dict[str, Any] = {}
            for action, f in sorted(actions.items()):
                if f.image is None or f.image["h"] != h or f.image["w"] % size:
                    continue
                per = f.image["w"] // size
                for r, direction in enumerate(directions):
                    spec = {
                        "frames": [[i, r] for i in range(per)],
                        "fps": naming.fps(action),
                        "loop": naming.is_looping(action),
                        "source": f"assets/packs/{self.pack_id}/{f.path}",
                    }
                    animations[f"{action}_{direction}"] = spec
                    if direction == "right":
                        animations[f"{action}_left"] = {**spec, "flip_h": True}
            inside = sorted(
                f.path for f in files if f.path.startswith(folder + "/") and f.path not in taken
            )
            facets: dict[str, Any] = {  # the role is the classifier's: a villager, a goblin
                "usage": "sprite",
                "grid": {"cell": [size, size], "margin": [0, 0], "separation": [0, 0]},
                "frame": [size, size],
                "origin": [size // 2, size - 1],
                "animations": animations,
                "tags": ["character"],
            }
            feet = _feet(self.root, walk.path, size)
            if feet:
                facets["feet"] = feet  # a character 14 px wide in frames of 32
            said, _stem = path_words(walk.path)
            if said & ANIMAL_WORDS:
                facets["role"] = "ANIMAL"  # a farm animal drawn a file an action
            elif said & (CRITTER_WORDS | PET_WORDS | {"animal", "animals"}):
                facets["role"] = "DECORATION"  # a deer of the forest walks, and talks to nobody
            result.assets.append(AssetFragment(walk.path, facets, 0.7, "full"))
            result.consumed.extend(p for p in inside if p != walk.path)
            out.add(folder)
            taken.update(inside)
        return {p for p in taken}

    # ------------------------------------------------------------------ layered characters

    def _layered(self, files: list[InventoryFile], result: AdapterResult) -> set[str]:
        """The pieces of layered characters: a file an action (``<character>/<action>/<part>/
        <style>/<colour>.png``) or a sheet a piece (``<pieces>/<part>/<size>/<piece>.png``)."""
        taken: set[str] = set()
        # the folders whose folders are actions with folders of parts in them
        owners: dict[str, set[str]] = {}
        for f in files:
            parts = f.path.split("/")
            for i in range(len(parts) - 2):
                if _action_of(parts[i]) and _part_of(parts[i + 1]):
                    owners.setdefault("/".join(parts[:i]), set()).add(parts[i])
                    break
        owners = {o: acts for o, acts in owners.items() if len(acts) >= 2}
        by_action: dict[tuple[str, str, str], dict[str, InventoryFile]] = {}
        sheets: dict[tuple[str, str], list[InventoryFile]] = {}
        extras: dict[str, list[InventoryFile]] = {}
        for f in files:
            parts = f.path.split("/")
            owner = next((o for o in owners if f.path.startswith(o + "/" if o else "")), None)
            depth = len(owner.split("/")) if owner else 0
            if owner is not None and len(parts) - depth >= 3:
                part = _part_of(parts[depth + 1])
                if not part:
                    # what a character's action has beside its parts: the bicycle it rides,
                    # the horse under it; a part of the character, no villager
                    extras.setdefault(owner, []).append(f)
                    continue
                if part:
                    action = _action_of(parts[depth]) or "other:" + parts[depth]
                    rest = "/".join(parts[depth + 2 :])
                    found = by_action.setdefault((owner, part, rest), {})
                    held = found.get(action)
                    if held is not None:
                        # ``1. Idle`` and ``24. Swim - Idle``: the folder that says nothing
                        # but the action is the action; the other is a file of the piece
                        mine = len(words(parts[depth]))
                        theirs = len(words(held.path.split("/")[depth]))
                        if mine < theirs:
                            found["other:" + held.path.split("/")[depth]] = held
                        else:
                            found["other:" + parts[depth]] = f
                            continue
                    found[action] = f
                    continue
            for i in range(1, len(parts) - 1):
                part = _part_of(parts[i])
                above = "/".join(parts[:i])
                if part and ({"pieces", "generator"} & set(words(above))):
                    sheets.setdefault((above, part), []).append(f)
                    break
        for owner in sorted(owners):
            pieces = {k: v for k, v in by_action.items() if k[0] == owner}
            if not any(part == "body" for _o, part, _r in pieces):
                continue
            for (_owner, part, rest), actions in sorted(pieces.items()):
                fragment = _action_piece(self.pack_id, part, rest, actions)
                if fragment is None:
                    continue
                fragment.facets["tags"].append(SET_TAG + owner)
                result.assets.append(fragment)
                first = fragment.path
                result.consumed.extend(f.path for f in actions.values() if f.path != first)
                taken.update(f.path for f in actions.values())
            for f in extras.get(owner, []):
                result.consumed.append(f.path)
                taken.add(f.path)
        groups: dict[str, dict[str, list[InventoryFile]]] = {}
        for (owner, part), members in sheets.items():
            groups.setdefault(owner, {})[part] = members
        for owner, parts_of in sorted(groups.items()):
            if "body" not in parts_of:
                continue
            for part, members in sorted(parts_of.items()):
                for f in sorted(members, key=lambda m: m.path):
                    fragment = _sheet_piece(part, f, result)
                    if fragment is not None:
                        fragment.facets["tags"].append(SET_TAG + owner)
                        result.assets.append(fragment)
                        taken.add(f.path)
        return taken


def _aseprite_copy(rel: str, folders: set[str]) -> bool:
    """True for a picture in a folder ``Aseprite`` beside a folder ``PNG``: the pack's pictures
    once more, as the artist's Aseprite files export them (*Farm RPG*'s characters)."""
    parts = rel.split("/")[:-1]
    for i, part in enumerate(parts):
        if part.strip().casefold() == "aseprite":
            beside = "/".join([*parts[:i], "png"]).casefold()
            if any(f == beside or f.startswith(beside + "/") for f in folders):
                return True
    return False


def _feet(root: Path, rel: str, size: int) -> int:
    """How wide a character stands in the first frame of ``rel`` (frames ``size`` square): what
    the lowest quarter of what it paints covers. 0 when it cannot be read."""
    try:
        a = _load(root, rel)
    except (OSError, ValueError):
        return 0
    alpha = a[:size, :size, 3] > 0
    rows = np.nonzero(alpha.any(axis=1))[0]
    if not rows.size:
        return 0
    low = alpha[max(int(rows[-1]) - max(1, size // 4) + 1, 0) : int(rows[-1]) + 1]
    columns = np.nonzero(low.any(axis=0))[0]
    if not columns.size:
        return 0
    return min(int(columns[-1] - columns[0] + 1), int(size * 0.6))  # a shadow is no foot


def _crop_names() -> frozenset[str]:
    from rpggen.core import classifier

    return classifier.CROP_NAMES


def naming_has_action(path: str) -> bool:
    """True for a file named with an action (``hero_walk_down``): a strip of an animation."""
    stem = posixpath.splitext(posixpath.basename(path))[0]
    found = set(words(stem))
    return any(naming.SYNONYMS.get(w, w) in naming.CANONICAL_ACTIONS for w in found)


def _sheet_grid(a: np.ndarray) -> tuple[int, int]:
    """(cell, gap) of a sheet of square tiles: 16 with a gap of 1 for Kenney's spaced sheet,
    else the first of 16, 32, 8 that divides it."""
    h, w = a.shape[:2]
    for cell in (16, 32, 8, 24, 48):
        for gap in (0, 1, 2):
            if (w + gap) % (cell + gap) == 0 and (h + gap) % (cell + gap) == 0:
                if gap and not _gaps_clear(a, cell, gap):
                    continue
                return cell, gap
    return 0, 0


def _gaps_clear(a: np.ndarray, cell: int, gap: int) -> bool:
    alpha = a[..., 3]
    step = cell + gap
    cols = [x for k in range(1, a.shape[1] // step + 1) for x in range(k * step - gap, k * step)]
    cols = [x for x in cols if x < a.shape[1]]
    return bool(cols) and not alpha[:, cols].any()


def cell_width(a: np.ndarray, candidates: tuple[int, ...] = (16, 32, 24, 48, 64)) -> int:
    """The cell width of ``candidates`` that divides the sheet into two columns or more and
    whose borders the drawings cross least (a cow is two tiles wide; a ripe cabbage touches
    the edges of its tile here and there), the first of ``candidates`` about as good."""
    h, w = a.shape[:2]
    alpha = a[..., 3] > 0
    scored: list[tuple[float, int]] = []
    for cell in dict.fromkeys(candidates):
        if not cell or w % cell or w // cell < 2:
            continue
        cuts = list(range(cell, w, cell))
        crossing = sum(int((alpha[:, x - 1] & alpha[:, x]).sum()) for x in cuts)
        scored.append((crossing / len(cuts), cell))
    if not scored:
        return 0
    best = min(score for score, _cell in scored)
    limit = max(best + 1.0, best * 1.5, h * 0.15)
    return next(cell for score, cell in scored if score <= limit)


def _action_of(folder: str) -> str | None:
    found = set(words(folder))
    for action, names in ACTION_FOLDER_WORDS:
        if found & names:
            return action
    return None


def _part_of(folder: str) -> str | None:
    found = set(words(folder))
    for part, names in PART_WORDS:
        if found & names:
            return part
    return None


def _piece_tags(part: str) -> list[str]:
    from rpggen.core import lpc_compose

    if part == "body":
        return [lpc_compose.BODY_TAG, LAYERED_TAG, lpc_compose.LAYERED_UNUSED]
    return [
        lpc_compose.LAYER_TAG,
        lpc_compose.PART_TAG + part,
        LAYERED_TAG,
        lpc_compose.LAYERED_UNUSED,
    ]


def _action_piece(
    pack_id: str, part: str, rest: str, actions: dict[str, InventoryFile]
) -> AssetFragment | None:
    """One piece drawn a file an action: every file a row of four directions. The files of the
    actions no animation is made of (fishing, riding) are parts of it all the same."""
    animations: dict[str, Any] = {}
    frame: tuple[int, int] | None = None
    first: InventoryFile | None = None
    for action in [a for a, _w in ACTION_FOLDER_WORDS if a in actions]:
        f = actions[action]
        if f.image is None:
            continue
        w, h = f.image["w"], f.image["h"]
        if w % h or (w // h) % 4:
            continue
        if frame is None:
            frame, first = (h, h), f
        if (h, h) != frame:
            continue
        per = (w // h) // 4
        for d, direction in enumerate(FILE_DIRECTIONS):
            animations[f"{action}_{direction}"] = {
                "frames": [[d * per + i, 0] for i in range(per)],
                "fps": naming.fps(action),
                "loop": naming.is_looping(action),
                "source": f"assets/packs/{pack_id}/{f.path}",
            }
    if first is None or frame is None or "walk_down" not in animations:
        return None
    facets = {
        "usage": "sprite",
        "role": "NONE",
        "grid": {"cell": list(frame), "margin": [0, 0], "separation": [0, 0]},
        "frame": list(frame),
        "origin": [frame[0] // 2, frame[1] - 1],
        "animations": animations,
        "tags": [*_piece_tags(part), "piece:" + rest.rsplit(".", 1)[0]],
    }
    return AssetFragment(first.path, facets, 0.8, "full")


def _sheet_piece(part: str, f: InventoryFile, result: AdapterResult) -> AssetFragment | None:
    """One piece drawn as a sheet with every action in its rows (LimeZu's generator): its
    frames are a tile wide and two high; the first rows of four directions are idle and walk."""
    if f.image is None:
        return None
    w, h = f.image["w"], f.image["h"]
    width = size_token(f.path) or 16
    height = 2 * width
    if w % width or h % height:
        return None
    cols, rows = w // width, h // height
    animations: dict[str, Any] = {}
    named = 0
    for r in range(rows):
        if named >= len(SHEET_ROW_ACTIONS):
            break
        if r == 0:
            continue  # four standing pictures, one a direction
        per = cols // 4 if cols >= 8 else 0
        per = min(per, 6)
        if not per:
            continue
        action = SHEET_ROW_ACTIONS[named]
        for d, direction in enumerate(SHEET_DIRECTIONS):
            animations[f"{action}_{direction}"] = {
                "frames": [[d * per + i, r] for i in range(per)],
                "fps": naming.fps(action),
                "loop": True,
            }
        named += 1
    if "walk_down" not in animations:
        return None
    facets = {
        "usage": "sprite",
        "role": "NONE",
        "grid": {"cell": [width, height], "margin": [0, 0], "separation": [0, 0]},
        "frame": [width, height],
        "origin": [width // 2, height - 1],
        "animations": animations,
        "tags": [*_piece_tags(part), "piece:" + posixpath.splitext(posixpath.basename(f.path))[0]],
    }
    return AssetFragment(f.path, facets, 0.8, "full")

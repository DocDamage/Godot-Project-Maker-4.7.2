"""Animations saved as one numbered image per frame (T12.50).

``hero_walk_down_01.png``, ``hero/walk/0001.png`` and ``Walk (3).png`` are frames of one
animation. The files of a folder that share a stem without its trailing number are a sequence;
the frames are composited into one strip per animation, and the animations of a character become
one sprite asset, as the strips adapter does for whole strips.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core.adapters import aseprite_file, naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import frames as frames_mod
from rpggen.core.analyzer import image_facts
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

# "walk_01", "walk-01", "walk 01", "walk (1)", "walk(1)" and a bare "0001". A number glued to the
# name ("tileset2", "walk3") is part of the name.
NUMBERED = re.compile(r"^(?P<base>.*?)(?:[_\- ]*\((?P<paren>\d+)\)|(?:(?<=[_\- ])|^)(?P<num>\d+))$")
# "<name>_<action>[_<direction>]", or the action alone when a folder names the character.
SEQUENCE_NAME = re.compile(
    rf"^(?:(?P<name>.+?)[_\- ])?(?P<action>{naming.ACTION_PATTERN})"
    rf"(?:[_\- ](?P<dir>{naming.DIRECTION_PATTERN}))?$",
    re.IGNORECASE,
)
DIRECTION_ONLY = re.compile(rf"^(?:{naming.DIRECTION_PATTERN})$", re.IGNORECASE)
# A frame export with no action word (T16.21): "CHARACTER1", "PORTAL 10", "BOX (3)". The
# number may be glued to the stem here, because the whole folder is the evidence, not the name.
EXPORT_FRAME = re.compile(r"^(?P<base>.*?[^\d\s_\-(])[_\- ]*\(?(?P<num>\d+)\)?[_\- ]*$")
EXPORT_MIN_FRAMES = 3
SOURCE_EXTENSIONS = (".aseprite", ".ase")
UNNAMED = "anim_{0}"
UNNAMED_CONFIDENCE = 0.5  # needs review: the animations have no names yet
MOTION_CONFIDENCE = 0.8  # T17.33: the animations named from what their frames do
# a frame export of these words is tiles exported one by one, not frames (T17.33)
TILE_EXPORT_WORDS = frozenset({"terrain", "tile", "tiles", "tileset", "tilemap", "tilesheet"})


def _label_words(label: str) -> list[str]:
    return [w for w in re.split(r"[^0-9a-z]+", label.casefold()) if w and not w.isdigit()]


def _tags_by_motion(
    pictures: list[Any], plan: list[tuple[str | None, list[int], bool]]
) -> tuple[list[tuple[str | None, list[int], bool]], bool]:
    """``_named_by_motion`` for the tags of a drawn Aseprite file: frames by index."""
    from rpggen.core import motion

    runs = []
    for _name, frames, _loop in plan:
        found = [motion.frame_of(np.asarray(pictures[i].convert("RGBA")), i, 0) for i in frames]
        runs.append([f for f in found if f is not None])
    if any(not r for r in runs):
        return plan, False
    fig = motion.figure(runs)
    if fig is None:
        return plan, False
    names = motion.names(runs, fig)
    taken = {name for name, _f, _l in plan if name}
    out: list[tuple[str | None, list[int], bool]] = []
    for (name, frames, loop), found_name in zip(plan, names, strict=True):
        if name is None:
            candidate = f"{found_name}_down"
            n = 2
            while candidate in taken:
                candidate = f"{found_name}_{n}_down"
                n += 1
            taken.add(candidate)
            out.append((candidate, frames, naming.is_looping(found_name.split("_")[0])))
        else:
            out.append((name, frames, loop))
    return out, True


def _named_by_motion(root: Path, plan: list[Any]) -> tuple[list[Any], bool]:
    """The plan of a frame export whose animations no tag names (T17.33: pozak's ``player.ase``
    exported frame by frame): each unnamed one named by what its frames do (``motion``); the
    named ones are kept. Returns the plan and whether motion named any."""
    if not any(name is None for name, *_rest in plan):
        return plan, False
    from rpggen.core import motion

    runs: list[list[Any]] = []
    for _name, seq, _fps, _loop in plan:
        frames = []
        for i, (_n, f) in enumerate(seq.frames):
            try:
                with Image.open(root / f.path) as im:
                    found = motion.frame_of(np.asarray(im.convert("RGBA")), i, 0)
            except (OSError, ValueError):
                found = None
            if found is not None:
                frames.append(found)
        runs.append(frames)
    if any(not r for r in runs):
        return plan, False
    fig = motion.figure(runs)
    if fig is None:
        return plan, False
    names = motion.names(runs, fig)
    taken = {name for name, *_r in plan if name}
    out = []
    for (name, seq, fps, loop), said in zip(plan, names, strict=True):
        if name is None:
            verb = said.split("_")[0]
            candidate = f"{said}_down"
            n = 2
            while candidate in taken:
                candidate = f"{said}_{n}_down"
                n += 1
            taken.add(candidate)
            out.append((candidate, seq, naming.fps(verb), naming.is_looping(verb)))
        else:
            out.append((name, seq, fps, loop))
    return out, True


FRAME_STRIP_DIR = "generated/frame_strips"
WORK_FOLDER = "frame_strips"
MIN_FRAMES = 2
# A source drawn by rpggen (a ``.aseprite`` with no export beside it): its strip is named after
# the source's bytes and this number, which goes up when ``aseprite_file.render`` draws
# something differently.
RENDER_VERSION = 1
RENDERED_CONFIDENCE = 0.85
INEXACT_CONFIDENCE = 0.6  # needs review: something in the source is not drawn as Aseprite does
_WORD = re.compile(r"[^0-9a-z]+")
# A strip wider than this wraps into rows, so a long sequence stays a texture every GPU loads.
MAX_STRIP_WIDTH = 4096
MAX_LISTED_GAPS = 5


@dataclass
class Sequence:
    """The numbered frames of one animation, in playing order."""

    folder: str  # posix folder of the frames inside the pack ("" for the pack root)
    base: str  # the stem without its number ("" for bare numbers)
    frames: list[tuple[int, InventoryFile]]
    # Filled by ``_name``: where the character lives, its name and the animation's raw name.
    owner_folder: str = ""
    owner: str = ""
    raw_name: str = ""

    @property
    def label(self) -> str:
        return posixpath.join(self.folder, self.base) if self.base else self.folder

    @property
    def size(self) -> tuple[int, int]:
        image = self.frames[0][1].image or {}
        return int(image.get("w", 0)), int(image.get("h", 0))

    def missing(self) -> list[int]:
        numbers = {n for n, _ in self.frames}
        return [n for n in range(min(numbers), max(numbers) + 1) if n not in numbers]


def split_number(stem: str) -> tuple[str, int] | None:
    """``("hero_walk", 1)`` for ``hero_walk_01``; None when the stem has no trailing number."""
    m = NUMBERED.match(stem)
    if m is None:
        return None
    return m.group("base").rstrip("_- "), int(m.group("paren") or m.group("num"))


def _is_still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext != ".gif"


def _name(seq: Sequence) -> bool:
    """Reads the character and the animation from the stem, then from the folders above it."""
    folders = [p for p in seq.folder.split("/") if p]
    text = seq.base
    for _ in range(2):  # "hero/walk/0001.png", "hero/walk/down/0001.png", "hero/walk/down_01.png"
        if text and not DIRECTION_ONLY.match(text):
            break
        if not folders:
            return False
        text = f"{folders.pop()}_{text}" if text else folders.pop()
    m = SEQUENCE_NAME.match(text)
    if m is None:
        return False
    seq.owner_folder = "/".join(folders)
    seq.owner = (m.group("name") or "").casefold()
    seq.raw_name = m.group("action") + ("_" + m.group("dir") if m.group("dir") else "")
    return True


def find_sequences(inv: Inventory, claimed: set[str]) -> list[Sequence]:
    """Every group of numbered frames that names an action, ordered by folder and stem.

    Numbered files without an action word (``item_01.png`` ... ``item_12.png``) stay separate
    assets: they are far more often variants than frames.
    """
    groups: dict[tuple[str, str], Sequence] = {}
    for f in inv.files:
        if not _is_still(f) or f.path in claimed:
            continue
        split = split_number(posixpath.splitext(posixpath.basename(f.path))[0])
        if split is None:
            continue
        folder = posixpath.dirname(f.path)
        key = (folder, split[0].casefold())
        seq = groups.setdefault(key, Sequence(folder, split[0], []))
        seq.frames.append((split[1], f))
    found: list[Sequence] = []
    for key in sorted(groups):
        seq = groups[key]
        # numeric order: 10 comes after 9, whatever the zero padding
        seq.frames.sort(key=lambda nf: (nf[0], nf[1].path.casefold(), nf[1].path))
        sizes = {((f.image or {}).get("w", 0), (f.image or {}).get("h", 0)) for _, f in seq.frames}
        if len(seq.frames) < MIN_FRAMES or len(sizes) != 1 or 0 in next(iter(sizes)):
            continue
        if _name(seq):
            found.append(seq)
    return found


# A character rendered once a facing (Kenney's *Miniature* packs): ``Male_3_Run7.png`` is the
# character ``Male``, facing 3 of eight, frame 7 of its run. The facing is a number before the
# action, and the frame's number is glued to the action.
FACING_FRAME = re.compile(
    r"^(?P<name>.+?)[_\- ](?P<facing>[0-7])[_\- ](?P<action>[A-Za-z]+?)[_\- ]?(?P<num>\d+)$"
)
# The facing a number is, on the screen: 0 looks up and to the right, and every next number is
# an eighth of a turn clockwise (looked at on *Miniature Dungeon*: 3 runs towards the camera, 7
# away from it, 1 to the right and 5 to the left).
FACINGS = ("up_right", "right", "down_right", "down", "down_left", "left", "up_left", "up")
FACING_MIRROR = 6  # facing k seen in a mirror is facing (6 - k): 3 and 7 are their own
FACINGS_CONFIDENCE = 0.9
FACINGS_UNSURE_CONFIDENCE = 0.5  # needs review: the pictures do not mirror as the facings say


@dataclass
class FacingSet:
    """A character whose frames are files named by facing, action and frame."""

    folder: str
    name: str
    # {action as written: {facing: frames in playing order}}
    actions: dict[str, dict[int, list[tuple[int, InventoryFile]]]]

    @property
    def files(self) -> list[InventoryFile]:
        return [
            f
            for action in sorted(self.actions)
            for facing in sorted(self.actions[action])
            for _n, f in self.actions[action][facing]
        ]


def find_facings(inv: Inventory, claimed: set[str]) -> list[FacingSet]:
    """The characters of a pack that are drawn once a facing, by folder and name: every action
    of one has all eight facings, 0 to 7, each with as many frames, all pictures one size. An
    action that lacks a facing is left out; a name with no whole action is no such character."""
    groups: dict[tuple[str, str], dict[str, dict[int, list[tuple[int, InventoryFile]]]]] = {}
    for f in inv.files:
        if not _is_still(f) or f.path in claimed:
            continue
        m = FACING_FRAME.match(posixpath.splitext(posixpath.basename(f.path))[0])
        if m is None:
            continue
        key = (posixpath.dirname(f.path), m.group("name"))
        frames = groups.setdefault(key, {}).setdefault(m.group("action"), {})
        frames.setdefault(int(m.group("facing")), []).append((int(m.group("num")), f))
    found: list[FacingSet] = []
    for key in sorted(groups):
        whole: dict[str, dict[int, list[tuple[int, InventoryFile]]]] = {}
        sizes: set[tuple[int, int]] = set()
        for action, facings in groups[key].items():
            counts = {len(numbered) for numbered in facings.values()}
            if set(facings) != set(range(len(FACINGS))) or len(counts) != 1:
                continue
            whole[action] = {
                facing: sorted(numbered, key=lambda nf: (nf[0], nf[1].path))
                for facing, numbered in facings.items()
            }
            for numbered in facings.values():
                sizes.update(
                    (int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0)))
                    for _n, f in numbered
                )
        # one action at least is a word for what a character does: "tile_3_a1" is no person
        acts = any(
            naming.SYNONYMS.get(a.casefold(), a.casefold()) in naming.CANONICAL_ACTIONS
            for a in whole
        )
        if acts and len(sizes) == 1 and 0 not in next(iter(sizes)):
            found.append(FacingSet(key[0], key[1], whole))
    return found


def facings_mirror(root: Path, character: FacingSet) -> bool:
    """Whether the pictures bear out which facing a number is. A character seen in a mirror
    looks the other way across the screen: facing ``k`` mirrored is most like facing
    ``6 - k`` when 3 and 7 are the two that look straight at and away from the camera. Of the
    eight ways the numbers could lie round the mirror's axis, the pictures must be most like
    this one. (Which of the two looks at the camera no silhouette says: that is the order the
    renderer of these packs writes.)"""
    from rpggen.core.analyzer import views

    action = min(character.actions, key=lambda a: (len(character.actions[a][0]), a))
    shown, mirrored = [], []
    for facing in range(len(FACINGS)):
        try:
            rgba = image_facts.load_rgba(root / character.actions[action][facing][0][1].path)
        except (OSError, ValueError):
            return False
        one, other = views.view(rgba), views.view(rgba[:, ::-1])
        if one is None or other is None:
            return False
        shown.append(one)
        mirrored.append(other)
    count = len(FACINGS)
    alike = [
        sum(views.likeness(mirrored[k], shown[(axis - k) % count], None) for k in range(count))
        for axis in range(count)
    ]
    return max(range(count), key=lambda axis: (alike[axis], -axis)) == FACING_MIRROR


@dataclass
class FrameExport:
    """A folder that is one numbered frame export without an action word."""

    folder: str
    base: str
    frames: list[tuple[int, InventoryFile]]  # in numeric order
    source: str | None  # the .aseprite beside the frames, when there is one

    @property
    def label(self) -> str:
        return posixpath.join(self.folder, self.base)


def find_frame_exports(inv: Inventory, claimed: set[str]) -> list[FrameExport]:
    """Folders whose pictures are ``<STEM><n>.png`` with one stem and one size and nothing else
    (``CHARACTER/CHARACTER1.png`` ... ``CHARACTER168.png``). Whether such a folder is an
    animation or a set of variants (``icons/icon_01`` ... ``icon_64``) the names cannot say:
    ``SequencesAdapter`` asks the pictures (a blank separator frame) and the folder (the
    ``.aseprite`` source the frames were exported from)."""
    folders: dict[str, list[InventoryFile]] = {}
    sources: dict[str, list[str]] = {}
    for f in inv.files:
        folder = posixpath.dirname(f.path)
        if f.ext in SOURCE_EXTENSIONS:
            sources.setdefault(folder, []).append(f.path)
        elif f.kind == "image":
            folders.setdefault(folder, []).append(f)
    found: list[FrameExport] = []
    for folder in sorted(folders):
        files = folders[folder]
        if len(files) < EXPORT_MIN_FRAMES or any(
            not _is_still(f) or f.path in claimed for f in files
        ):
            continue
        parsed = [
            (EXPORT_FRAME.match(posixpath.splitext(posixpath.basename(f.path))[0]), f)
            for f in files
        ]
        if any(m is None for m, _f in parsed):
            continue
        bases = {m.group("base").strip().casefold() for m, _f in parsed if m}
        numbers = [int(m.group("num")) for m, _f in parsed if m]
        sizes = {((f.image or {}).get("w", 0), (f.image or {}).get("h", 0)) for f in files}
        if len(bases) != 1 or len(set(numbers)) != len(numbers) or len(sizes) != 1:
            continue
        if 0 in next(iter(sizes)):
            continue
        base = next(m.group("base").strip() for m, _f in parsed if m)
        beside = sorted(sources.get(folder, []))
        named = [
            p
            for p in beside
            if posixpath.splitext(posixpath.basename(p))[0].casefold() == base.casefold()
        ]
        frames = sorted(zip(numbers, files, strict=True), key=lambda nf: nf[0])
        source = (named or beside)[0] if named or beside else None
        found.append(FrameExport(folder, base, frames, source))
    return found


def lone_sources(inv: Inventory) -> list[InventoryFile]:
    """The ``.aseprite`` sources a pack ships no picture of, by path. A source has an export
    when a picture anywhere in the pack has its name (``hero.png``, ``hero1.png`` ...), when a
    picture of its own folder has all the words of its name (``player jump 48x48`` beside
    ``player jump left 48x48-sheet.png``), or when its folder is a frame export."""
    stems: set[str] = set()
    words: dict[str, list[set[str]]] = {}
    for f in inv.files:
        if f.kind != "image":
            continue
        stem = posixpath.splitext(posixpath.basename(f.path))[0].strip().casefold()
        stems.add(stem)
        numbered = EXPORT_FRAME.match(stem)
        if numbered:
            stems.add(numbered.group("base").strip())
        words.setdefault(posixpath.dirname(f.path), []).append(set(_WORD.split(stem)) - {""})
    taken = {e.source for e in find_frame_exports(inv, set()) if e.source}
    found: list[InventoryFile] = []
    seen: set[tuple[str, str]] = set()
    for f in sorted(inv.files, key=lambda f: (f.path.casefold(), f.path)):
        if f.ext not in SOURCE_EXTENSIONS or f.path in taken:
            continue
        folder = posixpath.dirname(f.path)
        stem = posixpath.splitext(posixpath.basename(f.path))[0].strip().casefold()
        own = set(_WORD.split(stem)) - {""}
        if stem in stems or (folder, stem) in seen or any(own <= w for w in words.get(folder, [])):
            continue
        seen.add((folder, stem))  # "hero.ase" beside "hero.aseprite" is the same sprite
        found.append(f)
    return found


def rendered_name(f: InventoryFile, cols: int) -> str:
    """The strip of a drawn source: named after the source, so the same file gives the same."""
    text = f"aseprite/{RENDER_VERSION}/{cols}\n{f.sha256}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


def _is_blank(path: Path) -> bool:
    """A fully transparent picture: what some exporters write between two animations."""
    try:
        with Image.open(path) as im:
            return im.convert("RGBA").getchannel("A").getextrema()[1] == 0
    except (OSError, ValueError):
        return False


def split_export(root: Path, export: FrameExport) -> tuple[list[Sequence], bool]:
    """The animations of a frame export, and whether blank frames separated them. They are cut
    at the blank frames, which belong to no animation; an export without one is cut at the
    gaps of its numbering."""
    blank = {f.path for _n, f in export.frames if _is_blank(root / f.path)}
    runs: list[list[tuple[int, InventoryFile]]] = [[]]
    previous: int | None = None
    for number, f in export.frames:
        cut = f.path in blank or (not blank and previous is not None and number != previous + 1)
        if cut and runs[-1]:
            runs.append([])
        if f.path not in blank:
            runs[-1].append((number, f))
        previous = number
    return [Sequence(export.folder, export.base, run) for run in runs if run], bool(blank)


def cached_strip(project_path: str) -> Path:
    """Where the strip with this project path lies after an analysis that named no work
    folder (the wizard's): in the cache."""
    return paths.cache_dir() / WORK_FOLDER / posixpath.basename(project_path)


def layout(count: int, frame_width: int) -> tuple[int, int]:
    """Columns and rows of the strip that holds ``count`` frames."""
    cols = max(1, min(count, MAX_STRIP_WIDTH // max(1, frame_width)))
    return cols, -(-count // cols)


def strip_name(seq: Sequence) -> str:
    """Named after the frames it is made of, so that the same frames give the same file."""
    cols, _rows = layout(len(seq.frames), seq.size[0])
    text = "\n".join([f"frames/{cols}", *(f.sha256 for _, f in seq.frames)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


def write_strip(root: Path, seq: Sequence, dest: Path) -> None:
    w, h = seq.size
    cols, rows = layout(len(seq.frames), w)
    strip = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    for i, (_number, f) in enumerate(seq.frames):
        with Image.open(root / f.path) as im:
            strip.paste(im.convert("RGBA"), ((i % cols) * w, (i // cols) * h))
    dest.parent.mkdir(parents=True, exist_ok=True)
    strip.save(dest, format="PNG", optimize=False, pnginfo=None)


class SequencesAdapter:
    name = "sequences"
    priority = 55  # before the strips adapter

    def match(self, inv: Inventory, root: Path) -> float:
        if find_sequences(inv, set()) or find_facings(inv, set()):
            return 1.0
        for export in find_frame_exports(inv, set()):
            if split_export(root, export)[1] or self._source(root, export, IssueList()):
                return 1.0
        return 1.0 if lone_sources(inv) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        # one asset per character and frame size
        characters: dict[tuple[str, str, tuple[int, int]], list[Sequence]] = {}
        for seq in find_sequences(inv, ctx.claimed):
            characters.setdefault((seq.owner_folder, seq.owner, seq.size), []).append(seq)
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        for key in sorted(characters):
            self._character(root, ctx.pack_id, characters[key], work, result, issues)
        for character in find_facings(inv, ctx.claimed):
            self._facings(root, character, work, result, issues)
        taken = set(ctx.claimed) | {f.path for f in result.assets} | set(result.consumed)
        for export in find_frame_exports(inv, taken):
            self._export(root, export, work, result, issues)
        for source in lone_sources(inv):
            if source.path not in ctx.claimed:
                self._lone(root, source, work, result, issues)
        result.issues = list(issues)
        return result

    def _lone(
        self,
        root: Path,
        f: InventoryFile,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        """A ``.aseprite`` with no export beside it: its frames are drawn into one strip in the
        work folder, as a GIF's are, and that strip is the sprite, with the tags as its
        animations. A source nothing is drawn in (no cel) is no sprite; one that cannot be read
        is a note (ADAPT-006)."""
        try:
            picture = aseprite_file.render_file(root / f.path)
        except aseprite_file.AsepriteError as exc:
            issues.add("ADAPT-006", file=f.path, reason=str(exc))
            return
        drawn = [i for i, im in enumerate(picture.frames) if im.getchannel("A").getextrema()[1] > 0]
        if not drawn:
            return
        source = picture.file
        w, h = source.width, source.height
        cols, rows = layout(len(picture.frames), w)
        strip = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
        for i, im in enumerate(picture.frames):
            strip.paste(im, ((i % cols) * w, (i // cols) * h))
        file_name = rendered_name(f, cols)
        dest = work / file_name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            strip.save(dest, format="PNG", optimize=False, pnginfo=None)
        except OSError as exc:
            issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=str(exc))
            return

        def speed(indexes: list[int]) -> float:
            times = sorted(source.durations_ms[i] for i in indexes)
            return round(1000.0 / (times[len(times) // 2] or 100), 6)

        # (name or None, frames, loop): the tags, else everything that is drawn as one
        plan: list[tuple[str | None, list[int], bool]] = []
        for tag in source.tags:
            frames = [i for i in tag.frames() if i in drawn]
            norm = naming.normalize_name(tag.name)
            known = norm.action in naming.CANONICAL_ACTIONS
            if frames:
                loop = tag.looped and (naming.is_looping(norm.action) if known else True)
                plan.append((norm.name if known else None, frames, loop))
        if not plan and len(drawn) > 1:
            # no tag: the file's own name may say what it is ("player run 48x48.aseprite")
            stem = naming.name_facts(posixpath.splitext(posixpath.basename(f.path))[0]).stem
            m = SEQUENCE_NAME.match(stem)
            raw = m.group("action") + ("_" + m.group("dir") if m.group("dir") else "") if m else ""
            norm = naming.normalize_name(raw)
            named = bool(m) and norm.action in naming.CANONICAL_ACTIONS
            plan.append(
                (norm.name if named else "idle_down", drawn, naming.is_looping(norm.action))
            )
        if len(plan) == 1 and plan[0][0] is None:
            plan = [("idle_down", *plan[0][1:])]  # what a prop does all the time
        by_motion = False
        if any(name is None for name, _f, _l in plan):
            # tags whose names say nothing (pozak's ``player .ase``): named by their frames
            plan, by_motion = _tags_by_motion(picture.frames, plan)
        cell = [(i % cols, i // cols) for i in range(len(picture.frames))]
        mask = image_facts.occupancy(np.asarray(strip, dtype=np.uint8))
        rects = [(cell[i][0] * w, cell[i][1] * h, w, h) for i in (plan[0][1] if plan else drawn)]
        facets: dict[str, Any] = {
            "usage": "sprite",
            "frame": [w, h],
            "origin": [w // 2, frames_mod.baseline_y(mask, rects)],
            "size": [strip.width, strip.height],
        }
        unnamed = 0
        if plan:
            animations: dict[str, Any] = {}
            for index, (name, frames, loop) in enumerate(plan, start=1):
                if name is None or name in animations:
                    name = UNNAMED.format(index)
                    unnamed += 1
                animations[name] = {
                    "frames": [list(cell[i]) for i in frames],
                    "fps": speed(frames),
                    "loop": loop,
                }
            facets["grid"] = {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]}
            facets["animations"] = animations
        confidence = UNNAMED_CONFIDENCE if unnamed else RENDERED_CONFIDENCE
        if by_motion and not unnamed:
            confidence = min(confidence, MOTION_CONFIDENCE)
            facets["tags"] = ["motion_named"]
        if picture.inexact:
            confidence = min(confidence, INEXACT_CONFIDENCE)
        project_path = f"{FRAME_STRIP_DIR}/{file_name}"
        result.assets.append(AssetFragment(f.path, facets, confidence, "full"))
        result.generated[project_path] = str(dest)
        result.rendered[f.path] = project_path
        if unnamed:
            issues.add("ADAPT-005", count=unnamed, sequence=f.path, file=f.path)

    def _export(
        self,
        root: Path,
        export: FrameExport,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        """A frame export without an action word: one sprite. Its animations are those the
        ``.aseprite`` source beside the frames tags, by name when a tag has one that says what
        it is; else ``anim_1`` ... ``anim_n`` until somebody names them."""
        if set(_label_words(export.label)) & TILE_EXPORT_WORDS:
            return  # tiles exported one by one (pozak's ``Terrain/PNG``): pictures, no frames
        source = self._source(root, export, issues)
        sequences, separated = split_export(root, export)
        if not separated and source is None:
            return  # nothing says these are frames: they stay pictures of their own
        plan = self._plan(export, sequences, source)
        if not plan:
            return
        if len(plan) == 1 and plan[0][0] is None:
            # one animation and no name: what a prop does all the time (a flame, a portal)
            plan = [("idle_down", *plan[0][1:])]
        plan, by_motion = _named_by_motion(root, plan)
        w, h = plan[0][1].size
        animations: dict[str, Any] = {}
        baseline = 0
        unnamed = 0
        for index, (name, seq, fps, loop) in enumerate(plan, start=1):
            if name is None or name in animations:
                name = UNNAMED.format(index)
                unnamed += 1
            file_name = strip_name(seq)
            dest = work / file_name
            try:
                write_strip(root, seq, dest)
            except (OSError, ValueError) as exc:
                issues.add(
                    "ADAPT-001", adapter=self.name, file=seq.frames[0][1].path, reason=str(exc)
                )
                return
            project_path = f"{FRAME_STRIP_DIR}/{file_name}"
            result.generated[project_path] = str(dest)
            cols, _rows = layout(len(seq.frames), w)
            cells = [[i % cols, i // cols] for i in range(len(seq.frames))]
            animations[name] = {
                "frames": cells,
                "fps": fps,
                "loop": loop,
                "source": project_path,
            }
            if index == 1:
                mask = image_facts.occupancy(image_facts.load_rgba(dest))
                baseline = frames_mod.baseline_y(mask, [(c * w, r * h, w, h) for c, r in cells])
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
            "frame": [w, h],
            "origin": [w // 2, baseline],
            "animations": animations,
        }
        first = export.frames[0][1]
        confidence = UNNAMED_CONFIDENCE if unnamed else 0.9
        if by_motion and not unnamed:
            # named from what the frames do (T17.33)
            confidence = MOTION_CONFIDENCE
            facets["tags"] = ["motion_named"]
        result.assets.append(AssetFragment(first.path, facets, confidence, "full"))
        result.consumed.extend(f.path for _n, f in export.frames if f.path != first.path)
        if unnamed:
            issues.add("ADAPT-005", count=unnamed, sequence=export.label, file=first.path)

    def _source(
        self, root: Path, export: FrameExport, issues: IssueList
    ) -> aseprite_file.AsepriteFile | None:
        """The source beside the frames, when it is the file these frames were exported from:
        as many frames as there are pictures, numbered without a gap. A source that cannot be
        read is a note (ADAPT-006); one of another shape (a layered still beside four
        backgrounds) says nothing about the pictures and is left alone."""
        if export.source is None:
            return None
        try:
            source = aseprite_file.read(root / export.source)
        except aseprite_file.AsepriteError as exc:
            issues.add("ADAPT-006", file=export.source, reason=str(exc))
            return None
        numbers = [n for n, _f in export.frames]
        whole = numbers == list(range(numbers[0], numbers[0] + len(numbers)))
        return source if whole and source.frame_count == len(numbers) > 1 else None

    def _plan(
        self,
        export: FrameExport,
        sequences: list[Sequence],
        source: aseprite_file.AsepriteFile | None,
    ) -> list[tuple[str | None, Sequence, float, bool]]:
        """``(name or None, frames, fps, loop)`` per animation. The tags of the source are the
        animations when it has any (they cut where the artist cut, also between two
        animations with no blank frame between them); else the runs between the blank frames."""

        def speed(indexes: list[int]) -> float:
            if source is None or not indexes:
                return 8.0
            times = sorted(source.durations_ms[i] for i in indexes)
            return round(1000.0 / (times[len(times) // 2] or 100), 6)

        if source is None or not source.tags:
            first = export.frames[0][0]
            return [
                (None, seq, speed([n - first for n, _f in seq.frames]), True) for seq in sequences
            ]
        shown = {f.path for seq in sequences for _n, f in seq.frames}  # the frames not blank
        plan: list[tuple[str | None, Sequence, float, bool]] = []
        for tag in source.tags:
            frames = [export.frames[i] for i in tag.frames() if export.frames[i][1].path in shown]
            if not frames:
                continue
            norm = naming.normalize_name(tag.name)
            known = norm.action in naming.CANONICAL_ACTIONS
            plan.append(
                (
                    norm.name if known else None,
                    Sequence(export.folder, export.base, frames),
                    speed(tag.frames()),
                    tag.looped and (naming.is_looping(norm.action) if known else True),
                )
            )
        return plan

    def _facings(
        self,
        root: Path,
        character: FacingSet,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        """A character drawn once a facing (``find_facings``): one sprite with an animation
        for every action and facing, named as the runtime plays them (``walk_down``,
        ``walk_up_left``; a run is the walk), each from a strip of its own frames. An action
        the runtime does not know (``Pickup``) keeps its name, small, and plays once."""
        files = character.files
        size = ((files[0].image or {}).get("w", 0), (files[0].image or {}).get("h", 0))
        w, h = int(size[0]), int(size[1])
        animations: dict[str, Any] = {}
        baseline = 0
        for written in sorted(character.actions, key=lambda a: (a.casefold(), a)):
            action = naming.SYNONYMS.get(written.casefold(), written.casefold())
            known = action in naming.CANONICAL_ACTIONS
            for facing, direction in enumerate(FACINGS):
                name = f"{action}_{direction}"
                if name in animations:
                    continue  # "Run" and "Walk" of one character: the first one is the walk
                seq = Sequence(character.folder, written, character.actions[written][facing])
                file_name = strip_name(seq)
                dest = work / file_name
                try:
                    write_strip(root, seq, dest)
                except (OSError, ValueError) as exc:
                    issues.add(
                        "ADAPT-001", adapter=self.name, file=seq.frames[0][1].path, reason=str(exc)
                    )
                    return
                project_path = f"{FRAME_STRIP_DIR}/{file_name}"
                result.generated[project_path] = str(dest)
                cols, _rows = layout(len(seq.frames), w)
                cells = [[i % cols, i // cols] for i in range(len(seq.frames))]
                animations[name] = {
                    "frames": cells,
                    "fps": naming.fps(action),
                    "loop": naming.is_looping(action) if known else len(cells) == 1,
                    "source": project_path,
                }
                if direction == "down" and not baseline:
                    mask = image_facts.occupancy(image_facts.load_rgba(dest))
                    baseline = frames_mod.baseline_y(mask, [(c * w, r * h, w, h) for c, r in cells])
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
            "frame": [w, h],
            "origin": [w // 2, baseline],
            "animations": {k: animations[k] for k in sorted(animations)},
            "directions": len(FACINGS),
        }
        sure = facings_mirror(root, character)
        confidence = FACINGS_CONFIDENCE if sure else FACINGS_UNSURE_CONFIDENCE
        result.assets.append(AssetFragment(files[0].path, facets, confidence, "full"))
        result.consumed.extend(f.path for f in files[1:])

    def _character(
        self,
        root: Path,
        pack_id: str,
        sequences: list[Sequence],
        work: Path,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        w, h = sequences[0].size
        animations: dict[str, Any] = {}
        used: list[InventoryFile] = []
        baseline = 0
        for seq in sequences:
            norm = naming.normalize_name(seq.raw_name)
            if norm.name in animations:
                continue  # "run" and "walk" of one character: the first one is the walk
            file_name = strip_name(seq)
            dest = work / file_name
            try:
                write_strip(root, seq, dest)
            except (OSError, ValueError) as exc:
                issues.add(
                    "ADAPT-001", adapter=self.name, file=seq.frames[0][1].path, reason=str(exc)
                )
                continue
            project_path = f"{FRAME_STRIP_DIR}/{file_name}"
            result.generated[project_path] = str(dest)
            cols, _rows = layout(len(seq.frames), w)
            spec: dict[str, Any] = {
                "frames": [[i % cols, i // cols] for i in range(len(seq.frames))],
                "fps": naming.fps(norm.action),
                "loop": naming.is_looping(norm.action),
                "source": project_path,
            }
            animations[norm.name] = spec
            if norm.side and norm.direction == "right":
                mirror = f"{norm.action}_left"
                if mirror not in animations:
                    animations[mirror] = {**spec, "flip_h": True}
                    issues.add(
                        "ANIM-002", anim=mirror, source_anim=norm.name, file=seq.frames[0][1].path
                    )
            if norm.direction_assumed:
                result.pack_warnings.append(f"sequences_direction_assumed:{seq.label}")
            missing = seq.missing()
            if missing:
                listed = ", ".join(str(n) for n in missing[:MAX_LISTED_GAPS])
                more = ", ..." if len(missing) > MAX_LISTED_GAPS else ""
                issues.add(
                    "ADAPT-004",
                    sequence=seq.label,
                    frames=f"missing {listed}{more}",
                    file=seq.frames[0][1].path,
                )
            if not used:
                mask = image_facts.occupancy(image_facts.load_rgba(dest))
                rects = [(c * w, r * h, w, h) for c, r in spec["frames"]]
                baseline = frames_mod.baseline_y(mask, rects)
            used.extend(f for _, f in seq.frames)
        if not used:
            return
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
            "frame": [w, h],
            "origin": [w // 2, baseline],
            "animations": {k: animations[k] for k in sorted(animations)},
        }
        if any(k.endswith(naming.DIAGONALS) for k in animations):
            facets["directions"] = 8
        result.assets.append(AssetFragment(used[0].path, facets, 0.9, "full"))
        result.consumed.extend(f.path for f in used[1:])

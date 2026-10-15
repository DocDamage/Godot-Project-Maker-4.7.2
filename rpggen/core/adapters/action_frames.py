"""Characters as frames in folders named by their actions (T17.32).

ansimuz's and pozak's side-view characters are folders of numbered frames, one folder an
action, under the character's folder (``Hell-Hound-Files/Sprites/Idle/frame5.png``,
``Ogre/Sprites/walk-unarmed/ogre-walk-unarmed-3.png``, ``Hell-Beast-Files/Burn/Sprites/*``),
often with the same animations again as strips (``Spritesheets/hell-hound-idle.png``) and as
previews (``Previews/hell-hound-idle.gif``). The frame files carry no action word of their own
(``frame5``) or one the numbered-frame reader takes for a character of its own folder, so each
frame used to become an asset, and the animations' names were lost although the folders give
them.

A **character** here is a folder holding two or more *action folders* (a folder whose pictures
are numbered frames of one stem), at least one of which is named by an action word
(``naming.ACTIONS``) in its own name or its frames' stem. A folder named ``Sprites``, ``PNG``,
``frames`` and the like is no action and no character: it is looked through (the action is
the folder above it, or the character is). Every action folder is one animation of the
character, named by its words (``idle``, ``walk``, ``attack``, ``attack_crouch``,
``walk_unarmed``; ``run`` stays ``run`` beside a ``walk``); a folder whose frames are much
smaller than the character's (*Hell-Beast*'s fireball) is no animation of it. A character of
one action folder and nothing else (``flying-eye-demon/Sprites/flying-eye-demon1..8``) is read
when the folder is a generic one under the character's own: its one animation is named by the
action word of its stem, else ``idle``.

The frames are put into one strip an animation, each frame on a canvas as large as the
largest frame of the character, its bottom and middle where the frame's are, so every
animation has one frame size. The pictures of the character's folder that hold an animation
again (a strip as wide as its frames side by side, or a sheet named by the action) are set
aside as ``same_frames``; its GIFs as ``preview_gif``. The role is left to the classifier
(the words of the character's folders), and the catalog's side-view pass makes a character
that only a folder called *characters* called an NPC an enemy (``catalog._side_characters``).
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from rpggen import paths
from rpggen.core.adapters import naming, sequences
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

NAME = "action_frames"
TAG = "action_folders"
FOLDER_TAG = "character_folder:"
SAME_FRAMES = "same_frames"
PREVIEW_GIF = "preview_gif"
UNUSED = "unused_because:"
SAME_AS = "same_as:"
CONFIDENCE = 0.9
# a folder of these words holds the frames, it does not name an action or a character
GENERIC_WORDS = frozenset(
    {"sprites", "sprite", "png", "pngs", "frames", "frame", "images", "image", "animations",
     "animation", "anims", "anim", "individual", "separate", "split"}
)  # fmt: skip
PREVIEW_WORDS = frozenset({"preview", "previews", "gif", "gifs"})
# a frame's number: glued to the stem (``frame5``), after a separator (``ogre-attack-3``), in
# brackets (``Walk (3)``) or first (``_0003_Layer-4``)
TRAILING = re.compile(r"^(?P<base>.*?)[_\- ]*\(?(?P<num>\d+)\)?[_\- ]*$")
LEADING = re.compile(r"^[_\- ]*(?P<num>\d+)(?P<base>\D.*)?$")
MIN_FRAMES = 2
# an action folder whose frames are this much smaller both ways than the character's largest
# is something it throws, not one of its animations
SMALL_PART = 0.5
_WORDS = re.compile(r"[^0-9a-z]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
STRIP_DIR = sequences.FRAME_STRIP_DIR
WORK_FOLDER = sequences.WORK_FOLDER


def words(text: str) -> list[str]:
    """The small-letter words of a name: camel case and separators split, numbers dropped."""
    spaced = _CAMEL.sub(" ", text)
    return [w for w in _WORDS.split(spaced.casefold()) if w and not w.isdigit()]


def _action_of(text: str) -> str | None:
    """The action word a name holds (its canonical form), or None."""
    for word in words(text):
        if word in naming.ACTIONS:
            return naming.SYNONYMS.get(word, word) if word != "run" else "run"
    return None


@dataclass
class ActionFolder:
    """The numbered frames of one folder, in order."""

    folder: str
    label: str  # the folder that names the action (the frames' folder, or the one above it)
    frames: list[InventoryFile]
    size: tuple[int, int]
    stem: str  # the frames' stem without its number
    strip: bool = False  # T17.33: one file, its frames side by side (``male_hero-run.png``)


def _numbered(files: list[InventoryFile]) -> list[tuple[int, InventoryFile]] | None:
    """The frames of a folder in order, when every picture is one stem with a number."""
    parsed: list[tuple[str, int, InventoryFile]] = []
    for f in files:
        stem = posixpath.splitext(posixpath.basename(f.path))[0]
        m = TRAILING.match(stem)
        if m is None:
            return None
        parsed.append((m.group("base").strip().casefold(), int(m.group("num")), f))
    if len({b for b, _n, _f in parsed}) != 1:
        # ``_0000_Layer-1`` ... ``_0006_Layer-7``: the number in front counts
        lead: list[tuple[str, int, InventoryFile]] = []
        for f in files:
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            m2 = LEADING.match(stem)
            if m2 is None:
                return None
            lead.append(
                (
                    _WORDS.sub("", (m2.group("base") or "").casefold().rstrip("0123456789")),
                    int(m2.group("num")),
                    f,
                )
            )
        if len({b for b, _n, _f in lead}) != 1:
            return None
        parsed = lead
    numbers = [n for _b, n, _f in parsed]
    if len(set(numbers)) != len(numbers):
        return None
    return [(n, f) for _b, n, f in sorted(parsed, key=lambda t: t[1])]


def _is_still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext in (".png", ".bmp", ".webp")


def _generic(name: str) -> bool:
    ws = words(name)
    return bool(ws) and all(w in GENERIC_WORDS for w in ws)


def find_action_folders(inv: Inventory, claimed: set[str]) -> list[ActionFolder]:
    """Every folder whose pictures are the numbered frames of one stem and one size."""
    by_folder: dict[str, list[InventoryFile]] = {}
    for f in inv.files:
        if f.kind == "image":
            by_folder.setdefault(posixpath.dirname(f.path), []).append(f)
    found: list[ActionFolder] = []
    for folder in sorted(by_folder):
        files = by_folder[folder]
        if not folder or len(files) < MIN_FRAMES:
            continue
        if any(not _is_still(f) or f.path in claimed for f in files):
            continue
        ordered = _numbered(files)
        if ordered is None:
            continue
        sizes = {
            (int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))) for f in files
        }
        if len(sizes) != 1 or 0 in next(iter(sizes)):
            continue
        name = posixpath.basename(folder)
        parent = posixpath.dirname(folder)
        label = folder
        if _generic(name) and parent:
            label = parent  # ``Burn/Sprites``: the action is the folder above
        stem = posixpath.splitext(posixpath.basename(ordered[0][1].path))[0]
        m = TRAILING.match(stem)
        found.append(
            ActionFolder(folder, label, [f for _n, f in ordered], next(iter(sizes)),
                         (m.group("base") if m else stem).strip())
        )  # fmt: skip
    return found


@dataclass
class Character:
    folder: str  # the character's folder
    actions: list[tuple[str, ActionFolder]]  # (animation name, frames), in name order
    size: tuple[int, int]  # the largest frame


def _owner(action: ActionFolder) -> str:
    """The character's folder of an action folder: the one above the action, past the generic
    folders between them."""
    owner = posixpath.dirname(action.label)
    while owner and _generic(posixpath.basename(owner)):
        owner = posixpath.dirname(owner)
    return owner


def _canonical(word: str) -> str:
    """An action word in its usual form (``hit`` is ``hurt``); ``run`` stays ``run``, and a
    word that is no action (``front``) is left as it is."""
    if word == "run" or word not in naming.ACTIONS:
        return word
    return naming.SYNONYMS.get(word, word)


def _anim_name(action: ActionFolder, character: str, shared: set[str]) -> str:
    """``attack``, ``attack_crouch``, ``walk_unarmed``: the action folder's words (or its
    frames' stem's) without the character's own name, without the words every animation of
    the character has (``player`` of ``player-idle``, ``player-attack``) and without generic
    words."""
    own = set(words(posixpath.basename(character))) | shared
    for text in (posixpath.basename(action.label), action.stem):
        ws = [w for w in words(text) if w not in own and w not in GENERIC_WORDS]
        if not ws:
            continue
        mapped = [_canonical(w) for w in ws]
        verb = next((w for w in mapped if w in naming.CANONICAL_ACTIONS or w == "run"), None)
        if verb is not None:
            rest = [w for w in mapped if w != verb]
            return "_".join([verb, *rest])
        if text == posixpath.basename(action.label):
            return "_".join(mapped)
    return ""


def _shared_words(members: list[ActionFolder]) -> set[str]:
    """The words every action folder of a character has in its name or its stem and that are
    no action: the character's name written into each (``player`` of ``player-idle``)."""
    if len(members) < 2:
        return set()
    sets = [set(words(posixpath.basename(a.label))) | set(words(a.stem)) for a in members]
    common = set.intersection(*sets)
    return {w for w in common if w not in naming.ACTIONS}


def _sequences_read(
    actions: dict[str, ActionFolder], by_sequence: dict[str, tuple[Any, ...]]
) -> bool:
    """True when the numbered-frame reader reads these frames as one character already (bare
    numbers in folders named by actions, ``bat/attack/0001.png``): it is left to that reader,
    which names the animations as it always has."""
    owners = set()
    for a in actions.values():
        for f in a.frames:
            if f.path not in by_sequence:
                return False
            owners.add(by_sequence[f.path])
    return len(owners) == 1


def find_characters(inv: Inventory, claimed: set[str]) -> list[Character]:
    by_sequence: dict[str, tuple[Any, ...]] = {}
    for seq in sequences.find_sequences(inv, claimed):
        for _n, f in seq.frames:
            by_sequence[f.path] = (seq.owner_folder, seq.owner, seq.size)
    groups: dict[str, list[ActionFolder]] = {}
    for action in find_action_folders(inv, claimed):
        owner = _owner(action)
        if not owner:
            continue
        groups.setdefault(owner, []).append(action)
    out: list[Character] = []
    for owner in sorted(groups):
        members = groups[owner]
        named = [
            a for a in members if _action_of(posixpath.basename(a.label)) or _action_of(a.stem)
        ]
        single = (
            len(members) == 1
            and members[0].label == members[0].folder
            and _generic(posixpath.basename(members[0].folder))
        )
        # folders of frames of one size side by side in a folder of sprites (``Dancing Girl
        # Files/sprites/{Balancing,hips,Skip}``): one character's animations, whatever they do
        structural = (
            len(members) >= 2
            and len({a.size for a in members}) == 1
            and all(a.label == a.folder for a in members)
            and all(_generic(posixpath.basename(posixpath.dirname(a.folder))) for a in members)
        )
        if not named and not single and not structural:
            continue
        if set(words(owner)) & EFFECTS_FOLDER:
            continue  # ``Grotto-escape-2-FX/sprites/{fire-ball,slash}``: effects, each its own
        if len(members) < 2 and not single:
            # one folder of frames and nothing beside it: the sequences reader's, or no character
            continue
        big = (max(a.size[0] for a in members), max(a.size[1] for a in members))
        actions: dict[str, ActionFolder] = {}
        shared = _shared_words(members)
        for a in sorted(members, key=lambda a: a.folder.casefold()):
            if a.size[0] < big[0] * SMALL_PART and a.size[1] < big[1] * SMALL_PART:
                continue  # a fireball the beast throws
            name = "idle" if single else _anim_name(a, owner, shared)
            if single:
                name = _action_of(a.stem) or "idle"
            if not name or name in actions:
                continue
            actions[name] = a
        if not actions or _sequences_read(actions, by_sequence):
            continue
        size = (
            max(a.size[0] for a in actions.values()),
            max(a.size[1] for a in actions.values()),
        )
        out.append(Character(owner, sorted(actions.items()), size))
    taken = {f.path for c in out for _n, a in c.actions for f in a.frames}
    out.extend(find_action_files(inv, claimed | taken))
    return out


# the words of a file that name what a character does (an action word, or one the packs use
# for one: ``stand`` is idle, ``hit`` is hurt, ``duck`` is a crouch)
FILE_ACTIONS = frozenset({*naming.ACTIONS, "stand", "duck", "crouch", "hurt", "attacking", "atk"})
_FILE_FRAME = re.compile(r"^(?P<base>.*?[^\d])[_\- ]?(?P<num>\d{1,3})$")


def find_action_files(inv: Inventory, claimed: set[str]) -> list[Character]:
    """A folder of one character's pictures, a file an action or a frame (Kenney's
    ``alienBeige_walk1``, ``alienBeige_walk2``, ``alienBeige_jump``, ``alienBeige_stand``,
    ``alienBeige_hit``): every name is the character's name, an action word and maybe a frame's
    number, all of one size, and two actions at least. The animations are named by the action
    (``stand`` is ``idle``, ``hit`` is ``hurt``)."""
    # a character rendered once a facing (``Male_3_Run7``) is the numbered-frame reader's
    facing = {f.path for s in sequences.find_facings(inv, claimed) for f in s.files}
    # and frames it reads by their names (``hero_walk_ne_01``) are its as well
    facing |= {f.path for s in sequences.find_sequences(inv, claimed) for _n, f in s.frames}
    by_folder: dict[str, list[InventoryFile]] = {}
    for f in inv.files:
        if f.kind == "image":
            by_folder.setdefault(posixpath.dirname(f.path), []).append(f)
    out: list[Character] = []
    for folder in sorted(by_folder):
        files = by_folder[folder]
        if any(f.path in facing for f in files):
            continue
        if (
            not folder
            or len(files) < 3
            or any(not _is_still(f) or f.path in claimed for f in files)
        ):
            continue
        sizes = {
            (int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))) for f in files
        }
        if len(sizes) != 1 or 0 in next(iter(sizes)):
            continue
        w, h = next(iter(sizes))
        if w >= 2 * h:
            continue  # strips of frames side by side: the strips reader's
        split: list[tuple[list[str], int, InventoryFile]] = []
        for f in files:
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            m = _FILE_FRAME.match(stem)
            split.append(
                (words(m.group("base") if m else stem), int(m.group("num")) if m else 0, f)
            )
        names = set()
        for ws, _n, _f in split:
            k = next((i for i, w in enumerate(ws) if w in FILE_ACTIONS), None)
            if k:
                names.add(tuple(ws[:k]))
        if len(names) != 1:
            continue
        prefix = list(next(iter(names)))
        parsed: list[tuple[str, str, int, InventoryFile]] = []  # (name, action, frame, file)
        for ws, number, f in split:
            if ws[: len(prefix)] != prefix or len(ws) == len(prefix):
                parsed = []
                break  # a picture of something else in the folder: no character's folder
            parsed.append(("_".join(prefix), "_".join(ws[len(prefix) :]), number, f))
        if not parsed or sum(1 for p in parsed if p[1].split("_")[0] in FILE_ACTIONS) < 2:
            continue
        actions: dict[str, list[tuple[int, InventoryFile]]] = {}
        for _name, action, number, f in parsed:
            actions.setdefault(action, []).append((number, f))
        if len(actions) < 2:
            continue
        size = next(iter(sizes))
        named: dict[str, ActionFolder] = {}
        for action in sorted(actions):
            frames = [f for _n, f in sorted(actions[action], key=lambda nf: (nf[0], nf[1].path))]
            first = action.split("_")[0]
            verb = {"stand": "idle", "duck": "crouch", "atk": "attack", "attacking": "attack"}.get(
                first, _canonical(first)
            )
            name = "_".join([verb, *action.split("_")[1:]])
            if name not in named:
                named[name] = ActionFolder(folder, folder, frames, size, action)
        out.append(Character(folder, sorted(named.items()), size))
    return out


# the words of a folder of an effect's frames (T17.33: ansimuz's *Explosions and Magic*)
EFFECT_WORDS = frozenset(
    {"fx", "vfx", "effect", "effects", "explosion", "explosions", "slash", "magic", "spell",
     "particle", "particles", "smoke", "impact", "hit", "hits", "spark", "sparks", "splash",
     "bolt", "pulse", "shock", "energy", "fireball", "burst", "blast", "death", "charged",
     "waveform", "crossed", "flash", "dust", "poof", "explode"}
)  # fmt: skip
EFFECT_CONFIDENCE = 0.85
# a folder of these words holds effects, never a character's animations
EFFECTS_FOLDER = frozenset({"fx", "vfx", "effect", "effects", "explosion", "explosions"})
EFFECT_TAG = "effect_frames"


def find_effects(inv: Inventory, claimed: set[str]) -> list[Character]:
    """The folders of numbered frames of one stem that no character took and whose folders say
    an effect (``Explosions pack/explosion-1-c/Sprites/explosion-c1..c10``, ``Hit/Sprites``,
    ``Warped shooting fx/Bolt/sprites``): one effect each, its frames one animation."""
    out: list[Character] = []
    for action in find_action_folders(inv, claimed):
        said = set(words(action.label)) | set(words(action.stem))
        if not said & EFFECT_WORDS:
            continue
        out.append(Character(action.label, [("idle", action)], action.size))
    return out


STRIP_FOLDER_WORDS = frozenset({"individual", "sheets", "sheet", "strips", "strip"})
WHOLE_SHEET = 8  # frames on a grid, at least: a sheet of all of a character's frames


def find_action_strips(inv: Inventory, claimed: set[str]) -> list[Character]:
    """A folder of one character's strips, a file an action (T17.33: the *hero with cape*'s
    ``individual_sheets/male_hero-run.png``, ``-idle``, ``-combo_1``): every picture as high as
    the others, as wide as a whole number of square frames, named by the character's name and
    then what it does, two of them by an action word. Each strip is one animation."""
    by_folder: dict[str, list[InventoryFile]] = {}
    for f in inv.files:
        if f.kind == "image" and _is_still(f) and f.path not in claimed:
            by_folder.setdefault(posixpath.dirname(f.path), []).append(f)
    out: list[Character] = []
    for folder in sorted(by_folder):
        files = by_folder[folder]
        if not folder or len(files) < 3:
            continue
        heights = {int((f.image or {}).get("h", 0)) for f in files}
        if len(heights) != 1:
            continue
        h = heights.pop()
        if h <= 0 or any(int((f.image or {}).get("w", 0)) % h for f in files):
            continue
        if all(int((f.image or {}).get("w", 0)) == h for f in files):
            continue  # single pictures: the action files' reader's
        split = [(words(posixpath.splitext(posixpath.basename(f.path))[0]), f) for f in files]
        # the character's name: the words every file begins with
        prefix: list[str] = []
        for column in zip(*(ws for ws, _f in split), strict=False):
            if len(set(column)) != 1:
                break
            prefix.append(column[0])
        if not prefix:
            continue
        actions: dict[str, ActionFolder] = {}
        for ws, f in sorted(split, key=lambda t: t[1].path):
            if ws[: len(prefix)] != prefix or len(ws) == len(prefix):
                actions = {}
                break
            raw = re.sub(
                r"[^0-9a-z]+", "_", posixpath.splitext(posixpath.basename(f.path))[0].casefold()
            )
            raw = raw.strip("_")
            head = "_".join(prefix)
            rest = (raw[len(head) + 1 :] if raw.startswith(head + "_") else raw).split("_")
            verb = {"stand": "idle", "duck": "crouch", "atk": "attack"}.get(
                rest[0], _canonical(rest[0])
            )
            name = "_".join([verb, *rest[1:]])
            if name not in actions:
                actions[name] = ActionFolder(folder, folder, [f], (h, h), "_".join(rest), True)
        if sum(1 for n in actions if n.split("_")[0] in FILE_ACTIONS | {"idle", "crouch"}) < 2:
            continue
        owner = folder
        if set(words(posixpath.basename(folder))) <= GENERIC_WORDS | STRIP_FOLDER_WORDS:
            owner = posixpath.dirname(folder) or folder
        out.append(Character(owner, sorted(actions.items()), (h, h)))
    return out


def write_cells(root: Path, f: InventoryFile, size: tuple[int, int], dest: Path) -> int:
    """A strip's frames laid out as ``write_strip`` lays frames; returns how many."""
    w, h = size
    with Image.open(root / f.path) as im:
        strip = im.convert("RGBA")
    count = max(1, strip.width // w)
    cols, rows = sequences.layout(count, w)
    out = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    for i in range(count):
        out.paste(strip.crop((i * w, 0, (i + 1) * w, h)), ((i % cols) * w, (i // cols) * h))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, format="PNG", optimize=False, pnginfo=None)
    return count


RUN_MIN_FRAMES = 16
MOTION_CONFIDENCE = 0.8
TILE_WORDS = frozenset({"terrain", "tile", "tiles", "tileset", "tilemap", "tilesheet", "ground"})


def find_runs(root: Path, inv: Inventory, claimed: set[str]) -> list[Character]:
    """A folder of many numbered frames of one stem with empty frames between its animations
    (T17.33: the *black knight*'s ``CHARACTER/CHARACTER1..168``): one character, each run of
    painted frames an animation named by what its frames do (``motion``)."""
    import numpy as np

    from rpggen.core import motion

    out: list[Character] = []
    for action in find_action_folders(inv, claimed):
        if len(action.frames) < RUN_MIN_FRAMES:
            continue
        if set(words(action.label)) & TILE_WORDS or set(words(action.stem)) & TILE_WORDS:
            continue  # pozak's ``Terrain/PNG/Terrain (24x24))1..533``: tiles one by one
        images = []
        for f in action.frames:
            try:
                with Image.open(root / f.path) as im:
                    images.append(np.asarray(im.convert("RGBA")))
            except (OSError, ValueError):
                images.append(np.zeros((1, 1, 4), np.uint8))
        found = motion.runs(images)
        if len(found) < 2:
            continue
        fig = motion.figure(found)
        if fig is None:
            continue
        named = motion.names(found, fig)
        actions = [
            (name, ActionFolder(action.folder, action.label, [action.frames[f.col] for f in run],
                                action.size, action.stem))
            for name, run in zip(named, found, strict=True)
        ]  # fmt: skip
        owner = _owner(action) or action.label
        out.append(Character(owner, sorted(actions), action.size))
    return out


SAYS = "says:"
# the words of a file beside a character's folders that say what the character is
# (``space-marine-lite/player.ase``, ``player-preview.gif``)
ROLE_FILE_WORDS = frozenset({"player", "hero", "heroine", "boss", "npc", "villager"})


def _sibling_words(inv: Inventory, folder: str) -> list[str]:
    """``says:<word>`` for every role word in the names of the files in the character's own
    folder (not in its sub-folders)."""
    found: set[str] = set()
    for f in inv.files:
        if posixpath.dirname(f.path) == folder:
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            found |= set(words(stem)) & ROLE_FILE_WORDS
    return sorted(SAYS + w for w in found)


def directed(name: str) -> str:
    """An animation's name as the other readers write it: with the direction it faces, ``down``
    when the name gives none (the side-view kinds read ``attack_down`` as ``attack``)."""
    parts = name.split("_")
    if any(p in naming.DIRECTIONS for p in parts):
        return name
    return f"{name}_down"


def strip_name(frames: list[InventoryFile], size: tuple[int, int]) -> str:
    cols, _rows = sequences.layout(len(frames), size[0])
    text = "\n".join([f"action_frames/{cols}/{size[0]}x{size[1]}", *(f.sha256 for f in frames)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


def write_strip(root: Path, frames: list[InventoryFile], size: tuple[int, int], dest: Path) -> None:
    """The frames side by side, each on a canvas of ``size`` with its bottom middle at the
    canvas's bottom middle."""
    w, h = size
    cols, rows = sequences.layout(len(frames), w)
    strip = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        with Image.open(root / f.path) as im:
            frame = im.convert("RGBA")
        x = (i % cols) * w + (w - frame.width) // 2
        y = (i // cols) * h + (h - frame.height)
        strip.paste(frame, (x, y))
    dest.parent.mkdir(parents=True, exist_ok=True)
    strip.save(dest, format="PNG", optimize=False, pnginfo=None)


def _lowest_row(path: Path, size: tuple[int, int], count: int) -> int:
    """The lowest painted row of the first frame of a strip (the character's feet)."""
    try:
        with Image.open(path) as im:
            alpha = im.convert("RGBA").getchannel("A").crop((0, 0, size[0], size[1]))
    except (OSError, ValueError):
        return size[1] - 1
    box = alpha.point(lambda v: 255 if v > 0 else 0).getbbox()
    return (box[3] - 1) if box else size[1] - 1


class ActionFramesAdapter:
    name = NAME
    priority = 54  # after the object sheets, before the numbered frames of one folder

    def match(self, inv: Inventory, root: Path) -> float:
        if find_characters(inv, set()) or find_effects(inv, set()):
            return 1.0
        if find_action_strips(inv, set()):
            return 1.0
        # a folder of many numbered frames may be one character's animations (``find_runs``)
        many = any(len(a.frames) >= RUN_MIN_FRAMES for a in find_action_folders(inv, set()))
        return 1.0 if many else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        characters = find_characters(inv, ctx.claimed)
        for character in characters:
            ctx.check_cancel()
            self._character(root, inv, character, work, result, issues)
        taken = {f.path for c in characters for _n, a in c.actions for f in a.frames}
        effects = find_effects(inv, ctx.claimed | taken)
        for effect in effects:
            ctx.check_cancel()
            self._character(root, inv, effect, work, result, issues, effect=True)
        taken |= {f.path for c in effects for _n, a in c.actions for f in a.frames}
        held = taken | set(result.consumed) | {a.path for a in result.assets}
        homes = tuple(c.folder + "/" for c in characters)
        for character in find_action_strips(inv, ctx.claimed | held):
            if character.folder.startswith(homes) or (character.folder + "/").startswith(homes):
                continue  # a character's strips beside its frames: set aside with it
            ctx.check_cancel()
            self._character(root, inv, character, work, result, issues)
            taken |= {f.path for _n, a in character.actions for f in a.frames}
        for character in find_runs(root, inv, ctx.claimed | taken):
            ctx.check_cancel()
            self._character(root, inv, character, work, result, issues, named_by_motion=True)
            # the empty frames between the animations are part of the folder too
            folder = character.actions[0][1].folder + "/"
            used = set(result.consumed) | {a.path for a in result.assets}
            result.consumed.extend(
                f.path for f in inv.files
                if f.kind == "image" and posixpath.dirname(f.path) + "/" == folder
                and f.path not in used
            )  # fmt: skip
        result.issues = list(issues)
        return result

    def _character(
        self,
        root: Path,
        inv: Inventory,
        character: Character,
        work: Path,
        result: AdapterResult,
        issues: IssueList,
        effect: bool = False,
        named_by_motion: bool = False,
    ) -> None:
        w, h = character.size
        animations: dict[str, Any] = {}
        used: list[InventoryFile] = []
        baseline = h - 1
        counts: dict[str, int] = {}
        for anim, action in character.actions:
            file_name = strip_name(action.frames, character.size)
            dest = work / file_name
            try:
                if action.strip:
                    count = write_cells(root, action.frames[0], character.size, dest)
                else:
                    write_strip(root, action.frames, character.size, dest)
                    count = len(action.frames)
            except (OSError, ValueError) as exc:
                issues.add(
                    "ADAPT-001", adapter=self.name, file=action.frames[0].path, reason=str(exc)
                )
                continue
            project_path = f"{STRIP_DIR}/{file_name}"
            result.generated[project_path] = str(dest)
            cols, _rows = sequences.layout(count, w)
            verb = anim.split("_")[0]
            animations[directed(anim)] = {
                "frames": [[i % cols, i // cols] for i in range(count)],
                "fps": naming.fps(verb),
                "loop": naming.is_looping(verb),
                "source": project_path,
            }
            counts[directed(anim)] = count
            if not used or anim == "idle":
                baseline = _lowest_row(dest, character.size, len(action.frames))
            used.extend(action.frames)
        if not used:
            return
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [w, h], "margin": [0, 0], "separation": [0, 0]},
            "frame": [w, h],
            "origin": [w // 2, baseline],
            "animations": {k: animations[k] for k in sorted(animations)},
            "tags": [
                TAG,
                f"{FOLDER_TAG}{character.folder}",
                *_sibling_words(inv, character.folder),
            ],
        }
        confidence = CONFIDENCE
        if named_by_motion:
            facets["tags"] = [*facets["tags"], "motion_named"]
            said = set(words(character.folder)) | set(words(character.actions[0][1].stem))
            facets["role"] = (
                "PLAYER" if said & {"character", "player", "hero", "heroine"} else "ENEMY"
            )
            confidence = MOTION_CONFIDENCE
        if effect:
            # an effect plays once where it happens (T17.33)
            facets["role"] = "EFFECT"
            facets["tags"] = [EFFECT_TAG]
            for anim in facets["animations"].values():
                anim["loop"] = False
            facets["origin"] = [w // 2, h // 2]
            confidence = EFFECT_CONFIDENCE
        result.assets.append(AssetFragment(used[0].path, facets, confidence, "full"))
        result.consumed.extend(f.path for f in used[1:])
        # the Aseprite sources of the same animations are not drawn again
        prefix = character.folder + "/"
        result.consumed.extend(
            f.path for f in inv.files
            if f.path.startswith(prefix) and f.ext in sequences.SOURCE_EXTENSIONS
        )  # fmt: skip
        taken = {f.path for f in used}
        self._aside(inv, character, counts, used[0].path, taken, result)

    def _aside(
        self,
        inv: Inventory,
        character: Character,
        counts: dict[str, int],
        first: str,
        taken: set[str],
        result: AdapterResult,
    ) -> None:
        """The character's strips and previews of the same animations: set aside."""
        prefix = character.folder + "/"
        sizes = {(int(a.size[0]), int(a.size[1])) for _n, a in character.actions}
        frame_counts = set(counts.values())
        anim_words = {w for name in counts for w in name.split("_")}
        for f in inv.files:
            if f.kind != "image" or f.path in taken or not f.path.startswith(prefix):
                continue
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            folders = posixpath.dirname(f.path)[len(prefix) :]
            if f.ext == ".gif":
                reason = PREVIEW_GIF
            else:
                iw, ih = int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))
                strip = any(
                    ih == sh and iw % sw == 0 and iw // sw in frame_counts for sw, sh in sizes
                )
                named = bool(set(words(stem)) & anim_words) and any(ih == sh for _sw, sh in sizes)
                in_previews = bool(set(words(folders)) & PREVIEW_WORDS)
                # a sheet of all its frames on their grid (T17.33: ``male_hero.png`` beside
                # ``individual_sheets/``)
                whole = any(
                    iw % sw == 0 and ih % sh == 0 and (iw // sw) * (ih // sh) >= WHOLE_SHEET
                    and ih > sh
                    for sw, sh in sizes
                )  # fmt: skip
                strip = strip or whole
                if not (strip or named or in_previews):
                    continue
                reason = SAME_FRAMES if not in_previews or strip or named else PREVIEW_GIF
            iw, ih = int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))
            facets = {
                "usage": "sprite",
                "role": "NONE",
                "frame": [iw, ih],
                "origin": [iw // 2, max(0, ih - 1)],
                "tags": sorted({UNUSED + reason, SAME_AS + first}),
            }
            result.assets.append(AssetFragment(f.path, facets, CONFIDENCE, "full"))

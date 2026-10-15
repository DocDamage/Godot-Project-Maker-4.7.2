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
            lead.append((_WORDS.sub("", (m2.group("base") or "").casefold().rstrip("0123456789")), int(m2.group("num")), f))
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
        sizes = {(int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))) for f in files}
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
    sets = [
        set(words(posixpath.basename(a.label))) | set(words(a.stem)) for a in members
    ]
    common = set.intersection(*sets)
    return {w for w in common if w not in naming.ACTIONS}


def find_characters(inv: Inventory, claimed: set[str]) -> list[Character]:
    groups: dict[str, list[ActionFolder]] = {}
    for action in find_action_folders(inv, claimed):
        owner = _owner(action)
        if not owner:
            continue
        groups.setdefault(owner, []).append(action)
    out: list[Character] = []
    for owner in sorted(groups):
        members = groups[owner]
        named = [a for a in members if _action_of(posixpath.basename(a.label)) or _action_of(a.stem)]
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
        if not actions:
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
    by_folder: dict[str, list[InventoryFile]] = {}
    for f in inv.files:
        if f.kind == "image":
            by_folder.setdefault(posixpath.dirname(f.path), []).append(f)
    out: list[Character] = []
    for folder in sorted(by_folder):
        files = by_folder[folder]
        if not folder or len(files) < 3 or any(not _is_still(f) or f.path in claimed for f in files):
            continue
        sizes = {(int((f.image or {}).get("w", 0)), int((f.image or {}).get("h", 0))) for f in files}
        if len(sizes) != 1 or 0 in next(iter(sizes)):
            continue
        split: list[tuple[list[str], int, InventoryFile]] = []
        for f in files:
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            m = _FILE_FRAME.match(stem)
            split.append((words(m.group("base") if m else stem), int(m.group("num")) if m else 0, f))
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
        return 1.0 if find_characters(inv, set()) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        work = (ctx.work_dir or paths.cache_dir()) / WORK_FOLDER
        for character in find_characters(inv, ctx.claimed):
            ctx.check_cancel()
            self._character(root, inv, character, work, result, issues)
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
                write_strip(root, action.frames, character.size, dest)
            except (OSError, ValueError) as exc:
                issues.add("ADAPT-001", adapter=self.name, file=action.frames[0].path, reason=str(exc))
                continue
            project_path = f"{STRIP_DIR}/{file_name}"
            result.generated[project_path] = str(dest)
            cols, _rows = sequences.layout(len(action.frames), w)
            verb = anim.split("_")[0]
            animations[anim] = {
                "frames": [[i % cols, i // cols] for i in range(len(action.frames))],
                "fps": naming.fps(verb),
                "loop": naming.is_looping(verb),
                "source": project_path,
            }
            counts[anim] = len(action.frames)
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
            "tags": [TAG, f"{FOLDER_TAG}{character.folder}"],
        }
        result.assets.append(AssetFragment(used[0].path, facets, CONFIDENCE, "full"))
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

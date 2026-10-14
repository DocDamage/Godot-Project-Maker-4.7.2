"""Characters in a folder of facings (T17.30).

Two layouts of real packs draw a character once a facing and name the facings, not the frames:

* **SakPix** (about 280 characters): a folder a character with ``rotations/east.png``,
  ``north-east.png`` and the rest, eight still pictures; animations, where a character has them,
  in folders beside ``rotations``.
* ***Lords Of Pain***: a folder a character, a folder an action in it named after the character
  (``warrior/warrior_default_walk``), a folder a facing in that (``NE``, ``NEE`` is 22.5 degrees,
  ``S`` 270), a file a frame (``warrior_default_walk_NE_45.0_3.png``). Sixteen facings. Its props
  are drawn the same way, a folder a prop (``prop/barrel/SE/barrel_SE_315.0_0.png``).

An **action folder** is a folder whose pictures or whose sub-folders are named by a direction
(``naming.direction_angle``) and cover four, eight or sixteen facings, each with as many frames,
all of one size. Its parent is the character when the folder is named by an action (``walk``,
``rotations`` is the still the character stands in) or after the parent (*Lords Of Pain*'s
``fighter_special_select``); otherwise the folder is a thing of its own in its facings (a prop).

Every character is one sprite: an animation a facing for every action (``walk_up_right``), each
a strip in the work folder of its frames cut to what the character paints (the pictures of
*Lords Of Pain* are 256 x 256 around a figure of 40). Of sixteen facings the eight the game
turns by are used and the note ADAPT-008 says so (the asset is tagged ``facings:16``); four are
used as they are. Of the variants of an action (*Lords Of Pain*'s ``default_walk`` and
``armed_walk``) the one of the variant that attacks is taken. A character with no walk (SakPix's
``rotations`` only) walks in its still pictures (tag ``walk_from_still``), so that it can be
the player of a game.
"""

from __future__ import annotations

import hashlib
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from rpggen import paths
from rpggen.core import classifier
from rpggen.core.adapters import iso_sheets, naming, sequences
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

NAME = "facings"
STILL_WORDS = frozenset({"rotation", "rotations", "rotate", "turnaround", "still", "stills"})
FACING_COUNTS = {4: 90.0, 8: 45.0, 16: 22.5}
CONFIDENCE = 0.9
PAINTED_ALPHA = 64  # a fainter pixel is the soft shadow round a rendered figure
MARGIN = 2
FACINGS_TAG = "facings:"
WALK_FROM_STILL = "walk_from_still"
PREVIEW = "preview_gif"  # pack_forms.PREVIEW_GIF
PREVIEW_WORDS = frozenset({"showcase", "preview", "demo", "turnaround"})
RENDER_VERSION = 2


@dataclass
class ActionFolder:
    folder: str
    frames: dict[float, list[InventoryFile]]  # angle -> frames in order

    @property
    def count(self) -> int:
        return len(self.frames)


@dataclass
class FacingCharacter:
    folder: str
    actions: dict[str, ActionFolder] = field(default_factory=dict)  # folder name -> action

    @property
    def files(self) -> list[InventoryFile]:
        return [f for a in self.actions.values() for fr in a.frames.values() for f in fr]


def _is_still(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext in (".png", ".bmp", ".webp")


def _size(f: InventoryFile) -> tuple[int, int]:
    image = f.image or {}
    return int(image.get("w", 0)), int(image.get("h", 0))


def _order(files: list[InventoryFile]) -> list[InventoryFile]:
    def key(f: InventoryFile) -> tuple[int, str]:
        split = sequences.split_number(posixpath.splitext(posixpath.basename(f.path))[0])
        return (split[1] if split else 0, f.path)

    return sorted(files, key=key)


def _valid(frames: dict[float, list[InventoryFile]]) -> bool:
    step = FACING_COUNTS.get(len(frames))
    if step is None or set(frames) != {k * step for k in range(len(frames))}:
        return False
    counts = {len(fr) for fr in frames.values()}
    sizes = {_size(f) for fr in frames.values() for f in fr}
    return len(counts) == 1 and len(sizes) == 1 and min(counts) > 0


def action_folders(inv: Inventory, claimed: set[str]) -> list[ActionFolder]:
    """The folders whose pictures or sub-folders are named by the facings of one thing."""
    by_folder: dict[str, list[InventoryFile]] = {}
    for f in inv.files:
        if _is_still(f) and f.path not in claimed:
            by_folder.setdefault(posixpath.dirname(f.path), []).append(f)
    found: list[ActionFolder] = []
    # pictures named by a facing: ``rotations/east.png``
    for folder, files in sorted(by_folder.items()):
        frames: dict[float, list[InventoryFile]] = {}
        for f in files:
            angle = naming.direction_angle(posixpath.splitext(posixpath.basename(f.path))[0])
            if angle is not None:
                frames.setdefault(angle, []).append(f)
        if _valid(frames) and sum(len(v) for v in frames.values()) == len(frames):
            found.append(ActionFolder(folder, frames))
    # sub-folders named by a facing: ``warrior_default_walk/NE/*.png``
    parents: dict[str, dict[float, list[InventoryFile]]] = {}
    for folder, files in by_folder.items():
        angle = naming.direction_angle(posixpath.basename(folder))
        if angle is not None and "/" in folder:
            parents.setdefault(posixpath.dirname(folder), {})[angle] = _order(files)
    for parent, frames in sorted(parents.items()):
        if _valid(frames):
            found.append(ActionFolder(parent, frames))
    return found


def _words(name: str) -> list[str]:
    return [w.casefold() for w in classifier.name_words(name)]


def is_action_name(name: str, parent: str) -> bool:
    words = set(_words(name))
    if words & STILL_WORDS:
        return True
    if {naming.SYNONYMS.get(w, w) for w in words} & naming.CANONICAL_ACTIONS:
        return True
    lead = _words(parent)
    return bool(lead) and _words(name)[: len(lead)] == lead and len(_words(name)) > len(lead)


def find_characters(inv: Inventory, claimed: set[str]) -> list[FacingCharacter]:
    """The characters (and things) of a pack drawn in named facings (see the module)."""
    out: dict[str, FacingCharacter] = {}
    for action in action_folders(inv, claimed):
        name = posixpath.basename(action.folder)
        parent = posixpath.dirname(action.folder)
        if parent and is_action_name(name, posixpath.basename(parent)):
            owner = parent
        else:
            owner = action.folder
        out.setdefault(owner, FacingCharacter(owner)).actions[action.folder] = action
    return [out[k] for k in sorted(out)]


def _canonical(folder: str, owner: str) -> tuple[str, frozenset[str]]:
    """``(action, variant words)`` of an action folder: ``walk`` and ``{armed}`` for
    ``warrior/warrior_armed_walk``; ``idle`` for a folder of stills or the thing's own."""
    if folder == owner:
        return "idle", frozenset()
    words = _words(posixpath.basename(folder))
    lead = _words(posixpath.basename(owner))
    if words[: len(lead)] == lead:
        words = words[len(lead) :]
    if set(words) & STILL_WORDS:
        return "idle", frozenset()
    mapped = [naming.SYNONYMS.get(w, w) for w in words]
    action = next((w for w in mapped if w in naming.CANONICAL_ACTIONS), "")
    rest = frozenset(w for w, m in zip(words, mapped, strict=True) if m != action)
    return (action or "_".join(words) or "idle"), rest


def plan(character: FacingCharacter) -> dict[str, ActionFolder]:
    """The action folder each animation takes its frames from, by action name."""
    named = {f: _canonical(f, character.folder) for f in character.actions}
    attack_variants = [v for f, (a, v) in sorted(named.items()) if a == "attack"]
    kit = attack_variants[0] if attack_variants else None
    chosen: dict[str, tuple[tuple[int, int, str], str]] = {}
    for folder, (action, variant) in sorted(named.items()):
        rank = (
            0 if kit is not None and variant == kit else 1,
            0 if not variant or variant <= {"default", "base"} else 1,
            folder,
        )
        if action not in chosen or rank < chosen[action][0]:
            chosen[action] = (rank, folder)
    return {action: character.actions[folder] for action, (_rank, folder) in chosen.items()}


PLAYER_WORDS = frozenset({"playable", "player", "players", "hero", "heroes", "protagonist"})
NPC_WORDS = frozenset({"npc", "npcs", "villager", "villagers", "townfolk", "citizens"})
NOT_WORDS = frozenset({"non", "none", "not", "un"})  # *Lords Of Pain*'s "none-playable"
ENEMY_WORDS = frozenset({"enemy", "enemies", "monster", "monsters", "mob", "mobs"})
BOSS_WORDS = frozenset({"boss", "bosses"})


def role_of(character: FacingCharacter) -> str:
    """The role the folders of a character say (``playable character/warrior``, ``enemy/``,
    ``boss/``, ``none-playable character/``), or "" for the classifier to decide."""
    words = set(_words(character.folder.replace("/", " ")))
    if words & BOSS_WORDS:
        return "BOSS"
    if words & ENEMY_WORDS:
        return "ENEMY"
    if words & NPC_WORDS or (words & PLAYER_WORDS and words & NOT_WORDS):
        return "NPC"
    if words & PLAYER_WORDS:
        return "PLAYER"
    return ""


def _strip_name(files: list[InventoryFile], box: tuple[int, int, int, int]) -> str:
    text = "\n".join([f"facings/{RENDER_VERSION}/{box}", *(f.sha256 for f in files)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest() + ".png"


class FacingsAdapter:
    name = NAME
    priority = 46  # before the isometric reader and the farm's: a facing is no turn of a tile

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if action_folders(inv, set()) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        work = (ctx.work_dir or paths.cache_dir()) / sequences.WORK_FOLDER
        characters = find_characters(inv, ctx.claimed)
        from rpggen.core.adapters import isometric

        iso = bool(characters) and isometric.pack_words(inv, root).isometric

        def one(character: FacingCharacter) -> tuple[AssetFragment | None, dict[str, str], str]:
            ctx.check_cancel()
            try:
                return self._character(root, character, work, iso)
            except (OSError, ValueError) as exc:
                return None, {}, str(exc)

        for character, (fragment, generated, error) in zip(
            characters, iso_sheets.in_parallel(one, characters, ctx), strict=True
        ):
            if fragment is None:
                if error:
                    issues.add("ADAPT-001", adapter=self.name, file=character.folder, reason=error)
                continue
            result.assets.append(fragment)
            result.generated.update(generated)
            result.consumed.extend(f.path for f in character.files if f.path != fragment.path)
            # SakPix's ``9._Librarian_showcase.gif`` beside the folder ``9._Librarian``: the
            # character shown turning round, a preview of what was read
            stem = posixpath.basename(character.folder).casefold()
            parent = posixpath.dirname(character.folder)
            for f in inv.files:
                name = posixpath.splitext(posixpath.basename(f.path))[0].casefold()
                if (
                    f.kind == "image"
                    and f.path not in ctx.claimed
                    and posixpath.dirname(f.path) == parent
                    and name.startswith(stem)
                    and set(_words(name[len(stem) :])) & PREVIEW_WORDS
                ):
                    result.assets.append(iso_sheets.aside(f, PREVIEW))
            count = max(a.count for a in character.actions.values())
            if count > 8:
                issues.add("ADAPT-008", character=character.folder, count=count, file=fragment.path)
        result.issues = list(issues)
        return result

    def _character(
        self, root: Path, character: FacingCharacter, work: Path, iso: bool = False
    ) -> tuple[AssetFragment | None, dict[str, str], str]:
        chosen = plan(character)
        if not chosen:
            return None, {}, ""
        used: dict[str, dict[str, list[InventoryFile]]] = {}  # action -> direction -> frames
        for action, folder in chosen.items():
            step = 360.0 / folder.count
            for angle, frames in folder.frames.items():
                if folder.count > 8 and angle % 45.0:
                    continue  # of sixteen facings the eight the game turns by
                if folder.count == 4 and angle % 90.0:
                    continue
                direction = naming.ANGLE_DIRECTIONS.get(angle)
                if direction is not None and step:
                    used.setdefault(action, {})[direction] = frames
        pictures: dict[str, np.ndarray] = {}
        box: tuple[int, int, int, int] | None = None
        for frames in (fr for dirs in used.values() for fr in dirs.values()):
            for f in frames:
                if f.path in pictures:
                    continue
                with Image.open(root / f.path) as im:
                    a = np.asarray(im.convert("RGBA"), dtype=np.uint8)
                # the soft shadow round a rendered figure goes: the game draws its own, and
                # the feet are where the figure ends
                a = a.copy()
                a[a[..., 3] < PAINTED_ALPHA] = 0
                pictures[f.path] = a
                ys, xs = np.nonzero(a[..., 3] >= PAINTED_ALPHA)
                if xs.size:
                    found = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
                    box = found if box is None else (
                        min(box[0], found[0]), min(box[1], found[1]),
                        max(box[2], found[2]), max(box[3], found[3]),
                    )  # fmt: skip
        if box is None:
            return None, {}, ""
        h, w = next(iter(pictures.values())).shape[:2]
        box = (
            max(0, box[0] - MARGIN),
            max(0, box[1] - MARGIN),
            min(w, box[2] + MARGIN),
            box[3],  # the feet are the frame's bottom: no margin under them
        )
        fw, fh = box[2] - box[0], box[3] - box[1]
        animations: dict[str, Any] = {}
        generated: dict[str, str] = {}
        for action in sorted(used):
            for direction in sorted(used[action]):
                frames = used[action][direction]
                cols, rows = sequences.layout(len(frames), fw)
                name = _strip_name(frames, box)
                dest = work / name
                if not dest.exists():
                    strip = np.zeros((rows * fh, cols * fw, 4), dtype=np.uint8)
                    for i, f in enumerate(frames):
                        part = pictures[f.path][box[1] : box[3], box[0] : box[2]]
                        y, x = (i // cols) * fh, (i % cols) * fw
                        strip[y : y + fh, x : x + fw] = part
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(strip, "RGBA").save(dest, format="PNG", optimize=False)
                project = f"{sequences.FRAME_STRIP_DIR}/{name}"
                generated[project] = str(dest)
                known = action in naming.CANONICAL_ACTIONS
                animations[f"{action}_{direction}"] = {
                    "frames": [[i % cols, i // cols] for i in range(len(frames))],
                    "fps": naming.fps(action),
                    "loop": naming.is_looping(action) if known else len(frames) == 1,
                    "source": project,
                }
        tags: list[str] = []
        thing = list(character.actions) == [character.folder]  # a prop in its facings
        if "walk" not in used and "idle" in used and not thing:
            for key in [k for k in animations if k.startswith("idle_")]:
                animations["walk_" + key[len("idle_") :]] = dict(animations[key])
            tags.append(WALK_FROM_STILL)
        count = max(a.count for a in character.actions.values())
        if count != 8:
            tags.append(f"{FACINGS_TAG}{count}")
        directions = {d for dirs in used.values() for d in dirs}
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [fw, fh], "margin": [0, 0], "separation": [0, 0]},
            "frame": [fw, fh],
            "origin": [fw // 2, fh - 1],
            "animations": {k: animations[k] for k in sorted(animations)},
            "directions": 8 if len(directions) >= 8 else 4,
        }
        if tags:
            facets["tags"] = sorted(tags)
        # how wide it stands: the lowest quarter of its standing picture (the frame is as wide as
        # its widest swing, and the body is the feet: two of them could not pass each other)
        first_action = "idle" if "idle" in used else sorted(used)[0]
        first_dir = "down" if "down" in used[first_action] else sorted(used[first_action])[0]
        first = used[first_action][first_dir][0]
        stand = first
        figure = pictures[stand.path][box[1] : box[3], box[0] : box[2], 3] > 0
        figure_rows = np.nonzero(figure.any(axis=1))[0]
        if figure_rows.size:
            low = figure[max(0, int(figure_rows[-1]) - fh // 4 + 1) : int(figure_rows[-1]) + 1]
            figure_cols = np.nonzero(low.any(axis=0))[0]
            if figure_cols.size:
                facets["feet"] = min(int(figure_cols[-1] - figure_cols[0] + 1), int(fw * 0.6))
        if thing and iso:
            # a prop of an isometric pack stands on one diamond, on its own foot (T17.14)
            facets.update({"projection": "isometric", "canvas": [fw, fh], "stands_on": [1, 1]})
        role = role_of(character) or ("DECORATION" if thing else "")
        if role:
            facets["role"] = role
        return AssetFragment(first.path, facets, CONFIDENCE, "full"), generated, ""

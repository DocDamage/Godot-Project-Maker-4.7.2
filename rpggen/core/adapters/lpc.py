"""Liberated Pixel Cup characters (T2.12; the whole layout and the collection's files, M16).

Two shapes of the same art are read. The **universal sheet**: every animation of one character
in one picture 832 px wide, 64 px frames, four rows per animation (up, left, down, right); the
classic one has 21 rows, the generator's goes on to 54. And the **collection's files**
(the Universal LPC Spritesheet Character Generator's ``spritesheets`` folder): one picture per
animation, ``body/bodies/male/walk.png``, or one folder per animation with a picture per colour,
``torso/clothes/shirt/male/walk/red.png``. The files of one thing are one sprite whose
animations each come from their own file.

A character of the collection is a body with layers over it (hair, clothes, a weapon). The body
is a character; a layer is catalogued with its animations and left unused, with the reason:
rpggen does not draw one picture over another yet.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import frames, image_facts
from rpggen.core.inventory import Inventory, InventoryFile

LPC_WIDTH = 832
LPC_MIN_HEIGHT = 1344
FRAME = 64
LPC_DIRECTIONS = ["up", "left", "down", "right"]  # row order inside every 4-row block
STANDARD_ORIGIN = (32, 60)
BASELINE_TOLERANCE = 4
UNUSED_LAYER = "lpc_layer"


@dataclass(frozen=True)
class Action:
    """One animation of the LPC layout."""

    lpc: str  # the name the collection gives it (a file or folder name)
    row: int  # its first row on the universal sheet
    rows: int  # 4: one per direction; 1: one row for all
    frames: int  # the cells of a row that are drawn
    name: str  # the name of the animation in a project (``<name>_<direction>``)
    fps: float
    loop: bool
    cycle: tuple[int, ...] | None = None  # the cells in playing order (None: left to right)


# The universal sheet from top to bottom. The first six are the classic 21 rows.
ACTIONS: tuple[Action, ...] = (
    Action("spellcast", 0, 4, 7, "cast", 10.0, False),
    Action("thrust", 4, 4, 8, "thrust", 12.0, False),
    Action("walk", 8, 4, 9, "walk", 10.0, True, (1, 2, 3, 4, 5, 6, 7, 8)),
    Action("slash", 12, 4, 6, "attack", 12.0, False),
    Action("shoot", 16, 4, 13, "shoot", 12.0, False),
    Action("hurt", 20, 1, 6, "hurt", 10.0, False),
    Action("climb", 21, 1, 6, "climb", 8.0, True),
    Action("idle", 22, 4, 2, "idle", 3.0, True, (0, 0, 1)),
    Action("jump", 26, 4, 5, "jump", 10.0, False, (0, 1, 2, 3, 4, 1)),
    Action("sit", 30, 4, 3, "sit", 4.0, False),
    Action("emote", 34, 4, 3, "emote", 4.0, False),
    Action("run", 38, 4, 8, "run", 12.0, True),
    Action("combat_idle", 42, 4, 2, "combat_idle", 3.0, True, (0, 0, 1)),
    Action("backslash", 46, 4, 13, "backslash", 12.0, False),
    Action("halfslash", 50, 4, 6, "halfslash", 12.0, False),
)
BY_NAME = {a.lpc: a for a in ACTIONS}
CLASSIC = ("walk", "slash", "hurt")  # what every LPC sheet has, drawn or not (T2.12)
# The parts of a character in the collection: its first folder. ``body`` is the character.
BODY_PARTS = frozenset({"body", "bodies"})
LAYER_PARTS = frozenset(
    {"hair", "head", "heads", "eyes", "facial", "beards", "hat", "hats", "neck", "torso",
     "arms", "shoulders", "legs", "feet", "dress", "cape", "capes", "backpack", "quiver",
     "weapon", "weapons", "shield", "shields", "tools", "shadow", "wings", "tail", "ears"}
)  # fmt: skip


def _is_lpc_sheet(f: InventoryFile) -> bool:
    return (
        f.kind == "image"
        and f.image is not None
        and f.image["w"] == LPC_WIDTH
        and f.image["h"] % FRAME == 0
        and f.image["h"] >= LPC_MIN_HEIGHT
    )


def _spec(action: Action, row: int, source: str | None = None) -> dict[str, Any]:
    cells = action.cycle or tuple(range(action.frames))
    spec: dict[str, Any] = {
        "frames": [[c, row] for c in cells],
        "fps": action.fps,
        "loop": action.loop,
    }
    if action.lpc == "slash":
        spec["active_frames"] = [3, 4]
    if source is not None:
        spec["source"] = source
    return spec


def _animations(action: Action, first_row: int, source: str | None = None) -> dict[str, Any]:
    """The animations one action gives: one per direction, or ``hurt`` and ``death`` and
    ``climb_up`` for the three that have a single row."""
    if action.rows == 1:
        spec = _spec(action, first_row, source)
        if action.lpc == "hurt":
            return {"hurt": spec, "death": {**spec, "fps": 8.0}}
        return {f"{action.name}_up": spec}
    return {
        f"{action.name}_{direction}": _spec(action, first_row + i, source)
        for i, direction in enumerate(LPC_DIRECTIONS)
    }


def action_of(f: InventoryFile) -> tuple[Action, str, str] | None:
    """``(action, the folder of the thing, its name)`` for one animation of the collection:
    a picture named by its animation (``.../male/walk.png``: the thing is the folder), or in a
    folder named by it (``.../male/walk/red.png``: the thing is ``red`` of the folder above).
    Its size must be that animation's: ``frames`` cells of 64 px, four rows or one."""
    if f.kind != "image" or f.image is None or f.ext != ".png":
        return None
    folder, name = posixpath.split(f.path)
    stem = posixpath.splitext(name)[0]
    found = BY_NAME.get(stem.casefold())
    key = (folder, "")
    if found is None:
        found = BY_NAME.get(posixpath.basename(folder).casefold())
        key = (posixpath.dirname(folder), stem)
    if found is None:
        return None
    if (f.image["w"], f.image["h"]) != (found.frames * FRAME, found.rows * FRAME):
        return None  # an oversize weapon sheet (192 px frames), or another picture of that name
    return found, key[0], key[1]


def part_of(path: str) -> str | None:
    """The part of a character a file of the collection belongs to (``hair``, ``torso``),
    ``body`` for the character itself; None when no folder says."""
    for folder in posixpath.dirname(path).casefold().split("/"):
        if folder in BODY_PARTS:
            return "body"
        if folder in LAYER_PARTS:
            return folder
    return None


def looks_like_collection(names: list[str]) -> bool:
    """True for a listing that has the collection's files: three animations or more as file
    or folder names (read by ``pack_sniff``; no size is looked at)."""
    seen: set[str] = set()
    for name in names:
        parts = name.replace("\\", "/").casefold().split("/")
        if not parts[-1].endswith(".png"):
            continue
        stem = parts[-1][:-4]
        for word in (stem, parts[-2] if len(parts) > 1 else ""):
            if word in BY_NAME:
                seen.add(word)
        if len(seen) >= 3:
            return True
    return False


class LpcAdapter:
    name = "lpc"
    priority = 50

    def match(self, inv: Inventory, root: Path) -> float:
        if any(_is_lpc_sheet(f) for f in inv.files):
            return 1.0
        return 1.0 if any(action_of(f) for f in inv.files) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        for f in inv.files:
            if not _is_lpc_sheet(f) or f.path in ctx.claimed:
                continue
            mask = image_facts.occupancy(image_facts.load_rgba(root / f.path))
            result.assets.append(self._fragment(f, mask))
        groups: dict[tuple[str, str], list[tuple[Action, InventoryFile]]] = {}
        for f in inv.files:
            if f.path in ctx.claimed or _is_lpc_sheet(f):
                continue
            found = action_of(f)
            if found is not None:
                groups.setdefault((found[1], found[2]), []).append((found[0], f))
        for key in sorted(groups):
            self._collection(ctx.pack_id, groups[key], result)
        return result

    @staticmethod
    def _fragment(f: InventoryFile, mask) -> AssetFragment:  # noqa: ANN001
        """One universal sheet: the classic walk, attack and hurt always, every other
        animation whose rows are on the sheet and have something drawn in them."""
        rows = mask.shape[0] // FRAME
        animations: dict[str, Any] = {}
        drawn: set[str] = set()
        for action in ACTIONS:
            if action.row + action.rows > rows:
                continue
            band = mask[action.row * FRAME : (action.row + action.rows) * FRAME]
            if action.lpc in CLASSIC or band.any():
                drawn.add(action.lpc)
                animations.update(_animations(action, action.row))
        walk = BY_NAME["walk"]
        if "idle" not in drawn:  # the classic sheet stands on the first cell of its walk
            for i, direction in enumerate(LPC_DIRECTIONS):
                animations[f"idle_{direction}"] = {
                    "frames": [[0, walk.row + i]],
                    "fps": 1.0,
                    "loop": True,
                }
        walk_rects = [
            (c * FRAME, (walk.row + i) * FRAME, FRAME, FRAME)
            for i in range(4)
            for c in range(walk.frames)
        ]
        baseline = frames.baseline_y(mask, walk_rects)
        origin_y = (
            baseline
            if abs(baseline - STANDARD_ORIGIN[1]) > BASELINE_TOLERANCE
            else STANDARD_ORIGIN[1]
        )
        facets = {
            "usage": "sprite",
            "grid": {"cell": [FRAME, FRAME], "margin": [0, 0], "separation": [0, 0]},
            "frame": [FRAME, FRAME],
            "origin": [STANDARD_ORIGIN[0], origin_y],
            "directions": 4,
            "animations": {k: animations[k] for k in sorted(animations)},
        }
        return AssetFragment(f.path, facets, 0.9, "full")

    @staticmethod
    def _collection(
        pack_id: str, members: list[tuple[Action, InventoryFile]], result: AdapterResult
    ) -> None:
        """The pictures of one thing of the collection, one per animation: one sprite. Its
        asset is the walk (else the first animation of the layout), and every animation names
        the file its cells are in."""
        order = {a.lpc: n for n, a in enumerate(ACTIONS)}
        members = sorted(members, key=lambda m: (order[m[0].lpc], m[1].path))
        by_action: dict[str, InventoryFile] = {}
        for action, f in members:
            by_action.setdefault(action.lpc, f)
        primary = by_action.get("walk") or members[0][1]
        animations: dict[str, Any] = {}
        for lpc, f in by_action.items():
            animations.update(_animations(BY_NAME[lpc], 0, f"assets/packs/{pack_id}/{f.path}"))
        if "idle" not in by_action and "walk" in by_action:
            source = f"assets/packs/{pack_id}/{by_action['walk'].path}"
            for i, direction in enumerate(LPC_DIRECTIONS):
                animations[f"idle_{direction}"] = {
                    "frames": [[0, i]],
                    "fps": 1.0,
                    "loop": True,
                    "source": source,
                }
        facets: dict[str, Any] = {
            "usage": "sprite",
            "grid": {"cell": [FRAME, FRAME], "margin": [0, 0], "separation": [0, 0]},
            "frame": [FRAME, FRAME],
            "origin": list(STANDARD_ORIGIN),
            "directions": 4,
            "animations": {k: animations[k] for k in sorted(animations)},
        }
        part = part_of(primary.path)
        if part is not None and part != "body":
            facets["role"] = "NONE"
            facets["tags"] = [
                "lpc_layer",
                f"lpc_part:{part}",
                f"unused_because:{UNUSED_LAYER}",
            ]
        else:
            facets["tags"] = ["lpc_body"]
        result.assets.append(AssetFragment(primary.path, facets, 0.9, "full"))
        result.consumed.extend(f.path for _a, f in members if f.path != primary.path)

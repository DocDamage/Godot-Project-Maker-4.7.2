"""Pure helpers for editing animation specs (the animation editor holds no logic of its own)."""

from __future__ import annotations

import copy
import re
from typing import Any

Anim = dict[str, Any]
DIRECTIONS = ("down", "left", "right", "up")
ACTIONS = ("idle", "walk", "attack", "hurt")
STANDARD_DIRECTIONAL = tuple(f"{a}_{d}" for a in ACTIONS for d in DIRECTIONS)
STANDARD_NAMES = (*STANDARD_DIRECTIONAL, "death")
MIRROR = {"left": "right", "right": "left"}
DEFAULT_FPS = 8.0


def new_animation(fps: float = DEFAULT_FPS, loop: bool = True) -> Anim:
    return {"frames": [], "fps": fps, "loop": loop}


def missing_standard_names(animations: dict[str, Anim]) -> list[str]:
    """Standard names that do not exist yet, in standard order."""
    return [n for n in STANDARD_NAMES if n not in animations]


# The names offered for an animation that has none yet (T16.21): what the runtime of some
# kind of game plays by name, each in the four directions.
OFFERED_ACTIONS = (
    "idle", "walk", "attack", "hurt", "death", "jump", "fall", "climb", "dash", "shoot", "cast",
)  # fmt: skip
_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def offered_names(animations: dict[str, Anim]) -> list[str]:
    """Names to offer for one of ``animations``: every offered action in every direction that
    is not taken, the actions in their order."""
    return [
        f"{action}_{direction}"
        for action in OFFERED_ACTIONS
        for direction in DIRECTIONS
        if f"{action}_{direction}" not in animations
    ]


def clean_name(text: str) -> str:
    """What a typed name becomes: lower case, with ``_`` for spaces and hyphens, and ``_down``
    added to a lone action word, as a strip named ``walk`` is read. "" when nothing is left
    that can be a name."""
    name = re.sub(r"[\s\-]+", "_", text.strip().lower()).strip("_")
    if not _NAME.fullmatch(name):
        return ""
    return f"{name}_down" if name in OFFERED_ACTIONS else name


def renamed(animations: dict[str, Anim], old: str, new: str) -> dict[str, Anim]:
    """``animations`` with ``old`` called ``new``, in the place it had. Unchanged when ``old``
    is not there, ``new`` is taken or the two are the same."""
    if old not in animations or new in animations or not new:
        return animations
    return {(new if name == old else name): spec for name, spec in animations.items()}


def split_name(name: str) -> tuple[str, str | None]:
    """``walk_left`` -> (``walk``, ``left``); ``death`` -> (``death``, None)."""
    action, _, direction = name.rpartition("_")
    if action and direction in DIRECTIONS:
        return action, direction
    return name, None


def groups(names: list[str]) -> list[tuple[str, list[str]]]:
    """Animation names grouped by action, directions in down/left/right/up order."""
    by_action: dict[str, list[str]] = {}
    for name in names:
        by_action.setdefault(split_name(name)[0], []).append(name)

    def order(name: str) -> int:
        direction = split_name(name)[1]
        return DIRECTIONS.index(direction) if direction else -1

    def action_key(action: str) -> tuple[int, str]:
        return (ACTIONS.index(action) if action in ACTIONS else len(ACTIONS), action)

    return [(a, sorted(by_action[a], key=order)) for a in sorted(by_action, key=action_key)]


def mirror_name(name: str) -> str | None:
    """The opposite-side name (``walk_left`` <-> ``walk_right``), None for up/down/others."""
    action, direction = split_name(name)
    return f"{action}_{MIRROR[direction]}" if direction in MIRROR else None


def mirrored(source: Anim) -> Anim:
    """A copy of ``source`` shown flipped horizontally (flip_h toggled)."""
    out = copy.deepcopy(source)
    out["flip_h"] = not source.get("flip_h", False)
    return out


def reversed_frames(anim: Anim) -> Anim:
    out = copy.deepcopy(anim)
    for key in ("frames", "rects", "offsets", "durations"):
        if key in out:
            out[key] = list(reversed(out[key]))
    return out


def ping_pong(anim: Anim) -> Anim:
    """Frames forwards then backwards without repeating the end frames: a b c -> a b c b."""
    out = copy.deepcopy(anim)
    for key in ("frames", "rects", "offsets", "durations"):
        items = out.get(key)
        if items and len(items) > 2:
            out[key] = items + list(reversed(items[1:-1]))
    return out


def cleared(anim: Anim) -> Anim:
    out = copy.deepcopy(anim)
    for key in ("frames", "rects", "offsets", "durations"):
        out.pop(key, None)
    out["frames"] = []
    return out


def toggle_cell(anim: Anim, cell: tuple[int, int]) -> Anim:
    """Add the cell to the frame list (click order) or remove it when it is there.

    Hand-picked cells replace rect/offset frames, so those lists are dropped.
    """
    out = copy.deepcopy(anim)
    for key in ("rects", "offsets", "durations"):
        out.pop(key, None)
    frames = [list(f) for f in out.get("frames", [])]
    target = [cell[0], cell[1]]
    if target in frames:
        frames.remove(target)
    else:
        frames.append(target)
    out["frames"] = frames
    return out


def cell_at(grid: dict[str, list[int]], x: float, y: float) -> tuple[int, int] | None:
    """Grid cell under a pixel position, None in margins and gutters."""
    cw, ch = grid["cell"]
    mx, my = grid.get("margin", [0, 0])
    sx, sy = grid.get("separation", [0, 0])
    col, rem_x = divmod(int(x) - mx, cw + sx)
    row, rem_y = divmod(int(y) - my, ch + sy)
    if int(x) < mx or int(y) < my or rem_x >= cw or rem_y >= ch:
        return None
    return col, row


def frame_rect(
    anim: Anim, index: int, frame_size: tuple[int, int], grid: dict[str, list[int]] | None
) -> tuple[int, int, int, int]:
    """Pixel rectangle (x, y, w, h) of frame ``index`` of an animation."""
    rects = anim.get("rects")
    if rects and index < len(rects):
        x, y, w, h = rects[index]
        return x, y, w, h
    col, row = anim["frames"][index]
    if grid:
        cw, ch = grid["cell"]
        mx, my = grid.get("margin", [0, 0])
        sx, sy = grid.get("separation", [0, 0])
        if frame_size == (cw, ch):
            return mx + col * (cw + sx), my + row * (ch + sy), cw, ch
    fw, fh = frame_size
    return col * fw, row * fh, fw, fh


def frame_duration_ms(anim: Anim, index: int) -> int:
    """Milliseconds frame ``index`` is shown (``durations`` override the fps)."""
    durations = anim.get("durations")
    if durations and index < len(durations):
        return max(1, round(float(durations[index]) * 1000))
    fps = float(anim.get("fps") or DEFAULT_FPS)
    return max(1, round(1000 / max(fps, 0.1)))


def anim_overrides(effective: dict[str, Anim], edited: dict[str, Anim]) -> dict[str, Any]:
    """The ``animations`` override that turns ``effective`` into ``edited``.

    Overrides merge recursively, so a changed animation lists every key it has plus ``None`` for
    keys it lost (which deletes them); a removed animation is ``None``.
    """
    out: dict[str, Any] = {}
    for name, spec in edited.items():
        before = effective.get(name)
        if before == spec:
            continue
        item = copy.deepcopy(spec)
        for key in before or {}:
            if key not in spec:
                item[key] = None
        out[name] = item
    for name in effective:
        if name not in edited:
            out[name] = None
    return out

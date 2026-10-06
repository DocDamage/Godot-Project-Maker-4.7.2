from __future__ import annotations

import re
from dataclasses import dataclass

SYNONYMS = {
    "run": "walk",
    "move": "walk",
    "walking": "walk",
    "stand": "idle",
    "idling": "idle",
    "atk": "attack",
    "attacking": "attack",
    "hit": "hurt",
    "damage": "hurt",
    "die": "death",
    "dead": "death",
    "dying": "death",
    "s": "down",
    "south": "down",
    "front": "down",
    "n": "up",
    "north": "up",
    "back": "up",
    "e": "right",
    "east": "right",
    "w": "left",
    "west": "left",
    "side": "right",
}
DIRECTIONS = ("down", "up", "left", "right")
SIDE_TOKENS = {"side"}
NON_LOOPING_ACTIONS = {"attack", "hurt", "death"}
_SPLIT = re.compile(r"[_\-\s]+")


@dataclass(frozen=True)
class NormalizedName:
    action: str
    direction: str | None  # down/up/left/right, or None when the name carries no direction
    side: bool  # the direction was "side": a mirrored left variant should be generated
    name: str  # "<action>_<direction>" with a missing direction assumed to be down
    direction_assumed: bool


def normalize_name(raw: str) -> NormalizedName:
    """Normalize an animation tag / file stem to ``<action>_<direction>`` using SYNONYMS."""
    tokens = [t for t in _SPLIT.split(raw.strip().lower()) if t]
    side = any(t in SIDE_TOKENS for t in tokens)
    mapped = [SYNONYMS.get(t, t) for t in tokens]
    directions = [t for t in mapped if t in DIRECTIONS]
    rest = [t for t in mapped if t not in DIRECTIONS]
    action = "_".join(rest) if rest else "idle"
    direction = directions[0] if directions else None
    final_direction = direction or "down"
    return NormalizedName(action, direction, side, f"{action}_{final_direction}", direction is None)


def is_looping(action: str) -> bool:
    return action.split("_")[0] not in NON_LOOPING_ACTIONS

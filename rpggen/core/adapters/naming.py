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
    "sw": "down_left",
    "southwest": "down_left",
    "downleft": "down_left",
    "se": "down_right",
    "southeast": "down_right",
    "downright": "down_right",
    "nw": "up_left",
    "northwest": "up_left",
    "upleft": "up_left",
    "ne": "up_right",
    "northeast": "up_right",
    "upright": "up_right",
}
CARDINALS = ("down", "up", "left", "right")
DIAGONALS = ("down_left", "down_right", "up_left", "up_right")
DIRECTIONS = (*CARDINALS, *DIAGONALS)
SIDE_TOKENS = {"side"}
# The action words a file or folder name can carry (T12.50), and how they are written in a
# pattern: the longer words first, so that "walking" is not read as "walk" plus a rest.
ACTIONS = (
    "idle", "walk", "run", "attack", "hurt", "death", "die", "hit", "move",
    "jump", "fall", "cast", "shoot", "slash", "thrust", "block", "roll", "dash", "climb", "swim",
    "interact",
)  # fmt: skip
CANONICAL_ACTIONS = frozenset(SYNONYMS.get(a, a) for a in ACTIONS)
ACTION_PATTERN = "|".join(sorted(ACTIONS, key=lambda a: (-len(a), a)))
DIRECTION_PATTERN = (
    r"down[_\- ]?left|down[_\- ]?right|up[_\- ]?left|up[_\- ]?right"
    r"|down|up|left|right|front|back|side|sw|se|nw|ne|s|n|e|w"
)
NON_LOOPING_ACTIONS = {
    "attack", "hurt", "death",
    "jump", "cast", "shoot", "slash", "thrust", "roll", "dash", "interact",
}  # fmt: skip
DEFAULT_FPS = {
    "idle": 4.0, "walk": 8.0, "attack": 12.0, "hurt": 10.0, "death": 8.0,
    "jump": 10.0, "fall": 8.0, "cast": 10.0, "shoot": 12.0, "slash": 12.0, "thrust": 12.0,
    "block": 6.0, "roll": 12.0, "dash": 12.0, "climb": 8.0, "swim": 8.0, "interact": 8.0,
}  # fmt: skip
_SPLIT = re.compile(r"[_\-\s]+")


@dataclass(frozen=True)
class NormalizedName:
    action: str
    # down/up/left/right or a diagonal (down_left, ...); None when the name carries no direction
    direction: str | None
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
    vertical = next((t for t in directions if t in ("down", "up")), None)
    horizontal = next((t for t in directions if t in ("left", "right")), None)
    diagonal = next((t for t in directions if t in DIAGONALS), None)
    if diagonal:
        direction = diagonal
    elif vertical and horizontal and not side:
        direction = f"{vertical}_{horizontal}"  # "walk_down_left", "walk-left-down"
    final_direction = direction or "down"
    return NormalizedName(action, direction, side, f"{action}_{final_direction}", direction is None)


def fps(action: str) -> float:
    return DEFAULT_FPS.get(action.split("_")[0], 8.0)


def is_looping(action: str) -> bool:
    return action.split("_")[0] not in NON_LOOPING_ACTIONS

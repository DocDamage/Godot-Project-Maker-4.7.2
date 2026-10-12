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
    "idle", "walk", "run", "attack", "hurt", "death", "die", "dead", "hit", "move",
    "jump", "fall", "cast", "shoot", "slash", "thrust", "block", "roll", "dash", "climb", "swim",
    "interact", "sleep", "fly",
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
    "sleep": 2.0, "fly": 8.0,
}  # fmt: skip
_SPLIT = re.compile(r"[_\-\s]+")

# What some artists write into a file name (T16.21): the cell size, how many frames the strip
# has, a nine-slice piece, the number of directions. ``cow_01_brown_move_down_32x32_4frames``.
_FACT_SUFFIX = re.compile(
    r"[_\- ](?:(?P<w>\d{1,4})x(?P<h>\d{1,4})|(?P<frames>\d{1,3})frames?"
    r"|(?P<split>\d{1,2})split|(?P<dirs>\d{1,2})dir(?:ection)?s?)$",
    re.IGNORECASE,
)
GROWTH_WORDS = frozenset({"growth", "grow", "growing"})  # a crop's growth strip (a tag, M17)


@dataclass(frozen=True)
class NameFacts:
    """A file stem without its size suffixes, and what they said (None: not said)."""

    stem: str
    cell: tuple[int, int] | None = None
    frames: int | None = None
    split: int | None = None
    directions: int | None = None

    @property
    def any(self) -> bool:
        return (self.cell, self.frames, self.split, self.directions) != (None, None, None, None)


def name_facts(stem: str) -> NameFacts:
    """Take ``_<W>x<H>``, ``_<N>frames``, ``_<N>split`` and ``_<N>dir`` off the end of a file
    stem, in any order. A size of zero or a count of zero is not a fact and stays in the name."""
    rest = stem.strip()
    found: dict[str, object] = {}
    while True:
        m = _FACT_SUFFIX.search(rest)
        if m is None:
            break
        value: object
        if m.group("w"):
            cell = (int(m.group("w")), int(m.group("h")))
            key, value, ok = "cell", cell, cell[0] > 0 and cell[1] > 0
        else:
            key = "frames" if m.group("frames") else "split" if m.group("split") else "dirs"
            count = int(m.group(key))
            value, ok = count, count > 0
        if not ok or key in found:
            break
        found[key] = value
        rest = rest[: m.start()]
    return NameFacts(
        rest,
        found.get("cell"),  # type: ignore[arg-type]
        found.get("frames"),  # type: ignore[arg-type]
        found.get("split"),  # type: ignore[arg-type]
        found.get("dirs"),  # type: ignore[arg-type]
    )


# One thing turned (T17.12): ``roadTile_001_0`` to ``_3``, ``watercraftPack_001_0`` to ``_7``,
# ``cornDouble_N`` / ``_E`` / ``_S`` / ``_W``, ``taxi_NE``. The compass words are capitals, as
# the packs write them: a small ``n`` after an action is a character's direction. A last ``U``
# or ``D`` (``taxi_NEU``) is the same heading on a slope going up or down.
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_TURN = re.compile(
    r"^(?P<base>.*[^_\- ])[_\- ]"
    r"(?:(?P<number>[0-7])|(?P<word>NE|NW|SE|SW|N|E|S|W)(?P<slope>[UD])?)$"
)
TURN_SETS = (  # the turns a set must have, all of them, to be one thing turned
    frozenset(range(4)),
    frozenset(range(8)),
)
COMPASS_SETS = (frozenset({"N", "E", "S", "W"}), frozenset(COMPASS))
# Sides in a name (T17.12): ``beachCornerES``, ``roadNS``, ``waterW``. Capitals glued to the
# name, each side once; ``News`` and ``Blue`` end in small letters and are words.
_JOINS = re.compile(r"^(?P<base>.*[a-z0-9])(?P<sides>[NESW]{1,4})$")
SIDES = ("n", "e", "s", "w")


@dataclass(frozen=True)
class Turn:
    """What the end of a file stem says about a turn: ``roadTile_001_2``, ``taxi_NEU``."""

    base: str  # the stem without the turn
    word: str  # the compass word (``NE``), or "" for a number
    number: int  # the number, or the word's place going round clockwise from N (of eight)
    slope: str = ""  # "up" or "down" for a heading on a slope


def split_turn(stem: str) -> Turn | None:
    """The turn a file stem ends in, or None. Whether the file is one of a set of turns the
    stems beside it say (``turns_of``): ``item_3`` alone ends in a number too."""
    m = _TURN.match(stem.strip())
    if m is None:
        return None
    if m.group("number") is not None:
        return Turn(m.group("base"), "", int(m.group("number")))
    slope = {"U": "up", "D": "down"}.get(m.group("slope") or "", "")
    return Turn(m.group("base"), m.group("word"), COMPASS.index(m.group("word")), slope)


def turns_of(turns: list[Turn]) -> int:
    """How many turns a set of stems with one base is: 4 or 8 when they are exactly the
    numbers 0 to 3 or 0 to 7, or the four or the eight compass words (the headings on a slope
    beside them do not count); else 0, and the stems are not one thing turned."""
    flat = [t for t in turns if not t.slope]
    if len({(t.word, t.number) for t in flat}) != len(flat):
        return 0
    words = {t.word for t in flat}
    if "" not in words:
        return len(words) if frozenset(words) in COMPASS_SETS else 0
    if words != {""} or any(t.slope for t in turns):
        return 0
    numbers = frozenset(t.number for t in flat)
    return len(numbers) if numbers in TURN_SETS else 0


def split_joins(stem: str) -> tuple[str, list[str]] | None:
    """``("beachCorner", ["e", "s"])`` for ``beachCornerES``: the name and the sides of its
    diamond a tile joins on, in the order n, e, s, w. None for a stem that ends in no such
    capitals or names a side twice. They are sides only when several files share the name."""
    m = _JOINS.match(stem.strip())
    if m is None:
        return None
    sides = m.group("sides").lower()
    if len(set(sides)) != len(sides):
        return None
    return m.group("base"), [side for side in SIDES if side in sides]


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

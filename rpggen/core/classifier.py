from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen.core import audio_info

MUSIC_MIN_SECONDS = 20.0
MUSIC_NAME_TOKENS = {"music", "bgm", "theme", "song", "ost", "soundtrack", "overworld"}
DIRECTION_LETTERS = {"s", "n", "e", "w"}
MAX_CONFIDENCE = 0.95

# (role, {keyword: weight}) in tie-break order (earlier wins ties).
ROLE_KEYWORDS: list[tuple[str, dict[str, float]]] = [
    ("GROUND", {"grass": 1.0, "ground": 1.0, "dirt": 1.0, "floor": 1.0, "terrain": 1.0, "soil": 1.0, "tile": 1.0, "tiles": 1.0, "tileset": 0.5}),
    ("ROAD", {"road": 1.0, "path": 1.0, "pavement": 1.0, "cobble": 1.0}),
    ("WATER", {"water": 1.0, "sea": 1.0, "lake": 1.0, "river": 1.0, "ocean": 1.0, "pond": 1.0}),
    ("WALL", {"wall": 1.0, "walls": 1.0, "fence": 1.0}),
    ("CLIFF", {"cliff": 1.0, "cliffs": 1.0, "mountain": 1.0, "ledge": 1.0}),
    ("BUILDING", {"house": 1.0, "building": 1.0, "buildings": 1.0, "home": 1.0, "shop": 1.0, "inn": 1.0, "castle": 1.0, "tower": 1.0, "barn": 1.0, "church": 1.0, "hut": 1.0, "tent": 1.0, "store": 1.0}),
    ("DECORATION", {"tree": 1.0, "trees": 1.0, "bush": 1.0, "rock": 1.0, "rocks": 1.0, "stone": 1.0, "flower": 1.0, "plant": 1.0, "prop": 1.0, "props": 1.0, "deco": 1.0, "decor": 1.0, "decoration": 1.0, "decorations": 1.0, "barrel": 1.0, "crate": 1.0, "sign": 1.0, "lamp": 1.0, "statue": 1.0, "well": 1.0, "object": 1.0, "objects": 1.0}),
    ("INTERIOR", {"interior": 1.0, "inside": 1.0, "indoor": 1.0, "room": 1.0, "furniture": 1.0, "inner": 1.0}),
    ("PLAYER", {"player": 1.0, "hero": 1.0, "heroine": 1.0, "protagonist": 1.0, "main": 0.5}),
    ("NPC", {"npc": 1.0, "npcs": 1.0, "villager": 1.0, "merchant": 1.0, "townsfolk": 1.0, "people": 1.0, "citizen": 1.0, "shopkeeper": 1.0, "guard": 1.0, "character": 0.5, "characters": 0.5}),
    ("ENEMY", {"enemy": 1.0, "enemies": 1.0, "monster": 1.0, "monsters": 1.0, "mob": 1.0, "mobs": 1.0, "slime": 1.0, "skeleton": 1.0, "goblin": 1.0, "bat": 1.0, "orc": 1.0, "zombie": 1.0, "bandit": 1.0, "wolf": 1.0, "spider": 1.0}),
    ("BOSS", {"boss": 1.0, "bosses": 1.0}),
    ("ITEM", {"item": 1.0, "items": 1.0, "icon": 1.0, "icons": 1.0, "potion": 1.0, "loot": 1.0, "pickup": 1.0, "gem": 1.0, "coin": 1.0, "key": 1.0, "food": 1.0, "consumable": 1.0}),
    ("WEAPON", {"weapon": 1.0, "weapons": 1.0, "sword": 1.0, "bow": 1.0, "axe": 1.0, "spear": 1.0, "staff": 1.0, "dagger": 1.0}),
    ("EFFECT", {"fx": 1.0, "effect": 1.0, "effects": 1.0, "vfx": 1.0, "explosion": 1.0, "slash": 1.0, "magic": 1.0, "spell": 1.0, "particle": 1.0, "smoke": 1.0, "impact": 1.0}),
    ("PROJECTILE", {"projectile": 1.0, "arrow": 1.0, "bullet": 1.0, "fireball": 1.0, "bolt": 1.0}),
    ("UI", {"ui": 1.0, "gui": 1.0, "hud": 1.0, "button": 1.0, "panel": 1.0, "frame": 1.0, "window": 1.0, "cursor": 1.0, "bar": 1.0, "dialog": 1.0, "dialogue": 1.0, "menu": 1.0}),
    ("PORTRAIT", {"portrait": 1.0, "portraits": 1.0, "face": 1.0, "faces": 1.0, "bust": 1.0}),
    ("BACKGROUND", {"background": 1.0, "backgrounds": 1.0, "bg": 1.0, "parallax": 1.0, "sky": 1.0, "title": 1.0}),
]  # fmt: skip
ROLE_ORDER = [role for role, _ in ROLE_KEYWORDS]
KEYWORD_WEIGHTS = {role: kws for role, kws in ROLE_KEYWORDS}

DEEP_FOLDER_WEIGHT = 1.0
OTHER_FOLDER_WEIGHT = 0.6
FILE_WEIGHT = 0.9

_SPLIT_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SPLIT_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


TYPO_MIN_LETTERS = 6  # shorter words are too close to one another to be folded


def _one_edit_apart(a: str, b: str) -> bool:
    """True when one letter was left out, added or changed between ``a`` and ``b``."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :] if len(a) < len(b) else a[i + 1 :] == b[i + 1 :]


@functools.cache
def _vocabulary() -> frozenset[str]:
    """Every word of the word lists that is long enough to stand for a misspelt one."""
    words: set[str] = set(MUSIC_NAME_TOKENS)
    for _role, keywords in ROLE_KEYWORDS:
        words.update(keywords)
    words |= LIGHT_WORDS | PARALLAX_WORDS | SIDE_VIEW_WORDS | TOP_VIEW_WORDS | {"environment"}
    words.update(SURFACE_WORDS)
    return frozenset(w for w in words if len(w) >= TYPO_MIN_LETTERS)


@functools.cache
def fold_typo(word: str) -> str:
    """The word of the word lists that ``word`` is a slip of the keyboard away from
    (``backgroud`` → ``background``, T16.21), else ``word`` itself. Only words of six letters
    and more, only one letter apart with the first and the last letter in place (a slip is
    made inside a word; ``village`` is not ``villager`` and ``status`` is not ``statue``), only
    when exactly one listed word is that close, and never a plural for its singular."""
    vocabulary = _vocabulary()
    if len(word) < TYPO_MIN_LETTERS or word in vocabulary:
        return word
    near = [
        known
        for known in vocabulary
        if word[0] == known[0]
        and word[-1] == known[-1]
        and _one_edit_apart(word, known)
        and word != known + "s"
        and known != word + "s"
    ]
    return near[0] if len(near) == 1 else word


def _raw_tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    parts: list[str] = []
    for chunk in _SPLIT_NON_ALNUM.split(folded):
        parts.extend(_SPLIT_CAMEL.split(chunk))
    out = []
    for p in parts:
        p = p.lower()
        if not p or p.isdigit():
            continue
        if len(p) == 1 and p not in DIRECTION_LETTERS:
            continue
        out.append(p)
    return out


def _tokenize(text: str) -> list[str]:
    """The words of a folder or file name as artists write them: a leading number (``10. ``),
    ampersands, commas, brackets and emoji only separate, and a misspelt word of the word
    lists is read as the word that was meant."""
    return [fold_typo(word) for word in _raw_tokens(text)]


def folded_typos(posix_path: str) -> dict[str, str]:
    """``{as written: as read}`` for the words of a path that were taken for a typo."""
    out: dict[str, str] = {}
    for part in posix_path.split("/"):
        for word in _raw_tokens(part.rsplit(".", 1)[0] if "." in part else part):
            if fold_typo(word) != word:
                out[word] = fold_typo(word)
    return out


def _path_parts(posix_path: str) -> tuple[list[str], str]:
    parts = [p for p in posix_path.split("/") if p]
    stem = parts[-1].rsplit(".", 1)[0] if parts else ""
    return parts[:-1], stem


# Names of things that give light (T12.62): the "light" tag is suggested for them.
LIGHT_WORDS = frozenset(
    {"torch", "torches", "lamp", "lamps", "lantern", "lanterns", "candle", "candles", "campfire",
     "campfires"}
)  # fmt: skip


# What the ground is made of (T13.16): the footstep the player makes on it. The file's words win
# over its folders', and the nearest folder over the ones above it.
SURFACE_WORDS = ("grass", "stone", "wood", "sand", "water", "snow")


# Side-view words (T14.02): what a platformer's folders and files call their parts. The tags are
# read by the metroidvania's recipes only; the other archetypes ignore them.
SIDE_TAG_WORDS: tuple[tuple[str, frozenset[str]], ...] = (
    ("platform", frozenset({"platform", "platforms", "ledge", "ledges"})),
    ("one_way", frozenset({"oneway", "semi", "semisolid", "jumpthrough"})),
    ("ladder", frozenset({"ladder", "ladders", "rope", "ropes", "vine", "vines"})),
    ("hazard", frozenset({"spike", "spikes", "lava", "thorn", "thorns", "saw", "saws"})),
    ("save_point", frozenset({"save", "savepoint", "checkpoint", "checkpoints", "bench"})),
    ("ability", frozenset({"powerup", "powerups", "upgrade", "upgrades", "ability", "abilities", "orb", "orbs"})),
)  # fmt: skip
# two words that make a tag only together: "one_way", "thin platform", "power_up"
SIDE_TAG_PAIRS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("one_way", ("one", "way")),
    ("one_way", ("thin", "platform")),
    ("one_way", ("thin", "platforms")),
    ("ability", ("power", "up")),
)
PARALLAX_DEPTHS = {"far": 1, "mid": 2, "middle": 2, "near": 3}
PARALLAX_WORDS = frozenset({"bg", "background", "backgrounds", "layer", "parallax"})
_PARALLAX_NUMBER = re.compile(
    r"(?:^|[^a-z])(?:bg|backgrounds?|layer|parallax)[_\- ]?(\d{1,2})(?!\d)", re.IGNORECASE
)
PARALLAX_MAX = 9

SIDE_VIEW_WORDS = frozenset(
    {"platformer", "platformers", "sidescroller", "sidescrolling", "metroidvania", "jump"}
)
TOP_VIEW_WORDS = frozenset({"rpg", "jrpg", "topdown", "overworld"})
SIDE_VIEW_PAIRS = (("side", "scroller"), ("side", "view"), ("side", "scrolling"))
TOP_VIEW_PAIRS = (("top", "down"),)


def _all_words(text: str) -> list[str]:
    """Like _tokenize, but one-letter words and numbers stay out and nothing else is dropped."""
    return [w for w in _tokenize(text) if len(w) > 1]


def _has_pair(words: list[str], pair: tuple[str, str]) -> bool:
    return any(a == pair[0] and b == pair[1] for a, b in zip(words, words[1:], strict=False))


def parallax_depth(path: str) -> int | None:
    """The depth a background's name gives it; 1 is the farthest layer. ``bg_far`` and
    ``background_1`` are 1, ``layer2`` and ``bg_mid`` are 2, ``bg_near`` is 3. None for a name
    that says nothing about depth (a title picture, ``sky.png``)."""
    folders, stem = _path_parts(path)
    words = [w.rstrip("0123456789") for w in _all_words(stem)]  # "layer2" is the word "layer"
    folder_words = set(_all_words(folders[-1])) if folders else set()
    if not (set(words) | folder_words) & PARALLAX_WORDS:
        return None
    for word in words:
        if word in PARALLAX_DEPTHS:
            return PARALLAX_DEPTHS[word]
    numbered = _PARALLAX_NUMBER.search(stem)
    if numbered and 1 <= int(numbered.group(1)) <= PARALLAX_MAX:
        return int(numbered.group(1))
    return None


def side_view_tags(name: str) -> list[str]:
    """The side-view tags the words of a file or an object suggest (T14.02), sorted:
    ``platform``, ``one_way``, ``ladder``, ``hazard``, ``save_point``, ``ability`` and
    ``parallax:<n>``. The name's own words and those of its nearest folder count."""
    path = name if "." in name.rsplit("/", 1)[-1] else name + ".png"
    folders, stem = _path_parts(path)
    found: set[str] = set()
    for words in (_all_words(stem), _all_words(folders[-1]) if folders else []):
        have = set(words)
        for tag, tag_words in SIDE_TAG_WORDS:
            if have & tag_words:
                found.add(tag)
        for tag, pair in SIDE_TAG_PAIRS:
            if _has_pair(words, pair):
                found.add(tag)
    if "one_way" in found:
        found.discard("platform")  # a thin platform is the one-way kind
    depth = parallax_depth(path)
    if depth is not None:
        found.add(f"parallax:{depth}")
    return sorted(found)


def _is_side_sheet(animations: Any) -> bool:
    """A character that jumps or falls and never walks up the screen."""
    if not isinstance(animations, dict) or not animations:
        return False
    actions = {str(name).split("_", 1)[0] for name in animations}
    return bool(actions & {"jump", "fall"}) and not _is_top_sheet(animations)


def _is_top_sheet(animations: Any) -> bool:
    return isinstance(animations, dict) and any(
        str(name) in ("walk_up", "idle_up") for name in animations
    )


def pack_view(inventory: Any, sheets: Any = ()) -> str:
    """``"side"`` or ``"top"``: how a pack looks at its world (T14.02). The words of its folders
    and files count (platformer, sidescroller, metroidvania, jump against rpg, topdown,
    overworld; a name is counted once), and so does every character sheet in ``sheets``
    (detected facets): one with a jump or a fall and no walk up the screen is a side-view
    character, one that walks up the screen a top-down one. A pack that says nothing is
    top-down."""
    side = 0
    top = 0
    seen: set[str] = set()
    for f in getattr(inventory, "files", ()):
        folders, stem = _path_parts(f.path)
        for part in (*folders, stem):
            if part.casefold() in seen:
                continue
            seen.add(part.casefold())
            words = _all_words(part)
            have = set(words)
            if have & SIDE_VIEW_WORDS or any(_has_pair(words, p) for p in SIDE_VIEW_PAIRS):
                side += 1
            if have & TOP_VIEW_WORDS or any(_has_pair(words, p) for p in TOP_VIEW_PAIRS):
                top += 1
    for facets in sheets:
        animations = facets.get("animations") if isinstance(facets, dict) else None
        if _is_side_sheet(animations):
            side += 2
        elif _is_top_sheet(animations):
            top += 2
    return "side" if side > top else "top"


# A sheet whose name is a number and nothing else (``3.png``) says nothing: its folders do
# (T16.21). These words of a folder say what kind of thing the sheet is; the others
# (``medieval``, ``town``) say what is on it and become its tags.
TILE_SHEET_WORDS = frozenset({"tileset", "tilesets", "tile", "tiles", "autotile", "autotiles"})
PACK_FILLER_WORDS = TILE_SHEET_WORDS | frozenset(
    {"pixel", "pixelart", "art", "pack", "packs", "asset", "assets", "bundle", "sprites",
     "sprite", "sheet", "sheets", "the", "and", "of", "for", "by", "px"}
)  # fmt: skip
SHEET_MIN_SIDE = 256  # a numbered picture at least this large is a sheet, never a frame


def is_numbered_name(path: str) -> bool:
    """True for a file whose name is only a number: ``12.png``, ``Town Tileset/ 3 .png``."""
    _folders, stem = _path_parts(path)
    return stem.strip().isdigit()


def folder_words(path: str, pack_words: str = "") -> list[str]:
    """The words the folders of ``path`` give a file that has none of its own, nearest folder
    first; ``pack_words`` is the name of the pack (its folder, when it was added on its own)."""
    folders, _stem = _path_parts(path)
    words: list[str] = []
    for folder in [*reversed(folders), pack_words]:
        for word in _tokenize(folder):
            if word not in words:
                words.append(word)
    return words


def folder_tags(path: str, pack_words: str = "") -> list[str]:
    """What the folders say is on a numbered sheet: their words without those every pack of a
    bundle shares (*pixel art tileset pack*), which say what kind of file it is."""
    return [w for w in folder_words(path, pack_words) if w not in PACK_FILLER_WORDS and len(w) > 2]


# One art, several engines (T16.21): ``engines/Godot/...``, ``engines/RPG_Maker_MV_MZ/...``.
ENGINES_FOLDER = "engines"
UNUSED_OTHER_ENGINE = "other_engine"
UNUSED_OTHER_LAYOUT = "other_layout"
AUTOTILE_FOLDERS = frozenset({"autotile", "autotiles"})
# Godot's two autotile layouts: the 3x3 one is the 47-tile sheet rpggen reads as a terrain.
LAYOUT_KEPT, LAYOUT_DROPPED = "3x3", "2x2"


def _engine_key(folder: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", folder.casefold()).strip("_")


def _engine_parts(path: str, wrapper: str = "") -> tuple[str, list[str]] | None:
    """``(engine folder, the folders below it)`` for a file under ``engines/<Engine>/``."""
    folders, _stem = _path_parts(path)
    if wrapper and folders[:1] == [wrapper]:
        folders = folders[1:]
    for index, folder in enumerate(folders[:-1]):
        if folder.casefold() == ENGINES_FOLDER:
            return folders[index + 1], folders[index + 2 :]
    return None


@dataclass(frozen=True)
class EnginePlan:
    """Which engine's copy of the art a pack is read from."""

    engines: tuple[str, ...]  # the engine folders, as the pack names them
    kept: str  # the one that is used
    godot_autotiles: bool  # Godot's folder has autotiles: the raw templates are not needed
    both_layouts: bool  # ... in both of Godot's layouts

    @property
    def warning(self) -> str:
        """The line for the pack's card: ``engines:5:Godot``."""
        return f"engines:{len(self.engines)}:{self.kept}"


def engine_plan(paths: list[str], wrapper: str = "") -> EnginePlan | None:
    """The plan for a pack that ships its art for two engines or more, else None. Godot's
    folder is used when there is one, else RPG Maker MV's, else another RPG Maker's (the A-sheet
    reader knows those), else the first by name."""
    found: dict[str, str] = {}
    below: dict[str, set[str]] = {}
    for path in paths:
        parts = _engine_parts(path, wrapper)
        if parts is not None:
            found.setdefault(_engine_key(parts[0]), parts[0])
            below.setdefault(_engine_key(parts[0]), set()).update(f.casefold() for f in parts[1])
    if len(found) < 2:
        return None

    def rank(key: str) -> tuple[int, str]:
        if key == "godot":
            return (0, key)
        if key.startswith("rpg_maker"):
            return (1 if "mv" in key or "mz" in key else 2, key)
        return (3, key)

    kept = min(found, key=rank)
    inside = below.get("godot", set()) if kept == "godot" else set()
    return EnginePlan(
        tuple(found[k] for k in sorted(found)),
        found[kept],
        bool(inside & AUTOTILE_FOLDERS),
        LAYOUT_KEPT in inside and LAYOUT_DROPPED in inside,
    )


def not_this_engine(path: str, plan: EnginePlan, wrapper: str = "") -> str | None:
    """Why a picture of a pack with several engine folders is left unused, or None: it is the
    copy for another engine, the other of Godot's two autotile layouts, or the raw autotile
    template the Godot sheets were made from."""
    parts = _engine_parts(path, wrapper)
    if parts is not None:
        if _engine_key(parts[0]) != _engine_key(plan.kept):
            return UNUSED_OTHER_ENGINE
        below = [f.casefold() for f in parts[1]]
        return UNUSED_OTHER_LAYOUT if plan.both_layouts and LAYOUT_DROPPED in below else None
    folders, _stem = _path_parts(path)
    if plan.godot_autotiles and any(f.casefold() in AUTOTILE_FOLDERS for f in folders):
        return UNUSED_OTHER_LAYOUT
    return None


# A copy of a file beside the file (T16.21): ``B-10_副本.jpg`` (*copy*, as a Chinese Windows
# names it), ``tree - Copy.png``, ``tree (copy).png``, ``tree_copy.png``.
UNUSED_COPY = "copy"
_COPY_SUFFIX = re.compile(
    r"^(?P<base>.*?[A-Za-z0-9)])[\s_\-]*(?:[^\x00-\x7f]+|\(copy\)|copy)[\s_\-]*$", re.IGNORECASE
)


def copy_of(path: str, stems: set[tuple[str, str]]) -> str | None:
    """The stem of the file that ``path`` is a copy of, when that file lies beside it, else
    None. ``stems`` holds ``(folder, stem)`` of the pack's pictures, both case-folded."""
    folders, stem = _path_parts(path)
    m = _COPY_SUFFIX.match(stem)
    if m is None:
        return None
    base = m.group("base")
    return base if ("/".join(folders).casefold(), base.casefold()) in stems else None


PREVIEW_FOLDERS = frozenset({"preview", "previews", "screenshot", "screenshots"})
GUIDE_WORDS = frozenset(
    {"preview", "test", "grid", "guide", "slots", "template", "mockup", "showcase"}
)
UNUSED_TAG = "unused_because:"
UNUSED_PREVIEW_FOLDER = "preview_folder"
UNUSED_GUIDE_PICTURE = "guide_picture"


def not_game_art(path: str, wrapper: str = "") -> str | None:
    """Why a picture of a pack is most likely not game art (T16.21), or None: it lies in a
    preview folder, or it is a preview, a test or a layout guide (a picture at the pack's root
    with such a word in its name, or one anywhere whose name is nothing but such words:
    ``Grid Slots.png``). ``path`` is relative to the pack; ``wrapper`` is the one folder an
    archive wraps everything in, which does not count as a folder. Such a picture is unused by
    default, never left out: one click in the audit brings it back."""
    folders, stem = _path_parts(path)
    if wrapper and folders[:1] == [wrapper]:
        folders = folders[1:]
    if any(folder.strip().casefold() in PREVIEW_FOLDERS for folder in folders):
        return UNUSED_PREVIEW_FOLDER
    words = set(_tokenize(stem))
    if words and (words <= GUIDE_WORDS or (not folders and words & GUIDE_WORDS)):
        return UNUSED_GUIDE_PICTURE
    return None


def suggested_tags(name: str) -> list[str]:
    """Tags the name of a file or object suggests: "light" for a torch, lamp, lantern, candle or
    campfire. ``name`` is a path or a plain name."""
    folders, file_tokens = tokens(name if "." in name.rsplit("/", 1)[-1] else name + ".png")
    words = set(file_tokens) | set(folders[-1:])
    return ["light"] if words & LIGHT_WORDS else []


def suggested_surface(path: str) -> str | None:
    """The surface the folder and file words of a ground asset name, or None."""
    folders, file_tokens = tokens(path)
    for words in (file_tokens, *([f] for f in reversed(folders))):
        for word in words:
            if word in SURFACE_WORDS:
                return word
    return None


def tokens(posix_path: str) -> tuple[list[str], list[str]]:
    """(folder tokens, file tokens): split on non-alphanumerics and camelCase, lowercased.

    One-letter tokens survive only as direction letters (s, n, e, w); pure numbers are dropped.
    """
    folders, stem = _path_parts(posix_path)
    folder_tokens: list[str] = []
    for folder in folders:
        folder_tokens.extend(_tokenize(folder))
    return folder_tokens, _tokenize(stem)


def audio_duration(path: Path) -> float | None:
    """Duration in seconds (WAV, OGG, MP3, FLAC); None when unknown."""
    return audio_info.duration_seconds(path)


def _has_directional_animations(facets: dict[str, Any]) -> bool:
    anims = facets.get("animations") or {}
    return any(name.rsplit("_", 1)[-1] in ("down", "up", "left", "right") for name in anims)


def classify(
    fragment_facets: dict[str, Any], path: str, analysis: dict[str, Any] | None
) -> tuple[str, float, list[list[Any]]]:
    """Returns ``(role, confidence, roles_alt)`` for an asset without an adapter-assigned role."""
    analysis = analysis or {}
    kind = analysis.get("kind")
    usage = fragment_facets.get("usage")
    folders, stem = _path_parts(path)
    file_tokens = _tokenize(stem)

    if kind == "font" or usage == "font":
        return "FONT", 1.0, []
    if kind == "audio" or usage == "audio":
        duration = analysis.get("duration_s")
        name_tokens = set(file_tokens) | {t for f in folders for t in _tokenize(f)}
        is_music = (duration is not None and duration >= MUSIC_MIN_SECONDS) or bool(
            name_tokens & MUSIC_NAME_TOKENS
        )
        return ("AUDIO_MUSIC" if is_music else "AUDIO_SFX"), 0.9, []

    deep_folders = folders[-2:]
    deep_tokens = {t for f in deep_folders for t in _tokenize(f)}
    other_tokens = {t for f in folders[:-2] for t in _tokenize(f)}

    scores = {role: 0.0 for role in ROLE_ORDER}
    for role, keywords in ROLE_KEYWORDS:
        for kw, weight in keywords.items():
            mult = 0.0
            if kw in deep_tokens:
                mult = DEEP_FOLDER_WEIGHT
            elif kw in other_tokens:
                mult = OTHER_FOLDER_WEIGHT
            if kw in file_tokens:
                mult = max(mult, FILE_WEIGHT)
            scores[role] += weight * mult

    if usage == "tiles":
        scores["GROUND"] += 0.6
        scores["DECORATION"] += 0.2
        scores["WALL"] += 0.1
    if usage == "sprite":
        w, h = (fragment_facets.get("frame") or [0, 0])[:2]
        if _has_directional_animations(fragment_facets):
            scores["NPC"] += 0.5
            scores["PLAYER"] += 0.1
        elif w and h and w <= 32 and h <= 32:
            scores["ITEM"] += 0.4
    if usage == "background":
        scores["BACKGROUND"] += 1.0
    if usage == "portrait":
        scores["PORTRAIT"] += 1.0
    if fragment_facets.get("nine_slice") or analysis.get("nine_slice"):
        scores["UI"] += 0.8

    ranked = sorted(ROLE_ORDER, key=lambda r: (-scores[r], ROLE_ORDER.index(r)))
    best = ranked[0]
    s1, s2 = scores[best], scores[ranked[1]]
    if s1 <= 0.0:
        return "DECORATION", 0.1, []
    denominator = s1 + s2 + 0.5
    confidence = min(MAX_CONFIDENCE, max(0.0, s1 / denominator))
    alt = [[r, round(scores[r] / denominator, 6)] for r in ranked[1:4] if scores[r] > 0]
    return best, round(confidence, 6), alt

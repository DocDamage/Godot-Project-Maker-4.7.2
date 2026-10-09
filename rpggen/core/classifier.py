from __future__ import annotations

import re
import unicodedata
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


def _tokenize(text: str) -> list[str]:
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

"""Sound slots: which audio asset plays where in the generated game (T11.20).

A fixed list of slots, each filled by one audio asset or left empty. ``default_sounds`` picks an
asset per slot from file-name tokens, ``resolve_sounds`` keeps the user's choices, drops stale
ones and fills the gaps (the same shape as ``mapping.default_starter`` / ``resolve_starter``).
Audio is never required and there are no audio placeholders: an empty slot is silent.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpggen.core import catalog as catalog_mod
from rpggen.core import classifier

MUSIC = "music"
SFX = "sfx"
_INACTIVE = {"UNUSED", "MISSING"}
ROLE_OF_KIND = {MUSIC: "AUDIO_MUSIC", SFX: "AUDIO_SFX"}


@dataclass(frozen=True)
class Slot:
    key: str
    kind: str  # "music" or "sfx"
    label: str
    help: str
    tokens: tuple[str, ...]  # file-name tokens, first hit wins (in this order)


SLOTS: tuple[Slot, ...] = (
    Slot("music_map", MUSIC, "Map music", "Plays on the maps.",
         ("town", "village", "overworld", "field", "map", "theme")),
    Slot("music_battle", MUSIC, "Battle music", "Plays during battles.",
         ("battle", "fight", "combat", "boss")),
    Slot("music_title", MUSIC, "Title music", "Plays on the title screen.",
         ("title", "menu", "intro")),
    Slot("sfx_ui_move", SFX, "Menu cursor", "Moving through a menu.",
         ("cursor", "move", "select", "tick", "hover")),
    Slot("sfx_ui_confirm", SFX, "Menu confirm", "Choosing a menu entry.",
         ("confirm", "accept", "ok", "click")),
    Slot("sfx_ui_cancel", SFX, "Menu cancel", "Going back in a menu.",
         ("cancel", "back", "close")),
    Slot("sfx_hit", SFX, "Hit", "Something is hurt.",
         ("hit", "hurt", "damage", "impact", "slash")),
    Slot("sfx_attack", SFX, "Attack", "An attack starts.",
         ("attack", "swing", "sword", "whoosh")),
    Slot("sfx_pickup", SFX, "Pick up", "An item or coin is picked up.",
         ("pickup", "coin", "item", "collect")),
    Slot("sfx_chest", SFX, "Chest", "A chest opens.",
         ("chest", "open", "unlock")),
    Slot("sfx_door", SFX, "Door", "A door or stairs are used.",
         ("door", "enter", "stairs")),
    Slot("sfx_step", SFX, "Footstep", "The player walks.",
         ("step", "footstep", "walk")),
    Slot("sfx_save", SFX, "Save", "The game is saved.",
         ("save",)),
    Slot("sfx_levelup", SFX, "Level up", "The player levels up.",
         ("levelup", "level", "fanfare", "victory")),
)  # fmt: skip
SLOT_KEYS = tuple(s.key for s in SLOTS)
_BY_KEY = {s.key: s for s in SLOTS}


def slot(key: str) -> Slot:
    return _BY_KEY[key]


def audio_assets(catalog: catalog_mod.Catalog, kind: str) -> list[catalog_mod.Asset]:
    """Active audio assets of one kind, sorted by id."""
    role = ROLE_OF_KIND[kind]
    return [
        a
        for a in sorted(catalog.assets, key=lambda a: a.id)
        if a.kind == "audio"
        and a.status not in _INACTIVE
        and catalog_mod.effective(a).get("role") == role
    ]


def duration_of(asset: catalog_mod.Asset) -> float | None:
    audio = catalog_mod.effective(asset).get("audio") or {}
    value = audio.get("duration_s") if isinstance(audio, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def _name_tokens(asset: catalog_mod.Asset) -> set[str]:
    stem = asset.path.rsplit("/", 1)[-1]
    return set(classifier.tokens(f"x/{stem}")[1])


def _by_tokens(slot_def: Slot, pool: list[catalog_mod.Asset]) -> str | None:
    named = [(a, _name_tokens(a)) for a in pool]
    for token in slot_def.tokens:
        for asset, tokens in named:
            if token in tokens:
                return asset.id
    return None


def _longest(pool: list[catalog_mod.Asset]) -> str | None:
    if not pool:
        return None
    ranked = sorted(pool, key=lambda a: (-(duration_of(a) or 0.0), a.id))
    return ranked[0].id


def default_sounds(catalog: catalog_mod.Catalog) -> dict[str, str]:
    """An asset per slot where the packs have a plausible one (file-name tokens; the map music
    falls back to the longest music track and the title music to the map music)."""
    music = audio_assets(catalog, MUSIC)
    sfx = audio_assets(catalog, SFX)
    out: dict[str, str] = {}
    for s in SLOTS:
        found = _by_tokens(s, music if s.kind == MUSIC else sfx)
        if found is None and s.key == "music_map":
            found = _longest(music)
        if found is None and s.key == "music_title":
            found = out.get("music_map")
        if found is not None:
            out[s.key] = found
    return out


def valid_choice(catalog: catalog_mod.Catalog, key: str, asset_id: str | None) -> bool:
    if not asset_id or key not in _BY_KEY:
        return False
    asset = catalog.asset(asset_id)
    return asset is not None and any(
        a.id == asset_id for a in audio_assets(catalog, _BY_KEY[key].kind)
    )


CLEARED = ""  # a slot the user emptied on purpose: it stays silent instead of getting a default


def resolve_sounds(catalog: catalog_mod.Catalog, current: dict[str, str]) -> dict[str, str]:
    """``current`` with stale entries dropped and gaps filled with the default choice. A slot
    that is ``CLEARED`` stays cleared."""
    defaults = default_sounds(catalog)
    out: dict[str, str] = {}
    for s in SLOTS:
        chosen = current.get(s.key)
        if chosen == CLEARED and s.key in current:
            out[s.key] = CLEARED
        elif valid_choice(catalog, s.key, chosen):
            out[s.key] = chosen  # type: ignore[assignment]
        elif s.key in defaults:
            out[s.key] = defaults[s.key]
    return out


def summary(sounds: dict[str, str]) -> str:
    """ "3 music tracks, 14 sound effects assigned" for the collapsed Mapping group."""
    music = sum(1 for k, v in sounds.items() if v and k in _BY_KEY and _BY_KEY[k].kind == MUSIC)
    sfx = sum(1 for k, v in sounds.items() if v and k in _BY_KEY and _BY_KEY[k].kind == SFX)
    tracks = f"{music} music track{'s' if music != 1 else ''}"
    effects = f"{sfx} sound effect{'s' if sfx != 1 else ''}"
    return f"{tracks}, {effects} assigned"
